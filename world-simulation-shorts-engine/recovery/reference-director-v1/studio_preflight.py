"""Opt-in read-only reference readiness over the preserved authenticated Studio.

This is deliberately not a render implementation. A reference request can be
validated and explained, but cannot become a submission, claim, or worker while
the protected renderer and precise source-data gates remain unresolved.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[1]
REQUEST_SCHEMA = 'WORLD_ENGINE_REFERENCE_DIRECTOR_STUDIO_REQUEST_V1'
TARGET_SHA256 = '090c499edd8791e74a0e0dec9f099af92a8d93739c6e9045b2f55a97369009e9'
TARGET_FILE = HERE / 'supplied/REFERENCE_DIRECTOR_TARGET_V1.json'
PARTIAL_INPUT_FILE = HERE / 'REFERENCE_DIRECTOR_INPUT.json'
PARTIAL_INPUT_SHA256 = '4b892aadfb6415088a7a35bba58e9408d50bbd6f140d6e5c74d6f931e68b4dc0'
RENDERER_FILE = ENGINE / 'web/map_infographic_v1/renderer.mjs'
RENDERER_82854AF_SHA256 = 'e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38'
WINDOWS = {'A_CONTEXT': (29, 209), 'B_FOCUS': (209, 389), 'C_BOUNDARY_METRIC': (389, 575)}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


preserved = _load('_rd_preserved_presentation_studio', HERE.parent / 'universal-presentation-v2/studio_adapter.py')
StudioError, server = preserved.StudioError, preserved.server


def selected(value):
    return isinstance(value, dict) and value.get('schema') == REQUEST_SCHEMA


def _sealed_file(path, expected, error_code):
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise StudioError(error_code)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise StudioError(error_code)
    return raw


def reference_readiness(value):
    """Inspect a known server target; never take admission flags from a client."""
    if (not selected(value) or set(value) != {'schema', 'windowId', 'targetSHA256'}
            or not isinstance(value.get('windowId'), str) or value.get('windowId') not in WINDOWS
            or value.get('targetSHA256') != TARGET_SHA256):
        raise StudioError('RD_EXPLICIT_SEALED_WINDOW_REQUEST_REQUIRED', status=400)
    target = json.loads(_sealed_file(TARGET_FILE, TARGET_SHA256, 'RD_SERVER_TARGET_CHANGED'))
    partial = json.loads(_sealed_file(PARTIAL_INPUT_FILE, PARTIAL_INPUT_SHA256, 'RD_SERVER_PARTIAL_INPUT_CHANGED'))
    _sealed_file(RENDERER_FILE, RENDERER_82854AF_SHA256, 'RD_PROTECTED_RENDERER_CHANGED')
    # This exact source was audited: factory.updateCamera accepts only bounds;
    # camera/project and fullscreen terrain UV uniforms are private. Capability
    # is pinned to actual preserved bytes, rather than a user-selectable boolean.
    start, end = WINDOWS[value['windowId']]
    frame_count = end - start
    bindings = partial['dataBindings']
    missing = deepcopy(partial['gate']['missingBindings'])
    available = {key: deepcopy(value) for key, value in bindings.items()
        if key != 'bindingRule' and value and (not isinstance(value, list) or all(value))}
    return {
        'valid': True, 'ready': False, 'renderAllowed': False,
        'scope': 'READ_ONLY_REFERENCE_DIRECTOR_PREFLIGHT_V1',
        'blockers': ['CAPABILITY_EXTENSION_REQUIRED', 'DATA_DETAIL_BLOCKED'],
        'checks': [
            {'name': 'SEALED_TARGET_AND_REQUEST', 'status': 'PASS'},
            {'name': 'BOUNDED_WINDOW_ON_GLOBAL_TIMELINE', 'status': 'PASS'},
            {'name': 'PROTECTED_RENDERER_ORIGINAL_BYTES', 'status': 'PASS'},
            {'name': 'NATIVE_SHARED_ROTATION_PROJECTION_HOOK', 'status': 'BLOCKED',
             'code': 'CAPABILITY_EXTENSION_REQUIRED'},
            {'name': 'REFERENCE_GEOMETRY_AND_DETAIL_SOURCE', 'status': 'BLOCKED',
             'code': 'DATA_DETAIL_BLOCKED'},
        ],
        'window': {'id': value['windowId'], 'sourceFrameRange': [start, end],
            'globalCoreFrameRange': [start - 29, end - 29], 'localFrameRange': [0, frame_count],
            'frameCount': frame_count, 'fps': 30, 'durationSeconds': frame_count / 30,
            'globalSourceFrameRange': [29, 575], 'globalFrameCount': 546,
            'globalDurationSeconds': 18.2, 'maxFramesPerJob': 240, 'resetTimeline': False},
        'totalFrames': frame_count, 'rendererStillProtected': True,
        'rendererSHA256': RENDERER_82854AF_SHA256, 'targetSHA256': TARGET_SHA256,
        'partialInputSHA256': PARTIAL_INPUT_SHA256,
        'requiredNativeCapabilities': ['SHARED_FORWARD_AND_INVERSE_CAMERA_SIMILARITY',
            'TERRAIN_UV_INVERSE_GEOGRAPHY', 'PROJECTED_NATIVE_LABEL_EVENT_CONSUMERS'],
        'missingDataBindings': missing,
        'availableBindings': available,
        'unverifiedClaims': deepcopy(partial['gate']['unverifiedClaims']),
        'additionalDataQualification': ['VERIFIED_DETAIL_POLYGON_AND_BOUNDARY_LINESTRING',
            'VERIFIED_DETAIL_ANCHOR', 'LICENSED_FULL_ENVELOPE_FINE_RESOLUTION_BASEMAP'],
        'requiresGpu': False, 'gpuRenderingVerified': False, 'nvidiaVerified': False,
        'historicalRenderAllowed': False, 'paidRenderAllowed': False,
        'visualQualityApproved': False, 'actualRendererDrawPerformed': False,
        'createsSubmission': False, 'createsClaim': False,
    }


class StudioController(preserved.StudioController):
    def preflight(self, value):
        if not selected(value):
            return super().preflight(value)
        try:
            return reference_readiness(value)
        except StudioError as error:
            return {'valid': False, 'ready': False, 'renderAllowed': False,
                'error': {'code': error.code}, 'requiresGpu': False,
                'gpuRenderingVerified': False, 'historicalRenderAllowed': False,
                'paidRenderAllowed': False, 'visualQualityApproved': False}

    def submit(self, value):
        if not selected(value):
            return super().submit(value)
        # Validate before returning a precise block, but never call _normal,
        # _save_submission, a claim operation, worker, Popen, or legacy fallback.
        result = reference_readiness(value)
        raise StudioError('RD_REFERENCE_RENDER_GATES_BLOCKED', status=409,
            fields=[{'blockers': deepcopy(result['blockers'])}])


def local_application(*, state_root, owner_file, export_root, port, **options):
    """Existing owner/Origin/CSRF server, localhost-only development opt-in.

    No public deployment, reverse-proxy configuration, or auth route is added.
    """
    root = Path(state_root)
    root.mkdir(parents=False, mode=0o700, exist_ok=True)
    controller = StudioController(control_root=root / 'control', export_root=export_root, **options)
    config = server.StudioConfig(root, Path(owner_file), f'http://127.0.0.1:{port}', Path(export_root),
        host='127.0.0.1', port=port, local_test_only=True)
    return server.StudioApplication(config, controller)
