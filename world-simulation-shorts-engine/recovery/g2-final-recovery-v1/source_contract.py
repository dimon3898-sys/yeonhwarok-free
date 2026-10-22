"""Preserved source Scene plus a server-owned generic location-placement policy."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'g2-renderer-recovery-v1'
REPO = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


original = load('_g2_final_preserved_recovery_contract', OLD / 'source_contract.py')
adapter = load('_g2_final_explicit_layout_adapter', HERE / 'layout_adapter.py')
SCHEMA, PROFILE = original.SCHEMA, original.PROFILE


def final_bindings():
    paths = [HERE / name for name in ('source_contract.py', 'studio_controller.py',
        'studio_service.py', 'software_worker.py', 'capture_source.mjs', 'capture_recovery.mjs',
        'layout_adapter.py', 'layout_extension.mjs', 'fixtures/LAYOUT_PROFILE.json')]
    paths.append(REPO / 'world-simulation-shorts-engine/web/map_infographic_v1/graphic_layout.mjs')
    rows = original.recovery_bindings()
    for file in paths:
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(REPO):
            raise ValueError('G2_FINAL_EXECUTION_BINDING_MISSING')
        raw = file.read_bytes()
        rows.append({'path': file.relative_to(REPO).as_posix(),
                     'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    if len({row['path'] for row in rows}) != len(rows):
        raise ValueError('G2_FINAL_EXECUTION_BINDING_DUPLICATE')
    return rows


recovery_bindings = final_bindings


def apply_layout_profile(runtime_payload):
    """Return sourcePipeline update fields for a trusted precompiled runtime.

    Geometry, camera and roles remain exactly as supplied; the only Native Plan
    addition is the versioned placement policy. The full Studio path first runs
    the preserved strict source normalizer; bounded generic probes call this
    same adapter for their server-owned synthetic inputs.
    """
    profile_file = HERE / 'fixtures/LAYOUT_PROFILE.json'
    if profile_file.is_symlink() or not profile_file.is_file():
        raise ValueError('G2_FINAL_SERVER_LAYOUT_PROFILE_REQUIRED')
    raw = profile_file.read_bytes()
    profile = original.original.control.parse(raw)
    runtime = deepcopy(runtime_payload)
    plan, receipt = adapter.apply_location_policy(runtime['nativePlan'], profile)
    runtime['nativePlan'] = plan
    return {'runtimePayload': runtime, 'layoutProfile': deepcopy(profile),
            'layoutProfileSHA256': hashlib.sha256(raw).hexdigest(),
            'layoutActivationReceipt': receipt, 'recoveryBindings': final_bindings()}


def normalize_submission(value, *, source_root, expected_index_sha256):
    # The prior strict source normalizer enforces unchanged authored Scene,
    # exact numeric semantics, 180 synthetic frames, old source index and style.
    result = original.normalize_submission(value, source_root=source_root,
                                            expected_index_sha256=expected_index_sha256)
    pipeline = result['sourcePipeline']
    if (pipeline.get('mode') != 'SYNTHETIC_TEST' or pipeline.get('scope') != 'SYNTHETIC_TECHNICAL_DEMO'
            or pipeline.get('totalFrames') != 180 or pipeline.get('startFrame') != 0
            or pipeline.get('ready') is not True):
        raise ValueError('G2_FINAL_SYNTHETIC_SIX_SECONDS_ONLY')
    pipeline.update(apply_layout_profile(pipeline['runtimePayload']))
    receipt = pipeline['layoutActivationReceipt']
    pipeline['finalRecoveryScope'] = {
        'schema': 'WORLD_ENGINE_G2_FINAL_RECOVERY_EXECUTION_V1',
        'historicalRenderAllowed': False, 'paidGpuAllowed': False,
        'sameAuthoredSceneAsBaseline': True, 'maxFrames': 180,
        'rendererChanged': False, 'layoutExtensionSelected': True,
        'visualQualityApproved': False,
    }
    pipeline['captureSignature'] = hashlib.sha256(adapter.canonical({
        'schema': 'WORLD_ENGINE_G2_FINAL_CAPTURE_SIGNATURE_V1',
        'requestSHA256': pipeline['requestSHA256'],
        'sourceIndexSHA256': pipeline['sourceIndexSHA256'],
        'sourceStyleSHA256': pipeline['sourceStyleSHA256'],
        'layoutProfileSHA256': pipeline['layoutProfileSHA256'],
        'afterNativePlanSHA256': receipt['afterNativePlanSHA256'],
        'bindings': pipeline['recoveryBindings'],
    })).hexdigest()
    return result
