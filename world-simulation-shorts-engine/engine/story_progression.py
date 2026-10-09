"""Authored event information progresses inside an immutable camera lock.

No story, GIS line, object, sound or camera motion is generated here. The
versioned layer binds short observed text accents to existing source records.
Its OFF branch is the exact v020 plan and renderer/cache identity.
"""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import math

from . import reference_effects as parent
from .frame_grid import FrameGrid

ROOT = parent.ROOT
VERSION = 'v021'
PROFILE_URL = '/static/story_progression_v021.json'
REFERENCE_SHA256 = parent.REFERENCE_SHA256
SOURCES = ('engine/story_progression.py', 'engine/story_progression_backend.py',
           'web/story_progression_adapter.js', 'web/render_story_progression_earth.html',
           'data/story_progression_v021.json', 'web/story_progression_v021.json')
PHASES = ('EVENT_REVEAL', 'STATE_CHANGE', 'PERCEPTION', 'LOCATION_EMPHASIS', 'EVENT_STATE')
QC_CODES = ('CAMERA_CHANGED_DURING_EVENT_VIEW', 'TOO_MANY_PRIMARY_EFFECTS',
            'CONTINUOUS_EFFECT', 'UNSUPPORTED_STORY_EVENT', 'FAKE_GEOMETRY',
            'TEXT_PRIORITY_CONFLICT', 'MICRO_BEAT_OVERDENSITY')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def hashes():
    return {name: _sha(ROOT / name) for name in SOURCES}


def _expected_profile():
    return dict(version=VERSION, parent_version=parent.VERSION,
                reference_sha256=REFERENCE_SHA256,
                timing=dict(reference_fps=30, text_reveal_frames=17,
                            recognition_gap_frames=24, location_emphasis_frames=17),
                typography=dict(event_size_px=64, event_weight=400,
                                event_opacity=.98, location_opacity=.60),
                patterns=dict(TEXT_REVEAL_HALO=dict(max_frames=17, primary=False),
                              LOCATION_TEXT_HALO=dict(max_frames=17, primary=True)),
                limits=dict(max_primary=1, max_added_sfx=0, max_added_textures=0,
                            max_effect_frames=17, max_location_emphasis_per_event=1),
                geometry=dict(status='NOT_AVAILABLE_IN_CURRENT_SCENE',
                              action='NO_BOUNDARY_DRAW_WITHOUT_AUTHORED_EVENT_BOUND_GIS'),
                evidence=[dict(id='REF_LABEL_CHARACTER_ENTRANCE', start_frame=289,
                               end_frame=306, second_start_frame=311, second_end_frame=328),
                          dict(id='REF_SHORT_LABEL_HALO', start_frame=289, end_frame=306)],
                audio=dict(action='Preserve exact v020 audio; no new SFX or TTS'),
                design=dict(font='Existing Noto Cinema; weight preserved',
                            halo='Brief neutral text-local halo only; no reference colour copied',
                            texture_uploads=0, shader_changes=False))


