"""CPU fixtures never certify NVIDIA output or the user's retained cache."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('test_cpu_recovery_extension', HERE / 'recover.py')
recovery = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = recovery
spec.loader.exec_module(recovery)


@unittest.skipUnless(os.geteuid() == 1000 and os.getegid() == 1000 and shutil.which('ffmpeg'),
                     'BLOCKED: frozen storage needs UID/GID1000 and real FFmpeg')
class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory(prefix='.cpu-media-', dir=HERE)
        cls.source = Path(cls.media.name) / 'segment.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'lavfi', '-i',
                        'testsrc2=size=64x96:rate=30', '-frames:v', '200', '-c:v', 'libx264', '-threads', '1',
                        '-preset', 'ultrafast', '-crf', '18', '-bf', '0', '-pix_fmt', 'yuv420p', str(cls.source)],
                       check=True, timeout=30, capture_output=True)
        cls.source.chmod(0o600)
        cls.modules = recovery.modules()
        cls.probe = cls.modules['compose'].verify_segment(cls.source, {'startFrame': 0, 'endFrame': 200}, {
            'fps': 30, 'durationSeconds': 80, 'resolution': [64, 96]})

    @classmethod
    def tearDownClass(cls):
        cls.media.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='.cpu-recovery-', dir=HERE)
        self.base = Path(self.temporary.name)
        self.root, self.export = self.base / 'private', self.base / 'shared'
        self.root.mkdir(mode=0o700)
        self.export.mkdir(mode=0o700)
        self.parent = 'studio-' + 'a' * 32
        self.plan = {'testOnly': True, 'durationSeconds': 80, 'fps': 30, 'totalFrames': 2400,
                     'resolution': {'width': 64, 'height': 96}, 'aspectRatio': '9:16',
                     'audioSettings': {'enabled': False, 'mode': 'SILENT'},
                     'renderProfile': {'imageDigest': 'sha256:' + 'b' * 64},
                     'productionV3': {'eventChapters': [{'eventId': 'synthetic-event', 'startFrame': 0, 'endFrame': 2400}]},
                     'scenes': [{'sceneId': 'synthetic-' + str(i), 'startFrame': i * 200, 'endFrame': (i + 1) * 200}
                                for i in range(12)]}
        now = datetime.now(timezone.utc)
        self.approval = {'schema': 'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1', 'approved': True,
                         'planSHA256': recovery._sha(self.plan), 'imageDigest': self.plan['renderProfile']['imageDigest'],
                         'validUntil': (now - timedelta(minutes=1)).isoformat(), 'maxWallSeconds': 3600,
                         'maxRetries': 1, 'maxCostAmount': '1', 'currency': 'USD', 'gpuHourlyRate': '1'}
        self.native_id = 'video-v2-' + recovery._sha(self.plan)[:24]
        self.native = self.root / 'render-v4'
        cache = self.modules['cache']
        with cache.PrivateTree(self.root) as root:
            with root.child(self.parent, create=True) as job:
                job.write_json('STATE.json', {'schema': 'WORLD_ENGINE_STUDIO_JOB_V1', 'jobId': self.parent,
                    'state': 'FAILED', 'errorCode': 'STUDIO_APPROVED_DEADLINE_EXCEEDED', 'profileId': 'V4_ARCHIVAL_80S',
                    'supervisorIdentity': None, 'createdUnix': time.time() - 3600, 'finishedUnix': time.time(),
                    'completedScenes': 12, 'processedFrames': 2400, 'timingsSeconds': {}})
                job.write_json('PLAN.json', self.plan)
                job.write_json('APPROVAL.json', self.approval)
                job.write_json('AUDIO.json', {'enabled': True, 'gain': 0.4, 'exportWav': False,
                    'cues': [{'eventId': 'synthetic-event', 'frame': 120, 'type': 'CLICK', 'gain': 0.5}]})
            with root.child('render-v4', create=True) as native:
                with native.child('cache', create=True):
                    pass
                with native.child(self.native_id, create=True):
                    pass
        self.ledger = {'schema': 'WORLD_ENGINE_UNIVERSAL_JOB_V2', 'jobId': self.native_id,
                       'planSHA256': recovery._sha(self.plan), 'state': 'FAILED', 'testOnly': True,
                       'supervisorIdentity': None, 'rendererIdentity': None, 'completedScenes': {},
                       'progressFrames': 2400, 'sceneCheckpoints': {}}
        scene_cache = cache.SceneCache(self.native / 'cache')
        try:
            for index, scene in enumerate(self.plan['scenes']):
                key = cache.scene_cache_key(self.plan, scene, self.plan['scenes'][index - 1] if index else None,
                    self.plan['scenes'][index + 1] if index + 1 < 12 else None)
                attempt = scene_cache.begin(key)
                target = attempt / 'segment.mp4'
                shutil.copyfile(self.source, target)
                target.chmod(0o600)
                segment = {**self.probe, **scene, 'path': str(target), 'testOnly': True, 'hardwareVerified': False}
                saved = scene_cache.complete(key, attempt, segment)
                self.ledger['completedScenes'][scene['sceneId']] = {'cacheKey': key, 'sha256': saved['sha256']}
        finally:
            scene_cache.close()
        self.save_ledger()
        self.grant = {'schema': 'WORLD_ENGINE_STUDIO_CPU_RECOVERY_AUTHORIZATION_V1', 'approved': True, 'gpuAllowed': False,
                      'parentJobId': self.parent, 'planSHA256': recovery._sha(self.plan),
                      'originalApprovalSHA256': recovery._sha(self.approval), 'validUntil': (now + timedelta(hours=3)).isoformat(),
                      'maxWallSeconds': 10800, 'maxRetries': 0, 'maxAdditionalGpuCostAmount': '0', 'currency': 'USD'}
        with cache.PrivateTree(self.root) as root:
            root.write_json('CPU_GRANT.json', self.grant)
        self.grant_path = self.root / 'CPU_GRANT.json'

    def tearDown(self):
        self.temporary.cleanup()

    def save_ledger(self):
        with self.modules['cache'].PrivateTree(self.native / self.native_id) as job, job.lock():
            job.write_json('JOB.json', self.ledger, replace=True)

    def inventory(self):
        return recovery._inventory(self.parent, self.root, self.export, _test_only=True)

    def inspect(self):
        return recovery.inspect(self.parent, self.root, self.export, _test_only=True)

    def test_completed_counts_require_all_real_receipts(self):
        value = self.inspect()
        self.assertEqual((value['scenes'], value['frames']), (12, 2400))
        self.assertFalse(value['historicalGpuProvenanceVerified'])
        self.assertTrue(value['originalPolicyExpired'])
        self.assertFalse(value['gpuExecuted'])

    def test_missing_cache_and_checkpoint_blocks_without_gpu_fallback(self):
        key = next(iter(self.ledger['completedScenes'].values()))['cacheKey']
        # Fixture mutation only; production recovery never removes a cache.
        shutil.rmtree(self.native / 'cache' / key)
        with self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_RETAINED_CHECKPOINT_REQUIRED'):
            self.inspect()

    def test_corrupt_cache_is_not_trusted(self):
        first = self.inventory()['rows'][0]
        Path(first['path']).write_bytes(b'corrupted-synthetic-fixture')
        with self.assertRaisesRegex(Exception, 'CPU_RECOVERY_RETAINED_CHECKPOINT_REQUIRED'):
            self.inspect()

    def test_corrupt_cache_can_only_fall_back_to_retained_verified_checkpoint(self):
        first, scene = self.inventory()['rows'][0], self.plan['scenes'][0]
        checkpoint = self.modules['delivery'].export_scene_checkpoint(self.plan, scene, first['segment'], self.export,
                                                                     private_base=self.native / self.native_id)
        self.ledger['sceneCheckpoints'][scene['sceneId']] = checkpoint
        self.save_ledger()
        Path(first['path']).write_bytes(b'corrupted-private-fixture')
        result = self.inventory()
        self.assertEqual(result['rows'][0]['kind'], 'DROPBOX_CHECKPOINT')
        self.assertEqual(result['rows'][0]['privateCacheRejectionCode'], 'CACHE_ARTIFACT_CORRUPT')

    def test_source_hash_is_checked_before_module_execution(self):
        fake = self.base / 'untrusted.py'
        fake.write_text('raise AssertionError("must not execute")\n')
        with self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_SOURCE_CHANGED'):
            recovery._load('_recovery_untrusted_fixture', fake, '0' * 64)

    def test_wrong_plan_cache_key_is_rejected(self):
        next(iter(self.ledger['completedScenes'].values()))['cacheKey'] = 'f' * 64
        self.save_ledger()
        with self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_SCENE_BINDING_MISMATCH'):
            self.inspect()

    def test_scene_count_alone_cannot_establish_completion(self):
        self.ledger['completedScenes'].pop(self.plan['scenes'][-1]['sceneId'])
        self.save_ledger()
        with self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_NOT_ALL_SCENES_COMPLETE'):
            self.inspect()

    def test_expired_new_grant_rejected_old_historical_expiry_retained(self):
        value = self.inventory()
        grant = {**self.grant, 'validUntil': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
        with self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_GRANT_EXPIRED'):
            recovery.validate_grant(grant, value)
        self.assertGreater(recovery.validate_grant(self.grant, value), 0)

    def test_grant_cannot_allow_gpu_cost_retry_or_mismatched_approval(self):
        value = self.inventory()
        for change in ({'gpuAllowed': True}, {'maxAdditionalGpuCostAmount': '1'}, {'maxRetries': 1},
                       {'originalApprovalSHA256': '0' * 64}, {'maxWallSeconds': 10801}):
            with self.subTest(change=change), self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_EXPLICIT_ZERO_GPU_GRANT_REQUIRED'):
                recovery.validate_grant({**self.grant, **change}, value)

    def test_synthetic_cannot_be_read_as_hardware_provenance(self):
        with self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_TEST_PROVENANCE_MISMATCH'):
            recovery.inspect(self.parent, self.root, self.export)

    def test_alive_process_veto(self):
        with recovery._studio_modules() as studio:
            identity = studio['studio_runtime']._manager().process_identity(os.getpid())
        self.ledger['rendererIdentity'] = identity
        self.save_ledger()
        with self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_NATIVE_PROCESS_STILL_RUNNING'):
            self.inspect()

    def test_unresolved_active_claim_is_preserved_and_blocks(self):
        with self.modules['cache'].PrivateTree(self.root) as root:
            root.write_json('active.json', {'requestId': 'old-start-request', 'jobId': None})
        with self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_UNRESOLVED_ACTIVE_CLAIM'):
            self.inspect()
        self.assertIsNone(json.loads((self.root / 'active.json').read_text())['jobId'])

    def test_failed_cpu_claim_is_not_silently_retried(self):
        with mock.patch.object(self.modules['compose'], 'compose_segments', side_effect=RuntimeError('SYNTHETIC_COMPOSE_FAILURE')):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_COMPOSE_FAILURE'):
                recovery.recover(self.parent, self.grant_path, 'synthetic-failure-0001', self.root, self.export, _test_only=True)
        with self.assertRaisesRegex(recovery.RecoveryError, 'CPU_RECOVERY_ALREADY_CLAIMED_NO_AUTOMATIC_RETRY'):
            recovery.recover(self.parent, self.grant_path, 'synthetic-failure-0001', self.root, self.export, _test_only=True)
        self.assertTrue((self.root / self.parent / 'APPROVAL.json').exists())

    def test_retained_private_anchor_reuses_checkpoint_without_cache(self):
        value = self.inventory()
        first, scene = value['rows'][0], self.plan['scenes'][0]
        checkpoint = self.modules['delivery'].export_scene_checkpoint(self.plan, scene, first['segment'], self.export,
                                                                     private_base=self.native / self.native_id)
        self.ledger['sceneCheckpoints'][scene['sceneId']] = checkpoint
        self.save_ledger()
        key = self.ledger['completedScenes'][scene['sceneId']]['cacheKey']
        shutil.rmtree(self.native / 'cache' / key)
        result = self.inspect()
        self.assertEqual(result['sources'][0], 'DROPBOX_CHECKPOINT')
        self.assertTrue(Path(checkpoint['privateAnchor']).exists())
        target = self.export / checkpoint['exportDirectory'] / 'segment.mp4'
        target.write_bytes(b'corrupted-shared-fixture')
        with self.assertRaises(Exception):
            self.inspect()

    def test_actual_80_seconds_12_scene_cpu_sfx_recovery_immutable_idempotent(self):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        with recovery._studio_modules() as studio, \
             mock.patch.object(studio['studio_runtime'], '_call_original', side_effect=AssertionError('GPU coordinator forbidden')) as coordinator, \
             mock.patch.object(studio['studio_runtime'], '_health', side_effect=AssertionError('GPU probe forbidden')) as gpu:
            result = recovery.recover(self.parent, self.grant_path, 'synthetic-recovery-0001', self.root, self.export, _test_only=True)
            repeat = recovery.recover(self.parent, self.grant_path, 'synthetic-recovery-0001', self.root, self.export, _test_only=True)
            coordinator.assert_not_called()
            gpu.assert_not_called()
        self.assertEqual(result, repeat)
        self.assertEqual((result['frames'], result['scenes'], result['durationSeconds']), (2400, 12, 80))
        self.assertEqual(result['state'], 'COMPLETED')
        self.assertTrue(result['testOnly'])
        self.assertFalse(result['gpuExecuted'])
        self.assertFalse(result['historicalGpuProvenanceVerified'])
        self.assertTrue(result['videoDecodedPixelsUnchanged'])
        self.assertEqual(result['fullDecode'], 'PASS')
        self.assertFalse(result['externalDownloadVerified'])
        for name, digest in before.items():
            self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(), digest, name)
        folder = self.export / result['result']['exportDirectory']
        summary = json.loads((folder / 'QUALITY_SUMMARY.json').read_text())
        self.assertEqual(summary['audioStreams'], 1)
        self.assertEqual(summary['frames'], 2400)
        self.assertEqual(summary['visualQuality'], 'USER_VIDEO_REVIEW_REQUIRED')
        # Once the original coordinator's COMPLETE silent receipt exists, no
        # scene cache or new composition is needed. This is still TEST_ONLY.
        silent = json.loads((self.root / 'cpu-recoveries' / result['recoveryId'] / 'SILENT_EXPORT.json').read_text())
        self.ledger.update(state='COMPLETED', result=silent, gpuRenderingVerified=False)
        self.save_ledger()
        shutil.rmtree(self.native / 'cache')
        self.assertEqual(self.inspect()['sourceMode'], 'VERIFIED_EXISTING_SILENT_EXPORT')
        with mock.patch.object(self.modules['compose'], 'compose_segments', side_effect=AssertionError('recomposition forbidden')) as composed:
            alternate = recovery.recover(self.parent, self.grant_path, 'synthetic-recovery-0002', self.root, self.export, _test_only=True)
        composed.assert_not_called()
        self.assertEqual(alternate['state'], 'COMPLETED')
        self.assertEqual(alternate['skippedStages'], ['SCENE_COPY', 'COMPOSE', 'SILENT_EXPORT'])
        self.assertNotEqual(alternate['result']['exportDirectory'], result['result']['exportDirectory'])
        evidence = os.environ.get('CPU_RECOVERY_EVIDENCE_PATH')
        if evidence:
            safe = {'schema': 'WORLD_ENGINE_CPU_RECOVERY_SYNTHETIC_80S_V1', 'testOnly': True,
                    'userProductionVideoRecovered': False, 'frames': 2400, 'scenes': 12, 'durationSeconds': 80,
                    'width': 64, 'height': 96, 'fps': 30, 'audioStreams': summary['audioStreams'],
                    'fullDecode': result['fullDecode'], 'videoDecodedPixelsUnchanged': True,
                    'gpuExecuted': False, 'externalDropboxDownloadVerified': False,
                    'originalInputBytesUnchanged': True, 'duplicateRequestReused': True,
                    'timingsSeconds': result['timingsSeconds'], 'elapsedSeconds': result['elapsedSeconds'],
                    'existingSilentReuse': {'composeCalled': False, 'status': alternate['state'],
                                            'timingsSeconds': alternate['timingsSeconds'],
                                            'elapsedSeconds': alternate['elapsedSeconds']}}
            descriptor = os.open(evidence, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'w') as output:
                json.dump(safe, output, indent=2, allow_nan=False)
                output.write('\n')


if __name__ == '__main__':
    unittest.main()
