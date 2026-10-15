"""CPU-only success-result transport tests; every mocked PASS is TEST_ONLY."""
import errno
from http.server import HTTPServer
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / "gcube-diagnostic-image-v1"))
import startup
import records
import service
import healthcheck

CANARY = "result-private-secret-canary"


def mock_checked_result(*, admitted_test=False):
    """Native result schema fixture, not an execution of any GPU operation."""
    reasons = {"A": "DEVICE_NODES_VISIBLE", "B": "NVIDIA_QUERY_VISIBLE", "C": "CHROMIUM_STARTED",
               "D": "WEBGL2_CONTEXT_CREATED", "E": "NVIDIA_DEVICE_MATCHED", "F": "WEBGL_DRAW_VERIFIED"}
    diagnostics = {"schema_version": 1, "render_mode": "gpu-required", "gpu_profile": "vulkan",
        "failed_stage": None, "reason_code": "VERIFIED", "browser_version": "155.0.8059.79",
        "stages": [{"id": name, "status": "PASS", "reason_code": reason} for name, reason in reasons.items()],
        "nvidia_devices": [{"name": "NVIDIA GeForce RTX 4080 SUPER", "driver_version": "580.105.08",
                            "memory_total_mib": 16384, "uuid": "GPU-01234567-89ab-cdef-0123-456789abcdef"}],
        "webgl": {"context_available": True, "webgl2": True, "context_version": 2,
                  "debug_renderer_available": True, "draw_passed": True, "software_renderer": False,
                  "webgl_error": 0, "pixel": [255, 0, 0, 255], "max_texture_size": 32768,
                  "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 SUPER)", "password": CANARY},
        "runtime": {"environment": {"NVIDIA_VISIBLE_DEVICES": {"present": True, "selection": "configured",
                                                                "value": CANARY}},
                    "devices": {"nvidia": 2, "dri": 1}, "libraries": {"egl": True, "vulkan": True,
                      "nvidia_egl": True, "nvidia_vulkan": True}}, "token": CANARY}
    safe = {"schema": "RTX_GPU_ADMISSION_V1", "status": "TEST_ONLY" if admitted_test else "GPU_VERIFIED",
            "testOnly": admitted_test, "gpuRenderingVerified": not admitted_test,
            "verificationScope": "STARTUP_NATIVE_GPU_PIXEL_DRAW", "renderMode": "gpu-required",
            "gpuProfile": "vulkan", "autoRender": False, "renderExecuted": False,
            "visualQualityVerified": False, "sourceVerification": {"status": "PASS", "files": 160}}
    private = {**safe, "allocation": {"uuid": "GPU-01234567-89ab-cdef-0123-456789abcdef", "token": CANARY},
               "probe": {"gpu_rendering_verified": True, "render_mode": "gpu-required",
                         "gpu_profile": "vulkan", "hardware_status": "visible", "diagnostics": diagnostics}}
    admission = SimpleNamespace(safe_report=safe, private_report=private, test_only=admitted_test)
    return (SimpleNamespace(), SimpleNamespace(), admission)


