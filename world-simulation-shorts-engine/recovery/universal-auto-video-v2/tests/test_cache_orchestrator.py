"""Focused CPU control-plane tests; fake media is never NVIDIA/video evidence."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cache import CacheError, PrivateTree, SceneCache, canonical_sha256, scene_cache_key, _pinned_path
from contracts import canonical_sha256 as plan_sha
from planner import bind_renderer, plan_topic
import orchestrator as coordinator


def approval(plan, **changes):
    return {'schema': coordinator.AUTH_SCHEMA, 'approved': True,
        'planSHA256': canonical_sha256(plan), 'imageDigest': plan['renderProfile']['imageDigest'],
        'validUntil': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        'maxWallSeconds': 1800, 'maxRetries': 0, 'maxCostAmount': '10',
        'currency': 'USD', 'gpuHourlyRate': '1', **changes}


def private_bytes(path, data):
    with open(path, 'xb') as stream:
        stream.write(data)
    os.chmod(path, 0o600)


def test_temp_parent():
    """Write tests outside the immutable source tree in image and checkout."""
    for candidate in (Path(tempfile.gettempdir()), Path('/workspace')):
        if not candidate.is_dir() or candidate.is_symlink() or not os.access(candidate, os.W_OK):
            continue
        info = candidate.stat()
        root_sticky = info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
        if info.st_uid in {0, os.geteuid()} and (not info.st_mode & 0o022 or root_sticky):
            return candidate
    raise unittest.SkipTest('BLOCKED: no safe writable test temporary parent')


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=test_temp_parent())
        self.root = Path(self.temp.name)
        self.cache = SceneCache(self.root / 'cache', create=True)
        self.key = '1' * 64

    def tearDown(self):
        self.cache.close()
        self.temp.cleanup()

    def segment(self):
        attempt = self.cache.begin(self.key)
        path = attempt / 'segment.mp4'
        private_bytes(path, b'TEST_ONLY_NOT_A_VIDEO')
        return attempt, {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'sceneId': 'fixture', 'startFrame': 0, 'endFrame': 2, 'testOnly': True,
            'technical': 'PASS', 'frameCountVerified': True}

    def test_canonical_hash_matches_scene_contract(self):
        self.assertEqual(canonical_sha256({'b': 1, 'a': '지형'}), plan_sha({'b': 1, 'a': '지형'}))

    def test_deployed_alias_preferred_with_exact_hash(self):
        deployed, checkout = self.root / 'deployed.py', self.root / 'checkout.py'
        body = b'PINNED_ORIGINAL_FIXTURE'
        private_bytes(deployed, body)
        private_bytes(checkout, body)
        self.assertEqual(_pinned_path(deployed, checkout, hashlib.sha256(body).hexdigest()), deployed)

    def test_checkout_fallback_only_when_deployed_alias_absent(self):
        deployed, checkout = self.root / 'absent.py', self.root / 'checkout.py'
        body = b'PINNED_ORIGINAL_FIXTURE'
        private_bytes(checkout, body)
        self.assertEqual(_pinned_path(deployed, checkout, hashlib.sha256(body).hexdigest()), checkout)

    def test_corrupt_deployed_alias_does_not_fall_back_to_good_checkout(self):
        deployed, checkout = self.root / 'deployed.py', self.root / 'checkout.py'
        body = b'PINNED_ORIGINAL_FIXTURE'
        private_bytes(deployed, b'CORRUPT_DEPLOYED')
        private_bytes(checkout, body)
        with self.assertRaisesRegex(RuntimeError, 'PINNED_DEPENDENCY_SOURCE_CHANGED'):
            _pinned_path(deployed, checkout, hashlib.sha256(body).hexdigest())

    def test_deployed_symlink_and_missing_dependency_fail_closed(self):
        deployed, checkout = self.root / 'deployed.py', self.root / 'checkout.py'
        body = b'PINNED_ORIGINAL_FIXTURE'
        private_bytes(checkout, body)
        deployed.symlink_to(checkout)
        with self.assertRaisesRegex(RuntimeError, 'PINNED_DEPENDENCY_SYMLINK_FORBIDDEN'):
            _pinned_path(deployed, checkout, hashlib.sha256(body).hexdigest())
        with self.assertRaisesRegex(RuntimeError, 'PINNED_DEPENDENCY_UNAVAILABLE'):
            _pinned_path(self.root / 'absent.py', self.root / 'also-absent.py', hashlib.sha256(body).hexdigest())

    def test_success_reuse_rehashes_actual_file(self):
        attempt, segment = self.segment()
        self.cache.complete(self.key, attempt, segment)
        found = self.cache.lookup(self.key)
        self.assertTrue(found['cacheHit'])
        self.assertEqual(found['sha256'], segment['sha256'])
        self.assertEqual(Path(found['path']), Path(segment['path']))

    def test_failed_attempt_is_not_cached_as_success(self):
        self.segment()
        self.assertIsNone(self.cache.lookup(self.key))

    def test_unverified_partial_segment_rejected(self):
        attempt, segment = self.segment()
        segment['frameCountVerified'] = False
        with self.assertRaisesRegex(CacheError, 'SEGMENT_VERIFICATION_REQUIRED'):
            self.cache.complete(self.key, attempt, segment)
        self.assertIsNone(self.cache.lookup(self.key))

    def test_corrupt_completed_segment_rejected_not_deleted(self):
        attempt, segment = self.segment()
        self.cache.complete(self.key, attempt, segment)
        Path(segment['path']).write_bytes(b'CORRUPTED')
        with self.assertRaisesRegex(CacheError, 'CACHE_ARTIFACT_CORRUPT'):
            self.cache.lookup(self.key)
        self.assertTrue(attempt.exists())

    def test_corrupt_receipt_rejected(self):
        attempt, segment = self.segment()
        self.cache.complete(self.key, attempt, segment)
        (attempt / 'COMPLETE.json').write_bytes(b'{}')
        with self.assertRaisesRegex(CacheError, 'CACHE_RECEIPT_CORRUPT'):
            self.cache.lookup(self.key)

    def test_symlink_artifact_and_parent_rejected(self):
        attempt, segment = self.segment()
        Path(segment['path']).unlink()
        external = self.root / 'existing.mp4'
        private_bytes(external, b'EXISTING_DO_NOT_CHANGE')
        Path(segment['path']).symlink_to(external)
        with self.assertRaises(OSError):
            self.cache.complete(self.key, attempt, segment)
        linked = self.root / 'linked'
        linked.symlink_to(self.root / 'cache')
        with self.assertRaises(OSError):
            PrivateTree(linked)
        self.assertEqual(external.read_bytes(), b'EXISTING_DO_NOT_CHANGE')

    def test_hardlink_artifact_rejected(self):
        attempt, segment = self.segment()
        os.link(segment['path'], self.root / 'second.mp4')
        with self.assertRaisesRegex(CacheError, 'PRIVATE_PATH_REQUIRED'):
            self.cache.complete(self.key, attempt, segment)

    def test_duplicate_process_lock_rejected(self):
        with self.cache.tree.lock():
            with self.assertRaisesRegex(CacheError, 'JOB_OR_CACHE_BUSY'):
                with self.cache.tree.lock():
                    self.fail('second independent file description acquired lock')

    def test_wrong_owner_mode_shared_root_and_path_traversal_rejected(self):
        os.chmod(self.root / 'cache', 0o755)
        with self.assertRaisesRegex(CacheError, 'PRIVATE_PATH_REQUIRED'):
            PrivateTree(self.root / 'cache')
        with self.assertRaisesRegex(CacheError, 'SHARED_STORAGE'):
            PrivateTree('/world-storage/cache')
        with self.assertRaisesRegex(CacheError, 'UNSAFE_NAME'):
            self.cache.tree.child('../existing')

    def test_cache_key_all_dependencies_and_neighbor_boundaries(self):
        plan = {'fps': 30, 'resolution': {'width': 1080, 'height': 1920},
            'sourceManifest': {'sha256': 'a'}, 'renderProfile': {'version': 'one'},
            'encoder': {'codec': 'h264'}, 'legacyScenePlan': {'timeline': 1}}
        scene = {'sceneId': 'a', 'cameraProfile': {'x': 1}, 'materialProfile': {'a': 2}, 'eventTimeline': [1]}
        before, after = {'boundaryEnd': {'x': 2}}, {'boundaryStart': {'x': 3}}
        original = scene_cache_key(plan, scene, before, after)
        for key in ('sourceManifest', 'renderProfile', 'encoder', 'legacyScenePlan'):
            changed = deepcopy(plan)
            changed[key]['changed'] = True
            self.assertNotEqual(original, scene_cache_key(changed, scene, before, after), key)
        for key in ('cameraProfile', 'materialProfile', 'eventTimeline'):
            changed = deepcopy(scene)
            changed[key] = {'changed': True}
            self.assertNotEqual(original, scene_cache_key(plan, changed, before, after), key)
        self.assertNotEqual(original, scene_cache_key(plan, scene, {'boundaryEnd': {'x': 4}}, after))
        self.assertNotEqual(original, scene_cache_key(plan, scene, before, {'boundaryStart': {'x': 4}}))
        changed = deepcopy(plan)
        changed['title'] = 'metadata-only change'
        self.assertEqual(original, scene_cache_key(changed, scene, before, after))


class OrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = plan_topic('한국전쟁의 전선 변화를 80초 영상으로 만들어줘.')
        cls.plan = bind_renderer(source, {'adapter': 'UNIVERSAL_AREA_ASTRA_V2', 'gpuMode': 'gpu-required',
            'status': 'READY', 'imageDigest': 'sha256:' + '2' * 64,
            'rendererCapability': 'POLYGON_STATE_TIMELINE',
            'nativePayload': {'path': 'TEST_ONLY_NATIVE.json', 'sha256': '3' * 64, 'validationStatus': 'VERIFIED'}})

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=test_temp_parent())
        self.root = Path(self.temp.name)
        self.control = self.root / 'control'
        self.plan = deepcopy(self.__class__.plan)
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def components(self, fail=None):
        def render(plan, scene, directory, *, approval, progress=None):
            self.calls.append(scene['sceneId'])
            if fail:
                fail(scene)
            path = Path(directory) / 'segment.mp4'
            private_bytes(path, ('TEST_ONLY_SYNTHETIC_CONTROL:' + scene['sceneId']).encode())
            return {'sceneId': scene['sceneId'], 'startFrame': scene['startFrame'], 'endFrame': scene['endFrame'],
                    'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        def verify(path, scene, plan):
            return {'technical': 'PASS', 'frameCountVerified': True, 'fullDecodeVerified': False,
                    'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
        def compose(plan, segments, directory):
            self.assertEqual([s['sceneId'] for s in segments], [s['sceneId'] for s in plan['scenes']])
            directory.mkdir(mode=0o700)
            return {'path': str(directory / 'TEST_ONLY.mp4'), 'testOnly': True}
        def export(*_):
            destination = self.root / ('CPU_ONLY_MOUNTED-' + os.urandom(4).hex())
            private_bytes(destination, b'CPU_ONLY_SYNTHETIC_DELIVERY')
            return {'mountedViewReadbackVerified': True, 'path': str(destination),
                    'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                    'externalDownloadVerified': False, 'remotePersistenceVerified': False, 'testOnly': True}
        def verify_completed(value, _root):
            if hashlib.sha256(Path(value['path']).read_bytes()).hexdigest() != value['sha256']:
                raise ValueError('CPU_ONLY_HASH_MISMATCH')
            return value
        return {'render': render, 'verify': verify, 'compose': compose, 'lease': nullcontext,
                'export': export, 'verify_completed': verify_completed}

    def run(self, result=None):
        # Keep unittest's own run method; job execution is named execute below.
        return super().run(result)

    def execute(self, **kwargs):
        return coordinator.run_job(self.plan, control_root=self.control, export_root=self.root / 'export',
            approval=kwargs.pop('approval', approval(self.plan)), _test_components=kwargs.pop('components', self.components()), **kwargs)

    def test_synthetic_control_path_all_scenes_complete_without_gpu_claim(self):
        result = self.execute()
        self.assertEqual(result['state'], 'COMPLETED')
        self.assertEqual(result['progressFrames'], 2400)
        self.assertEqual(len(self.calls), len(self.plan['scenes']))
        self.assertTrue(result['testOnly'])
        self.assertFalse(result['gpuRenderingVerified'])
        self.assertFalse(result['externalDownloadVerified'])

    def test_new_metadata_job_reuses_all_unchanged_segments(self):
        self.execute()
        count = len(self.calls)
        self.plan['title'] = 'another public title, identical pixels'
        result = self.execute()
        self.assertEqual(result['state'], 'COMPLETED')
        self.assertEqual(len(self.calls), count)

    def test_completed_job_rehashes_missing_or_corrupt_final_before_return(self):
        result = self.execute()
        final = Path(result['result']['path'])
        self.assertEqual(self.execute()['completionReverification'], 'MOUNTED_BYTES_REHASHED')
        final.write_bytes(b'CORRUPTED_CPU_ONLY_FINAL')
        with self.assertRaisesRegex(coordinator.CoordinatorError, 'COMPLETED_RESULT_INTEGRITY_FAILED'):
            self.execute()
        final.unlink()
        with self.assertRaisesRegex(coordinator.CoordinatorError, 'COMPLETED_RESULT_INTEGRITY_FAILED'):
            self.execute()
        # No automatic rerender, reset or replacement of historical evidence.
        self.assertEqual(len(self.calls), len(self.plan['scenes']))

    def test_interruption_then_explicit_resume_reuses_completed_scene(self):
        target = self.plan['scenes'][1]['sceneId']
        def stop(scene):
            if scene['sceneId'] == target:
                raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.execute(approval=approval(self.plan, maxRetries=1), components=self.components(stop))
        self.assertEqual(coordinator.status(self.plan, self.control)['state'], 'INTERRUPTED')
        with self.assertRaisesRegex(coordinator.CoordinatorError, 'EXPLICIT_RESUME_REQUIRED'):
            self.execute()
        result = self.execute(resume=True, approval=approval(self.plan, maxRetries=1))
        self.assertEqual(result['state'], 'COMPLETED')
        self.assertEqual(self.calls.count(self.plan['scenes'][0]['sceneId']), 1)
        self.assertEqual(self.calls.count(target), 2)

    def test_failed_segment_retry_is_bounded_across_resume(self):
        def fail(_scene):
            raise RuntimeError('CPU_FIXTURE_FAILED')
        with self.assertRaisesRegex(RuntimeError, 'CPU_FIXTURE_FAILED'):
            self.execute(approval=approval(self.plan, maxRetries=1), components=self.components(fail))
        self.assertEqual(len(self.calls), 2)
        with self.assertRaisesRegex(coordinator.CoordinatorError, 'APPROVED_RETRY_LIMIT_REACHED'):
            self.execute(resume=True, approval=approval(self.plan, maxRetries=1), components=self.components(fail))
        self.assertEqual(len(self.calls), 2)

    def test_corrupt_cache_renders_only_corrupt_scene_preserving_old_attempt(self):
        self.execute()
        original_count = len(self.calls)
        first = self.plan['scenes'][0]
        key = scene_cache_key(self.plan, first, None, self.plan['scenes'][1])
        cache = SceneCache(self.control / 'cache')
        hit = cache.lookup(key)
        old = Path(hit['path'])
        old.write_bytes(b'CORRUPT_OLD_PRESERVED')
        cache.close()
        self.plan['title'] = 'metadata only'
        result = self.execute()
        self.assertEqual(result['state'], 'COMPLETED')
        self.assertEqual(len(self.calls), original_count + 1)
        self.assertEqual(old.read_bytes(), b'CORRUPT_OLD_PRESERVED')

    def test_approval_mismatch_expiry_rate_and_retry_limits_fail_before_render(self):
        cases = [{'approved': False}, {'planSHA256': 'f' * 64}, {'imageDigest': 'sha256:' + 'f' * 64},
            {'maxRetries': 3}, {'maxWallSeconds': 0}, {'gpuHourlyRate': 'NaN'},
            {'maxCostAmount': '0.01'}, {'validUntil': '2020-01-01T00:00:00+00:00'}]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(coordinator.CoordinatorError):
                self.execute(approval=approval(self.plan, **change))
        self.assertEqual(self.calls, [])
        self.assertFalse(self.control.exists())

    def test_unbound_history_plan_blocked_before_gpu_or_private_state(self):
        self.plan = plan_topic('Korean War', duration_seconds=80)
        with self.assertRaisesRegex(ValueError, 'NATIVE_PAYLOAD_REQUIRED'):
            coordinator.run_job(self.plan, control_root=self.control, approval={}, _test_components=self.components())
        self.assertEqual(self.calls, [])
        self.assertFalse(self.control.exists())

    def test_live_duplicate_supervisor_blocks_resume(self):
        self.execute()
        job_id = coordinator._job_id(self.plan)
        with PrivateTree(self.control) as root, root.child(job_id) as job, job.lock():
            state = job.json('JOB.json')
            state.update(state='RUNNING', supervisorIdentity=coordinator._identity(os.getpid()))
            # A real different live process, not a synthetic PID identity.
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
            try:
                state['supervisorIdentity'] = coordinator._identity(child.pid)
                job.write_json('JOB.json', state, replace=True)
                with self.assertRaisesRegex(CacheError, 'JOB_OR_CACHE_BUSY'):
                    self.execute(resume=True)
            finally:
                child.terminate()
                child.wait()

    def test_whole_job_deadline_covers_composition_not_just_gpu_capture(self):
        with self.assertRaisesRegex(coordinator.CoordinatorError, 'APPROVED_JOB_DEADLINE_EXCEEDED'):
            with coordinator.deadline_guard(0.02):
                time.sleep(0.1)
        self.assertEqual(__import__('signal').getitimer(__import__('signal').ITIMER_REAL)[0], 0)

    def test_private_operator_authorization_never_accepts_embedded_credentials(self):
        value = approval(self.plan)
        value['token'] = 'TEST_ONLY_TOKEN_FIELD_NOT_A_REAL_SECRET'
        with self.assertRaisesRegex(coordinator.CoordinatorError, 'EXPLICIT_GPU_APPROVAL_REQUIRED'):
            coordinator.validate_approval(value, self.plan)

    def test_real_detached_cpu_worker_survives_terminal_hangup(self):
        """Replace native worker only in Python test; no fake GPU evidence."""
        approval_path = self.root / 'OPERATOR_APPROVAL.json'
        private_bytes(approval_path, json.dumps(approval(self.plan)).encode())
        marker = self.root / 'CPU_ONLY_DETACHED_RESULT.json'
        original_popen = subprocess.Popen
        parent, terminal = pty.fork()
        if parent == 0:
            try:
                def cpu_worker(command, **options):
                    self.assertEqual(command[2], str(ROOT / 'orchestrator.py'))
                    self.assertEqual(command[3], 'worker')
                    script = ('import json,os,time; from pathlib import Path; time.sleep(0.3); '
                              'Path(' + repr(str(marker)) + ').write_text(json.dumps({"testOnly":True,"sid":os.getsid(0)}))')
                    return original_popen([sys.executable, '-c', script], **options)
                with mock.patch.object(coordinator.subprocess, 'Popen', side_effect=cpu_worker):
                    state = coordinator.start_job(self.plan, approval_path, control_root=self.control)
                    self.assertFalse(state['gpuRenderingVerified'])
                os.write(1, b'CPU_READY\n')
                time.sleep(20)
            finally:
                os._exit(0)
        try:
            data = b''
            expires = time.monotonic() + 5
            while b'CPU_READY' not in data and time.monotonic() < expires:
                ready, _, _ = select.select([terminal], [], [], 0.1)
                if ready:
                    data += os.read(terminal, 4096)
            self.assertIn(b'CPU_READY', data)
        finally:
            os.close(terminal)  # Actual PTY hangup kills the submitting terminal.
            os.waitpid(parent, 0)
        expires = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < expires:
            time.sleep(0.02)
        record = json.loads(marker.read_text())
        self.assertTrue(record['testOnly'])
        self.assertNotEqual(record['sid'], parent)
        state = coordinator.status(self.plan, self.control)
        self.assertEqual(state['observedState'], 'INTERRUPTED')
        self.assertFalse(state['gpuRenderingVerified'])

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'BLOCKED: FFmpeg tools unavailable')
    def test_real_cpu_fixture_pipeline_cache_compose_and_original_dropbox_adapter(self):
        """Actual tiny testsrc media; not WORLD ENGINE/NVIDIA visual proof."""
        import compose
        import delivery
        self.plan = bind_renderer(plan_topic('Korean War', duration_seconds=2,
            resolution={'width': 90, 'height': 160}), self.plan['renderProfile'])
        shared = self.root / 'CPU_ONLY_SHARED_MOUNT'
        shared.mkdir(mode=0o700)
        def render(plan, scene, directory, *, approval, progress=None):
            self.calls.append(scene['sceneId'])
            path = Path(directory) / 'segment.mp4'
            count = scene['endFrame'] - scene['startFrame']
            subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-nostdin', '-f', 'lavfi',
                '-i', 'testsrc2=size=90x160:rate=30', '-frames:v', str(count), '-an',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-pix_fmt', 'yuv420p',
                '-threads', '1', str(path)], check=True, timeout=30, capture_output=True)
            os.chmod(path, 0o600)
            return {'sceneId': scene['sceneId'], 'startFrame': scene['startFrame'],
                'endFrame': scene['endFrame'], 'path': str(path),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'hardwareVerified': False}
        components = {'render': render, 'verify': compose.verify_segment,
            'compose': compose.compose_segments, 'export': delivery.export_video,
            'lease': nullcontext, 'verify_completed': delivery.verify_mounted_export,
            'checkpoint': delivery.export_scene_checkpoint, 'verify_checkpoint': delivery.verify_scene_checkpoint}
        result = coordinator.run_job(self.plan, control_root=self.control, export_root=shared,
            approval=approval(self.plan), _test_components=components)
        self.assertEqual(result['state'], 'COMPLETED')
        self.assertEqual(result['progressFrames'], 60)
        self.assertEqual(len(result['sceneCheckpoints']), len(self.plan['scenes']))
        self.assertTrue(result['testOnly'])
        self.assertFalse(result['gpuRenderingVerified'])
        self.assertFalse(result['externalDownloadVerified'])
        checked = coordinator.run_job(self.plan, control_root=self.control, export_root=shared,
            approval=approval(self.plan), _test_components=components)
        self.assertEqual(checked['completionReverification'], 'MOUNTED_BYTES_REHASHED')
        self.assertEqual(len(self.calls), len(self.plan['scenes']))


if __name__ == '__main__':
    unittest.main()
