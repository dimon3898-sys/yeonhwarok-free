"""gcube public HTTPS -> Istio/Envoy -> internal HTTP matrix; no rendering."""
from email.message import Message
import json
import unittest
from unittest.mock import patch

from deployment.gcube import test_server as fixture
from deployment.gcube.server import GcubePolicy
from deployment.gcube.proxy import request_envelope, safe_proxy_summary
from deployment.security import SecurityError

ORIGIN = "https://3f2de722.service.gcube.ai:24999"
HOST = ORIGIN.removeprefix("https://")


def envelope(**values):
    result = {"Host": HOST, "Origin": ORIGIN, "X-Forwarded-Proto": "https",
              "X-Forwarded-Host": HOST, "X-Forwarded-Port": "24999",
              "X-Forwarded-For": "203.0.113.8, 10.42.0.2, 127.0.0.6",
              "X-Envoy-External-Address": "203.0.113.8"}
    result.update(values)
    return {key: value for key, value in result.items() if value is not None}


class ProxyContracts(unittest.TestCase):
    def test_abc_single_multiple_xff_and_dynamic_ports(self):
        for port in (443, 24999, 31042, 65535):
            host = "3f2de722.service.gcube.ai" + (":" + str(port) if port != 443 else "")
            origin = "https://" + host
            for xff in ("203.0.113.8", "203.0.113.8, 10.42.0.2", "203.0.113.8, 10.42.0.2, ::1"):
                headers = envelope(Host=host, Origin=origin, **{"X-Forwarded-Host": host,
                    "X-Forwarded-Port": str(port), "X-Forwarded-For": xff})
                for bound in (None, origin):
                    self.assertEqual(GcubePolicy(origin=bound).check_request(headers, method="POST", peer_ip="127.0.0.6"), origin)

    def test_d_same_pod_rewrites_are_normalized_and_pinned(self):
        for host in ("localhost:8000", "127.0.0.1:8000", "[::1]:8000",
                     "3f2de722.service.gcube.ai:8000", "3f2de722.service.gcube.ai"):
            for bound in (None, ORIGIN):
                headers = envelope(Host=host)
                self.assertEqual(GcubePolicy(origin=bound).check_request(headers, method="POST", peer_ip="::1"), ORIGIN)
        headers = envelope(Host="10.42.0.12:8000")
        with patch("deployment.gcube.proxy.pod_addresses", return_value={"10.42.0.12"}):
            self.assertEqual(GcubePolicy().check_request(headers, method="POST", peer_ip="10.42.0.12"), ORIGIN)

    def test_forwarded_rfc7239_quotes_ipv6_and_multiple_header_lines(self):
        headers = Message()
        for key, value in envelope(Host="localhost:8000").items():
            if key != "X-Forwarded-For": headers[key] = value
        headers["X-Forwarded-For"] = "203.0.113.8"
        headers["X-Forwarded-For"] = "10.42.0.2, ::1"
        headers["Forwarded"] = 'for=203.0.113.8;proto=https;host="' + HOST + '"'
        headers["Forwarded"] = 'for="[::1]:43122";by=127.0.0.6;proto=http;host="localhost:8000"'
        policy = GcubePolicy(origin=ORIGIN)
        self.assertEqual(policy.check_request(headers, method="POST", peer_ip="127.0.0.6"), ORIGIN)
        summary = policy.diagnostics(headers, peer_ip="127.0.0.6")
        self.assertEqual(summary["xff_entry_count"], 3)
        self.assertNotIn("203.0.113.8", json.dumps(summary))

    def test_rfc_only_and_forwarded_port_reconstruct_external_authority(self):
        for host in ("localhost:8000", "3f2de722.service.gcube.ai:8000"):
            headers = envelope(Host=host, **{"X-Forwarded-Host": None, "X-Forwarded-Proto": None,
                "Forwarded": 'for=203.0.113.8;proto=https;host="' + HOST + '"'})
            self.assertEqual(GcubePolicy().check_request(headers, method="POST", peer_ip="127.0.0.1"), ORIGIN)
        headers = envelope(Host="3f2de722.service.gcube.ai:8000", **{"X-Forwarded-Host": None})
        self.assertEqual(GcubePolicy(origin=ORIGIN).check_request(headers, method="POST", peer_ip="127.0.0.1"), ORIGIN)

    def test_efgh_forged_external_hosts_origins_ports_and_peer_fail(self):
        changes = [dict(Host="attacker.example"), dict(Host="10.42.0.77:8000"),
                   {"X-Forwarded-Host": "attacker.example"},
                   {"X-Forwarded-Host": "another-workload.service.gcube.ai:24999"},
                   {"X-Forwarded-Host": "3f2de722.service.gcube.ai:31042"},
                   {"X-Forwarded-Port": "31042"}, {"X-Forwarded-Port": "0"},
                   {"X-Forwarded-Port": "65536"}, {"X-Forwarded-Proto": "http"},
                   {"X-Forwarded-Proto": "https,http"}, {"Origin": "https://attacker.example"},
                   {"Origin": None}, {"Origin": "null"},
                   {"Forwarded": 'for=203.0.113.8;host="another-workload.service.gcube.ai:24999";proto=https'},
                   {"Forwarded": 'for=203.0.113.8;proto=http'},
                   {"Forwarded": 'for=203.0.113.8;proto=https,for=10.0.0.1;host="attacker.example"'}]
        for changeset in changes:
            for policy in (GcubePolicy(), GcubePolicy(origin=ORIGIN)):
                with self.subTest(change=changeset, bound=policy.origin):
                    with self.assertRaises(SecurityError):
                        policy.check_request(envelope(**changeset), method="POST", peer_ip="127.0.0.1")
        for peer in (None, "203.0.113.9", "10.42.99.99", "malformed"):
            with self.subTest(peer=peer), self.assertRaises(SecurityError):
                GcubePolicy().check_request(envelope(), method="POST", peer_ip=peer)

    def test_g_malformed_xff_forwarded_envoy_and_duplicate_headers_fail(self):
        for value in ("", ",", "203.0.113.8,", ",203.0.113.8", "203.0.113.8,,10.0.0.1",
                      "client,proxy", "999.0.0.1", "10.0.0.1:99", "unknown", "::1%eth0", "[::1]",
                      "10.0.0.1\r\nSecret: hidden", ",".join(["10.0.0.1"] * 33)):
            with self.subTest(xff=value), self.assertRaises(SecurityError):
                GcubePolicy().check_request(envelope(**{"X-Forwarded-For": value}), peer_ip="127.0.0.1")
        for value in ('for=unknown', 'for="[::1]:0"', 'for="203.0.113.8', 'for=203.0.113.8;;proto=https',
                      'for=203.0.113.8;for=203.0.113.8', 'for=203.0.113.9;proto=https',
                      'for=203.0.113.8;host="' + HOST + '/path"'):
            with self.subTest(forwarded=value), self.assertRaises(SecurityError):
                GcubePolicy().check_request(envelope(Forwarded=value), peer_ip="127.0.0.1")
        for name in ("Host", "Origin", "X-Forwarded-Host", "X-Forwarded-Proto", "X-Forwarded-Port", "X-Envoy-External-Address"):
            headers = Message()
            for key, value in envelope().items(): headers[key] = value
            headers[name] = headers[name]
            with self.subTest(duplicate=name), self.assertRaises(SecurityError):
                GcubePolicy().check_request(headers, peer_ip="127.0.0.1")

    def test_diagnostic_failure_never_reflects_secrets_or_client_addresses(self):
        result = safe_proxy_summary(envelope(Host="PRIVATE_OWNER_SECRET"), peer_ip="127.0.0.1")
        self.assertEqual(result, {"status": "FAIL", "error_code": "INVALID_HOST"})
        result = safe_proxy_summary(envelope(Cookie="private-cookie", Authorization="secret-token"), peer_ip="127.0.0.1")
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn("secret", json.dumps(result)); self.assertNotIn("203.0.113.8", json.dumps(result))