def _typed(value):
    if isinstance(value, dict):
        return all(isinstance(k, str) and _typed(v) for k, v in value.items())
    if isinstance(value, list):
        return all(_typed(v) for v in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return value is None or isinstance(value, (str, bool, int))


def _strict_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        return (set(actual) == set(expected)
                and all(_strict_equal(actual[key], expected[key]) for key in actual))
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(_strict_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _profile():
    source = ROOT / 'data/story_progression_v021.json'
    served = ROOT / 'web/story_progression_v021.json'
    if source.read_bytes() != served.read_bytes():
        raise ValueError('STORY_PROGRESSION_SERVED_PROFILE_MISMATCH')
    value = json.loads(source.read_text())
    if not _typed(value) or not _strict_equal(value, _expected_profile()):
        raise ValueError('STORY_PROGRESSION_PROFILE_INVALID')
    integer_paths = [('timing', key) for key in value['timing']]
    integer_paths += [('limits', key) for key in value['limits']]
    integer_paths += [('typography', 'event_size_px'), ('typography', 'event_weight')]
    if any(type(value[a][b]) is not int for a, b in integer_paths):
        raise ValueError('STORY_PROGRESSION_PROFILE_TYPE_INVALID')
    if any(type(e[k]) is not int for e in value['evidence'] for k in e if k.endswith('_frame')):
        raise ValueError('STORY_PROGRESSION_EVIDENCE_TYPE_INVALID')
    return value


def _contract():
    _profile()
    parent._contract()
    return dict(version=VERSION, parent_version=parent.VERSION, profile_url=PROFILE_URL,
                profile_sha256=_sha(ROOT / 'web/story_progression_v021.json'),
                source_hashes=hashes(), parent_source_hashes=parent.hashes())


def _clock(scene, fps=None):
    duration = scene.get('duration')
    total = scene.get('frame_count')
    if (isinstance(duration, bool) or not isinstance(duration, (int, float))
            or not math.isfinite(duration) or duration <= 0
            or type(total) is not int or total <= 0):
        raise ValueError('STORY_PROGRESSION_FRAME_GRID_INVALID')
    if fps is None:
        grid = scene.get('frame_grid', {})
        if not isinstance(grid, dict):
            raise ValueError('STORY_PROGRESSION_FPS_INVALID')
        fps = grid.get('fps', scene.get('fps'))
    if fps is None:
        fps = Fraction(total, 1) / Fraction(str(duration))
    if isinstance(fps, bool):
        raise ValueError('STORY_PROGRESSION_FPS_INVALID')
    try:
        clock = FrameGrid(fps)
    except (ValueError, TypeError, ZeroDivisionError):
        raise ValueError('STORY_PROGRESSION_FPS_INVALID') from None
    if abs(float(clock.fps) * duration - total) > 1e-7:
        raise ValueError('STORY_PROGRESSION_FRAME_GRID_INVALID')
    return clock


def _frame(clock, seconds):
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds)):
        raise ValueError('STORY_PROGRESSION_TIME_INVALID')
    frame = clock.frames(seconds)
    if abs(float(clock.fps) * seconds - frame) > 1e-7:
        raise ValueError('STORY_PROGRESSION_TIME_NOT_ON_FRAME_GRID')
    return frame


def _camera_snapshot(scene):
    return {key: deepcopy(scene.get(key)) for key in
            ('camera_start', 'camera_end', 'camera_preset', 'camera_easing', 'camera_speed',
             'second_event_camera', 'return_wide_camera', 'single_event_camera', 'direction',
             'entry_state', 'exit_state', 'motion_timing')}


def _source_snapshot(scene):
    return {key: deepcopy(scene.get(key)) for key in
            ('scene_id', 'start_time', 'duration', 'frame_count', 'scene_start_frame',
             'scene_end_frame', 'visual_events', 'text_events', 'labels', 'geographic_targets',
             'narration', 'narration_event_ids', 'claim_ids', 'routes', 'entities', 'sound_events')}


def _quality_snapshot(scene):
    return {key: deepcopy(scene.get(key)) for key in
            ('visual_quality', 'event_quality', 'lighting_preset', 'render_quality', 'visual_polish',
             'render_mode', 'visual_mode', 'reference_effects')}


def _locked_windows(scene, total):
    """Read declared camera locks; merge only contiguous identical camera keys."""
    if scene.get('second_event_camera'):
        camera = scene['second_event_camera']
        if not isinstance(camera, dict) or not isinstance(camera.get('timeline'), list):
            raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
        entries = []
        for index, item in enumerate(camera.get('timeline', [])):
            if not isinstance(item, dict):
                raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
            state = item.get('state', '')
            if state in {'EVENT1_VIEW', 'EVENT1_HOLD', 'EVENT1_RESOLVED'}:
                key = 'event1_camera'
            elif state in {'EVENT2_VIEW', 'EVENT2_HOLD', 'EVENT2_RESOLVED'}:
                key = 'event2_camera'
            else:
                continue
            if key not in camera:
                raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
            entries.append(dict(start_frame=item.get('start_frame'), end_frame=item.get('end_frame'),
                                camera_key=key, source_path=f'second_event_camera.timeline[{index}]'))
    else:
        direction = scene.get('direction', {})
        if not isinstance(direction, dict):
            raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
        raw = direction.get('locked_windows', [])
        if not isinstance(raw, list):
            raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
        entries = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or set(item) != {'start_frame', 'end_frame', 'camera_key'}:
                raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
            # An abstract word such as "locked" is not evidence that a moving
            # camera is actually fixed. This generic planning input references
            # a real static endpoint pose; production moving rigs require an
            # independently verified pose-window contract before admission.
            if (item['camera_key'] not in {'camera_start', 'camera_end'}
                    or not isinstance(scene.get(item['camera_key']), dict)
                    or scene.get('camera_start') != scene.get('camera_end')):
                raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
            entries.append(dict(**item, source_path=f'direction.locked_windows[{index}]'))
    merged = []
    for item in entries:
        a, b = item['start_frame'], item['end_frame']
        if (type(a) is not int or type(b) is not int or not 0 <= a < b <= total
                or not isinstance(item['camera_key'], str) or not item['camera_key']):
            raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
        if merged and a < merged[-1]['end_frame']:
            raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
        if merged and a == merged[-1]['end_frame'] and item['camera_key'] == merged[-1]['camera_key']:
            merged[-1]['end_frame'] = b
            merged[-1]['source_paths'].append(item['source_path'])
        else:
            merged.append(dict(start_frame=a, end_frame=b, camera_key=item['camera_key'],
                               source_paths=[item['source_path']]))
    return merged


