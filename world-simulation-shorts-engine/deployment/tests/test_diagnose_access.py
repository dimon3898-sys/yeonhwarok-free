"""Synthetic HTTP observations only; no remote request or credential access."""
from contextlib import redirect_stdout
from email.message import Message
import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from deployment import diagnose_access as diagnostic


BASE = "https://miniature-doodle-fixture123-7860.app.github.dev"
PRIVATE = "SYNTHETIC_SECRET_MUST_NEVER_BE_RECORDED"


class FakeResponse:
    def __init__(self, status, content_type="application/json", body=b"", location=None):
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.headers["Set-Cookie"] = "synthetic_session=" + PRIVATE
        self.headers["WWW-Authenticate"] = "Bearer " + PRIVATE
        if location is not None:
            self.headers["Location"] = location
        self.body = body.encode() if isinstance(body, str) else body
        self.read_sizes, self.closed = [], False

    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []

    def open(self, request, *, timeout):
        self.requests.append((request, timeout))
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


class URLValidationTests(unittest.TestCase):
    def test_exact_https_codespaces_7860_origin_and_case_normalization(self):
        self.assertEqual(diagnostic.normalize_origin(BASE + "/"), BASE)
        self.assertEqual(diagnostic.normalize_origin(BASE.upper().replace("HTTPS", "https") + ":443/"), BASE)

    def test_copied_path_is_neither_requested_nor_reported(self):
        responses = [FakeResponse(200), FakeResponse(200), FakeResponse(303, location="/auth/login")]
        opener = FakeOpener(responses)
        result = diagnostic.diagnose_url(BASE + "/private/" + PRIVATE, opener=opener)
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertEqual([r.full_url for r, _ in opener.requests],
                         [BASE + p for p in diagnostic.PROBE_PATHS])

    def test_wrong_origin_port_scheme_userinfo_query_fragment_and_malformed_url_rejected(self):
        wrong = ["http://" + BASE.removeprefix("https://"),
                 BASE.replace("-7860", "-7861"), BASE + ".evil.invalid", BASE + ":7860",
                 BASE.replace("https://", "https://owner:" + PRIVATE + "@"),
                 BASE + "?code=" + PRIVATE, BASE + "#" + PRIVATE,
                 "https://github.com/login", "https://[bad-7860.app.github.dev",
                 BASE + ":invalid", BASE + "?", BASE + "#", BASE + "\\secret"]
        for value in wrong:
            with self.subTest(value=value), self.assertRaises(diagnostic.AccessDiagnosticError) as error:
                diagnostic.normalize_origin(value)
            self.assertNotIn(PRIVATE, str(error.exception))

    def test_invalid_url_fails_before_any_network_call(self):
        opener = Mock()
        with self.assertRaises(diagnostic.AccessDiagnosticError):
            diagnostic.diagnose_url("https://owner:" + PRIVATE + "@example.invalid", opener=opener)
        opener.open.assert_not_called()


