"""Explicit CPU-only completion of retained, authenticated scene checkpoints.

This extension never invokes an original start/resume coordinator, GPU admission,
or renderer. A scene count is not a reusable artifact. Private NVIDIA provenance,
every byte hash, the original plan, and a new CPU-only grant must all agree.
Old claims, approvals, caches and failed jobs are read-only inputs.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time

HERE = Path(__file__).resolve().parent
RECOVERY = (Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery')
            if HERE.is_relative_to('/opt') else HERE.parent)
STUDIO = (Path('/opt/world-engine-production-studio')
          if HERE.is_relative_to('/opt') else HERE.parent / 'production-studio-mvp-v1')
HEX = re.compile(r'[a-f0-9]{64}\Z')
JOB = re.compile(r'studio-[a-f0-9]{32}\Z')
REQUEST = re.compile(r'[A-Za-z0-9_-]{8,128}\Z')
SOURCE_HASHES = {
    'cache': ('universal-auto-video-v2/cache.py', '4ad9dc03c11ccb39df027cb39dc31715525f2eb7be6da76bedbccfaefd5984fd'),
    'compose': ('universal-auto-video-v2/compose.py', 'd4478f758988923a18620a07b0dcf0e0883c99b6ef419d4bffac5999e65d5245'),
    'delivery': ('universal-auto-video-v2/delivery.py', 'b41022ec747c6cd0683dccb3cd0fa94619c5e1badff82015ad0ec29d17dcffcf'),
}
STUDIO_HASHES = {
    'studio_runtime': '79f8a58a3bf99b6edfc73f9fc7266b23ebd7b6646257f3ffeed08afd68a00f1e',
    'studio_audio': '03a9083aa71ac5acbe17806afd8dfb44e1fd155e886237aba6c00ae3552dca5d',
    'studio_delivery': '26841e62659946cc3ec58f89f75cb9c9375005ab98c3c74d67022800a09081c7',
}
_MODULES = {}


class RecoveryError(RuntimeError):
    pass


def fail(code):
    raise RecoveryError(code)


def safe_code(error):
    code = getattr(error, 'code', None) or str(error).split(':', 1)[0]
    return code if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', code) else 'CPU_RECOVERY_FAILED'


def _load(name, path, expected):
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file():
        fail('CPU_RECOVERY_SOURCE_UNAVAILABLE')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        fail('CPU_RECOVERY_SOURCE_CHANGED')
    if name in sys.modules:
        module = sys.modules[name]
        if Path(module.__file__).absolute() != path:
            fail('CPU_RECOVERY_IMPORT_CONFLICT')
        return module
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def modules():
    """Only fixed, hash-pinned CPU helpers; no orchestrator/render imports."""
    for name, (relative, expected) in SOURCE_HASHES.items():
        _MODULES[name] = _load('_studio_cpu_recovery_' + name, RECOVERY / relative, expected)
    return _MODULES


@contextmanager
def _studio_modules():
    previous = list(sys.path)
    sys.path.insert(0, str(STUDIO))
    try:
        values = {name: _load(name, STUDIO / (name + '.py'), expected)
                  for name, expected in STUDIO_HASHES.items()}
        yield values
    finally:
        sys.path[:] = previous


def _sha(value):
    return modules()['cache'].canonical_sha256(value)


def _alive(identity):
    """Reuse the detached manager's PID/start-time check, never a GPU probe."""
    with _studio_modules() as loaded:
        try:
            return loaded['studio_runtime']._manager().is_alive(identity)
        except Exception:
            fail('CPU_RECOVERY_PROCESS_IDENTITY_UNRESOLVED')


