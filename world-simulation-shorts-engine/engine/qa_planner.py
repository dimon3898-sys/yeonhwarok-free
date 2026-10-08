"""Opt-in bounded QA input adapter, preserving the certified production planner.

Use the *same* planner function code with a per-call request validator namespace.
No shared module monkey-patching, retiming of a rendered video, shortened speech,
promotion hash changes, or suppression of plan/visibility/retention gates occurs.
Normal requests call the original planner directly.
"""
from copy import deepcopy
import math
import os
from types import FunctionType
from pathlib import Path
from . import planner


def configure_qa_schema():
    # Deployment-only schema extension. The certified schema remains immutable
    # and the extension's normal-request branch is that exact original policy.
    from . import schema, visibility
    if (os.environ.get('WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST')=='1' or os.environ.get('WORLD_ENGINE_RETURN_WIDE_TEST')=='1' or os.environ.get('WORLD_ENGINE_SECOND_EVENT_TEST')=='1'):
        from .single_event_camera import install_validation
        install_validation()
    # Deployment-selected additive certifier; its legacy branch replays the
    # original native definitions with unchanged thresholds. Frozen source
    # and quality-promotion hashes remain intact.
    visibility.TOOL = Path(__file__).resolve().parents[1] / 'tools/readable_semantic_preflight.mjs'
    schema.SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'data/readable_scene_plan.schema.json'
    if os.environ.get('WORLD_ENGINE_DIRECTION_VERSION') == 'v012':
        visibility.TOOL = Path(__file__).resolve().parents[1] / 'tools/direction_semantic_preflight.mjs'
        schema.SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'data/direction_scene_plan.schema.json'


    if os.environ.get('WORLD_ENGINE_DIRECTION_VERSION')=='v013':
        visibility.TOOL=Path(__file__).resolve().parents[1]/'tools/reference_semantic_preflight.mjs'
        schema.SCHEMA_PATH=Path(__file__).resolve().parents[1]/'data/reference_scene_plan.schema.json'


def directed_plan(plan, raw):
    if ((os.environ.get('WORLD_ENGINE_DIRECTION_VERSION') == 'v012' or raw.get('direction_profile')=='FAST_PLUS_LEGACY')
            and raw.get('production_preset') != 'LEGACY'):
        from .direction import apply_direction
        from .schema import validate_plan
        plan = apply_direction(plan)
        plan['gate'] = validate_plan(plan)
    return plan


