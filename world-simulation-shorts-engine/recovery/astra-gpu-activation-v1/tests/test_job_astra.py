"""New ASTRA profile CPU checks; no GPU admission, render, deploy or account API."""
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import zlib

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tested_astra_job_profile', HERE / 'job_astra.py')
job = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(job)


def wait(predicate, seconds=6):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        value = predicate()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError('CPU_AST_A_LIFECYCLE_TIMEOUT')


def synthetic_result():
    files = [{'file': 'fixture.mp4', 'sha256': '0' * 64, 'bytes': 1}]
    files += [{'file': 'frame-' + str(n) + '.png', 'sha256': '1' * 64, 'bytes': 1} for n in range(5)]
    files += [{'file': 'SHA256SUMS', 'sha256': '2' * 64, 'bytes': 1}]
    return {'schema': 'WORLD_ENGINE_EXPORT_LOCATION_V1', 'testOnly': True,
            'exportDirectory': 'world-engine-export-' + 'a' * 24,
            'mountedViewReadbackVerified': True, 'remotePersistenceVerified': False,
            'externalDownloadVerified': False, 'captures': [{'directory': 'capture-' + 'b' * 12 + '-' + 'c' * 24,
            'publicDirectory': 'public-review', 'completionReceipt': 'EXPORT_COMPLETE.json', 'files': files}]}


def clear():
    return {'status': 'CLEAR', 'testOnly': True}


def verify_synthetic(result, export_root):
    if result != synthetic_result():
        raise ValueError('SYNTHETIC_RESULT_REJECTED')
    return result


