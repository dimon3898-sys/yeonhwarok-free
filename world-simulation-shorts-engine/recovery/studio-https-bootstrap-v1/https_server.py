#!/usr/bin/env python3
"""Authenticated HTTPS setup followed by the unchanged Studio application.

Only setup/health routing is new. Production authentication, CSRF, controller,
rendering, budget enforcement, claims, assets, SFX and export stay frozen.
"""
from __future__ import annotations
import argparse
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit
from frozen import load_originals
from setup_core import SetupCore, TTL

HERE = Path(__file__).resolve().parent
original = load_originals().server
security = original.security
CHALLENGE_COOKIE = '__Host-world_studio_setup_challenge'
DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')


def fail(code, status=409):
    raise security.SecurityError(code, '설정과 운영 정책을 확인해 주세요. 영상 제작은 시작되지 않았습니다.', status)


def production_controller(**kwargs):
    from studio_controller import StudioController
    return StudioController(**kwargs)


def physical_gpu_check():
    # Reuse the existing strict physical NVIDIA, model and gpu-required check.
    from studio_runtime import _health
    return _health()


class GateController:
    """Lazy frozen coordinator: setup cannot construct or start a GPU job."""
    def __init__(self, app, factory, gpu_check):
        self.app, self.factory, self.gpu_check = app, factory, gpu_check
        self.value = None

    def _controller(self):
        if not self.app.core.public_origin:
            fail('STUDIO_HTTPS_SETUP_REQUIRED', 503)
        if not isinstance(self.app.image_digest, str) or not DIGEST.fullmatch(self.app.image_digest):
            fail('STUDIO_IMAGE_DIGEST_REQUIRED', 503)
        if self.value is None:
            self.value = self.factory(control_root=self.app.state_root / 'production',
                                      export_root=self.app.export_root, image_digest=self.app.image_digest)
        return self.value

    def _render_controller(self):
        if self.app.configuration_error:
            fail(self.app.configuration_error, 503)
        controller = self._controller()
        try:
            report = self.gpu_check()
            if (not isinstance(report, dict) or report.get('model') not in {'RTX 4080 SUPER', 'RTX 4090', 'RTX 5090'}
                    or report.get('verificationScope') != 'STARTUP_HEALTH_NATIVE_ADMISSION_RECHECK_REQUIRED'):
                fail('STUDIO_PHYSICAL_GPU_HEALTH_REQUIRED', 503)
        except Exception as error:
            code = getattr(error, 'code', None) or str(error)
            if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
                code = 'STUDIO_PHYSICAL_GPU_HEALTH_REQUIRED'
            fail(code, 503)
        # The unchanged controller then enforces private operator policy,
        # expiry, real rate/cost/time/retry bounds and explicit consent.
        return controller

    def preflight(self, *args, **kwargs):
        if self.app.configuration_error:
            fail(self.app.configuration_error, 503)
        return self._controller().preflight(*args, **kwargs)

    def start(self, *args, **kwargs):
        return self._render_controller().start(*args, **kwargs)

    def resume(self, *args, **kwargs):
        return self._render_controller().resume(*args, **kwargs)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(self._controller(), name)


class _ApplicationProxy:
    def __init__(self, owner):
        self.owner = owner

    def __getattr__(self, key):
        if self.owner.normal is None:
            if key == 'config':
                return SimpleNamespace(local_test_only=False)
            fail('STUDIO_HTTPS_SETUP_REQUIRED', 503)
        return getattr(self.owner.normal, key)


