"""Preview-only source/selection/image authority; no full-video fallback.

Optional unavailable national/scalar capabilities are checked only when selected.
A qualified partial-history base preview never invents those missing actors.
"""
from copy import deepcopy
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/'universal-integration-completion-v2'


def load(name,path):
    spec=importlib.util.spec_from_file_location('_overnight_'+name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=value;spec.loader.exec_module(value);return value


def _manifest(): return load('source_manifest',HERE/'package_manifest.py')

def _source_plan(submission):
    old=load('parent_bridge',PARENT/'runtime_bridge.py')
    plan=old._source_plan(submission)
    contract=load('contract',HERE/'contract_v3.py')
    value=submission.get('overnightV3')
    if not isinstance(value,dict) or contract.normalize_overnight(value)!=value:
        raise RuntimeError('STUDIO_OVERNIGHT_EXPLICIT_CANONICAL_PROFILE_REQUIRED')
    return plan


def _visual_admission(value,catalog,plan):
    result=subprocess.run(['node',str(HERE/'visual_extensions.mjs'),'--admit'],
        input=json.dumps({'request':value,'trustedSources':catalog['trustedSources'],
            'fps':plan['fps'],'totalFrames':plan['totalFrames']},allow_nan=False).encode(),
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
    if result.returncode or len(result.stdout)>1024*1024:
        raise RuntimeError('STUDIO_OVERNIGHT_SELECTED_VISUAL_SOURCE_BLOCKED')
    try: facts=json.loads(result.stdout)
    except ValueError: raise RuntimeError('STUDIO_OVERNIGHT_SELECTED_VISUAL_SOURCE_BLOCKED') from None
    if facts.get('status')!='CPU_ADMITTED':raise RuntimeError('STUDIO_OVERNIGHT_SELECTED_VISUAL_SOURCE_BLOCKED')
    return facts


def gate_context(submission,*,image_digest,control_root=None):
    plan=_source_plan(submission);manifest=_manifest();proof=manifest.verify_sources()
    data=load('qualified_data',HERE/'data_readiness.py')
    catalog,catalog_raw,catalog_sha=data.load_effective_catalog()
    history=data.admit_capture_sources(submission,catalog)
    visual=_visual_admission(submission['overnightV3']['visualExtensions'],catalog,plan)
    image=manifest.read_image_proof(control_root,source_manifest_sha256=proof['manifestSHA256'],image_digest=image_digest)
    bindings={'sourceCommit':image['sourceCommit'] if image else proof['sourceCommit'],
        'sourceManifestSHA256':proof['manifestSHA256'],'imageDigest':image_digest,
        'originalPlanSHA256':manifest.sha(manifest.canonical(plan)),
        'completionProfileSHA256':manifest.sha(manifest.canonical({
            'integration':submission['integration'],'completionV2':submission['completionV2'],
            'visualExtensions':submission['overnightV3']['visualExtensions']})),
        'sourceCatalogSHA256':catalog_sha}
    preview=load('preview_contract',HERE/'preview_contract.py').compile_preview(plan,bindings=bindings,
        start_frame=submission['overnightV3'].get('startFrame'),frame_count=150)
    return {'schema':'WORLD_ENGINE_OVERNIGHT_GATE_CONTEXT_V3','sourceClosureVerified':True,
        'sourceManifestSHA256':proof['manifestSHA256'],'imagePackageIncluded':image is not None,
        'preview':preview,'dataAdmitted':history['dataAdmitted'],
        'dataBlockers':history['essentialDataBlockers'],'selectedVisualAdmission':visual,
        'requiredModules':{'PRESERVED_V5_CAMERA':'READY','SUPPLIED_AREA_FRONTIER':'READY',
            'SOURCE_BOUND_PREVIEW_150':'READY','QUALIFIED_SOURCE_HISTORY':'READY' if history['dataAdmitted'] else 'BLOCKED'},
        'full80Allowed':False,'full80Blocker':'STUDIO_OVERNIGHT_FULL_VIDEO_REQUIRES_REVIEW',
        'gpuRenderingVerified':False,'renderAllowed':False}


def preflight(submission,*,control_root,export_root,image_digest):
    checks=[]
    try:
        context=gate_context(submission,image_digest=image_digest,control_root=control_root)
        checks.append({'name':'OVERNIGHT_SOURCE_AND_PREVIEW_RANGE','status':'PASS','facts':{'frames':150}})
        if not context['imagePackageIncluded']:
            checks.append({'name':'OVERNIGHT_IMAGE','status':'BLOCKED','code':'STUDIO_OVERNIGHT_IMAGE_PROOF_REQUIRED'})
        if not context['dataAdmitted'] or context['dataBlockers']:
            checks.append({'name':'OVERNIGHT_QUALIFIED_HISTORY','status':'BLOCKED','code':'STUDIO_OVERNIGHT_REQUIRED_SOURCE_BLOCKED'})
        if all(r['status']=='PASS' for r in checks):
            manager=load('preview_manager',HERE/'execution_manager.py')
            result=manager.preflight(submission,control_root=control_root,export_root=export_root,image_digest=image_digest)
            checks.extend(result['checks'])
    except Exception as error:
        code=getattr(error,'code',None) or str(error)
        if not isinstance(code,str) or not code.replace('_','').isalnum() or len(code)>95:
            code='STUDIO_OVERNIGHT_PREFLIGHT_FAILED'
        checks.append({'name':'OVERNIGHT_ADMISSION','status':'BLOCKED','code':code})
    return {'checks':checks,'renderAllowed':bool(checks) and all(r['status']=='PASS' for r in checks),
        'gpuRenderingVerified':False,'requiresGpu':True,'full80Allowed':False,
        'providerBillingStopControlled':False}


def prepare_runtime_request(submission,*,image_digest,control_root=None):
    context=gate_context(submission,image_digest=image_digest,control_root=control_root)
    old=load('old_capture_identity',PARENT/'runtime_bridge.py')
    parent_request=old.prepare_runtime_request(submission,image_digest=image_digest)
    manifest=_manifest()
    identity={'schema':'WORLD_ENGINE_OVERNIGHT_CAPTURE_REQUEST_V3','profile':'OVERNIGHT_SAFE_V3',
        'sourceManifestSHA256':context['sourceManifestSHA256'],
        'imageDigest':image_digest,'preview':context['preview'],
        'overnightV3':deepcopy(submission['overnightV3']),
        'parentCaptureRequest':parent_request,'frameConvention':'GLOBAL_HALF_OPEN',
        'oldCacheReuseAllowed':False}
    return {**identity,'captureSignature':manifest.sha(manifest.canonical(identity)),
        'globalGPUAdmissionRequired':True,'rendererOutputVerified':False}


def _authorize_start(submission,control_root,image_digest):
    context=gate_context(submission,image_digest=image_digest,control_root=control_root)
    if not context['imagePackageIncluded']:raise RuntimeError('STUDIO_OVERNIGHT_IMAGE_PROOF_REQUIRED')
    if not context['dataAdmitted'] or context['dataBlockers']:
        raise RuntimeError('STUDIO_OVERNIGHT_REQUIRED_SOURCE_BLOCKED')
    return load('authorized_preview_manager',HERE/'execution_manager.py')


def start_studio_job(submission,approval_path,sfx,request_id,*,control_root,export_root,image_digest):
    manager=_authorize_start(submission,control_root,image_digest)
    return manager.start(submission,approval_path,sfx,request_id,control_root=control_root,
        export_root=export_root,image_digest=image_digest)


def studio_status(job_id,*,control_root,export_root,image_digest):
    return load('preview_status',HERE/'execution_manager.py').status(job_id,control_root=control_root,export_root=export_root)


def start_studio_recovery(*args,**kwargs):
    raise RuntimeError('STUDIO_OVERNIGHT_PREVIEW_RETRY_REQUIRES_NEW_APPROVAL')
