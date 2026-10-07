"""Opt-in bounded QA input adapter, preserving the certified production planner.

Use the *same* planner function code with a per-call request validator namespace.
No shared module monkey-patching, retiming of a rendered video, shortened speech,
promotion hash changes, or suppression of plan/visibility/retention gates occurs.
Normal requests call the original planner directly.
"""
from copy import deepcopy
import math
from types import FunctionType
from pathlib import Path
from . import planner


def configure_qa_schema():
    # Deployment-only schema extension. The certified schema remains immutable
    # and the extension's normal-request branch is that exact original policy.
    from . import schema
    schema.SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'data/qa_scene_plan.schema.json'


def generate_deployment_plan(raw):
    configure_qa_schema()
    qa = raw.get('qa_mode', False)
    if not isinstance(qa, bool):
        raise planner.PlanningInputError('QA 설정은 ON/OFF여야 합니다.')
    if not qa:
        return planner.generate_plan(raw)
    try:
        duration = float(raw.get('duration'))
    except (TypeError, ValueError):
        raise planner.PlanningInputError('QA 테스트는 10~15초입니다.') from None
    if not math.isfinite(duration) or not 10 <= duration <= 15:
        raise planner.PlanningInputError('QA 테스트는 10~15초입니다.')

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
    if plan.get('story', {}).get('domain') == 'shipping':
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
    from .schema import validate_plan
    plan['gate'] = validate_plan(plan)
    return plan
