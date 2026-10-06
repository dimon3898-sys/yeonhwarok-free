"""Trusted Codespaces origin and real HTTP dispatch regressions, without rendering.

All credentials, sessions, projects and jobs below are isolated test fixtures.
The HTTP listener is ephemeral loopback; planner/revision/store/worker calls are
mocked. No production server, actual access file or completed video is touched.
"""
from email.message import Message
import http.client
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from deployment.security import RequestPolicy, SecurityError, codespaces_origin
from deployment.mobile_server import BoundedHTTPServer, MobileHandler


NAME = "fictional-cod-ab1234"
ENV = {"CODESPACE_NAME": NAME,
       "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev"}
PID = "project_origin_fixture"
RID = "revision_origin_fixture"
JID = "job_origin_fixture"
FIXTURE_CODE = "synthetic-origin-fixture-owner-code"
FIXTURE_TOKEN = "synthetic-origin-fixture-session"


def headers(*pairs):
    result = Message()
    for key, value in pairs:
        if value is not None:
            result[key] = value
    return result


class CodespacesOriginTests(unittest.TestCase):
    def test_absent_codespace_does_not_invent_public_origin(self):
        self.assertIsNone(codespaces_origin(7860, environ={}))
        self.assertIsNone(codespaces_origin(7860, environ={
            "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev"}))

    def test_trusted_name_and_absent_domain_have_exact_canonical_origin(self):
        expected = f"https://{NAME}-7860.app.github.dev"
        self.assertEqual(codespaces_origin(7860, environ=ENV), expected)
        self.assertEqual(codespaces_origin(7860, environ={"CODESPACE_NAME": NAME}), expected)
        self.assertEqual(codespaces_origin(7860, environ={**ENV,
                         "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": ""}), expected)
        self.assertEqual(codespaces_origin(7861, environ=ENV),
                         f"https://{NAME}-7861.app.github.dev")

    def test_invalid_environment_name_fails_closed(self):
        for value in ("../owned", "https://evil.invalid", "has space", "x.app.github.dev",
                      "-bad", "bad-", "name,evil"):
            with self.subTest(name=value), self.assertRaises(SecurityError):
                codespaces_origin(7860, environ={**ENV, "CODESPACE_NAME": value})

    def test_untrusted_forwarding_domain_and_invalid_port_fail_closed(self):
        for value in ("example.invalid", "app.github.dev.evil", "https://app.github.dev",
                      "app.github.dev:443", "app.github.dev,evil"):
            with self.subTest(domain=value), self.assertRaises(SecurityError):
                codespaces_origin(7860, environ={**ENV, "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": value})
        for port in (0, -1, 65536):
            with self.subTest(port=port), self.assertRaises(SecurityError):
                codespaces_origin(port, environ=ENV)

    def test_request_policy_automatically_uses_trusted_environment(self):
        origin = codespaces_origin(7860, environ=ENV)
        policy = RequestPolicy(local_port=7860, environ=ENV)
        self.assertIn(origin, policy.origins)
        with patch.dict("os.environ", ENV, clear=True):
            self.assertIn(origin, RequestPolicy(local_port=7860).origins)
        self.assertNotIn(origin, RequestPolicy(local_port=7860, environ={}).origins)

    def test_direct_public_host_and_forwarded_proxy_return_verified_origin(self):
        origin = codespaces_origin(7860, environ=ENV)
        host = origin.split("//", 1)[1]
        policy = RequestPolicy(local_port=7860, environ=ENV)
        for raw_host, peer in (("127.0.0.1:7860", "127.0.0.1"),
                               (host, "198.51.100.7"),
                               ("localhost:7860", "10.4.5.6")):
            with self.subTest(host=raw_host, peer=peer):
                incoming = headers(("Host", raw_host), ("Origin", origin),
                                   ("X-Forwarded-Host", host),
                                   ("X-Forwarded-Proto", "https"))
                self.assertEqual(policy.check_request(incoming, method="POST", peer_ip=peer), origin)
        self.assertEqual(policy.check_request(headers(("Host", host)), method="GET"), origin)
        self.assertEqual(policy.check_request(headers(("Host", host), ("Origin", origin)),
                                               method="POST"), origin)

    def test_configured_https_origin_with_local_host_without_proxy_metadata(self):
        origin = codespaces_origin(7860, environ=ENV)
        policy = RequestPolicy(local_port=7860, environ=ENV)
        self.assertEqual(policy.check_request(headers(("Host", "127.0.0.1:7860"),
                                                       ("Origin", origin)), method="POST"), origin)
        self.assertEqual(policy.check_request(headers(("Host", "127.0.0.1:7860")),
                                               method="GET"), "http://127.0.0.1:7860")

    def test_wrong_codespace_port_suffix_scheme_null_and_absent_origin_rejected(self):
        policy = RequestPolicy(local_port=7860, environ=ENV)
        origin = codespaces_origin(7860, environ=ENV)
        wrong = (f"https://other-cod-ab1234-7860.app.github.dev",
                 f"https://{NAME}-7861.app.github.dev", origin + ".evil",
                 origin.replace("https://", "http://"), "null", None)
        for candidate in wrong:
            with self.subTest(origin=candidate), self.assertRaises(SecurityError) as error:
                policy.check_request(headers(("Host", "127.0.0.1:7860"),
                                              ("Origin", candidate)), method="POST")
            self.assertEqual(error.exception.status, 403)

    def test_forwarded_headers_do_not_learn_an_attacker_allowlist(self):
        policy = RequestPolicy(local_port=7860, environ=ENV)
        original_origins, original_hosts = set(policy.origins), set(policy.hosts)
        incoming = headers(("Host", "127.0.0.1:7860"),
                           ("Origin", "https://attacker.invalid"),
                           ("X-Forwarded-Host", "attacker.invalid"),
                           ("X-Forwarded-Proto", "https"))
        with self.assertRaises(SecurityError):
            policy.check_request(incoming, method="POST", peer_ip="127.0.0.1")
        self.assertEqual(policy.origins, original_origins)
        self.assertEqual(policy.hosts, original_hosts)
        with self.assertRaises(SecurityError):
            policy.check_host("attacker.invalid")

    def test_duplicate_comma_and_malformed_host_origin_forward_headers_rejected(self):
        policy = RequestPolicy(local_port=7860, environ=ENV)
        origin = codespaces_origin(7860, environ=ENV)
        host = origin.split("//", 1)[1]
        baseline = {"Host": "127.0.0.1:7860", "Origin": origin,
                    "X-Forwarded-Host": host, "X-Forwarded-Proto": "https"}
        for field in baseline:
            for bad in ("duplicate", "comma"):
                incoming = headers(*[(k, v) for k, v in baseline.items() if k != field])
                if bad == "duplicate":
                    incoming[field] = baseline[field]
                    incoming[field] = baseline[field]
                else:
                    incoming[field] = baseline[field] + "," + baseline[field]
                with self.subTest(field=field, value=bad), self.assertRaises(SecurityError):
                    policy.check_request(incoming, method="POST")
        malformed = (("Host", "localhost:7860/path"),
                     ("Origin", origin + "/path"),
                     ("X-Forwarded-Host", "https://" + host),
                     ("X-Forwarded-Host", host + "/path"),
                     ("X-Forwarded-Proto", "ftp"),
                     ("X-Forwarded-Proto", "https,http"))
        for field, value in malformed:
            incoming = headers(*[(k, v if k != field else value) for k, v in baseline.items()])
            with self.subTest(field=field, value=value), self.assertRaises(SecurityError):
                policy.check_request(incoming, method="POST")

    def test_partial_proxy_metadata_uses_only_configured_https_origin(self):
        policy = RequestPolicy(local_port=7860, environ=ENV)
        origin = codespaces_origin(7860, environ=ENV)
        host = origin.split("//", 1)[1]
        for pairs in ((("X-Forwarded-Host", host),),
                      (("X-Forwarded-Proto", "https"),)):
            with self.subTest(forwarded=pairs):
                self.assertEqual(policy.check_request(headers(("Host", "127.0.0.1:7860"),
                                                               ("Origin", origin), *pairs),
                                                       method="POST"), origin)
            # Consistent forwarding metadata cannot replace the mutation Origin.
            with self.subTest(forwarded=pairs, origin="absent"), self.assertRaises(SecurityError):
                policy.check_request(headers(("Host", "127.0.0.1:7860"), *pairs), method="POST")
        for pairs in ((("X-Forwarded-Proto", "http"),),
                      (("X-Forwarded-Host", host), ("X-Forwarded-Proto", "http")),
                      (("X-Forwarded-Host", "attacker.invalid"),),
                      (("X-Forwarded-Proto", "https,http"),)):
            with self.subTest(forwarded=pairs), self.assertRaises(SecurityError):
                policy.check_request(headers(("Host", "127.0.0.1:7860"),
                                              ("Origin", origin), *pairs), method="POST")

    def test_two_configured_origins_cannot_be_mixed_by_host_or_proxy(self):
        a, b = "https://first.example.test", "https://second.example.test"
        policy = RequestPolicy([a, b], local_port=7860, environ={})
        mismatched = (
            headers(("Host", "first.example.test"), ("Origin", b)),
            headers(("Host", "127.0.0.1:7860"), ("Origin", b),
                    ("X-Forwarded-Host", "first.example.test")),
            headers(("Host", "first.example.test"), ("Origin", a),
                    ("X-Forwarded-Host", "second.example.test"),
                    ("X-Forwarded-Proto", "https")),
        )
        for incoming in mismatched:
            with self.subTest(headers=dict(incoming)), self.assertRaises(SecurityError):
                policy.check_request(incoming, method="POST")

    def test_codespaces_auto_configuration_rejects_foreign_manual_public_origin(self):
        for origin in ("https://other-cod-ab1234-7860.app.github.dev",
                       "https://manual.example.test"):
            with self.subTest(origin=origin), self.assertRaises(SecurityError):
                RequestPolicy([origin], local_port=7860, environ=ENV)

    def test_explicit_manual_https_proxy_with_and_without_metadata(self):
        policy = RequestPolicy(["https://manual.example.test"], local_port=7860, environ={})
        origin = "https://manual.example.test"
        for forwarded in ((), (("X-Forwarded-Host", "manual.example.test"),
                              ("X-Forwarded-Proto", "https"))):
            with self.subTest(forwarded=forwarded):
                self.assertEqual(policy.check_request(headers(("Host", "127.0.0.1:7860"),
                                                               ("Origin", origin), *forwarded),
                                                       method="POST"), origin)

    def test_host_case_and_explicit_default_https_port_normalize(self):
        policy = RequestPolicy(["https://MANUAL.EXAMPLE.TEST:443"], local_port=7860, environ={})
        incoming = headers(("Host", "MANUAL.EXAMPLE.TEST:443"),
                           ("Origin", "https://Manual.Example.Test:443"))
        self.assertEqual(policy.check_request(incoming, method="POST"),
                         "https://manual.example.test")
        policy.check_host("MANUAL.EXAMPLE.TEST:443")
        policy.check_origin("https://Manual.Example.Test:443", "MANUAL.EXAMPLE.TEST:443")


