#!/usr/bin/env python3
"""Explicit reference-V2 one-shot profile over the unchanged detached manager.

No HTTP API, autostart, reset, implicit retry or caller-selected render command.
All 65422, ASTRA and Quality claims/results remain intact.
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
PROFILE = 'WORLD_ENGINE_REFERENCE_VISUAL_MASTER_V2'
PROFILE_ID = 'REFERENCE_VISUAL_MASTER_V2_F'
CONTROL_ROOT = Path('/var/lib/world-engine-private/engine/job-reference-v2-v1')
EXPORT_ROOT = Path('/world-storage')
SHARED_NAME = 'world-engine-reference-v2-job-v1'
LAUNCH = Path('/opt/world-engine-reference-v2/launch_ref2.py')
CAPTURE = '/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/reference-visual-master-v2/capture_ref2.mjs'
QUALITY_SHA256 = 'fc8d4e2502a5a57e2a7d2075326088842d6b1ef32cd690dde08deaaf2e699937'
QUALITY_ROOT = Path('/opt/world-engine-visual-quality')
if not (QUALITY_ROOT / 'job_quality.py').is_file():
    QUALITY_ROOT = HERE.parent / 'visual-quality-upgrade-v1'


def _load_quality(name):
    path = QUALITY_ROOT / 'job_quality.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != QUALITY_SHA256:
        raise RuntimeError('REFERENCE_SUPERVISOR_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old_quality = _load_quality('_reference_v2_untouched_quality_profile')
base = _load_quality('_reference_v2_active_profile_dependencies')
manager, job_store = base.manager, base.job_store
# These are isolated module-instance settings; old singleton globals and source
# bytes are unchanged. Reuse the existing strict authorization/store functions.
base.PROFILE, base.PROFILE_ID = PROFILE, PROFILE_ID
base._AUTH_SCHEMA = 'WORLD_ENGINE_REFERENCE_V2_PROFILE_AUTHORIZATION_V1'
base._AUTHORIZATION = 'REFERENCE_V2_PROFILE_AUTHORIZATION.json'
job_store.CONTROL_ROOT = CONTROL_ROOT
job_store.SHARED_NAME = SHARED_NAME
job_store.SCHEMA = 'WORLD_ENGINE_REFERENCE_V2_DETACHED_JOB_V1'
job_store._JOB_ID = re.compile(r'reference-v2-65422-[0-9a-f]{24}\Z')
_pending_job_id = None
_acknowledge_history = False


class Store(base.Store):
    def __init__(self, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
        super().__init__(control_root=control_root, export_root=export_root)


def _initial(test_only):
    value = base.base._original_initial(test_only)
    if not test_only and _pending_job_id is None:
        raise manager.ManagerError('UNEXPECTED_FAILURE')
    value['jobId'] = 'reference-v2-65422-' + os.urandom(12).hex() if test_only else _pending_job_id
    return value


_original_role = base.base.inspector._role
_PREFIX = '/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/'
_NATIVE_ALIASES = {
    str(LAUNCH): 'REFERENCE_V2_NATIVE_LAUNCHER',
    _PREFIX + 'reference-visual-master-v2/launch_ref2.py': 'REFERENCE_V2_NATIVE_LAUNCHER',
    str(old_quality.LAUNCH): 'QUALITY_NATIVE_LAUNCHER',
    _PREFIX + 'visual-quality-upgrade-v1/launch_quality.py': 'QUALITY_NATIVE_LAUNCHER',
    str(old_quality.old_astra.LAUNCH): 'ASTRA_NATIVE_LAUNCHER',
    _PREFIX + 'astra-gpu-activation-v1/launch_astra.py': 'ASTRA_NATIVE_LAUNCHER',
}


def _role(command):
    role = _original_role(command)
    if role:
        return role
    if command and Path(command[0]).name in {'node', 'nodejs'} and CAPTURE in command:
        return 'REFERENCE_V2_NATIVE_CAPTURE'
    if (command and re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)?)?', Path(command[0]).name)
            and any(flag in command for flag in ('--render-65422', '--render-astra-65422',
                                                '--render-quality-65422', '--render-reference-v2-65422'))):
        return next((role for filename, role in _NATIVE_ALIASES.items() if filename in command), None)
    return None


base.base.inspector._role = _role
base.base.inspector.CONTROL_ROOT = CONTROL_ROOT


def _quality_state(private_base, export_root):
    path = Path(private_base) / 'job-quality-v1'
    descriptor = old_quality.base.legacy_inspector._directory(path, optional=True)
    if descriptor is None:
        return None
    os.close(descriptor)
    return old_quality.Store(control_root=path, export_root=export_root).read()


def inspect_profile(control_root=CONTROL_ROOT, private_base=base.base.inspector.PRIVATE_BASE,
                    export_root=EXPORT_ROOT, exclude_pids=(), *, _proc_root=base.base.inspector.PROC_ROOT,
                    acknowledge_baseline_history=False):
    """A history acknowledgement permits only a distinct V2 operation."""
    gate = base.inspect_profile(control_root=control_root, private_base=private_base,
        export_root=export_root, exclude_pids=exclude_pids, _proc_root=_proc_root,
        acknowledge_baseline_history=acknowledge_baseline_history)
    gate.update(profile=PROFILE, profileId=PROFILE_ID)
    if gate['status'] in {'RUNNING', 'BLOCKED'}:
        return gate
    try:
        old = _quality_state(private_base, export_root)
        if old is not None and any(old_quality.manager.is_alive(old[key])
                                  for key in ('supervisorIdentity', 'rendererIdentity')):
            gate.update(status='RUNNING', reason='QUALITY_JOB_ACTIVE', baselineHistoryAcknowledged=False)
            return gate
        descriptor = old_quality.base.legacy_inspector._directory(Path(export_root) / old_quality.SHARED_NAME, optional=True)
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
                gate.update(status='CLEAR', reason='NEW_REFERENCE_V2_PROFILE_BASELINE_HISTORY_ACKNOWLEDGED',
                            baselineHistoryAcknowledged=True)
        return gate
    except (OSError, ValueError, TypeError, old_quality.job_store.JobError,
            old_quality.base.legacy_inspector.InspectionBlocked, old_quality.manager.ManagerError,
            manager.storage.StorageError):
        gate.update(status='BLOCKED', reason='QUALITY_CAPTURE_REVIEW_UNAVAILABLE', baselineHistoryAcknowledged=False)
        return gate


def _dispatch_inspection(**kwargs):
    global _pending_job_id
    gate = inspect_profile(**kwargs, acknowledge_baseline_history=_acknowledge_history)
    if gate['status'] != 'CLEAR':
        return gate
    _pending_job_id = 'reference-v2-65422-' + os.urandom(12).hex()
    value = {'schema': base._AUTH_SCHEMA, 'profile': PROFILE, 'profileId': PROFILE_ID,
        'jobId': _pending_job_id, 'createdAt': manager.stamp(),
        'baselineHistoryPresent': gate.get('baselineHistoryPresent', False),
        'baselineHistoryAcknowledged': gate['baselineHistoryAcknowledged'],
        'evidenceCounts': gate['evidenceCounts'], 'gpuExecuted': False, 'renderAllowed': False}
    if not base._valid_authorization(value):
        raise manager.ManagerError('UNEXPECTED_FAILURE')
    descriptor = manager.storage._open_directory(kwargs['control_root'], safe_parents=True)
    try:
        manager.storage._new_file(descriptor, base._AUTHORIZATION, job_store._encode(value), private=True)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return gate


# The existing exact public-media and ASTRA receipt verifier also binds the new
# fixed profileId through this independent module's PROFILE_ID configuration.
verify_export = base.verify_quality_export
manager.Store, manager.CONTROL_ROOT, manager.LAUNCH = Store, CONTROL_ROOT, LAUNCH
manager._initial, manager.verify_export = _initial, verify_export
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
        print(json.dumps({'schema': 'WORLD_ENGINE_REFERENCE_V2_MANAGER_ERROR_V1', 'state': 'BLOCKED',
                          'reason': code, 'renderAllowed': False, 'gpuRenderingVerified': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
