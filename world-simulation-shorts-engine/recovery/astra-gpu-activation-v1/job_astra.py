#!/usr/bin/env python3
"""Explicit ASTRA one-shot profile using the pinned detached supervisor unchanged.

No HTTP API, autostart, reset, environment-selected command or renderer override.
The ASTRA namespace never deletes or rewrites an existing 65422 claim/result.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
PROFILE = 'ASTRA_GPU_ACTIVATION_V1'
CONTROL_ROOT = Path('/var/lib/world-engine-private/engine/job-astra-v1')
EXPORT_ROOT = Path('/world-storage')
SHARED_NAME = 'world-engine-astra-job-v1'
LAUNCH = Path('/opt/world-engine-astra-activation/launch_astra.py')
_CAPTURE = '/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/astra-gpu-activation-v1/capture_astra.mjs'
PINNED = {
    'job_manager.py': '6398967204168e9284a6cc1b5b7f7e2951b996fb7cf5cb3d5f0a785b26047d99',
    'job_store.py': '1b8261f59a0b0652dae64fdd1ed040cb24b80743780c40fb141576fe7bb7b5fe',
    'inspect_existing.py': '23a361ac0da95dad50ae7c2d5a57d2e527c904869b2d8bbf8e99146386cf7b38',
}
_BASE = Path('/opt/world-engine-detached-render')
if not (_BASE / 'job_manager.py').is_file():
    _BASE = HERE.parent / 'gcube-detached-render-v1'


def _load(name, filename, aliases=None):
    """New module instance, with temporary import aliases restored immediately.

    Configuring this new instance cannot mutate the old CLI/module singleton.
    All functions still execute the original pinned source bytes.
    """
    path = _BASE / filename
    if hashlib.sha256(path.read_bytes()).hexdigest() != PINNED[filename]:
        raise RuntimeError('ASTRA_SUPERVISOR_SOURCE_CHANGED')
    marker = object()
    aliases = aliases or {}
    prior = {key: sys.modules.get(key, marker) for key in aliases}
    original_path = list(sys.path)
    try:
        sys.modules.update(aliases)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = original_path
        for key, value in prior.items():
            if value is marker:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


# Independent instances are profile configuration, never a patch of old files
# or of modules that existing jobs might already be using in this interpreter.
legacy_store = _load('_astra_legacy_store', 'job_store.py')
legacy_inspector = _load('_astra_legacy_inspector', 'inspect_existing.py')
legacy_manager = _load('_astra_legacy_manager', 'job_manager.py',
                       {'job_store': legacy_store, 'inspect_existing': legacy_inspector})
job_store = _load('_astra_profile_store', 'job_store.py')
job_store.CONTROL_ROOT = CONTROL_ROOT
job_store.SHARED_NAME = SHARED_NAME
job_store.SCHEMA = 'WORLD_ENGINE_ASTRA_DETACHED_JOB_V1'
job_store._JOB_ID = re.compile(r'astra-[0-9a-f]{24}\Z')


class Store(job_store.Store):
    def __init__(self, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
        super().__init__(control_root=control_root, export_root=export_root)

    def create(self, initial):
        if initial['testOnly']:
            return super().create(initial)
        private = shared = None
        try:
            private = self._private()
            authorization = manager._read_json_fd(private, 'ASTRA_PROFILE_AUTHORIZATION.json')
            if (not _valid_authorization(authorization)
                    or authorization['jobId'] != initial['jobId']):
                raise job_store.JobError('JOB_RECORD_INVALID')
            value = super().create(initial)
            shared = self._shared(private, value)
            manager.storage._new_file(shared, 'PROFILE_AUTHORIZATION.json', job_store._encode(authorization))
            manager.storage._shared_fsync(shared)
            return value
        finally:
            for descriptor in (shared, private):
                if descriptor is not None:
                    os.close(descriptor)


inspector = _load('_astra_profile_inspector', 'inspect_existing.py')
inspector.CONTROL_ROOT = CONTROL_ROOT
inspector._LAUNCHERS = frozenset((*inspector._LAUNCHERS, str(LAUNCH)))
_original_role = inspector._role


def _role(command):
    role = _original_role(command)
    if role:
        return role
    if command and Path(command[0]).name in {'node', 'nodejs'} and _CAPTURE in command:
        return 'ASTRA_NATIVE_CAPTURE'
    if (command and re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)?)?', Path(command[0]).name)
            and str(LAUNCH) in command and '--render-astra-65422' in command):
        return 'ASTRA_NATIVE_LAUNCHER'
    return None


inspector._role = _role
manager = _load('_astra_profile_manager', 'job_manager.py',
                {'job_store': job_store, 'inspect_existing': inspector})
manager.Store = Store
manager.CONTROL_ROOT = CONTROL_ROOT
manager.LAUNCH = LAUNCH
_original_initial = manager._initial
_original_verify = manager.verify_export


def _initial(test_only):
    value = _original_initial(test_only)
    if not test_only and _pending_job_id is None:
        raise manager.ManagerError('UNEXPECTED_FAILURE')
    value['jobId'] = ('astra-' + os.urandom(12).hex()) if test_only else _pending_job_id
    return value


def verify_astra_export(result, export_root):
    """Hash/FFprobe seven original bytes, then require ASTRA-native attestation.

    The extra receipt stays outside public-review. It is a native capture
    statement, not an independent proof of NVIDIA hardware or visual quality.
    """
    _original_verify(result, export_root)
    root = directory = unit = None
    try:
        root = manager.storage._open_directory(export_root)
        directory = os.open(result['exportDirectory'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
        unit = os.open(result['captures'][0]['directory'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        native = manager._read_json_fd(unit, 'ASTRA_COMPLETE.json')
        original = manager._read_json_fd(unit, 'EXPORT_COMPLETE.json')
        required = {'schema', 'status', 'profile', 'profileId', 'captureId', 'materialPlanSha256',
                    'activationSha256', 'bundleManifestSha256', 'extensionManifestSha256',
                    'astraApplied', 'gpuRenderingVerified', 'testOnly', 'visualQualityVerified',
                    'mountedViewReadbackVerified', 'remotePersistenceVerified', 'externalDownloadVerified'}
        if (not isinstance(native, dict) or set(native) != required
                or native['schema'] != 'WORLD_ENGINE_ASTRA_CAPTURE_RECEIPT_V1'
                or native['status'] != 'COMPLETE' or native['profile'] != PROFILE
                or not isinstance(native['profileId'], str)
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', native['profileId'])
                or native['captureId'] != original['captureId']
                or any(not isinstance(native[key], str) or not re.fullmatch('[0-9a-f]{64}', native[key])
                       for key in ('captureId', 'materialPlanSha256', 'activationSha256',
                                   'bundleManifestSha256', 'extensionManifestSha256'))
                or native['testOnly'] is not result['testOnly']
                or native['gpuRenderingVerified'] is not (not result['testOnly'])
                or native['astraApplied'] is not True or native['mountedViewReadbackVerified'] is not True
                or any(native[key] is not False for key in ('visualQualityVerified',
                       'remotePersistenceVerified', 'externalDownloadVerified'))):
            raise manager.ManagerError('RESULT_VERIFICATION_FAILED')
        return result
    finally:
        for descriptor in (unit, directory, root):
            if descriptor is not None:
                os.close(descriptor)


def _old_state(private_base, export_root):
    path = Path(private_base) / 'job-control-v1'
    descriptor = legacy_inspector._directory(path, optional=True)
    if descriptor is None:
        return None
    os.close(descriptor)
    return legacy_store.Store(control_root=path, export_root=export_root).read()


def inspect_profile(control_root=CONTROL_ROOT, private_base=inspector.PRIVATE_BASE,
                    export_root=EXPORT_ROOT, exclude_pids=(), *, _proc_root=inspector.PROC_ROOT,
                    acknowledge_baseline_history=False):
    """History acknowledgement authorizes a NEW ASTRA job, never an old retry.

    No mutable shared record is trusted as proof of old completion. Live PIDs,
    a held native guard, malformed state and inspection errors always veto.
    Historical directories/claims are preserved and recorded, not reset.
    """
    gate = inspector.inspect(control_root=control_root, private_base=private_base,
                             export_root=export_root, exclude_pids=exclude_pids, _proc_root=_proc_root)
    gate['profile'] = PROFILE
    gate['baselineHistoryAcknowledged'] = False
    if gate['status'] in {'RUNNING', 'BLOCKED'}:
        return gate
    try:
        old = _old_state(private_base, export_root)
        if old is not None and any(legacy_manager.is_alive(old[key])
                                  for key in ('supervisorIdentity', 'rendererIdentity')):
            gate.update(status='RUNNING', reason='LEGACY_JOB_ACTIVE')
            return gate
        old_claim = legacy_inspector._directory(Path(export_root) / legacy_store.SHARED_NAME, optional=True)
        claimed = old_claim is not None
        if old_claim is not None:
            os.close(old_claim)
        history = gate['status'] == 'EXISTING_RECORDS' or old is not None or claimed
        gate['baselineHistoryPresent'] = history
        if history:
            if not acknowledge_baseline_history:
                gate.update(status='EXISTING_RECORDS', reason='BASELINE_HISTORY_ACKNOWLEDGEMENT_REQUIRED')
            else:
                gate.update(status='CLEAR', reason='NEW_ASTRA_PROFILE_BASELINE_HISTORY_ACKNOWLEDGED',
                            baselineHistoryAcknowledged=True)
        return gate
    except (OSError, ValueError, TypeError, legacy_store.JobError, legacy_inspector.InspectionBlocked,
            legacy_manager.ManagerError, manager.storage.StorageError):
        gate.update(status='BLOCKED', reason='LEGACY_CAPTURE_REVIEW_UNAVAILABLE')
        return gate


_pending_job_id = None
_acknowledge_history = False


def _valid_authorization(value):
    return (isinstance(value, dict) and set(value) == {'schema', 'profile', 'jobId', 'createdAt',
            'baselineHistoryPresent', 'baselineHistoryAcknowledged', 'evidenceCounts',
            'gpuExecuted', 'renderAllowed'}
            and value['schema'] == 'WORLD_ENGINE_ASTRA_PROFILE_AUTHORIZATION_V1'
            and value['profile'] == PROFILE and isinstance(value['jobId'], str)
            and bool(job_store._JOB_ID.fullmatch(value['jobId']))
            and isinstance(value['createdAt'], str) and bool(job_store._STAMP.fullmatch(value['createdAt']))
            and all(type(value[key]) is bool for key in ('baselineHistoryPresent', 'baselineHistoryAcknowledged'))
            and (not value['baselineHistoryPresent'] or value['baselineHistoryAcknowledged'])
            and isinstance(value['evidenceCounts'], dict)
            and all(isinstance(key, str) and re.fullmatch('[A-Za-z]{1,40}', key)
                    and type(number) is int and 0 <= number <= 4096
                    for key, number in value['evidenceCounts'].items())
            and value['gpuExecuted'] is False and value['renderAllowed'] is False)


def _dispatch_inspection(**kwargs):
    global _pending_job_id
    gate = inspect_profile(**kwargs, acknowledge_baseline_history=_acknowledge_history)
    if gate['status'] != 'CLEAR':
        return gate
    # Called only inside the unchanged manager's already-held ASTRA Store lock.
    # This immutable authorization is not a job-completion/GPU status record.
    _pending_job_id = 'astra-' + os.urandom(12).hex()
    value = {'schema': 'WORLD_ENGINE_ASTRA_PROFILE_AUTHORIZATION_V1', 'profile': PROFILE,
             'jobId': _pending_job_id, 'createdAt': manager.stamp(),
             'baselineHistoryPresent': gate.get('baselineHistoryPresent', False),
             'baselineHistoryAcknowledged': gate['baselineHistoryAcknowledged'],
             'evidenceCounts': gate['evidenceCounts'], 'gpuExecuted': False, 'renderAllowed': False}
    if not _valid_authorization(value):
        raise manager.ManagerError('UNEXPECTED_FAILURE')
    descriptor = manager.storage._open_directory(kwargs['control_root'], safe_parents=True)
    try:
        manager.storage._new_file(descriptor, 'ASTRA_PROFILE_AUTHORIZATION.json',
                                  job_store._encode(value), private=True)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return gate


def start(store, *, acknowledge_baseline_history=False):
    global _acknowledge_history, _pending_job_id
    if type(acknowledge_baseline_history) is not bool:
        raise manager.ManagerError('INVALID_MANAGER_ARGUMENTS')
    _acknowledge_history = acknowledge_baseline_history
    try:
        return manager.start(store)
    finally:
        _acknowledge_history = False
        _pending_job_id = None


manager._initial = _initial
manager.verify_export = verify_astra_export
manager.inspect_existing = SimpleNamespace(inspect=_dispatch_inspection)


def main(argv=None):
    parser = manager.Parser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True, parser_class=manager.Parser)
    sub.add_parser('inspect')
    sub.add_parser('status')
    begin = sub.add_parser('start')
    begin.add_argument('--confirm-new-job', action='store_true')
    begin.add_argument('--acknowledge-baseline-history', action='store_true')
    try:
        args = parser.parse_args(argv)
        if args.action == 'inspect':
            value = inspect_profile()
            print(json.dumps(value, sort_keys=True))
            return 0 if value['status'] == 'CLEAR' else 2
        if args.action == 'start' and (not args.confirm_new_job
                or os.environ.get('WORLD_ENGINE_STARTUP_MODE', 'normal') != 'normal'):
            raise manager.ManagerError('EXPLICIT_NORMAL_NEW_JOB_CONFIRMATION_REQUIRED')
        manager._identity_setup()
        store = Store()
        value = manager.status(store) if args.action == 'status' else start(
            store, acknowledge_baseline_history=args.acknowledge_baseline_history)
        print(json.dumps(value, sort_keys=True))
        return 0 if value.get('state') != 'FAILED' else 2
    except Exception as error:
        code = error.code if isinstance(error, (manager.ManagerError, job_store.JobError)) else 'MANAGER_OPERATION_FAILED'
        allowed = set(job_store.ERROR_CODES) | {'PROCESS_IDENTITY_INVALID', 'EXISTING_CAPTURE_REQUIRES_REVIEW',
            'INVALID_MANAGER_ARGUMENTS', 'EXPLICIT_NORMAL_NEW_JOB_CONFIRMATION_REQUIRED'}
        if code not in allowed:
            code = 'MANAGER_OPERATION_FAILED'
        print(json.dumps({'schema': 'WORLD_ENGINE_ASTRA_MANAGER_ERROR_V1', 'state': 'BLOCKED',
                          'reason': code, 'renderAllowed': False, 'gpuRenderingVerified': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