@unittest.skipUnless(os.geteuid() == 1000 and os.getegid() == 1000, 'requires engine UID/GID 1000')
class ProfileLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='astra-profile-cpu-', dir='/workspace')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name)
        self.control, self.export = self.root / 'control', self.root / 'export'
        self.control.mkdir(mode=0o700)
        self.export.mkdir(mode=0o700)
        self.store = job.Store(control_root=self.control, export_root=self.export)
        self.counter = self.root / 'calls'
        self.children = []

    def tearDown(self):
        try:
            state = self.store.read()
            for field in ('supervisorIdentity', 'rendererIdentity'):
                identity = state.get(field) if state else None
                if identity and job.manager.is_alive(identity):
                    os.kill(identity['pid'], signal.SIGKILL)
                if identity:
                    self.children.append(identity['pid'])
        except (OSError, job.job_store.JobError):
            pass
        for pid in self.children:
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass

    def native(self, delay=.04, fail=False):
        def run(state, update):
            with self.counter.open('a') as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                stream.write('called\n')
                stream.flush()
                os.fsync(stream.fileno())
            time.sleep(delay)
            failure = job.manager.records.make_record('WEBGL2', 'GPU_WEBGL_UNVERIFIED', 7, test_only=True) if fail else None
            return {'exitCode': 7 if fail else 0, 'result': None if fail else synthetic_result(), 'firstFailure': failure}
        return run

    def start(self, native=None):
        state = job.manager.start(self.store, native_override=native or self.native(),
                                  verify_override=verify_synthetic, inspect_override=clear)
        if state.get('supervisorIdentity'):
            self.children.append(state['supervisorIdentity']['pid'])
        return state

    def terminal(self):
        return wait(lambda: (lambda value: value if value and value['state'] in {'COMPLETED', 'FAILED'} else None)(job.manager.status(self.store)))

    def count(self):
        return len(self.counter.read_text().splitlines()) if self.counter.exists() else 0

    def test_new_profile_old_shared_claim_and_results_preserved(self):
        old = self.export / job.legacy_store.SHARED_NAME
        old.mkdir()
        claim = old / 'CLAIM.json'
        claim.write_text('UNTRUSTED_OLD_CLAIM_PRESERVED\n')
        original = hashlib.sha256(claim.read_bytes()).hexdigest()
        self.start()
        final = self.terminal()
        self.assertEqual(final['state'], 'COMPLETED')
        self.assertRegex(final['jobId'], '^astra-[0-9a-f]{24}$')
        self.assertEqual(final['schema'], 'WORLD_ENGINE_ASTRA_DETACHED_JOB_V1')
        self.assertTrue(final['testOnly'])
        self.assertEqual(hashlib.sha256(claim.read_bytes()).hexdigest(), original)
        self.assertTrue((self.export / job.SHARED_NAME / 'CLAIM.json').is_file())
        self.assertNotEqual(job.SHARED_NAME, job.legacy_store.SHARED_NAME)
        self.assertEqual(job.legacy_store.SCHEMA, 'WORLD_ENGINE_DETACHED_JOB_V1')

    def test_concurrent_repeat_starts_invoke_only_one_cpu_worker(self):
        processes = []
        for unused in range(3):
            pid = os.fork()
            if pid == 0:
                try:
                    self.start(self.native(.3))
                except job.job_store.JobError:
                    pass
                except BaseException:
                    os._exit(91)
                os._exit(0)
            processes.append(pid)
        for pid in processes:
            self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]), 0)
        final = self.terminal()
        self.assertEqual(final['state'], 'COMPLETED')
        self.assertEqual(self.start()['jobId'], final['jobId'])
        self.assertEqual(job.start(self.store)['jobId'], final['jobId'])
        self.assertEqual(self.count(), 1)

    def test_actual_pty_disconnect_does_not_stop_new_astra_profile(self):
        pid, terminal = pty.fork()
        if pid == 0:
            try:
                state = self.start(self.native(.65))
                os.write(1, ('ASTRA_ACK ' + state['jobId'] + '\n').encode())
                signal.pause()
            except BaseException:
                os._exit(92)
            os._exit(0)
        output = b''
        try:
            until = time.monotonic() + 5
            while b'ASTRA_ACK ' not in output and time.monotonic() < until:
                available, unused, unused2 = select.select([terminal], [], [], .1)
                if available:
                    output += os.read(terminal, 8192)
            self.assertIn(b'ASTRA_ACK astra-', output)
            os.close(terminal)
            terminal = None
            try:
                os.kill(pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]), -signal.SIGHUP)
            final = self.terminal()
            self.assertEqual(final['state'], 'COMPLETED', final)
            self.assertEqual(self.count(), 1)
        finally:
            if terminal is not None:
                os.close(terminal)

    def test_native_failure_retained_and_no_retry(self):
        self.start(self.native(fail=True))
        failed = self.terminal()
        self.assertEqual(failed['exitCode'], 7)
        self.assertEqual(failed['firstFailure']['stage'], 'WEBGL2')
        self.assertEqual(failed['state'], 'FAILED')
        self.assertEqual(self.start()['jobId'], failed['jobId'])
        self.assertEqual(self.count(), 1)

    def test_lost_worker_does_not_autorestart_or_erase_new_claim(self):
        started = self.start(self.native(8))
        wait(lambda: self.count() == 1)
        os.kill(started['supervisorIdentity']['pid'], signal.SIGKILL)
        wait(lambda: not job.manager.is_alive(started['supervisorIdentity']))
        self.assertEqual(self.terminal()['reason'], 'WORKER_LOST')
        self.start()
        self.assertEqual(self.count(), 1)
        for filename in ('JOB.json', 'CLAIM_RECEIPT.json'):
            (self.control / filename).unlink()
        with self.assertRaises(job.job_store.JobError):
            self.start()
        self.assertEqual(self.count(), 1)

    def test_export_verification_failure_is_not_complete(self):
        def reject(result, root):
            raise ValueError('SYNTHETIC_BAD_SHA_NOT_TO_BE_EXPOSED')
        job.manager.start(self.store, native_override=self.native(), verify_override=reject, inspect_override=clear)
        final = self.terminal()
        self.assertEqual(final['state'], 'FAILED')
        self.assertEqual(final['reason'], 'RESULT_VERIFICATION_FAILED')
        self.assertNotIn('BAD_SHA', json.dumps(final))

    def test_production_authorization_bound_to_astra_id_and_published(self):
        value = job._initial(True)
        value['testOnly'] = False
        authorization = {'schema': 'WORLD_ENGINE_ASTRA_PROFILE_AUTHORIZATION_V1', 'profile': job.PROFILE,
            'jobId': value['jobId'], 'createdAt': value['createdAt'], 'baselineHistoryPresent': True,
            'baselineHistoryAcknowledged': True, 'evidenceCounts': {'captureDirectories': 1},
            'gpuExecuted': False, 'renderAllowed': False}
        (self.control / 'ASTRA_PROFILE_AUTHORIZATION.json').write_text(json.dumps(authorization))
        (self.control / 'ASTRA_PROFILE_AUTHORIZATION.json').chmod(0o600)
        descriptor = self.store.lock()
        try:
            result = self.store.create(value)
            actual = json.loads((self.export / job.SHARED_NAME / 'PROFILE_AUTHORIZATION.json').read_text())
            self.assertEqual(actual, authorization)
            self.assertEqual(result['jobId'], authorization['jobId'])
        finally:
            job.manager._close_lock(self.store, descriptor)

    def test_dispatch_authorization_is_bound_immutable_and_not_gpu_evidence(self):
        gate = {'status': 'CLEAR', 'baselineHistoryPresent': True,
                'baselineHistoryAcknowledged': True, 'evidenceCounts': {'sharedCaptureDirectories': 1},
                'gpuExecuted': False, 'renderAllowed': False, 'testOnly': True}
        descriptor = self.store.lock()
        try:
            with mock.patch.object(job, 'inspect_profile', return_value=gate):
                result = job._dispatch_inspection(control_root=self.control)
                self.assertEqual(result, gate)
                authorized = json.loads((self.control / 'ASTRA_PROFILE_AUTHORIZATION.json').read_text())
                candidate = job._initial(False)
                self.assertEqual(authorized['jobId'], candidate['jobId'])
                self.assertTrue(job._valid_authorization(authorized))
                self.assertFalse(authorized['gpuExecuted'])
                self.assertFalse((self.export / job.SHARED_NAME).exists())
                self.assertFalse((self.control / 'JOB.json').exists())
                with self.assertRaises(FileExistsError):
                    job._dispatch_inspection(control_root=self.control)
        finally:
            job._pending_job_id = None
            job.manager._close_lock(self.store, descriptor)

    def test_production_cannot_use_missing_or_other_job_authorization(self):
        value = job._initial(True)
        value['testOnly'] = False
        descriptor = self.store.lock()
        try:
            with self.assertRaises((OSError, job.job_store.JobError)):
                self.store.create(value)
            self.assertFalse((self.export / job.SHARED_NAME).exists())
        finally:
            job.manager._close_lock(self.store, descriptor)


class HistoryAndIdentityTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='astra-inspection-cpu-', dir='/workspace')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name)
        self.private, self.export, self.proc = [self.root / name for name in ('private', 'export', 'proc')]
        for path in (self.private, self.export, self.proc):
            path.mkdir(mode=0o700)
        random = self.proc / 'sys/kernel/random'
        random.mkdir(parents=True)
        (random / 'boot_id').write_text('00000000-0000-0000-0000-000000000001\n')
        self.args = dict(control_root=self.private / 'job-astra-v1', private_base=self.private,
                         export_root=self.export, _proc_root=self.proc)

    def test_old_claim_history_requires_explicit_new_profile_acknowledgement(self):
        old = self.export / job.legacy_store.SHARED_NAME
        old.mkdir()
        (old / 'CLAIM.json').write_text('NOT_A_COMPLETION_OR_PERMISSION\n')
        default = job.inspect_profile(**self.args)
        self.assertEqual(default['status'], 'EXISTING_RECORDS')
        self.assertFalse(default['baselineHistoryAcknowledged'])
        admitted = job.inspect_profile(**self.args, acknowledge_baseline_history=True)
        self.assertEqual(admitted['status'], 'CLEAR')
        self.assertTrue(admitted['baselineHistoryAcknowledged'])
        self.assertFalse(admitted['gpuExecuted'])
        self.assertFalse(admitted['renderAllowed'])
        self.assertEqual((old / 'CLAIM.json').read_text(), 'NOT_A_COMPLETION_OR_PERMISSION\n')

    def test_history_ack_does_not_override_actual_common_gpu_guard(self):
        with (self.private / 'CAPTURE.guard').open('w') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            blocked = job.inspect_profile(**self.args, acknowledge_baseline_history=True)
            self.assertEqual(blocked['status'], 'RUNNING')
            self.assertEqual(blocked['evidenceCounts']['heldCaptureGuards'], 1)

    def test_history_ack_cannot_override_live_legacy_supervisor_identity(self):
        active = job.manager.process_identity(os.getpid())
        with mock.patch.object(job, '_old_state', return_value={'supervisorIdentity': active, 'rendererIdentity': None}):
            blocked = job.inspect_profile(**self.args, acknowledge_baseline_history=True)
        self.assertEqual(blocked['status'], 'RUNNING')
        self.assertEqual(blocked['reason'], 'LEGACY_JOB_ACTIVE')

    def test_malformed_old_private_job_still_fails_closed_with_ack(self):
        control = self.private / 'job-control-v1'
        control.mkdir(mode=0o700)
        record = control / 'JOB.json'
        record.write_text('{"state":"invented"}')
        record.chmod(0o600)
        blocked = job.inspect_profile(**self.args, acknowledge_baseline_history=True)
        self.assertEqual(blocked['status'], 'BLOCKED')
        self.assertEqual(blocked['reason'], 'LEGACY_CAPTURE_REVIEW_UNAVAILABLE')

    def test_unsafe_path_stays_blocked_even_with_history_ack(self):
        (self.export / job.legacy_store.SHARED_NAME).symlink_to(self.private, target_is_directory=True)
        self.assertEqual(job.inspect_profile(**self.args, acknowledge_baseline_history=True)['status'], 'BLOCKED')

    def test_astra_and_original_native_process_roles_are_recognized(self):
        self.assertEqual(job.inspector._role(['/usr/bin/python3', str(job.LAUNCH), '--render-65422']), 'NATIVE_LAUNCHER')
        self.assertEqual(job.inspector._role(['/usr/bin/python3', str(job.LAUNCH), '--render-astra-65422']), 'ASTRA_NATIVE_LAUNCHER')
        self.assertEqual(job.inspector._role(['node', job._CAPTURE]), 'ASTRA_NATIVE_CAPTURE')
        self.assertEqual(job.inspector._role(['/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py', '--render-65422']), 'NATIVE_LAUNCHER')
        self.assertIsNone(job.inspector._role(['/usr/bin/python3', '/tmp/arbitrary.py', '--render-65422']))

    def test_old_profile_globals_and_source_pins_remain_original(self):
        self.assertEqual(str(job.legacy_manager.LAUNCH), '/opt/world-engine-storage-fix/launch.py')
        self.assertEqual(job.legacy_store.SHARED_NAME, 'world-engine-65422-job-v1')
        self.assertRegex(job.legacy_manager._initial(True)['jobId'], '^65422-')
        with tempfile.TemporaryDirectory(dir='/workspace') as area:
            root = Path(area)
            (root / 'job_manager.py').write_text('raise SystemExit(99)\n')
            with mock.patch.object(job, '_BASE', root), self.assertRaisesRegex(RuntimeError, 'SOURCE_CHANGED'):
                job._load('_forbidden_changed_supervisor', 'job_manager.py')

    def test_cli_refuses_unconfirmed_or_command_selected_start(self):
        self.assertEqual(job.main(['start']), 2)
        self.assertEqual(job.main(['start', '--acknowledge-baseline-history']), 2)
        self.assertEqual(job.main(['start', '--confirm-new-job', '--command', '/bin/true']), 2)
        self.assertEqual(job.main(['reset']), 2)
        self.assertFalse(job._valid_authorization({'jobId': 'anything'}))


class AstraReceiptBindingTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='astra-receipt-cpu-', dir='/workspace')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name)
        self.result = synthetic_result()
        self.unit = self.root / self.result['exportDirectory'] / self.result['captures'][0]['directory']
        self.unit.mkdir(parents=True)
        self.base = {'captureId': 'b' * 64}
        self.receipt = {'schema': 'WORLD_ENGINE_ASTRA_CAPTURE_RECEIPT_V1', 'status': 'COMPLETE',
            'profile': job.PROFILE, 'captureId': 'b' * 64, 'materialPlanSha256': 'd' * 64,
            'astraApplied': True, 'testOnly': True, 'profileId': 'synthetic-cpu-profile',
            'activationSha256': 'e' * 64, 'bundleManifestSha256': 'a' * 64,
            'extensionManifestSha256': 'c' * 64, 'gpuRenderingVerified': False,
            'visualQualityVerified': False, 'mountedViewReadbackVerified': True,
            'remotePersistenceVerified': False, 'externalDownloadVerified': False}
        (self.unit / 'EXPORT_COMPLETE.json').write_text(json.dumps(self.base))
        self.write()

    def write(self):
        (self.unit / 'ASTRA_COMPLETE.json').write_text(json.dumps(self.receipt))

    def test_astra_native_receipt_binds_profile_plan_and_actual_capture(self):
        with mock.patch.object(job, '_original_verify', side_effect=lambda result, root: result) as original:
            self.assertEqual(job.verify_astra_export(self.result, self.root), self.result)
            original.assert_called_once_with(self.result, self.root)

    def test_old_capture_or_wrong_profile_cannot_satisfy_astra_completion(self):
        for field, value in (('profile', 'OLD_65422'), ('captureId', 'f' * 64),
                             ('materialPlanSha256', 'not-a-sha'), ('astraApplied', False),
                             ('testOnly', False), ('gpuRenderingVerified', True),
                             ('visualQualityVerified', True), ('remotePersistenceVerified', True),
                             ('profileId', '../wrong'), ('extensionManifestSha256', 'bad')):
            with self.subTest(field=field):
                initial = dict(self.receipt)
                self.receipt[field] = value
                self.write()
                with mock.patch.object(job, '_original_verify', side_effect=lambda result, root: result):
                    with self.assertRaises(job.manager.ManagerError):
                        job.verify_astra_export(self.result, self.root)
                self.receipt = initial

    def test_missing_native_astra_receipt_cannot_finish(self):
        (self.unit / 'ASTRA_COMPLETE.json').unlink()
        with mock.patch.object(job, '_original_verify', side_effect=lambda result, root: result):
            with self.assertRaises(OSError):
                job.verify_astra_export(self.result, self.root)


