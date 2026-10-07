"""Real HTTP checks for the non-authenticating, read-only boot listener."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import socket
import sys
import unittest

APP = Path(__file__).resolve().parents[2]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from deployment.gcube.boot_status import BootStatusServer, safe_error_code


class BootStatusTests(unittest.TestCase):
    def setUp(self):
        self.status = BootStatusServer("127.0.0.1", 0).start()

    def tearDown(self):
        self.status.close()

    def call(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.status.port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_default_bind_and_initial_status(self):
        self.assertEqual(BootStatusServer().server_address, ("0.0.0.0", 8000))
        status, headers, body = self.call("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True, "authentication_required": True,
                                           "engine_ready": False, "phase": "checking",
                                           "error_code": None})
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Connection"], "close")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_pod_ip_and_istio_forwarded_headers_do_not_block_liveness(self):
        headers = {"Host": "10.34.9.12:8000", "X-Forwarded-Host": "workload.gcube.ai",
                   "X-Forwarded-Proto": "https", "Origin": "https://untrusted.example"}
        for path in ("/api/health", "/healthz"):
            with self.subTest(path=path):
                status, _, body = self.call("GET", path, headers=headers)
                self.assertEqual(status, 200)
                self.assertFalse(json.loads(body)["engine_ready"])
                self.assertNotIn(b"untrusted", body)
                self.assertNotIn(b"10.34", body)
        self.assertEqual(self.call("POST", "/auth/login", "{}", headers)[0], 405)

    def test_head_and_readiness_do_not_claim_engine_ready(self):
        for path in ("/healthz", "/api/health", "/", "/auth/login"):
            status, headers, body = self.call("HEAD", path)
            self.assertEqual(status, 200)
            self.assertGreater(int(headers["Content-Length"]), 0)
            self.assertEqual(body, b"")
        for method in ("GET", "HEAD"):
            status, _, body = self.call(method, "/readyz")
            self.assertEqual(status, 503)
            if body:
                self.assertFalse(json.loads(body)["engine_ready"])

    def test_status_page_uses_fixed_korean_messages_without_login_form(self):
        self.status.set_phase("blocked", "WORLD_ENGINE_OWNER_CODE_REQUIRED")
        for path in ("/", "/auth/login"):
            status, headers, body = self.call("GET", path)
            self.assertEqual(status, 200)
            text = body.decode()
            self.assertIn("WORLD_ENGINE_OWNER_CODE", text)
            self.assertIn("16자", text)
            self.assertIn("과금", text)
            self.assertNotIn("<form", text)
            self.assertNotIn("<script", text)
            self.assertLess(len(body), 6000)
            self.assertIn("form-action 'none'", headers["Content-Security-Policy"])

    def test_known_storage_gpu_and_dependency_errors_are_safe_and_helpful(self):
        for code, expected in (("STORAGE_MOUNT_REQUIRED", "/world-storage"),
                               ("GPU_WEBGL_UNVERIFIED", "CPU로 자동 전환하지"),
                               ("GPU_BROWSER_UNAVAILABLE", "필수 실행환경"),
                               ("CERTIFIED_SOURCE_MISMATCH", "필수 실행환경"),
                               ("MISSING_DEPENDENCY", "필수 실행환경"),
                               ("CERTIFICATE_INCOMPLETE", "필수 실행환경"),
                               ("ASSETS_INVALID", "필수 실행환경")):
            with self.subTest(code=code):
                self.status.set_phase("blocked", code)
                status, _, body = self.call("GET", "/auth/login")
                self.assertEqual(status, 200)
                self.assertIn(expected, body.decode())
                self.assertEqual(json.loads(self.call("GET", "/healthz")[2])["error_code"], code)

    def test_arbitrary_errors_and_raw_values_are_not_disclosed(self):
        secrets = ("OWNER_SECRET_ABC123", "<script>alert(1)</script>",
                   "/private/owner-code.txt", "x" * 10000, None, 42, {"secret": "password"})
        for value in secrets:
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(safe_error_code(value), "STARTUP_BLOCKED")
                self.status.set_phase("blocked", value)
                record = json.loads(self.call("GET", "/api/health")[2])
                self.assertEqual(record["error_code"], "STARTUP_BLOCKED")
                page = self.call("GET", "/")[2].decode()
                if isinstance(value, str):
                    self.assertNotIn(value, page)

    def test_engine_api_assets_and_arbitrary_paths_are_unavailable(self):
        for path in ("/api/projects", "/auth/session", "/gcube/benchmark.json",
                     "/static/app.js", "/../../etc/passwd", "/%2e%2e/owner-code.txt"):
            with self.subTest(path=path):
                status, _, body = self.call("GET", path)
                self.assertEqual(status, 503)
                self.assertEqual(json.loads(body)["error"]["code"], "ENGINE_NOT_READY")
                self.assertNotIn(path.encode(), body)

    def test_all_state_changes_are_rejected_without_reading_body(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
            with self.subTest(method=method):
                status, _, body = self.call(method, "/auth/login", "private-never-echoed")
                self.assertEqual(status, 405)
                self.assertEqual(json.loads(body)["error"]["code"], "ENGINE_NOT_READY")
                self.assertNotIn(b"private", body)
        # Claim a huge body and send none: the response must not wait for it.
        connection = http.client.HTTPConnection("127.0.0.1", self.status.port, timeout=3)
        connection.putrequest("POST", "/api/projects")
        connection.putheader("Content-Length", "1000000000000")
        connection.endheaders()
        response = connection.getresponse()
        self.assertEqual(response.status, 405)
        self.assertNotIn(b"project_id", response.read())
        connection.close()

    def test_unknown_method_and_parser_failures_do_not_echo_input(self):
        status, _, body = self.call("SECRETLEAK", "/private/path")
        self.assertEqual(status, 405)
        self.assertNotIn(b"SECRETLEAK", body)
        self.assertNotIn(b"/private/path", body)
        with socket.create_connection(("127.0.0.1", self.status.port), timeout=3) as stream:
            stream.sendall(b"GET /private/path HTTP/SECRETLEAK\r\nHost: leak.example\r\n\r\n")
            content = bytearray()
            while True:
                chunk = stream.recv(4096)
                if not chunk:
                    break
                content.extend(chunk)
        self.assertTrue(content.startswith(b"HTTP/1.0 400"))
        self.assertIn(b"ENGINE_NOT_READY", content)
        self.assertNotIn(b"SECRETLEAK", content)
        self.assertNotIn(b"leak.example", content)

    def test_close_is_idempotent_and_listener_can_restart(self):
        self.assertIs(self.status.start(), self.status)
        port = self.status.port
        self.status.close()
        self.status.close()
        self.status.stop_listener()
        # The handoff port is free for the real foreground server.
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", port))
            listener.listen(1)
        self.status.set_phase("blocked", "WORLD_ENGINE_PROCESS_EXITED")
        self.assertEqual(self.status.error_code, "WORLD_ENGINE_PROCESS_EXITED")
        self.status.start()
        self.assertEqual(json.loads(self.call("GET", "/healthz")[2])["phase"], "blocked")

    def test_invalid_phase_cannot_claim_readiness(self):
        for phase in ("ready", "engine_ready", "complete", "<script>"):
            with self.assertRaises(ValueError):
                self.status.set_phase(phase)
        self.assertEqual(self.status.snapshot(), ("checking", None))

    def test_concurrent_status_reads_are_consistent(self):
        self.status.set_phase("blocked", "GPU_HARDWARE_UNAVAILABLE")
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(lambda _: json.loads(self.call("GET", "/api/health")[2]), range(32)))
        self.assertEqual(len(records), 32)
        self.assertTrue(all(row["engine_ready"] is False for row in records))
        self.assertTrue(all(row["error_code"] == "GPU_HARDWARE_UNAVAILABLE" for row in records))

    def test_gpu_failure_displays_observed_stages_without_admitting_render(self):
        diagnostic = {
            "schema_version": 1, "render_mode": "gpu-required", "gpu_profile": "egl",
            "failed_stage": "D", "reason_code": "WEBGL_CONTEXT_UNAVAILABLE",
            "stages": [{"id": letter, "status": state} for letter, state in
                       (("A", "PASS"), ("B", "PASS"), ("C", "PASS"),
                        ("D", "FAIL"), ("E", "NOT_RUN"), ("F", "NOT_RUN"))],
            "nvidia_devices": [{"name": "NVIDIA GeForce RTX 3070", "driver_version": "616.56",
                                "memory_total_mib": 8192, "uuid": "GPU-private-uuid"}],
            "runtime": {"libraries": {"nvidia_egl": False, "nvidia_vulkan": False},
                        "driver_delivery": {"egl_vendor_manifest": False,
                                            "vulkan_nvidia_icd": False}},
            "webgl": {"context_available": False, "renderer": None},
            "owner_code": "secret-never-echoed", "raw_stderr": "/private/owner-code.txt",
            "profile_attempts": [{"backend": "egl", "status": "failed"},
                                 {"backend": "vulkan", "status": "failed"}],
        }
        self.status.set_phase("blocked", "GPU_WEBGL_UNVERIFIED", gpu_diagnostics=diagnostic)
        status, _, body = self.call("GET", "/")
        self.assertEqual(status, 200)
        text = body.decode()
        self.assertIn("RTX 3070", text)
        self.assertIn("실패 단계: D", text)
        self.assertIn("그래픽 드라이버 전달", text)
        self.assertIn("gcube에서 Workload를 중지", text)
        self.assertIn("영상 생성 엔진: 아직 준비되지 않음", text)
        self.assertNotIn("WebGL VERIFIED", text)
        for secret in ("GPU-private-uuid", "secret-never-echoed", "/private/owner-code.txt"):
            self.assertNotIn(secret, text)
        health = json.loads(self.call("GET", "/api/health")[2])
        self.assertFalse(health["engine_ready"])
        self.assertEqual(health["gpu_diagnostics"]["failed_stage"], "D")
        self.assertNotIn("uuid", json.dumps(health))
        self.assertEqual(self.call("GET", "/readyz")[0], 503)
        self.assertEqual(self.call("POST", "/api/projects", "{}")[0], 405)
        self.assertEqual(self.call("POST", "/auth/login", "{}")[0], 405)

    def test_gpu_diagnostic_snapshot_is_private_and_not_reused_for_other_errors(self):
        self.status.set_phase("blocked", "GPU_WEBGL_UNVERIFIED", gpu_diagnostics={
            "schema_version": 1, "gpu_profile": "egl", "failed_stage": "E",
            "webgl": {"renderer": "ANGLE (Google, Vulkan SwiftShader Device)",
                      "software_renderer": True, "context_available": True},
        })
        diagnostic = self.status.gpu_diagnostics
        diagnostic["webgl"]["renderer"] = "secret"
        self.assertNotIn(b"secret", self.call("GET", "/")[2])
        self.assertIn(b"SwiftShader", self.call("GET", "/")[2])
        self.status.set_phase("blocked", "STORAGE_MOUNT_REQUIRED", gpu_diagnostics=diagnostic)
        self.assertIsNone(self.status.gpu_diagnostics)
        self.assertNotIn("gpu_diagnostics", json.loads(self.call("GET", "/api/health")[2]))
        self.status.set_phase("checking")
        self.assertIsNone(self.status.gpu_diagnostics)

    def test_t4_missing_graphics_is_readable_through_full_istio_envelope(self):
        from deployment.gcube.test_proxy import envelope
        diagnostic = {"render_mode": "gpu-required", "gpu_profile": "egl", "failed_stage": "D",
                      "reason_code": "DRIVER_GRAPHICS_MISSING",
                      "nvidia_devices": [{"name": "NVIDIA Tesla T4", "driver_version": "535.104.05"}],
                      "webgl": {"context_available": False},
                      "runtime": {"libraries": {"nvidia_egl": False, "nvidia_vulkan": False}},
                      "stages": [{"id": key, "status": "PASS" if key in "ABC" else "FAIL" if key == "D" else "NOT_RUN"} for key in "ABCDEF"],
                      "profile_attempts": [{"backend": "egl", "status": "failed"}, {"backend": "vulkan", "status": "failed"}]}
        self.status.set_phase("blocked", "GPU_WEBGL_UNVERIFIED", gpu_diagnostics=diagnostic)
        status, _, body = self.call("GET", "/", headers=envelope(Host="localhost:8000"))
        self.assertEqual(status, 200)
        text = body.decode()
        for value in ("Tier1 T4에서도 NVIDIA graphics runtime 전달 실패", "EGL GPU backend", "VULKAN GPU backend",
                      "WebGL2 context", "Normalized Host", "XFF entry count", "GPU_WEBGL_UNVERIFIED"):
            self.assertIn(value, text)
        self.assertNotIn("203.0.113.8", text)
        record = json.loads(self.call("GET", "/api/health", headers=envelope())[2])
        self.assertFalse(record["engine_ready"])
        self.assertEqual(record["proxy"]["status"], "PASS")
        self.assertEqual(record["proxy"]["xff_entry_count"], 3)
        self.assertEqual(self.call("POST", "/api/projects", "{}", envelope())[0], 405)

    def test_software_backend_never_claims_egl_or_vulkan_gpu_pass(self):
        from deployment.gcube.boot_status import gpu_diagnostic_html, safe_gpu_diagnostics
        diagnostic = safe_gpu_diagnostics({"render_mode": "cpu", "gpu_profile": "egl", "reason_code": "VERIFIED",
            "webgl": {"renderer": "ANGLE (Google, SwiftShader Device)", "context_available": True,
                      "context_version": 2, "draw_passed": True},
            "profile_attempts": [{"backend": "egl", "status": "verified"}]})
        text = gpu_diagnostic_html(diagnostic)
        self.assertNotIn("EGL GPU backend</th><td>PASS", text)
        self.assertNotIn("VULKAN GPU backend</th><td>PASS", text)


if __name__ == "__main__":
    unittest.main()
