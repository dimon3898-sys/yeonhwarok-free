"""Future-only policy revisions against the real frozen validator/private cache.

All I/O uses UID/GID 1000-owned local test directories. No GPU, remote storage,
existing operator policy, job, approval or claim is read or changed.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PROFILE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_test_future_recovery_policy", PROFILE / "policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class FuturePolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual((os.geteuid(), os.getegid()), (1000, 1000),
                         "Focused policy tests require actual UID/GID 1000")
        self.tmp = tempfile.TemporaryDirectory(prefix="studio-policy-tests-", dir=PROFILE)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.control = self.base / "control"
        self.input = self.base / "input"
        self.control.mkdir(mode=0o700)
        self.input.mkdir(mode=0o700)
        self.now = datetime.now(timezone.utc)
        self.previous = {"schema": "WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1",
                         "validUntil": (self.now + timedelta(hours=8)).isoformat(),
                         "maxWallSeconds": 3600, "maxRetries": 0,
                         "maxCostAmount": "12.00", "currency": "USD", "gpuHourlyRate": "3.00"}
        # Deliberately noncanonical bytes prove that staging preserves raw input.
        self.original = (json.dumps(self.previous, indent=3, sort_keys=False) + "\n").encode()
        self.write(self.control / "operator_policy.json", self.original)
        self.candidate = {**self.previous, "maxWallSeconds": 10800}
        self.candidate_path = self.input / "candidate.json"
        self.write(self.candidate_path, self.candidate)
        self.add_existing_records()

    @staticmethod
    def write(path, value):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        path.write_bytes(data)
        path.chmod(0o600)

    def add_existing_records(self):
        self.protected = {}
        for directory, name, data in (
                ("jobs", "studio-bcd340f797498d7c9fea8181921f91b9.json",
                 b'{ "state": "FAILED", "errorCode": "STUDIO_APPROVED_DEADLINE_EXCEEDED" }\n'),
                ("approvals", "existing-approval.json",
                 b'{ "maxWallSeconds": 3600, "consent": true, "immutable": "existing" }\n'),
                ("runs", "existing-claim.json", b'{ "claim": "retained", "attempt": 1 }\n')):
            folder = self.control / directory
            folder.mkdir(mode=0o700)
            path = folder / name
            self.write(path, data)
            self.protected[path] = data

    def assert_existing_records_untouched(self):
        for path, expected in self.protected.items():
            self.assertEqual(path.read_bytes(), expected, str(path))

    def stage(self):
        return policy.stage_future_policy(self.control, self.candidate_path)

    def revision(self, staged):
        return self.control / "future-policy-revisions" / staged["revisionId"]

    def error(self, expected, action):
        with self.assertRaises(Exception) as caught:
            action()
        self.assertEqual(getattr(caught.exception, "code", None) or str(caught.exception), expected)

    def test_10800_seconds_accepted_by_existing_full_cost_validator(self):
        result = policy.validate_future_policy(self.candidate, self.previous, now=self.now)
        self.assertEqual(result["maxWallSeconds"], 10800)
        self.assertEqual(result["maxCostAmount"], self.previous["maxCostAmount"])
        self.assertEqual(result["maxRetries"], 0)

    def test_insufficient_existing_cost_cap_blocks_three_hours(self):
        old = {**self.previous, "maxCostAmount": "8.99"}
        candidate = {**self.candidate, "maxCostAmount": "8.99"}
        self.error("STUDIO_COST_LIMIT_EXCEEDED",
                   lambda: policy.validate_future_policy(candidate, old, now=self.now))

    def test_exact_three_hour_cost_cap_is_allowed(self):
        old = {**self.previous, "maxCostAmount": "9.00"}
        candidate = {**self.candidate, "maxCostAmount": "9.00"}
        self.assertEqual(policy.validate_future_policy(candidate, old, now=self.now)["maxCostAmount"], "9.00")

    def test_financial_or_retry_changes_are_not_implicitly_approved(self):
        changes = {"maxCostAmount": "13.00", "gpuHourlyRate": "2.00",
                   "currency": "KRW", "maxRetries": 1}
        for key, value in changes.items():
            with self.subTest(field=key):
                self.error("RECOVERY_EXISTING_FINANCIAL_AND_RETRY_CAPS_REQUIRED",
                           lambda k=key, v=value: policy.validate_future_policy(
                               {**self.candidate, k: v}, self.previous, now=self.now))

    def test_candidate_must_cover_full_future_three_hours(self):
        value = {**self.candidate, "validUntil": (self.now + timedelta(seconds=10799)).isoformat()}
        self.error("RECOVERY_POLICY_VALIDITY_TOO_SHORT_FOR_180_MINUTES",
                   lambda: policy.validate_future_policy(value, self.previous, now=self.now))

    def test_exact_three_hour_validity_is_accepted(self):
        value = {**self.candidate, "validUntil": (self.now + timedelta(seconds=10800)).isoformat()}
        self.assertEqual(policy.validate_future_policy(value, self.previous, now=self.now)["maxWallSeconds"], 10800)

    def test_original_expiry_timezone_and_schema_checks_remain_enforced(self):
        for value, code in (
                ({**self.candidate, "validUntil": (self.now - timedelta(seconds=5)).isoformat()}, "STUDIO_OPERATOR_POLICY_EXPIRED"),
                ({**self.candidate, "validUntil": "2030-01-01T00:00:00"}, "STUDIO_OPERATOR_POLICY_INVALID"),
                ({**self.candidate, "unsupported": True}, "STUDIO_OPERATOR_POLICY_INVALID"),
                ({**self.candidate, "maxWallSeconds": True}, "STUDIO_OPERATOR_POLICY_INVALID"),
                ({**self.candidate, "maxRetries": 3}, "STUDIO_OPERATOR_POLICY_INVALID")):
            with self.subTest(code=code, value=value):
                self.error(code, lambda v=value: policy.validate_future_policy(v, self.previous, now=self.now))

    def test_other_wall_limits_cannot_be_staged(self):
        self.error("RECOVERY_FUTURE_LIMIT_MUST_BE_10800",
                   lambda: policy.validate_future_policy(
                       {**self.candidate, "maxWallSeconds": 7200}, self.previous, now=self.now))

    def test_stage_is_inactive_and_preserves_old_raw_policy_and_all_existing_records(self):
        result = self.stage()
        self.assertEqual(result["status"], "STAGED_NOT_ACTIVE")
        self.assertFalse(result["gpuExecuted"])
        self.assertFalse(result["originalApprovalsChanged"])
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)
        self.assertEqual((self.revision(result) / "PREVIOUS_POLICY_BYTES.json").read_bytes(), self.original)
        self.assertEqual(result["previousPolicySHA256"], hashlib.sha256(self.original).hexdigest())
        self.assert_existing_records_untouched()

    def test_repeated_stage_reuses_same_immutable_revision(self):
        first = self.stage()
        before = {p.name: p.read_bytes() for p in self.revision(first).iterdir() if p.is_file()}
        second = self.stage()
        self.assertEqual(first, second)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.revision(first).iterdir() if p.is_file()})
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)

    def test_repeated_stage_rejects_damaged_revision_policy_and_backups(self):
        staged = self.stage()
        revision = self.revision(staged)
        for name in ("POLICY.json", "PREVIOUS_POLICY.json", "PREVIOUS_POLICY_BYTES.json"):
            path = revision / name
            before = path.read_bytes()
            try:
                self.write(path, {"damaged": True})
                with self.subTest(file=name):
                    self.error("RECOVERY_POLICY_REVISION_CORRUPT", self.stage)
                    self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)
                    self.assert_existing_records_untouched()
            finally:
                self.write(path, before)

    def test_activation_requires_explicit_boolean_consent(self):
        staged = self.stage()
        for consent in (False, None, "true", 1):
            with self.subTest(consent=consent):
                self.error("RECOVERY_EXPLICIT_POLICY_ACTIVATION_REQUIRED",
                           lambda c=consent: policy.activate_future_policy(self.control, staged["revisionId"], consent=c))
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)

    def test_activation_changes_future_policy_only_not_old_job_approval_or_claim(self):
        staged = self.stage()
        result = policy.activate_future_policy(self.control, staged["revisionId"], consent=True)
        self.assertEqual(result["status"], "ACTIVE_FUTURE_NEW_JOBS_ONLY")
        active = json.loads((self.control / "operator_policy.json").read_bytes())
        self.assertEqual(active["maxWallSeconds"], 10800)
        self.assertEqual(active["maxRetries"], self.previous["maxRetries"])
        self.assertEqual(active["maxCostAmount"], self.previous["maxCostAmount"])
        self.assert_existing_records_untouched()
        self.assertEqual((self.revision(staged) / "PREVIOUS_POLICY_BYTES.json").read_bytes(), self.original)

    def test_activation_is_idempotent_and_keeps_existing_approval_bytes(self):
        staged = self.stage()
        policy.activate_future_policy(self.control, staged["revisionId"], consent=True)
        active_bytes = (self.control / "operator_policy.json").read_bytes()
        activated_bytes = (self.revision(staged) / "ACTIVATED.json").read_bytes()
        result = policy.activate_future_policy(self.control, staged["revisionId"], consent=True)
        self.assertEqual(result["status"], "ALREADY_ACTIVE")
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), active_bytes)
        self.assertEqual((self.revision(staged) / "ACTIVATED.json").read_bytes(), activated_bytes)
        self.assert_existing_records_untouched()

    def test_active_policy_with_interrupted_receipt_write_repairs_receipt_only(self):
        staged = self.stage()
        revision = self.revision(staged)
        # Materialize the actual durable crash boundary: policy replacement
        # survived, but the following immutable activation receipt did not.
        cache, _ = policy.dependencies()
        candidate = json.loads((revision / "POLICY.json").read_bytes())
        with cache.PrivateTree(self.control) as root, root.lock(wait_seconds=5):
            root.write_json("operator_policy.json", candidate, replace=True)
        active_bytes = (self.control / "operator_policy.json").read_bytes()
        self.assertFalse((revision / "ACTIVATED.json").exists())
        result = policy.activate_future_policy(self.control, staged["revisionId"], consent=True)
        self.assertEqual(result["status"], "ALREADY_ACTIVE")
        self.assertEqual(json.loads((revision / "ACTIVATED.json").read_bytes()),
                         {"scope": "FUTURE_NEW_JOBS_ONLY", "originalApprovalsChanged": False})
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), active_bytes)
        self.assert_existing_records_untouched()

    def test_corrupt_raw_backup_or_activation_receipt_is_never_silently_repaired(self):
        staged = self.stage()
        revision = self.revision(staged)
        self.write(revision / "PREVIOUS_POLICY_BYTES.json", self.original + b"\n")
        self.error("RECOVERY_POLICY_REVISION_CORRUPT",
                   lambda: policy.activate_future_policy(self.control, staged["revisionId"], consent=True))
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)
        self.write(revision / "PREVIOUS_POLICY_BYTES.json", self.original)
        policy.activate_future_policy(self.control, staged["revisionId"], consent=True)
        active_bytes = (self.control / "operator_policy.json").read_bytes()
        corrupt = b'{"scope":"ALL_EXISTING_JOBS","originalApprovalsChanged":true}'
        self.write(revision / "ACTIVATED.json", corrupt)
        self.error("RECOVERY_POLICY_ACTIVATION_RECEIPT_CORRUPT",
                   lambda: policy.activate_future_policy(self.control, staged["revisionId"], consent=True))
        self.assertEqual((revision / "ACTIVATED.json").read_bytes(), corrupt)
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), active_bytes)
        self.assert_existing_records_untouched()

    def test_policy_bytes_changed_after_review_block_activation_even_if_same_json(self):
        staged = self.stage()
        alternate_bytes = json.dumps(self.previous, separators=(",", ":")).encode()
        self.assertNotEqual(alternate_bytes, self.original)
        self.write(self.control / "operator_policy.json", alternate_bytes)
        self.error("RECOVERY_POLICY_CHANGED_SINCE_REVIEW",
                   lambda: policy.activate_future_policy(self.control, staged["revisionId"], consent=True))
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), alternate_bytes)
        self.assert_existing_records_untouched()

    def test_tampered_revision_candidate_is_rejected(self):
        staged = self.stage()
        candidate_path = self.revision(staged) / "POLICY.json"
        data = json.loads(candidate_path.read_bytes())
        data["maxRetries"] = 1
        self.write(candidate_path, data)
        self.error("RECOVERY_POLICY_REVISION_CORRUPT",
                   lambda: policy.activate_future_policy(self.control, staged["revisionId"], consent=True))
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)

    def test_invalid_revision_id_is_rejected_without_path_traversal(self):
        for identifier in (None, "../other", "A" * 64, "a" * 63, "a" * 65):
            with self.subTest(identifier=identifier):
                self.error("RECOVERY_POLICY_REVISION_INVALID",
                           lambda i=identifier: policy.activate_future_policy(self.control, i, consent=True))

    def test_duplicate_candidate_keys_and_nonfinite_json_are_rejected(self):
        for data, code in ((b'{"maxWallSeconds":10800,"maxWallSeconds":1}', "DUPLICATE_JSON_KEY"),
                           (b'{"maxWallSeconds":NaN}', "NONFINITE_JSON")):
            with self.subTest(code=code):
                self.write(self.candidate_path, data)
                self.error(code, self.stage)
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)

    def test_public_candidate_file_mode_is_rejected_without_repair(self):
        self.candidate_path.chmod(0o644)
        self.error("PRIVATE_PATH_REQUIRED", self.stage)
        self.assertEqual(self.candidate_path.stat().st_mode & 0o777, 0o644)
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)

    def test_symlink_candidate_and_symlink_control_root_are_rejected(self):
        link = self.input / "link.json"
        link.symlink_to(self.candidate_path)
        with self.assertRaises(OSError):
            policy.stage_future_policy(self.control, link)
        alias = self.base / "control-alias"
        alias.symlink_to(self.control, target_is_directory=True)
        with self.assertRaises(OSError):
            policy.stage_future_policy(alias, self.candidate_path)
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)

    def test_hardlinked_candidate_is_not_a_private_record(self):
        os.link(self.candidate_path, self.input / "candidate-alias.json")
        self.error("PRIVATE_PATH_REQUIRED", self.stage)
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)

    def test_wrong_uid_or_gid_fails_before_private_state_access(self):
        for uid, gid in ((0, 1000), (1000, 0), (1001, 1000)):
            with self.subTest(uid=uid, gid=gid), patch.object(policy.os, "geteuid", return_value=uid), patch.object(policy.os, "getegid", return_value=gid):
                self.error("RECOVERY_UID_GID_1000_REQUIRED", self.stage)
                self.error("RECOVERY_UID_GID_1000_REQUIRED",
                           lambda: policy.activate_future_policy(self.control, "a" * 64, consent=True))
        self.assertEqual((self.control / "operator_policy.json").read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
