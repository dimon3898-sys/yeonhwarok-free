"""Safety-contract tests only; actual Dropbox/container proof is separate CI."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_production_restart_probe_test', HERE / 'restart_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ReadOnlyProbeTests(unittest.TestCase):
    def test_only_frozen_download_operation_is_allowed(self):
        original = Mock(return_value=b'opaque-authenticated-by-frozen-vault')
        store = SimpleNamespace(_request=original)
        counts = probe.readonly_transport(store)
        argument = {'path': '/approved-opaque-object'}
        self.assertEqual(store._request('download', argument=argument), original.return_value)
        original.assert_called_once_with('download', argument=argument, data=None)
        self.assertEqual(counts, {'downloads': 1, 'remoteWrites': 0})

    def test_upload_folder_receipt_and_unknown_endpoints_fail_before_network(self):
        for endpoint in ('upload', 'mkdir', 'list', 'continue', 'delete', 'unknown'):
            original = Mock()
            store = SimpleNamespace(_request=original)
            counts = probe.readonly_transport(store)
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_REMOTE_WRITE_FORBIDDEN'):
                store._request(endpoint)
            original.assert_not_called()
            self.assertEqual(counts['remoteWrites'], 1)

    def test_direct_put_and_publish_cannot_create_remote_objects(self):
        for method in ('put', 'publish_receipt'):
            original = Mock()
            store = SimpleNamespace(_request=original)
            counts = probe.readonly_transport(store)
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_REMOTE_WRITE_FORBIDDEN'):
                getattr(store, method)('opaque-object')
            original.assert_not_called()
            self.assertEqual(counts['downloads'], 0)

    def test_download_with_mutating_payload_is_forbidden(self):
        store = SimpleNamespace(_request=Mock())
        probe.readonly_transport(store)
        with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_REMOTE_WRITE_FORBIDDEN'):
            store._request('download', data=b'not-permitted')

    def snapshot(self):
        return {'checkpointId': probe.CHECKPOINT_ID, 'imageDigest': probe.IMAGE_DIGEST,
                'planSHA256': 'a' * 64}

    def frozen(self, snapshot=None):
        gate = {'status': 'PASS', 'proofId': probe.PROOF_ID,
                'externalStorageRecoveryVerified': True, 'nvidiaRenderingVerified': False}
        saved = {'testOnly': True, 'executionAuthorityRestored': False,
                 'planSHA256': 'a' * 64, 'imageDigest': probe.IMAGE_DIGEST}
        vault = SimpleNamespace(load_manifest=Mock(side_effect=[snapshot or self.snapshot(), saved]))
        old = SimpleNamespace(preflight=SimpleNamespace(require_external_proof=Mock(return_value=gate)))
        return old, vault

    def test_requires_existing_approved_proof_and_exact_synthetic_checkpoint(self):
        old, vault = self.frozen()
        result = probe.approved_snapshot(old, vault)
        self.assertEqual(result, self.snapshot())
        old.preflight.require_external_proof.assert_called_once_with(vault, probe.PROOF_ID)
        self.assertEqual([call.args[0] for call in vault.load_manifest.call_args_list],
                         [probe.PROOF_ID, probe.CHECKPOINT_ID])

    def test_altered_checkpoint_or_image_cannot_select_other_backup(self):
        for name in ('checkpointId', 'imageDigest'):
            modified = dict(self.snapshot(), **{name: 'unapproved'})
            old, vault = self.frozen(modified)
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_APPROVED_PROOF_REQUIRED'):
                probe.approved_snapshot(old, vault)
            self.assertEqual(vault.load_manifest.call_count, 1)

    def test_expired_proof_failure_is_preserved_without_local_restore(self):
        old, vault = self.frozen()
        old.preflight.require_external_proof.side_effect = RuntimeError('DURABILITY_EXTERNAL_PROOF_EXPIRED')
        with self.assertRaisesRegex(RuntimeError, 'DURABILITY_EXTERNAL_PROOF_EXPIRED'):
            probe.approved_snapshot(old, vault)
        vault.load_manifest.assert_not_called()

    def test_no_general_restore_path_or_production_test_mode_cli(self):
        for arguments in ([], ['restore', '/arbitrary-root'], ['production'], ['verify', '--test-only']):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(probe.main(arguments), 2)
            result = json.loads(out.getvalue())
            self.assertEqual(result['reasonCode'], 'PRODUCTION_RESTART_FIXED_STAGE_REQUIRED')
            self.assertFalse(result['renderAllowed'])
            self.assertFalse(result['productionRenderingStarted'])
            self.assertFalse(result['gpuExecuted'])

    def test_same_process_cannot_claim_distinct_container_restart(self):
        class Tree:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def json(self, name):
                return {'schema': 'CPU_CONTAINER_RESTART_PROBE_V1',
                    'checkpointId': probe.CHECKPOINT_ID, 'planSHA256': 'a' * 64,
                    'imageDigest': probe.IMAGE_DIGEST, 'proofId': probe.PROOF_ID,
                    'testOnly': True, 'executionAuthorityRestored': False,
                    'containerIdentitySHA256': 'same-container'}
        store = SimpleNamespace(_request=Mock())
        vault = SimpleNamespace(store=store)
        cache = SimpleNamespace(PrivateTree=Mock(return_value=Tree()))
        old = SimpleNamespace(checkpoint=SimpleNamespace(modules=lambda: {'cache': cache}),
            backend=SimpleNamespace(make_vault_from_env=lambda: vault),
            preflight=SimpleNamespace(require_dropbox_transport=Mock()))
        with patch.object(probe.os, 'geteuid', return_value=1000), \
             patch.object(probe.os, 'getegid', return_value=1000), \
             patch.object(probe, 'container_identity', return_value='same-container'), \
             patch.object(probe, 'approved_snapshot', return_value=self.snapshot()):
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_DISTINCT_CONTAINER_REQUIRED'):
                probe.operation('verify', old)


class FilesystemInventoryTests(unittest.TestCase):
    """Real files/openat I/O; the full frozen PrivateTree runs in container CI."""
    class Tree:
        def __init__(self, root):
            self.root = Path(root)
            self.fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            os.close(self.fd)
        def child(self, name):
            return self.__class__(self.root / name)
        def hash_file(self, name):
            raw = (self.root / name).read_bytes()
            if not raw:
                raise RuntimeError('EMPTY_ARTIFACT')
            return {'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='restart-inventory-test-')
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.cache = SimpleNamespace(PrivateTree=self.Tree)
        self.lock = self.root / 'LOCK'
        self.lock.touch(mode=0o600)
        self.data = self.root / 'segment.mp4'
        self.data.write_bytes(b'NONEMPTY_SYNTHETIC_BYTES_NOT_MEDIA_VERIFICATION')
        self.data.chmod(0o600)

    def tearDown(self):
        self.temporary.cleanup()

    def test_real_zero_byte_lock_and_nonempty_artifact_have_stable_unchanged_inventory(self):
        before = {name: (self.root / name).read_bytes() for name in ('LOCK', 'segment.mp4')}
        first = probe.inventory(self.cache, self.root)
        self.assertRegex(first, r'^[a-f0-9]{64}$')
        self.assertEqual(first, probe.inventory(self.cache, self.root))
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in before})
        self.assertEqual(self.lock.stat().st_size, 0)

    def test_zero_byte_media_still_uses_frozen_artifact_rejection(self):
        self.data.write_bytes(b'')
        with self.assertRaisesRegex(RuntimeError, 'EMPTY_ARTIFACT'):
            probe.inventory(self.cache, self.root)

    def test_lock_symlink_and_extra_hardlink_are_not_private_metadata(self):
        self.lock.unlink()
        self.lock.symlink_to(self.data)
        with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_UNSAFE_RETAINED_PATH'):
            probe.inventory(self.cache, self.root)
        self.lock.unlink()
        self.lock.touch(mode=0o600)
        os.link(self.lock, self.root / 'other-lock')
        with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_PRIVATE_EMPTY_METADATA_REQUIRED'):
            probe.inventory(self.cache, self.root)

    def test_foreign_owner_and_group_or_nonprivate_permissions_are_rejected(self):
        with patch.object(probe.os, 'geteuid', return_value=os.geteuid() + 1):
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_PRIVATE_EMPTY_METADATA_REQUIRED'):
                probe.inventory(self.cache, self.root)
        with patch.object(probe.os, 'getegid', return_value=os.getegid() + 1):
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_PRIVATE_EMPTY_METADATA_REQUIRED'):
                probe.inventory(self.cache, self.root)
        self.lock.chmod(0o640)
        with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_PRIVATE_EMPTY_METADATA_REQUIRED'):
            probe.inventory(self.cache, self.root)

    def test_mutation_during_zero_byte_lock_read_is_rejected(self):
        original_read = os.read
        def mutate(descriptor, size):
            result = original_read(descriptor, size)
            self.lock.write_bytes(b'changed-during-read')
            return result
        with patch.object(probe.os, 'read', side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_RESTART_(PRIVATE_EMPTY_METADATA_REQUIRED|EMPTY_METADATA_CHANGED)'):
                probe.inventory(self.cache, self.root)

    def test_successful_verification_empty_logs_and_nonempty_rgb_hash_are_inventoried(self):
        evidence = self.root / 'verification-abcdefgh'
        evidence.mkdir(mode=0o700)
        for name in probe.EMPTY_DIAGNOSTICS:
            (evidence / name).touch(mode=0o600)
        rgb = evidence / 'rgb24.sha256'
        rgb.write_text('a' * 64 + '\n', encoding='ascii')
        rgb.chmod(0o600)
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        digest = probe.inventory(self.cache, self.root)
        self.assertEqual(digest, probe.inventory(self.cache, self.root))
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes()
                                 for p in self.root.rglob('*') if p.is_file()})
        rgb.write_bytes(b'changed-nonempty-hash-evidence')
        self.assertNotEqual(digest, probe.inventory(self.cache, self.root))

    def test_empty_diagnostics_outside_exact_verification_context_are_rejected(self):
        for parent in (self.root, self.root / 'other-evidence', self.root / 'verification-unrecognized'):
            parent.mkdir(mode=0o700, exist_ok=True)
            path = parent / 'segment-probe.stderr'
            path.touch(mode=0o600)
            with self.assertRaisesRegex(RuntimeError, 'EMPTY_ARTIFACT'):
                probe.inventory(self.cache, self.root)
            path.unlink()  # Only this test's newly created synthetic fixture.

    def test_unknown_empty_file_inside_verification_directory_remains_rejected(self):
        evidence = self.root / 'verification-abcdefgh'
        evidence.mkdir(mode=0o700)
        (evidence / 'rgb24.sha256').touch(mode=0o600)
        with self.assertRaisesRegex(RuntimeError, 'EMPTY_ARTIFACT'):
            probe.inventory(self.cache, self.root)

    def test_probe_private_umask_is_scoped_and_restored_on_success_and_failure(self):
        original = os.umask(0o022)
        runtime = SimpleNamespace(install=lambda: object())
        try:
            for index, (should_fail, expected) in enumerate(((False, 0), (True, 2))):
                def operation(stage, old):
                    current = os.umask(0o077)
                    self.assertEqual(current, 0o077)
                    evidence = self.root / ('verification-' + str(index).zfill(8))
                    evidence.mkdir(mode=0o700)
                    for name in probe.EMPTY_DIAGNOSTICS:
                        with open(evidence / name, 'xb'):
                            pass
                        self.assertEqual((evidence / name).stat().st_mode & 0o777, 0o600)
                    with open(evidence / 'rgb24.sha256', 'x', encoding='ascii') as stream:
                        stream.write('a' * 64 + '\n')
                    self.assertEqual((evidence / 'rgb24.sha256').stat().st_mode & 0o777, 0o600)
                    self.assertRegex(probe.inventory(self.cache, self.root), r'^[a-f0-9]{64}$')
                    if should_fail:
                        raise RuntimeError('PRODUCTION_RESTART_TEST_FAILURE')
                    return {'status': 'PASS', 'gpuExecuted': False}
                with patch.dict(sys.modules, {'production_runtime': runtime}), \
                     patch.object(probe, 'operation', side_effect=operation), \
                     redirect_stdout(io.StringIO()):
                    self.assertEqual(probe.main(['restore']), expected)
                self.assertEqual(os.umask(0o022), 0o022)
        finally:
            os.umask(original)


if __name__ == '__main__':
    unittest.main()
