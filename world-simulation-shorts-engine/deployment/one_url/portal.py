"""Provider-neutral owner portal. Only authenticated engine traffic can wake a backend.

The backend adapter's ensure() returns one trusted HTTPS origin and may be async.
Use MobileHandler's public listener, never its internal renderer listener. This
module neither provisions a provider nor starts render jobs itself.
"""
from __future__ import annotations

import asyncio
import base64
from email.message import Message
import hashlib
import hmac
import inspect
import json
import re
import secrets
import time
from http.cookies import SimpleCookie
from typing import Protocol
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse

from deployment.security import RateLimiter, RequestPolicy, SecurityError

COOKIE = "__Host-world_portal_session"
BACKEND_COOKIE = "world_owner_session"
LIFETIME = 12 * 3600
MAX_UPLOAD = 32 * 1024**2
GATEWAY_UPLOAD = 16 * 1024**2
MAX_JSON = 64 * 1024
MAX_LOGIN = 2048
PROJECT = r"project_[a-z0-9_]{6,64}"
VERSION = r"v\d{3,}"
REVISION = r"revision_[a-f0-9]{12}"
HEADERS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "content-security-policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
}
LOGIN = """<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>World Engine · 로그인</title><style>body{font-family:system-ui;background:#0b1520;color:#eff5fa;max-width:28rem;margin:8vh auto;padding:1.5rem}input,button{box-sizing:border-box;width:100%;font:inherit;padding:.9rem;margin:.5rem 0;border-radius:.5rem}button{background:#a4d8ee;color:#10202b;border:0}p{line-height:1.7}</style><h1>World Engine</h1><p>비밀번호를 입력해 주세요.</p><form action="/auth/login" method="post"><label for="owner-password">비밀번호</label><input id="owner-password" name="password" type="password" autocomplete="current-password" required maxlength="512"><button id="owner-login-submit" type="submit">로그인</button></form></html>"""


class Backend(Protocol):
    def ensure(self):
        """Return a trusted HTTPS origin, optionally as an awaitable."""


class RevocationStore(Protocol):
    async def contains(self, sid: str) -> bool:
        """Check durable logout revocation without allocating a renderer."""

    async def revoke(self, sid: str, expires: int) -> None:
        """Persist revocation before returning; retain it until token expiry."""


