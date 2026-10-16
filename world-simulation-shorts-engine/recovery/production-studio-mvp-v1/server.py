#!/usr/bin/env python3
"""Owner-authenticated mobile studio, independent from the frozen health service.

The controller owns production admission and durable jobs. This HTTP adapter
never restores or starts a job on process startup or on a GET request.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import sys
import tempfile
import threading
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
SECURITY_SHA256 = '3f7ea527f7209e4d3effc22b9a7b935db2e9642f135d064ff6c701c12131f704'
security_path = HERE / 'dependencies' / 'security.py'
if security_path.is_symlink() or hashlib.sha256(security_path.read_bytes()).hexdigest() != SECURITY_SHA256:
    raise RuntimeError('STUDIO_FROZEN_SECURITY_CHANGED')
_spec = importlib.util.spec_from_file_location('_studio_mvp_frozen_security', security_path)
security = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(security)
SecurityError = security.SecurityError
MAX_BODY = 8 * 1024 * 1024
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
KEY = re.compile(r'[A-Za-z0-9_-]{16,128}')
HASH = re.compile(r'[a-f0-9]{64}')
ALLOWED_FILES = {'.mp4': 'video/mp4', '.wav': 'audio/wav'}


def _fail(code, status=400):
    raise SecurityError(code, '입력 또는 실행 설정을 확인해 주세요.', status)


@dataclass(frozen=True)
class StudioConfig:
    state_root: Path
    owner_file: Path
    public_origin: str
    export_root: Path
    host: str = '0.0.0.0'
    port: int = 8080
    local_test_only: bool = False

    def validate(self):
        parsed = urlsplit(self.public_origin or '')
        if not self.public_origin or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            _fail('STUDIO_EXPLICIT_ORIGIN_REQUIRED')
        if self.local_test_only:
            if self.host != '127.0.0.1' or parsed.hostname not in {'127.0.0.1', 'localhost'} or parsed.scheme != 'http':
                _fail('STUDIO_LOCAL_TEST_LOOPBACK_ONLY')
        elif parsed.scheme != 'https':
            _fail('STUDIO_HTTPS_REQUIRED')
        if type(self.port) is not int or not 1024 <= self.port <= 65535 or self.port == 8000:
            _fail('STUDIO_DISTINCT_PORT_REQUIRED')
        if not self.owner_file.is_file() or self.owner_file.is_symlink():
            _fail('STUDIO_OWNER_FILE_REQUIRED')
        root = self.state_root.absolute()
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            _fail('STUDIO_STATE_UNSAFE')
        if root.resolve().is_relative_to(self.export_root.resolve()):
            _fail('STUDIO_STATE_MUST_BE_PRIVATE')
        if root.exists() and (stat.S_IMODE(root.stat().st_mode) & 0o077 or root.stat().st_uid != os.getuid()):
            _fail('STUDIO_STATE_MUST_BE_PRIVATE')
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        return self


class StudioSessions(security.OwnerSessions):
    cookie_name = 'world_studio_session'


class StudioApplication:
    def __init__(self, config, controller):
        self.config = config.validate()
        self.controller = controller
        self.policy = security.RequestPolicy([config.public_origin], local_port=config.port, environ={})
        self.sessions = StudioSessions(config.owner_file, config.state_root / 'studio-auth.json')
        self.rate = security.RateLimiter()
        self.lock = threading.RLock()
        self.csrf = {}
        self.download_slot = threading.BoundedSemaphore(1)

    def token_csrf(self, token):
        claim = self.sessions.claims(token)
        if not claim:
            _fail('AUTH_REQUIRED', 401)
        with self.lock:
            active = self.sessions.record.get('sessions', {})
            self.csrf = {k: v for k, v in self.csrf.items() if k in active}
            return self.csrf.setdefault(claim['sid'], secrets.token_urlsafe(32))


def _json_object(raw):
    def no_duplicates(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                _fail('DUPLICATE_JSON_KEY')
            result[name] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=no_duplicates,
                           parse_constant=lambda _: _fail('NONFINITE_JSON'))
    except (ValueError, UnicodeError, RecursionError):
        _fail('INVALID_JSON')
    if not isinstance(value, dict):
        _fail('JSON_OBJECT_REQUIRED')
    return value


def _safe_public(value):
    """Only the controller's public contract; filesystem capability stays private."""
    if not isinstance(value, dict):
        _fail('STUDIO_CONTROLLER_RESULT_INVALID', 500)
    result = dict(value)
    downloads = result.get('downloads')
    if isinstance(downloads, list):
        result['downloads'] = [{k: row[k] for k in ('name', 'sha256', 'bytes') if k in row}
                               for row in downloads if isinstance(row, dict)]
    for name in ('path', 'absolutePath', 'approvalPath', 'privatePath', 'downloadRoot'):
        result.pop(name, None)
    return result