def _original_approval(approval, plan):
    keys = {'schema', 'approved', 'planSHA256', 'imageDigest', 'validUntil',
            'maxWallSeconds', 'maxRetries', 'maxCostAmount', 'currency', 'gpuHourlyRate'}
    if (not isinstance(approval, dict) or set(approval) != keys
            or approval['schema'] != 'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1'
            or approval['approved'] is not True or approval['planSHA256'] != _sha(plan)
            or not isinstance(approval['imageDigest'], str)
            or not re.fullmatch(r'sha256:[a-f0-9]{64}', approval['imageDigest'])
            or approval['imageDigest'] != plan.get('renderProfile', {}).get('imageDigest')
            or type(approval['maxWallSeconds']) is not int or not 1 <= approval['maxWallSeconds'] <= 86400
            or type(approval['maxRetries']) is not int or not 0 <= approval['maxRetries'] <= 2
            or not isinstance(approval['currency'], str) or not re.fullmatch(r'[A-Z]{3}', approval['currency'])):
        fail('CPU_RECOVERY_ORIGINAL_APPROVAL_INVALID')
    try:
        expiry = datetime.fromisoformat(approval['validUntil'])
        if expiry.tzinfo is None or expiry.utcoffset() is None:
            raise ValueError()
        for key in ('gpuHourlyRate', 'maxCostAmount'):
            if not isinstance(approval[key], (str, int)) or isinstance(approval[key], bool):
                raise ValueError()
            if not re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,8})?', str(approval[key])):
                raise ValueError()
        rate, cost = Decimal(approval['gpuHourlyRate']), Decimal(approval['maxCostAmount'])
        if rate <= 0 or cost <= 0 or Decimal(approval['maxWallSeconds']) * rate / Decimal(3600) > cost:
            raise ValueError()
    except (ValueError, TypeError, InvalidOperation):
        fail('CPU_RECOVERY_ORIGINAL_APPROVAL_INVALID')
    # Historical expiry is retained, not renewed. This grants no new GPU work.
    return approval


def _read_private(path):
    with modules()['cache'].PrivateTree(Path(path).absolute().parent) as tree:
        return tree.json(Path(path).name)


def _source_snapshot(tree, names):
    return {name: tree.hash_file(name) for name in names}


def _no_active_studio_process(root):
    # Both existing managers keep their own active pointer. Observe, never
    # remove/reset either claim. A pending unassigned claim is not safe to race.
    for filename in ('ACTIVE.json', 'active.json'):
        active = root.json(filename, optional=True)
        if active is None:
            continue
        job_id = active.get('jobId') if isinstance(active, dict) else None
        if not isinstance(job_id, str) or not JOB.fullmatch(job_id):
            fail('CPU_RECOVERY_UNRESOLVED_ACTIVE_CLAIM')
        with root.child(job_id) as job:
            state = job.json('STATE.json')
        if _alive(state.get('supervisorIdentity')):
            fail('CPU_RECOVERY_ANOTHER_STUDIO_PROCESS_RUNNING')
        if state.get('state') in {'QUEUED', 'RUNNING'} and not state.get('supervisorIdentity'):
            fail('CPU_RECOVERY_UNRESOLVED_ACTIVE_CLAIM')
    for name in ('render-v3', 'render-v4'):
        try:
            with root.child(name) as native:
                names = os.listdir(native.fd)
                if len(names) > 10000:
                    fail('CPU_RECOVERY_NATIVE_INVENTORY_LIMIT')
                for job_id in names:
                    if not re.fullmatch(r'video-v2-[a-f0-9]{24}', job_id):
                        continue
                    with native.child(job_id) as job:
                        ledger = job.json('JOB.json', optional=True)
                    if ledger is None:
                        continue
                    if _alive(ledger.get('supervisorIdentity')) or _alive(ledger.get('rendererIdentity')):
                        fail('CPU_RECOVERY_NATIVE_PROCESS_STILL_RUNNING')
        except FileNotFoundError:
            pass