def _compile_microbeats(scene, fps=None):
    """Plan only exact authored status records; no named-place or time special case."""
    if not isinstance(scene, dict) or not _typed(scene):
        raise ValueError('UNSUPPORTED_STORY_EVENT')
    clock = _clock(scene, fps)
    total = scene['frame_count']
    windows = _locked_windows(scene, total)
    events = scene.get('visual_events', [])
    statuses = scene.get('text_events', [])
    labels = scene.get('labels', [])
    if not all(isinstance(value, list) for value in (events, statuses, labels)):
        raise ValueError('UNSUPPORTED_STORY_EVENT')
    if any(not isinstance(label, dict) for label in labels):
        raise ValueError('UNSUPPORTED_STORY_EVENT')
    ids = [e.get('id') for e in events if isinstance(e, dict)]
    if len(ids) != len(events) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('UNSUPPORTED_STORY_EVENT')
    selected = []
    for text_index, text in enumerate(statuses):
        if not isinstance(text, dict):
            raise ValueError('UNSUPPORTED_STORY_EVENT')
        if text.get('role') != 'status' or not text.get('text'):
            continue
        matches = [(i, event) for i, event in enumerate(events) if event.get('id') == text.get('event_id')]
        if (len(matches) != 1 or not isinstance(text.get('text'), str)
                or not isinstance(text.get('id'), str) or not text['id']):
            raise ValueError('UNSUPPORTED_STORY_EVENT')
        event_index, event = matches[0]
        if (event.get('kind') not in {'route_blocked', 'milestone_reveal', 'event_start',
                                     'event_state_change', 'event_resolved', 'state_change',
                                     'status_reveal', 'counter_update', 'new_variable',
                                     'route_reroute', 'consequence_reveal'}
                or not isinstance(event.get('coordinates'), dict)
                or not isinstance(text.get('coordinates'), dict)
                or any(isinstance(text['coordinates'].get(k), bool)
                       or not isinstance(text['coordinates'].get(k), (int, float))
                       or not math.isfinite(text['coordinates'][k]) for k in ('lon', 'lat'))
                or event.get('text') != text['text'] or event.get('coordinates') != text.get('coordinates')
                or not isinstance(event.get('target_id'), str) or not event['target_id']
                or event['coordinates'].get('location_id') != event['target_id']):
            raise ValueError('UNSUPPORTED_STORY_EVENT')
        from .gis import verified_coordinate
        if not verified_coordinate(text['coordinates']):
            raise ValueError('UNSUPPORTED_STORY_EVENT')
        start, end = _frame(clock, text.get('start_time')), _frame(clock, text.get('end_time'))
        if start != _frame(clock, event.get('time')) or not 0 <= start < end <= total:
            raise ValueError('STORY_PROGRESSION_SOURCE_TIMING_INVALID')
        lock = next((w for w in windows if w['start_frame'] <= start < w['end_frame']), None)
        if lock is None:
            raise ValueError('CAMERA_CHANGED_DURING_EVENT_VIEW')
        selected.append(dict(event=event, event_index=event_index, text=text, text_index=text_index,
                             start_frame=start, end_frame=min(end, lock['end_frame']), lock=lock))
    selected.sort(key=lambda item: (item['start_frame'], item['event_index']))
    if len({item['event']['id'] for item in selected}) != len(selected):
        raise ValueError('TEXT_PRIORITY_CONFLICT')
    for left, right in zip(selected, selected[1:]):
        if (left['event']['target_id'] == right['event']['target_id']
                and left['end_frame'] > right['start_frame']):
            raise ValueError('TEXT_PRIORITY_CONFLICT')
    timing = _profile()['timing']
    reveal_frames = max(1, clock.frames(Fraction(timing['text_reveal_frames'], timing['reference_fps'])))
    gap_frames = max(1, clock.frames(Fraction(timing['recognition_gap_frames'], timing['reference_fps'])))
    emphasis_frames = max(1, clock.frames(Fraction(timing['location_emphasis_frames'], timing['reference_fps'])))
    beats = []
    for item in selected:
        event, text = item['event'], item['text']
        start, end = item['start_frame'], item['end_frame']
        # A source state may extend beyond its camera lock; it is never retimed.
        next_state = next((v for v in selected if v['start_frame'] > start
                           and v['event']['target_id'] == event['target_id']), None)
        if next_state:
            end = min(end, next_state['start_frame'])
        if end - start < reveal_frames:
            raise ValueError('MICRO_BEAT_OVERDENSITY')
        predecessor = next((v for v in selected if v['event']['id'] == event.get('caused_by')
                            and v['event']['target_id'] == event['target_id']
                            and v['start_frame'] < start), None)
        source = dict(event_path=f'visual_events[{item["event_index"]}]',
                      text_path=f'text_events[{item["text_index"]}]',
                      event_sha256=_json_sha(event), text_sha256=_json_sha(text))
        location_matches = [(i, label) for i, label in enumerate(labels)
                            if label.get('coordinates') == text['coordinates']
                            and label.get('text') and label.get('role') in {'city', 'country'}
                            and _frame(clock, label.get('start_time')) <= start
                            and _frame(clock, label.get('end_time')) >= end]
        location_ref = location_matches[0][0] if len(location_matches) == 1 else None

        def add(phase, a, b, pattern='NONE', primary=False, label_ref=None):
            if a >= b:
                return
            beats.append(dict(id=f'SP_{event["id"]}_{phase}', phase=phase,
                              story_event_id=event['id'], text_event_id=text['id'],
                              start_frame=a, end_frame=b, primary_information=text['text'],
                              pattern=pattern, primary=primary, coordinates=deepcopy(text['coordinates']),
                              target_id=event['target_id'], claim_id=event.get('claim_id'),
                              caused_by=event.get('caused_by'), source_ref=deepcopy(source),
                              location_label_ref=label_ref, camera_lock_ref=deepcopy(item['lock']),
                              geometry_ref=None, semantic_segment_ref=None,
                              reference_evidence_ids=['REF_SHORT_LABEL_HALO'] if pattern != 'NONE' else []))

        reveal_end = start + reveal_frames
        add('STATE_CHANGE' if predecessor else 'EVENT_REVEAL', start, reveal_end,
            'TEXT_REVEAL_HALO', False)
        # Existing state replacement gets no second location effect. Neither a
        # short camera lock nor lack of geometry is filled with invented content.
        use_emphasis = (predecessor is None and location_ref is not None
                        and end - reveal_end >= gap_frames + emphasis_frames + 1)
        perception_end = reveal_end + gap_frames if use_emphasis else end
        add('PERCEPTION', reveal_end, perception_end)
        if use_emphasis:
            emphasis_end = perception_end + emphasis_frames
            add('LOCATION_EMPHASIS', perception_end, emphasis_end,
                'LOCATION_TEXT_HALO', True, location_ref)
            add('EVENT_STATE', emphasis_end, end)
    return beats


