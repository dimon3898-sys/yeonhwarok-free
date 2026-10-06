"""Real local HTTP tests of gCube proxy headers; no rendering or external calls."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import stat
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[2]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
from deployment.gcube.server import BoundedHTTPServer, GcubeApplication, GcubeHandler, GcubePolicy
from deployment.security import SecurityError, private_json
from engine.storage import EngineError

PASSWORD = "controlled-gcube-owner-password-2026"
ORIGIN = "https://controlled-workload.gcube.ai"
OTHER = "https://another-workload.gcube.ai"


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.access = self.root / "owner.txt"
        self.access.write_text(PASSWORD)
        self.access.chmod(0o600)
        self.runtime = self.root / "runtime"
        self.env = patch.dict("os.environ", {}, clear=True)
        self.env.start()
        self.app = GcubeApplication(self.runtime, "http://127.0.0.1:8001", self.access, disk_floor=0)
        self.server = BoundedHTTPServer(("127.0.0.1", 0), GcubeHandler, self.app)
        self.port = self.server.server_port
        self.app.public_port = self.port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = None

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.app.scheduler.close()
        self.env.stop()
        self.temp.cleanup()

    def call(self, method, path, body=None, *, origin=ORIGIN, headers=None, cookie=None):
        values = {"Host": origin.removeprefix("https://"), "X-Forwarded-Host": origin.removeprefix("https://"), "X-Forwarded-Proto": "https"}
        if method == "POST":
            values["Origin"] = origin
        if self.cookie or cookie:
            values["Cookie"] = cookie or self.cookie
        if headers:
            values.update(headers)
        values = {name: value for name, value in values.items() if value is not None}
        if isinstance(body, dict):
            body = json.dumps(body)
            values["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request(method, path, body=body, headers=values)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def login(self, *, origin=ORIGIN):
        status, headers, body = self.call("POST", "/auth/login", {"password": PASSWORD}, origin=origin)
        self.assertEqual(status, 200, body)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertIn("Secure", headers["Set-Cookie"])
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        return headers

    def test_pending_get_and_wrong_password_never_bind_origin(self):
        self.assertEqual(self.call("GET", "/")[0], 303)
        status, _, page = self.call("GET", "/auth/login")
        self.assertEqual(status, 200)
        self.assertIn("World Engine".encode(), page)
        self.assertNotIn("비공개 접근 파일".encode(), page)
        self.assertEqual(self.call("GET", "/api/health")[0], 200)
        self.assertEqual(self.call("GET", "/api/projects")[0], 401)
        self.assertEqual(self.call("POST", "/api/projects", {})[0], 403)
        self.assertEqual(self.call("POST", "/auth/logout", {})[0], 403)
        self.assertEqual(self.call("POST", "/auth/login", {"password": "wrong"})[0], 401)
        self.assertIsNone(self.app.bound_origin)
        self.assertFalse(self.app.binding_path.exists())

    def test_incomplete_login_body_does_not_commit_origin(self):
        body = json.dumps({"password": PASSWORD}).encode()
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.putrequest("POST", "/auth/login", skip_host=True)
        host = ORIGIN.removeprefix("https://")
        for key, value in {"Host": host, "Origin": ORIGIN, "X-Forwarded-Host": host,
                           "X-Forwarded-Proto": "https", "Content-Type": "application/json",
                           "Content-Length": str(len(body) + 20)}.items():
            connection.putheader(key, value)
        connection.endheaders(body)
        connection.sock.shutdown(socket.SHUT_WR)
        response = connection.getresponse()
        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(response.read())["error"]["code"], "INCOMPLETE_BODY")
        connection.close()
        self.assertIsNone(self.app.bound_origin)
        self.assertFalse(self.app.binding_path.exists())

    def test_owner_login_persists_exact_origin_and_existing_ui_api(self):
        self.login()
        self.assertEqual(self.app.bound_origin, ORIGIN)
        self.assertEqual(stat.S_IMODE(self.app.binding_path.stat().st_mode), 0o600)
        binding = json.loads(self.app.binding_path.read_text())
        self.assertEqual(binding["origin"], ORIGIN)
        self.assertNotIn(PASSWORD, self.app.binding_path.read_text())
        self.assertEqual(self.call("GET", "/auth/session")[0], 200)
        self.assertEqual(json.loads(self.call("GET", "/api/projects")[2]), {"projects": []})
        status, headers, page = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"/static/app.js", page)
        self.assertIn("gCube Workload".encode(), page)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(self.call("GET", "/static/app.js")[0], 200)

    def test_measurement_download_is_owner_only_and_read_only(self):
        self.assertEqual(self.call("GET", "/api/gcube/benchmark")[0], 401)
        self.login()
        private_json(self.runtime / "gcube-runtime.json", {"gpu": {"render_mode": "cpu"}, "owner": PASSWORD})
        status, _, record = self.call("GET", "/api/gcube/benchmark")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(record)["runtime"]["render_mode"], "cpu")
        self.assertNotIn(PASSWORD.encode(), record)
        status, headers, body = self.call("GET", "/gcube/benchmark.json")
        self.assertEqual(status, 200)
        self.assertIn('attachment; filename="world-engine-gcube-measurements.json"', headers["Content-Disposition"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        status, headers, body = self.call("HEAD", "/gcube/benchmark.json")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)
        self.assertEqual(self.call("POST", "/api/gcube/benchmark", {})[0], 405)
        self.assertIn(self.call("GET", "/gcube/benchmark.json", origin=OTHER)[0], {400, 403})
        saved_cookie, self.cookie = self.cookie, None
        self.assertEqual(self.call("GET", "/api/gcube/benchmark")[0], 401)
        self.assertEqual(self.call("GET", "/gcube/benchmark.json")[0], 401)
        self.cookie = saved_cookie
        (self.runtime / "gcube-runtime.json").write_text("broken")
        status, _, body = self.call("GET", "/api/gcube/benchmark")
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error"]["code"], "DIAGNOSTIC_RUNTIME_INVALID")
        self.assertNotIn(str(self.runtime).encode(), body)

    def test_invalid_hosts_origins_and_forwarding_do_not_bind(self):
        cases = [
            {"Host": "attacker.example"}, {"Host": "x.gcube.ai.evil.example"},
            {"Host": "console.gcube.ai", "X-Forwarded-Host": "console.gcube.ai"},
            {"Host": "gcube.ai"}, {"Host": "world.sub.gcube.ai"},
            {"Host": "controlled-workload.gcube.ai:443"},
            {"Host": f"127.0.0.1:{self.port}"},
            {"X-Forwarded-Host": "another-workload.gcube.ai"},
            {"X-Forwarded-Host": "controlled-workload.gcube.ai, attacker.example"},
            {"X-Forwarded-Proto": "https,http"}, {"X-Forwarded-Proto": "http"},
            {"Origin": None}, {"Origin": "null"}, {"Origin": OTHER}, {"Origin": ORIGIN + "/"},
        ]
        for headers in cases:
            with self.subTest(headers=headers):
                status, _, _ = self.call("POST", "/auth/login", {"password": PASSWORD}, headers=headers)
                self.assertIn(status, {400, 403})
        self.assertIsNone(self.app.bound_origin)
        self.assertFalse(self.app.binding_path.exists())

    def test_bound_origin_rejects_other_origin_and_survives_restart(self):
        self.login()
        old_cookie = self.cookie
        self.assertIn(self.call("GET", "/api/projects", origin=OTHER, cookie=old_cookie)[0], {400, 403})
        self.assertIn(self.call("POST", "/auth/login", {"password": PASSWORD}, origin=OTHER)[0], {400, 403})
        restarted = GcubeApplication(self.runtime, "http://127.0.0.1:8001", self.access, disk_floor=0)
        self.assertEqual(restarted.bound_origin, ORIGIN)
        self.assertTrue(restarted.sessions.claims(old_cookie.split("=", 1)[1]))
        self.assertEqual(restarted.maximum_duration, 20)
        self.assertEqual(restarted.maximum_job_seconds, 3600)

    def test_explicit_origin_change_revokes_old_sessions(self):
        self.login()
        token = self.cookie.split("=", 1)[1]
        configured = GcubeApplication(self.runtime, "http://127.0.0.1:8001", self.access,
                                      public_origin=OTHER, disk_floor=0)
        self.assertEqual(configured.bound_origin, OTHER)
        self.assertIsNone(configured.sessions.claims(token))
        self.assertEqual(json.loads(configured.binding_path.read_text())["origin"], OTHER)

    def test_concurrent_candidate_logins_only_one_origin_can_win(self):
        def candidate(origin):
            return self.call("POST", "/auth/login", {"password": PASSWORD}, origin=origin)
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(candidate, (ORIGIN, OTHER)))
        self.assertEqual(sum(value[0] == 200 for value in responses), 1)
        self.assertEqual(sum(value[0] in {400, 403} for value in responses), 1)
        self.assertIn(self.app.bound_origin, {ORIGIN, OTHER})
        self.assertEqual(json.loads(self.app.binding_path.read_text())["origin"], self.app.bound_origin)

    def test_binding_corruption_permission_and_symlink_fail_closed(self):
        for text, mode in [("not json", 0o600), ("[]", 0o600), ("null", 0o600), ('{"schema_version":1,"origin":"https://controlled-workload.gcube.ai"}', 0o644)]:
            self.app.binding_path.write_text(text)
            self.app.binding_path.chmod(mode)
            with self.assertRaises(SecurityError):
                GcubeApplication(self.runtime, "http://127.0.0.1:8001", self.access, disk_floor=0)
        self.app.binding_path.unlink()
        self.app.binding_path.symlink_to(self.access)
        with self.assertRaises(SecurityError):
            GcubeApplication(self.runtime, "http://127.0.0.1:8001", self.access, disk_floor=0)

    def test_pending_does_not_accept_restored_session_until_password_binding(self):
        token = self.app.sessions.login(PASSWORD)
        cookie = "world_owner_session=" + token
        self.assertEqual(self.call("GET", "/api/projects", cookie=cookie)[0], 401)
        self.login()
        self.assertIsNone(self.app.sessions.claims(token))

    def test_download_and_range_reuse_existing_owned_output_checks(self):
        self.login()
        pid, version = "project_abcdef123456", "v001"
        folder = self.app.store.root / pid / "versions" / version
        folder.mkdir(parents=True)
        asset = folder / "scene_plan_readable.md"
        asset.write_bytes(b"0123456789")
        path = f"/download/{pid}/{version}/{asset.name}"
        status, headers, body = self.call("GET", path, headers={"Range": "bytes=2-5"})
        self.assertEqual(status, 206, body)
        self.assertEqual(body, b"2345")
        self.assertEqual(headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(self.call("HEAD", path)[0], 200)
        self.assertEqual(self.call("HEAD", path)[2], b"")
        private = folder / "private.txt"
        private.write_text("not public")
        self.assertEqual(self.call("GET", f"/download/{pid}/{version}/private.txt")[0], 404)

    def test_real_health_reports_only_observed_gpu_and_storage_fields(self):
        private_json(self.runtime / "gcube-runtime.json", {
            "gpu": {"render_mode": "gpu-required", "gpu_profile": "egl-nvidia", "gpu_rendering_verified": True,
                    "speedup_measured": False, "cache_namespace": "private-cache-path"},
            "storage": {"persistent_mount_detected": True, "mode": "required", "filesystem_probe_passed": True,
                        "path": "/private-owner-path"}})
        status, _, body = self.call("GET", "/api/health")
        self.assertEqual(status, 200)
        value = json.loads(body)
        self.assertEqual(value["render_backend"], "GPU_VERIFIED")
        self.assertTrue(value["storage"]["persistent_mount_detected"])
        self.assertFalse(value["gpu"]["speedup_measured"])
        self.assertNotIn(b"private-owner-path", body)
        self.assertNotIn(b"private-cache-path", body)
        self.assertEqual(value["limits"]["max_duration"], 20)
        self.assertIsNone(self.app.bound_origin)

    def test_loopback_health_exception_does_not_open_other_paths(self):
        local = {"Host": f"127.0.0.1:{self.port}", "X-Forwarded-Host": None, "X-Forwarded-Proto": None}
        self.assertEqual(self.call("GET", "/api/health", headers=local)[0], 200)
        self.assertEqual(self.call("GET", "/api/projects", headers=local)[0], 400)
        self.assertEqual(self.call("GET", "/auth/login", headers=local)[0], 400)
        self.assertEqual(self.call("POST", "/auth/login", {"password": PASSWORD}, headers=local)[0], 400)
        self.assertIsNone(self.app.bound_origin)

    def test_maximum_duration_guard_without_rendering(self):
        self.assertEqual(self.app.validate_request({"topic": "test", "duration": 20})["duration"], 20)
        with self.assertRaises(EngineError):
            self.app.validate_request({"topic": "test", "duration": 75})


if __name__ == "__main__":
    from engine.storage import EngineError
    unittest.main()
