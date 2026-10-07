"""Read-only port-8000 startup status while the real engine is unavailable.

The entrypoint owns this listener and its foreground lifetime. It must close the
listener before starting the owner-authenticated engine on the same port. An
``ok`` liveness response is deliberately never an engine-readiness claim.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import json
import re
from socketserver import ThreadingMixIn
import threading


_OWNER = (
    "gcube 환경변수 WORLD_ENGINE_OWNER_CODE에 앞뒤 공백 없는 16자 이상의 "
    "로그인 코드를 입력하세요. 기존 저장소는 이전과 같은 코드를 사용하세요."
)
_STORAGE = (
    "gcube Personal Storage를 /world-storage에 연결하세요. 첫 테스트에서만 "
    "WORLD_ENGINE_STORAGE_MODE=ephemeral을 명시할 수 있으며, 이 경우 종료하면 "
    "결과가 사라질 수 있습니다. 기존 자료를 삭제하거나 권한을 바꾸지 마세요."
)
_GPU = (
    "NVIDIA GPU와 그래픽 드라이버 전달을 확인하세요. GPU 검증을 통과하지 않아 "
    "렌더를 시작하지 않았습니다. CPU로 자동 전환하지 않습니다. gcube Workload를 중지하세요."
)
_RUNTIME = "필수 실행환경을 확인할 수 없습니다. 새 배포 이미지와 설정을 확인하세요."
_MESSAGES = {
    "STARTUP_BLOCKED": "초기화가 중단되었습니다. 배포 설정과 gcube 컨테이너 로그의 오류 코드를 확인하세요.",
    "WORLD_ENGINE_OWNER_CODE_REQUIRED": _OWNER,
    "STORAGE_OWNER_CODE_INVALID": _OWNER,
    "STORAGE_OWNER_CODE_MISMATCH": _OWNER,
    "STORAGE_MOUNT_REQUIRED": _STORAGE,
    "STORAGE_MODE": _STORAGE,
    "STORAGE_UNSAFE_PATH": _STORAGE,
    "STORAGE_OWNERSHIP": _STORAGE,
    "STORAGE_UNSAFE_FILE": _STORAGE,
    "STORAGE_FOREIGN_ROOT": _STORAGE,
    "STORAGE_INITIALIZATION_RACE": _STORAGE,
    "STORAGE_UNSUPPORTED": _STORAGE,
    "STORAGE_PROBE_CHANGED": _STORAGE,
    "GPU_HARDWARE_UNAVAILABLE": _GPU,
    "GPU_WEBGL_UNVERIFIED": _GPU,
    "GPU_BROWSER_PROBE_FAILED": _GPU,
    "GPU_PROFILE_INVALID": _GPU,
    "GPU_BROWSER_UNAVAILABLE": _RUNTIME,
    "GPU_GRAPHICS_RUNTIME_PATH_UNSAFE": _RUNTIME,
    "GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE": _RUNTIME,
    "GPU_WRAPPER_NOT_EXECUTABLE": _RUNTIME,
    "CPU_FALLBACK_UNVERIFIED": _RUNTIME,
    "WORLD_ENGINE_BOOT_FAILED": _RUNTIME,
    "WORLD_ENGINE_SERVER_EXITED": _RUNTIME,
    "WORLD_ENGINE_PROCESS_EXITED": _RUNTIME,
    "RUNTIME_PREFLIGHT_FAILED": _RUNTIME,
    "CERTIFIED_SOURCE_MISMATCH": _RUNTIME,
    "MISSING_DEPENDENCY": _RUNTIME,
    "CERTIFICATE_INCOMPLETE": _RUNTIME,
    "ASSETS_INVALID": _RUNTIME,
    "IMAGE_LAYOUT_REQUIRED": _RUNTIME,
    "INVALID_WORLD_ENGINE_MAX_DURATION": "WORLD_ENGINE_MAX_DURATION은 5~180 사이의 정수여야 합니다.",
    "INVALID_WORLD_ENGINE_MAX_JOB_SECONDS": "WORLD_ENGINE_MAX_JOB_SECONDS는 60~14400 사이의 정수여야 합니다.",
    "INVALID_RENDER_PROFILE": _RUNTIME,
    "UNSAFE_IMAGE_AUDIO": _RUNTIME,
    "UNSAFE_PERSISTED_AUDIO": _STORAGE,
    "PERSISTED_AUDIO_CONFLICT": _STORAGE,
    "IMAGE_WRITABLE_PATH_CONFLICT": _RUNTIME,
    "IMAGE_WRITABLE_PATH_NOT_EMPTY": _RUNTIME,
    "UNSAFE_PERSISTED_CACHE": _STORAGE,
    "PERSISTED_CACHE_OWNERSHIP": _STORAGE,
    "IMAGE_AUDIO_SEED_CONFLICT": _RUNTIME,
}
KNOWN_ERROR_CODES = frozenset(_MESSAGES)
_SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,79}\Z")
_GPU_REASONS = {
    "DEVICE_NODES_ABSENT": "NVIDIA 장치가 컨테이너에 전달되지 않았습니다.",
    "NVIDIA_QUERY_FAILED": "nvidia-smi에서 NVIDIA 장치를 확인하지 못했습니다.",
    "NVIDIA_QUERY_TIMEOUT": "nvidia-smi 확인 시간이 초과되었습니다.",
    "CHROMIUM_START_FAILED": "Chromium을 시작하지 못했습니다.",
    "CHROMIUM_TIMEOUT": "Chromium 시작 시간이 초과되었습니다.",
    "CHROMIUM_EVALUATION_FAILED": "Chromium에서 WebGL 진단을 실행하지 못했습니다.",
    "PROBE_OUTPUT_INVALID": "GPU 진단 응답을 확인하지 못했습니다.",
    "DRIVER_GRAPHICS_MISSING": "NVIDIA GPU는 표시되지만 EGL/Vulkan 그래픽 드라이버 전달이 확인되지 않았습니다.",
    "WEBGL2_CONTEXT_UNAVAILABLE": "Chromium에서 WebGL2 context를 생성하지 못했습니다.",
    "DEBUG_RENDERER_UNAVAILABLE": "실제 WebGL renderer 정보를 확인하지 못했습니다.",
    "SOFTWARE_RENDERER_REJECTED": "소프트웨어 renderer가 감지되어 NVIDIA GPU 렌더를 차단했습니다.",
    "NVIDIA_RENDERER_MISSING": "WebGL renderer에서 NVIDIA GPU를 확인하지 못했습니다.",
    "NVIDIA_DEVICE_MISMATCH": "WebGL renderer와 전달된 NVIDIA GPU 모델이 일치하지 않습니다.",
    "WEBGL_DRAW_FAILED": "WebGL 테스트 frame의 실제 GPU 그리기 결과를 확인하지 못했습니다.",
    "GPU_PROBE_SHADER_FAILED": "GPU 검증용 WebGL shader를 생성하지 못했습니다.",
    "GPU_PROBE_PROGRAM_FAILED": "GPU 검증용 WebGL program을 연결하지 못했습니다.",
    "GPU_GRAPHICS_RUNTIME_PATH_UNSAFE": "NVIDIA 그래픽 초기화용 디렉터리의 안전성을 확인하지 못했습니다.",
    "GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE": "NVIDIA 그래픽 초기화용 디렉터리에 필요한 파일을 기록하지 못했습니다.",
}


def safe_error_code(value):
    """Return a fixed public identifier, never a raw exception or env value."""
    if isinstance(value, str) and _SAFE_CODE.fullmatch(value) and value in KNOWN_ERROR_CODES:
        return value
    return "STARTUP_BLOCKED"


def safe_gpu_diagnostics(value):
    """Share the probe's strict projection, never expose raw process output."""
    from deployment.gcube.gpu import sanitize_gpu_diagnostics
    return sanitize_gpu_diagnostics(value)


