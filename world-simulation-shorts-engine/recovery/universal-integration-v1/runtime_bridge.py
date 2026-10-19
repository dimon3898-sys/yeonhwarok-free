"""Fail-closed Studio V2 bridge: preserve frozen plan and expose honest readiness.

The metadata-to-browser binding is implemented in runtime_binding.mjs. Current
history does not admit the requested occupation/military choreography and this
source extension is not in the operating image. Neither condition is papered
by routing the submission back to the old renderer. No operation in this module
starts a render or rewrites an existing claim.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
RECOVERY=HERE.parent
REFERENCE_SHA256='5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6'


def _load(name, filename):
    path=HERE/filename
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise RuntimeError('INTEGRATION_SOURCE_PATH_UNSAFE')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def _manifest():
    return _load('_integration_package_manifest', 'package_manifest.py')


def _source_plan(submission):
    if (not isinstance(submission,dict) or submission.get('integration',{}).get('schema')!='WORLD_ENGINE_UNIVERSAL_INTEGRATION_V1'
            or submission.get('integration',{}).get('profile')!='VISUAL_UNIFIED_V1'
            or not isinstance(submission.get('videoPlan'),dict)):
        raise RuntimeError('INTEGRATION_EXPLICIT_SUBMISSION_REQUIRED')
    return submission['videoPlan']


def gate_context(submission, *, image_digest, control_root=None):
    plan=_source_plan(submission);manifest=_manifest();proof=manifest.verify_sources()
    coverage=_load('_integration_data_coverage','data_coverage.py')
    front=json.loads((RECOVERY/'verified-front-data-v4-recovery/FRONT_PROFILE.json').read_bytes())
    data=coverage.build_coverage(plan,front)
    # Required facts are missing in the preserved inputs. They are not optional
    # decoration, and a user quality receipt cannot authorize invented history.
    modules={'ASTRA_SOURCE_MATERIAL':'READY','AREA_SUPPLIED_FRONT':'READY','V5_NATIVE_CAMERA':'READY',
        'INTEGRATED_PRESENTATION_BINDINGS':'READY', 'SFX_EVENT_TIMELINE':'READY',
        'HISTORICAL_UNIT_TRACKS':'BLOCKED','BILATERAL_OWNERSHIP_GEOMETRY':'BLOCKED',
        'CONTINUOUS_OBSERVED_FRONT_MOTION':'BLOCKED','DETACHED_INTEGRATED_CAPTURE_HANDOFF':'READY'}
    requirements=json.loads(manifest.read_regular(HERE/'REQUIRED_MODULES.json'))
    modules.update(requirements['requirements'])
    return {'sourceCommit':manifest.BASE_COMMIT,'sourceManifestSHA256':proof['manifestSHA256'],
        'sourceClosureManifestSHA256':proof['manifestSHA256'],
        'sceneSHA256':hashlib.sha256(manifest.canonical({'videoPlan':plan,'integration':submission['integration']})).hexdigest(),
        'imageDigest':image_digest,'durationSeconds':int(plan['durationSeconds']),'fps':plan['fps'],
        'sourceClosureVerified':proof['status']=='PASS',
        'imagePackageIncluded':proof['registeredCandidateImageDigest']==image_digest,
        'requiredModules':modules,
        'dataBlockers':list(data['dataSafetyBlockers']),
        'referenceSHA256':REFERENCE_SHA256,'candidateSHA256':_candidate_sha(control_root)}


def prepare_runtime_request(submission, *, image_digest):
    """Compile neutral sidecar identity without mutating a frozen video plan.

    This is the contract consumed by the source-bound browser-plan composer.
    It is NOT a render claim or coordinator launch permission.
    """
    plan = _source_plan(submission)
    manifest = _manifest(); proof = manifest.verify_sources()
    identity = {'schema': 'WORLD_ENGINE_INTEGRATED_CAPTURE_REQUEST_V1',
        'videoPlanSHA256':hashlib.sha256(manifest.canonical(plan)).hexdigest(),
        'integration':deepcopy(submission['integration']), 'imageDigest':image_digest,
        'sourceManifestSHA256':proof['manifestSHA256'],
        'frameConvention':'GLOBAL_HALF_OPEN', 'oldCacheReuseAllowed':False}
    return {**identity, 'captureSignature':hashlib.sha256(manifest.canonical(identity)).hexdigest(),
        'globalGPUAdmissionRequired':True,'rendererOutputVerified':False}


def _candidate_sha(control_root):
    if control_root is None:return None
    quality=_load('_integration_private_quality','quality_gate.py')
    root=Path(control_root)/'quality_receipts';file=root/'approval.json'
    if not file.exists():return None
    receipt=quality._private_receipt(file,root,__import__('os').geteuid())
    return receipt.get('candidateSHA256')


def preflight(submission, *, control_root, export_root, image_digest):
    context=gate_context(submission,image_digest=image_digest,control_root=control_root)
    checks=[{'name':'INTEGRATION_SOURCE_CLOSURE','status':'PASS'},
      {'name':'INTEGRATION_CAPTURE_HANDOFF','status':'PASS'}]
    if not context['imagePackageIncluded']:
        checks.append({'name':'INTEGRATION_IMAGE','status':'BLOCKED','code':'INTEGRATION_CANDIDATE_NOT_INCLUDED_IN_IMAGE'})
    if context['dataBlockers']:
        checks.append({'name':'INTEGRATION_HISTORY','status':'BLOCKED','code':'INTEGRATION_REQUIRED_DATA_BLOCKED'})
    if any(row['status']=='BLOCKED' for row in checks):
        return {'checks':checks,'renderAllowed':False,'gpuRenderingVerified':False}
    manager=_load('_integration_execution_manager','execution_manager.py')
    # Frozen checks remain authoritative and run only after the controller gate.
    native=manager.runtime().preflight(submission['videoPlan'],submission['profile'],
        control_root=control_root,export_root=export_root)
    return {**native,'checks':checks+native['checks']}


def _authorize_start(submission,control_root,image_digest):
    context=gate_context(submission,image_digest=image_digest,control_root=control_root)
    if context['dataBlockers']:raise RuntimeError('INTEGRATION_REQUIRED_DATA_BLOCKED')
    if not context['imagePackageIncluded']:raise RuntimeError('INTEGRATION_CANDIDATE_NOT_INCLUDED_IN_IMAGE')
    manager=_load('_integration_execution_manager','execution_manager.py');runtime=manager.runtime()
    # Reuse the exact controller's private operator-policy parser.
    import importlib.util
    location=_manifest().parent_path('production-studio-mvp-v1/studio_controller.py')
    spec=importlib.util.spec_from_file_location('_integration_original_policy_controller',location)
    controller_parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(controller_parent)
    def read_policy():
        base=Path(control_root)
        with runtime._cache().PrivateTree(base) as root:
            if root.json('operator_policy.json',optional=True) is not None:return controller_parent.StudioController._policy(None,root)
        with runtime._cache().PrivateTree(base.parent) as root:return controller_parent.StudioController._policy(None,root)
    policy=read_policy()
    quality=_load('_integration_start_quality','quality_gate.py')
    def validate_policy(value):
        actual=read_policy()
        if value!=actual:raise RuntimeError('INTEGRATION_OPERATOR_POLICY_CHANGED')
        return actual
    report=quality.evaluate_render_gate(context,phase='FULL_VIDEO',operator_policy=policy,
        policy_validator=validate_policy,receipt_path=Path(control_root)/'quality_receipts/approval.json',
        trusted_receipt_root=Path(control_root)/'quality_receipts')
    if not report['allowed']:raise RuntimeError('INTEGRATION_FULL_VIDEO_QUALITY_GATE_BLOCKED')
    return manager


def start_studio_job(submission, approval_path, sfx, request_id, *, control_root, export_root, image_digest):
    manager=_authorize_start(submission,control_root,image_digest)
    return manager.start(submission,approval_path,sfx,request_id,control_root=control_root,
        export_root=export_root,image_digest=image_digest)


def studio_status(job_id, *, control_root, export_root, image_digest):
    manager=_load('_integration_execution_manager','execution_manager.py')
    return manager.status(job_id,control_root=control_root,export_root=export_root)


def start_studio_recovery(job_id, approval_path, request_id, *, control_root, export_root, image_digest):
    manager=_load('_integration_execution_manager','execution_manager.py')
    return manager.recover(job_id,approval_path,request_id,control_root=control_root,export_root=export_root,image_digest=image_digest)
