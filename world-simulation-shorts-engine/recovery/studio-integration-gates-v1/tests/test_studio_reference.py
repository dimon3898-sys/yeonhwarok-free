import copy
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gates_test_service", HERE / "studio_service.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)
module = service.controller_module
contract = module.contract
IMAGE = "sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5"


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gates-reference-test-", dir="/workspace")
        self.root = Path(self.temp.name)
        self.controller = service.StudioController(control_root=self.root / "state", export_root=self.root / "exports",
            image_digest=IMAGE, allow_software_reference=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_source_bytes_retained(self):
        actual = self.controller._normal(contract.REQUEST)
        self.assertEqual(actual["sourceSceneSHA256"], contract.SCENE_SHA)
        self.assertEqual(actual["videoPlan"]["schema"], "MAP_ENGINE_UNIT_SCENE_V4")
        self.assertTrue(actual["softwareOnly"])

    def test_reject_all_unknown_or_mutated_inputs(self):
        changes = {"extra": True, "startFrame": 1, "endFrame": 2400, "fps": 60, "width": 540,
                   "sourceSceneSHA256": "0" * 64, "audio": True, "height": True}
        for key, value in changes.items():
            request = {**contract.REQUEST, key: value}
            self.assertFalse(self.controller.preflight(request)["valid"], key)

    def test_requires_server_owned_opt_in(self):
        self.controller.allow_software_reference = False
        result = self.controller.preflight(contract.REQUEST)
        self.assertTrue(result["valid"])
        self.assertFalse(result["ready"])
        self.assertFalse(result["requiresGpu"])

    def test_legacy_requests_delegate_unchanged(self):
        legacy = {"schema": "NOT_REFERENCE", "durationSeconds": 80}
        with patch.object(module.parent.StudioController, "_normal", return_value="unchanged") as mock:
            self.assertEqual(self.controller._normal(legacy), "unchanged")
            mock.assert_called_once_with(legacy)

    def test_consent_and_duplicate_claims_no_gpu_authorization(self):
        submission = self.controller.submit(contract.REQUEST)["submissionId"]
        with self.assertRaisesRegex(module.StudioError, "STUDIO_OWNER_CONSENT_REQUIRED"):
            self.controller.start(submission, "reference-test-key")
        class MockChild:
            pid = os.getpid()
        with patch.object(module.subprocess, "Popen", return_value=MockChild()) as child:
            first = self.controller.start(submission, "reference-test-key", consent=True)
            second = self.controller.start(submission, "reference-test-key", consent=True)
            third = self.controller.start(submission, "another-reference-key", consent=True)
            self.assertEqual(first["jobId"], second["jobId"])
            self.assertEqual(first["jobId"], third["jobId"])
            self.assertEqual(child.call_count, 1)
            command = child.call_args[0][0]
            self.assertIn("software_worker.py", " ".join(command))
            self.assertTrue(child.call_args.kwargs["start_new_session"])
        self.assertEqual(list(self.controller.control_root.glob("approvals/**/*json")), [])
        with self.assertRaisesRegex(module.StudioError, "STUDIO_REFERENCE_AUTORETRY_FORBIDDEN"):
            self.controller.resume(first["jobId"], "new-resume-key-123", consent=True)

    def test_construction_never_starts_work(self):
        with patch.object(module.subprocess, "Popen") as child:
            service.StudioController(control_root=self.root / "other", export_root=self.root / "exports",
                image_digest=IMAGE, allow_software_reference=True)
            child.assert_not_called()


if __name__ == "__main__":
    unittest.main()
