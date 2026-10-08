"""Geographic IR compiler, selected AFTER the reference beat budget is fixed.

Shares the immutable planner's GIS/claim/entity constructors. It does not call
its five-scene event scheduler or retime a completed plan. Legacy code is intact.
Blueprint owns scene boundaries, event onsets and route windows before geometry.
"""
from copy import deepcopy
import math
from .planner import CAMERA_PRESETS, RouteEngine, SOUND_MAP, _claims, _narration, _scene_role, _shipping_narration, _topic_hook, apply_readable_place_labels, camera_state, choose_lighting, coordinate_source_report, require_plugins

def compile_content(raw, blueprint):
    request=deepcopy(blueprint['request']);duration=request['duration'];scenario=deepcopy(blueprint['scenario']);require_plugins(scenario['plugins'])
    locations=scenario['locations'];bounds=blueprint['bounds'];n=len(bounds)-1;events=deepcopy(blueprint['events'])
    event_window_repairs=[]
    for event in events:
        if event['kind'] in {'route_start','entity_departure','arrival','route_blocked'}:continue
        index=next((i for i in range(n) if bounds[i]<=event['time']<bounds[i+1]),n-1)
        if bounds[index+1]-event['time']<.6:
            previous=max((item['time'] for item in events if item['time']<event['time']),default=0.)
            timestamp=round(bounds[index+1]-.6,6)
            if timestamp>previous+.7:
                event_window_repairs.append(dict(event_id=event['id'],before_time=event['time'],after_time=timestamp,reason='Information needs a real30fps draw/read window inside its independent Scene'))
                event['time']=timestamp
    claims=_claims(scenario,request);sources=coordinate_source_report()
    route_specs=deepcopy(blueprint['route_specs'])
    for window in event_window_repairs:
        window['planning_event_id']=window['event_id']
        window['event_id']=next((event['id'] for event in events if abs(event['time']-window['after_time'])<1e-6),window['event_id'])
    def boundary_anchor(time,pose):
        if time<=0:return pose,None
        primary=[r for r in route_specs if not r[0]['route_id'].startswith('N_')]
        active=[r for r in primary if r[1]<=time<r[2]]
        if scenario['bypass'] and time/duration>=.5:active=[r for r in active if r[0]['route_id']==scenario['routes'][-1]['route_id']] or active
        item=active[-1] if active else next((r for r in primary if time<r[1]),primary[-1])
        route,rs,re_=item;p=max(0.,min(1.,(time-rs)/(re_-rs)))
        if scenario['domain']=='shipping' and route['route_id']=='R_SUEZ':p*=.40194431692212046
        p=round(p,8)
        point=RouteEngine.spherical_point(route['points'],p)
        pose={**pose,**point,'target_lon':point['lon'],'target_lat':point['lat']}
        pose.pop('location_id',None)
        return pose,dict(time=time,route_id=route['route_id'],progress=p,method='GIS cumulative angular-length spherical interpolation; derived camera position, not a new place',source_ids=route['source_ids'])
    camera_provenance=[];overview_provenance=None
    first_start=camera_state(locations[0],'GLOBAL_ESTABLISH');first_start['yaw']=-.26
    states=[];scenes=[];previous_exit=None
    for i in range(n):
        start,end=bounds[i:i+2];d=end-start;q=(start+end)/2/duration
        scene_type,camera,directing,role=_scene_role(q,i==n-1)
        if i==0:scene_type,camera,directing,role='EARTH_ESTABLISH','FAST_HOOK_DIVE','HOOK_REVEAL','hook'
        if duration<40 and .64<=q<=.8:scene_type,camera,directing,role='ROUTE_CHASE','HORIZON_REVEAL','PEAK_MOMENT','peak'
        loc=locations[blueprint['beats'][i]['location_index']]
        light=choose_lighting(scene_type,role)
        if scenario['domain']=='shipping' and .2<=q<=.7:light='GEOGRAPHY_READABILITY'
        if scenario['domain']=='comparison':
            light='GEOGRAPHY_READABILITY'
            if i not in (0,n-1):scene_type='COUNTRY_FOCUS';camera='COUNTRY_APPROACH';directing='COUNTRY_REVEAL'
        style=request['style_profile'];speed_factor=1.
        if style=='travel':
            speed_factor=.85
            if light!='HERO':light='GEOGRAPHY_READABILITY' if scene_type in {'COUNTRY_FOCUS','COMPARISON','TERRITORY','TIMELINE'} or scenario['domain']=='shipping' else 'DAY_DOCUMENTARY'
        elif style=='documentary' and (scene_type in {'EARTH_ESTABLISH','COUNTRY_FOCUS','CITY_FOCUS','COMPARISON','FINAL_OVERVIEW'} or role in {'orientation','geography','consequence'}):light='GEOGRAPHY_READABILITY'
        elif style=='network':
            speed_factor=1.1
            if scene_type in {'NETWORK','COMPARISON'} and camera!='HORIZON_REVEAL':camera='EARTH_ORBIT' if role=='peak' else 'NETWORK_EXPANSION'
        camera_begin=deepcopy(previous_exit['camera']) if previous_exit else deepcopy(first_start)
        camera_end=camera_state(loc,camera)
        # Continuous camera changes, including the wide final frame.
        camera_end['yaw']+=.025*(i%3-1)
        if i==n-1:
            camera_end,overview_provenance=RouteEngine.network_overview([scenario['routes'][-1]],camera_end)
            provenance=dict(time=end,method=overview_provenance['method'],source_ids=overview_provenance['source_ids'],network_overview=True)
        elif scenario['domain']=='comparison':
            coord=loc['coordinates'];camera_end.update(lon=coord['lon'],lat=coord['lat'],target_lon=coord['lon'],target_lat=coord['lat'])
            provenance=dict(time=end,method='Verified country focus coordinate; comparison has no moving entity',source_ids=[coord['source_id']],geography_focus=True,location_id=loc['id'])
        else:camera_end,provenance=boundary_anchor(end,camera_end)
        if provenance:camera_provenance.append(provenance)
        visible=[];entities=[]
        for r,rs,re_ in route_specs:
            if end<=rs:continue
            ps=max(0.,min(1.,(start-rs)/(re_-rs)));pe=max(0.,min(1.,(end-rs)/(re_-rs)))
            if scenario['domain']=='shipping' and r['route_id']=='R_SUEZ':
                ps*=.40194431692212046;pe*=.40194431692212046
            route={**deepcopy(r),'start_time':round(max(0.,rs-start),6),'end_time':round(min(d,max(0.,re_-start)),6),'progress_start':round(ps,8),'progress_end':round(pe,8),'faint':r['route_id'].startswith('N_') or (scenario['bypass'] and r['route_id']!=scenario['routes'][-1]['route_id'] and q>.5)}
            if route['end_time']<=route['start_time']:route.update(start_time=0.,end_time=d)
            visible.append(route)
            if pe>ps and scenario['domain']!='comparison' and not r['route_id'].startswith('N_'):
                entities.append(dict(id=('ship_reference' if r['route_id']=='R_SUEZ' else 'ship_alternative') if scenario['domain']=='shipping' else 'aircraft_'+r['route_id'],type='cargo_ship' if scenario['domain']=='shipping' else 'aircraft',route_id=r['route_id'],location_id=loc['id'],action='move',start_time=round(max(route['start_time'],rs+.2-start),6) if rs>=start else route['start_time'],end_time=route['end_time']))
        scene_events=[{**deepcopy(e),'time':round(e['time']-start,6)} for e in events if start<=e['time']<end]
        sound_events=[dict(id='A_'+e['id'],kind=SOUND_MAP[e['kind']],time=e['time'],duration=min(1.2,d-e['time']),visual_event_id=e['id'],gain_db=-15 if e['role']!='peak' else -10) for e in scene_events]
        if i==0:sound_events.insert(0,dict(id='A_OPEN',kind='cinematic_hit',time=0.,duration=1.,visual_event_id=None,gain_db=-12))
        labels=[dict(text=loc['id'][8:].upper() if loc['kind']=='airport' else loc['name'].upper(),coordinates=deepcopy(loc['coordinates']),start_time=.1,end_time=d,role='city',opacity=.9)]
        if i==n-1:
            labels=[dict(text=place['id'][8:].upper() if place['kind']=='airport' else place['name'].upper(),coordinates=deepcopy(place['coordinates']),start_time=.1,end_time=d,role='city',opacity=.9) for place in locations]
        if scenario['domain']=='shipping' and role=='variable':labels.append(dict(text='ASSUMPTION · CANAL CLOSED',coordinates=deepcopy(loc['coordinates']),start_time=.8,end_time=d,role='status',opacity=.8))
        apply_readable_place_labels(labels,light,include_status=True)
        timeline=dict(year=None,date=None,era='modern',timeline_position=round(start/duration,6))
        entry=deepcopy(previous_exit) if previous_exit else dict(camera=deepcopy(camera_begin),earth_rotation=0.,active_countries=[],active_routes=[],entities=[],lighting=light,timeline=timeline)
        exit_state=dict(camera=deepcopy(camera_end),earth_rotation=0.,active_countries=sorted({l.get('country','') for l in locations if l.get('country')}),active_routes=[r['route_id'] for r in visible],entities=[dict(id=e['id'],route_id=e['route_id'],progress=next(r['progress_end'] for r in visible if r['route_id']==e['route_id'])) for e in entities],lighting=light,timeline={**timeline,'timeline_position':round(end/duration,6)})
        narration=_topic_hook(scenario,request) if i==0 else _shipping_narration(start,end,duration,scene_events,route_specs,request,scenes[-1]['narration']) if scenario['domain']=='shipping' else _narration(role,loc,scenario['domain'],scenario['conditional'],d)
        # Keep short scenes comfortably under conservative Korean speech estimation.
        if len(narration.replace(' ',''))/5.8>d*.9:narration={'hook':'이 연결이 바뀐다면?','orientation':'검증된 출발점을 확인합니다.','progression':'다음 연결로 향합니다.','variable':'다른 경로가 필요합니다.','peak':'전체 연결이 드러납니다.','payoff':'새로운 연결이 보입니다.'}.get(role,'연결을 비교합니다.')
        scene=dict(hook=_topic_hook(scenario,request) if i==0 else '',scene_id=f'S{i+1:03}',start_time=start,duration=d,scene_type=scene_type,narration=narration,location=loc['name'],coordinates=deepcopy(loc['coordinates']),geographic_targets=[loc['id']],camera_preset=camera,camera_start=camera_begin,camera_end=camera_end,camera_speed=CAMERA_PRESETS[camera]['speed']*speed_factor,camera_easing=CAMERA_PRESETS[camera]['easing'],lighting_preset=light,entities=entities,entity_actions=[dict(entity_id=e['id'],action=e['action']) for e in entities],routes=visible,visual_events=scene_events,effects=[dict(kind='city_focus',target_id=loc['id'],strength=.35)],labels=labels,sound_events=sound_events,music_energy=.9 if role in {'hook','peak','payoff'} else .42 if role=='orientation' else .6,transition_in='camera_continuity',transition_out='camera_continuity',source_type='VERIFIED_GIS_WITH_EXPLICIT_SCENARIO',fact_status='SIMULATION',render_quality='CINEMA' if role=='peak' and request['quality']=='CINEMA' else request['quality'],entry_state=entry,exit_state=exit_state,directing_presets=[directing],claim_ids=['A01','M01']+[c['id'] for c in claims if c['status']=='FACT' and loc['coordinates']['source_id'] in c['source_ids']],year=None,date=None,era='modern',timeline_position=round(start/duration,6),motion_start=0.,description=f'{role}: {loc["name"]}',role=role,narration_event_ids=[e['id'] for e in scene_events])
        scenes.append(scene);previous_exit=exit_state
    plan=dict(schema_version='1.0',project_id=str(request.get('project_id','')),version=1,duration=duration,request=request,options={k:request[k] for k in ('tts','subtitles','bgm','quality')},story=dict(hook=scenes[0]['hook'],claims=claims,beats=[dict(scene_id=s['scene_id'],role=s['role'],cause=scenes[i-1]['scene_id'] if i else None,summary=s['description']) for i,s in enumerate(scenes)],domain=scenario['domain'],planner='offline-capability-bounded-v1',conclusion=claims[-1]['text'],limitations=['사실은 공개 GIS의 위치·형태·경로 자료에 한정합니다.','이동 속도·항로 선택·폐쇄의 결과는 가정 기반 시각화이며 예측이 아닙니다.']),scenes=scenes,required_plugins=scenario['plugins'],sources=sources,metadata=dict(camera_provenance=camera_provenance,style_profile=request['style_profile'],story_pattern={'shipping':'disruption-detour-network','comparison':'geography-comparison','geography':'route-choice-comparison','aviation':'journey-network-reveal'}[scenario['domain']]))
    # Explicit typed bindings distinguish places which share the same GIS file;
    # provenance cannot be established merely by matching a source ID.
    plan['metadata']['coordinate_claim_targets']={f'F{index+1:02}':loc['id'] for index,loc in enumerate(locations)}
    for optional in ('narration_file','narration_timing','tts_language'):
        if optional in request:plan['options'][optional]=request[optional]
    plan['metadata']['final_overview']=overview_provenance
    if event_window_repairs:plan['metadata']['scene_event_window_repairs']=event_window_repairs
    plan['story']['pattern']=plan['metadata']['story_pattern']
    return plan
