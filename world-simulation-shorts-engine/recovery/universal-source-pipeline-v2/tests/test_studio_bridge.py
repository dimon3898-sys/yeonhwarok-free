"""Focused source orchestration tests. No native frames or GPU are produced."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


service = load("source_bridge_test_service", HERE / "studio_service.py")
module = service.controller_module
worker = load("source_bridge_test_worker", HERE / "software_worker.py")
IMAGE = "sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5"
REQUEST = {"schema": module.SCHEMA, "scenario_id": "unit-only-nonhistorical"}


class FixtureController(service.StudioController):
    """Keep orchestration separate from root's real source-contract tests."""
    mode = "SYNTHETIC_TEST"
    scope = "SYNTHETIC_TECHNICAL_DEMO"
    blockers = []
    start_frame = 0

    def _normal(self, value):
        if not module.selected(value):
            return super()._normal(value)
        pipeline = {"ready": not self.blockers, "mode": self.mode, "scope": self.scope,
            "blockers": list(self.blockers), "totalFrames": 180, "startFrame": self.start_frame,
            "requestSHA256": module._sha(value), "originalRequest": deepcopy(value),
            "runtimePayload": {"frames": [{"frame": self.start_frame + frame} for frame in range(180)]}}
        return {"schema": module.SCHEMA, "profile": module.PROFILE, "title": "Unit-only software source test",
            "videoPlan": deepcopy(value), "sourcePipeline": pipeline, "sfx": {"enabled": False}}


class StudioBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-bridge-unit-", dir="/workspace")
        self.root = Path(self.temp.name)
        self.controller = FixtureController(control_root=self.root / "state", export_root=self.root / "exports",
            source_root=self.root, expected_index_sha256="1" * 64, image_digest=IMAGE,
            allow_software_source_review=True)

    def tearDown(self):
        self.temp.cleanup()

    def launch_mock(self, request=REQUEST, key="source-unit-first-key"):
        class Child:
            pid = os.getpid()
        submission = self.controller.submit(request)["submissionId"]
        with patch.object(module.subprocess, "Popen", return_value=Child()) as child:
            state = self.controller.start(submission, key, consent=True)
        return submission, state, child

    def test_explicit_server_enable_and_consent_required(self):
        self.controller.allow_software_source_review = False
        self.assertFalse(self.controller.preflight(REQUEST)["ready"])
        self.controller.allow_software_source_review = True
        submission = self.controller.submit(REQUEST)["submissionId"]
        with self.assertRaisesRegex(module.StudioError, "STUDIO_OWNER_CONSENT_REQUIRED"):
            self.controller.start(submission, "unit-missing-consent-key")

    def test_missing_historical_control_blocks_before_launch(self):
        self.controller.mode, self.controller.scope = "PRODUCTION", "G3_SOURCE_QUALIFIED_HISTORICAL"
        self.controller.blockers = ["G2_FULL_CONTROL_AREA_BLOCKED"]
        result = self.controller.preflight(REQUEST)
        self.assertFalse(result["ready"])
        self.assertFalse(result["historicalRenderAllowed"])
        submission = self.controller.submit(REQUEST)["submissionId"]
        with patch.object(module.subprocess, "Popen") as child:
            with self.assertRaisesRegex(module.StudioError, "STUDIO_PREFLIGHT_BLOCKED"):
                self.controller.start(submission, "unit-missing-history-key", consent=True)
            child.assert_not_called()

    def test_no_scene_mode_alone_can_admit_historical_render(self):
        self.controller.mode, self.controller.scope = "PRODUCTION", "UNREVIEWED"
        result = self.controller.preflight(REQUEST)
        self.assertFalse(result["ready"])
        self.assertFalse(result["historicalRenderAllowed"])

    def test_g1_and_other_production_normalizers_delegate(self):
        actual = service.StudioController(control_root=self.root / "delegation", export_root=self.root / "exports",
            source_root=self.root, expected_index_sha256="1" * 64, image_digest=IMAGE)
        value = {"schema": "WORLD_ENGINE_STUDIO_EXACT_REFERENCE_V1"}
        with patch.object(module.parent.StudioController, "_normal", return_value="original-g1") as inherited:
            self.assertEqual(actual._normal(value), "original-g1")
            inherited.assert_called_once_with(value)

    def test_duplicate_touch_and_reconnect_cannot_spawn_again(self):
        submission, first, child = self.launch_mock()
        self.assertEqual(child.call_count, 1)
        self.assertTrue(child.call_args.kwargs["start_new_session"])
        with patch.object(module.subprocess, "Popen") as next_child:
            second = self.controller.start(submission, "source-unit-first-key", consent=True)
            third = self.controller.start(submission, "source-unit-new-browser-key", consent=True)
            self.assertEqual(first["jobId"], second["jobId"])
            self.assertEqual(first["jobId"], third["jobId"])
            next_child.assert_not_called()
        self.assertEqual(list(self.controller.control_root.glob("approvals/**/*json")), [])
        self.assertIn("software_worker.py", " ".join(child.call_args.args[0]))

    def test_conflicting_idempotency_key_and_active_job_are_rejected(self):
        _, first, _ = self.launch_mock()
        second = self.controller.submit({**REQUEST, "scenario_id": "other-unit"})["submissionId"]
        with self.assertRaisesRegex(module.StudioError, "STUDIO_IDEMPOTENCY_CONFLICT"):
            self.controller.start(second, "source-unit-first-key", consent=True)
        with self.assertRaises(module.StudioError) as active_error:
            self.controller.start(second, "source-unit-second-key", consent=True)
        self.assertEqual(active_error.exception.code, "STUDIO_JOB_ALREADY_ACTIVE")

    def test_scene_revalidated_and_changed_sources_fail_closed(self):
        submission = self.controller.submit(REQUEST)["submissionId"]
        self.controller.blockers = ["SOURCE_CHANGED_AFTER_SUBMIT"]
        with patch.object(module.subprocess, "Popen") as child:
            with self.assertRaisesRegex(module.StudioError, "STUDIO_SOURCE_SCENE_BINDING_CHANGED"):
                self.controller.start(submission, "source-unit-changed-source", consent=True)
            child.assert_not_called()

    def test_global_offset_is_preserved_in_private_execution_receipt(self):
        self.controller.start_frame = 600
        _, state, _ = self.launch_mock()
        receipt = json.loads((self.controller.control_root / "source-jobs" / state["jobId"] / "compiledpackage.json").read_bytes())["executionReceipt"]
        self.assertEqual(receipt["frameRange"], [600, 780])
        self.assertTrue(receipt["softwareOnly"])
        self.assertFalse(receipt["historicalRenderAllowed"])

    def test_constructor_and_resume_never_implicitly_launch(self):
        with patch.object(module.subprocess, "Popen") as child:
            FixtureController(control_root=self.root / "other", export_root=self.root / "exports",
                source_root=self.root, expected_index_sha256="1" * 64, image_digest=IMAGE,
                allow_software_source_review=True)
            child.assert_not_called()
        _, state, _ = self.launch_mock()
        with self.assertRaisesRegex(module.StudioError, "STUDIO_SOURCE_AUTORETRY_FORBIDDEN"):
            self.controller.resume(state["jobId"], "source-unit-no-retry", consent=True)


