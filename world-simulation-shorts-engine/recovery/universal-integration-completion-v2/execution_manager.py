"""Reuse V1 detached jobs in an isolated, metadata-bound completion namespace.

Only a fresh Python module instance is configured. Preserved source, existing
claims and workers are untouched. All native GPU/cost/admission checks remain.
"""
from pathlib import Path
import importlib.util
import os
import sys

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


parent = _load('_completion_detached_v1_instance', HERE.parent / 'universal-integration-v1/execution_manager.py')
parent.HERE = HERE
_original_module = parent._module
parent._module = lambda name, path: _original_module('_completion' + name, path)
_original_runtime = parent.runtime


def runtime():
    value = _original_runtime()
    value.HERE = HERE
    value.PROFILES = dict(value.PROFILES, V4_ARCHIVAL_80S='universal-integration-completion-v2')
    return value


parent.runtime = runtime


def authorize_request(plan=None):
    request = parent.read_request()
    scope = Path(os.environ[parent.ENV]).parent
    if scope.parent.name != 'runtime_inputs' or scope.name != request['captureSignature']:
        raise RuntimeError('COMPLETION_CAPTURE_SCOPE_INVALID')
    value = runtime()
    if plan is None:
        plan = value.bind_render_image(value.default_plan('V4_ARCHIVAL_80S'), 'V4_ARCHIVAL_80S', request['imageDigest'])
    if value._cache().canonical_sha256(plan) != request['videoPlanSHA256']:
        raise RuntimeError('COMPLETION_CAPTURE_PLAN_BINDING_REQUIRED')
    bridge = _load('_completion_worker_gate', HERE / 'runtime_bridge.py')
    return bridge._authorize_start({'videoPlan': plan, 'profile': 'V4_ARCHIVAL_80S',
        'integration': request['integration'], 'completionV2': request.get('completionV2')},
        scope.parent.parent, request['imageDigest'])


parent.authorize_request = authorize_request
read_request = parent.read_request
request_environment = parent.request_environment
start = parent.start
job_scope = parent.job_scope
status = parent.status
recover = parent.recover


def revise(parent_job_id, submission, request_id, *, control_root, export_root, image_digest):
    """SFX-only child reuses verified silent media and the same capture identity."""
    bridge = _load('_completion_revision_gate', HERE / 'runtime_bridge.py')
    bridge._authorize_start(submission, control_root, image_digest)
    scope = job_scope(control_root, parent_job_id)
    with request_environment(scope / 'INTEGRATION_REQUEST.json'):
        request = read_request()
        if (request.get('completionV2') != submission.get('completionV2')
                or request.get('integration') != submission.get('integration')):
            raise RuntimeError('COMPLETION_REVISION_CAPTURE_CHANGED')
        authorize_request(submission['videoPlan'])
        state = runtime().start_studio_revision(parent_job_id, submission['sfx'], request_id,
            control_root=scope, export_root=export_root)
    parent._index_job(control_root, state['jobId'], scope.name)
    return state
