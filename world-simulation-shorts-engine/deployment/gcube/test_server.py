"""Real local HTTP tests of gCube proxy headers; no rendering or external calls."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from email.message import Message
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
from deployment.gcube.server import BoundedHTTPServer, GcubeApplication, GcubeHandler, GcubePolicy, provider_origin
from deployment.security import SecurityError, private_json
from engine.storage import EngineError

PASSWORD = "controlled-gcube-owner-password-2026"
ORIGIN = "https://controlled-workload.gcube.ai"
OTHER = "https://another-workload.gcube.ai"
SERVICE_ORIGIN = "https://3f2de722.service.gcube.ai:24999"


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

    def test_official_service_dynamic_ports_are_pending_owner_login_candidates(self):
        for port in (24999, 31042, 65535):
            origin = f"https://3f2de722.service.gcube.ai:{port}"
            with self.subTest(port=port):
                status, headers, page = self.call("GET", "/auth/login", origin=origin)
                self.assertEqual(status, 200, page)
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                self.assertEqual(self.call("GET", "/api/projects", origin=origin)[0], 401)
                self.assertEqual(self.call("POST", "/auth/login", {"password": "wrong"}, origin=origin)[0], 401)
                self.assertEqual(self.call("POST", "/api/projects", {}, origin=origin)[0], 403)
                self.assertIsNone(self.app.bound_origin)
                self.assertFalse(self.app.binding_path.exists())

    def test_official_service_owner_login_persists_exact_dynamic_origin(self):
        headers = self.login(origin=SERVICE_ORIGIN)
        self.assertIn("Secure", headers["Set-Cookie"])
        self.assertEqual(self.app.bound_origin, SERVICE_ORIGIN)
        self.assertEqual(json.loads(self.app.binding_path.read_text())["origin"], SERVICE_ORIGIN)
        self.assertEqual(self.call("GET", "/auth/session", origin=SERVICE_ORIGIN)[0], 200)
        self.assertEqual(json.loads(self.call("GET", "/api/projects", origin=SERVICE_ORIGIN)[2]), {"projects": []})
        self.assertEqual(self.call("GET", "/", origin=SERVICE_ORIGIN)[0], 200)
        self.assertEqual(self.call("GET", "/static/app.js", origin=SERVICE_ORIGIN)[0], 200)
        restarted = GcubeApplication(self.runtime, "http://127.0.0.1:8001", self.access, disk_floor=0)
        try:
            self.assertEqual(restarted.bound_origin, SERVICE_ORIGIN)
            self.assertTrue(restarted.sessions.claims(self.cookie.split("=", 1)[1]))
            good = {"Host": "3f2de722.service.gcube.ai:24999", "Origin": SERVICE_ORIGIN,
                    "X-Forwarded-Host": "3f2de722.service.gcube.ai:24999", "X-Forwarded-Proto": "https"}
            self.assertEqual(restarted.policy.check_request(good, method="POST"), SERVICE_ORIGIN)
        finally:
            restarted.scheduler.close()

    def test_official_service_origin_and_port_checks_block_every_mutation_before_core(self):
        self.login(origin=SERVICE_ORIGIN)
        mutations = ("/auth/logout", "/api/projects", "/api/assets",
                     "/api/projects/project_abcdef123456/approve", "/api/projects/project_abcdef123456/render",
                     "/api/projects/project_abcdef123456/revise", "/api/projects/project_abcdef123456/clip",
                     "/api/projects/project_abcdef123456/revisions/revision_001/approve",
                     "/api/gcube/gpu")
        envelopes = (
            {"Origin": "https://untrusted.example"},
            {"Origin": "https://3f2de722.service.gcube.ai:31042"},
            {"Origin": None}, {"Origin": "null"},
            {"X-Forwarded-Host": "3f2de722.service.gcube.ai:31042"},
            {"Host": "3f2de722.service.gcube.ai:31042", "X-Forwarded-Host": "3f2de722.service.gcube.ai:31042",
             "Origin": "https://3f2de722.service.gcube.ai:31042"},
            {"Host": "another-workload.service.gcube.ai:24999", "X-Forwarded-Host": "another-workload.service.gcube.ai:24999",
             "Origin": "https://another-workload.service.gcube.ai:24999"},
            {"X-Forwarded-Proto": "http"},
        )
        binding = self.app.binding_path.read_bytes()
        with patch("deployment.gcube.server.MobileHandler.dispatch") as core:
            for path in mutations:
                for envelope in envelopes:
                    with self.subTest(path=path, envelope=envelope):
                        status, _, body = self.call("POST", path, {}, origin=SERVICE_ORIGIN, headers=envelope)
                        self.assertIn(status, {400, 403}, body)
                        self.assertIn(json.loads(body)["error"]["code"],
                                      {"INVALID_HOST", "INVALID_ORIGIN", "INVALID_FORWARDED_HEADERS"})
            core.assert_not_called()
        self.assertEqual(self.app.binding_path.read_bytes(), binding)
        self.assertEqual(self.app.bound_origin, SERVICE_ORIGIN)
        self.assertEqual(self.call("GET", "/auth/session", origin=SERVICE_ORIGIN)[0], 200)
        self.assertEqual(json.loads(self.call("GET", "/api/projects", origin=SERVICE_ORIGIN)[2]), {"projects": []})

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

    def test_gpu_diagnostic_routes_keep_existing_owner_and_origin_checks(self):
        routes = ("/api/gcube/gpu", "/gcube/gpu", "/gcube/gpu.json")
        for path in routes:
            self.assertEqual(self.call("GET", path)[0], 401)
        self.login()
        private_json(self.runtime / "gcube-runtime.json", {
            "gpu": {"render_mode": "cpu", "gpu_rendering_verified": False,
                    "diagnostics": {"schema_version": 1, "render_mode": "cpu",
                                    "gpu_profile": "cpu", "webgl": {
                                        "renderer": "ANGLE (Google, Vulkan SwiftShader Device)",
                                        "software_renderer": True, "context_available": True,
                                        "context_version": 2, "webgl2": True, "draw_passed": True},
                                    "owner_code": PASSWORD, "stderr": "private-engine-stderr"}},
            "owner": PASSWORD, "path": str(self.runtime)})
        for path in routes:
            status, headers, body = self.call("GET", path)
            self.assertEqual(status, 200, body)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertNotIn(PASSWORD.encode(), body)
            self.assertNotIn(str(self.runtime).encode(), body)
            self.assertNotIn(b"private-engine-stderr", body)
            self.assertNotIn(b"WebGL VERIFIED", body)
            self.assertEqual(self.call("POST", path, {})[0], 405)
            self.assertIn(self.call("GET", path, origin=OTHER)[0], {400, 403})
            self.assertEqual(self.call("HEAD", path)[0], 200)
            self.assertEqual(self.call("HEAD", path)[2], b"")
        record = json.loads(self.call("GET", "/api/gcube/gpu")[2])
        self.assertEqual(record["render_mode"], "cpu")
        self.assertFalse(record["gpu_rendering_verified"])
        self.assertIn("CPU 비교 모드", record["message"])
        self.assertIn("SwiftShader", record["diagnostics"]["webgl"]["renderer"])
        self.cookie = None
        for path in routes:
            self.assertEqual(self.call("GET", path)[0], 401)

    def test_gpu_diagnostic_verified_message_requires_observed_gpu_draw_proof(self):
        self.login()
        stages = [{"id": letter, "status": "PASS"} for letter in "ABCDEF"]
        diagnostic = {"schema_version": 1, "render_mode": "gpu-required", "gpu_profile": "egl",
                      "failed_stage": None, "stages": stages,
                      "nvidia_devices": [{"name": "NVIDIA GeForce RTX 3070", "driver_version": "616.56",
                                          "memory_total_mib": 8192, "uuid": "private-gpu-uuid"}],
                      "webgl": {"vendor": "WebKit", "renderer": "WebKit WebGL",
                                "unmasked_vendor": "NVIDIA Corporation", "unmasked_renderer": "NVIDIA GeForce RTX 3070",
                                "context_available": True, "context_version": 2,
                                "webgl2": True, "draw_passed": True, "software_renderer": False}}
        report = {"gpu": {"render_mode": "gpu-required", "gpu_rendering_verified": True,
                          "diagnostics": diagnostic}}
        private_json(self.runtime / "gcube-runtime.json", report)
        value = json.loads(self.call("GET", "/gcube/gpu.json")[2])
        self.assertTrue(value["gpu_rendering_verified"])
        self.assertIn("RTX 3070 WebGL VERIFIED", value["message"])
        self.assertIn("World Engine READY", value["message"])
        self.assertNotIn(b"private-gpu-uuid", self.call("GET", "/gcube/gpu")[2])
        self.assertIn(b"GPU / WebGL", self.call("GET", "/")[2])
        for modified in ("software", "missing_frame", "missing_stage", "cpu"):
            with self.subTest(modified=modified):
                changed = json.loads(json.dumps(report))
                if modified == "software":
                    changed["gpu"]["diagnostics"]["webgl"]["unmasked_renderer"] = "ANGLE (Google, Vulkan SwiftShader Device)"
                elif modified == "missing_frame":
                    changed["gpu"]["diagnostics"]["webgl"]["draw_passed"] = False
                elif modified == "missing_stage":
                    changed["gpu"]["diagnostics"]["stages"][-1]["status"] = "NOT_RUN"
                else:
                    changed["gpu"]["render_mode"] = "cpu"
                private_json(self.runtime / "gcube-runtime.json", changed)
                value = json.loads(self.call("GET", "/api/gcube/gpu")[2])
                self.assertFalse(value["gpu_rendering_verified"])
                self.assertNotIn("WebGL VERIFIED", value["message"])

    def test_gpu_diagnostic_runtime_corruption_never_leaks_or_claims_gpu_success(self):
        self.login()
        path = self.runtime / "gcube-runtime.json"
        for text in ("not-json-private-secret", 'null', '[]', '{"gpu":[]}'):
            path.write_text(text)
            path.chmod(0o600)
            value = json.loads(self.call("GET", "/api/gcube/gpu")[2])
            self.assertFalse(value["gpu_rendering_verified"])
            self.assertEqual(value["diagnostics"], {})
            self.assertNotIn("secret", json.dumps(value))
        path.unlink()
        path.symlink_to(self.access)
        value = json.loads(self.call("GET", "/api/gcube/gpu")[2])
        self.assertFalse(value["gpu_rendering_verified"])
        self.assertNotIn(PASSWORD, json.dumps(value))

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

    def test_kubelet_and_istio_health_never_bind_an_origin(self):
        for host in ("10.42.0.12:8000", "[fd00::5324]:8000", "localhost:8000"):
            for path in ("/api/health", "/healthz", "/readyz"):
                headers = {"Host": host, "X-Forwarded-Host": "internal-service:8000",
                           "X-Forwarded-Proto": "http", "User-Agent": "kube-probe/1.30"}
                with self.subTest(host=host, path=path):
                    status, _, body = self.call("GET", path, headers=headers)
                    self.assertEqual(status, 200)
                    self.assertEqual(json.loads(body), {"ok": True, "engine_ready": True,
                                     "phase": "ready", "authentication_required": True})
        self.assertIsNone(self.app.bound_origin)
        self.assertFalse(self.app.binding_path.exists())

    def test_probe_headers_cannot_reach_authentication_or_mutations(self):
        headers = {"Host": "10.42.0.12:8000", "X-Forwarded-Host": "internal-service:8000",
                   "X-Forwarded-Proto": "http", "Origin": None}
        for method, path in (("GET", "/auth/login"), ("GET", "/api/projects"),
                             ("POST", "/auth/login"), ("POST", "/api/projects"),
                             ("POST", "/api/health"), ("POST", "/healthz")):
            with self.subTest(method=method, path=path):
                status, _, _ = self.call(method, path, {} if method == "POST" else None, headers=headers)
                self.assertIn(status, {400, 403})
        self.assertIsNone(self.app.bound_origin)

    def test_liveness_does_not_accept_an_explicit_foreign_origin(self):
        for path in ("/api/health", "/healthz", "/readyz"):
            status, _, _ = self.call("GET", path,
                                    headers={"Host": "10.42.0.12:8000", "Origin": "https://evil.example"})
            self.assertIn(status, {400, 403})

    def test_readiness_head_does_not_open_project_data(self):
        status, headers, body = self.call("HEAD", "/readyz", headers={"Host": "10.42.0.12:8000"})
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)
        self.assertNotIn("Access-Control-Allow-Origin", headers)


SERVICE_HOST = "3f2de722.service.gcube.ai"


def envelope(host, *, origin=None):
    return {"Host": host, "Origin": origin if origin is not None else "https://" + host,
            "X-Forwarded-Host": host, "X-Forwarded-Proto": "https"}


class ProviderAuthorityTests(unittest.TestCase):
    def test_official_service_dynamic_ports_and_historical_host_shape(self):
        for host in (SERVICE_HOST, "controlled-workload.gcube.ai"):
            for suffix in ("", ":24999", ":31042", ":65535"):
                authority = host + suffix
                with self.subTest(authority=authority):
                    expected = "https://" + authority
                    self.assertEqual(provider_origin(authority), expected)
                    self.assertEqual(GcubePolicy().check_request(envelope(authority), method="POST"), expected)

    def test_https_default_port_is_canonicalized_without_changing_origin_policy(self):
        origin = "https://" + SERVICE_HOST
        headers = envelope(SERVICE_HOST + ":443", origin=origin)
        self.assertEqual(provider_origin(SERVICE_HOST + ":443"), origin)
        self.assertEqual(GcubePolicy().check_request(headers, method="POST"), origin)
        self.assertEqual(GcubePolicy(origin=origin).check_request(headers, method="POST"), origin)
        for policy in (GcubePolicy(), GcubePolicy(origin=origin)):
            with self.assertRaises(SecurityError):
                policy.check_request(dict(headers, Origin=origin + ":443"), method="POST")

    def test_reserved_apex_suffix_spoof_and_deep_domains_fail_closed(self):
        invalid = ("gcube.ai", "service.gcube.ai", "api.gcube.ai", "console.gcube.ai", "www.gcube.ai",
                   "api.service.gcube.ai", "console.service.gcube.ai", "service.service.gcube.ai",
                   "gcube.ai.evil.example", SERVICE_HOST + ".evil.example", "world.sub.gcube.ai",
                   "world.sub.service.gcube.ai", "3f2de722.service.gcube.ai.", "gpu.other.example")
        for host in invalid:
            for suffix in ("", ":24999"):
                with self.subTest(authority=host + suffix):
                    with self.assertRaises(SecurityError) as caught:
                        provider_origin(host + suffix)
                    self.assertEqual(caught.exception.code, "INVALID_HOST")

    def test_malformed_authorities_are_security_errors_not_parser_exceptions(self):
        invalid = (None, 24999, "", SERVICE_HOST + ":0", SERVICE_HOST + ":65536", SERVICE_HOST + ":-1",
                   SERVICE_HOST + ":not-a-port", SERVICE_HOST + ":", SERVICE_HOST + ":24999:1",
                   "https://" + SERVICE_HOST + ":24999", SERVICE_HOST + ":24999/path",
                   SERVICE_HOST + ":24999?query", SERVICE_HOST + ":24999#fragment",
                   "owner@" + SERVICE_HOST + ":24999", SERVICE_HOST + ":24999,attacker.example",
                   SERVICE_HOST + " :24999", SERVICE_HOST + ":24999\r\n", SERVICE_HOST + "/evil",
                   SERVICE_HOST + "\\evil", "[::1]:24999", "127.0.0.1:24999", "-world.service.gcube.ai:24999")
        for authority in invalid:
            with self.subTest(authority=authority):
                with self.assertRaises(SecurityError) as caught:
                    provider_origin(authority)
                self.assertEqual(caught.exception.code, "INVALID_HOST")

    def test_pending_dynamic_authority_retains_https_origin_and_forwarding_checks(self):
        headers = envelope(SERVICE_HOST + ":24999")
        overrides = ({"Origin": None}, {"Origin": "null"}, {"Origin": "https://untrusted.example"},
                     {"Origin": "https://" + SERVICE_HOST}, {"Origin": "https://" + SERVICE_HOST + ":31042"},
                     {"Origin": headers["Origin"] + "/"}, {"X-Forwarded-Proto": "http"},
                     {"X-Forwarded-Proto": "https,http"}, {"X-Forwarded-Host": SERVICE_HOST + ":31042"},
                     {"X-Forwarded-Host": SERVICE_HOST + ":24999,attacker.example"})
        for override in overrides:
            with self.subTest(override=override):
                with self.assertRaises(SecurityError):
                    GcubePolicy().check_request(dict(headers, **override), method="POST")
        read_only = {name: value for name, value in headers.items() if name != "Origin"}
        self.assertEqual(GcubePolicy().check_request(read_only, method="GET"), headers["Origin"])

    def test_bound_dynamic_authority_admits_only_exact_hostname_and_port(self):
        host = SERVICE_HOST + ":24999"
        policy = GcubePolicy(origin="https://" + host)
        self.assertEqual(policy.check_request(envelope(host), method="POST"), "https://" + host)
        for foreign in (SERVICE_HOST, SERVICE_HOST + ":8000", SERVICE_HOST + ":31042",
                        "another-workload.service.gcube.ai:24999", "3f2de722.gcube.ai:24999"):
            with self.subTest(foreign=foreign):
                with self.assertRaises(SecurityError):
                    policy.check_request(envelope(foreign), method="POST")

    def test_duplicate_address_headers_fail_in_pending_and_bound_policy(self):
        host = SERVICE_HOST + ":24999"
        for policy in (GcubePolicy(), GcubePolicy(origin="https://" + host)):
            for name in ("Host", "Origin", "X-Forwarded-Host", "X-Forwarded-Proto"):
                headers = Message()
                for key, value in envelope(host).items():
                    headers[key] = value
                headers[name] = headers[name]
                with self.subTest(bound=bool(policy.origin), header=name):
                    with self.assertRaises(SecurityError):
                        policy.check_request(headers, method="POST")

    def test_explicit_local_development_origin_keeps_existing_behavior(self):
        for host in ("localhost:7860", "127.0.0.1:7860"):
            origin = "http://" + host
            policy = GcubePolicy(origin=origin, port=7860, local_mode=True)
            self.assertEqual(policy.check_request({"Host": host, "Origin": origin}, method="POST"), origin)
            for foreign in ("http://localhost:7861", "https://untrusted.example", None):
                with self.subTest(host=host, foreign=foreign):
                    with self.assertRaises(SecurityError):
                        policy.check_request({"Host": host, "Origin": foreign}, method="POST")


if __name__ == "__main__":
    from engine.storage import EngineError
    unittest.main()
