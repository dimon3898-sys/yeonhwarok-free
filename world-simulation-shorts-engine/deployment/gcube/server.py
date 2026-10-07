"""gCube public gateway adapter; the approved mobile gateway and engine stay intact."""
from __future__ import annotations

import argparse
import fcntl
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import threading
from urllib.parse import parse_qs, unquote, urlsplit

# The core gateway imports its top-level `server` module. Keep that directory
# first even when this adapter is executed directly or discovered as a test.
_ENGINE_ROOT = str(Path(__file__).resolve().parents[2])
if _ENGINE_ROOT in sys.path:
    sys.path.remove(_ENGINE_ROOT)
sys.path.insert(0, _ENGINE_ROOT)

from deployment.mobile_server import (APP_ROOT, BoundedHTTPServer, InternalHandler,
                                      MobileApplication, MobileHandler, checked_state_root)
from deployment.security import RequestPolicy, SecurityError, _authority, content_length, private_json
from deployment.gcube.diagnostics import DiagnosticsError, build_mobile_diagnostics
from deployment.gcube.boot_status import gpu_diagnostic_html, proxy_diagnostic_html, safe_gpu_diagnostics
from deployment.gcube.proxy import internal_probe_headers, provider_origin, request_envelope
from engine.storage import EngineError

LOGIN_HTML = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>World Engine · 로그인</title><style>body{font-family:system-ui;background:#0b1520;color:#eff5fa;max-width:28rem;margin:8vh auto;padding:1.5rem}input,button{box-sizing:border-box;width:100%;font:inherit;padding:.9rem;margin:.5rem 0;border-radius:.5rem}button{background:#a4d8ee;color:#10202b;border:0}p{line-height:1.7}</style><h1>World Engine</h1><p>비밀번호를 입력해 주세요.</p><form id="owner-login-form" action="/auth/login" method="post"><label for="owner-password">비밀번호</label><input id="owner-password" name="password" type="password" autocomplete="current-password" required maxlength="512"><button id="owner-login-submit" type="submit">로그인</button></form></html>'''

# The upstream protocol no longer attests browser TLS. Keep the public form
# disabled until the browser itself confirms HTTPS; never submit a password on
# an HTTP address. Existing explicitly local development retains its own form.
SECURE_LOGIN_JS = ''''use strict';
const form=document.getElementById('owner-login-form');
const fields=document.getElementById('owner-login-fields');
const notice=document.getElementById('owner-https-required');
const secure=()=>window.location.protocol==='https:' && window.isSecureContext===true;
if(form && fields){
  if(secure()){fields.disabled=false;if(notice)notice.hidden=true;}
  form.addEventListener('submit',event=>{if(!secure()){event.preventDefault();fields.disabled=true;if(notice)notice.hidden=false;}});
}
'''


def public_login_html(origin):
    fields = LOGIN_HTML.replace('<label for="owner-password">', '<fieldset id="owner-login-fields" disabled><label for="owner-password">')
    fields = fields.replace('</button></form>', '</button></fieldset></form>')
    notice = '<p id="owner-https-required">HTTPS 주소에서만 로그인할 수 있습니다. <a href="' + html.escape(origin + '/auth/login', quote=True) + '">HTTPS로 열기</a></p>'
    return fields.replace('</html>', notice + '<script src="/auth/secure-login.js" defer></script></html>')


def configured_origin(value, *, port=8000, local_mode=False):
    policy = RequestPolicy([value], local_port=port, environ={})
    origin = next(iter(policy.origins))
    if not local_mode and not origin.startswith("https://"):
        raise SecurityError("HTTPS_REQUIRED", "공개 주소에는 HTTPS가 필요합니다.")
    return origin


class GcubePolicy:
    """A pending authority is a login candidate, never a trusted binding."""
    def __init__(self, *, origin=None, port=8000, local_mode=False):
        self.origin, self.port, self.local_mode = origin, port, local_mode
        self._bound = None
        self.secure_cookie = True
        if origin:
            self._bound = RequestPolicy([origin], local_port=port, environ={})
            self._bound.hosts = {urlsplit(origin).netloc}
            self._bound.local_hosts = {urlsplit(origin).netloc} if origin.startswith("http://") else set()

    def check_request(self, headers, *, method="GET", peer_ip=None):
        if self.local_mode and self._bound:
            effective = self._bound.check_request(headers, method=method, peer_ip=peer_ip)
            if effective != self.origin:
                raise SecurityError("INVALID_ORIGIN", "같은 사이트의 요청만 허용됩니다.", 403)
            origin = RequestPolicy._single_header(headers, "Origin")
            if origin is not None and origin != effective:
                raise SecurityError("INVALID_ORIGIN", "같은 사이트의 요청만 허용됩니다.", 403)
            return effective
        origin = RequestPolicy._single_header(headers, "Origin")
        candidate, _ = request_envelope(headers, origin=self.origin, port=self.port, peer_ip=peer_ip)
        if origin is not None and origin != candidate:
            raise SecurityError("INVALID_ORIGIN", "같은 사이트의 요청만 허용됩니다.", 403)
        if method not in {"GET", "HEAD", "OPTIONS"} and origin != candidate:
            raise SecurityError("INVALID_ORIGIN", "같은 사이트의 요청만 허용됩니다.", 403)
        return candidate

    def diagnostics(self, headers, *, peer_ip=None):
        effective = self.check_request(headers, peer_ip=peer_ip)
        if self.local_mode:
            return {"status": "PASS", "normalized_host": urlsplit(effective).netloc,
                    "forwarded_host": None, "forwarded_proto": None, "forwarded_port": None,
                    "xff_entry_count": 0, "envoy_external_address_present": False,
                    "effective_origin": effective}
        _, summary = request_envelope(headers, origin=self.origin, port=self.port, peer_ip=peer_ip)
        return {"status": "PASS", **summary}


class GcubeApplication(MobileApplication):
    def __init__(self, state_root, internal_url, access_file, *, public_origin=None,
                 public_port=8000, local_mode=False, maximum_duration=20,
                 maximum_projects=30, disk_floor=2 * 1024**3,
                 maximum_job_seconds=3600, runner=None):
        super().__init__(state_root, internal_url, access_file, public_port=public_port,
                         maximum_duration=maximum_duration, maximum_projects=maximum_projects,
                         disk_floor=disk_floor, maximum_job_seconds=maximum_job_seconds, runner=runner)
        self.origin_lock = threading.RLock()
        self.public_port, self.local_mode = public_port, local_mode
        self.binding_path = self.state_root / "gcube-origin.json"
        stored = self._stored_origin()
        value = public_origin or os.environ.get("WORLD_ENGINE_PUBLIC_ORIGIN")
        configured = configured_origin(value, port=public_port, local_mode=local_mode) if value else None
        if local_mode and not configured:
            raise SecurityError("LOCAL_ORIGIN_REQUIRED", "로컬 테스트 주소를 지정해 주세요.")
        self.bound_origin = stored
        if configured and configured != stored:
            self._clear_sessions()
            self._save_binding(configured)
            self.bound_origin = configured
        self.policy = GcubePolicy(origin=self.bound_origin, port=public_port, local_mode=local_mode)

    def _stored_origin(self):
        path = self.binding_path
        if not path.exists() and not path.is_symlink():
            return None
        if (path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077
                or path.stat().st_size > 2048):
            raise SecurityError("INVALID_ORIGIN_BINDING", "서버 주소 설정 파일을 확인해 주세요.")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or record.get("schema_version") != 1:
                raise ValueError()
            return configured_origin(record["origin"], port=self.public_port, local_mode=self.local_mode)
        except (OSError, ValueError, KeyError, TypeError, SecurityError):
            raise SecurityError("INVALID_ORIGIN_BINDING", "서버 주소 설정 파일을 확인해 주세요.") from None

    def _save_binding(self, origin):
        private_json(self.binding_path, {"schema_version": 1, "origin": origin})

    def _clear_sessions(self, keep_token=None):
        with self.sessions.lock:
            claim = self.sessions.claims(keep_token) if keep_token else None
            self.sessions.record["sessions"] = {claim["sid"]: claim["exp"]} if claim else {}
            private_json(self.sessions.path, self.sessions.record)

    def claim_origin(self, origin, token):
        # Caller must hold origin_lock and have verified the owner's password.
        if not self.sessions.claims(token):
            raise SecurityError("LOGIN_FAILED", "비밀번호를 확인해 주세요.", 401)
        if self.bound_origin and origin != self.bound_origin:
            raise SecurityError("ORIGIN_ALREADY_BOUND", "서버 주소 설정을 확인해 주세요.", 403)
        if not self.bound_origin:
            if not self.local_mode:
                provider_origin(urlsplit(origin).netloc)
            self._clear_sessions(keep_token=token)
            self._save_binding(origin)
            self.bound_origin = origin
            self.policy = GcubePolicy(origin=origin, port=self.public_port, local_mode=self.local_mode)

    def runtime_health(self):
        diagnostic = {}
        path = self.state_root / "gcube-runtime.json"
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 256 * 1024:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    diagnostic = value
            except (OSError, ValueError):
                pass
        gpu = diagnostic.get("gpu") if isinstance(diagnostic.get("gpu"), dict) else {}
        storage = diagnostic.get("storage") if isinstance(diagnostic.get("storage"), dict) else {}
        verified = gpu.get("gpu_rendering_verified") is True
        mode = gpu.get("render_mode") if gpu.get("render_mode") in {"gpu-required", "cpu"} else "unknown"
        profile = gpu.get("gpu_profile") if isinstance(gpu.get("gpu_profile"), str) and len(gpu["gpu_profile"]) <= 80 else None
        devices = gpu.get("nvidia_devices")
        devices = devices if isinstance(devices, list) else []
        models = [device["name"][:128] for device in devices
                  if isinstance(device, dict) and isinstance(device.get("name"), str)][:4]
        return {"ok": True, "engine_ready": True, "phase": "ready",
                "authentication_required": True, "provider": "GCUBE",
                "public_origin_bound": bool(self.bound_origin),
                "render_backend": "GPU_VERIFIED" if verified else "CPU_VERIFIED" if mode == "cpu" else "UNVERIFIED",
                "gpu": {"render_mode": mode, "gpu_profile": profile, "gpu_rendering_verified": verified,
                        "models": models,
                        "speedup_measured": gpu.get("speedup_measured") is True},
                "storage": {"persistent_mount_detected": storage.get("persistent_mount_detected") is True,
                            "filesystem_probe_passed": storage.get("filesystem_probe_passed") is True,
                            "mode": storage.get("mode") if storage.get("mode") in {"required", "ephemeral"} else "unknown"},
                "billing": {"provider_stop_verified": False,
                            "message": "유휴 상태에서도 과금될 수 있습니다. 다운로드 후 gCube Workload를 중지해 주세요."},
                "limits": {"max_duration": self.maximum_duration}}

    def gpu_diagnostics(self):
        """Owner-only observed graphics proof, projected from the private report."""
        gpu = {}
        path = self.state_root / "gcube-runtime.json"
        if (path.is_file() and not path.is_symlink() and path.stat().st_size <= 256 * 1024
                and not stat.S_IMODE(path.stat().st_mode) & 0o077):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict) and isinstance(value.get("gpu"), dict):
                    gpu = value["gpu"]
            except (OSError, ValueError):
                pass
        mode = gpu.get("render_mode") if gpu.get("render_mode") in {"gpu-required", "cpu"} else "unknown"
        diagnostic = safe_gpu_diagnostics(gpu.get("diagnostics"))
        stages = {row.get("id"): row.get("status") for row in diagnostic.get("stages", [])}
        webgl = diagnostic.get("webgl", {})
        verified = (mode == "gpu-required" and gpu.get("gpu_rendering_verified") is True
                    and not diagnostic.get("failed_stage") and stages.get("E") == "PASS"
                    and stages.get("F") == "PASS" and webgl.get("draw_passed") is True
                    and webgl.get("software_renderer") is False)
        devices = diagnostic.get("nvidia_devices", [])
        models = ", ".join(device.get("name", "") for device in devices) or "NVIDIA"
        message = (models + " WebGL VERIFIED · World Engine READY" if verified else
                   "CPU 비교 모드 · NVIDIA WebGL 검증 아님" if mode == "cpu" else
                   "NVIDIA WebGL 진단 증명 미확인")
        if verified and any("T4" in device.get("name", "").split() for device in devices):
            message = "NVIDIA T4 WEBGL VERIFIED · WORLD ENGINE READY"
        return {"engine_ready": True, "gpu_rendering_verified": verified,
                "render_mode": mode, "message": message, "diagnostics": diagnostic}


