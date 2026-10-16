"""Focused CPU/data/command evidence, never NVIDIA execution or billing proof."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
import stat
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


binding = load('_test_archival_execution_plan', 'scene_binding.py')
coordinator = load('_test_archival_execution_coordinator', 'orchestrator.py')
hardware = load('_test_archival_execution_hardware', 'render_adapter.py')
SYNTHETIC_BINDING = {'profileId': binding.PROFILE_ID,
                     'profileSha256': '1' * 64, 'sourceManifestSha256': '2' * 64}
SYNTHETIC_IMAGE = 'sha256:' + '3' * 64


def plan():
    return binding.derive_execution_plan(binding.parent_plan(), image_digest=SYNTHETIC_IMAGE,
        front_profile_sha256=SYNTHETIC_BINDING['profileSha256'],
        front_manifest_sha256=SYNTHETIC_BINDING['sourceManifestSha256'])


class ExecutionBindingTests(unittest.TestCase):
    def test_unchanged_parent_and_original_v3_validator_accept_extended_plan(self):
        before = binding.parent_plan()
        result = plan()
        self.assertEqual(result['totalFrames'], 2400)
        self.assertEqual(len(result['scenes']), 12)
        self.assertEqual(len(result['productionV3']['eventChapters']), 12)
        self.assertEqual(result['productionV3'], before['productionV3'])
        for name in ('legacyScenePlan', 'cameraProfile', 'materialProfile',
                     'splitPolicy', 'durationSeconds', 'fps', 'resolution'):
            self.assertEqual(result[name], before[name], name)
        self.assertEqual(result['sourceManifest']['archivalFrontV4'], SYNTHETIC_BINDING)
        binding._planner().validate_production_plan(result, require_renderable=True)
        self.assertEqual(binding.parent_plan(), before)

    def test_every_scene_cache_identity_includes_new_data_and_image(self):
        before, after = binding.parent_plan(), plan()
        contracts = binding._planner()._parent()[0]
        self.assertNotEqual(contracts.canonical_sha256(before), contracts.canonical_sha256(after))
        for old, new in zip(before['scenes'], after['scenes']):
            self.assertEqual((old['startFrame'], old['endFrame']), (new['startFrame'], new['endFrame']))
            self.assertEqual(new['sourceManifest'], {'sha256': contracts.canonical_sha256(after['sourceManifest'])})
            self.assertNotEqual(new['sourceManifest'], old['sourceManifest'])
            self.assertEqual(new['renderProfile']['imageDigest'], SYNTHETIC_IMAGE)
            self.assertNotEqual(contracts.canonical_sha256(old), contracts.canonical_sha256(new))
            self.assertEqual(new['productionBoundaryStart'], old['productionBoundaryStart'])
            self.assertEqual(new['productionBoundaryEnd'], old['productionBoundaryEnd'])

    def test_only_declared_data_and_image_changes_are_accepted(self):
        value = plan()
        with mock.patch.object(binding, 'source_binding', return_value=SYNTHETIC_BINDING):
            binding.validate_execution_plan(value)
            for field in ('legacyScenePlan', 'cameraProfile', 'productionV3'):
                altered = deepcopy(value)
                altered[field]['UNAPPROVED_CHANGE'] = True
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'FRONT_EXECUTION_PLAN_DATA_OR_TIMELINE_MISMATCH'):
                    binding.validate_execution_plan(altered)
            altered = deepcopy(value)
            altered['sourceManifest']['archivalFrontV4']['profileSha256'] = '4' * 64
            with self.assertRaisesRegex(ValueError, 'FRONT_EXECUTION_PLAN_DATA_OR_TIMELINE_MISMATCH'):
                binding.validate_execution_plan(altered)

    def test_old_plan_missing_data_binding_cannot_start_as_new_job(self):
        with mock.patch.object(binding, 'source_binding', return_value=SYNTHETIC_BINDING):
            with self.assertRaisesRegex(ValueError, 'FRONT_EXECUTION_PLAN_DATA_OR_TIMELINE_MISMATCH'):
                binding.validate_execution_plan(binding.parent_plan())

    def test_modified_parent_is_not_accepted_as_an_editorial_override(self):
        original = binding.parent_plan()
        original['fps'] = 29
        with self.assertRaisesRegex(ValueError, 'FRONT_EXECUTION_UNCHANGED_PARENT_PLAN_REQUIRED'):
            binding.derive_execution_plan(original, image_digest=SYNTHETIC_IMAGE,
                front_profile_sha256='1' * 64, front_manifest_sha256='2' * 64)

    def test_source_and_image_hashes_are_not_optional(self):
        for image, profile, manifest in (('latest', '1' * 64, '2' * 64),
                                         (SYNTHETIC_IMAGE, '', '2' * 64),
                                         (SYNTHETIC_IMAGE, '1' * 64, None)):
            with self.subTest(image=image, profile=profile, manifest=manifest), self.assertRaises(ValueError):
                binding.derive_execution_plan(binding.parent_plan(), image_digest=image,
                    front_profile_sha256=profile, front_manifest_sha256=manifest)

    def test_frozen_execution_owners_and_distinct_namespace(self):
        old = ROOT.parent / 'universal-auto-video-v2'
        self.assertEqual(Path(coordinator._parent_start_job.__code__.co_filename), old / 'orchestrator.py')
        self.assertEqual(Path(coordinator._parent_run_job.__code__.co_filename), old / 'orchestrator.py')
        self.assertEqual(coordinator.parent.HERE, ROOT)
        self.assertEqual(coordinator.CONTROL_ROOT, Path('/var/lib/world-engine-private/engine/verified-front-v4'))
        self.assertEqual(hardware.parent.HERE / 'long_capture.mjs', ROOT / 'long_capture.mjs')
        for name in ('native_gpu', 'common_gpu_lease', 'prepare_job', 'render_segment', '_run_native_capture'):
            function = getattr(hardware.parent, name)
            self.assertEqual(Path(getattr(function, '__wrapped__', function).__code__.co_filename), old / 'render_adapter.py')

    def test_real_detached_manager_constructs_only_new_fixed_worker_command(self):
        # Exercise real old start_job, approval, private ledger and Popen args.
        # The process creation/identity alone is mocked; no worker or GPU runs.
        value = plan()
        approval = {'schema': coordinator.parent.AUTH_SCHEMA, 'approved': True,
            'planSHA256': coordinator.parent.canonical_sha256(value), 'imageDigest': SYNTHETIC_IMAGE,
            'validUntil': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            'maxWallSeconds': 60, 'maxRetries': 0, 'maxCostAmount': '1', 'currency': 'USD', 'gpuHourlyRate': '1'}
        # This managed host's /tmp is owned by nobody, so it intentionally fails
        # the inherited private-parent contract. Choose only an actually safe
        # existing ancestor, without chmod/chown or relaxing the security guard.
        safe = next(path for path in (Path('/tmp'), Path('/workspace'), ROOT)
                    if path.is_dir() and path.stat().st_uid in (0, os.geteuid())
                    and (not stat.S_IMODE(path.stat().st_mode) & 0o022
                         or path.stat().st_uid == 0 and stat.S_IMODE(path.stat().st_mode) & stat.S_ISVTX))
        with tempfile.TemporaryDirectory(dir=safe) as temporary:
            directory = Path(temporary)
            authorization = directory / 'APPROVAL_SYNTHETIC_NOT_EXECUTED.json'
            authorization.write_text(json.dumps(approval))
            authorization.chmod(0o600)
            control = directory / 'private-control'
            with mock.patch.object(coordinator, '_verify_sources'), \
                 mock.patch.object(coordinator, '_validate_plan', side_effect=lambda p: binding._planner().validate_production_plan(p, require_renderable=True)), \
                 mock.patch.object(coordinator, '_adapter', hardware), \
                 mock.patch.object(coordinator.parent, '_identity', return_value={'pid': 12345, 'testOnly': True}), \
                 mock.patch.object(coordinator.parent.subprocess, 'Popen') as popen:
                popen.return_value.pid = 12345
                result = coordinator.start_job(value, authorization, control_root=control, export_root=directory / 'export')
            command = popen.call_args.args[0]
            self.assertEqual(command[:4], [sys.executable, '-B', str(ROOT / 'orchestrator.py'), 'worker'])
            self.assertIn(str(control), command)
            self.assertNotIn('universal-production-v3/orchestrator.py', ' '.join(command))
            self.assertTrue(popen.call_args.kwargs['start_new_session'])
            self.assertTrue(popen.call_args.kwargs['close_fds'])
            self.assertEqual(popen.call_args.kwargs['stdin'], subprocess.DEVNULL)
            self.assertEqual(result['state'], 'QUEUED')
            self.assertFalse(result['gpuRenderingVerified'])
            saved = json.loads((control / result['jobId'] / 'PLAN.json').read_text())
            self.assertEqual(saved['sourceManifest']['archivalFrontV4'], SYNTHETIC_BINDING)

    def test_scoped_imports_restore_modules_and_resolve_real_frozen_dependencies(self):
        previous = {name: sys.modules.get(name) for name in ('orchestrator', 'render_adapter')}
        with mock.patch.object(coordinator, '_adapter', hardware), coordinator._fixed_entry_modules():
            self.assertIs(sys.modules['orchestrator'], coordinator)
            self.assertIs(sys.modules['render_adapter'], hardware)
            import compose, delivery, prepare_video
            for module in (compose, delivery, prepare_video):
                self.assertEqual(Path(module.__file__).parent, ROOT.parent / 'universal-auto-video-v2')
        self.assertEqual({name: sys.modules.get(name) for name in previous}, previous)

    def test_node_shim_uses_fixed_manifest_paths_and_rejects_profile_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name, raw in {'long_capture.mjs': (ROOT / 'long_capture.mjs').read_bytes(),
                              'front_capture.mjs': b'export const fixture="SYNTHETIC_NO_GPU";',
                              'front_runtime.mjs': b'export const fixture="SYNTHETIC_NO_GPU";',
                              'FRONT_PROFILE.json': b'{"SYNTHETIC_NO_GPU":true}'}.items():
                (directory / name).write_bytes(raw)
            manifest = {'schema': 'WORLD_ENGINE_VERIFIED_FRONT_FILES_V4', 'profileId': binding.PROFILE_ID,
                'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()}}
            (directory / 'FRONT_FILES.json').write_text(json.dumps(manifest))
            script = """