class _RelayStream(StreamingResponse):
    def __init__(self, upstream, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.upstream = upstream

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # A disconnect at response.start can occur before the streaming
            # generator ever begins, so generator cleanup alone is insufficient.
            await self.upstream.aclose()


def _configured_origin(value: str, *, local=False) -> str:
    if not isinstance(value, str) or not value.isascii() or re.search(r"[\s\\]", value):
        raise ValueError("A fixed origin is required")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid origin") from None
    if (parsed.username is not None or parsed.password is not None or not parsed.hostname
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
            or "?" in value or "#" in value or parsed.scheme not in {"https", "http"}
            or not re.fullmatch(r"[a-zA-Z0-9.-]+", parsed.hostname)
            or (port is not None and not 1 <= port <= 65535)):
        raise ValueError("Invalid origin")
    if parsed.scheme != "https" and not (local and parsed.hostname in {"localhost", "127.0.0.1"}):
        raise ValueError("HTTPS is required")
    authority = parsed.hostname.lower()
    if port is not None and port != (443 if parsed.scheme == "https" else 80):
        authority += f":{port}"
    return f"{parsed.scheme}://{authority}"


def allowed_route(method: str, path: str) -> bool:
    if method in {"GET", "HEAD"}:
        if path in {"/", "/index.html", "/favicon.ico", "/api/projects", "/api/production-default"}:
            return True
        if re.fullmatch(r"/static/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+\.(?:js|css|svg|png|jpg|jpeg|webp|gif|ico|woff2?|ttf|otf|json)", path):
            return True
        if re.fullmatch(rf"/api/projects/{PROJECT}(?:/(?:status|versions)|/versions/{VERSION}/plan)?", path):
            return True
        if re.fullmatch(rf"/(?:media|download)/{PROJECT}/{VERSION}/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+\.(?:mp4|png|jpg|jpeg|md|json|txt|wav|mp3|ass|srt|zip)", path):
            return True
    if method == "POST":
        return (path in {"/api/projects", "/api/assets"}
                or bool(re.fullmatch(rf"/api/projects/{PROJECT}/(?:approve|render|revise|clip)", path))
                or bool(re.fullmatch(rf"/api/projects/{PROJECT}/revisions/{REVISION}/approve", path))
                or bool(re.fullmatch(r"/api/jobs/job_[a-f0-9]{12}/cancel", path)))
    return False


def _checked_query(path: str, query: str):
    try:
        values = parse_qs(query, strict_parsing=True, keep_blank_values=True) if query else {}
    except ValueError:
        raise SecurityError("INVALID_TARGET", "요청 주소를 확인해 주세요.", 400) from None
    if any(len(value) != 1 for value in values.values()):
        raise SecurityError("INVALID_TARGET", "요청 주소를 확인해 주세요.", 400)
    if path == "/api/assets":
        if set(values) != {"filename", "kind", "license"}:
            raise SecurityError("INVALID_ASSET", "업로드 정보를 확인해 주세요.", 400)
        name, kind = values["filename"][0], values["kind"][0]
        if (not name or len(name) > 200 or "/" in name or "\\" in name
                or re.search(r"[\x00-\x1f\x7f]", name) or values["license"] != ["user_owned"]
                or kind not in {"clip", "narration"}
                or not name.lower().endswith((".mp4",) if kind == "clip" else (".wav", ".mp3"))):
            raise SecurityError("INVALID_ASSET", "업로드 정보를 확인해 주세요.", 400)
    elif re.fullmatch(rf"/api/projects/{PROJECT}(?:/status)?", path):
        if set(values) - {"version"} or ("version" in values and not re.fullmatch(VERSION, values["version"][0])):
            raise SecurityError("INVALID_TARGET", "요청 주소를 확인해 주세요.", 400)
    elif values:
        raise SecurityError("INVALID_TARGET", "요청 주소를 확인해 주세요.", 400)


class Portal:
    def __init__(self, *, origin: str, owner_password: str, backend: Backend,
                 session_key: str | bytes, client: httpx.AsyncClient | None = None,
                 clock=time.time, allow_local_backend=False,
                 revocation_store: RevocationStore | None = None):
        self.origin = _configured_origin(origin, local=True)
        self.host = urlsplit(self.origin).netloc
        if not isinstance(owner_password, str) or not 16 <= len(owner_password) <= 512:
            raise ValueError("Owner password must contain 16 to 512 characters")
        key = session_key.encode() if isinstance(session_key, str) else session_key
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("Session key must contain at least 32 bytes")
        self._key, self._owner_password = key, owner_password
        if allow_local_backend and urlsplit(self.origin).hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("Local backends are only allowed with a loopback front origin")
        self._allow_local_backend = allow_local_backend
        self._password_digest = self._hmac(owner_password.encode())
        self.backend, self.clock = backend, clock
        # Production adapters supply a durable store. The bounded RAM fallback
        # is only suitable for local tests and a single uninterrupted process.
        self.revocation_store = revocation_store
        # No inherited Codespace origin, forwarded header, or localhost alias can
        # expand the one configured front origin.
        parsed = urlsplit(self.origin)
        self.policy = RequestPolicy([self.origin], local_port=parsed.port or (443 if parsed.scheme == "https" else 80), environ={})
        self.policy.hosts = {self.host}
        self.policy.local_hosts = {self.host} if parsed.scheme == "http" else set()
        self.rate = RateLimiter(clock=clock, maximum_keys=1024)
        self._revoked: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._backend_origin: str | None = None
        self._backend_checked = 0.0
        self._backend_cookie: str | None = None
        self._backend_cookie_expiry = 0.0
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(follow_redirects=False, trust_env=False,
                                                  timeout=httpx.Timeout(240, connect=20))

    def _hmac(self, value: bytes) -> str:
        return hmac.new(self._key, value, hashlib.sha256).hexdigest()

    def _new_token(self) -> str:
        claims = {"sid": secrets.token_hex(20), "exp": int(self.clock()) + LIFETIME,
                  "aud": self.origin, "pwd": self._password_digest}
        payload = base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode()).decode().rstrip("=")
        return payload + "." + self._hmac(payload.encode())

    def _claims(self, token: str | None):
        try:
            if not isinstance(token, str) or len(token) > 1024:
                return None
            payload, signature = token.split(".")
            if not re.fullmatch(r"[a-f0-9]{64}", signature) or not hmac.compare_digest(signature, self._hmac(payload.encode())):
                return None
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            exp = claims["exp"]
            if (not isinstance(exp, int) or isinstance(exp, bool) or not self.clock() < exp <= self.clock() + LIFETIME
                    or claims.get("aud") != self.origin or not re.fullmatch(r"[a-f0-9]{40}", claims.get("sid", ""))
                    or not hmac.compare_digest(claims.get("pwd", ""), self._password_digest)
                    or claims["sid"] in self._revoked):
                return None
            return claims
        except (ValueError, TypeError, KeyError, UnicodeError):
            return None

    @staticmethod
    def _token(request: Request):
        try:
            cookies = SimpleCookie(request.headers.get("cookie", ""))
            return cookies[COOKIE].value if COOKIE in cookies else None
        except Exception:
            return None

    def _response(self, response: Response) -> Response:
        for key, value in HEADERS.items():
            response.headers[key] = value
        if self.origin.startswith("https:"):
            response.headers["strict-transport-security"] = "max-age=31536000"
        return response

    def _error(self, code: str, status: int):
        messages = {"AUTH_REQUIRED": "소유자 로그인이 필요합니다.", "LOGIN_FAILED": "비밀번호를 확인해 주세요.",
                    "RATE_LIMIT": "잠시 후 다시 시도해 주세요.", "BACKEND_UNAVAILABLE": "영상 서버를 준비하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                    "BACKEND_AUTH_FAILED": "영상 서버 인증 설정을 확인해 주세요.", "REQUEST_TOO_LARGE": "요청 파일이 너무 큽니다."}
        return self._response(JSONResponse({"error": {"code": code, "message": messages.get(code, "요청을 확인해 주세요.")}}, status_code=status))

    def _check_front(self, request: Request):
        headers = Message()
        # Validate duplicates through RequestPolicy. All client supplied proxy
        # headers are discarded, never interpreted as authority or forwarded.
        for raw_name, raw_value in request.scope.get("headers", []):
            name = raw_name.decode("latin1")
            if name.lower() in {"host", "origin"}:
                headers[name.title()] = raw_value.decode("latin1")
        effective = self.policy.check_request(headers, method=request.method)
        if effective != self.origin:
            raise SecurityError("INVALID_ORIGIN", "같은 사이트의 요청만 허용됩니다.", 403)
        if request.method == "POST" and headers.get("Origin") != self.origin:
            raise SecurityError("INVALID_ORIGIN", "같은 사이트의 요청만 허용됩니다.", 403)

    @staticmethod
    def _target(request: Request):
        raw = request.scope.get("raw_path", request.url.path.encode()).decode("ascii", errors="strict")
        path = request.scope["path"]
        query = request.scope.get("query_string", b"")
        if (len(raw) + len(query) > 4096 or not path.startswith("/") or path.startswith("//")
                or re.search(r"[\x00-\x20\x7f\\]", path) or "%" in path
                or re.search(r"%(?:2f|5c|00)", raw, re.I)
                or any(part in {".", ".."} for part in path.split("/"))
                or unquote(raw) != path or any(byte < 32 or byte == 127 for byte in query)):
            raise SecurityError("INVALID_TARGET", "요청 주소를 확인해 주세요.", 400)
        return path, query.decode("ascii")

    @staticmethod
    async def _body(request: Request, maximum: int):
        lengths = request.headers.getlist("content-length")
        if len(lengths) > 1 or (lengths and not re.fullmatch(r"\d+", lengths[0])) or request.headers.get("transfer-encoding"):
            raise SecurityError("INVALID_CONTENT_LENGTH", "요청 크기를 확인해 주세요.", 400)
        declared = int(lengths[0]) if lengths else None
        if declared is not None and declared > maximum:
            raise SecurityError("REQUEST_TOO_LARGE", "요청 파일이 너무 큽니다.", 413)
        chunks, total = [], 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > maximum:
                raise SecurityError("REQUEST_TOO_LARGE", "요청 파일이 너무 큽니다.", 413)
            chunks.append(chunk)
        if declared is not None and declared != total:
            raise SecurityError("INCOMPLETE_BODY", "요청이 완료되지 않았습니다.", 400)
        return b"".join(chunks)

    async def _login(self, request: Request):
        peer = request.client.host if request.client else "unknown"
        ip_key = self._hmac(peer.encode())
        if not self.rate.allow(("login", ip_key), count=8, window=60):
            return self._error("RATE_LIMIT", 429)
        body = await self._body(request, MAX_LOGIN)
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        password = None
        try:
            if content_type == "application/x-www-form-urlencoded":
                fields = parse_qs(body.decode("utf-8"), strict_parsing=True)
                if set(fields) == {"password"} and len(fields["password"]) == 1:
                    password = fields["password"][0]
            elif content_type == "application/json":
                fields = json.loads(body)
                if isinstance(fields, dict) and set(fields) == {"password"}:
                    password = fields["password"]
        except (ValueError, UnicodeError):
            pass
        valid = isinstance(password, str) and 1 <= len(password) <= 512
        supplied = self._hmac((password if valid else "").encode())
        if not valid or not hmac.compare_digest(supplied, self._password_digest):
            return self._error("LOGIN_FAILED", 401)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(COOKIE, self._new_token(), max_age=LIFETIME, httponly=True, secure=True, samesite="strict", path="/")
        return self._response(response)

    def _backend_headers(self, origin: str):
        headers = {"Host": urlsplit(origin).netloc, "Origin": origin, "Accept-Encoding": "identity"}
        if origin.startswith("https:"):
            headers.update({"X-Forwarded-Host": urlsplit(origin).netloc, "X-Forwarded-Proto": "https"})
        return headers

    async def _backend(self, *, renew=False, stale_token=None):
        # Ensure and internal login are serialized. Parallel browser requests
        # share one allocation and one owner session instead of creating clones.
        async with self._lock:
            now = self.clock()
            if not self._backend_origin or now - self._backend_checked >= 30:
                ensure = self.backend.ensure
                result = await ensure() if inspect.iscoroutinefunction(ensure) else await asyncio.to_thread(ensure)
                if inspect.isawaitable(result):
                    result = await result
                origin = _configured_origin(result, local=self._allow_local_backend)
                if origin == self.origin:
                    raise ValueError("Backend cannot be the front origin")
                if origin != self._backend_origin:
                    self._backend_cookie = None
                self._backend_origin, self._backend_checked = origin, now
            origin = self._backend_origin
            if (renew and self._backend_cookie == stale_token) or not self._backend_cookie or now >= self._backend_cookie_expiry:
                headers = self._backend_headers(origin)
                response = await self._client.post(origin + "/auth/login", headers=headers,
                                                   json={"password": self._owner_password}, follow_redirects=False)
                try:
                    # Backend cookies never reach the owner's browser.
                    token = None
                    for value in response.headers.get_list("set-cookie"):
                        parsed = SimpleCookie(value)
                        if BACKEND_COOKIE in parsed:
                            token = parsed[BACKEND_COOKIE].value
                    if response.status_code != 200 or not token or len(token) > 1024 or re.search(r"[;\s]", token):
                        raise SecurityError("BACKEND_AUTH_FAILED", "영상 서버 인증 설정을 확인해 주세요.", 502)
                    self._backend_cookie, self._backend_cookie_expiry = token, now + LIFETIME - 300
                finally:
                    await response.aclose()
            return origin, self._backend_cookie

    @staticmethod
    def _location(value: str, backend_origin: str):
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            if not value.startswith(backend_origin + "/"):
                raise SecurityError("BACKEND_REDIRECT_REJECTED", "영상 서버 응답을 확인해 주세요.", 502)
            value = value[len(backend_origin):]
        if (not value.startswith("/") or value.startswith("//") or parsed.fragment
                or re.search(r"[\x00-\x20\x7f\\]", value)):
            raise SecurityError("BACKEND_REDIRECT_REJECTED", "영상 서버 응답을 확인해 주세요.", 502)
        path = unquote(urlsplit(value).path)
        if "%" in path or any(part in {".", ".."} for part in path.split("/")) or not (path in {"/auth/login", "/auth/logout", "/auth/session"} or allowed_route("GET", path)):
            raise SecurityError("BACKEND_REDIRECT_REJECTED", "영상 서버 응답을 확인해 주세요.", 502)
        return value

    async def _proxy(self, request: Request, path: str, query: str, body: bytes):
        origin, token = await self._backend()
        headers = self._backend_headers(origin)
        headers["Cookie"] = f"{BACKEND_COOKIE}={token}"
        for key in ("Accept", "Content-Type", "Range", "If-Range", "If-None-Match", "If-Modified-Since"):
            value = request.headers.get(key)
            if value is not None:
                headers[key] = value
        if request.method == "POST":
            headers["Content-Length"] = str(len(body))
        target = origin + path + ("?" + query if query else "")
        upstream_request = self._client.build_request(request.method, target, headers=headers, content=body if request.method == "POST" else None)
        upstream = await self._client.send(upstream_request, stream=True, follow_redirects=False)
        expired = (upstream.status_code == 401 or (upstream.status_code in {301, 302, 303, 307, 308}
                   and upstream.headers.get("location") in {"/auth/login", origin + "/auth/login"}))
        if expired and self._backend_cookie == token:
            self._backend_cookie = None
        if expired and request.method in {"GET", "HEAD"}:
            await upstream.aclose()
            origin, token = await self._backend(renew=True, stale_token=token)
            headers.update(self._backend_headers(origin)); headers["Cookie"] = f"{BACKEND_COOKIE}={token}"
            target = origin + path + ("?" + query if query else "")
            upstream = await self._client.send(self._client.build_request(request.method, target, headers=headers), stream=True, follow_redirects=False)
            if upstream.status_code == 401:
                self._backend_cookie = None
        try:
            response_headers = {}
            for key in ("content-type", "content-length", "content-range", "accept-ranges", "content-disposition", "etag", "last-modified"):
                if key in upstream.headers:
                    response_headers[key] = upstream.headers[key]
            if "location" in upstream.headers:
                response_headers["location"] = self._location(upstream.headers["location"], origin)
            if "content-encoding" in upstream.headers:
                # Raw streaming preserves a backend response's encoding and length.
                response_headers["content-encoding"] = upstream.headers["content-encoding"]
        except Exception:
            await upstream.aclose()
            raise
        if request.method == "HEAD":
            await upstream.aclose()
            return self._response(Response(status_code=upstream.status_code, headers=response_headers))

        async def chunks():
            try:
                if upstream.is_stream_consumed:
                    yield upstream.content
                else:
                    async for chunk in upstream.aiter_raw():
                        yield chunk
            finally:
                await upstream.aclose()

        return self._response(_RelayStream(upstream, chunks(), status_code=upstream.status_code, headers=response_headers))

    async def _dispatch(self, request: Request):
        self._check_front(request)
        path, query = self._target(request)
        method = request.method
        if method not in {"GET", "HEAD", "POST"}:
            return self._error("METHOD_NOT_ALLOWED", 405)
        if method in {"GET", "HEAD"} and path == "/api/health":
            return self._response(JSONResponse({"ok": True, "authentication_required": True, "service": "World Engine"}))
        if path == "/auth/login":
            if method in {"GET", "HEAD"}:
                return self._response(HTMLResponse(LOGIN if method == "GET" else ""))
            return await self._login(request)
        claims = self._claims(self._token(request))
        if claims and self.revocation_store is not None and await self.revocation_store.contains(claims["sid"]):
            claims = None
        if path == "/auth/session" and method == "GET":
            return self._response(JSONResponse({"authenticated": bool(claims)}))
        if not claims:
            if method in {"GET", "HEAD"} and path in {"/", "/index.html"}:
                return self._response(RedirectResponse("/auth/login", status_code=303))
            return self._error("AUTH_REQUIRED", 401)
        if path == "/auth/logout" and method == "POST":
            if self.revocation_store is not None:
                await self.revocation_store.revoke(claims["sid"], claims["exp"])
            else:
                self._revoked = {sid: expiry for sid, expiry in self._revoked.items() if expiry > self.clock()}
                if len(self._revoked) >= 4096:
                    return self._error("RATE_LIMIT", 429)
                self._revoked[claims["sid"]] = claims["exp"]
            response = RedirectResponse("/auth/login", status_code=303)
            response.delete_cookie(COOKIE, path="/", httponly=True, secure=True, samesite="strict")
            return self._response(response)
        if not allowed_route(method, path):
            return self._error("NOT_FOUND", 404)
        _checked_query(path, query)
        if method == "POST":
            peer = request.client.host if request.client else "unknown"
            if not self.rate.allow(("api", self._hmac(peer.encode())), count=30, window=60):
                return self._error("RATE_LIMIT", 429)
        range_value = request.headers.get("range")
        if range_value is not None and (len(range_value) > 96 or not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", range_value)):
            return self._error("INVALID_RANGE", 416)
        body = await self._body(request, min(MAX_UPLOAD, GATEWAY_UPLOAD) if path == "/api/assets" else MAX_JSON) if method == "POST" else b""
        return await self._proxy(request, path, query, body)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                event = await receive()
                if event["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif event["type"] == "lifespan.shutdown":
                    if self._owns_client:
                        await self._client.aclose()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            return
        request = Request(scope, receive)
        try:
            response = await self._dispatch(request)
        except SecurityError as error:
            response = self._error(error.code, error.status)
        except (httpx.HTTPError, ValueError, UnicodeError, TimeoutError):
            self._backend_origin, self._backend_cookie = None, None
            response = self._error("BACKEND_UNAVAILABLE", 503)
        except Exception:
            response = self._error("BACKEND_UNAVAILABLE", 503)
        # No request logging or exception/body serialization: credentials and
        # owner paths never appear in portal diagnostics.
        await response(scope, receive, send)
