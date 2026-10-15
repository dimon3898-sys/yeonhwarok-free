"""First diagnostic failure survives a later supervisor permission failure."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import errno
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
storage_candidates = [Path("/opt/world-engine-storage-fix"), HERE.parent / "gcube-storage-fix-v1"]
STORAGE = next(path for path in storage_candidates if (path / "launch.py").is_file())
sys.path.insert(0, str(STORAGE))
spec = importlib.util.spec_from_file_location("storage_launch_first_failure_test_only", STORAGE / "launch.py")
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)


class FirstFailureTests(unittest.TestCase):
    def invoke_drop_failure(self, original):
        private_records, shared_records = [], []
        stdout, stderr = io.StringIO(), io.StringIO()
        account = SimpleNamespace(pw_uid=1000, pw_gid=1000)
        gpu = Mock(side_effect=AssertionError("no GPU or renderer dispatch allowed"))
        operations = SimpleNamespace(account=Mock(return_value=account), gpu=gpu)
        session = SimpleNamespace(private_root=Path("/var/lib/world-engine-private/engine/session-test-only"),
                                  export_name="world-engine-export-" + "a" * 24)
        def export(record):
            shared_records.append(deepcopy(record))
            body = json.dumps(record, sort_keys=True).encode()
            return {"schema": "WORLD_ENGINE_SAFE_RECORD_EXPORT_V1", "status": "EXPORTED",
                    "exportName": session.export_name, "file": f"startup-safe-{len(shared_records):024x}.json",
                    "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                    "mountedViewReadbackVerified": True, "remotePersistenceVerified": False,
                    "externalDownloadVerified": False, "privateDataAllowed": False}
        session.export_safe_record = Mock(side_effect=export)
        def persist(record, roots=None):
            private_records.append(deepcopy(record))
            self.assertEqual(roots, [session.private_root / "startup-diagnostics"])
            return {"persisted": True, "tier": "primary"}
        service = Mock(side_effect=AssertionError("HTTP forbidden after privilege-drop failure"))
        worker = Mock(return_value=original)
        with patch.object(launch.records, "persist_record", side_effect=persist), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            result = launch.main([], operations=operations, session_factory=lambda _: session,
                environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic"}, worker=worker,
                privilege_drop=Mock(side_effect=PermissionError(errno.EPERM, "private-canary-do-not-print")),
                diagnostic_service=service)
        service.assert_not_called()
        gpu.assert_not_called()
        worker.assert_called_once()
        console = [json.loads(line) for line in stdout.getvalue().splitlines()]
        console = [value for value in console if value.get("schema") == launch.records.SCHEMA]
        self.assertNotEqual(result, 0)
        self.assertNotIn("private-canary", stdout.getvalue() + stderr.getvalue())
        return console, private_records, shared_records

    def test_gpu_failure_retains_first_code_timestamp_gpu_and_all_save_order(self):
        original = launch.records.make_record("WEBGL2", "GPU_WEBGL_UNVERIFIED", 2, mode="diagnostic",
            gpu_diagnostics={"reason_code": "GPU_WEBGL_UNVERIFIED", "failed_stage": "D",
                             "webgl": {"context_available": False, "reason_code": "WEBGL2_CONTEXT_UNAVAILABLE"}},
            test_only=True)
        original["timestamp"] = "2026-10-15T00:00:00+00:00"
        before = deepcopy(original)
        for output in self.invoke_drop_failure(original):
            self.assertEqual(len(output), 2)
            self.assertEqual(output[0], launch.records.safe_record(before))
            self.assertEqual(output[0]["safeDiagnostics"]["gpu"], before["safeDiagnostics"]["gpu"])
            self.assertEqual(output[0]["timestamp"], "2026-10-15T00:00:00+00:00")
            self.assertEqual(output[1]["stage"], "UID_GID")
            self.assertEqual(output[1]["errorCode"], "UID_GID_FAILED")
            self.assertFalse(output[1]["renderAllowed"])
        self.assertEqual(original, before)

    def test_source_failure_is_not_replaced_by_secondary_uid_failure(self):
        original = launch.records.make_record("SOURCE_INTEGRITY", "SOURCE_CONTRACT_INVALID", 1,
                                              mode="diagnostic", test_only=True)
        for output in self.invoke_drop_failure(original):
            self.assertEqual([record["errorCode"] for record in output],
                             ["SOURCE_CONTRACT_INVALID", "UID_GID_FAILED"])
            self.assertEqual(output[0]["stage"], "SOURCE_INTEGRITY")

    def test_storage_errno_is_preserved_separately_from_secondary_permission_errno(self):
        original = launch.records.make_record("STORAGE", "STORAGE_UNAVAILABLE", 1,
                                              mode="diagnostic", errno_value=errno.EROFS, test_only=True)
        for output in self.invoke_drop_failure(original):
            self.assertEqual(output[0]["errorCode"], "STORAGE_UNAVAILABLE")
            self.assertEqual(output[0]["safeDiagnostics"]["errnoName"], "EROFS")
            self.assertEqual(output[1]["safeDiagnostics"]["errnoName"], "EPERM")

    def test_diagnostic_only_success_publishes_only_actual_uid_failure(self):
        original = launch.records.make_record("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_ONLY", 0,
                                              mode="diagnostic", test_only=True)
        for output in self.invoke_drop_failure(original):
            self.assertEqual(len(output), 1)
            self.assertEqual(output[0]["stage"], "UID_GID")
            self.assertEqual(output[0]["errorCode"], "UID_GID_FAILED")
            self.assertFalse(output[0]["gpuRenderingVerified"])
            self.assertFalse(output[0]["renderAllowed"])


if __name__ == "__main__":
    unittest.main()