import assert from 'node:assert/strict';
const module=await import(process.argv[1]);
const input={planFile:'/SYNTHETIC_PLAN',expectedPlanSha256:'1'.repeat(64),sceneId:'SYNTHETIC',admissionFile:'/SYNTHETIC_ADMISSION',outputRoot:'/SYNTHETIC_OUTPUT'};
const out=await module.fixedCaptureOptions(input);
assert.equal(out.frontProfileFile,process.argv[2]+'/FRONT_PROFILE.json');
assert.equal(out.frontManifestFile,process.argv[2]+'/FRONT_FILES.json');
assert.equal(out.expectedFrontProfileSha256,process.argv[3]);
await assert.rejects(()=>module.fixedCaptureOptions({...input,frontProfileFile:'/UNTRUSTED'}),/FRONT_EXECUTION_FIXED_CAPTURE_ARGUMENTS_REQUIRED/);
console.log('CPU_FIXED_DATA_BINDING_PASS_GPU_NOT_EXECUTED');
"""
            run = subprocess.run(['node', '--input-type=module', '-e', script,
                (directory / 'long_capture.mjs').as_uri(), str(directory), manifest['files']['FRONT_PROFILE.json']],
                check=True, capture_output=True, text=True, timeout=30)
            self.assertIn('CPU_FIXED_DATA_BINDING_PASS_GPU_NOT_EXECUTED', run.stdout)
            (directory / 'FRONT_PROFILE.json').write_text('{"SYNTHETIC_TAMPER":true}')
            failed = subprocess.run(['node', '--input-type=module', '-e', script,
                (directory / 'long_capture.mjs').as_uri(), str(directory), manifest['files']['FRONT_PROFILE.json']],
                capture_output=True, text=True, timeout=30)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('FRONT_EXECUTION_CAPTURE_SOURCE_CHANGED', failed.stderr)


if __name__ == '__main__':
    unittest.main()
