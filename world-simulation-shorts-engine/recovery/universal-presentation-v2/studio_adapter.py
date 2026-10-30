"""Opt-in natural-language/data presentation lane over preserved Studio safety."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REQUEST_SCHEMA = 'WORLD_ENGINE_PRESENTATION_STUDIO_REQUEST_V2'
SCHEMA = 'WORLD_ENGINE_PRESENTATION_STUDIO_SUBMISSION_V2'
PROFILE = 'FREE_UNIVERSAL_PRESENTATION_REVIEW_V2'
TIMELINE_ID = '__timeline__'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Only this isolated module instance dispatches this new source family.
legacy = load('_up2_existing_data_studio', HERE.parent / 'universal-data-pipeline-v1/studio_adapter.py')
manager = load('_up2_preserved_source_manager', HERE.parent / 'universal-source-pipeline-v2/studio_controller.py')
manager.SCHEMA, manager.PROFILE, manager.HERE = SCHEMA, PROFILE, HERE
manager.selected = lambda value: isinstance(value, dict) and value.get('schema') == REQUEST_SCHEMA
StudioError, server = manager.StudioError, legacy.server
canonical, sha = legacy.canonical, legacy.sha


def source_bindings():
    result = []
    for file in sorted([*HERE.glob('*.mjs'), *HERE.glob('*.py'), *HERE.glob('*.json')]):
        if file.is_symlink() or file.resolve().parent != HERE or not file.is_file():
            raise StudioError('UP2_EXECUTION_SOURCE_UNSAFE')
        raw = file.read_bytes()
        result.append({'path': file.relative_to(REPO).as_posix(), 'sha256': sha(raw), 'bytes': len(raw)})
    return result


def node_json(script, payload, *, timeout=90):
    try:
        raw = canonical(payload)
    except (ValueError, TypeError, RecursionError):
        raise StudioError('UP2_FINITE_JSON_INPUT_REQUIRED', status=400) from None
    if len(raw) > 8 * 1024**2:
        raise StudioError('UP2_INPUT_SIZE_LIMIT', status=400)
    try:
        result = subprocess.run(['node', '--input-type=module', '-e', script], input=raw,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise StudioError('UP2_DATA_PROCESSOR_UNAVAILABLE') from None
    if result.returncode or len(result.stdout) > 24 * 1024**2:
        # Only expose a bounded machine code, never a stack/environment value.
        codes = re.findall(rb'\b(?:UP2|REGION)_[A-Z0-9_]{2,100}\b', result.stderr)
        code = codes[-1].decode('ascii') if codes else 'UP2_DATA_PROCESSOR_FAILED'
        raise StudioError(code)
    try:
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise StudioError('UP2_DATA_PROCESSOR_RESULT_INVALID') from None


def compile_prompt(prompt, evidence_registry, *, allow_ten_second_sample=False):
    value = node_json("import{readFileSync}from'node:fs';"
        "const p=JSON.parse(readFileSync(0,'utf8'));"
        "const{analyzePresentationPrompt}=await import(p.module);"
        "process.stdout.write(JSON.stringify(await analyzePresentationPrompt(p.input,{evidenceRegistry:p.registry,allowTenSecondStudioSample:p.allowTenSecondStudioSample})));",
        {'module': (HERE / 'presentation_prompt.mjs').as_uri(), 'input': prompt, 'registry': evidence_registry,
         'allowTenSecondStudioSample': allow_ten_second_sample is True})
    if value.get('schema') != 'WORLD_ENGINE_PRESENTATION_PIPELINE_RESULT_V2':
        raise StudioError('UP2_COMPILER_SCHEMA_INVALID')
    return value


def prepare_runtime(request, cache_root):
    return node_json("import{readFileSync}from'node:fs';"
        "const p=JSON.parse(readFileSync(0,'utf8'));"
        "const{prepareRuntimeRequest}=await import(p.module);"
        "process.stdout.write(JSON.stringify(await prepareRuntimeRequest({request:JSON.parse(p.wireJSON),cacheRoot:p.cacheRoot})));",
        {'module': (HERE / 'capture_presentation.mjs').as_uri(),
         'wireJSON': json.dumps(request, ensure_ascii=False, separators=(',', ':'), allow_nan=False),
         'cacheRoot': str(cache_root)}, timeout=150)


def verify_prepared_sources(prepared, admission=None, prepared_wire=None):
    if (not isinstance(prepared, dict) or admission is not None and any(
            prepared.get(key) != admission.get(key) for key in (
                'sourceQualification', 'sourceQualificationSHA256', 'sourceQualificationWireJSON'))):
        raise StudioError('UP2_STORED_SOURCE_AGGREGATE_CHANGED')
    wire = prepared_wire if prepared_wire is not None else json.dumps(
        prepared, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    try:
        wire_matches = isinstance(wire, str) and json.loads(wire) == prepared
    except (ValueError, TypeError):
        wire_matches = False
    if not wire_matches:
        raise StudioError('UP2_STORED_SOURCE_WIRE_CHANGED')
    result = node_json("import{readFileSync}from'node:fs';"
        "const p=JSON.parse(readFileSync(0,'utf8'));"
        "const{verifyPreparedRuntimeRequest}=await import(p.module);"
        "process.stdout.write(JSON.stringify(await verifyPreparedRuntimeRequest(JSON.parse(p.preparedWireJSON))));",
        {'module': (HERE / 'capture_presentation.mjs').as_uri(), 'preparedWireJSON': wire}, timeout=150)
    if result.get('status') != 'PASS':
        raise StudioError('UP2_STORED_SOURCE_QUALIFICATION_INVALID', fields=[{'code': result.get('code')}])
    return result


def selected_segments(analyzed, scene_id, *, allow_ten_second_sample=False):
    requests = analyzed.get('renderRequests', [])
    if scene_id == TIMELINE_ID:
        if analyzed.get('status') != 'PASS' or analyzed.get('blockedSceneIds'):
            raise StudioError('UP2_COMPLETE_TIMELINE_DATA_REQUIRED', status=422,
                fields=[{'issues': analyzed.get('issues', []), 'blockedSceneIds': analyzed.get('blockedSceneIds', [])}])
        rows = deepcopy(requests)
        end = 0
        for row in rows:
            if row.get('startFrame') != end or type(row.get('endFrame')) is not int or row['endFrame'] <= end:
                raise StudioError('UP2_CONTIGUOUS_TIMELINE_REQUIRED')
            end = row['endFrame']
        maximum = 300 if allow_ten_second_sample is True and analyzed.get('totalFrames') == 300 else 240
        if not rows or not 2 <= end <= maximum:
            raise StudioError('UP2_BOUNDED_TIMELINE_REQUIRED')
        transitions = deepcopy(analyzed.get('transitionPlan', []))
        expected = [{'type': 'CUT', 'frame': row['startFrame']} for row in rows[1:]]
        if transitions != expected:
            raise StudioError('UP2_EXPLICIT_SCENE_CUTS_REQUIRED')
        return rows, end, transitions
    matches = [row for row in requests if row.get('sceneId') == scene_id]
    if len(matches) != 1 or scene_id not in analyzed.get('renderableSceneIds', []):
        raise StudioError('UP2_SELECTED_SCENE_NOT_RENDERABLE', status=422,
            fields=[{'sceneId': scene_id, 'issues': analyzed.get('issues', []), 'sceneResults': analyzed.get('sceneResults', [])}])
    row = deepcopy(matches[0])
    original = [row['startFrame'], row['endFrame']]
    frames = row['endFrame'] - row['startFrame']
    row.update(startFrame=0, endFrame=frames, sourceFrameRange=original)
    return [row], frames, []


def runtime_segment(row):
    fields = ['sceneId', 'startFrame', 'endFrame', 'scene', 'region', 'presentation', 'inputTrace', 'sourceFrameRange']
    return {key: deepcopy(row[key]) for key in fields if key in row}


class StudioController(manager.StudioController):
    def __init__(self, *, control_root, export_root, evidence_registry=None, expected_registry_sha256=None,
                 allow_free_data_review=False, allow_ten_second_sample=False, **kwargs):
        root, exports = Path(control_root), Path(export_root)
        if (not root.is_absolute() or root.is_relative_to(REPO) or root.is_symlink()
                or root.resolve().is_relative_to(exports.resolve()) or exports.resolve().is_relative_to(root.resolve())):
            raise StudioError('UP2_SEPARATE_PRIVATE_STATE_REQUIRED')
        self.registry_file = Path(evidence_registry) if evidence_registry else None
        self.registry_pin = expected_registry_sha256
        self.allow_free_data_review = allow_free_data_review is True
        self.allow_ten_second_sample = allow_ten_second_sample is True
        super().__init__(control_root=root, export_root=exports, source_root=HERE,
            expected_index_sha256=sha(canonical({'schema': PROFILE, 'registryPin': self.registry_pin})),
            image_digest=legacy.BASELINE_IMAGE_PROVENANCE, allow_software_source_review=True)
        with self._cache.PrivateTree(self.control_root) as private:
            with private.child('presentation-sources', create=True):
                pass

    def _registry(self):
        return legacy.StudioController._registry(self)

    def _admit_sources(self, request, bindings):
        identity = sha(canonical({'request': request, 'code': bindings}))
        with self._cache.PrivateTree(self.control_root) as private:
            with private.child('presentation-sources') as sources, sources.lock(wait_seconds=180):
                cached = sources.json(identity + '.json', optional=True)
                if cached:
                    if cached.get('requestSHA256') != sha(canonical(request)) or cached.get('sourceBindings') != bindings:
                        raise StudioError('UP2_SOURCE_ADMISSION_CACHE_INVALID')
                    self._verify_material_files(cached.get('materialFiles'))
                    self._verify_qualification(cached['admission'], request['totalFrames'])
                    verify_prepared_sources(cached.get('prepared'), cached['admission'], cached.get('preparedWireJSON'))
                    return cached['admission']
                prepared = prepare_runtime(request, self.control_root / 'presentation-sources' / (identity + '-crop'))
                qualification = prepared.get('sourceQualification')
                qualification_sha = prepared.get('sourceQualificationSHA256')
                if (prepared.get('totalFrames') != request['totalFrames'] or not isinstance(qualification, dict)
                        or not re.fullmatch(r'[a-f0-9]{64}', str(qualification_sha))):
                    raise StudioError('UP2_ACTUAL_SOURCE_QUALIFICATION_REQUIRED')
                admission = {'status': 'PASS', 'sourceQualification': qualification,
                    'sourceQualificationSHA256': qualification_sha, 'preparedBeforeClaim': True,
                    'sourceQualificationWireJSON': prepared.get('sourceQualificationWireJSON'),
                    'sourceCredits': [{'sourceId': row.get('regionEvidence', {}).get('sourceId'),
                        'attribution': row.get('regionEvidence', {}).get('attribution'),
                        'license': row.get('regionEvidence', {}).get('license'),
                        'sourceURL': row.get('sourceStyle', {}).get('sourceOriginal', {}).get('url')}
                        for row in prepared.get('segments', [])],
                    'actualDrawPerformed': False}
                self._verify_qualification(admission, request['totalFrames'])
                material_files = self._verify_material_files(prepared.get('sourceBindings'))
                verify_prepared_sources(prepared, admission)
                sources.write_json(identity + '.json', {'requestSHA256': sha(canonical(request)),
                    'sourceBindings': bindings, 'materialFiles': material_files, 'admission': admission,
                    'prepared': prepared, 'preparedWireJSON': json.dumps(prepared,
                        ensure_ascii=False, separators=(',', ':'), allow_nan=False)})
                return admission

    def _verify_qualification(self, admission, total_frames):
        if not isinstance(admission, dict) or admission.get('status') != 'PASS':
            raise StudioError('UP2_QUALIFICATION_RECEIPT_INVALID')
        wire = admission.get('sourceQualificationWireJSON')
        try:
            valid = (isinstance(wire, str) and sha(wire.encode()) == admission.get('sourceQualificationSHA256')
                and isinstance(admission.get('sourceQualification'), dict)
                and json.loads(wire) == admission.get('sourceQualification')
                and admission['sourceQualification'].get('schema') == 'WORLD_ENGINE_PRESENTATION_SOURCES_V2'
                and admission['sourceQualification'].get('totalFrames') == total_frames)
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise StudioError('UP2_QUALIFICATION_SEAL_MISMATCH')

    def _verify_material_files(self, rows):
        if not isinstance(rows, list) or not rows:
            raise StudioError('UP2_ACTUAL_MATERIAL_FILES_REQUIRED')
        bound = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('path'), str):
                raise StudioError('UP2_MATERIAL_BINDING_INVALID')
            file = Path(row['path'])
            if not file.is_absolute():
                file = REPO / file
            if (not file.is_relative_to(REPO) and not file.is_relative_to(self.control_root / 'presentation-sources')
                    or file.resolve() != file
                    or any(part.is_symlink() for part in (file, *file.parents)) or not file.is_file()
                    or not re.fullmatch(r'[a-f0-9]{64}', str(row.get('sha256')))
                    or sha(file.read_bytes()) != row['sha256']):
                raise StudioError('UP2_MATERIAL_FILE_CHANGED_OR_UNSAFE')
            bound.append({'path': str(file), 'sha256': row['sha256']})
        return bound

    def _normal(self, value):
        if (not isinstance(value, dict) or set(value) != {'schema', 'prompt', 'sceneId'}
                or value.get('schema') != REQUEST_SCHEMA or not isinstance(value.get('prompt'), dict)
                or not isinstance(value.get('sceneId'), str)):
            raise StudioError('UP2_EXPLICIT_PRESENTATION_INPUT_REQUIRED', status=400)
        extended = getattr(self, 'allow_ten_second_sample', False)
        analyzed = (compile_prompt(value['prompt'], self._registry(), allow_ten_second_sample=True)
                    if extended else compile_prompt(value['prompt'], self._registry()))
        simulation = analyzed.get('simulationType')
        if simulation not in {'GENERAL', 'FICTIONAL', 'HISTORICAL'}:
            raise StudioError('UP2_SIMULATION_TYPE_REQUIRED', status=422,
                fields=[{'issues': analyzed.get('issues', [])}])
        rows, total, cuts = (selected_segments(analyzed, value['sceneId'], allow_ten_second_sample=True)
                            if extended else selected_segments(analyzed, value['sceneId']))
        for row in rows:
            scene = row.get('scene', {})
            if (scene.get('metadata', {}).get('schema') != 'PLANNER_SCENE_JSON_V1'
                    or scene.get('metadata', {}).get('output') != {'width': 1080, 'height': 1920, 'fps': 30, 'audio': False}
                    or scene.get('timing', {}).get('total_frames') != row['endFrame'] - row['startFrame']):
                raise StudioError('UP2_CANONICAL_SCENE_AND_FRAME_BINDING_REQUIRED')
        runtime = {'schema': 'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2', 'segments': [runtime_segment(row) for row in rows],
            'totalFrames': total, 'transitions': cuts, 'sourceInputSHA256': analyzed.get('inputSHA256'),
            'inputTrace': deepcopy(analyzed.get('inputTrace', []))}
        if extended and total == 300:
            runtime['durationSeconds'] = 10
        # Strings preserve the actual Planner member ordering across sorted
        # private JSON persistence. Semantic and wire hashes are independent.
        wire = json.dumps(runtime, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        wire_sha, semantic_sha = sha(wire.encode()), sha(canonical(runtime))
        bindings = source_bindings()
        historical = simulation == 'HISTORICAL'
        admission = {'status': 'BLOCKED', 'reason': 'UP2_HISTORICAL_G3_REMAINS_BLOCKED'} if historical else self._admit_sources(runtime, bindings)
        request_sha = sha(canonical(value))
        identity = {'requestSHA256': request_sha, 'runtimeSemanticSHA256': semantic_sha,
            'runtimeWireSHA256': wire_sha, 'sourceAdmission': admission, 'sourceBindings': bindings,
            'sourceRegistrySHA256': self.registry_pin}
        result = {'schema': SCHEMA, 'title': str(value['prompt'].get('prompt', 'Presentation review'))[:180],
            'profile': PROFILE, 'videoPlan': runtime, 'sfx': {'enabled': False},
            'sourcePipeline': {'ready': not historical and admission['status'] == 'PASS',
                'mode': 'FREE_PRESENTATION_REVIEW', 'scope': PROFILE, 'simulationType': simulation,
                'blockers': ['UP2_HISTORICAL_G3_REMAINS_BLOCKED'] if historical else [],
                'totalFrames': total, 'fps': 30, 'startFrame': 0, 'segmentCount': len(rows),
                'requestSHA256': request_sha, 'originalRequest': deepcopy(value),
                'runtimePayload': runtime, 'runtimeRequestWireJSON': wire,
                'runtimeSemanticSHA256': semantic_sha, 'runtimeWireSHA256': wire_sha,
                'compilerInputSHA256': analyzed.get('inputSHA256'), 'sourceBindings': bindings,
                'sourceRegistrySHA256': self.registry_pin, 'sourceAdmission': admission,
                'captureSignature': sha(canonical(identity)), 'explicitSelectedSceneId': value['sceneId'],
                'blockedSceneIds': analyzed.get('blockedSceneIds', []), 'validation': {
                    'status': analyzed.get('status'), 'issues': analyzed.get('issues', []),
                    'clarifications': analyzed.get('clarifications', []), 'sceneResults': analyzed.get('sceneResults', [])},
                'actualRuntime': 'SOURCE_CHECKOUT_NOT_OCI_IMAGE'}}
        if extended and total == 300:
            result['sourcePipeline']['durationSeconds'] = 10
        return result

    def _preflight_record(self, root, record):
        pipeline = record['submission']['sourcePipeline']
        checks = [
            {'name': 'SERVER_FREE_REVIEW_OPT_IN', 'status': 'PASS' if self.allow_free_data_review else 'BLOCKED'},
            {'name': 'EXPLICIT_DATA_AND_PRESENTATION_VALIDATION', 'status': 'PASS' if pipeline['ready'] else 'BLOCKED'},
            {'name': 'ACTUAL_SOURCE_COVERAGE_BEFORE_CLAIM', 'status': pipeline['sourceAdmission']['status']},
            {'name': 'SOFTWARE_DEPENDENCIES', 'status': 'PASS' if all(shutil.which(v) for v in ('node', 'ffmpeg', 'ffprobe')) else 'BLOCKED'},
            {'name': 'PRIVATE_DISK_RESERVE', 'status': 'PASS' if shutil.disk_usage(self.control_root).free >= 2 * 1024**3 else 'BLOCKED'},
        ]
        checks += [{'name': 'DATA_GATE', 'status': 'BLOCKED', 'code': code} for code in pipeline['blockers']]
        return {'valid': True, 'ready': all(row['status'] == 'PASS' for row in checks), 'checks': checks,
            'requiresGpu': False, 'gpuRenderingVerified': False, 'historicalRenderAllowed': False,
            'paidRenderAllowed': False, 'scope': PROFILE, 'totalFrames': pipeline['totalFrames'],
            'totalScenes': pipeline['segmentCount'], 'maxWallSeconds': 900, 'maxRetries': 0,
            'selectedSceneId': pipeline['explicitSelectedSceneId'], 'blockedSceneIds': pipeline['blockedSceneIds'],
            'captureSignature': pipeline['captureSignature'], 'validation': pipeline['validation'],
            'sourceAdmission': pipeline['sourceAdmission'], 'actualRuntime': 'SOURCE_CHECKOUT_NOT_OCI_IMAGE',
            'visualQualityApproved': False}

    def preflight(self, value):
        try:
            submission = self._normal(value)
            with self._cache.PrivateTree(self.control_root) as root:
                return self._preflight_record(root, {'submission': submission})
        except StudioError as error:
            return {'valid': False, 'ready': False, 'error': {'code': error.code, 'fields': error.fields},
                'requiresGpu': False, 'gpuRenderingVerified': False, 'historicalRenderAllowed': False, 'paidRenderAllowed': False}

    def _raw_status(self, job_id):
        state = super()._raw_status(job_id)
        with self._cache.PrivateTree(self.control_root) as root:
            if self._source_job(root, job_id):
                with root.child('source-jobs') as jobs, jobs.child(job_id) as job:
                    package = job.json('compiledpackage.json')
                pipeline = package.get('sourcePipeline', {})
                if package.get('schema') == SCHEMA:
                    state = {**state, 'totalScenes': pipeline['segmentCount'],
                        'completedScenes': sum(row['endFrame'] <= state.get('processedFrames', 0)
                            for row in pipeline['runtimePayload']['segments'])}
        return state


def local_application(*, state_root, owner_file, export_root, port, **options):
    root = Path(state_root)
    root.mkdir(parents=False, mode=0o700, exist_ok=True)
    controller = StudioController(control_root=root / 'control', export_root=export_root, **options)
    config = server.StudioConfig(root, Path(owner_file), f'http://127.0.0.1:{port}', Path(export_root),
        host='127.0.0.1', port=port, local_test_only=True)
    return server.StudioApplication(config, controller)
