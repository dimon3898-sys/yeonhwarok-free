"""New pending-evidence regression cases only. No G0/G1/G2 or GPU execution.

Runs the actual supervisor/worker functions extracted by AST to isolate their
GPU imports. Process, pidfd, flock, pipes and diagnostic helper I/O are real;
DescendantGuard cleanup results are synthetic failure injections, not GPU proof.
"""
import ast
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
CTRL = ROOT / 'codex-to-gcube-handoff-v1/controller'
sys.path.insert(0, str(CTRL))
import safe_capture_export as safe
import capture_diagnostics_safe as wrapper
JOB = 'studio-' + 'a' * 32
SECRET = 'TEST_SECRET_DO_NOT_EXPORT'

def write(path, value):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)

def atomic(path, value):
    tmp = path.with_name('.' + path.name + '.test-tmp')
    write(tmp, value)
    os.replace(tmp, path)

class PrivateTree:
    def __init__(self, path): self.path = Path(path)
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def json(self, name): return json.loads((self.path / name).read_text())

def functions(file, names, namespace):
    tree = ast.parse((CTRL / file).read_text())
    nodes = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            nodes.append(node)
        if isinstance(node, ast.ClassDef):
            nodes.extend(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in names)
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(CTRL / file), 'exec'), namespace)
    return namespace

def operation():
    return {'schema': 'WORLD_ENGINE_CAPTURE_OPERATIONS_V1', 'runId': JOB,
        'sequence': 6, 'renderedFrames': 2, 'operationId': 'DRAW',
        'firstFailure': {'operationId': 'DRAW', 'sourceId': 'CAPTURE_ADAPTER',
            'errorCode': 'UP2_FRAME_GL_ERROR', 'frameIndex': 2,
            'exceptionType': 'Error', 'failureKind': 'DOMAIN_ERROR', 'message': SECRET},
        'cleanupFailure': {'operationId': 'CLEANUP', 'sourceId': 'CAPTURE_ADAPTER',
            'errorCode': SECRET}, 'stderr': SECRET, 'token': SECRET}

