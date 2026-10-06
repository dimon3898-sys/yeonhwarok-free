"""Read-only, secret-safe classification of Codespaces port 7860 access.

The tool sends three GET requests, never logs in, stores cookies or follows a
redirect. A status alone does not prove which server issued it. Output contains
only a normalized user-supplied origin and bounded, whitelisted observations.
"""
from __future__ import annotations

import argparse
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


PROBE_PATHS = ("/api/health", "/auth/login", "/")
MAX_JSON_BYTES = 8192
ERROR_CODES = frozenset({
    "AUTH_REQUIRED", "LOGIN_FAILED", "INVALID_HOST", "INVALID_ORIGIN",
    "INVALID_FORWARDED_HEADERS", "RATE_LIMIT", "REQUEST_TIMEOUT", "REQUEST_FAILED",
})
CONTENT_TYPES = frozenset({"application/json", "text/html", "text/plain"})
REDIRECT_PATHS = frozenset({
    "/", "/auth/login", "/login", "/session", "/sessions/new", "/codespaces",
    "/api/health",
})


class AccessDiagnosticError(ValueError):
    code = "INVALID_DIAGNOSTIC_URL"

    def __init__(self):
        super().__init__("포트 7860의 HTTPS Codespaces 주소를 입력하세요. 계정정보·쿼리·fragment는 포함할 수 없습니다.")


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        return None


def normalize_origin(value):
    """Accept only one exact HTTPS Codespaces 7860 host; never echo bad input."""
    if not isinstance(value, str) or len(value) > 2048 or not value.isascii() or re.search(r"[\s\\]", value):
        raise AccessDiagnosticError()
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        label = host.split(".", 1)[0]
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None or
                parsed.port not in {None, 443} or parsed.query or parsed.fragment or
                "?" in value or "#" in value or len(label) > 63 or
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?-7860\.app\.github\.dev", host)):
            raise AccessDiagnosticError()
    except (ValueError, TypeError):
        raise AccessDiagnosticError() from None
    # A copied link may include a path. It is neither requested nor recorded.
    return "https://" + host


def _content_type(headers):
    value = headers.get("Content-Type", "")
    if not isinstance(value, str):
        return "other"
    mime = value.split(";", 1)[0].strip().lower()
    return mime if mime in CONTENT_TYPES else "other"


def _redirect(headers, origin):
    raw = headers.get("Location")
    if not isinstance(raw, str) or len(raw) > 2048 or re.search(r"[\r\n\\]", raw):
        return None, None
    try:
        parsed = urlsplit(urljoin(origin + "/", raw))
        if (parsed.scheme not in {"https", "http"} or parsed.username is not None or
                parsed.password is not None or parsed.port not in {None, 80, 443}):
            return None, None
        path = parsed.path or "/"
        safe_path = path if path in REDIRECT_PATHS else "[other]"
        if parsed.hostname == "github.com" and path in {"/login", "/session", "/sessions/new"}:
            kind = "github_login"
        elif parsed.scheme + "://" + (parsed.hostname or "") == origin:
            kind = "same_origin"
        else:
            kind = "external_or_unknown"
        return safe_path, kind
    except (ValueError, TypeError):
        return None, None