def compile_microbeats(scene, fps=None):
    """Fail closed with a typed rule for malformed public planning inputs."""
    try:
        return _compile_microbeats(scene, fps)
    except (KeyError, TypeError, AttributeError, ZeroDivisionError):
        raise ValueError('UNSUPPORTED_STORY_EVENT') from None


def _selection(scene, fps=None):
    clock = _clock(scene, fps)
    return dict(**_contract(), fps=str(clock.fps),
                source_sha256=_json_sha(_source_snapshot(scene)),
                camera_sha256=_json_sha(_camera_snapshot(scene)),
                quality_sha256=_json_sha(_quality_snapshot(scene)),
                boundary=dict(status='NOT_AVAILABLE', geometry_ref=None,
                              reason='No event-bound canal/region GIS geometry is authored in this Scene'),
                microbeats=compile_microbeats(scene, clock.fps))


def progression_timeline(scene):
    selected = scene.get('story_progression')
    beats = selected.get('microbeats', []) if selected else []
    clock = _clock(scene, selected.get('fps') if selected else None)
    total = scene['frame_count']
    camera = scene.get('second_event_camera', {}).get('timeline', [])
    boundaries = {0, total}
    for item in camera + beats:
        boundaries.update((item['start_frame'], item['end_frame']))
    parent_events = scene.get('reference_effects', {}).get('events', [])
    for item in parent_events:
        boundaries.update((item['start_frame'], item['end_frame']))
    rows = []
    points = sorted(v for v in boundaries if 0 <= v <= total)
    for start, end in zip(points, points[1:]):
        active = [b for b in beats if b['start_frame'] <= start < b['end_frame']]
        inherited = next(((i, e) for i, e in enumerate(parent_events)
                          if e['start_frame'] <= start < e['end_frame']), None)
        inherited_event = inherited[1] if inherited else None
        inherited_text = inherited_event.get('text') if inherited_event else None
        inherited_source = (dict(path=f'reference_effects.events[{inherited[0]}]',
                                 sha256=_json_sha(inherited_event)) if inherited else None)
        camera_state = next((c['state'] for c in camera if c['start_frame'] <= start < c['end_frame']), 'UNKNOWN')
        rows.append(dict(start_frame=start, end_frame=end, frame_count=end-start,
                         start_seconds=clock.seconds(start), end_seconds=clock.seconds(end),
                         camera_state=camera_state,
                         story_state=next((b['phase'] for b in active), 'NONE'),
                         story_event_id=next((b['story_event_id'] for b in active), None),
                         primary_information=next((b['primary_information'] for b in active), inherited_text or None),
                         visual_effect=next((b['pattern'] for b in active), 'NONE'),
                         source_refs=[b['source_ref'] for b in active],
                         parent_story_event_id=inherited_event.get('story_event_id') if inherited_event else None,
                         parent_story_state=(inherited_event['type'] if inherited_event and inherited_event['pattern'] != 'NONE' else 'NONE'),
                         parent_primary_information=inherited_text or None,
                         parent_visual_effect=inherited_event['pattern'] if inherited_event else 'NONE',
                         parent_source_ref=inherited_source, added_sfx='NONE'))
    return rows


