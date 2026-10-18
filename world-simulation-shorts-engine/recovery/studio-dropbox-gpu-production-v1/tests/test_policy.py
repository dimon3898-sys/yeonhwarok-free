"""Four-hour support through unchanged validators; no GPU or provider request.

Synthetic budgets below are test inputs, not gCube prices or owner approvals.
The suite runs against inherited immutable source paths in the CPU container.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

PROFILE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROFILE))


class FourHourPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from production_runtime import install
        cls.old = install()
        cls.controller = cls.old.parent.load_file(
            '_production_four_hour_frozen_controller',
            cls.old.parent.STUDIO / 'studio_controller.py',
            'c2e0d94a31cd90569d29f944da1a538c9efcf77d15cd0f2bfacbe99396ae053c')
        cls.coordinator = cls.old.parent.load_file(
            '_production_four_hour_frozen_coordinator',
            cls.old.parent.RECOVERY / 'universal-auto-video-v2/orchestrator.py',
            '2e1e9d76c6ecf760f69fa2204c80d91da251fa0ee2abf8ed7cf3fe2388afcca4')

    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.policy = {'validUntil': (self.now + timedelta(hours=8)).isoformat(),
                       'maxWallSeconds': 14400, 'maxRetries': 0,
                       'maxCostAmount': '12.00', 'currency': 'USD',
                       'gpuHourlyRate': '3.00'}
        self.plan = {'renderProfile': {'imageDigest': 'sha256:' + 'a' * 64},
                     'fixture': 'FOCUSED_CPU_POLICY_VALIDATION_ONLY'}

    def read_policy(self, policy):
        class Reader:
            def json(self, name, optional=False):
                if name != 'operator_policy.json':
                    raise AssertionError('Unexpected policy read')
                return policy
        return self.controller.StudioController._policy(None, Reader())

    def approval(self, policy=None):
        return {'schema': self.coordinator.AUTH_SCHEMA, 'approved': True,
                'planSHA256': self.coordinator.canonical_sha256(self.plan),
                'imageDigest': self.plan['renderProfile']['imageDigest'],
                **deepcopy(self.policy if policy is None else policy)}

    def check_approval(self, approval):
        return self.coordinator.validate_approval(approval, self.plan, now=self.now)

    def assert_code(self, expected, action):
        with self.assertRaises(Exception) as caught:
            action()
        self.assertEqual(getattr(caught.exception, 'code', None) or str(caught.exception), expected)

    def test_studio_accepts_14400_at_exact_four_hour_budget(self):
        result = self.read_policy(self.policy)
        self.assertEqual(result['maxWallSeconds'], 14400)
        self.assertEqual(result['maxCostAmount'], '12.00')
        self.assertEqual(result['maxRetries'], 0)

    def test_coordinator_accepts_same_14400_approval(self):
        approval = self.approval()
        self.assertEqual(self.check_approval(approval), approval)

    def test_studio_rejects_budget_below_four_hours(self):
        policy = {**self.policy, 'maxCostAmount': '11.99'}
        self.assert_code('STUDIO_COST_LIMIT_EXCEEDED', lambda: self.read_policy(policy))

    def test_coordinator_rejects_budget_below_four_hours(self):
        approval = self.approval({**self.policy, 'maxCostAmount': '11.99'})
        self.assert_code('TIME_CEILING_EXCEEDS_APPROVED_COST', lambda: self.check_approval(approval))

    def test_studio_rejects_expired_policy(self):
        policy = {**self.policy, 'validUntil': (self.now - timedelta(seconds=1)).isoformat()}
        self.assert_code('STUDIO_OPERATOR_POLICY_EXPIRED', lambda: self.read_policy(policy))

    def test_coordinator_rejects_expired_approval(self):
        approval = self.approval({**self.policy, 'validUntil': (self.now - timedelta(seconds=1)).isoformat()})
        self.assert_code('GPU_APPROVAL_EXPIRED', lambda: self.check_approval(approval))

    def test_studio_requires_explicit_expiry_timezone(self):
        policy = {**self.policy, 'validUntil': '2099-01-01T00:00:00'}
        self.assert_code('STUDIO_OPERATOR_POLICY_INVALID', lambda: self.read_policy(policy))

    def test_coordinator_requires_explicit_expiry_timezone(self):
        approval = self.approval({**self.policy, 'validUntil': '2099-01-01T00:00:00'})
        self.assert_code('GPU_APPROVAL_EXPIRY_INVALID', lambda: self.check_approval(approval))

    def test_validating_new_policy_does_not_mutate_its_input(self):
        before = deepcopy(self.policy)
        self.read_policy(self.policy)
        self.assertEqual(self.policy, before)

    def test_new_policy_does_not_extend_original_one_hour_approval(self):
        original = self.approval({**self.policy, 'maxWallSeconds': 3600})
        before = deepcopy(original)
        self.read_policy(self.policy)
        self.check_approval(self.approval())
        self.check_approval(original)
        self.assertEqual(original, before)
        self.assertEqual(original['maxWallSeconds'], 3600)

    def test_failed_validation_does_not_rewrite_original_approval(self):
        original = self.approval({**self.policy, 'maxCostAmount': '11.99'})
        before = deepcopy(original)
        self.assert_code('TIME_CEILING_EXCEEDS_APPROVED_COST', lambda: self.check_approval(original))
        self.assertEqual(original, before)

    def test_retry_limits_remain_enforced(self):
        policy = {**self.policy, 'maxRetries': 3}
        self.assert_code('STUDIO_OPERATOR_POLICY_INVALID', lambda: self.read_policy(policy))
        self.assert_code('BOUNDED_APPROVAL_REQUIRED', lambda: self.check_approval(self.approval(policy)))


if __name__ == '__main__':
    unittest.main()
