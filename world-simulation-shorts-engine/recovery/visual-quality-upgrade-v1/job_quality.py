#!/usr/bin/env python3
"""One explicitly authorized visual-quality render, independent of a terminal.

The immutable ASTRA supervisor/store/inspector are reused in isolated instances.
Old ASTRA and 65422 claims/results are preserved. No HTTP API, reset, auto-retry,
caller-selected command, browser flags or GPU admission replacement is offered.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
PROFILE = 'WORLD_ENGINE_VISUAL_QUALITY_UPGRADE_V1'
PROFILE_ID = 'VISUAL_QUALITY_UPGRADE_V1_F'
CONTROL_ROOT = Path('/var/lib/world-engine-private/engine/job-quality-v1')
EXPORT_ROOT = Path('/world-storage')
SHARED_NAME = 'world-engine-quality-job-v1'
LAUNCH = Path('/opt/world-engine-visual-quality/launch_quality.py')
CAPTURE = '/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/visual-quality-upgrade-v1/capture_quality.mjs'
ASTRA_SHA256 = '5a796d769fa5785f3317aa8aecf4020e9e2b55831a339eb79801aed6f9af8854'
ASTRA_ROOT = Path('/opt/world-engine-astra-activation')
if not (ASTRA_ROOT / 'job_astra.py').is_file():
    ASTRA_ROOT = HERE.parent / 'astra-gpu-activation-v1'


def _load_astra(name):
    path = ASTRA_ROOT / 'job_astra.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != ASTRA_SHA256:
        raise RuntimeError('QUALITY_SUPERVISOR_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Distinct instances protect old module singletons as well as source bytes.
old_astra = _load_astra('_quality_untouched_astra_profile')
base = _load_astra('_quality_active_profile_dependencies')
manager = base.manager
job_store = base.job_store
job_store.CONTROL_ROOT = CONTROL_ROOT
job_store.SHARED_NAME = SHARED_NAME
job_store.SCHEMA = 'WORLD_ENGINE_QUALITY_DETACHED_JOB_V1'
job_store._JOB_ID = re.compile(r'quality-[0-9a-f]{24}\Z')
_AUTHORIZATION = 'QUALITY_PROFILE_AUTHORIZATION.json'
_AUTH_SCHEMA = 'WORLD_ENGINE_QUALITY_PROFILE_AUTHORIZATION_V1'
_pending_job_id = None
_acknowledge_history = False


def _valid_authorization(value):
    return (isinstance(value, dict) and set(value) == {'schema', 'profile', 'profileId', 'jobId',
            'createdAt', 'baselineHistoryPresent', 'baselineHistoryAcknowledged', 'evidenceCounts',
            'gpuExecuted', 'renderAllowed'}
            and value['schema'] == _AUTH_SCHEMA and value['profile'] == PROFILE
            and value['profileId'] == PROFILE_ID and isinstance(value['jobId'], str)
            and bool(job_store._JOB_ID.fullmatch(value['jobId']))
            and isinstance(value['createdAt'], str) and bool(job_store._STAMP.fullmatch(value['createdAt']))
            and all(type(value[key]) is bool for key in ('baselineHistoryPresent', 'baselineHistoryAcknowledged'))
            and (not value['baselineHistoryPresent'] or value['baselineHistoryAcknowledged'])
            and isinstance(value['evidenceCounts'], dict)
            and all(isinstance(key, str) and re.fullmatch('[A-Za-z]{1,40}', key)
                    and type(number) is int and 0 <= number <= 4096
                    for key, number in value['evidenceCounts'].items())
            and value['gpuExecuted'] is False and value['renderAllowed'] is False)


class Store(job_store.Store):
    def __init__(self, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
        super().__init__(control_root=control_root, export_root=export_root)

    def create(self, initial):
        if initial['testOnly']:
            return super().create(initial)
        private = shared = None
        try:
            private = self._private()
            authorization = manager._read_json_fd(private, _AUTHORIZATION)
            if not _valid_authorization(authorization) or authorization['jobId'] != initial['jobId']:
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


def _initial(test_only):
    value = base._original_initial(test_only)
    if not test_only and _pending_job_id is None:
        raise manager.ManagerError('UNEXPECTED_FAILURE')
    value['jobId'] = 'quality-' + os.urandom(12).hex() if test_only else _pending_job_id
    return value


_original_role = base.inspector._role


def _role(command):
    role = _original_role(command)
    if role:
        return role
    if command and Path(command[0]).name in {'node', 'nodejs'} and CAPTURE in command:
        return 'QUALITY_NATIVE_CAPTURE'
    if (command and re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)?)?', Path(command[0]).name)
            and str(LAUNCH) in command and any(flag in command for flag in ('--render-65422', '--render-quality-65422'))):
        return 'QUALITY_NATIVE_LAUNCHER'
    return None


base.inspector._role = _role
base.inspector.CONTROL_ROOT = CONTROL_ROOT


def _astra_state(private_base, export_root):
    path = Path(private_base) / 'job-astra-v1'
    descriptor = old_astra.legacy_inspector._directory(path, optional=True)
    if descriptor is None:
        return None
    os.close(descriptor)
    return old_astra.Store(control_root=path, export_root=export_root).read()


def inspect_profile(control_root=CONTROL_ROOT, private_base=base.inspector.PRIVATE_BASE,
                    export_root=EXPORT_ROOT, exclude_pids=(), *, _proc_root=base.inspector.PROC_ROOT,
                    acknowledge_baseline_history=False):
    """Acknowledge history only for a new quality operation; active jobs veto."""
    gate = base.inspect_profile(control_root=control_root, private_base=private_base,
        export_root=export_root, exclude_pids=exclude_pids, _proc_root=_proc_root,
        acknowledge_baseline_history=acknowledge_baseline_history)
    gate.update(profile=PROFILE, profileId=PROFILE_ID)
    if gate['status'] in {'RUNNING', 'BLOCKED'}:
        return gate
    try:
        old = _astra_state(private_base, export_root)
        if old is not None and any(old_astra.manager.is_alive(old[key])
                                  for key in ('supervisorIdentity', 'rendererIdentity')):
            gate.update(status='RUNNING', reason='ASTRA_JOB_ACTIVE', baselineHistoryAcknowledged=False)
            return gate
        descriptor = old_astra.legacy_inspector._directory(Path(export_root) / old_astra.SHARED_NAME, optional=True)
        claimed = descriptor is not None
        if descriptor is not None:
            os.close(descriptor)
        history = gate.get('baselineHistoryPresent', False) or old is not None or claimed
        gate['baselineHistoryPresent'] = history
        if history:
            if not acknowledge_baseline_history:
                gate.update(status='EXISTING_RECORDS', reason='BASELINE_HISTORY_ACKNOWLEDGEMENT_REQUIRED',
                            baselineHistoryAcknowledged=False)
            else:
                gate.update(status='CLEAR', reason='NEW_QUALITY_PROFILE_BASELINE_HISTORY_ACKNOWLEDGED',
                            baselineHistoryAcknowledged=True)
        return gate
    except (OSError, ValueError, TypeError, old_astra.job_store.JobError,
            old_astra.legacy_inspector.InspectionBlocked, old_astra.manager.ManagerError,
            manager.storage.StorageError):
        gate.update(status='BLOCKED', reason='ASTRA_CAPTURE_REVIEW_UNAVAILABLE', baselineHistoryAcknowledged=False)
        return gate


def _dispatch_inspection(**kwargs):
    global _pending_job_id
    gate = inspect_profile(**kwargs, acknowledge_baseline_history=_acknowledge_history)
    if gate['status'] != 'CLEAR':
        return gate
    _pending_job_id = 'quality-' + os.urandom(12).hex()
    value = {'schema': _AUTH_SCHEMA, 'profile': PROFILE, 'profileId': PROFILE_ID,
        'jobId': _pending_job_id, 'createdAt': manager.stamp(),
        'baselineHistoryPresent': gate.get('baselineHistoryPresent', False),
        'baselineHistoryAcknowledged': gate['baselineHistoryAcknowledged'],
        'evidenceCounts': gate['evidenceCounts'], 'gpuExecuted': False, 'renderAllowed': False}
    if not _valid_authorization(value):
        raise manager.ManagerError('UNEXPECTED_FAILURE')
    descriptor = manager.storage._open_directory(kwargs['control_root'], safe_parents=True)
    try:
        manager.storage._new_file(descriptor, _AUTHORIZATION, job_store._encode(value), private=True)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return gate


def verify_quality_export(result, export_root):
    # Existing source-anchored seven-file/FFprobe and exact ASTRA receipt checks.
    base.verify_astra_export(result, export_root)
    root = export = unit = None
    try:
        root = manager.storage._open_directory(export_root)
        export = os.open(result['exportDirectory'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
        unit = os.open(result['captures'][0]['directory'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=export)
        receipt = manager._read_json_fd(unit, 'ASTRA_COMPLETE.json')
        if receipt['profileId'] != PROFILE_ID:
            raise manager.ManagerError('RESULT_VERIFICATION_FAILED')
        return result
    finally:
        for descriptor in (unit, export, root):
            if descriptor is not None:
                os.close(descriptor)


manager.Store = Store
manager.CONTROL_ROOT = CONTROL_ROOT
manager.LAUNCH = LAUNCH
manager._initial = _initial
manager.verify_export = verify_quality_export
manager.inspect_existing = SimpleNamespace(inspect=_dispatch_inspection)


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
        print(json.dumps({'schema': 'WORLD_ENGINE_QUALITY_MANAGER_ERROR_V1', 'state': 'BLOCKED',
                          'reason': code, 'renderAllowed': False, 'gpuRenderingVerified': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
