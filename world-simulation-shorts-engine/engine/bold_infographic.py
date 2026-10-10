"""Additive v023 visual hierarchy over the immutable v022 GIS/state contract.

Only verified native polygons are selected. A country containing a sourced
event point is a geographic backdrop, never an invented event area. Existing
camera, material, event state, marker and text contracts are not rewritten.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math
from urllib.parse import urlsplit, urlunsplit
from functools import lru_cache

from . import infographic_contract as parent

ROOT = parent.ROOT
VERSION = 'v023'
PROFILE_ID = 'BOLD_INFOGRAPHIC_V023'
PROFILE_URL = '/static/infographic/v023/bold_profile.json'
PROFILE_PATH = ROOT / 'data/infographic/v023/bold_profile.json'
PUBLIC_PATH = ROOT / 'web/infographic/v023/bold_profile.json'
SOURCES = ('engine/bold_infographic.py', 'web/bold_infographic_adapter.js',
           'web/render_bold_infographic_earth.html',
           'data/infographic/v023/bold_profile.json',
           'web/infographic/v023/bold_profile.json')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def profile():
    if PROFILE_PATH.read_bytes() != PUBLIC_PATH.read_bytes():
        raise ValueError('BOLD_PROFILE_MIRROR_MISMATCH')
    value = json.loads(PROFILE_PATH.read_text())
    if value.get('version') != VERSION or value.get('profile_id') != PROFILE_ID:
        raise ValueError('BOLD_PROFILE_VERSION_INVALID')
    geometry = value.get('geometry', {})
    if (geometry.get('preserve_holes') is not True
            or geometry.get('horizon_occlusion') is not True
            or geometry.get('boundary_draw') is not False
            or geometry.get('blend_mode') != 'source-over'
            or geometry.get('screen_space_reference_width') != 1080):
        raise ValueError('BOLD_GEOMETRY_POLICY_INVALID')
    a, b = geometry['PRIMARY'], geometry['SECONDARY']
    if (not .35 <= a['fill_alpha'] <= .65
            or not .10 <= b['fill_alpha'] < a['fill_alpha']
            or not 6 <= a['core_width_px'] <= 12
            or not 2 <= b['core_width_px'] < a['core_width_px']
            or a['edge_width_px'] <= a['core_width_px']
            or b['edge_width_px'] <= b['core_width_px']):
        raise ValueError('BOLD_HIERARCHY_INVALID')
    if any(value['limits'][key] != 0 for key in ('added_routes', 'added_entities', 'added_sfx')):
        raise ValueError('BOLD_CONTENT_ADDITION_FORBIDDEN')
    return value


def source_hashes():
    return {name: _sha(ROOT / name) for name in SOURCES}


def _polygons(record):
    if record['geometry_type'] == 'Polygon':
        return [record['coordinates']]
    if record['geometry_type'] == 'MultiPolygon':
        return record['coordinates']
    return []


def _longitude_near(lon, reference):
    return reference + ((lon - reference + 180) % 360 - 180)


def _ring_contains(point, ring):
    """Real EPSG:4326 ring membership, including a dateline-safe longitude.

    Native vertices are never modified or converted into generated geometry.
    """
    x, y = point
    inside = False
    values = [(_longitude_near(a, x), b) for a, b in ring]
    for (ax, ay), (bx, by) in zip(values, values[1:]):
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if abs(cross) < 1e-10 and min(ax, bx)-1e-10 <= x <= max(ax, bx)+1e-10 and min(ay, by)-1e-10 <= y <= max(ay, by)+1e-10:
            return True
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside


def polygon_contains_point(record, point):
    return any(_ring_contains(point, rings[0])
               and not any(_ring_contains(point, hole) for hole in rings[1:])
               for rings in _polygons(record))


def _distance_km(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371.0088 * 2 * math.asin(min(1., math.sqrt(max(0., h))))


def _vertices(record):
    return [p for rings in _polygons(record) for ring in rings for p in ring[:-1]]


def _edges(record):
    return {tuple(sorted((tuple(a), tuple(b))))
            for rings in _polygons(record) for ring in rings
            for a, b in zip(ring, ring[1:])}


def _select_context_regions(primary, anchor, registry, maximum=6):
    """Vetted adjacent and nearby countries; no guessed borders or sea fill.

    Shared native edges prove land adjacency. Nearby island/coastal context is
    separately labelled as proximity, not a claim of a shared border. Distance
    from the actual event anchor excludes remote overseas dependencies.
    """
    edges = _edges(primary)
    rows = []
    for record in registry['geometries']:
        if record['id'] == primary['id'] or record.get('geometry_role') != 'country' or not _polygons(record):
            continue
        distance = min(_distance_km(anchor, p) for p in _vertices(record))
        shared = len(edges & _edges(record))
        if shared and distance <= 1800:
            rows.append((0, distance, record['id'], 'SHARED_NATIVE_BOUNDARY', shared, record))
        elif distance <= 650:
            rows.append((1, distance, record['id'], 'VERIFIED_GEOGRAPHIC_PROXIMITY', 0, record))
    rows.sort(key=lambda row: row[:3])
    return [dict(geometry_ref=row[2], selection_method=row[3], shared_edge_count=row[4],
                 anchor_distance_km=round(row[1], 6), record=row[5]) for row in rows[:maximum]]


@lru_cache(maxsize=48)
def _cached_context(registry_json, primary_id, anchor, maximum):
    registry = json.loads(registry_json)
    primary = next(record for record in registry['geometries'] if record['id'] == primary_id)
    return _select_context_regions(primary, anchor, registry, maximum)


def select_context_regions(primary, anchor, registry, maximum=6):
    # Cache only pure selection from the complete supplied native registry.
    # The JSON is the key, so a changed geometry/source cannot reuse a result.
    # Callers receive copies and cannot contaminate later admission/fixtures.
    return deepcopy(_cached_context(parent.canonical_json(registry), primary['id'],
                                    tuple(anchor), maximum))


def _primary_candidates(scene, registry):
    selected = scene['infographic']
    records = {g['id']: g for g in registry['geometries']}
    events = {e['id']: e for e in selected['events']}
    candidates = []
    for layer in selected.get('geometry_layers', []):
        record = records[layer['geometry_ref']]
        if _polygons(record):
            candidates.append(dict(geometry_ref=record['id'], start_frame=layer['start_frame'],
                end_frame=layer['end_frame'], event_id=layer['event_id'],
                selection_method='AUTHORED_EVENT_NATIVE_POLYGON', source_layer_id=layer['id']))
    for event in selected['events']:
        if any(row['start_frame'] <= event['start_frame'] < row['end_frame']
               and events[row['event_id']]['location_point_ref'] == event['location_point_ref']
               for row in candidates):
            continue
        point_id = event.get('location_point_ref')
        if point_id is None:
            continue
        point = records[point_id]['coordinates']
        containing = [g for g in registry['geometries'] if g.get('geometry_role') == 'country'
                      and _polygons(g) and polygon_contains_point(g, point)]
        if len(containing) == 1:
            candidates.append(dict(geometry_ref=containing[0]['id'], start_frame=event['start_frame'],
                end_frame=event['end_frame'], event_id=event['id'],
                selection_method='VERIFIED_POINT_IN_NATIVE_COUNTRY', source_layer_id=None))
    # The most recent authored location owns the visual focus. This changes no
    # event/state timing; it only prevents competing country backgrounds.
    boundaries = sorted({t for row in candidates for t in (row['start_frame'], row['end_frame'])})
    windows = []
    for start, end in zip(boundaries, boundaries[1:]):
        active = [row for row in candidates if row['start_frame'] <= start < row['end_frame']]
        if not active:
            continue
        active.sort(key=lambda row: (row['selection_method'] != 'AUTHORED_EVENT_NATIVE_POLYGON', -row['start_frame'], row['geometry_ref']))
        chosen = {**active[0], 'start_frame': start, 'end_frame': end}
        if windows and all(windows[-1][key] == chosen[key] for key in ('geometry_ref', 'event_id', 'selection_method', 'source_layer_id')) and windows[-1]['end_frame'] == start:
            windows[-1]['end_frame'] = end
        else:
            windows.append(chosen)
    return windows


def compile_bold_scene(scene, registry=None):
    registry = parent.load_registry() if registry is None else registry
    selected = scene['infographic']
    records = {g['id']: g for g in registry['geometries']}
    events = {e['id']: e for e in selected['events']}
    style = profile()
    regions = []
    for window_index, window in enumerate(_primary_candidates(scene, registry)):
        primary = records[window['geometry_ref']]
        event = events[window['event_id']]
        point_id = event.get('location_point_ref')
        # This derived anchor only sorts vetted context; it is not a new GIS
        # record, polygon, label, event location, or renderer camera target.
        anchor = records[point_id]['coordinates'] if point_id else _vertices(primary)[0]
        base = dict(start_frame=window['start_frame'], end_frame=window['end_frame'],
            event_id=event['id'], source_event_id=event['id'], primary_geometry_ref=primary['id'],
            source_layer_id=window['source_layer_id'])
        regions.append(dict(**base, id=f'BOLD_{window_index}_PRIMARY', role='PRIMARY',
            geometry_ref=primary['id'], selection_method=window['selection_method'],
            source_sha256=primary['sha256'], shared_edge_count=None, anchor_distance_km=None))
        for context_index, context in enumerate(select_context_regions(primary, anchor, registry,
                style['limits']['context_max_regions'])):
            record = context['record']
            regions.append(dict(**base, id=f'BOLD_{window_index}_SECONDARY_{context_index}', role='SECONDARY',
                geometry_ref=record['id'], selection_method=context['selection_method'],
                source_sha256=record['sha256'], shared_edge_count=context['shared_edge_count'],
                anchor_distance_km=context['anchor_distance_km']))
    ids = sorted({row['geometry_ref'] for row in regions})
    return dict(version=VERSION, profile_id=PROFILE_ID, profile_url=PROFILE_URL,
        profile_sha256=_sha(PROFILE_PATH), registry_sha256=selected['registry_sha256'],
        source_hashes=source_hashes(), parent_infographic_sha256=parent.canonical_sha(selected),
        parent_camera_sha256=parent.canonical_sha(parent._camera_snapshot(scene)),
        parent_quality_sha256=parent.canonical_sha(parent._quality_snapshot(scene)),
        total_frames=selected['total_frames'], fps=selected['fps'], regions=regions,
        geometry_ids=ids, geometries=[deepcopy(records[identifier]) for identifier in ids])


def _metadata(scenes):
    return dict(version=VERSION, profile_id=PROFILE_ID, profile_url=PROFILE_URL,
        profile_sha256=_sha(PROFILE_PATH), registry_sha256=scenes[0]['infographic']['registry_sha256'],
        source_hashes=source_hashes(), scene_contract_sha256={scene['scene_id']:
            parent.canonical_sha(scene['bold_infographic']) for scene in scenes})


def prepare_bold_infographic(plan, enabled=True):
    if type(enabled) is not bool:
        raise ValueError('BOLD_ENABLE_REQUIRES_BOOLEAN')
    if not enabled:
        if plan.get('metadata', {}).get('bold_infographic') is not None or any('bold_infographic' in s for s in plan.get('scenes', [])):
            raise ValueError('BOLD_OFF_REQUIRES_V022_BASELINE')
        return deepcopy(plan)
    if not parent.validate_infographic(plan)['passed']:
        raise ValueError('BOLD_V022_BASELINE_REQUIRED')
    value = deepcopy(plan)
    registry = parent.load_registry()
    for scene in value['scenes']:
        scene['bold_infographic'] = compile_bold_scene(scene, registry)
    value['metadata']['bold_infographic'] = _metadata(value['scenes'])
    if not validate_bold_infographic(value)['passed']:
        raise ValueError('BOLD_PLAN_INVALID')
    install_runtime()
    from .schema import validate_plan
    value['gate'] = validate_plan(value)
    if not value['gate']['passed']:
        raise ValueError('BOLD_PLAN_INVALID')
    return value


def validate_bold_scene(scene):
    errors = []
    try:
        if not parent.validate_scene_infographic(scene)['passed']:
            raise ValueError('BOLD_V022_SCENE_INVALID')
        selected = scene.get('bold_infographic')
        registry = _registry_after_parent_admission(scene['infographic']['registry_sha256'])
        if not isinstance(selected, dict) or not parent._strict(selected, compile_bold_scene(scene, registry)):
            raise ValueError('BOLD_SCENE_CONTRACT_MISMATCH')
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        errors.append(dict(code=str(error).split(':')[0] if isinstance(error, ValueError) else 'BOLD_SCENE_INVALID'))
    return dict(passed=not errors, errors=errors, warnings=[], version=VERSION, physical_gpu='NOT_RUN')


def _registry_after_parent_admission(expected_sha):
    # The original v022 admission just verified every source/feature/license.
    # Re-read the mirrored registry and check its exact admitted bytes instead
    # of repeating that expensive source proof for every child Scene.
    registry = parent._read_pair('registry.json')
    if _sha(parent.DIRECTORY / 'registry.json') != expected_sha:
        raise ValueError('BOLD_PARENT_REGISTRY_CHANGED')
    return registry


def _validate_child(plan):
    errors = []
    try:
        scenes = plan['scenes']
        if not scenes or not parent._strict(plan.get('metadata', {}).get('bold_infographic'), _metadata(scenes)):
            raise ValueError('BOLD_METADATA_MISMATCH')
        registry = _registry_after_parent_admission(scenes[0]['infographic']['registry_sha256'])
        for scene in scenes:
            selected = scene.get('bold_infographic')
            if not isinstance(selected, dict) or not parent._strict(selected, compile_bold_scene(scene, registry)):
                errors.append(dict(code='BOLD_SCENE_CONTRACT_MISMATCH', scene_id=scene['scene_id']))
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        errors.append(dict(code=str(error).split(':')[0] if isinstance(error, ValueError) else 'BOLD_PLAN_INVALID'))
    return dict(passed=not errors, errors=errors, warnings=[], version=VERSION, physical_gpu='NOT_RUN')


def validate_bold_infographic(plan):
    if not parent.validate_infographic(plan)['passed']:
        return dict(passed=False, errors=[dict(code='BOLD_V022_PLAN_INVALID')],
                    warnings=[], version=VERSION, physical_gpu='NOT_RUN')
    return _validate_child(plan)


def diagnostic_record(plan):
    return dict(version=VERSION, profile_id=PROFILE_ID, qc=validate_bold_infographic(plan),
                scenes=[dict(scene_id=scene['scene_id'], **deepcopy(scene['bold_infographic']))
                        for scene in plan['scenes']], physical_gpu='NOT_RUN',
                pixel_quality='CPU preview and real NVIDIA output are separate evidence')


def _has_child(plan):
    return ('bold_infographic' in plan.get('metadata', {})
            or any('bold_infographic' in scene for scene in plan.get('scenes', [])))


def _parent_plan_view(plan):
    # This projection is permitted only after the actual child/source proof.
    # Every original camera, event, narration, timing and GIS field is retained.
    base = deepcopy(plan)
    base['metadata'].pop('bold_infographic', None)
    for scene in base['scenes']:
        scene.pop('bold_infographic', None)
    return base


def install_runtime():
    """Extend admission, page mapping and cache identity without editing parents."""
    from . import schema, gpu_preflight, infographic_backend, semantic_timeline
    parent.install_validation()
    if not getattr(semantic_timeline.validate_production_plan, 'bold_infographic_wrapper', False):
        original_production = semantic_timeline.validate_production_plan
        def measured(plan):
            if not _has_child(plan):
                return original_production(plan)
            report = validate_bold_infographic(plan)
            if not report['passed']:
                return report
            technical = original_production(_parent_plan_view(plan))
            if not technical['passed']:
                return technical
            return {**technical, 'bold_infographic': report}
        measured.bold_infographic_wrapper = True
        semantic_timeline.validate_production_plan = measured
    if not getattr(schema.validate_plan, 'bold_infographic_wrapper', False):
        original = schema.validate_plan
        def checked(plan):
            if not _has_child(plan):
                return original(plan)
            report = validate_bold_infographic(plan)
            if not report['passed']:
                return report
            technical = original(_parent_plan_view(plan))
            if not technical['passed']:
                return technical
            return {**technical, 'bold_infographic': report}
        checked.__dict__.update(original.__dict__)
        checked.bold_infographic_wrapper = True
        schema.validate_plan = checked
        gpu_preflight.validate_plan = checked
    if not getattr(infographic_backend.infographic_command, 'bold_infographic_wrapper', False):
        original_command = infographic_backend.infographic_command
        def command(value):
            mapped = original_command(value)
            if '--scene-json' not in mapped:
                return mapped
            scene = json.loads(Path(mapped[mapped.index('--scene-json') + 1]).read_text())
            if 'bold_infographic' not in scene:
                return mapped
            if not validate_bold_scene(scene)['passed']:
                raise RuntimeError('BOLD_INFOGRAPHIC_SCENE_SOURCE_MISMATCH')
            index = mapped.index('--url') + 1
            url = urlsplit(mapped[index])
            if url.path != '/static/render_infographic_earth.html':
                raise RuntimeError('BOLD_INFOGRAPHIC_PARENT_RENDER_PAGE_INVALID')
            mapped[index] = urlunsplit(url._replace(path='/static/render_bold_infographic_earth.html'))
            return mapped
        command.bold_infographic_wrapper = True
        infographic_backend.infographic_command = command
    if not getattr(parent.renderer_version, 'bold_infographic_wrapper', False):
        original_version = parent.renderer_version
        def renderer_version(scene):
            baseline = original_version(scene)
            if 'bold_infographic' not in scene:
                return baseline
            if not validate_bold_scene(scene)['passed']:
                raise RuntimeError('BOLD_INFOGRAPHIC_CACHE_CONTRACT_INVALID')
            return hashlib.sha256(b'BOLD_INFOGRAPHIC/v023' + bytes.fromhex(baseline)
                + parent.canonical_json(scene['bold_infographic'])).hexdigest()
        renderer_version.bold_infographic_wrapper = True
        parent.renderer_version = renderer_version
    if not getattr(parent.diagnostic_record, 'bold_infographic_wrapper', False):
        original_diagnostic = parent.diagnostic_record
        def recorded(plan):
            result = original_diagnostic(plan)
            if plan.get('metadata', {}).get('bold_infographic') is not None:
                result['bold_infographic'] = diagnostic_record(plan)
            return result
        recorded.bold_infographic_wrapper = True
        parent.diagnostic_record = recorded

