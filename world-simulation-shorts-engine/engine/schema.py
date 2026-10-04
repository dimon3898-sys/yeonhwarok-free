"""JSON Schema plus semantic, provenance and inter-scene continuity validation."""
from pathlib import Path
import json, math
from jsonschema import Draft202012Validator
from .presets import CAMERA_PRESETS,LIGHTING_PRESETS,DIRECTING_PRESETS
from .plugins import REGISTRY
from .gis import verified_coordinate,resolve_location,UnknownLocation
from .retention import analyze_retention
SCHEMA_PATH=Path(__file__).resolve().parents[1]/'data'/'scene_plan.schema.json'

def validate_plan(plan):
    errors=[];warnings=[]
    schema=json.loads(SCHEMA_PATH.read_text())
    for e in sorted(Draft202012Validator(schema).iter_errors(plan),key=lambda e:str(list(e.path))):
        errors.append(dict(code='SCHEMA_ERROR',path='.'.join(map(str,e.path)),message=e.message))
    if errors:return dict(passed=False,errors=errors,warnings=warnings,retention=None)
    errors.extend(plan.get('revision',{}).get('blocking_issues',[]))
    duration=plan['duration'];cursor=0.;previous=None
    claims={c['id']:c for c in plan['story']['claims']}
    source_ids={s['id'] for s in plan['sources']}
    # New planner versions publish explicit claim->GIS-place bindings. Older
    # immutable plans have no such metadata; their original structure remains
    # readable. This checks typed IDs, not whether arbitrary narration is true.
    coordinate_claim_targets=plan.get('metadata',{}).get('coordinate_claim_targets')
    if coordinate_claim_targets is not None:
        if not isinstance(coordinate_claim_targets,dict):
            errors.append(dict(code='INVALID_GEOGRAPHIC_CLAIM_BINDINGS',message='coordinate_claim_targets must be an object'))
            coordinate_claim_targets={}
        coordinate_claim_ids={cid for cid,c in claims.items() if c.get('scope')=='coordinate provenance'}
        if set(coordinate_claim_targets)!=coordinate_claim_ids:
            errors.append(dict(code='INCOMPLETE_GEOGRAPHIC_CLAIM_BINDINGS',message='Every coordinate-provenance FACT requires exactly one explicit GIS target'))
        for cid,target in coordinate_claim_targets.items():
            claim=claims.get(cid)
            try:location=resolve_location(target) if isinstance(target,str) else None
            except UnknownLocation:location=None
            if not claim or claim.get('status')!='FACT' or claim.get('scope')!='coordinate provenance' or not location or location['id']!=target:
                errors.append(dict(code='INVALID_GEOGRAPHIC_CLAIM_BINDING',message=cid,location_id=target))
            elif location['coordinates']['source_id'] not in claim['source_ids']:
                errors.append(dict(code='GEOGRAPHIC_CLAIM_SOURCE_MISMATCH',message=cid,location_id=target))
    for claim in claims.values():
        if claim['status']=='FACT' and not claim['source_ids']:errors.append(dict(code='UNSOURCED_FACT',message=claim['id']))
        if any(s not in source_ids for s in claim['source_ids']):errors.append(dict(code='UNKNOWN_CLAIM_SOURCE',message=claim['id']))
        if claim['status']=='SIMULATION' and not claim.get('assumption_ids'):errors.append(dict(code='UNBOUND_SIMULATION',message=claim['id']))
        for cid in claim.get('assumption_ids',[]):
            if cid not in claims or claims[cid]['status']!='ASSUMPTION':errors.append(dict(code='INVALID_ASSUMPTION_REFERENCE',message=claim['id']))
    for name in plan['required_plugins']:
        if name not in REGISTRY or not REGISTRY[name].available:errors.append(dict(code='UNSUPPORTED_VISUAL_REQUIREMENT',message=f'필요 모듈: {name}',required_plugin=name))
    event_ids=[]
    for scene in plan['scenes']:
        sid=scene['scene_id'];d=scene['duration']
        if abs(scene['start_time']-cursor)>.001:errors.append(dict(code='SCENE_GAP_OR_OVERLAP',message=sid))
        cursor+=d
        if scene['camera_preset'] not in CAMERA_PRESETS:errors.append(dict(code='UNKNOWN_CAMERA_PRESET',message=sid))
        if scene['lighting_preset'] not in LIGHTING_PRESETS:errors.append(dict(code='UNKNOWN_LIGHTING_PRESET',message=sid))
        if any(p not in DIRECTING_PRESETS for p in scene['directing_presets']):errors.append(dict(code='UNKNOWN_DIRECTING_PRESET',message=sid))
        if previous and previous['exit_state']!=scene['entry_state']:errors.append(dict(code='SCENE_DEPENDENCY_MISMATCH',message=f"{previous['scene_id']} → {sid}"))
        if scene['entry_state']['camera']!=scene['camera_start'] or scene['exit_state']['camera']!=scene['camera_end']:errors.append(dict(code='CAMERA_STATE_MISMATCH',message=sid))
        for coord in [scene['coordinates']]+[e['coordinates'] for e in scene['visual_events'] if e.get('coordinates')]+[label['coordinates'] for label in scene['labels']]+[p for r in scene['routes'] for p in r['points']]:
            if not verified_coordinate(coord):errors.append(dict(code='UNVERIFIED_GIS_COORDINATE',message=sid,coordinate=coord))
            if coord['source_id'] not in source_ids:errors.append(dict(code='MISSING_GIS_SOURCE',message=sid,source=coord['source_id']))
        route_ids={r['route_id'] for r in scene['routes']}
        for route in scene['routes']:
            if route['kind']=='sea' and len(route['points'])<3:errors.append(dict(code='UNVERIFIED_SEA_ROUTE',message=sid))
            if route['kind']=='land':errors.append(dict(code='UNSUPPORTED_VISUAL_REQUIREMENT',message='LAND_ROUTING required',required_plugin='LAND_ROUTING'))
            if not 0<=route['progress_start']<=route['progress_end']<=1:errors.append(dict(code='ROUTE_DISCONTINUITY',message=sid))
        for entity in scene['entities']:
            if entity.get('route_id') and entity['route_id'] not in route_ids:errors.append(dict(code='MISSING_ENTITY_ROUTE',message=sid))
        for e in scene['visual_events']+scene['sound_events']:
            if not 0<=e['time']<d+.001:errors.append(dict(code='EVENT_OUT_OF_BOUNDS',message=f"{sid}: {e['id']}"))
        event_ids.extend(e['id'] for e in scene['visual_events'])
        for event in scene['visual_events']:
            if event.get('claim_id') and event['claim_id'] not in claims:errors.append(dict(code='UNKNOWN_EVENT_CLAIM',message=f'{sid}: {event["claim_id"]}'))
            if coordinate_claim_targets is not None and event.get('claim_id') in coordinate_claim_targets:
                target=coordinate_claim_targets[event['claim_id']]
                if event.get('target_id')!=target or event.get('coordinates',{}).get('location_id')!=target:
                    errors.append(dict(code='GEOGRAPHIC_EVENT_CLAIM_MISMATCH',message=f'{sid}: {event["id"]}',claim_id=event['claim_id'],expected_location_id=target,target_id=event.get('target_id'),coordinate_location_id=event.get('coordinates',{}).get('location_id')))
        local_events={e['id']:e for e in scene['visual_events']}
        for sound in scene['sound_events']:
            event_id=sound.get('visual_event_id')
            if event_id and event_id not in local_events:errors.append(dict(code='UNKNOWN_SOUND_EVENT_TARGET',message=f'{sid}: {event_id}'))
            elif event_id and abs(sound['time']-local_events[event_id]['time'])>.02:errors.append(dict(code='SOUND_EVENT_DESYNC',message=f'{sid}: {event_id}',offset=round(sound['time']-local_events[event_id]['time'],4)))
        if scene['scene_type']=='TERRITORY':errors.append(dict(code='UNSUPPORTED_VISUAL_REQUIREMENT',message='Territory visual implementation is not installed',required_plugin='TERRITORY_TIMELINE'))
        if scene['scene_type']=='CINEMATIC_CLIP':
            clip=scene.get('cinematic_clip',scene.get('clip'))
            if not clip:errors.append(dict(code='MISSING_CINEMATIC_CLIP',message=sid))
            elif not clip.get('user_owned') and not clip.get('license'):errors.append(dict(code='UNKNOWN_CLIP_LICENSE',message=sid))
            if clip:
                from .assets import validate_clip_requirements
                errors.extend(validate_clip_requirements(scene,source_ids,{cid:claim['status'] for cid,claim in claims.items()})['errors'])
        for cid in scene['claim_ids']:
            if cid not in claims:errors.append(dict(code='UNKNOWN_SCENE_CLAIM',message=sid))
        if scene['fact_status']=='FACT' and any(claims.get(cid,{}).get('status')!='FACT' for cid in scene['claim_ids']):errors.append(dict(code='FACT_SIMULATION_CONFUSION',message=sid))
        # Transparent estimate only; actual speech duration is validated again after TTS.
        estimate=len(scene['narration'].replace(' ',''))/5.8 if any('\uac00'<=c<='\ud7a3' for c in scene['narration']) else len(scene['narration'].split())/2.6
        if estimate>d*1.08:errors.append(dict(code='NARRATION_TOO_LONG',message=sid,estimated_seconds=round(estimate,2),duration=d,suggestions=['대본 축약','Scene 길이 증가','Scene 분할']))
        if scene['scene_type'] in {'COUNTRY_FOCUS','COMPARISON','TERRITORY','TIMELINE'} and scene['lighting_preset'] not in {'GEOGRAPHY_READABILITY','DAY_DOCUMENTARY','DISASTER','WAR_SIMULATION'}:errors.append(dict(code='GEOGRAPHY_LIGHTING_UNREADABLE',message=sid))
        previous=scene
    if len(event_ids)!=len(set(event_ids)):errors.append(dict(code='DUPLICATE_EVENT_ID',message='visual_events ids must be unique'))
    if len({s['scene_id'] for s in plan['scenes']})!=len(plan['scenes']):errors.append(dict(code='DUPLICATE_SCENE_ID',message='Scene IDs must be unique'))
    if abs(cursor-duration)>.001:errors.append(dict(code='DURATION_MISMATCH',message=f'{cursor} != {duration}'))
    from .narration import validate_narration_bindings
    narration_alignment=validate_narration_bindings(plan)
    errors+=narration_alignment['errors'];warnings+=narration_alignment['warnings']
    retention=analyze_retention(plan);errors+=retention['errors'];warnings+=retention['warnings']
    semantic_visibility=None
    # Validate actual renderer eligibility rather than trusting a saved planner
    # certificate. Invalid GIS/capabilities never reach renderer preflight.
    if not errors:
        from .visibility import certify_semantic_visibility
        semantic_visibility=certify_semantic_visibility(plan)
        if not semantic_visibility['passed']:
            errors.extend(semantic_visibility['failures'])
    return dict(passed=not errors,errors=errors,warnings=warnings,retention=retention,
                semantic_visibility=semantic_visibility,narration_alignment=narration_alignment)
