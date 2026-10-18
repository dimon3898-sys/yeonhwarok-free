import importlib.util
import json
from pathlib import Path
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('proxy_remote_evidence', ROOT / 'remote.py')
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)


class ReadOnlyEvidenceTests(unittest.TestCase):
    def test_missing_secret_never_initializes_client(self):
        def factory(_):
            self.fail('client must not initialize')
        result = remote.collect_rest({}, factory=factory)
        self.assertEqual(result['blocking_reason'], 'APPROVED_SECRET_CREDENTIAL_NOT_PROVIDED')

    def test_safe_configuration_never_exports_owner_policy_or_token(self):
        owner = 'TEST_ONLY_NEVER_PUBLISH_OWNER'
        container = {'containerEnvs': [{'WORLD_ENGINE_STUDIO_OWNER_CODE': owner},
            {'WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN': remote.EXPECTED_ORIGIN},
            {'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': remote.EXPECTED_DIGEST}],
            'containerImage': remote.PREFIX + ':' + remote.EXPECTED_TAG,
            'serviceUrl': remote.EXPECTED_ORIGIN, 'port': 8080, 'containerCommand': ''}
        result = remote.current_configuration(container)
        self.assertNotIn(owner, json.dumps(result))
        self.assertNotIn(remote.EXPECTED_ORIGIN, json.dumps(result))
        self.assertTrue(result['configuration_checks']['configured_image_matches_https_baseline'])
        self.assertTrue(result['configuration_checks']['image_digest_matches_https_baseline'])
        self.assertTrue(result['configuration_checks']['origin_matches_user_confirmed_service'])

    def test_only_authorized_read_methods_and_closed_error_values(self):
        calls = []
        class API:
            def describe(self, ser):
                calls.append(('describe', ser))
                return SimpleNamespace(raw={'ser': '5373', 'state': 'deploy', 'containerArray': []})
            def pods(self, ser):
                calls.append(('pods', ser))
                return [{'name': 'authorized-existing-pod', 'status': 'Running'}]
            def logs(self, ser, pod):
                calls.append(('logs', ser, pod))
                return json.dumps({'records': [{'errorCode': 'INVALID_FORWARDED_HEADERS',
                    'token': 'TEST_ONLY_PRIVATE_TOKEN', 'headers': {'Host': 'PRIVATE_HOST'}}]})
        result = remote.collect_rest({'GCUBE_ACCESS_TOKEN': 'TEST_ONLY_TOKEN'}, factory=lambda token: API())
        self.assertEqual([x[0] for x in calls], ['describe', 'pods', 'logs'])
        self.assertEqual(result['proxy_errors'][0]['error_code'], 'INVALID_FORWARDED_HEADERS')
        self.assertFalse(result['actual_proxy_headers_available'])
        raw = json.dumps(result)
        for private in ('TEST_ONLY_PRIVATE_TOKEN', 'TEST_ONLY_TOKEN', 'PRIVATE_HOST'):
            self.assertNotIn(private, raw)
        self.assertEqual(result['state_changes'], 0)
        self.assertEqual(result['paid_operations'], 0)

    def test_unknown_error_and_exception_details_withheld(self):
        class API:
            def describe(self, ser):
                raise ValueError('PRIVATE_SECRET_MUST_NOT_ESCAPE')
        result = remote.collect_rest({'GCUBE_ACCESS_TOKEN': 'TEST_ONLY_TOKEN'}, factory=lambda token: API())
        self.assertNotIn('PRIVATE_SECRET_MUST_NOT_ESCAPE', json.dumps(result))
        self.assertEqual(result['blocking_reason'], 'UNEXPECTED_ERROR')
        self.assertEqual(remote.safe_proxy_errors([{'errorCode': 'PRIVATE_SECRET'}]), [])

    def test_duplicate_environment_rows_fail_closed(self):
        result = remote.current_configuration({'containerEnvs': [{'X': 'a'}, {'X': 'b'}]})
        self.assertFalse(result['environment_shape_verified'])
        self.assertIsNone(result['configuration_checks'])


if __name__ == '__main__':
    unittest.main()