def progression_qc(scene):
    errors = []
    selected = scene.get('story_progression')
    if selected is None:
        return dict(passed=True, errors=[], warnings=[], enabled=False, added_sfx=0)
    def fail(code, **context):
        row = dict(code=code, **context)
        if row not in errors:
            errors.append(row)
    try:
        if not isinstance(selected, dict) or not _typed(selected):
            raise ValueError('UNSUPPORTED_STORY_EVENT')
        total = scene['frame_count']
        beats = selected.get('microbeats')
        if not isinstance(beats, list):
            raise ValueError('UNSUPPORTED_STORY_EVENT')
        if selected.get('camera_sha256') != _json_sha(_camera_snapshot(scene)):
            fail('CAMERA_CHANGED_DURING_EVENT_VIEW')
        if selected.get('boundary') != dict(status='NOT_AVAILABLE', geometry_ref=None,
                                           reason='No event-bound canal/region GIS geometry is authored in this Scene'):
            fail('FAKE_GEOMETRY')
        for beat in beats:
            if not isinstance(beat, dict):
                fail('UNSUPPORTED_STORY_EVENT')
                continue
            if beat.get('geometry_ref') is not None:
                fail('FAKE_GEOMETRY', microbeat_id=beat.get('id'))
            if beat.get('semantic_segment_ref') is not None:
                fail('UNSUPPORTED_STORY_EVENT', microbeat_id=beat.get('id'))
            if beat.get('pattern') not in {'NONE', 'TEXT_REVEAL_HALO', 'LOCATION_TEXT_HALO'}:
                fail('CONTINUOUS_EFFECT', microbeat_id=beat.get('id'))
            if beat.get('phase') not in PHASES or type(beat.get('primary')) is not bool:
                fail('UNSUPPORTED_STORY_EVENT', microbeat_id=beat.get('id'))
            a, b = beat.get('start_frame'), beat.get('end_frame')
            if type(a) is not int or type(b) is not int or not 0 <= a < b <= total:
                fail('MICRO_BEAT_OVERDENSITY', microbeat_id=beat.get('id'))
                continue
            if beat.get('pattern') != 'NONE' and b-a > max(1, _clock(scene, selected.get('fps')).frames(Fraction(17, 30))):
                fail('CONTINUOUS_EFFECT', microbeat_id=beat.get('id'))
        expected = compile_microbeats(scene, selected.get('fps'))
        if not _strict_equal(beats, expected):
            fail('UNSUPPORTED_STORY_EVENT')
        if selected.get('source_sha256') != _json_sha(_source_snapshot(scene)):
            fail('UNSUPPORTED_STORY_EVENT')
        if selected.get('quality_sha256') != _json_sha(_quality_snapshot(scene)):
            fail('STORY_PROGRESSION_VISUAL_QUALITY_CHANGED')
        parent_events = scene.get('reference_effects', {}).get('events', [])
        for frame in range(total):
            primary = [b for b in beats if isinstance(b, dict) and type(b.get('start_frame')) is int
                       and type(b.get('end_frame')) is int and b['start_frame'] <= frame < b['end_frame']
                       and b.get('primary')]
            primary += [e for e in parent_events if e.get('primary') and e['start_frame'] <= frame < e['end_frame']]
            if len(primary) > 1:
                fail('TOO_MANY_PRIMARY_EFFECTS', frame=frame)
                break
        status_beats = [b for b in beats if isinstance(b, dict) and b.get('phase') in {'EVENT_REVEAL', 'STATE_CHANGE'}]
        for left, right in zip(status_beats, status_beats[1:]):
            if left['end_frame'] > right['start_frame']:
                fail('TEXT_PRIORITY_CONFLICT')
    except (KeyError, ValueError, TypeError, AttributeError, OSError) as error:
        fail(str(error).split(':')[0] if isinstance(error, ValueError) else 'UNSUPPORTED_STORY_EVENT')
    return dict(passed=not errors, errors=errors, warnings=[], enabled=True,
                version=VERSION, added_sfx=0, added_textures=0, physical_gpu='NOT_RUN')


