"""Versioned GPU profile over unchanged Studio auth/consent/budget/claims."""
from copy import deepcopy
from pathlib import Path
import sys
import re
import subprocess
import json

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from common import PLAN, PROFILE, HISTORY_PROFILE, REQUEST, RECOVERY, canonical, duration_contract, load, mvp, sha, verify_manifest

# Closed source-literal vocabulary from presentation_prompt.mjs, prompt_pipeline.mjs,
# and presentation_plan.mjs at af934796. Unknown values never become log text.
_UP2_CODES = frozenset("""
ACTUAL_NEW_REGION_SOURCE_QUALIFICATION_REQUIRED
ACTUAL_PROVIDER_QUALIFICATION_PASS_CAMERA_ENVELOPE_GATE_STILL_REQUIRED AMBIGUOUS_NATIVE_CONTEXT
AMBIGUOUS_NL_DURATION AMBIGUOUS_NL_FPS ANTIMERIDIAN_SEGMENT AREA_REVEAL ARRAY_REQUIRED AS_WRITTEN
ATTACHED_DATA_REQUIRED BOUNDED_COMPOSITE_PREVIEW_LIMIT
BOUNDED_KOREAN_ENGLISH_GRAMMAR_AND_SUPPLIED_ENTITY_LINKING BOUNDED_PREVIEW_FRAME_BUDGET
BOUNDED_SCENE_CLAUSE_SCOPE CAMERA_INTENT_REQUIRED CAMERA_MOVE
CLI_EXPECTS_INPUT_OUTPUT_AND_OPTIONAL_EVIDENCE_REGISTRY CLI_INPUT_REQUIRED
CONTIGUOUS_HALF_OPEN_TIMELINE COORDINATE_ARRAY_REQUIRED COORDINATE_RANGE
CURRENT_PROJECTION_NATIVE_RASTER_MASK_NO_MODEL_BOX_SUBSTITUTION CUT_BOUNDARY_MISMATCH
CYCLIC_SCENE_DEPENDENCY DEPENDENCY_BLOCKED DEPENDENCY_REFERENCE DOCUMENTED_DISPLAY_DEFAULT
DUPLICATE_ID DURATION_FRAME_BINDING EVENT_HIGHLIGHT EVIDENCE_ARRAY_REQUIRED
EVIDENCE_DATASET_NOT_REVIEWED EVIDENCE_DATE_MISMATCH EVIDENCE_GEOMETRY_MISMATCH
EVIDENCE_ID_LIST_REQUIRED EVIDENCE_NOT_ADMITTED EVIDENCE_SCOPE_INSUFFICIENT EVIDENCE_SOURCE_MISMATCH
EXACT_FRAME_BUDGET_DISPLAY_ALLOCATION EXISTING_AREA_V3 EXISTING_FLOW_V2
EXPLICIT_CURRENT_FACTORY_PROJECTION_OVER_UNCHANGED_MODEL_TIME EXPLICIT_EVENT_LOCATION_REQUIRED
EXPLICIT_LABEL_CONSUMER_WITH_SUPPLIED_LOCATION_EVENT_AND_FRAME_BINDINGS
EXPLICIT_MATCHED_LEGACY_SOURCE_SELECTION EXPLICIT_PUBLIC_AREA_OPERATION_MODE
EXPLICIT_REGION_REQUIRED EXPLICIT_SCENE_ID_OR_ORDINAL_IN_CLAUSE EXPLICIT_USER_DEFINED_SIMULATION
FACTS_REQUIRED FAMILY_NOT_CONNECTED FEATURE_HAS_NO_PIXEL_CONSUMER FICTION_MODE_BINDING
FINAL_ZOOM_OUT_NOT_ADMITTED FLOW_GRAPHIC_GPU_LIMIT FLOW_GRAPHIC_VERTEX_LIMIT FPS_RANGE
FREE_NATURAL_LANGUAGE_NOT_SUPPORTED FRONT_LINE FULL_TERRITORY HIGHLIGHT_CAPACITY
HISTORY_MODE_BINDING IDENTIFIER_REQUIRED INPUT_COMPLEXITY_LIMIT INPUT_OBJECT_OR_TEXT_REQUIRED
INPUT_OBJECT_REQUIRED INPUT_TOO_LARGE INTEGER_DETERMINISTIC ISO_DATE_REQUIRED
JSON_ACCESSOR_NOT_ALLOWED JSON_ARRAY_DELIMITER_REQUIRED JSON_COLON_REQUIRED
JSON_OBJECT_DELIMITER_REQUIRED JSON_OBJECT_KEY_REQUIRED JSON_VALUE_REQUIRED
LEGACY_SOURCE_SELECTION_CONFLICT LINE_METRIC LINE_METRIC_DATA_REQUIRED LOCATION_HIGHLIGHT
MODEL_FIXED_V5_ONLY_NOT_CURRENT_MOVING_CAMERA MOVING_PROJECTION_READY
NATIVE_CONTEXT_COUNTRY_BINDING_MISSING NATIVE_CONTEXT_COUNTRY_LIST_CONFLICT
NATIVE_CONTEXT_LOCATION_BINDING_MISSING NATIVE_CONTEXT_PRECEDENCE_CONFLICT
NATIVE_CONTEXT_REGION_COUNTRY_CONFLICT NATURAL_CAMERA_MODE_CONFLICT NATURAL_CAMERA_MOTION_CONFLICT
NATURAL_CONNECTION_NOT_IN_ATTACHED_DATA NATURAL_COORDINATE_BINDING_REQUIRED
NATURAL_COORDINATE_INVALID NATURAL_DATE_INVALID NATURAL_DATE_OUTSIDE_ATTACHED_DATA
NATURAL_ENTITY_LINKING_LIMIT NATURAL_LANGUAGE NATURAL_LANGUAGE_COMPOUND_DURATION
NATURAL_LANGUAGE_DATA_CONFLICT NATURAL_LANGUAGE_EXPLICIT_SCALAR NATURAL_LANGUAGE_EXPLICIT_SPAN
NATURAL_LANGUAGE_FIRST_CLAUSE_DISPLAY_ONLY NATURAL_LANGUAGE_REFERENCE_TO_SUPPLIED_LOCATION
NATURAL_LANGUAGE_REFERENCE_TO_SUPPLIED_ROUTE NATURAL_LOCATION_AMBIGUOUS
NATURAL_LOCATION_DATA_REQUIRED NATURAL_PROMPT_TEXT_REQUIRED NATURAL_REGION_CENTER_CONFLICT
NATURAL_SCENE_REFERENCE_MISSING NATURAL_ZOOM_PROFILE_CONFLICT NEEDS_INPUT
NL_CITY_HIGHLIGHT_INTENT_AND_SUPPLIED_LOCATION_IDS NL_DISPLAY_INTENT_FRAMED_FROM_SUPPLIED_GEOMETRY
NL_FOLLOW_INTENT_AND_SUPPLIED_ROUTE_REFERENCE NL_TRANSITION_INTENT_AND_SUPPLIED_SCENE_BOUNDARIES
NONFINITE_JSON_NUMBER NOT_REQUESTED OBJECT_REQUIRED ONLY_CUT_TRANSITION_CONNECTED
PLAIN_ACYCLIC_JSON_REQUIRED PLAIN_JSON_OBJECT_REQUIRED PLANNER_FACTS_V1 PLANNER_SCENE_JSON_V1
PRESENTATION_ACTUAL_MOVING_CAMERA_STATE_REQUIRED
PRESENTATION_ALREADY_VISIBLE_AREA_WITHOUT_EVENT_PREFIX_REQUIRED
PRESENTATION_BOUNDARY_GEOMETRY_REQUIRED PRESENTATION_BOUNDARY_SOURCE_REQUIRED
PRESENTATION_BOUNDARY_STATE_REQUIRED PRESENTATION_CAMERA PRESENTATION_CAMERA_MODE_UNSUPPORTED
PRESENTATION_CAMERA_OBJECT_REQUIRED PRESENTATION_CAMERA_UNKNOWN_FIELD
PRESENTATION_CLI_ARGUMENTS_INVALID PRESENTATION_CLI_INPUT_REQUIRED
PRESENTATION_COMPLETE_KEYFRAME_RANGE_REQUIRED PRESENTATION_CONTINUITY_EXPLICIT_STATE_COLOR_REQUIRED
PRESENTATION_CONTINUITY_PREVIOUS_AREA_REQUIRED PRESENTATION_CURRENT_PROJECTION_BINDING_FAILED
PRESENTATION_CURRENT_PROTECTED_RESERVATION_INVALID PRESENTATION_CUT_PROVIDED_STATE_DISCONTINUITY
PRESENTATION_CUT_REQUIRED PRESENTATION_CUT_STATE_TIME_REVERSED
PRESENTATION_DETAIL_ADMISSION_EXCEEDED PRESENTATION_FAKE_LOCK_REJECTED
PRESENTATION_FINAL_ENDPOINT_CLOSEST_REQUIRED PRESENTATION_FOLLOW_ENGINE_REQUIRED
PRESENTATION_FOLLOW_KEYFRAME_CONFLICT PRESENTATION_FOLLOW_RANGE_INVALID
PRESENTATION_FOLLOW_SUPPLIED_ROUTE_REQUIRED PRESENTATION_GENUINE_MODEL_CAMERA_REQUIRED
PRESENTATION_HIGHLIGHT PRESENTATION_HIGHLIGHT_CAPACITY PRESENTATION_HIGHLIGHT_ID_INVALID
PRESENTATION_HIGHLIGHT_LOCATION_REQUIRED PRESENTATION_HIGHLIGHT_OBJECT_REQUIRED
PRESENTATION_HIGHLIGHT_TIMING_INVALID PRESENTATION_HIGHLIGHT_UNKNOWN_FIELD
PRESENTATION_INITIAL_VISIBILITY_UNSUPPORTED PRESENTATION_KEYFRAME PRESENTATION_KEYFRAMES_REQUIRED
PRESENTATION_KEYFRAME_FIELD_CONFLICT PRESENTATION_KEYFRAME_OBJECT_REQUIRED
PRESENTATION_KEYFRAME_ORDER_INVALID PRESENTATION_KEYFRAME_RANGE_INVALID
PRESENTATION_KEYFRAME_UNKNOWN_FIELD PRESENTATION_MODEL_CAMERA_STATE_REQUIRED
PRESENTATION_NONUNIFORM_PROJECTION_UNSUPPORTED PRESENTATION_OBJECT_FULL_ROI_OUTSIDE_SAFE
PRESENTATION_OBJECT_REQUIRED PRESENTATION_PROMPT_SCHEMA_REQUIRED PRESENTATION_PULSE_OUTSIDE_SAFE
PRESENTATION_ROUTE_FULL_FOOTPRINT_OUTSIDE_SAFE PRESENTATION_SCENE_MUTATION
PRESENTATION_SCENE_TIMING_REQUIRED PRESENTATION_SOURCE_COVERAGE_FAILED
PRESENTATION_STATE_COLOR_BINDING_INVALID PRESENTATION_TERRITORY_COLOR_OBJECT_REQUIRED
PRESENTATION_TERRITORY_COLOR_UNKNOWN_FIELD PRESENTATION_TERRITORY_PALETTE_INVALID
PRESENTATION_TRANSITION PRESENTATION_TRANSITION_ARRAY_REQUIRED
PRESENTATION_TRANSITION_OBJECT_REQUIRED PRESENTATION_TRANSITION_UNKNOWN_FIELD
PRESENTATION_UNKNOWN_FIELD PRESERVED_REVEAL_DEFAULT PRESERVE_PROVIDED PREVIEW_FPS PREVIEW_RESOLUTION
PROMPT_SCHEMA_REQUIRED REGIONAL_SCALE_ONLY REGION_SOURCE_NOT_ADMITTED REQUIRED_FIELD
RESERVED_JSON_KEY REVERSED_TIME_RANGE REVIEWED_EVIDENCE_REQUIRED ROUTE_DATA_REQUIRED ROUTE_FOLLOW
ROUTE_FOLLOW_DYNAMIC_ZOOM_NOT_CONNECTED ROUTE_FOLLOW_REFERENCE_REQUIRED SCENES_REQUIRED
SCENE_FRAME_BUDGET_MISMATCH SCENE_ID_UNIQUE SCENE_TIMING_FRAME_MISMATCH SCENE_TRANSITION
SECONDARY_CONTEXT_NOT_CONNECTED SERVER_EVIDENCE_BINDING SIMULATION_TYPE_REQUIRED
SINGLE_JSON_FENCE_REQUIRED SOURCE_REGION_NOT_AVAILABLE SOURCE_STATE_CONTINUITY_CONFIRMED
SPARSE_JSON_ARRAY_NOT_ALLOWED SUPPLIED_LOCATION_CONNECTION
SUPPLIED_SUBJECT_ALIAS_FOR_EXISTING_COMPILER SYNTHETIC_TEST TERRITORY_AND_FRONT_STATES_REQUIRED
TERRITORY_CHANGE TERRITORY_DATA_REQUIRED TOPIC_REQUIRED TOTAL_FRAME_MISMATCH TRAILING_JSON_CONTENT
TRANSITION_ARRAY_REQUIRED UNCHANGED_COMPILE_AREA_PLAN_PUBLIC_OPERATIONS UNCHANGED_DATA_PIPELINE_V1
UNCHANGED_FLOW_V2_AT_GENUINE_FIXED_V5_FRAME UNCHANGED_REFERENCE_CAMERA_ADAPTER_V1
UNCHANGED_WORLD_ENGINE_DATA_PROMPT_V1 UNCONSUMED_FIELD UNREVIEWED_GEOMETRY UNREVIEWED_SOURCE_CLAIM
UNREVIEWED_STAGE_DATE UNSCOPED_SHARED_INTENT UNSUPPORTED_3D UNSUPPORTED_AUDIO
UNSUPPORTED_CAMERA_ROTATION UNSUPPORTED_EXPLOSION UNSUPPORTED_FADE UNSUPPORTED_FIELD
UNSUPPORTED_LIVE_DATA UNSUPPORTED_VISIBLE_LABELS UNTERMINATED_JSON_ARRAY UNTERMINATED_JSON_OBJECT
UNTERMINATED_JSON_STRING USER_ATTACHED_STRUCTURE WORLD_ENGINE_BOUNDED_NL_INTENT_V2
WORLD_ENGINE_DATA_PIPELINE_RESULT_V1 WORLD_ENGINE_DATA_PROMPT_V1
WORLD_ENGINE_PRESENTATION_PIPELINE_RESULT_V2 WORLD_ENGINE_PRESENTATION_PLAN_V2
WORLD_ENGINE_PRESENTATION_PROMPT_V2 ZOOM_IN ZOOM_OUT
""".split())
_UP2_FIELD_PARTS = frozenset("""data prompt region presentation schema simulationType topic
subject label durationSeconds fps resolution width height scenes sceneId startFrame endFrame
facts dependsOn version event_type metadata output timing locations geometries routes markers
moving_objects source_notes id coordinates geometry source_id source_reference validity
start end camera mode keyframes frame center zoom routeId followStrength territoryColors
highlights transitions initialStateVisibility labels sceneOverrides countryCodes bounds
legacyProfileId native_context scale preferred scene_timing date startDate endDate
context_location_ids primary_country_id renderSettings sourceRegionId
""".split())


