"""Retain the ORIGINAL flock description while an owned capture is cleaned up.

No new GPU lock is created. The caller must already hold the original common
lease and pass its uniquely identified descriptor. CPU tests use the same
inherited-description mechanism without invoking any GPU operation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time
import re

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from common import RECOVERY, canonical, duration_contract, load, sha, validate_plan, verify_manifest
from nvidia_backend import approval_limit, cache
_stop_requested = False


def request_stop(*_):
    global _stop_requested
    _stop_requested = True


def validate_lease_descriptor(fd, expected_path):
    expected_path = Path(expected_path)
    if (type(fd) is not int or fd < 3 or not expected_path.is_absolute()
            or any(p.is_symlink() for p in (expected_path, *expected_path.parents))):
        raise RuntimeError('HANDOFF_ORIGINAL_LEASE_DESCRIPTOR_REQUIRED')
    actual, expected = os.fstat(fd), os.stat(expected_path, follow_symlinks=False)
    if (not stat.S_ISREG(actual.st_mode) or actual.st_uid != os.getuid()
            or actual.st_nlink != 1 or actual.st_mode & 0o077
            or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino)
            or Path(os.readlink(f'/proc/self/fd/{fd}')) != expected_path):
        raise RuntimeError('HANDOFF_ORIGINAL_LEASE_DESCRIPTOR_CHANGED')
    return fd


def original_lease_descriptor(expected_path):
    expected_path = Path(expected_path)
    found = []
    for row in Path('/proc/self/fd').iterdir():
        try:
            if int(row.name) >= 3 and Path(os.readlink(row)) == expected_path:
                found.append(int(row.name))
        except (OSError, ValueError):
            continue
    if len(found) != 1:
        raise RuntimeError('HANDOFF_ORIGINAL_LEASE_DESCRIPTOR_AMBIGUOUS')
    return validate_lease_descriptor(found[0], expected_path)


def parent_identity(pid):
    file = Path('/proc') / str(pid)
    fields = (file / 'stat').read_text().rsplit(') ', 1)[1].split()
    return {'pid': pid, 'startTicks': fields[19], 'uid': file.stat().st_uid}


def supervise_owned_capture(command, *, lease_fd, lease_path, parent, seconds,
                            environment, output, capture_factory=subprocess.Popen,
                            _cpu_test_before_cleanup=None, monitor=None, total_frames=180):
    """Internal function; production CLI constructs command from pinned inputs.

    A failed cleanup remains unresolved. The original descriptor is kept open
    until owned descendants have been checked, including after parent death.
    """
    if type(total_frames) is not int or total_frames not in (180, 300):
        raise RuntimeError('HANDOFF_CAPTURE_FRAME_CONTRACT_REQUIRED')
    validate_lease_descriptor(lease_fd, lease_path)
    if (parent['pid'] != os.getppid() or parent_identity(parent['pid']) != parent
            or parent['uid'] != os.getuid() or not 0 < seconds <= 600):
        raise RuntimeError('HANDOFF_CAPTURE_PARENT_IDENTITY_REQUIRED')
    parent_fd = os.pidfd_open(parent['pid'], 0)
    if parent_identity(parent['pid']) != parent:
        os.close(parent_fd)
        raise RuntimeError('HANDOFF_CAPTURE_PARENT_IDENTITY_CHANGED')
    helpers = load('_handoff_original_descendant_cleanup',
                   RECOVERY / 'studio-integration-gates-v1/process_guard.py')
    atomic = load('_handoff_original_atomic_record',
                  RECOVERY / 'universal-source-pipeline-v2/software_worker.py').atomic
    child, cleanup, stage, count = None, None, 'START', 0
    started, pending, last_monitor = time.monotonic(), bytearray(), 0
    reason, first_failure = None, None
    def consume(block):
        nonlocal count, reason, first_failure
        pending.extend(block)
        if len(pending) > 128 * 1024:
            raise RuntimeError('HANDOFF_CAPTURE_PROGRESS_LIMIT')
        while b'\n' in pending:
            line, _, rest = pending.partition(b'\n'); pending[:] = rest
            try:
                row = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(row, dict):
                continue
            if row.get('status') == 'FAILED' and first_failure is None:
                code, failed_stage = row.get('code'), row.get('stage')
                allowed = {'RENDER_RUNTIME', 'APPROVAL_OR_INPUT', 'SOURCE_OR_SCENE',
                    'RUNTIME_PERMISSIONS', 'GPU_NATIVE_DRAW', 'ENCODING_OR_DECODE', 'DEADLINE'}
                if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{2,120}', code) and failed_stage in allowed:
                    first_failure = {'code': code, 'stage': failed_stage}
                    atomic(Path(output) / 'FIRST_CAPTURE_FAILURE.json', first_failure)
                    try:
                        from capture_diagnostics_safe import preserve_before_cleanup
                        preserve_before_cleanup(output)
                    except BaseException:
                        pass  # First safe evidence must not depend on cleanup returning.
            if row.get('stage') != 'ACTUAL_FRAME_DRAW':
                continue
            if (type(row.get('renderedFrames')) is not int or row['renderedFrames'] != count + 1
                    or row.get('totalFrames') != total_frames or row.get('frame') != count
                    or total_frames == 300 and (type(row.get('totalFrames')) is not int or type(row.get('frame')) is not int)
                    or count >= total_frames):
                raise RuntimeError('HANDOFF_ACTUAL_FRAME_PROGRESS_INVALID')
            count += 1
            atomic(Path(output) / 'actual-progress.json', {'processedFrames': count, 'totalFrames': total_frames})
    try:
        if select.select([parent_fd], [], [], 0)[0]:
            raise RuntimeError('HANDOFF_PARENT_EXITED_BEFORE_CAPTURE')
        child = capture_factory(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, env=environment,
                                start_new_session=True, close_fds=True)
        os.set_blocking(child.stdout.fileno(), False)
        with helpers.DescendantGuard(child.pid) as guard:
            try:
                while child.poll() is None:
                    if _stop_requested:
                        reason = 'HANDOFF_CAPTURE_STOP_REQUESTED'
                        break
                    if select.select([parent_fd], [], [], 0)[0]:
                        reason = 'HANDOFF_PARENT_EXITED_CAPTURE_ABORTED'
                        break
                    if time.monotonic() - started >= seconds:
                        reason = 'HANDOFF_APPROVED_CAPTURE_DEADLINE_EXCEEDED'
                        break
                    if monitor is not None and time.monotonic() - last_monitor >= 1:
                        monitor(seconds - (time.monotonic() - started))
                        last_monitor = time.monotonic()
                    try:
                        data = os.read(child.stdout.fileno(), 65536)
                    except BlockingIOError:
                        data = b''
                    consume(data)
                    if reason:
                        break
                    time.sleep(.05)
                # A fast failure can exit before the first poll. Drain only
                # already available bounded bytes; never wait on an orphan's
                # inherited stdout or print arbitrary exception text.
                for _ in range(4):
                    try:
                        block = os.read(child.stdout.fileno(), 65536)
                    except BlockingIOError:
                        break
                    if not block:
                        break
                    consume(block)
                stage = 'DESCENDANT_CLEANUP'
            finally:
                if _cpu_test_before_cleanup is not None:
                    # Python-only fixture seam, never exposed by CLI or job data.
                    _cpu_test_before_cleanup()
                cleanup = guard.cleanup()
                child.wait(timeout=5)
                child.stdout.close()
        if cleanup['remaining'] or cleanup['errors'] or cleanup['observationError']:
            reason = 'HANDOFF_GPU_DESCENDANT_CLEANUP_UNRESOLVED'
        if reason:
            raise RuntimeError(reason)
        if child.returncode:
            reason = first_failure['code'] if first_failure else 'HANDOFF_CAPTURE_PROCESS_FAILED'
            raise RuntimeError(reason)
        return {'status': 'CAPTURE_PROCESS_AND_CLEANUP_COMPLETE', 'exitCode': child.returncode,
                'processedFramesObserved': count, 'cleanup': cleanup,
                'parentStillAlive': not bool(select.select([parent_fd], [], [], 0)[0])}
    except BaseException as error:
        if reason is None:
            message = str(error)
            reason = message if re.fullmatch(r'[A-Z][A-Z0-9_]{1,120}', message) else 'HANDOFF_CAPTURE_SUPERVISOR_FAILED'
        raise
    finally:
        verified = bool(cleanup and not cleanup['remaining'] and not cleanup['errors']
                        and not cleanup['observationError'])
        try:
            try:
                os.close(parent_fd)
                if child is not None and child.poll() is None:
                    # Only this owned process group; no broad process matching.
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait(timeout=5)
            except BaseException:
                verified = False
            try:
                atomic(Path(output) / 'LEASE_SUPERVISOR_RESULT.json', {
                    'stage': stage, 'reason': reason, 'cleanup': cleanup,
                    'firstFailure': first_failure,
                    'gpuBasicProbeRepeated': False, 'newLockCreated': False,
                    'inheritedOriginalLeaseHeldThroughCleanup': True, 'cleanupVerified': verified})
            except BaseException:
                verified = False
        finally:
            try:
                from capture_diagnostics_safe import preserve_before_cleanup
                preserve_before_cleanup(output)
            except BaseException:
                pass  # Diagnostic I/O must not release an unresolved lease.
            if child is not None and not verified:
                # Even a wait/storage failure cannot close the last inherited
                # original flock description after its parent has died.
                while True:
                    time.sleep(1)


def run(args):
    from nvidia_backend import NvidiaPresentationBackend, _runtime_environment, lease_helper
    job = Path(args.job_root)
    with cache().PrivateTree(job) as private:
        plan, approval, state = private.json('PLAN.json'), private.json('APPROVAL.json'), private.json('state.json')
    image = plan['renderProfile']['imageDigest']
    backend = NvidiaPresentationBackend(args.manifest_file, args.manifest_sha256, image)
    backend._verify(plan, 'GCUBE_NVIDIA_SIX_SECOND_REVIEW_V1')
    timing = duration_contract(plan)
    if sha(canonical(plan)) != args.plan_sha256:
        raise RuntimeError('HANDOFF_PRIVATE_PLAN_CHANGED')
    permit = approval_limit(approval, plan, image)
    deadline = datetime.fromisoformat(state['executionDeadline'])
    seconds = min(permit['maxWallSeconds'], (deadline - datetime.now(timezone.utc)).total_seconds())
    if seconds <= 0:
        raise RuntimeError('HANDOFF_APPROVAL_EXPIRED')
    original = lease_helper()
    lease_path = Path(original.storage.PRIVATE_BASE) / 'CAPTURE.guard'
    gpu = original.native_gpu().gpu()
    environment = _runtime_environment()
    def query(remaining):
        def bounded_runner(*values, **options):
            options['timeout'] = max(.05, min(1, remaining))
            return subprocess.run(*values, **options)
        return gpu.query_allocation(environment, bounded_runner)
    baseline = query(seconds)
    gpu._check_limits(baseline, gpu.shared_memory_facts(), 8 * gpu.GIB)
    with cache().PrivateTree(job) as private:
        private.write_json('GPU_ALLOCATION.json', {
            'model': baseline['model'], 'driverVersion': baseline['driver_version'],
            'memoryTotalMiB': baseline['memory_total_mib'], 'uuidSHA256': sha(baseline['uuid'].encode()),
            'nativeWebGLBasicProbeRepeated': False})
    def monitor(remaining):
        current = query(remaining)
        if any(current[key] != baseline[key] for key in ('uuid', 'model', 'driver_version', 'memory_total_mib')):
            raise RuntimeError('HANDOFF_GPU_ALLOCATION_CHANGED')
        growth = max(0, baseline['memory_free_mib'] - current['memory_free_mib']) * gpu.MIB
        if growth > 8 * gpu.GIB or current['memory_free_mib'] * gpu.MIB < gpu.RESERVED_MEMORY_BYTES:
            raise RuntimeError('HANDOFF_GPU_MEMORY_BUDGET_EXCEEDED')
    command = ['node', str(HERE.parent / 'backend/capture_nvidia.mjs'),
        '--package=' + str(job / 'RUNTIME_REQUEST.json'), '--output-root=' + str(job / 'capture'),
        '--expected-sha256=' + plan['runtimeWireSHA256'],
        '--expected-source-qualification-sha256=' + plan['sourceQualificationSHA256'],
        '--deps-root=' + os.environ.get('WORLD_ENGINE_NODE_DEPS', ''),
        '--authorization=' + str(job / 'APPROVAL.json'),
        '--expected-authorization-sha256=' + sha((job / 'APPROVAL.json').read_bytes()),
        '--plan-file=' + str(job / 'PLAN.json'), '--expected-plan-sha256=' + args.plan_sha256,
        '--private-workspace-root=' + str(args.control_root),
        '--public-export-root=' + str(args.export_root)]
    result = supervise_owned_capture(command, lease_fd=args.lease_fd, lease_path=lease_path,
        parent={'pid': args.parent_pid, 'startTicks': args.parent_start, 'uid': os.getuid()},
        seconds=min(seconds, (deadline - datetime.now(timezone.utc)).total_seconds()),
        environment=environment, output=job, monitor=monitor, total_frames=timing['totalFrames'])
    with cache().PrivateTree(job) as private:
        private.write_json('CAPTURE_PROCESS_RESULT.json', result)
    return result


if __name__ == '__main__':
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(number, request_stop)
    parser = argparse.ArgumentParser()
    for name in ('job-root', 'plan-sha256', 'manifest-file', 'manifest-sha256',
                 'control-root', 'export-root', 'parent-start'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--lease-fd', type=int, required=True)
    parser.add_argument('--parent-pid', type=int, required=True)
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        code = str(error)
        safe = code if re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', code) else 'HANDOFF_CAPTURE_SUPERVISOR_FAILED'
        try:
            # If supervise returned/raised after creating a child, its nested
            # finally already wrote a cleanup receipt or keeps the FD forever.
            # No receipt here therefore means no capture child was created.
            with cache().PrivateTree(Path(args.job_root)) as private:
                if not (private.path / 'LEASE_SUPERVISOR_RESULT.json').exists():
                    private.write_json('LEASE_SUPERVISOR_RESULT.json', {
                        'stage': 'PRE_CAPTURE_VALIDATION', 'reason': safe, 'captureChildStarted': False,
                        'cleanup': {'remaining': [], 'errors': [], 'observationError': None},
                        'cleanupVerified': True, 'firstFailure': {'stage': 'PRE_CAPTURE_VALIDATION', 'code': safe}})
        except Exception:
            print('HANDOFF_FAILURE_STATE_WRITE_FAILED', file=sys.stderr)
        print(safe, file=sys.stderr)
        raise SystemExit(1)

