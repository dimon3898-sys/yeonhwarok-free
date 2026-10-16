"""CPU bridge tests only; inherited GPU admission is not executed or replaced."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import subprocess
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


coordinator = load('_test_production_coordinator_bridge', 'orchestrator.py')
hardware = load('_test_production_hardware_bridge', 'render_adapter.py')


class ExecutionBridgeTests(unittest.TestCase):
    def test_frozen_coordinator_bytes_and_original_function_owner(self):
        old = ROOT.parent / 'universal-auto-video-v2/orchestrator.py'
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(), coordinator.PARENT_SHA256)
        self.assertEqual(Path(coordinator._parent_run_job.__code__.co_filename), old)
        self.assertEqual(coordinator.parent.HERE, ROOT)
        self.assertEqual(coordinator.parent.CONTROL_ROOT, coordinator.CONTROL_ROOT)
        self.assertNotIn('universal-video-v2', str(coordinator.CONTROL_ROOT))

    def test_fixed_modules_are_restored_after_scoped_dispatch(self):
        before = {name: sys.modules.get(name) for name in ('orchestrator', 'render_adapter')}
        with mock.patch.object(coordinator, '_adapter', hardware):
            with coordinator._fixed_entry_modules():
                self.assertIs(sys.modules['orchestrator'], coordinator)
                self.assertIs(sys.modules['render_adapter'], hardware)
        self.assertEqual({name: sys.modules.get(name) for name in before}, before)

    def test_programmatic_run_checks_source_and_plan_then_delegates(self):
        events = []
        with mock.patch.object(coordinator, '_verify_sources', side_effect=lambda: events.append('SOURCE')), \
                mock.patch.object(coordinator, '_validate_plan', side_effect=lambda p: events.append('PLAN')), \
                mock.patch.object(coordinator, '_adapter', hardware), \
                mock.patch.object(coordinator, '_parent_run_job', return_value={'testOnly': True}) as old:
            result = coordinator.run_job({'TEST_ONLY': True}, approval={'TEST_ONLY': True})
        self.assertEqual(events, ['SOURCE', 'PLAN'])
        self.assertTrue(result['testOnly'])
        self.assertEqual(old.call_args.kwargs['control_root'], coordinator.CONTROL_ROOT)
        self.assertNotIn('_test_components', old.call_args.kwargs)

    def test_cli_inherited_parser_dispatches_through_v3_validation(self):
        self.assertIs(coordinator.parent.run_job, coordinator.run_job)
        self.assertIs(coordinator.parent.start_job, coordinator.start_job)
        self.assertIs(coordinator.parent.status, coordinator.status)

    def test_source_verifier_pin_checked_before_import(self):
        with mock.patch.object(coordinator, 'SOURCE_VERIFIER_SHA256', '0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_SOURCE_VERIFIER_CHANGED'):
                coordinator._verify_sources()
        with mock.patch.object(hardware, 'SOURCE_VERIFIER_SHA256', '0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_SOURCE_VERIFIER_CHANGED'):
                hardware._verify_sources()

    def test_hardware_bridge_reuses_actual_parent_lease_and_admission_owner(self):
        old = ROOT.parent / 'universal-auto-video-v2/render_adapter.py'
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(), hardware.PARENT_SHA256)
        for function in ('native_gpu', 'common_gpu_lease', 'prepare_job', 'render_segment', '_run_native_capture'):
            value = getattr(hardware.parent, function)
            self.assertEqual(Path(getattr(value, '__wrapped__', value).__code__.co_filename), old)
        self.assertEqual(hardware.parent.HERE / 'long_capture.mjs', ROOT / 'long_capture.mjs')

    def test_hardware_prepare_validates_before_original_cpu_preparation(self):
        events = []
        with mock.patch.object(hardware, '_verify_sources', side_effect=lambda: events.append('SOURCE')), \
                mock.patch.object(hardware, '_validate_plan', side_effect=lambda p: events.append('PLAN')), \
                mock.patch.object(hardware.parent, 'prepare_job', side_effect=lambda *a, **k: events.append('PARENT')):
            hardware.prepare_job({'TEST_ONLY': True}, Path('/TEST_ONLY_PRIVATE'), approval={})
        self.assertEqual(events, ['SOURCE', 'PLAN', 'PARENT'])

    def test_hardware_render_forwards_only_existing_fixed_signature(self):
        with mock.patch.object(hardware, '_verify_sources'), mock.patch.object(hardware, '_validate_plan'), \
                mock.patch.object(hardware.parent, 'render_segment', return_value={'testOnly': True}) as old:
            plan, scene, approval = {'TEST_ONLY': True}, {'sceneId': 'CPU_ONLY'}, {'TEST_ONLY': True}
            result = hardware.render_segment(plan, scene, Path('/TEST_ONLY_PRIVATE'), approval=approval)
        self.assertTrue(result['testOnly'])
        self.assertEqual(old.call_args.args, (plan, scene, Path('/TEST_ONLY_PRIVATE')))
        self.assertEqual(old.call_args.kwargs, {'approval': approval, 'progress': None})

    def test_original_generic_module_instance_remains_unchanged(self):
        parent = ROOT.parent / 'universal-auto-video-v2'
        original_path = list(sys.path)
        try:
            sys.path.insert(0, str(parent))
            spec = importlib.util.spec_from_file_location('_test_untouched_old_coordinator', parent / 'orchestrator.py')
            old = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(old)
        finally:
            sys.path[:] = original_path
        self.assertEqual(old.HERE, parent)
        self.assertNotEqual(old.CONTROL_ROOT, coordinator.CONTROL_ROOT)
        self.assertIsNot(old.run_job, coordinator._parent_run_job)

    def test_clean_worker_resolves_actual_frozen_lazy_dependencies_without_gpu(self):
        code = """
