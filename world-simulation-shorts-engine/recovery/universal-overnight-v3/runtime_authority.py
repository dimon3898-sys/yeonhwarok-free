"""Verify both private capture sidecars before either hardware or software boot."""
from pathlib import Path
import argparse
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
ORIGINAL = Path('/opt/world-engine-production-studio') if HERE.is_relative_to('/opt') else HERE.parent / 'production-studio-mvp-v1'
sys.path.insert(0, str(ORIGINAL))


def load(name, file):
    spec = importlib.util.spec_from_file_location('_overnight_authority_' + name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_runtime_sidecars(request_file, plan_file, *, preview_file=None):
    manifest = load('manifest', HERE / 'package_manifest.py')
    source = manifest.verify_sources()
    request_path, plan_path = Path(request_file), Path(plan_file)
    request = json.loads(manifest.read_regular(request_path))
    raw_plan = manifest.read_regular(plan_path)
    plan = json.loads(raw_plan)
    keys = {'schema', 'profile', 'sourceManifestSHA256', 'imageDigest', 'preview', 'overnightV3',
            'parentCaptureRequest', 'frameConvention', 'oldCacheReuseAllowed', 'captureSignature',
            'globalGPUAdmissionRequired', 'rendererOutputVerified'}
    if (not isinstance(request, dict) or set(request) != keys
            or request['schema'] != 'WORLD_ENGINE_OVERNIGHT_CAPTURE_REQUEST_V3'
            or request['profile'] != 'OVERNIGHT_SAFE_V3'
            or request['frameConvention'] != 'GLOBAL_HALF_OPEN'
            or request['oldCacheReuseAllowed'] is not False
            or request['globalGPUAdmissionRequired'] is not True
            or request['rendererOutputVerified'] is not False
            or request['sourceManifestSHA256'] != source['manifestSHA256']):
        raise RuntimeError('OVERNIGHT_EXACT_CAPTURE_REQUEST_REQUIRED')
    body = {key: value for key, value in request.items()
            if key not in {'captureSignature', 'globalGPUAdmissionRequired', 'rendererOutputVerified'}}
    if manifest.sha(manifest.canonical(body)) != request['captureSignature']:
        raise RuntimeError('OVERNIGHT_CAPTURE_SIGNATURE_CHANGED')
    contract = load('contract', HERE / 'contract_v3.py')
    if contract.normalize_overnight(request['overnightV3']) != request['overnightV3']:
        raise RuntimeError('OVERNIGHT_CANONICAL_PROFILE_REQUIRED')
    old = load('parent_bridge', HERE.parent / 'universal-integration-completion-v2/runtime_bridge.py')
    parent_request = request['parentCaptureRequest']
    submission = {'videoPlan': plan, 'integration': parent_request['integration'],
                  'completionV2': parent_request['completionV2']}
    expected_parent = old.prepare_runtime_request(submission, image_digest=request['imageDigest'])
    actual_parent = json.loads(manifest.read_regular(plan_path.with_name('INTEGRATION_REQUEST.json')))
    if parent_request != expected_parent or actual_parent != expected_parent:
        raise RuntimeError('OVERNIGHT_PRESERVED_CAPTURE_REQUEST_CHANGED')
    data = load('qualified_data', HERE / 'data_readiness.py')
    catalog, catalog_raw, catalog_sha = data.load_effective_catalog()
    data.admit_capture_sources(submission, catalog)  # Actual history AND original supplied subevents.
    preview_owner = load('preview', HERE / 'preview_contract.py')
    preview_owner.validate_preview(request['preview'], plan)
    bindings = request['preview']['bindings']
    if (bindings['originalPlanSHA256'] != manifest.sha(raw_plan)
            or bindings['imageDigest'] != request['imageDigest']
            or bindings['sourceManifestSHA256'] != source['manifestSHA256']):
        raise RuntimeError('OVERNIGHT_PREVIEW_CAPTURE_BINDING_MISMATCH')
    if (bindings['sourceCatalogSHA256'] != catalog_sha
            or bindings['completionProfileSHA256'] != manifest.sha(manifest.canonical({
                'integration': submission['integration'], 'completionV2': submission['completionV2'],
                'visualExtensions': request['overnightV3']['visualExtensions']}))):
        raise RuntimeError('OVERNIGHT_PREVIEW_SOURCE_CATALOG_CHANGED')
    expected_preview = preview_owner.compile_preview(plan, bindings=bindings,
        start_frame=request['overnightV3'].get('startFrame'), frame_count=150)
    if expected_preview != request['preview']:
        raise RuntimeError('OVERNIGHT_AUTHORED_PREVIEW_SELECTION_CHANGED')
    preview_path = Path(preview_file) if preview_file else plan_path.with_name('PREVIEW_REQUEST.json')
    if json.loads(manifest.read_regular(preview_path)) != request['preview']:
        raise RuntimeError('OVERNIGHT_PREVIEW_FILE_CHANGED')
    return request


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request-file', required=True)
    parser.add_argument('--plan-file', required=True)
    parser.add_argument('--preview-file')
    args = parser.parse_args()
    result = verify_runtime_sidecars(args.request_file, args.plan_file, preview_file=args.preview_file)
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
