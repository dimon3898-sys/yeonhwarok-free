"""Bounded, unprivileged diagnostic liveness. Never exposes a rendering action."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import signal
import threading
import time

from records import emit_record, make_record, safe_record


class DiagnosticHTTPServer(HTTPServer):
    allow_reuse_address = True

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(1.0)
        return sock, address

    def handle_error(self, request, client_address):
        # Do not log request URLs, exception strings, client addresses or headers.
        pass


def diagnostic_handler(record):
    safe = safe_record(record)
    safe["startupMode"] = "diagnostic"

    class Handler(BaseHTTPRequestHandler):
        server_version = "WorldEngineDiagnostic"
        sys_version = ""

        def _reply(self, status, body):
            encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(encoded)
            self.close_connection = True

        def do_GET(self):
            if self.path == "/healthz":
                self._reply(200, {**safe, "diagnosticServiceAlive": True})
            elif self.path == "/readyz":
                self._reply(503, {**safe, "diagnosticServiceAlive": True, "ready": False})
            elif self.path == "/diagnostics":
                self._reply(200, safe)
            else:
                self._reply(404, {"error": "NOT_FOUND", "renderAllowed": False})

        def _deny(self):
            self._reply(405, {"error": "DIAGNOSTIC_READ_ONLY", "renderAllowed": False})

        do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = do_CONNECT = do_TRACE = _deny

        def log_message(self, *args):
            pass

        def send_error(self, code, message=None, explain=None):
            self._reply(code, {"error": "INVALID_REQUEST", "renderAllowed": False})

    return Handler


def serve_diagnostic(record, *, port=8000, host="0.0.0.0", max_seconds=900, server_factory=None):
    safe = safe_record(record)
    failure_exit = safe["exitCode"] or 2
    if (os.geteuid() != 1000 or os.getegid() != 1000 or os.getgroups()
            or isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535
            or host not in {"0.0.0.0", "127.0.0.1"}
            or isinstance(max_seconds, bool) or not isinstance(max_seconds, int) or not 1 <= max_seconds <= 900):
        emit_record(make_record("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_SERVICE_REFUSED", failure_exit, mode="diagnostic"))
        return failure_exit
    factory = DiagnosticHTTPServer if server_factory is None else server_factory
    stopped = threading.Event()
    old_handlers = {}
    server = None
    try:
        server = factory((host, port), diagnostic_handler(safe))
        server.timeout = min(0.25, max_seconds)
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGTERM, signal.SIGINT):
                old_handlers[signum] = signal.signal(signum, lambda *_: stopped.set())
        deadline = time.monotonic() + max_seconds
        while not stopped.is_set() and time.monotonic() < deadline:
            server.handle_request()
    except Exception:
        emit_record(make_record("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_SERVICE_FAILED", failure_exit, mode="diagnostic"))
    finally:
        if server is not None:
            try:
                server.server_close()
            except Exception:
                emit_record(make_record("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_SERVICE_FAILED", failure_exit, mode="diagnostic"))
        for signum, previous in old_handlers.items():
            signal.signal(signum, previous)
    return failure_exit
