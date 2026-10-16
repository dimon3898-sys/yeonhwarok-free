"""Real HTTP security tests with an injected CPU-only controller, never GPU proof."""
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile
import threading
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_studio_http_under_test', HERE / 'server.py')
studio = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = studio
spec.loader.exec_module(studio)


class FakeController:
    """Only this test harness injects fake production; executable server never does."""
    def __init__(self, export):
        self.calls, self.starts, self.export = [], {}, export

    def preflight(self, value):
        self.calls.append(('preflight', value))
        return {'valid': True, 'ready': True, 'checks': [{'name': 'CPU_TEST_ONLY', 'status': 'PASS'}],
                'budget': {'maxCost': 1, 'currency': 'TEST_NOT_BILLING', 'maxWallSeconds': 60, 'maxRetries': 0}}

    def submit(self, value):
        self.calls.append(('submit', value))
        return {'submissionId': 'submission_test', 'preflight': self.preflight(value)}

    def start(self, submission_id, idempotency_key, consent=False):
        self.calls.append(('start', submission_id, idempotency_key, consent))
        self.starts.setdefault(idempotency_key, {'jobId': 'job_test', 'state': 'queued'})
        return self.starts[idempotency_key]

    def status(self, job_id):
        self.calls.append(('status', job_id))
        return {'jobId': job_id, 'state': 'complete', 'processedFrames': 2400, 'elapsedSeconds': 3.5,
                'completedScenes': 12, 'totalScenes': 12, 'phase': 'GPU_RENDERING'}

    def revise(self, job_id, revision):
        self.calls.append(('revise', job_id, revision))
        return {'submissionId': 'revision_test', 'state': 'ready', 'affectedScenes': ['scene_04', 'scene_05'], 'preflight': self.preflight(revision)}

    def resume(self, job_id, key, consent=False):
        self.calls.append(('resume', job_id, key, consent))
        return {'jobId': 'job_retry', 'state': 'queued', 'parentJobId': job_id}

    def result(self, job_id):
        self.calls.append(('result', job_id))
        path = self.export / 'proof.mp4'
        return {'jobId': job_id, 'state': 'complete', 'downloads': [{'name': path.name, 'path': str(path),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}],
                'dropbox': {'mountReadbackVerified': True, 'externalDownloadVerified': False, 'relativeDirectory': 'CPU_UI_FIXTURE_NOT_DROPBOX'}}


class StudioHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='studio-http-test-')
        self.root = Path(self.tmp.name)
        self.export = self.root / 'export'; self.export.mkdir(mode=0o700)
        (self.export / 'proof.mp4').write_bytes(b'CPU_HTTP_TEST_FIXTURE_NOT_A_GPU_VIDEO')
        self.owner = self.root / 'owner'; self.password = secrets.token_urlsafe(32)
        self.owner.write_text(self.password); self.owner.chmod(0o600)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); self.port = sock.getsockname()[1]
        self.origin = f'http://127.0.0.1:{self.port}'
        self.config = studio.StudioConfig(self.root / 'state', self.owner, self.origin, self.export,
                                          '127.0.0.1', self.port, True)
        self.controller = FakeController(self.export)
        self.app = studio.StudioApplication(self.config, self.controller)
        self.http = studio.StudioHTTPServer(('127.0.0.1', self.port), studio.make_handler(self.app))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()
        self.cookie = self.csrf = None

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(2); self.tmp.cleanup()

    def call(self, path, body=None, *, method=None, headers=None, raw=None):
        method = method or ('POST' if body is not None or raw is not None else 'GET')
        payload = raw if raw is not None else json.dumps(body).encode() if body is not None else None
        request_headers = {'Host': f'127.0.0.1:{self.port}'}
        if payload is not None:
            request_headers.update({'Origin': self.origin, 'Content-Type': 'application/json'})
        if self.cookie:
            request_headers['Cookie'] = self.cookie
        if self.csrf:
            request_headers['X-Studio-CSRF'] = self.csrf
        request_headers.update(headers or {})
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        connection.request(method, path, payload, request_headers)
        response = connection.getresponse(); data = response.read(); status = response.status
        response_headers = dict(response.getheaders()); connection.close()
        try:
            value = json.loads(data)
        except ValueError:
            value = data
        return status, value, response_headers

    def login(self):
        status, record, headers = self.call('/api/login', {'password': self.password})
        self.assertEqual(status, 200)
        self.cookie = headers['Set-Cookie'].split(';', 1)[0]; self.csrf = record['csrf']
        return headers

    def test_public_readonly_health_does_not_start_job(self):
        status, record, _ = self.call('/healthz')
        self.assertEqual(status, 200); self.assertTrue(record['authenticationRequired'])
        self.assertFalse(record['renderingVerified']); self.assertEqual(self.controller.calls, [])

    def test_api_and_studio_page_require_owner_authentication(self):
        for path in ('/', '/app.js', '/api/session', '/api/jobs/job_test', '/api/jobs/job_test/result'):
            self.assertEqual(self.call(path)[0], 401)
        self.assertEqual(self.controller.calls, [])

    def test_session_and_cookies(self):
        headers = self.login()
        self.assertIn('HttpOnly', headers['Set-Cookie']); self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        self.assertNotIn('Secure', headers['Set-Cookie'])  # Explicit loopback-only test mode.
        status, record, _ = self.call('/api/session')
        self.assertEqual(status, 200); self.assertEqual(record['csrf'], self.csrf)
        self.assertFalse(record['gpuExecutionVerified'])

    def test_production_cookie_secure_and_https_origin_required(self):
        bad = studio.StudioConfig(self.root / 'bad', self.owner, self.origin, self.export, '0.0.0.0', self.port, False)
        with self.assertRaises(studio.SecurityError): bad.validate()
        production = studio.StudioConfig(self.root / 'production', self.owner, 'https://studio.example.test', self.export, '0.0.0.0', self.port, False)
        app = studio.StudioApplication(production, self.controller)
        handler = studio.make_handler(app)
        dummy = object.__new__(handler)
        self.assertIn('Secure', dummy._cookie('TEST_COOKIE_ONLY')[1])

    def test_cross_origin_and_csrf_fail_before_controller(self):
        self.login()
        self.assertEqual(self.call('/api/preflight', {}, headers={'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.call('/api/preflight', {}, headers={'X-Studio-CSRF': 'wrong'})[0], 403)
        self.assertEqual(self.call('/api/preflight', {}, headers={'Origin': 'null'})[0], 403)
        self.assertEqual(self.controller.calls, [])

    def test_wrong_host_and_forwarded_authority_are_rejected(self):
        self.login()
        self.assertEqual(self.call('/api/session', headers={'Host': 'evil.example'})[0], 400)
        self.assertEqual(self.call('/api/session', headers={'X-Forwarded-Host': 'evil.example', 'X-Forwarded-Proto': 'https'})[0], 400)

    def test_complete_submission_start_calls_existing_bridge_once_by_key(self):
        self.login(); value = {'prompt': 'structured', 'durationSeconds': 80, 'profile': 'V4_ARCHIVAL_80S', 'sfx': {'enabled': True, 'gain': .7}}
        self.assertEqual(self.call('/api/preflight', value)[0], 200)
        self.assertEqual(self.call('/api/submissions', value)[0], 201)
        body = {'submissionId': 'submission_test', 'idempotencyKey': secrets.token_hex(16), 'consent': True}
        first = self.call('/api/start', body); second = self.call('/api/start', body)
        self.assertEqual(first[0], 202); self.assertEqual(first[1], second[1]); self.assertEqual(len(self.controller.starts), 1)

    def test_missing_explicit_consent_blocks_start(self):
        self.login()
        body = {'submissionId': 'submission_test', 'idempotencyKey': secrets.token_hex(16), 'consent': False}
        self.assertEqual(self.call('/api/start', body)[0], 400); self.assertEqual(self.controller.starts, {})

    def test_explicit_authenticated_resume_is_never_a_get_or_automatic(self):
        self.assertEqual(self.call('/api/jobs/job_test/resume', {'idempotencyKey': secrets.token_hex(16), 'consent': True})[0], 401)
        self.login(); self.assertEqual(self.call('/api/jobs/job_test/resume')[0], 404)
        key = secrets.token_hex(16)
        self.assertEqual(self.call('/api/jobs/job_test/resume', {'idempotencyKey': key, 'consent': False})[0], 400)
        self.assertFalse(any(value[0] == 'resume' for value in self.controller.calls))
        status, record, _ = self.call('/api/jobs/job_test/resume', {'idempotencyKey': key, 'consent': True})
        self.assertEqual(status, 202); self.assertEqual(record['parentJobId'], 'job_test')
        self.assertIn(('resume', 'job_test', key, True), self.controller.calls)

    def test_invalid_json_duplicate_nonfinite_and_unknown_method(self):
        self.login()
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[]'):
            self.assertEqual(self.call('/api/preflight', raw=raw)[0], 400)
        self.assertEqual(self.call('/api/preflight', method='DELETE')[0], 405)

    def test_status_reconnection_never_submits_or_starts(self):
        self.login()
        for _ in range(3): self.assertEqual(self.call('/api/jobs/job_test')[0], 200)
        self.assertTrue(all(call[0] == 'status' for call in self.controller.calls))
        rebuilt = studio.StudioApplication(self.config, self.controller)
        self.assertIsNotNone(rebuilt.sessions.claims(self.cookie.split('=', 1)[1]))
        self.assertFalse(any(call[0] == 'start' for call in self.controller.calls))

    def test_revision_interval_and_request_are_forwarded_without_invention(self):
        self.login(); value = {'startSeconds': 25, 'endSeconds': 35, 'prompt': 'cameraZoom=1.1'}
        status, result, _ = self.call('/api/jobs/job_test/revisions', value)
        self.assertEqual(status, 201); self.assertEqual(result['submissionId'], 'revision_test')
        self.assertIn(('revise', 'job_test', value), self.controller.calls)
        value['endSeconds'] = 20
        self.assertEqual(self.call('/api/jobs/job_test/revisions', value)[0], 400)

    def test_result_never_exposes_download_path(self):
        self.login(); status, result, _ = self.call('/api/jobs/job_test/result')
        self.assertEqual(status, 200); self.assertNotIn('path', result['downloads'][0]); self.assertNotIn(str(self.root), json.dumps(result))
        self.assertFalse(result['dropbox']['externalDownloadVerified'])

    def test_download_authorization_sha_and_range(self):
        self.assertEqual(self.call('/api/jobs/job_test/downloads/proof.mp4')[0], 401)
        self.login(); expected = (self.export / 'proof.mp4').read_bytes()
        self.assertEqual(self.call('/api/jobs/job_test/downloads/proof.mp4')[1], expected)
        status, value, headers = self.call('/api/jobs/job_test/downloads/proof.mp4', headers={'Range': 'bytes=1-4'})
        self.assertEqual(status, 206); self.assertEqual(value, expected[1:5]); self.assertIn('Content-Range', headers)
        record = self.controller.result('job_test'); record['downloads'][0]['sha256'] = '0' * 64
        self.controller.result = lambda _: record
        self.assertEqual(self.call('/api/jobs/job_test/downloads/proof.mp4')[0], 409)

    def test_download_private_file_and_symlink_are_rejected(self):
        self.login(); record = self.controller.result('job_test')
        record['downloads'][0]['path'] = str(self.owner); self.controller.result = lambda _: record
        self.assertEqual(self.call('/api/jobs/job_test/downloads/proof.mp4')[0], 404)
        link = self.export / 'private.mp4'; link.symlink_to(self.owner)
        record['downloads'][0].update(name='private.mp4', path=str(link))
        self.assertEqual(self.call('/api/jobs/job_test/downloads/private.mp4')[0], 404)

    def test_shared_source_mutation_after_hash_never_changes_served_bytes(self):
        self.login()
        original = (self.export / 'proof.mp4').read_bytes()
        handler = self.http.RequestHandlerClass
        headers = handler._headers
        def mutate_after_verification(request, status, content_type, length, extra=()):
            if any(name == 'Content-Disposition' for name, _ in extra):
                (self.export / 'proof.mp4').write_bytes(b'ALTERED_SHARED_SOURCE_BYTES_AFTER_VERIFICATION')
            return headers(request, status, content_type, length, extra)
        handler._headers = mutate_after_verification
        try:
            status, content, _ = self.call('/api/jobs/job_test/downloads/proof.mp4')
        finally:
            handler._headers = headers
        self.assertEqual(status, 200)
        self.assertEqual(content, original)
        self.assertNotEqual((self.export / 'proof.mp4').read_bytes(), original)

    def test_no_png_or_internal_log_download(self):
        self.login()
        for name in ('FRAME.png', 'startup.log', 'SOURCE_MANIFEST.json'):
            path = self.export / name; path.write_bytes(b'private')
            record = {'downloads': [{'name': name, 'path': str(path), 'sha256': hashlib.sha256(b'private').hexdigest()}]}
            self.controller.result = lambda _, value=record: value
            self.assertEqual(self.call('/api/jobs/job_test/downloads/' + name)[0], 404)

    def test_restart_csrf_is_rotated_without_rendering(self):
        self.login(); old = self.csrf
        rebuilt = studio.StudioApplication(self.config, self.controller)
        fresh = rebuilt.token_csrf(self.cookie.split('=', 1)[1])
        self.assertNotEqual(old, fresh); self.assertEqual(self.controller.calls, [])

    def test_errors_do_not_echo_exception_secrets_or_paths(self):
        self.login()
        def bad(_): raise RuntimeError('DO_NOT_ECHO_PRIVATE_VALUE_OR_PATH')
        self.controller.preflight = bad
        status, result, _ = self.call('/api/preflight', {})
        self.assertEqual(status, 400); self.assertEqual(result['error']['code'], 'STUDIO_REQUEST_FAILED')
        self.assertNotIn('DO_NOT_ECHO', json.dumps(result))

    def test_authored_contract_error_exposes_only_safe_hint_and_fields(self):
        self.login()
        old_path = list(sys.path)
        try:
            sys.path.insert(0, str(HERE))
            import studio_contracts
            def missing(_):
                raise studio_contracts.StudioContractError('STUDIO_SCENE_REQUIRED',
                    'Scene JSON 또는 검증된 자료 프리셋이 필요합니다.', ['sceneJson', 'preset'])
            self.controller.preflight = missing
            status, result, _ = self.call('/api/preflight', {})
            self.assertEqual(status, 400)
            self.assertEqual(result['error']['fields'], ['sceneJson', 'preset'])
            self.assertIn('Scene JSON', result['error']['message'])
        finally:
            sys.path[:] = old_path

    def test_missing_owner_private_state_and_reserved_port_fail_closed(self):
        for config in (
            studio.StudioConfig(self.root/'a', self.root/'absent', self.origin, self.export, '127.0.0.1', self.port, True),
            studio.StudioConfig(self.export/'private', self.owner, self.origin, self.export, '127.0.0.1', self.port, True),
            studio.StudioConfig(self.root/'b', self.owner, self.origin, self.export, '127.0.0.1', 8000, True),
        ):
            with self.assertRaises(studio.SecurityError): config.validate()


if __name__ == '__main__': unittest.main()