def _up2_diagnostic(error, value):
    """Bounded machine facts only; never copy messages, input IDs or unknown keys."""
    if getattr(error, 'code', None) != 'UP2_COMPLETE_TIMELINE_DATA_REQUIRED':
        return None
    scenes = value.get('prompt', {}).get('data', {}).get('scenes', [])
    ids = {row['sceneId']: 'scene[' + str(i) + ']'
           for i, row in enumerate(scenes[:64])
           if type(row) is dict and type(row.get('sceneId')) is str
           and len(row['sceneId']) <= 192} if type(scenes) is list else {}

    def field_name(raw):
        if type(raw) is not str or len(raw) > 192:
            return 'REDACTED_FIELD'
        candidates = []
        for scene_id, alias in ids.items():
            for prefix in ('$.presentation.sceneOverrides.', '$.data.scenes.'):
                if raw == prefix + scene_id or raw.startswith(prefix + scene_id + '.'):
                    candidates.append(prefix[:-1] + '[' + alias[6:] + raw[len(prefix + scene_id):])
        if len(candidates) > 1:
            return 'REDACTED_FIELD'  # Dotted IDs can also denote nested fields.
        if candidates:
            raw = candidates[0]
        if not re.fullmatch(r'\$(?:\.[A-Za-z_]+|\[[0-9]{1,4}\])*', raw):
            return 'REDACTED_FIELD'
        return raw if all(p in _UP2_FIELD_PARTS for p in re.findall(r'\.([A-Za-z_]+)', raw)) else 'REDACTED_FIELD'

    result = {'schema': 'WORLD_ENGINE_UP2_DIAGNOSTIC_V1',
              'code': 'UP2_COMPLETE_TIMELINE_DATA_REQUIRED',
              'fields': {'issues': [], 'blockedSceneIds': []},
              'sceneIdEncoding': 'ZERO_BASED_INPUT_SCENE_INDEX', 'limit': 16}
    fields = getattr(error, 'fields', None)
    if type(fields) is not list:
        return result
    for group in fields[:16]:
        if type(group) is not dict:
            continue
        issues = group.get('issues')
        if type(issues) is list:
            for row in issues[:16]:
                if len(result['fields']['issues']) >= 16:
                    break
                if type(row) is dict:
                    code = row.get('code')
                    result['fields']['issues'].append({
                        'code': code if type(code) is str and code in _UP2_CODES else 'UNLISTED_CODE',
                        'field': field_name(row.get('field'))})
        blocked = group.get('blockedSceneIds')
        if type(blocked) is list:
            for scene_id in blocked[:16]:
                if len(result['fields']['blockedSceneIds']) >= 16:
                    break
                result['fields']['blockedSceneIds'].append(
                    ids.get(scene_id, 'REDACTED_SCENE_ID') if type(scene_id) is str else 'REDACTED_SCENE_ID')
    return result