def apply_progression(plan, enabled=True):
    if type(enabled) is not bool:
        raise ValueError('STORY_PROGRESSION_SELECTION_INVALID')
    if not enabled:
        if (plan.get('metadata', {}).get('story_progression') is not None
                or any('story_progression' in s for s in plan.get('scenes', []))):
            raise ValueError('STORY_PROGRESSION_OFF_REQUIRES_PARENT_PLAN')
        return deepcopy(plan)
    if not parent.validate_effects(plan)['passed']:
        raise ValueError('STORY_PROGRESSION_V020_BASELINE_REQUIRED')
    value = deepcopy(plan)
    fps = value.get('metadata', {}).get('frame_grid', {}).get('fps')
    contract = _contract()
    for scene in value['scenes']:
        scene['story_progression'] = _selection(scene, fps)
    value['metadata']['story_progression'] = dict(version=VERSION, source_hashes=contract['source_hashes'])
    install_validation()
    from .schema import validate_plan
    value['gate'] = validate_plan(value)
    if not value['gate']['passed']:
        raise ValueError('STORY_PROGRESSION_PLAN_INVALID')
    return value


def validate_progression(plan):
    errors = []
    try:
        contract = _contract()
        baseline = deepcopy(plan)
        baseline.get('metadata', {}).pop('story_progression', None)
        for scene in baseline.get('scenes', []):
            scene.pop('story_progression', None)
        if not parent.validate_effects(baseline)['passed']:
            errors.append(dict(code='STORY_PROGRESSION_V020_BASELINE_REQUIRED'))
        if plan.get('metadata', {}).get('story_progression') != dict(version=VERSION, source_hashes=contract['source_hashes']):
            errors.append(dict(code='STORY_PROGRESSION_METADATA_MISMATCH'))
        fps = plan.get('metadata', {}).get('frame_grid', {}).get('fps')
        for scene in plan.get('scenes', []):
            if not _strict_equal(scene.get('story_progression'), _selection(scene, fps)):
                errors.append(dict(code='STORY_PROGRESSION_SOURCE_OR_EVENT_MISMATCH', scene_id=scene.get('scene_id')))
            errors.extend(progression_qc(scene)['errors'])
        if not plan.get('scenes'):
            errors.append(dict(code='STORY_PROGRESSION_SCENES_REQUIRED'))
    except (KeyError, TypeError, ValueError, OSError, AttributeError) as error:
        errors.append(dict(code=str(error).split(':')[0] if isinstance(error, ValueError) else 'STORY_PROGRESSION_DEPENDENCY_INVALID'))
    return dict(passed=not errors, errors=errors, warnings=[], version=VERSION,
                parent_version=parent.VERSION, added_textures=0, added_sfx=0,
                physical_gpu='NOT_RUN')


