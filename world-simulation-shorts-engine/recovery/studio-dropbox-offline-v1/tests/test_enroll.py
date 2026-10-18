"""CPU-only enrollment contracts; no real authorization/Secret is supplied."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import consent as enroll
from offline_frozen import modules


def temporary_parent():
    for root in (Path('/tmp'), Path('/workspace')):
        if root.is_dir() and not root.is_symlink():
            info = root.stat()
            if info.st_uid in {0, os.geteuid()} and (not stat.S_IMODE(info.st_mode) & 0o022
                    or info.st_uid == 0 and info.st_mode & stat.S_ISVTX):
                return root
    raise RuntimeError('NO_PRIVATE_CPU_FIXTURE_PARENT')


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='offline-enroll-test-', dir=temporary_parent())
        self.root = Path(self.temp.name)
        self.output = self.root / 'refresh-secret'
        self.body = {'refresh_token': 'refreshfixture' * 2, 'access_token': 'accessfixture' * 2,
                     'token_type': 'bearer', 'expires_in': 14400,
                     'scope': 'files.content.read files.content.write files.metadata.read'}

    def tearDown(self):
        self.temp.cleanup()

    def exchange(self, body=None):
        with mock.patch.object(enroll, 'token_request', return_value=self.body if body is None else body):
            return enroll.exchange('appkeyfixture', 'appsecretfixture', 'codefixture', self.output)

    def test_official_no_redirect_url_has_offline_and_exact_required_scopes(self):
        parsed = urlsplit(enroll.authorize_url('appkeyfixture'))
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                         ('https', 'www.dropbox.com', '/oauth2/authorize'))
        query = parse_qs(parsed.query)
        self.assertEqual(query['response_type'], ['code'])
        self.assertEqual(query['token_access_type'], ['offline'])
        self.assertEqual(set(query['scope'][0].split()), enroll.REQUIRED_SCOPES)
        self.assertNotIn('client_secret', query)
        self.assertNotIn('redirect_uri', query)

    def test_exchange_writes_only_private_refresh_secret_and_safe_receipt(self):
        result = self.exchange()
        self.assertEqual(self.output.read_text().strip(), self.body['refresh_token'])
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        receipt = json.dumps(result)
        for key in ('refresh_token', 'access_token'):
            self.assertNotIn(self.body[key], receipt)
        self.assertFalse(result['accessTokenPersisted'])
        self.assertFalse(result['gpuExecuted'])

    def test_existing_secret_never_replaced(self):
        self.output.write_text('retained-secret')
        self.output.chmod(0o600)
        with self.assertRaises(FileExistsError):
            self.exchange()
        self.assertEqual(self.output.read_text(), 'retained-secret')

    def test_missing_refresh_scope_or_invalid_response_never_writes_secret(self):
        for patch in ({'refresh_token': ''}, {'scope': 'files.content.read files.content.write'},
                      {'expires_in': True}, {'token_type': 'different'}, {'access_token': ''}):
            with self.subTest(patch=tuple(patch)), self.assertRaises(modules().stores.BackupError):
                self.exchange({**self.body, **patch})
            self.assertFalse(self.output.exists())

    def test_shared_source_and_symlink_secret_destinations_rejected(self):
        for path in (Path('/world-storage/refresh'), HERE / 'refresh'):
            with self.subTest(path=path), self.assertRaises(modules().stores.BackupError):
                enroll.write_refresh_secret(path, self.body['refresh_token'])
        self.output.symlink_to(self.root / 'unused')
        with self.assertRaises(modules().stores.BackupError):
            enroll.write_refresh_secret(self.output, self.body['refresh_token'])

    def test_noninteractive_input_requires_private_file_and_does_not_echo(self):
        with mock.patch.object(enroll.sys.stdin, 'isatty', return_value=False):
            with mock.patch.object(enroll.getpass, 'getpass') as hidden:
                with self.assertRaisesRegex(modules().stores.BackupError, 'PRIVATE_INPUT_REQUIRED'):
                    enroll.read_input(None, 'hidden')
                hidden.assert_not_called()

    def test_cli_failure_sanitizes_unexpected_exception(self):
        with mock.patch.object(enroll, 'read_input', side_effect=RuntimeError('private value must never print')):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(enroll.main(['--refresh-secret-file', str(self.output)]), 1)
        self.assertNotIn('private value', errors.getvalue())
        self.assertEqual(json.loads(errors.getvalue())['status'], 'BLOCKED')
