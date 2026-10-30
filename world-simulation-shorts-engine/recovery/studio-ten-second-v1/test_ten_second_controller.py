"""Focused NEW optional-10s controller contracts; no accepted suite is imported.

Media files and child-process outputs are synthetic. These tests prove validation
and state boundaries, never NVIDIA rendering, GPU cleanup or an encoded video.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
CONTROLLER = HERE.parent / 'codex-to-gcube-handoff-v1/controller'
sys.path.insert(0, str(CONTROLLER))

with mock.patch('subprocess.run', side_effect=AssertionError('REAL_PROCESS_FORBIDDEN')), \
        mock.patch('subprocess.Popen', side_effect=AssertionError('REAL_PROCESS_FORBIDDEN')):
    import common
    import nvidia_backend as backend
    import nvidia_worker as worker
    import nvidia_controller as coordinator_module
    import lease_supervisor as supervisor
    import safe_capture_export as safe_export

IMAGE = 'sha256:' + 'a' * 64
SOURCE = 'b' * 64
SYNTHETIC_SECRET = 'SYNTHETIC_NOT_A_REAL_CREDENTIAL'


def plan_for(seconds=10):
    count = seconds * 30
    lengths = [count // 2, count - count // 2]
    cursor, segments = 0, []
    for length in lengths:
        segments.append({'startFrame': cursor, 'endFrame': cursor + length,
            'scene': {'timing': {'fps': 30, 'total_frames': length},
                      'metadata': {'output': {'width': 1080, 'height': 1920,
                                              'fps': 30, 'audio': False}}}})
        cursor += length
    runtime = {'totalFrames': count, 'segments': segments}
    if seconds == 10:
        runtime['durationSeconds'] = 10
    wire = common.canonical(runtime).decode()
    return {'schema': common.PLAN, 'durationSeconds': seconds, 'totalFrames': count,
        'fps': 30, 'resolution': {'width': 1080, 'height': 1920}, 'aspectRatio': '9:16',
        'audioSettings': {'enabled': False, 'mode': 'SILENT'}, 'simulationType': 'GENERAL',
        'renderProfile': {'profileId': common.PROFILE, 'backend': 'vulkan',
                          'imageDigest': IMAGE, 'sourceClosureSHA256': SOURCE},
        'runtime': runtime, 'runtimeWireJSON': wire,
        'runtimeWireSHA256': common.sha(wire.encode()),
        'sourceQualificationSHA256': 'c' * 64}


def bind_runtime(plan):
    plan['runtimeWireJSON'] = common.canonical(plan['runtime']).decode()
    plan['runtimeWireSHA256'] = common.sha(plan['runtimeWireJSON'].encode())
    return plan


def approval(plan):
    return {'schema': 'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1', 'approved': True,
        'planSHA256': common.sha(common.canonical(plan)), 'imageDigest': IMAGE,
        'validUntil': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        'maxWallSeconds': 900, 'maxRetries': 0, 'maxCostAmount': '10',
        'currency': 'USD', 'gpuHourlyRate': '1'}


def native_proof(index):
    return {'schema': 'WORLD_ENGINE_NATIVE_MAP_STABILITY_V1', 'status': 'PASS',
        'segmentIndex': index, 'backend': 'NVIDIA example / Vulkan',
        'draws': [{'index': i, 'frame': 0, 'glError': 0,
                   'rgbaBytes': 1080 * 1920 * 4, 'nonBlackPixels': 1080 * 1920,
                   'rawRGBA256': 'd' * 64} for i in range(3)]}


class JsonDirectory:
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def json(self, name):
        return json.loads((self.path / name).read_text())


def media_fixture(output, plan):
    count, seconds = plan['totalFrames'], plan['durationSeconds']
    label = 'TEN' if seconds == 10 else 'SIX'
    video = output / 'VIDEO.mp4'
    video.write_bytes(b'SYNTHETIC_MEDIA_VALIDATION_FIXTURE_NOT_AN_MP4')
    receipt = {'schema': f'WORLD_ENGINE_NVIDIA_{label}_SECOND_CAPTURE_V1',
        'status': 'TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED',
        'packageSHA256': plan['runtimeWireSHA256'],
        'sourceQualificationSHA256': plan['sourceQualificationSHA256'],
        'softwareOnly': False, 'nvidiaVerified': True, 'renderedFrames': count,
        'totalFrames': count, 'visualQualityApproved': False,
        'video': {'sha256': common.sha(video.read_bytes())},
        'nativeStability': [native_proof(i) for i in range(len(plan['runtime']['segments']))]}
    frames = {'frames': [{'frame': i, 'diagnostic': {'glError': 0}} for i in range(count)]}
    if seconds == 10:
        receipt['durationSeconds'] = 10
        frames.update(durationSeconds=10, totalFrames=300)
    write_json(output / 'CAPTURE_RECEIPT.json', receipt)
    write_json(output / 'FRAME_EVIDENCE.json', frames)
    return receipt, frames


def probe_fixture(frames=300, duration=10):
    return {'streams': [{'codec_type': 'video', 'codec_name': 'h264',
        'width': 1080, 'height': 1920, 'r_frame_rate': '30/1',
        'nb_read_frames': str(frames)}], 'format': {'duration': str(duration)}}


def write_json(path, value):
    Path(path).write_text(json.dumps(value))
    Path(path).chmod(0o600)


class NewTenSecondControllerTests(unittest.TestCase):
    def setUp(self):
        self.effects = ExitStack()
        self.effects.enter_context(mock.patch('subprocess.Popen',
            side_effect=AssertionError('REAL_PROCESS_FORBIDDEN')))
        self.effects.enter_context(mock.patch('subprocess.run',
            side_effect=AssertionError('REAL_PROCESS_FORBIDDEN')))
        self.effects.enter_context(mock.patch('urllib.request.urlopen',
            side_effect=AssertionError('REAL_NETWORK_FORBIDDEN')))
        self.addCleanup(self.effects.close)
        self.temp = tempfile.TemporaryDirectory(prefix='new-ten-second-contract-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def validate_media(self, plan, *, probe=None, decode=None):
        calls = []
        def fake_run(args, **options):
            calls.append((args, options))
            if args[0] == 'ffprobe':
                return SimpleNamespace(returncode=0, stdout=json.dumps(
                    probe if probe is not None else probe_fixture(
                        plan['totalFrames'], plan['durationSeconds'])).encode(), stderr=b'')
            self.assertEqual(args[0], 'ffmpeg')
            return decode or SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        with mock.patch.object(worker, 'cache', return_value=SimpleNamespace(PrivateTree=JsonDirectory)), \
                mock.patch('subprocess.run', side_effect=fake_run):
            result = worker._validate_capture(self.root, plan)
        return result, calls

    def test_01_explicit_ten_second_plan_and_unchanged_six_second_shape(self):
        ten = plan_for()
        self.assertEqual(common.duration_contract(ten),
            {'durationSeconds': 10, 'totalFrames': 300, 'fps': 30})
        self.assertTrue(common.validate_plan(ten, image_digest=IMAGE, source_sha=SOURCE))
        six = plan_for(6)
        original_wire = six['runtimeWireJSON']
        self.assertNotIn('durationSeconds', six['runtime'])
        self.assertEqual(common.duration_contract(six),
            {'durationSeconds': 6, 'totalFrames': 180, 'fps': 30})
        self.assertTrue(common.validate_plan(six, image_digest=IMAGE, source_sha=SOURCE))
        self.assertEqual(six['runtimeWireJSON'], original_wire)

    def test_02_duration_pairs_types_and_unsupported_scope_are_rejected(self):
        for field, value in (('durationSeconds', 80), ('durationSeconds', 10.0),
                ('durationSeconds', True), ('totalFrames', 180), ('totalFrames', 300.0),
                ('fps', 24), ('fps', 30.0)):
            with self.subTest(field=field, value=value):
                plan = plan_for()
                plan[field] = value
                with self.assertRaises(RuntimeError):
                    common.duration_contract(plan)
        for field in ('durationSeconds', 'totalFrames', 'fps'):
            plan = plan_for()
            del plan[field]
            with self.subTest(missing=field), self.assertRaises(RuntimeError):
                common.duration_contract(plan)

    def test_03_ten_second_runtime_wire_and_full_three_hundred_coverage_are_bound(self):
        changes = (
            lambda p: p['runtime'].pop('durationSeconds'),
            lambda p: p['runtime'].update(durationSeconds=6),
            lambda p: p['runtime'].update(totalFrames=299),
            lambda p: p['runtime']['segments'][1].update(endFrame=299),
            lambda p: p['runtime']['segments'][1].update(startFrame=149),
        )
        for index, change in enumerate(changes):
            with self.subTest(change=index):
                plan = plan_for()
                change(plan)
                bind_runtime(plan)
                with self.assertRaises(RuntimeError):
                    common.validate_plan(plan, image_digest=IMAGE, source_sha=SOURCE)
        plan = plan_for()
        plan['runtimeWireSHA256'] = 'f' * 64
        with self.assertRaisesRegex(RuntimeError, 'HANDOFF_RUNTIME_WIRE_BINDING_CHANGED'):
            common.validate_plan(plan, image_digest=IMAGE, source_sha=SOURCE)

    def test_04_ten_second_capture_receipt_media_and_frame_evidence_validate(self):
        plan = plan_for()
        media_fixture(self.root, plan)
        result, calls = self.validate_media(plan)
        self.assertEqual(result['schema'], 'WORLD_ENGINE_NVIDIA_TEN_SECOND_MEDIA_VERIFY_V1')
        self.assertEqual((result['frames'], result['durationSeconds'], result['fps']), (300, 10, 30))
        self.assertEqual(result['audioStreams'], 0)
        self.assertEqual(result['visualQuality'], 'USER_VIDEO_REVIEW_REQUIRED')
        self.assertEqual([call[0][0] for call in calls], ['ffprobe', 'ffmpeg'])
        self.assertEqual([call[1]['timeout'] for call in calls], [45, 45])

    def test_05_ten_second_receipt_rejects_legacy_shape_and_software_fallback(self):
        plan = plan_for()
        for field, value in (('schema', 'WORLD_ENGINE_NVIDIA_SIX_SECOND_CAPTURE_V1'),
                ('durationSeconds', 6), ('durationSeconds', 10.0),
                ('renderedFrames', 180), ('renderedFrames', 300.0),
                ('totalFrames', 301), ('softwareOnly', True), ('nvidiaVerified', False)):
            with self.subTest(field=field, value=value):
                receipt, _ = media_fixture(self.root, plan)
                receipt[field] = value
                write_json(self.root / 'CAPTURE_RECEIPT.json', receipt)
                with self.assertRaisesRegex(RuntimeError, 'HANDOFF_NVIDIA_CAPTURE_RECEIPT_INVALID'):
                    self.validate_media(plan)
        receipt, _ = media_fixture(self.root, plan)
        receipt['nativeStability'][0]['backend'] = 'NVIDIA SwiftShader Vulkan software'
        write_json(self.root / 'CAPTURE_RECEIPT.json', receipt)
        with self.assertRaisesRegex(RuntimeError, 'HANDOFF_NATIVE_STABILITY_PROOF_INVALID'):
            self.validate_media(plan)

    def test_06_ten_second_ffprobe_and_full_decode_cannot_accept_six_second_media(self):
        plan = plan_for()
        media_fixture(self.root, plan)
        for probe in (probe_fixture(180, 6), probe_fixture(299, 10), probe_fixture(300, 9.9)):
            with self.subTest(probe=probe), self.assertRaisesRegex(RuntimeError,
                    'HANDOFF_VIDEO_300_FRAME_CONTRACT_FAILED'):
                self.validate_media(plan, probe=probe)
        for decoded in (SimpleNamespace(returncode=1, stdout=b'', stderr=b''),
                        SimpleNamespace(returncode=0, stdout=b'', stderr=b'DECODE_ERROR')):
            with self.subTest(decode=decoded.returncode), self.assertRaisesRegex(RuntimeError,
                    'HANDOFF_VIDEO_FULL_DECODE_FAILED'):
                self.validate_media(plan, decode=decoded)

    def test_07_three_hundred_frame_evidence_requires_every_integer_index_and_pair(self):
        plan = plan_for()
        for mutation in (
                lambda f: f['frames'].pop(),
                lambda f: f['frames'][299].update(frame=298),
                lambda f: f['frames'][299].update(frame=299.0),
                lambda f: f['frames'][299]['diagnostic'].update(glError=1280),
                lambda f: f.pop('durationSeconds'),
                lambda f: f.update(totalFrames=301)):
            _, frames = media_fixture(self.root, plan)
            mutation(frames)
            write_json(self.root / 'FRAME_EVIDENCE.json', frames)
            with self.assertRaisesRegex(RuntimeError, 'HANDOFF_ACTUAL_FRAME_EVIDENCE_INVALID'):
                self.validate_media(plan)

    def test_08_six_second_media_schema_remains_the_existing_default(self):
        plan = plan_for(6)
        media_fixture(self.root, plan)
        result, _ = self.validate_media(plan)
        self.assertEqual(result, {'schema': 'WORLD_ENGINE_NVIDIA_SIX_SECOND_MEDIA_VERIFY_V1',
            'videoSHA256': common.sha((self.root / 'VIDEO.mp4').read_bytes()), 'frames': 180,
            'width': 1080, 'height': 1920, 'fps': 30, 'durationSeconds': 6,
            'fullDecode': 'PASS', 'audioStreams': 0, 'visualQuality': 'USER_VIDEO_REVIEW_REQUIRED'})

    def test_09_ten_second_authorization_stays_plan_bound_cost_bounded_and_retry_free(self):
        plan = plan_for()
        authorized = approval(plan)
        self.assertEqual(backend.approval_limit(authorized, plan, IMAGE),
                         {'maxWallSeconds': 600, 'maxRetries': 0})
        for field, value in (('approved', False), ('planSHA256', 'f' * 64),
                ('imageDigest', 'sha256:' + 'f' * 64),
                ('validUntil', (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()),
                ('maxCostAmount', '0.001')):
            with self.subTest(field=field):
                invalid = dict(authorized, **{field: value})
                with self.assertRaises(RuntimeError):
                    backend.approval_limit(invalid, plan, IMAGE)

    def test_10_ten_second_start_cannot_skip_owner_consent_claim_or_private_approval(self):
        plan = plan_for()
        coordinator = SimpleNamespace(videoPlan=plan)
        with self.assertRaises(RuntimeError) as error:
            backend.base.StudioController.start(coordinator, 'a' * 64, 'newtenkey', consent=False)
        self.assertEqual(error.exception.code, 'STUDIO_OWNER_CONSENT_REQUIRED')
        coordinator._raw_status = lambda _: {'state': 'RUNNING', 'totalFrames': 300}
        active = SimpleNamespace(json=lambda *_args, **_kw: {'jobId': 'studio-' + 'a' * 32})
        with self.assertRaises(RuntimeError) as error:
            backend.base.StudioController._check_active(coordinator, active)
        self.assertEqual(error.exception.code, 'STUDIO_JOB_ALREADY_ACTIVE')
        instance = object.__new__(backend.NvidiaPresentationBackend)
        instance._verify = lambda p, _profile: common.validate_plan(p, image_digest=IMAGE, source_sha=SOURCE)
        for request_id, approval_path in (('owner-invalid', self.root / 'authorization.json'),
                ('owner-' + 'a' * 32, self.root / 'public-authorization.json')):
            with self.subTest(request_id=request_id), self.assertRaises(RuntimeError):
                instance.start_studio_job(plan, common.PROFILE, approval_path, {'enabled': False},
                    request_id, control_root=self.root / 'control', export_root=self.root / 'exports')

    def test_11_diagnostic_three_hundred_bounds_require_explicit_pair_and_redact_raw_data(self):
        failure = {'operationId': 'DRAW', 'sourceId': 'PRESENTATION_RUNTIME',
            'errorCode': 'UP2_FRAME_GL_ERROR', 'exceptionType': 'Error',
            'failureKind': 'DOMAIN_ERROR', 'frameIndex': 299,
            'stderr': SYNTHETIC_SECRET, 'environment': {'TOKEN': SYNTHETIC_SECRET}}
        record = {'schema': 'WORLD_ENGINE_CAPTURE_OPERATIONS_V1', 'durationSeconds': 10,
            'totalFrames': 300, 'renderedFrames': 300, 'firstFailure': failure,
            'operationId': 'DRAW', 'sequence': 3, 'observedAtUnixMs': 1793300000000}
        result = safe_export.safe_operations(record)
        self.assertEqual((result['durationSeconds'], result['totalFrames'], result['renderedFrames']),
                         (10, 300, 300))
        self.assertEqual(result['firstFailure']['frameIndex'], 299)
        self.assertNotIn(SYNTHETIC_SECRET, json.dumps(result))
        for pair in ({}, {'durationSeconds': 10}, {'durationSeconds': 10, 'totalFrames': 180},
                {'durationSeconds': 10.0, 'totalFrames': 300},
                {'durationSeconds': 10, 'totalFrames': 300.0}):
            legacy = dict(record)
            legacy.pop('durationSeconds')
            legacy.pop('totalFrames')
            legacy.update(pair)
            checked = safe_export.safe_operations(legacy)
            self.assertIsNone(checked['renderedFrames'])
            self.assertIsNone(checked['firstFailure']['frameIndex'])
            self.assertNotIn('durationSeconds', checked)
        for index in (300, 301, True):
            checked = safe_export.safe_failure(dict(failure, frameIndex=index), total_frames=300)
            self.assertIsNone(checked['frameIndex'])
        self.assertIsNone(safe_export.safe_failure(failure)['frameIndex'])

    def test_12_ten_second_safe_export_keeps_cleanup_gate_and_non_sensitive_summary(self):
        job = self.root / 'job'
        capture = job / 'capture'
        capture.mkdir(parents=True, mode=0o700)
        job.chmod(0o700)
        result_file = job / 'LEASE_SUPERVISOR_RESULT.json'
        write_json(result_file, {'cleanupVerified': False})
        with self.assertRaisesRegex(ValueError, 'DIAGNOSTIC_VERIFIED_CLEANUP_REQUIRED'):
            safe_export.export_failure(job, self.root / 'blocked-export')
        self.assertFalse((self.root / 'blocked-export').exists())
        write_json(result_file, {'cleanupVerified': True, 'reason': 'UP2_FRAME_GL_ERROR'})
        write_json(job / 'FIRST_CAPTURE_FAILURE.json', {'stage': 'GPU_NATIVE_DRAW', 'code': 'UP2_FRAME_GL_ERROR'})
        write_json(capture / 'CAPTURE_RECEIPT.json', {'durationSeconds': 10, 'totalFrames': 300,
            'renderedFrames': 300, 'nvidiaVerified': False, 'stderr': SYNTHETIC_SECRET})
        write_json(capture / 'CAPTURE_OPERATION_CHECKPOINT.json', {
            'schema': 'WORLD_ENGINE_CAPTURE_OPERATIONS_V1', 'durationSeconds': 10,
            'totalFrames': 300, 'renderedFrames': 299, 'operationId': 'DRAW', 'sequence': 3})
        observed = safe_export.export_failure(job, self.root / 'safe-export')
        self.assertEqual(observed['diagnostic']['capture']['renderedFrames'], 300)
        self.assertEqual(observed['diagnostic']['capture']['operations']['totalFrames'], 300)
        body = (self.root / 'safe-export/CAPTURE_DIAGNOSTIC.json').read_text()
        self.assertNotIn(SYNTHETIC_SECRET, body)
        self.assertEqual((self.root / 'safe-export/CAPTURE_DIAGNOSTIC.json').stat().st_mode & 0o777, 0o600)
        for seconds in (0, 5.1, True):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                safe_export.export_failure(job, self.root / 'invalid-deadline', deadline_seconds=seconds)

    def simulate_supervisor(self, rows, *, total_frames=300, seconds=600):
        progress, events = [], []
        parent = {'pid': 4242, 'startTicks': '123', 'uid': 1000}
        cleanup = {'remaining': [], 'errors': [], 'observationError': False}
        class Guard:
            def __init__(self, _pid):
                pass
            def __enter__(self):
                events.append('guard-enter')
                return self
            def __exit__(self, *_):
                return False
            def cleanup(self):
                events.append('cleanup')
                return deepcopy(cleanup)
        class Stdout:
            def fileno(self):
                return 21
            def close(self):
                events.append('stdout-close')
        class Child:
            pid, returncode = 5252, 0
            stdout = Stdout()
            def __init__(self):
                self.polls = 0
            def poll(self):
                self.polls += 1
                return None if self.polls == 1 else 0
            def wait(self, timeout):
                events.append(('wait', timeout))
                return 0
        def atomic(path, value):
            progress.append((Path(path).name, deepcopy(value)))
        def load(_name, path):
            return SimpleNamespace(DescendantGuard=Guard) if Path(path).name == 'process_guard.py' else SimpleNamespace(atomic=atomic)
        chunks = [b''.join(json.dumps(row).encode() + b'\n' for row in rows), b'', b'']
        factory = mock.Mock(side_effect=lambda *_args, **_kw: Child())
        diagnostics = SimpleNamespace(preserve_before_cleanup=lambda *_: events.append('private-diagnostic'))
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(supervisor, 'validate_lease_descriptor', return_value=11))
            stack.enter_context(mock.patch.object(supervisor, 'parent_identity', return_value=parent))
            stack.enter_context(mock.patch.object(supervisor.os, 'getppid', return_value=4242))
            stack.enter_context(mock.patch.object(supervisor.os, 'getuid', return_value=1000))
            stack.enter_context(mock.patch.object(supervisor.os, 'pidfd_open', return_value=31))
            stack.enter_context(mock.patch.object(supervisor.os, 'set_blocking'))
            stack.enter_context(mock.patch.object(supervisor.os, 'close'))
            stack.enter_context(mock.patch.object(supervisor.os, 'read', side_effect=chunks))
            stack.enter_context(mock.patch.object(supervisor.select, 'select', return_value=([], [], [])))
            stack.enter_context(mock.patch.object(supervisor.time, 'sleep'))
            stack.enter_context(mock.patch.object(supervisor, 'load', side_effect=load))
            stack.enter_context(mock.patch.dict(sys.modules, {'capture_diagnostics_safe': diagnostics}))
            stack.enter_context(mock.patch.object(supervisor, '_stop_requested', False))
            result = supervisor.supervise_owned_capture(['MOCK_CAPTURE_ONLY'], lease_fd=11,
                lease_path=self.root / 'existing-original-lease', parent=parent, seconds=seconds,
                environment={}, output=self.root, capture_factory=factory, total_frames=total_frames)
        return result, progress, events, factory

    def test_13_supervisor_accepts_only_ordered_three_hundred_frame_progress(self):
        rows = [{'stage': 'ACTUAL_FRAME_DRAW', 'frame': i, 'renderedFrames': i + 1,
                 'totalFrames': 300} for i in range(300)]
        result, progress, events, factory = self.simulate_supervisor(rows)
        self.assertEqual(result['processedFramesObserved'], 300)
        actual = [row for name, row in progress if name == 'actual-progress.json']
        self.assertEqual(actual[-1], {'processedFrames': 300, 'totalFrames': 300})
        self.assertEqual(len(actual), 300)
        self.assertEqual(factory.call_count, 1)
        final = [row for name, row in progress if name == 'LEASE_SUPERVISOR_RESULT.json'][-1]
        self.assertTrue(final['cleanupVerified'])
        self.assertTrue(final['inheritedOriginalLeaseHeldThroughCleanup'])
        self.assertFalse(final['newLockCreated'])
        self.assertFalse(final['gpuBasicProbeRepeated'])
        self.assertIn('cleanup', events)

    def test_14_supervisor_rejects_extra_misnumbered_or_wrong_duration_progress(self):
        valid = [{'stage': 'ACTUAL_FRAME_DRAW', 'frame': i, 'renderedFrames': i + 1,
                  'totalFrames': 300} for i in range(300)]
        variants = [valid + [{'stage': 'ACTUAL_FRAME_DRAW', 'frame': 300,
                             'renderedFrames': 301, 'totalFrames': 300}],
                    valid[:-1] + [dict(valid[-1], frame=298)],
                    [dict(valid[0], totalFrames=180)],
                    [dict(valid[0], totalFrames=300.0)]]
        for rows in variants:
            with self.subTest(last=rows[-1]), self.assertRaisesRegex(RuntimeError,
                    'HANDOFF_ACTUAL_FRAME_PROGRESS_INVALID'):
                self.simulate_supervisor(rows)

    def test_15_supervisor_ten_second_path_does_not_raise_wall_time_or_frame_ceiling(self):
        for frames in (301, 80 * 30, 300.0, True):
            with self.subTest(frames=frames), self.assertRaisesRegex(RuntimeError,
                    'HANDOFF_CAPTURE_FRAME_CONTRACT_REQUIRED'):
                self.simulate_supervisor([], total_frames=frames)
        for seconds in (0, 601):
            with self.subTest(seconds=seconds), self.assertRaisesRegex(RuntimeError,
                    'HANDOFF_CAPTURE_PARENT_IDENTITY_REQUIRED'):
                self.simulate_supervisor([], seconds=seconds)

    def test_16_owner_preflight_reports_explicit_ten_second_scope_only_for_new_path(self):
        original = {'valid': True, 'ready': False, 'requiresGpu': True,
                    'checks': [], 'gpuRenderingVerified': False}
        instance = object.__new__(coordinator_module.NvidiaPresentationController)
        with mock.patch.object(coordinator_module.base.StudioController,
                               '_preflight_record', side_effect=lambda *_: deepcopy(original)):
            ten = instance._preflight_record(None, {'submission': {'videoPlan': plan_for()}})
            six = instance._preflight_record(None, {'submission': {'videoPlan': plan_for(6)}})
        self.assertEqual((ten['durationSeconds'], ten['totalFrames']), (10, 300))
        self.assertFalse(ten['gpuRenderingVerified'])
        self.assertEqual(six, original)

    def test_17_export_qa_uses_validated_ten_second_plan_and_retains_legacy_default(self):
        class Tree(JsonDirectory):
            def __init__(self, path, create=False):
                super().__init__(path)
                if create:
                    self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
            def child(self, name, create=False):
                return Tree(self.path / name, create)
            def write_json(self, name, value):
                write_json(self.path / name, value)
        output = self.root / 'output'
        output.mkdir()
        video = b'SYNTHETIC_EXPORTED_BYTES_NOT_A_VIDEO'
        (output / 'VIDEO.mp4').write_bytes(video)
        observations = []
        def exported(public, *_):
            observations.append(json.loads((public / 'QUALITY_SUMMARY.json').read_bytes()))
            self.assertEqual((public / 'WORLD_ENGINE_STUDIO_VIDEO.mp4').read_bytes(), video)
            return {'exported': True}
        delivery = SimpleNamespace(export_media=exported)
        for index, plan in enumerate((plan_for(), None)):
            job = self.root / ('job-' + str(index))
            job.mkdir()
            with mock.patch.object(worker, 'cache', return_value=SimpleNamespace(PrivateTree=Tree)), \
                    mock.patch.object(worker, 'load', return_value=delivery):
                result = worker._export(job, output, self.root / 'exports', self.root / 'control', plan)
            self.assertTrue(result['exported'])
        self.assertEqual([(x['frames'], x['durationSeconds']) for x in observations], [(300, 10), (180, 6)])
        for summary in observations:
            self.assertFalse(summary['sfxEnabled'])
            self.assertFalse(summary['finalPromotion'])
            self.assertEqual(summary['visualQuality'], 'USER_VIDEO_REVIEW_REQUIRED')

    def test_18_detached_initial_state_derives_three_hundred_from_bound_plan(self):
        class Tree(JsonDirectory):
            def __init__(self, path, create=False):
                super().__init__(path)
                if create:
                    self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
            def child(self, name, create=False):
                return Tree(self.path / name, create)
            def write_json(self, name, value, replace=False):
                if not replace:
                    self.assert_not_existing(name)
                write_json(self.path / name, value)
            def assert_not_existing(self, name):
                if (self.path / name).exists():
                    raise FileExistsError(name)
        control = self.root / 'control'
        exports = self.root / 'exports'
        request_id = 'owner-' + 'a' * 32
        approval_path = control / 'approvals' / request_id / 'authorization.json'
        approval_path.parent.mkdir(parents=True)
        plan = plan_for()
        write_json(approval_path, approval(plan))
        instance = object.__new__(backend.NvidiaPresentationBackend)
        instance._verify = lambda p, _profile: common.validate_plan(p, image_digest=IMAGE, source_sha=SOURCE)
        instance.preflight = lambda *_args, **_kwargs: {'renderAllowed': True}
        instance.manifest_file, instance.source_sha, instance.image_digest = self.root / 'manifest.json', SOURCE, IMAGE
        old_read = Path.read_text
        def read_text(path, *args, **kwargs):
            if str(path) == '/proc/999999/stat':
                fields = ['S'] + ['0'] * 18 + ['1234']
                return '999999 (synthetic-worker) ' + ' '.join(fields)
            return old_read(path, *args, **kwargs)
        process = mock.Mock(return_value=SimpleNamespace(pid=999999))
        with mock.patch.object(backend, 'cache', return_value=SimpleNamespace(PrivateTree=Tree)), \
                mock.patch.object(backend.subprocess, 'Popen', process), \
                mock.patch.object(Path, 'read_text', read_text):
            state = instance.start_studio_job(plan, common.PROFILE, approval_path, {'enabled': False},
                request_id, control_root=control, export_root=exports)
        self.assertEqual((state['processedFrames'], state['totalFrames'], state['durationSeconds']), (0, 300, 10))
        self.assertEqual(state['state'], 'QUEUED')
        self.assertFalse(state['gpuRenderingVerified'])
        self.assertEqual(process.call_count, 1)
        self.assertLessEqual((datetime.fromisoformat(state['executionDeadline']) - datetime.now(timezone.utc)).total_seconds(), 600)
        self.assertEqual(state['processStart'], '1234')


if __name__ == '__main__':
    unittest.main(verbosity=2)