class GcubeHandler(MobileHandler):
    def dispatch(self, method):
        try:
            target = urlsplit(self.path)
            if len(self.path) > 4096 or target.scheme or target.netloc:
                raise SecurityError("INVALID_TARGET", "요청 주소를 확인해 주세요.")
            path = unquote(target.path)
            # Kubelet/Istio probes use a Pod IP or localhost authority rather
            # than the external HTTPS origin. Only fixed read-only liveness
            # facts bypass the origin policy, never authentication or APIs.
            if method in {"GET", "HEAD"} and path in {"/healthz", "/readyz", "/api/health"}:
                origin = RequestPolicy._single_header(self.headers, "Origin")
                host = RequestPolicy._single_header(self.headers, "Host")
                forwarded_present = any(self.headers.get_all(name, []) for name in (
                    "Forwarded", "X-Forwarded-Host", "X-Forwarded-Proto", "X-Forwarded-Port",
                    "X-Forwarded-For", "X-Envoy-External-Address"))
                probe = path in {"/healthz", "/readyz"}
                if path == "/api/health" and host:
                    try:
                        authority = urlsplit("http://" + host)
                        numeric = authority.hostname
                        probe = numeric in {"localhost", "0.0.0.0"}
                        if not probe:
                            ipaddress.ip_address(numeric)
                            probe = True
                        probe = probe and not authority.username and not authority.password and not authority.path
                        # Reject malformed or out-of-range ports before the
                        # authority can be used even for this read-only route.
                        authority.port
                    except (ValueError, TypeError):
                        probe = False
                    bound = urlsplit(self.app.bound_origin).netloc if self.app.bound_origin else None
                    local_health = (self.client_address[0] in {"127.0.0.1", "::1"}
                                    and host in {f"127.0.0.1:{self.app.public_port}",
                                                 f"localhost:{self.app.public_port}"}
                                    and all(RequestPolicy._single_header(self.headers, name) is None
                                            for name in ("X-Forwarded-Host", "X-Forwarded-Proto")))
                    if host == bound or local_health:
                        probe = False
                internal_probe = forwarded_present and internal_probe_headers(
                    self.headers, peer_ip=self.client_address[0], port=self.app.public_port)
                if probe and origin is None and (not forwarded_present or internal_probe):
                    return self.json({"ok": True, "engine_ready": True, "phase": "ready",
                                      "authentication_required": True})
            # Container liveness is a read-only exception on the loopback peer.
            # It cannot bind an origin, authenticate, or reach any other route.
            if method in {"GET", "HEAD"} and path == "/api/health" and self.client_address[0] in {"127.0.0.1", "::1"}:
                host = RequestPolicy._single_header(self.headers, "Host")
                if (host in {f"127.0.0.1:{self.app.public_port}", f"localhost:{self.app.public_port}"}
                        and origin is None and not forwarded_present):
                    return self.json(self.app.runtime_health())
            self._effective_origin = self.app.policy.check_request(self.headers, method=method, peer_ip=self.client_address[0])
            if method in {"GET", "HEAD"} and path in {"/healthz", "/readyz"}:
                return self.json({"ok": True, "engine_ready": True, "phase": "ready",
                                  "authentication_required": True})
            if not self.app.bound_origin and method not in {"GET", "HEAD", "OPTIONS"} and path != "/auth/login":
                raise SecurityError("ORIGIN_UNBOUND", "먼저 소유자 로그인을 완료해 주세요.", 403)
            if method in {"GET", "HEAD"} and path == "/api/health":
                return self.json(self.app.runtime_health())
            if method in {"GET", "HEAD"} and path == "/auth/login":
                return self._html(LOGIN_HTML if self.app.local_mode else public_login_html(self._effective_origin))
            if method in {"GET", "HEAD"} and path == "/auth/secure-login.js":
                body = SECURE_LOGIN_JS.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                if method != 'HEAD': self.wfile.write(body)
                return
            # A restored auth.json must not grant access before the origin binds.
            if not self.app.bound_origin and path != "/auth/login":
                if path.startswith(("/api/", "/media/", "/download/", "/auth/")) or path in {
                        "/gcube/gpu", "/gcube/gpu.json"}:
                    raise SecurityError("AUTH_REQUIRED", "소유자 로그인이 필요합니다.", 401)
                self.send_response(303)
                self.send_header("Location", "/auth/login")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path in {"/api/gcube/proxy", "/gcube/proxy.json"}:
                if not self.app.sessions.claims(self._token()):
                    raise SecurityError("AUTH_REQUIRED", "소유자 로그인이 필요합니다.", 401)
                if method not in {"GET", "HEAD"}:
                    raise SecurityError("METHOD_NOT_ALLOWED", "읽기 전용 요청입니다.", 405)
                return self.json(self.app.policy.diagnostics(self.headers, peer_ip=self.client_address[0]))
            if path in {"/api/gcube/gpu", "/gcube/gpu", "/gcube/gpu.json"}:
                if not self.app.sessions.claims(self._token()):
                    raise SecurityError("AUTH_REQUIRED", "소유자 로그인이 필요합니다.", 401)
                if method not in {"GET", "HEAD"}:
                    raise SecurityError("METHOD_NOT_ALLOWED", "읽기 전용 요청입니다.", 405)
                record = self.app.gpu_diagnostics()
                record["proxy"] = self.app.policy.diagnostics(self.headers, peer_ip=self.client_address[0])
                if path != "/gcube/gpu":
                    return self.json(record)
                body = ("<!doctype html><html lang=ko><meta charset=utf-8>"
                        "<meta name=viewport content='width=device-width,initial-scale=1'>"
                        "<title>World Engine GPU 진단</title><style>"
                        "body{margin:0;background:#101722;color:#edf3fa;font:16px/1.6 sans-serif}"
                        "main{max-width:36rem;padding:1.5rem 1rem;margin:auto}h1{font-size:1.25rem}"
                        "h2{font-size:1.1rem}table{width:100%;border-collapse:collapse;font-size:.85rem}"
                        "th,td{padding:.45rem .25rem;text-align:left;border-bottom:1px solid #344352;overflow-wrap:anywhere}"
                        "th{width:48%}a{color:#b7d9f1}</style><main><h1>" + html.escape(record["message"]) +
                        "</h1>" + gpu_diagnostic_html(record["diagnostics"]) + proxy_diagnostic_html(record["proxy"]) +
                        "<p>GPU 속도 향상과 실제 영상 렌더 시간은 별도 실측이 필요합니다.</p>"
                        "<p>검증 실패 시 gcube Workload를 중지하세요. 브라우저 종료만으로 과금이 멈추지 않습니다.</p>"
                        "<p><a href='/'>World Engine으로 돌아가기</a> · <a href='/gcube/gpu.json'>진단 JSON</a></p></main></html>")
                return self._html(body)
            if path in {"/api/gcube/benchmark", "/gcube/benchmark.json"}:
                if not self.app.sessions.claims(self._token()):
                    raise SecurityError("AUTH_REQUIRED", "소유자 로그인이 필요합니다.", 401)
                if method not in {"GET", "HEAD"}:
                    raise SecurityError("METHOD_NOT_ALLOWED", "읽기 전용 요청입니다.", 405)
                try:
                    record = build_mobile_diagnostics(self.app.state_root)
                except DiagnosticsError as error:
                    raise SecurityError(error.code, "측정 기록을 읽지 못했습니다.", 503) from None
                if path == "/api/gcube/benchmark":
                    return self.json(record)
                body = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="world-engine-gcube-measurements.json"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if method != "HEAD":
                    self.wfile.write(body)
                return
            return super().dispatch(method)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            self.error(error)

    def _login(self):
        if not self.app.rate.allow(("login", self.client_address[0]), count=8):
            raise SecurityError("RATE_LIMIT", "잠시 후 다시 시도해 주세요.", 429)
        size = content_length(self.headers, 2048)
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise SecurityError("INCOMPLETE_BODY", "요청이 완료되지 않았습니다.")
        form = self.headers.get_content_type() == "application/x-www-form-urlencoded"
        password = None
        try:
            if form:
                fields = parse_qs(raw.decode("utf-8"), strict_parsing=True)
                if set(fields) == {"password"} and len(fields["password"]) == 1:
                    password = fields["password"][0]
            elif self.headers.get_content_type() == "application/json":
                fields = json.loads(raw)
                if isinstance(fields, dict) and set(fields) == {"password"}:
                    password = fields["password"]
        except (ValueError, TypeError, UnicodeError):
            pass
        with self.app.origin_lock:
            if self.app.bound_origin and self._effective_origin != self.app.bound_origin:
                raise SecurityError("ORIGIN_ALREADY_BOUND", "서버 주소 설정을 확인해 주세요.", 403)
            token = self.app.sessions.login(password)
            if not token:
                raise SecurityError("LOGIN_FAILED", "비밀번호를 확인해 주세요.", 401)
            try:
                self.app.claim_origin(self._effective_origin, token)
            except Exception:
                self.app.sessions.logout(token)
                raise
        if form:
            self.send_response(303)
            self._cookie(token)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            body = b'{"authenticated":true}'
            self.send_response(200)
            self._cookie(token)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def file(self, path, attachment=False, head=False):
        if Path(path) == APP_ROOT / "web" / "index.html" and not attachment:
            health = self.app.runtime_health()
            storage = "영구 저장 공간 감지됨" if health["storage"]["persistent_mount_detected"] else "영구 저장 공간 미확인 · 최종 MP4를 다운로드해 보관하세요."
            message = html.escape(health["billing"]["message"])
            graphics = ("3D NVIDIA 그래픽 확인 · " + ", ".join(health["gpu"]["models"])) if health["gpu"]["gpu_rendering_verified"] else "CPU 비교 모드 · GPU 가속 미사용" if health["gpu"]["render_mode"] == "cpu" else "그래픽 검증 미확인"
            if health["gpu"]["gpu_rendering_verified"]:
                graphics = self.app.gpu_diagnostics()["message"]
            note = f'<aside role="note" aria-label="서버 상태" style="max-width:45rem;margin:.75rem auto;padding:.8rem;border:1px solid #a4d8ee;border-radius:.5rem;background:#10202b;color:#eff5fa;font:12px/1.5 system-ui">{html.escape(graphics)} · FFmpeg 인코딩은 CPU<br>{message}<br>{html.escape(storage)}<br><a href="/gcube/gpu" style="color:#a4d8ee">GPU / WebGL 진단</a> · <a href="/gcube/benchmark.json" download style="color:#a4d8ee">GPU·메모리 측정 기록 다운로드</a></aside>'
            text = Path(path).read_text(encoding="utf-8")
            return self._html(text.replace("<body>", "<body>" + note, 1))
        return super().file(path, attachment, head)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--access-file")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--internal-port", type=int, default=8001)
    parser.add_argument("--public-origin")
    parser.add_argument("--local-mode", action="store_true", help="Allow explicit loopback HTTP tests only")
    parser.add_argument("--max-duration", type=float, default=20)
    parser.add_argument("--max-projects", type=int, default=30)
    parser.add_argument("--maximum-job-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    if not (1 <= args.port <= 65535 and 1 <= args.internal_port <= 65535) or args.port == args.internal_port:
        parser.error("Distinct valid public and internal ports are required")
    if not 5 <= args.max_duration <= 180 or args.maximum_job_seconds <= 0:
        parser.error("The video limit must be 5 to 180 seconds and the job limit positive")
    runtime = checked_state_root(args.state_root)
    lease = (runtime / "server.lock").open("a")
    os.chmod(runtime / "server.lock", 0o600)
    try:
        fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lease.close()
        raise SecurityError("RUNTIME_IN_USE", "이 상태 폴더의 서버가 이미 실행 중입니다.") from None
    access = args.access_file or str(runtime / "owner-code.txt")
    app = GcubeApplication(runtime, f"http://127.0.0.1:{args.internal_port}", access,
                           public_origin=args.public_origin, public_port=args.port, local_mode=args.local_mode,
                           maximum_duration=args.max_duration, maximum_projects=args.max_projects,
                           maximum_job_seconds=args.maximum_job_seconds)
    internal = BoundedHTTPServer(("127.0.0.1", args.internal_port), InternalHandler, app)
    public = BoundedHTTPServer((args.host, args.port), GcubeHandler, app)
    thread = threading.Thread(target=internal.serve_forever, daemon=True, name="private-render-http")
    thread.start()
    app.scheduler.start()
    stopping = threading.Event()

    def stop(_signum, _frame):
        if not stopping.is_set():
            stopping.set()
            threading.Thread(target=public.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"World Engine gateway ready on port {args.port}; owner login is required.", flush=True)
    try:
        public.serve_forever()
    finally:
        app.scheduler.close()
        internal.shutdown()
        public.server_close()
        internal.server_close()
        thread.join(2)
        lease.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (SecurityError, EngineError) as error:
        print(f"World Engine startup blocked: {error.code}.", file=sys.stderr)
        sys.exit(2)
