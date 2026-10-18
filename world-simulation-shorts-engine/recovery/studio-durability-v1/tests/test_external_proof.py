"""Mocked transport contract tests. They are NOT live Dropbox/GPU evidence."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import checkpoint
import cli
import preflight
from stores import BackupError, DropboxStore, NotFound
from test_checkpoint import test_temp_root
from vault import Vault


class LocalMemoryStore:
    external_verified = False
    def __init__(self): self.objects = {}
    def get(self, oid):
        if oid not in self.objects: raise NotFound()
        return self.objects[oid]
    def put(self, oid, payload): self.objects[oid] = payload


def mocked_dropbox_vault():
    """Exercise validation with no HTTP. Never emit these IDs as real proof."""
    store = object.__new__(DropboxStore)
    store.prefix = '/UNIT_TEST_ONLY_NOT_EXTERNAL_EVIDENCE'
    memory = LocalMemoryStore()
    store.get, store.put = memory.get, memory.put
    return Vault(b'q' * 32, store), memory


def proof_fixture(vault, now):
    plan = {'testOnly': True, 'durationSeconds': 3, 'fps': 30, 'totalFrames': 90,
            'resolution': {'width': 64, 'height': 96}, 'aspectRatio': '2:3',
            'renderProfile': {'imageDigest': 'sha256:' + 'b' * 64},
            'sourceManifest': {'sha256': 'c' * 64},
            'scenes': [{'sceneId': 'external-probe-' + str(i),
                        'startFrame': i * 30, 'endFrame': (i + 1) * 30} for i in range(3)]}
    descriptor = vault.put_bytes(b'SYNTHETIC_MOCK_TRANSPORT_ONLY')
    saved = {'schema': checkpoint.SCHEMA, 'testOnly': True,
             'executionAuthorityRestored': False, 'planSHA256': checkpoint.sha(plan),
             'imageDigest': plan['renderProfile']['imageDigest'], 'plan': plan,
             'audio': {'enabled': False}, 'profileId': 'UNIVERSAL_V3',
             'scenes': [{'segment': {'testOnly': True, 'hardwareVerified': False},
                         'files': [{'name': 'segment.mp4', 'descriptor': descriptor}]} for _ in range(2)]}
    checkpoint_id = vault.save_manifest(saved)
    proof = {'schema': preflight.SCHEMA, 'scope': preflight.SCOPE,
             'provider': preflight.PROVIDER, 'providerBindingSHA256': preflight.provider_binding(vault),
             'createdUnix': now, 'expiresUnix': now + preflight.TTL_SECONDS,
             'checkpointId': checkpoint_id, 'planSHA256': checkpoint.sha(plan),
             'imageDigest': plan['renderProfile']['imageDigest'], 'completedScenes': 2,
             'restoredScenes': 2, 'nextIncompleteSceneIds': ['external-probe-1'],
             'mediaProvenance': 'CPU_SYNTHETIC_TEST_ONLY', 'externalDownloadVerified': True,
             'freshRestoreVerified': True, 'nvidiaRenderingVerified': False,
             'executionAuthorityRestored': False}
    return proof, saved


class ExternalProofTests(unittest.TestCase):
    def setUp(self):
        self.vault, self.memory = mocked_dropbox_vault()
        self.now = int(time.time())
        self.proof, self.saved = proof_fixture(self.vault, self.now)

    def gate(self, proof=None):
        identifier = self.vault.save_manifest(self.proof if proof is None else proof)
        with mock.patch.object(preflight.time, 'time', return_value=self.now):
            return preflight.require_external_proof(self.vault, identifier)

    def test_mocked_valid_proof_contract_is_not_nvidia_or_live_evidence(self):
        result = self.gate()
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(result['nvidiaRenderingVerified'])

    def test_missing_or_malformed_proof_id_rejected(self):
        for value in (None, '', '../record', 'a' * 63, 'A' * 64):
            with self.subTest(value=value), self.assertRaisesRegex(BackupError, 'PROOF_REQUIRED'):
                preflight.require_external_proof(self.vault, value)

    def test_local_and_claimed_external_fake_store_rejected(self):
        local = LocalMemoryStore()
        local.external_verified = True
        with self.assertRaisesRegex(BackupError, 'REAL_DROPBOX_TRANSPORT_REQUIRED'):
            preflight.require_external_proof(Vault(b'q' * 32, local), 'a' * 64)

    def test_dropbox_subclass_transport_rejected(self):
        class FakeDropbox(DropboxStore): pass
        fake = object.__new__(FakeDropbox)
        with self.assertRaisesRegex(BackupError, 'REAL_DROPBOX_TRANSPORT_REQUIRED'):
            preflight.require_dropbox_transport(Vault(b'q' * 32, fake))

    def test_expiry_future_and_extended_ttl_rejected(self):
        for created, expires in ((self.now - preflight.TTL_SECONDS, self.now),
                                 (self.now + 31, self.now + 31 + preflight.TTL_SECONDS),
                                 (self.now, self.now + preflight.TTL_SECONDS + 1)):
            candidate = dict(self.proof, createdUnix=created, expiresUnix=expires)
            with self.subTest(created=created, expires=expires), self.assertRaisesRegex(BackupError, 'EXPIRED'):
                self.gate(candidate)

    def test_prefix_binding_change_rejected(self):
        identifier = self.vault.save_manifest(self.proof)
        self.vault.store.prefix = '/OTHER_TEST_FOLDER'
        with self.assertRaisesRegex(BackupError, 'PROOF_INVALID'):
            preflight.require_external_proof(self.vault, identifier)

    def test_test_scope_gpu_or_authority_claims_rejected(self):
        for patch in ({'scope': 'MOCK_TRANSPORT_TEST_ONLY'},
                      {'nvidiaRenderingVerified': True},
                      {'executionAuthorityRestored': True},
                      {'freshRestoreVerified': False}, {'restoredScenes': True}):
            with self.subTest(patch=patch), self.assertRaises(BackupError):
                self.gate(dict(self.proof, **patch))

    def test_authenticated_proof_tamper_rejected(self):
        identifier = self.vault.save_manifest(self.proof)
        sealed = self.memory.objects[identifier]
        self.memory.objects[identifier] = sealed[:-1] + bytes([sealed[-1] ^ 1])
        with self.assertRaisesRegex(BackupError, 'AUTHENTICATION_FAILED'):
            preflight.require_external_proof(self.vault, identifier)

    def test_retained_probe_media_loss_rejected(self):
        identifier = self.vault.save_manifest(self.proof)
        descriptor = self.saved['scenes'][0]['files'][0]['descriptor']
        del self.memory.objects[descriptor['chunks'][0]]
        with self.assertRaisesRegex(BackupError, 'OBJECT_NOT_FOUND'):
            preflight.require_external_proof(self.vault, identifier)

    def test_backup_failure_cannot_publish_success_proof(self):
        if os.geteuid() != 1000: self.skipTest('BLOCKED UID1000 private fixture')
        with tempfile.TemporaryDirectory(prefix='.external-proof-fixture-', dir=test_temp_root()) as temporary:
            root = Path(temporary)
            with mock.patch.object(cli, '_cpu_fixture', return_value=({}, {}, root / 'nonexistent')):
                with mock.patch.object(checkpoint.Checkpoints, 'save', side_effect=BackupError('SYNTHETIC_BACKUP_FAILURE')):
                    with mock.patch.object(self.vault, 'save_manifest') as publish:
                        with self.assertRaisesRegex(BackupError, 'SYNTHETIC_BACKUP_FAILURE'):
                            cli.external_check(self.vault, root)
                        publish.assert_not_called()

    def test_restore_failure_cannot_publish_success_proof(self):
        if os.geteuid() != 1000: self.skipTest('BLOCKED UID1000 private fixture')
        with tempfile.TemporaryDirectory(prefix='.external-proof-fixture-', dir=test_temp_root()) as temporary:
            root = Path(temporary)
            private = root / 'new-synthetic-source'
            private.mkdir(mode=0o700)
            plan = {'renderProfile': {'imageDigest': 'sha256:' + 'b' * 64}}
            with mock.patch.object(cli, '_cpu_fixture', return_value=(plan, {}, private)):
                with mock.patch.object(checkpoint.Checkpoints, 'save', return_value={
                    'checkpointId': 'f' * 64, 'completedScenes': 2,
                    'externalDownloadVerified': True, 'remotePersistenceVerified': True}):
                    with mock.patch.object(checkpoint, 'restore', side_effect=BackupError('SYNTHETIC_RESTORE_FAILURE')) as restore:
                        with mock.patch.object(self.vault, 'save_manifest') as publish:
                            with self.assertRaisesRegex(BackupError, 'SYNTHETIC_RESTORE_FAILURE'):
                                cli.external_check(self.vault, root)
                            restore.assert_called_once()
                            publish.assert_not_called()

    def test_cli_fails_closed_without_secrets_and_sanitizes_error(self):
        with mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(cli.main(['list-checkpoints']), 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertFalse(result['productionRenderingStarted'])
        self.assertNotIn('Traceback', output.getvalue())

    def test_listing_prefers_complete_checkpoint_with_explicit_bindings(self):
        receipts, checkpoints = [], {}
        for index, completed in enumerate((0, 2, 1)):
            identifier = str(index + 1) * 64
            receipts.append({'receiptId': str(index + 4) * 64, 'manifest': {
                'schema': 'WORLD_ENGINE_STUDIO_DURABLE_RECEIPT_V1',
                'checkpointId': identifier, 'planSHA256': 'a' * 64,
                'completedScenes': completed, 'createdUnixNs': index + 10,
                'testOnly': True}})
            checkpoints[identifier] = {'schema': checkpoint.SCHEMA, 'planSHA256': 'a' * 64,
                'testOnly': True, 'scenes': [{}] * completed, 'audioSHA256': 'c' * 64,
                'profileId': 'UNIVERSAL_V3', 'imageDigest': 'sha256:' + 'b' * 64}
        with mock.patch.object(self.vault, 'list_receipts', return_value=receipts):
            with mock.patch.object(self.vault, 'load_manifest', side_effect=lambda oid: checkpoints[oid]):
                result = cli.list_checkpoints(self.vault)
        self.assertEqual([row['completedScenes'] for row in result['checkpoints']], [2, 1, 0])
        for row in result['checkpoints']:
            self.assertEqual(row['audioSHA256'], 'c' * 64)
            self.assertEqual(row['imageDigest'], 'sha256:' + 'b' * 64)
            self.assertEqual(row['profileId'], 'UNIVERSAL_V3')
            self.assertNotIn('plan', row)

    def test_listing_rejects_receipt_checkpoint_count_mismatch(self):
        receipt = {'manifest': {'schema': 'WORLD_ENGINE_STUDIO_DURABLE_RECEIPT_V1',
            'checkpointId': 'a' * 64, 'planSHA256': 'b' * 64,
            'testOnly': True, 'completedScenes': 3}}
        saved = {'schema': checkpoint.SCHEMA, 'planSHA256': 'b' * 64,
                 'testOnly': True, 'scenes': []}
        with mock.patch.object(self.vault, 'list_receipts', return_value=[receipt]):
            with mock.patch.object(self.vault, 'load_manifest', return_value=saved):
                with self.assertRaisesRegex(BackupError, 'RECEIPT_CHECKPOINT_MISMATCH'):
                    cli.list_checkpoints(self.vault)


@unittest.skipUnless(os.geteuid() == 1000 and os.getegid() == 1000 and shutil.which('ffmpeg'),
                     'BLOCKED: UID/GID1000 plus FFmpeg required; no GPU test')
class CPUProbeMediaTests(unittest.TestCase):
    def test_probe_fixture_has_real_decode_and_honest_test_provenance(self):
        with tempfile.TemporaryDirectory(prefix='.external-proof-fixture-', dir=test_temp_root()) as temporary:
            plan, audio, private = cli._cpu_fixture(Path(temporary))
            self.assertTrue(plan['testOnly'])
            self.assertEqual(plan['totalFrames'], 90)
            cache = checkpoint.modules()['cache'].SceneCache(private / 'render-v3/cache')
            try:
                for index in (0, 2):
                    segment = cache.lookup(checkpoint._key(plan, index))
                    self.assertTrue(segment['testOnly'])
                    self.assertFalse(segment['hardwareVerified'])
                    self.assertTrue(segment['fullDecodeVerified'])
            finally:
                cache.close()


if __name__ == '__main__': unittest.main()
