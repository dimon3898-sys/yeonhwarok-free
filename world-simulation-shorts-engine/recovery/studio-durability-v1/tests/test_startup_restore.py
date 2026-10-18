"""Explicit startup recovery CPU tests; never NVIDIA or live Dropbox claims."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import bootstrap
import checkpoint
import startup_restore
from stores import BackupError
from vault import Vault
from test_checkpoint import MemoryStore, create_cpu_fixture, test_temp_root


class StartupRestoreContractTests(unittest.TestCase):
    def config(self):
        return {'WORLD_ENGINE_STUDIO_RESTORE_CHECKPOINT_ID': 'a' * 64,
                'WORLD_ENGINE_STUDIO_RESTORE_PLAN_SHA256': 'b' * 64,
                'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': 'sha256:' + 'c' * 64,
                'WORLD_ENGINE_STUDIO_STATE_ROOT': '/var/lib/world-engine-private/engine/fresh-restored',
                'WORLD_ENGINE_STUDIO_OWNER_CODE': 'NOT_PASSED_TO_RESTORE_CHILD',
                'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON': 'NOT_PASSED_TO_RESTORE_CHILD',
                'GCUBE_ACCESS_TOKEN': 'NOT_PASSED_TO_RESTORE_CHILD',
                'AWS_SECRET_ACCESS_KEY': 'NOT_PASSED_TO_RESTORE_CHILD',
                'GH_TOKEN': 'NOT_PASSED_TO_RESTORE_CHILD',
                'HTTPS_PROXY': 'http://proxy.invalid:8080',
                'WORLD_ENGINE_STUDIO_BACKUP_MODE': 'dropbox-api'}

    def test_absent_restore_profile_is_noop(self):
        run = Mock()
        self.assertEqual(bootstrap.prepare_startup_restore({}, run=run), {})
        run.assert_not_called()

    def test_partial_or_missing_explicit_bindings_fail_before_spawning(self):
        for missing in ('WORLD_ENGINE_STUDIO_RESTORE_PLAN_SHA256', 'WORLD_ENGINE_STUDIO_STATE_ROOT',
                        'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'):
            value = self.config()
            value.pop(missing)
            run = Mock()
            with self.assertRaisesRegex(RuntimeError, 'DURABILITY_EXPLICIT_STARTUP_RESTORE_BINDINGS_REQUIRED'):
                bootstrap.prepare_startup_restore(value, run=run)
            run.assert_not_called()

    def test_shared_storage_target_remains_forbidden(self):
        value = self.config()
        value['WORLD_ENGINE_STUDIO_STATE_ROOT'] = '/world-storage/private-looking'
        run = Mock()
        with self.assertRaisesRegex(RuntimeError, 'DURABILITY_PRIVATE_RESTORE_ROOT_REQUIRED'):
            bootstrap.prepare_startup_restore(value, run=run)
        run.assert_not_called()

    def test_cpu_child_is_explicit_uid1000_and_never_receives_owner_policy_secret(self):
        value = self.config()
        receipt = {'checkpointId': value['WORLD_ENGINE_STUDIO_RESTORE_CHECKPOINT_ID'],
                   'planSHA256': value['WORLD_ENGINE_STUDIO_RESTORE_PLAN_SHA256'],
                   'imageDigest': value['WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'],
                   'restoreVerified': True, 'productionRenderingStarted': False,
                   'executionAuthorityRestored': False, 'newOperatorApprovalRequired': True}
        run = Mock(return_value=SimpleNamespace(returncode=0, stdout=json.dumps(receipt).encode()))
        original = bootstrap.proxy().https.bootstrap.original
        with patch.object(original, '_private_directory'), \
             patch.object(bootstrap, 'prepare_backup_secrets', side_effect=lambda env, root: dict(env)):
            self.assertEqual(bootstrap.prepare_startup_restore(value, run=run), value)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, '-B', str(HERE / 'startup_restore.py')])
        settings = run.call_args.kwargs
        self.assertEqual((settings['user'], settings['group'], settings['extra_groups']), (1000, 1000, []))
        self.assertNotIn('WORLD_ENGINE_STUDIO_OWNER_CODE', settings['env'])
        self.assertNotIn('WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON', settings['env'])
        for name in ('GCUBE_ACCESS_TOKEN', 'AWS_SECRET_ACCESS_KEY', 'GH_TOKEN'):
            self.assertNotIn(name, settings['env'])
        self.assertEqual(settings['env']['HTTPS_PROXY'], value['HTTPS_PROXY'])
        self.assertFalse(any('render' in part for part in command[3:]))

    def test_failed_or_ambiguous_cpu_restore_blocks_bootstrap(self):
        original = bootstrap.proxy().https.bootstrap.original
        for result in (SimpleNamespace(returncode=2, stdout=b'{"code":"DURABILITY_OBJECT_NOT_FOUND"}'),
                       SimpleNamespace(returncode=0, stdout=b'{"restoreVerified":true}')):
            with patch.object(original, '_private_directory'), \
                 patch.object(bootstrap, 'prepare_backup_secrets', side_effect=lambda env, root: dict(env)):
                with self.assertRaisesRegex(RuntimeError, 'DURABILITY_'):
                    bootstrap.prepare_startup_restore(self.config(), run=Mock(return_value=result))

    def test_production_entry_never_selects_test_mode_or_starts_renderer(self):
        value = self.config()
        target = Path(value['WORLD_ENGINE_STUDIO_STATE_ROOT'])
        with patch.object(startup_restore.os, 'geteuid', return_value=1000), \
             patch.object(startup_restore.os, 'getegid', return_value=1000), \
             patch('preflight.require_dropbox_transport'), \
             patch.object(Path, 'exists', return_value=False), \
             patch.object(Path, 'is_symlink', return_value=False), \
             patch.object(checkpoint, 'restore', return_value={'executionAuthorityRestored': False}) as restore:
            result = startup_restore.ensure_restore(object(), value['WORLD_ENGINE_STUDIO_RESTORE_CHECKPOINT_ID'],
                value['WORLD_ENGINE_STUDIO_RESTORE_PLAN_SHA256'], value['WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'], target)
        self.assertTrue(restore.call_args.kwargs['production'])
        self.assertFalse(result['productionRenderingStarted'])
        self.assertFalse(result['gpuVerified'])


@unittest.skipUnless(os.geteuid() == 1000 and os.getegid() == 1000 and shutil.which('ffmpeg'),
                     'BLOCKED: requires UID/GID1000 and actual CPU FFmpeg')
class ActualFreshRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.startup-restore-', dir=test_temp_root())
        self.base = Path(self.temp.name)
        fixture = create_cpu_fixture(self.base)
        self.plan, self.audio = fixture['plan'], fixture['audio']
        self.store = MemoryStore()
        self.vault = Vault(os.urandom(32), self.store)
        self.saved = checkpoint.Checkpoints(self.vault, production=False).save(
            self.plan, self.audio, 'UNIVERSAL_V3', fixture['private'], coordinator_root=fixture['native'])
        shutil.rmtree(fixture['private'])  # Only this test's synthetic source.
        self.target = self.base / 'restored'
        checkpoint.restore(self.vault, self.saved['checkpointId'], self.target,
            expected_plan_sha=checkpoint.sha(self.plan),
            expected_image_digest=self.plan['renderProfile']['imageDigest'], production=False)

    def tearDown(self):
        self.temp.cleanup()

    def verify(self, vault=None, checkpoint_id=None, production=False):
        return startup_restore._verify_existing(vault or self.vault, checkpoint_id or self.saved['checkpointId'],
            checkpoint.sha(self.plan), self.plan['renderProfile']['imageDigest'], self.target, production=production)

    def test_same_container_restart_rechecks_actual_media_preserves_claims_and_results(self):
        marker = self.target / 'production' / 'unchanged-job-claim.json'
        marker.write_text('{"claim":"SYNTHETIC_EXISTING_HISTORY"}')
        marker.chmod(0o600)
        before = {p.relative_to(self.target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.target.rglob('*') if p.is_file()}
        result = self.verify()
        after = {p.relative_to(self.target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.target.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(result['restoreVerified'])
        self.assertEqual(result['completedScenes'], 2)
        self.assertTrue(result['newOperatorApprovalRequired'])
        self.assertFalse(result['executionAuthorityRestored'])

    def test_existing_root_cannot_change_snapshot_or_promote_synthetic_provenance(self):
        with self.assertRaisesRegex(BackupError, 'DURABILITY_RESTORE_BINDING_MISMATCH'):
            self.verify(production=True)
        manifest = copy.deepcopy(self.vault.load_manifest(self.saved['checkpointId']))
        manifest['audio']['gain'] = 0.25
        changed = self.vault.save_manifest(manifest)
        with self.assertRaises(BackupError):
            self.verify(checkpoint_id=changed)

    def test_every_artifact_is_bound_to_authenticated_remote_descriptor(self):
        manifest = copy.deepcopy(self.vault.load_manifest(self.saved['checkpointId']))
        manifest['scenes'][0]['files'][0]['descriptor']['sha256'] = '0' * 64
        # The local cache is internally self-consistent, but this remote binding
        # mismatch must still fail instead of accepting local receipt hashes.
        changed = self.vault.save_manifest(manifest)
        with checkpoint.modules()['cache'].PrivateTree(self.target / 'production') as prod:
            receipt = prod.json('RESTORED_INPUT.json')
            receipt['checkpointId'] = changed
            with prod.lock():
                prod.write_json('RESTORED_INPUT.json', receipt, replace=True)
        with self.assertRaisesRegex(BackupError, 'DURABILITY_RESTORE_CACHE_HASH_MISMATCH'):
            self.verify(checkpoint_id=changed)

    def test_incomplete_or_unrelated_existing_root_never_gets_repaired(self):
        receipt = self.target / 'production' / 'RESTORED_INPUT.json'
        before = receipt.read_bytes()
        receipt.unlink()  # Only this newly created synthetic fixture.
        with self.assertRaises(FileNotFoundError):
            self.verify()
        self.assertFalse(receipt.exists())
        self.assertTrue(before)


if __name__ == '__main__':
    unittest.main()
