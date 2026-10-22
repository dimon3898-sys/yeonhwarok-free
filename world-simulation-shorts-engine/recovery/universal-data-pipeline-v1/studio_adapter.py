"""Opt-in, authenticated free-data Studio adapter over unchanged job management.

Only this source namespace is selected. Old G1/G2 normalizers and production
profiles are neither widened nor used as an unreviewed fallback.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REQUEST_SCHEMA = 'WORLD_ENGINE_DATA_STUDIO_REQUEST_V1'
SCHEMA = 'WORLD_ENGINE_DATA_STUDIO_SUBMISSION_V1'
PROFILE = 'FREE_UNIVERSAL_DATA_REVIEW_V1'
BASELINE_IMAGE_PROVENANCE = 'sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5'
REGIONS = frozenset({'namibia_desert_coast', 'europe_germany', 'south_america_chile', 'korean_peninsula', 'nepal_himalaya'})


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


# A separate module instance changes only this extension's dispatch constants.
# The preserved source files and their normally imported module remain untouched.
manager = load('_udp_preserved_source_studio_manager', HERE.parent / 'universal-source-pipeline-v2/studio_controller.py')
manager.SCHEMA, manager.PROFILE, manager.HERE = SCHEMA, PROFILE, HERE
manager.selected = lambda value: isinstance(value, dict) and value.get('schema') == REQUEST_SCHEMA
StudioError = manager.StudioError
server = load('_udp_preserved_authenticated_http', HERE.parent / 'production-studio-mvp-v1/server.py')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_bindings():
    files = sorted([*HERE.glob('*.mjs'), *HERE.glob('*.py')])
    result = []
    for file in files:
        if file.is_symlink() or not file.is_file() or file.resolve().parent != HERE:
            raise StudioError('UDP_EXECUTION_SOURCE_UNSAFE')
        raw = file.read_bytes()
        result.append({'path': file.relative_to(REPO).as_posix(), 'sha256': sha(raw), 'bytes': len(raw)})
    return result


def compile_prompt(prompt, evidence_registry):
    """Run the existing compiler module without writing files or trusting flags."""
    payload = canonical({'input': prompt, 'evidenceRegistry': evidence_registry})
    if len(payload) > 4 * 1024**2:
        raise StudioError('UDP_INPUT_SIZE_LIMIT', status=400)
    script = ("import{readFileSync}from'node:fs';"
              "const p=JSON.parse(readFileSync(0,'utf8'));"
              "const m=await import(process.argv[1]);"
              "process.stdout.write(JSON.stringify(m.analyzePrompt(p.input,{evidenceRegistry:p.evidenceRegistry}))); ")
    try:
        completed = subprocess.run(['node', '--input-type=module', '-e', script, (HERE / 'prompt_pipeline.mjs').as_uri()],
            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise StudioError('UDP_COMPILER_UNAVAILABLE') from None
    if completed.returncode or len(completed.stdout) > 8 * 1024**2:
        raise StudioError('UDP_COMPILER_FAILED')
    try:
        result = json.loads(completed.stdout)
        if result.get('schema') != 'WORLD_ENGINE_DATA_PIPELINE_RESULT_V1':
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise StudioError('UDP_COMPILER_RESULT_INVALID') from None


class StudioController(manager.StudioController):
    def __init__(self, *, control_root, export_root, evidence_registry=None, expected_registry_sha256=None,
                 allow_free_data_review=False, **kwargs):
        root, exports = Path(control_root), Path(export_root)
        if (not root.is_absolute() or root.is_relative_to(REPO) or root.is_symlink()
                or root.resolve().is_relative_to(exports.resolve()) or exports.resolve().is_relative_to(root.resolve())):
            raise StudioError('UDP_SEPARATE_PRIVATE_STATE_REQUIRED')
        self.registry_file = Path(evidence_registry) if evidence_registry else None
        self.registry_pin = expected_registry_sha256
        self.allow_free_data_review = allow_free_data_review is True
        super().__init__(control_root=root, export_root=exports, source_root=HERE,
            expected_index_sha256=sha(canonical({'schema': PROFILE, 'registryPin': self.registry_pin})),
            image_digest=BASELINE_IMAGE_PROVENANCE, allow_software_source_review=True)

    def _registry(self):
        if self.registry_file is None:
            return []
        file = self.registry_file
        if not file.is_absolute() or any(p.is_symlink() for p in (file, *file.parents)) or not file.is_file():
            raise StudioError('UDP_SERVER_EVIDENCE_REGISTRY_REQUIRED')
        raw = file.read_bytes()
        if not re.fullmatch(r'[a-f0-9]{64}', str(self.registry_pin)) or sha(raw) != self.registry_pin:
            raise StudioError('UDP_SERVER_EVIDENCE_REGISTRY_CHANGED')
        try:
            return json.loads(raw)
        except ValueError:
            raise StudioError('UDP_SERVER_EVIDENCE_REGISTRY_INVALID') from None

    def _normal(self, value):
        if (not isinstance(value, dict) or set(value) != {'schema', 'prompt', 'sceneId'}
                or value['schema'] != REQUEST_SCHEMA or not isinstance(value['sceneId'], str)):
            raise StudioError('UDP_EXPLICIT_DATA_SCENE_SELECTION_REQUIRED', status=400)
        prompt = value['prompt']
        if not isinstance(prompt, (dict, str)):
            raise StudioError('UDP_STRUCTURED_PROMPT_REQUIRED', status=400)
        analyzed = compile_prompt(prompt, self._registry())
        matches = [row for row in analyzed.get('renderRequests', []) if row.get('sceneId') == value['sceneId']]
        accepted = value['sceneId'] in analyzed.get('renderableSceneIds', [])
        if not accepted or len(matches) != 1:
            raise StudioError('UDP_SELECTED_SCENE_NOT_RENDERABLE', status=422,
                fields=[{'sceneId': value['sceneId'], 'issues': analyzed.get('issues', []), 'sceneResults': analyzed.get('sceneResults', [])}])
        selected = deepcopy(matches[0])
        scene = selected.get('scene', {})
        if (not isinstance(scene, dict) or scene.get('metadata', {}).get('schema') != 'PLANNER_SCENE_JSON_V1'):
            raise StudioError('UDP_COMPILER_SCENE_INVALID')
        frames = scene.get('timing', {}).get('total_frames')
        if scene.get('metadata', {}).get('output') != {'width': 1080, 'height': 1920, 'fps': 30, 'audio': False}:
            raise StudioError('UDP_CANONICAL_SOFTWARE_OUTPUT_REQUIRED')
        if type(frames) is not int or not 2 <= frames <= 240 or scene['timing'].get('fps') != 30:
            raise StudioError('UDP_BOUNDED_SOFTWARE_FRAMES_REQUIRED')
        # Existing historical G3 remains blocked. No prompt-level VERIFIED flag,
        # accepted chronology or new data analysis can authorize its pixel lane.
        simulation = analyzed.get('simulationType')
        if simulation not in {'GENERAL', 'FICTIONAL', 'HISTORICAL'}:
            raise StudioError('UDP_SIMULATION_TYPE_REQUIRED')
        history_blocked = simulation == 'HISTORICAL'
        region = selected.get('renderSettings', {}).get('sourceRegionId')
        if region not in REGIONS:
            raise StudioError('UDP_SOURCE_REGION_UNSUPPORTED')
        request_hash = sha(canonical(value))
        scene_hash = sha(canonical(scene))
        # The preserved Scene validator checks canonical *member order* inside
        # geometry records using JSON.stringify. PrivateTree storage deliberately
        # sorts JSON keys, so preserve the compiler's validated wire ordering as
        # a string while independently binding its semantic hash.
        scene_wire = json.dumps(scene, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        scene_wire_hash = sha(scene_wire.encode())
        selected['sceneWireJSON'] = scene_wire
        bindings = source_bindings()
        identity = {'requestSHA256': request_hash, 'sceneSHA256': scene_hash, 'sceneWireSHA256': scene_wire_hash,
            'compilerInputSHA256': analyzed.get('inputSHA256'), 'registrySHA256': self.registry_pin,
            'sourceRegionId': region, 'executionSourceBindings': bindings}
        return {'schema': SCHEMA, 'title': str(scene.get('subject', {}).get('label') or value['sceneId'])[:180],
            'profile': PROFILE, 'videoPlan': scene, 'sfx': {'enabled': False},
            'sourcePipeline': {'ready': not history_blocked, 'mode': 'FREE_DATA_REVIEW', 'scope': PROFILE,
                'simulationType': simulation, 'blockers': ['UDP_HISTORICAL_G3_REMAINS_BLOCKED'] if history_blocked else [],
                'totalFrames': frames, 'fps': 30, 'startFrame': 0, 'requestSHA256': request_hash,
                'originalRequest': deepcopy(value), 'runtimePayload': selected,
                'sceneSHA256': scene_hash, 'sceneWireSHA256': scene_wire_hash, 'compilerInputSHA256': analyzed.get('inputSHA256'),
                'sourceBindings': bindings, 'sourceRegistrySHA256': self.registry_pin,
                'captureSignature': sha(canonical(identity)), 'blockedSceneIds': analyzed.get('blockedSceneIds', []),
                'explicitSelectedSceneId': value['sceneId'], 'validation': {
                    'status': analyzed.get('status'), 'sceneResults': analyzed.get('sceneResults', []),
                    'issues': analyzed.get('issues', [])}, 'actualRuntime': 'SOURCE_CHECKOUT_NOT_OCI_IMAGE'}}

    def _preflight_record(self, root, record):
        pipeline = record['submission']['sourcePipeline']
        checks = [
            {'name': 'SERVER_FREE_REVIEW_OPT_IN', 'status': 'PASS' if self.allow_free_data_review else 'BLOCKED'},
            {'name': 'EXPLICIT_SCENE_DATA_VALIDATION', 'status': 'PASS' if pipeline['ready'] else 'BLOCKED'},
            {'name': 'SOFTWARE_REVIEW_DEPENDENCIES', 'status': 'PASS' if all(shutil.which(v) for v in ('node', 'ffmpeg', 'ffprobe')) else 'BLOCKED'},
            {'name': 'PRIVATE_DISK_RESERVE', 'status': 'PASS' if shutil.disk_usage(self.control_root).free >= 2 * 1024**3 else 'BLOCKED'},
        ]
        for code in pipeline['blockers']:
            checks.append({'name': 'DATA_GATE', 'status': 'BLOCKED', 'code': code})
        return {'valid': True, 'ready': all(row['status'] == 'PASS' for row in checks), 'checks': checks,
            'requiresGpu': False, 'gpuRenderingVerified': False, 'historicalRenderAllowed': False,
            'paidRenderAllowed': False, 'scope': PROFILE, 'totalFrames': pipeline['totalFrames'],
            'maxWallSeconds': 900, 'maxRetries': 0, 'captureSignature': pipeline['captureSignature'],
            'validation': pipeline['validation'], 'selectedSceneId': pipeline['explicitSelectedSceneId'],
            'blockedSceneIds': pipeline['blockedSceneIds'], 'partialSelectionExplicit': True,
            'actualRuntime': 'SOURCE_CHECKOUT_NOT_OCI_IMAGE', 'visualQualityApproved': False}

    def preflight(self, value):
        try:
            submission = self._normal(value)
            with self._cache.PrivateTree(self.control_root) as root:
                return self._preflight_record(root, {'submission': submission})
        except StudioError as error:
            return {'valid': False, 'ready': False, 'error': {'code': error.code, 'fields': error.fields},
                'requiresGpu': False, 'gpuRenderingVerified': False, 'historicalRenderAllowed': False, 'paidRenderAllowed': False}


def local_application(*, state_root, owner_file, export_root, port, **options):
    """Preserved real Studio HTTP/auth service; loopback-only test deployment."""
    state_root = Path(state_root)
    state_root.mkdir(parents=False, exist_ok=True, mode=0o700)
    controller = StudioController(control_root=state_root / 'control', export_root=export_root, **options)
    config = server.StudioConfig(state_root, Path(owner_file), f'http://127.0.0.1:{port}', Path(export_root),
        host='127.0.0.1', port=port, local_test_only=True)
    return server.StudioApplication(config, controller)
