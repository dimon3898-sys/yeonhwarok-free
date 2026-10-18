"""Focused HTTP boundary tests; injected controller is never a real GPU."""
import http.client
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from https_server import Application, original, security

ORIGIN = 'https://studio-test.invalid'


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'private'
        self.root.mkdir(mode=0o700)
        self.owner = self.root / 'owner-code'
        self.password = secrets.token_urlsafe(32)
        self.owner.write_text(self.password)
        self.owner.chmod(0o600)
        self.calls = []
        test = self
        class Controller:
            def __init__(self, **kwargs):
                test.calls.append('construct')
            def start(self, *args, **kwargs):
                test.calls.append('start')
                return {'state': 'TEST_ONLY', 'gpuRenderingVerified': False}
        self.factory = Controller
        self.app = Application(self.root, self.owner, Path(self.tmp.name) / 'exports',
            'sha256:' + 'a' * 64, controller_factory=Controller, gpu_check=lambda: False)
        self.server = original.StudioHTTPServer(('127.0.0.1', 0), self.app.handler())
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, method='GET', body=None, cookie='', csrf=None, host='studio-test.invalid', origin=ORIGIN, setup=False):
        conn = http.client.HTTPConnection('127.0.0.1', self.port)
        headers = {'Host': host, 'Origin': origin, 'Sec-Fetch-Site': 'same-origin'}
        if cookie:
            headers['Cookie'] = cookie
        if csrf:
            headers['X-Studio-Setup-CSRF' if setup else 'X-Studio-CSRF'] = csrf
        if body is not None:
            body = json.dumps(body)
            headers['Content-Type'] = 'application/json'
        conn.request(method, path, body, headers)
        response = conn.getresponse()
        data = response.read()
        try:
            value = json.loads(data)
        except ValueError:
            value = data
        cookies = []
        for key, raw in response.getheaders():
            if key.lower() == 'set-cookie':
                parsed = SimpleCookie(raw)
                cookies += [name + '=' + morsel.value for name, morsel in parsed.items()]
        result = response.status, value, '; '.join(cookies), response.getheaders()
        conn.close()
        return result

    def register(self):
        _, challenge, cookie, _ = self.request('/setup/challenge')
        status, login, cookie, headers = self.request('/api/setup/login', 'POST',
            {'password': self.password, 'origin': ORIGIN, 'challenge': challenge['challenge']},
            cookie, challenge['challenge'], setup=True)
        self.assertEqual(status, 200)
        self.assertNotIn('token', login)
        self.assertTrue(all('Secure' in value and 'HttpOnly' in value for key, value in headers if key == 'Set-Cookie'))
        result = self.request('/api/setup/origin', 'POST', {'origin': ORIGIN, 'confirm': True},
                              cookie, login['csrf'], setup=True)
        self.assertEqual(result[0], 200)
        self.assertFalse(result[1]['renderAllowed'])
        return cookie, login['csrf']

    def login(self):
        status, data, cookie, _ = self.request('/api/login', 'POST', {'password': self.password})
        self.assertEqual(status, 200)
        return cookie, data['csrf']

    def start(self, cookie, csrf):
        return self.request('/api/start', 'POST', {'submissionId': 'test-submission',
            'idempotencyKey': 'test-only-key-123456', 'consent': True}, cookie, csrf)

    def test_setup_does_not_construct_controller_and_public_start_blocked(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/healthz')[1]['mode'], 'SETUP')
        self.assertEqual(self.start('', '')[0], 503)
        self.assertEqual(self.calls, [])

    def test_registration_then_original_auth_csrf_host_origin(self):
        old_cookie, old_csrf = self.register()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.request('/api/session')[0], 401)
        cookie, csrf = self.login()
        self.assertEqual(self.request('/api/session', cookie=cookie)[0], 200)
        self.assertEqual(self.start(cookie, 'bad')[0], 403)
        self.assertGreaterEqual(self.request('/api/session', cookie=cookie, host='bad.invalid')[0], 400)
        self.assertGreaterEqual(self.request('/api/session', cookie=cookie, origin='https://bad.invalid')[0], 400)
        self.assertGreaterEqual(self.request('/api/setup/origin', 'POST', {'origin': ORIGIN, 'confirm': True}, old_cookie, old_csrf, setup=True)[0], 400)
        status, data, *_ = self.start(cookie, csrf)
        self.assertEqual(status, 503)
        self.assertEqual(data['error']['code'], 'STUDIO_PHYSICAL_GPU_HEALTH_REQUIRED')
        self.assertNotIn('start', self.calls)

    def test_bad_digest_web_alive_but_controller_never_created(self):
        self.register()
        self.app.image_digest = 'bad'
        cookie, csrf = self.login()
        self.assertEqual(self.start(cookie, csrf)[1]['error']['code'], 'STUDIO_IMAGE_DIGEST_REQUIRED')
        self.assertEqual(self.calls, [])

    def test_configuration_error_not_a_startup_crash(self):
        self.register()
        self.app.configuration_error = 'STUDIO_OPERATOR_POLICY_INVALID'
        cookie, csrf = self.login()
        self.assertEqual(self.start(cookie, csrf)[1]['error']['code'], 'STUDIO_OPERATOR_POLICY_INVALID')
        self.assertEqual(self.request('/healthz')[0], 200)
        self.assertEqual(self.calls, [])

    def test_only_explicit_start_after_valid_injected_gates_reaches_spy(self):
        self.register()
        cookie, csrf = self.login()
        self.app.controller.gpu_check = lambda: {'model': 'RTX 4080 SUPER',
            'verificationScope': 'STARTUP_HEALTH_NATIVE_ADMISSION_RECHECK_REQUIRED'}
        self.assertEqual(self.calls, [])
        self.assertEqual(self.start(cookie, csrf)[0], 202)
        self.assertEqual(self.calls, ['construct', 'start'])
        # This is an injected CPU spy, never evidence of actual NVIDIA admission.

    def test_origin_environment_conflict_preserves_private_origin_and_blocks_production(self):
        self.register()
        restarted = Application(self.root, self.owner, Path(self.tmp.name) / 'exports',
            'sha256:' + 'a' * 64, controller_factory=self.factory, gpu_check=lambda: False,
            initial_origin='https://stale-test.invalid')
        self.assertEqual(restarted.core.public_origin, ORIGIN)
        self.assertEqual(restarted.normal.config.public_origin, ORIGIN)
        self.assertEqual(restarted.configuration_error, 'STUDIO_CONFIGURED_ORIGIN_CONFLICT')
        with self.assertRaises(security.SecurityError) as caught:
            restarted.controller.start('test', 'test-only-key-123456', consent=True)
        self.assertEqual(caught.exception.code, 'STUDIO_CONFIGURED_ORIGIN_CONFLICT')
        self.assertEqual(self.calls, [])

    def test_unchanged_original_plan_image_binding_mismatch_is_rejected(self):
        from unittest.mock import patch
        import studio_runtime
        # Isolate the unchanged binding check, not source/GPU admission.
        with patch.object(studio_runtime, '_base'), patch.object(studio_runtime, '_validate_child'):
            with self.assertRaisesRegex(RuntimeError, 'STUDIO_PLAN_IMAGE_BINDING_MISMATCH'):
                studio_runtime.validate_render_plan({'renderProfile': {'imageDigest': 'sha256:' + 'b' * 64}},
                    'TEST_ONLY', 'sha256:' + 'a' * 64)

    def test_ui_font_is_static_and_original_css_rules_are_preserved(self):
        status, font, _, headers = self.request('/setup-font.woff2')
        self.assertEqual(status, 200)
        self.assertEqual(font[:4], b'wOF2')
        self.assertIn(('Content-Type', 'font/woff2'), headers)
        self.assertEqual(self.calls, [])
        self.register()
        status, css, *_ = self.request('/style.css')
        from frozen import load_originals
        self.assertEqual(status, 200)
        self.assertTrue(css.startswith((load_originals().root / 'web/style.css').read_bytes()))
        self.assertIn(b'WorldEngineStudioSetup', css)
        self.assertIn(b'/setup-font.woff2', css)
        self.assertEqual(self.calls, [])

    def test_registered_setup_page_requires_existing_authentication(self):
        self.register()
        self.assertEqual(self.request('/setup')[0], 401)
        cookie, _ = self.login()
        self.assertEqual(self.request('/setup', cookie=cookie)[0], 200)


if __name__ == '__main__':
    unittest.main()
