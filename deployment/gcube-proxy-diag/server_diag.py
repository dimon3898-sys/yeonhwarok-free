"""Proxy-only owner gateway; never starts the engine, GPU probe or a renderer."""
from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
from urllib.parse import urlsplit

for candidate in (Path(__file__).resolve().parents[2] / "world-simulation-shorts-engine",
                  Path("/opt/world-engine/world-simulation-shorts-engine")):
    if (candidate / "deployment/gcube/proxy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deployment.gcube.server import GcubePolicy
from deployment.security import OwnerSessions, RateLimiter, SecurityError, content_length
from observer import Observer


class Application:
    def __init__(self, owner, state_root, port=8000, *, record=None):
        if not isinstance(owner, str) or not 16 <= len(owner) <= 512 or owner != owner.strip():
            raise RuntimeError("WORLD_ENGINE_OWNER_CODE_REQUIRED")
        state_root = Path(state_root)
        state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        access = state_root / "owner.txt"
        fd = os.open(access, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream: stream.write(owner)
        self.sessions = OwnerSessions(access, state_root / "auth.json")
        self.policy = GcubePolicy(port=port)
        self.observer, self.rate = Observer(secrets.token_bytes(32)), RateLimiter()
        self.lock, self.record = threading.RLock(), record
        self.origin = None


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, app):
        self.app, self.slots = app, threading.BoundedSemaphore(24)
        super().__init__(address, Handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(8)
        return connection, address

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try: super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try: super().process_request_thread(request, address)
        finally: self.slots.release()

    def handle_error(self, *args):
        # No traceback, frame locals, request/query/body or auth data on stderr.
        print('{"diagnostic_error":"REQUEST_HANDLER_FAILED"}', flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *args): pass

    def reply(self, status, value, *, page=False, cookie=None):
        nonce = secrets.token_hex(16)
        if page:
            text = json.dumps(value, ensure_ascii=False, indent=2)
            rule = value.get("validation", {}).get("FAILED_VALIDATION_RULE") or "PROXY VALIDATION PASS"
            body = ("<!doctype html><html lang=ko><meta charset=utf-8>"
                "<meta name=viewport content='width=device-width,initial-scale=1'><title>gcube Proxy 진단</title>"
                "<style>body{background:#101722;color:#eef3f8;font:15px/1.6 system-ui;max-width:42rem;margin:auto;padding:1rem}"
                "textarea{box-sizing:border-box;width:100%;height:65vh;background:#152335;color:#fff;font:12px monospace}"
                "button,input{font:inherit;padding:.8rem;margin:.5rem 0;width:100%}h1{font-size:1.15rem;overflow-wrap:anywhere}</style>"
                "<h1>FAILED_VALIDATION_RULE: " + html.escape(rule) + "</h1>"
                "<p>Proxy 진단 전용 · GPU 검사 안 함 · 영상 생성 불가</p>"
                "<p>진단 결과를 복사한 뒤 Workload를 중지하세요. 브라우저 종료만으로 과금이 멈추지 않습니다.</p>"
                "<button id=copy>진단 결과 복사</button><textarea id=result readonly>" + html.escape(text) + "</textarea>"
                "<script nonce='" + nonce + "'>document.getElementById('copy').onclick=async()=>{const e=document.getElementById('result');"
                "try{await navigator.clipboard.writeText(e.value);document.getElementById('copy').textContent='복사 완료';}"
                "catch(x){e.select();document.execCommand('copy');}};</script></html>").encode()
            kind = "text/html; charset=utf-8"
        else:
            body, kind = json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-" + nonce + "'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        if cookie is not None:
            self.send_header("Set-Cookie", self.server.app.sessions.cookie_name + "=" + cookie + "; Path=/; Secure; HttpOnly; SameSite=Strict")
        self.end_headers()
        if self.command != "HEAD": self.wfile.write(body)

    def token(self):
        values = self.headers.get_all("Cookie", [])
        if len(values) != 1 or len(values[0]) > 4096: return None
        prefix = self.server.app.sessions.cookie_name + "="
        found = [value.strip()[len(prefix):] for value in values[0].split(";") if value.strip().startswith(prefix)]
        return found[0] if len(found) == 1 else None

    def do_GET(self): self.dispatch("GET")
    def do_HEAD(self): self.dispatch("HEAD")
    def do_POST(self): self.dispatch("POST")
    def do_PUT(self): self.reply(405, {"error": "DIAGNOSTIC_ONLY"})
    def do_DELETE(self): self.reply(405, {"error": "DIAGNOSTIC_ONLY"})

    def dispatch(self, method):
        app = self.server.app
        try:
            parsed = urlsplit(self.path)
            if len(self.path) > 4096 or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
                return self.reply(400, {"error": "INVALID_TARGET"})
            path = parsed.path
            if method in {"GET", "HEAD"} and path in {"/healthz", "/readyz"}:
                return self.reply(200 if path == "/healthz" else 503, {"ok": True, "diagnostic_mode": "PROXY_ONLY",
                    "engine_ready": False, "authentication_required": True, "gpu": "NOT_RUN", "rendering": "DISABLED"})
            with app.lock:
                effective, error, report = app.observer.observe(app.policy, self.headers, method=method, peer_ip=self.client_address[0])
                if error:
                    if app.rate.allow(("diagnostics", self.client_address[0]), count=12) and app.record:
                        app.record(report)
                    return self.reply(error.status, report, page=method == "GET" and path in {"/", "/auth/login"})
                if method == "GET" and (path == "/auth/login" or
                        path == "/" and not app.sessions.claims(self.token())):
                    # The same strict proxy policy must pass before login is available.
                    body = ("<!doctype html><html lang=ko><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                        "<h1>Proxy 진단 전용</h1><p>GPU와 렌더는 실행하지 않습니다.</p>"
                        "<form action=/auth/login method=post><input name=password type=password autocomplete=current-password required>"
                        "<button>로그인</button></form></html>").encode()
                    self.send_response(200);self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)));self.send_header("Cache-Control", "no-store")
                    self.send_header("Referrer-Policy", "same-origin")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Content-Security-Policy", "default-src 'none'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
                    self.end_headers();self.wfile.write(body)
                    return
                if path == "/auth/login" and method == "POST":
                    if not app.rate.allow(("login", self.client_address[0]), count=8):
                        return self.reply(429, {"error": "RATE_LIMIT"})
                    size = content_length(self.headers, 2048)
                    data = self.rfile.read(size)
                    try:
                        if self.headers.get_content_type() == "application/x-www-form-urlencoded":
                            from urllib.parse import parse_qs
                            fields = parse_qs(data.decode(), strict_parsing=True)
                            fields = {"password": fields["password"][0]} if set(fields) == {"password"} and len(fields["password"]) == 1 else {}
                        elif self.headers.get_content_type() == "application/json": fields = json.loads(data)
                        else: fields = {}
                    except (ValueError, UnicodeError, TypeError): fields = {}
                    token = app.sessions.login(fields.get("password") if isinstance(fields, dict) and set(fields) == {"password"} else None)
                    if not token: return self.reply(401, {"error": "LOGIN_FAILED"})
                    app.origin, app.policy = effective, GcubePolicy(origin=effective, port=app.policy.port)
                    return self.reply(200, {"authenticated": True, "diagnostic_mode": "PROXY_ONLY"}, cookie=token)
                if not app.sessions.claims(self.token()):
                    return self.reply(401, {"error": "AUTH_REQUIRED", "diagnostic_mode": "PROXY_ONLY"})
                if method not in {"GET", "HEAD"} or path not in {"/", "/diag.json", "/auth/session"}:
                    return self.reply(405, {"error": "DIAGNOSTIC_ONLY", "gpu": "NOT_RUN", "rendering": "DISABLED"})
                if app.record: app.record(report)
                return self.reply(200, report, page=path == "/")
        except SecurityError as error:
            return self.reply(error.status, {"error": error.code})
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception:
            return self.reply(400, {"error": "DIAGNOSTIC_REQUEST_FAILED"})


def main():
    owner = os.environ.get("WORLD_ENGINE_OWNER_CODE")
    if not owner or not 16 <= len(owner) <= 512 or owner != owner.strip():
        raise SystemExit("WORLD_ENGINE_OWNER_CODE_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="world-proxy-diag-") as folder:
        app = Application(owner, Path(folder) / "private", record=lambda value: print(json.dumps(value, ensure_ascii=False), flush=True))
        del owner
        server = Server(("0.0.0.0", 8000), app)
        print('{"diagnostic_mode":"PROXY_ONLY","bind":"0.0.0.0:8000","gpu":"NOT_RUN","rendering":"DISABLED"}', flush=True)
        server.serve_forever()


if __name__ == "__main__": main()