def _inventory(parent_job_id, control_root, export_root, *, _test_only=False):
    if not isinstance(parent_job_id, str) or not JOB.fullmatch(parent_job_id):
        fail('CPU_RECOVERY_PARENT_JOB_INVALID')
    cache, delivery = modules()['cache'], modules()['delivery']
    root_path, export_root = Path(control_root).absolute(), Path(export_root).absolute()
    with cache.PrivateTree(root_path) as root, root.child(parent_job_id) as job:
        _no_active_studio_process(root)
        snapshot = _source_snapshot(job, ('STATE.json', 'PLAN.json', 'AUDIO.json', 'APPROVAL.json'))
        state, plan, audio, approval = (job.json(name) for name in ('STATE.json', 'PLAN.json', 'AUDIO.json', 'APPROVAL.json'))
        if (state.get('schema') != 'WORLD_ENGINE_STUDIO_JOB_V1' or state.get('jobId') != parent_job_id
                or state.get('state') not in {'FAILED', 'INTERRUPTED'}):
            fail('CPU_RECOVERY_FAILED_PARENT_REQUIRED')
        if _alive(state.get('supervisorIdentity')):
            fail('CPU_RECOVERY_PARENT_STILL_RUNNING')
        profile = state.get('profileId')
        if profile not in {'V4_ARCHIVAL_80S', 'UNIVERSAL_V3'}:
            fail('CPU_RECOVERY_PROFILE_UNSUPPORTED')
        if type(_test_only) is not bool or (plan.get('testOnly') is True) != _test_only:
            fail('CPU_RECOVERY_TEST_PROVENANCE_MISMATCH')
        _original_approval(approval, plan)
        contract = modules()['compose'].video_contract(plan)
        scenes = plan.get('scenes')
        if (not isinstance(scenes, list) or not scenes or len(scenes) > 10000
                or plan.get('totalFrames') != contract['frames']):
            fail('CPU_RECOVERY_PLAN_INVALID')
        if not _test_only:
            with _studio_modules() as loaded:
                loaded['studio_runtime'].validate_render_plan(plan, profile, approval['imageDigest'])
        base = {'parentJobId': parent_job_id, 'plan': plan, 'audio': audio, 'state': state, 'approval': approval,
                'contract': contract, 'snapshot': snapshot, 'testOnly': _test_only,
                'nativeLedgerFacts': None, 'nativeLedgerPath': None, 'silentResult': None}
        if state.get('silentResult') and (_test_only or state.get('gpuRenderingVerified') is True):
            # Original Studio assigns this receipt only after native completion.
            # It remains untrusted bytes until the frozen exporter rehashes it.
            delivery.verify_mounted_export(state['silentResult'], export_root)
            if _source_snapshot(job, snapshot) != snapshot:
                fail('CPU_RECOVERY_PARENT_CHANGED')
            return {**base, 'rows': [], 'silentResult': state['silentResult'],
                    'sourceMode': 'VERIFIED_EXISTING_SILENT_EXPORT'}
        native_name = 'render-v4' if profile == 'V4_ARCHIVAL_80S' else 'render-v3'
        native_id = 'video-v2-' + _sha(plan)[:24]
        with root.child(native_name) as native, native.child(native_id) as native_job:
            ledger_facts = native_job.hash_file('JOB.json')
            ledger = native_job.json('JOB.json')
            if (ledger.get('schema') != 'WORLD_ENGINE_UNIVERSAL_JOB_V2' or ledger.get('jobId') != native_id
                    or ledger.get('planSHA256') != _sha(plan) or ledger.get('testOnly') is not _test_only):
                fail('CPU_RECOVERY_NATIVE_LEDGER_INVALID')
            if _alive(ledger.get('supervisorIdentity')) or _alive(ledger.get('rendererIdentity')):
                fail('CPU_RECOVERY_NATIVE_PROCESS_STILL_RUNNING')
            base.update(nativeLedgerFacts=ledger_facts, nativeLedgerPath=native_job.path / 'JOB.json')
            if (ledger.get('state') == 'COMPLETED' and ledger.get('result')
                    and (_test_only or ledger.get('gpuRenderingVerified') is True)):
                delivery.verify_mounted_export(ledger['result'], export_root)
                if native_job.hash_file('JOB.json') != ledger_facts or _source_snapshot(job, snapshot) != snapshot:
                    fail('CPU_RECOVERY_PARENT_CHANGED')
                return {**base, 'rows': [], 'silentResult': ledger['result'],
                        'sourceMode': 'VERIFIED_EXISTING_SILENT_EXPORT'}
            completed = ledger.get('completedScenes')
            if not isinstance(completed, dict) or set(completed) != {s.get('sceneId') for s in scenes}:
                fail('CPU_RECOVERY_NOT_ALL_SCENES_COMPLETE')
            rows, cursor = [], 0
            for index, scene in enumerate(scenes):
                if (not isinstance(scene, dict) or type(scene.get('startFrame')) is not int
                        or type(scene.get('endFrame')) is not int or scene['startFrame'] != cursor
                        or not cursor < scene['endFrame'] <= contract['frames']):
                    fail('CPU_RECOVERY_SCENE_RANGE_INVALID')
                cursor = scene['endFrame']
                key = cache.scene_cache_key(plan, scene, scenes[index - 1] if index else None,
                                             scenes[index + 1] if index + 1 < len(scenes) else None)
                saved = completed[scene['sceneId']]
                if (not isinstance(saved, dict) or saved.get('cacheKey') != key
                        or not HEX.fullmatch(str(saved.get('sha256', '')))):
                    fail('CPU_RECOVERY_SCENE_BINDING_MISMATCH')
                segment, checkpoint = None, (ledger.get('sceneCheckpoints') or {}).get(scene['sceneId'])
                cache_rejection = None
                try:
                    # Native lookup creates a missing key. Require a preexisting
                    # pinned key before reusing it, keeping this inspection read-only.
                    with native.child('cache') as ct, ct.child(key):
                        pass
                    scene_cache = cache.SceneCache(native.path / 'cache')
                    try:
                        segment = scene_cache.lookup(key)
                    finally:
                        scene_cache.close()
                except (OSError, cache.CacheError) as error:
                    cache_rejection = safe_code(error)
                    segment = None
                if segment is not None:
                    if (any(segment.get(k) != scene.get(k) for k in ('sceneId', 'startFrame', 'endFrame'))
                            or segment.get('sha256') != saved['sha256'] or segment.get('technical') != 'PASS'
                            or segment.get('frameCountVerified') is not True or segment.get('fullDecodeVerified') is not True
                            or segment.get('testOnly') is not _test_only
                            or (not _test_only and segment.get('hardwareVerified') is not True)):
                        cache_rejection = 'CPU_RECOVERY_CACHE_PROVENANCE_INVALID'
                        segment = None
                if segment is not None:
                    source = {'kind': 'PRIVATE_CACHE', 'path': segment['path'], 'segment': segment}
                else:
                    if (not isinstance(checkpoint, dict) or checkpoint.get('planSHA256') != _sha(plan)
                            or checkpoint.get('sceneSHA256') != _sha(scene)
                            or any(checkpoint.get(k) != scene.get(k) for k in ('sceneId', 'startFrame', 'endFrame'))
                            or checkpoint.get('testOnly') is not _test_only
                            or (not _test_only and checkpoint.get('hardwareVerified') is not True)):
                        fail('CPU_RECOVERY_RETAINED_CHECKPOINT_REQUIRED')
                    delivery.verify_scene_checkpoint(checkpoint, export_root)
                    recorded = [r for r in checkpoint['files'] if r.get('file') == 'segment.mp4']
                    if len(recorded) != 1 or recorded[0].get('sha256') != saved['sha256']:
                        fail('CPU_RECOVERY_CHECKPOINT_HASH_MISMATCH')
                    source = {'kind': 'DROPBOX_CHECKPOINT', 'checkpoint': checkpoint, 'segment': {
                        **{k: scene[k] for k in ('sceneId', 'startFrame', 'endFrame')}, 'sha256': saved['sha256']},
                        'privateCacheRejectionCode': cache_rejection}
                rows.append(source)
            if cursor != contract['frames'] or ledger.get('progressFrames') != contract['frames']:
                fail('CPU_RECOVERY_FRAME_COVERAGE_INCOMPLETE')
            if native_job.hash_file('JOB.json') != ledger_facts:
                fail('CPU_RECOVERY_LEDGER_CHANGED')
        if _source_snapshot(job, snapshot) != snapshot:
            fail('CPU_RECOVERY_PARENT_CHANGED')
    return {**base, 'rows': rows, 'sourceMode': 'VERIFIED_SCENE_SEGMENTS'}


