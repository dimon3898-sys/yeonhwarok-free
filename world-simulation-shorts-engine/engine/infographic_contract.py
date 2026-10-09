"""Versioned sourced map-state contract; legacy v021 contracts stay strict.

The registry preserves real native GIS coordinates. Events consume authored
claims and states, never infer a polygon/line from a representative point.
"""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import math

from . import story_progression as parent
from .frame_grid import FrameGrid

ROOT = parent.ROOT
VERSION = 'v022'
DIRECTORY = ROOT / 'data/infographic/v022'
PUBLIC = ROOT / 'web/infographic/v022'
REGISTRY_URL = '/static/infographic/v022/registry.json'
PROFILE_URL = '/static/infographic/v022/profile.json'
SOURCES = ('engine/infographic_contract.py', 'engine/infographic_backend.py',
           'engine/infographic_planner.py', 'engine/semantic_timeline.py',
           'engine/infographic_framing.py', 'engine/infographic_qc.py',
           'engine/qa_planner.py', 'engine/pipeline_stability.py',
           'web/infographic_adapter.js', 'web/render_infographic_earth.html',
           'tools/build_infographic_assets.py', 'data/infographic/v022/registry.json',
           'web/infographic/v022/registry.json', 'data/infographic/v022/profile.json',
           'web/infographic/v022/profile.json', 'data/infographic/v022/SOURCES.json',
           'web/infographic/v022/SOURCES.json',
           'data/infographic/v022/production_scene_plan.schema.json',
           'web/infographic/v022/production_scene_plan.schema.json',
           'web/fonts/NotoSansCJKkr-Bold.otf',
           'web/fonts/NotoSansCJKkr-Regular.otf', 'web/fonts/BOLD_SOURCE_v022.json',
           'web/fonts/SOURCE.json', 'web/fonts/LICENSE_Noto_CJK.txt')
FAMILIES = {'story-progression-v021', 'production-earth-v1'}
ROLES = {'EVENT_TITLE', 'LOCATION_LABEL', 'SUPPORT_DATA', 'TTS_SUBTITLE'}
STATES = {'CONTEXT', 'LOCATION', 'OPEN', 'CLOSED', 'ACTIVE', 'INACTIVE', 'BLOCKED', 'PREVIOUS', 'UNCHANGED'}
EVENT_FIELDS = {'id', 'scene_id', 'semantic_segment_ref', 'claim_id', 'target_geometry_refs',
                'location_point_ref', 'state_before', 'state_after', 'start_frame',
                'transition_end_frame', 'end_frame', 'primary_role', 'evidence_type',
                'watermark', 'text', 'story_source_ref'}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize(value):
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('INFOGRAPHIC_NONFINITE')
        return int(value) if value.is_integer() else value
    return value


