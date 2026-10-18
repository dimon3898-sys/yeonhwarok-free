"""CPU-only fixed-origin proxy fixtures; these do not observe gCube headers."""
from contextlib import redirect_stdout
from email.message import Message
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import proxy_policy as proxy

ORIGIN = 'https://proxy-fixture.invalid:24999'
AUTHORITY = 'proxy-fixture.invalid:24999'


def headers(**changes):
    values = {'Host': AUTHORITY, 'Origin': ORIGIN,
              'X-Forwarded-Proto': 'http', 'Sec-Fetch-Site': 'same-origin'}
    values.update(changes)
    result = Message()
    for key, value in values.items():
        if value is not None:
            result[key] = value
    return result


class ProxyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = proxy.FixedHTTPSProxyPolicy([ORIGIN], local_port=8080, environ={})
        self.output = io.StringIO()
        self.quiet = redirect_stdout(self.output)
        self.quiet.__enter__()

    def tearDown(self):
        self.quiet.__exit__(None, None, None)

    def assertRejected(self, value, code=None, method='POST'):
        with self.assertRaises(proxy.security.SecurityError) as raised:
            self.policy.check_request(value, method=method, peer_ip='192.0.2.30')
        if code:
            self.assertEqual(raised.exception.code, code)

    def test_original_fails_exact_https_with_http_hop(self):
        original = proxy.security.RequestPolicy([ORIGIN], local_port=8080, environ={})
        with self.assertRaises(proxy.security.SecurityError) as raised:
            original.check_request(headers(), method='POST')
        self.assertEqual(raised.exception.code, 'INVALID_FORWARDED_HEADERS')

    def test_exact_fixed_origin_http_hop_is_accepted_without_mutating_input(self):
        incoming = headers(**{'X-Forwarded-Host': AUTHORITY})
        normalized = proxy.normalize_headers(incoming, ORIGIN)
        self.assertEqual(incoming['X-Forwarded-Proto'], 'http')
        self.assertIsNone(normalized['X-Forwarded-Proto'])
        self.assertEqual(self.policy.check_request(incoming, method='POST'), ORIGIN)
        # The unmodified frozen validator accepts the resulting envelope.
        self.assertEqual(proxy.security.RequestPolicy([ORIGIN], local_port=8080, environ={})
                         .check_request(normalized, method='POST'), ORIGIN)

    def test_missing_and_https_hop_keep_existing_behavior(self):
        for value in (None, 'https'):
            with self.subTest(value=value):
                incoming = headers(**{'X-Forwarded-Proto': value})
                normalized = proxy.normalize_headers(incoming, ORIGIN)
                self.assertEqual(normalized.get('X-Forwarded-Proto'), value)
                self.assertEqual(self.policy.check_request(incoming, method='POST'), ORIGIN)

    def test_every_mutation_requires_exact_non_null_origin(self):
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            for value in (None, 'null', 'https://other.invalid:24999', 'http://' + AUTHORITY,
                          ORIGIN + '/', ORIGIN + ', ' + ORIGIN):
                with self.subTest(method=method, value=value):
                    self.assertRejected(headers(Origin=value), 'INVALID_ORIGIN', method=method)

    def test_wrong_host_or_forwarded_authority_and_port_never_normalized(self):
        for field in ('Host', 'X-Forwarded-Host'):
            for value in ('other.invalid:24999', 'proxy-fixture.invalid',
                          'proxy-fixture.invalid:8080', '127.0.0.1:8080',
                          'studio.default.svc:8080', 'localhost:8080',
                          AUTHORITY + ',other.invalid'):
                with self.subTest(field=field, value=value):
                    self.assertRejected(headers(**{field: value}))

    def test_duplicate_security_headers_rejected_before_normalization(self):
        for field in ('Host', 'Origin', 'X-Forwarded-Host', 'X-Forwarded-Proto'):
            incoming = headers(**{'X-Forwarded-Host': AUTHORITY})
            incoming[field] = incoming[field]
            with self.subTest(field=field):
                self.assertRejected(incoming)

    def test_proto_chains_whitespace_and_unknown_protocols_rejected(self):
        for value in ('http,https', 'https, https', ' http', 'http ', 'HTTP', 'ws',
                      'http\thttps', '', 'ftp'):
            with self.subTest(value=value):
                self.assertRejected(headers(**{'X-Forwarded-Proto': value}), 'INVALID_FORWARDED_HEADERS')

    def test_canonical_hostname_casing_preserves_exact_authority(self):
        self.assertEqual(self.policy.check_request(headers(Host=AUTHORITY.upper()), method='POST'), ORIGIN)

    def test_no_forwarded_header_can_create_or_expand_trust(self):
        fake = 'for=192.0.2.1;proto=https;host="untrusted.invalid"'
        self.assertRejected(headers(Host='untrusted.invalid', Forwarded=fake), 'INVALID_HOST')
        self.assertRejected(headers(Origin='https://untrusted.invalid', Forwarded=fake), 'INVALID_ORIGIN')
        # Like the parent policy, standard Forwarded is advisory and ignored.
        # It never selects the fixed origin or grants a new authority.
        self.assertEqual(self.policy.check_request(headers(Forwarded=fake), method='POST'), ORIGIN)

    def test_get_requires_fixed_host_and_rejects_supplied_wrong_origin(self):
        self.assertEqual(self.policy.check_request(headers(Origin=None), method='GET'), ORIGIN)
        self.assertRejected(headers(Origin='https://other.invalid'), 'INVALID_ORIGIN', method='GET')
        self.assertRejected(headers(Host='other.invalid:24999', Origin=None), method='GET')

    def test_existing_verified_loopback_https_path_stays_supported(self):
        incoming = headers(Host='127.0.0.1:8080', **{'X-Forwarded-Host': AUTHORITY,
                                                   'X-Forwarded-Proto': 'https'})
        self.assertEqual(self.policy.check_request(incoming, method='POST'), ORIGIN)
        self.assertRejected(headers(Host='127.0.0.1:8080'))

    def test_one_fixed_https_origin_required(self):
        for values in ([], [ORIGIN, 'https://other.invalid'], ['http://localhost:8080']):
            with self.subTest(values=values), self.assertRaises(proxy.security.SecurityError):
                proxy.FixedHTTPSProxyPolicy(values, local_port=8080, environ={})

    def test_header_copy_preserves_body_auth_csrf_fields_and_duplicates(self):
        incoming = headers(**{'Content-Length': '42', 'Cookie': 'FIXTURE_PRIVATE_COOKIE',
                             'X-Studio-Setup-CSRF': 'FIXTURE_PRIVATE_CSRF'})
        incoming['X-Test'] = 'one'
        incoming['X-Test'] = 'two'
        result = proxy.normalize_headers(incoming, ORIGIN)
        self.assertEqual(result.get_all('X-Test'), ['one', 'two'])
        for name in ('Content-Length', 'Cookie', 'X-Studio-Setup-CSRF'):
            self.assertEqual(result[name], incoming[name])
        self.assertIsNot(result, incoming)

    def test_diagnostics_expose_only_counts_classes_and_booleans(self):
        incoming = headers(Forwarded='for=PRIVATE_ADDRESS;host=PRIVATE_HOST',
                           Cookie='PRIVATE_COOKIE', Authorization='PRIVATE_TOKEN')
        record = proxy.request_diagnostics(incoming, ORIGIN)
        self.assertEqual(record['protoClass'], 'HTTP')
        self.assertTrue(record['hostMatchesKnownOrigin'])
        self.assertTrue(record['standardForwardedPresent'])
        self.assertEqual(record['secFetchSiteClass'], 'SAME_ORIGIN')
        self.assertEqual(set(record), {'headerCounts', 'protoClass', 'hostMatchesKnownOrigin',
                                      'standardForwardedPresent', 'secFetchSiteClass'})
        self.assertEqual(proxy.request_diagnostics(incoming)['hostMatchesKnownOrigin'], False)
        self.policy.check_request(incoming, method='POST')
        raw = json.dumps(record) + self.output.getvalue()
        for value in ('PRIVATE_', ORIGIN, AUTHORITY, '192.0.2.'):
            self.assertNotIn(value, raw)

    def test_diagnostics_duplicate_and_ambiguous_values_are_closed_classes(self):
        incoming = headers(**{'X-Forwarded-Proto': 'http,https', 'Sec-Fetch-Site': 'strange PRIVATE'})
        self.assertEqual(proxy.request_diagnostics(incoming)['protoClass'], 'INVALID')
        self.assertEqual(proxy.request_diagnostics(incoming)['secFetchSiteClass'], 'INVALID')
        incoming['X-Forwarded-Proto'] = 'https'
        incoming['Host'] = AUTHORITY
        self.assertEqual(proxy.request_diagnostics(incoming, ORIGIN)['protoClass'], 'MULTIPLE')
        self.assertFalse(proxy.request_diagnostics(incoming, ORIGIN)['hostMatchesKnownOrigin'])

    def test_diagnostics_are_rate_bounded_and_header_counts_capped(self):
        limiter = proxy.security.RateLimiter(clock=lambda: 10.0)
        with patch.object(proxy, '_diagnostic_rate', limiter):
            for _ in range(25):
                self.policy.check_request(headers(), method='POST')
        lines = self.output.getvalue().splitlines()
        self.assertEqual(len(lines), 20)
        self.assertTrue(all(json.loads(line)['event'] == 'STUDIO_PROXY_HTTP_HOP_COMPATIBILITY'
                            for line in lines))
        incoming = headers()
        for _ in range(10):
            incoming['Host'] = AUTHORITY
        self.assertEqual(proxy.request_diagnostics(incoming, ORIGIN)['headerCounts']['Host'], 3)


if __name__ == '__main__':
    unittest.main()