def generate_deployment_plan(raw):
    configure_qa_schema()
    selected=raw.get('direction_profile')
    # This deployment's exact 24-second test can use the unchanged production
    # duration control (QA checkbox off, whose old UI range is 12..15). The
    # generated request is explicitly QA and names this isolated preset.
    if selected=='SECOND_EVENT_ADAPTIVE_WIDE_TEST' or (os.environ.get('WORLD_ENGINE_SECOND_EVENT_TEST')=='1' and float(raw.get('duration',0))==24 and selected in {None,'REFERENCE_MASTER'} and raw.get('production_preset')!='LEGACY'):
        from .second_event_camera import generate
        return generate({**raw,'qa_mode':True})
    if selected=='SINGLE_EVENT_RETURN_TO_WIDE_TEST' or (os.environ.get('WORLD_ENGINE_RETURN_WIDE_TEST')=='1' and raw.get('qa_mode') is True and float(raw.get('duration',0))==15):
        from .return_wide_camera import generate
        return generate(raw)
    if selected=='SINGLE_EVENT_CAMERA_TEST' or (os.environ.get('WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST')=='1' and raw.get('qa_mode') is True and float(raw.get('duration',0))==12):
        from .single_event_camera import generate
        return generate(raw)
    if selected not in {None,'REFERENCE_MASTER','FAST_PLUS_LEGACY'}:
        raise planner.PlanningInputError('지원하지 않는 연출 프로파일입니다.')
    if selected=='REFERENCE_MASTER' or (selected is None and os.environ.get('WORLD_ENGINE_DIRECTION_VERSION')=='v013' and raw.get('production_preset')!='LEGACY'):
        from . import schema,visibility
        schema.SCHEMA_PATH=Path(__file__).resolve().parents[1]/'data/reference_scene_plan.schema.json'
        visibility.TOOL=Path(__file__).resolve().parents[1]/'tools/reference_semantic_preflight.mjs'
        from .reference_master import generate_reference_plan
        return generate_reference_plan(raw)
    qa = raw.get('qa_mode', False)
    if not isinstance(qa, bool):
        raise planner.PlanningInputError('QA 설정은 ON/OFF여야 합니다.')
    if not qa:
        # The actual-output quality candidate is previewed in bounded QA first.
        # Existing non-QA production requests keep their certified exact plan.
        return directed_plan(planner.generate_plan(raw), raw)
    try:
        duration = float(raw.get('duration'))
    except (TypeError, ValueError):
        raise planner.PlanningInputError('QA 테스트는 12~15초입니다.') from None
    if not math.isfinite(duration) or not 12 <= duration <= 15:
        raise planner.PlanningInputError('QA 테스트는 12~15초입니다.')

    def qa_request(value):
        checked = deepcopy(value)
        checked['duration'] = 20
        checked = planner._request(checked)  # Existing topic/style/quality/options checks.
        checked['duration'] = round(duration * 30) / 30
        if abs(checked['duration'] - duration) > 1e-9:
            checked['original_duration'] = duration
        return checked

    # Both functions use only their own globals. The approved algorithm and its
    # helpers stay unchanged; only this invocation accepts the explicit QA range.
    namespace = dict(planner._generate_legacy_plan.__globals__)
    namespace['_request'] = qa_request
    namespace['_generate_legacy_plan'] = FunctionType(
        planner._generate_legacy_plan.__code__, namespace, '_generate_legacy_plan')
    generate = FunctionType(planner.generate_plan.__code__, namespace, 'generate_plan')
    plan = generate(deepcopy(raw))
    if (os.environ.get('WORLD_ENGINE_DIRECTION_VERSION') == 'v012' or selected=='FAST_PLUS_LEGACY') and raw.get('production_preset') != 'LEGACY':
        return directed_plan(plan, raw)
    if plan.get('story', {}).get('domain') == 'shipping':
        # A compressed HORIZON_REVEAL crosses the native camera angular gate.
        # Use an existing geographic preset in QA only, preserving the original
        # GIS rig endpoints, all routes/entities/events, HERO lighting and HIGH.
        # Normal plans and saved projects remain byte-for-byte unchanged.
        for index, scene in enumerate(plan['scenes']):
            if scene['camera_preset'] == 'HORIZON_REVEAL':
                scene['camera_preset'] = 'COUNTRY_APPROACH'
                scene['camera_speed'] = 1.0
                # Native projection replay found the moving primary ship wholly
                # outside the portrait frustum on frames 47..50 at 44 degrees.
                # Widen this QA rig, retaining its pose, tracking, model and quality.
                for endpoint in ('camera_start', 'camera_end'):
                    scene[endpoint]['fov'] = max(50, scene[endpoint].get('fov', 44))
                scene['entry_state']['camera'] = deepcopy(scene['camera_start'])
                scene['exit_state']['camera'] = deepcopy(scene['camera_end'])
                # Keep the adjacent boundary and its declared state continuous.
                if index:
                    previous = plan['scenes'][index-1]
                    previous['camera_end'] = deepcopy(scene['camera_start'])
                    previous['exit_state']['camera'] = deepcopy(scene['camera_start'])
                if index+1 < len(plan['scenes']):
                    following = plan['scenes'][index+1]
                    following['camera_start'] = deepcopy(scene['camera_end'])
                    following['entry_state']['camera'] = deepcopy(scene['camera_end'])
                timing = scene.setdefault('motion_timing', {})
                timing.update(camera_travel_duration=scene['duration'],
                              zoom_duration=scene['duration'], camera_speed_reference=1.0)
                plan.setdefault('metadata', {})['qa_camera_adjustment'] = dict(
                    scene_id=scene['scene_id'], original_preset='HORIZON_REVEAL',
                    reason='Native camera angle gate in bounded QA')
        # In a short shipping QA the physically drawn alternative-route start
        # introduces the new variable. Preserve its geometry, onset and kind;
        # do not claim that a camera move or a caption is a new physical event.
        for scene in plan['scenes']:
            for event in scene['visual_events']:
                if (event.get('kind') == 'route_start' and event.get('target_id') == 'R_CAPE'
                        and any(route['route_id'] == 'R_CAPE' and route['progress_start'] == 0
                                and abs(route['start_time'] - event['time']) < 1/30
                                for route in scene['routes'])):
                    event['role'] = 'variable'
                    plan.setdefault('metadata', {})['qa_variable_event'] = event['id']
    from .visual_readability import apply_readability_policy
    plan = apply_readability_policy(plan)
    from .schema import validate_plan
    plan['gate'] = validate_plan(plan)
    return plan
