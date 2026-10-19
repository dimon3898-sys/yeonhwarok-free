"""Synthetic CPU tests of read-only collection and output allowlists; no GPU run."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace
import unittest

import read_policy as module

NOW = datetime(2026, 10, 19, 0, tzinfo=timezone.utc)
SECRET = 'test-only-sensitive-value-never-published'


def policy(**changes):
    value = {'validUntil': '2026-10-20T00:00:00+09:00', 'maxWallSeconds': 3600,
        'maxRetries': 0, 'maxCostAmount': '1000', 'currency': 'KRW', 'gpuHourlyRate': '910'}
    value.update(changes)
    return value


def container(raw_policy=None):
    return {'containerEnvs': [{module.PREFIX + 'OPERATOR_POLICY_JSON': json.dumps(policy()) if raw_policy is None else raw_policy},
        {module.PREFIX + 'OWNER_CODE': SECRET}, {'DROPBOX_TOKEN': SECRET},
        {'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': module.DIGEST},
        {module.PREFIX + 'STATE_ROOT': '/var/lib/world-engine-private/engine/studio-no-backup-80s-v1'}]}


class API:
    def __init__(self):
        self.calls = []
        self.raw = {'ser': 5373, 'state': 'deploy', 'containerArray': [container()],
            'gpuSpecArray': [{'gpu': 'RTX5090', 'vram': 32, 'price': 910, 'maxPrice': 1300}],
            'maxPrice': 1300, 'irrelevantSecret': SECRET}
        self.item = SimpleNamespace(price=1300, usage_price=910, currency_unit='KRW',
            product_name='RTX 5090', product_code='tier2', availability=True)
    def describe(self, workload):
        self.calls.append(('describe', workload)); print(SECRET)
        return SimpleNamespace(raw=self.raw)
    def get_indexed_gpu_pricings(self, service_code):
        self.calls.append(('pricing', service_code)); return [('001', self.item)]


class Tests(unittest.TestCase):
    def test_two_reads_only_typed_policy_and_prices_without_credentials(self):
        api = API()
        result = module.collect({'GCUBE_ACCESS_TOKEN': SECRET}, factory=lambda _: api,
            matcher=lambda spec, indexed: indexed[0], now=NOW)
        self.assertEqual(api.calls, [('describe', '5373'), ('pricing', 'gcube')])
        self.assertEqual(result['status'], 'READ_ONLY_SETTINGS_AND_CATALOGUE_COLLECTED')
        parsed = result['configuration']['operatorPolicy']
        self.assertTrue(parsed['configuredTimeFitsCostCap'])
        self.assertFalse(parsed['fourHoursFitsCostCap'])
        self.assertEqual(parsed['policy'], policy())
        self.assertEqual(result['gpuPricing']['catalogue']['usagePrice'], 910)
        self.assertFalse(result['gpuPricing']['actualBilledHourlyRateVerified'])
        self.assertNotIn(SECRET, json.dumps(result))
        for key in ('paidOperations', 'stateChanges', 'jobCreated', 'renderInvoked', 'gpuProbeRun'):
            self.assertFalse(result[key])

    def test_policy_rejects_untyped_duplicates_bad_time_and_secret_injection(self):
        bad = [json.dumps(policy(gpuHourlyRate=SECRET)), json.dumps(policy(validUntil=SECRET)),
            json.dumps(policy(currency=SECRET)), json.dumps(policy(maxRetries=True)),
            json.dumps(policy(validUntil='2026-10-20T00:00:00')), json.dumps(policy())[:-1] + ',"maxRetries":1}']
        for raw in bad:
            with self.subTest(raw=raw):
                result = module.configuration(container(raw), NOW)
                self.assertEqual(result['operatorPolicy']['status'], 'MISSING_OR_INVALID_POLICY')
                self.assertNotIn(SECRET, json.dumps(result))
        value = container(); value['containerEnvs'].append({module.PREFIX + 'OWNER_CODE': SECRET})
        self.assertFalse(module.configuration(value, NOW)['environmentShapeVerified'])

    def test_expiry_budget_and_unsafe_path_are_reported_without_authorization(self):
        floating = module.configuration(container(json.dumps(policy(gpuHourlyRate=910.0, maxCostAmount=1000.0))), NOW)
        self.assertEqual(floating['operatorPolicy']['policy']['gpuHourlyRate'], 910.0)
        self.assertTrue(floating['operatorPolicy']['configuredTimeFitsCostCap'])
        value = container(json.dumps(policy(validUntil='2026-10-18T00:00:00+09:00', maxWallSeconds=14400)))
        value['containerEnvs'][-1] = {module.PREFIX + 'STATE_ROOT': '/world-storage/' + SECRET}
        result = module.configuration(value, NOW)
        self.assertTrue(result['operatorPolicy']['expired'])
        self.assertFalse(result['operatorPolicy']['configuredTimeFitsCostCap'])
        self.assertIsNone(result['stateRoot'])
        self.assertNotIn(SECRET, json.dumps(result))
        api = API(); api.item.product_name = SECRET; api.item.currency_unit = SECRET
        result = module.pricing_summary(api.raw['gpuSpecArray'][0], api.raw, [], lambda *_: ('', api.item))
        self.assertIsNone(result['catalogue']['product'])
        self.assertIsNone(result['catalogue']['currency'])
        self.assertNotIn(SECRET, json.dumps(result))

    def test_missing_secret_and_sdk_failure_do_not_expose_raw_error(self):
        self.assertEqual(module.collect({}, now=NOW)['blockingReason'], 'APPROVED_REPOSITORY_SECRET_REQUIRED')
        def broken(_):
            print(SECRET)
            raise RuntimeError(SECRET)
        result = module.collect({'GCUBE_ACCESS_TOKEN': SECRET}, factory=broken, now=NOW)
        self.assertEqual(result['blockingReason'], 'UNEXPECTED_ERROR')
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertFalse(result['renderInvoked'])


if __name__ == '__main__':
    unittest.main()