def gpu_diagnostic_html(diagnostic):
    """A static, mobile-sized view of observed GPU stages, with no scripts."""
    if not diagnostic:
        return ""
    escape = lambda value: html.escape(str(value), quote=True)
    stage_names = {"A": "NVIDIA 장치 전달", "B": "nvidia-smi", "C": "Chromium 실행",
                   "D": "WebGL context", "E": "실제 NVIDIA renderer", "F": "테스트 frame GPU render"}
    rows = []
    for stage in diagnostic.get("stages", []):
        ident = stage.get("id")
        if ident in stage_names:
            rows.append("<tr><th>" + ident + ". " + stage_names[ident] + "</th><td>" +
                        escape(stage.get("status", "NOT_RUN")) + "</td></tr>")
    devices = diagnostic.get("nvidia_devices", [])
    if devices:
        rows.append("<tr><th>GPU</th><td>" + escape(", ".join(device.get("name", "") for device in devices)) + "</td></tr>")
        rows.append("<tr><th>Driver</th><td>" + escape(", ".join(device.get("driver_version") or "확인하지 못함" for device in devices)) + "</td></tr>")
    if diagnostic.get("gpu_profile"):
        rows.append("<tr><th>Backend</th><td>" + escape(diagnostic["gpu_profile"]) + "</td></tr>")
    webgl = diagnostic.get("webgl", {})
    backend_results = {"egl": "NOT_RUN", "vulkan": "NOT_RUN"}
    for attempt in diagnostic.get("profile_attempts", []):
        backend = attempt.get("backend")
        observed = attempt.get("diagnostics", {})
        observed_gl = observed.get("webgl", {})
        stages = {stage.get("id"): stage.get("status") for stage in observed.get("stages", [])}
        if backend in backend_results and diagnostic.get("render_mode") == "gpu-required":
            passed = (attempt.get("status") == "verified" and stages.get("E") == "PASS" and stages.get("F") == "PASS"
                      and observed_gl.get("draw_passed") is True and observed_gl.get("software_renderer") is False)
            backend_results[backend] = "PASS" if passed else "FAIL"
    if (not diagnostic.get("profile_attempts") and diagnostic.get("gpu_profile") in backend_results
            and diagnostic.get("render_mode") == "gpu-required"):
        observed_stages = {stage.get("id"): stage.get("status") for stage in diagnostic.get("stages", [])}
        backend_results[diagnostic["gpu_profile"]] = ("PASS" if
            diagnostic.get("reason_code") == "VERIFIED" and webgl.get("draw_passed") is True
            and webgl.get("software_renderer") is False and observed_stages.get("E") == "PASS"
            and observed_stages.get("F") == "PASS" else "FAIL")
    for backend in ("egl", "vulkan"):
        rows.append("<tr><th>" + backend.upper() + " GPU backend</th><td>" + backend_results[backend] + "</td></tr>")
    context = webgl.get("context_available") is True
    stages = {stage.get("id"): stage.get("status") for stage in diagnostic.get("stages", [])}
    context_status = "PASS" if context else "NOT_RUN" if stages.get("D") == "NOT_RUN" else "FAIL"
    rows.append("<tr><th>WebGL context</th><td>" + context_status + "</td></tr>")
    rows.append("<tr><th>WebGL2 context</th><td>" + ("PASS" if context and webgl.get("webgl2") is True else context_status if not context else "FAIL") + "</td></tr>")
    renderer = webgl.get("unmasked_renderer") or webgl.get("renderer") or "확인하지 못함"
    vendor = webgl.get("unmasked_vendor") or webgl.get("vendor") or "확인하지 못함"
    rows.extend(("<tr><th>WebGL renderer</th><td>" + escape(renderer) + "</td></tr>",
                 "<tr><th>WebGL vendor</th><td>" + escape(vendor) + "</td></tr>",
                 "<tr><th>Software renderer</th><td>" +
                 ("YES · GPU 검증 실패" if webgl.get("software_renderer") is True else
                  "NO" if webgl.get("context_available") is True else "확인하지 못함") + "</td></tr>"))
    reason = diagnostic.get("reason_code")
    if reason:
        rows.append("<tr><th>진단 코드</th><td>" + escape(reason) + "</td></tr>")
    failed = diagnostic.get("failed_stage")
    detail = ("<p>실패 단계: " + escape(failed) + " · " + stage_names.get(failed, "확인 필요") + "</p>") if failed else ""
    if reason in _GPU_REASONS:
        detail += "<p>" + _GPU_REASONS[reason] + "</p>"
    runtime = diagnostic.get("runtime", {})
    delivery = runtime.get("driver_delivery", {})
    libraries = runtime.get("libraries", {})
    if delivery or libraries:
        rows.append("<tr><th>NVIDIA EGL / Vulkan 전달</th><td>" +
                    ("YES" if delivery.get("egl_vendor_manifest") is True else "NO") + " / " +
                    ("YES" if delivery.get("vulkan_nvidia_icd") is True else "NO") + "</td></tr>")
    # No third-party failure string is inserted into the page. Observed fixed
    # graphics-delivery facts provide useful guidance without exposing stderr.
    if failed in {"C", "D", "E", "F"} and libraries and not (
            libraries.get("nvidia_egl") is True or libraries.get("nvidia_vulkan") is True):
        detail += "<p>NVIDIA GPU는 표시되더라도 그래픽 드라이버 전달이 없으면 WebGL을 검증할 수 없습니다. gcube의 NVIDIA graphics runtime 전달을 확인해야 합니다.</p>"
        if any("T4" in device.get("name", "").split() for device in devices):
            detail += "<p>Tier1 T4에서도 NVIDIA graphics runtime 전달 실패</p>"
    elif failed:
        detail += "<p>위 단계에서 실제 GPU 렌더 증명을 완료하지 못했습니다. 표시된 진단 코드와 renderer를 확인하세요.</p>"
    attempts = diagnostic.get("profile_attempts", [])
    if attempts:
        detail += "<p>검증한 backend: " + escape(" → ".join(
            str(attempt.get("backend", "")) + " (" + str(attempt.get("status", "")) + ")"
            for attempt in attempts)) + "</p>"
        for attempt in attempts:
            observed = attempt.get("diagnostics", {})
            if not observed:
                continue
            actual = observed.get("webgl", {})
            identity = actual.get("unmasked_renderer") or actual.get("renderer") or "확인하지 못함"
            detail += ("<p class=code>" + escape(attempt.get("backend", "")) +
                       ": " + escape(observed.get("reason_code") or attempt.get("status", "")) +
                       " · renderer: " + escape(identity) + "</p>")
    return "<section aria-label='GPU 진단'><h2>GPU / WebGL 진단</h2>" + detail + "<table>" + "".join(rows) + "</table></section>"