def _error_code(response, content_type):
    if content_type != "application/json":
        return None
    try:
        body = response.read(MAX_JSON_BYTES + 1)
        if not isinstance(body, bytes) or len(body) > MAX_JSON_BYTES:
            return None
        value = json.loads(body)
        error = value.get("error") if isinstance(value, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        return code if isinstance(code, str) and code in ERROR_CODES else None
    except (OSError, ValueError, TypeError, UnicodeError):
        return None


def _probe(origin, path, opener, timeout):
    record = {"path": path, "status": None, "content_type": None,
              "redirect_path": None, "redirect_kind": None, "error_code": None,
              "network_error": None}
    request = Request(origin + path, method="GET", headers={"Accept": "application/json,text/html;q=0.8"})
    response = None
    try:
        try:
            response = opener.open(request, timeout=timeout)
        except HTTPError as error:
            response = error  # HTTP statuses remain observable without redirects.
        status = getattr(response, "status", None) or response.getcode()
        record["status"] = int(status) if isinstance(status, int) and 100 <= status <= 599 else None
        record["content_type"] = _content_type(response.headers)
        if record["status"] is not None and 300 <= record["status"] < 400:
            record["redirect_path"], record["redirect_kind"] = _redirect(response.headers, origin)
        record["error_code"] = _error_code(response, record["content_type"])
    except (URLError, OSError, TimeoutError, ValueError, TypeError, AttributeError):
        # Exception text, headers and reason strings may contain secrets.
        record["network_error"] = "REQUEST_UNAVAILABLE"
    finally:
        if response is not None:
            try:
                response.close()
            except OSError:
                pass
    return record


def classify_observations(records):
    """Classify safe response signatures; do not attribute anonymous 401s."""
    app_auth = [r for r in records if r.get("status") == 401 and
                r.get("error_code") in {"AUTH_REQUIRED", "LOGIN_FAILED"}]
    if app_auth:
        expected = {"/api/health", "/auth/login", "/"}
        unexpected_get = any(r.get("path") in expected for r in app_auth)
        codes = sorted({r["error_code"] for r in app_auth})
        return {
            "code": "GATEWAY_ERROR_SIGNATURE", "error_codes": codes,
            "evidence_paths": [r["path"] for r in app_auth],
            "unexpected_for_current_probe_get": unexpected_get,
            "cause_confirmed": False,
            "message": ("앱 인증 오류 형식과 일치합니다. 현재 검사한 GET 경로에서는 예상 밖의 응답이므로 원격 버전·다른 서버 여부를 확인하세요."
                        if unexpected_get else
                        "앱 인증 오류 형식과 일치합니다. AUTH_REQUIRED는 소유자 세션, LOGIN_FAILED는 로그인 제출 결과를 확인해야 합니다."),
        }
    unauthorized = [r for r in records if r.get("status") == 401]
    if unauthorized:
        return {"code": "UPSTREAM_OR_UNKNOWN_401", "cause_confirmed": False,
                "evidence_paths": [r["path"] for r in unauthorized],
                "message": "401 응답의 인증 계층은 미확정입니다. GitHub private-port 인증·다른 서버·원격 버전을 구분해야 합니다."}
    policy = [r for r in records if r.get("status") in {400, 403} and
              r.get("error_code") in {"INVALID_HOST", "INVALID_ORIGIN", "INVALID_FORWARDED_HEADERS"}]
    if policy:
        return {"code": "GATEWAY_POLICY_SIGNATURE", "cause_confirmed": False,
                "evidence_paths": [r["path"] for r in policy],
                "message": "앱 주소 검증 오류 형식과 일치합니다. 원격 시작 기록과 현재 Codespaces 주소 설정을 확인하세요."}
    github = [r for r in records if r.get("redirect_kind") == "github_login"]
    if github:
        return {"code": "GITHUB_LOGIN_REDIRECT", "cause_confirmed": False,
                "evidence_paths": [r["path"] for r in github],
                "message": "GitHub 로그인 경로로 이동하는 응답입니다. 소유자 GitHub 계정의 브라우저 인증을 확인하세요. 리다이렉트는 따라가지 않았습니다."}
    by_path = {r.get("path"): r for r in records}
    root, health, login = (by_path.get(p, {}) for p in ("/", "/api/health", "/auth/login"))
    if (health.get("status") == login.get("status") == 200 and
            root.get("status") == 303 and root.get("redirect_path") == "/auth/login" and
            root.get("redirect_kind") == "same_origin"):
        return {"code": "OWNER_LOGIN_FLOW_COMPATIBLE", "cause_confirmed": False,
                "evidence_paths": list(PROBE_PATHS),
                "message": "최신 앱의 미로그인 접근 흐름과 일치합니다. 소유자 로그인 성공이나 GitHub 계정 상태 자체를 검증한 것은 아닙니다."}
    if any(r.get("network_error") for r in records):
        return {"code": "ACCESS_CHECK_INCOMPLETE", "cause_confirmed": False,
                "evidence_paths": [r["path"] for r in records if r.get("network_error")],
                "message": "일부 GET 응답을 확인하지 못했습니다. 원인은 이 검사만으로 확정할 수 없습니다."}
    return {"code": "ACCESS_LAYER_UNCONFIRMED", "cause_confirmed": False,
            "evidence_paths": [r["path"] for r in records],
            "message": "현재 응답으로 인증 계층을 확정할 수 없습니다. 소유자 로그인이나 원격 실행 상태를 단정하지 않았습니다."}


def diagnose_url(value, *, timeout=5, opener=None):
    origin = normalize_origin(value)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 10:
        raise AccessDiagnosticError()
    client = opener if opener is not None else build_opener(NoRedirects())
    observations = [_probe(origin, path, client, timeout) for path in PROBE_PATHS]
    return {"format": "codespaces-access-diagnostic-v1", "origin": origin,
            "read_only": True, "redirects_followed": False, "cookies_stored": False,
            "response_bodies_recorded": False, "observations": observations,
            "assessment": classify_observations(observations)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="로그인 없이 Codespaces 7860 접근 응답을 안전하게 검사합니다.")
    parser.add_argument("url", help="포트 7860의 전체 HTTPS Codespaces URL")
    parser.add_argument("--timeout", type=float, default=5, help="각 GET의 연결 timeout, 최대10초")
    args = parser.parse_args(argv)
    try:
        result = diagnose_url(args.url, timeout=args.timeout)
    except AccessDiagnosticError as error:
        print(json.dumps({"error": {"code": error.code, "message": str(error)}}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
