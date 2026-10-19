"""Focused CPU data-admission tests; no new coordinates or media are produced."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("completion_history_admission", ROOT / "history_admission.py")
history = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(history)
DATA = ROOT.parent / "verified-front-data-v4-recovery"
COVERAGE = ROOT.parent / "universal-integration-v1/reports/TIMELINE_80S_COVERAGE.json"


class HistoryAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((DATA / "VIDEO_PLAN_80S.json").read_text())
        cls.front = json.loads((DATA / "FRONT_PROFILE.json").read_text())
        cls.coverage = json.loads(COVERAGE.read_text())

    def assess(self, **kwargs):
        return history.assess_history(kwargs.pop("plan", self.plan), kwargs.pop("front", self.front),
                                      coverage=kwargs.pop("coverage", self.coverage), **kwargs)

    def test_qualified_plan_is_not_blocked_for_lack_of_survey_or_daily_fronts(self):
        result = history.load_default_admission()
        self.assertTrue(result["dataAdmitted"])
        self.assertTrue(result["qualifiedBasePlanAdmitted"])
        self.assertEqual(result["grade"], "FACT_BASED_VISUAL_GRADE")
        self.assertEqual(result["essentialDataBlockers"], [])
        self.assertEqual(result["status"], "QUALIFIED_DATA_ADMITTED")
        self.assertEqual(result["summary"]["archivalPartialHoldFrames"], 850)
        self.assertEqual(result["summary"]["schematicContextFrames"], 1550)
        self.assertTrue(result["sourceChecks"]["actualPrimaryPlanProfileManifestParentBytesVerified"])

    def test_all_chapters_and_exact_frame_coverage_preserved(self):
        result = self.assess()
        self.assertEqual((result["chapterCount"], result["totalFrames"], result["fps"]), (12, 2400, 30))
        self.assertEqual(sum(row["frames"] for row in result["chapterCoverage"]), 2400)
        self.assertEqual([row["front"]["archivalPartialHoldFrames"] for row in result["chapterCoverage"]],
                         [0] * 7 + [50, 200, 200, 200, 200])
        self.assertTrue(all(not row["territory"]["opponentComplementAllowed"] for row in result["chapterCoverage"]))
        self.assertTrue(all(not part["areasAllowed"] for row in result["chapterCoverage"]
                            for part in row["sourceSegments"] if part["kind"] == "ARCHIVAL_PARTIAL_FRONT_HOLD"))

    def test_approximate_original_endpoint_presentation_has_explicit_semantics(self):
        result = self.assess()
        policy = result["endpointTransitions"]
        self.assertTrue(policy["schematicOriginalEndpointAlphaAllowed"])
        self.assertTrue(policy["partialFrontOriginalGeometryCrossfadeDataAllowed"])
        self.assertFalse(policy["intermediateObservedFrontClaimAllowed"])
        self.assertFalse(policy["vertexMorphOrGapBridgingAllowed"])
        self.assertFalse(policy["inferredOccupationFillAllowed"])
        self.assertEqual(policy["partialFrontCrossfadeRendererConnected"], "NOT_VERIFIED")

    def test_missing_optional_data_blocks_requested_feature_only(self):
        expected = {
            "nationalUnits": "DATED_HISTORICAL_UNIT_POSITIONS_MISSING",
            "movingUnits": "HISTORICAL_UNIT_TRACKS_MISSING",
            "completeOccupation": "COMPLETE_BILATERAL_OWNERSHIP_MISSING",
            "observedDailyFronts": "OBSERVED_DAILY_FRONT_SEQUENCE_MISSING",
            "routes": "HISTORICAL_ROUTE_GEOMETRY_MISSING",
            "combatImpacts": "SOURCED_COMBAT_LOCATION_EVENT_MISSING",
            "fullSceneHighDetail": "FULL_SCENE_DEM_DEPTH_SUPPORT_MISSING",
        }
        for capability, code in expected.items():
            with self.subTest(capability=capability):
                result = self.assess(requested={capability: True})
                self.assertFalse(result["dataAdmitted"])
                self.assertTrue(result["qualifiedBasePlanAdmitted"])
                self.assertEqual([row["code"] for row in result["essentialDataBlockers"]], [code])

    def test_partial_chronology_does_not_become_exact_day_proof(self):
        result = self.assess()
        self.assertEqual(result["partialExactDateChapterIds"], ["chapter-05", "chapter-07"])
        exact = self.assess(requested={"exactEventDates": True})
        self.assertFalse(exact["dataAdmitted"])
        self.assertEqual(exact["essentialDataBlockers"][0]["code"], "EXACT_EVENT_DATE_PROOF_PARTIAL")
        self.assertFalse(result["chapterCoverage"][8]["sourceSegments"][0]["exactEventDateMatch"])

    def test_unknown_and_nonboolean_requests_are_rejected(self):
        for request in ({"inventUnits": True}, {"nationalUnits": "false"}, {"completeOccupation": 1}):
            with self.subTest(request=request), self.assertRaisesRegex(history.HistoryAdmissionError, "HISTORY_REQUEST_FIELD_OR_TYPE_UNSUPPORTED"):
                self.assess(requested=request)

    def test_stale_coverage_or_wrong_source_binding_rejected(self):
        coverage = deepcopy(self.coverage)
        coverage["rows"][0]["front"]["archivalPartialHoldFrames"] = 200
        with self.assertRaisesRegex(history.HistoryAdmissionError, "HISTORY_PRESERVED_COVERAGE_MISMATCH"):
            self.assess(coverage=coverage)
        bindings = deepcopy(self.coverage["inputBindings"])
        bindings["FRONT_PROFILE.json"] = "0" * 64
        with self.assertRaisesRegex(history.HistoryAdmissionError, "HISTORY_SOURCE_BINDING_SHA_MISMATCH"):
            self.assess(source_bindings=bindings)

    def test_false_faction_or_attack_arrow_role_is_not_admitted(self):
        plan = deepcopy(self.plan)
        plan["productionV3"]["visualBindings"]["areaStyles"][0]["enemyComplementAdmitted"] = True
        with self.assertRaisesRegex(history.HistoryAdmissionError, "HISTORY_SOURCE_QUALIFIED_HELD_CORE_REQUIRED"):
            self.assess(plan=plan)
        front = deepcopy(self.front)
        front["fronts"][0]["source"]["classification"] = "ATTACK_ARROW"
        with self.assertRaisesRegex(history.HistoryAdmissionError, "HISTORY_REVIEWED_PARTIAL_FRONT_PROOF_REQUIRED"):
            self.assess(front=front)

    def test_no_mutation_no_render_authorization_no_country_branch(self):
        original = deepcopy((self.plan, self.front))
        result = self.assess()
        self.assertEqual(original, (self.plan, self.front))
        self.assertFalse(result["renderAllowed"])
        self.assertFalse(result["gpuOutputVerified"])
        self.assertFalse(result["userQualityApproved"])
        self.assertFalse(result["newHistoricalCoordinatesCreated"])
        self.assertTrue(all(row["actualRenderedOutputStatus"] == "NOT_VERIFIED" for row in result["chapterCoverage"]))
        plan = deepcopy(self.plan)
        plan["subjectId"] = "OTHER_SUBJECT_METADATA"
        self.assertEqual(self.assess(plan=plan)["summary"], result["summary"])


if __name__ == "__main__":
    unittest.main()