def proxy_diagnostic_html(summary):
    """Only the strict parser's bounded allowlist; no raw request header dump."""
    if not summary or summary.get("status") != "PASS":
        return "<p>Proxy 진단: " + html.escape(str((summary or {}).get("error_code", "NOT_RUN"))) + "</p>"
    labels = {"normalized_host": "Normalized Host", "forwarded_host": "Forwarded Host",
              "forwarded_proto": "Forwarded Proto", "forwarded_port": "Forwarded Port",
              "xff_entry_count": "XFF entry count", "envoy_external_address_present": "Envoy external address present"}
    rows = ["<tr><th>" + label + "</th><td>" + html.escape(str(summary.get(key)), quote=True) + "</td></tr>"
            for key, label in labels.items()]
    return "<section><h2>Proxy 진단</h2><table>" + "".join(rows) + "</table></section>"


class _BoundedServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False
    request_queue_size = 32

    def __init__(self, address, owner):
        self.owner = owner
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(address, _Handler)

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(5)
        return request, address

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(
                    b"HTTP/1.0 503 Service Unavailable\r\nConnection: close\r\n"
                    b"Content-Length: 0\r\nCache-Control: no-store\r\n\r\n"
                )
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        # No traceback, headers, request body, or path can enter startup logs.
        pass


