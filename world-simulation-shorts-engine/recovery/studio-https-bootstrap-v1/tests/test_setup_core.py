"""Focused CPU security tests; fixture credentials never enter deployment config."""
from email.message import Message
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest

PROFILE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROFILE))
# The root-owned frozen loader is supplied by the independent extension. For
# direct development before that file exists, load only the unchanged server.
if not (PROFILE / 'frozen.py').is_file():
    original = PROFILE.parent / 'production-studio-mvp-v1'
    spec = importlib.util.spec_from_file_location('_core_test_original_server', original / 'server.py')
    server = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = server
    spec.loader.exec_module(server)
    sys.modules['frozen'] = SimpleNamespace(load_originals=lambda: SimpleNamespace(server=server))
import setup_core as core

TEST_OWNER = 'TEST_ONLY-owner-code-for-setup-fixtures'
FIRST = 'https://studio.example.test'
SECOND = 'https://next-studio.example.test'


def headers(origin=FIRST, host=None, **overrides):
    values = {'Host': host or origin.split('://', 1)[1], 'Origin': origin,
              'Sec-Fetch-Site': 'same-origin', 'Content-Type': 'application/json'}
    values.update(overrides)
    result = Message()
    for key, value in values.items():
        if value is not None:
            result[key] = value
    return result


class SetupCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.owner = self.root / 'owner-code'
        self.owner.write_text(TEST_OWNER)
        self.owner.chmod(0o600)
        self.now = [1800000000.0]
        self.app = core.SetupCore(self.root, self.owner, clock=lambda: self.now[0])
        self.owner_sha = hashlib.sha256(self.owner.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def assertCode(self, expected, function):
        with self.assertRaises(core.SetupError) as raised:
            function()
        self.assertEqual(raised.exception.code, expected)

    def begin(self, *, target=FIRST, request=None, password=TEST_OWNER):
        cookie, csrf = self.app.challenge()
        return self.app.begin(request or headers(), '127.0.0.1', password, target, cookie, csrf)

    def commit(self, pending, *, request=None, origin=None, csrf=None, confirm=True):
        return self.app.commit(request or headers(), '127.0.0.1', pending['token'],
                               pending['csrf'] if csrf is None else csrf,
                               pending['origin'] if origin is None else origin, confirm)

    def test_missing_origin_is_safe_unconfigured_state_without_creation(self):
        self.assertIsNone(self.app.public_origin)
        self.assertFalse(self.app.origin_path.exists())
        self.assertFalse((self.root / 'production').exists())

    def test_owner_required_and_never_generated(self):
        missing = self.root / 'missing'
        self.assertCode('STUDIO_OWNER_CONFIGURATION_REQUIRED',
                        lambda: core.SetupCore(self.root, missing))
        self.assertFalse(missing.exists())

    def test_begin_requires_owner_and_consumes_challenge(self):
        cookie, csrf = self.app.challenge()
        call = lambda: self.app.begin(headers(), '127.0.0.1', 'wrong', FIRST, cookie, csrf)
        self.assertCode('LOGIN_FAILED', call)
        self.assertCode('STUDIO_SETUP_CHALLENGE_REQUIRED', call)
        self.assertIsNone(self.app.public_origin)

    def test_authenticated_confirmation_persists_and_requires_fresh_login(self):
        pending = self.begin()
        self.assertIsNone(self.app.public_origin)
        self.assertTrue(self.app.sessions.claims(pending['token']))
        result = self.commit(pending)
        self.assertEqual(result['origin'], FIRST)
        self.assertTrue(result['reloginRequired'])
        self.assertFalse(result['renderAllowed'])
        self.assertEqual(self.app.public_origin, FIRST)
        self.assertIsNone(self.app.sessions.claims(pending['token']))
        self.assertEqual(stat.S_IMODE(self.app.origin_path.stat().st_mode), 0o600)
        self.assertEqual(hashlib.sha256(self.owner.read_bytes()).hexdigest(), self.owner_sha)

    def test_nonce_replay_and_setup_session_replay_fail(self):
        pending = self.begin()
        self.commit(pending)
        self.assertCode('AUTH_REQUIRED', lambda: self.commit(pending))

    def test_bad_cookie_or_csrf_cannot_login(self):
        cookie, csrf = self.app.challenge()
        for wrong_cookie, wrong_csrf in [('X' * 43, csrf), (cookie, 'X' * 43), ('', csrf)]:
            with self.subTest(cookie=bool(wrong_cookie), csrf=wrong_csrf == csrf):
                self.assertCode('STUDIO_SETUP_CHALLENGE_REQUIRED', lambda: self.app.begin(
                    headers(), '127.0.0.1', TEST_OWNER, FIRST, wrong_cookie, wrong_csrf))

    def test_login_challenge_expires(self):
        cookie, csrf = self.app.challenge()
        self.now[0] += 121
        self.assertCode('STUDIO_SETUP_CHALLENGE_REQUIRED', lambda: self.app.begin(
            headers(), '127.0.0.1', TEST_OWNER, FIRST, cookie, csrf))

    def test_commit_challenge_expires(self):
        pending = self.begin()
        self.now[0] += 121
        self.assertCode('CSRF_REQUIRED', lambda: self.commit(pending))

    def test_commit_requires_explicit_confirmation(self):
        pending = self.begin()
        self.assertCode('STUDIO_SETUP_EXPLICIT_CONFIRMATION_REQUIRED',
                        lambda: self.commit(pending, confirm=False))
        self.assertIsNone(self.app.public_origin)

    def test_commit_csrf_and_origin_bound(self):
        pending = self.begin()
        self.assertCode('CSRF_REQUIRED', lambda: self.commit(pending, csrf='wrong'))
        self.assertCode('CSRF_REQUIRED', lambda: self.commit(pending, origin=SECOND))
        self.assertIsNone(self.app.public_origin)

    def test_canonical_origin_rejects_non_https_local_and_ambiguous_values(self):
        values = ['http://studio.example.test', 'https://localhost', 'https://127.0.0.1',
                  'https://10.0.0.1', 'https://169.254.1.1', 'https://[::1]',
                  FIRST + '/', FIRST + '/path', FIRST + '?x=1', FIRST + '#hash',
                  'https://user:password@studio.example.test', 'https://studio',
                  'https://STUDIO.example.test', 'https://studio.example.test:443',
                  'https://studio.example.test\\@bad.test', 'https://example.local']
        for value in values:
            with self.subTest(value=value):
                self.assertCode('STUDIO_HTTPS_ORIGIN_REQUIRED', lambda: core.canonical_origin(value))

    def test_wrong_host_origin_or_cross_site_request_never_persists(self):
        requests = [headers(host='attacker.example.test'), headers(origin=SECOND),
                    headers(**{'Origin': None}), headers(**{'Origin': 'null'}),
                    headers(**{'Sec-Fetch-Site': 'cross-site'}),
                    headers(**{'Sec-Fetch-Site': 'none'}), headers(**{'Sec-Fetch-Site': None}),
                    headers(**{'X-Forwarded-Host': 'attacker.example.test'}),
                    headers(**{'X-Forwarded-Proto': 'http'}),
                    headers(**{'Content-Type': 'text/plain'})]
        for index, request in enumerate(requests):
            with self.subTest(index=index):
                # Independent peer rate buckets preserve the real rate limit.
                cookie, csrf = self.app.challenge()
                with self.assertRaises(core.SetupError):
                    self.app.begin(request, '127.0.0.' + str(index + 1), TEST_OWNER, FIRST, cookie, csrf)
                self.assertIsNone(self.app.public_origin)

    def test_duplicate_security_headers_rejected(self):
        for field, value in [('Host', 'attacker.example.test'), ('Origin', SECOND),
                             ('X-Forwarded-Host', 'attacker.example.test'),
                             ('Sec-Fetch-Site', 'same-origin'), ('Content-Type', 'application/json')]:
            with self.subTest(field=field):
                request = headers()
                if field == 'X-Forwarded-Host':
                    request[field] = 'studio.example.test'
                request[field] = value
                with self.assertRaises(core.SetupError):
                    self.begin(request=request)
                self.assertIsNone(self.app.public_origin)

    def test_verified_proxy_envelope_supported_without_host_learning(self):
        request = headers(host='127.0.0.1:8080', **{'X-Forwarded-Host': 'studio.example.test',
                                                   'X-Forwarded-Proto': 'https'})
        pending = self.begin(request=request)
        self.commit(pending, request=request)
        self.assertEqual(self.app.public_origin, FIRST)

    def test_owner_changes_origin_from_existing_trusted_origin(self):
        self.commit(self.begin())
        pending = self.begin(target=SECOND, request=headers(FIRST))
        self.assertEqual(self.app.public_origin, FIRST)
        self.assertCode('INVALID_HOST', lambda: self.commit(pending, request=headers(SECOND)))
        result = self.commit(pending, request=headers(FIRST))
        self.assertEqual(result['version'], 2)
        self.assertEqual(self.app.public_origin, SECOND)

    def test_restart_preserves_origin_and_does_not_construct_render_controller(self):
        self.commit(self.begin())
        restart = core.SetupCore(self.root, self.owner, clock=lambda: self.now[0])
        self.assertEqual(restart.public_origin, FIRST)
        self.assertFalse((self.root / 'production').exists())
        self.assertEqual(hashlib.sha256(self.owner.read_bytes()).hexdigest(), self.owner_sha)

    def test_production_live_and_disk_sessions_revoked_before_origin_change(self):
        production = core._originals.server.StudioSessions(self.owner, self.root / 'studio-auth.json',
                                                          clock=lambda: self.now[0])
        token = production.login(TEST_OWNER)
        key_before = production.key
        self.app.bind_production_sessions(production)
        self.commit(self.begin())
        self.assertIsNone(production.claims(token))
        self.assertNotEqual(production.key, key_before)
        restarted = core._originals.server.StudioSessions(self.owner, self.root / 'studio-auth.json',
                                                         clock=lambda: self.now[0])
        self.assertIsNone(restarted.claims(token))

    def test_disk_only_production_sessions_revoked(self):
        production = core._originals.server.StudioSessions(self.owner, self.root / 'studio-auth.json',
                                                          clock=lambda: self.now[0])
        token = production.login(TEST_OWNER)
        self.commit(self.begin())
        restarted = core._originals.server.StudioSessions(self.owner, self.root / 'studio-auth.json',
                                                         clock=lambda: self.now[0])
        self.assertIsNone(restarted.claims(token))

    def test_environment_configuration_preserves_existing_origin(self):
        self.assertIsNone(self.app.configure_from_environment(None))
        self.app.configure_from_environment(FIRST)
        first = self.app.origin_path.read_bytes()
        self.app.configure_from_environment(FIRST)
        self.assertEqual(self.app.origin_path.read_bytes(), first)
        self.assertCode('STUDIO_CONFIGURED_ORIGIN_CONFLICT',
                        lambda: self.app.configure_from_environment(SECOND))
        self.assertEqual(self.app.origin_path.read_bytes(), first)

    def test_origin_path_symlink_and_permissive_file_fail_closed(self):
        target = self.root / 'target.json'
        target.write_text('{}')
        target.chmod(0o600)
        self.app.origin_path.symlink_to(target)
        self.assertCode('STUDIO_PRIVATE_FILE_REQUIRED', lambda: self.app.public_origin)
        self.app.origin_path.unlink()
        self.app.origin_path.write_text('{}')
        self.app.origin_path.chmod(0o644)
        self.assertCode('STUDIO_PRIVATE_FILE_REQUIRED', lambda: self.app.public_origin)

    def test_owner_symlink_hardlink_and_private_directory_permissions(self):
        link = self.root / 'owner-link'
        link.symlink_to(self.owner)
        self.assertCode('STUDIO_PRIVATE_FILE_REQUIRED', lambda: core.SetupCore(self.root, link))
        hardlink = self.root / 'hardlink'
        os.link(self.owner, hardlink)
        self.assertCode('STUDIO_PRIVATE_FILE_REQUIRED', lambda: core.SetupCore(self.root, self.owner))
        hardlink.unlink()
        self.root.chmod(0o755)
        self.assertCode('STUDIO_PRIVATE_DIRECTORY_REQUIRED', lambda: core.SetupCore(self.root, self.owner))
        self.root.chmod(0o700)

    def test_challenge_storage_bounded_and_expired_entries_reclaimed(self):
        for _ in range(128):
            self.app.challenge()
        self.assertCode('STUDIO_SETUP_BUSY', self.app.challenge)
        self.now[0] += 121
        self.assertEqual(len(self.app.challenge()), 2)

    def test_rate_limit_limits_owner_password_attempts(self):
        for _ in range(5):
            self.assertCode('LOGIN_FAILED', lambda: self.begin(password='wrong'))
        self.assertCode('LOGIN_RATE_LIMIT', self.begin)

    def test_unauthenticated_commit_cannot_write_any_configuration(self):
        self.assertCode('AUTH_REQUIRED', lambda: self.app.commit(
            headers(), '127.0.0.1', 'invalid', 'invalid', FIRST, True))
        self.assertFalse(self.app.origin_path.exists())

    def test_origin_json_duplicate_keys_or_invalid_schema_fail_closed(self):
        self.app.origin_path.write_text('{"origin":"%s","origin":"%s"}' % (FIRST, SECOND))
        self.app.origin_path.chmod(0o600)
        self.assertCode('STUDIO_PRIVATE_CONFIGURATION_INVALID', lambda: self.app.public_origin)
        self.app.origin_path.write_text(json.dumps({'schema': 'unknown', 'origin': FIRST}))
        self.assertCode('STUDIO_ORIGIN_CONFIGURATION_INVALID', lambda: self.app.public_origin)


if __name__ == '__main__':
    unittest.main()