class FixtureSessions:
    """Synthetic authentication; production HMAC/scrypt tests live elsewhere."""
    cookie_name = "world_owner_session"
    lifetime = 3600

    def __init__(self):
        self.valid = True
        self.login = Mock(side_effect=self._login)
        self.claims = Mock(side_effect=self._claims)
        self.logout = Mock(side_effect=self._logout)

    def _login(self, password):
        if password == FIXTURE_CODE:
            self.valid = True
            return FIXTURE_TOKEN
        return None

    def _claims(self, token):
        return {"authenticated": True} if self.valid and token == FIXTURE_TOKEN else None

    def _logout(self, token):
        self.valid = False


class ProbeHandler(MobileHandler):
    """Observe body/upload dispatch while using the real request guards/login."""
    def body(self):
        self.app.body_reads.append(self.path.split("?", 1)[0])
        return super().body()

    def upload_asset(self, query):
        self.app.dispatched.append("upload")
        return self.json({"fixture_dispatch": "upload"}, 201)


class CodespacesHTTPTests(unittest.TestCase):
    def setUp(self):
        self.sessions = FixtureSessions()
        self.store = SimpleNamespace(
            create=Mock(return_value={"fixture_dispatch": "create"}),
            get=Mock(return_value={"version": "v001", "fixture_dispatch": "get"}),
            approve=Mock())
        self.app = SimpleNamespace(
            policy=None, sessions=self.sessions,
            rate=SimpleNamespace(allow=Mock(return_value=True)), store=self.store,
            body_reads=[], dispatched=[], upload_root="/tmp/synthetic-not-used",
            validate_request=Mock(side_effect=lambda x: x), check_plan_budget=Mock(),
            check_disk=Mock(), asset=Mock(), active_project_ticket=Mock(return_value=None),
            start_render=Mock(return_value={"job_id": JID, "status": "queued"}),
            scheduler=SimpleNamespace(cancel=Mock(return_value={"fixture_dispatch": "cancel"})))
        self.server = BoundedHTTPServer(("127.0.0.1", 0), ProbeHandler, self.app)
        self.port = self.server.server_port
        self.origin = codespaces_origin(self.port, environ=ENV)
        self.public_host = self.origin.split("//", 1)[1]
        self.local_host = f"127.0.0.1:{self.port}"
        self.local_origin = f"http://{self.local_host}"
        self.app.policy = RequestPolicy(local_port=self.port, environ=ENV)
        self.patches = [
            patch("engine.planner.generate_plan", return_value={"duration": 12, "scenes": []}),
            patch("engine.revisions.preview_revision", return_value={"fixture_dispatch": "revise"}),
            patch("engine.revisions.preview_clip_revision", return_value={"fixture_dispatch": "clip"}),
            patch("engine.revisions.approve_revision", return_value={"fixture_dispatch": "revision_approve"}),
            patch("deployment.mobile_server.subprocess.Popen", side_effect=AssertionError("No real worker is permitted in this HTTP fixture."))]
        self.mocks = [p.start() for p in self.patches]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        for p in reversed(self.patches):
            p.stop()

    def call(self, method, route, body=None, *, origin=None, host=None,
             cookie=True, forwarded=False, extra=()):
        pairs = [("Host", host or self.local_host), *extra]
        if origin is not None:
            pairs.append(("Origin", origin))
        if cookie:
            pairs.append(("Cookie", f"{self.sessions.cookie_name}={FIXTURE_TOKEN}"))
        if forwarded:
            pairs += [("X-Forwarded-Host", self.public_host),
                      ("X-Forwarded-Proto", "https")]
        if isinstance(body, dict):
            body = json.dumps(body).encode()
            pairs.append(("Content-Type", "application/json"))
        elif isinstance(body, str):
            body = body.encode()
        if body is not None:
            pairs.append(("Content-Length", str(len(body))))
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.putrequest(method, route, skip_host=True)
        for key, value in pairs:
            conn.putheader(key, value)
        conn.endheaders(body)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    @staticmethod
    def endpoints():
        return [
            ("/auth/login", {"password": FIXTURE_CODE}, 200),
            ("/auth/logout", {}, 303),
            ("/api/projects", {"topic": "synthetic fixture", "duration": 12}, 201),
            ("/api/assets?kind=narration", {}, 201),
            (f"/api/projects/{PID}/approve", {"version": "v001", "plan_hash": "f" * 64}, 200),
            (f"/api/projects/{PID}/render", {"version": "v001"}, 202),
            (f"/api/projects/{PID}/revise", {"version": "v001", "request": "synthetic edit"}, 200),
            (f"/api/projects/{PID}/clip", {"version": "v001", "scene_id": "S001", "asset_id": "asset_fixture"}, 200),
            (f"/api/projects/{PID}/revisions/{RID}/approve", {}, 200),
            (f"/api/jobs/{JID}/cancel", {}, 200)]

    def test_all_ten_post_endpoints_reject_wrong_origin_before_body_or_auth(self):
        self.assertEqual(len(self.endpoints()), 10)
        wrong = (None, "null", "https://foreign.invalid",
                 self.origin.replace(NAME, "other-cod-ab1234"),
                 self.origin.replace(f"-{self.port}.", f"-{self.port + 1}."),
                 self.origin + ".evil", self.origin.replace("https://", "http://"))
        for route, _, _ in self.endpoints():
            for candidate in wrong:
                with self.subTest(route=route, origin=candidate):
                    # Invalid JSON ensures guard ordering is tested, not merely
                    # a later validation or unavailable fixture plan.
                    status, _, body = self.call("POST", route, "not-json", origin=candidate)
                    self.assertEqual(status, 403)
                    self.assertEqual(json.loads(body)["error"]["code"], "INVALID_ORIGIN")
        self.assertEqual(self.app.body_reads, [])
        self.sessions.claims.assert_not_called()
        self.sessions.login.assert_not_called()
        self.sessions.logout.assert_not_called()
        self.store.create.assert_not_called()
        self.store.approve.assert_not_called()
        self.app.start_render.assert_not_called()
        for m in self.mocks:
            m.assert_not_called()

    def test_all_ten_post_endpoints_dispatch_with_exact_codespaces_origin(self):
        for route, payload, expected in self.endpoints():
            with self.subTest(route=route):
                self.sessions.valid = True
                status, _, _ = self.call("POST", route, payload, origin=self.origin, forwarded=True)
                self.assertEqual(status, expected)
        self.store.create.assert_called_once()
        self.store.approve.assert_called_once_with(PID, "v001", "f" * 64)
        self.app.start_render.assert_called_once_with(PID, "v001")
        self.app.scheduler.cancel.assert_called_once_with(JID)
        self.mocks[0].assert_called_once()
        self.mocks[1].assert_called_once()
        self.mocks[2].assert_called_once()
        self.mocks[3].assert_called_once()
        self.mocks[4].assert_not_called()
        self.assertEqual(self.app.dispatched, ["upload"])

    def test_codespaces_form_303_and_json_200_set_secure_owner_cookie(self):
        for body, expected, content_type in (
            ({"password": FIXTURE_CODE}, 200, None),
            (urlencode({"password": FIXTURE_CODE}), 303, "application/x-www-form-urlencoded")):
            with self.subTest(form=content_type is not None):
                extras = (("Content-Type", content_type),) if content_type else ()
                status, response_headers, _ = self.call("POST", "/auth/login", body,
                                                         origin=self.origin, forwarded=True,
                                                         cookie=False, extra=extras)
                self.assertEqual(status, expected)
                cookie = response_headers["Set-Cookie"]
                self.assertIn("; Secure", cookie)
                self.assertIn("HttpOnly", cookie)
                self.assertIn("SameSite=Strict", cookie)
                self.assertEqual(response_headers["Referrer-Policy"], "same-origin")
                if expected == 303:
                    self.assertEqual(response_headers["Location"], "/")

    def test_local_http_login_cookie_is_not_secure_despite_codespaces_environment(self):
        status, response_headers, _ = self.call("POST", "/auth/login",
                                                 {"password": FIXTURE_CODE},
                                                 origin=self.local_origin, cookie=False)
        self.assertEqual(status, 200)
        self.assertNotIn("; Secure", response_headers["Set-Cookie"])
        self.assertNotIn("Strict-Transport-Security", response_headers)

    def test_direct_public_host_without_forwarded_metadata_is_valid(self):
        status, response_headers, _ = self.call("POST", "/auth/login",
                                                 {"password": FIXTURE_CODE},
                                                 origin=self.origin, host=self.public_host,
                                                 cookie=False)
        self.assertEqual(status, 200)
        self.assertIn("; Secure", response_headers["Set-Cookie"])
        self.assertEqual(self.call("GET", "/api/health", host=self.public_host, cookie=False)[0], 200)

    def test_wrong_password_401_and_unauthenticated_data_401(self):
        status, _, body = self.call("POST", "/auth/login", {"password": "incorrect-fixture"},
                                     origin=self.origin, forwarded=True, cookie=False)
        self.assertEqual(status, 401)
        self.assertNotIn(FIXTURE_CODE.encode(), body)
        for route in ("/api/projects", "/auth/session",
                      f"/download/{PID}/v001/final/final.mp4",
                      f"/media/{PID}/v001/final/final.mp4"):
            with self.subTest(route=route):
                status, _, body = self.call("GET", route, forwarded=True, cookie=False)
                self.assertEqual(status, 401)
                self.assertEqual(json.loads(body)["error"]["code"], "AUTH_REQUIRED")

    def test_duplicate_forwarded_host_and_origin_rejected_before_login(self):
        for extra, forwarded in (
            ((("Origin", self.origin),), True),
            ((("X-Forwarded-Host", self.public_host),), True),
            ((("Host", self.local_host),), False)):
            with self.subTest(extra=extra):
                status, _, _ = self.call("POST", "/auth/login",
                                          {"password": FIXTURE_CODE}, origin=self.origin,
                                          forwarded=forwarded, cookie=False, extra=extra)
                self.assertIn(status, (400, 403))
        self.sessions.login.assert_not_called()


if __name__ == "__main__":
    unittest.main()