class _Handler(BaseHTTPRequestHandler):
    server_version = "WorldEngineBoot"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler normally reflects invalid verbs/version strings
        # into an HTML error page. Keep parser failures fixed and non-reflective.
        if code == 501:
            code = 405
        self.request_version = "HTTP/1.0"
        self._json(code, {"error": {"code": "ENGINE_NOT_READY"}, "engine_ready": False})

    def _reply(self, status, payload, content_type="application/json; charset=utf-8"):
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _json(self, status, record):
        self._reply(status, json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def _read_only(self):
        phase, code = self.server.owner.snapshot()
        diagnostic = self.server.owner.gpu_diagnostics
        from deployment.gcube.proxy import safe_proxy_summary
        proxy = safe_proxy_summary(self.headers, peer_ip=self.client_address[0]) if diagnostic else None
        # URLs and all reverse-proxy headers are deliberately not reflected.
        # This server has no authentication, state changes, assets, or engine API.
        path = self.path.partition("?")[0]
        if path in {"/api/health", "/healthz"}:
            record = {"ok": True, "authentication_required": True,
                      "engine_ready": False, "phase": phase, "error_code": code}
            if diagnostic:
                record["gpu_diagnostics"] = diagnostic
                record["proxy"] = proxy
            self._json(200, record)
        elif path == "/readyz":
            self._json(503, {"ok": False, "engine_ready": False, "phase": phase,
                             "error_code": code})
        elif path in {"/", "/auth/login"}:
            if phase == "blocked":
                title, description = "초기화가 중단되었습니다", _MESSAGES[code]
                detail = "<p class=code>오류 코드: " + code + "</p>"
                if diagnostic:
                    detail += gpu_diagnostic_html(diagnostic)
                    detail += proxy_diagnostic_html(proxy)
            else:
                title, description = "World Engine 준비 중", "저장소와 실행환경을 확인하고 있습니다. 아직 로그인과 영상 생성을 시작할 수 없습니다. 잠시 후 새로고침하세요."
                detail = ""
            page = (
                "<!doctype html><html lang=ko><meta charset=utf-8>"
                "<meta name=viewport content='width=device-width,initial-scale=1'>"
                "<title>World Engine 시작 상태</title><style>"
                "body{margin:0;background:#101722;color:#edf3fa;font:16px/1.6 sans-serif}"
                "main{max-width:36rem;padding:2rem 1.2rem;margin:auto}h1{font-size:1.5rem}"
                ".code{overflow-wrap:anywhere;font-family:monospace;color:#b7d9f1}"
                "h2{font-size:1.1rem}table{width:100%;border-collapse:collapse;font-size:.85rem}"
                "th,td{padding:.45rem .25rem;text-align:left;border-bottom:1px solid #344352;overflow-wrap:anywhere}th{width:48%}"
                "small{display:block;color:#b8c4d0;margin-top:2rem}</style>"
                "<main><h1>" + title + "</h1><p>" + description + "</p>" + detail +
                "<p>영상 생성 엔진: 아직 준비되지 않음</p>"
                "<small>gcube Workload 실행 중에는 유휴 상태도 과금될 수 있습니다. "
                "테스트를 마치거나 설정을 수정할 때 gcube에서 Workload를 중지하세요. "
                "브라우저를 닫는 것만으로 과금이 멈추지는 않습니다.</small></main></html>"
            )
            self._reply(200, page.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._json(503, {"error": {"code": "ENGINE_NOT_READY"}, "engine_ready": False})

    do_GET = _read_only
    do_HEAD = _read_only

    def _no_actions(self):
        # Never read, evaluate, log, or dispatch request bodies.
        self._json(405, {"error": {"code": "ENGINE_NOT_READY"}, "engine_ready": False})

    do_POST = _no_actions
    do_PUT = _no_actions
    do_PATCH = _no_actions
    do_DELETE = _no_actions
    do_OPTIONS = _no_actions
    do_TRACE = _no_actions
    do_CONNECT = _no_actions


class BootStatusServer:
    """Idempotent temporary listener, with explicit handoff to the real server."""

    def __init__(self, host="0.0.0.0", port=8000):
        self.host = host
        self.port = port
        self._requested_port = port
        self._phase = "checking"
        self._code = None
        self._gpu_diagnostics = None
        self._state_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._server = None
        self._thread = None

    @property
    def server_address(self):
        return self.host, self.port

    def snapshot(self):
        with self._state_lock:
            return self._phase, self._code

    @property
    def error_code(self):
        return self.snapshot()[1]

    @property
    def gpu_diagnostics(self):
        with self._state_lock:
            # This shape contains no secret/raw exception/env values; callers
            # receive a copy so a concurrent HTTP read cannot mutate our state.
            return json.loads(json.dumps(self._gpu_diagnostics)) if self._gpu_diagnostics else None

    def set_phase(self, phase, error_code=None, *, gpu_diagnostics=None):
        if phase not in {"checking", "blocked"}:
            raise ValueError("Invalid startup phase")
        with self._state_lock:
            self._phase = phase
            self._code = safe_error_code(error_code) if phase == "blocked" else None
            self._gpu_diagnostics = (safe_gpu_diagnostics(gpu_diagnostics)
                                     if phase == "blocked" and self._code.startswith("GPU_")
                                     and isinstance(gpu_diagnostics, dict) else None)

    def start(self):
        with self._lifecycle_lock:
            if self._server is not None:
                return self
            server = _BoundedServer((self.host, self._requested_port), self)
            self.port = server.server_port
            thread = threading.Thread(target=server.serve_forever,
                                      kwargs={"poll_interval": 0.1},
                                      name="gcube-boot-status", daemon=True)
            self._server, self._thread = server, thread
            thread.start()
        return self

    def close(self):
        with self._lifecycle_lock:
            server, thread = self._server, self._thread
            if server is None:
                return
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            self._server, self._thread = None, None

    stop_listener = close
