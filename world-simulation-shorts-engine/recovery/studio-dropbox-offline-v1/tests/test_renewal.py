"""CPU-only fake HTTPS tests. No request reaches Dropbox or any other host."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import traceback
import unittest
import urllib.error
import urllib.parse
import urllib.request


HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from offline_frozen import DURABILITY


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


oauth = load('offline_renewal_under_test', HERE / 'renewal.py')
stores = load('offline_frozen_stores_under_test', DURABILITY / 'stores.py')


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class Response:
    def __init__(self, payload=b'{}', *, status=200, url=oauth.TOKEN_URL):
        self.payload, self.status, self.url = payload, status, url
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def read(self, limit):
        return self.payload[:limit]

    def close(self):
        self.closed = True

    def geturl(self):
        return self.url


def token_response(token='synthetic-access-value-001', ttl=3600, **extra):
    row = dict(access_token=token, expires_in=ttl, token_type='bearer')
    row.update(extra)
    return Response(json.dumps(row).encode())


def http_error(status, url=oauth.TOKEN_URL):
    return urllib.error.HTTPError(url, status, 'SYNTHETIC_ERROR', {},
                                 io.BytesIO(b'synthetic-private-error-body'))


class Opener:
    def __init__(self, *results):
        self.results, self.calls = list(results), []
        self.lock = threading.Lock()

    def open(self, request, timeout):
        with self.lock:
            self.calls.append((request, timeout))
            result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        if callable(result):
            return result(request)
        return result


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.previous_stores = oauth._stores
        oauth._stores = lambda: stores
        self.directory = tempfile.TemporaryDirectory(prefix='offline-oauth-test-')
        self.root = Path(self.directory.name)
        self.files = []
        for name, body in (
                ('app-key', 'synthetic_app_key'),
                ('app-secret', 'synthetic-app-secret-value'),
                ('refresh-token', 'synthetic-refresh-token-value')):
            path = self.root / name
            path.write_text(body)
            path.chmod(0o600)
            if os.getuid() == 0:
                os.chown(path, 1000, 1000)
            self.files.append(path)
        self.clock = Clock()

    def tearDown(self):
        oauth._stores = self.previous_stores
        self.directory.cleanup()

    def provider(self, opener, **kwargs):
        return oauth.TokenProvider(*self.files, opener=opener, clock=self.clock, **kwargs)

    def assert_code(self, code, function):
        with self.assertRaises(stores.BackupError) as caught:
            function()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_refresh_form_fixed_https_and_memory_cache(self):
        opener = Opener(token_response())
        provider = self.provider(opener)
        self.assertEqual(provider.access_token(), 'synthetic-access-value-001')
        self.assertEqual(provider.access_token(), 'synthetic-access-value-001')
        self.assertEqual(len(opener.calls), 1)
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, oauth.TOKEN_URL)
        self.assertEqual(timeout, 30)
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(urllib.parse.parse_qs(request.data.decode()), {
            'grant_type': ['refresh_token'],
            'refresh_token': ['synthetic-refresh-token-value'],
            'client_id': ['synthetic_app_key'],
            'client_secret': ['synthetic-app-secret-value'],
        })
        self.assertNotIn('Authorization', dict(request.header_items()))
        self.assertEqual(sorted(path.name for path in self.root.iterdir()),
                         ['app-key', 'app-secret', 'refresh-token'])

    def test_offline_authorization_code_exchange_uses_same_bounded_transport(self):
        form = {'grant_type': 'authorization_code', 'client_id': 'synthetic_app_key',
                'client_secret': 'synthetic-app-secret-value', 'code': 'synthetic-one-time-code'}
        opener = Opener(token_response(refresh_token='synthetic-refresh-token-value'))
        result = oauth.token_request(form, opener=opener)
        self.assertEqual(result['refresh_token'], 'synthetic-refresh-token-value')
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, oauth.TOKEN_URL)
        self.assertEqual(timeout, 30)
        self.assertEqual(urllib.parse.parse_qs(request.data.decode())['grant_type'], ['authorization_code'])

    def test_enrollment_transport_rejects_extra_fields_or_invalid_grants(self):
        form = {'grant_type': 'authorization_code', 'client_id': 'synthetic_app_key',
                'client_secret': 'synthetic-app-secret-value', 'code': 'synthetic-one-time-code'}
        for mutation in ({'redirect_uri': 'https://other.example'}, {'grant_type': 'password'},
                         {'grant_type': []}, {'code': 'short'}, {'client_id': 'invalid space'}):
            with self.subTest(mutation=mutation):
                opener = Opener()
                self.assert_code('DURABILITY_OAUTH_REQUEST_INVALID',
                    lambda: oauth.token_request(dict(form, **mutation), opener=opener))
                self.assertEqual(opener.calls, [])

    def test_refresh_before_expiry_with_monotonic_clock(self):
        opener = Opener(token_response(ttl=3600), token_response('synthetic-access-value-002'))
        provider = self.provider(opener)
        provider.access_token()
        self.clock.now += 3539
        self.assertEqual(provider.access_token(), 'synthetic-access-value-001')
        self.clock.now += 1
        self.assertEqual(provider.access_token(), 'synthetic-access-value-002')
        self.assertEqual(len(opener.calls), 2)

    def test_short_ttl_has_bounded_refresh_lead(self):
        opener = Opener(token_response(ttl=1), token_response('synthetic-access-value-002', ttl=1))
        provider = self.provider(opener)
        provider.access_token()
        self.clock.now += .89
        self.assertEqual(provider.access_token(), 'synthetic-access-value-001')
        self.clock.now += .02
        self.assertEqual(provider.access_token(), 'synthetic-access-value-002')

    def test_concurrent_requests_only_one_refresh(self):
        barrier = threading.Barrier(8)

        def delayed(_):
            time.sleep(.02)
            return token_response()

        opener = Opener(delayed)
        provider = self.provider(opener)

        def get(_):
            barrier.wait()
            return provider.access_token()

        with ThreadPoolExecutor(max_workers=8) as executor:
            self.assertEqual(list(executor.map(get, range(8))), ['synthetic-access-value-001'] * 8)
        self.assertEqual(len(opener.calls), 1)

    def test_concurrent_rejected_token_reuses_replacement(self):
        opener = Opener(token_response(), token_response('synthetic-access-value-002'))
        provider = self.provider(opener)
        rejected = provider.access_token()
        with ThreadPoolExecutor(max_workers=8) as executor:
            values = list(executor.map(lambda _: provider.access_token(force=True, rejected_token=rejected), range(8)))
        self.assertEqual(values, ['synthetic-access-value-002'] * 8)
        self.assertEqual(len(opener.calls), 2)

    def test_refresh_failure_discards_cached_token_and_does_not_retry(self):
        opener = Opener(token_response(), http_error(400), token_response('synthetic-access-value-003'))
        provider = self.provider(opener)
        provider.access_token()
        self.clock.now += 4000
        self.assert_code('DURABILITY_OAUTH_REFRESH_REJECTED', provider.access_token)
        self.assertIsNone(provider._access_token)
        self.assertEqual(len(opener.calls), 2)
        self.assertEqual(provider.access_token(), 'synthetic-access-value-003')

    def test_safe_errors_never_expose_credentials_or_response(self):
        opener = Opener(RuntimeError('synthetic-refresh-token-value synthetic-private-error-body'))
        provider = self.provider(opener)
        error = self.assert_code('DURABILITY_OAUTH_CONNECTION_FAILED', provider.access_token)
        message = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        for secret in ('synthetic-refresh-token-value', 'synthetic-app-secret-value', 'synthetic-private-error-body'):
            self.assertNotIn(secret, message + repr(provider))

    def test_required_scope_when_present(self):
        opener = Opener(token_response(scope=' '.join(sorted(oauth.REQUIRED_SCOPES))))
        self.assertEqual(self.provider(opener).access_token(), 'synthetic-access-value-001')
        for scope in ('files.content.read files.content.write', '', None, ['files.metadata.read']):
            with self.subTest(scope=scope):
                self.assert_code('DURABILITY_OAUTH_SCOPE_MISSING',
                                 self.provider(Opener(token_response(scope=scope))).access_token)

    def test_missing_scope_is_not_falsely_reported_as_granted(self):
        # Dropbox may omit scope on refresh. Actual metadata API use still
        # occurs in the external proof; this unit test makes no grant claim.
        provider = self.provider(Opener(token_response()))
        self.assertEqual(provider.access_token(), 'synthetic-access-value-001')

    def test_response_validation(self):
        rows = [
            {'expires_in': True}, {'expires_in': 0}, {'expires_in': -1},
            {'expires_in': 3600.0}, {'expires_in': '3600'},
            {'expires_in': oauth.MAX_EXPIRES_IN + 1},
            {'access_token': 'short'}, {'access_token': 'invalid\nheader-value'},
            {'token_type': 'mac'}, {'token_type': None},
        ]
        for row in rows:
            with self.subTest(row=row):
                self.assert_code('DURABILITY_OAUTH_RESPONSE_INVALID',
                                 self.provider(Opener(token_response(**row))).access_token)
        for body in (b'not-json', b'[]', b'{"access_token":"a","access_token":"b"}', b'{"expires_in":NaN}'):
            with self.subTest(body=body):
                self.assert_code('DURABILITY_OAUTH_RESPONSE_INVALID',
                                 self.provider(Opener(Response(body))).access_token)

    def test_bounded_response_and_redirect(self):
        self.assert_code('DURABILITY_OAUTH_RESPONSE_TOO_LARGE',
                         self.provider(Opener(Response(b'x' * (oauth.MAX_RESPONSE + 1)))).access_token)
        self.assert_code('DURABILITY_OAUTH_REDIRECT_REJECTED',
                         self.provider(Opener(Response(url='https://other.example/token'))).access_token)
        self.assert_code('DURABILITY_OAUTH_REDIRECT_POLICY_REQUIRED',
                         lambda: self.provider(urllib.request.build_opener()))

    def test_credential_file_permissions_symlink_and_shape(self):
        self.files[0].chmod(0o644)
        self.assert_code('DURABILITY_PRIVATE_SECRET_REQUIRED', lambda: self.provider(Opener()))
        self.files[0].chmod(0o600)
        linked = self.root / 'linked'
        linked.symlink_to(self.files[0])
        self.assert_code('DURABILITY_PRIVATE_SECRET_REQUIRED',
                         lambda: oauth.TokenProvider(linked, *self.files[1:], opener=Opener(), clock=self.clock))
        self.files[0].write_text('invalid key with space')
        self.assert_code('DURABILITY_OAUTH_CREDENTIAL_INVALID', lambda: self.provider(Opener()))

    def test_token_endpoint_http_errors_never_retry(self):
        for status, code in ((400, 'DURABILITY_OAUTH_REFRESH_REJECTED'),
                             (401, 'DURABILITY_OAUTH_REFRESH_REJECTED'),
                             (403, 'DURABILITY_OAUTH_HTTP_FAILED'),
                             (429, 'DURABILITY_OAUTH_RATE_LIMITED'),
                             (500, 'DURABILITY_OAUTH_HTTP_FAILED')):
            with self.subTest(status=status):
                opener = Opener(http_error(status))
                self.assert_code(code, self.provider(opener).access_token)
                self.assertEqual(len(opener.calls), 1)

    def test_invalid_clock_and_refresh_latency(self):
        self.clock.now = float('nan')
        self.assert_code('DURABILITY_OAUTH_CLOCK_INVALID', self.provider(Opener()).access_token)
        self.clock.now = 100

        def expired(_):
            self.clock.now += 3600
            return token_response()

        provider = self.provider(Opener(expired))
        self.assert_code('DURABILITY_OAUTH_TOKEN_LIFETIME_EXHAUSTED', provider.access_token)
        self.assertIsNone(provider._access_token)

    def test_file_route_injects_token_preserves_app_folder_path(self):
        provider = self.provider(Opener(token_response()))
        argument = json.dumps({'path': '/WORLD_ENGINE_STUDIO_BACKUPS_V1/' + 'a' * 64})
        request = urllib.request.Request('https://content.dropboxapi.com/2/files/upload',
            data=b'opaque-encrypted-object', method='POST', headers={
                'Dropbox-API-Arg': argument, 'Authorization': 'Bearer synthetic-expired-access-value',
                'Content-Type': 'application/octet-stream'})
        response = Response(b'{}', url=request.full_url)
        underlying = Opener(response)
        wrapper = oauth.OfflineOpener(provider, underlying)
        self.assertIs(wrapper.open(request, timeout=30), response)
        sent, timeout = underlying.calls[0]
        self.assertEqual(sent.get_header('Authorization'), 'Bearer synthetic-access-value-001')
        self.assertEqual(sent.get_header('Dropbox-api-arg'), argument)
        self.assertEqual(sent.data, request.data)
        self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-expired-access-value')
        self.assertEqual(timeout, 30)
        self.assertNotIn('synthetic-access-value-001', repr(wrapper))

    def test_file_route_401_refreshes_once(self):
        tokens = Opener(token_response(), token_response('synthetic-access-value-002'))
        provider = self.provider(tokens)
        url = 'https://content.dropboxapi.com/2/files/download'
        response = Response(b'opaque', url=url)
        underlying = Opener(http_error(401, url), response)
        wrapper = oauth.OfflineOpener(provider, underlying)
        request = urllib.request.Request(url, data=b'', method='POST')
        self.assertIs(wrapper.open(request), response)
        self.assertEqual(len(tokens.calls), 2)
        self.assertEqual([row[0].get_header('Authorization') for row in underlying.calls],
                         ['Bearer synthetic-access-value-001', 'Bearer synthetic-access-value-002'])

    def test_second_401_propagates_and_never_loops(self):
        tokens = Opener(token_response(), token_response('synthetic-access-value-002'))
        url = 'https://content.dropboxapi.com/2/files/download'
        underlying = Opener(http_error(401, url), http_error(401, url))
        wrapper = oauth.OfflineOpener(self.provider(tokens), underlying)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            wrapper.open(urllib.request.Request(url, data=b'', method='POST'))
        self.assertEqual(caught.exception.code, 401)
        caught.exception.close()
        self.assertEqual(len(tokens.calls), 2)
        self.assertEqual(len(underlying.calls), 2)

    def test_no_replay_for_forbidden_limit_server_or_ambiguous_upload_failure(self):
        url = 'https://content.dropboxapi.com/2/files/upload'
        for failure in (http_error(403, url), http_error(429, url), http_error(500, url),
                        urllib.error.URLError('synthetic ambiguous upload failure')):
            with self.subTest(failure=type(failure).__name__):
                tokens = Opener(token_response())
                underlying = Opener(failure)
                wrapper = oauth.OfflineOpener(self.provider(tokens), underlying)
                with self.assertRaises(type(failure)) as caught:
                    wrapper.open(urllib.request.Request(url, data=b'opaque', method='POST'))
                if isinstance(caught.exception, urllib.error.HTTPError):
                    caught.exception.close()
                self.assertEqual(len(tokens.calls), 1)
                self.assertEqual(len(underlying.calls), 1)

    def test_untrusted_routes_fail_before_credentials_are_requested(self):
        for url in ('http://content.dropboxapi.com/2/files/download',
                    'https://other.example/2/files/download',
                    oauth.TOKEN_URL, 'https://content.dropboxapi.com/2/files/download?x=1',
                    'https://content.dropboxapi.com/2/files/download#fragment',
                    'https://user:password@content.dropboxapi.com/2/files/download'):
            with self.subTest(url=url):
                tokens, underlying = Opener(), Opener()
                wrapper = oauth.OfflineOpener(self.provider(tokens), underlying)
                self.assert_code('DURABILITY_OAUTH_FILE_ROUTE_REJECTED',
                    lambda: wrapper.open(urllib.request.Request(url, data=b'', method='POST')))
                self.assertEqual(tokens.calls, [])
                self.assertEqual(underlying.calls, [])

    def test_wrong_host_get_request_and_timeout_rejected_before_authentication(self):
        url = 'https://content.dropboxapi.com/2/files/download'
        tokens, underlying = Opener(), Opener()
        wrapper = oauth.OfflineOpener(self.provider(tokens), underlying)
        self.assert_code('DURABILITY_OAUTH_FILE_ROUTE_REJECTED',
            lambda: wrapper.open(urllib.request.Request(url)))
        self.assert_code('DURABILITY_OAUTH_FILE_ROUTE_REJECTED',
            lambda: wrapper.open(urllib.request.Request(url, data=b'', headers={'Host': 'other.example'})))
        for timeout in (0, 31, True, float('inf')):
            self.assert_code('DURABILITY_OAUTH_TIMEOUT_INVALID',
                lambda: wrapper.open(urllib.request.Request(url, data=b''), timeout=timeout))
        self.assertEqual(tokens.calls, [])

    def test_file_route_redirect_is_rejected(self):
        tokens = Opener(token_response())
        response = Response(url='https://other.example/download')
        wrapper = oauth.OfflineOpener(self.provider(tokens), Opener(response))
        url = 'https://content.dropboxapi.com/2/files/download'
        self.assert_code('DURABILITY_OAUTH_REDIRECT_REJECTED',
            lambda: wrapper.open(urllib.request.Request(url, data=b'')))
        self.assertTrue(response.closed)


if __name__ == '__main__':
    unittest.main()