class ObservationTests(unittest.TestCase):
    def run_responses(self, responses):
        opener = FakeOpener(responses)
        return diagnostic.diagnose_url(BASE, opener=opener), opener

    def assert_redacted(self, result):
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertFalse(result["cookies_stored"])
        self.assertFalse(result["response_bodies_recorded"])
        self.assertFalse(result["redirects_followed"])
        self.assertFalse(result["assessment"]["cause_confirmed"])

    def test_current_unauthenticated_gateway_redirect_flow_is_compatible_not_proven_login(self):
        result, opener = self.run_responses([FakeResponse(200), FakeResponse(200, "text/html"),
                                            FakeResponse(303, "text/html", location="/auth/login")])
        self.assertEqual(result["assessment"]["code"], "OWNER_LOGIN_FLOW_COMPATIBLE")
        self.assertEqual(len(opener.requests), 3)
        self.assert_redacted(result)

    def test_gateway_auth_required_signature_is_distinct_from_anonymous_401(self):
        body = json.dumps({"error": {"code": "AUTH_REQUIRED", "message": PRIVATE}, "password": PRIVATE})
        result, _ = self.run_responses([FakeResponse(401, body=body), FakeResponse(200), FakeResponse(303)])
        self.assertEqual(result["assessment"]["code"], "GATEWAY_ERROR_SIGNATURE")
        self.assertEqual(result["assessment"]["error_codes"], ["AUTH_REQUIRED"])
        self.assertTrue(result["assessment"]["unexpected_for_current_probe_get"])
        self.assert_redacted(result)

    def test_login_failed_signature_does_not_claim_password_was_submitted(self):
        body = json.dumps({"error": {"code": "LOGIN_FAILED", "message": PRIVATE}})
        result, opener = self.run_responses([FakeResponse(200), FakeResponse(401, body=body), FakeResponse(303)])
        self.assertEqual(result["assessment"]["error_codes"], ["LOGIN_FAILED"])
        self.assertTrue(result["assessment"]["unexpected_for_current_probe_get"])
        self.assertTrue(all(r.get_method() == "GET" and r.data is None for r, _ in opener.requests))
        self.assert_redacted(result)

    def test_github_style_html_401_remains_upstream_or_unknown_without_reading_body(self):
        upstream = FakeResponse(401, "text/html", body="<h1>401</h1>" + PRIVATE)
        result, _ = self.run_responses([upstream, FakeResponse(401, "text/plain", PRIVATE), FakeResponse(401)])
        self.assertEqual(result["assessment"]["code"], "UPSTREAM_OR_UNKNOWN_401")
        self.assertEqual(upstream.read_sizes, [])
        self.assert_redacted(result)

    def test_github_login_redirect_is_reported_without_following_or_logging_token(self):
        result, opener = self.run_responses([FakeResponse(302, "text/html", location=
                                                        "https://github.com/login?return_to=" + PRIVATE),
                                            FakeResponse(200), FakeResponse(302, "text/html", location="/login?token=" + PRIVATE)])
        self.assertEqual(result["assessment"]["code"], "GITHUB_LOGIN_REDIRECT")
        self.assertEqual(result["observations"][0]["redirect_path"], "/login")
        self.assertEqual(len(opener.requests), 3)
        self.assert_redacted(result)

    def test_redirect_dynamic_path_and_userinfo_are_never_recorded(self):
        result, _ = self.run_responses([FakeResponse(302, location="/token/" + PRIVATE),
                                        FakeResponse(302, location="https://owner:" + PRIVATE + "@github.com/login"),
                                        FakeResponse(303, location="/auth/login?token=" + PRIVATE + "#" + PRIVATE)])
        self.assertEqual(result["observations"][0]["redirect_path"], "[other]")
        self.assertIsNone(result["observations"][1]["redirect_path"])
        self.assertEqual(result["observations"][2]["redirect_path"], "/auth/login")
        self.assert_redacted(result)

    def test_content_type_parameters_unknown_error_code_and_error_message_are_redacted(self):
        body = json.dumps({"error": {"code": PRIVATE, "message": PRIVATE}, "cookies": PRIVATE})
        result, _ = self.run_responses([FakeResponse(401, "application/json; secret=" + PRIVATE, body),
                                        FakeResponse(200, "custom/" + PRIVATE), FakeResponse(200)])
        self.assertEqual(result["observations"][0]["content_type"], "application/json")
        self.assertIsNone(result["observations"][0]["error_code"])
        self.assertEqual(result["observations"][1]["content_type"], "other")
        self.assert_redacted(result)

    def test_policy_403_signature_is_separate_from_401(self):
        body = json.dumps({"error": {"code": "INVALID_ORIGIN", "message": PRIVATE}})
        result, _ = self.run_responses([FakeResponse(403, body=body), FakeResponse(200), FakeResponse(200)])
        self.assertEqual(result["assessment"]["code"], "GATEWAY_POLICY_SIGNATURE")
        self.assert_redacted(result)

    def test_oversized_or_malformed_json_cannot_leak_arbitrary_content(self):
        large = FakeResponse(401, body=PRIVATE * diagnostic.MAX_JSON_BYTES)
        result, _ = self.run_responses([large, FakeResponse(401, body=b"not-json-" + PRIVATE.encode()),
                                        FakeResponse(401, body=b"\xff")])
        self.assertEqual(large.read_sizes, [diagnostic.MAX_JSON_BYTES + 1])
        self.assertTrue(all(r["error_code"] is None for r in result["observations"]))
        self.assert_redacted(result)

    def test_network_failure_exception_messages_are_not_recorded(self):
        result, _ = self.run_responses([URLError(PRIVATE), TimeoutError(PRIVATE), OSError(PRIVATE)])
        self.assertEqual(result["assessment"]["code"], "ACCESS_CHECK_INCOMPLETE")
        self.assertTrue(all(r["network_error"] == "REQUEST_UNAVAILABLE" for r in result["observations"]))
        self.assert_redacted(result)

    def test_requests_are_get_only_without_cookie_authorization_or_body(self):
        responses = [FakeResponse(200), FakeResponse(200), FakeResponse(200)]
        result, opener = self.run_responses(responses)
        for request, timeout in opener.requests:
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertIsNone(request.get_header("Cookie"))
            self.assertIsNone(request.get_header("Authorization"))
            self.assertEqual(timeout, 5)
        self.assertTrue(all(r.closed for r in responses))
        self.assert_redacted(result)

    def test_http_error_401_response_is_captured_without_echoing_reason(self):
        headers = Message()
        headers["Content-Type"] = "application/json"
        body = io.BytesIO(json.dumps({"error": {"code": "AUTH_REQUIRED", "message": PRIVATE}}).encode())
        error = HTTPError(BASE + "/api/health", 401, PRIVATE, headers, body)
        result, _ = self.run_responses([error, FakeResponse(200), FakeResponse(200)])
        self.assertEqual(result["observations"][0]["status"], 401)
        self.assertEqual(result["observations"][0]["error_code"], "AUTH_REQUIRED")
        self.assert_redacted(result)

    def test_default_client_has_no_redirect_handler_and_does_not_follow_redirect(self):
        opener = FakeOpener([FakeResponse(302, location="https://github.com/login?token=" + PRIVATE),
                             FakeResponse(200), FakeResponse(200)])
        with patch.object(diagnostic, "build_opener", return_value=opener) as build:
            result = diagnostic.diagnose_url(BASE)
        self.assertIsInstance(build.call_args.args[0], diagnostic.NoRedirects)
        request = Request(BASE)
        self.assertIsNone(build.call_args.args[0].redirect_request(request, None, 302, PRIVATE, {},
                                                                 "https://github.com/login"))
        self.assertEqual(len(opener.requests), 3)
        self.assert_redacted(result)

    def test_invalid_timeout_is_rejected_before_network(self):
        for timeout in (0, -1, 11, True, "secret", float("nan"), float("inf")):
            opener = Mock()
            with self.subTest(timeout=timeout), self.assertRaises(diagnostic.AccessDiagnosticError):
                diagnostic.diagnose_url(BASE, timeout=timeout, opener=opener)
            opener.open.assert_not_called()


class CLITests(unittest.TestCase):
    def test_invalid_credentials_url_cli_reports_only_fixed_error(self):
        captured = io.StringIO()
        with redirect_stdout(captured), patch.object(diagnostic, "build_opener") as build:
            code = diagnostic.main([BASE.replace("https://", "https://owner:" + PRIVATE + "@")])
        self.assertEqual(code, 2)
        self.assertNotIn(PRIVATE, captured.getvalue())
        self.assertEqual(json.loads(captured.getvalue())["error"]["code"], "INVALID_DIAGNOSTIC_URL")
        build.assert_not_called()

    def test_success_cli_emits_safe_diagnostic_not_raw_body_or_cookie(self):
        opener = FakeOpener([FakeResponse(401, "text/html", PRIVATE), FakeResponse(200), FakeResponse(200)])
        captured = io.StringIO()
        with redirect_stdout(captured), patch.object(diagnostic, "build_opener", return_value=opener):
            code = diagnostic.main([BASE])
        self.assertEqual(code, 0)
        self.assertNotIn(PRIVATE, captured.getvalue())
        self.assertEqual(json.loads(captured.getvalue())["assessment"]["code"], "UPSTREAM_OR_UNKNOWN_401")


if __name__ == "__main__":
    unittest.main()
