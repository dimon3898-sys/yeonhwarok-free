"""Additive, quality-gated production policy over the existing planning engine.

Existing saved plans are never upgraded implicitly. A natural-language request
uses this policy only when explicitly selected or after a short rendered test
has promoted the default. Legacy render/cache behavior stays available.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from .gis import resolve_location, UnknownLocation, verified_coordinate, LOCATIONS, great_circle_distance
from .pace import apply_scene_pace, analyze_dead_time, frame_time, normalize_pace

APP_ROOT=Path(__file__).resolve().parents[1]
REPO_ROOT=APP_ROOT.parent
PROMOTION_PATH=APP_ROOT/'data/production_default_promotion.json'
PRODUCTION_VERSION='v1'
PRODUCTION_PRESET=dict(version='v1',profile='PRODUCTION_DEFAULT',visual='PREMIUM_FLAT_v004',
    pace='FAST',text='MINIMAL_INFORMATIONAL',sfx='EVENT_DRIVEN_VARIANTS',earth='PEAK_ONLY',
    retention=True,event_diversity=True,large_titles=False)
COUNTRY_PALETTE=('#dba966','#82b8cb','#acb47c')
COUNTRY_ALIASES={'South Korea':'KOR','Korea':'KOR','Japan':'JPN','Taiwan':'TWN','China':'CHN',
                 'Singapore':'SGP','United Kingdom':'GBR','France':'FRA','Spain':'ESP',
                 'Germany':'DEU','Italy':'ITA','United States':'USA','Egypt':'EGY'}
CAMERA_TO_FLAT={'GLOBAL_ESTABLISH':'FLAT_ESTABLISH','FAST_HOOK_DIVE':'FLAT_COUNTRY_FOCUS',
    'COUNTRY_APPROACH':'FLAT_COUNTRY_FOCUS','CITY_APPROACH':'FLAT_COUNTRY_FOCUS',
    'GEOGRAPHY_APPROACH':'FLAT_REGION_FOCUS','ROUTE_CHASE':'FLAT_ROUTE_FOLLOW',
    'ENTITY_FOLLOW':'FLAT_ENTITY_FOLLOW','EARTH_ORBIT':'FLAT_MULTI_COUNTRY',
    'HORIZON_REVEAL':'FLAT_MULTI_COUNTRY','TERRITORY_OVERVIEW':'FLAT_MULTI_COUNTRY',
    'NETWORK_EXPANSION':'FLAT_MULTI_COUNTRY','GLOBAL_PULLBACK':'FLAT_PULLBACK',
    'FINAL_REVEAL':'FLAT_PULLBACK'}


def production_default_status(path=None):
    """Read a promotion record backed by immutable, successfully tested evidence."""
    path=Path(path or PROMOTION_PATH)
    if not path.is_file():return dict(active=False,reason='short_integration_test_not_promoted',preset='LEGACY')
    try:
        record=json.loads(path.read_text());evidence=Path(record['evidence_path'])
        artifact_root=REPO_ROOT if record.get('path_base')=='repository' else APP_ROOT
        if not evidence.is_absolute():evidence=artifact_root/evidence
        digest=hashlib.sha256(evidence.read_bytes()).hexdigest()
        passed=record.get('version')=='v1' and record.get('promoted') is True and digest==record.get('evidence_sha256')
        qc=json.loads(evidence.read_text())
        passed=passed and qc.get('passed') is True and 10<=float(qc.get('duration',0))<=15
        passed=passed and qc.get('full_video_speedup') is False and qc.get('rendered_mp4_verified') is True
        passed=passed and qc.get('no_75s_render') is True
        required=['mobile_full_playback_passed','automatic_qc_passed','sfx_frame_sync_passed','sfx_repeat_prevention_passed','tts_ducking_fixture_passed']
        passed=passed and all(qc.get(key) is True for key in required)
        passed=passed and int(qc.get('decoded_frames',0))==round(float(qc.get('duration',0))*30)
        movie=Path(record.get('final_mp4_path',''))
        if not movie.is_absolute():movie=artifact_root/movie
        passed=passed and movie.is_file() and hashlib.sha256(movie.read_bytes()).hexdigest()==record.get('final_mp4_sha256')
        source_manifest=record.get('source_manifest',{})
        passed=passed and bool(source_manifest)
        for relative,expected in source_manifest.items():
            candidate=(APP_ROOT/relative).resolve()
            if not candidate.is_relative_to(APP_ROOT) or not candidate.is_file() or hashlib.sha256(candidate.read_bytes()).hexdigest()!=expected:
                passed=False;break
        return dict(active=bool(passed),reason='quality_gated_promotion' if passed else 'promotion_evidence_invalid',preset='PRODUCTION_DEFAULT' if passed else 'LEGACY',record=record)
    except (OSError,KeyError,TypeError,ValueError,json.JSONDecodeError):
        return dict(active=False,reason='promotion_evidence_invalid',preset='LEGACY')


def requested_production_profile(request):
    selected=request.get('production_preset')
    if selected is not None:
        selected=str(selected).upper()
        if selected not in {'LEGACY','PRODUCTION_DEFAULT','PRODUCTION_DEFAULT_CANDIDATE'}:
            raise ValueError('production_preset must be LEGACY / PRODUCTION_DEFAULT / PRODUCTION_DEFAULT_CANDIDATE')
        if selected=='PRODUCTION_DEFAULT' and not production_default_status()['active']:
            raise ValueError('PRODUCTION_DEFAULT_NOT_PROMOTED: run the bounded short integration QC before activation')
        return None if selected=='LEGACY' else selected
    return 'PRODUCTION_DEFAULT' if production_default_status()['active'] else None


def _registered_terrain(scene):
    source=APP_ROOT/'assets/flat/SOURCES.json'
    rows=json.loads(source.read_text()) if source.is_file() else []
    if isinstance(rows,dict):rows=rows.get('assets',[])
    targets=[scene['coordinates']]
    targets += [point for route in scene.get('routes',[]) if not route.get('faint') for point in route['points']]
    targets += [event['coordinates'] for event in scene.get('visual_events',[]) if event.get('coordinates')]
    candidates=[]
    for asset in rows:
        bounds=asset.get('geographic_bounds',{})
        if not all(key in bounds for key in ['west','south','east','north']):continue
        if not str(asset.get('file','')).startswith('web/flat_assets/'):continue
        if all(bounds['west']<=point['lon']<=bounds['east'] and bounds['south']<=point['lat']<=bounds['north'] for point in targets):
            size=(bounds['east']-bounds['west'])*(bounds['north']-bounds['south'])
            candidates.append((size,asset))
    if not candidates:return None
    asset=min(candidates,key=lambda pair:pair[0])[1]
    return dict(url='/static/'+asset['file'].removeprefix('web/'),
                bounds=[asset['geographic_bounds'][key] for key in ['west','south','east','north']])


def _coordinate_name(coordinates,fallback=''):
    target=coordinates.get('location_id') if coordinates else None
    try:return resolve_location(target)['name'].upper() if target else fallback
    except UnknownLocation:return fallback


def _minimal_event_text(event,scene):
    kind=event['kind'];name=_coordinate_name(event.get('coordinates',{}),scene['location'].upper())
    if kind in {'country_reveal','region_reveal'}:
        old=event.get('text','').strip()
        return old if len(old)<=22 and '·' not in old and 'ASSUMPTION' not in old else name
    if kind in {'city_reveal','destination_preview','arrival'}:return name
    if kind in {'distance_reveal','milestone_reveal','comparison_reveal'}:
        value=event.get('value')
        if isinstance(value,(int,float)):return f'{value:,.0f} km' if event.get('unit','km').lower()=='km' else f'{value:g} {event.get("unit","")}'.strip()
        import re
        match=re.search(r'([\d,.]+)\s*km',event.get('text',''),re.I)
        if match:return match.group(1)+' km'
        return name
    if kind=='new_variable':return 'ASSUME '+name
    if kind=='route_blocked':return 'ASSUMED HOLD'
    if kind=='route_choice' and event.get('text','').startswith('TO '):return event['text']
    if kind in {'route_reroute','alternate_route_reveal','response','route_choice'}:return 'REROUTE'
    if kind=='final_reveal' and event.get('unit')=='km' and isinstance(event.get('value'),(int,float)):
        return f'+{event["value"]:,.0f} km'
    if kind=='final_reveal' and event.get('target_id','').startswith('P_FINAL_'):
        return name
    if kind in {'connection_reveal','consequence_reveal','escalation','peak_reveal'} and event.get('unit')=='km' and isinstance(event.get('value'),(int,float)):
        return f'{event["value"]:,.0f} km'
    if kind in {'route_start','entity_departure','network_expand','connection_reveal','peak_reveal','final_reveal','escalation'}:return ''
    return name if event.get('coordinates') else ''


def _country_code(scene,event=None):
    target=event.get('target_id') if event else None
    if target and len(target)==3 and target.isupper():return target
    c=(event or {}).get('coordinates',scene['coordinates'])
    try:place=resolve_location(c.get('location_id'))
    except UnknownLocation:return None
    return COUNTRY_ALIASES.get(place.get('country',place['name']))


def _snap_scene_events(scene):
    duration=scene['duration'];frames=max(1,round(duration*30))
    for event in scene.get('visual_events',[]):
        event['time']=frame_time(event['time'],latest=(frames-1)/30)
        event['duration']=round(min(duration-event['time'],max(.35,float(event.get('duration',1)))),6)
    preview=scene.get('flat_map',{}).get('next_event')
    if preview:
        target=next((event for event in scene['visual_events'] if event['id']==preview['event_id']),None)
        if target:preview['event_time']=target['time']
    for sound in scene.get('sound_events',[]):
        target=next((event for event in scene['visual_events'] if event['id']==sound.get('visual_event_id')),None)
        sound['time']=target['time'] if target else frame_time(sound['time'],latest=(frames-1)/30)
        sound['duration']=round(min(float(sound.get('duration',1)),duration-sound['time']),6)


def _fresh_final_edge(plan, context_node=None):
    """A new sourced context node/edge is the payoff, never an old reverse path."""
    if not plan['scenes']:return
    final=plan['scenes'][-1]
    event=next((e for e in final['visual_events'] if e['kind']=='final_reveal'),None)
    if not event or not final.get('routes'):return
    domain=plan.get('story',{}).get('domain')
    if domain in {'shipping','comparison'}:
        routes=[route for route in final['routes'] if not route.get('faint')]
        if len(routes)>=2:
            lengths=[sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:])) for route in routes[:2]]
            value=abs(lengths[1]-lengths[0]);target=routes[1]
            event.update(target_id=target['route_id'],coordinates=deepcopy(final['coordinates']),
                text=f'+{value:,.0f} km',value=round(value,6),unit='km',claim_id='M01')
            plan.setdefault('metadata',{})['production_final_payoff']=dict(scene_id=final['scene_id'],event_id=event['id'],
                kind='verified_geometric_route_comparison',route_ids=[route['route_id'] for route in routes[:2]],
                difference_km=round(value,6),source_ids=sorted({source for route in routes[:2] for source in route['source_ids']}),
                interpretation='Derived geometry under explicit scenario; not delay, economics, traffic or a new unverified sea route')
        return
    fresh=next((route for route in final['routes'] if route['route_id']==event.get('target_id') and route.get('progress_start',0)==0 and abs(route.get('start_time',0)-event['time'])<=1/30),None)
    if fresh:return
    seen={point.get('location_id') for scene in plan['scenes'] for route in scene['routes'] for point in route['points']}
    # Prefer a genuinely new city separated enough to form a legible new edge.
    # The explicit sample Shanghai comes from the same catalog as its three cities.
    if context_node:
        city=resolve_location(context_node)
        if city['id'] in seen:raise ValueError('Final context node must be genuinely new to this plan')
    else:
        anchor=final['coordinates']
        candidates=[city for city in LOCATIONS.values() if city['kind']=='city' and city['id'] not in seen and great_circle_distance(anchor,city['coordinates'])>=250]
        if not candidates:return
        city=min(candidates,key=lambda place:great_circle_distance(anchor,place['coordinates']))
    origin=deepcopy(final['coordinates']);destination=deepcopy(city['coordinates'])
    identifier='P_FINAL_'+city['id'].upper()
    route=dict(route_id=identifier,kind='great_circle',points=[origin,destination],
        altitude_km=13.,start_time=event['time'],end_time=round(max(event['time']+.25,final['duration']-.10),6),
        progress_start=0.,progress_end=1.,faint=True,color='#8ebbc9',
        length_km=round(great_circle_distance(origin,destination),6),
        source_ids=sorted({origin['source_id'],destination['source_id']}),
        description='Hypothetical context connection to '+city['name']+'; not observed traffic',assumption_ids=['A01'])
    final['routes'].append(route)
    event.update(target_id=identifier,coordinates=deepcopy(destination),text=city['name'].upper())
    claims=plan['story']['claims'];claim_ids={claim['id'] for claim in claims}
    fact='FP_CONTEXT';simulation='MP_CONTEXT'
    while fact in claim_ids:fact+='1'
    while simulation in claim_ids:simulation+='1'
    claims.append(dict(id=fact,text=city['name']+'의 위치는 보존된 공개 GIS 좌표에서 확인됩니다.',status='FACT',source_ids=[destination['source_id']],scope='coordinate provenance'))
    assumptions=[claim['id'] for claim in claims if claim['status']=='ASSUMPTION']
    claims.append(dict(id=simulation,text='기존 연결망에서 '+city['name']+'로 가상 연결 한 개가 추가됩니다. 실제 운항, 수요 또는 미래 결과가 아닙니다.',status='SIMULATION',source_ids=route['source_ids'],assumption_ids=assumptions,scope='hypothetical final context-network extension; visualization only'))
    event['claim_id']=simulation
    final['claim_ids']=list(dict.fromkeys(final['claim_ids']+[fact,simulation]+assumptions))
    final['geographic_targets']=list(dict.fromkeys(final['geographic_targets']+[city['id']]))
    final['exit_state']['active_routes'].append(identifier)
    metadata=plan.setdefault('metadata',{})
    if 'coordinate_claim_targets' in metadata:metadata['coordinate_claim_targets'][fact]=city['id']
    metadata['production_final_payoff']=dict(scene_id=final['scene_id'],event_id=event['id'],route_id=identifier,context_node=city['id'],context_coordinates=destination,
        source_ids=route['source_ids'],fact_status='SIMULATION',new_edge_onset=event['time'],coordinate_fact_id=fact,simulation_claim_id=simulation)
    plan['story'].setdefault('limitations',[]).append('마지막 주변 도시 연결은 가상의 네트워크 확장입니다. 실제 항공편이나 교통량을 의미하지 않습니다.')


def _map_text(scene,large_titles=False):
    texts=[]
    for event in scene['visual_events']:
        if not large_titles:event['text']=_minimal_event_text(event,scene)
        text=event.get('text','').strip()
        active_city=next((label for label in scene.get('labels',[]) if label.get('role')=='city' and label.get('coordinates')==event.get('coordinates') and label.get('start_time',0)<=event['time']<label.get('end_time',scene['duration'])),None)
        if not large_titles and active_city:
            if event['kind']=='arrival' and text.casefold()==active_city['text'].casefold():
                text=event['text']='ARRIVED'
            elif event['kind']=='new_variable' and text=='ASSUME '+active_city['text'].upper():
                text=event['text']='ASSUMPTION'
        if not text:continue
        coordinates=event.get('coordinates')
        if not coordinates or not verified_coordinate(coordinates):continue
        role='status' if text=='ARRIVED' else 'country' if event['kind']=='country_reveal' else 'distance' if event.get('unit')=='km' or event['kind'] in {'distance_reveal','milestone_reveal','comparison_reveal'} else 'status' if event['kind'] in {'route_blocked','new_variable'} else 'route' if event['kind'] in {'route_reroute','alternate_route_reveal','response','route_choice'} else 'city'
        texts.append(dict(id='T_'+event['id'],event_id=event['id'],text=text,coordinates=deepcopy(coordinates),
            start_time=event['time'],end_time=round(min(scene['duration'],event['time']+max(.55,event['duration'])),6),
            role=role,priority=8 if event.get('role') in {'peak','payoff','variable'} else 5,large_title_approved=False))
        if role in {'route','distance','status'}:

            route=next((r for r in scene['routes'] if r['route_id']==event['target_id']),None)
            if route is None:route=next((r for r in scene['routes'] if not r.get('faint') and r['start_time']<=event['time']<r['end_time']),None)
            if route is not None:texts[-1]['route_id']=route['route_id']
    scene['text_events']=texts
    scene['text_density']='MINIMAL'
    # Explicit persistent labels remain map-anchored and retain their place IDs.
    for label in scene.get('labels',[]):
        if label.get('role')=='status' and not large_titles:
            label['text']='ON HOLD' if 'CLOSED' in label['text'] or 'HOLD' in label['text'] else 'ASSUMPTION'


def _repair_global_route_information(scene):
    """A route annotation names a distant endpoint without placing a city there.

    The existing globe may hide a far destination behind its horizon. Legacy
    header captions bypassed that constraint. Production writes short, sourced
    information beside the currently visible route instead of an occluded place
    label. Geography/focus and physical arrival/block events are not fabricated.
    """
    changes=[]
    geographic={'city_reveal','country_reveal','region_reveal','destination_preview'}
    for event in scene['visual_events']:
        if event['kind'] in {'route_start','entity_departure','arrival','route_blocked','final_reveal'}:continue
        moving=[r for r in scene['routes'] if not r.get('faint') and r.get('progress_end',1)>r.get('progress_start',0)]
        routes=[r for r in moving if r.get('start_time',0)<=event['time']<r.get('end_time',scene['duration'])] or moving
        route=next((r for r in routes if r['route_id']==event.get('target_id')),None) or (routes[-1] if routes else next((r for r in scene['routes'] if not r.get('faint')),None))
        if not route:continue
        original=deepcopy(event)
        if event['kind'] in geographic:
            name=_coordinate_name(event.get('coordinates',{}),scene['location'].upper())
            event.update(kind='route_choice' if event.get('role')=='hint' else 'milestone_reveal',target_id=route['route_id'],claim_id='M01')
            if event['kind']=='route_choice':event.update(text='TO '+name,value=None,unit='')
        elif event['kind'] in {'connection_reveal','escalation','peak_reveal'} and not event.get('text'):
            event.update(target_id=route['route_id'],claim_id='M01')
        # Every available informational annotation has an explicit route owner;
        # it can remain visible while its verified endpoint is beyond the rim.
        if event['kind'] in {'route_choice','milestone_reveal','distance_reveal','comparison_reveal','new_variable','connection_reveal','response','consequence_reveal','escalation','peak_reveal','alternate_route_reveal'}:
            event['target_id']=route['route_id']
            if event['kind'] in {'connection_reveal','consequence_reveal','escalation','peak_reveal'}:

                u=max(0.,min(1.,(event['time']-route['start_time'])/max(.001,route['end_time']-route['start_time'])))
                progress=route['progress_start']+(route['progress_end']-route['progress_start'])*u*u*(3-2*u)
                length=sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:]))
                event.update(value=round(length if progress>=1-1e-8 else length*(1-progress),6),unit='km',claim_id='M01')
        if event!=original:changes.append(dict(event_id=event['id'],before_kind=original['kind'],after_kind=event['kind'],route_id=route['route_id'],reason='Direct route information uses real route geometry instead of a globe-occluded geographic caption'))
    return changes


def _flat_settings(scene,terrain):
    if scene.get('render_mode')!='FLAT_MAP_PREMIUM':
        scene['render_mode']='FLAT_MAP_PREMIUM'
        scene['camera_preset']=CAMERA_TO_FLAT.get(scene['camera_preset'],'FLAT_REGION_FOCUS')
        begin,end=scene['camera_start'],scene['camera_end']
        coordinates=[scene['coordinates']]+[p for r in scene['routes'] if not r.get('faint') for p in r['points']]
        extent=max((c['lon'] for c in coordinates),default=end['lon'])-min((c['lon'] for c in coordinates),default=begin['lon'])
        span=max(24.,min(90.,extent*1.5+8.))
        scene['flat_map']=dict(projection='LOCAL_MERCATOR',terrain_texture=terrain,
            camera_start=dict(lon=begin['lon'],lat=begin['lat'],span_degrees=span*1.12,tilt=.07,rotation=0.),
            camera_end=dict(lon=end['lon'],lat=end['lat'],span_degrees=span,tilt=.07,rotation=0.),
            country_highlights=[],focus=[])
    flat=scene['flat_map'];flat.setdefault('terrain_texture',terrain)
    for event in scene['visual_events']:
        if event['kind']=='network_expand':
            route=next((r for r in scene['routes'] if r['route_id']==event['target_id']),None)
            if route and route.get('progress_start',0)==0:
                route['start_time']=event['time']
                route['end_time']=max(route['end_time'],min(scene['duration'],event['time']+.35))
    scene['lighting_preset']='GEOGRAPHY_READABILITY'
    from .presets import CAMERA_PRESETS
    scene['camera_speed']=CAMERA_PRESETS[scene['camera_preset']]['speed']
    scene['visual_polish']={'version':'v004','entity_separation':'v1'}
    country_events=[e for e in scene['visual_events'] if e['kind']=='country_reveal']
    for event in country_events:
        country=_country_code(scene,event)
        if not country:continue
        highlight=next((h for h in flat.get('country_highlights',[]) if h['country']==country),None)
        if highlight:
            # Fresh fill must begin with its reveal, never count earlier tint as
            # a second new incident. Root's E006 defect is corrected here.
            highlight['start_time']=event['time'];highlight['end_time']=scene['duration']
        else:
            flat.setdefault('country_highlights',[]).append(dict(country=country,source_id='natural_earth_countries',
                start_time=event['time'],end_time=scene['duration'],color=COUNTRY_PALETTE[0],opacity=.24))
    if not flat.get('country_highlights'):
        code=_country_code(scene)
        if code:flat['country_highlights']=[dict(country=code,source_id='natural_earth_countries',start_time=0.,end_time=scene['duration'],color=COUNTRY_PALETTE[0],opacity=.20)]
    focus=flat.get('focus')
    if not focus:
        flat['focus']=[dict(target_id=scene['coordinates']['location_id'],coordinates=deepcopy(scene['coordinates']),
            start_time=0.,end_time=scene['duration'],radius_degrees=7.,strength=.18)]
    scene['focus_target']=dict(target_id=scene['coordinates']['location_id'],coordinates=deepcopy(scene['coordinates']),type='city')
    eligible=[e for e in scene['visual_events'] if e.get('coordinates') and e['time']>.35 and e['kind'] in {'new_variable','destination_preview','country_reveal','region_reveal'}]
    if eligible and not flat.get('next_event'):
        event=eligible[-1];flat['next_event']=dict(event_id=event['id'],coordinates=deepcopy(event['coordinates']),
            event_time=event['time'],lead_time=min(.35,event['time']),strength=.25)
        if event['kind']=='new_variable':scene['camera_preset']='FLAT_NEXT_EVENT_PREVIEW'


def apply_production_defaults(plan, *, pace=None, profile='PRODUCTION_DEFAULT_CANDIDATE', preserve_scene_ids=(), final_context_node=None):
    """Transform a new in-memory plan; never mutate a stored approval/version."""
    plan=deepcopy(plan);pace=normalize_pace(pace or plan['request'].get('pace','FAST'))
    if profile not in {'PRODUCTION_DEFAULT','PRODUCTION_DEFAULT_CANDIDATE'}:raise ValueError('Unknown production profile')
    large=plan['request'].get('large_title_requested',False)
    if not isinstance(large,bool):raise ValueError('large_title_requested must be true/false')
    marker={**PRODUCTION_PRESET,'profile':profile,'pace':pace,'large_titles':large}
    plan['production_defaults']=deepcopy(marker)
    plan['options'].update(pace=pace,sfx=plan['request'].get('sfx',True))
    plan['request'].update(pace=pace,sfx=plan['options']['sfx'],production_preset=profile)
    repairs=[];coverage=[];route_annotation_repairs=[];preserved=set(preserve_scene_ids)
    for index,scene in enumerate(plan['scenes']):
        if scene['scene_id'] in preserved:continue
        scene['production_defaults']=dict(version='v1',profile=profile,large_titles=large)
        for event in scene['visual_events']:
            if event.get('role') in {'peak','payoff'} or event['kind'] in {'peak_reveal','final_reveal'}:
                event['time']=min(event['time'],scene['duration']-.8)
                event['duration']=max(.8,event.get('duration',.8))
        _snap_scene_events(scene)
        terrain=_registered_terrain(scene)
        purpose_peak=scene.get('role') in {'peak','payoff'} or any(e.get('role')=='peak' for e in scene['visual_events'])
        clip=scene['scene_type']=='CINEMATIC_CLIP'
        if not clip and terrain and not purpose_peak:
            _flat_settings(scene,terrain);scene['visual_mode']='FLAT_MAP'
            coverage.append(dict(scene_id=scene['scene_id'],selection='REGISTERED_NATIVE_TERRAIN_FLAT_v004',terrain=terrain['url']))
        elif not clip:
            if scene.get('render_mode')=='FLAT_MAP_PREMIUM' and purpose_peak:
                # A mixed sample's already authored Flat peak may stay Flat until
                # its existing geographic handoff; ratios are never forced.
                _flat_settings(scene,terrain or scene['flat_map'].get('terrain_texture'))
                scene['visual_mode']='FLAT_MAP'
                coverage.append(dict(scene_id=scene['scene_id'],selection='AUTHORED_FLAT_PEAK_BEFORE_EARTH_HANDOFF'))
            else:
                scene['render_mode']='MASTER_V3_EARTH';scene['visual_polish']={'version':'v004'}
                scene['visual_mode']='HERO' if purpose_peak else '3D_EARTH'
                if not purpose_peak:scene['lighting_preset']='GEOGRAPHY_READABILITY'
                coverage.append(dict(scene_id=scene['scene_id'],selection='MASTER_V3_PEAK' if purpose_peak else 'READABLE_MASTER_V3_COVERAGE_FALLBACK',reason=None if purpose_peak else 'No registered native terrain tile covers all required locations; original global renderer retained'))
        else:scene['visual_mode']='CINEMATIC_CLIP'
        scene['sfx_intensity']='PEAK' if scene.get('role')=='payoff' else 'HIGH' if purpose_peak or scene.get('role')=='variable' else 'LOW' if scene.get('role') in {'orientation','geography'} else 'MEDIUM'
        scene,repair=apply_scene_pace(scene,pace);plan['scenes'][index]=scene;repairs.append(repair)
        if terrain is None and not clip:
            route_annotation_repairs.extend(dict(scene_id=scene['scene_id'],**record) for record in _repair_global_route_information(scene))
        # A held network is not fresh peak information. Reveal an exact sourced
        # route metric instead of relying on the old inherited peak caption.
        for event in scene['visual_events']:
            if event['kind']!='peak_reveal' or isinstance(event.get('value'),(int,float)):continue
            choices=[route for route in scene['routes'] if not route.get('faint') and not route['route_id'].startswith('N_')]
            if not choices:continue
            active=[route for route in choices if route['start_time']<=event['time']<route['end_time']]
            route=(active or choices)[-1]
            u=max(0.,min(1.,(event['time']-route['start_time'])/max(.001,route['end_time']-route['start_time'])))
            progress=route['progress_start']+(route['progress_end']-route['progress_start'])*u*u*(3-2*u)
            length=sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:]))
            event.update(target_id=route['route_id'],coordinates=deepcopy(route['points'][-1]),value=round(length if progress>=1-1e-8 else length*(1-progress),6),unit='km',claim_id='M01')
        _map_text(scene,large)
        active=[r for r in scene['routes'] if not r.get('faint') and r.get('progress_end',1)>r.get('progress_start',0)]
        reroute=next((e for e in scene['visual_events'] if e['kind']=='route_reroute'),None)
        preferred=reroute['target_id'] if reroute else active[0]['route_id'] if active else None
        for route in scene['routes']:
            route['visibility_role']='primary' if route['route_id']==preferred else 'secondary'
        if preferred:
            scene['focus_target']=dict(target_id=preferred,type='route',coordinates=deepcopy(scene['coordinates']))
    # Countries use at most three simultaneous distinguishable translucent hues.
    countries={h['country'] for s in plan['scenes'] for h in s.get('flat_map',{}).get('country_highlights',[])}
    colors={country:COUNTRY_PALETTE[i%len(COUNTRY_PALETTE)] for i,country in enumerate(sorted(countries))}
    for scene in plan['scenes']:
        if scene['scene_id'] in preserved:continue
        for h in scene.get('flat_map',{}).get('country_highlights',[]):h['color']=colors[h['country']]
    # For very short samples preserve the density gate without accelerating TTS:
    # strengthen the initial event and reserve .8s for the last visible reward.
    if plan['duration']<20 and pace=='FAST' and not preserved:
        first=plan['scenes'][0]
        meaningful=[e for e in first['visual_events'] if e.get('meaningful',True)]
        if meaningful:
            event=meaningful[0];event['time']=min(event['time'],.1)
            for h in first.get('flat_map',{}).get('country_highlights',[]):
                if h['country']==_country_code(first,event):h['start_time']=event['time']
            for text in first.get('text_events',[]):
                if text['event_id']==event['id']:text['start_time']=event['time']
        final=plan['scenes'][-1]
        payoff=next((e for e in final['visual_events'] if e['kind']=='final_reveal'),None)
        if payoff:
            payoff['time']=frame_time(final['duration']-.8,latest=final['duration']-.8)
            payoff['duration']=round(final['duration']-payoff['time'],6)
    if plan['scenes'][-1]['scene_id'] not in preserved:_fresh_final_edge(plan,final_context_node)
    # Exact new renderer clocks and read windows invalidate only changed Scenes.
    from .planner import refresh_clock_dependent_route_information
    for scene in plan['scenes']:
        if scene['scene_id'] in preserved:continue
        for event in scene['visual_events']:
            if any(route['route_id']==event.get('target_id') for route in scene['routes']):
                refresh_clock_dependent_route_information(scene,event)
        _map_text(scene,large)
    # A concise map-attached question is actually drawn even when TTS is off.
    first=plan['scenes'][0]
    if first['scene_id'] not in preserved:
        import re
        shipping=plan.get('story',{}).get('domain')=='shipping'
        days=re.search(r'(\d+)\s*(?:일|days?)',plan['request'].get('topic',''),re.I) if shipping else None
        question=(days.group(1)+' DAYS?') if days else 'BLOCKED?' if shipping else 'NEXT?'
        identifier='P_HOOK_QUESTION'
        first['visual_events'].append(dict(id=identifier,kind='hook_reveal',time=0.,duration=min(1.1,first['duration']),
            target_id=first['coordinates'].get('location_id',first['geographic_targets'][0]),coordinates=deepcopy(first['coordinates']),
            role='hook',caused_by=None,meaningful=False,text=question,claim_id='A01',description='Short map-attached scenario question'))
        first['text_events'].append(dict(id='T_'+identifier,event_id=identifier,text=question,coordinates=deepcopy(first['coordinates']),
            start_time=0.,end_time=min(1.1,first['duration']),role='question',priority=9,large_title_approved=False))
    # Preserve continuity snapshots including new readable lighting state.
    previous=None
    for scene in plan['scenes']:
        if scene['scene_id'] not in preserved:
            if previous is not None:scene['entry_state']=deepcopy(previous)
            scene['entry_state']['camera']=deepcopy(scene['camera_start'])
            scene['exit_state']['camera']=deepcopy(scene['camera_end'])
            scene['exit_state']['lighting']=scene['lighting_preset']
        previous=scene['exit_state']
    # Geographic mixed-mode transitions are explicitly authored. Production
    # never obscures the current map with the legacy opaque cloud/blur veil.
    for a,b in zip(plan['scenes'],plan['scenes'][1:]):
        if a['scene_id'] in preserved or b['scene_id'] in preserved:continue
        am=a.get('render_mode','MASTER_V3_EARTH');bm=b.get('render_mode','MASTER_V3_EARTH')
        if am!=bm:
            transition='FLAT_TO_EARTH' if am=='FLAT_MAP_PREMIUM' else 'EARTH_TO_FLAT'
            a['transition_out']=b['transition_in']=transition
            d=a['motion_timing']['transition_duration']
            a['map_transition']=b['map_transition']=dict(duration=d)
    from .sfx_library import prepare_production_sound_events
    plan=prepare_production_sound_events(plan)
    metadata=plan.setdefault('metadata',{})
    metadata['production_pace_changes']=repairs;metadata['production_coverage']=coverage
    metadata['production_global_route_annotations']=route_annotation_repairs
    metadata['production_policy']=dict(information_first=True,default_graphics='PREMIUM_FLAT_v004',
        global_renderer_preserved=True,native_regional_coverage_validated_only=True,ratios_guideline_not_forced=True,
        no_global_video_speedup=True,narration_playback_rate=1.0,large_titles_require_explicit_request=True)
    metadata['production_visual_mix_seconds']={mode:round(sum(s['duration'] for s in plan['scenes'] if s.get('visual_mode')==mode),6) for mode in ['FLAT_MAP','3D_EARTH','HERO','CINEMATIC_CLIP']}
    metadata['dead_time_gate']=analyze_dead_time(plan)
    for key in ['gate','approval','plan_hash']:plan.pop(key,None)
    return plan


def fit_production_readability(plan, certificate):
    """Bounded shared-camera widening for direct globe labels, never fake events.

    This restores global composition after replacing old screen captions with
    real map annotations. Only failed globe scenes
    are adjusted; a passing East Asia production sample is unchanged.
    """
    from .visibility import certify_semantic_visibility
    scenes=plan['scenes'];indices={scene['scene_id']:i for i,scene in enumerate(scenes)}
    records=[]
    # A distant status label keeps its explicit GIS position rather than riding
    # a nearby route head. Four 25% pull-backs can still leave a valid Singapore
    # label outside a Cape-route shot; retain the 6-radius cap and certify up to
    # eight real composition changes instead of changing the label or gate.
    for attempt in range(8):
        failed={failure.get('scene_id') for failure in certificate.get('failures',[]) if failure.get('code') in {'GEOGRAPHIC_EVENT_NOT_VISIBLE','MEANINGFUL_EVENT_NOT_ELIGIBLE','MEANINGFUL_EVENT_ELIGIBLE_LATE','MEANINGFUL_EVENT_ELIGIBLE_TOO_BRIEFLY'}}
        failed={sid for sid in failed if sid in indices and scenes[indices[sid]].get('render_mode')=='MASTER_V3_EARTH'}
        if not failed:break
        boundaries={boundary for sid in failed for boundary in (indices[sid],indices[sid]+1)}
        changed=False
        for boundary in sorted(boundaries):
            pose=deepcopy(scenes[boundary-1]['camera_end'] if boundary else scenes[0]['camera_start'])
            old=pose['height'];pose['height']=min(6.,old*1.25)
            if abs(pose['height']-old)<1e-9:continue
            changed=True
            if boundary:
                scenes[boundary-1]['camera_end']=deepcopy(pose);scenes[boundary-1]['exit_state']['camera']=deepcopy(pose)
            if boundary<len(scenes):
                scenes[boundary]['camera_start']=deepcopy(pose);scenes[boundary]['entry_state']['camera']=deepcopy(pose)
            records.append(dict(attempt=attempt+1,boundary_index=boundary,before_height=old,after_height=pose['height'],reason='Real world-attached route information needs readable global geographic framing'))
        if not changed:break
        certificate=certify_semantic_visibility(plan)
    if records:plan.setdefault('metadata',{})['production_global_readability_framing']=records
    plan.setdefault('metadata',{})['semantic_visibility']=certificate
    return certificate


def validate_production_plan(plan):
    """Optional semantic checks leave every unmarked historical JSON unchanged."""
    if plan.get('production_defaults',{}).get('version')!='v1':return dict(passed=True,errors=[],warnings=[],legacy=True)
    errors=[]
    for scene in plan['scenes']:
        sid=scene['scene_id'];marker=scene.get('production_defaults',{})
        if marker.get('version')!='v1':continue # explicitly preserved cache Scene
        if scene.get('render_mode')=='FLAT_MAP_PREMIUM' and scene.get('visual_polish',{}).get('version')!='v004':
            errors.append(dict(code='PRODUCTION_FLAT_REQUIRES_APPROVED_V004',scene_id=sid))
        if scene.get('visual_mode') in {'HERO','3D_EARTH'} and scene.get('render_mode','MASTER_V3_EARTH')!='MASTER_V3_EARTH':
            errors.append(dict(code='PRODUCTION_VISUAL_MODE_RENDER_MISMATCH',scene_id=sid))
        if not marker.get('large_titles',False):
            for text in scene.get('text_events',[]):
                if text.get('role')=='title' or text.get('large_title_approved'):
                    errors.append(dict(code='UNAPPROVED_LARGE_TITLE',scene_id=sid,text_event_id=text['id']))
        ids={e['id']:e for e in scene['visual_events']}
        for text in scene.get('text_events',[]):
            event=ids.get(text.get('event_id'))
            if not verified_coordinate(text['coordinates']):errors.append(dict(code='UNVERIFIED_PRODUCTION_TEXT_ANCHOR',scene_id=sid,text_event_id=text['id']))
            if text['end_time']<=text['start_time'] or text['end_time']>scene['duration']+.001:errors.append(dict(code='PRODUCTION_TEXT_WINDOW_INVALID',scene_id=sid,text_event_id=text['id']))
            if text.get('event_id') and (not event or abs(text['start_time']-event['time'])>1/30+.001):errors.append(dict(code='PRODUCTION_TEXT_EVENT_DESYNC',scene_id=sid,text_event_id=text['id']))
        if scene.get('motion_timing',{}).get('tts_playback_rate',1)!=1:errors.append(dict(code='TTS_RATE_CHANGED_BY_PACE',scene_id=sid))
    dead_time=analyze_dead_time(plan)
    errors.extend(dead_time['errors'])
    return dict(passed=not errors,errors=errors,warnings=dead_time['warnings'],dead_time=dead_time)


def production_default_active():
    return production_default_status()['active']


def production_status():
    return production_default_status()


def promote_production_default(evidence_path, final_mp4_path=None, *, promotion_path=None):
    """Promote only an actual 10–15s delivered integration test, with file hashes.

    Paths in the saved record are repository-relative for a fresh checkout.
    This is an internal quality gate, never a user's approval of a new topic.
    Renderer/plan approval and future project-level rendering remain separate.
    """
    from .qc import probe_video
    evidence=Path(evidence_path).resolve();qc=json.loads(evidence.read_text())
    required=dict(passed=True,full_video_speedup=False,rendered_mp4_verified=True,
                  no_75s_render=True,mobile_full_playback_passed=True,
                  automatic_qc_passed=True,sfx_frame_sync_passed=True,
                  sfx_repeat_prevention_passed=True,tts_ducking_fixture_passed=True)
    failures=[key for key,value in required.items() if qc.get(key) is not value]
    duration=float(qc.get('duration',0))
    if not 10<=duration<=15:failures.append('bounded_10_to_15_seconds')
    if int(qc.get('decoded_frames',0))!=round(duration*30):failures.append('all_frames_decoded')
    movie=Path(final_mp4_path or qc.get('final_mp4',''))
    if not movie.is_absolute():movie=APP_ROOT/movie
    movie=movie.resolve()
    try:
        evidence_relative=str(evidence.relative_to(REPO_ROOT));movie_relative=str(movie.relative_to(REPO_ROOT))
    except ValueError as error:raise ValueError('Promotion evidence and MP4 must be inside the repository for portable checkout') from error
    if not movie.is_file():failures.append('final_mp4_missing')
    if failures:raise ValueError('PRODUCTION_PROMOTION_BLOCKED: '+', '.join(failures))
    from fractions import Fraction
    media=probe_video(movie)
    stream=next((item for item in media.get('streams',[]) if item.get('codec_type')=='video'),{})
    fps=float(Fraction(stream.get('avg_frame_rate','0/1')))
    if stream.get('codec_name')!='h264' or stream.get('width')!=1080 or stream.get('height')!=1920 or abs(float(media.get('format',{}).get('duration',0))-duration)>.04 or fps<30:
        raise ValueError('PRODUCTION_PROMOTION_BLOCKED: actual_final_mp4_spec')
    from datetime import datetime,timezone
    record=dict(version='v1',promoted=True,profile='PRODUCTION_DEFAULT',path_base='repository',
        promoted_at=datetime.now(timezone.utc).isoformat(),evidence_path=evidence_relative,
        evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
        final_mp4_path=movie_relative,final_mp4_sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),
        duration=duration,decoded_frames=int(qc['decoded_frames']),
        scope='Approved v004 native terrain + minimal FAST map policy; global GIS uses readable preserved V3 fallback when no registered tile covers required locations')
    paths=['engine/production.py','engine/pace.py','engine/planner.py','engine/presets.py','engine/retention.py','engine/sfx_library.py','engine/audio.py','engine/schema.py','engine/qc.py','engine/assets.py','engine/rendering.py',
        'data/scene_plan.schema.json','web/production_visual_adapter.js','web/render_production_flat.html','web/render_production_earth.html','tools/render_production_scene.mjs','tools/semantic_preflight.mjs']
    record['source_manifest']={name:hashlib.sha256((APP_ROOT/name).read_bytes()).hexdigest() for name in paths}
    destination=Path(promotion_path or PROMOTION_PATH)
    if destination.exists():raise ValueError('Existing promotion record is preserved; choose a new versioned path')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    return record