class ActualCpuExportTests(unittest.TestCase):
    def test_actual_seven_file_ffprobe_sha_and_astra_receipt_handoff(self):
        """A solid-color CPU fixture, not a GPU-rendered WORLD ENGINE frame."""
        verifier = job._BASE / 'verify_artifacts.py'
        if not verifier.is_file():
            verifier = job._BASE.parent / 'gcube-65422-render-v1/verify_artifacts.py'
        spec = importlib.util.spec_from_file_location('astra_existing_media_names', verifier)
        names = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(names)
        with tempfile.TemporaryDirectory(prefix='astra-actual-cpu-export-', dir='/workspace') as area:
            root = Path(area)
            encoded = root / 'SYNTHETIC_CPU_ONLY.mp4'
            completed = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi', '-i',
                'color=c=0x14324a:s=1080x1920:r=30', '-frames:v', '150', '-an', '-c:v', 'libx264',
                '-preset', 'ultrafast', '-crf', '35', '-threads', '2', '-pix_fmt', 'yuv420p', str(encoded)],
                capture_output=True, timeout=120, check=False)
            self.assertEqual(completed.returncode, 0, 'SYNTHETIC_CPU_VIDEO_ENCODING_FAILED')
            def chunk(kind, body):
                return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
            def png(number):
                raw = (b'\0' + bytes((10 + number, 30, 50)) * 1080) * 1920
                return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1080, 1920, 8, 2, 0, 0, 0))
                        + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
            bodies = {names.MOVIE: encoded.read_bytes(), **{name: png(index) for index, name in enumerate(names.PNGS)}}
            bodies['SHA256SUMS'] = ''.join(hashlib.sha256(body).hexdigest() + '  ' + name + '\n'
                                                  for name, body in sorted(bodies.items())).encode()
            result = synthetic_result()
            capture = result['captures'][0]
            capture['files'] = [{'file': name, 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
                                for name, body in sorted(bodies.items())]
            unit = root / result['exportDirectory'] / capture['directory']
            public = unit / 'public-review'
            public.mkdir(parents=True)
            for name, body in bodies.items():
                (public / name).write_bytes(body)
            (unit / 'EXPORT_COMPLETE.json').write_text(json.dumps({
                'schema': 'WORLD_ENGINE_PUBLIC_EXPORT_RECEIPT_V1', 'status': 'COMPLETE',
                'sourceSha256SumsVerified': True, 'remotePersistenceVerified': False,
                'externalDownloadVerified': False, 'privateDataAllowed': False,
                'captureId': 'b' * 64, 'files': capture['files']}))
            astra = {'schema': 'WORLD_ENGINE_ASTRA_CAPTURE_RECEIPT_V1', 'status': 'COMPLETE',
                'profile': job.PROFILE, 'profileId': 'synthetic-cpu', 'captureId': 'b' * 64,
                'materialPlanSha256': 'd' * 64, 'activationSha256': 'e' * 64,
                'bundleManifestSha256': 'a' * 64, 'extensionManifestSha256': 'c' * 64,
                'astraApplied': True, 'testOnly': True, 'gpuRenderingVerified': False,
                'visualQualityVerified': False, 'mountedViewReadbackVerified': True,
                'remotePersistenceVerified': False, 'externalDownloadVerified': False}
            (unit / 'ASTRA_COMPLETE.json').write_text(json.dumps(astra))
            self.assertEqual(job.verify_astra_export(result, root), result)
            self.assertEqual(len(list(public.iterdir())), 7)
            self.assertFalse((public / 'ASTRA_COMPLETE.json').exists())
            # Existing independently anchored manifest must reject changed bytes.
            with (public / names.PNGS[0]).open('ab') as stream:
                stream.write(b'SYNTHETIC_CORRUPTION')
            with self.assertRaises(RuntimeError):
                job.verify_astra_export(result, root)


if __name__ == '__main__':
    unittest.main()