def fixture(mode, job):
    # This process owns only a synthetic CPU lease, never the production lock.
    job = Path(job)
    fd = os.open(job / 'CPU_TEST.guard', os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    class Guard:
        def __init__(self, pid): self.pid = pid
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def cleanup(self):
            if mode == 'cleanup_hang':
                write(job / 'cleanup-entered.json', {'synthetic': True})
                while True: time.sleep(.1)
            if mode == 'cleanup_error': raise OSError('injected synthetic cleanup failure')
            if mode == 'timeout':
                try: os.kill(self.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            return {'remaining': [123] if mode == 'descendant' else [],
                'errors': [], 'observationError': None}
    def load(name, path):
        return types.SimpleNamespace(DescendantGuard=Guard, atomic=atomic)
    ns = dict(os=os, Path=Path, stat=stat, subprocess=subprocess, select=select,
        signal=signal, time=time, re=re, json=json, load=load, RECOVERY=ROOT,
        _stop_requested=False)
    ns = functions('lease_supervisor.py',
        ['validate_lease_descriptor', 'parent_identity', 'supervise_owned_capture'], ns)
    if mode == 'worker_hold':
        ns.update(contextmanager=contextmanager, cache=lambda: types.SimpleNamespace(PrivateTree=PrivateTree))
        functions('nvidia_worker.py', ['keep_original_lease_until_cleanup'], ns)
        @contextmanager
        def lease(): yield
        child = types.SimpleNamespace(poll=lambda: 1)
        def save(**row): atomic(job / 'held-state.json', row)
        with ns['keep_original_lease_until_cleanup'](types.SimpleNamespace(common_gpu_lease=lease), job, [child], save):
            raise RuntimeError('synthetic worker failure')
    else:
        rows = [{'status': 'FAILED', 'code': 'UP2_FRAME_GL_ERROR', 'stage': 'GPU_NATIVE_DRAW'},
                {'status': 'FAILED', 'code': 'UP2_ENCODER_CLOSED', 'stage': 'ENCODING_OR_DECODE'}]
        script = ('pass' if mode == 'normal' else 'import time; time.sleep(5)' if mode == 'timeout'
            else 'import json; rows=' + repr(rows) + '; [print(json.dumps(r),flush=True) for r in rows]; raise SystemExit(1)')
        try:
            result = ns['supervise_owned_capture']([sys.executable, '-I', '-B', '-c', script],
                lease_fd=fd, lease_path=job / 'CPU_TEST.guard',
                parent=ns['parent_identity'](os.getppid()), seconds=.15 if mode == 'timeout' else 3,
                environment={}, output=job)
            write(job / 'fixture-return.json', result)
        except Exception:
            write(job / 'fixture-return.json', {'raised': True})
    os.close(fd)

class PendingEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='pending-evidence-')
        self.base = Path(self.tmp.name)
        self.job = self.base / 'handoff-gpu-jobs' / JOB
        self.job.mkdir(parents=True, mode=0o700)
        (self.job / 'capture').mkdir(mode=0o700)
        self.exports = self.base / 'exports'; self.exports.mkdir()
        self.children = []
    def tearDown(self):
        for child in self.children:
            if child.poll() is None: child.kill()
            child.wait(timeout=3)
        self.tmp.cleanup()
    def checkpoint(self): write(self.job / 'capture/CAPTURE_OPERATION_CHECKPOINT.json', operation())
    def pending(self): return self.job / 'CAPTURE_DIAGNOSTIC_PENDING.json'
    def start(self, mode):
        child = subprocess.Popen([sys.executable, '-I', '-B', str(Path(__file__)), '--fixture', mode, str(self.job)],
            env={}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.children.append(child); return child
    def await_file(self, path):
        end = time.monotonic() + 4
        while time.monotonic() < end:
            if path.exists(): return
            time.sleep(.02)
        self.fail('synthetic fixture did not preserve evidence')
    def assert_locked(self):
        with (self.job / 'CPU_TEST.guard').open('rb') as stream:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    def test_01_normal_capture_and_verified_cleanup(self):
        child = self.start('normal'); self.assertEqual(child.wait(timeout=5), 0)
        result = json.loads((self.job / 'fixture-return.json').read_text())
        self.assertEqual(result['status'], 'CAPTURE_PROCESS_AND_CLEANUP_COMPLETE')
        self.assertEqual(result['exitCode'], 0)
        self.assertFalse(self.pending().exists())
        self.assertTrue(json.loads((self.job / 'LEASE_SUPERVISOR_RESULT.json').read_text())['cleanupVerified'])
    def test_02_first_error_survives_later_failure_and_export(self):
        self.checkpoint()
        child = self.start('failure'); self.assertEqual(child.wait(timeout=5), 0)
        first = self.pending().read_bytes()
        payload = json.loads(first)
        self.assertEqual(payload['firstFailure']['errorCode'], 'UP2_FRAME_GL_ERROR')
        self.assertEqual(payload['supervisorFirstFailure']['code'], 'UP2_FRAME_GL_ERROR')
        write(self.job / 'FIRST_CAPTURE_FAILURE.json', {'code': 'UP2_ENCODER_CLOSED', 'stage': 'ENCODING_OR_DECODE'})
        self.assertEqual(wrapper.preserve_before_cleanup(self.job)['status'], 'LOCAL_ATTEMPT_COMPLETE')
        self.assertEqual(first, self.pending().read_bytes())
        result = safe.export_failure(self.job, self.exports / 'post-cleanup')
        self.assertTrue(result['diagnostic']['supervisor']['cleanupVerified'])
        self.assertNotIn(SECRET.encode(), first)
        self.assertLess(len(first), safe.LIMIT)
        self.assertEqual(stat.S_IMODE(self.pending().stat().st_mode), 0o600)
    def test_03_dead_worker_status_preserves_without_state_mutation(self):
        self.checkpoint()
        state = {'jobId': JOB, 'state': 'RUNNING', 'phase': 'CAPTURE', 'pid': 2147483647, 'processStart': '0'}
        write(self.job / 'state.json', state)
        ns = functions('nvidia_backend.py', ['studio_status'], dict(JOB=re.compile(r'studio-[0-9a-f]{32}\Z'),
            Path=Path, cache=lambda: types.SimpleNamespace(PrivateTree=PrivateTree)))
        result = ns['studio_status'](None, JOB, control_root=self.base, export_root=self.exports)
        self.assertEqual(result['errorCode'], 'HANDOFF_UNRESOLVED_WORKER_OR_DESCENDANTS')
        self.assertEqual(result['state'], 'RUNNING')
        self.assertEqual(json.loads((self.job / 'state.json').read_text()), state)
        self.assertTrue(self.pending().exists())
        self.assertEqual(list(self.exports.iterdir()), [])
    def test_04_supervisor_cleanup_failure_preserves_and_holds_lock(self):
        self.checkpoint(); child = self.start('cleanup_error')
        self.await_file(self.pending()); self.assertIsNone(child.poll()); self.assert_locked()
        self.await_file(self.job / 'LEASE_SUPERVISOR_RESULT.json')
        self.assertFalse(json.loads((self.job / 'LEASE_SUPERVISOR_RESULT.json').read_text())['cleanupVerified'])
        with self.assertRaisesRegex(ValueError, 'VERIFIED_CLEANUP_REQUIRED'):
            safe.export_failure(self.job, self.exports / 'forbidden')
        self.assertEqual(list(self.exports.iterdir()), [])
    def test_05_descendants_unresolved_worker_and_supervisor_keep_lease(self):
        self.checkpoint(); child = self.start('descendant')
        self.await_file(self.pending()); self.assertIsNone(child.poll()); self.assert_locked()
        self.await_file(self.job / 'LEASE_SUPERVISOR_RESULT.json')
        row = json.loads((self.job / 'LEASE_SUPERVISOR_RESULT.json').read_text())
        self.assertEqual(row['reason'], 'HANDOFF_GPU_DESCENDANT_CLEANUP_UNRESOLVED')
        self.assertFalse(row['cleanupVerified'])
        child.kill(); child.wait(timeout=2)
        self.pending().unlink()  # isolated synthetic fixture only
        worker = self.start('worker_hold'); self.await_file(self.job / 'held-state.json')
        self.await_file(self.pending()); self.assertIsNone(worker.poll()); self.assert_locked()
        self.assertEqual(json.loads((self.job / 'held-state.json').read_text())['state'], 'RUNNING')
    def test_06_storage_failures_do_not_destroy_local_evidence(self):
        self.checkpoint(); original = (self.job / 'capture/CAPTURE_OPERATION_CHECKPOINT.json').read_bytes()
        with patch.object(safe.os, 'link', side_effect=OSError(28, 'synthetic disk full')):
            with self.assertRaises(OSError): safe.preserve_private_pending(self.job)
        self.assertFalse(self.pending().exists())
        self.assertEqual((self.job / 'capture/CAPTURE_OPERATION_CHECKPOINT.json').read_bytes(), original)
        self.assertEqual(list(self.job.glob('.pending-diagnostic-*')), [])
        wrapper.preserve_before_cleanup(self.job); saved = self.pending().read_bytes()
        write(self.job / 'LEASE_SUPERVISOR_RESULT.json', {'cleanupVerified': True})
        (self.exports / ('capture-diagnostic-' + JOB)).mkdir()
        deadline = (datetime.now(timezone.utc) + timedelta(seconds=3)).isoformat()
        self.assertEqual(wrapper.export_after_cleanup(self.job, self.exports, deadline)['status'], 'EXPORT_FAILED')
        self.assertEqual(self.pending().read_bytes(), saved)
    def test_07_concurrent_preservers_no_secret_export_or_gpu_unlock(self):
        self.checkpoint(); holding = self.start('descendant'); self.await_file(self.pending())
        before = self.pending().read_bytes()
        calls = [subprocess.Popen([sys.executable, '-I', '-S', str(CTRL / 'safe_capture_export.py'),
            '--job-root', str(self.job), '--private-pending', '--seconds', '1'], env={}) for _ in range(4)]
        for child in calls: self.assertEqual(child.wait(timeout=3), 0)
        self.assertEqual(self.pending().read_bytes(), before); self.assert_locked()
        self.assertIsNone(holding.poll()); self.assertEqual(list(self.exports.iterdir()), [])
    def test_08_deadline_and_stalled_diagnostic_child_are_bounded(self):
        self.checkpoint(); real_popen = subprocess.Popen; children = []
        def stalled(*args, **options):
            self.assertEqual(options['env'], {})
            child = real_popen([sys.executable, '-I', '-c', 'import time; time.sleep(20)'], **options)
            children.append(child); self.children.append(child); return child
        started = time.monotonic()
        with patch.object(wrapper.subprocess, 'Popen', side_effect=stalled):
            self.assertEqual(wrapper.preserve_before_cleanup(self.job)['status'], 'TIMEOUT')
        self.assertLess(time.monotonic() - started, 2)
        self.assertIsNotNone(children[0].poll())
        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        with self.assertRaises(TimeoutError): wrapper.export_after_cleanup(self.job, self.exports, expired)
        child = self.start('timeout'); self.assertEqual(child.wait(timeout=5), 0)
        row = json.loads((self.job / 'LEASE_SUPERVISOR_RESULT.json').read_text())
        self.assertEqual(row['reason'], 'HANDOFF_APPROVED_CAPTURE_DEADLINE_EXCEEDED')
        wrapper.preserve_before_cleanup(self.job); self.assertTrue(self.pending().exists())
        self.assertEqual(list(self.exports.iterdir()), [])
    def test_09_symlink_oversize_and_unknown_fields_fail_closed(self):
        self.checkpoint()
        target = self.job / 'capture/CAPTURE_OPERATION_CHECKPOINT.json'
        target.unlink(); target.symlink_to(self.base / 'missing-secret')
        self.assertEqual(safe.preserve_private_pending(self.job), 'NO_FIRST_FAILURE_EVIDENCE')
        target.unlink(); target.write_bytes(b'x' * (safe.LIMIT + 1)); target.chmod(0o600)
        self.assertEqual(safe.preserve_private_pending(self.job), 'NO_FIRST_FAILURE_EVIDENCE')
        target.unlink(); self.checkpoint()
        self.job.chmod(0o755)
        with self.assertRaises(ValueError): safe.preserve_private_pending(self.job)
        self.job.chmod(0o700)
        safe.preserve_private_pending(self.job)
        self.assertNotIn(SECRET, self.pending().read_text())
    def test_10_first_failure_is_durable_before_cleanup_can_hang(self):
        self.checkpoint(); child = self.start('cleanup_hang')
        self.await_file(self.job / 'cleanup-entered.json')
        self.assertTrue(self.pending().exists()); self.assert_locked()
        self.assertIsNone(child.poll())
        self.assertFalse((self.job / 'LEASE_SUPERVISOR_RESULT.json').exists())
        self.assertEqual(json.loads(self.pending().read_text())['firstFailure']['errorCode'], 'UP2_FRAME_GL_ERROR')
        with self.assertRaisesRegex(ValueError, 'VERIFIED_CLEANUP_REQUIRED'):
            safe.export_failure(self.job, self.exports / 'forbidden')
        self.assertEqual(list(self.exports.iterdir()), [])

if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--fixture': fixture(sys.argv[2], sys.argv[3])
    else: unittest.main(verbosity=2)
