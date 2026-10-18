"""Real frozen CPU runtime seams; OAuth/network/GPU I/O remains mocked.

Synthetic credentials in this file are not usable provider credentials. These
checks exercise the immutable private-file and key readers, not NVIDIA or an
external Dropbox account. The CI image supplies all inherited source manifests.
"""
from contextlib import contextmanager
import base64
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
import production_entry
import production_runtime as production


class ProductionRuntimeTests(unittest.TestCase):
    RAW = b'\xfb\xff\xff' * 10 + b'\xfb\xff'

    @classmethod
    def setUpClass(cls):
        if os.geteuid() != 1000:
            raise unittest.SkipTest('Real frozen Secret reader requires UID 1000')
        cls.offline = production.frozen()
        cls.old = production.install()
        # Another focused test may already have installed the same adapter.
        # Keep the actual unchanged consumer for before/after assertions.
        reader = cls.old.vault.read_key_file
        cls.original_reader = staticmethod(getattr(reader, 'original_reader', reader))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='production-runtime-',
            dir='/tmp' if os.stat('/tmp').st_uid == 0 else str(HERE))
        self.base = Path(self.temporary.name)
        self.base.chmod(0o700)
        self.offline._PROVIDER = None
        self.offline._PROVIDER_BINDING = None

    def tearDown(self):
        self.temporary.cleanup()

    def environment(self, value=None):
        result = {'WORLD_ENGINE_STUDIO_BACKUP_MODE': 'dropbox-api',
                  'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_AUTH_MODE': 'offline'}
        inputs = [('WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE', value if value is not None
                   else base64.b64encode(self.RAW).decode('ascii')),
                  *[(row[1], 'SYNTHETIC_CPU_SECRET_VALUE_' + str(index))
                    for index, row in enumerate(self.offline.OAUTH_INPUTS)]]
        for index, (name, body) in enumerate(inputs):
            path = self.base / ('credential-' + str(index))
            path.write_text(body, encoding='ascii')
            path.chmod(0o600)
            result[name] = str(path)
        return result

    def fingerprint(self, path):
        value = path.stat()
        return (path.read_bytes(), value.st_dev, value.st_ino, value.st_uid,
                value.st_mode, value.st_nlink, value.st_size, value.st_mtime_ns)

    def test_standard_and_urlsafe_forms_reach_actual_reader_with_same_key_bytes(self):
        for encoder in (base64.b64encode, base64.urlsafe_b64encode):
            with self.subTest(encoding=encoder.__name__):
                environment = self.environment(encoder(self.RAW).decode('ascii'))
                path = Path(environment['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'])
                before = self.fingerprint(path)
                if encoder is base64.b64encode:
                    with self.assertRaisesRegex(RuntimeError, 'DURABILITY_KEY_32_BYTES_REQUIRED'):
                        self.original_reader(path)
                else:
                    self.assertEqual(self.original_reader(path), self.RAW)
                self.assertEqual(self.old.vault.read_key_file(path), self.RAW)
                self.assertEqual(self.fingerprint(path), before)

    def test_real_frozen_vault_and_dropbox_store_use_same_key_without_secret_rewrite(self):
        environment = self.environment()
        before = {path.name: self.fingerprint(path) for path in self.base.iterdir()}
        provider = Mock()
        provider.access_token.return_value = 'SYNTHETIC_ACCESS_TOKEN_CPU_ONLY'
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(self.offline, 'TokenProvider', return_value=provider) as constructor:
            vault = self.old.backend.make_vault_from_env()
        self.assertIs(type(vault), self.old.vault.Vault)
        self.assertIs(type(vault.store), self.old.stores.DropboxStore)
        self.assertIsInstance(vault.store._opener, self.offline.OfflineOpener)
        constructor.assert_called_once_with(*[environment[row[1]] for row in self.offline.OAUTH_INPUTS])
        self.assertEqual({path.name: self.fingerprint(path) for path in self.base.iterdir()}, before)
        self.assertTrue(self.old.preflight.require_dropbox_transport(vault))

    def assert_private_rejection_before_canonical_or_oauth(self, environment, expected):
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(production, 'canonical_key') as canonical, \
             patch.object(self.offline, 'TokenProvider') as provider:
            with self.assertRaises(RuntimeError) as failure:
                self.old.backend.make_vault_from_env()
            self.assertEqual(str(failure.exception), expected)
        canonical.assert_not_called()
        provider.assert_not_called()

    def test_nonprivate_mode_rejected_before_normalization_or_oauth(self):
        for mode in (0o644, 0o400):
            with self.subTest(mode=oct(mode)):
                environment = self.environment()
                Path(environment['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE']).chmod(mode)
                self.assert_private_rejection_before_canonical_or_oauth(
                    environment, 'DURABILITY_PRIVATE_SECRET_FILE_REQUIRED')

    def test_symlink_and_hardlinked_secret_rejected_before_normalization_or_oauth(self):
        for form in ('symlink', 'hardlink'):
            with self.subTest(form=form):
                environment = self.environment()
                original = Path(environment['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'])
                other = self.base / ('other-' + form)
                if form == 'symlink':
                    other.symlink_to(original)
                    environment['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'] = str(other)
                else:
                    os.link(original, other)
                try:
                    self.assert_private_rejection_before_canonical_or_oauth(environment,
                        'DURABILITY_PRIVATE_SECRET_PATH_REQUIRED' if form == 'symlink'
                        else 'DURABILITY_PRIVATE_SECRET_FILE_REQUIRED')
                finally:
                    other.unlink()

    def test_uid_mismatch_fault_rejected_before_normalization_or_oauth(self):
        # UID is the only changed stat field. This is a CPU fault injection,
        # not a claim to have changed ownership on a provider Secret mount.
        environment = self.environment()
        original = os.fstat
        def foreign_owner(descriptor):
            value = original(descriptor)
            return SimpleNamespace(st_mode=value.st_mode, st_uid=0,
                                   st_nlink=value.st_nlink, st_size=value.st_size)
        with patch.object(self.old.stores.os, 'fstat', side_effect=foreign_owner):
            self.assert_private_rejection_before_canonical_or_oauth(
                environment, 'DURABILITY_PRIVATE_SECRET_FILE_REQUIRED')

    def test_malformed_private_key_fails_before_provider_creation(self):
        environment = self.environment('SYNTHETIC_CPU_NOT_A_VALID_KEY')
        path = Path(environment['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'])
        before = self.fingerprint(path)
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(self.offline, 'TokenProvider') as provider:
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_BACKUP_KEY_ENCODING_INVALID'):
                self.old.backend.make_vault_from_env()
        provider.assert_not_called()
        self.assertEqual(self.fingerprint(path), before)

    def observed_scratch(self):
        original = self.offline._access_scratch
        observed = []
        @contextmanager
        def scratch(old):
            with original(old) as path:
                observed.append(path)
                yield path
        return observed, scratch

    def test_consumer_failure_removes_only_new_canonical_scratch_copy(self):
        environment = self.environment()
        path = Path(environment['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'])
        before = self.fingerprint(path)
        observed, scratch = self.observed_scratch()
        copies = []
        def reject(copy):
            copy = Path(copy)
            copies.append(copy)
            self.assertEqual(copy.stat().st_uid, 1000)
            self.assertEqual(copy.stat().st_mode & 0o777, 0o600)
            self.assertEqual(copy.stat().st_nlink, 1)
            self.assertEqual(copy.read_bytes(), base64.urlsafe_b64encode(self.RAW))
            raise self.old.stores.BackupError('SYNTHETIC_CPU_READER_FAILURE')
        reader = production.canonical_reader(self.old, self.offline, reject)
        with patch.object(self.offline, '_access_scratch', scratch):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_CPU_READER_FAILURE'):
                reader(path)
        self.assertEqual(len(copies), 1)
        self.assertEqual(len(observed), 1)
        self.assertTrue(all(not value.exists() for value in [*copies, *observed]))
        self.assertEqual(self.fingerprint(path), before)

    def test_incomplete_scratch_write_fails_closed_and_cleans_new_copy(self):
        environment = self.environment()
        path = Path(environment['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'])
        before = self.fingerprint(path)
        observed, scratch = self.observed_scratch()
        consumer = Mock()
        reader = production.canonical_reader(self.old, self.offline, consumer)
        with patch.object(self.offline, '_access_scratch', scratch), \
             patch.object(production.os, 'write', return_value=0):
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_PRIVATE_KEY_COPY_FAILED'):
                reader(path)
        consumer.assert_not_called()
        self.assertEqual(len(observed), 1)
        self.assertFalse(observed[0].exists())
        self.assertEqual(self.fingerprint(path), before)

    def test_install_is_idempotent_without_stacked_key_or_child_adapters(self):
        reader = self.old.vault.read_key_file
        redirect = self.offline.redirect_command
        for _ in range(3):
            self.assertIs(production.install(), self.old)
            self.assertIs(self.old.vault.read_key_file, reader)
            self.assertIs(self.offline.redirect_command, redirect)
        self.assertIs(self.old.backend.make_vault_from_env, self.offline.make_vault_from_env)

    def test_all_four_frozen_children_select_production_entry_without_argument_changes(self):
        for filename, stage in (('durable_server.py', 'server'), ('runtime_entry.py', 'runtime'),
                                ('durable_coordinator.py', 'coordinator'),
                                ('startup_restore.py', 'startup-restore')):
            with self.subTest(stage=stage):
                command = [sys.executable, '-B', str(self.offline.DURABILITY / filename),
                           '--existing-option', 'unchanged']
                self.assertEqual(self.offline.redirect_command(command), [sys.executable,
                    '-B', str(HERE / 'production_entry.py'), stage,
                    '--existing-option', 'unchanged'])

    def test_native_gpu_and_unrelated_commands_remain_unchanged(self):
        commands = [[sys.executable, '-B', '/opt/rtx-package/gpu_launcher.py', '--render-65422'],
                    [sys.executable, '-B', '/opt/astra-gpu/runtime.py', '--gpu-required'],
                    ['/usr/bin/ffmpeg', '-version'], 'not interpreted as a shell command']
        for command in commands:
            self.assertEqual(self.offline.redirect_command(command), command)
        original = Mock()
        proxy = self.offline.ProcessRedirect(original)
        proxy.Popen(commands[0], start_new_session=True, close_fds=True,
                    stdin=subprocess.DEVNULL)
        original.Popen.assert_called_once_with(commands[0], start_new_session=True,
                                               close_fds=True, stdin=subprocess.DEVNULL)

    def test_production_entry_rejects_test_and_probe_stages_before_install(self):
        self.assertEqual(production_entry.STAGES,
                         {'bootstrap', 'server', 'runtime', 'coordinator', 'startup-restore', 'cli'})
        for stage in ('test', 'test-only', 'external-proof', 'restart-probe', 'restore-test'):
            with self.subTest(stage=stage), patch.object(production, 'install') as install:
                with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_FIXED_STAGE_REQUIRED'):
                    production_entry.main([stage])
                install.assert_not_called()


if __name__ == '__main__':
    unittest.main()
