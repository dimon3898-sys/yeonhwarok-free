"""Fixed hardware-only bridge into the existing NVIDIA/ASTRA runtime.

No renderer, camera, shader or existing launcher is patched. The coordinator
holds the original common GPU lease for the whole job. Every scene obtains a
fresh unchanged native admission and allocation/VRAM monitoring.
"""
from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from cache import PrivateTree, canonical_sha256, storage

_SESSION = None
MAX_LOG_BYTES = 32 * 1024**2


class RenderError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def native_gpu():
    # Reuse the existing pinned module loader, not a replacement GPU probe.
    from orchestrator import manager
    manager_module = manager()
    directory = manager_module.job_store.DIAGNOSTIC_HELPERS
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    import startup
    if Path(startup.__file__).resolve().parent != directory.resolve():
        raise RenderError('NATIVE_STARTUP_ORIGIN_INVALID')
    return startup.NativeOperations()


def _normal_mode():
    if os.geteuid() != 1000 or os.getegid() != 1000:
        raise RenderError('ENGINE_UID_GID_1000_REQUIRED')
    if (os.environ.get('WORLD_ENGINE_STARTUP_MODE', 'normal') != 'normal'
            or os.environ.get('WORLD_ENGINE_RENDER_MODE') != 'gpu-required'):
        raise RenderError('EXPLICIT_NORMAL_GPU_REQUIRED_MODE_REQUIRED')


def _image_binding(plan):
    expected = plan.get('renderProfile', {}).get('imageDigest')
    configured = os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST')
    if (not isinstance(expected, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', expected)
            or configured != expected):
        raise RenderError('CONFIGURED_IMMUTABLE_IMAGE_BINDING_MISMATCH')
    # This is explicit operator configuration, not runtime self-attestation of
    # the container registry digest. Independent pull proves image identity.
    return expected


@contextmanager
def common_gpu_lease():
    _normal_mode()
    native = native_gpu()
    # Exact original common path: excludes legacy65422, ASTRA, F and V2 jobs.
    with native.gpu().capture_guard(storage.PRIVATE_BASE):
        yield


def prepare_job(plan, private_root, *, approval):
    """One CPU source preparation per job, reusable across all its scenes."""
    global _SESSION
    _normal_mode()
    _image_binding(plan)
    import universal_files
    universal_files.verify_extension()
    if plan.get('resolution') != {'width': 1080, 'height': 1920} or plan.get('aspectRatio') != '9:16':
        raise RenderError('UNSUPPORTED_NATIVE_RESOLUTION_OR_ASPECT_RATIO')
    native = native_gpu()
    native.bootstrap().prepare_environment(native.account(), storage=Path(private_root))
    native.source()
    if native.dependencies().get('status') != 'PASS':
        raise RenderError('CPU_DEPENDENCY_CHECK_FAILED')
    import prepare_video
    # Never bind a different plan after approval. This call prepares only
    # immutable ASTRA/runtime inputs and leaves scene geometry/time unchanged.
    inputs = prepare_video.prepare_job_inputs(plan, Path(private_root))
    if (not isinstance(inputs, dict) or not inputs.get('activationFile')
            or not isinstance(inputs.get('activationSha256'), str)):
        raise RenderError('UNIVERSAL_RUNTIME_INPUTS_REQUIRED')
    _SESSION = {'planSHA256': canonical_sha256(plan), 'inputs': inputs, 'native': native}
    return {'status': 'CPU_INPUTS_PREPARED', 'gpuRenderingVerified': False}


def _copy_artifact(source_tree, name, destination_tree):
    """Copy only fresh generated files, using existing no-follow primitives."""
    facts = source_tree.hash_file(name)
    source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=source_tree.fd)
    destination = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=destination_tree.fd)
    try:
        while True:
            block = os.read(source, 1024 * 1024)
            if not block:
                break
            storage._write_all(destination, block)
        os.fsync(destination)
    finally:
        os.close(source)
        os.close(destination)
    if destination_tree.hash_file(name) != facts or source_tree.hash_file(name) != facts:
        raise RenderError('CAPTURE_ARTIFACT_COPY_HASH_MISMATCH')
    return facts


