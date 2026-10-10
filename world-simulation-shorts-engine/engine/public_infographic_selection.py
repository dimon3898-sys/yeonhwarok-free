"""Public v022 selection bridge; existing geographic/planning code is unchanged.

Only authored JSON crosses this boundary. Speech artifacts remain in a private,
server-owned persistent directory so immutable plans survive restart and retry.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import re

from .storage import EngineError

QA_PROFILE = 'MAP_INFOGRAPHIC_QA_V022'
PRODUCTION_PROFILE = 'MAP_INFOGRAPHIC_PRODUCTION_V022'
PUBLIC_PROFILES = {QA_PROFILE, PRODUCTION_PROFILE}
FAMILIES = {QA_PROFILE: 'story-progression-v021',
            PRODUCTION_PROFILE: 'production-earth-v1'}


def expected_creation_profile(request, environ=None):
    env = os.environ if environ is None else environ
    selected = request.get('direction_profile')
    if isinstance(selected, str) and selected in PUBLIC_PROFILES:
        return selected
    try:
        duration = float(request.get('duration', 0))
    except (TypeError, ValueError):
        duration = None
    if (env.get('WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION') == 'v022'
            and duration == 24
            and (selected is None or selected == 'REFERENCE_MASTER')
            and request.get('production_preset') != 'LEGACY'):
        return QA_PROFILE
    return None


def require_infographic_selection(plan, expected_profile=None):
    """Reject partial/claimed v022 selection; never migrate a saved legacy plan."""
    def mismatch():
        raise EngineError('INFOGRAPHIC_SELECTION_MISMATCH',
                          '선택한 지도 인포그래픽과 실제 Scene Plan이 일치하지 않습니다. 새 기획을 확인해 주세요.', status=409)
    if not isinstance(plan, dict):
        mismatch()
    metadata = plan.get('metadata', {})
    scenes = plan.get('scenes', [])
    request = plan.get('request', {})
    if (not isinstance(metadata, dict) or not isinstance(scenes, list)
            or any(not isinstance(s, dict) for s in scenes)
            or not isinstance(request, dict)):
        mismatch()
    declared = request.get('direction_profile')
    expected_profile = expected_profile or (declared if isinstance(declared, str) and declared in PUBLIC_PROFILES else None)
    present = ('infographic' in metadata or any('infographic' in s for s in scenes)
               or 'bold_infographic' in metadata or any('bold_infographic' in s for s in scenes)
               or 'terrain_infographic' in metadata or any('terrain_infographic' in s for s in scenes))
    if not present and expected_profile is None:
        return None
    selected = metadata.get('infographic')
    family = selected.get('parent_renderer_family') if isinstance(selected, dict) else None
    actual = next((p for p, f in FAMILIES.items() if f == family), None)
    if (not isinstance(selected, dict) or selected.get('version') != 'v022'
            or not scenes or actual is None
            or expected_profile is not None and actual != expected_profile
            or any(not isinstance(s.get('infographic'), dict)
                   or s['infographic'].get('version') != 'v022'
                   or s['infographic'].get('parent_renderer_family') != family for s in scenes)):
        mismatch()
    from .infographic_contract import validate_infographic
    checked = validate_infographic(plan)
    if checked['passed'] and ('terrain_infographic' in metadata
                              or any('terrain_infographic' in scene for scene in scenes)):
        from .terrain_infographic import install_runtime, validate_terrain_infographic
        if not validate_terrain_infographic(plan)['passed']:
            raise EngineError('TERRAIN_INFOGRAPHIC_PLAN_INVALID',
                              '지형 인포그래픽의 실제 지역·소스 검증을 통과하지 못했습니다.', status=409)
        install_runtime()
    if checked['passed'] and ('bold_infographic' in metadata
                              or any('bold_infographic' in scene for scene in scenes)):
        from .bold_infographic import install_runtime, validate_bold_infographic
        if not validate_bold_infographic(plan)['passed']:
            raise EngineError('BOLD_INFOGRAPHIC_PLAN_INVALID',
                              'BOLD 지도 표현의 실제 지역·소스 검증을 통과하지 못했습니다.', status=409)
        # The additive child is proven before the unchanged strict Production
        # schema receives its original parent view. Cold workers use this gate.
        install_runtime()
    if checked['passed'] and actual == PRODUCTION_PROFILE:
        # Metadata-only timing is insufficient after restart. Recheck the
        # persisted PCM and authored speech/Scene binding with the existing gate.
        from .semantic_timeline import validate_production_plan
        checked = validate_production_plan(plan)
    if not checked['passed']:
        raise EngineError('INFOGRAPHIC_PLAN_INVALID',
                          '지도 인포그래픽의 사건·소스 검증을 통과하지 못했습니다.', status=409)
    return actual


def require_project_infographic_selection(store, pid, version, plan=None):
    """Bind immutable saved inputs to the admitted profile, including retries."""
    from .storage import read_json
    plan = store.get(pid, version)['plan'] if plan is None else plan
    expected = None
    expected_visual = None
    receipt_path = store.version_path(pid, version) / 'public-selection.json'
    original_receipt_path = store.path(pid) / 'versions' / 'v001' / 'public-selection.json'
    original_path = store.path(pid) / 'prompt' / 'request_v001.json'
    try:
        if receipt_path.is_symlink() or original_receipt_path.is_symlink() or original_path.is_symlink():
            raise ValueError('unsafe selection receipt')
        for path in dict.fromkeys((original_receipt_path, receipt_path)):
            if not path.exists():
                continue
            receipt = read_json(path)
            if (not isinstance(receipt, dict) or receipt.get('version') != 'v022'
                    or receipt.get('effective_profile') not in PUBLIC_PROFILES):
                raise ValueError('invalid selection receipt')
            if expected is not None and expected != receipt['effective_profile']:
                raise ValueError('selection receipt conflict')
            expected = receipt['effective_profile']
            visual = receipt.get('visual_profile')
            if visual is not None:
                if visual not in {'BOLD_INFOGRAPHIC_V023', 'VISUAL_TARGET_MAP_V024'} or expected_visual not in {None, visual}:
                    raise ValueError('invalid visual selection receipt')
                expected_visual = visual
        if original_path.exists():
            original = read_json(original_path)
            profile = original.get('direction_profile') if isinstance(original, dict) else None
            if isinstance(profile, str) and profile in PUBLIC_PROFILES:
                if expected is not None and expected != profile:
                    raise ValueError('selection receipt conflict')
                expected = profile
            if isinstance(original, dict) and 'infographic_visual_profile' in original:
                visual = original['infographic_visual_profile']
                if visual not in {'BOLD_INFOGRAPHIC_V023', 'VISUAL_TARGET_MAP_V024', 'V022_LEGACY'} or expected_visual not in {None, visual}:
                    raise ValueError('visual selection receipt conflict')
                expected_visual = visual
    except (OSError, ValueError, TypeError):
        raise EngineError('INFOGRAPHIC_SELECTION_MISMATCH',
                          '저장된 연출 선택과 기획이 일치하지 않습니다.', status=409) from None
    actual = require_infographic_selection(plan, expected)
    bold = plan.get('metadata', {}).get('bold_infographic') is not None
    terrain = plan.get('metadata', {}).get('terrain_infographic') is not None
    selected_visual = 'VISUAL_TARGET_MAP_V024' if terrain else 'BOLD_INFOGRAPHIC_V023' if bold else 'V022_LEGACY'
    if expected_visual is not None and selected_visual != expected_visual:
        raise EngineError('TERRAIN_INFOGRAPHIC_SELECTION_MISMATCH'
                          if expected_visual == 'VISUAL_TARGET_MAP_V024'
                          else 'BOLD_INFOGRAPHIC_SELECTION_MISMATCH',
                          '저장된 지도 표현과 실제 기획이 일치하지 않습니다.', status=409)
    return actual


def _reject_script():
    raise EngineError('INFOGRAPHIC_SCRIPT_INVALID',
                      '등록된 지리 소스와 연결된 대본·사건 JSON이 필요합니다.')


def validate_public_production_request(value):
    """Validate source-bound authored input before any speech subprocess runs."""
    if (not isinstance(value, dict) or set(value) - {'direction_profile', 'script_record', 'topic'}
            or value.get('direction_profile') != PRODUCTION_PROFILE):
        raise EngineError('UNSUPPORTED_INPUT', '대본 기반 인포그래픽은 연출 선택과 대본 JSON만 받습니다.')
    script = value.get('script_record')
    allowed = {'text', 'segments', 'claims', 'sources', 'events', 'topic', 'hook',
               'conclusion', 'domain', 'language', 'speed', 'options'}
    if not isinstance(script, dict) or set(script) - allowed:
        _reject_script()
    try:
        # Also rejects NaN/Infinity and non-JSON values without exposing content.
        if len(json.dumps(script, ensure_ascii=False, allow_nan=False).encode()) > 60 * 1024:
            _reject_script()
        from .semantic_timeline import (_script, _sentence_ranges,
                                        registered_production_sources)
        from .infographic_contract import load_registry, canonical_sha, _validate_event
        from .gis import resolve_location, verified_coordinate
        from jsonschema import Draft202012Validator
        text, definitions = _script(script)
        if len(text) > 2000 or len(definitions) > 40:
            _reject_script()
        if any(set(d) != {'id', 'start_char', 'end_char', 'claim_ids', 'source_ids',
                          'target_ids', 'event_ids'} for d in definitions):
            _reject_script()
        for field in ('topic', 'hook', 'conclusion', 'domain'):
            if field in script and (not isinstance(script[field], str) or len(script[field]) > 2000):
                _reject_script()
        language = script.get('language')
        if language is not None and language not in {'en', 'ko', 'ja', 'zh', 'es', 'fr', 'de', 'pt'}:
            _reject_script()
        speed = script.get('speed', 155)
        if type(speed) is not int or not 80 <= speed <= 240:
            _reject_script()
        options = script.get('options', {})
        if (not isinstance(options, dict)
                or set(options) - {'tts', 'subtitles', 'bgm', 'sfx', 'quality', 'pace'}
                or options.get('tts', True) is not True
                or any(type(options.get(k, True)) is not bool for k in ('subtitles', 'bgm', 'sfx'))
                or options.get('quality', 'HIGH') not in {'FAST', 'HIGH', 'CINEMA'}
                or options.get('pace', 'NORMAL') not in {'FAST_PLUS', 'FAST', 'NORMAL', 'CINEMATIC'}):
            _reject_script()
        claims, sources, events = (script.get(k) for k in ('claims', 'sources', 'events'))
        if any(not isinstance(v, list) or not v or len(v) > 120 for v in (claims, sources, events)):
            _reject_script()
        schema_path = Path(__file__).resolve().parents[1] / 'data/infographic/v022/production_scene_plan.schema.json'
        claim_schema = json.loads(schema_path.read_text())['properties']['story']['properties']['claims']
        if list(Draft202012Validator(claim_schema).iter_errors(claims)):
            _reject_script()
        def indexed(rows):
            if any(not isinstance(r, dict) or not isinstance(r.get('id'), str)
                   or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', r['id']) for r in rows):
                _reject_script()
            result = {r['id']: r for r in rows}
            if len(result) != len(rows):
                _reject_script()
            return result
        claim_by_id, source_by_id, event_by_id = map(indexed, (claims, sources, events))
        trusted = registered_production_sources()
        if any(sid not in trusted or canonical_sha(record) != canonical_sha(trusted[sid])
               for sid, record in source_by_id.items()):
            _reject_script()
        for claim in claims:
            if (not claim['text'].strip() or len(claim['text']) > 2000
                    or any(s not in source_by_id for s in claim['source_ids'])
                    or claim['status'] == 'FACT' and not claim['source_ids']
                    or claim['status'] == 'SIMULATION' and not claim.get('assumption_ids')
                    or any(a not in claim_by_id or claim_by_id[a]['status'] != 'ASSUMPTION'
                           for a in claim.get('assumption_ids', []))):
                _reject_script()
        geometries = {g['id']: g for g in load_registry()['geometries']}
        segments = {s['id']: s for s in definitions}
        allowed_events = {'id', 'semantic_segment_ref', 'claim_id', 'target_geometry_refs',
                          'location_point_ref', 'state_before', 'state_after', 'primary_role',
                          'evidence_type', 'watermark', 'text', 'visual_kind', 'sentence_index'}
        required_events = allowed_events - {'visual_kind', 'sentence_index'}
        kinds = {'city_reveal', 'country_reveal', 'region_reveal', 'destination_preview',
                 'new_variable', 'response', 'consequence_reveal', 'final_reveal', 'route_blocked'}
        used = []
        for definition in definitions:
            if (any(c not in claim_by_id for c in definition['claim_ids'])
                    or any(s not in source_by_id for s in definition['source_ids'])
                    or not definition['event_ids']):
                _reject_script()
            sentence_count = len(list(_sentence_ranges(text, definition['start_char'], definition['end_char'])))
            for eid in definition['event_ids']:
                event = event_by_id.get(eid)
                if (event is None or set(event) - allowed_events or not required_events <= set(event)
                        or event['semantic_segment_ref'] != definition['id']
                        or event['claim_id'] not in definition['claim_ids']
                        or event.get('visual_kind', 'region_reveal') not in kinds
                        or type(event.get('sentence_index', 0)) is not int
                        or not 0 <= event.get('sentence_index', 0) < sentence_count):
                    _reject_script()
                point = geometries.get(event['location_point_ref'])
                if (point is None or point['geometry_type'] != 'Point'
                        or point.get('location_id') not in definition['target_ids']):
                    _reject_script()
                location = resolve_location(point['location_id'])
                if not verified_coordinate(location['coordinates']) or location['coordinates']['source_id'] not in source_by_id:
                    _reject_script()
                bound = {k: deepcopy(event[k]) for k in required_events}
                bound.update(scene_id='PUBLIC_AUTHORED_INPUT', start_frame=0,
                             transition_end_frame=1, end_frame=3, story_source_ref=None)
                _validate_event(bound, {'scene_id': 'PUBLIC_AUTHORED_INPUT', 'frame_count': 3},
                                geometries, claim_by_id, segments)
                if event.get('visual_kind') == 'route_blocked' and (
                        not event['target_geometry_refs'] or event['state_after'] not in {'CLOSED', 'BLOCKED', 'INACTIVE'}
                        or any(geometries[g]['geometry_type'] not in {'LineString', 'MultiLineString'}
                               for g in event['target_geometry_refs'])):
                    _reject_script()
                used.append(eid)
        if len(used) != len(set(used)) or set(used) != set(event_by_id):
            _reject_script()
    except EngineError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        _reject_script()
    topic = value.get('topic', script.get('topic', text))
    if not isinstance(topic, str) or not 1 <= len(topic.strip()) <= 2000:
        raise EngineError('TOPIC_LENGTH', '주제는 1~2000자여야 합니다.')
    return dict(direction_profile=PRODUCTION_PROFILE, topic=topic, script_record=deepcopy(script))
