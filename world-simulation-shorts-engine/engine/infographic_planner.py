"""Explicit v022 plans; never migrate or retime a saved camera-only fixture."""
from copy import deepcopy

QA_PRESET = 'MAP_INFOGRAPHIC_QA_V022'
PRODUCTION_PRESET = 'MAP_INFOGRAPHIC_PRODUCTION_V022'


def parent_qa_plan(raw=None):
    """Rebuild the certified QA family with its original, explicit preset."""
    from .second_event_camera import generate
    from .visual_quality import apply_quality
    from .event_quality import apply_quality as apply_event_quality
    from .reference_effects import apply_effects
    from .story_progression import apply_progression
    request = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                   quality='HIGH', pace='FAST_PLUS', qa_mode=True,
                   tts=False, subtitles=False, bgm=True, sfx=True)
    request.update(deepcopy(raw or {}))
    if float(request.get('duration', 0)) != 24:
        raise ValueError('INFOGRAPHIC_QA_REQUIRES_24_SECONDS')
    request['direction_profile'] = 'SECOND_EVENT_ADAPTIVE_WIDE_TEST'
    request['qa_mode'] = True
    # The QA has no narration; real speech belongs to the separate Production
    # builder whose integer timing is allocated only after PCM measurement.
    request['tts'] = False
    request['subtitles'] = False
    return apply_progression(apply_effects(apply_event_quality(apply_quality(
        generate(request)))))


def generate_infographic_qa(raw=None):
    from .infographic_contract import prepare_infographic
    request = deepcopy(raw or {})
    enabled = request.get('map_infographic', True)
    if type(enabled) is not bool:
        raise ValueError('INFOGRAPHIC_ENABLE_REQUIRES_BOOLEAN')
    parent = parent_qa_plan(request)
    if not enabled:
        return prepare_infographic(parent, enabled=False)
    scene = parent['scenes'][0]
    # This is an authored, separately named QA mapping of existing Scene data.
    # Registry geometry is never guessed from a point or an event title.
    def event(identifier, start, end, before, after, refs, point, role,
              title, location, label_index, text_event=None):
        source = next(v for v in scene['visual_events'] if v['id'] == identifier)
        hypothetical = source['claim_id'] == 'A01'
        return dict(id='MAP_' + identifier, scene_id=scene['scene_id'],
            semantic_segment_ref=None, claim_id=source['claim_id'],
            target_geometry_refs=refs, location_point_ref=point,
            state_before=before, state_after=after, start_frame=start,
            transition_end_frame=start + 17, end_frame=end, primary_role=role,
            evidence_type='hypothetical_scenario' if hypothetical else 'sourced_fact',
            watermark='가정 시나리오' if hypothetical else None,
            text=dict(event_title=title, location_label=location, support_data=None),
            story_source_ref=dict(visual_event_id=identifier,
                                  text_event_id=text_event, label_index=label_index))
    events = [
        event('E001', 60, 180, 'CONTEXT', 'LOCATION',
              ['COUNTRY_EGY'],
              'LOCATION_SUEZ_CANAL', 'LOCATION_LABEL', None, 'SUEZ CANAL', 0),
        event('E002', 180, 330, 'OPEN', 'CLOSED',
              ['CANAL_SUEZ_RIVER_NE10M', 'CANAL_SUEZ_LAKE_NE10M'],
              'LOCATION_SUEZ_CANAL', 'EVENT_TITLE', 'CANAL CLOSED', 'SUEZ CANAL', 0, 'T_E002'),
        event('E003', 330, 450, 'CLOSED', 'OPEN',
              ['CANAL_SUEZ_RIVER_NE10M', 'CANAL_SUEZ_LAKE_NE10M'],
              'LOCATION_SUEZ_CANAL', 'EVENT_TITLE', 'CANAL OPEN', 'SUEZ CANAL', 0, 'T_E003'),
        event('E004', 450, 720, 'CONTEXT', 'LOCATION', ['COUNTRY_SGP'],
              'LOCATION_SINGAPORE', 'LOCATION_LABEL', None, 'SINGAPORE', 1),
    ]
    return prepare_infographic(parent, events=events, enabled=True)


def generate_production_infographic(script_record, directory, provider=None, *, fps=30):
    """Actual authored script -> measured speech -> dynamic geographic plan."""
    from .semantic_timeline import generate_production_plan
    return generate_production_plan(script_record, directory, provider=provider, fps=fps)
