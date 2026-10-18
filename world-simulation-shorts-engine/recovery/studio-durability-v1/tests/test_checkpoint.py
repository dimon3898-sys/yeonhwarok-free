"""Real FFmpeg + authenticated vault CPU fixtures, never GPU/storage claims."""
import copy
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import checkpoint
from stores import BackupError, NotFound
from vault import Vault


def test_temp_root():
    # Image /tmp is root-owned sticky, while this managed host maps its owner
    # to nobody. Keep the frozen trust check; use the owned workspace only in
    # that host case. Never place fixtures below the immutable image payload.
    for root in (Path('/tmp'), Path('/workspace')):
        if root.is_dir() and not root.is_symlink():
            info = root.stat()
            if (info.st_uid in {0, os.geteuid()} and
                    (not stat.S_IMODE(info.st_mode) & 0o022 or
                     info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
                return root
    raise RuntimeError('BLOCKED: no trusted writable CPU fixture parent')


class MemoryStore:
    external_verified = False
    def __init__(self): self.objects, self.receipts = {}, []
    def put(self, oid, data):
        if oid in self.objects and self.objects[oid] != data:
            raise BackupError('TEST_OBJECT_CONFLICT')
        self.objects[oid] = data
    def get(self, oid):
        if oid not in self.objects: raise NotFound()
        return self.objects[oid]
    def publish_receipt(self, oid):
        if oid not in self.receipts: self.receipts.append(oid)
    def list_receipts(self): return list(self.receipts)


def create_cpu_fixture(base, source_video=None):
    """Reusable real-media smoke fixture; never represents historical/NVIDIA data."""
    base = Path(base)
    if source_video is None:
        source_video = base / 'fixture.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'lavfi', '-i',
            'testsrc2=size=64x96:rate=30', '-frames:v', '30', '-c:v', 'libx264', '-threads', '1',
            '-preset', 'ultrafast', '-crf', '18', '-bf', '0', '-pix_fmt', 'yuv420p', str(source_video)],
            check=True, capture_output=True, timeout=30)
        source_video.chmod(0o600)
    cachemod, compose = checkpoint.modules()['cache'], checkpoint.modules()['compose']
    private = base / 'private'
    private.mkdir(mode=0o700)
    native = private / 'render-v3'
    native.mkdir(mode=0o700)
    (native / 'cache').mkdir(mode=0o700)
    plan = {'testOnly': True, 'durationSeconds': 3, 'fps': 30, 'totalFrames': 90,
        'resolution': {'width': 64, 'height': 96}, 'aspectRatio': '2:3',
        'renderProfile': {'imageDigest': 'sha256:' + 'b' * 64},
        'sourceManifest': {'sha256': 'c' * 64, 'records': [{'kind': 'SYNTHETIC_TEST'}]},
        'scenes': [{'sceneId': 'fixture-' + str(i), 'startFrame': i * 30, 'endFrame': (i + 1) * 30}
                   for i in range(3)]}
    audio, cache_keys = {'enabled': False, 'gain': 0.5, 'cues': []}, []
    scene_cache = cachemod.SceneCache(native / 'cache')
    try:
        for i in (0, 2):
            scene = plan['scenes'][i]
            key = checkpoint._key(plan, i)
            cache_keys.append(key)
            attempt = scene_cache.begin(key)
            shutil.copyfile(source_video, attempt / 'segment.mp4')
            (attempt / 'segment.mp4').chmod(0o600)
            checked = compose.verify_segment(attempt / 'segment.mp4', scene, plan)
            scene_cache.complete(key, attempt, {**checked, **scene, 'path': str(attempt / 'segment.mp4'),
                'testOnly': True, 'hardwareVerified': False, 'artifacts': ['segment.mp4']})
    finally:
        scene_cache.close()
    return {'plan': plan, 'audio': audio, 'private': private, 'native': native, 'cache_keys': cache_keys}


@unittest.skipUnless(os.geteuid() == 1000 and os.getegid() == 1000 and shutil.which('ffmpeg'),
                     'BLOCKED: private cache requires UID/GID1000 and actual FFmpeg')