import importlib.util,json,pathlib,sys
root=pathlib.Path(sys.argv[1]);sys.path[:]=[str(root),*[x for x in sys.path if 'universal-auto-video-v2' not in x]]
spec=importlib.util.spec_from_file_location('clean_v3_adapter',root/'render_adapter.py')
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
before=list(sys.path)
with module._parent_imports():
 import compose,delivery,universal_files,prepare_video
 assert all(pathlib.Path(m.__file__).parent==module.PARENT for m in (compose,delivery,universal_files,prepare_video))
 assert callable(compose.compose_segments) and callable(delivery.export_video)
 assert callable(universal_files.verify_extension) and callable(prepare_video.prepare_job_inputs)
assert sys.path==before
print(json.dumps({'status':'CPU_IMPORT_PASS','gpuExecuted':False}))
"""
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT)], check=True,
                                capture_output=True, text=True, timeout=30)
        self.assertIn('CPU_IMPORT_PASS', result.stdout)

    def test_wrong_preloaded_lazy_module_is_rejected_without_overwrite(self):
        wrong = types.SimpleNamespace(__file__='/UNTRUSTED/compose.py')
        before = list(sys.path)
        with mock.patch.dict(sys.modules, {'compose': wrong}):
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_PARENT_LAZY_MODULE_ORIGIN_INVALID'):
                with hardware._parent_imports():
                    self.fail('wrong module was accepted')
            self.assertIs(sys.modules['compose'], wrong)
        self.assertEqual(sys.path, before)

    def test_completed_status_keeps_frozen_delivery_import_in_scope(self):
        def parent_status(_plan, _root):
            import delivery
            self.assertEqual(Path(delivery.__file__).parent, hardware.PARENT)
            return {'state': 'CPU_ONLY_COMPLETED_STATUS'}
        with mock.patch.object(coordinator, '_verify_sources'), mock.patch.object(coordinator, '_validate_plan'), \
                mock.patch.object(coordinator, '_adapter', hardware), \
                mock.patch.object(coordinator, '_parent_status', side_effect=parent_status):
            self.assertEqual(coordinator.status({'TEST_ONLY': True})['state'], 'CPU_ONLY_COMPLETED_STATUS')


if __name__ == '__main__':
    unittest.main()