def inspect(parent_job_id, control_root, export_root, *, _test_only=False):
    value = _inventory(parent_job_id, control_root, export_root, _test_only=_test_only)
    return {'schema': 'WORLD_ENGINE_STUDIO_CPU_RECOVERY_INSPECTION_V1', 'status': 'READY_FOR_EXPLICIT_CPU_GRANT',
            'parentJobId': parent_job_id, 'planSHA256': _sha(value['plan']),
            'originalApprovalSHA256': _sha(value['approval']), 'scenes': len(value['plan']['scenes']),
            'frames': value['contract']['frames'], 'durationSeconds': value['contract']['durationSeconds'],
            'sources': [row['kind'] for row in value['rows']], 'sourceMode': value['sourceMode'], 'testOnly': _test_only,
            'historicalGpuProvenanceVerified': not _test_only, 'gpuExecuted': False, 'gpuAllowed': False,
            'originalApprovalRetained': True, 'originalPolicyExpired': datetime.fromisoformat(value['approval']['validUntil']) <= datetime.now(timezone.utc),
            'originalTimingsSeconds': value['state'].get('timingsSeconds', {}),
            'originalElapsedSeconds': max(0, (value['state'].get('finishedUnix') or time.time()) - value['state']['createdUnix']),
            'externalDownloadVerified': False}


