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


if __name__ == "__main__":
    unittest.main()
