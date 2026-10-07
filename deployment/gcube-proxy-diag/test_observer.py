"""Exercise the real pinned validator, not a permissive test replacement."""
import hashlib
import json
from email.message import Message
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

for root in (Path(__file__).resolve().parents[2] / 'world-simulation-shorts-engine',
             Path('/opt/world-engine/world-simulation-shorts-engine')):
    if (root / 'deployment/gcube/proxy.py').exists():
        sys.path.insert(0, str(root)); break
from deployment.gcube.server import GcubePolicy
from deployment.gcube import proxy
from deployment.security import SecurityError
from observer import Observer, EXPECTED_PROXY_SHA256, failure_rule, rule_catalog


def headers(**changes):
    values = {'Host': 'e.gcube.ai:24999', 'X-Forwarded-Proto': 'https',
              'X-Forwarded-For': '203.0.113.8', 'Origin': 'https://e.gcube.ai:24999'}
    values.update({name.replace('_', '-'): value for name, value in changes.items()})
    message = Message()
    for name, value in values.items():
        if value is None: continue
        for item in value if isinstance(value, list) else [value]: message[name] = item
    return message


class ObserverTests(unittest.TestCase):
    def setUp(self): self.observer = Observer(b'a' * 32)

    def observe(self, values, peer='127.0.0.6', method='POST'):
        return self.observer.observe(GcubePolicy(), values, method=method, peer_ip=peer)

    def rule(self, values, expected, peer='127.0.0.6'):
        effective, error, report = self.observe(values, peer)
        self.assertIsNone(effective); self.assertIsInstance(error, SecurityError)
        self.assertEqual(report['validation']['FAILED_VALIDATION_RULE'], expected)
        self.assertFalse(report['engine_ready']); self.assertEqual(report['gpu'], 'NOT_RUN')
        return report

    def test_pinned_source_and_all_twenty_two_failure_sites(self):
        self.assertEqual(hashlib.sha256(Path(proxy.__file__).read_bytes()).hexdigest(), EXPECTED_PROXY_SHA256)
        self.assertEqual(len(rule_catalog()), 22)

    def test_ipv4_ipv6_mapped_and_multiple_physical_xff(self):
        for value in ('203.0.113.8', '2001:db8::8', '::ffff:203.0.113.8',
                      '203.0.113.8, 10.42.0.2, ::1', ['203.0.113.8', '2001:db8::8']):
            with self.subTest(value=value):
                effective, error, report = self.observe(headers(X_Forwarded_For=value))
                self.assertIsNone(error); self.assertEqual(effective, 'https://e.gcube.ai:24999')
                self.assertEqual(report['validation']['status'], 'PASS')
        self.assertTrue(proxy.trusted_peer('::ffff:127.0.0.6'))

    def test_quoted_forwarded_ipv6_node_port_and_envoy(self):
        for address, node in [('203.0.113.8', '203.0.113.8:54321'),
                              ('2001:db8::8', '[2001:db8::8]:54321'),
                              ('::ffff:203.0.113.8', '[::ffff:203.0.113.8]:54321')]:
            effective, error, report = self.observe(headers(X_Forwarded_For=address,
                X_Envoy_External_Address=address,
                Forwarded='for="' + node + '";proto=https;host="e.gcube.ai:24999", for=10.42.0.2;proto=http'))
            self.assertIsNone(error); self.assertIsNotNone(effective)
            self.assertEqual(report['headers']['Forwarded']['values'][0]['entry_count'], 2)

    def test_internal_http_host_and_public_https_dynamic_port(self):
        effective, error, _ = self.observe(headers(Host='localhost:8000',
            X_Forwarded_Host='e.gcube.ai:24999', X_Forwarded_Port='24999'))
        self.assertIsNone(error); self.assertEqual(effective, 'https://e.gcube.ai:24999')
        effective, error, _ = self.observe(headers(Host='e.gcube.ai:8000', X_Forwarded_Port='24999'))
        self.assertIsNone(error); self.assertEqual(effective, 'https://e.gcube.ai:24999')

    def test_identifies_untrusted_peer_and_does_not_trust_claimed_xff(self):
        report = self.rule(headers(X_Forwarded_For='127.0.0.1'), 'FORWARDED_PEER_NOT_TRUSTED', peer='192.0.2.77')
        self.assertFalse(report['tcp_peer']['trusted_by_unchanged_v005'])

    def test_single_header_duplicates_and_comma_chains(self):
        for name in ('X_Forwarded_Host', 'X_Forwarded_Proto', 'X_Forwarded_Port', 'X_Envoy_External_Address'):
            for value, rule in [(['https', 'https'], 'SINGLE_HEADER_DUPLICATE'),
                                ('https, http', 'SINGLE_HEADER_WHITESPACE_OR_COMMA')]:
                with self.subTest(name=name, rule=rule): self.rule(headers(**{name: value}), rule)

    def test_specific_ip_header_family(self):
        for name, family in [('X_Forwarded_For', 'XFF'), ('X_Envoy_External_Address', 'X_ENVOY_EXTERNAL_ADDRESS')]:
            report = self.rule(headers(**{name: '203.0.113.8:54321'}), 'IP_NODE_FORMAT')
            self.assertEqual(report['validation']['header_family'], family)
        report = self.rule(headers(Forwarded='for="[invalid]:54321"'), 'IP_NODE_FORMAT')
        self.assertEqual(report['validation']['header_family'], 'FORWARDED_NODE')

    def test_admission_failure_matrix(self):
        cases = [
            ({'X_Forwarded_Proto':'http'}, 'GCUBE_INTERNAL_HTTP_PROFILE_MISMATCH'),
            ({'X_Forwarded_Port':'65536'}, 'PORT_FORMAT_OR_RANGE'),
            ({'X_Forwarded_For':'203.0.113.8,'}, 'CHAIN_EMPTY_OR_TOO_MANY_ENTRIES'),
            ({'X_Forwarded_For':'"203.0.113.8'}, 'CHAIN_QUOTE_SYNTAX'),
            ({'Forwarded':'for=203.0.113.8;for=203.0.113.8'}, 'FORWARDED_PARAMETER_SYNTAX_OR_DUPLICATE'),
            ({'Forwarded':'for=203.0.113.8;proto=ftp'}, 'FORWARDED_PROTO_VALUE'),
            ({'Forwarded':'for=203.0.113.8;proto=http'}, 'FORWARDED_FIRST_PROTO_NOT_HTTPS'),
            ({'Forwarded':'for=192.0.2.9;proto=https'}, 'FORWARDED_FOR_XFF_DISAGREE'),
            ({'X_Forwarded_Port':'25000'}, 'X_FORWARDED_PORT_AUTHORITY_DISAGREE'),
            ({'X_Forwarded_Host':'other.gcube.ai:24999'}, 'HOST_FORWARDED_AUTHORITY_DISAGREE'),
            ({'X_Forwarded_Host':'e.gcube.ai:24999', 'Forwarded':'for=203.0.113.8;proto=https;host="other.gcube.ai:24999"'}, 'FORWARDED_HOST_HEADERS_DISAGREE'),
            ({'Forwarded':'for=203.0.113.8;proto=https, for=10.42.0.2;host="other.gcube.ai:8000"'}, 'FORWARDED_LATER_HOST_DISAGREE'),
            ({'Origin':'https://attacker.example'}, 'ORIGIN_EFFECTIVE_OR_BOUND_AUTHORITY_MISMATCH'),
            ({'Host':'attacker.example'}, 'PUBLIC_OR_INTERNAL_HOST_NOT_ALLOWED'),
        ]
        for change, expected in cases:
            with self.subTest(expected=expected): self.rule(headers(**change), expected)

    def test_direct_functions_report_other_unreachable_or_low_level_rules(self):
        cases = [
            (lambda: proxy.list_header(headers(X_Forwarded_For=['1'] * 9), 'X-Forwarded-For'), 'CHAIN_FIELD_BOUNDS_OR_CONTROL'),
            (lambda: proxy.list_header(headers(X_Forwarded_For=['1'*3000]*2), 'X-Forwarded-For'), 'CHAIN_TOTAL_SIZE_LIMIT'),
            (lambda: proxy.forwarded_value('"invalid'), 'FORWARDED_UNCLOSED_QUOTED_VALUE'),
            (lambda: proxy.forwarded_value('"a\\b"'), 'FORWARDED_ESCAPED_VALUE'),
            (lambda: proxy.forwarded_value('[]'), 'FORWARDED_VALUE_TOKEN_SYNTAX'),
        ]
        for call, expected in cases:
            try: call()
            except SecurityError as error:
                self.assertEqual(failure_rule(error, self.observer.catalog)['FAILED_VALIDATION_RULE'], expected)
            else: self.fail('real validator did not reject')

    def test_masking_preserves_structure_and_address_correlations_without_raw_values(self):
        sentinel = 'NEVER_PRINT_PRIVATE_SECRET_7654321'
        values = headers(X_Forwarded_For='203.0.113.8, ::ffff:203.0.113.8',
            X_Forwarded_Host='private-workload.service.gcube.ai:24999',
            Forwarded='for="[2001:db8::8]:54321";proto=https;secret="'+sentinel+'"',
            Cookie=sentinel, Authorization='Bearer '+sentinel, X_Envoy_Internal=sentinel,
            X_Envoy_Custom_Secret=sentinel)
        report = self.observer.capture(values, '192.0.2.77')
        text = json.dumps(report)
        for raw in (sentinel, '203.0.113.8', '2001:db8::8', '192.0.2.77', 'private-workload', '54321', 'x-envoy-custom-secret'):
            self.assertNotIn(raw, text)
        entries = report['headers']['X-Forwarded-For']['values'][0]['entries']
        self.assertEqual(entries[0]['address_id'], entries[1]['address_id'])
        self.assertNotEqual(self.observer.tag('203.0.113.8'), Observer(b'b'*32).tag('203.0.113.8'))

    def test_typed_bounds_quoted_and_empty_entries(self):
        self.assertEqual(self.observer.chain('') ['entries'][0]['kind'], 'EMPTY')
        self.assertIsNone(self.observer.chain('a'*4097)['entry_count'])
        self.assertTrue(self.observer.chain(','.join(['203.0.113.8']*33))['truncated'])
        value = self.observer.ip_structure('"[::ffff:203.0.113.8]:54321"')
        self.assertEqual(value['kind'], 'IPV4_MAPPED_IPV6'); self.assertTrue(value['quoted'])
        self.assertTrue(value['has_port']); self.assertTrue(value['port_valid'])
        self.assertEqual(self.observer.ip_structure('fe80::1%eth0')['kind'], 'INVALID_OR_NON_IP')

    def test_masked_policy_addresses_expose_mapping_disagreement_without_trusting_peer(self):
        with patch.object(proxy, 'pod_addresses', return_value=frozenset({'10.42.0.9','127.0.0.1','::1'})):
            report = self.rule(headers(), 'FORWARDED_PEER_NOT_TRUSTED', peer='::ffff:10.42.0.9')
        self.assertFalse(report['tcp_peer']['trusted_by_unchanged_v005'])
        self.assertIn(report['tcp_peer']['address_id'],
                      [entry['address_id'] for entry in report['trusted_peer_policy']['addresses']])
        self.assertNotIn('10.42.0.9', json.dumps(report))


if __name__ == '__main__': unittest.main()