def validate_grant(grant, value):
    keys = {'schema', 'approved', 'gpuAllowed', 'parentJobId', 'planSHA256', 'originalApprovalSHA256',
            'validUntil', 'maxWallSeconds', 'maxRetries', 'maxAdditionalGpuCostAmount', 'currency'}
    if (not isinstance(grant, dict) or set(grant) != keys
            or grant.get('schema') != 'WORLD_ENGINE_STUDIO_CPU_RECOVERY_AUTHORIZATION_V1'
            or grant.get('approved') is not True or grant.get('gpuAllowed') is not False
            or grant.get('parentJobId') != value['parentJobId'] or grant.get('planSHA256') != _sha(value['plan'])
            or grant.get('originalApprovalSHA256') != _sha(value['approval'])
            or type(grant.get('maxWallSeconds')) is not int or not 1 <= grant['maxWallSeconds'] <= 10800
            or type(grant.get('maxRetries')) is not int or grant['maxRetries'] != 0
            or grant.get('maxAdditionalGpuCostAmount') != '0' or grant.get('currency') != value['approval']['currency']):
        fail('CPU_RECOVERY_EXPLICIT_ZERO_GPU_GRANT_REQUIRED')
    try:
        expiry = datetime.fromisoformat(grant['validUntil'])
        if expiry.tzinfo is None or expiry.utcoffset() is None:
            raise ValueError()
        if expiry <= datetime.now(timezone.utc):
            fail('CPU_RECOVERY_GRANT_EXPIRED')
    except (ValueError, TypeError):
        fail('CPU_RECOVERY_GRANT_EXPIRY_INVALID')
    return min(grant['maxWallSeconds'], expiry.timestamp() - time.time())


def _copy_source(row, target):
    loaded = modules()
    storage = loaded['delivery']._storage()
    if row['kind'] == 'DROPBOX_CHECKPOINT':
        fail('CPU_RECOVERY_INTERNAL_COPY_CONTEXT_REQUIRED')
    source = Path(row['path'])
    directory = storage._open_directory(source.parent, safe_parents=True, account_uid=1000)
    try:
        with _studio_modules() as studio:
            # Frozen copy validates inode/size/mtime/hash before+after, and uses
            # exclusive creation. It cannot overwrite a cache or old result.
            expected = {'name': source.name, 'sha256': row['segment']['sha256'],
                        'bytes': os.stat(source, follow_symlinks=False).st_size}
            studio['studio_delivery']._facts(storage, directory, source.name, expected, copy_to=target)
    finally:
        os.close(directory)


