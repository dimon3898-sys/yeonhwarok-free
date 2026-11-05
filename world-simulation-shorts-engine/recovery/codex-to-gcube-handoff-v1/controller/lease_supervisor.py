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
import hashlib

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from common import RECOVERY, canonical, duration_contract, load, sha, validate_plan, verify_manifest
from nvidia_backend import approval_limit, cache, _capture_diagnostic_environment
_stop_requested = False


# Strict values, not a general log redactor. Unknown content is never retained.
_BROWSER_EXECUTABLES = {'/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    '/opt/google/chrome/chrome', '/opt/google/chrome/google-chrome'}
_BROWSER_ARGS = {'--disable-dev-shm-usage', '--headless', '--headless=new',
    '--headless=old', '--enable-gpu', '--enable-webgl', '--use-gl=angle',
    '--use-gl=egl', '--use-gl=desktop', '--use-angle=vulkan', '--use-angle=gl',
    '--use-angle=gles', '--use-angle=gl-egl', '--use-angle=default',
    '--use-angle=swiftshader', '--use-vulkan=native', '--use-vulkan=swiftshader',
    '--enable-features=Vulkan', '--enable-features=CDPScreenshotNewSurface',
    '--disable-vulkan-surface', '--disable-software-rasterizer',
    '--enable-unsafe-swiftshader', '--no-sandbox', '--disable-setuid-sandbox',
    '--disable-gpu-sandbox', '--disable-gpu', '--disable-webgl',
    '--ignore-gpu-blocklist', '--enable-automation', '--remote-debugging-pipe'}
_NATIVE_CODES = {'VK_ERROR_OUT_OF_HOST_MEMORY', 'VK_ERROR_OUT_OF_DEVICE_MEMORY',
    'VK_ERROR_INITIALIZATION_FAILED', 'VK_ERROR_DEVICE_LOST',
    'VK_ERROR_MEMORY_MAP_FAILED', 'VK_ERROR_LAYER_NOT_PRESENT',
    'VK_ERROR_EXTENSION_NOT_PRESENT', 'VK_ERROR_FEATURE_NOT_PRESENT',
    'VK_ERROR_INCOMPATIBLE_DRIVER', 'VK_ERROR_FORMAT_NOT_SUPPORTED',
    'VK_ERROR_UNKNOWN', 'VK_ERROR_SURFACE_LOST_KHR',
    'VK_ERROR_NATIVE_WINDOW_IN_USE_KHR', 'EGL_NOT_INITIALIZED',
    'EGL_BAD_ACCESS', 'EGL_BAD_ALLOC', 'EGL_BAD_ATTRIBUTE', 'EGL_BAD_CONFIG',
    'EGL_BAD_CONTEXT', 'EGL_BAD_CURRENT_SURFACE', 'EGL_BAD_DISPLAY',
    'EGL_BAD_MATCH', 'EGL_BAD_NATIVE_PIXMAP', 'EGL_BAD_NATIVE_WINDOW',
    'EGL_BAD_PARAMETER', 'EGL_BAD_SURFACE', 'EGL_CONTEXT_LOST',
    'GL_OUT_OF_MEMORY', 'GL_INVALID_OPERATION', 'GL_INVALID_VALUE',
    'GL_INVALID_ENUM', 'GL_INVALID_FRAMEBUFFER_OPERATION', 'GL_CONTEXT_LOST'}
_NATIVE_FUNCTIONS = {'vkCreateInstance', 'vkEnumeratePhysicalDevices',
    'vkCreateDevice', 'vkGetInstanceProcAddr', 'vkGetDeviceProcAddr',
    'eglInitialize', 'eglGetDisplay', 'eglCreateContext', 'eglMakeCurrent',
    'InitializeSandbox', 'InitializeVulkan', 'CreateVulkanInstance',
    'CreateVulkanDevice', 'InitializeGLOneOff', 'GetPlatformDisplay'}
_BROWSER_SIGNALS = {'SIGABRT', 'SIGBUS', 'SIGFPE', 'SIGILL', 'SIGINT',
    'SIGKILL', 'SIGPIPE', 'SIGQUIT', 'SIGSEGV', 'SIGTERM', 'SIGTRAP',
    'SIGXCPU', 'SIGXFSZ'}
_DRIVER_CAPABILITIES = {'compute', 'utility', 'graphics', 'video', 'display', 'compat32', 'all'}


class _BrowserDiagnostics:
    """Bounded safe facts from Playwright's existing pw:browser stream.

    The launch text is Playwright's joined argument string, not OS attestation.
    Full argv, arbitrary messages, paths, environment and UUIDs are not copied.
    """
    def __init__(self, environment):
        digest = environment.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST', '')
        devices = environment.get('NVIDIA_VISIBLE_DEVICES')
        caps = environment.get('NVIDIA_DRIVER_CAPABILITIES', '').split(',')
        icd = environment.get('VK_ICD_FILENAMES')
        self.value = {
            'schema': 'WORLD_ENGINE_BROWSER_DIAGNOSTIC_V1',
            'source': 'PLAYWRIGHT_BROWSER_STDIO', 'launchObserved': False,
            'executable': {'knownPath': None, 'basename': None, 'pathSHA256': None},
            'safeActualArgs': [], 'omittedArgumentCount': 0,
            'argumentLineSHA256': None, 'fullArgvCaptured': False,
            'browserExit': {'exitCode': None, 'signal': None, 'observed': False},
            'nativeErrors': [], 'observedLines': 0, 'droppedLines': 0,
            'truncated': False,
            'expectedImageDigest': digest if re.fullmatch(r'sha256:[a-f0-9]{64}', digest) else None,
            'graphicsEnvironment': {
                'gpuBackend': environment.get('GPU_BACKEND') if environment.get('GPU_BACKEND') in {'vulkan', 'egl'} else None,
                'renderMode': environment.get('WORLD_ENGINE_RENDER_MODE') if environment.get('WORLD_ENGINE_RENDER_MODE') in {'gpu-required', 'cpu'} else None,
                'driverCapabilities': sorted(set(caps)) if caps and all(c in _DRIVER_CAPABILITIES for c in caps) else [],
                'deviceSelectionClass': 'NOT_SET' if devices is None else 'ALL' if devices == 'all' else 'NONE' if devices in {'', 'none', 'void'} else 'EXPLICIT',
                'deviceSelectionSHA256': hashlib.sha256(devices.encode()).hexdigest() if isinstance(devices, str) else None,
                'vulkanICDOverrideSet': bool(icd),
                'vulkanICDOverrideSHA256': hashlib.sha256(icd.encode()).hexdigest() if isinstance(icd, str) else None,
                'libraryPathSet': bool(environment.get('LD_LIBRARY_PATH')),
                'runtimeDirSet': bool(environment.get('XDG_RUNTIME_DIR')),
                'displaySet': bool(environment.get('DISPLAY')),
                'uid': os.geteuid(), 'gid': os.getegid(),
                'nativeGraphicsInitializationVerified': False,
            },
        }
        self._bytes = 0

    def dropped(self):
        self.value['droppedLines'] = min(1000000, self.value['droppedLines'] + 1)
        self.value['truncated'] = True

    def consume(self, line):
        self.value['observedLines'] = min(1000000, self.value['observedLines'] + 1)
        if len(line) > 16384 or self._bytes + len(line) > 262144:
            self.dropped()
            return
        self._bytes += len(line)
        try:
            self._consume(line)
        except Exception:
            # Diagnostics cannot replace the original capture/progress failure.
            self.dropped()

    def _consume(self, line):
        text = line.decode('utf-8', errors='replace')
        if 'pw:browser ' not in text:
            return
        value = self.value
        if '<launching> ' in text and not value['launchObserved']:
            launch = text.split('<launching> ', 1)[1]
            parts = launch.split()
            if not parts:
                return
            executable, args = parts[0], parts[1:]
            value['launchObserved'] = True
            value['executable'] = {
                'knownPath': executable if executable in _BROWSER_EXECUTABLES else None,
                'basename': Path(executable).name if executable in _BROWSER_EXECUTABLES else None,
                'pathSHA256': hashlib.sha256(executable.encode()).hexdigest(),
            }
            safe = [arg for arg in args if arg in _BROWSER_ARGS]
            value['safeActualArgs'] = safe[:64]
            value['omittedArgumentCount'] = min(1000000, len(args) - len(value['safeActualArgs']))
            value['argumentLineSHA256'] = hashlib.sha256(line).hexdigest()
            if len(safe) > 64:
                value['truncated'] = True
        match = re.search(r'<process did exit: exitCode=(null|-?\d{1,3}), signal=(null|SIG[A-Z0-9]{1,10})>', text)
        if match:
            code = None if match[1] == 'null' else int(match[1])
            sig = None if match[2] == 'null' else match[2]
            if (code is None or -255 <= code <= 255) and (sig is None or sig in _BROWSER_SIGNALS):
                value['browserExit'] = {'exitCode': code, 'signal': sig, 'observed': True}
        if not re.search(r'\[pid=\d+\]\[err\]', text):
            return
        words = set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*', text))
        codes, functions = sorted(words & _NATIVE_CODES), sorted(words & _NATIVE_FUNCTIONS)
        lower = text.lower()
        category = ('VULKAN' if any(c.startswith('VK_') for c in codes) else
            'EGL' if any(c.startswith('EGL_') for c in codes) else
            'OPENGL' if codes else
            'DEVICE_ACCESS' if 'permission denied' in lower and any(w in lower for w in ('nvidia', 'vulkan', 'gpu', 'dri')) else
            'SANDBOX' if 'sandbox' in lower and any(w in lower for w in ('failed', 'error', 'denied')) else
            'VULKAN' if 'vulkan' in lower and any(w in lower for w in ('failed', 'error', 'not found', 'not supported')) else
            'ANGLE' if 'angle' in lower and any(w in lower for w in ('failed', 'error')) else
            'GPU_PROCESS' if 'gpu process' in lower and any(w in lower for w in ('failed', 'error', 'exited', 'crash')) else None)
        if category:
            event = {'category': category, 'codes': codes, 'functions': functions,
                     'lineSHA256': hashlib.sha256(line).hexdigest()}
            if len(value['nativeErrors']) < 32:
                value['nativeErrors'].append(event)
            else:
                self.dropped()


class _CaptureLineBuffer:
    """Keep the JSON progress bound; discard overlong non-JSON log lines."""
    def __init__(self, diagnostics):
        self.pending = bytearray()
        self.discarding = False
        self.diagnostics = diagnostics

    def feed(self, block):
        complete = []
        pieces = block.split(b'\n')
        for index, piece in enumerate(pieces):
            ended = index < len(pieces) - 1
            if not self.discarding:
                self.pending.extend(piece)
                prefix = self.pending.lstrip()
                structured = not prefix or prefix[:1] in (b'{', b'[')
                limit = 128 * 1024 if structured else 16384
                if len(self.pending) > limit:
                    if structured:
                        raise RuntimeError('HANDOFF_CAPTURE_PROGRESS_LIMIT')
                    self.diagnostics.dropped()
                    self.pending.clear()
                    self.discarding = True
            if ended:
                if not self.discarding:
                    complete.append(bytes(self.pending))
                self.pending.clear()
                self.discarding = False
        return complete


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
    started, last_monitor = time.monotonic(), 0
    diagnostics = _BrowserDiagnostics(environment)
    lines = _CaptureLineBuffer(diagnostics)
    reason, first_failure = None, None
    def preserve_browser_snapshot():
        try:
            atomic(Path(output) / 'BROWSER_DIAGNOSTIC.json', diagnostics.value)
        except Exception:
            pass  # Diagnostic storage never alters firstFailure or the lease.
    def consume(block):
        nonlocal count, reason, first_failure
        for line in lines.feed(block):
            try:
                row = json.loads(line)
            except (ValueError, UnicodeError):
                diagnostics.consume(line)
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
                    # A terminal FAILED receipt must enter owned cleanup even
                    # when an encoder child keeps the capture process alive.
                    reason = code
                    preserve_browser_snapshot()
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
                                stderr=subprocess.STDOUT, env=_capture_diagnostic_environment(environment),
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
                if lines.pending and not lines.pending.lstrip().startswith((b'{', b'[')):
                    diagnostics.consume(bytes(lines.pending))
                preserve_browser_snapshot()
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
                    'captureProcessExitCode': child.returncode if child is not None else None,
                    'browserDiagnostics': diagnostics.value,
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


