#!/usr/bin/env python3
"""Explicit, detached, resumable scene coordinator; no public execution API.

This adds a multi-scene ledger around the existing private-storage, process
identity, common GPU lock, NVIDIA admission, FFmpeg and export components.
Production has no command override or CPU fallback. Paid execution requires a
private operator approval bound to the complete plan and immutable image.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from cache import CacheError, PrivateTree, SceneCache, canonical_sha256, _pinned_path
from contracts import validate_plan

CONTROL_ROOT = Path('/var/lib/world-engine-private/engine/universal-video-v2')
EXPORT_ROOT = Path('/world-storage')
SCHEMA = 'WORLD_ENGINE_UNIVERSAL_JOB_V2'
AUTH_SCHEMA = 'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1'
JOB_ID = re.compile(r'video-v2-[0-9a-f]{24}\Z')
_manager = None


class CoordinatorError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def manager():
    global _manager
    if _manager is None:
        path = _pinned_path('/opt/world-engine-detached-render/job_manager.py',
            HERE.parent / 'gcube-detached-render-v1/job_manager.py',
            '6398967204168e9284a6cc1b5b7f7e2951b996fb7cf5cb3d5f0a785b26047d99')
        directory = path.parent
        for name, expected in (
            ('job_store.py', '1b8261f59a0b0652dae64fdd1ed040cb24b80743780c40fb141576fe7bb7b5fe'),
            ('inspect_existing.py', '23a361ac0da95dad50ae7c2d5a57d2e527c904869b2d8bbf8e99146386cf7b38')):
            _pinned_path(directory / name, directory / name, expected)
        sys.path.insert(0, str(directory))
        spec = importlib.util.spec_from_file_location('_universal_original_manager', path)
        candidate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(candidate)
        if (Path(candidate.__file__).absolute() != path.absolute()
                or Path(candidate.job_store.__file__).absolute() != (directory / 'job_store.py').absolute()
                or Path(candidate.inspect_existing.__file__).absolute() != (directory / 'inspect_existing.py').absolute()):
            raise CoordinatorError('PINNED_MANAGER_ORIGIN_INVALID')
        _manager = candidate
    return _manager


def _identity(pid):
    return manager().process_identity(pid)


def _alive(identity):
    return manager().is_alive(identity) if identity is not None else False


def _safe_code(error):
    code = getattr(error, 'code', None) or str(error)
    return code if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', code) else 'COORDINATOR_OPERATION_FAILED'


def _decimal(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise CoordinatorError('FINITE_BUDGET_REQUIRED')
    if not re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,8})?', str(value)):
        raise CoordinatorError('FINITE_BUDGET_REQUIRED')
    try:
        number = Decimal(value)
        if not number.is_finite() or number <= 0:
            raise InvalidOperation
        return number
    except (InvalidOperation, ValueError):
        raise CoordinatorError('FINITE_BUDGET_REQUIRED') from None


def validate_approval(value, plan, *, now=None):
    """A local private operator record, not a signature or platform billing cap.

    All execution time, including retry attempts, shares one wall-time ceiling.
    The fixed known hourly rate must fit inside the explicitly approved cost.
    No API deployment or account billing modification is performed here.
    """
    keys = {'schema', 'approved', 'planSHA256', 'imageDigest', 'validUntil',
            'maxWallSeconds', 'maxRetries', 'maxCostAmount', 'currency', 'gpuHourlyRate'}
    if not isinstance(value, dict) or set(value) != keys or value.get('schema') != AUTH_SCHEMA or value.get('approved') is not True:
        raise CoordinatorError('EXPLICIT_GPU_APPROVAL_REQUIRED')
    if value['planSHA256'] != canonical_sha256(plan):
        raise CoordinatorError('APPROVAL_PLAN_MISMATCH')
    digest = plan.get('renderProfile', {}).get('imageDigest')
    if (not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest)
            or value['imageDigest'] != digest):
        raise CoordinatorError('APPROVAL_IMAGE_MISMATCH')
    if (type(value['maxWallSeconds']) is not int or not 1 <= value['maxWallSeconds'] <= 86400
            or type(value['maxRetries']) is not int or not 0 <= value['maxRetries'] <= 2
            or not isinstance(value['currency'], str) or not re.fullmatch(r'[A-Z]{3}', value['currency'])):
        raise CoordinatorError('BOUNDED_APPROVAL_REQUIRED')
    try:
        expiry = datetime.fromisoformat(value['validUntil'])
        if expiry.tzinfo is None or expiry.utcoffset() is None:
            raise ValueError
        current = datetime.now(timezone.utc) if now is None else now
        if expiry <= current:
            raise CoordinatorError('GPU_APPROVAL_EXPIRED')
    except (ValueError, TypeError):
        raise CoordinatorError('GPU_APPROVAL_EXPIRY_INVALID') from None
    cost, rate = _decimal(value['maxCostAmount']), _decimal(value['gpuHourlyRate'])
    if Decimal(value['maxWallSeconds']) * rate / Decimal(3600) > cost:
        raise CoordinatorError('TIME_CEILING_EXCEEDS_APPROVED_COST')
    return dict(value)


def read_private_json(path):
    path = Path(path)
    with PrivateTree(path.parent) as directory:
        return directory.json(path.name)


def _job_id(plan):
    return 'video-v2-' + canonical_sha256(plan)[:24]


def _event(state, phase, **facts):
    event = {'at': stamp(), 'phase': phase, **facts}
    state['events'] = (state.get('events', []) + [event])[-512:]
    state.update(phase=phase, updatedAt=event['at'])


def _initial(plan):
    return {'schema': SCHEMA, 'jobId': _job_id(plan), 'planSHA256': canonical_sha256(plan),
            'state': 'QUEUED', 'phase': 'QUEUED', 'createdAt': stamp(), 'updatedAt': stamp(),
            'supervisorIdentity': None, 'rendererIdentity': None, 'startedUnix': None,
            'deadlineUnix': None, 'attempts': {}, 'retriesUsed': 0, 'completedScenes': {},
            'sceneCheckpoints': {},
            'progressFrames': 0, 'totalFrames': plan['totalFrames'], 'firstFailure': None,
            'result': None, 'events': [], 'timingsSeconds': {}, 'testOnly': False,
            'gpuRenderingVerified': False, 'externalDownloadVerified': False,
            'remotePersistenceVerified': False}


def _state(job, plan):
    state = job.json('JOB.json', optional=True)
    if state is None:
        return None
    if (not isinstance(state, dict) or state.get('schema') != SCHEMA
            or state.get('jobId') != _job_id(plan) or state.get('planSHA256') != canonical_sha256(plan)
            or state.get('state') not in {'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'INTERRUPTED'}):
        raise CoordinatorError('JOB_RECORD_INVALID')
    return state


def verify_completed_job(state, export_root, *, verifier=None):
    """A historical success is not proof that final bytes still exist."""
    if verifier is None:
        import delivery
        verifier = delivery.verify_mounted_export
    try:
        result = verifier(state['result'], export_root)
        if result.get('mountedViewReadbackVerified') is not True:
            raise ValueError
    except Exception:
        raise CoordinatorError('COMPLETED_RESULT_INTEGRITY_FAILED') from None
    return {**state, 'completionReverification': 'MOUNTED_BYTES_REHASHED',
            'externalDownloadVerified': False, 'remotePersistenceVerified': False}


def status(plan, control_root=CONTROL_ROOT):
    validate_plan(plan)
    try:
        with PrivateTree(control_root) as root, root.child(_job_id(plan)) as job:
            state = _state(job, plan)
            if state and state['state'] in {'QUEUED', 'RUNNING'} and not _alive(state['supervisorIdentity']):
                # Read-only observation. A remaining native PID still vetoes a
                # resume, and no status call ever starts or resets work.
                state = {**state, 'observedState': 'NATIVE_STILL_RUNNING' if _alive(state['rendererIdentity']) else 'INTERRUPTED'}
            return state
    except FileNotFoundError:
        return {'schema': SCHEMA, 'jobId': _job_id(plan), 'state': 'NOT_STARTED',
                'gpuRenderingVerified': False, 'externalDownloadVerified': False}


def _deadline(state, approval):
    current = time.time()
    expiry = datetime.fromisoformat(approval['validUntil']).timestamp()
    if state['startedUnix'] is None:
        state['startedUnix'] = current
        state['deadlineUnix'] = min(current + approval['maxWallSeconds'], expiry)
    if (not isinstance(state['deadlineUnix'], (int, float)) or not math.isfinite(state['deadlineUnix'])
            or current >= min(state['deadlineUnix'], expiry)):
        raise CoordinatorError('APPROVED_JOB_DEADLINE_EXCEEDED')
    return max(0.0, min(state['deadlineUnix'], expiry) - current)


@contextmanager
def deadline_guard(seconds):
    """Hard local wall ceiling across admission, capture, compose and export.

    This stops local work; it cannot stop an externally billed GPU workload.
    The supervisor is a dedicated main-thread process, never a web service.
    """
    if not math.isfinite(seconds) or seconds <= 0:
        raise CoordinatorError('APPROVED_JOB_DEADLINE_EXCEEDED')
    previous = signal.getsignal(signal.SIGALRM)
    timer = signal.getitimer(signal.ITIMER_REAL)
    if timer[0] > 0:
        raise CoordinatorError('EXISTING_PROCESS_TIMER_CONFLICT')
    def expired(_number, _frame):
        raise CoordinatorError('APPROVED_JOB_DEADLINE_EXCEEDED')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def run_job(plan, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT, approval,
            resume=False, _test_components=None, _wait_start_lock=False):
    """Serial production path; injected CPU seams are explicitly TEST_ONLY.

    A killed coordinator is never auto-restarted. An explicit resume rehashes
    completed segments and retries only incomplete scenes within the same cap.
    """
    validate_plan(plan, require_renderable=True)
    validate_approval(approval, plan)
    test_only = _test_components is not None
    if test_only:
        components = _test_components
    else:
        import render_adapter
        import compose
        import delivery
        components = {'render': render_adapter.render_segment,
                      'verify': compose.verify_segment, 'compose': compose.compose_segments,
                      'export': delivery.export_video, 'lease': render_adapter.common_gpu_lease,
                      'prepare': render_adapter.prepare_job,
                      'verify_completed': delivery.verify_mounted_export,
                      'checkpoint': delivery.export_scene_checkpoint,
                      'verify_checkpoint': delivery.verify_scene_checkpoint}
    with PrivateTree(control_root, create=True) as root:
        with root.child('cache', create=True) as cache_directory:
            cache_root = cache_directory.path
        with root.child(_job_id(plan), create=True) as job, job.lock(wait_seconds=5 if _wait_start_lock else 0):
            state = _state(job, plan)
            if state is None:
                state = _initial(plan)
                job.write_json('PLAN.json', plan)
            elif state['state'] == 'COMPLETED':
                verifier = components.get('verify_completed')
                if test_only and verifier is None:
                    raise CoordinatorError('TEST_COMPLETED_VERIFIER_REQUIRED')
                return verify_completed_job(state, export_root, verifier=verifier)
            elif _alive(state.get('supervisorIdentity')) and state['supervisorIdentity']['pid'] != os.getpid():
                raise CoordinatorError('JOB_ALREADY_RUNNING')
            elif _alive(state.get('rendererIdentity')):
                raise CoordinatorError('ORPHAN_NATIVE_RENDERER_STILL_RUNNING')
            elif not resume and state['state'] != 'QUEUED':
                raise CoordinatorError('EXPLICIT_RESUME_REQUIRED')
            if state['testOnly'] != test_only and state['state'] != 'QUEUED':
                raise CoordinatorError('TEST_PRODUCTION_JOB_MIX_FORBIDDEN')
            state.update(state='RUNNING', supervisorIdentity=_identity(os.getpid()),
                         rendererIdentity=None, testOnly=test_only)
            _event(state, 'ADMISSION_PENDING')
            job.write_json('JOB.json', state, replace=True)
            cache = SceneCache(cache_root)
            try:
                _deadline(state, approval)
                job.write_json('JOB.json', state, replace=True)
                started = time.monotonic()
                with deadline_guard(_deadline(state, approval)), components['lease']():
                    if components.get('prepare'):
                        _event(state, 'CPU_INPUT_PREPARATION')
                        job.write_json('JOB.json', state, replace=True)
                        prepare_started = time.monotonic()
                        components['prepare'](plan, job.path, approval=approval)
                        state['timingsSeconds']['cpuInputPreparation'] = round(time.monotonic() - prepare_started, 6)
                    completed = []
                    for index, scene in enumerate(plan['scenes']):
                        _deadline(state, approval)
                        key = __import__('cache').scene_cache_key(plan, scene,
                            plan['scenes'][index - 1] if index else None,
                            plan['scenes'][index + 1] if index + 1 < len(plan['scenes']) else None)
                        segment = None
                        try:
                            segment = cache.lookup(key)
                        except (CacheError, OSError, ValueError, KeyError, TypeError):
                            _event(state, 'CACHE_REJECTED', sceneId=scene['sceneId'])
                        if segment is not None and segment.get('testOnly') is not test_only:
                            raise CoordinatorError('TEST_CACHE_REJECTED_IN_PRODUCTION')
                        while segment is None:
                            attempts = state['attempts'].get(key, 0)
                            if attempts:
                                if state['retriesUsed'] >= approval['maxRetries']:
                                    raise CoordinatorError('APPROVED_RETRY_LIMIT_REACHED')
                                state['retriesUsed'] += 1
                            state['attempts'][key] = attempts + 1
                            attempt = cache.begin(key)
                            _event(state, 'RENDER', sceneId=scene['sceneId'], attempt=attempts + 1)
                            job.write_json('JOB.json', state, replace=True)
                            def progress(event):
                                if not isinstance(event, dict):
                                    return
                                identity = event.get('rendererIdentity')
                                if identity is not None:
                                    # Reuse PID+boot ID+start time validation;
                                    # an arbitrary PID is never a live identity.
                                    if not manager().job_store._identity(identity):
                                        raise CoordinatorError('RENDERER_IDENTITY_INVALID')
                                    state['rendererIdentity'] = identity
                                frame_count = event.get('completedFrames')
                                if type(frame_count) is int and 0 <= frame_count <= scene['endFrame'] - scene['startFrame']:
                                    state['progressFrames'] = scene['startFrame'] + frame_count
                                job.write_json('JOB.json', state, replace=True)
                            try:
                                segment = components['render'](plan, scene, attempt,
                                    approval={**approval, 'remainingWallSeconds': _deadline(state, approval)}, progress=progress)
                                verified = components['verify'](segment['path'], scene, plan)
                                segment = {**segment, **verified, 'testOnly': test_only}
                                segment = cache.complete(key, attempt, segment)
                                state['rendererIdentity'] = None
                            except Exception as error:
                                code = _safe_code(error)
                                if state['firstFailure'] is None:
                                    state['firstFailure'] = {'at': stamp(), 'sceneId': scene['sceneId'], 'code': code}
                                _event(state, 'SCENE_FAILED', sceneId=scene['sceneId'], code=code)
                                job.write_json('JOB.json', state, replace=True)
                                if state['retriesUsed'] >= approval['maxRetries']:
                                    raise
                                segment = None
                        completed.append(segment)
                        if components.get('checkpoint'):
                            # A shared copy is a recoverable byte checkpoint,
                            # not a trusted private ledger or a Dropbox sync ACK.
                            checkpoint = state.setdefault('sceneCheckpoints', {}).get(scene['sceneId'])
                            if checkpoint is not None and components.get('verify_checkpoint'):
                                try:
                                    components['verify_checkpoint'](checkpoint, export_root)
                                except Exception:
                                    checkpoint = None
                                    _event(state, 'SCENE_CHECKPOINT_REJECTED', sceneId=scene['sceneId'])
                            if checkpoint is None:
                                _event(state, 'SCENE_CHECKPOINT_EXPORT', sceneId=scene['sceneId'])
                                job.write_json('JOB.json', state, replace=True)
                                checkpoint = components['checkpoint'](plan, scene, segment, export_root,
                                                                      private_base=job.path)
                                if checkpoint.get('mountedViewReadbackVerified') is not True:
                                    raise CoordinatorError('SCENE_CHECKPOINT_MOUNTED_READBACK_FAILED')
                                state['sceneCheckpoints'][scene['sceneId']] = checkpoint
                        state['completedScenes'][scene['sceneId']] = {'cacheKey': key, 'sha256': segment['sha256']}
                        state['progressFrames'] = scene['endFrame']
                        _event(state, 'SCENE_COMPLETE', sceneId=scene['sceneId'], cacheHit=segment.get('cacheHit', False))
                        job.write_json('JOB.json', state, replace=True)
                    state['timingsSeconds']['sceneRenderingAndVerification'] = round(time.monotonic() - started, 6)
                    _deadline(state, approval)
                    _event(state, 'COMPOSE')
                    job.write_json('JOB.json', state, replace=True)
                    composition = job.path / ('composition-' + os.urandom(12).hex())
                    started = time.monotonic()
                    composed = components['compose'](plan, completed, composition)
                    state['timingsSeconds']['composition'] = round(time.monotonic() - started, 6)
                    _deadline(state, approval)
                    _event(state, 'EXPORT')
                    job.write_json('JOB.json', state, replace=True)
                    started = time.monotonic()
                    result = components['export'](plan, composed, export_root)
                    state['timingsSeconds']['mountedExport'] = round(time.monotonic() - started, 6)
                    _deadline(state, approval)
                if result.get('mountedViewReadbackVerified') is not True:
                    raise CoordinatorError('MOUNTED_EXPORT_VERIFICATION_FAILED')
                # Remote sync and external downloads require separate real proof.
                state.update(state='COMPLETED', result=result, rendererIdentity=None,
                             gpuRenderingVerified=not test_only)
                _event(state, 'COMPLETED')
                job.write_json('JOB.json', state, replace=True)
                return state
            except BaseException as error:
                state['state'] = 'INTERRUPTED' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'FAILED'
                code = _safe_code(error)
                if state['firstFailure'] is None:
                    state['firstFailure'] = {'at': stamp(), 'phase': state['phase'], 'code': code}
                _event(state, state['state'], code=code)
                job.write_json('JOB.json', state, replace=True)
                raise
            finally:
                cache.close()


def start_job(plan, approval_path, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT, resume=False):
    """Reuse original process identity/setsid behavior with a new ledger only.

    No shell, arbitrary executable, HTTP endpoint or automatic restart. The
    stored plan is immutable and the worker checks the authorization again.
    """
    validate_plan(plan, require_renderable=True)
    approval = validate_approval(read_private_json(approval_path), plan)
    with PrivateTree(control_root, create=True) as root, root.child(_job_id(plan), create=True) as job, job.lock():
        state = _state(job, plan)
        if state and state['state'] == 'COMPLETED':
            return verify_completed_job(state, export_root)
        if state and (_alive(state.get('supervisorIdentity')) or _alive(state.get('rendererIdentity'))):
            return state
        if state is not None and not resume:
            raise CoordinatorError('EXPLICIT_RESUME_REQUIRED')
        if state is None:
            state = _initial(plan)
            job.write_json('PLAN.json', plan)
        _deadline(state, approval)
        state.update(state='QUEUED', rendererIdentity=None)
        _event(state, 'DETACH_PENDING')
        job.write_json('JOB.json', state, replace=True)
        # Only the fixed in-image worker can be detached. Console descriptors
        # are disconnected, matching the existing manager's terminal contract.
        worker_log = 'worker-' + os.urandom(12).hex() + '.log'
        descriptor = os.open(worker_log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=job.fd)
        try:
            child = subprocess.Popen([sys.executable, '-B', str(HERE / 'orchestrator.py'), 'worker',
                '--plan', str(job.path / 'PLAN.json'), '--approval', str(Path(approval_path).absolute()),
                '--control-root', str(root.path), '--export-root', str(Path(export_root).absolute()),
                *(('--resume',) if resume else ())], stdin=subprocess.DEVNULL,
                stdout=descriptor, stderr=descriptor, start_new_session=True, close_fds=True)
        finally:
            os.close(descriptor)
        state['workerLog'] = worker_log
        try:
            state['supervisorIdentity'] = _identity(child.pid)
        except (FileNotFoundError, ProcessLookupError):
            raise CoordinatorError('DETACHED_WORKER_START_FAILED') from None
        _event(state, 'DETACHED')
        job.write_json('JOB.json', state, replace=True)
        return state


def main(argv=None):
    class SafeParser(argparse.ArgumentParser):
        def error(self, _message):
            raise CoordinatorError('INVALID_COORDINATOR_ARGUMENTS')
    parser = SafeParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('status', 'run', 'start', 'worker'):
        child = sub.add_parser(action)
        child.add_argument('--plan', type=Path, required=True)
        child.add_argument('--control-root', type=Path, default=CONTROL_ROOT)
        if action != 'status':
            child.add_argument('--approval', type=Path, required=True)
            child.add_argument('--export-root', type=Path, default=EXPORT_ROOT)
            child.add_argument('--resume', action='store_true')
    try:
        args = parser.parse_args(argv)
        plan = read_private_json(args.plan)
        if args.action == 'status':
            result = status(plan, args.control_root)
        elif args.action == 'start':
            result = start_job(plan, args.approval, control_root=args.control_root,
                               export_root=args.export_root, resume=args.resume)
        else:
            # SIGHUP cannot kill a detached production worker. TERM/INT retain
            # an interrupted ledger; native wrapper always stops its child.
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
            def interrupted(_number, _frame):
                raise KeyboardInterrupt
            signal.signal(signal.SIGTERM, interrupted)
            result = run_job(plan, control_root=args.control_root, export_root=args.export_root,
                             approval=read_private_json(args.approval), resume=args.resume,
                             _wait_start_lock=args.action == 'worker')
        print(json.dumps(result, sort_keys=True))
        return 0
    except BaseException as error:
        if isinstance(error, SystemExit):
            return error.code
        print(json.dumps({'schema': 'WORLD_ENGINE_UNIVERSAL_JOB_ERROR_V2', 'state': 'BLOCKED',
                          'code': _safe_code(error), 'gpuRenderingVerified': False,
                          'renderAllowed': False}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
