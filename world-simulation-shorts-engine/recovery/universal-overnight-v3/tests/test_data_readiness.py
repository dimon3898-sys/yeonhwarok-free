"""Focused authority/role tests; no acquisition, GPU or old-suite rerun."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("overnight_data_readiness_test", ROOT / "data_readiness.py")
OWNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OWNER)


class ReadinessTest(unittest.TestCase):
    def test_exact_existing_history_and_regional_masks(self):
        result = OWNER.assess_existing_data()
        self.assertTrue(result["requestedCapabilitiesAdmitted"])
        self.assertTrue(result["sourceBytesVerified"])
        self.assertFalse(result["renderAllowed"])
        self.assertEqual(result["dataAdmission"]["summary"]["archivalSnapshotCount"], 8)
        self.assertEqual(result["dataAdmission"]["summary"]["suppliedSchematicStateCount"], 5)
        self.assertFalse(result["dataAdmission"]["assets"]["fullSceneCoverageVerified"])

    def test_missing_national_units_blocks_only_requested_capability(self):
        result = OWNER.assess_existing_data(requested={"nationalUnits": True})
        self.assertTrue(result["qualifiedBasePlanAdmitted"])
        self.assertFalse(result["requestedCapabilitiesAdmitted"])
        self.assertEqual(result["dataAdmission"]["essentialDataBlockers"][0]["code"],
                         "DATED_HISTORICAL_UNIT_POSITIONS_MISSING")

    def test_routes_cannot_be_fabricated_from_city_geometry(self):
        catalog = OWNER.load_existing_catalog()
        row = catalog["trustedSources"][0]
        with self.assertRaisesRegex(OWNER.DataReadinessError, "ROLE_OR_REVIEW"):
            OWNER.resolve_source_reference(catalog, {"sourceId": row["sourceId"], "sha256": row["sha256"]},
                                           expected_role="FLOW_PLAN")

    def test_exact_geometry_is_source_bound(self):
        catalog = OWNER.load_existing_catalog()
        row = catalog["trustedSources"][0]
        payload = OWNER.resolve_source_reference(catalog,
            {"sourceId": row["sourceId"], "sha256": row["sha256"]}, expected_role="GEOMETRY")
        self.assertEqual(payload, row["payload"])
        self.assertIsNot(payload, row["payload"])

    def test_duplicate_authority_is_rejected(self):
        catalog = OWNER.load_existing_catalog()
        row = catalog["trustedSources"][0]
        catalog["trustedSources"].append(copy.deepcopy(row))
        with self.assertRaisesRegex(OWNER.DataReadinessError, "NOT_UNIQUE"):
            OWNER.resolve_source_reference(catalog,
                {"sourceId": row["sourceId"], "sha256": row["sha256"]}, expected_role="GEOMETRY")

    def test_payload_tampering_is_rejected(self):
        catalog = OWNER.load_existing_catalog()
        row = catalog["trustedSources"][0]
        reference = {"sourceId": row["sourceId"], "sha256": row["sha256"]}
        row["payload"] = {"type": "Point", "coordinates": [0, 0]}
        with self.assertRaisesRegex(OWNER.DataReadinessError, "PAYLOAD_SHA"):
            OWNER.resolve_source_reference(catalog, reference, expected_role="GEOMETRY")

    def test_unknown_capability_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError, "REQUEST_FIELD"):
            OWNER.assess_existing_data(requested={"inventRoutes": True})

    def test_changed_execution_plan_cannot_use_original_source_receipt(self):
        plan = json.loads((ROOT.parent / "verified-front-data-v4-recovery/VIDEO_PLAN_80S.json").read_text())
        plan["durationSeconds"] = 80.5
        with self.assertRaisesRegex(ValueError, "DIFFERS_FROM_VERIFIED_SOURCE"):
            OWNER.assess_existing_data(plan=plan)


if __name__ == "__main__":
    unittest.main()