def install_validation():
    from . import schema, gpu_preflight
    if getattr(schema.validate_plan, 'story_progression_wrapper', False):
        gpu_preflight.validate_plan = schema.validate_plan
        return
    parent.install_validation()
    original = schema.validate_plan
    def checked(plan):
        selected = plan.get('metadata', {}).get('story_progression') is not None or any('story_progression' in s for s in plan.get('scenes', []))
        if not selected:
            return original(plan)
        result = validate_progression(plan)
        if not result['passed']:
            return result
        baseline = deepcopy(plan)
        baseline['metadata'].pop('story_progression', None)
        for scene in baseline['scenes']:
            scene.pop('story_progression', None)
        return {**original(baseline), 'story_progression': dict(passed=True, version=VERSION)}
    checked.story_progression_wrapper = True
    for name in ('reference_effects_wrapper', 'event_quality_wrapper', 'visual_quality_wrapper', 'single_test_wrapper'):
        setattr(checked, name, getattr(original, name, False))
    schema.validate_plan = checked
    gpu_preflight.validate_plan = checked


def renderer_version(scene):
    base = parent.renderer_version(scene)
    if not scene.get('story_progression'):
        return base
    digest = hashlib.sha256(b'STORY_PROGRESSION/v021' + bytes.fromhex(base))
    digest.update(json.dumps(scene['story_progression'], sort_keys=True, separators=(',', ':')).encode())
    return digest.hexdigest()


def project_renderer_version(plan):
    if not any(s.get('story_progression') for s in plan['scenes']):
        return parent.project_renderer_version(plan)
    return hashlib.sha256(json.dumps({s['scene_id']: renderer_version(s) for s in plan['scenes']},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def diagnostic_record(plan):
    return dict(version=VERSION, qc=validate_progression(plan), reference_sha256=REFERENCE_SHA256,
                scenes=[dict(scene_id=s['scene_id'], fps=s['story_progression']['fps'],
                             source_sha256=s['story_progression']['source_sha256'],
                             camera_sha256=s['story_progression']['camera_sha256'],
                             quality_sha256=s['story_progression']['quality_sha256'],
                             boundary=s['story_progression']['boundary'],
                             microbeats=s['story_progression']['microbeats'],
                             timeline=progression_timeline(s)) for s in plan['scenes']],
                audio='EXACT_V020_AUDIO; NO_ADDED_SFX_OR_TTS', physical_gpu='NOT_RUN')


def record_source_report(directory, plan, assets=None, *, original=None):
    from .storage import atomic_json
    import os
    directory = Path(directory)
    report = (original or parent.record_source_report)(directory, plan, assets)
    result = validate_progression(plan)
    if not result['passed']:
        raise ValueError('STORY_PROGRESSION_SOURCE_REPORT_INVALID')
    report['story_progression'] = result
    report['renderer_version'] = project_renderer_version(plan)
    report['license_notice'] += ' v021 sequences only authored event information in existing camera locks. No event, boundary, texture, entity, sound, narration, or geographic content is invented or copied.'
    atomic_json(directory / 'source_report.json', report)
    atomic_json(directory / 'story_progression_plan.json', diagnostic_record(plan), exclusive=True)
    with (directory / 'source_report.md').open('a', encoding='utf-8') as stream:
        stream.write('\n\n## v021 authored story progression\n\n' + report['license_notice'] + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    return report
