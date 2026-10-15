"""Focused diagnostic safety tests; mock GPU facts are never hardware evidence."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import healthcheck
import records
import service


class RecordTests(unittest.TestCase):
    def test_unknown_codes_exception_messages_and_env_canaries_never_emitted(self):
        canary = "diagnostic-privacy-canary-not-a-credential"
        record = records.make_record(canary, canary, 2, exception_type=canary,
            gpu_diagnostics={"token": canary, "webgl": {"renderer": "NVIDIA " + canary},
                             "environment": {"SECRET": canary}}, test_only=True)
        record["rawException"] = canary
        record["safeDiagnostics"]["secret"] = canary
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            records.emit_record(record)
        for body in (out.getvalue(), err.getvalue()):
            self.assertNotIn(canary, body)
            value = json.loads(body)
            self.assertEqual(value["stage"], "UNEXPECTED")
            self.assertEqual(value["errorCode"], "STARTUP_UNEXPECTED_EXCEPTION")
            self.assertFalse(value["gpuRenderingVerified"])
            self.assertFalse(value["renderAllowed"])

    def test_gpu_nested_reasons_preserved_without_uuid_or_identity_strings(self):
        canary = "GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        value = {"reason_code": "GPU_WEBGL_UNVERIFIED", "failed_stage": "D",
                 "webgl": {"context_available": False, "unmasked_renderer": "NVIDIA " + canary,
                           "reason_code": "WEBGL2_CONTEXT_UNAVAILABLE"},
                 "profile_attempts": [{"backend": "egl", "status": "failed",
                    "error_code": "GPU_WEBGL_UNVERIFIED", "diagnostics": {
                        "reason_code": "GPU_WEBGL_UNVERIFIED", "failed_stage": "D"}}],
                 "nvidia_devices": [{"name": "NVIDIA GeForce RTX 4080 SUPER",
                                     "uuid": canary, "driver_version": "560.35.03", "memory_total_mib": 16384}],
                 "runtime": {"environment": {"NVIDIA_VISIBLE_DEVICES": {
                     "present": True, "selection": "configured", "value": canary}}}}
        record = records.make_record("WEBGL2", "GPU_WEBGL_UNVERIFIED", 2, gpu_diagnostics=value)
        text = json.dumps(record)
        self.assertNotIn(canary, text)
        gpu = record["safeDiagnostics"]["gpu"]
        self.assertEqual(gpu["failed_stage"], "D")
        self.assertEqual(gpu["webgl"]["reason_code"], "WEBGL2_CONTEXT_UNAVAILABLE")
        self.assertEqual(gpu["profile_attempts"][0]["backend"], "egl")
        self.assertEqual(gpu["nvidia_devices"][0]["memory_total_mib"], 16384)

    def test_native_and_standalone_sanitizers_preserve_safe_numeric_facts(self):
        # The immutable image imports the original sanitizer. Its legitimate-name
        # requirement must remain intact; UUID canaries belong in UUID fields.
        # CI mounts this diagnostic overlay separately from the immutable repo.
        # Resolve the original module from the image/PYTHONPATH, with the source
        # checkout as the local fallback, rather than assuming a sibling layout.
        engine_candidates = [Path("/opt/rtx-package/repo/world-simulation-shorts-engine"),
                             HERE.parents[1], *(Path(item) for item in sys.path if item)]
        engine = next(path for path in engine_candidates if (path / "deployment/gcube/gpu.py").is_file())
        canary = "GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        raw = {"reason_code": "GPU_WEBGL_UNVERIFIED", "failed_stage": "D",
               "webgl": {"unmasked_renderer": "NVIDIA " + canary,
                         "reason_code": "WEBGL2_CONTEXT_UNAVAILABLE"},
               "nvidia_devices": [{"name": "NVIDIA GeForce RTX 4080 SUPER", "uuid": canary,
                                   "driver_version": "560.35.03", "memory_total_mib": 16384}]}
        standalone = records._safe_gpu(raw)
        with mock.patch.object(sys, "path", [str(engine), *sys.path]):
            from deployment.gcube import gpu as original_gpu
            self.assertEqual(Path(original_gpu.__file__).resolve(),
                             (engine / "deployment/gcube/gpu.py").resolve())
            native = records._engine_sanitize(raw)
            record = records.make_record("WEBGL2", "GPU_WEBGL_UNVERIFIED", 2, gpu_diagnostics=raw)
        for safe in (standalone, native):
            self.assertEqual(safe["failed_stage"], "D")
            self.assertEqual(safe["webgl"]["reason_code"], "WEBGL2_CONTEXT_UNAVAILABLE")
            self.assertEqual(safe["nvidia_devices"][0],
                             {"driver_version": "560.35.03", "memory_total_mib": 16384})
            self.assertNotIn(canary, json.dumps(safe))
        # Worker envelopes must use this idempotent second allowlist, rather
        # than requiring removed raw names again through the original parser.
        self.assertEqual(records.safe_record(records.safe_record(record)), records.safe_record(record))
        self.assertEqual(records.safe_record(record)["safeDiagnostics"]["gpu"]["nvidia_devices"],
                         [{"driver_version": "560.35.03", "memory_total_mib": 16384}])

    def test_errno_and_exception_type_are_bounded(self):
        record = records.make_record("STORAGE", "STORAGE_PERMISSION_DENIED", 1,
                                     errno_value=13, exception_type="PermissionError")
        self.assertEqual(record["safeDiagnostics"], {"errno": 13, "errnoName": "EACCES",
                                                    "exceptionType": "PermissionError"})
        self.assertEqual(records.make_record("STORAGE", "STORAGE_PERMISSION_DENIED", -1,
                          errno_value=True, exception_type="Exception: secret")["safeDiagnostics"], {})

    def test_interrupted_worker_code_survives_safe_normalization(self):
        record = records.make_record("UNEXPECTED", "DIAGNOSTIC_WORKER_INTERRUPTED", 143, mode="diagnostic")
        record["rawException"] = "diagnostic-privacy-canary"
        safe = records.safe_record(record)
        self.assertEqual(safe["errorCode"], "DIAGNOSTIC_WORKER_INTERRUPTED")
        self.assertEqual(safe["exitCode"], 143)
        self.assertEqual(safe["status"], "BLOCKED")
        self.assertFalse(safe["renderAllowed"])
        self.assertNotIn("canary", json.dumps(safe))

    def test_primary_atomic_private_persistence_does_not_change_parent_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            before = stat.S_IMODE(parent.stat().st_mode)
            destination = parent / "private"
            record = records.make_record("STORAGE", "STORAGE_READ_ONLY", 1)
            self.assertEqual(records.persist_record(record, roots=[destination]),
                             {"persisted": True, "tier": "primary"})
            files = list(destination.iterdir())
            self.assertEqual(len(files), 1)
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(files[0].stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), before)
            self.assertEqual(json.loads(files[0].read_text())["errorCode"], "STORAGE_READ_ONLY")

    def test_symlink_and_foreign_owner_primary_refused_without_chmod_chown(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            target = parent / "target"
            target.mkdir(mode=0o700)
            link = parent / "link"
            link.symlink_to(target, target_is_directory=True)
            record = records.make_record("STORAGE", "STORAGE_PATH_UNSAFE", 1)
            # No fallback files escape test cleanup, and no chmod/chown repair is attempted.
            with mock.patch.object(records.tempfile, "mkdtemp", side_effect=PermissionError), \
                    mock.patch.object(records.os, "chmod", side_effect=AssertionError("must not chmod")), \
                    mock.patch.object(records.os, "chown", side_effect=AssertionError("must not chown")):
                self.assertEqual(records.persist_record(record, roots=[link]),
                                 {"persisted": False, "tier": "stderr_only"})
                with mock.patch.object(records.os, "geteuid", return_value=os.geteuid() + 1):
                    self.assertEqual(records.persist_record(record, roots=[target]),
                                     {"persisted": False, "tier": "stderr_only"})
            self.assertEqual(list(target.iterdir()), [])

    def test_unwritable_primary_falls_back_and_labels_non_durable_tier(self):
        with tempfile.TemporaryDirectory() as temporary:
            fallback = Path(temporary) / "local"
            fallback.mkdir(mode=0o700)
            with mock.patch.object(records.tempfile, "mkdtemp", return_value=str(fallback)):
                result = records.persist_record(records.make_record("STORAGE", "STORAGE_UNAVAILABLE", 1),
                                                roots=[Path(temporary) / "missing" / ".." / "bad"])
            self.assertEqual(result, {"persisted": True, "tier": "local_fallback"})
            self.assertEqual(len(list(fallback.glob("startup-*.json"))), 1)

    def test_failed_persistence_leaves_stderr_record_available(self):
        record = records.make_record("STORAGE", "STORAGE_PERMISSION_DENIED", 1)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(records, "_persist", side_effect=PermissionError), \
                mock.patch.object(records.tempfile, "mkdtemp", side_effect=PermissionError), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            records.emit_record(record)
            result = records.persist_record(record)
        self.assertEqual(result["tier"], "stderr_only")
        self.assertEqual(json.loads(err.getvalue())["errorCode"], "STORAGE_PERMISSION_DENIED")


class HealthTests(unittest.TestCase):
    def test_diagnostic_liveness_not_gpu_or_readiness(self):
        body = {**records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, mode="diagnostic"),
                "diagnosticServiceAlive": True}
        self.assertTrue(healthcheck.check_health(body, "diagnostic"))
        self.assertFalse(healthcheck.check_health(body, "normal"))
        for field in ("schema", "startupMode", "status", "diagnosticServiceAlive", "gpuRenderingVerified", "renderAllowed"):
            changed = dict(body)
            changed.pop(field)
            self.assertFalse(healthcheck.check_health(changed, "diagnostic"), field)
        self.assertFalse(healthcheck.check_health({**body, "renderAllowed": True}, "diagnostic"))
        self.assertFalse(healthcheck.check_health({**body, "gpuRenderingVerified": True}, "diagnostic"))
        self.assertFalse(healthcheck.check_health({**body, "exitCode": 0}, "diagnostic"))
        self.assertFalse(healthcheck.check_health({**body, "status": "DIAGNOSTIC_ONLY"}, "diagnostic"))

    def test_normal_health_accepts_only_original_verified_native_draw(self):
        body = {"status": "GPU_VERIFIED", "testOnly": False, "gpuRenderingVerified": True,
                "renderMode": "gpu-required", "verificationScope": "STARTUP_NATIVE_GPU_PIXEL_DRAW"}
        self.assertTrue(healthcheck.check_health(body, "normal"))
        self.assertFalse(healthcheck.check_health({**body, "testOnly": True}, "normal"))
        self.assertFalse(healthcheck.check_health(body, "diagnostic"))
        self.assertFalse(healthcheck.check_health(body, "arbitrary"))


class ServiceTests(unittest.TestCase):
    def test_privileged_or_device_group_identity_refuses_service(self):
        record = records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, mode="diagnostic")
        for uid, gid, groups in ((0, 0, []), (1000, 1000, [44]), (1000, 0, [])):
            with mock.patch.object(service.os, "geteuid", return_value=uid), \
                    mock.patch.object(service.os, "getegid", return_value=gid), \
                    mock.patch.object(service.os, "getgroups", return_value=groups), \
                    mock.patch.object(service, "emit_record") as emit:
                factory = mock.Mock()
                self.assertEqual(service.serve_diagnostic(record, server_factory=factory), 2)
                factory.assert_not_called()
                self.assertEqual(emit.call_args.args[0]["errorCode"], "DIAGNOSTIC_SERVICE_REFUSED")

    def test_bounded_service_reports_blocked_denies_render_and_keeps_exit(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        record = records.make_record("WEBGL2", "GPU_WEBGL_UNVERIFIED", 2, mode="diagnostic", test_only=True)
        result = []
        with mock.patch.object(service.os, "geteuid", return_value=1000), \
                mock.patch.object(service.os, "getegid", return_value=1000), \
                mock.patch.object(service.os, "getgroups", return_value=[]):
            thread = threading.Thread(target=lambda: result.append(service.serve_diagnostic(
                record, host="127.0.0.1", port=port, max_seconds=1)))
            thread.start()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            url = f"http://127.0.0.1:{port}"
            for _ in range(30):
                try:
                    with opener.open(url + "/healthz", timeout=0.5) as response:
                        body = json.load(response)
                    break
                except OSError:
                    time.sleep(0.01)
            else:
                self.fail("diagnostic test server did not become reachable")
            self.assertTrue(healthcheck.check_health(body, "diagnostic"))
            self.assertEqual(body["status"], "BLOCKED")
            for path, method, status in (("/readyz", "GET", 503), ("/render", "POST", 405),
                                         ("/render", "GET", 404), ("/healthz?secret=canary", "GET", 404)):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    opener.open(urllib.request.Request(url + path, method=method), timeout=0.5)
                self.assertEqual(caught.exception.code, status)
                self.assertNotIn(b"canary", caught.exception.read())
            with opener.open(url + "/diagnostics", timeout=0.5) as response:
                self.assertEqual(json.load(response)["errorCode"], "GPU_WEBGL_UNVERIFIED")
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [2])

    def test_diagnostic_only_ttl_still_exits_nonzero(self):
        fake = mock.Mock()
        record = records.make_record("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_ONLY", 0, mode="diagnostic")
        with mock.patch.object(service.os, "geteuid", return_value=1000), \
                mock.patch.object(service.os, "getegid", return_value=1000), \
                mock.patch.object(service.os, "getgroups", return_value=[]), \
                mock.patch.object(service.time, "monotonic", side_effect=[0, 2]):
            self.assertEqual(service.serve_diagnostic(record, max_seconds=1,
                                                       server_factory=lambda *_: fake), 2)
        fake.server_close.assert_called_once()

    def test_sigterm_stops_service_and_restores_handlers_without_success_exit(self):
        installed = {}
        def signal_test_seam(number, handler):
            previous = installed.get(number, signal.SIG_DFL)
            installed[number] = handler
            return previous
        fake = mock.Mock()
        fake.handle_request.side_effect = lambda: installed[signal.SIGTERM](signal.SIGTERM, None)
        record = records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, mode="diagnostic")
        with mock.patch.object(service.os, "geteuid", return_value=1000), \
                mock.patch.object(service.os, "getegid", return_value=1000), \
                mock.patch.object(service.os, "getgroups", return_value=[]), \
                mock.patch.object(service.signal, "signal", side_effect=signal_test_seam):
            self.assertEqual(service.serve_diagnostic(record, server_factory=lambda *_: fake), 2)
        self.assertEqual(installed[signal.SIGTERM], signal.SIG_DFL)
        self.assertEqual(installed[signal.SIGINT], signal.SIG_DFL)
        fake.server_close.assert_called_once()

    def test_service_failure_records_fixed_code_without_traceback(self):
        record = records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, mode="diagnostic")
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(service.os, "geteuid", return_value=1000), \
                mock.patch.object(service.os, "getegid", return_value=1000), \
                mock.patch.object(service.os, "getgroups", return_value=[]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(service.serve_diagnostic(record,
                server_factory=mock.Mock(side_effect=RuntimeError("diagnostic-privacy-canary"))), 2)
        self.assertNotIn("canary", err.getvalue())
        self.assertEqual(json.loads(err.getvalue())["errorCode"], "DIAGNOSTIC_SERVICE_FAILED")


if __name__ == "__main__":
    unittest.main()
