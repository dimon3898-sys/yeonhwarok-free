"""CPU-only evidence integrity checks for the 151/53 decision reports."""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("integration_feature_decisions", ROOT / "feature_decisions.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FeatureDecisionIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog, cls.catalog_sha = module.load_catalog()
        cls.decisions = module.build_decisions(cls.catalog, cls.catalog_sha)
        cls.by_id = {f["id"]: f for f in cls.decisions["features"]}

    def test_all_151_exact_original_records_are_preserved(self):
        self.assertEqual(len(self.by_id), 151)
        for original in self.catalog["features"]:
            with self.subTest(feature=original["id"]):
                reviewed = copy.deepcopy(self.by_id[original["id"]])
                reviewed.pop("integrationReview")
                self.assertEqual(reviewed, original)

    def test_all_53_not_wired_are_reviewed_exactly_once(self):
        report = module.unwired_report(self.decisions)
        expected = {f["id"] for f in self.catalog["features"] if f["classification"] == "NOT_WIRED"}
        self.assertEqual(len(expected), 53)
        self.assertEqual({f["id"] for f in report["features"]}, expected)
        self.assertEqual(report["count"], 53)
        self.assertTrue(report["allReviewed"])

    def test_no_fabricated_applied_or_output_claim(self):
        self.assertNotIn("APPLIED", self.decisions["summary"])
        self.assertFalse(self.decisions["full80sRenderAllowed"])
        for f in self.decisions["features"]:
            with self.subTest(feature=f["id"]):
                r = f["integrationReview"]
                self.assertFalse(r["candidateOutputVerified"])
                self.assertEqual(r["executionTrace"]["actualCandidateRendererCalled"], "NOT_EXECUTED")
                self.assertEqual(r["executionTrace"]["actualCandidateOutput"], "NOT_PRODUCED")
                self.assertFalse(r["executionTrace"]["actual80sArtifactCompared"])

    def test_every_decision_has_specific_reason_action_and_source_trace(self):
        for f in self.decisions["features"]:
            with self.subTest(feature=f["id"]):
                r = f["integrationReview"]
                self.assertIn(r["status"], module.VALID_STATUSES)
                self.assertIn(r["relevance"], module.VALID_RELEVANCE)
                self.assertGreater(len(r["reason"]), 40)
                self.assertGreater(len(r["nextAction"]), 25)
                self.assertEqual(r["executionTrace"]["historicalSourceEvidenceIds"], [e["evidenceId"] for e in f["evidence"]])
                self.assertEqual(r["reviewedOriginalInput"], f["input"])
                self.assertEqual(r["reviewedDataDependencies"], f["dependencies"])

    def test_missing_required_historical_movement_is_not_disguised_as_unrelated(self):
        required_blocked = {
            "FLOW.MOVING_OBJECT", "FLOW.DIRECTIONAL_FLOW", "FLOW.ENDPOINT_PULSE",
            "FLOW.HEADING", "FLOW.ROUTE_HOLD", "FLOW.ROUTE_REVEAL",
            "FLOW.VISUAL_POLISH_PROFILE", "UNITS.NATIONAL_TABLETS",
            "UNITS.SAFE_STATIC_SCALE", "PLANNER.CAUSAL_TRACKS",
            "AREA.GROW", "AREA.CONTRACT", "AREA.MOVE",
            "TERRITORY.COMPLEMENTARY_SCALAR_CONTROL",
            "TERRITORY.SUPPLIED_AREA_COLOR",
        }
        for feature_id in required_blocked:
            with self.subTest(feature=feature_id):
                r = self.by_id[feature_id]["integrationReview"]
                self.assertEqual((r["relevance"], r["status"]), ("REQUIRED", "BLOCKED"))
                self.assertIn(feature_id, self.decisions["requiredBlockers"])

    def test_unrelated_disaster_audio_and_metric_are_explicit_not_applicable(self):
        for feature_id in ("WAVE.IRREGULAR_OPEN_FRONTS", "AREA.PROPAGATION_RING", "AREA.PROPAGATION_WAVE", "AUDIO.LEGACY_BGM", "AUDIO.LEGACY_TTS", "AUDIO.LEGACY_SUBTITLES", "PLANNER.FAMILY_LINE_METRIC"):
            with self.subTest(feature=feature_id):
                self.assertEqual(self.by_id[feature_id]["integrationReview"]["status"], "NOT_APPLICABLE")
        self.assertEqual(self.by_id["EVENT.GEOGRAPHIC_LINE_ARCLENGTH"]["integrationReview"]["status"], "SUPPORTING")
        self.assertEqual(self.by_id["EVENT.METRIC_GLYPH_PRIMITIVE"]["integrationReview"]["status"], "SUPPORTING")

    def test_aliases_are_preserved_and_not_counted_as_independent_engines(self):
        for group in self.catalog["overlapGroups"]:
            ids = [group["canonical"], *group["records"]]
            for feature_id in ids:
                with self.subTest(feature=feature_id):
                    r = self.by_id[feature_id]["integrationReview"]
                    self.assertEqual(r["canonicalId"], group["canonical"])
                    self.assertEqual(r["aliasGroup"], ids)

    def test_old_image_inclusion_is_not_new_candidate_inclusion(self):
        self.assertEqual(self.decisions["baselineOperatingImage"], self.catalog["operatingImage"])
        self.assertEqual(self.decisions["candidateImage"], {"state": "NOT_BUILT", "digest": None})
        for f in self.decisions["features"]:
            with self.subTest(feature=f["id"]):
                r = f["integrationReview"]
                self.assertEqual(r["parentImageMembership"], f["axes"]["BUILT_IN_IMAGE"])
                self.assertFalse(r["candidateExtensionInParentImage"])
                self.assertIsNone(r["candidateImage"]["digest"])

    def test_catalog_is_not_mutated_and_reports_are_deterministic(self):
        before = copy.deepcopy(self.catalog)
        again = module.build_decisions(self.catalog, self.catalog_sha)
        self.assertEqual(again, self.decisions)
        self.assertEqual(before, self.catalog)
        self.assertEqual(hashlib.sha256(module.CATALOG.read_bytes()).hexdigest(), module.CATALOG_SHA256)

    def test_unknown_duplicate_missing_and_unwired_count_changes_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "SHA_MISMATCH"):
            module.build_decisions(self.catalog, "0" * 64)
        duplicate = copy.deepcopy(self.catalog)
        duplicate["features"][-1] = duplicate["features"][0]
        with self.assertRaisesRegex(ValueError, "DISTINCT_IDS"):
            module.build_decisions(duplicate, self.catalog_sha)
        changed_id = copy.deepcopy(self.catalog)
        changed_id["features"][0]["id"] = "UNKNOWN.NEW_FEATURE"
        with self.assertRaisesRegex(ValueError, "ID_SET_MISMATCH"):
            module.build_decisions(changed_id, self.catalog_sha)
        changed_unwired = copy.deepcopy(self.catalog)
        changed_unwired["features"][0]["classification"] = "SCENE_ONLY"
        with self.assertRaisesRegex(ValueError, "53_UNWIRED"):
            module.build_decisions(changed_unwired, self.catalog_sha)

    def test_csv_roundtrips_ids_unicode_reasons_and_json_axes(self):
        rows = list(csv.DictReader(io.StringIO(module.decisions_csv(self.decisions["features"]))))
        self.assertEqual(len(rows), 151)
        self.assertEqual({r["id"] for r in rows}, set(self.by_id))
        for row in rows:
            with self.subTest(feature=row["id"]):
                self.assertEqual(row["reason"], self.by_id[row["id"]]["integrationReview"]["reason"])
                self.assertEqual(json.loads(row["sourceAxes"]), self.by_id[row["id"]]["axes"])
                self.assertEqual(row["candidateOutputVerified"], "False")

    def test_saved_reports_match_generated_decisions_and_have_no_temp_dependency(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            produced = module.write_reports(output)
            self.assertEqual(produced, self.decisions)
            self.assertEqual(json.loads((output / "FEATURE_DECISIONS_151.json").read_text()), produced)
            self.assertEqual(len(json.loads((output / "UNWIRED_REVIEW_53.json").read_text())["features"]), 53)
            self.assertEqual(len(list(csv.DictReader(io.StringIO((output / "UNWIRED_REVIEW_53.csv").read_text())))), 53)
        self.assertFalse(self.decisions["reviewPolicy"]["blindAPIExposureAllowed"])
        self.assertFalse(self.decisions["reviewPolicy"]["missingHistoryMayBeInvented"])


if __name__ == "__main__":
    unittest.main()