def _run_native_capture(gpu, admission, config, command, environment, log_path, *, progress=None):
    """Use original query/termination APIs and the same strict memory budget."""
    if admission.test_only or admission.safe_report.get('gpuRenderingVerified') is not True:
        raise RenderError('TEST_ADMISSION_NOT_EXECUTABLE')
    allocation = admission.private_report['allocation']
    baseline = allocation['memory_total_mib'] - allocation['memory_free_mib']
    budget = admission.safe_report['vramBudgetBytes']
    process = None
    read_log = None
    pending = bytearray()
    def consume_progress():
        if read_log is None or progress is None:
            return
        block = os.read(read_log, 128 * 1024)
        pending.extend(block)
        while b'\n' in pending:
            line, _, rest = pending.partition(b'\n')
            pending[:] = rest
            if len(line) > 128 * 1024:
                raise RenderError('NATIVE_LOG_LINE_LIMIT_EXCEEDED')
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if (isinstance(event, dict) and event.get('phase') == 'SCENE_CAPTURE'
                    and type(event.get('completedFrames')) is int):
                progress({'completedFrames': event['completedFrames']})
        if len(pending) > 128 * 1024:
            raise RenderError('NATIVE_LOG_LINE_LIMIT_EXCEEDED')
    deadline = time.monotonic() + config.render_timeout_seconds
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, 'wb', buffering=0) as log:
            process = subprocess.Popen(command, cwd=gpu.ENGINE_ROOT, env=environment,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, close_fds=True)
            read_log = os.open(log_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            if progress:
                from orchestrator import _identity
                progress({'rendererIdentity': _identity(process.pid), 'completedFrames': 0})
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise RenderError('GPU_RENDER_DEADLINE_EXCEEDED')
                current = gpu.query_allocation(admission.environ, subprocess.run)
                if any(current[key] != allocation[key] for key in ('uuid', 'model', 'driver_version', 'memory_total_mib')):
                    raise RenderError('GPU_ALLOCATION_CHANGED_DURING_RENDER')
                growth = max(0, current['memory_total_mib'] - current['memory_free_mib'] - baseline) * gpu.MIB
                if growth > budget or current['memory_free_mib'] * gpu.MIB < gpu.RESERVED_MEMORY_BYTES:
                    raise RenderError('GPU_RENDER_VRAM_BUDGET_EXCEEDED')
                if os.fstat(log.fileno()).st_size > MAX_LOG_BYTES:
                    raise RenderError('NATIVE_LOG_LIMIT_EXCEEDED')
                consume_progress()
                time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
            if process.returncode != 0:
                raise RenderError('GPU_RENDER_PROCESS_FAILED')
            consume_progress()
    finally:
        if process is not None and process.poll() is None:
            gpu._stop_render(process)
        if read_log is not None:
            os.close(read_log)


def render_segment(plan, scene, output_directory, *, approval, progress=None):
    """Actual fixed native CLI; no test callback or caller-selected command."""
    _normal_mode()
    _image_binding(plan)
    if _SESSION is None or _SESSION['planSHA256'] != canonical_sha256(plan):
        raise RenderError('JOB_INPUT_PREPARATION_REQUIRED')
    profile = plan.get('renderProfile', {})
    if profile.get('status') != 'READY' or profile.get('adapter') != 'UNIVERSAL_AREA_ASTRA_V2':
        raise RenderError('UNSUPPORTED_UNIVERSAL_RENDERER_CAPABILITY')
    remaining = approval.get('remainingWallSeconds')
    if not isinstance(remaining, (int, float)) or remaining < 1:
        raise RenderError('APPROVED_JOB_DEADLINE_EXCEEDED')
    output_directory = Path(output_directory)
    with PrivateTree(output_directory) as attempt:
        attempt.write_json('PLAN.json', plan)
        with attempt.child('native-admission', create=True) as private_admission:
            gpu = _SESSION['native'].gpu()
            config = gpu.LauncherConfig(storage_root=private_admission.path,
                budget_gib=8., render_timeout_seconds=min(14400, max(1, int(remaining))))
            started = time.monotonic()
            admission = gpu.admit_gpu(config)  # No injected native replacements.
            admission_seconds = time.monotonic() - started
        if admission.test_only:
            raise RenderError('TEST_ADMISSION_NOT_EXECUTABLE')
        inputs = _SESSION['inputs']
        environment = dict(admission.environ,
            WORLD_ENGINE_ASTRA_ACTIVATION_FILE=str(inputs['activationFile']),
            WORLD_ENGINE_ASTRA_ACTIVATION_SHA256=inputs['activationSha256'])
        capture_root = attempt.path / 'native-capture'
        command = ['node', str(HERE / 'long_capture.mjs'), '--plan-file', str(attempt.path / 'PLAN.json'),
            '--plan-sha256', canonical_sha256(plan), '--scene-id', scene['sceneId'],
            '--admission-file', str(admission.admission_file), '--output-root', str(capture_root)]
        started = time.monotonic()
        _run_native_capture(gpu, admission, config, command, environment, attempt.path / 'native.log', progress=progress)
        with PrivateTree(capture_root) as native_capture:
            receipt = native_capture.json('SEGMENT_COMPLETE.json')
            if (receipt.get('schema') != 'WORLD_ENGINE_LONG_SEGMENT_COMPLETE_V2'
                    or receipt.get('hardwareVerified') is not True or receipt.get('fullDecodeVerified') is not True
                    or receipt.get('planSha256') != canonical_sha256(plan)
                    or any(receipt.get(key) != scene[key] for key in ('sceneId', 'startFrame', 'endFrame'))
                    or receipt.get('path') != 'segment.mp4'):
                raise RenderError('NATIVE_SEGMENT_RECEIPT_INVALID')
            files = ['segment.mp4', 'FRAMES.ndjson', 'SCENE_RECEIPT.json', 'SEGMENT_COMPLETE.json', 'SHA256SUMS']
            for name in files:
                # FFmpeg may create0644 under an otherwise private directory;
                # tighten only this job's newly generated, owned regular file.
                descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=native_capture.fd)
                try:
                    info = os.fstat(descriptor)
                    if info.st_uid != os.geteuid() or info.st_nlink != 1:
                        raise RenderError('NATIVE_ARTIFACT_OWNER_INVALID')
                    os.fchmod(descriptor, 0o600)
                finally:
                    os.close(descriptor)
                _copy_artifact(native_capture, name, attempt)
        facts = attempt.hash_file('segment.mp4')
        if facts['sha256'] != receipt.get('sha256'):
            raise RenderError('NATIVE_SEGMENT_HASH_MISMATCH')
        return {'sceneId': scene['sceneId'], 'startFrame': scene['startFrame'], 'endFrame': scene['endFrame'],
                'path': str(attempt.path / 'segment.mp4'), 'sha256': facts['sha256'],
                'bytes': facts['bytes'], 'artifacts': files, 'hardwareVerified': True,
                'fullDecodeVerified': True, 'visualQualityVerified': False,
                'timingsSeconds': {'admission': round(admission_seconds, 6),
                                  'captureEncodeDecode': round(time.monotonic() - started, 6)}}
