"""Approval and persisted input certificates cannot bypass render eligibility."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))
from engine.planner import generate_plan
from engine.schema import validate_plan
from engine.storage import EngineError, ProjectStore
from engine.visibility import semantic_input_hash


class MandatoryVisibilityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = dict(topic='뉴욕에서 런던을 거쳐 두바이까지 이어지는 항공 여행',
                           duration=20, quality='HIGH', tts=False, subtitles=False, bgm=True)
        cls.plan = generate_plan(cls.request)

    def test_saved_pass_cannot_override_current_failed_certificate(self):
        plan = deepcopy(self.plan)
        plan['gate'] = {'passed': True, 'semantic_visibility': {'passed': True}}
        failure = {'passed': False, 'failures': [{'code': 'GEOGRAPHIC_EVENT_NOT_VISIBLE',
                                                'scene_id': 'S002', 'event_id': 'E006'}]}
        with patch('engine.visibility.certify_semantic_visibility', return_value=failure):
            report = validate_plan(plan)
        self.assertFalse(report['passed'])
        self.assertIn('GEOGRAPHIC_EVENT_NOT_VISIBLE', [e['code'] for e in report['errors']])

    def test_invalid_coordinates_never_enter_renderer_preflight(self):
        plan = deepcopy(self.plan)
        plan['scenes'][0]['coordinates']['lat'] = 91
        with patch('engine.visibility.certify_semantic_visibility') as certifier:
            self.assertFalse(validate_plan(plan)['passed'])
            certifier.assert_not_called()

    def test_storage_certifies_normalized_inputs_and_approval_rechecks(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(directory)
            saved = store.create(self.request, deepcopy(self.plan))
            plan = saved['plan']
            self.assertTrue(plan['gate']['passed'], plan['gate']['errors'])
            self.assertEqual(plan['gate']['semantic_visibility']['semantic_input_sha256'],
                             semantic_input_hash(plan))
            self.assertIn('render_context', plan)
            failed = {'passed': False, 'failures': [{'code': 'SEMANTIC_CERTIFICATION_FAILED'}]}
            with patch('engine.visibility.certify_semantic_visibility', return_value=failed):
                with self.assertRaises(EngineError) as error:
                    store.approve(saved['project']['id'], 'v001', plan['plan_hash'])
            self.assertEqual(error.exception.code, 'PLAN_GATE_FAILED')
            self.assertFalse((store.version_path(saved['project']['id'], 'v001')/'approval.json').exists())


if __name__ == '__main__':
    unittest.main()
