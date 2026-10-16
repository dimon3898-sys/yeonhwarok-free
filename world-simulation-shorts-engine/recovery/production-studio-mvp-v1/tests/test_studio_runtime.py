"""Focused CPU protocol tests. Mocks never establish NVIDIA verification."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import studio_runtime as runtime
import studio_delivery as delivery


class StudioRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = runtime.default_plan('V4_ARCHIVAL_80S')
        cls.digest = 'sha256:' + 'a' * 64
        cls.plan = runtime.bind_render_image(cls.original, 'V4_ARCHIVAL_80S', cls.digest)

    def setUp(self):
        # This managed environment's /tmp belongs to nobody, unlike root-owned
        # sticky /tmp. Preserve the real private-parent checks; choose a safe
        # owned workspace instead of weakening or mocking those checks.
        temporary_parent = '/tmp' if os.stat('/tmp').st_uid == 0 else str(HERE)
        self.temporary = tempfile.TemporaryDirectory(prefix='.studio-runtime-test-', dir=temporary_parent)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'private'; self.root.mkdir(mode=0o700)
        self.export = self.base / 'shared'; self.export.mkdir(mode=0o700)
        self.env = mock.patch.dict(os.environ, WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST=self.digest)
        self.env.start()

    def tearDown(self):
        self.env.stop(); self.temporary.cleanup()

    def audio(self):
        return {'enabled': False, 'gain': 0.5, 'exportWav': False, 'cues': []}

    def approval(self):
        return {'schema': 'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1', 'approved': True,
                'planSHA256': runtime._cache().canonical_sha256(self.plan), 'imageDigest': self.digest,
                'validUntil': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                'maxWallSeconds': 600, 'maxRetries': 1, 'maxCostAmount': '1', 'currency': 'USD', 'gpuHourlyRate': '1'}

    def queue(self, request='test-request-0001', approval=None):
        with mock.patch.object(runtime.subprocess, 'Popen', return_value=mock.Mock(pid=os.getpid())) as spawn:
            state = runtime._start_supervisor(self.plan, 'V4_ARCHIVAL_80S', approval or self.approval(), self.audio(), request,
                control_root=self.root, export_root=self.export)
        return state, spawn

    def alter(self, job_id, **values):
        with runtime._cache().PrivateTree(self.root) as root, root.child(job_id) as job, job.lock():
            state = job.json('STATE.json'); state.update(values); job.write_json('STATE.json', state, replace=True)

    def test_v4_rebind_preserves_evidence_geometry_camera_and_duration(self):
        runtime.validate_render_plan(self.plan, 'V4_ARCHIVAL_80S')
        for field in ('sourceManifest', 'legacyScenePlan', 'productionV3', 'cameraProfile', 'durationSeconds', 'totalFrames'):
            self.assertEqual(self.original[field], self.plan[field])
        self.assertNotEqual(self.original['renderProfile']['imageDigest'], self.plan['renderProfile']['imageDigest'])

    def test_v3_rebind_preserves_native_sources(self):
        old = runtime.default_plan('UNIVERSAL_V3')
        plan = runtime.bind_render_image(old, 'UNIVERSAL_V3', self.digest)
        runtime.validate_render_plan(plan, 'UNIVERSAL_V3')
        self.assertEqual(old['sourceManifest'], plan['sourceManifest'])

    def test_v4_arbitrary_geometry_change_is_rejected(self):
        bad = copy.deepcopy(self.plan); bad['legacyScenePlan']['subject']['label'] += ' changed'
        with self.assertRaisesRegex(RuntimeError, 'FRONT_EXECUTION_PLAN_DATA_OR_TIMELINE_MISMATCH'):
            runtime.validate_render_plan(bad, 'V4_ARCHIVAL_80S')

    def test_v4_long_duration_cannot_silently_stretch_dates(self):
        bad = copy.deepcopy(self.plan); bad['durationSeconds'] = 120
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_ARCHIVAL_PROFILE_EXACT_80_SECONDS_REQUIRED'):
            runtime.bind_render_image(bad, 'V4_ARCHIVAL_80S', self.digest)

    def test_gpu_plan_audio_cannot_bypass_silent_renderer(self):
        bad = copy.deepcopy(self.plan); bad['audioSettings'] = {'enabled': True}
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_GPU_PLAN_MUST_REMAIN_SILENT'):
            runtime.validate_render_plan(bad, 'V4_ARCHIVAL_80S')

    def test_wrong_configured_immutable_image_is_rejected(self):
        with mock.patch.dict(os.environ, WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST='sha256:' + 'b' * 64):
            with self.assertRaisesRegex(RuntimeError, 'STUDIO_PLAN_IMAGE_BINDING_MISMATCH'):
                runtime.validate_render_plan(self.plan, 'V4_ARCHIVAL_80S')

    def test_production_start_requires_explicit_configured_image(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(runtime, '_start_supervisor') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'STUDIO_CONFIGURED_IMMUTABLE_IMAGE_REQUIRED'):
                runtime.start_studio_job(self.plan, 'V4_ARCHIVAL_80S', self.root / 'missing.json', self.audio(),
                    'production-test-1', control_root=self.root, export_root=self.export)
        spawn.assert_not_called()

    def test_approval_requires_exact_plan_and_nonexpired_cost_caps(self):
        runtime._validate_child(self.plan, 'V4_ARCHIVAL_80S', 'approval', approval=self.approval())
        wrong = self.approval(); wrong['planSHA256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'APPROVAL_PLAN_MISMATCH'):
            runtime._validate_child(self.plan, 'V4_ARCHIVAL_80S', 'approval', approval=wrong)
        wrong = self.approval(); wrong['maxCostAmount'] = '0.001'
        with self.assertRaisesRegex(RuntimeError, 'TIME_CEILING_EXCEEDS_APPROVED_COST'):
            runtime._validate_child(self.plan, 'V4_ARCHIVAL_80S', 'approval', approval=wrong)

    def test_detach_disconnects_descriptors_and_uses_fixed_worker(self):
        state, spawn = self.queue()
        command = spawn.call_args.args[0]; options = spawn.call_args.kwargs
        self.assertEqual(command[:4], ['/usr/bin/python3', '-B', str(HERE / 'studio_runtime.py'), 'worker'])
        self.assertTrue(options['start_new_session']); self.assertTrue(options['close_fds'])
        self.assertEqual(options['stdin'], subprocess.DEVNULL)
        self.assertEqual(state['state'], 'QUEUED')

    def test_duplicate_touch_uses_same_claim_without_relaunch(self):
        first, _ = self.queue()
        with mock.patch.object(runtime.subprocess, 'Popen') as spawn:
            again = runtime._start_supervisor(self.plan, 'V4_ARCHIVAL_80S', self.approval(), self.audio(), 'test-request-0001',
                control_root=self.root, export_root=self.export)
        self.assertEqual(first['jobId'], again['jobId']); spawn.assert_not_called()

    def test_second_job_rejected_while_existing_supervisor_alive(self):
        self.queue()
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_ANOTHER_JOB_IS_ACTIVE'):
            self.queue('test-request-0002')

    def test_failed_supervisor_does_not_ignore_running_original_gpu(self):
        queued, _ = self.queue(); self.alter(queued['jobId'], state='FAILED', supervisorIdentity=None)
        with mock.patch.object(runtime, 'status', return_value={'state': 'RUNNING'}):
            with self.assertRaisesRegex(RuntimeError, 'STUDIO_ANOTHER_JOB_IS_ACTIVE'):
                self.queue('test-request-0002')

    def test_status_of_dead_supervisor_never_automatically_starts_worker(self):
        queued, _ = self.queue(); self.alter(queued['jobId'], supervisorIdentity=None)
        with mock.patch.object(runtime.subprocess, 'Popen') as spawn:
            state = runtime.studio_status(queued['jobId'], control_root=self.root, export_root=self.export)
        self.assertEqual(state['state'], 'INTERRUPTED'); spawn.assert_not_called()
        self.assertNotIn('supervisorIdentity', state)

    def test_sfx_revision_uses_silent_ancestry_without_gpu_start_or_approval(self):
        queued, _ = self.queue()
        self.alter(queued['jobId'], state='COMPLETED', gpuRenderingVerified=True,
                   result={'TEST_ONLY_RECEIPT': True}, silentResult={'TEST_ONLY_SILENT': True})
        with mock.patch.object(delivery, 'verify_export') as verify, \
             mock.patch.object(runtime, '_start_supervisor', return_value={'state': 'QUEUED'}) as spawn, \
             mock.patch.object(runtime, '_call_original') as native:
            result = runtime.start_studio_revision(queued['jobId'], self.audio(), 'revision-request-1',
                control_root=self.root, export_root=self.export)
        self.assertEqual(result['state'], 'QUEUED'); native.assert_not_called(); verify.assert_called_once()
        self.assertIsNone(spawn.call_args.args[2]); self.assertEqual(spawn.call_args.kwargs['silent_result'], {'TEST_ONLY_SILENT': True})

    def test_cpu_only_parent_cannot_authorize_hardware_result_reuse(self):
        queued, _ = self.queue(); self.alter(queued['jobId'], state='COMPLETED', gpuRenderingVerified=False)
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_COMPLETED_HARDWARE_PARENT_REQUIRED'):
            runtime.start_studio_revision(queued['jobId'], self.audio(), 'revision-request-1', control_root=self.root, export_root=self.export)

    def test_explicit_recovery_retains_original_approval_and_claim(self):
        approval = self.approval(); queued, _ = self.queue(approval=approval)
        self.alter(queued['jobId'], state='FAILED', supervisorIdentity=None)
        location = self.root / 'approval.json'
        with runtime._cache().PrivateTree(self.root) as directory:directory.write_json(location.name, approval)
        with mock.patch.object(runtime, '_start_supervisor', return_value={'state': 'QUEUED'}) as spawn:
            runtime.start_studio_recovery(queued['jobId'], location, 'recovery-request-1', control_root=self.root, export_root=self.export)
        self.assertTrue(spawn.call_args.kwargs['resume_render'])
        self.assertEqual(spawn.call_args.args[2], approval)
        self.assertTrue((self.root / queued['jobId'] / 'STATE.json').is_file())

    def test_recovery_cannot_reset_or_extend_budget_caps(self):
        approval = self.approval(); queued, _ = self.queue(approval=approval)
        self.alter(queued['jobId'], state='FAILED', supervisorIdentity=None)
        changed = dict(approval, maxRetries=2)
        with runtime._cache().PrivateTree(self.root) as directory:directory.write_json('approval.json', changed)
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_RECOVERY_ORIGINAL_APPROVAL_CAPS_REQUIRED'):
            runtime.start_studio_recovery(queued['jobId'], self.root / 'approval.json', 'recovery-request-1', control_root=self.root, export_root=self.export)

    def test_original_resume_command_cannot_be_caller_selected(self):
        with mock.patch.object(runtime.subprocess, 'run', return_value=mock.Mock(returncode=0, stdout=b'{"state":"QUEUED"}')) as run:
            runtime._call_original('start', self.plan, 'V4_ARCHIVAL_80S', self.root / 'PLAN.json', self.root / 'APPROVAL.json',
                control_root=self.root, export_root=self.export, resume=True)
        command = run.call_args.args[0]
        self.assertEqual(command[2], str(runtime.RECOVERY / 'verified-front-data-v4-recovery/orchestrator.py'))
        self.assertIn('--resume', command)

    def test_free_preflight_never_invents_nvidia_pass(self):
        with mock.patch.object(runtime, '_health', side_effect=RuntimeError('STUDIO_EXISTING_GPU_HEALTH_UNAVAILABLE')):
            result = runtime.preflight(self.plan, 'V4_ARCHIVAL_80S', control_root=self.root, export_root=self.export)
        self.assertEqual(result['status'], 'BLOCKED'); self.assertFalse(result['renderAllowed'])
        self.assertFalse(result['gpuRenderingVerified'])
        self.assertTrue(any(row['name'] == 'CURRENT_GPU_HEALTH' and row['status'] == 'BLOCKED' for row in result['checks']))

    def test_frozen_health_normalized_models_are_accepted_without_alias_guessing(self):
        # Values are exactly gpu_launcher._model_name + health_payload output;
        # this is a mocked HTTP contract, never a hardware execution claim.
        connection = mock.Mock(); response = mock.Mock(status=200)
        connection.getresponse.return_value = response
        for model in ('RTX 4080 SUPER', 'RTX 4090', 'RTX 5090'):
            response.read.return_value = json.dumps({'gpuRenderingVerified': True, 'testOnly': False,
                'renderMode': 'gpu-required', 'model': model, 'physicalMemoryMiB': 16384}).encode()
            with mock.patch.object(runtime.http.client, 'HTTPConnection', return_value=connection):
                self.assertEqual(runtime._health()['model'], model)
        response.read.return_value = json.dumps({'gpuRenderingVerified': True, 'testOnly': True,
            'renderMode': 'gpu-required', 'model': 'RTX 4080 SUPER'}).encode()
        with mock.patch.object(runtime.http.client, 'HTTPConnection', return_value=connection):
            with self.assertRaisesRegex(RuntimeError, 'STUDIO_PHYSICAL_GPU_HEALTH_REQUIRED'):runtime._health()

    def test_shared_file_growth_stops_before_private_copy_exceeds_initial_size(self):
        storage = delivery._storage()
        target = self.export / 'growing.mp4'; target.write_bytes(b'abc')
        descriptor = os.open(self.export, os.O_RDONLY | os.O_DIRECTORY)
        real_read = os.read; expanded = False
        def grow(source, length):
            nonlocal expanded
            if not expanded:
                expanded = True
                with target.open('ab') as output:output.write(b'0123456789')
            return real_read(source, length)
        private = self.root / 'copy.mp4'
        try:
            with mock.patch.object(delivery.os, 'read', side_effect=grow):
                with self.assertRaisesRegex(RuntimeError, 'STUDIO_EXPORT_CHANGED_DURING_READ'):
                    delivery._facts(storage, descriptor, target.name, copy_to=private)
            self.assertFalse(private.exists())
        finally:os.close(descriptor)

    def test_copy_failure_never_deletes_an_existing_private_file(self):
        target = self.export / 'source.mp4'; target.write_bytes(b'abc')
        private = self.root / 'existing.mp4'; private.write_bytes(b'preserved')
        descriptor = os.open(self.export, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with self.assertRaises(FileExistsError):delivery._facts(delivery._storage(), descriptor, target.name, copy_to=private)
            self.assertEqual(private.read_bytes(), b'preserved')
        finally:os.close(descriptor)

    def test_export_symlink_and_path_traversal_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_EXPORT_LOCATION_INVALID'):
            delivery._export_fd(delivery._storage(), self.export, '../../private')
        real = self.export / ('world-engine-export-' + 'a' * 24); real.mkdir()
        (real / ('studio-' + 'b' * 24)).symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            delivery._export_fd(delivery._storage(), self.export, real.name + '/studio-' + 'b' * 24)

    @unittest.skipUnless(os.geteuid() == 1000 and os.getegid() == 1000, 'BLOCKED: real frozen exporter requires UID/GID1000')
    def test_actual_cpu_mux_versioned_export_readback_and_tamper_rejection(self):
        # Real FFmpeg and real storage primitives, deliberately tiny synthetic
        # content. No GPU coordinator, NVIDIA claim, or historical video exists.
        source = self.root / 'synthetic.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'lavfi', '-i', 'testsrc2=size=64x96:rate=30',
                        '-frames:v', '60', '-c:v', 'libx264', '-threads', '1', '-preset', 'ultrafast', '-crf', '18',
                        '-bf', '0', '-pix_fmt', 'yuv420p', str(source)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
        os.chmod(source, 0o600)
        plan = {'durationSeconds': 2, 'fps': 30, 'totalFrames': 60, 'resolution': {'width': 64, 'height': 96},
                'productionV3': {'eventChapters': [{'eventId': 'fixture-click', 'startFrame': 10, 'endFrame': 11}]},
                'scenes': [{'sceneId': 'synthetic', 'startFrame': 0, 'endFrame': 60}]}
        compose = runtime._load('_studio_test_existing_compose', runtime.RECOVERY / 'universal-auto-video-v2/compose.py')
        legacy = runtime._load('_studio_test_existing_delivery', runtime.RECOVERY / 'universal-auto-video-v2/delivery.py')
        segment = {'sceneId': 'synthetic', 'startFrame': 0, 'endFrame': 60, 'path': str(source),
                   'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        composed = compose.compose_segments(plan, [segment], self.root / 'old-composition')
        # The unchanged composer leaves its newly produced MP4 at0644.
        for path in Path(composed['publicDir']).iterdir():os.chmod(path, 0o600)
        silent = legacy.export_video(plan, composed, self.export)
        final_job = self.root / 'finalization'; final_job.mkdir(mode=0o700)
        audio = {'enabled': True, 'gain': 0.4, 'exportWav': True,
                 'cues': [{'eventId': 'fixture-click', 'frame': 10, 'type': 'CLICK', 'gain': 0.5}]}
        result = runtime.finalize(plan, audio, silent, final_job, self.export)
        self.assertTrue(result['mountedViewReadbackVerified']); self.assertFalse(result['externalDownloadVerified'])
        self.assertEqual({row['name'] for row in result['files']}, delivery.PUBLIC)
        delivery.verify_export(result, self.export)
        folder = self.export / result['exportDirectory']
        safe = json.loads((folder / 'QUALITY_SUMMARY.json').read_text())
        self.assertEqual(safe['audioStreams'], 1); self.assertTrue(safe['videoDecodedPixelsUnchanged'])
        self.assertEqual(safe['visualQuality'], 'USER_VIDEO_REVIEW_REQUIRED')
        (folder / 'WORLD_ENGINE_STUDIO_VIDEO.mp4').write_bytes(b'corrupted-new-test-export')
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_EXPORT_HASH_MISMATCH'):
            delivery.verify_export(result, self.export)


if __name__ == '__main__':unittest.main()
