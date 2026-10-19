"""Full completion metadata to the preserved Studio, capture and safety gates."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'universal-integration-v1'


def _load(name, path):
    spec = importlib.util.spec_from_file_location('_completion_' + name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


parent = _load('v1_bridge_instance', PREVIOUS / 'runtime_bridge.py')
parent.HERE = HERE


def _manifest():
    return _load('source_manifest', HERE / 'package_manifest.py')


def _owned(name, filename):
    base = PREVIOUS if filename in {'quality_gate.py', 'data_coverage.py'} else HERE
    return _load(name, base / filename)


parent._manifest, parent._load = _manifest, _owned


def _source_plan(submission):
    plan = parent._source_plan(submission)
    contract = _load('contract', HERE / 'contract_v2.py')
    completion = submission.get('completionV2')
    if not isinstance(completion, dict) or contract.normalize_completion(completion) != completion:
        raise RuntimeError('COMPLETION_EXPLICIT_CANONICAL_PROFILE_REQUIRED')
    return plan


def data_admission(submission):
    plan = _source_plan(submission)
    history = _load('history_admission', HERE / 'history_admission.py')
    front = json.loads((HERE.parent / 'verified-front-data-v4-recovery/FRONT_PROFILE.json').read_bytes())
    catalog = json.loads(_manifest().read_regular(HERE / 'SOURCE_DATA_CATALOG.json'))
    authority = _load('history_source_bytes', HERE / 'history_source_binding.py')
    bindings = authority.verify_bound_history_objects(catalog, HERE.parent, plan=plan,
        front_profile=front, image_digest=plan.get('renderProfile', {}).get('imageDigest'))
    result = history.assess_history(plan, front, source_bindings=bindings)
    result['sourceChecks']['actualSourceBytesVerifiedByThisAssessment'] = True
    # An arbitrary client source binding can never become verification authority.
    request = submission['completionV2']['eventFlow']
    if any(request.get(kind) for kind in ('events', 'flows', 'areas')):
        event = _load('event_flow_bridge', HERE / 'event_flow_contract.py')
        event.validate_event_flow(request, fps=plan['fps'], total_frames=plan['totalFrames'],
                                 trusted_sources=catalog['trustedSources'])
    return result


def gate_context(submission, *, image_digest, control_root=None):
    plan = _source_plan(submission)
    proof = _manifest().verify_sources()
    history = data_admission(submission)
    image_module = _load('operator_image_proof', HERE / 'image_proof.py')
    image = image_module.read(control_root, source_manifest_sha256=proof['manifestSHA256'], image_digest=image_digest)
    # Current display may honestly hold partial fronts. Missing daily lines or
    # opponent-complement polygons do not invalidate a qualified source-only plan.
    modules = {'SOURCE_BOUND_COMPLETION_STUDIO': 'READY', 'PRESERVED_V5_CAMERA': 'READY',
        'SUPPLIED_AREA_FRONTIER': 'READY', 'QUALIFIED_SOURCE_HISTORY': 'READY' if history['dataAdmitted'] else 'BLOCKED',
        'ASTRA_SUPPORTED_SOURCE_MATERIAL': 'READY', 'EVENT_FLOW_DATA_ADMISSION': 'READY',
        'SFX_ONLY_REVISION': 'READY', 'PRIVATE_METADATA_CAPTURE': 'READY'}
    # The brief requires historical national actors and premium scalar lighting;
    # neither can be fabricated from partial lines or city anchors.
    modules.update({'HISTORICAL_NATIONAL_UNIT_POSITIONS': 'BLOCKED',
                    'TERRAIN_AWARE_SCALAR_FRONTIER_CONTRACT': 'BLOCKED'})
    return {'sourceCommit': image['sourceCommit'] if image else BASE_COMMIT, 'sourceManifestSHA256': proof['manifestSHA256'],
        'sourceClosureManifestSHA256': proof['manifestSHA256'],
        'sceneSHA256': _manifest().sha(_manifest().canonical({key: submission[key]
            for key in ('videoPlan', 'integration', 'completionV2')})),
        'imageDigest': image_digest, 'durationSeconds': int(plan['durationSeconds']), 'fps': plan['fps'],
        'sourceClosureVerified': True, 'imagePackageIncluded': image is not None,
        'requiredModules': modules, 'dataBlockers': history['essentialDataBlockers'],
        'referenceSHA256': parent.REFERENCE_SHA256, 'candidateSHA256': parent._candidate_sha(control_root)}


BASE_COMMIT = '61c7fc3a36cc987c3f88844aba98c57bb62fe22e'
parent.gate_context = gate_context


def prepare_runtime_request(submission, *, image_digest):
    plan = _source_plan(submission)
    manifest = _manifest(); proof = manifest.verify_sources()
    identity = {'schema': 'WORLD_ENGINE_INTEGRATED_CAPTURE_REQUEST_V1',
        'videoPlanSHA256': manifest.sha(manifest.canonical(plan)),
        'integration': deepcopy(submission['integration']),
        'completionV2': deepcopy(submission['completionV2']), 'imageDigest': image_digest,
        'sourceManifestSHA256': proof['manifestSHA256'],
        'previousManifestSHA256': proof['previousManifestSHA256'],
        'frameConvention': 'GLOBAL_HALF_OPEN', 'oldCacheReuseAllowed': False}
    return {**identity, 'captureSignature': manifest.sha(manifest.canonical(identity)),
            'globalGPUAdmissionRequired': True, 'rendererOutputVerified': False}


parent.prepare_runtime_request = prepare_runtime_request
_authorize_start = parent._authorize_start
preflight = parent.preflight
start_studio_job = parent.start_studio_job
studio_status = parent.studio_status
start_studio_recovery = parent.start_studio_recovery


def start_studio_revision(parent_job_id, submission, request_id, *, control_root, export_root, image_digest):
    manager = _authorize_start(submission, control_root, image_digest)
    return manager.revise(parent_job_id, submission, request_id, control_root=control_root,
                          export_root=export_root, image_digest=image_digest)
