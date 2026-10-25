"""One bounded, explicit Studio GPU job; no restart or retry entry point."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import PROFILE, RECOVERY, canonical, load, sha
from nvidia_backend import NvidiaPresentationBackend, approval_limit, cache, lease_helper, _runtime_environment
from lease_supervisor import original_lease_descriptor, parent_identity


@contextmanager
def keep_original_lease_until_cleanup(original, job, holder, save):
    """Never execute original LOCK_UN while a GPU descendant is unresolved."""
    with original.common_gpu_lease():
        try:
            yield
        except BaseException:
            child = holder[0]
            if child is not None:
                if child.poll() is None:
                    try:
                        child.send_signal(signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        child.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        pass
                try:
                    with cache().PrivateTree(job) as directory:
                        result = directory.json('LEASE_SUPERVISOR_RESULT.json')
                    verified = result.get('cleanupVerified') is True and child.poll() is not None
                except (OSError, ValueError, RuntimeError, FileNotFoundError):
                    verified = False
                if not verified:
                    save(state='RUNNING', phase='UNRESOLVED_CAPTURE_CLEANUP',
                         errorCode='HANDOFF_UNRESOLVED_CAPTURE_CLEANUP')
                    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                        signal.signal(number, lambda *_: None)
                    # No rendering or retry occurs here. Keep the SAME original
                    # lease/claim for the operator's manual workload stop.
                    while True:
                        time.sleep(1)
            raise


def _code(error):
    value = str(error)
    return value if re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', value) else 'HANDOFF_WORKER_FAILED'


def _write_runtime(job, wire):
    descriptor = os.open(job / 'RUNTIME_REQUEST.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        data = wire.encode()
        while data:
            count = os.write(descriptor, data); data = data[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_capture(output, plan):
    video = output / 'VIDEO.mp4'
    with cache().PrivateTree(output) as directory:
        receipt = directory.json('CAPTURE_RECEIPT.json')
        frames = directory.json('FRAME_EVIDENCE.json')
    if (receipt.get('schema') != 'WORLD_ENGINE_NVIDIA_SIX_SECOND_CAPTURE_V1'
            or receipt.get('status') != 'TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED'
            or receipt.get('packageSHA256') != plan['runtimeWireSHA256']
            or receipt.get('sourceQualificationSHA256') != plan['sourceQualificationSHA256']
            or receipt.get('softwareOnly') is not False or receipt.get('nvidiaVerified') is not True
            or receipt.get('renderedFrames') != 180 or receipt.get('totalFrames') != 180
            or receipt.get('visualQualityApproved') is not False
            or receipt.get('video', {}).get('sha256') != sha(video.read_bytes())):
        raise RuntimeError('HANDOFF_NVIDIA_CAPTURE_RECEIPT_INVALID')
    proofs = receipt.get('nativeStability', [])
    if [row.get('segmentIndex') for row in proofs] != list(range(len(plan['runtime']['segments']))):
        raise RuntimeError('HANDOFF_NATIVE_STABILITY_SEGMENTS_REQUIRED')
    for proof in proofs:
        draws, backend = proof.get('draws', []), proof.get('backend', '')
        if (proof.get('schema') != 'WORLD_ENGINE_NATIVE_MAP_STABILITY_V1' or proof.get('status') != 'PASS'
                or not isinstance(backend, str) or not re.search(r'\bNVIDIA\b', backend, re.I)
                or 'Vulkan' not in backend or re.search(r'swiftshader|llvmpipe|lavapipe|softpipe|software', backend, re.I)
                or len(draws) != 3 or any(row.get('index') != index or row.get('frame') != 0
                    or row.get('glError') != 0 or row.get('rgbaBytes') != 1080 * 1920 * 4
                    or row.get('nonBlackPixels', 0) <= 1080 * 1920 * .2
                    or not re.fullmatch(r'[a-f0-9]{64}', str(row.get('rawRGBA256'))) for index, row in enumerate(draws))
                or len({row['rawRGBA256'] for row in draws}) != 1):
            raise RuntimeError('HANDOFF_NATIVE_STABILITY_PROOF_INVALID')
    metadata = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
        '-show_format', '-of', 'json', str(video)], capture_output=True, timeout=45, check=False)
    if metadata.returncode:
        raise RuntimeError('HANDOFF_VIDEO_FFPROBE_FAILED')
    info = json.loads(metadata.stdout)
    streams = info.get('streams', [])
    if (len(streams) != 1 or streams[0].get('codec_type') != 'video'
            or streams[0].get('codec_name') != 'h264' or streams[0].get('width') != 1080
            or streams[0].get('height') != 1920 or streams[0].get('r_frame_rate') != '30/1'
            or int(streams[0].get('nb_read_frames', '-1')) != 180
            or abs(float(info.get('format', {}).get('duration', -1)) - 6) > .001):
        raise RuntimeError('HANDOFF_VIDEO_180_FRAME_CONTRACT_FAILED')
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'],
                             capture_output=True, timeout=45, check=False)
    if decoded.returncode or decoded.stderr:
        raise RuntimeError('HANDOFF_VIDEO_FULL_DECODE_FAILED')
    rows = frames.get('frames', [])
    if (len(rows) != 180 or [row.get('frame') for row in rows] != list(range(180))
            or any(row.get('diagnostic', {}).get('glError') != 0 for row in rows)):
        raise RuntimeError('HANDOFF_ACTUAL_FRAME_EVIDENCE_INVALID')
    return {'schema': 'WORLD_ENGINE_NVIDIA_SIX_SECOND_MEDIA_VERIFY_V1',
            'videoSHA256': sha(video.read_bytes()), 'frames': 180, 'width': 1080,
            'height': 1920, 'fps': 30, 'durationSeconds': 6, 'fullDecode': 'PASS',
            'audioStreams': 0, 'visualQuality': 'USER_VIDEO_REVIEW_REQUIRED'}


def _export(job, output, export_root, control_root):
    delivery = load('_handoff_original_export_media', RECOVERY / 'production-studio-mvp-v1/studio_delivery.py')
    private_base = Path(control_root) / 'handoff-export-private'
    with cache().PrivateTree(private_base, create=True):
        pass
    with cache().PrivateTree(job) as directory:
        with directory.child('public', create=True) as public:
            with (output / 'VIDEO.mp4').open('rb') as source, (public.path / 'WORLD_ENGINE_STUDIO_VIDEO.mp4').open('xb') as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
                os.fchmod(target.fileno(), 0o600); target.flush(); os.fsync(target.fileno())
            public.write_json('QUALITY_SUMMARY.json', {
                'schema': 'WORLD_ENGINE_STUDIO_SAFE_QA_V1', 'technicalVerification': 'PASS',
                'frames': 180, 'fps': 30, 'width': 1080, 'height': 1920, 'durationSeconds': 6,
                'audioStreams': 0, 'sfxEnabled': False, 'videoDecodedPixelsUnchanged': True,
                'fullDecode': 'PASS', 'visualQuality': 'USER_VIDEO_REVIEW_REQUIRED',
                'externalDownloadVerified': False, 'finalPromotion': False})
            names = ['QUALITY_SUMMARY.json', 'WORLD_ENGINE_STUDIO_VIDEO.mp4']
            hashes = ''.join(sha((public.path / name).read_bytes()) + '  ' + name + '\n' for name in names)
            with (public.path / 'SHA256SUMS').open('x') as stream:
                stream.write(hashes)
            return delivery.export_media(public.path, Path(export_root), private_base)


def _run(args):
    job, control, exports = map(Path, (args.job_root, args.control_root, args.export_root))
    with cache().PrivateTree(job) as directory:
        plan, approval, state = directory.json('PLAN.json'), directory.json('APPROVAL.json'), directory.json('state.json')
    image = plan['renderProfile']['imageDigest']
    backend = NvidiaPresentationBackend(args.manifest_file, args.manifest_sha256, image)
    backend._verify(plan, PROFILE)
    if sha(canonical(plan)) != args.plan_sha256:
        raise RuntimeError('HANDOFF_PRIVATE_PLAN_CHANGED')
    approval_limit(approval, plan, image)
    _write_runtime(job, plan['runtimeWireJSON'])
    # Start is acknowledged before the detached worker renders. A container
    # restart does not recreate either this file or the inherited start claim.
    for _ in range(100):
        if (job / 'launch.json').is_file():
            break
        time.sleep(.05)
    else:
        raise RuntimeError('HANDOFF_LAUNCH_RECEIPT_MISSING')
    original = lease_helper()
    supervisor, cleanup_verified, holder = None, False, [None]
    started = time.monotonic()
    def save(**updates):
        state.update(updates, updatedAt=datetime.now(timezone.utc).isoformat(),
                     elapsedSeconds=time.monotonic() - started)
        with cache().PrivateTree(job) as directory:
            directory.write_json('state.json', state, replace=True)
    try:
        with keep_original_lease_until_cleanup(original, job, holder, save):
            fd = original_lease_descriptor(Path(original.storage.PRIVATE_BASE) / 'CAPTURE.guard')
            save(state='RUNNING', phase='CAPTURE')
            parent = parent_identity(os.getpid())
            log = os.open(job / 'lease-supervisor.stderr.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                supervisor = subprocess.Popen([sys.executable, str(HERE / 'lease_supervisor.py'),
                '--job-root', str(job), '--plan-sha256', args.plan_sha256,
                '--manifest-file', args.manifest_file, '--manifest-sha256', args.manifest_sha256,
                '--control-root', str(control), '--export-root', str(exports),
                '--lease-fd', str(fd), '--parent-pid', str(parent['pid']),
                '--parent-start', parent['startTicks']], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=log,
                env=_runtime_environment(), pass_fds=(fd,), start_new_session=True, close_fds=True)
                holder[0] = supervisor
            finally:
                os.close(log)
            with cache().PrivateTree(job) as directory:
                directory.write_json('lease-holder.json', parent_identity(supervisor.pid))
            deadline = datetime.fromisoformat(state['executionDeadline'])
            while supervisor.poll() is None:
                progress = job / 'actual-progress.json'
                if progress.is_file():
                    with cache().PrivateTree(job) as directory:
                        row = directory.json(progress.name)
                    count = row.get('processedFrames')
                    if type(count) is not int or not state['processedFrames'] <= count <= 180:
                        raise RuntimeError('HANDOFF_CAPTURE_PROGRESS_INVALID')
                    if count != state['processedFrames']:
                        save(processedFrames=count,
                             completedScenes=sum(s['endFrame'] <= count for s in plan['runtime']['segments']))
                remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
                if remaining < -8:
                    # Never kill the last original-lease holder while cleanup
                    # is unresolved. Preserve ACTIVE claim and require review.
                    raise RuntimeError('HANDOFF_UNRESOLVED_CAPTURE_CLEANUP')
                time.sleep(.1)
            with cache().PrivateTree(job) as directory:
                result = directory.json('LEASE_SUPERVISOR_RESULT.json')
            cleanup = result.get('cleanup')
            cleanup_verified = bool(cleanup and not cleanup['remaining'] and not cleanup['errors'] and not cleanup['observationError'])
            if not cleanup_verified:
                raise RuntimeError('HANDOFF_UNRESOLVED_CAPTURE_CLEANUP')
            if supervisor.returncode:
                raise RuntimeError(result.get('reason') or 'HANDOFF_CAPTURE_PROCESS_FAILED')
            save(phase='VIDEO_VERIFY')
            output = job / 'capture'
            remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                raise RuntimeError('HANDOFF_APPROVED_JOB_DEADLINE_EXCEEDED')
            runtime = load('_handoff_preserved_postprocess_deadline', RECOVERY / 'production-studio-mvp-v1/studio_runtime.py')
            with runtime._deadline(remaining):
                validation = _validate_capture(output, plan)
                with cache().PrivateTree(job) as directory:
                    directory.write_json('MEDIA_VERIFICATION.json', validation)
                save(phase='EXPORT')
                exported = _export(job, output, exports, control)
            save(state='COMPLETED', phase='COMPLETE', processedFrames=180,
                 completedScenes=len(plan['runtime']['segments']), gpuRenderingVerified=True,
                 result=exported, errorCode=None)
    except BaseException as error:
        unresolved = supervisor is not None and (supervisor.poll() is None or not cleanup_verified)
        save(state='RUNNING' if unresolved else 'FAILED',
             phase='UNRESOLVED_CAPTURE_CLEANUP' if unresolved else 'FAILED', errorCode=_code(error))
        raise
    return state


def run(args):
    try:
        return _run(args)
    except BaseException as error:
        # This path also records source/mode/expiry failures which occur before
        # lease acquisition. Such failures must not disappear as stale QUEUED.
        try:
            with cache().PrivateTree(Path(args.job_root)) as directory:
                state = directory.json('state.json')
                if state.get('state') == 'QUEUED':
                    code = _code(error)
                    stage = 'APPROVAL_OR_INPUT' if any(word in code for word in ('APPROVAL', 'PLAN', 'EXPIRED')) else 'SOURCE_VERIFY'
                    directory.write_json('state.json', {**state, 'state': 'FAILED', 'phase': stage,
                        'errorCode': code, 'firstFailure': {'stage': stage, 'code': code},
                        'gpuRenderingVerified': False}, replace=True)
        except Exception:
            print('HANDOFF_FAILURE_STATE_WRITE_FAILED', file=sys.stderr)
        raise


if __name__ == '__main__':
    def interrupted(*_):
        raise RuntimeError('HANDOFF_WORKER_STOP_REQUESTED')
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(number, interrupted)
    parser = argparse.ArgumentParser()
    for name in ('job-root', 'plan-sha256', 'manifest-file', 'manifest-sha256', 'control-root', 'export-root'):
        parser.add_argument('--' + name, required=True)
    try:
        run(parser.parse_args())
    except BaseException as error:
        print(_code(error), file=sys.stderr)
        raise SystemExit(1)