class WorkerContractTests(unittest.TestCase):
    def package(self, start=0):
        request = deepcopy(REQUEST)
        return {"schema": module.SCHEMA, "sourcePipeline": {"ready": True, "mode": "SYNTHETIC_TEST",
            "scope": "SYNTHETIC_TECHNICAL_DEMO", "totalFrames": 3, "startFrame": start,
            "requestSHA256": module._sha(request), "runtimePayload": {"frames": [{"frame": start + f} for f in range(3)]}},
            "executionReceipt": {"schema": "WORLD_ENGINE_STUDIO_SOURCE_EXECUTION_V2", "jobId": "studio-" + "3" * 32,
                "softwareOnly": True, "historicalRenderAllowed": False, "frameRange": [start, start + 3],
                "maxWallSeconds": 900, "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                "sourceScope": "SYNTHETIC_TECHNICAL_DEMO", "sourceIndexSHA256": "1" * 64, "requestSHA256": module._sha(request)}}

    def validate(self, package):
        raw = json.dumps(package).encode()
        return worker.validate_package(raw, hashlib.sha256(raw).hexdigest())

    def test_scope_package_keeps_original_global_frame_range(self):
        self.assertEqual(self.validate(self.package(600))["executionReceipt"]["frameRange"], [600, 603])

    def test_gpu_lookalike_receipts_or_historical_promotion_are_rejected(self):
        for field, value in (("softwareOnly", False), ("historicalRenderAllowed", True), ("maxWallSeconds", 14400), ("sourceIndexSHA256", "untrusted")):
            package = self.package()
            package["executionReceipt"][field] = value
            with self.assertRaisesRegex(RuntimeError, "STUDIO_SOURCE_EXECUTION_SCOPE_INVALID"):
                self.validate(package)

    def test_package_hash_corruption_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "STUDIO_SOURCE_PACKAGE_HASH_MISMATCH"):
            worker.validate_package(json.dumps(self.package()).encode(), "0" * 64)

    def test_missing_or_duplicate_frames_are_rejected(self):
        for frames in ([{"frame": 0}], [{"frame": 0}, {"frame": 0}, {"frame": 2}]):
            package = self.package()
            package["sourcePipeline"]["runtimePayload"]["frames"] = frames
            with self.assertRaisesRegex(RuntimeError, "STUDIO_SOURCE_FRAME_PACKAGE_INCOMPLETE"):
                self.validate(package)

    def test_expired_or_reversed_receipt_is_rejected(self):
        package = self.package()
        package["executionReceipt"]["expiresAt"] = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(RuntimeError, "STUDIO_SOURCE_APPROVAL_EXPIRED"):
            self.validate(package)

    def test_completion_report_cannot_hide_missing_frames_or_changed_output(self):
        # Byte fixture exercises the receipt/hash contract only. It is not a
        # decoded video and is never published as rendered output.
        with tempfile.TemporaryDirectory(dir="/workspace") as directory:
            file = Path(directory) / "unit-only-bytes.mp4"
            file.write_bytes(b"unit-only-output-contract")
            report = {"schema": "WORLD_ENGINE_SOURCE_SCENE_CAPTURE_V2", "status": "SOFTWARE_PREVIEW_COMPLETE",
                "totalFrames": 3, "newlyRenderedFrames": 3, "fullDecode": "PASS",
                "video": {"sha256": hashlib.sha256(file.read_bytes()).hexdigest()}}
            self.assertEqual(worker.validate_capture(report, file, 3), report["video"]["sha256"])
            for update in ({"newlyRenderedFrames": 2}, {"fullDecode": "FAIL"}, {"gpuRenderingVerified": True}):
                with self.assertRaisesRegex(RuntimeError, "STUDIO_SOURCE_CAPTURE_INCOMPLETE_OR_CHANGED"):
                    worker.validate_capture({**report, **update}, file, 3)
            file.write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "STUDIO_SOURCE_CAPTURE_INCOMPLETE_OR_CHANGED"):
                worker.validate_capture(report, file, 3)


if __name__ == "__main__":
    unittest.main()
