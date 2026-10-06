"""JSON Schema plus semantic, provenance and inter-scene continuity validation."""
from pathlib import Path
import json, math
from jsonschema import Draft202012Validator
from .presets import CAMERA_PRESETS,LIGHTING_PRESETS,DIRECTING_PRESETS,FLAT_CAMERA_PRESETS,FLAT_MAP_VFX,FLAT_ENTITY_ACTIONS,QUALITY_PRESETS,scene_render_mode
from .plugins import REGISTRY
from .gis import verified_coordinate,resolve_location,UnknownLocation
from .retention import analyze_retention
SCHEMA_PATH=Path(__file__).resolve().parents[1]/'data'/'scene_plan.schema.json'

def validate_flat_scene(scene, source_ids):
    """Validate new geography/focus/action contracts without rewriting old plans."""
    errors=[];sid=scene['scene_id'];mode=scene_render_mode(scene)
    flat=mode=='FLAT_MAP_PREMIUM'
    if (scene['camera_preset'] in FLAT_CAMERA_PRESETS)!=flat:
        errors.append(dict(code='CAMERA_RENDER_MODE_MISMATCH',message=sid))
    if not flat:
        if any(e['type']=='ship' for e in scene['entities']):
            errors.append(dict(code='UNSUPPORTED_VISUAL_REQUIREMENT',message='ship alias requires FLAT_MAP_PREMIUM; legacy cargo_ship remains supported',required_plugin='FLAT_MAP_PREMIUM'))
        return errors
    settings=scene.get('flat_map',{});duration=scene['duration']
    from .assets import V3_ROOT,APP_ROOT
    features=json.loads((V3_ROOT/'assets/gis/countries_50m.geojson').read_text())['features']
    country_codes={f['properties'].get('ADM0_A3') for f in features}|{f['properties'].get('ISO_A3') for f in features}
    def coordinate_check(coord,target=None):
        if not verified_coordinate(coord):errors.append(dict(code='UNVERIFIED_FLAT_GIS_COORDINATE',message=sid,coordinate=coord))
        if coord.get('source_id') not in source_ids:errors.append(dict(code='MISSING_GIS_SOURCE',message=sid,source=coord.get('source_id')))
        if target and coord.get('location_id')!=target:errors.append(dict(code='FLAT_FOCUS_TARGET_MISMATCH',message=sid,target_id=target))
    def timed(item):
        if not 0<=item.get('start_time',0)<item.get('end_time',duration)<=duration+.001:
            errors.append(dict(code='FLAT_EVENT_WINDOW_INVALID',message=sid))
    for key in ('camera_start','camera_end','center'):
        pose=settings.get(key,scene.get(key,{}))
        if abs(pose.get('lat',scene['coordinates']['lat']))>80:
            errors.append(dict(code='UNSUPPORTED_FLAT_PROJECTION_LATITUDE',message=sid,latitude=pose.get('lat'),required_plugin='POLAR_PROJECTION'))
    for highlight in settings.get('country_highlights',[]):
        timed(highlight)
        if highlight['country'] not in country_codes:errors.append(dict(code='UNKNOWN_GIS_COUNTRY',message=sid,country=highlight['country']))
        if highlight['source_id'] not in source_ids:errors.append(dict(code='MISSING_GIS_SOURCE',message=sid,source=highlight['source_id']))
    for focus in settings.get('focus',[]):timed(focus);coordinate_check(focus['coordinates'],focus['target_id'])
    next_event=settings.get('next_event')
    if next_event:
        coordinate_check(next_event['coordinates'])
        event=next((e for e in scene['visual_events'] if e['id']==next_event['event_id']),None)
        if (not event or abs(event['time']-next_event['event_time'])>.001 or event.get('coordinates')!=next_event['coordinates']):
            errors.append(dict(code='NEXT_EVENT_CAMERA_BINDING_MISMATCH',message=sid,event_id=next_event['event_id']))
        if next_event['event_time']-next_event['lead_time']<0:
            errors.append(dict(code='NEXT_EVENT_CAMERA_NO_LEAD_WINDOW',message=sid))
    terrain=settings.get('terrain_texture')
    if terrain:
        west,south,east,north=terrain['bounds']
        if not -180<=west<east<=180 or not -90<=south<north<=90:
            errors.append(dict(code='INVALID_FLAT_TERRAIN_BOUNDS',message=sid))
        registered_path=terrain['url'].removeprefix('/static/')
        manifest=APP_ROOT/'assets/flat/SOURCES.json'
        rows=json.loads(manifest.read_text()) if manifest.is_file() else []
        if isinstance(rows,dict):rows=rows.get('assets',[])
        asset=next((item for item in rows if item.get('file')=='web/'+registered_path),None)
        bounds=asset.get('geographic_bounds',{}) if asset else {}
        if not asset or [bounds.get(k) for k in ['west','south','east','north']]!=terrain['bounds']:
            errors.append(dict(code='UNREGISTERED_OR_MISLOCATED_FLAT_TERRAIN',message=sid))
    entities={e['id']:e for e in scene['entities']};routes={r['route_id'] for r in scene['routes']}
    # A new network connection must begin at its authored event, rather than
    # counting a caption over a route that was already moving. Final overviews
    # may show continued routes and deliberately do not use this freshness rule.
    route_specs={r['route_id']:r for r in scene['routes']}
    frame_seconds=1/QUALITY_PRESETS.get(scene.get('render_quality','HIGH'),QUALITY_PRESETS['HIGH'])['fps']
    for event in scene['visual_events']:
        if event.get('meaningful',True) and event.get('kind') in {'network_expand','network_expansion'}:
            route=route_specs.get(event.get('target_id'))
            if route is None:
                errors.append(dict(code='FLAT_NETWORK_NEW_ROUTE_REQUIRED',message=sid,event_id=event['id']))
            elif route.get('progress_start',0)!=0:
                errors.append(dict(code='FLAT_NETWORK_ROUTE_ALREADY_ACTIVE',message=sid,event_id=event['id'],route_id=route['route_id']))
            elif abs(route.get('start_time',0)-event['time'])>frame_seconds+1e-9:
                errors.append(dict(code='FLAT_NETWORK_EVENT_TIMING_MISMATCH',message=sid,event_id=event['id'],route_id=route['route_id'],route_start_time=route.get('start_time',0),event_time=event['time'],allowed_seconds=frame_seconds))
    for entity in entities.values():
        if entity.get('coordinates'):coordinate_check(entity['coordinates'],entity.get('location_id'))
    for action in scene.get('entity_actions',[]):
        if action.get('entity_id') not in entities:errors.append(dict(code='UNKNOWN_FLAT_ACTION_ENTITY',message=sid))
        if action.get('action') not in FLAT_ENTITY_ACTIONS:errors.append(dict(code='UNSUPPORTED_FLAT_ENTITY_ACTION',message=sid,action=action.get('action')))
        if action.get('target_entity_id') and action['target_entity_id'] not in entities:errors.append(dict(code='UNKNOWN_FLAT_ACTION_TARGET',message=sid))
        if action.get('action') in {'reroute','split','diverge'} and not action.get('route_id'):
            errors.append(dict(code='FLAT_ACTION_ROUTE_REQUIRED',message=sid))
        if action.get('action') in {'follow','merge','converge','intercept'} and not action.get('target_entity_id'):
            errors.append(dict(code='FLAT_ACTION_TARGET_REQUIRED',message=sid))
        if action.get('route_id') and action['route_id'] not in routes:errors.append(dict(code='MISSING_FLAT_ACTION_ROUTE',message=sid))
        if not 0<=action.get('time',action.get('start_time',0))<duration+.001:errors.append(dict(code='FLAT_ACTION_OUT_OF_BOUNDS',message=sid))
    for effect in scene.get('effects',[]):
        kind=str(effect.get('kind','')).upper()
        if kind in FLAT_MAP_VFX|{'COUNTRY_HIGHLIGHT','REGION_HIGHLIGHT'}:
            if effect.get('coordinates'):coordinate_check(effect['coordinates'])
            if effect.get('country'):
                if effect['country'] not in country_codes:errors.append(dict(code='UNKNOWN_GIS_COUNTRY',message=sid,country=effect['country']))
                if effect.get('source_id')!='natural_earth_countries' or effect.get('source_id') not in source_ids:errors.append(dict(code='FLAT_COUNTRY_SOURCE_REQUIRED',message=sid))
            if effect.get('route_id') and effect['route_id'] not in routes:errors.append(dict(code='MISSING_FLAT_EFFECT_ROUTE',message=sid))
        elif kind!='CITY_FOCUS':
            errors.append(dict(code='UNSUPPORTED_VISUAL_REQUIREMENT',message='Unsupported flat VFX '+kind,required_plugin='FLAT_VFX_'+kind))
    return errors

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
        errors.extend(validate_flat_scene(scene,source_ids))
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
    production_validation=None
    if plan.get('production_defaults',{}).get('version')=='v1':
        from .production import validate_production_plan
        production_validation=validate_production_plan(plan)
        errors+=production_validation.get('errors',[])
        warnings+=production_validation.get('warnings',[])
    rhythm_validation=None
    if plan.get('rhythm_policy',{}).get('version')=='v1':
        from .rhythm import validate_rhythm_plan
        rhythm_validation=validate_rhythm_plan(plan)
        errors+=rhythm_validation.get('errors',[])
        warnings+=rhythm_validation.get('warnings',[])
    semantic_visibility=None
    # Validate actual renderer eligibility rather than trusting a saved planner
    # certificate. Invalid GIS/capabilities never reach renderer preflight.
    if not errors:
        from .visibility import certify_semantic_visibility
        semantic_visibility=certify_semantic_visibility(plan)
        if not semantic_visibility['passed']:
            errors.extend(semantic_visibility['failures'])
    result=dict(passed=not errors,errors=errors,warnings=warnings,retention=retention,
                semantic_visibility=semantic_visibility,narration_alignment=narration_alignment)
    if production_validation is not None:result['production_validation']=production_validation
    if rhythm_validation is not None:result['rhythm_validation']=rhythm_validation
    return result
