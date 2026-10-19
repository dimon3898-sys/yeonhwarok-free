"""Fail before GPU admission for slots the frozen native producer cannot supply.

This is an additive capability guard, not source, history, operator, image or GPU
admission. The preserved source/catalog and current-frame layout owners remain
mandatory. Capabilities are tied to exact code bytes; no public request, Scene,
environment variable or caller-supplied map can declare a native slot available.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECOVERY = HERE.parent
OVERNIGHT = RECOVERY / 'universal-overnight-v3'
COMPLETION = RECOVERY / 'universal-integration-completion-v2'
FROZEN_SOURCE_COMMIT = 'e23613195c356ad53874030f983a30a0e30d639f'
OVERNIGHT_MANIFEST_SHA256 = 'ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7'
COMPLETION_MANIFEST_SHA256 = '99caa40a2c7566982f5c5502ce4d5ce95e35367dc5809c8e7013ca4e83c7b3e9'
_COMPONENTS = {
    'nativePublisher': ('universal-integration-completion-v2/production_camera_bridge.mjs',
        '41f79321ce2beb7c04a694bffabba9bce75f7096cad3f4c37c52d51ee2be08ab'),
    'privateFrameContext': ('universal-integration-completion-v2/frame_context.mjs',
        '2930b8777eff4a23afb97319986ee18eea42f2039ccf5b20a6c9a23c0559b86b'),
    'optionalCompositor': ('universal-overnight-v3/browser_adapter.mjs',
        'df89ddc6f6d568d27c3fecf695a93821a5117631432458ae8f59075158fa9590'),
    'optionalConsumer': ('universal-overnight-v3/visual_extensions.mjs',
        '770adb1f498c91ec772b1321b29cdcaee2d1d53cc243aa3917d0cda146e72666'),
}
_CAPABILITIES = {
    # The current wrapper executes its parent BEFORE optional scalar painting.
    # It has no replacement slot that suppresses the parent's Area fill/front.
    'scalarParentCompositionSlot': False,
    'parentGeographicAreaMayBePresent': True,
    'sourceBoundBoundarySegments': True,
    # production_camera_bridge publishes only frame/native/boundarySegments.
    'internalBoundarySegments': False,
    'sameFramePreTerritoryTerrainTexture': False,
    'sameFrameNativeRoleCoverage': False,
    # National badges have their own retained source + CURRENT layout owner.
    # This is not a claim that historical unit-position data is available.
    'nationalSourceAndCurrentLayoutOwnerRetained': True,
}


class NativeCapabilityError(RuntimeError):
    def __init__(self, code, details=None):
        super().__init__(code)
        self.code = code
        self.details = deepcopy(details or {})


def _fail(code, details=None):
    raise NativeCapabilityError(code, details)


def _read_bytes(path):
    """Use the retained bounded, no-symlink reader, never a public path."""
    module_path = OVERNIGHT / 'package_manifest.py'
    spec = importlib.util.spec_from_file_location('_reconcile_native_manifest', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_regular(path)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect_native_capabilities():
    """Return audited capabilities only for the exact preserved 27 + 55 closure.

    New native producer bytes require a separately reviewed capability version.
    Unknown code fails closed; substring matching cannot grant a native slot.
    """
    if _digest(_read_bytes(OVERNIGHT / 'OVERNIGHT_FILES.json')) != OVERNIGHT_MANIFEST_SHA256:
        _fail('RECONCILE_NATIVE_SOURCE_MANIFEST_CHANGED')
    if _digest(_read_bytes(COMPLETION / 'COMPLETION_FILES.json')) != COMPLETION_MANIFEST_SHA256:
        _fail('RECONCILE_NATIVE_PARENT_MANIFEST_CHANGED')
    spec = importlib.util.spec_from_file_location('_reconcile_frozen_overnight', OVERNIGHT / 'package_manifest.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    proof = module.verify_sources()
    if (proof.get('status') != 'PASS' or proof.get('manifestSHA256') != OVERNIGHT_MANIFEST_SHA256
            or proof.get('previousManifestSHA256') != COMPLETION_MANIFEST_SHA256
            or proof.get('files') != 27 or proof.get('parentFiles') != 55):
        _fail('RECONCILE_NATIVE_FROZEN_CLOSURE_REQUIRED')
    components = {}
    for role, (relative, expected) in _COMPONENTS.items():
        if _digest(_read_bytes(RECOVERY / relative)) != expected:
            _fail('RECONCILE_NATIVE_COMPONENT_CHANGED', {'component': role})
        components[role] = {'path': relative, 'sha256': expected}
    return {'schema': 'WORLD_ENGINE_NATIVE_CAPABILITIES_V1',
        'frozenSource': {'sourceCommit': FROZEN_SOURCE_COMMIT,
            'overnightManifestSHA256': OVERNIGHT_MANIFEST_SHA256,
            'completionManifestSHA256': COMPLETION_MANIFEST_SHA256,
            'overnightFilesVerified': 27, 'parentFilesVerified': 55, 'components': components},
        'capabilities': deepcopy(_CAPABILITIES),
        'gpuVerified': False, 'renderAllowed': False}


def _selected(visual_request):
    if (not isinstance(visual_request, dict)
            or set(visual_request) != {'schema', 'scalarTerritory', 'nationalUnits'}
            or visual_request.get('schema') != 'WORLD_ENGINE_OVERNIGHT_VISUAL_V1'):
        _fail('RECONCILE_NATIVE_EXACT_VISUAL_REQUEST_REQUIRED')
    result = {}
    for key in ('scalarTerritory', 'nationalUnits'):
        value = visual_request[key]
        if value is not None and not isinstance(value, dict):
            _fail('RECONCILE_NATIVE_EXACT_VISUAL_REQUEST_REQUIRED')
        result[key] = value is not None
    return result


def guard_native_selection(visual_request, *, source_admission=None):
    """Check native slots, retaining all old gates before any render is allowed.

    A national selection may pass this guard but still fail its unchanged source
    catalog or current-frame layout admission. An optional existing admission
    receipt is checked for consistency, never treated as independent authority.
    """
    selected = _selected(visual_request)
    report = inspect_native_capabilities()
    if source_admission is not None:
        if (not isinstance(source_admission, dict) or source_admission.get('status') != 'CPU_ADMITTED'
                or source_admission.get('scalarControlSelected') is not selected['scalarTerritory']
                or source_admission.get('nationalUnitsSelected') is not selected['nationalUnits']):
            _fail('RECONCILE_NATIVE_SOURCE_ADMISSION_MISMATCH')
    if selected['scalarTerritory']:
        _fail('RECONCILE_NATIVE_SCALAR_COMPOSITION_UNAVAILABLE', {
            'missingNativeSlots': ['SCALAR_PARENT_COMPOSITION_SLOT', 'INTERNAL_BOUNDARY_SEGMENTS',
                'SAME_FRAME_PRE_TERRITORY_TERRAIN_TEXTURE', 'SAME_FRAME_NATIVE_ROLE_COVERAGE'],
            'parentGeographicAreaMayBePresent': True,
            'firstExistingDrawFailure': 'OVERNIGHT_SCALAR_PARENT_COMPOSITION_SLOT_REQUIRED',
            'frozenSource': report['frozenSource'],
            'repairScope': 'NEW_SOURCE_BOUND_NATIVE_COMPOSITION_ADAPTER_REQUIRED',
            'historicalDataFabricated': False, 'gpuVerified': False, 'renderAllowed': False})
    return {**report, 'status': 'NATIVE_GUARD_PASSED', 'selected': selected,
        'sourceAdmissionRequired': any(selected.values()) and source_admission is None,
        'existingSourceAdmissionRetained': True,
        'nationalLayoutOwner': 'UNCHANGED_EXISTING_SOURCE_AND_CURRENT_LAYOUT_ADMISSION',
        'historicalUnitPositionsVerified': False, 'visualQualityApproved': False}


def guard_submission(submission, *, source_admission=None):
    if not isinstance(submission, dict) or not isinstance(submission.get('overnightV3'), dict):
        _fail('RECONCILE_NATIVE_OVERNIGHT_SUBMISSION_REQUIRED')
    return guard_native_selection(submission['overnightV3'].get('visualExtensions'),
        source_admission=source_admission)


if __name__ == '__main__':
    print(json.dumps(inspect_native_capabilities(), ensure_ascii=False, sort_keys=True))