@contextmanager
def verified_download_snapshot(path, expected_hash, state_root):
    """Serve immutable private bytes rather than a mutable shared-store handle."""
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as source:
        before = os.fstat(source.fileno())
        bound = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > 5 * 1024**3 or (before.st_dev, before.st_ino) != (bound.st_dev, bound.st_ino):
            _fail('DOWNLOAD_NOT_ALLOWED', 404)
        if shutil.disk_usage(state_root).free < before.st_size + 512 * 1024**2:
            _fail('DOWNLOAD_PRIVATE_DISK_RESERVE', 507)
        with tempfile.TemporaryFile(mode='w+b', dir=state_root, prefix='verified-download-') as snapshot:
            digest = hashlib.sha256(); size = 0
            while chunk := source.read(64 * 1024):
                size += len(chunk)
                if size > before.st_size:
                    _fail('DOWNLOAD_SOURCE_CHANGED', 409)
                digest.update(chunk); snapshot.write(chunk)
            after = os.fstat(source.fileno()); rebound = path.lstat()
            identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
            if size != before.st_size or identity(before) != identity(after) or identity(after) != identity(rebound):
                _fail('DOWNLOAD_SOURCE_CHANGED', 409)
            if digest.hexdigest() != expected_hash:
                _fail('DOWNLOAD_SHA_MISMATCH', 409)
            snapshot.flush(); snapshot.seek(0)
            yield snapshot, size


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'WorldEngineStudio'
        sys_version = ''
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_):
            pass

        def _headers(self, status, content_type, length, extra=()):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(length))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
            if not app.config.local_test_only:
                self.send_header('Strict-Transport-Security', 'max-age=31536000')
            for key, value in extra:
                self.send_header(key, value)
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True

        def _send(self, status, body, content_type='application/json; charset=utf-8', extra=()):
            data = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode() if isinstance(body, dict) else body
            self._headers(status, content_type, len(data), extra)
            if self.command != 'HEAD':
                self.wfile.write(data)

        def _body(self, maximum=MAX_BODY):
            size = security.content_length(self.headers, maximum)
            if self.headers.get_content_type() != 'application/json':
                _fail('JSON_CONTENT_TYPE_REQUIRED', 415)
            raw = self.rfile.read(size)
            if len(raw) != size:
                _fail('INCOMPLETE_BODY')
            return _json_object(raw)

        def _token(self):
            try:
                values = SimpleCookie(self.headers.get('Cookie', ''))
                return values[app.sessions.cookie_name].value if app.sessions.cookie_name in values else None
            except Exception:
                return None

        def _cookie(self, token, logout=False):
            value = f'{app.sessions.cookie_name}={token or ""}; Path=/; Max-Age={0 if logout else app.sessions.lifetime}; HttpOnly; SameSite=Strict'
            if not app.config.local_test_only:
                value += '; Secure'
            return ('Set-Cookie', value)

        def _authenticate(self, mutation=False):
            token = self._token()
            if not app.sessions.claims(token):
                _fail('AUTH_REQUIRED', 401)
            if mutation:
                supplied = security.RequestPolicy._single_header(self.headers, 'X-Studio-CSRF')
                expected = app.token_csrf(token)
                if not isinstance(supplied, str) or not hmac.compare_digest(supplied, expected):
                    _fail('CSRF_REQUIRED', 403)
                if not app.rate.allow(('api', self.client_address[0]), count=30):
                    _fail('RATE_LIMIT', 429)
            return token

        def _download(self, job_id, name):
            if not app.download_slot.acquire(blocking=False):
                _fail('DOWNLOAD_BUSY', 429)
            try:
                return self._download_locked(job_id, name)
            finally:
                app.download_slot.release()

        def _download_locked(self, job_id, name):
            value = app.controller.result(job_id)
            rows = value.get('downloads', []) if isinstance(value, dict) else []
            matches = [r for r in rows if isinstance(r, dict) and r.get('name') == name]
            if len(matches) != 1 or not ID.fullmatch(name):
                _fail('DOWNLOAD_NOT_FOUND', 404)
            row = matches[0]
            suffix = Path(name).suffix.lower()
            mime = ALLOWED_FILES.get(suffix)
            if name == 'SHA256SUMS':
                mime = 'text/plain; charset=utf-8'
            elif name == 'QUALITY_SUMMARY.json':
                mime = 'application/json; charset=utf-8'
            if not mime or not HASH.fullmatch(str(row.get('sha256', ''))):
                _fail('DOWNLOAD_NOT_ALLOWED', 404)
            try:
                path = Path(row.get('path', ''))
                if not path.is_absolute() or path.name != name or path.is_symlink():
                    _fail('DOWNLOAD_NOT_ALLOWED', 404)
                resolved = security.owned_path(app.config.export_root, str(path.relative_to(app.config.export_root)))
                if not resolved.is_file() or resolved.stat().st_size > 5 * 1024**3:
                    _fail('DOWNLOAD_NOT_ALLOWED', 404)
                with verified_download_snapshot(resolved, row['sha256'], app.config.state_root) as (stream, size):
                    begin, end = 0, size - 1
                    requested = self.headers.get('Range')
                    if requested:
                        match = re.fullmatch(r'bytes=(\d+)-(\d*)', requested) if len(requested) <= 96 else None
                        if not match:
                            _fail('INVALID_RANGE', 416)
                        begin = int(match[1]); end = min(end, int(match[2])) if match[2] else end
                        if begin > end or begin >= size:
                            _fail('INVALID_RANGE', 416)
                    extra = [('Content-Disposition', f'attachment; filename="{name}"'), ('Accept-Ranges', 'bytes')]
                    if requested:
                        extra.append(('Content-Range', f'bytes {begin}-{end}/{size}'))
                    count = end - begin + 1
                    self._headers(206 if requested else 200, mime, count, extra)
                    stream.seek(begin)
                    while count > 0 and self.command != 'HEAD':
                        chunk = stream.read(min(count, 64 * 1024))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        count -= len(chunk)
            except (ValueError, OSError):
                _fail('DOWNLOAD_NOT_FOUND', 404)

        def _dispatch(self):
            target = urlsplit(self.path)
            if len(self.path) > 2048 or target.scheme or target.netloc or target.query or target.fragment:
                _fail('INVALID_TARGET')
            effective = app.policy.check_request(self.headers, method=self.command, peer_ip=self.client_address[0])
            if effective != app.config.public_origin:
                _fail('STUDIO_ORIGIN_MISMATCH', 403)
            path = unquote(target.path)
            if path == '/healthz' and self.command == 'GET':
                return self._send(200, {'service': 'WORLD_ENGINE_STUDIO_MVP', 'authenticationRequired': True, 'renderingVerified': False})
            if path in {'/login', '/login.js', '/style.css'} and self.command == 'GET':
                file = {'/login': 'login.html', '/login.js': 'login.js', '/style.css': 'style.css'}[path]
                mime = 'text/html; charset=utf-8' if file.endswith('.html') else 'text/javascript; charset=utf-8' if file.endswith('.js') else 'text/css; charset=utf-8'
                return self._send(200, (HERE / 'web' / file).read_bytes(), mime)
            if path == '/api/login' and self.command == 'POST':
                if not app.rate.allow(('login', self.client_address[0]), count=5):
                    _fail('LOGIN_RATE_LIMIT', 429)
                body = self._body(4096)
                if set(body) != {'password'}:
                    _fail('INVALID_LOGIN')
                token = app.sessions.login(body['password'])
                if not token:
                    _fail('LOGIN_FAILED', 401)
                return self._send(200, {'authenticated': True, 'csrf': app.token_csrf(token)}, extra=[self._cookie(token)])
            token = self._authenticate(self.command == 'POST')
            if path == '/api/session' and self.command == 'GET':
                return self._send(200, {'authenticated': True, 'csrf': app.token_csrf(token), 'gpuExecutionVerified': False, 'manualWorkloadStopRequired': True})
            if path == '/api/logout' and self.command == 'POST':
                self._body()
                app.sessions.logout(token)
                return self._send(200, {'authenticated': False}, extra=[self._cookie(None, True)])
            if self.command == 'GET' and path in {'/', '/app.js'}:
                file = 'index.html' if path == '/' else 'app.js'
                return self._send(200, (HERE / 'web' / file).read_bytes(), 'text/html; charset=utf-8' if path == '/' else 'text/javascript; charset=utf-8')
            if path == '/api/preflight' and self.command == 'POST':
                return self._send(200, _safe_public(app.controller.preflight(self._body())))
            if path == '/api/submissions' and self.command == 'POST':
                return self._send(201, _safe_public(app.controller.submit(self._body())))
            if path == '/api/start' and self.command == 'POST':
                body = self._body()
                if set(body) != {'submissionId', 'idempotencyKey', 'consent'} or not ID.fullmatch(str(body['submissionId'])) or not KEY.fullmatch(str(body['idempotencyKey'])) or body['consent'] is not True:
                    _fail('EXPLICIT_START_CONSENT_REQUIRED')
                return self._send(202, _safe_public(app.controller.start(body['submissionId'], body['idempotencyKey'], consent=True)))
            match = re.fullmatch(r'/api/jobs/([A-Za-z0-9][A-Za-z0-9_.-]{0,127})(?:/(result|revisions|downloads|resume)(?:/([^/]+))?)?', path)
            if match:
                job_id, action, name = match.groups()
                if self.command == 'GET' and action is None:
                    return self._send(200, _safe_public(app.controller.status(job_id)))
                if self.command == 'GET' and action == 'result' and name is None:
                    return self._send(200, _safe_public(app.controller.result(job_id)))
                if self.command == 'GET' and action == 'downloads' and name:
                    return self._download(job_id, name)
                if self.command == 'POST' and action == 'resume' and name is None:
                    body = self._body(4096)
                    if set(body) != {'idempotencyKey', 'consent'} or not KEY.fullmatch(str(body['idempotencyKey'])) or body['consent'] is not True:
                        _fail('EXPLICIT_RESUME_CONSENT_REQUIRED')
                    return self._send(202, _safe_public(app.controller.resume(job_id, body['idempotencyKey'], consent=True)))
                if self.command == 'POST' and action == 'revisions' and name is None:
                    body = self._body()
                    if set(body) - {'startSeconds', 'endSeconds', 'prompt', 'sfx'} or not {'startSeconds', 'endSeconds', 'prompt'} <= set(body):
                        _fail('REVISION_FIELDS_REQUIRED')
                    if any(type(body[k]) not in {int, float} or not math.isfinite(body[k]) for k in ('startSeconds', 'endSeconds')) or not 0 <= body['startSeconds'] < body['endSeconds'] or not isinstance(body['prompt'], str) or not 1 <= len(body['prompt']) <= 4000:
                        _fail('INVALID_REVISION')
                    return self._send(201, _safe_public(app.controller.revise(job_id, body)))
            _fail('NOT_FOUND', 404)

        def _handle(self):
            try:
                self._dispatch()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as exc:
                code = getattr(exc, 'code', 'STUDIO_REQUEST_FAILED')
                code = code if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{1,99}', code) else 'STUDIO_REQUEST_FAILED'
                status = getattr(exc, 'status', 400)
                status = status if type(status) is int and 400 <= status <= 599 else 400
                public_error = {'code': code}
                contracts = sys.modules.get('studio_contracts')
                contract_class = getattr(contracts, 'StudioContractError', None) if contracts else None
                if isinstance(contract_class, type) and type(exc) is contract_class:
                    message = getattr(exc, 'message', '')
                    if isinstance(message, str) and len(message) <= 1024 and not any(ord(c) < 32 and c not in '\n\t' for c in message):
                        public_error['message'] = message
                    fields = getattr(exc, 'fields', [])
                    if isinstance(fields, list):
                        public_error['fields'] = [field for field in fields[:16] if isinstance(field, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.\[\]-]{0,95}', field)]
                try:
                    self._send(status, {'error': public_error, 'renderAllowed': False})
                except (BrokenPipeError, ConnectionResetError):
                    pass

        do_GET = do_POST = _handle

        def do_HEAD(self):
            self._send(405, {'error': {'code': 'METHOD_NOT_ALLOWED'}})

        do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = do_CONNECT = do_HEAD

        def send_error(self, code, message=None, explain=None):
            self._send(code if type(code) is int and 400 <= code <= 599 else 400,
                       {'error': {'code': 'INVALID_HTTP_REQUEST'}, 'renderAllowed': False})

    return Handler


class StudioHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, *args, **kwargs):
        self._slots = threading.BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(15)
        return sock, address

    def handle_error(self, *_):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description='Independent authenticated Studio; no automatic render or GPU deployment.')
    parser.add_argument('--state-root', type=Path, default=Path('/var/lib/world-engine-private/engine/studio-mvp'))
    parser.add_argument('--owner-file', type=Path, default=os.environ.get('WORLD_ENGINE_STUDIO_OWNER_FILE'))
    parser.add_argument('--public-origin', default=os.environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'))
    parser.add_argument('--export-root', type=Path, default=Path('/world-storage'))
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--local-test-only', action='store_true')
    args = parser.parse_args(argv)
    if args.owner_file is None:
        _fail('STUDIO_OWNER_FILE_REQUIRED')
    config = StudioConfig(args.state_root, args.owner_file, args.public_origin, args.export_root, args.host, args.port, args.local_test_only)
    config.validate()
    # This factory is an explicit production bridge, never a fallback fake GPU.
    sys.path.insert(0, str(HERE))
    from studio_controller import StudioController
    image_digest = os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST')
    app = StudioApplication(config, StudioController(control_root=config.state_root / 'production',
        export_root=config.export_root, image_digest=image_digest))
    server = StudioHTTPServer((args.host, args.port), make_handler(app))
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        code = getattr(error, 'code', 'STUDIO_STARTUP_BLOCKED')
        code = code if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{1,99}', code) else 'STUDIO_STARTUP_BLOCKED'
        print(json.dumps({'state': 'BLOCKED', 'code': code, 'renderAllowed': False}), file=sys.stderr)
        raise SystemExit(2)
