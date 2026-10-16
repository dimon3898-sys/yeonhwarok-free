"""Detached Studio post-production over the immutable GPU coordinators.

Original GPU admission, lease, scene cache, renderers and approval accounting
remain authoritative. This module never provisions/stops workloads, resets a
claim, silently resumes work, or asserts an external Dropbox synchronization.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import http.client
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
RECOVERY = (Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery')
            if str(HERE).startswith('/opt/') else HERE.parent)
CONTROL_ROOT = Path('/var/lib/world-engine-private/engine/production-studio-v1')
EXPORT_ROOT = Path('/world-storage')
PROFILES = {'V4_ARCHIVAL_80S': 'verified-front-data-v4-recovery', 'UNIVERSAL_V3': 'universal-production-v3'}
JOB = re.compile(r'studio-[a-f0-9]{32}\Z')
DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')
REQUEST = re.compile(r'[A-Za-z0-9_-]{8,128}\Z')
SCHEMA = 'WORLD_ENGINE_STUDIO_JOB_V1'
_CACHE = _MANAGER = None


def _safe(error):
    code = getattr(error, 'code', None) or str(error).split(':', 1)[0]
    return code if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', code) else 'STUDIO_OPERATION_FAILED'


def _load(name, path, expected=None):
    path = Path(path)
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise RuntimeError('STUDIO_FROZEN_SOURCE_SYMLINK_FORBIDDEN')
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('STUDIO_FROZEN_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def _cache():
    global _CACHE
    if _CACHE is None:
        _CACHE = _load('_studio_frozen_cache', RECOVERY / 'universal-auto-video-v2/cache.py',
            '4ad9dc03c11ccb39df027cb39dc31715525f2eb7be6da76bedbccfaefd5984fd')
    return _CACHE


def _manager():
    global _MANAGER
    if _MANAGER is None:
        path = Path('/opt/world-engine-detached-render/job_manager.py')
        if not path.is_file():
            path = RECOVERY / 'gcube-detached-render-v1/job_manager.py'
        original = list(sys.path)
        try:
            sys.path.insert(0, str(path.parent))
            _MANAGER = _load('_studio_frozen_process_identity', path,
                '6398967204168e9284a6cc1b5b7f7e2951b996fb7cf5cb3d5f0a785b26047d99')
        finally:
            sys.path[:] = original
    return _MANAGER


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _base(plan, profile_id, image_digest):
    if profile_id not in PROFILES:
        raise RuntimeError('STUDIO_UNSUPPORTED_PRODUCTION_PROFILE')
    if not isinstance(image_digest, str) or not DIGEST.fullmatch(image_digest):
        raise RuntimeError('STUDIO_IMMUTABLE_IMAGE_REQUIRED')
    if (not isinstance(plan, dict) or not isinstance(plan.get('durationSeconds'), (int, float))
            or plan.get('durationSeconds') not in {80, 120, 180, 300, 600} or plan.get('fps') != 30
            or plan.get('resolution') != {'width': 1080, 'height': 1920} or plan.get('aspectRatio') != '9:16'):
        raise RuntimeError('STUDIO_UNSUPPORTED_VIDEO_FORMAT')
    if profile_id == 'V4_ARCHIVAL_80S' and plan['durationSeconds'] != 80:
        raise RuntimeError('STUDIO_ARCHIVAL_PROFILE_EXACT_80_SECONDS_REQUIRED')
    if plan.get('audioSettings') != {'enabled': False, 'mode': 'SILENT'}:
        raise RuntimeError('STUDIO_GPU_PLAN_MUST_REMAIN_SILENT')


_VALIDATOR = r'''
import hashlib,importlib.util,json,pathlib,re,sys
root=pathlib.Path(sys.argv[1]);action=sys.argv[2];profile=sys.argv[3];value=json.load(sys.stdin)
def load(name,path,expected):
 if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('STUDIO_FROZEN_VALIDATOR_CHANGED')
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
try:
 plan=value['plan']
 if profile=='V4_ARCHIVAL_80S':
  m=load('_studio_child_v4_binding',root/'verified-front-data-v4-recovery/scene_binding.py','15e61204681cd90a3458b629b2ce3f64aee84807312eb6d20974435b16289829')
  if action=='bind':
   refs=m.source_binding();expected=m.derive_execution_plan(m.parent_plan(),image_digest=plan.get('renderProfile',{}).get('imageDigest'),front_profile_sha256=refs['profileSha256'],front_manifest_sha256=refs['sourceManifestSha256'])
   if plan!=expected:raise ValueError('STUDIO_V4_SOURCE_PLAN_CHANGED')
   plan=m.derive_execution_plan(m.parent_plan(),image_digest=value['imageDigest'],front_profile_sha256=refs['profileSha256'],front_manifest_sha256=refs['sourceManifestSha256'])
  else:m.validate_execution_plan(plan)
 else:
  m=load('_studio_child_v3_planner',root/'universal-production-v3/scene_planner.py','7b7bfbe132903714279f5308d32827fe80a34578fbb5a3bd7f6747e584919f62')
  m.validate_production_plan(plan,require_renderable=True)
  if action=='bind':
   plan['renderProfile']['imageDigest']=value['imageDigest'];plan['scenes']=m._work_scenes(plan,plan['splitPolicy']['maxSceneFrames']);m.validate_production_plan(plan,require_renderable=True)
 if action=='approval':
  sys.path.insert(0,str(root/'universal-auto-video-v2'))
  o=load('_studio_child_approval',root/'universal-auto-video-v2/orchestrator.py','2e1e9d76c6ecf760f69fa2204c80d91da251fa0ee2abf8ed7cf3fe2388afcca4');o.validate_approval(value['approval'],plan)
 if action=='sources':
  if profile=='V4_ARCHIVAL_80S':m.verify_sources()
  else:load('_studio_child_sources',root/'universal-production-v3/source_manifest.py','c63757663cba3c3e8efd4f9606be5a78ef8ac5e6d9c54a18c1adfab8f6e8ca42').verify_sources()
 print(json.dumps({'status':'PASS',**({'plan':plan} if action=='bind' else {})},allow_nan=False))
except Exception as e:
 code=getattr(e,'code',None) or str(e).split(':',1)[0]
 if not isinstance(code,str) or not re.fullmatch('[A-Z][A-Z0-9_]{1,95}',code):code='STUDIO_PLAN_VALIDATION_FAILED'
 print(json.dumps({'status':'BLOCKED','code':code}));sys.exit(2)
'''


def _validate_child(plan, profile_id, action='validate', **extras):
    response = subprocess.run(['/usr/bin/python3', '-B', '-c', _VALIDATOR, str(RECOVERY), action, profile_id],
        input=_cache().canonical_bytes({'plan': plan, **extras}), stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=90, check=False)
    if len(response.stdout) > 8 * 1024**2:
        raise RuntimeError('STUDIO_VALIDATION_RESPONSE_TOO_LARGE')
    try:
        result = json.loads(response.stdout)
    except (ValueError, TypeError):
        raise RuntimeError('STUDIO_PLAN_VALIDATION_FAILED') from None
    if response.returncode or result.get('status') != 'PASS':
        raise RuntimeError(_safe(RuntimeError(result.get('code', 'STUDIO_PLAN_VALIDATION_FAILED'))))
    return result


def bind_render_image(plan, profile_id, image_digest):
    _base(plan, profile_id, image_digest)
    return _validate_child(plan, profile_id, 'bind', imageDigest=image_digest)['plan']


def default_plan(profile_id):
    if profile_id not in PROFILES:raise RuntimeError('STUDIO_UNSUPPORTED_PRODUCTION_PROFILE')
    original = json.loads((RECOVERY / 'verified-front-data-v4-recovery/PARENT_PLAN_80S.json').read_bytes())
    if profile_id == 'UNIVERSAL_V3':return original
    module = _load('_studio_default_v4_binding', RECOVERY / 'verified-front-data-v4-recovery/scene_binding.py',
        '15e61204681cd90a3458b629b2ce3f64aee84807312eb6d20974435b16289829')
    refs = module.source_binding()
    return module.derive_execution_plan(original, image_digest=original['renderProfile']['imageDigest'],
        front_profile_sha256=refs['profileSha256'], front_manifest_sha256=refs['sourceManifestSha256'])


def validate_render_plan(plan, profile_id, image_digest=None):
    image_digest = image_digest or os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST') or plan.get('renderProfile', {}).get('imageDigest')
    _base(plan, profile_id, image_digest)
    if plan.get('renderProfile', {}).get('imageDigest') != image_digest:
        raise RuntimeError('STUDIO_PLAN_IMAGE_BINDING_MISMATCH')
    _validate_child(plan, profile_id)
    return plan


def _execution_image():
    digest = os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST')
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise RuntimeError('STUDIO_CONFIGURED_IMMUTABLE_IMAGE_REQUIRED')
    if os.geteuid() != 1000 or os.getegid() != 1000:
        raise RuntimeError('STUDIO_ENGINE_UID_GID_1000_REQUIRED')
    return digest


def _health():
    connection = http.client.HTTPConnection('127.0.0.1', 8000, timeout=3)
    try:
        connection.request('GET', '/healthz')
        response = connection.getresponse(); data = response.read(16385)
        if response.status != 200 or len(data) > 16384:
            raise RuntimeError('STUDIO_EXISTING_GPU_HEALTH_UNAVAILABLE')
        report = json.loads(data)
        if (report.get('gpuRenderingVerified') is not True or report.get('testOnly') is not False
                or report.get('renderMode') != 'gpu-required'
                or report.get('model') not in {'RTX 4080 SUPER', 'RTX 4090', 'RTX 5090'}):
            raise RuntimeError('STUDIO_PHYSICAL_GPU_HEALTH_REQUIRED')
        return {'model': report['model'], 'physicalMemoryMiB': report.get('physicalMemoryMiB'),
                'verificationScope': 'STARTUP_HEALTH_NATIVE_ADMISSION_RECHECK_REQUIRED'}
    finally:
        connection.close()


def preflight(plan, profile_id, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
    checks = []
    def check(name, operation):
        try:
            facts = operation()
            checks.append({'name': name, 'status': 'PASS', **({'facts': facts} if isinstance(facts, dict) else {})})
        except Exception as error:
            checks.append({'name': name, 'status': 'BLOCKED', 'code': _safe(error)})
    def scene():
        validate_render_plan(plan, profile_id, _execution_image())
        return {'frames': plan['totalFrames'], 'scenes': len(plan['scenes'])}
    check('INPUT_AND_SCENE', scene)
    check('IMMUTABLE_SOURCE_CLOSURE', lambda: _validate_child(plan, profile_id, 'sources'))
    def private():
        with _cache().PrivateTree(Path(control_root)):
            pass
        return {'localPosixOnly': True}
    check('PRIVATE_STORAGE', private)
    def claim():
        with _cache().PrivateTree(Path(control_root)) as root:
            if _active_blocked(root, export_root=export_root):
                raise RuntimeError('STUDIO_ANOTHER_JOB_IS_ACTIVE')
        return {'studioClaimAvailable': True, 'crossProfileGpuLockEnforcedByOriginalCoordinator': True}
    check('WORK_CLAIM', claim)
    def storage():
        import pwd
        session = _cache().storage.StorageSession.create(pwd.getpwuid(1000), base=Path(control_root), export_root=Path(export_root))
        session.preflight()
        return {'mountedReadWriteVerified': True, 'externalDownloadVerified': False}
    check('DROPBOX_MOUNT', storage)
    def space():
        minimum = max(2 * 1024**3, math.ceil(plan['durationSeconds'] * 30_000_000 / 8) * 4)
        info = os.statvfs(control_root); available = info.f_bavail * info.f_frsize
        if available < minimum:
            raise RuntimeError('STUDIO_PRIVATE_DISK_BUDGET_INSUFFICIENT')
        return {'availableBytes': available, 'minimumEstimatedBytes': minimum, 'estimateOnly': True}
    check('DISK_BUDGET', space); check('CURRENT_GPU_HEALTH', _health)
    allowed = all(row['status'] == 'PASS' for row in checks)
    return {'status': 'PASS' if allowed else 'BLOCKED', 'renderAllowed': allowed, 'checks': checks,
            'gpuRenderingVerified': False, 'nativeAdmissionBeforeEachSegment': True, 'externalDownloadVerified': False}


def _profile_root(profile_id, control_root):
    if profile_id not in PROFILES:
        raise RuntimeError('STUDIO_UNSUPPORTED_PRODUCTION_PROFILE')
    name = 'render-v4' if profile_id == 'V4_ARCHIVAL_80S' else 'render-v3'
    with _cache().PrivateTree(Path(control_root)) as root, root.child(name, create=True) as child:
        return child.path


def _call_original(action, plan, profile_id, plan_path, approval_path=None, *, control_root=CONTROL_ROOT,
                   export_root=EXPORT_ROOT, resume=False):
    if action not in {'start', 'status'} or profile_id not in PROFILES or type(resume) is not bool:
        raise RuntimeError('STUDIO_FIXED_ORIGINAL_ACTION_REQUIRED')
    command = ['/usr/bin/python3', '-B', str(RECOVERY / PROFILES[profile_id] / 'orchestrator.py'), action,
               '--plan', str(plan_path), '--control-root', str(_profile_root(profile_id, control_root))]
    if action == 'start':
        command += ['--approval', str(approval_path), '--export-root', str(export_root), *(('--resume',) if resume else ())]
    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=90, check=False)
    if len(result.stdout) > 4 * 1024**2:
        raise RuntimeError('STUDIO_ORIGINAL_RESPONSE_TOO_LARGE')
    try:
        value = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise RuntimeError('STUDIO_ORIGINAL_COORDINATOR_FAILED') from None
    if result.returncode or value.get('state') == 'BLOCKED':
        raise RuntimeError(_safe(RuntimeError(value.get('code', 'STUDIO_ORIGINAL_COORDINATOR_FAILED'))))
    return value


def _saved_plan(plan, profile_id, control_root):
    identity = _cache().canonical_sha256({'profileId': profile_id, 'plan': plan})
    with _cache().PrivateTree(Path(control_root), create=True) as root, root.child('inputs', create=True) as inputs:
        with inputs.child(identity, create=True) as target, target.lock():
            old = target.json('PLAN.json', optional=True)
            if old is None:target.write_json('PLAN.json', plan)
            elif old != plan:raise RuntimeError('STUDIO_IMMUTABLE_PLAN_COLLISION')
            return target.path / 'PLAN.json'


def start(plan, profile_id, approval_path, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT, resume=False):
    validate_render_plan(plan, profile_id, _execution_image())
    return _call_original('start', plan, profile_id, _saved_plan(plan, profile_id, control_root), approval_path,
        control_root=control_root, export_root=export_root, resume=resume)


def status(plan, profile_id, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
    validate_render_plan(plan, profile_id, os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'))
    return _call_original('status', plan, profile_id, _saved_plan(plan, profile_id, control_root),
        control_root=control_root, export_root=export_root)


def _normalized_audio(settings, plan):
    from studio_audio import normalize_sfx
    return normalize_sfx(settings, plan)


def _job_id(plan, profile_id, audio, request_id):
    if not isinstance(request_id, str) or not REQUEST.fullmatch(request_id):
        raise RuntimeError('STUDIO_STABLE_REQUEST_ID_REQUIRED')
    return 'studio-' + _cache().canonical_sha256({'plan': plan, 'profile': profile_id, 'audio': audio, 'requestId': request_id})[:32]


def _public(state):
    names = ('jobId', 'state', 'phase', 'profileId', 'totalScenes', 'completedScenes', 'processedFrames',
             'totalFrames', 'createdAt', 'updatedAt', 'errorCode', 'result', 'gpuRenderingVerified',
             'externalDownloadVerified', 'timingsSeconds', 'reuseSilentJobId', 'recoveryOfJobId')
    result = {name: state.get(name) for name in names}
    result['elapsedSeconds'] = max(0, round((state.get('finishedUnix') or time.time()) - state['createdUnix'], 3))
    return result


def _read_job(root, job_id):
    if not isinstance(job_id, str) or not JOB.fullmatch(job_id):
        raise RuntimeError('STUDIO_JOB_ID_INVALID')
    with root.child(job_id) as job:
        state = job.json('STATE.json')
        if state.get('schema') != SCHEMA or state.get('jobId') != job_id:
            raise RuntimeError('STUDIO_JOB_RECORD_INVALID')
        return state


def _active_blocked(root, *, export_root):
    active = root.json('ACTIVE.json', optional=True)
    if active is None:return False
    state = _read_job(root, active.get('jobId'))
    if state['state'] == 'COMPLETED':return False
    if _manager().is_alive(state.get('supervisorIdentity')):return True
    with root.child(state['jobId']) as job:plan = job.json('PLAN.json')
    current = status(plan, state['profileId'], control_root=root.path, export_root=export_root)
    return current.get('state') in {'QUEUED', 'RUNNING'} and current.get('observedState') != 'INTERRUPTED'


def _start_supervisor(plan, profile_id, approval, audio, request_id, *, control_root, export_root,
                      reuse_silent_job_id=None, silent_result=None, recovery_of_job_id=None, resume_render=False):
    job_id = _job_id(plan, profile_id, audio, request_id)
    with _cache().PrivateTree(Path(control_root), create=True) as root, root.lock('START.lock'):
        with root.child(job_id, create=True) as job, job.lock():
            previous = job.json('STATE.json', optional=True)
            if previous is not None:return _public(previous)
            if _active_blocked(root, export_root=export_root):raise RuntimeError('STUDIO_ANOTHER_JOB_IS_ACTIVE')
            now = time.time()
            state = {'schema': SCHEMA, 'jobId': job_id, 'profileId': profile_id, 'state': 'QUEUED', 'phase': 'QUEUED',
                     'createdUnix': now, 'createdAt': _stamp(), 'updatedAt': _stamp(), 'finishedUnix': None,
                     'supervisorIdentity': None, 'totalScenes': len(plan['scenes']), 'completedScenes': 0,
                     'processedFrames': 0, 'totalFrames': plan['totalFrames'], 'errorCode': None, 'result': None,
                     'gpuRenderingVerified': False, 'externalDownloadVerified': False, 'timingsSeconds': {},
                     'reuseSilentJobId': reuse_silent_job_id, 'silentResult': silent_result,
                     'recoveryOfJobId': recovery_of_job_id, 'resumeRender': resume_render}
            job.write_json('PLAN.json', plan); job.write_json('AUDIO.json', audio)
            if approval is not None:job.write_json('APPROVAL.json', approval)
            job.write_json('STATE.json', state)
            descriptor = os.open('supervisor.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=job.fd)
            try:
                worker = subprocess.Popen(['/usr/bin/python3', '-B', str(HERE / 'studio_runtime.py'), 'worker',
                    '--job-id', job_id, '--control-root', str(root.path), '--export-root', str(Path(export_root).absolute())],
                    stdin=subprocess.DEVNULL, stdout=descriptor, stderr=descriptor, start_new_session=True, close_fds=True)
            finally:os.close(descriptor)
            try:state['supervisorIdentity'] = _manager().process_identity(worker.pid)
            except (FileNotFoundError, ProcessLookupError):
                state.update(state='FAILED', phase='FAILED', errorCode='STUDIO_SUPERVISOR_START_FAILED', finishedUnix=time.time())
            job.write_json('STATE.json', state, replace=True)
            root.write_json('ACTIVE.json', {'jobId': job_id}, replace=True)
            return _public(state)


def _approval(path, plan, profile_id):
    location = Path(path).absolute()
    with _cache().PrivateTree(location.parent) as directory:value = directory.json(location.name)
    _validate_child(plan, profile_id, 'approval', approval=value)
    return value


def start_studio_job(plan, profile_id, approval_path, audio_spec, request_id, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
    validate_render_plan(plan, profile_id, _execution_image())
    return _start_supervisor(plan, profile_id, _approval(approval_path, plan, profile_id),
        _normalized_audio(audio_spec, plan), request_id, control_root=control_root, export_root=export_root)


def start_studio_revision(parent_job_id, audio_spec, request_id, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
    with _cache().PrivateTree(Path(control_root)) as root:
        parent = _read_job(root, parent_job_id)
        if parent['state'] != 'COMPLETED' or parent.get('gpuRenderingVerified') is not True or not parent.get('silentResult'):
            raise RuntimeError('STUDIO_COMPLETED_HARDWARE_PARENT_REQUIRED')
        with root.child(parent_job_id) as job:plan = job.json('PLAN.json')
    import studio_delivery
    studio_delivery.verify_export(parent['result'], export_root)
    return _start_supervisor(plan, parent['profileId'], None, _normalized_audio(audio_spec, plan), request_id,
        control_root=control_root, export_root=export_root, reuse_silent_job_id=parent_job_id, silent_result=parent['silentResult'])


def start_studio_recovery(parent_job_id, approval_path, request_id, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
    """Explicit owner action only; the original deadline/retry ledger is retained."""
    with _cache().PrivateTree(Path(control_root)) as root:
        parent = _read_job(root, parent_job_id)
        if parent['state'] not in {'FAILED', 'INTERRUPTED', 'QUEUED', 'RUNNING'}:
            raise RuntimeError('STUDIO_RECOVERY_REQUIRES_FAILED_OR_INTERRUPTED_JOB')
        if _manager().is_alive(parent.get('supervisorIdentity')):
            raise RuntimeError('STUDIO_RECOVERY_PARENT_STILL_RUNNING')
        with root.child(parent_job_id) as job:
            plan, audio = job.json('PLAN.json'), job.json('AUDIO.json')
            original_approval = job.json('APPROVAL.json', optional=True)
    profile_id = parent['profileId']
    approval = None if parent.get('silentResult') else _approval(approval_path, plan, profile_id)
    if approval is not None and approval != original_approval:
        raise RuntimeError('STUDIO_RECOVERY_ORIGINAL_APPROVAL_CAPS_REQUIRED')
    return _start_supervisor(plan, profile_id, approval, audio, request_id, control_root=control_root,
        export_root=export_root, silent_result=parent.get('silentResult'), reuse_silent_job_id=parent_job_id if parent.get('silentResult') else None,
        recovery_of_job_id=parent_job_id, resume_render=not bool(parent.get('silentResult')))


def studio_status(job_id, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
    with _cache().PrivateTree(Path(control_root)) as root:
        state = _read_job(root, job_id)
        if state['state'] in {'QUEUED', 'RUNNING'} and not _manager().is_alive(state.get('supervisorIdentity')):
            state = {**state, 'state': 'INTERRUPTED', 'phase': 'EXPLICIT_RECOVERY_REQUIRED',
                     'errorCode': 'STUDIO_SUPERVISOR_INTERRUPTED_NO_AUTO_RESTART'}
        if state['state'] == 'COMPLETED':
            import studio_delivery
            studio_delivery.verify_export(state['result'], export_root)
        return _public(state)


@contextmanager
def _deadline(seconds):
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise RuntimeError('STUDIO_APPROVED_DEADLINE_EXCEEDED')
    if signal.getitimer(signal.ITIMER_REAL)[0]:raise RuntimeError('STUDIO_EXISTING_PROCESS_TIMER_CONFLICT')
    previous = signal.getsignal(signal.SIGALRM)
    def expired(_number, _frame):raise RuntimeError('STUDIO_APPROVED_DEADLINE_EXCEEDED')
    signal.signal(signal.SIGALRM, expired); signal.setitimer(signal.ITIMER_REAL, seconds)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, previous)


def finalize(plan, audio_spec, silent_result, job_directory, export_root):
    import studio_audio
    import studio_delivery
    cache = _cache()
    with cache.PrivateTree(Path(job_directory)) as job, job.child('media', create=True) as media:
        silent = media.path / 'silent-source.mp4'
        studio_delivery.copy_verified_silent(silent_result, export_root, silent)
        audio = studio_audio.render_sfx(audio_spec, plan, media.path / 'SFX.wav')
        with media.child('public', create=True) as public:
            movie = public.path / 'WORLD_ENGINE_STUDIO_VIDEO.mp4'; wav = Path(audio['file']) if audio.get('enabled') else None
            mux = studio_audio.mux_sfx(silent, wav, movie, plan)
            for candidate in (movie, wav):
                if candidate is not None:
                    descriptor = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    try:
                        info = os.fstat(descriptor)
                        if info.st_uid != os.geteuid() or info.st_nlink != 1:raise RuntimeError('STUDIO_NEW_MEDIA_OWNER_INVALID')
                        os.fchmod(descriptor, 0o600)
                    finally:os.close(descriptor)
            if audio_spec.get('exportWav') and wav is not None:
                source = os.open(wav, os.O_RDONLY | os.O_NOFOLLOW)
                output = os.open('SFX.wav', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=public.fd)
                try:
                    while True:
                        block = os.read(source, 1024 * 1024)
                        if not block:break
                        cache.storage._write_all(output, block)
                    os.fsync(output)
                finally:os.close(source); os.close(output)
                if public.hash_file('SFX.wav')['sha256'] != audio['sha256']:raise RuntimeError('STUDIO_WAV_COPY_SHA_MISMATCH')
            if mux.get('fullDecode') != 'PASS' or mux.get('videoDecodedPixelsUnchanged') is not True:
                raise RuntimeError('STUDIO_FINAL_MEDIA_VERIFICATION_FAILED')
            summary = {'schema': 'WORLD_ENGINE_STUDIO_SAFE_QA_V1', 'technicalVerification': 'PASS',
                'frames': plan['totalFrames'], 'fps': plan['fps'], 'width': plan['resolution']['width'], 'height': plan['resolution']['height'],
                'durationSeconds': plan['durationSeconds'], 'audioStreams': mux['audioStreams'], 'sfxEnabled': audio['enabled'],
                'videoDecodedPixelsUnchanged': True, 'fullDecode': 'PASS', 'visualQuality': 'USER_VIDEO_REVIEW_REQUIRED',
                'externalDownloadVerified': False, 'finalPromotion': False}
            public.write_json('QUALITY_SUMMARY.json', summary)
            rows = [public.hash_file(name) for name in sorted(os.listdir(public.path))]
            cache.storage._new_file(public.fd, 'SHA256SUMS', ''.join(row['sha256'] + '  ' + row['file'] + '\n' for row in rows).encode('ascii'), private=True)
            result = studio_delivery.export_media(public.path, export_root, media.path)
        media.write_json('AUDIO_RECEIPT.json', audio); media.write_json('MUX_RECEIPT.json', mux)
        return result


def _worker(job_id, control_root, export_root):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    def stop(_number, _frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    with _cache().PrivateTree(Path(control_root)) as root, root.child(job_id) as job, job.lock(wait_seconds=5):
        state = _read_job(root, job_id)
        if state['state'] != 'QUEUED':raise RuntimeError('STUDIO_WORKER_CLAIM_NOT_QUEUED')
        plan, audio = job.json('PLAN.json'), job.json('AUDIO.json'); approval = job.json('APPROVAL.json', optional=True)
        state.update(state='RUNNING', supervisorIdentity=_manager().process_identity(os.getpid()))
        def save(phase):
            state.update(phase=phase, updatedAt=_stamp()); job.write_json('STATE.json', state, replace=True)
        save('INPUT_VALIDATION')
        try:
            validate_render_plan(plan, state['profileId'], _execution_image())
            if approval is not None:
                _validate_child(plan, state['profileId'], 'approval', approval=approval)
                limit = min(state['createdUnix'] + approval['maxWallSeconds'], datetime.fromisoformat(approval['validUntil']).timestamp())
            else:
                if state.get('reuseSilentJobId') is None or state.get('silentResult') is None:raise RuntimeError('STUDIO_GPU_APPROVAL_REQUIRED')
                limit = state['createdUnix'] + 3600
            with _deadline(limit - time.time()):
                if state.get('silentResult') is None:
                    save('GPU_DELEGATION')
                    current = _call_original('start', plan, state['profileId'], job.path / 'PLAN.json', job.path / 'APPROVAL.json',
                        control_root=root.path, export_root=export_root, resume=state.get('resumeRender', False))
                    while True:
                        state['completedScenes'] = len(current.get('completedScenes', {})); state['processedFrames'] = current.get('progressFrames', 0)
                        save('GPU_' + str(current.get('phase', 'PENDING')))
                        if current.get('state') == 'COMPLETED':
                            if current.get('testOnly') is not False or current.get('gpuRenderingVerified') is not True:raise RuntimeError('STUDIO_REAL_GPU_COMPLETION_REQUIRED')
                            state['silentResult'] = current['result']; state['timingsSeconds']['gpuPipeline'] = max(0, time.time() - state['createdUnix']); break
                        if current.get('state') in {'FAILED', 'INTERRUPTED'} or current.get('observedState') == 'INTERRUPTED':
                            raise RuntimeError(_safe(RuntimeError((current.get('firstFailure') or {}).get('code', 'STUDIO_ORIGINAL_RENDER_FAILED'))))
                        time.sleep(3)
                        current = _call_original('status', plan, state['profileId'], job.path / 'PLAN.json', control_root=root.path, export_root=export_root)
                state['gpuRenderingVerified'] = True; state['completedScenes'] = len(plan['scenes']); state['processedFrames'] = plan['totalFrames']
                save('SFX_AND_FINAL_COMPOSITION'); started = time.monotonic()
                result = finalize(plan, audio, state['silentResult'], job.path, export_root)
                state['timingsSeconds']['sfxComposeExportVerify'] = round(time.monotonic() - started, 6)
                state.update(state='COMPLETED', result=result, finishedUnix=time.time()); save('COMPLETED'); return 0
        except BaseException as error:
            state.update(state='INTERRUPTED' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'FAILED', errorCode=_safe(error), finishedUnix=time.time())
            save(state['state']); return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('action', choices=['worker'])
    parser.add_argument('--job-id', required=True); parser.add_argument('--control-root', type=Path, default=CONTROL_ROOT)
    parser.add_argument('--export-root', type=Path, default=EXPORT_ROOT); args = parser.parse_args(argv)
    try:
        if not JOB.fullmatch(args.job_id):raise RuntimeError('STUDIO_JOB_ID_INVALID')
        return _worker(args.job_id, args.control_root, args.export_root)
    except BaseException as error:
        print(json.dumps({'schema': SCHEMA, 'state': 'BLOCKED', 'code': _safe(error), 'gpuRenderingVerified': False, 'renderAllowed': False}), flush=True); return 2


if __name__ == '__main__':raise SystemExit(main())
