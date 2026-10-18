"""Slow unauthenticated bodies must not block probes or change auth state.

The real handler dispatch runs in threads with a controlled body reader. No
network permissions, GPU service, renderer fixture, or paid workload is used.
"""
from email.message import Message
from pathlib import Path
import sys
import tempfile
import threading
import unittest

PROFILE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROFILE))
import https_server as module

ORIGIN = 'https://studio-concurrency.example.test'
OWNER = 'TEST_ONLY-concurrency-owner-fixture'


class HealthConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.owner = self.root / 'owner-code'
        self.owner.write_text(OWNER)
        self.owner.chmod(0o600)
        self.factory_calls = []
        def controller_factory(**kwargs):
            self.factory_calls.append(kwargs)
            raise AssertionError('Setup must not construct a rendering controller')
        self.app = module.Application(self.root, self.owner, self.root / 'export', None,
                                      controller_factory=controller_factory)
        self.handler = self.app.handler()
        self.threads = []
        self.release = threading.Event()

    def tearDown(self):
        self.release.set()
        for thread in self.threads:
            thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, path, command='GET', headers=None):
        handler = object.__new__(self.handler)
        handler.path, handler.command = path, command
        handler.headers = headers or Message()
        handler.client_address = ('127.0.0.1', 23456)
        return handler

    def run_thread(self, target):
        thread = threading.Thread(target=target, daemon=True)
        self.threads.append(thread)
        thread.start()
        return thread

    def test_health_responds_while_unauthenticated_setup_body_is_incomplete(self):
        body_entered, health_done = threading.Event(), threading.Event()
        slow = self.request('/api/setup/login', 'POST')
        def incomplete_body(*args, **kwargs):
            body_entered.set()
            self.release.wait(timeout=3)
            return {}
        slow._body = incomplete_body
        errors, responses = [], []
        def handle_slow():
            try:
                slow._dispatch()
            except Exception as error:
                errors.append(getattr(error, 'code', type(error).__name__))
        self.run_thread(handle_slow)
        self.assertTrue(body_entered.wait(timeout=1), 'Controlled body reader was not reached')
        probe = self.request('/healthz')
        def send(status, body, *args, **kwargs):
            responses.append((status, body))
            health_done.set()
        probe._send = send
        self.run_thread(probe._dispatch)
        self.assertTrue(health_done.wait(timeout=1), 'Health probe waited on an unauthenticated request body')
        self.assertEqual(responses[0][0], 200)
        self.assertTrue(responses[0][1]['serviceAlive'])
        self.assertFalse(responses[0][1]['renderAllowed'])
        self.assertFalse(responses[0][1]['gpuRenderingVerified'])
        self.assertIsNone(self.app.core.public_origin)
        self.assertEqual(self.factory_calls, [])
        self.release.set()
        for thread in self.threads:
            thread.join(timeout=3)
        self.assertEqual(errors, ['STUDIO_SETUP_FIELDS_REQUIRED'])

    def test_incomplete_body_cannot_authenticate_consume_nonce_or_register_origin(self):
        cookie, csrf = self.app.core.challenge()
        headers = Message()
        for key, value in [('Host', 'studio-concurrency.example.test'), ('Origin', ORIGIN),
                           ('Sec-Fetch-Site', 'same-origin'), ('Content-Type', 'application/json'),
                           ('X-Studio-Setup-CSRF', csrf),
                           ('Cookie', module.CHALLENGE_COOKIE + '=' + cookie)]:
            headers[key] = value
        body_entered, done = threading.Event(), threading.Event()
        request = self.request('/api/setup/login', 'POST', headers)
        def incomplete_body(*args, **kwargs):
            body_entered.set()
            self.release.wait(timeout=3)
            return {'password': OWNER, 'origin': ORIGIN, 'challenge': csrf}
        request._body = incomplete_body
        responses, errors = [], []
        request._send = lambda status, body, *a, **k: responses.append((status, body))
        def handle():
            try:
                request._dispatch()
            except Exception as error:
                errors.append(getattr(error, 'code', type(error).__name__))
            finally:
                done.set()
        self.run_thread(handle)
        self.assertTrue(body_entered.wait(timeout=1))
        self.assertEqual(self.app.core.sessions.record['sessions'], {})
        self.assertEqual(self.app.core._pending, {})
        self.assertEqual(len(self.app.core._challenges), 1)
        self.assertFalse(self.app.core.origin_path.exists())
        self.assertEqual(self.factory_calls, [])
        self.assertFalse(done.is_set())
        self.release.set()
        self.assertTrue(done.wait(timeout=2))
        self.assertEqual(errors, [])
        self.assertEqual(responses[0][0], 200)
        self.assertTrue(responses[0][1]['authenticated'])
        self.assertNotIn('token', responses[0][1])
        self.assertFalse(responses[0][1]['renderAllowed'])
        self.assertEqual(len(self.app.core.sessions.record['sessions']), 1)
        self.assertEqual(len(self.app.core._pending), 1)
        self.assertEqual(self.app.core._challenges, {})
        self.assertIsNone(self.app.core.public_origin)
        self.assertEqual(self.factory_calls, [])


if __name__ == '__main__':
    unittest.main()