class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory(prefix='.durability-media-', dir=test_temp_root())
        cls.video = Path(cls.media.name) / 'segment.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'lavfi', '-i',
                        'testsrc2=size=64x96:rate=30', '-frames:v', '30', '-c:v', 'libx264',
                        '-threads', '1', '-preset', 'ultrafast', '-crf', '18', '-bf', '0',
                        '-pix_fmt', 'yuv420p', str(cls.video)], check=True, capture_output=True, timeout=30)
        cls.video.chmod(0o600)
        cls.cache = checkpoint.modules()['cache']
        cls.compose = checkpoint.modules()['compose']

    @classmethod
    def tearDownClass(cls): cls.media.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.durability-checkpoint-', dir=test_temp_root())
        self.base = Path(self.temp.name)
        fixture = create_cpu_fixture(self.base, self.video)
        for name, value in fixture.items(): setattr(self, name, value)
        self.store = MemoryStore()
        self.vault = Vault(b'x' * 32, self.store)
        self.saved = checkpoint.Checkpoints(self.vault, production=False)
        with self.cache.PrivateTree(self.native) as native, native.child('video-v2-' + checkpoint.sha(self.plan)[:24], create=True) as job:
            job.write_json('JOB.json', {'planSHA256': checkpoint.sha(self.plan), 'state': 'RUNNING',
                'retriesUsed': 1, 'deadlineUnix': 12345, 'supervisorIdentity': {'pid': 999999},
                'approval': {'token': 'SYNTHETIC_DO_NOT_EXPORT'}})

    def tearDown(self): self.temp.cleanup()

    def save(self, **kwargs):
        return self.saved.save(self.plan, self.audio, 'UNIVERSAL_V3', self.private, **kwargs)

    def restore(self, identifier, destination=None, **kwargs):
        return checkpoint.restore(self.vault, identifier, destination or self.base / 'restored',
            expected_plan_sha=checkpoint.sha(self.plan),
            expected_image_digest=self.plan['renderProfile']['imageDigest'], production=False, **kwargs)

    def test_inputs_checkpoint_precedes_first_scene(self):
        receipt = self.save()
        manifest = self.vault.load_manifest(receipt['checkpointId'])
        self.assertEqual(manifest['plan'], self.plan)
        self.assertEqual(manifest['audio'], self.audio)
        self.assertEqual(manifest['scenes'], [])
        self.assertEqual(receipt['completedScenes'], 0)
        self.assertFalse(receipt['remotePersistenceVerified'])

    def test_encrypted_append_only_receipt_discovers_snapshot_after_private_loss(self):
        first = self.save()
        second = self.save(coordinator_root=self.native)
        self.assertNotEqual(first['receiptId'], second['receiptId'])
        self.assertEqual(self.store.list_receipts(), [first['receiptId'], second['receiptId']])
        receipt = self.vault.load_manifest(self.store.list_receipts()[-1])
        self.assertEqual(receipt['schema'], 'WORLD_ENGINE_STUDIO_DURABLE_RECEIPT_V1')
        self.assertEqual(receipt['checkpointId'], second['checkpointId'])
        self.assertEqual(receipt['completedScenes'], 2)
        self.assertTrue(receipt['testOnly'])
        shutil.rmtree(self.private)
        restored = self.restore(receipt['checkpointId'])
        self.assertTrue(restored['restoreVerified'])
        self.assertNotIn(b'fixture-0', b''.join(self.store.objects.values()))

    def test_receipt_publication_failure_blocks_completed_checkpoint_result(self):
        with mock.patch.object(self.store, 'publish_receipt', side_effect=BackupError('TEST_RECEIPT_PUBLISH_FAILURE')):
            with self.assertRaisesRegex(BackupError, 'TEST_RECEIPT_PUBLISH_FAILURE'): self.save()
        self.assertEqual(self.store.receipts, [])

    def test_actual_partial_cache_survives_private_state_loss_fresh_restore(self):
        receipt = self.save(coordinator_root=self.native)
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.private.rglob('*') if p.is_file()}
        self.assertEqual(receipt['completedScenes'], 2)
        manifest = self.vault.load_manifest(receipt['checkpointId'])
        self.assertNotIn('supervisorIdentity', manifest['history'])
        self.assertNotIn('SYNTHETIC_DO_NOT_EXPORT', json.dumps(manifest))
        self.assertFalse(manifest['history']['executionAuthorityRestored'])
        for path, digest in before.items(): self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)
        # Only fixture private state is destroyed to model container loss.
        shutil.rmtree(self.private)
        result = self.restore(receipt['checkpointId'])
        self.assertEqual(result['completedScenes'], 2)
        self.assertEqual(result['nextIncompleteSceneIds'], ['fixture-1'])
        self.assertFalse(result['executionAuthorityRestored'])
        self.assertTrue(result['newOperatorApprovalRequired'])
        self.assertFalse(result['externalDownloadVerified'])
        output = self.base / 'restored/production'
        self.assertEqual(json.loads((output / 'PLAN.json').read_text()), self.plan)
        self.assertEqual(json.loads((output / 'AUDIO.json').read_text()), self.audio)
        for key in self.cache_keys:
            cache = self.cache.SceneCache(output / 'render-v3/cache')
            try:
                segment = cache.lookup(key)
                self.assertTrue(segment['fullDecodeVerified'])
                self.assertTrue(segment['testOnly'])
                self.assertFalse(segment['hardwareVerified'])
            finally: cache.close()
        self.assertFalse(list(output.rglob('JOB.json')))
        self.assertFalse(list(output.rglob('APPROVAL.json')))
        self.assertFalse(list(output.rglob('active.json')))

    def test_frozen_coordinator_reuses_restored_scenes_and_calls_only_missing_scene(self):
        receipt = self.save(coordinator_root=self.native)
        shutil.rmtree(self.private)  # Synthetic fixture loss only.
        self.restore(receipt['checkpointId'])
        restored = self.base / 'restored/production/render-v3'
        preserved = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                     for key in self.cache_keys for path in (restored / 'cache' / key).rglob('*') if path.is_file()}
        source = checkpoint.RECOVERY / 'universal-auto-video-v2/orchestrator.py'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                         '2e1e9d76c6ecf760f69fa2204c80d91da251fa0ee2abf8ed7cf3fe2388afcca4')
        spec = importlib.util.spec_from_file_location('_durability_test_frozen_coordinator', source)
        coordinator = importlib.util.module_from_spec(spec)
        # The original coordinator's ordinary imports still resolve to its
        # unchanged directory. No injected test component enters production.
        with mock.patch.object(sys, 'path', [str(source.parent), *sys.path]):
            spec.loader.exec_module(coordinator)
        rendered, composed = [], []
        def render(plan, scene, attempt, **_kwargs):
            rendered.append(scene['sceneId'])
            target = attempt / 'segment.mp4'
            shutil.copyfile(self.video, target)
            target.chmod(0o600)
            return {**scene, 'path': str(target), 'testOnly': True,
                    'hardwareVerified': False, 'artifacts': ['segment.mp4']}
        def compose(_plan, segments, _destination):
            composed.extend(segments)
            return {'testOnly': True}
        approval = {'schema': 'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1', 'approved': True,
            'planSHA256': checkpoint.sha(self.plan), 'imageDigest': self.plan['renderProfile']['imageDigest'],
            'validUntil': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            'maxWallSeconds': 60, 'maxRetries': 0, 'maxCostAmount': '1', 'currency': 'USD', 'gpuHourlyRate': '1'}
        components = {'render': render, 'verify': self.compose.verify_segment, 'compose': compose,
            'export': lambda *_args: {'mountedViewReadbackVerified': True, 'testOnly': True}, 'lease': nullcontext}
        with mock.patch.object(coordinator, 'validate_plan', return_value=self.plan), \
                mock.patch.object(coordinator, '_identity', return_value={'pid': os.getpid(), 'synthetic': True}), \
                mock.patch.dict(sys.modules, {'cache': self.cache}):
            state = coordinator.run_job(self.plan, control_root=restored, export_root=self.base,
                                        approval=approval, _test_components=components)
        self.assertEqual(rendered, ['fixture-1'])
        self.assertEqual([row['sceneId'] for row in composed], ['fixture-0', 'fixture-1', 'fixture-2'])
        self.assertTrue(composed[0]['cacheHit'])
        self.assertTrue(composed[2]['cacheHit'])
        self.assertEqual(state['progressFrames'], 90)
        self.assertEqual(len(state['completedScenes']), 3)
        self.assertEqual(state['state'], 'COMPLETED')
        self.assertTrue(state['testOnly'])
        self.assertFalse(state['gpuRenderingVerified'])
        for path, digest in preserved.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)

    def test_missing_cache_entries_do_not_get_created_by_snapshot(self):
        absent = checkpoint._key(self.plan, 1)
        self.save(coordinator_root=self.native)
        self.assertFalse((self.native / 'cache' / absent).exists())

    def test_production_blocks_mounted_or_synthetic_store(self):
        plan = {**self.plan, 'testOnly': False}
        with self.assertRaisesRegex(BackupError, 'DURABILITY_EXTERNAL_STORE_REQUIRED'):
            checkpoint.Checkpoints(self.vault).save(plan, self.audio, 'UNIVERSAL_V3', self.private)

    def test_changed_image_or_plan_binding_rejected_before_destination_created(self):
        receipt = self.save()
        dest = self.base / 'restored'
        with self.assertRaisesRegex(BackupError, 'DURABILITY_CHECKPOINT_BINDING_MISMATCH'):
            checkpoint.restore(self.vault, receipt['checkpointId'], dest,
                expected_plan_sha='d' * 64, expected_image_digest=self.plan['renderProfile']['imageDigest'], production=False)
        self.assertFalse(dest.exists())

    def test_existing_destination_is_never_overwritten(self):
        receipt = self.save()
        destination = self.base / 'existing'
        destination.mkdir(mode=0o700)
        keep = destination / 'KEEP'
        keep.write_bytes(b'preserve')
        with self.assertRaisesRegex(BackupError, 'DURABILITY_FRESH_RESTORE_ROOT_REQUIRED'):
            self.restore(receipt['checkpointId'], destination)
        self.assertEqual(keep.read_bytes(), b'preserve')

    def test_tampered_encrypted_chunk_blocks_restore(self):
        receipt = self.save(coordinator_root=self.native)
        manifest = self.vault.load_manifest(receipt['checkpointId'])
        oid = manifest['scenes'][0]['files'][0]['descriptor']['chunks'][0]
        body = self.store.objects[oid]
        self.store.objects[oid] = body[:-1] + bytes([body[-1] ^ 1])
        with self.assertRaises(BackupError): self.restore(receipt['checkpointId'])
        self.assertFalse((self.base / 'restored').exists())

    def test_wrong_key_rejects_manifest(self):
        receipt = self.save()
        with self.assertRaises(BackupError):
            checkpoint.restore(Vault(b'y' * 32, self.store), receipt['checkpointId'], self.base / 'restored',
                expected_plan_sha=checkpoint.sha(self.plan), expected_image_digest=self.plan['renderProfile']['imageDigest'], production=False)

    def test_authenticated_manifest_traversal_duplicate_and_wrong_key_rejected(self):
        receipt = self.save(coordinator_root=self.native)
        manifest = self.vault.load_manifest(receipt['checkpointId'])
        for mutation in ('traversal', 'duplicate', 'wrong-key'):
            altered = copy.deepcopy(manifest)
            if mutation == 'traversal': altered['scenes'][0]['files'][0]['name'] = '../leak'
            if mutation == 'duplicate': altered['scenes'].append(copy.deepcopy(altered['scenes'][0]))
            if mutation == 'wrong-key': altered['scenes'][0]['cacheKey'] = 'f' * 64
            identifier = self.vault.save_manifest(altered)
            with self.subTest(mutation=mutation), self.assertRaises(BackupError): self.restore(identifier)
        self.assertFalse((self.base / 'restored').exists())

    def test_failed_put_or_readback_never_yields_completed_manifest(self):
        for operation in ('put_file', 'verify_descriptor'):
            with self.subTest(operation=operation), mock.patch.object(self.vault, operation,
                    side_effect=BackupError('TEST_BACKUP_IO_FAILURE')), mock.patch.object(self.vault, 'save_manifest') as commit:
                with self.assertRaisesRegex(BackupError, 'TEST_BACKUP_IO_FAILURE'):
                    self.save(coordinator_root=self.native)
                commit.assert_not_called()

    def test_private_source_tamper_or_symlink_blocks_snapshot(self):
        cache = self.cache.SceneCache(self.native / 'cache')
        try: path = Path(cache.lookup(self.cache_keys[0])['path'])
        finally: cache.close()
        path.write_bytes(b'corrupt-synthetic-fixture')
        with self.assertRaises(Exception): self.save(coordinator_root=self.native)

    def test_credentials_are_not_accepted_as_inputs(self):
        self.audio['accessToken'] = 'SYNTHETIC_DO_NOT_EXPORT'
        with self.assertRaisesRegex(BackupError, 'DURABILITY_CREDENTIAL_FIELD_FORBIDDEN'): self.save()


if __name__ == '__main__': unittest.main()
