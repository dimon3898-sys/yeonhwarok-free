"""Bounded detached dispatch for authenticated free presentation requests.

The existing atomic-state and descendant-cleanup implementations are reused.
This worker owns only the new versioned request/capture binding, not a renderer.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


shared = load('_up2_preserved_worker_utilities', HERE.parent / 'universal-data-pipeline-v1/software_worker.py')
atomic, DescendantGuard = shared.atomic, shared.DescendantGuard
canonical, sha = shared.canonical, shared.sha
SCHEMA = 'WORLD_ENGINE_PRESENTATION_STUDIO_SUBMISSION_V2'
PROFILE = 'FREE_UNIVERSAL_PRESENTATION_REVIEW_V2'


def validate_package(raw, expected_sha):
    if len(raw) > 24 * 1024**2 or sha(raw) != expected_sha:
        raise RuntimeError('UP2_WORKER_PACKAGE_HASH_MISMATCH')
    package = json.loads(raw)
    pipeline, receipt = package.get('sourcePipeline', {}), package.get('executionReceipt', {})
    runtime, wire = pipeline.get('runtimePayload'), pipeline.get('runtimeRequestWireJSON')
    total = pipeline.get('totalFrames')
    if (package.get('schema') != SCHEMA or package.get('profile') != PROFILE
            or pipeline.get('ready') is not True or pipeline.get('scope') != PROFILE
            or pipeline.get('mode') != 'FREE_PRESENTATION_REVIEW'
            or pipeline.get('simulationType') not in {'GENERAL', 'FICTIONAL'}
            or type(total) is not int or not 2 <= total <= 240
            or pipeline.get('fps') != 30 or pipeline.get('startFrame') != 0
            or not isinstance(runtime, dict) or runtime != package.get('videoPlan')
            or runtime.get('schema') != 'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2'
            or runtime.get('totalFrames') != total or not isinstance(wire, str)
            or sha(wire.encode()) != pipeline.get('runtimeWireSHA256')
            or json.loads(wire) != runtime or sha(canonical(runtime)) != pipeline.get('runtimeSemanticSHA256')
            or pipeline.get('sourceAdmission', {}).get('status') != 'PASS'
            or pipeline.get('sourceAdmission', {}).get('preparedBeforeClaim') is not True
            or not re.fullmatch(r'[a-f0-9]{64}', str(pipeline.get('sourceAdmission', {}).get('sourceQualificationSHA256')))
            or sha(canonical(pipeline.get('originalRequest'))) != pipeline.get('requestSHA256')
            or receipt.get('requestSHA256') != pipeline.get('requestSHA256')
            or receipt.get('softwareOnly') is not True or receipt.get('historicalRenderAllowed') is not False
            or receipt.get('sourceScope') != PROFILE or receipt.get('frameRange') != [0, total]
            or receipt.get('maxWallSeconds') != 900):
        raise RuntimeError('UP2_WORKER_EXECUTION_SCOPE_INVALID')
    admission = pipeline['sourceAdmission']
    qualification_wire = admission.get('sourceQualificationWireJSON')
    if (not isinstance(qualification_wire, str)
            or sha(qualification_wire.encode()) != admission['sourceQualificationSHA256']
            or json.loads(qualification_wire) != admission.get('sourceQualification')
            or not isinstance(admission.get('sourceQualification'), dict)
            or admission['sourceQualification'].get('schema') != 'WORLD_ENGINE_PRESENTATION_SOURCES_V2'
            or admission['sourceQualification'].get('totalFrames') != total):
        raise RuntimeError('UP2_WORKER_QUALIFICATION_SEAL_MISMATCH')
    segments, end = runtime.get('segments'), 0
    if not isinstance(segments, list) or not segments or len(segments) != pipeline.get('segmentCount'):
        raise RuntimeError('UP2_WORKER_SEGMENT_BINDING_INVALID')
    for segment in segments:
        scene = segment.get('scene', {})
        if (segment.get('startFrame') != end or type(segment.get('endFrame')) is not int
                or segment['endFrame'] <= end or scene.get('timing', {}).get('total_frames') != segment['endFrame'] - end
                or scene.get('metadata', {}).get('output') != {'width': 1080, 'height': 1920, 'fps': 30, 'audio': False}):
            raise RuntimeError('UP2_WORKER_SEGMENT_BINDING_INVALID')
        end = segment['endFrame']
    if end != total or runtime.get('transitions') != [{'type': 'CUT', 'frame': s['startFrame']} for s in segments[1:]]:
        raise RuntimeError('UP2_WORKER_CUT_TIMELINE_INVALID')
    expires = datetime.fromisoformat(receipt['expiresAt'].replace('Z', '+00:00'))
    if expires.tzinfo is None or (expires - datetime.now(timezone.utc)).total_seconds() <= 5:
        raise RuntimeError('UP2_WORKER_RECEIPT_EXPIRED')
    bindings = pipeline.get('sourceBindings')
    if not isinstance(bindings, list) or not bindings:
        raise RuntimeError('UP2_WORKER_SOURCE_BINDINGS_REQUIRED')
    for row in bindings:
        relative = Path(row.get('path', ''))
        file = REPO / relative
        if (relative.is_absolute() or '..' in relative.parts or any(p.is_symlink() for p in (file, *file.parents))
                or not file.is_file() or sha(file.read_bytes()) != row.get('sha256')):
            raise RuntimeError('UP2_WORKER_SOURCE_BINDING_CHANGED')
    return package


def validate_capture(directory, pipeline):
    """Independently decode the produced file and verify the new receipt seals."""
    directory = Path(directory)
    video, receipt_file = directory / 'VIDEO.mp4', directory / 'CAPTURE_RECEIPT.json'
    if not video.is_file() or video.is_symlink() or not receipt_file.is_file() or receipt_file.is_symlink():
        raise RuntimeError('UP2_CAPTURE_OUTPUT_MISSING')
    receipt = json.loads(receipt_file.read_bytes())
    info = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(video)],
        capture_output=True, check=False, timeout=60)
    if info.returncode:
        raise RuntimeError('UP2_CAPTURE_FFPROBE_FAILED')
    metadata = json.loads(info.stdout)
    streams = metadata.get('streams', [])
    videos = [stream for stream in streams if stream.get('codec_type') == 'video']
    total, data = pipeline['totalFrames'], video.read_bytes()
    if (len(videos) != 1 or any(s.get('codec_type') == 'audio' for s in streams)
            or videos[0].get('codec_name') != 'h264' or videos[0].get('width') != 1080 or videos[0].get('height') != 1920
            or videos[0].get('r_frame_rate') != '30/1' or int(videos[0].get('nb_read_frames', '-1')) != total
            or abs(float(metadata.get('format', {}).get('duration', -1)) - total / 30) > .001):
        raise RuntimeError('UP2_CAPTURE_MEDIA_CONTRACT_INVALID')
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'], capture_output=True, timeout=60)
    if decoded.returncode or decoded.stderr:
        raise RuntimeError('UP2_CAPTURE_FULL_DECODE_FAILED')
    if (receipt.get('schema') != 'WORLD_ENGINE_PRESENTATION_CAPTURE_V2'
            or receipt.get('status') != 'TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED'
            or receipt.get('packageSHA256') != pipeline['runtimeWireSHA256']
            or receipt.get('sourceInputSHA256') != pipeline['compilerInputSHA256']
            or receipt.get('sourceQualificationSHA256') != pipeline['sourceAdmission']['sourceQualificationSHA256']
            or receipt.get('totalFrames') != total or receipt.get('renderedFrames') != total
            or receipt.get('softwareOnly') is not True or receipt.get('nvidiaVerified') is not False
            or receipt.get('visualQualityApproved') is not False or receipt.get('paidExecuted') is not False
            or 'SwiftShader' not in receipt.get('runtime', {}).get('backend', '')
            or receipt.get('video', {}).get('sha256') != sha(data) or receipt.get('video', {}).get('fullDecode') != 'PASS'):
        raise RuntimeError('UP2_CAPTURE_RECEIPT_BINDING_INVALID')
    return {'videoSHA256': sha(data), 'videoBytes': len(data), 'frames': total, 'resolution': [1080, 1920],
        'fps': 30, 'fullDecode': 'PASS', 'runtimeSemanticSHA256': pipeline['runtimeSemanticSHA256'],
        'runtimeWireSHA256': pipeline['runtimeWireSHA256'], 'sourceQualificationSHA256': receipt['sourceQualificationSHA256'],
        'gpuRenderingVerified': False, 'qualityApproved': False}


def run(args):
    job = args.job_root
    if (not job.is_absolute() or not job.is_dir() or any(p.is_symlink() for p in (job, *job.parents))
            or job.stat().st_uid != os.getuid() or job.stat().st_mode & 0o077):
        raise RuntimeError('UP2_WORKER_PRIVATE_STATE_REQUIRED')
    state_file = job / 'state.json'
    state, stage, started = json.loads(state_file.read_bytes()), 'PACKAGE_VERIFY', time.monotonic()
    try:
        for _ in range(100):
            if (job / 'launch.json').is_file():
                break
            time.sleep(.05)
        else:
            raise RuntimeError('UP2_WORKER_LAUNCH_RECEIPT_MISSING')
        package = validate_package((job / 'compiledpackage.json').read_bytes(), args.plan_sha256)
        pipeline, receipt = package['sourcePipeline'], package['executionReceipt']
        if receipt.get('jobId') != job.name:
            raise RuntimeError('UP2_WORKER_JOB_ID_MISMATCH')
        request_file = job / 'ACTUAL_RUNTIME_REQUEST.json'
        with request_file.open('xb') as output:
            output.write(pipeline['runtimeRequestWireJSON'].encode())
        request_file.chmod(0o600)
        output_root = args.export_root / job.name
        output_root.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        state.update(state='RUNNING', phase='PRESENTATION_SOURCE_VERIFY', processedFrames=0,
            totalScenes=pipeline['segmentCount'], completedScenes=0)
        atomic(state_file, state)
        stage = 'ACTUAL_PRESENTATION_CAPTURE'
        command = ['node', str(HERE / 'capture_presentation.mjs'), '--package=' + str(request_file),
            '--expected-sha256=' + pipeline['runtimeWireSHA256'], '--output-root=' + str(output_root),
            '--expected-source-qualification-sha256=' + pipeline['sourceAdmission']['sourceQualificationSHA256']]
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            text=True, bufsize=1, start_new_session=True)
        progress_errors = []
        def progress():
            try:
                for line in child.stdout:
                    if len(line) > 16384:
                        raise RuntimeError('UP2_CAPTURE_PROGRESS_INVALID')
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if row.get('stage') != 'ACTUAL_FRAME_DRAW':
                        continue
                    count = row.get('renderedFrames')
                    if (type(count) is not int or count != state['processedFrames'] + 1
                            or row.get('frame') != count - 1 or row.get('totalFrames') != pipeline['totalFrames']
                            or count > pipeline['totalFrames']):
                        raise RuntimeError('UP2_CAPTURE_PROGRESS_INVALID')
                    completed = sum(s['endFrame'] <= count for s in pipeline['runtimePayload']['segments'])
                    state.update(processedFrames=count, completedScenes=completed, phase='ACTUAL_PRESENTATION_FRAME_DRAW')
                    atomic(state_file, state)
            except Exception as error:
                progress_errors.append(type(error).__name__)
        thread = threading.Thread(target=progress, daemon=True)
        thread.start()
        remaining = (datetime.fromisoformat(receipt['expiresAt'].replace('Z', '+00:00')) - datetime.now(timezone.utc)).total_seconds()
        with DescendantGuard(child.pid) as guard:
            try:
                returncode = child.wait(timeout=max(.1, min(895, remaining - 5)))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait()
                raise RuntimeError('UP2_SOFTWARE_REVIEW_DEADLINE_EXCEEDED') from None
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                cleanup = guard.cleanup()
                atomic(job / 'cleanup.json', cleanup)
        thread.join(timeout=5); child.stdout.close()
        if thread.is_alive() or progress_errors or cleanup['remaining'] or cleanup['errors'] or cleanup['observationError']:
            raise RuntimeError('UP2_WORKER_PROGRESS_OR_CLEANUP_FAILED')
        if returncode:
            raise RuntimeError('UP2_NATIVE_CAPTURE_FAILED')
        if state['processedFrames'] != pipeline['totalFrames']:
            raise RuntimeError('UP2_CAPTURE_ACTUAL_FRAME_PROGRESS_INCOMPLETE')
        stage = 'VIDEO_VERIFY'
        validated = validate_capture(output_root, pipeline)
        atomic(job / 'MEDIA_VERIFICATION.json', validated)
        downloads = []
        for name in ('VIDEO.mp4', 'SHA256SUMS'):
            file = output_root / name
            raw = file.read_bytes()
            downloads.append({'name': name, 'path': str(file), 'sha256': sha(raw), 'bytes': len(raw)})
        atomic(job / 'result.json', {'jobId': job.name, 'state': 'COMPLETED', 'softwareOnly': True,
            'historicalRenderAllowed': False, 'paidRenderAllowed': False, 'gpuRenderingVerified': False,
            'userApproved': False, 'downloads': downloads, 'captureSignature': pipeline['captureSignature'],
            'sourceInputSHA256': pipeline['compilerInputSHA256'], 'runtimeWireSHA256': pipeline['runtimeWireSHA256'],
            'sourceQualificationSHA256': pipeline['sourceAdmission']['sourceQualificationSHA256'],
            'sourceCredits': pipeline['sourceAdmission'].get('sourceCredits', []),
            'actualRuntime': 'SOURCE_CHECKOUT_NOT_OCI_IMAGE'})
        state.update(state='COMPLETED', phase='PRESENTATION_SOFTWARE_REVIEW_COMPLETE',
            processedFrames=pipeline['totalFrames'], completedScenes=pipeline['segmentCount'])
    except Exception as error:
        code = str(error) if re.fullmatch(r'[A-Z][A-Z0-9_]{1,99}', str(error)) else 'UP2_STUDIO_WORKER_FAILED'
        state.update(state='FAILED', phase=stage, errorCode=code)
        atomic(job / 'failure.json', {'stage': stage, 'code': code, 'type': type(error).__name__})
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