def canonical_json(value):
    return json.dumps(_normalize(value), sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode()


def canonical_sha(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _strict(actual, expected):
    # Integral GeoJSON float values and integer values have identical JSON
    # semantics, but bool is never an accepted numeric coordinate/frame.
    return parent._strict_equal(_normalize(actual), _normalize(expected))


def _read_pair(name):
    data, public = DIRECTORY / name, PUBLIC / name
    if not data.is_file() or not public.is_file() or data.read_bytes() != public.read_bytes():
        raise ValueError('INFOGRAPHIC_ASSET_MIRROR_MISMATCH')
    return json.loads(data.read_text())


def _definition():
    from importlib.util import spec_from_file_location,module_from_spec
    spec=spec_from_file_location('_infographic_asset_definition',ROOT/'tools/build_infographic_assets.py')
    definition=module_from_spec(spec);spec.loader.exec_module(definition)
    return definition


def load_registry():
    value = _read_pair('registry.json')
    report = validate_registry(value)
    if not report['passed']:
        raise ValueError(report['errors'][0]['code'])
    return value


def _vertices(value):
    if isinstance(value, list) and len(value) == 2 and all(type(v) in (int, float) for v in value):
        return [value]
    if not isinstance(value, list) or not value:
        raise ValueError('INFOGRAPHIC_GEOMETRY_COORDINATES_INVALID')
    return [p for child in value for p in _vertices(child)]


def validate_geometry(record):
    geometry_type = record.get('geometry_type')
    coordinates = record.get('coordinates')
    points = _vertices(coordinates)
    if any(not math.isfinite(v) for p in points for v in p) or any(not -180 <= p[0] <= 180 or not -90 <= p[1] <= 90 for p in points):
        raise ValueError('INFOGRAPHIC_GEOMETRY_COORDINATES_INVALID')
    if geometry_type == 'Point':
        if len(points) != 1 or not _strict(coordinates, points[0]):
            raise ValueError('INFOGRAPHIC_POINT_TYPE_INVALID')
    elif geometry_type in {'LineString', 'MultiLineString'}:
        lines = [coordinates] if geometry_type == 'LineString' else coordinates
        if any(not isinstance(line,list)or len(line) < 2 or any(not isinstance(p,list) or len(p)!=2 for p in line) for line in lines):
            raise ValueError('INFOGRAPHIC_LINE_TYPE_INVALID')
    elif geometry_type in {'Polygon', 'MultiPolygon'}:
        polygons = [coordinates] if geometry_type == 'Polygon' else coordinates
        for polygon in polygons:
            if not isinstance(polygon,list) or not polygon:
                raise ValueError('INFOGRAPHIC_POLYGON_TYPE_INVALID')
            for ring in polygon:
                if not isinstance(ring,list)or len(ring)<4 or not _strict(ring[0],ring[-1]) or any(not isinstance(p,list) or len(p)!=2 for p in ring):
                    raise ValueError('INFOGRAPHIC_POLYGON_RING_INVALID')
    else:
        raise ValueError('INFOGRAPHIC_GEOMETRY_TYPE_UNSUPPORTED')
    expected_bbox = [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
    if not _strict(record.get('bbox'), expected_bbox):
        raise ValueError('INFOGRAPHIC_GEOMETRY_BBOX_INVALID')
    geometry = dict(type=geometry_type, coordinates=coordinates)
    if record.get('sha256') != canonical_sha(geometry) or record.get('crs') != 'EPSG:4326':
        raise ValueError('INFOGRAPHIC_GEOMETRY_HASH_INVALID')
    return dict(passed=True, geometry_type=geometry_type, vertices=len(points),
                holes_preserved=True, native_parts_preserved=True, captured_pixels='NOT_RUN')


def _safe_file(value):
    if not isinstance(value,str) or not value or '\\' in value or value.startswith('/'):
        raise ValueError('INFOGRAPHIC_SOURCE_PATH_INVALID')
    path=(ROOT/value).resolve()
    roots=[ROOT.resolve(),(ROOT.parent/'cinematic-world-map').resolve()]
    if not any(root in path.parents for root in roots):
        raise ValueError('INFOGRAPHIC_SOURCE_PATH_INVALID')
    if not path.is_file():
        raise ValueError('INFOGRAPHIC_SOURCE_MISSING')
    return path


def _source_feature(record, country, catalog, shipping):
    selector=record['provenance']['selector'];kind=selector['kind']
    if kind=='country':
        matches=[f for f in country['features'] if f['properties'].get(selector['field'])==selector['value']]
        if len(matches)!=1:raise ValueError('INFOGRAPHIC_SOURCE_FEATURE_INVALID')
        feature=matches[0];geometry=feature['geometry']
        if record['source_feature_id']!=feature['properties']['ADM0_A3']:raise ValueError('INFOGRAPHIC_SOURCE_FEATURE_INVALID')
    elif kind in {'location_catalog','shipping_location'}:
        values=catalog['locations'] if kind=='location_catalog' else list(shipping['locations'].values())
        matches=[item for item in values if item['id']==selector['location_id']]
        if len(matches)!=1:raise ValueError('INFOGRAPHIC_SOURCE_FEATURE_INVALID')
        feature=matches[0];c=feature['coordinates'];geometry=dict(type='Point',coordinates=[c['lon'],c['lat']])
        expected_id=feature.get('feature_id',feature.get('source_record'))
        if record['source_feature_id']!=str(expected_id) or record['source_id']!=c['source_id']:
            raise ValueError('INFOGRAPHIC_SOURCE_FEATURE_INVALID')
        if record.get('location_id')!=feature['id'] or record['geometry_role']!=feature['kind']:
            raise ValueError('INFOGRAPHIC_POINT_ROLE_INVALID')
    elif kind=='suez_native_feature':
        path=_safe_file(selector['file'])
        if _sha(path)!=selector['file_sha256']:raise ValueError('INFOGRAPHIC_SOURCE_HASH_INVALID')
        data=json.loads(path.read_text());matches=[f for f in data['features'] if f['properties'].get(selector['field'])==selector['value']]
        if len(matches)!=1 or len(data['features'])!=1:raise ValueError('INFOGRAPHIC_SOURCE_FEATURE_INVALID')
        feature=matches[0];geometry=feature['geometry']
        if record['source_feature_id']!=feature['properties']['dissolve'] or record['geometry_role']!='canal_centerline':
            raise ValueError('INFOGRAPHIC_SOURCE_FEATURE_INVALID')
    else:raise ValueError('INFOGRAPHIC_SOURCE_SELECTOR_INVALID')
    if canonical_sha(feature)!=record['source_feature_sha256'] or not _strict(geometry,dict(type=record['geometry_type'],coordinates=record['coordinates'])):
        raise ValueError('INFOGRAPHIC_SOURCE_FEATURE_OR_COORDINATE_MISMATCH')


def validate_registry(registry=None, require_assets=True):
    errors=[];count=0
    try:
        original=_read_pair('registry.json');value=registry if registry is not None else original
        if not parent._typed(value) or not _strict(value,original):raise ValueError('INFOGRAPHIC_REGISTRY_HASH_MISMATCH')
        manifest=_read_pair('SOURCES.json')
        if value['version']!=VERSION or value['crs']!='EPSG:4326' or value['coordinate_order']!='longitude,latitude':raise ValueError('INFOGRAPHIC_REGISTRY_VERSION_INVALID')
        if value['source_manifest_sha256']!=_sha(DIRECTORY/'SOURCES.json'):raise ValueError('INFOGRAPHIC_SOURCE_MANIFEST_HASH_INVALID')
        records=value['geometries'];ids=[r['id']for r in records]
        count=len(records)
        if not records or len(ids)!=len(set(ids)) or len(records)!=value['geometry_count']:raise ValueError('INFOGRAPHIC_REGISTRY_ID_INVALID')
        sources={s['id']:s for s in manifest['sources']}
        if len(sources)!=len(manifest['sources']):raise ValueError('INFOGRAPHIC_SOURCE_ID_INVALID')
        definition=_definition()
        if sources['natural_earth_countries']['sha256']!=definition.COUNTRY_SHA or sources['natural_earth_countries']['source_commit']!=definition.PIN:
            raise ValueError('INFOGRAPHIC_PINNED_COUNTRY_SOURCE_INVALID')
        canal_source=sources['NATURAL_EARTH_RIVERS_LAKE_CENTERLINES_10M']
        if canal_source['sha256']!='bb854a900ecbd3b408df46d5e16e3e0f974ba55993f9d8b5c26e855273c0905a' or canal_source['source_commit']!=definition.PIN:
            raise ValueError('INFOGRAPHIC_PINNED_CANAL_SOURCE_INVALID')
        for identifier,expected_sha in definition.CANALS.items():
            record=next(r for r in records if r['id']==identifier)
            if record['provenance']['selector']['file_sha256']!=expected_sha:
                raise ValueError('INFOGRAPHIC_PINNED_CANAL_FEATURE_INVALID')
        if require_assets:
            for source in sources.values():
                if source['file'] is not None and _sha(_safe_file(source['file']))!=source['sha256']:
                    raise ValueError('INFOGRAPHIC_SOURCE_HASH_INVALID')
                _safe_file(source['license']['file'])
            for license_record in manifest['licenses']:
                if _sha(_safe_file(license_record['file']))!=license_record['sha256']:raise ValueError('INFOGRAPHIC_LICENSE_HASH_INVALID')
        country=json.loads((ROOT.parent/'cinematic-world-map/assets/gis/countries_50m.geojson').read_text())
        catalog=json.loads((ROOT/'data/locations.json').read_text());shipping=json.loads((ROOT/'data/shipping_routes.json').read_text())
        for record in records:
            validate_geometry(record)
            source=sources.get(record.get('source_id'))
            if not source or record['source_version']!=source['version'] or record['source_file_sha256']!=source['sha256'] or not _strict(record['license'],source['license']):
                raise ValueError('INFOGRAPHIC_SOURCE_BINDING_INVALID')
            _source_feature(record,country,catalog,shipping)
    except (ValueError,KeyError,TypeError,AttributeError,OSError,json.JSONDecodeError) as error:
        errors.append(dict(code=str(error).split(':')[0] if isinstance(error,ValueError) else 'INFOGRAPHIC_REGISTRY_INVALID'))
    return dict(passed=not errors,errors=errors,warnings=[],version=VERSION,
                geometry_count=count,
                source_geometry='VERIFIED_NATIVE_DATA' if not errors else 'INVALID',physical_gpu='NOT_RUN')


def profile():
    value=_read_pair('profile.json')
    if value.get('version')!=VERSION or value.get('parent_version')!=parent.VERSION or not parent._typed(value):raise ValueError('INFOGRAPHIC_PROFILE_INVALID')
    for role,item in value['typography'].items():
        if role not in ROLES or type(item['size_px'])is not int or item['weight']not in {400,700} or type(item['weight'])is not int:raise ValueError('INFOGRAPHIC_FONT_WEIGHT_INVALID')
    if value['geometry']['boundary_draw'] is not False or value['limits']['added_sfx']!=0:raise ValueError('INFOGRAPHIC_UNSUPPORTED_EFFECT')
    if not parent._strict_equal(value,_definition().profile()):raise ValueError('INFOGRAPHIC_PROFILE_FIELDS_INVALID')
    if _sha(ROOT/'web/fonts/NotoSansCJKkr-Bold.otf')!='da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0':raise ValueError('INFOGRAPHIC_REAL_BOLD_FONT_INVALID')
    return value


def hashes():
    return {name:_sha(ROOT/name)for name in SOURCES}


def _contract():
    profile();parent._contract()
    return dict(version=VERSION,parent_version=parent.VERSION,registry_url=REGISTRY_URL,
                registry_sha256=_sha(DIRECTORY/'registry.json'),profile_url=PROFILE_URL,
                profile_sha256=_sha(DIRECTORY/'profile.json'),source_hashes=hashes(),parent_source_hashes=parent.hashes())


def _clock(scene, fps=None):
    return parent._clock(scene,fps)


def _camera_snapshot(scene):
    return {**parent._camera_snapshot(scene),'native_framing':deepcopy(scene.get('native_framing'))}


def _quality_snapshot(scene):
    return {**parent._quality_snapshot(scene),'regional_lod':deepcopy(scene.get('regional_lod')),
            'production_defaults':deepcopy(scene.get('production_defaults'))}


def _font_sources():
    bold=json.loads((ROOT/'web/fonts/BOLD_SOURCE_v022.json').read_text())
    regular=json.loads((ROOT/'web/fonts/SOURCE.json').read_text())
    if bold.get('sha256')!=_sha(ROOT/'web/fonts/NotoSansCJKkr-Bold.otf') or bold.get('license_sha256')!=_sha(ROOT/'web/fonts/LICENSE_Noto_CJK.txt'):
        raise ValueError('INFOGRAPHIC_FONT_SOURCE_HASH_INVALID')
    if regular.get('sha256')!=_sha(ROOT/'web/fonts/NotoSansCJKkr-Regular.otf'):raise ValueError('INFOGRAPHIC_FONT_SOURCE_HASH_INVALID')
    return dict(EVENT_TITLE=bold,other_roles=dict(file='NotoSansCJKkr-Regular.otf',weight=400,
        sha256=_sha(ROOT/'web/fonts/NotoSansCJKkr-Regular.otf'),license='SIL OFL 1.1',
        license_sha256=_sha(ROOT/'web/fonts/LICENSE_Noto_CJK.txt'),
        source_metadata=regular))


def _base_frame_grid(plan):
    grid=plan['metadata']['frame_grid'];clock=FrameGrid(grid['fps']);cursor=0
    if isinstance(grid['fps'],bool) or type(grid['total_frames'])is not int or grid['total_frames']<=0:raise ValueError('INFOGRAPHIC_FRAME_GRID_INVALID')
    for scene in plan['scenes']:
        _clock(scene,grid['fps'])
        if scene['scene_start_frame']!=cursor or scene['scene_end_frame']!=cursor+scene['frame_count'] or any(type(scene[k])is not int for k in ['scene_start_frame','scene_end_frame']):raise ValueError('INFOGRAPHIC_FRAME_GRID_INVALID')
        if abs(scene['start_time']-clock.seconds(cursor))>1e-8:raise ValueError('INFOGRAPHIC_FRAME_GRID_INVALID')
        cursor=scene['scene_end_frame']
    if cursor!=grid['total_frames']or abs(plan['duration']-clock.seconds(cursor))>1e-8:raise ValueError('INFOGRAPHIC_FRAME_GRID_INVALID')


def _base_admission(plan,family):
    _base_frame_grid(plan)
    if family=='story-progression-v021':
        if not parent.validate_progression(plan)['passed']:raise ValueError('INFOGRAPHIC_V021_BASELINE_REQUIRED')
    elif family=='production-earth-v1':
        if not plan['scenes']or any(s.get('production_defaults',{}).get('version')!='v1'for s in plan['scenes']):raise ValueError('INFOGRAPHIC_PRODUCTION_BASELINE_REQUIRED')
    else:raise ValueError('INFOGRAPHIC_PARENT_RENDERER_INVALID')


def _semantic_admission(plan,timeline,segments,family):
    if not segments and timeline is None:
        if family=='production-earth-v1':raise ValueError('INFOGRAPHIC_MEASURED_TIMELINE_REQUIRED')
        return
    if not isinstance(timeline,dict) or not _strict(segments,timeline.get('segments')):raise ValueError('INFOGRAPHIC_SEMANTIC_TIMELINE_REQUIRED')
    from .semantic_timeline import validate_semantic_timeline
    report=validate_semantic_timeline(timeline)
    if not report['passed']:raise ValueError(report['errors'][0]['code'])
    if timeline['fps']!=str(FrameGrid(plan['metadata']['frame_grid']['fps']).fps) or timeline['total_frames']!=plan['metadata']['frame_grid']['total_frames']:raise ValueError('INFOGRAPHIC_SEMANTIC_PLAN_GRID_MISMATCH')
    registry=load_registry();target_ids={r['id']for r in registry['geometries']}
    target_ids.update(t.get('id')if isinstance(t,dict)else t for s in plan['scenes']for t in s.get('geographic_targets',[]))
    if plan.get('metadata',{}).get('semantic_timeline')is not None and not _strict(plan['metadata']['semantic_timeline'],timeline):raise ValueError('INFOGRAPHIC_SEMANTIC_METADATA_MISMATCH')
    source_ids={s['id']for s in plan['sources']};source_ids.update(s['id']for s in _read_pair('SOURCES.json')['sources'])
    validate_semantic_segments(segments,timeline['script_text'],{c['id']:c for c in plan['story']['claims']},source_ids,target_ids,timeline['fps'])


def validate_semantic_segments(segments, script_text, claims, source_ids, target_ids, fps):
    if not isinstance(segments,list) or not isinstance(script_text,str):raise ValueError('INFOGRAPHIC_SEMANTIC_INPUT_INVALID')
    clock=FrameGrid(fps);seen=set();last_end=0.
    for segment in segments:
        if not isinstance(segment,dict) or segment.get('id')in seen:raise ValueError('INFOGRAPHIC_SEMANTIC_ID_INVALID')
        seen.add(segment['id']);span=segment['script_range'];a,b=span['start_char'],span['end_char']
        if type(a)is not int or type(b)is not int or not 0<=a<b<=len(script_text) or span['text']!=script_text[a:b]:raise ValueError('INFOGRAPHIC_SCRIPT_BINDING_INVALID')
        if not segment['claim_ids'] or any(c not in claims for c in segment['claim_ids']) or any(s not in source_ids for s in segment['source_ids']) or any(t not in target_ids for t in segment['target_ids']):raise ValueError('INFOGRAPHIC_SEMANTIC_SOURCE_BINDING_INVALID')
        start,end=segment['speech_start'],segment['speech_end'];count,rate=segment['sample_count'],segment['sample_rate']
        if any(type(v)not in (int,float) or not math.isfinite(v) for v in [start,end]) or not last_end<=start<end or type(count)is not int or type(rate)is not int or count<=0 or rate<=0 or abs((end-start)-count/rate)>1/rate+1e-9:raise ValueError('INFOGRAPHIC_MEASURED_SPEECH_INVALID')
        if segment['timing_method']!='sentence_synthesis_measured_pcm' or segment['confidence']!='measured_utterance_window_only' or segment['word_alignment'] is not False:raise ValueError('INFOGRAPHIC_UNVERIFIED_ALIGNMENT')
        if type(segment['start_frame'])is not int or type(segment['end_frame'])is not int or not 0<=segment['start_frame']<segment['end_frame']:raise ValueError('INFOGRAPHIC_SEMANTIC_FRAME_INVALID')
        last_end=end
    return dict(passed=True,measured_segments=len(segments),word_alignment=False)


def _validate_event(event,scene,registry_by_id,claims,segments):
    if not isinstance(event,dict) or set(event)!=EVENT_FIELDS or not parent._typed(event):raise ValueError('INFOGRAPHIC_EVENT_FIELDS_INVALID')
    if not isinstance(event['id'],str) or not event['id'] or event['scene_id']!=scene['scene_id']:raise ValueError('INFOGRAPHIC_EVENT_ID_INVALID')
    start,transition,end=[event[k]for k in ['start_frame','transition_end_frame','end_frame']]
    if any(type(v)is not int for v in [start,transition,end]) or not 0<=start<=transition<end<=scene['frame_count']:raise ValueError('INFOGRAPHIC_EVENT_FRAME_INVALID')
    if event['state_before']not in STATES or event['state_after']not in STATES or event['primary_role']not in ROLES:raise ValueError('INFOGRAPHIC_EVENT_STATE_INVALID')
    refs=event['target_geometry_refs'];point=event['location_point_ref']
    if not isinstance(refs,list) or len(refs)!=len(set(refs)) or any(g not in registry_by_id or registry_by_id[g]['geometry_type']=='Point'for g in refs):raise ValueError('INFOGRAPHIC_EVENT_GEOMETRY_INVALID')
    if point is not None and (point not in registry_by_id or registry_by_id[point]['geometry_type']!='Point'):raise ValueError('INFOGRAPHIC_EVENT_POINT_INVALID')
    if not refs and point is None:raise ValueError('INFOGRAPHIC_EVENT_TARGET_REQUIRED')
    claim=claims.get(event['claim_id'])
    if not claim:raise ValueError('INFOGRAPHIC_EVENT_CLAIM_INVALID')
    evidence=event['evidence_type']
    if evidence=='hypothetical_scenario':
        if claim['status']not in {'ASSUMPTION','SIMULATION'} or not isinstance(event['watermark'],str) or not event['watermark'].strip():raise ValueError('INFOGRAPHIC_HYPOTHESIS_NOT_MARKED')
    elif evidence=='sourced_fact':
        if claim['status']!='FACT' or not claim.get('source_ids') or event['state_after']in {'OPEN','CLOSED','BLOCKED'}:raise ValueError('INFOGRAPHIC_UNSUPPORTED_FACT_STATE')
        if event['watermark']is not None:raise ValueError('INFOGRAPHIC_FACT_WATERMARK_INVALID')
    else:raise ValueError('INFOGRAPHIC_EVENT_EVIDENCE_INVALID')
    text=event['text']
    if not isinstance(text,dict) or set(text)!={'event_title','location_label','support_data'} or any(v is not None and (not isinstance(v,str)or not v.strip())for v in text.values()):raise ValueError('INFOGRAPHIC_EVENT_TEXT_INVALID')
    if text['support_data']is not None and text['support_data']not in claim['text']:raise ValueError('INFOGRAPHIC_SUPPORT_DATA_UNSOURCED')
    if text['location_label']is not None and point is not None and text['location_label'].upper()!=registry_by_id[point]['name'].upper():
        raise ValueError('INFOGRAPHIC_LOCATION_TEXT_UNSOURCED')
    reference=event['story_source_ref']
    if reference is not None:
        if not isinstance(reference,dict)or set(reference)!={'visual_event_id','text_event_id','label_index'}:raise ValueError('INFOGRAPHIC_STORY_REFERENCE_INVALID')
        source=next((e for e in scene['visual_events']if e['id']==reference['visual_event_id']),None)
        if source is None or source.get('claim_id')!=event['claim_id']or parent._frame(_clock(scene),source['time'])!=start:raise ValueError('INFOGRAPHIC_STORY_BINDING_INVALID')
        if point is not None:
            record=registry_by_id[point];coordinates=source.get('coordinates',{})
            if record.get('location_id')!=source.get('target_id') or not _strict(record['coordinates'],[coordinates.get('lon'),coordinates.get('lat')]) or record['source_id']!=coordinates.get('source_id'):
                raise ValueError('INFOGRAPHIC_STORY_TARGET_MISMATCH')
        if source.get('kind')=='route_blocked' and (event['state_after']not in {'CLOSED','BLOCKED','INACTIVE'} or any(registry_by_id[g]['geometry_type']not in {'LineString','MultiLineString'}for g in refs)):
            raise ValueError('INFOGRAPHIC_STORY_GEOMETRY_SCOPE_INVALID')
        if reference['text_event_id'] is not None:
            t=next((t for t in scene['text_events']if t['id']==reference['text_event_id']),None)
            if t is None or t['event_id']!=source['id']or t['text']!=text['event_title']:raise ValueError('INFOGRAPHIC_TEXT_BINDING_INVALID')
        if reference['label_index']is not None:
            i=reference['label_index']
            if type(i)is not int or not 0<=i<len(scene['labels'])or scene['labels'][i]['text']!=text['location_label']:raise ValueError('INFOGRAPHIC_LOCATION_LABEL_BINDING_INVALID')
    elif event['semantic_segment_ref'] is None:
        # Independent source-backed location descriptions are valid; invented
        # physical/state events without either authored source are not.
        if evidence!='sourced_fact' or event['state_after']not in {'LOCATION','CONTEXT','UNCHANGED','ACTIVE'}:raise ValueError('INFOGRAPHIC_UNSUPPORTED_STORY_EVENT')
        known_names={registry_by_id[g]['name'].upper()for g in refs+([point]if point else [])}
        if text['location_label'] and text['location_label'].upper()not in known_names:raise ValueError('INFOGRAPHIC_LOCATION_TEXT_UNSOURCED')
    if event['semantic_segment_ref']is not None:
        segment=segments.get(event['semantic_segment_ref'])
        if not segment or event['claim_id']not in segment['claim_ids'] or event['id']not in segment.get('event_ids',[]):raise ValueError('INFOGRAPHIC_SEMANTIC_EVENT_BINDING_INVALID')
    return event


def compile_scene_selection(scene,events,registry,semantic_segments=None,fps=None,claims=None,
                            parent_renderer_family='story-progression-v021'):
    if parent_renderer_family not in FAMILIES:raise ValueError('INFOGRAPHIC_PARENT_RENDERER_INVALID')
    if parent_renderer_family=='story-progression-v021' and scene.get('story_progression',{}).get('version')!=parent.VERSION:raise ValueError('INFOGRAPHIC_V021_BASELINE_REQUIRED')
    if parent_renderer_family=='production-earth-v1' and scene.get('production_defaults',{}).get('version')!='v1':raise ValueError('INFOGRAPHIC_PRODUCTION_BASELINE_REQUIRED')
    clock=_clock(scene,fps);geometry_by_id={r['id']:r for r in registry['geometries']};claim_by_id=claims or {}
    segments={s['id']:s for s in semantic_segments or []}
    if not isinstance(events,list)or len({e.get('id')for e in events if isinstance(e,dict)})!=len(events):raise ValueError('INFOGRAPHIC_EVENT_ID_INVALID')
    events=[deepcopy(_validate_event(e,scene,geometry_by_id,claim_by_id,segments))for e in events]
    events.sort(key=lambda e:(e['start_frame'],e['id']))
    geometry_ids=sorted({g for e in events for g in e['target_geometry_refs']+([e['location_point_ref']]if e['location_point_ref']else[])})
    labels=[];markers=[];geometry_layers=[];styles=profile();pop=clock.frames(Fraction(styles['marker']['pop_frames'],styles['marker']['pop_reference_fps']))
    fade=clock.frames(Fraction(styles['marker']['fade_frames'],styles['marker']['pop_reference_fps']))
    def semantic_end(event):
        finish=event['end_frame']
        if event['location_point_ref']is not None:
            for later in events:
                if later['location_point_ref']==event['location_point_ref'] and event['start_frame']<=later['start_frame']<=finish:
                    finish=max(finish,later['end_frame'])
        return finish
    for event in events:
        for geometry_ref in event['target_geometry_refs']:
            context=(event['primary_role']=='LOCATION_LABEL'and event['state_after']in {'LOCATION','CONTEXT','UNCHANGED'})
            geometry_layers.append(dict(id=event['id']+'_GEOMETRY_'+geometry_ref,event_id=event['id'],geometry_ref=geometry_ref,
                start_frame=event['start_frame'],transition_end_frame=event['transition_end_frame'],
                end_frame=semantic_end(event)if context else event['end_frame'],source_event_end_frame=event['end_frame'],
                primary_until_frame=event['end_frame'],state_before=event['state_before'],state_after=event['state_after'],
                semantic_target_ref=event['location_point_ref'],claim_id=event['claim_id'],evidence_type=event['evidence_type'],
                source_ref=deepcopy(event['story_source_ref'])or dict(semantic_segment_ref=event['semantic_segment_ref'],claim_id=event['claim_id'],field='event.target_geometry_refs')))
        for key,role in [('event_title','EVENT_TITLE'),('location_label','LOCATION_LABEL'),('support_data','SUPPORT_DATA')]:
            text=event['text'][key]
            if text is not None:
                source_ref=deepcopy(event['story_source_ref']) or dict(semantic_segment_ref=event['semantic_segment_ref'],claim_id=event['claim_id'],field='event.text.'+key)
                repeated=role=='LOCATION_LABEL' and any(old['role']==role and old['text']==text and old['anchor_geometry_ref']==event['location_point_ref'] for old in labels)
                start=event['start_frame']+(pop if role=='LOCATION_LABEL'and event['primary_role']==role else 0)
                intro='STATIC'if repeated else'FADE'if len(text)>24 else'CHARACTER_REVEAL'
                reveal_end=start+1 if intro=='STATIC'else start+(event['transition_end_frame']-event['start_frame'])
                if not start<reveal_end<event['end_frame']:raise ValueError('INFOGRAPHIC_LABEL_READ_WINDOW_INVALID')
                labels.append(dict(id=event['id']+'_'+role,event_id=event['id'],role=role,text=text,
                                   anchor_geometry_ref=event['location_point_ref'],start_frame=start,
                                   reveal_end_frame=reveal_end,end_frame=event['end_frame'],intro_mode=intro,
                                   primary=event['primary_role']==role,claim_id=event['claim_id'],evidence_type=event['evidence_type'],source_ref=source_ref))
        if event['location_point_ref']is not None and event['primary_role']=='LOCATION_LABEL':
            # The semantic target persists across contiguous authored state
            # changes. Only the first reveal owns marker pop; later state events
            # update the same marker rather than replaying or replacing it.
            marker_end=semantic_end(event)
            source_ref=deepcopy(event['story_source_ref']) or dict(semantic_segment_ref=event['semantic_segment_ref'],claim_id=event['claim_id'],field='event.location_point_ref')
            markers.append(dict(id=event['id']+'_MARKER',event_id=event['id'],geometry_ref=event['location_point_ref'],
                                start_frame=event['start_frame'],intro_end_frame=min(event['start_frame']+pop,marker_end),
                                fade_start_frame=max(event['start_frame'],marker_end-fade),end_frame=marker_end,
                                state=event['state_after'],source_ref=source_ref))
    for frame in range(scene['frame_count']):
        active=[l for l in labels if l['primary']and l['start_frame']<=frame<l['end_frame']]
        if len(active)>1:raise ValueError('INFOGRAPHIC_PRIMARY_INFORMATION_CONFLICT')
    return dict(**_contract(),parent_renderer_family=parent_renderer_family,fps=str(clock.fps),total_frames=scene['frame_count'],events=events,geometry_ids=geometry_ids,
                geometries=[deepcopy(geometry_by_id[g])for g in geometry_ids],geometry_layers=geometry_layers,labels=labels,markers=markers,
                semantic_segments=deepcopy(semantic_segments or []),
                source_claims={e['claim_id']:deepcopy(claim_by_id[e['claim_id']])for e in events},
                parent_camera_sha256=parent._json_sha(_camera_snapshot(scene)),
                parent_quality_sha256=parent._json_sha(_quality_snapshot(scene)),
                source_scene_sha256=parent._json_sha(parent._source_snapshot(scene)),
                font_sources=_font_sources(),subtitle_owner='ffmpeg')


def prepare_infographic(plan,registry=None,*,events=None,semantic_segments=None,enabled=True,
                        parent_renderer_family=None,semantic_timeline=None):
    if type(enabled)is not bool:raise ValueError('INFOGRAPHIC_SELECTION_INVALID')
    if not enabled:
        if plan.get('metadata',{}).get('infographic')is not None or any('infographic'in s for s in plan.get('scenes',[])):raise ValueError('INFOGRAPHIC_OFF_REQUIRES_PARENT_PLAN')
        return deepcopy(plan)
    family=parent_renderer_family or ('story-progression-v021'if all(s.get('story_progression',{}).get('version')==parent.VERSION for s in plan.get('scenes',[]))else'production-earth-v1')
    _base_admission(plan,family)
    registry=registry if registry is not None else load_registry()
    if not validate_registry(registry)['passed']:raise ValueError('INFOGRAPHIC_REGISTRY_INVALID')
    if events is None:raise ValueError('INFOGRAPHIC_AUTHORED_EVENTS_REQUIRED')
    events=deepcopy(events);segments=deepcopy(semantic_segments if semantic_segments is not None else (semantic_timeline or {}).get('segments',[]));value=deepcopy(plan);claims={c['id']:c for c in value['story']['claims']}
    _semantic_admission(value,semantic_timeline,segments,family)
    fps=value['metadata']['frame_grid']['fps']
    for scene in value['scenes']:
        own=[e for e in events if e.get('scene_id')==scene['scene_id']]
        scene['infographic']=compile_scene_selection(scene,own,registry,segments,fps,claims,family)
    if any(e.get('scene_id')not in {s['scene_id']for s in value['scenes']}for e in events):raise ValueError('INFOGRAPHIC_EVENT_SCENE_INVALID')
    value['metadata']['infographic']=dict(version=VERSION,source_hashes=hashes(),registry_sha256=_sha(DIRECTORY/'registry.json'),
                                        parent_renderer_family=family,authored_events=deepcopy(events),semantic_segments=deepcopy(segments),
                                        semantic_timeline=deepcopy(semantic_timeline))
    install_validation();from .schema import validate_plan
    value['gate']=validate_plan(value)
    if not value['gate']['passed']:raise ValueError('INFOGRAPHIC_PLAN_INVALID')
    return value


def validate_infographic(plan):
    errors=[]
    try:
        registry=load_registry();baseline=deepcopy(plan);selected=baseline.get('metadata',{}).pop('infographic',None)
        if not isinstance(selected,dict)or set(selected)!={'version','source_hashes','registry_sha256','parent_renderer_family','authored_events','semantic_segments','semantic_timeline'}:raise ValueError('INFOGRAPHIC_METADATA_INVALID')
        if selected['version']!=VERSION or selected['source_hashes']!=hashes()or selected['registry_sha256']!=_sha(DIRECTORY/'registry.json'):raise ValueError('INFOGRAPHIC_SOURCE_CONTRACT_INVALID')
        claims={c['id']:c for c in plan['story']['claims']};fps=plan['metadata']['frame_grid']['fps']
        family=selected['parent_renderer_family']
        _semantic_admission(plan,selected['semantic_timeline'],selected['semantic_segments'],family)
        for scene in baseline['scenes']:
            own=scene.pop('infographic',None);events=[e for e in selected['authored_events']if e['scene_id']==scene['scene_id']]
            expected=compile_scene_selection(scene,events,registry,selected['semantic_segments'],fps,claims,family)
            if not _strict(own,expected):raise ValueError('INFOGRAPHIC_EVENT_OR_SOURCE_CONTRACT_MISMATCH')
        if any(e['scene_id']not in {s['scene_id']for s in baseline['scenes']}for e in selected['authored_events']):raise ValueError('INFOGRAPHIC_EVENT_SCENE_INVALID')
        _base_admission(baseline,family)
    except (ValueError,KeyError,TypeError,AttributeError,OSError,json.JSONDecodeError)as error:
        errors.append(dict(code=str(error).split(':')[0]if isinstance(error,ValueError)else'INFOGRAPHIC_CONFIG_INVALID'))
    return dict(passed=not errors,errors=errors,warnings=[],version=VERSION,parent_version=parent.VERSION,
                added_routes=0,added_entities=0,added_sfx=0,physical_gpu='NOT_RUN')


def validate_scene_infographic(scene):
    """Validate one admitted renderer Scene, including its immutable pins.

    Full-plan admission additionally binds captured claims to the actual Story.
    This boundary never accepts a loose renderer selection or arbitrary GIS.
    """
    errors=[]
    try:
        selected=scene.get('infographic')
        if not isinstance(selected,dict):raise ValueError('INFOGRAPHIC_SCENE_SELECTION_REQUIRED')
        value=deepcopy(scene);value.pop('infographic')
        expected=compile_scene_selection(value,selected['events'],load_registry(),
            selected['semantic_segments'],selected['fps'],selected['source_claims'],selected['parent_renderer_family'])
        if not _strict(selected,expected):raise ValueError('INFOGRAPHIC_SCENE_CONTRACT_MISMATCH')
    except (ValueError,KeyError,TypeError,AttributeError,OSError,json.JSONDecodeError)as error:
        errors.append(dict(code=str(error).split(':')[0]if isinstance(error,ValueError)else'INFOGRAPHIC_SCENE_INVALID'))
    return dict(passed=not errors,errors=errors,warnings=[],version=VERSION,physical_gpu='NOT_RUN')


def install_validation():
    from . import schema,gpu_preflight
    if getattr(schema.validate_plan,'infographic_wrapper',False):gpu_preflight.validate_plan=schema.validate_plan;return
    parent.install_validation();original=schema.validate_plan
    def checked(plan):
        selected=plan.get('metadata',{}).get('infographic')is not None or any('infographic'in s for s in plan.get('scenes',[]))
        if not selected:return original(plan)
        report=validate_infographic(plan)
        if not report['passed']:return report
        base=deepcopy(plan);base['metadata'].pop('infographic',None)
        for scene in base['scenes']:scene.pop('infographic',None)
        if plan['metadata']['infographic']['parent_renderer_family']=='production-earth-v1':
            from .semantic_timeline import validate_production_plan
            technical=validate_production_plan(plan)
        else:technical=original(base)
        return {**technical,'infographic':dict(passed=True,version=VERSION)}
    checked.infographic_wrapper=True
    for name in ('story_progression_wrapper','reference_effects_wrapper','event_quality_wrapper','visual_quality_wrapper','single_test_wrapper'):setattr(checked,name,getattr(original,name,False))
    schema.validate_plan=checked;gpu_preflight.validate_plan=checked


def renderer_version(scene):
    base=parent.renderer_version(scene)
    if not scene.get('infographic'):return base
    return hashlib.sha256(b'MAP_INFOGRAPHIC/v022'+bytes.fromhex(base)+canonical_json(scene['infographic'])).hexdigest()


def project_renderer_version(plan):
    if not any(s.get('infographic')for s in plan['scenes']):return parent.project_renderer_version(plan)
    return canonical_sha({s['scene_id']:renderer_version(s)for s in plan['scenes']})


def diagnostic_record(plan):
    return dict(version=VERSION,qc=validate_infographic(plan),registry_sha256=_sha(DIRECTORY/'registry.json'),
                sources=_read_pair('SOURCES.json'),scenes=[dict(scene_id=s['scene_id'],infographic=deepcopy(s['infographic']))for s in plan['scenes']],
                physical_gpu='NOT_RUN',pixel_metrics='NOT_RUN',quality_verdict='REQUIRES_ACTUAL_GPU_CAPTURE_AND_HUMAN_REVIEW')


def record_source_report(directory,plan,assets=None,*,original=None):
    from .storage import atomic_json
    from .assets import write_source_report
    import os
    checked=validate_infographic(plan)
    if not checked['passed']:raise ValueError('INFOGRAPHIC_SOURCE_REPORT_INVALID')
    directory=Path(directory)
    writer=original or (parent.record_source_report if plan['metadata']['infographic']['parent_renderer_family']=='story-progression-v021'else write_source_report)
    report=writer(directory,plan,assets)
    report['map_infographic']=checked
    report['renderer_version']=project_renderer_version(plan)
    report['infographic_source_manifest_sha256']=_sha(DIRECTORY/'SOURCES.json')
    report['license_notice']+=' v022 preserves licensed native GIS coordinates, holes and disjoint canal parts. Natural Earth 10m/50m means map scale 1:10/50 million, not metre accuracy. CLOSED/OPEN QA states are watermarked hypothetical scenarios. Real font weights are sourced SIL OFL faces. No reference artwork, sound or story is copied.'
    atomic_json(directory/'source_report.json',report)
    atomic_json(directory/'map-infographic-sources.json',diagnostic_record(plan),exclusive=True)
    with (directory/'source_report.md').open('a',encoding='utf-8')as stream:
        stream.write('\n\nv022 sourced map infographic\n\n'+report['license_notice']+'\n')
        stream.flush();os.fsync(stream.fileno())
    return report


def asset_records():
    records=[]
    for base in [DIRECTORY,PUBLIC]:
        for path in sorted(p for p in base.rglob('*')if p.is_file()):
            records.append(dict(file=str(path.relative_to(ROOT)),url='/static/'+str(path.relative_to(ROOT/'web'))if ROOT/'web'in path.parents else None,
                                sha256=_sha(path),bytes=path.stat().st_size,readable=True))
    for name in ['web/fonts/NotoSansCJKkr-Regular.otf','web/fonts/NotoSansCJKkr-Bold.otf','web/fonts/BOLD_SOURCE_v022.json','web/fonts/SOURCE.json','web/fonts/LICENSE_Noto_CJK.txt']:
        path=ROOT/name
        records.append(dict(file=name,url='/static/'+str(path.relative_to(ROOT/'web')),sha256=_sha(path),bytes=path.stat().st_size,readable=True))
    return records
