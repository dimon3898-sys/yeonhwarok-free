"""Deployment security checks with synthetic files and local HTTP; no rendering."""
from email.message import Message
import http.client
import io
import json
from pathlib import Path
import stat
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from deployment.security import OwnerSessions, RateLimiter, RequestPolicy, SecurityError, content_length, ensure_access_file, owned_path
from deployment.mobile_server import BoundedHTTPServer, InternalHandler, MobileApplication, MobileHandler, checked_state_root

FIXTURE_CODE = 'controlled-test-owner-password-2026'


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.access = self.root / 'owner.txt'
        self.access.write_text(FIXTURE_CODE)
        self.access.chmod(0o600)

    def tearDown(self):
        self.temp.cleanup()

    def test_secret_setup_never_returns_code(self):
        result = ensure_access_file(self.root / 'new.txt')
        self.assertEqual(set(result), {'path', 'created'})
        self.assertEqual(stat.S_IMODE(Path(result['path']).stat().st_mode), 0o600)
        self.assertFalse(ensure_access_file(self.root / 'new.txt')['created'])

    def test_scrypt_hmac_expiry_logout_and_restart(self):
        clock = [1000]
        state = self.root / 'auth.json'
        auth = OwnerSessions(self.access, state, lifetime=20, clock=lambda: clock[0])
        self.assertIsNone(auth.login('wrong'))
        token = auth.login(FIXTURE_CODE)
        self.assertTrue(auth.claims(token))
        forged = token[:-1] + ('0' if token[-1] != '0' else '1')
        self.assertIsNone(auth.claims(forged))
        self.assertTrue(OwnerSessions(self.access, state, clock=lambda: clock[0]).claims(token))
        clock[0] += 21
        self.assertIsNone(auth.claims(token))
        token = auth.login(FIXTURE_CODE)
        auth.logout(token)
        self.assertIsNone(auth.claims(token))
        self.assertNotIn(FIXTURE_CODE, state.read_text())
        self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o600)

    def test_private_access_and_json_fixture(self):
        self.access.write_text(json.dumps({'password': FIXTURE_CODE}))
        self.assertTrue(OwnerSessions(self.access, self.root / 'auth.json').login(FIXTURE_CODE))
        self.access.chmod(0o644)
        with self.assertRaises(SecurityError):
            ensure_access_file(self.access)
        self.access.chmod(0o600)
        link = self.root / 'link'
        link.symlink_to(self.access)
        with self.assertRaises(SecurityError):
            ensure_access_file(link)

    def test_negative_duplicate_chunked_missing_or_large_body_rejected(self):
        for values, transfer in [(['-1'], None), (['0'], None), (['65'], None), (['2', '2'], None), (['2'], 'chunked'), ([], None)]:
            headers = Message()
            for value in values:
                headers['Content-Length'] = value
            if transfer:
                headers['Transfer-Encoding'] = transfer
            with self.assertRaises(SecurityError):
                content_length(headers, 64)

    def test_origin_and_host_have_no_loopback_auth_bypass(self):
        policy = RequestPolicy(['https://example.test'], local_port=7860)
        policy.check_origin('https://example.test', '127.0.0.1:7860')
        for origin in [None, 'null', 'https://evil.test']:
            with self.assertRaises(SecurityError):
                policy.check_origin(origin, '127.0.0.1:7860')
        with self.assertRaises(SecurityError):
            policy.check_host('evil.test')
        self.assertTrue(policy.secure_cookie)

    def test_rate_budget_and_file_traversal_symlink(self):
        clock = [0]
        rate = RateLimiter(clock=lambda: clock[0], maximum_keys=2)
        self.assertTrue(rate.allow('a', count=1))
        self.assertFalse(rate.allow('a', count=1))
        self.assertTrue(rate.allow('b', count=1))
        self.assertFalse(rate.allow('c', count=1))
        clock[0] = 61
        self.assertTrue(rate.allow('a', count=1))
        (self.root / 'good.mp4').write_bytes(b'fixture')
        self.assertEqual(owned_path(self.root, 'good.mp4'), self.root / 'good.mp4')
        for value in ['../outside', '/etc/test', '.private']:
            with self.assertRaises(SecurityError):
                owned_path(self.root, value)
        (self.root / 'symbol').symlink_to(self.root / 'good.mp4')
        with self.assertRaises(SecurityError):
            owned_path(self.root, 'symbol')

    def test_existing_engine_and_project_trees_never_selected_as_state(self):
        from deployment.mobile_server import APP_ROOT
        for value in [APP_ROOT, APP_ROOT / 'projects', APP_ROOT / 'cache', APP_ROOT.parent / 'deliverables']:
            with self.assertRaises(SecurityError):
                checked_state_root(value)


class MobileHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        access = root / 'owner.txt'
        access.write_text(FIXTURE_CODE)
        access.chmod(0o600)
        self.app = MobileApplication(root / 'runtime', 'http://127.0.0.1:1', access, disk_floor=0)
        self.server = BoundedHTTPServer(('127.0.0.1', 0), MobileHandler, self.app)
        self.port = self.server.server_port
        self.origin = f'http://127.0.0.1:{self.port}'
        self.app.policy = RequestPolicy(local_port=self.port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = None

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.temp.cleanup()

    def call(self, method, path, body=None, *, origin=True, extra=None):
        headers = dict(extra or {})
        if method == 'POST' and origin:
            headers['Origin'] = self.origin if origin is True else origin
        if self.cookie:
            headers['Cookie'] = self.cookie
        if isinstance(body, dict):
            body = json.dumps(body)
            headers['Content-Type'] = 'application/json'
        client = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        client.request(method, path, body, headers)
        response = client.getresponse()
        value = response.status, dict(response.getheaders()), response.read()
        client.close()
        return value

    def login(self):
        status, headers, _ = self.call('POST', '/auth/login', {'password': FIXTURE_CODE})
        self.assertEqual(status, 200)
        self.cookie = headers['Set-Cookie'].split(';')[0]

    def test_public_health_unauthorized_api_media_and_page_redirect(self):
        self.assertEqual(self.call('GET', '/api/health')[0], 200)
        for path in ['/api/projects', '/download/project_abcdef/v001/final/final.mp4', '/media/project_abcdef/v001/final/final.mp4']:
            self.assertEqual(self.call('GET', path)[0], 401)
        self.assertEqual(self.call('GET', '/')[0], 303)

    def test_origin_auth_session_logout_even_from_loopback(self):
        for origin in [False, 'https://evil.test']:
            self.assertEqual(self.call('POST', '/api/projects', {}, origin=origin)[0], 403)
        self.login()
        self.assertEqual(json.loads(self.call('GET', '/auth/session')[2]), {'authenticated': True})
        self.assertEqual(self.call('GET', '/api/projects')[0], 200)
        self.assertEqual(self.call('GET', '/render_rhythm_flat.html')[0], 404)
        self.call('POST', '/auth/logout', {})
        self.assertEqual(self.call('GET', '/api/projects')[0], 401)

    def test_form_login_selectors_cookie_and_http_headers(self):
        self.assertIn(b'id="owner-password"', self.call('GET', '/auth/login')[2])
        status, headers, _ = self.call('POST', '/auth/login', urlencode({'password': FIXTURE_CODE}), extra={'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(status, 303)
        self.assertEqual(headers['Location'], '/')
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        self.assertIn('frame-ancestors', headers['Content-Security-Policy'])
        self.assertEqual(headers['Referrer-Policy'], 'same-origin')

    def test_unknown_fields_duration_raw_asset_rejected(self):
        self.login()
        for value in [dict(topic='서울에서 도쿄', duration=3600), dict(topic='a', command='test'), dict(topic='a', narration_audio='/etc/test')]:
            self.assertEqual(self.call('POST', '/api/projects', value)[0], 400)
        self.assertEqual(self.app.validate_request({'topic': '서울에서 도쿄', 'pace': 'FAST_PLUS'})['pace'], 'FAST_PLUS')

    def test_download_allowlist_range_and_private_metadata_denied(self):
        self.login()
        version = Path(self.temp.name) / 'version'
        (version / 'final').mkdir(parents=True)
        (version / 'final/final.mp4').write_bytes(b'0123456789')
        (version / 'private.json').write_text('{}')
        with patch.object(self.app.store, 'version_path', return_value=version), patch.object(self.app, 'outputs', return_value=[{'path': 'final/final.mp4'}]):
            status, headers, data = self.call('GET', '/media/project_abcdef/v001/final/final.mp4', extra={'Range': 'bytes=2-5'})
            self.assertEqual((status, data), (206, b'2345'))
            self.assertEqual(headers['Content-Range'], 'bytes 2-5/10')
            self.assertEqual(self.call('GET', '/download/project_abcdef/v001/private.json')[0], 404)
            self.assertEqual(self.call('GET', '/download/project_abcdef/v001/../private.json')[0], 404)

    def test_private_listener_get_only_and_scoped(self):
        server = BoundedHTTPServer(('127.0.0.1', 0), InternalHandler, self.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for method, path, expected in [('GET', '/api/projects', 403), ('POST', '/api/projects', 405), ('GET', '/static/app.js', 200),
                                          ('GET', '/favicon.ico', 204), ('HEAD', '/favicon.ico', 204),
                                          ('POST', '/favicon.ico', 405), ('GET', '/other.ico', 403)]:
                c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                c.request(method, path)
                response = c.getresponse()
                body = response.read()
                self.assertEqual(response.status, expected)
                if expected == 204:
                    self.assertEqual(body, b'')
                c.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


class UploadPolicyTests(unittest.TestCase):
    def setUp(self):
        from deployment.mobile_server import APP_ROOT
        self.temp = tempfile.TemporaryDirectory(prefix='fixture-upload-', dir=APP_ROOT / 'deployment')
        self.root = Path(self.temp.name)
        self.app = SimpleNamespace(upload_root=self.root, check_disk=lambda: None, maximum_duration=180)

    def tearDown(self):
        self.temp.cleanup()

    def fake(self, body, kind='narration', suffix='.wav'):
        headers = Message()
        headers['Content-Length'] = str(len(body))
        instance = SimpleNamespace(app=self.app, headers=headers, rfile=io.BytesIO(body),
                                   json=lambda value, status: (value, status))
        query = {'kind': [kind], 'filename': ['../fixture' + suffix], 'license': ['user_owned']}
        return instance, query

    def test_probe_forced_format_file_protocol_and_timeout(self):
        header = b'RIFF' + (16).to_bytes(4, 'little') + b'WAVEdata'
        instance, query = self.fake(header)
        media = {'format': {'duration': '3'}, 'streams': [{'codec_type': 'audio', 'codec_name': 'pcm_s16le', 'channels': 2, 'sample_rate': '48000'}]}
        with patch('deployment.mobile_server.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(media))) as probe:
            record, status = MobileHandler.upload_asset(instance, query)
        self.assertEqual(status, 201)
        command = probe.call_args.args[0]
        self.assertEqual(command[command.index('-protocol_whitelist') + 1], 'file')
        self.assertEqual(command[command.index('-f') + 1], 'wav')
        self.assertEqual(probe.call_args.kwargs['timeout'], 10)
        self.assertTrue(Path(record['path']).is_relative_to(self.root))
        self.assertEqual(record['owner'], 'single-owner')

    def test_disguised_playlist_rejected_before_ffprobe(self):
        instance, query = self.fake(b'#EXTM3U\nhttps://invalid.test/fixture', 'clip', '.mp4')
        with patch('deployment.mobile_server.subprocess.run') as probe:
            with self.assertRaises(Exception) as error:
                MobileHandler.upload_asset(instance, query)
            self.assertEqual(error.exception.code, 'INVALID_MEDIA_SIGNATURE')
            probe.assert_not_called()

    def test_media_duration_and_upload_byte_limits(self):
        instance, query = self.fake(b'RIFF' + b'1234' + b'WAVEdata')
        media = {'format': {'duration': '9999'}, 'streams': [{'codec_type': 'audio', 'codec_name': 'pcm_s16le', 'channels': 2, 'sample_rate': '48000'}]}
        with patch('deployment.mobile_server.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(media))):
            with self.assertRaises(Exception) as error:
                MobileHandler.upload_asset(instance, query)
            self.assertEqual(error.exception.code, 'MEDIA_LIMIT')
        instance.headers.replace_header('Content-Length', str(17 * 1024**2))
        with self.assertRaises(SecurityError):
            MobileHandler.upload_asset(instance, query)


if __name__ == '__main__':
    unittest.main()
