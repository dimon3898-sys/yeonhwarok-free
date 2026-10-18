"""Focused CPU adapter checks; mocked GPU facts never establish hardware PASS."""
from contextlib import nullcontext
import base64
import hashlib
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import durable_backend as backend
import durable_coordinator as coordinator
import durable_server
import bootstrap
from parent import RECOVERY, STUDIO, runtime, load_file


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.durability-integration-',
            dir='/tmp' if os.stat('/tmp').st_uid == 0 else str(HERE))
        self.base = Path(self.temp.name)
        self.root = self.base / 'production'
        self.root.mkdir(mode=0o700)

    def tearDown(self):
        self.temp.cleanup()

    def queued(self):
        name = 'studio-' + 'a' * 32
        old = runtime()
        with old._cache().PrivateTree(self.root) as root, root.child(name, create=True) as job:
            job.write_json('STATE.json', {'profileId': 'V4_ARCHIVAL_80S', 'createdUnix': 0,
                                         'jobId': name, 'state': 'QUEUED'})
            job.write_json('PLAN.json', {'scene': 'SYNTHETIC_CPU_ONLY'})
            job.write_json('AUDIO.json', {'enabled': False})
        return ['/usr/bin/python3', '-B', str(STUDIO / 'studio_runtime.py'), 'worker',
                '--job-id', name, '--control-root', str(self.root), '--export-root', str(self.base)]

    def test_initial_backup_failure_prevents_detached_worker_spawn(self):
        target = Mock()
        with patch.object(backend, 'save', side_effect=RuntimeError('DURABILITY_TEST_BACKUP_FAILED')):
            with self.assertRaisesRegex(RuntimeError, 'DURABILITY_TEST_BACKUP_FAILED'):
                backend.ProcessAdapter(target).Popen(self.queued())
        target.Popen.assert_not_called()
        with runtime()._cache().PrivateTree(self.root) as root, root.child('studio-' + 'a' * 32) as job:
            state = job.json('STATE.json')
        self.assertEqual(state['state'], 'FAILED')
        self.assertEqual(state['phase'], 'DURABLE_BACKUP_FAILED')
        self.assertIsNone(state['supervisorIdentity'])

    def test_detached_worker_path_uses_extension_and_venv_with_existing_detach_options(self):
        target = Mock()
        with patch.object(backend, 'save', return_value={'externalDownloadVerified': True}):
            backend.ProcessAdapter(target).Popen(self.queued(), start_new_session=True, close_fds=True)
        command = target.Popen.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, '-B', str(HERE / 'runtime_entry.py')])
        self.assertTrue(target.Popen.call_args.kwargs['start_new_session'])
        self.assertTrue(target.Popen.call_args.kwargs['close_fds'])

    def test_only_fixed_coordinator_command_is_redirected(self):
        target = Mock()
        original = ['/usr/bin/python3', '-B', str(RECOVERY / 'verified-front-data-v4-recovery/orchestrator.py'),
                    'start', '--plan', str(self.root / 'studio-test/PLAN.json')]
        backend.ProcessAdapter(target).run(original)
        command = target.run.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, '-B', str(HERE / 'durable_coordinator.py')])
        self.assertEqual(command[command.index('--profile') + 1], 'V4_ARCHIVAL_80S')
        validator = ['/usr/bin/python3', '-B', '-c', 'safe validator']
        backend.ProcessAdapter(target).run(validator)
        self.assertEqual(target.run.call_args.args[0], validator)

    def test_native_worker_path_preserves_profile_and_original_arguments(self):
        old = SimpleNamespace(HERE=RECOVERY / 'verified-front-data-v4-recovery')
        command = [sys.executable, '-B', str(old.HERE / 'orchestrator.py'), 'worker', '--resume',
                   '--plan', 'PLAN.json', '--approval', 'APPROVAL.json']
        result = coordinator.worker_command(command, old, 'V4_ARCHIVAL_80S', self.root / 'job')
        self.assertEqual(result[:3], [sys.executable, '-B', str(HERE / 'durable_coordinator.py')])
        self.assertEqual(result[-6:], command[-6:])

    def test_missing_backup_config_blocks_preflight_without_starting_gpu(self):
        original = backend.backend()
        clean = {k: v for k, v in os.environ.items() if not k.startswith('WORLD_ENGINE_STUDIO_BACKUP_')}
        with patch.dict(os.environ, clean, clear=True), patch.object(original, 'preflight',
                return_value={'checks': [], 'renderAllowed': True, 'status': 'PASS'}):
            report = backend.preflight({}, 'V4_ARCHIVAL_80S', control_root=self.root, export_root=self.base)
        self.assertFalse(report['renderAllowed'])
        self.assertEqual(report['checks'][-1]['name'], 'DURABLE_BACKUP')
        self.assertEqual(report['checks'][-1]['status'], 'BLOCKED')

    def test_preflight_only_checks_external_proof_and_never_publishes_checkpoint(self):
        original = backend.backend()
        with patch.object(original, 'preflight',
                return_value={'checks': [], 'renderAllowed': True, 'status': 'PASS'}), \
             patch.object(backend, 'checkpoints', return_value=object()) as configured, \
             patch.object(backend, 'save') as publish:
            report = backend.preflight({}, 'V4_ARCHIVAL_80S', control_root=self.root, export_root=self.base)
        configured.assert_called_once_with()
        publish.assert_not_called()
        self.assertTrue(report['renderAllowed'])
        self.assertFalse(report['checks'][-1]['facts']['checkpointPublished'])
        self.assertTrue(report['checks'][-1]['facts']['currentSceneCheckpointRequiredBeforeSpawn'])

    def test_missing_external_proof_blocks_readonly_preflight_without_publication(self):
        original = backend.backend()
        with patch.object(original, 'preflight',
                return_value={'checks': [], 'renderAllowed': True, 'status': 'PASS'}), \
             patch.object(backend, 'checkpoints', side_effect=RuntimeError('DURABILITY_EXTERNAL_PROOF_REQUIRED')), \
             patch.object(backend, 'save') as publish:
            report = backend.preflight({}, 'V4_ARCHIVAL_80S', control_root=self.root, export_root=self.base)
        publish.assert_not_called()
        self.assertFalse(report['renderAllowed'])
        self.assertEqual(report['checks'][-1]['code'], 'DURABILITY_EXTERNAL_PROOF_REQUIRED')

    def test_backend_retains_original_controller_and_security_application(self):
        instance = durable_server.controller_factory(control_root=self.root, export_root=self.base,
            image_digest='sha256:' + 'a' * 64)
        from studio_controller import StudioController
        self.assertIs(type(instance), StudioController)
        self.assertIs(instance.backend, backend)
        self.assertTrue(issubclass(durable_server.Application, durable_server.frozen.server.Application))
        # No auth handler, Host/Origin policy, CSRF or route has been replaced.
        self.assertIs(durable_server.Application.handler, durable_server.frozen.server.Application.handler)
        for name in ('default_plan', 'bind_render_image', 'validate_render_plan'):
            self.assertIs(getattr(backend, name), getattr(backend.backend(), name))

    def test_known_pre_spawn_failure_returns_failed_receipt_without_resetting_claims(self):
        state = {'state': 'FAILED', 'jobId': 'studio-' + 'a' * 32}
        failure = backend.DurabilityLaunchBlocked('DURABILITY_TEST_FAILED', state)
        with patch.object(backend.backend(), 'start_studio_job', side_effect=failure):
            self.assertEqual(backend.start_studio_job(), state)

    def test_checkpoint_save_failure_propagates_and_restores_original_functions(self):
        original_checkpoint = Mock(return_value={'mountedViewReadbackVerified': True})
        original_verify = Mock(return_value={})
        delivery = SimpleNamespace(export_scene_checkpoint=original_checkpoint,
                                   verify_scene_checkpoint=original_verify)
        with patch.object(coordinator, 'save', side_effect=RuntimeError('DURABILITY_TEST_SAVE_FAILED')):
            with self.assertRaisesRegex(RuntimeError, 'DURABILITY_TEST_SAVE_FAILED'):
                with coordinator.checkpoint_barriers(delivery, {}, {}, 'UNIVERSAL_V3', self.root, self.root):
                    delivery.export_scene_checkpoint({}, {}, {}, self.base)
        original_checkpoint.assert_called_once()
        self.assertIs(delivery.export_scene_checkpoint, original_checkpoint)
        self.assertIs(delivery.verify_scene_checkpoint, original_verify)

    def test_real_frozen_coordinator_stops_before_second_scene_on_backup_failure(self):
        """Use the real production run_job; only hardware/encoder I/O is mocked."""
        location = RECOVERY / 'universal-auto-video-v2'
        oldpath = list(sys.path)
        sys.path.insert(0, str(location))
        try:
            frozen = load_file('_durability_integration_production_coordinator', location / 'orchestrator.py')
            render = importlib.import_module('render_adapter')
            compose = importlib.import_module('compose')
            delivery = importlib.import_module('delivery')
            plan = {'totalFrames': 4, 'scenes': [
                {'sceneId': 'a', 'startFrame': 0, 'endFrame': 2},
                {'sceneId': 'b', 'startFrame': 2, 'endFrame': 4}]}
            calls = []
            def capture(plan, scene, attempt, **kwargs):
                calls.append(scene['sceneId'])
                path = Path(attempt) / 'segment.mp4'
                path.write_bytes(b'SYNTHETIC_CPU_IO_NOT_REAL_GPU')
                path.chmod(0o600)
                return {**scene, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'technical': 'PASS', 'frameCountVerified': True, 'fullDecodeVerified': True,
                        'hardwareVerified': True}
            with patch.object(frozen, 'validate_plan'), patch.object(frozen, 'validate_approval'), \
                 patch.object(frozen, '_deadline', return_value=60), patch.object(frozen, '_identity', return_value=None), \
                 patch.object(render, 'common_gpu_lease', return_value=nullcontext()), \
                 patch.object(render, 'prepare_job'), patch.object(render, 'render_segment', side_effect=capture), \
                 patch.object(compose, 'verify_segment', return_value={}), \
                 patch.object(delivery, 'export_scene_checkpoint', return_value={'mountedViewReadbackVerified': True}), \
                 patch.object(coordinator, 'save', side_effect=RuntimeError('DURABILITY_TEST_REMOTE_FAILED')):
                with coordinator.checkpoint_barriers(delivery, plan, {}, 'UNIVERSAL_V3', self.root, self.root):
                    with self.assertRaisesRegex(RuntimeError, 'DURABILITY_TEST_REMOTE_FAILED'):
                        # No _test_components: this is the original component-selection path.
                        frozen.run_job(plan, control_root=self.root, export_root=self.base,
                                       approval={'maxRetries': 0})
            self.assertEqual(calls, ['a'])
            with frozen.PrivateTree(self.root) as root, root.child(frozen._job_id(plan)) as job:
                ledger = job.json('JOB.json')
                self.assertEqual(ledger['state'], 'FAILED')
                self.assertFalse(ledger['testOnly'])
                self.assertEqual(ledger['completedScenes'], {})
        finally:
            sys.path[:] = oldpath

    def test_bootstrap_redirects_only_ui_child_to_isolated_venv(self):
        command = ['/usr/bin/python3', '-B', str(bootstrap.proxy().https.root / 'https_server.py'), '--port', '8080']
        with patch.object(bootstrap.subprocess, 'Popen') as spawn:
            bootstrap.spawn_studio(command, user=1000, group=1000)
        self.assertEqual(spawn.call_args.args[0][:3], [sys.executable, '-B', str(HERE / 'durable_server.py')])
        self.assertEqual(spawn.call_args.kwargs['user'], 1000)

    def test_missing_secrets_leave_web_configuration_usable_and_never_generate_key(self):
        configured = bootstrap.prepare_backup_secrets({}, self.base, uid=os.geteuid(), gid=os.getegid())
        self.assertEqual(configured, {})
        self.assertFalse((self.base / 'durability-secrets').exists())

    def test_bootstrap_materializes_only_approved_secret_and_removes_raw_value(self):
        name, file_name = 'WORLD_ENGINE_STUDIO_BACKUP_KEY', 'WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'
        raw = base64.urlsafe_b64encode(os.urandom(32)).decode()
        configured = bootstrap.prepare_backup_secrets({name: raw}, self.base,
                                                      uid=os.geteuid(), gid=os.getegid())
        self.assertNotIn(name, configured)
        location = Path(configured[file_name])
        self.assertEqual(location.read_text(), raw)
        self.assertEqual(location.stat().st_mode & 0o777, 0o600)
        self.assertEqual(location.parent.stat().st_mode & 0o777, 0o700)

    def test_bootstrap_never_overwrites_different_existing_recovery_key(self):
        name = 'WORLD_ENGINE_STUDIO_BACKUP_KEY'
        first, second = (base64.urlsafe_b64encode(os.urandom(32)).decode() for _ in range(2))
        configured = bootstrap.prepare_backup_secrets({name: first}, self.base,
                                                      uid=os.geteuid(), gid=os.getegid())
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_EXISTING_PRIVATE_CONFIGURATION_PRESERVED'):
            bootstrap.prepare_backup_secrets({name: second}, self.base,
                                              uid=os.geteuid(), gid=os.getegid())
        self.assertEqual(Path(configured[name + '_FILE']).read_text(), first)

    def test_bootstrap_prefers_file_input_and_rejects_symlink(self):
        path = self.base / 'secret-input'
        path.write_text(base64.urlsafe_b64encode(os.urandom(32)).decode())
        path.chmod(0o600)
        configured = bootstrap.prepare_backup_secrets({'WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE': str(path),
            'WORLD_ENGINE_STUDIO_BACKUP_KEY': 'IGNORED'}, self.base, uid=os.geteuid(), gid=os.getegid())
        self.assertEqual(Path(configured['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE']).read_bytes(), path.read_bytes())
        linked = self.base / 'linked-input'
        linked.symlink_to(path)
        with self.assertRaisesRegex(RuntimeError, 'DURABILITY_PRIVATE_SECRET_PATH_REQUIRED'):
            bootstrap._read_input(linked, os.geteuid())


if __name__ == '__main__':
    unittest.main()
