"""Focused CPU bridge/entry tests; no browser, GPU, container or paid work."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


bridge = load('_reconcile_test_bridge', 'runtime_bridge.py')


def submission(*, scalar=False, national=False):
    return {'overnightV3': {'visualExtensions': {
        'schema': 'WORLD_ENGINE_OVERNIGHT_VISUAL_V1',
        'scalarTerritory': {'sourceRef': 'TEST_ONLY_SOURCE'} if scalar else None,
        'nationalUnits': {'sourceRef': 'TEST_ONLY_SOURCE'} if national else None}}}


def context(*, scalar=False, national=False):
    return {'selectedVisualAdmission': {'status': 'CPU_ADMITTED',
        'scalarControlSelected': scalar, 'nationalUnitsSelected': national},
        'imagePackageIncluded': True, 'dataAdmitted': True, 'dataBlockers': [],
        'sourceManifestSHA256': 'test-only-original-manifest',
        'preview': {'startFrame': 1400, 'endFrame': 1550}}


class RuntimeGuardWiring(unittest.TestCase):
    def test_null_selections_return_exact_previous_context_without_new_approval(self):
        original = context()
        before = deepcopy(original)
        with patch.object(bridge, '_preserved_gate_context', return_value=original):
            result = bridge.gate_context(submission(), image_digest='test-only-image')
        self.assertIs(result, original)
        self.assertEqual(result, before)
        self.assertNotIn('nativeGuardApprovedRendering', result)

    def test_source_admission_runs_before_guard_and_exact_receipt_is_forwarded(self):
        calls = []
        old_context = context()
        def original(*args, **kwargs):
            calls.append('source')
            return old_context
        def guard(value, *, source_admission):
            calls.append('native')
            self.assertIs(source_admission, old_context['selectedVisualAdmission'])
            self.assertEqual(value, submission()['overnightV3']['visualExtensions'])
        with patch.object(bridge, '_preserved_gate_context', side_effect=original), \
             patch.object(bridge.capabilities, 'guard_native_selection', side_effect=guard):
            bridge.gate_context(submission(), image_digest='test-only-image')
        self.assertEqual(calls, ['source', 'native'])

    def test_original_source_failure_is_not_hidden_or_replaced(self):
        with patch.object(bridge, '_preserved_gate_context', side_effect=RuntimeError('SOURCE_UNAVAILABLE')), \
             patch.object(bridge.capabilities, 'guard_native_selection') as guard:
            with self.assertRaisesRegex(RuntimeError, '^SOURCE_UNAVAILABLE$'):
                bridge.gate_context(submission(), image_digest='test-only-image')
        guard.assert_not_called()

    def test_preflight_blocks_admitted_scalar_before_gpu_manager(self):
        with patch.object(bridge, '_preserved_gate_context', return_value=context(scalar=True)), \
             patch.object(bridge.preserved, 'load', side_effect=AssertionError('GPU_MANAGER_MUST_NOT_LOAD')) as loader:
            result = bridge.preflight(submission(scalar=True), control_root=Path('/unused'),
                export_root=Path('/unused'), image_digest='test-only-image')
        self.assertFalse(result['renderAllowed'])
        self.assertFalse(result['gpuRenderingVerified'])
        self.assertFalse(result['full80Allowed'])
        self.assertEqual(result['checks'][0]['code'], 'RECONCILE_NATIVE_SCALAR_COMPOSITION_UNAVAILABLE')
        loader.assert_not_called()

    def test_direct_start_blocks_same_scalar_before_manager_or_gpu(self):
        with patch.object(bridge, '_preserved_gate_context', return_value=context(scalar=True)), \
             patch.object(bridge.preserved, 'load', side_effect=AssertionError('GPU_MANAGER_MUST_NOT_LOAD')) as loader:
            with self.assertRaisesRegex(RuntimeError, '^RECONCILE_NATIVE_SCALAR_COMPOSITION_UNAVAILABLE$'):
                bridge.start_studio_job(submission(scalar=True), Path('/unused-approval'), {}, 'test-only-request',
                    control_root=Path('/unused'), export_root=Path('/unused'), image_digest='test-only-image')
        loader.assert_not_called()

    def test_capture_prepare_blocks_same_scalar_before_capture_identity(self):
        with patch.object(bridge, '_preserved_gate_context', return_value=context(scalar=True)), \
             patch.object(bridge.preserved, 'load', side_effect=AssertionError('CAPTURE_MUST_NOT_PREPARE')) as loader:
            with self.assertRaisesRegex(RuntimeError, '^RECONCILE_NATIVE_SCALAR_COMPOSITION_UNAVAILABLE$'):
                bridge.prepare_runtime_request(submission(scalar=True),
                    image_digest='test-only-image', control_root=Path('/unused'))
        loader.assert_not_called()

    def test_national_source_admission_mismatch_remains_blocked(self):
        with patch.object(bridge, '_preserved_gate_context', return_value=context()), \
             patch.object(bridge.preserved, 'load', side_effect=AssertionError('GPU_MANAGER_MUST_NOT_LOAD')) as loader:
            result = bridge.preflight(submission(national=True), control_root=Path('/unused'),
                export_root=Path('/unused'), image_digest='test-only-image')
        self.assertFalse(result['renderAllowed'])
        self.assertEqual(result['checks'][0]['code'], 'RECONCILE_NATIVE_SOURCE_ADMISSION_MISMATCH')
        loader.assert_not_called()

    def test_null_selection_still_requires_old_image_data_and_gpu_gates(self):
        manager = types.SimpleNamespace(preflight=Mock(return_value={
            'checks': [{'name': 'ORIGINAL_GPU_ADMISSION', 'status': 'BLOCKED', 'code': 'TEST_ONLY_NO_GPU'}]}))
        with patch.object(bridge, '_preserved_gate_context', return_value=context()), \
             patch.object(bridge.preserved, 'load', return_value=manager):
            result = bridge.preflight(submission(), control_root=Path('/unused'),
                export_root=Path('/unused'), image_digest='test-only-image')
        manager.preflight.assert_called_once()
        self.assertFalse(result['renderAllowed'])
        self.assertEqual(result['checks'][-1]['code'], 'TEST_ONLY_NO_GPU')

    def test_no_new_manager_or_renderer_function_was_substituted(self):
        self.assertIs(bridge.preflight, bridge.preserved.preflight)
        self.assertIs(bridge.start_studio_job, bridge.preserved.start_studio_job)
        self.assertIs(bridge.prepare_runtime_request, bridge.preserved.prepare_runtime_request)
        self.assertIs(bridge.preserved.gate_context, bridge.gate_context)


class ThinStudioAndBootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller = load('_reconcile_test_controller', 'studio_controller.py')
        cls.entry = load('_reconcile_test_entry', 'studio_entry.py')
        cls.boot = load('_reconcile_test_boot', 'bootstrap.py')

    def test_controller_injects_only_bridge_and_keeps_original_namespace_owner(self):
        with patch.object(self.controller.preserved.StudioController, '__init__', return_value=None) as constructor:
            self.controller.StudioController(control_root=Path('/unchanged-private-root'),
                export_root=Path('/unchanged-export'), image_digest='test-only-image', backend='test-only-backend')
        self.assertEqual(constructor.call_args.kwargs['control_root'], Path('/unchanged-private-root'))
        self.assertIs(constructor.call_args.kwargs['bridge_module'], self.controller.bridge)
        self.assertEqual(constructor.call_args.kwargs['backend'], 'test-only-backend')

    def test_original_normalization_policy_retry_and_revision_owners_retained(self):
        for name in ('_normal', '_policy', '_preflight_record', 'resume', 'revise'):
            self.assertIs(getattr(self.controller.StudioController, name),
                          getattr(self.controller.preserved.StudioController, name))

    def test_https_application_changes_controller_factory_only(self):
        with patch.object(self.entry._PreservedApplication, '__init__', return_value=None) as constructor:
            self.entry.Application('state', 'owner', 'export', initial_origin='https://example.invalid')
        self.assertIs(constructor.call_args.kwargs['controller_factory'], self.entry.controller.StudioController)
        self.assertEqual(constructor.call_args.kwargs['initial_origin'], 'https://example.invalid')
        self.assertIs(self.entry.Application.handler, self.entry._PreservedApplication.handler)

    def test_bootstrap_changes_only_exact_supervised_child_target(self):
        boot = self.boot
        expected = ['/usr/bin/python3', '-B', str(boot._owner.parent.parent.root / 'https_server.py')]
        command = [*expected, '--state-root', '/private-test-only']
        environment = {'TEST_ONLY_NON_SECRET': 'unchanged'}
        with patch.object(boot, '_preserved_spawn', return_value='child') as spawn:
            self.assertEqual(boot.spawn(command, env=environment, user=1000, group=1000), 'child')
        forwarded = spawn.call_args.args[0]
        self.assertEqual(forwarded, [*command[:2], str(HERE / 'studio_entry.py'), *command[3:]])
        self.assertIs(spawn.call_args.kwargs['env'], environment)
        self.assertEqual(spawn.call_args.kwargs['user'], 1000)
        self.assertEqual(spawn.call_args.kwargs['group'], 1000)
        self.assertEqual(boot._owner.HERE, boot.PRESERVED)

    def test_other_commands_are_not_rewritten(self):
        command = ['/usr/bin/python3', '-B', '/different/https_server.py']
        with patch.object(self.boot, '_preserved_spawn', return_value=None) as spawn:
            self.boot.spawn(command)
        self.assertEqual(spawn.call_args.args[0], command)

    def test_bootstrap_new_manifest_precedes_original_secure_bootstrap(self):
        order = []
        manifest = types.SimpleNamespace(verify_sources=lambda: order.append('new-manifest'))
        with patch.object(self.boot, '_load', return_value=manifest), \
             patch.object(self.boot._preserved_bootstrap, 'main', side_effect=lambda argv: order.append(('old-main', argv))):
            self.boot.main(['--test-only-args'])
        self.assertEqual(order, ['new-manifest', ('old-main', ['--test-only-args'])])


if __name__ == '__main__':
    unittest.main()
