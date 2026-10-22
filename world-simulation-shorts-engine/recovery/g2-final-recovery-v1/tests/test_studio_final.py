"""Focused final glue tests: opt-in compatibility, hard gates and source binding."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


adapter = load('_test_g2_final_layout_adapter', HERE / 'layout_adapter.py')
contract = load('_test_g2_final_source_contract', HERE / 'source_contract.py')
controller = load('_test_g2_final_controller', HERE / 'studio_controller.py')
worker = load('_test_g2_final_worker', HERE / 'software_worker.py')
PROFILE = json.loads((HERE / 'fixtures/LAYOUT_PROFILE.json').read_bytes())


def plan():
    return {'layout': {'canonical': [1080, 1920], 'safe': [48, 72, 1032, 1848],
            'measured': {'location': {'gap': 18, 'fontSize': 36}}},
            'scale': {'information': {'location': True, 'country': True}},
            'geometry': {'primary': 'generic-source-geometry'},
            'camera': {'unchanged': True}}


def gates():
    return {'baselineCommit': controller.BASELINE,
            **{'phase' + p: {'status': 'PASS'} for p in 'ABC'}, 'historicalG3': 'BLOCKED',
            'paidGpuExecuted': False}


class LayoutAdapterTests(unittest.TestCase):
    def test_absent_policy_preserves_existing_scene_contract(self):
        original = plan()
        before = deepcopy(original)
        self.assertIsNone(adapter.validate_location_policy(original))
        self.assertEqual(original, before)

    def test_explicit_policy_adds_only_one_field_and_preserves_active_label(self):
        original = plan()
        before = deepcopy(original)
        after, receipt = adapter.apply_location_policy(original, PROFILE)
        self.assertEqual(original, before)
        self.assertTrue(after['scale']['information']['location'])
        self.assertEqual(after['layout'].pop('locationPlacement'), PROFILE)
        self.assertEqual(after, before)
        self.assertTrue(receipt['activeLocationPreserved'])
        self.assertFalse(receipt['sourceGeometryChanged'])

    def test_unknown_or_disabling_policy_fields_are_not_ignored(self):
        for extra in [{'disableCollision': True}, {'location': False}, {'country': 'NPL'}]:
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'POLICY_INVALID'):
                adapter.apply_location_policy(plan(), {**PROFILE, **extra})
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_POLICY_REQUIRED'):
            adapter.apply_location_policy(plan(), None)

    def test_out_of_range_or_nonfinite_search_bounds_fail(self):
        for key, value in [('maxGap', 217), ('maxGap', 17), ('maxGap', float('nan')),
                           ('maxGap', True), ('step', 3), ('step', 33), ('step', True), ('step', 8.5)]:
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'BOUNDS_INVALID'):
                adapter.apply_location_policy(plan(), {**PROFILE, key: value})

    def test_profile_does_not_allow_a_silenced_native_location_role(self):
        invalid = plan()
        invalid['scale']['information']['location'] = False
        with self.assertRaisesRegex(ValueError, 'ACTIVE_LOCATION_REQUIRED'):
            adapter.apply_location_policy(invalid, PROFILE)

    def test_incompatible_existing_policy_is_an_explicit_conflict(self):
        original = plan()
        original['layout']['locationPlacement'] = {**PROFILE, 'step': 8}
        with self.assertRaisesRegex(ValueError, 'EXISTING_POLICY_CONFLICT'):
            adapter.apply_location_policy(original, PROFILE)


class GateTests(unittest.TestCase):
    def test_all_abc_gates_and_g3_block_are_mandatory(self):
        self.assertTrue(all(row['status'] == 'PASS' for row in controller.final_gate_checks(gates())))
        for phase in 'ABC':
            invalid = gates()
            invalid['phase' + phase]['status'] = 'FAIL'
            self.assertFalse(all(row['status'] == 'PASS' for row in controller.final_gate_checks(invalid)))
        for invalid in [None, {}, {**gates(), 'baselineCommit': 'old'},
                        {**gates(), 'historicalG3': 'PASS'}, {**gates(), 'paidGpuExecuted': True}]:
            self.assertFalse(all(row['status'] == 'PASS' for row in controller.final_gate_checks(invalid)))

    def test_preflight_has_no_historical_or_paid_permission(self):
        instance = object.__new__(controller.StudioController)
        prior = {'ready': True, 'checks': [{'name': 'PRESERVED', 'status': 'PASS'}]}
        with patch.object(controller.reused.StudioController, '_preflight_record', return_value=prior), \
             patch.object(controller, 'current_gate_checks', return_value=controller.final_gate_checks(gates())):
            result = instance._preflight_record(None, {'submission': {'schema': contract.SCHEMA}})
        self.assertTrue(result['ready'])
        self.assertFalse(result['paidRenderAllowed'])
        self.assertFalse(result['historicalRenderAllowed'])
        self.assertEqual((result['maxWallSeconds'], result['maxRetries']), (900, 0))

    def test_reused_worker_and_start_bodies_keep_original_security_path(self):
        old = HERE.parent / 'universal-source-pipeline-v2'
        self.assertEqual(Path(controller.reused.StudioController.start.__code__.co_filename),
                         old / 'studio_controller.py')
        self.assertEqual(Path(worker.reused.run.__code__.co_filename), old / 'software_worker.py')
        self.assertIs(worker.validate_package, worker.reused.validate_package)
        self.assertIs(worker.validate_capture, worker.reused.validate_capture)
        self.assertEqual(worker.reused.HERE, HERE)

    def test_repository_and_known_old_state_roots_reject_before_creation(self):
        for path in [HERE / 'state/control', Path('/workspace/source-studio-private-20261022-d/state/control'),
                     Path('/workspace/g2-recovery-studio-private-20261022/state/control')]:
            with self.subTest(path=path), self.assertRaisesRegex(controller.StudioError, 'SEPARATE_PRIVATE_STATE'):
                controller.StudioController(control_root=path)


class SourceContractTests(unittest.TestCase):
    def normalized(self, *, mode='SYNTHETIC_TEST', total=180):
        return {'schema': contract.SCHEMA, 'sourcePipeline': {'ready': True, 'mode': mode,
            'scope': 'SYNTHETIC_TECHNICAL_DEMO', 'totalFrames': total, 'startFrame': 0,
            'requestSHA256': 'a' * 64, 'sourceIndexSHA256': 'b' * 64, 'sourceStyleSHA256': 'c' * 64,
            'runtimePayload': {'nativePlan': plan()}}}

    def test_normalization_keeps_old_scene_parser_and_binds_new_profile_signature(self):
        value = {'explicit': 'unit fixture; not a valid production Scene'}
        result = self.normalized()
        with patch.object(contract.original, 'normalize_submission', return_value=result) as reused, \
             patch.object(contract, 'final_bindings', return_value=[]):
            out = contract.normalize_submission(value, source_root='/unit-explicit-fake', expected_index_sha256='b' * 64)
        reused.assert_called_once_with(value, source_root='/unit-explicit-fake', expected_index_sha256='b' * 64)
        pipeline = out['sourcePipeline']
        self.assertEqual(pipeline['runtimePayload']['nativePlan']['layout']['locationPlacement'], PROFILE)
        self.assertTrue(pipeline['runtimePayload']['nativePlan']['scale']['information']['location'])
        self.assertEqual(len(pipeline['captureSignature']), 64)
        self.assertEqual(pipeline['layoutProfile'], PROFILE)
        self.assertFalse(pipeline['finalRecoveryScope']['historicalRenderAllowed'])

    def test_wrong_mode_length_or_unready_result_cannot_create_final_scope(self):
        for change in [{'mode': 'PRODUCTION'}, {'totalFrames': 179}, {'ready': False}]:
            value = self.normalized()
            value['sourcePipeline'].update(change)
            with self.subTest(change=change), \
                 patch.object(contract.original, 'normalize_submission', return_value=value), \
                 self.assertRaisesRegex(ValueError, 'SYNTHETIC_SIX_SECONDS_ONLY'):
                contract.normalize_submission({}, source_root='/unit-explicit-fake', expected_index_sha256='b' * 64)


if __name__ == '__main__':
    unittest.main()
