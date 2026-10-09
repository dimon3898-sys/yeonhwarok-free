"""v020 sparse, observed information accents over an immutable v019 scene.

Only timing grammar is transferred. No reference image, colour, wording,
geographic content or sound is imported. OFF is the exact parent plan/identity.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math

from . import event_quality as parent

ROOT = parent.ROOT
VERSION = 'v020'
PROFILE_URL = '/static/reference_effects_v020.json'
REFERENCE_SHA256 = '853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc'
SOURCES = ('engine/reference_effects.py', 'engine/reference_effects_backend.py',
           'web/reference_effects_adapter.js', 'web/render_reference_effects_earth.html',
           'data/reference_effects_v020.json', 'web/reference_effects_v020.json')
EVENT_TYPES = ('LOCATION_REVEAL', 'EVENT_START', 'EVENT_STATE_CHANGE',
               'EVENT_RESOLVED', 'NEXT_LOCATION_REVEAL')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes():
    return {name: _sha(ROOT / name) for name in SOURCES}


def _profile():
    source = ROOT / 'data/reference_effects_v020.json'
    served = ROOT / 'web/reference_effects_v020.json'
    if source.read_bytes() != served.read_bytes():
        raise ValueError('REFERENCE_EFFECTS_SERVED_PROFILE_MISMATCH')
    value = json.loads(source.read_text())
    if set(value) != {'version', 'parent_version', 'reference_sha256', 'reference_fps',
                      'reference_content_end_frame', 'patterns', 'limits', 'evidence',
                      'excluded', 'audio', 'design'}:
        raise ValueError('REFERENCE_EFFECTS_PROFILE_FIELDS_INVALID')
    def typed(item):
        if isinstance(item, dict):
            return all(typed(v) for v in item.values())
        if isinstance(item, list):
            return all(typed(v) for v in item)
        if isinstance(item, float):
            return math.isfinite(item)
        return item is None or isinstance(item, (str, bool, int))
    if not typed(value):
        raise ValueError('REFERENCE_EFFECTS_PROFILE_NONFINITE')
    if (value.get('version') != VERSION or value.get('parent_version') != parent.VERSION
            or value.get('reference_sha256') != REFERENCE_SHA256
            or value.get('reference_content_end_frame') != 575
            or type(value.get('reference_content_end_frame')) is not int
            or type(value.get('reference_fps')) is not int or value.get('reference_fps') != 30):
        raise ValueError('REFERENCE_EFFECTS_PROFILE_INVALID')
    if value.get('patterns') != {
            'MARKER_POP': dict(pop_frames=9, peak_offset_frames=4,
                               dip_offset_frames=6, start_scale=.12, peak_scale=.95,
                               dip_scale=.85, radius_px=10),
            'TEXT_CHARACTER_REVEAL': dict(reveal_frames=17)}:
        raise ValueError('REFERENCE_EFFECTS_UNOBSERVED_PATTERN')
    for item in value['patterns'].values():
        for key, number in item.items():
            if ('frames' in key or key == 'radius_px') and type(number) is not int:
                raise ValueError('REFERENCE_EFFECTS_PATTERN_FRAME_TYPE_INVALID')
    if value.get('limits') != dict(max_primary=1, max_marker_frames=45,
                                   max_text_motion_frames=18, max_pops_per_event=1,
                                   max_added_sfx=0):
        raise ValueError('REFERENCE_EFFECTS_DENSITY_POLICY_INVALID')
    if any(type(number) is not int for number in value['limits'].values()):
        raise ValueError('REFERENCE_EFFECTS_LIMIT_TYPE_INVALID')
    evidence = value['evidence']
    if (not isinstance(evidence, list) or len(evidence) != 2
            or [e.get('id') for e in evidence] != ['REF_INITIAL_PIN_ENTRANCE', 'REF_LABEL_CHARACTER_ENTRANCE']):
        raise ValueError('REFERENCE_EFFECTS_EVIDENCE_INVALID')
    for item in evidence:
        expected = ({'id', 'start_frame', 'peak_frame', 'settled_frame', 'end_frame', 'method'}
                    if item['id'] == 'REF_INITIAL_PIN_ENTRANCE' else
                    {'id', 'start_frame', 'end_frame', 'second_start_frame', 'second_end_frame', 'method'})
        if set(item) != expected or not isinstance(item.get('method'), str):
            raise ValueError('REFERENCE_EFFECTS_EVIDENCE_FIELDS_INVALID')
        if any(type(v) is not int or not 0 <= v <= 575 for k, v in item.items() if k.endswith('_frame')):
            raise ValueError('REFERENCE_EFFECTS_EVIDENCE_FRAME_INVALID')
        if item['end_frame'] <= item['start_frame']:
            raise ValueError('REFERENCE_EFFECTS_EVIDENCE_RANGE_INVALID')
    if value['audio'] != dict(status='UNCONFIRMED', action='Preserve exact v019 audio; no new SFX',
                              reason='single mixed AAC track; syllabic voice/music peaks cannot establish isolated sound effects'):
        raise ValueError('REFERENCE_EFFECTS_UNVERIFIED_AUDIO')
    if (not isinstance(value['excluded'], list) or not all(isinstance(v, str) for v in value['excluded'])
            or not isinstance(value['design'], dict) or set(value['design']) != {'marker', 'font', 'texture_uploads', 'shader_changes'}
            or type(value['design']['texture_uploads']) is not int
            or value['design']['texture_uploads'] != 0 or value['design']['shader_changes'] is not False):
        raise ValueError('REFERENCE_EFFECTS_DESIGN_INVALID')
    return value


def _contract():
    _profile()
    parent._contract()
    return dict(version=VERSION, profile_url=PROFILE_URL,
                profile_sha256=_sha(ROOT / 'web/reference_effects_v020.json'),
                source_hashes=hashes(), parent_source_hashes=parent.hashes())


def _fps(scene):
    # This frozen test is 30 fps, but time is always derived from its frame grid.
    grid = scene.get('frame_grid', {})
    return float(grid.get('fps', scene.get('fps', 30)))


def _events(scene):
    events = []
    sequence = scene['visual_events']
    labels = scene.get('labels', [])
    statuses = scene.get('text_events', [])
    location_index = 0
    for source in sequence:
        start = round(float(source['time']) * _fps(scene))
        kind = source['kind']
        if kind == 'city_reveal':
            matches = [item for item in labels if item.get('coordinates') == source.get('coordinates')
                       and abs(item.get('start_time', 0) - source['time']) < 1e-9]
            if len(matches) != 1:
                raise ValueError('REFERENCE_EFFECTS_LOCATION_BINDING_INVALID')
            stops = [item['start_frame'] for item in scene['second_event_camera']['timeline']
                     if item['state'] == ('EVENT1_ZOOM_IN' if location_index == 0 else 'EVENT2_ZOOM_IN')]
            event = dict(type='LOCATION_REVEAL' if location_index == 0 else 'NEXT_LOCATION_REVEAL',
                         pattern='MARKER_POP', text=matches[0]['text'],
                         peak_frame=start + 4, end_frame=stops[0],
                         reference_evidence_ids=['REF_INITIAL_PIN_ENTRANCE'])
            location_index += 1
        elif kind == 'route_blocked' or any(item.get('event_id') == source['id'] for item in statuses):
            matches = [item for item in statuses if item.get('event_id') == source['id']]
            if len(matches) != 1:
                raise ValueError('REFERENCE_EFFECTS_TEXT_BINDING_INVALID')
            event = dict(type='EVENT_START' if kind == 'route_blocked' else 'EVENT_RESOLVED',
                         pattern='TEXT_CHARACTER_REVEAL', text=matches[0]['text'],
                         label_event_id=source['id'], peak_frame=start + 17, end_frame=start + 17,
                         reference_evidence_ids=['REF_LABEL_CHARACTER_ENTRANCE'])
        else:
            # A stable arrival with no authored text is not a new invented event.
            event = dict(type='EVENT_STATE_CHANGE', pattern='NONE', text='',
                         peak_frame=start, end_frame=start + 1, reference_evidence_ids=[])
        events.append(dict(id='FX_' + source['id'], story_event_id=source['id'],
                           start_frame=start, coordinates=deepcopy(source.get('coordinates')),
                           primary=event['pattern'] != 'NONE', sfx='NONE', **event))
    return events


def effect_timeline(scene):
    """Complete non-overlapping exclusive-end frame coverage, including NONE."""
    selected = scene.get('reference_effects')
    events = selected.get('events', []) if selected else []
    camera = scene.get('second_event_camera', {}).get('timeline', [])
    total = int(scene.get('frame_count', 720))
    boundaries = {0, total}
    for item in camera:
        boundaries.update((item['start_frame'], item['end_frame']))
    for item in events:
        boundaries.update((item['start_frame'], item['peak_frame'], item['end_frame']))
        if item['pattern'] == 'MARKER_POP':
            boundaries.add(item['start_frame'] + 9)
    fps = _fps(scene)
    sounds = [(round(float(s['time'])*fps), s) for s in scene.get('sound_events', [])]
    for frame, sound in sounds:
        boundaries.update((frame, frame+1))
    rows = []
    ordered = sorted(v for v in boundaries if 0 <= v <= total)
    for start, end in zip(ordered, ordered[1:]):
        if start == end:
            continue
        active = [e for e in events if e['start_frame'] <= start < e['end_frame'] and e['pattern'] != 'NONE']
        state = next((c['state'] for c in camera if c['start_frame'] <= start < c['end_frame']), 'UNKNOWN')
        rows.append(dict(start_frame=start, end_frame=end, frame_count=end-start,
                         start_seconds=start/fps, end_seconds=end/fps,
                         duration_seconds=(end-start)/fps, camera_state=state,
                         story_events=[e['story_event_id'] for e in active] or ['NONE'],
                         visual_effect=next((e['pattern'] for e in active if e['pattern'] == 'MARKER_POP'), 'NONE'),
                         text_effect=next((e['pattern'] for e in active if e['pattern'] == 'TEXT_CHARACTER_REVEAL'), 'NONE'),
                         sfx=next(('EXISTING_' + s['kind'] for frame, s in sounds if frame == start), 'NONE'),
                         sfx_policy='Existing v019 audio retained; no reference-isolated SFX verified'))
    return rows


def effect_qc(scene):
    errors = []
    selected = scene.get('reference_effects', {})
    events = selected.get('events', [])
    total = scene.get('frame_count', 720)
    def fail(code, **context):
        if not any(e['code'] == code and e.get('event_id') == context.get('event_id') for e in errors):
            errors.append(dict(code=code, **context))
    for event in events:
        start, peak, end = [event.get(k) for k in ('start_frame', 'peak_frame', 'end_frame')]
        if (any(isinstance(v, bool) or not isinstance(v, int) for v in (start, peak, end))
                or not 0 <= start <= peak <= end <= total or start == end):
            fail('REFERENCE_EFFECTS_FRAME_GRID_INVALID', event_id=event.get('id'))
            continue
        pattern = event.get('pattern')
        if pattern == 'GLOW':
            fail('CONTINUOUS_GLOW', event_id=event.get('id'))
        if event.get('repeat_count', 1) != 1 or pattern == 'PULSE':
            fail('EXCESSIVE_PULSE', event_id=event.get('id'))
        if event.get('sfx', 'NONE') != 'NONE':
            fail('SFX_OVERDENSITY', event_id=event.get('id'))
        if pattern == 'TEXT_CHARACTER_REVEAL' and end-start > 18:
            fail('TEXT_MOTION_OVERLOAD', event_id=event.get('id'))
        if pattern == 'MARKER_POP' and end-start > 45:
            fail('REFERENCE_EFFECTS_MARKER_TOO_LONG', event_id=event.get('id'))
        if pattern not in {'NONE', 'MARKER_POP', 'TEXT_CHARACTER_REVEAL'}:
            fail('REFERENCE_EFFECTS_UNOBSERVED_PATTERN', event_id=event.get('id'))
        if pattern != 'NONE':
            for c in scene.get('second_event_camera', {}).get('timeline', []):
                if ('ZOOM' in c['state'] or c['state'] == 'ZOOM_OUT') and start < c['end_frame'] and end > c['start_frame']:
                    fail('EFFECT_DURING_UNREADABLE_CAMERA_MOTION', event_id=event.get('id'))
    for frame in range(total):
        active = [e for e in events if isinstance(e.get('start_frame'), int) and isinstance(e.get('end_frame'), int)
                  and e['start_frame'] <= frame < e['end_frame'] and e.get('primary')]
        if len(active) > 1:
            fail('TOO_MANY_SIMULTANEOUS_EFFECTS', frame=frame)
            break
    return dict(passed=not errors, errors=errors, warnings=[], added_sfx=0,
                physical_gpu='NOT_RUN')


def apply_effects(plan, enabled=True):
    if not isinstance(enabled, bool):
        raise ValueError('REFERENCE_EFFECTS_SELECTION_INVALID')
    if not enabled:
        if (plan.get('metadata', {}).get('reference_effects') is not None
                or any('reference_effects' in s for s in plan.get('scenes', []))):
            raise ValueError('REFERENCE_EFFECTS_OFF_REQUIRES_PARENT_PLAN')
        return deepcopy(plan)
    if not parent.validate_quality(plan)['passed']:
        raise ValueError('REFERENCE_EFFECTS_V019_BASELINE_REQUIRED')
    value = deepcopy(plan)
    contract = _contract()
    for scene in value['scenes']:
        scene['reference_effects'] = dict(**deepcopy(contract), events=_events(scene))
    value['metadata']['reference_effects'] = dict(version=VERSION, source_hashes=contract['source_hashes'])
    install_validation()
    from .schema import validate_plan
    value['gate'] = validate_plan(value)
    if not value['gate']['passed']:
        raise ValueError('REFERENCE_EFFECTS_PLAN_INVALID')
    return value


def validate_effects(plan):
    errors = []
    try:
        contract = _contract()
        baseline = deepcopy(plan)
        baseline.get('metadata', {}).pop('reference_effects', None)
        for scene in baseline.get('scenes', []):
            scene.pop('reference_effects', None)
        if not parent.validate_quality(baseline)['passed']:
            errors.append(dict(code='REFERENCE_EFFECTS_V019_BASELINE_REQUIRED'))
        if plan.get('metadata', {}).get('reference_effects') != dict(version=VERSION, source_hashes=contract['source_hashes']):
            errors.append(dict(code='REFERENCE_EFFECTS_METADATA_MISMATCH'))
        for scene in plan.get('scenes', []):
            if scene.get('reference_effects') != dict(**contract, events=_events(scene)):
                errors.append(dict(code='REFERENCE_EFFECTS_SOURCE_OR_EVENT_MISMATCH', scene_id=scene.get('scene_id')))
            errors.extend(effect_qc(scene)['errors'])
        if not plan.get('scenes'):
            errors.append(dict(code='REFERENCE_EFFECTS_SCENES_REQUIRED'))
    except (KeyError, TypeError, ValueError, OSError, AttributeError) as error:
        errors.append(dict(code=str(error).split(':')[0] if isinstance(error, ValueError) else 'REFERENCE_EFFECTS_DEPENDENCY_INVALID'))
    return dict(passed=not errors, errors=errors, warnings=[], version=VERSION,
                parent_version=parent.VERSION, added_textures=0, added_sfx=0,
                physical_gpu='NOT_RUN')


def install_validation():
    from . import schema, gpu_preflight
    if getattr(schema.validate_plan, 'reference_effects_wrapper', False):
        gpu_preflight.validate_plan = schema.validate_plan
        return
    parent.install_validation()
    original = schema.validate_plan
    def checked(plan):
        selected = plan.get('metadata', {}).get('reference_effects') is not None or any('reference_effects' in s for s in plan.get('scenes', []))
        if not selected:
            return original(plan)
        effects = validate_effects(plan)
        if not effects['passed']:
            return effects
        baseline = deepcopy(plan)
        baseline['metadata'].pop('reference_effects', None)
        for scene in baseline['scenes']:
            scene.pop('reference_effects', None)
        return {**original(baseline), 'reference_effects': dict(passed=True, version=VERSION)}
    checked.reference_effects_wrapper = True
    checked.event_quality_wrapper = getattr(original, 'event_quality_wrapper', False)
    checked.visual_quality_wrapper = getattr(original, 'visual_quality_wrapper', False)
    checked.single_test_wrapper = getattr(original, 'single_test_wrapper', False)
    schema.validate_plan = checked
    gpu_preflight.validate_plan = checked


def renderer_version(scene):
    base = parent.renderer_version(scene)
    if not scene.get('reference_effects'):
        return base
    digest = hashlib.sha256(b'REFERENCE_EFFECTS/v020' + bytes.fromhex(base))
    digest.update(json.dumps(scene['reference_effects'], sort_keys=True, separators=(',', ':')).encode())
    return digest.hexdigest()


def project_renderer_version(plan):
    if not any(s.get('reference_effects') for s in plan['scenes']):
        return parent.project_renderer_version(plan)
    return hashlib.sha256(json.dumps({s['scene_id']: renderer_version(s) for s in plan['scenes']},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def diagnostic_record(plan):
    return dict(version=VERSION, qc=validate_effects(plan),
                reference_sha256=REFERENCE_SHA256,
                scenes=[dict(scene_id=s['scene_id'], events=s['reference_effects']['events'],
                             timeline=effect_timeline(s)) for s in plan['scenes']],
                sfx='UNCONFIRMED_IN_MIXED_REFERENCE; exact existing audio retained',
                physical_gpu='NOT_RUN')


def record_source_report(directory, plan, assets=None, *, original=None):
    from .storage import atomic_json
    import os
    directory = Path(directory)
    report = (original or parent.record_source_report)(directory, plan, assets)
    quality = validate_effects(plan)
    if not quality['passed']:
        raise ValueError('REFERENCE_EFFECTS_SOURCE_REPORT_INVALID')
    report['reference_effects'] = quality
    report['renderer_version'] = project_renderer_version(plan)
    report['license_notice'] += ' v020 transfers observed sparse entrance timing only. No reference artwork, story, colour, typography or audio is copied; existing v019 graphics and audio remain unchanged.'
    atomic_json(directory / 'source_report.json', report)
    atomic_json(directory / 'reference_effects_plan.json', diagnostic_record(plan), exclusive=True)
    with (directory / 'source_report.md').open('a', encoding='utf-8') as stream:
        stream.write('\n\n## v020 sparse reference effect layer\n\n' + report['license_notice'] + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    return report
