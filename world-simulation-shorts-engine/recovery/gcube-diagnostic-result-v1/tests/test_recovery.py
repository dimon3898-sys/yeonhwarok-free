"""Synthetic SAFE admissions and real local files; no GPU or gCube evidence."""
from copy import deepcopy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("recover_existing", HERE / "recover_existing.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() != 1000 or os.getegid() != 1000:
            self.skipTest("Real private-file fixtures require UID/GID1000; no production checks bypassed")
        self.temporary = tempfile.TemporaryDirectory(prefix="world-existing-admission-", dir="/workspace")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.base, self.shared = root / "private", root / "shared"
        self.base.mkdir(mode=0o700)
        self.shared.mkdir(mode=0o755)
        self.session = self.base / ("session-" + "a" * 24)
        self.session.mkdir(mode=0o700)
        self.export_name = "world-engine-export-" + "b" * 24
        self.export = self.shared / self.export_name
        self.export.mkdir(mode=0o700)
        self.current = reader.records.make_record("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_ONLY", 0, mode="diagnostic")
        self.current["timestamp"] = "2026-10-15T01:02:04+00:00"
        self.receipt = {"schema": "WORLD_ENGINE_EXPORT_SESSION_V1", "preflightVerified": True,
            "exportName": self.export_name, "rootIdentity": reader.storage._identity(self.shared.stat()),
            "directoryIdentity": reader.storage._identity(self.export.stat()), **reader.storage._FLAGS}
        self.write(self.session / "EXPORT_RECEIPT.json", self.receipt)
        self.export_file = self.export / ("startup-safe-" + "c" * 24 + ".json")
        self.write(self.export_file, self.current)
        self.diagnostics = self.session / "diagnostics"
        self.diagnostics.mkdir(mode=0o700)
        self.run = self.diagnostics / ("20261015T010203-" + "d" * 32)
        self.run.mkdir(mode=0o700)
        self.admission = {"schema": "RTX_GPU_ADMISSION_V1", "status": "GPU_VERIFIED", "testOnly": False,
            "gpuRenderingVerified": True, "observedAt": "2026-10-15T01:02:03+00:00",
            "verificationScope": "STARTUP_NATIVE_GPU_PIXEL_DRAW", "renderMode": "gpu-required",
            "gpuProfile": "egl", "model": "RTX 4080 SUPER", "driverVersion": "560.35.03",
            "physicalMemoryMiB": 16384, "availableMemoryMiB": 15000, "vramBudgetBytes": 8 * 1024**3,
            "sharedMemory": {"capacityBytes": 2 * 1024**3, "availableBytes": 2 * 1024**3},
            "sourceVerification": {"status": "PASS", "files": 160, "sourceContractSha256": "e" * 64},
            "autoRender": False, "renderExecuted": False, "visualQualityVerified": False,
            "unapprovedPrivateCanary": "DO_NOT_PRINT_PRIVATE_VALUE"}
        self.safe_file = self.run / "admission_safe.json"
        self.write(self.safe_file, self.admission)

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
        path.chmod(0o600)

    def recover(self):
        return reader.recover(_current_record=self.current, _base=self.base, _export_root=self.shared)

    def assert_unverified(self):
        result = self.recover()
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertFalse(result["gpuRenderingVerified"])
        self.assertFalse(result["renderAllowed"])
        self.assertNotIn("DO_NOT_PRINT", json.dumps(result))

    def test_exact_existing_receipt_and_safe_admission_correlate_read_only(self):
        before = {str(path): (path.stat().st_mode, path.read_bytes()) for path in self.base.rglob("*.json")}
        with mock.patch.object(reader.os, "write", side_effect=AssertionError("reader must never write")), \
             mock.patch.object(reader.os, "chmod", side_effect=AssertionError("reader must never chmod")):
            result = self.recover()
        self.assertEqual(result["status"], "TEST_ONLY")
        self.assertTrue(result["testOnly"])
        self.assertEqual(result["model"], "RTX 4080 SUPER")
        self.assertEqual(result["verificationScope"], "STARTUP_NATIVE_GPU_PIXEL_DRAW")
        self.assertEqual(result["sourceFileSHA256"], hashlib.sha256(self.safe_file.read_bytes()).hexdigest())
        self.assertFalse(result["gpuRenderingVerified"])
        self.assertFalse(result["actualHardwareRerun"])
        self.assertNotIn("DO_NOT_PRINT", json.dumps(result))
        self.assertNotIn(str(self.base), json.dumps(result))
        self.assertEqual(before, {str(path): (path.stat().st_mode, path.read_bytes()) for path in self.base.rglob("*.json")})

    def test_no_private_admission_file_ever_read(self):
        self.write(self.run / "admission_private.json", {"privateCanary": "MUST_NOT_READ"})
        original = reader.os.open
        def opening(path, *args, **kwargs):
            self.assertNotIn("admission_private", str(path))
            return original(path, *args, **kwargs)
        with mock.patch.object(reader.os, "open", side_effect=opening):
            self.assertEqual(self.recover()["status"], "TEST_ONLY")

    def test_loopback_must_match_exact_exported_startup_record(self):
        changed = deepcopy(self.current)
        changed["timestamp"] = "2026-10-15T01:02:05+00:00"
        self.write(self.export_file, changed)
        self.assert_unverified()

    def test_duplicate_export_record_is_ambiguous(self):
        self.write(self.export / ("startup-safe-" + "f" * 24 + ".json"), self.current)
        self.assert_unverified()

    def test_duplicate_native_admissions_are_ambiguous(self):
        another = self.diagnostics / ("20261015T010203-" + "f" * 32)
        another.mkdir(mode=0o700)
        self.write(another / "admission_safe.json", self.admission)
        self.assert_unverified()

    def test_stale_and_future_admission_rejected(self):
        for stamp in ("2026-10-15T00:58:03+00:00", "2026-10-15T01:02:05+00:00"):
            with self.subTest(stamp=stamp):
                self.admission["observedAt"] = stamp
                self.write(self.safe_file, self.admission)
                self.assert_unverified()

    def test_fixed_stale_reason_code_preserved(self):
        self.admission["observedAt"] = "2026-10-15T00:58:03+00:00"
        self.write(self.safe_file, self.admission)
        self.assertEqual(self.recover()["reasonCode"], "NATIVE_ADMISSION_STALE")

    def test_failed_testonly_software_and_wrong_scope_never_verified(self):
        for patch in ({"status": "BLOCKED"}, {"testOnly": True}, {"gpuRenderingVerified": False},
                      {"gpuProfile": "swiftshader"}, {"verificationScope": "MOCK"}, {"model": "untrusted-path"},
                      {"driverVersion": "560 PRIVATE"}, {"renderExecuted": True}):
            with self.subTest(patch=patch):
                self.write(self.safe_file, {**self.admission, **patch})
                self.assert_unverified()

    def test_invalid_source_memory_and_shared_memory_fail_closed(self):
        for patch in ({"sourceVerification": {"status": "FAIL"}}, {"physicalMemoryMiB": True},
                      {"availableMemoryMiB": 17000}, {"sharedMemory": {"capacityBytes": 64, "availableBytes": 64}},
                      {"vramBudgetBytes": 16384 * 1024**2}):
            with self.subTest(patch=patch):
                self.write(self.safe_file, {**self.admission, **patch})
                self.assert_unverified()

    def test_current_failure_or_testonly_never_overwritten(self):
        for patch in ({"exitCode": 2}, {"status": "BLOCKED"}, {"safeDiagnostics": {"testOnly": True}},
                      {"gpuRenderingVerified": True}, {"renderAllowed": True}):
            with self.subTest(patch=patch):
                current = {**self.current, **patch}
                result = reader.recover(_current_record=current, _base=self.base, _export_root=self.shared)
                self.assertEqual(result["status"], "UNVERIFIED")

    def test_private_file_mode_and_symlink_rejected(self):
        self.safe_file.chmod(0o644)
        self.assert_unverified()
        self.safe_file.chmod(0o600)
        target = self.run / "fixture.json"
        self.safe_file.rename(target)
        self.safe_file.symlink_to(target)
        self.assert_unverified()

    def test_receipt_root_and_directory_identity_must_match(self):
        for key in ("rootIdentity", "directoryIdentity"):
            changed = deepcopy(self.receipt)
            changed[key]["inode"] += 1
            self.write(self.session / "EXPORT_RECEIPT.json", changed)
            self.assert_unverified()

    def test_missing_receipt_and_missing_admission_never_guess_latest(self):
        self.safe_file.unlink()
        self.assert_unverified()
        (self.session / "EXPORT_RECEIPT.json").unlink()
        self.assert_unverified()

    def test_duplicate_and_nonfinite_json_rejected(self):
        for body in (b'{"status":"GPU_VERIFIED","status":"BLOCKED"}', b'{"value":NaN}'):
            with self.subTest(body=body), self.assertRaises(reader.RecoveryError):
                reader._object(body)


class LoopbackTests(unittest.TestCase):
    def response(self, body=b"{}", status=200):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = status
        response.read.return_value = body
        return response

    def test_fixed_loopback_without_proxy_and_bounded_timeout(self):
        response = self.response()
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(reader.urllib.request, "build_opener", return_value=opener) as build:
            self.assertEqual(reader.fetch_current(), {})
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], reader._NoRedirect)
        opener.open.assert_called_once_with("http://127.0.0.1:8000/diagnostics", timeout=3)
        response.read.assert_called_once_with(reader.LIMIT + 1)

    def test_http_error_oversize_and_redirect_rejected(self):
        for response in (self.response(status=503), self.response(b"x" * (reader.LIMIT + 1))):
            opener = mock.Mock()
            opener.open.return_value = response
            with mock.patch.object(reader.urllib.request, "build_opener", return_value=opener), \
                 self.assertRaises(reader.RecoveryError):
                reader.fetch_current()
        with self.assertRaises(reader.RecoveryError):
            reader._NoRedirect().redirect_request(None, None, None, None, None, None)

    def test_no_cli_paths_and_unavailable_endpoint_do_not_initialize_hardware(self):
        with mock.patch.object(reader, "fetch_current", side_effect=OSError("PRIVATE_CANARY")):
            result = reader.recover()
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertFalse(result["testOnly"])
        self.assertFalse(result["actualHardwareRerun"])
        self.assertNotIn("PRIVATE_CANARY", json.dumps(result))

    def test_unknown_exception_or_recovery_message_stays_private_and_errno_is_static(self):
        for error in (RuntimeError("PRIVATE_CANARY"), reader.RecoveryError("PRIVATE_CANARY"),
                      PermissionError(errno.EACCES, "PRIVATE_CANARY", "/private/secret-canary")):
            with self.subTest(error_type=type(error).__name__), \
                 mock.patch.object(reader, "fetch_current", side_effect=error):
                result = reader.recover()
            self.assertEqual(result["reasonCode"], "EXISTING_EVIDENCE_UNVERIFIED")
            self.assertNotIn("CANARY", json.dumps(result))
            self.assertNotIn("secret-canary", json.dumps(result))
            if isinstance(error, OSError):
                self.assertEqual(result["errnoName"], "EACCES")
            else:
                self.assertNotIn("errnoName", result)


if __name__ == "__main__":
    unittest.main()