class Application:
    def __init__(self, state_root, owner_file, export_root, image_digest, port=8080,
                 controller_factory=None, gpu_check=None, configuration_error=None,
                 initial_origin=None):
        self.state_root, self.export_root = Path(state_root), Path(export_root)
        if self.state_root.resolve().is_relative_to(self.export_root.resolve()):
            fail('STUDIO_STATE_MUST_BE_PRIVATE')
        self.image_digest, self.port = image_digest, port
        if configuration_error and not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', str(configuration_error)):
            fail('STUDIO_CONFIGURATION_INVALID')
        self.configuration_error = configuration_error
        self.core = SetupCore(self.state_root, Path(owner_file), port=port)
        try:
            self.core.configure_from_environment(initial_origin)
        except security.SecurityError as error:
            if getattr(error, 'code', None) != 'STUDIO_CONFIGURED_ORIGIN_CONFLICT' or not self.core.public_origin:
                raise
            # Preserve both settings. A confirmed private origin remains the
            # fixed request authority; mismatched environment blocks production
            # without restarting the web service or trusting a request header.
            self.configuration_error = 'STUDIO_CONFIGURED_ORIGIN_CONFLICT'
        self.normal = None
        self.controller = GateController(self, controller_factory or production_controller,
                                         gpu_check or physical_gpu_check)
        self._sync_normal()

    def _sync_normal(self):
        origin = self.core.public_origin
        if origin is None:
            self.normal = None
        elif self.normal is None or self.normal.config.public_origin != origin:
            config = original.StudioConfig(self.state_root, self.core.owner_file, origin,
                                            self.export_root, port=self.port)
            self.normal = original.StudioApplication(config, self.controller)
            self.core.bind_production_sessions(self.normal.sessions)

    def handler(self):
        app = self
        frozen_handler = original.make_handler(_ApplicationProxy(self))

        class Handler(frozen_handler):
            def _setup_cookie(self, name, token, ttl=TTL):
                return ('Set-Cookie', f'{name}={token}; Path=/; Max-Age={ttl}; Secure; HttpOnly; SameSite=Strict')

            def _setup_token(self, name):
                # Duplicate Cookie headers or cookie names are not accepted.
                values = self.headers.get_all('Cookie', [])
                if len(values) > 1:
                    fail('STUDIO_SETUP_COOKIE_INVALID', 403)
                raw = values[0] if values else ''
                if sum(part.strip().split('=', 1)[0] == name for part in raw.split(';')) > 1:
                    fail('STUDIO_SETUP_COOKIE_INVALID', 403)
                try:
                    parsed = SimpleCookie(raw)
                    return parsed[name].value if name in parsed else None
                except Exception:
                    fail('STUDIO_SETUP_COOKIE_INVALID', 403)

            def _configured_policy(self):
                effective = app.normal.policy.check_request(self.headers, method=self.command,
                                                             peer_ip=self.client_address[0])
                if effective != app.normal.config.public_origin:
                    fail('STUDIO_ORIGIN_MISMATCH', 403)

            def _body(self, maximum=original.MAX_BODY):
                cached = getattr(self, '_parsed_body', None)
                if cached is not None:
                    if cached[0] > maximum:
                        fail('REQUEST_BODY_TOO_LARGE', 413)
                    return cached[1]
                size = security.content_length(self.headers, maximum)
                value = super()._body(maximum)
                self._parsed_body = (size, value)
                return value

            def _dispatch(self):
                target = urlsplit(self.path)
                if len(self.path) > 2048 or target.scheme or target.netloc or target.query or target.fragment:
                    fail('INVALID_TARGET', 400)
                path = unquote(target.path)
                # A slow unauthenticated body must not hold the configuration
                # lock or prevent health probes from observing a live service.
                if path == '/healthz' and self.command == 'GET':
                    return self._send(200, {'service': 'WORLD_ENGINE_STUDIO_HTTPS_BOOTSTRAP',
                        'serviceAlive': True, 'mode': 'CONFIGURED' if app.normal else 'SETUP',
                        'renderAllowed': False, 'gpuRenderingVerified': False})
                if self.command == 'POST':
                    self._body(4096 if path.startswith('/api/setup/') else original.MAX_BODY)
                # Registration and production requests still serialize after
                # bounded input has arrived; no old-origin Start can race a change.
                with app.core.lock:
                    if path == '/setup-font.woff2' and self.command == 'GET':
                        if app.normal is not None:
                            self._configured_policy()
                        return self._send(200, (HERE / 'web/fonts/studio-setup-ko.woff2').read_bytes(), 'font/woff2')
                    if path == '/style.css' and self.command == 'GET' and app.normal is not None:
                        self._configured_policy()
                        # Preserve every original layout/style rule; add only a
                        # UI-local missing-Hangul fallback, never a video font.
                        base = (load_originals().root / 'web/style.css').read_bytes()
                        fallback = (HERE / 'web/studio-font.css').read_bytes()
                        return self._send(200, base + b'\n' + fallback, 'text/css; charset=utf-8')
                    setup_path = path in {'/setup', '/setup.js', '/setup.css', '/setup/challenge',
                                          '/api/setup/login', '/api/setup/origin'}
                    if app.normal is not None and setup_path:
                        self._configured_policy()
                        if self.command == 'GET':
                            self._authenticate(False)
                    if self.command == 'GET' and (path in {'/setup', '/setup.js', '/setup.css'}
                            or (app.normal is None and path in {'/', '/login'})):
                        name = 'setup.js' if path.endswith('.js') else 'setup.css' if path.endswith('.css') else 'setup.html'
                        mime = 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8' if name.endswith('.css') else 'text/html; charset=utf-8'
                        return self._send(200, (HERE / 'web' / name).read_bytes(), mime)
                    if path == '/setup/challenge' and self.command == 'GET':
                        # A public random nonce is not a settings read/mutation.
                        # Foreign fetches cannot provision a browser challenge.
                        site = security.RequestPolicy._single_header(self.headers, 'Sec-Fetch-Site')
                        if site not in {'same-origin', 'none'}:
                            fail('STUDIO_SETUP_SAME_ORIGIN_REQUIRED', 403)
                        if not app.core.rate.allow(('challenge', self.client_address[0]), count=20):
                            fail('STUDIO_SETUP_BUSY', 429)
                        cookie, csrf = app.core.challenge()
                        return self._send(200, {'challenge': csrf, 'renderAllowed': False},
                                          extra=[self._setup_cookie(CHALLENGE_COOKIE, cookie)])
                    if path == '/api/setup/login' and self.command == 'POST':
                        body = self._body(4096)
                        if set(body) != {'password', 'origin', 'challenge'}:
                            fail('STUDIO_SETUP_FIELDS_REQUIRED', 400)
                        csrf = security.RequestPolicy._single_header(self.headers, 'X-Studio-Setup-CSRF')
                        if csrf != body['challenge']:
                            fail('STUDIO_SETUP_CHALLENGE_REQUIRED', 403)
                        value = app.core.begin(self.headers, self.client_address[0], body['password'],
                            body['origin'], self._setup_token(CHALLENGE_COOKIE), csrf)
                        token = value.pop('token')
                        return self._send(200, {**value, 'authenticated': True, 'renderAllowed': False},
                            extra=[self._setup_cookie(app.core.sessions.cookie_name, token, 600),
                                   self._setup_cookie(CHALLENGE_COOKIE, '', 0)])
                    if path == '/api/setup/origin' and self.command == 'POST':
                        body = self._body(4096)
                        if set(body) != {'origin', 'confirm'}:
                            fail('STUDIO_SETUP_FIELDS_REQUIRED', 400)
                        csrf = security.RequestPolicy._single_header(self.headers, 'X-Studio-Setup-CSRF')
                        value = app.core.commit(self.headers, self.client_address[0],
                            self._setup_token(app.core.sessions.cookie_name), csrf, body['origin'], body['confirm'])
                        app._sync_normal()
                        return self._send(200, value, extra=[
                            self._setup_cookie(app.core.sessions.cookie_name, '', 0),
                            self._setup_cookie(CHALLENGE_COOKIE, '', 0),
                            ('Set-Cookie', 'world_studio_session=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict')])
                    if app.normal is None:
                        fail('STUDIO_HTTPS_SETUP_REQUIRED', 503)
                    return super()._dispatch()

        return Handler


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-root', required=True, type=Path)
    parser.add_argument('--owner-file', required=True, type=Path)
    parser.add_argument('--export-root', type=Path, default=Path('/world-storage'))
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', default=8080, type=int)
    args = parser.parse_args(argv)
    # Production startup is never a fixture bypass. Both source trees checked.
    import manifest
    manifest.verify_sources()
    app = Application(args.state_root, args.owner_file, args.export_root,
        os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'), args.port,
        initial_origin=os.environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'),
        configuration_error=os.environ.get('WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR'))
    server = original.StudioHTTPServer((args.host, args.port), app.handler())
    print(json.dumps({'stage': 'STUDIO_WEB_STARTED', 'mode': 'CONFIGURED' if app.normal else 'SETUP',
                      'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        code = getattr(error, 'code', None) or str(error)
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'STUDIO_HTTPS_SERVER_FAILED'
        print(json.dumps({'stage': 'STUDIO_WEB_FAILED', 'errorCode': code,
                          'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
        raise SystemExit(1)
