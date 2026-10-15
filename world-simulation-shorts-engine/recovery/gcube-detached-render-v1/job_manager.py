#!/usr/bin/env python3
"""One explicitly armed 65422 job, independent of a terminal; no HTTP API."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import selectors
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import job_store
from job_store import Store, JobError, CONTROL_ROOT, EXPORT_ROOT
import inspect_existing
storage, records = job_store.storage, job_store.records
LAUNCH = Path('/opt/world-engine-storage-fix/launch.py')
MAX_LOG = 32 * 1024**2
MAX_LINE = 128 * 1024
JOB_DEADLINE = 3900


class ManagerError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def process_identity(pid):
    if type(pid) is not int or not 0 < pid < 2**31:
        raise ManagerError('PROCESS_IDENTITY_INVALID')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    text = Path('/proc', str(pid), 'stat').read_text()
    fields = text[text.rfind(')') + 2:].split()
    if len(fields) < 20 or fields[0] in {'Z', 'X'} or not fields[19].isdigit():
        raise ProcessLookupError()
    return {'pid': pid, 'bootId': boot, 'startTime': fields[19]}


def is_alive(identity):
    if identity is None:
        return False
    if not job_store._identity(identity):
        raise ManagerError('PROCESS_IDENTITY_INVALID')
    try:
        return process_identity(identity['pid']) == identity
    except (FileNotFoundError, ProcessLookupError):
        return False


def _initial(test_only):
    now = stamp()
    return {'schema': job_store.SCHEMA, 'jobId': '65422-' + os.urandom(12).hex(),
            'state': 'QUEUED', 'reason': 'NEW_JOB', 'phase': 'QUEUED',
            'createdAt': now, 'updatedAt': now, 'supervisorIdentity': None,
            'rendererIdentity': None, 'exitCode': None, 'firstFailure': None,
            'result': None, 'testOnly': test_only, 'sequence': 0,
            'gpuRenderingVerified': False, 'remotePersistenceVerified': False,
            'externalDownloadVerified': False}


def _close_lock(store, descriptor):
    # Never LOCK_UN the inherited open-file-description: the detached worker
    # retains the same lock after this parent closes its descriptor.
    os.close(descriptor)
    store._lock_fd = None


def status(store):
    value = store.read()
    if value is None:
        return {'schema': 'WORLD_ENGINE_DETACHED_STATUS_V1', 'state': 'NOT_STARTED',
                'renderAllowed': False, 'gpuRenderingVerified': False,
                'remotePersistenceVerified': False, 'externalDownloadVerified': False}
    if value['state'] in {'COMPLETED', 'FAILED'} or is_alive(value['supervisorIdentity']):
        return value
    if is_alive(value['rendererIdentity']):
        # The orphan native process still owns its original capture guard.
        result = dict(value)
        result.update(state='RUNNING', reason='NATIVE_STILL_RUNNING')
        return result
    descriptor = store.lock()
    try:
        value = store.read()
        if value['state'] in {'COMPLETED', 'FAILED'} or is_alive(value['supervisorIdentity']):
            return value
        if is_alive(value['rendererIdentity']):
            return {**value, 'state': 'RUNNING', 'reason': 'NATIVE_STILL_RUNNING'}
        return store.save({**value, 'state': 'FAILED', 'phase': 'FAILED',
                           'reason': 'WORKER_LOST', 'updatedAt': stamp(), 'exitCode': 1, 'result': None})
    finally:
        _close_lock(store, descriptor)


def _read_json_fd(directory, name):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = storage._file_info(descriptor)
        if not 1 <= info.st_size <= 128 * 1024:
            raise ManagerError('RESULT_VERIFICATION_FAILED')
        return json.loads(storage._read_fd(descriptor, limit=128 * 1024))
    finally:
        os.close(descriptor)


def verify_export(result, export_root):
    if not job_store._result(result):
        raise ManagerError('RESULT_VERIFICATION_FAILED')
    capture = result['captures'][0]
    root = directory = unit = None
    try:
        root = storage._open_directory(export_root)
        directory = os.open(result['exportDirectory'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
        unit = os.open(capture['directory'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        receipt = _read_json_fd(unit, 'EXPORT_COMPLETE.json')
        if (receipt.get('schema') != 'WORLD_ENGINE_PUBLIC_EXPORT_RECEIPT_V1'
                or receipt.get('status') != 'COMPLETE' or receipt.get('sourceSha256SumsVerified') is not True
                or receipt.get('remotePersistenceVerified') is not False
                or receipt.get('externalDownloadVerified') is not False
                or receipt.get('privateDataAllowed') is not False
                or not isinstance(receipt.get('captureId'), str)
                or not re.fullmatch('[0-9a-f]{64}', receipt['captureId'])
                or not capture['directory'].startswith('capture-' + receipt['captureId'][:12] + '-')
                or sorted(receipt.get('files', []), key=lambda x: x['file']) != sorted(capture['files'], key=lambda x: x['file'])):
            raise ManagerError('RESULT_VERIFICATION_FAILED')
        # Reuse the already-tested original-byte/FFprobe verifier, unchanged.
        dependency = HERE / 'verify_artifacts.py'
        if not dependency.is_file():
            dependency = HERE.parent / 'gcube-65422-render-v1/verify_artifacts.py'
        spec = importlib.util.spec_from_file_location('detached_artifact_verifier', dependency)
        verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
        def run_with_export_fd(*args, **kwargs):
            if 'pass_fds' in kwargs:
                raise ManagerError('RESULT_VERIFICATION_FAILED')
            return subprocess.run(*args, **kwargs, pass_fds=(unit,))
        # Pass only the read-only capture directory to the helper's subprocess.
        # The child resolves its own fd, even after UID drop makes a parent's
        # /proc/<pid>/fd inaccessible. Do not change dumpability or the helper.
        verifier.subprocess = SimpleNamespace(run=run_with_export_fd,
                                              SubprocessError=subprocess.SubprocessError)
        anchor = next(item['sha256'] for item in capture['files'] if item['file'] == 'SHA256SUMS')
        # The pinned directory descriptors keep all untrusted ancestor components
        # outside the verifier's path walk, which then rehashes after FFprobe.
        checked = verifier.verify_public(Path('/proc/self/fd') / str(unit) / 'public-review', anchor)
        if sorted(checked['files'], key=lambda x: x['file']) != sorted(capture['files'], key=lambda x: x['file']):
            raise ManagerError('RESULT_VERIFICATION_FAILED')
        return result
    finally:
        for descriptor in (unit, directory, root):
            if descriptor is not None:
                os.close(descriptor)


def native_work(state, update, control_root):
    """Fixed original launcher only; never a caller-selected shell command."""
    log = None
    process = None
    first_failure, result = None, None
    total, pending = 0, bytearray()
    started = time.monotonic()
    def consume(line):
        nonlocal first_failure, result
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            return
        if not isinstance(event, dict):
            return
        if event.get('schema') == records.SCHEMA and event.get('exitCode'):
            safe = records.safe_record(event)
            if first_failure is None:
                first_failure = safe
                update({'firstFailure': safe})
        if event.get('phase') == 'RTX_NATIVE_CAPTURE':
            update({'phase': 'CAPTURE'})
        if event.get('schema') == 'WORLD_ENGINE_EXPORT_LOCATION_V1' and 'captures' in event:
            if not job_store._result(event) or result is not None:
                raise ManagerError('RESULT_VERIFICATION_FAILED')
            result = event
            update({'phase': 'EXPORT'})
    try:
        directory = storage._open_directory(control_root, safe_parents=True)
        try:
            fd = os.open('native-' + state['jobId'] + '.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
        finally:
            os.close(directory)
        log = os.fdopen(fd, 'wb', buffering=0)
        process = subprocess.Popen(['/usr/bin/python3', str(LAUNCH), '--render-65422', '--vram-budget-gib', '8'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True, env=dict(os.environ, WORLD_ENGINE_STARTUP_MODE='normal',
                                                            WORLD_ENGINE_RENDER_MODE='gpu-required'))
        update({'rendererIdentity': process_identity(process.pid), 'phase': 'NATIVE_STARTUP'})
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while selector.get_map():
                if time.monotonic() - started > JOB_DEADLINE:
                    raise ManagerError('DEADLINE_EXCEEDED')
                for key, _ in selector.select(0.5):
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(block)
                    if total > MAX_LOG:
                        raise ManagerError('LOG_LIMIT_EXCEEDED')
                    storage._write_all(log.fileno(), block)
                    pending.extend(block)
                    while b'\n' in pending:
                        line, _, rest = pending.partition(b'\n'); pending[:] = rest
                        if len(line) > MAX_LINE:
                            raise ManagerError('LOG_LIMIT_EXCEEDED')
                        consume(line)
                    if len(pending) > MAX_LINE:
                        raise ManagerError('LOG_LIMIT_EXCEEDED')
            if pending:
                consume(pending)
            code = process.wait(timeout=10)
        finally:
            selector.close()
        return {'exitCode': code if 0 <= code <= 255 else 128 + abs(code),
                'result': result, 'firstFailure': first_failure}
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait(timeout=5)
        if process is not None and process.stdout is not None:
            process.stdout.close()
        if log is not None:
            os.fsync(log.fileno()); log.close()


def _worker(store, value, ack, native_override, verify_override):
    def update(changes):
        nonlocal value
        if set(changes) - {'rendererIdentity', 'phase', 'firstFailure'}:
            raise ManagerError('UNEXPECTED_FAILURE')
        if value['firstFailure'] is not None:
            changes = {k: v for k, v in changes.items() if k != 'firstFailure'}
        value = store.save({**value, **changes, 'updatedAt': stamp()})
        return value
    try:
        os.setsid()
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        def interrupted(number, frame):
            raise ManagerError('WORKER_INTERRUPTED')
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        null = os.open('/dev/null', os.O_RDWR)
        for target in (0, 1, 2): os.dup2(null, target)
        if null > 2: os.close(null)
        keep = {0, 1, 2, store._lock_fd, ack}
        for name in os.listdir('/proc/self/fd'):
            if int(name) not in keep:
                try: os.close(int(name))
                except OSError: pass
        value = store.save({**value, 'state': 'RUNNING', 'supervisorIdentity': process_identity(os.getpid()),
                            'phase': 'DETACHED', 'reason': 'STARTING', 'updatedAt': stamp()})
        os.write(ack, b'READY'); os.close(ack); ack = None
        value = store.save({**value, 'state': 'RUNNING', 'reason': 'NATIVE_RUNNING',
                            'phase': 'NATIVE_STARTUP', 'updatedAt': stamp()})
        outcome = (native_override(value, update) if native_override is not None
                   else native_work(value, update, store.control_root))
        if not isinstance(outcome, dict) or type(outcome.get('exitCode')) is not int:
            raise ManagerError('UNEXPECTED_FAILURE')
        failure = outcome.get('firstFailure')
        if failure is not None and value['firstFailure'] is None:
            update({'firstFailure': records.safe_record(failure)})
        if outcome['exitCode'] != 0 or value['firstFailure'] is not None:
            code = outcome['exitCode'] if 0 < outcome['exitCode'] <= 255 else 1
            reason = 'NATIVE_FAILED'
            if value['firstFailure'] and value['firstFailure']['stage'] == 'STORAGE': reason = 'STORAGE_FAILED'
            value = store.save({**value, 'state': 'FAILED', 'phase': 'FAILED', 'reason': reason,
                                'exitCode': code, 'updatedAt': stamp()})
            return
        update({'phase': 'VERIFY'})
        result = outcome.get('result')
        (verify_override or verify_export)(result, store.export_root)
        value = store.save({**value, 'state': 'COMPLETED', 'phase': 'COMPLETE', 'reason': 'SUCCEEDED',
                            'result': result, 'exitCode': 0, 'updatedAt': stamp()})
    except BaseException as error:
        reason = error.code if isinstance(error, ManagerError) and error.code in job_store.REASONS else (
            'STORAGE_FAILED' if isinstance(error, JobError) else 'RESULT_VERIFICATION_FAILED' if value.get('phase') == 'VERIFY' else 'UNEXPECTED_FAILURE')
        try:
            value = store.read() or value
            if value['state'] not in {'COMPLETED', 'FAILED'}:
                store.save({**value, 'state': 'FAILED', 'phase': 'FAILED', 'reason': reason,
                            'exitCode': 1, 'result': None, 'updatedAt': stamp()})
        except BaseException:
            pass  # The private store writes failure first; never convert to success.
    finally:
        if ack is not None:
            try: os.close(ack)
            except OSError: pass


def start(store, *, native_override=None, verify_override=None, inspect_override=None, ack_timeout=8):
    """Python seams are TEST_ONLY; production CLI cannot select commands/probes."""
    test_only = any(item is not None for item in (native_override, verify_override, inspect_override))
    descriptor = store.lock()
    read_fd = write_fd = None
    child = None
    old_hup = signal.getsignal(signal.SIGHUP)
    try:
        prior = store.read()
        if prior is not None:
            return prior  # Never launch again, including completed/failed/stale jobs.
        gate = (inspect_override() if inspect_override is not None else inspect_existing.inspect(
            control_root=store.control_root, private_base=storage.PRIVATE_BASE,
            export_root=store.export_root, exclude_pids=(os.getpid(),)))
        if not isinstance(gate, dict) or gate.get('status') != 'CLEAR':
            raise ManagerError('EXISTING_CAPTURE_REQUIRES_REVIEW')
        value = store.create(_initial(test_only))
        read_fd, write_fd = os.pipe()
        signal.signal(signal.SIGHUP, signal.SIG_IGN)  # Protect fork→setsid handshake.
        child = os.fork()
        if child == 0:
            os.close(read_fd)
            try:
                _worker(store, value, write_fd, native_override, verify_override)
            finally:
                os._exit(0)  # Job outcome is durable state, never GPU/service health.
        os.close(write_fd); write_fd = None
        ready, _, _ = select.select([read_fd], [], [], ack_timeout)
        if ready: os.read(read_fd, 16)
        # Even an ACK timeout is never an invitation to submit a second job.
        return store.read()
    except BaseException:
        if child is None:
            try:
                value = store.read()
                if value and value['state'] == 'QUEUED':
                    store.save({**value, 'state': 'FAILED', 'phase': 'FAILED', 'reason': 'SPAWN_FAILED',
                                'exitCode': 1, 'updatedAt': stamp()})
            except BaseException: pass
        raise
    finally:
        signal.signal(signal.SIGHUP, old_hup)
        for fd in (read_fd, write_fd):
            if fd is not None:
                try: os.close(fd)
                except OSError: pass
        _close_lock(store, descriptor)


def _identity_setup():
    # Original bootstrap configures groups and runtime without a GPU probe.
    sys.path.insert(0, str(job_store.DIAGNOSTIC_HELPERS))
    from startup import NativeOperations
    native = NativeOperations(); account = native.account()
    fd = storage._open_directory(CONTROL_ROOT, safe_parents=True)
    try:
        storage._private_check(fd, account)
        if storage._filesystem(CONTROL_ROOT) not in storage.LOCAL_FILESYSTEMS:
            raise ManagerError('JOB_PATH_UNSAFE')
    finally: os.close(fd)
    native.bootstrap().prepare_environment(account, storage=CONTROL_ROOT)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ManagerError('INVALID_MANAGER_ARGUMENTS')


def main(argv=None):
    parser = Parser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True, parser_class=Parser)
    sub.add_parser('inspect'); sub.add_parser('status')
    begin = sub.add_parser('start'); begin.add_argument('--confirm-new-job', action='store_true')
    try:
        args = parser.parse_args(argv)
        if args.action == 'inspect':
            value = inspect_existing.inspect()
            print(json.dumps(value, sort_keys=True)); return 0 if value['status'] == 'CLEAR' else 2
        if args.action == 'start' and (not args.confirm_new_job or os.environ.get('WORLD_ENGINE_STARTUP_MODE', 'normal') != 'normal'):
            raise ManagerError('EXPLICIT_NORMAL_NEW_JOB_CONFIRMATION_REQUIRED')
        _identity_setup()
        store = Store()
        value = status(store) if args.action == 'status' else start(store)
        print(json.dumps(value, sort_keys=True))
        return 0 if value.get('state') != 'FAILED' else 2
    except Exception as error:
        code = error.code if isinstance(error, (ManagerError, JobError)) else 'MANAGER_OPERATION_FAILED'
        allowed = set(job_store.ERROR_CODES) | {'PROCESS_IDENTITY_INVALID', 'EXISTING_CAPTURE_REQUIRES_REVIEW',
            'INVALID_MANAGER_ARGUMENTS', 'EXPLICIT_NORMAL_NEW_JOB_CONFIRMATION_REQUIRED'}
        if code not in allowed: code = 'MANAGER_OPERATION_FAILED'
        print(json.dumps({'schema': 'WORLD_ENGINE_DETACHED_MANAGER_ERROR_V1', 'state': 'BLOCKED',
                          'reason': code, 'renderAllowed': False, 'gpuRenderingVerified': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
