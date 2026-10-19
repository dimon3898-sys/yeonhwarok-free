"""CPU-only prerequisite tests. All receipts, media hashes and prices are synthetic.

These tests do not issue user approval or inspect/run NVIDIA hardware.
"""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from quality_gate import evaluate_render_gate

# Exercise the unchanged private-policy validator directly. No controller is
# constructed, no claim is created, and no runtime/GPU entry point is called.
ORIGINAL = HERE.parent / "production-studio-mvp-v1"
sys.path.insert(0, str(ORIGINAL))
spec = importlib.util.spec_from_file_location("_integration_test_policy", ORIGINAL / "studio_controller.py")
policy_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy_module)


def validate_original_policy(value):
    class Reader:
        def json(self, name, optional=False):
            assert name == "operator_policy.json"
            return value
    return policy_module.StudioController._policy(None, Reader())


class QualityGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.path = self.root / "quality-approval.json"
        self.now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        self.context = {"sourceCommit": "a" * 40, "sourceManifestSHA256": "b" * 64,
            "sourceClosureManifestSHA256": "c" * 64, "sceneSHA256": "d" * 64,
            "imageDigest": "sha256:" + "e" * 64, "durationSeconds": 80, "fps": 30,
            "sourceClosureVerified": True, "imagePackageIncluded": True,
            "requiredModules": {"TERRITORY": "READY", "MOVING_OBJECT": "NOT_REQUIRED"},
            "dataBlockers": [], "referenceSHA256": "f" * 64, "candidateSHA256": "1" * 64}
        self.policy = {"validUntil": "2099-01-01T00:00:00+00:00", "maxWallSeconds": 14400,
            "maxRetries": 0, "maxCostAmount": "4", "currency": "USD", "gpuHourlyRate": "1"}
        self.receipt = {key: self.context[key] for key in ("sourceCommit", "sourceManifestSHA256",
            "sourceClosureManifestSHA256", "sceneSHA256", "imageDigest", "referenceSHA256", "candidateSHA256")}
        self.receipt.update({"schema": "WORLD_ENGINE_5S_USER_QUALITY_APPROVAL_V1", "userReview": "PASS",
            "targetDurationSeconds": 80, "targetFps": 30,
            "reviewedAt": "2026-10-19T11:00:00+00:00", "validUntil": "2026-10-19T13:00:00+00:00",
            "candidate": {"durationSeconds": 5, "fps": 30, "width": 1080, "height": 1920,
                "frames": 150, "gpuVendor": "NVIDIA", "gpuRenderingVerified": True,
                "mp4FullyDecoded": True, "gpuEvidenceSHA256": "2" * 64},
            "referenceComparison": {"status": "COMPLETED", "referenceSHA256": "f" * 64,
                "candidateSHA256": "1" * 64, "evidenceSHA256": "3" * 64}})
        self.write_receipt()

    def tearDown(self):
        self.temporary.cleanup()

    def write_receipt(self, value=None):
        self.path.write_text(json.dumps(self.receipt if value is None else value), encoding="utf-8")
        self.path.chmod(0o600)

    def gate(self, context=None, **kwargs):
        values = {"phase": "FULL_VIDEO", "operator_policy": self.policy,
            "policy_validator": validate_original_policy, "receipt_path": self.path,
            "trusted_receipt_root": self.root, "now": self.now}
        values.update(kwargs)
        return evaluate_render_gate(self.context if context is None else context, **values)

    def has(self, result, code):
        self.assertFalse(result["allowed"], result)
        self.assertIn(code, {item["code"] for item in result["blockers"]})

    def test_complete_synthetic_receipt_only_permits_prerequisite_not_gpu(self):
        result = self.gate()
        self.assertTrue(result["allowed"])
        self.assertTrue(result["verification"]["userQualityReceiptVerified"])
        self.assertFalse(result["verification"]["gpuRenderingVerified"])
        self.assertFalse(result["verification"]["renderStarted"])
        self.assertTrue(result["verification"]["existingNVIDIAAdmissionStillRequired"])

    def test_reference5s_still_requires_separate_operator_policy(self):
        context = {**self.context, "durationSeconds": 5}
        result = self.gate(context, phase="REFERENCE_5S", operator_policy=None,
                           receipt_path=None, trusted_receipt_root=None)
        self.has(result, "INTEGRATION_SEPARATE_PAID_GPU_APPROVAL_REQUIRED")

    def test_reference5s_does_not_require_fullvideo_quality_receipt(self):
        result = self.gate({**self.context, "durationSeconds": 5}, phase="REFERENCE_5S",
                           receipt_path=None, trusted_receipt_root=None)
        self.assertTrue(result["allowed"])
        self.assertFalse(result["verification"]["userQualityReceiptVerified"])

    def test_missing_receipt_blocks80s(self):
        self.has(self.gate(receipt_path=None), "INTEGRATION_5S_USER_QUALITY_APPROVAL_REQUIRED")

    def test_missing_private_authority_root_blocks80s(self):
        self.has(self.gate(trusted_receipt_root=None), "INTEGRATION_5S_USER_QUALITY_APPROVAL_REQUIRED")

    def test_prompt_cannot_selfapprove_context(self):
        self.has(self.gate({**self.context, "qualityApproved": True}),
                 "INTEGRATION_TRUSTED_GATE_CONTEXT_INVALID")

    def test_source_scene_image_reference_candidate_binding_changes_reject(self):
        for name in ("sourceCommit", "sourceManifestSHA256", "sourceClosureManifestSHA256",
                     "sceneSHA256", "imageDigest", "referenceSHA256", "candidateSHA256"):
            with self.subTest(name=name):
                receipt = deepcopy(self.receipt)
                receipt[name] = "0" * 40 if name == "sourceCommit" else "0" * 64
                self.write_receipt(receipt)
                self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_BINDING_MISMATCH")

    def test_receipt_qualitywarning_does_not_equal_userpass(self):
        self.write_receipt({**self.receipt, "userReview": "WARNING"})
        self.has(self.gate(), "INTEGRATION_5S_USER_QUALITY_APPROVAL_REQUIRED")

    def test_extra_receipt_fields_are_not_silent_overrides(self):
        self.write_receipt({**self.receipt, "ignoreDataBlockers": True})
        self.has(self.gate(), "INTEGRATION_5S_USER_QUALITY_APPROVAL_REQUIRED")

    def test_expired_or_future_receipt_rejects(self):
        for changes in ({"validUntil": "2026-10-19T11:59:59+00:00"},
                        {"reviewedAt": "2026-10-19T12:01:00+00:00"},
                        {"validUntil": "2026-10-19T10:00:00+00:00"}):
            with self.subTest(changes=changes):
                self.write_receipt({**self.receipt, **changes})
                self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_EXPIRED_OR_FUTURE")

    def test_timezone_required(self):
        self.write_receipt({**self.receipt, "validUntil": "2099-01-01T00:00:00"})
        self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_TIME_INVALID")

    def test_cpu_or_swiftshader_candidate_never_qualifies(self):
        for value in ("SwiftShader", "CPU", "UNKNOWN"):
            receipt = deepcopy(self.receipt)
            receipt["candidate"]["gpuVendor"] = value
            self.write_receipt(receipt)
            self.has(self.gate(), "INTEGRATION_5S_NVIDIA_OUTPUT_EVIDENCE_REQUIRED")

    def test_undecoded_wrongframe_or_notgpu_candidate_rejects(self):
        for field, value in (("frames", 149), ("fps", 24), ("durationSeconds", 5.0),
                             ("gpuRenderingVerified", False), ("mp4FullyDecoded", False),
                             ("gpuEvidenceSHA256", "not-a-sha")):
            receipt = deepcopy(self.receipt)
            receipt["candidate"][field] = value
            self.write_receipt(receipt)
            self.has(self.gate(), "INTEGRATION_5S_NVIDIA_OUTPUT_EVIDENCE_REQUIRED")

    def test_missing_or_mismatched_reference_comparison_rejects(self):
        for field, value in (("status", "NOT_VERIFIED"), ("referenceSHA256", "0" * 64),
                             ("candidateSHA256", "0" * 64), ("evidenceSHA256", "")):
            receipt = deepcopy(self.receipt)
            receipt["referenceComparison"][field] = value
            self.write_receipt(receipt)
            self.has(self.gate(), "INTEGRATION_5S_REFERENCE_COMPARISON_REQUIRED")

    def test_userquality_cannot_override_missing_historical_data(self):
        self.has(self.gate({**self.context, "dataBlockers": ["HISTORICAL_UNIT_LOCATIONS_MISSING"]}),
                 "INTEGRATION_REQUIRED_DATA_BLOCKED")

    def test_userquality_cannot_override_unwired_requiredmodule(self):
        context = {**self.context, "requiredModules": {"TERRITORY": "NOT_WIRED"}}
        self.has(self.gate(context), "INTEGRATION_REQUIRED_MODULE_BLOCKED")

    def test_requiredmodule_evidence_cannot_be_empty_or_all_notrequired(self):
        for modules in ({}, {"ALL": "NOT_REQUIRED"}, None):
            self.has(self.gate({**self.context, "requiredModules": modules}),
                     "INTEGRATION_REQUIRED_MODULE_EVIDENCE_MISSING")

    def test_malformed_requiredmodule_value_rejects_without_crashing(self):
        self.has(self.gate({**self.context, "requiredModules": {"TERRITORY": {"ready": True}}}),
                 "INTEGRATION_REQUIRED_MODULE_BLOCKED")

    def test_unknown_data_blocker_format_rejects(self):
        self.has(self.gate({**self.context, "dataBlockers": ["sensitive raw error"]}),
                 "INTEGRATION_DATA_EVIDENCE_INVALID")

    def test_unverified_closure_rejects_even_with_userpass(self):
        self.has(self.gate({**self.context, "sourceClosureVerified": False}),
                 "INTEGRATION_SOURCE_CLOSURE_NOT_VERIFIED")

    def test_current_old_image_cannot_claim_candidate_inclusion(self):
        self.has(self.gate({**self.context, "imagePackageIncluded": False}),
                 "INTEGRATION_CANDIDATE_NOT_INCLUDED_IN_IMAGE")

    def test_unbuilt_image_unknown_digest_blocks(self):
        self.has(self.gate({**self.context, "imageDigest": None}), "INTEGRATION_IMMUTABLE_IMAGE_REQUIRED")

    def test_invalid_sourcehash_blocks(self):
        self.has(self.gate({**self.context, "sourceManifestSHA256": "missing"}),
                 "INTEGRATION_SOURCE_SCENE_REFERENCE_BINDING_REQUIRED")

    def test_missing_candidate_hash_blocks80s(self):
        context = deepcopy(self.context)
        del context["candidateSHA256"]
        self.has(self.gate(context), "INTEGRATION_5S_CANDIDATE_SHA_REQUIRED")

    def test_full_video_lengths_use_same_gate(self):
        for duration in (80, 120, 180, 300, 600):
            with self.subTest(duration=duration):
                self.write_receipt({**self.receipt, "targetDurationSeconds": duration})
                self.assertTrue(self.gate({**self.context, "durationSeconds": duration})["allowed"])

    def test_quality_receipt_is_bound_to_target_duration_and_fps(self):
        for changes in ({"targetDurationSeconds": 120}, {"targetDurationSeconds": 80.0}, {"targetFps": 24}):
            self.write_receipt({**self.receipt, **changes})
            self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_BINDING_MISMATCH")

    def test_invalid_frame_contract_blocks(self):
        for changes in ({"fps": 24}, {"fps": True}, {"durationSeconds": 80.0},
                        {"durationSeconds": True}, {"durationSeconds": 5}, {"durationSeconds": 81}):
            self.has(self.gate({**self.context, **changes}), "INTEGRATION_RENDER_DURATION_INVALID")

    def test_unknown_phase_blocks(self):
        self.has(self.gate(phase="FREE_GPU"), "INTEGRATION_RENDER_PHASE_INVALID")

    def test_policy_unknown_fields_fail_original_validator(self):
        self.has(self.gate(operator_policy={**self.policy, "ignoreBudget": True}),
                 "STUDIO_OPERATOR_POLICY_INVALID")

    def test_policy_expiry_fail_original_validator(self):
        self.has(self.gate(operator_policy={**self.policy, "validUntil": "2000-01-01T00:00:00+00:00"}),
                 "STUDIO_OPERATOR_POLICY_EXPIRED")

    def test_insufficient_budget_fail_original_validator(self):
        self.has(self.gate(operator_policy={**self.policy, "maxCostAmount": "0.1"}),
                 "STUDIO_COST_LIMIT_EXCEEDED")

    def test_missing_validator_cannot_selfapprove_paidwork(self):
        self.has(self.gate(policy_validator=None), "INTEGRATION_SEPARATE_PAID_GPU_APPROVAL_REQUIRED")

    def test_boolean_validator_result_not_policyproof(self):
        self.has(self.gate(policy_validator=lambda _: True), "INTEGRATION_OPERATOR_POLICY_NOT_VALIDATED")

    def test_receipt_symlink_rejected(self):
        actual = self.root / "actual.json"
        self.path.rename(actual)
        self.path.symlink_to(actual)
        self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_PATH_UNSAFE")

    def test_receipt_root_symlink_rejected(self):
        link = self.root / "linked"
        link.symlink_to(self.root, target_is_directory=True)
        self.has(self.gate(receipt_path=link / self.path.name, trusted_receipt_root=link),
                 "INTEGRATION_QUALITY_RECEIPT_PATH_UNSAFE")

    def test_shared_root_is_not_operator_authority(self):
        self.root.chmod(0o755)
        self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_ROOT_NOT_PRIVATE")

    def test_public_receipt_mode_rejected(self):
        self.path.chmod(0o644)
        self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_FILE_NOT_PRIVATE")

    def test_wrong_uid_rejected(self):
        self.has(self.gate(trusted_uid=os.geteuid() + 1), "INTEGRATION_QUALITY_RECEIPT_ROOT_NOT_PRIVATE")

    def test_hardlinked_receipt_rejected(self):
        os.link(self.path, self.root / "copy.json")
        self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_FILE_NOT_PRIVATE")

    def test_path_escape_rejected(self):
        self.has(self.gate(receipt_path=self.root / ".." / "outside.json"),
                 "INTEGRATION_QUALITY_RECEIPT_PATH_UNSAFE")

    def test_duplicate_json_key_rejected(self):
        self.path.write_text('{"userReview":"FAIL","userReview":"PASS"}')
        self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_INVALID")

    def test_nonfinite_json_rejected(self):
        self.path.write_text('{"value":NaN}')
        self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_INVALID")

    def test_empty_receipt_file_rejected(self):
        self.path.write_bytes(b"")
        self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_FILE_NOT_PRIVATE")

    def test_oversized_receipt_file_rejected(self):
        self.path.write_bytes(b" " * 65537)
        self.has(self.gate(), "INTEGRATION_QUALITY_RECEIPT_FILE_NOT_PRIVATE")

    def test_empty_context_denies_without_claim_or_render(self):
        result = self.gate({})
        self.assertFalse(result["allowed"])
        self.assertFalse(result["verification"]["renderStarted"])


if __name__ == "__main__":
    unittest.main()