def _normal_with_up2_diagnostic(normalizer, value):
    try:
        return normalizer(value)
    except Exception as error:
        try:
            diagnostic = _up2_diagnostic(error, value)
            if diagnostic is not None:
                encoded = json.dumps(diagnostic, separators=(',', ':'), ensure_ascii=True)
                error._up2_public_diagnostic_json = encoded
                print(encoded, flush=True)
        except Exception:
            pass  # Diagnostic failure must never replace the original exception.
        raise


base = mvp()


class NvidiaPresentationController(base.StudioController):
    """Only normalize a new profile; inherited start owns policy and claims.

    Its CPU source normalizer is reused without calling the FREE profile's
    submit/start/worker. A free-review preflight is never a GPU approval.
    """
    def __init__(self, *, control_root, export_root, image_digest,
                 source_manifest, expected_manifest_sha256, backend=None):
        control, exports = Path(control_root), Path(export_root)
        if (not control.is_absolute() or not exports.is_absolute()
                or '..' in control.parts or '..' in exports.parts
                or any(p.is_symlink() for p in (control, *control.parents, exports, *exports.parents))
                or control.resolve().is_relative_to(exports.resolve())
                or exports.resolve().is_relative_to(control.resolve())):
            raise base.StudioError('HANDOFF_PRIVATE_PUBLIC_ROOTS_MUST_BE_DISJOINT')
        self.source_manifest = Path(source_manifest)
        self.source_sha = expected_manifest_sha256
        verify_manifest(self.source_manifest, self.source_sha)
        if backend is None:
            from nvidia_backend import NvidiaPresentationBackend
            backend = NvidiaPresentationBackend(self.source_manifest, self.source_sha, image_digest)
        super().__init__(control_root=control_root, export_root=export_root,
                         image_digest=image_digest, backend=backend)
        self._source_normalizer = None

    def _normal(self, value):
        def invalid(code):
            raise base.studio_contracts.StudioContractError(code, code)
        if (not isinstance(value, dict) or set(value) != {'schema', 'prompt', 'sceneId'}
                or value.get('schema') != REQUEST or not isinstance(value.get('prompt'), dict)
                or not isinstance(value.get('sceneId'), str)):
            invalid('HANDOFF_EXPLICIT_NVIDIA_PRESENTATION_REQUEST_REQUIRED')
        verify_manifest(self.source_manifest, self.source_sha)
        if self._source_normalizer is None:
            module = load('_handoff_preserved_cpu_source_normalizer',
                          RECOVERY / 'universal-presentation-v2/studio_adapter.py')
            def node_profile_json(script, payload, *, timeout=90, maximum_input_bytes=8 * 1024**2):
                raw = module.canonical(payload)
                if maximum_input_bytes not in {8 * 1024**2, 24 * 1024**2} or len(raw) > maximum_input_bytes:
                    raise module.StudioError('UP2_INPUT_SIZE_LIMIT', status=400)
                try:
                    completed = subprocess.run(['node', '--input-type=module', '-e', script], input=raw,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
                except (OSError, subprocess.TimeoutExpired):
                    raise module.StudioError('UP2_DATA_PROCESSOR_UNAVAILABLE') from None
                if completed.returncode or len(completed.stdout) > 24 * 1024**2:
                    codes = re.findall(rb'\b(?:HANDOFF|GCUBE|UP2|REGION|PLANNER|AREA|FLOW|EVENT|CAMERA)_[A-Z0-9_]{2,100}\b', completed.stderr)
                    error = module.StudioError(codes[-1].decode() if codes else 'UP2_DATA_PROCESSOR_FAILED')
                    error._private_profile_stderr = completed.stderr[:128 * 1024]
                    raise error
                try:
                    value = json.loads(completed.stdout)
                    if not isinstance(value, dict):
                        raise ValueError()
                    return value
                except (ValueError, TypeError):
                    raise module.StudioError('UP2_DATA_PROCESSOR_RESULT_INVALID') from None
            # Same finite JSON limits and closed-code errors, with the new
            # profile's codes retained instead of being hidden as generic UP2.
            module.node_json = node_profile_json
            def prepare_profile_sources(request, cache_root):
                # Only this private module instance selects the versioned
                # source preparer. Original FREE source files/instances retain
                # their literal /workspace-only behavior and their paid gate.
                return module.node_json("import{readFileSync}from'node:fs';"
                    "const p=JSON.parse(readFileSync(0,'utf8'));"
                    "const{prepareNvidiaRuntimeRequest}=await import(p.module);"
                    "process.stdout.write(JSON.stringify(await prepareNvidiaRuntimeRequest({...p.input,request:JSON.parse(p.requestWireJSON)})));",
                    {'module': (HERE.parent / 'backend/capture_nvidia.mjs').as_uri(),
                     'requestWireJSON': json.dumps(request, ensure_ascii=False, separators=(',', ':'), allow_nan=False),
                     'input': {'cacheRoot': str(cache_root),
                        'privateWorkspaceRoot': str(self.control_root),
                        'publicExportRoot': str(self.export_root)}}, timeout=150)
            module.prepare_runtime = prepare_profile_sources
            def verify_profile_sources(prepared, admission=None, prepared_wire=None):
                # Exact existing Python aggregate and member-order checks are
                # retained; only this version's qualified cache-root transport
                # is selected for the unchanged geographic/source verifier.
                if (not isinstance(prepared, dict) or admission is not None and any(
                        prepared.get(key) != admission.get(key) for key in (
                            'sourceQualification', 'sourceQualificationSHA256', 'sourceQualificationWireJSON'))):
                    raise module.StudioError('UP2_STORED_SOURCE_AGGREGATE_CHANGED')
                wire = prepared_wire if prepared_wire is not None else json.dumps(
                    prepared, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
                try:
                    wire_matches = isinstance(wire, str) and json.loads(wire) == prepared
                except (ValueError, TypeError):
                    wire_matches = False
                if not wire_matches:
                    raise module.StudioError('UP2_STORED_SOURCE_WIRE_CHANGED')
                result = module.node_json("import{readFileSync}from'node:fs';"
                    "const p=JSON.parse(readFileSync(0,'utf8'));"
                    "const{verifyNvidiaPreparedRuntimeRequest}=await import(p.module);"
                    "process.stdout.write(JSON.stringify(await verifyNvidiaPreparedRuntimeRequest({...p.input,prepared:JSON.parse(p.preparedWireJSON)})));",
                    {'module': (HERE.parent / 'backend/capture_nvidia.mjs').as_uri(),
                     'preparedWireJSON': wire,
                     'input': {'privateWorkspaceRoot': str(self.control_root),
                        'publicExportRoot': str(self.export_root)}}, timeout=150,
                    maximum_input_bytes=24 * 1024**2 if prepared.get('profile') == 'HISTORICAL_CONTINUOUS_600F_V1'
                    and prepared.get('totalFrames') == 600 else 8 * 1024**2)
                if result.get('status') != 'PASS':
                    raise module.StudioError('UP2_STORED_SOURCE_QUALIFICATION_INVALID',
                                             fields=[{'code': result.get('code')}])
                return result
            module.verify_prepared_sources = verify_profile_sources
            self._source_normalizer = module.StudioController(
                control_root=self.control_root / 'handoff-source-normalization',
                export_root=self.export_root, allow_free_data_review=True,
                allow_ten_second_sample=True, allow_authored_history=True)
        module = sys.modules['_handoff_preserved_cpu_source_normalizer']
        cpu = _normal_with_up2_diagnostic(self._source_normalizer._normal,
            {**deepcopy(value), 'schema': module.REQUEST_SCHEMA})
        pipeline = cpu['sourcePipeline']
        historical = (pipeline.get('simulationType') == 'HISTORICAL' and pipeline.get('totalFrames') == 600
                      and pipeline.get('durationSeconds') == 20
                      and pipeline.get('historicalAdmission', {}).get('status') == 'PASS'
                      and pipeline.get('historicalAdmission', {}).get('scope') == 'HISTORICAL_CONTINUOUS_600F_V1')
        if ((not historical and (pipeline.get('simulationType') not in {'GENERAL', 'FICTIONAL'}
                or pipeline.get('totalFrames') not in {180, 300})) or pipeline.get('fps') != 30
                or (pipeline.get('totalFrames') == 300 and pipeline.get('durationSeconds') != 10)
                or pipeline.get('ready') is not True
                or pipeline.get('sourceAdmission', {}).get('status') != 'PASS'):
            invalid('HANDOFF_QUALIFIED_NONHISTORICAL_180_FRAMES_REQUIRED')
        frames = pipeline['totalFrames']
        profile = HISTORY_PROFILE if historical else PROFILE
        plan = {'schema': PLAN, 'totalFrames': frames, 'durationSeconds': frames // 30, 'fps': 30,
            'resolution': {'width': 1080, 'height': 1920}, 'aspectRatio': '9:16',
            'audioSettings': {'enabled': False, 'mode': 'SILENT'},
            'simulationType': pipeline['simulationType'],
            'renderProfile': {'profileId': profile, 'backend': 'vulkan',
                'imageDigest': self.image_digest, 'sourceClosureSHA256': self.source_sha},
            'runtime': deepcopy(pipeline['runtimePayload']),
            'runtimeWireJSON': pipeline['runtimeRequestWireJSON'],
            'runtimeWireSHA256': pipeline['runtimeWireSHA256'],
            'sourceQualificationSHA256': pipeline['sourceAdmission']['sourceQualificationSHA256'],
            'sourceBindings': deepcopy(pipeline['sourceBindings']),
            'sourceQualification': deepcopy(pipeline['sourceAdmission']['sourceQualification']),
            'originalInputSHA256': pipeline['compilerInputSHA256']}
        if historical:
            plan['historicalAdmission'] = deepcopy(pipeline['historicalAdmission'])
        duration_contract(plan)
        return {'schema': 'WORLD_ENGINE_NVIDIA_STUDIO_SUBMISSION_V1',
                'title': cpu['title'], 'profile': profile, 'videoPlan': plan,
                'sfx': {'enabled': False}, 'sourceTrace': {'cpuSourceQualificationReused': True,
                    'freeProfileStartCalled': False, 'sourceInputSHA256': pipeline['compilerInputSHA256']}}

    def _preflight_record(self, root, record):
        result = super()._preflight_record(root, record)
        timing = duration_contract(record['submission']['videoPlan'])
        if timing['durationSeconds'] in {10, 20}:
            # The preserved coordinator deliberately drops backend timing facts.
            # Surface only this new sample's validated duration for owner consent.
            result.update(durationSeconds=timing['durationSeconds'], totalFrames=timing['totalFrames'])
        return result

    def resume(self, *args, **kwargs):
        # No new GPU work is silently reauthorized or restarted in this bounded
        # first-review profile; failed/old claims and outputs remain untouched.
        raise base.StudioError('HANDOFF_EXPLICIT_RECOVERY_NOT_SUPPORTED')

    def revise(self, *args, **kwargs):
        raise base.StudioError('HANDOFF_REVISION_NOT_SUPPORTED')
