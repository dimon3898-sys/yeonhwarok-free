"""Run the actual strict new parser against an explicit server-owned source registry.

No GPU admission, policy modification, Studio job or fallback preset is created.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from director_contract import normalize_request
from camera_admission import validate_camera_admission
from control_contract import validate_control_timeline
from evidence_gates import validate_marker_evidence, validate_audio_manifest


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build(plan):
    profile = json.loads((ROOT / 'fixtures/HISTORY_EVENT_PROFILE_V2.json').read_bytes())
    request = {'schema': 'WORLD_ENGINE_EVENT_DIRECTOR_REQUEST_V1',
        'sourcePlanSha256': profile['sourcePlanSHA256'], 'subjectId': profile['subjectId'],
        'fps': profile['fps'], 'totalFrames': profile['totalFrames'],
        'purpose': 'QUALIFIED_SOURCE_REVIEW', 'requiredCapabilities': [
            'EVENT.CORRECT_CHRONOLOGY', 'SOURCE.NO_PREVIOUS_FALLBACK',
            'AREA.SUPPLIED_PARTIAL_FRONT', 'ASTRA.COMPOSED_TEXTURE', 'CAMERA.REGIONAL_REVIEW',
            'CAMERA.LOCAL_FOCUS', 'HISTORY.FULL_CONTROL_TRANSITIONS',
            'FRONT.EXACT_OWNERSHIP_SYNC', 'NATIONAL_FLAGS', 'AUDIO.SEMANTIC_SYNC']}
    names = {'eventDirectorProfileRef': 'HISTORY_EVENT_PROFILE_V2.json',
        'sourceCatalogRef': 'HISTORY_SOURCE_CATALOG.json', 'cameraAdmissionRef': 'CAMERA_ADMISSION.json',
        'controlTimelineRef': 'CONTROL_TIMELINE.json', 'markerEvidenceRef': 'MARKER_EVIDENCE.json',
        'audioCueManifestRef': 'AUDIO_CUE_MANIFEST.json'}
    trusted = {}
    for role, name in names.items():
        relative = 'fixtures/' + name
        raw = (ROOT / relative).read_bytes()
        reference = {'path': relative, 'version': str(json.loads(raw)['version']), 'sha256': sha(raw)}
        request[role] = reference
        trusted[relative] = {**reference, 'role': role}
    caps = {}
    bound = {'EVENT.CORRECT_CHRONOLOGY': ('derive_scene.mjs', 'compileDerivedScene'),
        'SOURCE.NO_PREVIOUS_FALLBACK': ('derive_scene.mjs', 'UNKNOWN_STATE_MUST_NOT_REUSE_PREVIOUS_GEOMETRY'),
        'AREA.SUPPLIED_PARTIAL_FRONT': ('browser_adapter.mjs', 'bootLongRuntime'),
        'ASTRA.COMPOSED_TEXTURE': ('material_context.mjs', 'readDirectorMaterialFrame'),
        'CAMERA.REGIONAL_REVIEW': ('camera_bridge.mjs', 'createProductionNativeCamera')}
    for capability in request['requiredCapabilities']:
        if capability in bound:
            name, symbol = bound[capability]
            raw = (ROOT / name).read_bytes()
            caps[capability] = {'available': True, 'sourcePath': str(ROOT / name),
                'sha256': sha(raw), 'symbol': symbol, 'consumer': 'ASTRA_EVENT_DIRECTOR_QUALIFIED_SOFTWARE_REVIEW',
                'selector': 'EXPLICIT_DIRECTOR_V2_IMPORT_MAP'}
        else:
            caps[capability] = {'available': False, 'reason': 'SOURCE_OR_ADMISSION_EVIDENCE_MISSING'}
    receipt = ROOT / 'reports/DERIVATION.json'
    normalized = normalize_request(request, source_plan_path=str(Path(plan).resolve()), source_root=str(ROOT),
        trusted_refs=trusted, capability_bindings=caps,
        component_validators={'cameraAdmissionRef': validate_camera_admission,
            'controlTimelineRef': validate_control_timeline, 'markerEvidenceRef': validate_marker_evidence,
            'audioCueManifestRef': validate_audio_manifest},
        derivation_bindings={'receiptPath': str(receipt), 'receiptSHA256': sha(receipt.read_bytes()),
            'scenePath': str(ROOT / 'fixtures/DERIVED_SCENE.json'),
            'frontProfilePath': str(ROOT / 'fixtures/DERIVED_FRONT_PROFILE.json'),
            'compilerPath': str(ROOT / 'derive_scene.mjs')})
    if normalized['productionReady'] or normalized['renderAllowed'] or not normalized['reviewReady']:
        raise ValueError('EXPLICIT_QUALIFIED_REVIEW_ONLY_PREFLIGHT_REQUIRED')
    return request, normalized


if __name__ == '__main__':
    request, normalized = build(sys.argv[1])
    for name, value in [('fixtures/EVENT_DIRECTOR_SOURCE_REVIEW_REQUEST.json', request),
                        ('fixtures/NORMALIZED_SOURCE_REVIEW.json', normalized)]:
        (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'schema': normalized['schema'], 'productionReady': normalized['productionReady'],
        'reviewReady': normalized['reviewReady'], 'requiredCapabilities': request['requiredCapabilities'],
        'blockers': normalized['blockers']}, ensure_ascii=False))
