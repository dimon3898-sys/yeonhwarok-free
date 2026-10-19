"""CPU-only source/clock regression, with no media generation or GPU access."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("integration_data_coverage", ROOT / "data_coverage.py")
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)
DATA = ROOT.parent / "verified-front-data-v4-recovery"


class DataCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((DATA / "VIDEO_PLAN_80S.json").read_text())
        cls.front = json.loads((DATA / "FRONT_PROFILE.json").read_text())
        cls.review = json.loads((DATA / "SCENE_EVIDENCE_CONNECTION.json").read_text())

    def build(self, plan=None, front=None):
        return coverage.build_coverage(plan or self.plan, front or self.front, chronology_review=self.review)

    def test_exact_supplied_partition_and_receipt_counts(self):
        report = self.build()
        self.assertEqual((report["totalFrames"], report["chapterCount"], report["workSegmentCount"]), (2400, 12, 12))
        self.assertEqual(report["summary"]["archivalPartialHoldFrames"], self.review["sourceFrameCount"])
        self.assertEqual(report["summary"]["schematicContextFrames"], self.review["schematicContextFrameCount"])
        self.assertEqual(report["summary"]["archivalSnapshotCount"], 8)
        self.assertEqual(report["summary"]["suppliedSchematicStateCount"], 5)
        self.assertEqual(sum(row["frames"] for row in report["rows"]), 2400)

    def test_archive_precedence_suppresses_occupation_fill(self):
        rows = self.build()["rows"]
        self.assertEqual([row["front"]["archivalPartialHoldFrames"] for row in rows], [0] * 7 + [50, 200, 200, 200, 200])
        self.assertEqual(rows[7]["territory"]["schematicCrossfadeFrames"], 100)
        self.assertEqual(rows[11]["territory"]["schematicCrossfadeFrames"], 0)
        self.assertEqual(rows[11]["territory"]["visibleSchematicAreaFrames"], 0)
        self.assertTrue(all(not part["areasAllowed"] for row in rows for part in row["segments"]
                            if part["kind"] == "ARCHIVAL_PARTIAL_FRONT_HOLD"))

    def test_map_date_and_event_date_are_not_conflated(self):
        row = self.build()["rows"][8]
        part = row["segments"][0]
        self.assertEqual((part["mapDate"], part["eventDate"]), ("1951-01-24", "1951-01-25"))
        self.assertFalse(part["exactEventDateMatch"])
        self.assertIn("NOT_VERIFIED", self.build()["rows"][4]["chronology"]["status"])

    def test_no_mutation_or_render_authorization(self):
        before = deepcopy((self.plan, self.front))
        report = self.build()
        self.assertEqual(before, (self.plan, self.front))
        self.assertFalse(report["renderAllowed"])
        self.assertFalse(report["actual80SecondOutputVerified"])
        self.assertEqual(report["summary"]["verifiedHistoricalNationalUnitTracks"], 0)
        self.assertFalse(report["newHistoricalCoordinatesCreated"])
        self.assertTrue(all(row["outputStatus"] == "NOT_VERIFIED" for row in report["rows"]))

    def test_generic_input_has_no_subject_or_country_requirement(self):
        plan = deepcopy(self.plan)
        plan["subjectId"] = "UNRELATED_SUBJECT"
        plan["topic"] = "unrelated hypothetical caller metadata"
        self.assertEqual(self.build(plan=plan)["summary"], self.build()["summary"])

    def test_gaps_overlaps_and_work_segment_gaps_fail_closed(self):
        for field in ("eventChapters", "geometrySchedule"):
            with self.subTest(field=field):
                plan = deepcopy(self.plan)
                plan["productionV3"][field][1]["startFrame"] += 1
                with self.assertRaisesRegex(coverage.CoverageError, "COVERAGE_HALF_OPEN_PARTITION_INVALID"):
                    self.build(plan=plan)
        plan = deepcopy(self.plan)
        plan["scenes"][1]["startFrame"] -= 1
        with self.assertRaisesRegex(coverage.CoverageError, "COVERAGE_HALF_OPEN_PARTITION_INVALID"):
            self.build(plan=plan)

    def test_invalid_source_binding_or_future_date_rejected(self):
        for change in ("frontId", "eventDate", "chapterId"):
            front = deepcopy(self.front)
            front["schedule"][0][change] = {"frontId": "unknown", "eventDate": "1950-01-01", "chapterId": "wrong"}[change]
            with self.subTest(change=change), self.assertRaises(coverage.CoverageError):
                self.build(front=front)

    def test_interpolation_and_inferred_territory_policies_rejected(self):
        for key in ("inferOccupiedAreas", "interpolateUnobservedDates", "exactMilitaryDemarcationLineClaimed"):
            front = deepcopy(self.front)
            front["semanticPolicy"][key] = True
            with self.subTest(key=key), self.assertRaisesRegex(coverage.CoverageError, "COVERAGE_NO_INFERRED_HISTORY_REQUIRED"):
                self.build(front=front)

    def test_regional_assets_do_not_become_full_coverage(self):
        assets = {"sources": {"terrain": {"sourceId": "regional-fixture", "coverage": {"sourceBBox": [-70, -40, -69, -39]}}}}
        report = coverage.build_coverage(self.plan, self.front, asset_metadata=assets)
        self.assertEqual(report["assets"]["sources"]["terrain"]["sourceBBox"], [-70, -40, -69, -39])
        self.assertFalse(report["assets"]["fullSceneCoverageVerified"])
        self.assertEqual(report["rows"][0]["chronology"]["status"], "NOT_VERIFIED")
        assets["sources"]["terrain"]["coverage"]["sourceBBox"] = [0, 0, 360, 90]
        with self.assertRaisesRegex(coverage.CoverageError, "COVERAGE_ASSET_BBOX_INVALID"):
            coverage.build_coverage(self.plan, self.front, asset_metadata=assets)


if __name__ == "__main__":
    unittest.main()
