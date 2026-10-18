"""Focused integration tests: CPU I/O mocks do not assert NVIDIA/Dropbox PASS."""
from contextlib import nullcontext
import base64
import hashlib
import importlib
import json
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
from offline_frozen import DURABILITY, modules
import offline_runtime as bridge


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = bridge.install()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='offline-runtime-',
            dir='/tmp' if os.stat('/tmp').st_uid == 0 else str(HERE))
        self.base = Path(self.temp.name)
        self.base.chmod(0o700)
        self.root = self.base / 'production'
        self.root.mkdir(mode=0o700)
        bridge._PROVIDER = None
        bridge._PROVIDER_BINDING = None

    def tearDown(self):
        self.temp.cleanup()

    def environment(self):
        environment = {'WORLD_ENGINE_STUDIO_BACKUP_MODE': 'dropbox-api',
                       'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_AUTH_MODE': 'offline'}
        values = [('WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE',
                   base64.urlsafe_b64encode(b'x' * 32).decode()),
                  *[(row[1], 'SYNTHETIC_CPU_SECRET_VALUE_' + str(index))
                    for index, row in enumerate(bridge.OAUTH_INPUTS)]]
        for index, (name, value) in enumerate(values):
            path = self.base / ('credential-' + str(index))
            path.write_text(value)
            path.chmod(0o600)
            environment[name] = str(path)
        return environment

    def queued(self):
        name = 'studio-' + 'a' * 32
        runtime = self.old.parent.runtime()
        with runtime._cache().PrivateTree(self.root) as root, root.child(name, create=True) as job:
            job.write_json('STATE.json', {'profileId': 'V4_ARCHIVAL_80S', 'createdUnix': 0,
                                         'jobId': name, 'state': 'QUEUED'})
            job.write_json('PLAN.json', {'scene': 'SYNTHETIC_CPU_ONLY'})
            job.write_json('AUDIO.json', {'enabled': False})
        return ['/usr/bin/python3', '-B', str(self.old.parent.STUDIO / 'studio_runtime.py'),
                'worker', '--job-id', name, '--control-root', str(self.root),
                '--export-root', str(self.base)]

    def test_exact_frozen_store_and_crypto_with_memory_token_cache(self):
        environment = self.environment()
        provider = Mock()
        provider.access_token.return_value = 'SYNTHETIC_ACCESS_TOKEN_CPU_ONLY'
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(bridge, 'TokenProvider', return_value=provider) as constructor:
            first = bridge.make_vault_from_env()
            second = bridge.make_vault_from_env()
        self.assertIs(type(first.store), self.old.stores.DropboxStore)
        self.assertIs(type(first), self.old.vault.Vault)
        self.assertEqual(first.store.prefix, '/WORLD_ENGINE_STUDIO_BACKUPS_V1')
        self.assertEqual(second.store.prefix, first.store.prefix)
        constructor.assert_called_once_with(*[environment[row[1]] for row in bridge.OAUTH_INPUTS])
        self.assertEqual(len(list(self.base.glob('.offline-access-*'))), 0)
        self.assertIsInstance(first.store._opener, bridge.OfflineOpener)
        self.assertTrue(self.old.preflight.require_dropbox_transport(first))

    def test_changed_secret_rebinds_provider_and_never_rewrites_key(self):
        environment = self.environment()
        key_path = Path(environment['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'])
        before = key_path.read_bytes()
        provider = Mock()
        provider.access_token.return_value = 'SYNTHETIC_ACCESS_TOKEN_CPU_ONLY'
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(bridge, 'TokenProvider', return_value=provider) as constructor:
            bridge.make_vault_from_env()
            Path(environment[bridge.OAUTH_INPUTS[-1][1]]).write_text('SYNTHETIC_REPLACED_REFRESH_CPU_ONLY')
            bridge.make_vault_from_env()
        self.assertEqual(constructor.call_count, 2)
        self.assertEqual(key_path.read_bytes(), before)

    def test_readonly_secret_mount_does_not_receive_ephemeral_access_file(self):
        environment = self.environment()
        before = {path.name: path.read_bytes() for path in self.base.glob('credential-*')}
        provider = Mock()
        provider.access_token.return_value = 'SYNTHETIC_ACCESS_TOKEN_CPU_ONLY'
        self.base.chmod(0o500)
        try:
            with patch.dict(os.environ, environment, clear=True), \
                 patch.object(bridge, 'TokenProvider', return_value=provider):
                self.assertIs(type(bridge.make_vault_from_env().store), self.old.stores.DropboxStore)
        finally:
            self.base.chmod(0o700)
        self.assertEqual({path.name: path.read_bytes() for path in self.base.glob('credential-*')}, before)

    def test_static_token_cannot_replace_missing_offline_secrets(self):
        environment = self.environment()
        environment.pop(bridge.OAUTH_INPUTS[-1][1])
        environment[bridge.STATIC_TOKEN] = 'SYNTHETIC_STATIC_CPU_ONLY'
        with patch.dict(os.environ, environment, clear=True), patch.object(bridge, 'TokenProvider') as provider:
            with self.assertRaisesRegex(RuntimeError, 'DURABILITY_SECRET_FILE_REQUIRED'):
                bridge.make_vault_from_env()
        provider.assert_not_called()

    def test_nonoffline_mode_cannot_select_static_fallback(self):
        environment = self.environment()
        environment['WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_AUTH_MODE'] = 'static'
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'DURABILITY_OAUTH_OFFLINE_MODE_REQUIRED'):
                bridge.make_vault_from_env()

    def test_four_fixed_children_redirect_but_native_gpu_command_unchanged(self):
        for filename, stage in [('durable_server.py', 'server'), ('runtime_entry.py', 'runtime'),
                                ('durable_coordinator.py', 'coordinator'),
                                ('startup_restore.py', 'startup-restore')]:
            command = ['/usr/bin/python3', '-B', str(DURABILITY / filename), '--original', 'value']
            self.assertEqual(bridge.redirect_command(command), [sys.executable, '-B',
                             str(HERE / 'offline_entry.py'), stage, '--original', 'value'])
        command = ['/usr/bin/python3', '-B', '/opt/rtx-package/gpu_launcher.py', '--render-65422']
        self.assertEqual(bridge.redirect_command(command), command)
        self.assertEqual(bridge.redirect_command('a shell command'), 'a shell command')

    def test_real_frozen_worker_seam_keeps_detach_options(self):
        target = Mock()
        with patch.object(self.old.backend, 'save', return_value={'externalDownloadVerified': True}):
            self.old.backend.ProcessAdapter(bridge.ProcessRedirect(target)).Popen(
                self.queued(), start_new_session=True, close_fds=True, stdin=subprocess.DEVNULL)
        command = target.Popen.call_args.args[0]
        self.assertEqual(command[:4], [sys.executable, '-B', str(HERE / 'offline_entry.py'), 'runtime'])
        self.assertTrue(target.Popen.call_args.kwargs['start_new_session'])
        self.assertTrue(target.Popen.call_args.kwargs['close_fds'])

    def test_real_frozen_coordinator_start_and_worker_seams(self):
        target = Mock()
        parent = self.old.parent.RECOVERY / 'verified-front-data-v4-recovery'
        command = ['/usr/bin/python3', '-B', str(parent / 'orchestrator.py'),
                   'start', '--plan', str(self.root / 'studio-test/PLAN.json')]
        self.old.backend.ProcessAdapter(bridge.ProcessRedirect(target)).run(command, timeout=40)
        redirected = target.run.call_args.args[0]
        self.assertEqual(redirected[:4], [sys.executable, '-B', str(HERE / 'offline_entry.py'), 'coordinator'])
        self.assertEqual(redirected[redirected.index('--profile') + 1], 'V4_ARCHIVAL_80S')
        original = SimpleNamespace(HERE=parent)
        worker = [sys.executable, '-B', str(parent / 'orchestrator.py'), 'worker', '--resume']
        self.old.coordinator.WorkerProcessAdapter(bridge.ProcessRedirect(target), original,
            'V4_ARCHIVAL_80S', self.root / 'studio-test').Popen(worker, start_new_session=True)
        self.assertEqual(target.Popen.call_args.args[0][:4],
            [sys.executable, '-B', str(HERE / 'offline_entry.py'), 'coordinator'])
        self.assertTrue(target.Popen.call_args.kwargs['start_new_session'])

    def test_real_frozen_server_spawn_seam(self):
        command = ['/usr/bin/python3', '-B',
                   str(self.old.bootstrap.proxy().https.root / 'https_server.py'), '--port', '8080']
        with patch.object(bridge.subprocess, 'Popen') as spawn:
            self.old.bootstrap.spawn_studio(command, user=1000, group=1000)
        self.assertEqual(spawn.call_args.args[0][:4],
            [sys.executable, '-B', str(HERE / 'offline_entry.py'), 'server'])
        self.assertEqual(spawn.call_args.kwargs['user'], 1000)

    def test_already_initialized_frozen_backend_gains_child_redirect_in_fresh_process(self):
        script = ("import sys; sys.path.insert(0, " + repr(str(HERE)) + "); "
                  "from offline_frozen import modules; old=modules(); "
                  "adapter=old.backend.backend().subprocess; "
                  "from offline_runtime import install, ProcessRedirect; install(); "
                  "assert old.backend.backend().subprocess is adapter; "
                  "assert isinstance(adapter.original, ProcessRedirect); print('CPU_ONLY_OK')")
        result = subprocess.run([sys.executable, '-B', '-c', script],
                                capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout.strip(), b'CPU_ONLY_OK')

    def test_explicit_startup_restore_child_keeps_offline_files_and_private_bindings(self):
        environment = self.environment()
        environment.update({'WORLD_ENGINE_STUDIO_RESTORE_CHECKPOINT_ID': 'a' * 64,
                            'WORLD_ENGINE_STUDIO_RESTORE_PLAN_SHA256': 'b' * 64,
                            'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': 'sha256:' + 'c' * 64,
                            'WORLD_ENGINE_STUDIO_STATE_ROOT': str(self.base / 'future-private')})
        receipt = {'restoreVerified': True, 'checkpointId': 'a' * 64, 'planSHA256': 'b' * 64,
                   'imageDigest': 'sha256:' + 'c' * 64, 'productionRenderingStarted': False,
                   'executionAuthorityRestored': False, 'newOperatorApprovalRequired': True}
        run = Mock(return_value=SimpleNamespace(returncode=0, stdout=json.dumps(receipt).encode()))
        private = self.old.bootstrap.proxy().https.bootstrap.original
        with patch.object(private, '_private_directory'), \
             patch.object(self.old.bootstrap, 'prepare_backup_secrets', side_effect=lambda env, root: dict(env)):
            self.old.bootstrap.prepare_startup_restore(environment, run=run)
        self.assertEqual(run.call_args.args[0][:4],
            [sys.executable, '-B', str(HERE / 'offline_entry.py'), 'startup-restore'])
        self.assertEqual(run.call_args.kwargs['user'], 1000)
        self.assertEqual(run.call_args.kwargs['group'], 1000)
        self.assertEqual(run.call_args.kwargs['timeout'], 600)
        for row in bridge.OAUTH_INPUTS:
            self.assertEqual(run.call_args.kwargs['env'][row[1]], environment[row[1]])

    def test_bootstrap_keeps_key_adds_three_secrets_and_drops_only_static_child_values(self):
        environment = {'WORLD_ENGINE_STUDIO_BACKUP_KEY': base64.urlsafe_b64encode(b'z' * 32).decode(),
                       bridge.STATIC_TOKEN: 'SYNTHETIC_OLD_STATIC_CPU_ONLY',
                       bridge.STATIC_TOKEN + '_FILE': '/private/unused-old-token'}
        environment.update({row[0]: 'SYNTHETIC_CPU_VALUE_' + str(index)
                            for index, row in enumerate(bridge.OAUTH_INPUTS)})
        result = self.old.bootstrap.prepare_backup_secrets(environment, self.base)
        self.assertEqual(len(self.old.bootstrap.SECRET_INPUTS), 4)
        self.assertNotIn(bridge.STATIC_TOKEN, result)
        self.assertNotIn(bridge.STATIC_TOKEN + '_FILE', result)
        for raw, file, _ in self.old.bootstrap.SECRET_INPUTS:
            self.assertNotIn(raw, result)
            self.assertEqual(Path(result[file]).read_text(), environment[raw])
            self.assertEqual(Path(result[file]).stat().st_mode & 0o777, 0o600)
        self.assertIn(bridge.STATIC_TOKEN, environment)  # Never edit the caller's Secret store.

    def test_missing_offline_settings_keep_setup_usable(self):
        self.assertEqual(self.old.bootstrap.prepare_backup_secrets({}, self.base), {})
        self.assertFalse((self.base / 'durability-secrets').exists())

    def test_metadata_scope_uses_app_folder_root_without_catalog_count_or_name_output(self):
        store = object.__new__(self.old.stores.DropboxStore)
        store._request = Mock(return_value=json.dumps({'entries': [], 'has_more': False}).encode())
        vault = SimpleNamespace(store=store)
        self.assertTrue(bridge.require_metadata_access(vault))
        store._request.assert_called_once_with('list', argument={'path': '', 'recursive': False,
                                                'include_deleted': False, 'limit': 1})
        store._request.return_value = b'{"entries": [], "has_more": "false"}'
        with self.assertRaisesRegex(RuntimeError, 'DURABILITY_OAUTH_METADATA_RESPONSE_INVALID'):
            bridge.require_metadata_access(vault)
        store._request.side_effect = self.old.stores.BackupError('DURABILITY_DROPBOX_AUTH_FAILED')
        with self.assertRaisesRegex(RuntimeError, 'DURABILITY_DROPBOX_AUTH_FAILED'):
            bridge.require_metadata_access(vault)

    def test_metadata_approximate_page_limit_does_not_block_valid_scope(self):
        store = object.__new__(self.old.stores.DropboxStore)
        store._request = Mock(return_value=json.dumps({'entries': [{}, {}], 'has_more': True}).encode())
        self.assertTrue(bridge.require_metadata_access(SimpleNamespace(store=store)))

    def test_missing_external_proof_still_blocks_unchanged_gpu_preflight(self):
        original = self.old.backend.backend()
        with patch.object(original, 'preflight', return_value={'checks': [], 'renderAllowed': True}), \
             patch.object(self.old.backend, 'checkpoints',
                          side_effect=RuntimeError('DURABILITY_EXTERNAL_PROOF_REQUIRED')):
            report = self.old.backend.preflight({}, 'V4_ARCHIVAL_80S',
                control_root=self.root, export_root=self.base)
        self.assertFalse(report['renderAllowed'])
        self.assertEqual(report['checks'][-1]['code'], 'DURABILITY_EXTERNAL_PROOF_REQUIRED')

    def test_refresh_failure_before_spawn_keeps_failed_state_and_no_child(self):
        target = Mock()
        with patch.object(self.old.backend, 'save',
                          side_effect=self.old.stores.BackupError('DURABILITY_OAUTH_REFRESH_REJECTED')):
            with self.assertRaisesRegex(RuntimeError, 'DURABILITY_OAUTH_REFRESH_REJECTED'):
                self.old.backend.ProcessAdapter(bridge.ProcessRedirect(target)).Popen(self.queued())
        target.Popen.assert_not_called()
        with self.old.parent.runtime()._cache().PrivateTree(self.root) as root, \
             root.child('studio-' + 'a' * 32) as job:
            state = job.json('STATE.json')
        self.assertEqual(state['state'], 'FAILED')
        self.assertEqual(state['errorCode'], 'DURABILITY_OAUTH_REFRESH_REJECTED')

    def test_real_frozen_coordinator_stops_next_scene_when_refresh_fails(self):
        """Real coordinator path; hardware/encoder I/O is explicitly mocked."""
        location = self.old.parent.RECOVERY / 'universal-auto-video-v2'
        previous = list(sys.path)
        sys.path.insert(0, str(location))
        try:
            frozen = self.old.parent.load_file('_offline_cpu_frozen_coordinator', location / 'orchestrator.py')
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
                 patch.object(frozen, '_deadline', return_value=60), \
                 patch.object(frozen, '_identity', return_value=None), \
                 patch.object(render, 'common_gpu_lease', return_value=nullcontext()), \
                 patch.object(render, 'prepare_job'), patch.object(render, 'render_segment', side_effect=capture), \
                 patch.object(compose, 'verify_segment', return_value={}), \
                 patch.object(delivery, 'export_scene_checkpoint', return_value={'mountedViewReadbackVerified': True}), \
                 patch.object(self.old.coordinator, 'save',
                     side_effect=self.old.stores.BackupError('DURABILITY_OAUTH_REFRESH_REJECTED')):
                with self.old.coordinator.checkpoint_barriers(delivery, plan, {}, 'UNIVERSAL_V3',
                                                              self.root, self.root):
                    with self.assertRaisesRegex(RuntimeError, 'DURABILITY_OAUTH_REFRESH_REJECTED'):
                        frozen.run_job(plan, control_root=self.root, export_root=self.base,
                                       approval={'maxRetries': 0})
            self.assertEqual(calls, ['a'])
            with frozen.PrivateTree(self.root) as root, root.child(frozen._job_id(plan)) as job:
                ledger = job.json('JOB.json')
            self.assertEqual(ledger['state'], 'FAILED')
            self.assertEqual(ledger['completedScenes'], {})
        finally:
            sys.path[:] = previous

    def test_all_frozen_parent_sources_remain_byte_identical(self):
        manifest = json.loads((HERE / 'PARENT_SOURCES.json').read_text())
        for name, digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((DURABILITY / name).read_bytes()).hexdigest(), digest, name)


if __name__ == '__main__':
    unittest.main()
