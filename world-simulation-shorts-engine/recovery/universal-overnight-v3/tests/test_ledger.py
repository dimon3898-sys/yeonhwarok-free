"""Focused 151 / 53 recount and evidence-boundary tests."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("overnight_ledger_tests", ROOT / "tools/build_ledger.py")
OWNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OWNER)


class LedgerTest(unittest.TestCase):
    def test_all_identities_preserved_and_original_33_individually_reviewed(self):
        ledger, unwired, remaining = OWNER.build()
        self.assertEqual(ledger["featureCount"], 151)
        self.assertEqual(unwired["count"], 53)
        self.assertEqual(remaining["count"], 33)
        self.assertEqual(sum(ledger["statusCounts"].values()), 151)
        self.assertEqual({r["id"] for r in remaining["features"]}, set(OWNER.GAPS))

    def test_no_source_or_cpu_claim_promoted_to_output(self):
        ledger, _, _ = OWNER.build()
        self.assertEqual(ledger["actualOutputAppliedCount"], 0)
        self.assertEqual(ledger["gpuProofCount"], 0)
        self.assertFalse(ledger["full80sRenderAllowed"])
        self.assertTrue(all(r["gpuProof"] == "NOT_VERIFIED" for r in ledger["features"]))

    def test_source_reference_path_escape_rejected(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_PATH"):
            OWNER.checked_reference({"path": "world-simulation-shorts-engine/../secret", "sha256": "0" * 64})

    def test_source_reference_hash_mismatch_rejected(self):
        value = OWNER.reference(ROOT / "data_readiness.py")
        value["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
            OWNER.checked_reference(value)

    def test_unknown_or_duplicate_evidence_not_ignored(self):
        with self.assertRaisesRegex(ValueError, "NEW_FEATURE"):
            OWNER._validate_evidence({"schema": "WORLD_ENGINE_OVERNIGHT_FEATURE_EVIDENCE_V1", "features": [{"featureId": "UNKNOWN"}]}, set())

    def test_arbitrary_unknown_fields_rejected(self):
        with self.assertRaisesRegex(ValueError, "SCHEMA"):
            OWNER._validate_evidence({"schema": "WORLD_ENGINE_OVERNIGHT_FEATURE_EVIDENCE_V1", "features": [], "gpuPass": True}, set())

    def test_no_feature_axis_dropped(self):
        ledger, _, _ = OWNER.build()
        self.assertEqual(len(ledger["featureAxisNames"]), 8)
        self.assertTrue(all(all(key in row for key in OWNER.FEATURE_AXES) for row in ledger["features"]))

    def test_csv_retains_one_row_per_identity(self):
        ledger, _, _ = OWNER.build()
        self.assertEqual(len(OWNER.csv_rows(ledger["features"]).splitlines()), 152)


if __name__ == "__main__":
    unittest.main()