def _copy_checkpoint(row, target, export_root):
    delivery = modules()['delivery']
    checkpoint = row['checkpoint']
    delivery.verify_scene_checkpoint(checkpoint, export_root)
    storage = delivery._storage()
    directory = delivery._open_export(storage, export_root, checkpoint['exportDirectory'], 'scene-recovery')
    expected = next(r for r in checkpoint['files'] if r['file'] == 'segment.mp4')
    try:
        with _studio_modules() as studio:
            studio['studio_delivery']._facts(storage, directory, 'segment.mp4', {
                'name': 'segment.mp4', 'sha256': expected['sha256'], 'bytes': expected['bytes']}, copy_to=target)
    finally:
        os.close(directory)


def _private_new_files(directory):
    """Only our new composition output, never a source or shared mount."""
    for path in Path(directory).iterdir():
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
                fail('CPU_RECOVERY_NEW_MEDIA_OWNER_INVALID')
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)


def recover(parent_job_id, grant_path, request_id, control_root, export_root, *, _test_only=False):
    started = time.monotonic()
    if not isinstance(request_id, str) or not REQUEST.fullmatch(request_id):
        fail('CPU_RECOVERY_REQUEST_ID_INVALID')
    loaded = modules()
    value = _inventory(parent_job_id, control_root, export_root, _test_only=_test_only)
    grant = _read_private(grant_path)
    seconds = validate_grant(grant, value)
    seconds = min(seconds, grant['maxWallSeconds'] - (time.monotonic() - started))
    cache = loaded['cache']
    identity = 'cpu-recovery-' + _sha({'parentJobId': parent_job_id, 'grant': grant, 'requestId': request_id})[:32]
    with cache.PrivateTree(Path(control_root).absolute()) as root:
        with root.child('cpu-recoveries', create=True) as recoveries, recoveries.lock('CPU_RECOVERY.lock'):
            with recoveries.child(identity, create=True) as work, work.lock():
                old = work.json('STATE.json', optional=True)
                if old is not None:
                    if old.get('state') == 'COMPLETED':
                        with _studio_modules() as studio:
                            studio['studio_delivery'].verify_export(old['result'], export_root)
                        return old
                    fail('CPU_RECOVERY_ALREADY_CLAIMED_NO_AUTOMATIC_RETRY')
                state = {'schema': 'WORLD_ENGINE_STUDIO_CPU_RECOVERY_V1', 'recoveryId': identity,
                         'parentJobId': parent_job_id, 'planSHA256': _sha(value['plan']),
                         'originalApprovalSHA256': _sha(value['approval']), 'grantSHA256': _sha(grant),
                         'state': 'RUNNING', 'phase': 'VALIDATED_SOURCE_COPY', 'startedAt': datetime.now(timezone.utc).isoformat(),
                         'timingsSeconds': {}, 'testOnly': _test_only, 'gpuExecuted': False, 'gpuAllowed': False,
                         'historicalGpuProvenanceVerified': not _test_only, 'originalApprovalRetained': True,
                         'originalGpuRetryOrDeadlineReset': False, 'externalDownloadVerified': False,
                         'visualQuality': 'USER_VIDEO_REVIEW_REQUIRED', 'finalPromotion': False,
                         'sourceMode': value['sourceMode'],
                         'privateCacheRejections': [row['privateCacheRejectionCode'] for row in value['rows']
                                                    if row.get('privateCacheRejectionCode')]}
                work.write_json('STATE.json', state)
                work.write_json('CPU_AUTHORIZATION.json', grant)
                def save(phase):
                    state['phase'] = phase
                    state['elapsedSeconds'] = round(time.monotonic() - started, 6)
                    work.write_json('STATE.json', state, replace=True)
                try:
                    with _studio_modules() as studio, studio['studio_runtime']._deadline(seconds):
                        silent = value['silentResult']
                        if silent is None:
                            with work.child('segments', create=True) as sources:
                                segments = []
                                phase_started = time.monotonic()
                                for index, row in enumerate(value['rows']):
                                    destination = sources.path / ('segment-' + str(index).zfill(5) + '.mp4')
                                    if row['kind'] == 'PRIVATE_CACHE':
                                        _copy_source(row, destination)
                                    else:
                                        _copy_checkpoint(row, destination, export_root)
                                    segments.append({**row['segment'], 'path': str(destination)})
                            state['timingsSeconds']['verifiedCopy'] = round(time.monotonic() - phase_started, 6)
                            save('COMPOSE')
                            phase_started = time.monotonic()
                            composed = loaded['compose'].compose_segments(value['plan'], segments, work.path / 'composition')
                            state['timingsSeconds']['compose'] = round(time.monotonic() - phase_started, 6)
                            _private_new_files(composed['publicDir'])
                            save('SILENT_EXPORT')
                            phase_started = time.monotonic()
                            silent = loaded['delivery'].export_video(value['plan'], composed, export_root)
                            state['timingsSeconds']['silentExport'] = round(time.monotonic() - phase_started, 6)
                        else:
                            state['skippedStages'] = ['SCENE_COPY', 'COMPOSE', 'SILENT_EXPORT']
                        work.write_json('SILENT_EXPORT.json', silent)
                        save('SFX_FINAL_EXPORT')
                        phase_started = time.monotonic()
                        with work.child('final', create=True) as final:
                            result = studio['studio_runtime'].finalize(value['plan'], value['audio'], silent, final.path, export_root)
                        state['timingsSeconds']['sfxComposeExportVerify'] = round(time.monotonic() - phase_started, 6)
                        # Rehash immutable inputs again; never repair or rewrite
                        # the old failed job, ledger, cache or original approval.
                        with root.child(parent_job_id) as original:
                            if _source_snapshot(original, value['snapshot']) != value['snapshot']:
                                fail('CPU_RECOVERY_PARENT_CHANGED')
                        if value['nativeLedgerPath'] is not None:
                            with cache.PrivateTree(value['nativeLedgerPath'].parent) as native_job:
                                if native_job.hash_file('JOB.json') != value['nativeLedgerFacts']:
                                    fail('CPU_RECOVERY_NATIVE_LEDGER_CHANGED')
                        state.update(state='COMPLETED', result=result, frames=value['contract']['frames'],
                                     scenes=len(value['plan']['scenes']), durationSeconds=value['contract']['durationSeconds'],
                                     videoDecodedPixelsUnchanged=True, fullDecode='PASS')
                        save('COMPLETED')
                        return state
                except BaseException as error:
                    state.update(state='FAILED', errorCode=safe_code(error))
                    save('FAILED')
                    raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'prepare', 'recover'))
    parser.add_argument('--parent-job-id', required=True)
    parser.add_argument('--control-root', required=True, type=Path)
    parser.add_argument('--export-root', type=Path, default=Path('/world-storage'))
    parser.add_argument('--grant', type=Path)
    parser.add_argument('--request-id')
    args = parser.parse_args(argv)
    try:
        if args.action == 'recover':
            if args.grant is None or args.request_id is None:
                fail('CPU_RECOVERY_GRANT_AND_REQUEST_REQUIRED')
            result = recover(args.parent_job_id, args.grant, args.request_id, args.control_root, args.export_root)
        else:
            result = inspect(args.parent_job_id, args.control_root, args.export_root)
            if args.action == 'prepare':
                result['grantContract'] = {'schema': 'WORLD_ENGINE_STUDIO_CPU_RECOVERY_AUTHORIZATION_V1',
                    'approved': False, 'gpuAllowed': False, 'parentJobId': args.parent_job_id,
                    'planSHA256': result['planSHA256'], 'originalApprovalSHA256': result['originalApprovalSHA256'],
                    'maxWallSeconds': 10800, 'maxRetries': 0, 'maxAdditionalGpuCostAmount': '0',
                    'validUntil': None, 'currency': None}
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'BLOCKED', 'errorCode': safe_code(error), 'gpuExecuted': False,
                          'gpuAllowed': False, 'externalDownloadVerified': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