class ProxyHTTP(unittest.TestCase):
    def setUp(self):
        fixture.GatewayTests.setUp(self)
        self.app.policy.port = self.port
    tearDown = fixture.GatewayTests.tearDown
    call = fixture.GatewayTests.call

    def login_with_proxy(self):
        status, headers, body = self.call("POST", "/auth/login", {"password": fixture.PASSWORD}, origin=ORIGIN,
                                         headers=envelope(Host=f"localhost:{self.port}"))
        self.assertEqual(status, 200, body)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertIn("Secure", headers["Set-Cookie"])

    def test_ijk_owner_code_absent_wrong_correct_and_owner_diagnostics(self):
        headers = envelope(Host=f"localhost:{self.port}")
        self.assertEqual(self.call("GET", "/api/gcube/proxy", origin=ORIGIN, headers=headers)[0], 401)
        for password in (None, "wrong"):
            self.assertEqual(self.call("POST", "/auth/login", {"password": password}, origin=ORIGIN, headers=headers)[0], 401)
            self.assertIsNone(self.app.bound_origin)
        self.login_with_proxy()
        self.assertEqual(self.app.bound_origin, ORIGIN)
        status, response_headers, body = self.call("GET", "/api/gcube/proxy", origin=ORIGIN, headers=headers)
        self.assertEqual(status, 200, body)
        record = json.loads(body)
        self.assertEqual(record["xff_entry_count"], 3)
        self.assertTrue(record["envoy_external_address_present"])
        self.assertNotIn("Access-Control-Allow-Origin", response_headers)
        self.assertNotIn(fixture.PASSWORD.encode(), body)
        self.assertEqual(self.call("GET", "/auth/session", origin=ORIGIN, headers=headers)[0], 200)

    def test_mutation_routes_block_spoofs_before_core_dispatch(self):
        self.login_with_proxy()
        paths = ("/auth/login", "/auth/logout", "/api/projects", "/api/assets",
                 "/api/projects/project_abcdef123456/approve", "/api/projects/project_abcdef123456/render",
                 "/api/projects/project_abcdef123456/revise", "/api/projects/project_abcdef123456/resume")
        attacks = ({"Origin": "https://attacker.example"}, {"X-Forwarded-Host": "attacker.example"},
                   {"X-Forwarded-For": "203.0.113.8, invalid"}, {"X-Forwarded-Port": "31042"},
                   {"Forwarded": "for=203.0.113.8;proto=http"})
        for path in paths:
            for changes in attacks:
                with self.subTest(path=path, change=changes):
                    status, _, body = self.call("POST", path, {}, origin=ORIGIN, headers=envelope(**changes))
                    self.assertIn(status, (400, 403), body)
        self.assertEqual(self.app.store.list(), [])

    def test_internal_host_health_with_forwarded_headers_uses_full_policy(self):
        headers = envelope(Host=f"localhost:{self.port}", Origin=None)
        status, _, body = self.call("GET", "/api/health", headers=headers)
        self.assertEqual(status, 200, body)
        self.assertIn("public_origin_bound", json.loads(body))
        self.login_with_proxy()
        status, _, body = self.call("GET", "/api/health", headers=headers)
        self.assertEqual(status, 200, body)
        self.assertTrue(json.loads(body)["public_origin_bound"])
        for key, value in (("X-Forwarded-Host", "attacker.example"),
                           ("X-Forwarded-For", "203.0.113.8, invalid"),
                           ("X-Forwarded-Port", "31042")):
            with self.subTest(header=key):
                status, _, _ = self.call("GET", "/api/health", headers={**headers, key: value})
                self.assertIn(status, (400, 403))

    def test_t4_success_message_is_only_emitted_for_existing_admitted_proof(self):
        from deployment.security import private_json
        self.login_with_proxy()
        diagnostic = {"render_mode": "gpu-required", "gpu_profile": "egl", "reason_code": "VERIFIED",
                      "stages": [{"id": key, "status": "PASS"} for key in "ABCDEF"],
                      "nvidia_devices": [{"name": "NVIDIA Tesla T4", "driver_version": "535.104.05"}],
                      "webgl": {"context_available": True, "context_version": 2, "draw_passed": True,
                                "renderer": "ANGLE (NVIDIA, Tesla T4)", "vendor": "NVIDIA Corporation"}}
        private_json(self.runtime / "gcube-runtime.json", {"gpu": {"render_mode": "gpu-required",
            "gpu_rendering_verified": True, "diagnostics": diagnostic}})
        status, _, body = self.call("GET", "/gcube/gpu.json", origin=ORIGIN, headers=envelope())
        self.assertEqual(status, 200)
        record = json.loads(body)
        self.assertEqual(record["message"], "NVIDIA T4 WEBGL VERIFIED · WORLD ENGINE READY")
        diagnostic["webgl"]["renderer"] = "ANGLE (Google, SwiftShader Device)"
        private_json(self.runtime / "gcube-runtime.json", {"gpu": {"render_mode": "gpu-required",
            "gpu_rendering_verified": True, "diagnostics": diagnostic}})
        record = json.loads(self.call("GET", "/gcube/gpu.json", origin=ORIGIN, headers=envelope())[2])
        self.assertFalse(record["gpu_rendering_verified"])
        self.assertNotIn("VERIFIED", record["message"])


if __name__ == "__main__":
    unittest.main()
