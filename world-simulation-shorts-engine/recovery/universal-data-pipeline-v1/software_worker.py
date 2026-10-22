"""Bounded detached CPU/SwiftShader worker for compiler-selected data scenes."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import threading

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('_udp_existing_source_worker_utils', HERE.parent / 'universal-source-pipeline-v2/software_worker.py')
reused = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reused
spec.loader.exec_module(reused)
atomic, DescendantGuard = reused.atomic, reused.DescendantGuard
SCHEMA = 'WORLD_ENGINE_DATA_STUDIO_SUBMISSION_V1'
PROFILE = 'FREE_UNIVERSAL_DATA_REVIEW_V1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_package(raw, expected_sha):
    if len(raw) > 16 * 1024**2 or sha(raw) != expected_sha:
        raise RuntimeError('UDP_WORKER_PACKAGE_HASH_MISMATCH')
    package = json.loads(raw)
    pipeline, receipt = package.get('sourcePipeline', {}), package.get('executionReceipt', {})
    total = pipeline.get('totalFrames')
    selected = pipeline.get('runtimePayload', {})
    scene = selected.get('scene')
    wire = selected.get('sceneWireJSON')
    if (package.get('schema') != SCHEMA or package.get('profile') != PROFILE
            or pipeline.get('ready') is not True or pipeline.get('scope') != PROFILE
            or pipeline.get('mode') != 'FREE_DATA_REVIEW' or pipeline.get('simulationType') not in {'FICTIONAL', 'GENERAL'}
            or type(total) is not int or not 2 <= total <= 240 or pipeline.get('startFrame') != 0
            or pipeline.get('fps') != 30 or receipt.get('softwareOnly') is not True
            or receipt.get('historicalRenderAllowed') is not False or receipt.get('maxWallSeconds') != 900
            or receipt.get('sourceScope') != PROFILE or receipt.get('frameRange') != [0, total]
            or receipt.get('requestSHA256') != pipeline.get('requestSHA256')
            or sha(canonical(pipeline.get('originalRequest'))) != pipeline.get('requestSHA256')
            or not isinstance(scene, dict) or scene != package.get('videoPlan')
            or sha(canonical(scene)) != pipeline.get('sceneSHA256')
            or not isinstance(wire, str) or sha(wire.encode()) != pipeline.get('sceneWireSHA256')
            or json.loads(wire) != scene
            or scene.get('timing', {}).get('total_frames') != total
            or scene.get('timing', {}).get('fps') != 30
            or selected.get('sceneId') != pipeline.get('explicitSelectedSceneId')):
        raise RuntimeError('UDP_WORKER_EXECUTION_SCOPE_INVALID')
    expires = datetime.fromisoformat(receipt['expiresAt'].replace('Z', '+00:00'))
    if expires.tzinfo is None or (expires - datetime.now(timezone.utc)).total_seconds() <= 5:
        raise RuntimeError('UDP_WORKER_RECEIPT_EXPIRED')
    for row in pipeline.get('sourceBindings', []):
        relative = Path(row.get('path', ''))
        file = REPO / relative
        if relative.is_absolute() or '..' in relative.parts or any(p.is_symlink() for p in (file, *file.parents)):
            raise RuntimeError('UDP_WORKER_SOURCE_PATH_REJECTED')
        if not file.is_file() or sha(file.read_bytes()) != row.get('sha256'):
            raise RuntimeError('UDP_WORKER_SOURCE_BINDING_CHANGED')
    if not pipeline.get('sourceBindings'):
        raise RuntimeError('UDP_WORKER_SOURCE_BINDINGS_REQUIRED')
    return package


def validate_capture(directory, pipeline):
    """Verify actual encoder output independently of renderer receipt assertions."""
    directory = Path(directory)
    video, receipt_file = directory / 'VIDEO.mp4', directory / 'CAPTURE_RECEIPT.json'
    if not video.is_file() or video.is_symlink() or not receipt_file.is_file() or receipt_file.is_symlink():
        raise RuntimeError('UDP_CAPTURE_OUTPUT_MISSING')
    receipt = json.loads(receipt_file.read_bytes())
    data = video.read_bytes()
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(video)],
        capture_output=True, check=False, timeout=40)
    if probe.returncode:
        raise RuntimeError('UDP_CAPTURE_FFPROBE_FAILED')
    metadata = json.loads(probe.stdout)
    streams = metadata.get('streams', [])
    videos = [row for row in streams if row.get('codec_type') == 'video']
    total = pipeline['totalFrames']
    if (len(videos) != 1 or any(row.get('codec_type') == 'audio' for row in streams)
            or videos[0].get('codec_name') != 'h264' or videos[0].get('width') != 1080 or videos[0].get('height') != 1920
            or videos[0].get('r_frame_rate') != '30/1' or int(videos[0].get('nb_read_frames', '-1')) != total
            or abs(float(metadata.get('format', {}).get('duration', -1)) - total / 30) > .001):
        raise RuntimeError('UDP_CAPTURE_MEDIA_CONTRACT_INVALID')
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'], capture_output=True, check=False, timeout=60)
    if decoded.returncode or decoded.stderr:
        raise RuntimeError('UDP_CAPTURE_FULL_DECODE_FAILED')
    # Renderer receipt field agreement is further checked by the focused runtime
    # audit. Here the file, clock, and backend declaration cannot be fabricated.
    if (receipt.get('schema') != 'WORLD_ENGINE_UNIVERSAL_DATA_CAPTURE_V1'
            or receipt.get('status') != 'TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED'
            or receipt.get('sceneSHA256') != pipeline['sceneWireSHA256']
            or receipt.get('sourceRegionId') != pipeline['runtimePayload']['renderSettings']['sourceRegionId']
            or receipt.get('totalFrames') != total or receipt.get('renderedFrames') != total
            or receipt.get('softwareOnly') is not True or receipt.get('nvidiaVerified') is not False
            or receipt.get('visualQualityApproved') is not False or receipt.get('paidExecuted') is not False
            or 'SwiftShader' not in receipt.get('runtime', {}).get('backend', '')
            or receipt.get('video', {}).get('sha256') != sha(data)
            or receipt.get('video', {}).get('fullDecode') != 'PASS'
            or receipt.get('inputTrace') != pipeline['runtimePayload'].get('inputTrace')):
        raise RuntimeError('UDP_CAPTURE_RECEIPT_BINDING_INVALID')
    return {'videoSHA256': sha(data), 'videoBytes': len(data), 'totalFrames': total,
        'resolution': [1080, 1920], 'fps': 30, 'fullDecode': 'PASS', 'receipt': receipt,
        'sceneSemanticSHA256': pipeline['sceneSHA256'], 'sceneWireSHA256': pipeline['sceneWireSHA256'],
        'gpuRenderingVerified': False, 'qualityApproved': False}


def run(args):
    job = args.job_root
    if (not job.is_absolute() or not job.is_dir() or any(p.is_symlink() for p in (job, *job.parents))
            or job.stat().st_uid != os.getuid() or job.stat().st_mode & 0o077):
        raise RuntimeError('UDP_WORKER_PRIVATE_STATE_REQUIRED')
    state_file = job / 'state.json'
    state = json.loads(state_file.read_bytes())
    stage, started = 'PACKAGE_VERIFY', time.monotonic()
    try:
        for _ in range(100):
            if (job / 'launch.json').is_file():
                break
            time.sleep(.05)
        else:
            raise RuntimeError('UDP_WORKER_LAUNCH_RECEIPT_MISSING')
        package = validate_package((job / 'compiledpackage.json').read_bytes(), args.plan_sha256)
        pipeline, receipt = package['sourcePipeline'], package['executionReceipt']
        if receipt.get('jobId') != job.name:
            raise RuntimeError('UDP_WORKER_JOB_ID_MISMATCH')
        selected = pipeline['runtimePayload']
        scene_file = job / 'ACTUAL_SCENE.json'
        with scene_file.open('xb') as stream:
            stream.write(selected['sceneWireJSON'].encode())
        os.chmod(scene_file, 0o600)
        trace_file = job / 'INPUT_TRACE.json'
        with trace_file.open('x') as stream:
            json.dump(selected.get('inputTrace'), stream, allow_nan=False)
        os.chmod(trace_file, 0o600)
        output = args.export_root / job.name
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # capture_generic owns exclusive output-directory creation.
        state.update(state='RUNNING', phase='COMPILER_SCENE_NATIVE_DRAW', processedFrames=0)
        atomic(state_file, state)
        stage = 'ACTUAL_STUDIO_SOURCE_RENDER'
        command = ['node', str(HERE / 'capture_generic.mjs'), '--scene=' + str(scene_file),
            '--output-root=' + str(output), '--expected-sha256=' + pipeline['sceneWireSHA256'],
            '--source-region=' + selected['renderSettings']['sourceRegionId'], '--input-trace=' + str(trace_file)]
        remaining = (datetime.fromisoformat(receipt['expiresAt'].replace('Z', '+00:00')) - datetime.now(timezone.utc)).total_seconds()
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        progress_errors = []
        def track_actual_frames():
            try:
                for line in child.stdout:
                    if len(line) > 8192:
                        raise RuntimeError('UDP_CAPTURE_PROGRESS_INVALID')
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if row.get('stage') != 'ACTUAL_FRAME_DRAW':
                        continue
                    count = row.get('renderedFrames')
                    if (type(count) is not int or count != state['processedFrames'] + 1
                            or row.get('totalFrames') != pipeline['totalFrames']
                            or row.get('frame') != count - 1 or count > pipeline['totalFrames']):
                        raise RuntimeError('UDP_CAPTURE_PROGRESS_INVALID')
                    state.update(processedFrames=count, phase='ACTUAL_COMPILER_FRAME_DRAW')
                    atomic(state_file, state)
            except Exception as error:
                progress_errors.append(type(error).__name__)
        progress_thread = threading.Thread(target=track_actual_frames, daemon=True)
        progress_thread.start()
        with DescendantGuard(child.pid) as guard:
            try:
                returncode = child.wait(timeout=max(.1, min(895, remaining - 5)))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                raise RuntimeError('UDP_SOFTWARE_REVIEW_DEADLINE_EXCEEDED') from None
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                cleanup = guard.cleanup()
                atomic(job / 'cleanup.json', cleanup)
        progress_thread.join(timeout=5)
        child.stdout.close()
        if progress_thread.is_alive() or progress_errors:
            raise RuntimeError('UDP_CAPTURE_PROGRESS_TRACKING_FAILED')
        if cleanup['remaining'] or cleanup['errors'] or cleanup['observationError']:
            raise RuntimeError('UDP_WORKER_CLEANUP_UNVERIFIED')
        if returncode:
            raise RuntimeError('UDP_NATIVE_CAPTURE_FAILED')
        stage = 'VIDEO_VERIFY'
        validated = validate_capture(output, pipeline)
        atomic(job / 'MEDIA_VERIFICATION.json', validated)
        downloads = []
        for name in ('VIDEO.mp4', 'SHA256SUMS'):
            file = output / name
            if file.is_file() and not file.is_symlink():
                raw = file.read_bytes()
                downloads.append({'name': name, 'path': str(file), 'sha256': sha(raw), 'bytes': len(raw)})
        result = {'jobId': job.name, 'state': 'COMPLETED', 'softwareOnly': True,
            'historicalRenderAllowed': False, 'paidRenderAllowed': False, 'gpuRenderingVerified': False,
            'userApproved': False, 'downloads': downloads, 'sourceSceneSHA256': pipeline['sceneSHA256'],
            'sceneWireSHA256': pipeline['sceneWireSHA256'],
            'captureSignature': pipeline['captureSignature'], 'sourceInputSHA256': pipeline['compilerInputSHA256'],
            'actualRuntime': 'SOURCE_CHECKOUT_NOT_OCI_IMAGE'}
        atomic(job / 'result.json', result)
        state.update(state='COMPLETED', phase='DATA_SOFTWARE_REVIEW_COMPLETE', processedFrames=pipeline['totalFrames'], completedScenes=1)
    except Exception as error:
        code = str(error) if re.fullmatch(r'[A-Z][A-Z0-9_]{1,99}', str(error)) else 'UDP_STUDIO_WORKER_FAILED'
        state.update(state='FAILED', phase=stage, errorCode=code)
        atomic(job / 'failure.json', {'stage': stage, 'code': code, 'type': type(error).__name__, 'childExitCode': getattr(error, 'returncode', None)})
        raise
    finally:
        state['elapsedSeconds'] = round(time.monotonic() - started, 3)
        atomic(state_file, state)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-root', type=Path, required=True)
    parser.add_argument('--export-root', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    run(parser.parse_args())
