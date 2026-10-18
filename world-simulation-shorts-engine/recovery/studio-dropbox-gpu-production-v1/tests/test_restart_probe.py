"""Safety-contract tests only; actual Dropbox/container proof is separate CI."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