class SuccessResultTests(unittest.TestCase):
    def worker_record(self, checked):
        with patch.object(startup, "_checks", return_value=(checked, None)):
            return startup._worker_record(object(), object(), True)

    def assert_safe_success(self, record):
        self.assertEqual((record["status"], record["errorCode"], record["exitCode"]), ("DIAGNOSTIC_ONLY", "DIAGNOSTIC_ONLY", 0))
        self.assertFalse(record["gpuRenderingVerified"])
        self.assertFalse(record["renderAllowed"])
        self.assertTrue(record["safeDiagnostics"]["testOnly"])
        gpu = record["safeDiagnostics"]["gpu"]
        self.assertEqual(gpu["reason_code"], "VERIFIED")
        self.assertEqual(gpu["gpu_profile"], "vulkan")
        self.assertEqual({item["id"] for item in gpu["stages"] if item["status"] == "PASS"}, set("ABCDEF"))
        self.assertTrue(gpu["webgl"]["draw_passed"])
        self.assertEqual(gpu["webgl"]["pixel"], [255, 0, 0, 255])
        self.assertEqual(gpu["nvidia_devices"][0]["driver_version"], "580.105.08")
        self.assertEqual(gpu["nvidia_devices"][0]["memory_total_mib"], 16384)
        encoded = json.dumps(record)
        for secret in (CANARY, "GPU-01234567", "allocation", "ANGLE", "GeForce"):
            self.assertNotIn(secret, encoded)

    def test_legacy_success_shape_omits_details_and_fixed_worker_preserves_them(self):
        baseline_path = os.environ.get("WORLD_ENGINE_TEST_BASELINE_STARTUP")
        if baseline_path:
            # CI mounts this read-only source from pinned baseline d1f6041.
            name = "world_engine_baseline_startup_test_only"
            spec = importlib.util.spec_from_file_location(name, baseline_path)
            baseline = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {name: baseline}):
                spec.loader.exec_module(baseline)
                with patch.object(baseline, "_checks", return_value=(mock_checked_result(), None)):
                    before = baseline._worker_record(object(), object(), True)
        else:
            # Exact previous success factory for local tests without the CI mount.
            before = records.make_record("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_ONLY", 0, mode="diagnostic", test_only=True)
        self.assertNotIn("gpu", before["safeDiagnostics"])
        after = self.worker_record(mock_checked_result())
        self.assert_safe_success(after)

    def test_original_test_admission_is_supported_only_as_explicit_test_only(self):
        self.assert_safe_success(self.worker_record(mock_checked_result(admitted_test=True)))
        with patch.object(startup, "_checks", return_value=(mock_checked_result(admitted_test=True), None)):
            blocked = startup._worker_record(object(), object(), False)
        self.assertEqual((blocked["stage"], blocked["errorCode"], blocked["exitCode"]),
                         ("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_RECORD_INVALID", 1))
        self.assertNotIn("gpu", blocked["safeDiagnostics"])

    def test_malformed_or_missing_success_evidence_is_explicitly_invalid(self):
        def mutate(checked, case):
            admission = checked[2]
            if case == "private-probe-missing":
                admission.private_report.pop("probe")
            elif case == "diagnostics-missing":
                admission.private_report["probe"].pop("diagnostics")
            elif case == "scope-mismatch":
                admission.safe_report["verificationScope"] = "PROCESS_EXISTS"
            elif case == "test-marker-mismatch":
                admission.safe_report["testOnly"] = True
            elif case == "source-not-verified":
                admission.safe_report["sourceVerification"]["status"] = "FAIL"
            else:
                diagnostics = admission.private_report["probe"]["diagnostics"]
                if case == "failed-stage":
                    diagnostics["failed_stage"] = "F"
                elif case == "invalid-schema-type":
                    diagnostics["schema_version"] = True
                elif case == "non-verified-reason":
                    diagnostics["reason_code"] = "WEBGL_DRAW_FAILED"
                elif case == "failed-stage-entry":
                    diagnostics["stages"][1]["status"] = "FAIL"
                elif case == "duplicate-stage":
                    diagnostics["stages"][5]["id"] = "A"
                elif case == "software-renderer":
                    diagnostics["webgl"]["software_renderer"] = True
                elif case == "draw-failed":
                    diagnostics["webgl"]["draw_passed"] = False
                elif case == "wrong-pixel":
                    diagnostics["webgl"]["pixel"] = [0, 0, 0, 255]
                elif case == "invalid-error-type":
                    diagnostics["webgl"]["webgl_error"] = False
        cases = ("private-probe-missing", "diagnostics-missing", "scope-mismatch", "test-marker-mismatch",
                 "source-not-verified", "failed-stage", "non-verified-reason", "failed-stage-entry",
                 "duplicate-stage", "software-renderer", "draw-failed", "wrong-pixel", "invalid-schema-type", "invalid-error-type")
        for case in cases:
            with self.subTest(case=case):
                checked = mock_checked_result()
                mutate(checked, case)
                result = self.worker_record(checked)
                self.assertEqual((result["stage"], result["errorCode"], result["exitCode"]),
                                 ("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_RECORD_INVALID", 1))
                self.assertFalse(result["gpuRenderingVerified"])
                self.assertFalse(result["renderAllowed"])
                self.assertNotIn("gpu", result["safeDiagnostics"])

    def test_existing_first_failure_record_is_returned_identically(self):
        for stage, code, exit_code in (("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2),
                                      ("WEBGL2", "GPU_WEBGL_UNVERIFIED", 2),
                                      ("STORAGE", "STORAGE_VALIDATION_FAILED", 1)):
            with self.subTest(stage=stage):
                first = records.make_record(stage, code, exit_code, mode="diagnostic", test_only=True)
                with patch.object(startup, "_checks", return_value=(None, first)):
                    self.assertIs(startup._worker_record(object(), object(), True), first)

    @unittest.skipUnless(hasattr(startup.os, "fork"), "Native worker transport requires Linux fork")
    def test_actual_fork_pipe_roundtrip_and_existing_http_routes_keep_safe_success_details(self):
        args = SimpleNamespace(vram_budget_gib=8.0, port=8000)
        with patch.object(startup, "_checks", return_value=(mock_checked_result(), None)):
            result = startup._diagnostic_worker(object(), args, test_only=True, timeout=2)
        self.assert_safe_success(result)
        self.assert_safe_success(records.safe_record(result))
        server = HTTPServer(("127.0.0.1", 0), service.diagnostic_handler(result))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = "http://127.0.0.1:" + str(server.server_port)
        try:
            with opener.open(base + "/diagnostics", timeout=2) as response:
                self.assertEqual(response.status, 200)
                diagnostic = json.load(response)
            self.assert_safe_success(diagnostic)
            with opener.open(base + "/healthz", timeout=2) as response:
                alive = json.load(response)
            self.assertTrue(healthcheck.check_health(alive, "diagnostic"))
            with self.assertRaises(urllib.error.HTTPError) as not_ready:
                opener.open(base + "/readyz", timeout=2)
            self.assertEqual(not_ready.exception.code, 503)
            self.assertFalse(json.load(not_ready.exception)["ready"])
            with self.assertRaises(urllib.error.HTTPError) as no_render:
                opener.open(urllib.request.Request(base + "/render", method="POST", data=b""), timeout=2)
            self.assertEqual(no_render.exception.code, 405)
            self.assertFalse(json.load(no_render.exception)["renderAllowed"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_old_startup_privilege_failure_publishes_primary_before_secondary(self):
        first = records.make_record("WEBGL2", "GPU_WEBGL_UNVERIFIED", 2, mode="diagnostic", test_only=True)
        operations = SimpleNamespace(account=lambda: SimpleNamespace(pw_uid=1000, pw_gid=1000))
        published, serve = [], Mock()
        def denied(account):
            raise PermissionError(errno.EPERM, CANARY)
        with patch.object(startup, "_publish", side_effect=lambda record: published.append(record)):
            code = startup.main([], operations=operations, environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic"},
                worker=lambda *args, **options: first, privilege_drop=denied, diagnostic_service=serve)
        self.assertIs(published[0], first)
        self.assertEqual(published[1]["stage"], "UID_GID")
        self.assertEqual(code, 1)
        serve.assert_not_called()
        self.assertNotIn(CANARY, json.dumps(published))


if __name__ == "__main__":
    unittest.main()
