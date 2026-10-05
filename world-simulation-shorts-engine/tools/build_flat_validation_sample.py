#!/usr/bin/env python3
"""Build a new, opt-in 15s map/Earth quality sample without rendering anything.

The validated 20s planner supplies the existing source/claim/Scene contracts.
Only the returned in-memory copy is authored into five 3s shots. Existing plans,
defaults, project versions, caches, assets and renderer sources are untouched.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from engine.gis import RouteEngine, great_circle_distance, resolve_location, verified_coordinate
from engine.planner import generate_plan
from engine.presets import CAMERA_PRESETS
from engine.schema import validate_plan
from engine.storage import ProjectStore

TOPIC = '서울에서 도쿄로 이동한 민간 항공 연결의 다음 목적지가 타이베이로 바뀐다면?'
HOOK = '다음 목적지가 바뀐다면?'
DURATION = 15.0


def _route(identifier, first, last, start, end, ps=0., pe=1., *, faint=False):
    points = [deepcopy(first['coordinates']), deepcopy(last['coordinates'])]
    return dict(route_id=identifier, kind='great_circle', points=points,
                start_time=float(start), end_time=float(end), altitude_km=13.,
                progress_start=ps, progress_end=pe,
                source_ids=sorted({p['source_id'] for p in points}),
                color='#bde1e8', faint=faint,
                length_km=round(great_circle_distance(first, last), 6),
                description=f"{first['name']} -> {last['name']}", assumption_ids=['A01'])


def _camera(coordinates, *, height=.75, tilt=.025, yaw=0., bank=0., fov=44.):
    return dict(lon=coordinates['lon'], lat=coordinates['lat'], height=height,
                tilt=tilt, yaw=yaw, bank=bank, fov=fov,
                target_lon=coordinates['lon'], target_lat=coordinates['lat'])


def _flat_camera(pose, span):
    return dict(lon=pose['lon'], lat=pose['lat'], span_degrees=span,
                tilt=.07, rotation=0.)


def _event(identifier, kind, timestamp, target, coordinates, claim, text,
           *, role='progression', cause=None, duration=1.25):
    return dict(id=identifier, kind=kind, time=float(timestamp), duration=duration,
                target_id=target, coordinates=deepcopy(coordinates), claim_id=claim,
                role=role, caused_by=cause, meaningful=True, text=text,
                description=text, value=None, unit='')


def _entity(identifier, route, start=0., *, phase=0., action='move', persistent=True):
    return dict(id=identifier, type='aircraft', route_id=route,
                action=action, start_time=float(start), end_time=3.,
                phase_offset=phase, persistent=persistent, visibility_role='primary')


def _label(place, start=.05, end=3.):
    return dict(text=place['name'].upper(), coordinates=deepcopy(place['coordinates']),
                start_time=start, end_time=end, role='city', color='#e8eee9',
                size=52, opacity=.95)


def _sound(event):
    mapping = dict(country_reveal='soft_pulse', route_start='digital_sweep',
                   entity_departure='pass_by', destination_preview='soft_pulse',
                   milestone_reveal='digital_sweep', arrival='soft_impact',
                   new_variable='tension_riser', route_blocked='warning_hit',
                   route_reroute='transition_sweep', network_expand='wide_riser',
                   final_reveal='deep_final_hit')
    return dict(id='A_'+event['id'], kind=mapping[event['kind']], time=event['time'],
                duration=min(1.1, 3.-event['time']), visual_event_id=event['id'],
                gain_db=-11 if event['kind']=='final_reveal' else -16)


def _state(camera, timestamp, routes, entities, *, lighting, countries):
    return dict(camera=deepcopy(camera), earth_rotation=0.,
                active_countries=list(countries), active_routes=[r['route_id'] for r in routes],
                entities=[dict(id=e['id'], route_id=e['route_id'],
                               progress=next(r['progress_end'] for r in routes if r['route_id']==e['route_id']))
                          for e in entities], lighting=lighting,
                timeline=dict(year=None, date=None, era='modern', timeline_position=timestamp/15.))


def validate_sample_contract(plan):
    """Additional checks specific to this sample, not a replacement for Gates."""
    errors=[]
    if plan.get('duration')!=15 or len(plan.get('scenes',[]))!=5:
        errors.append('The sample must have five 3-second Scenes.')
    for index, scene in enumerate(plan.get('scenes',[])):
        if scene['start_time']!=index*3 or scene['duration']!=3:
            errors.append(f"{scene['scene_id']}: invalid frame-aligned clock")
        expected='FLAT_MAP_PREMIUM' if index<4 else 'MASTER_V3_EARTH'
        if scene.get('render_mode')!=expected:
            errors.append(f"{scene['scene_id']}: incorrect explicit rendering backend")
        for route in scene['routes']:
            if not all(verified_coordinate(point) for point in route['points']):
                errors.append(f"{scene['scene_id']}: unsourced route")
        if index and scene['entry_state']!=plan['scenes'][index-1]['exit_state']:
            errors.append(f"{scene['scene_id']}: state boundary mismatch")
    if not all(plan['options'][key] is False for key in ('tts','subtitles')) or plan['options']['bgm'] is not True:
        errors.append('The visual sample requires BGM/SFX on and TTS/subtitles off.')
    event_ids={e['id'] for s in plan['scenes'] for e in s['visual_events']}
    if len(event_ids)!=sum(len(s['visual_events']) for s in plan['scenes']):
        errors.append('Event IDs must remain unique.')
    for scene in plan.get('scenes',[])[2:]:
        main=next((e for e in scene['entities'] if e['id']=='aircraft_main'),None)
        first=next((r for r in scene['routes'] if r['route_id']=='R_SEOUL_TOKYO'),None)
        if not main or main['route_id']!='R_SEOUL_TOKYO' or main['action']!='stop' or not first or first['progress_start']!=1. or first['progress_end']!=1.:
            errors.append(f"{scene['scene_id']}: the first aircraft must stay at its actual Tokyo endpoint")
    response=plan.get('scenes',[{}]*4)[3]
    for entity in response.get('entities',[]):
        if entity['id']=='aircraft_main':continue
        route=next(r for r in response['routes'] if r['route_id']==entity['route_id'])
        if entity.get('phase_offset',0)!=0 or route['progress_start']!=0 or entity['start_time']!=route['start_time']:
            errors.append(f"{entity['id']}: a new aircraft must start at its actual sourced origin")
    return dict(passed=not errors, errors=errors,
                final_scene_is_actual_master_v3_earth=True,
                defaults_or_existing_plans_modified=False,
                assertion_scope='Authored IR, verified GIS, clock/state contracts; actual flat/Earth draw eligibility remains mandatory.')


def build_validation_plan(quality='HIGH'):
    """Return a new plan with the real schema, Retention and mixed-renderer Gate."""
    if quality not in {'FAST','HIGH','CINEMA'}:
        raise ValueError('quality must be FAST, HIGH or CINEMA')
    base=generate_plan(dict(topic='서울에서 도쿄를 거쳐 타이베이로 이동하는 민간 항공 연결',
                            duration=20, style='긴장감 있는 세계 시뮬레이션',
                            quality=quality, tts=False, subtitles=False, bgm=True))
    if not base['gate']['passed']:
        raise ValueError('The existing 20s contract template is blocked: '+json.dumps(base['gate']['errors'],ensure_ascii=False))
    seoul, tokyo, taipei = [resolve_location(name) for name in ('Seoul','Tokyo','Taipei')]
    r1=_route('R_SEOUL_TOKYO',seoul,tokyo,.8,3,0.,.32)
    r2=_route('R_TOKYO_TAIPEI',tokyo,taipei,1.7,3,0.,.9)
    r3=_route('R_SEOUL_TAIPEI',seoul,taipei,.8,3,0.,.9)
    network=[deepcopy(r) for r in (r1,r2,r3)]
    for route in network:route.update(progress_start=1.,progress_end=1.,start_time=0.,end_time=3.)
    midpoint=RouteEngine.spherical_point(r1['points'],.32)
    preview_center=RouteEngine.spherical_point(r2['points'],.55)
    network_pose,overview=RouteEngine.network_overview(network,_camera(taipei['coordinates'],height=1.85,tilt=.4,yaw=.12,bank=.012))
    # Exact shared authored boundary poses, with separate flat projection spans.
    poses=[_camera(seoul['coordinates'],height=.95),_camera(midpoint,height=.75),
           _camera(tokyo['coordinates'],height=.75),_camera(preview_center,height=1.05),
           _camera(overview['focus'],height=1.1,tilt=.35,yaw=.10,bank=.01),network_pose]
    spans=[34.,30.,23.,42.,38.]
    claims=deepcopy(base['story']['claims'])
    claims += [dict(id='FD03',text=f"공개 좌표로 계산한 Seoul -> Taipei 구면 길이는 약 {r3['length_km']:,.0f} km입니다. 비행 시간이나 실제 운항 결과가 아닙니다.",status='FACT',source_ids=r3['source_ids'],scope='derived geometric length; spherical Earth radius 6371.0088 km'),
               dict(id='FC01',text='표시한 KOR/JPN/TWN 윤곽은 보존된 Natural Earth 공개 GIS 원본입니다. 지리 도형 참조이며 정치적 지위에 대한 주장이 아닙니다.',status='FACT',source_ids=['natural_earth_countries'],scope='geographic outline provenance'),
               dict(id='A02',text='도쿄 도착 뒤 타이베이 민간 후속 연결이 잠시 보류되고, 별도 항공기 두 대가 타이베이 연결을 재개한다고 가정합니다. 실제 공항 폐쇄·전쟁·날씨·운항 예측이 아닙니다.',status='ASSUMPTION',source_ids=[],scope='fictional civil connection change'),
               dict(id='M02',text='보류·재배정 가정에 따라 첫 항공기는 도쿄에 정지하고 별도 Tokyo -> Taipei 및 Seoul -> Taipei 연결을 시각화합니다.',status='SIMULATION',source_ids=['natural_earth_places'],assumption_ids=['A01','A02'],scope='fictional visualization only')]
    events=[
        [_event('E001','country_reveal',.3,'KOR',seoul['coordinates'],'FC01','KOREA',role='cause'),
         _event('E002','route_start',.8,r1['route_id'],seoul['coordinates'],'M01','SEOUL / TOKYO',role='cause',cause='E001'),
         _event('E003','entity_departure',1.4,'aircraft_main',seoul['coordinates'],'M01','FIRST CONNECTION',cause='E002'),
         _event('E004','destination_preview',2.4,tokyo['id'],tokyo['coordinates'],'F02','TOKYO',role='hint',cause='E003')],
        [_event('E005','milestone_reveal',.8,r1['route_id'],tokyo['coordinates'],'M01','',cause='E004'),
         _event('E006','country_reveal',2.25,'JPN',tokyo['coordinates'],'FC01','JAPAN',cause='E005')],
        [_event('E007','arrival',.1,tokyo['id'],tokyo['coordinates'],'M01','TOKYO',role='consequence',cause='E006'),
         _event('E008','new_variable',.95,taipei['id'],taipei['coordinates'],'A02','ASSUMPTION · NEXT STOP: TAIPEI',role='variable',cause='E007'),
         _event('E009','route_blocked',1.9,r2['route_id'],tokyo['coordinates'],'A02','ASSUMPTION · CONNECTION ON HOLD',role='response',cause='E008')],
        [_event('E010','route_reroute',.8,r3['route_id'],seoul['coordinates'],'M02','DIRECT LINK: SEOUL / TAIPEI',role='response',cause='E009'),
         _event('E011','network_expand',1.7,r2['route_id'],tokyo['coordinates'],'M02','A SECOND CONNECTION JOINS',role='peak',cause='E010')],
        [_event('E012','final_reveal',1.65,r3['route_id'],taipei['coordinates'],'M02','THREE CITIES · ONE NETWORK',role='payoff',cause='E011',duration=1.3)],
    ]
    route_sets=[
        [r1],
        [{**deepcopy(r1),'start_time':0.,'end_time':3.,'progress_start':.32,'progress_end':1.}],
        [{**deepcopy(r1),'start_time':0.,'end_time':3.,'progress_start':1.,'progress_end':1.},
         {**deepcopy(r2),'start_time':0.,'end_time':3.,'progress_start':0.,'progress_end':0.}],
        [{**deepcopy(r1),'start_time':0.,'end_time':3.,'progress_start':1.,'progress_end':1.},r2,r3],
        [network[0],{**deepcopy(r2),'start_time':0.,'end_time':.85,'progress_start':.9,'progress_end':1.},
         {**deepcopy(r3),'start_time':0.,'end_time':.95,'progress_start':.9,'progress_end':1.}],
    ]
    # Same smoothstep as both renderers; remaining distance is tied to E005's
    # actual Scene-local authored curve clock, not linear global progress.
    local=.8/3.;progress=.32+.68*local*local*(3.-2.*local)
    remaining=r1['length_km']*(1.-progress)
    events[1][0].update(text=f'{remaining:,.0f} km TO TOKYO',description='현재 저작된 곡선 위치에서 다음 도시까지의 구면 경로 거리',value=round(remaining,6),unit='km')
    entities=[[_entity('aircraft_main',r1['route_id'],1.4)],
              [_entity('aircraft_main',r1['route_id'])],
              [_entity('aircraft_main',r1['route_id'],action='stop')],
              [_entity('aircraft_main',r1['route_id'],action='stop'),
               _entity('aircraft_tokyo_support',r2['route_id'],1.7),
               _entity('aircraft_seoul_support',r3['route_id'],.8)],
              [_entity('aircraft_main',r1['route_id'],action='stop'),
               _entity('aircraft_tokyo_support',r2['route_id']),
               _entity('aircraft_seoul_support',r3['route_id'])]]
    # Separate aircraft disappear smoothly as they reach the same destination;
    # the final graphic is the network, not two overlapping stopped models.
    entities[4][1].update(end_time=.85,persistent=False)
    entities[4][2].update(end_time=.95,persistent=False)
    presets=['FLAT_COUNTRY_FOCUS','FLAT_ROUTE_FOLLOW','FLAT_NEXT_EVENT_PREVIEW','FLAT_MULTI_COUNTRY','FINAL_REVEAL']
    types=['COUNTRY_FOCUS','ROUTE_CHASE','CITY_FOCUS','NETWORK','FINAL_OVERVIEW']
    directing=['HOOK_REVEAL','ROUTE_CHASE','NEW_VARIABLE','COUNTER_RESPONSE','FINAL_REVEAL']
    roles=['hook','progression','variable','response','payoff']
    narrations=['다음 목적지가 바뀐다면?','첫 연결이 도쿄로 향합니다.','다음 목적지가 바뀐다고 가정합니다.','새 민간 항로가 연결됩니다.','세 도시의 연결망이 보입니다.']
    scenes=[];previous=None
    for index in range(5):
        scene=deepcopy(base['scenes'][min(index,len(base['scenes'])-1)])
        place=(seoul,tokyo,tokyo,taipei,taipei)[index]
        light='GEOGRAPHY_READABILITY' if index<4 else 'CINEMATIC_NIGHT'
        scene.update(scene_id=f'S{index+1:03}',start_time=index*3.,duration=3.,scene_type=types[index],
                     render_mode='FLAT_MAP_PREMIUM' if index<4 else 'MASTER_V3_EARTH',
                     hook=HOOK if index==0 else '',narration=narrations[index],location=place['name'],
                     coordinates=deepcopy(place['coordinates']),geographic_targets=[p['id'] for p in (seoul,tokyo,taipei)],
                     camera_preset=presets[index],camera_start=deepcopy(poses[index]),camera_end=deepcopy(poses[index+1]),
                     camera_speed=CAMERA_PRESETS[presets[index]]['speed'],camera_easing='smootherstep',
                     lighting_preset=light,routes=deepcopy(route_sets[index]),entities=deepcopy(entities[index]),
                     entity_actions=[dict(entity_id=e['id'],action=e['action'],time=0.,route_id=e['route_id']) for e in entities[index]],
                     visual_events=deepcopy(events[index]),sound_events=[_sound(event) for event in events[index]],
                     effects=[],labels=[_label(place)],music_energy=[.8,.45,.6,.85,1.][index],
                     transition_in='camera_continuity',transition_out='camera_continuity',
                     claim_ids=[c['id'] for c in claims],fact_status='SIMULATION',render_quality=quality,
                     directing_presets=[directing[index]],role=roles[index],description=narrations[index],
                     timeline_position=index/5.,motion_start=0.,narration_event_ids=[e['id'] for e in events[index]],
                     render_time_offset=index*3.)
        if index==0:scene['sound_events'].insert(0,dict(id='A_OPEN',kind='cinematic_hit',time=0.,duration=1.,visual_event_id=None,gain_db=-13))
        if index<4:
            country=('KOR','JPN','JPN','TWN')[index]
            scene['flat_map']=dict(projection='LOCAL_MERCATOR',
                center=dict(lon=poses[index]['lon'],lat=poses[index]['lat']),span_degrees=spans[index],
                camera_start=_flat_camera(poses[index],spans[index]),camera_end=_flat_camera(poses[index+1],spans[index+1]),
                country_highlights=[dict(country=country,source_id='natural_earth_countries',start_time=.05,end_time=3.,color='#c18b4b',opacity=.24)],
                focus=[dict(target_id=place['id'],coordinates=deepcopy(place['coordinates']),start_time=0.,end_time=3.,radius_degrees=5.,strength=.18)],
                terrain_texture=dict(url='/static/flat_assets/cache/terrain_99a6ebfafb2f78a29cea244d9a20cf732c619c4c97db868bf98255f34ec26624.png',bounds=[104.00000000005679,-8.000000000019583,152.0000000000664,64.99999999999501]),
                transition='FLAT_TO_EARTH' if index==3 else 'NONE',transition_duration=.65)
        if index==2:
            scene['flat_map']['next_event']=dict(event_id='E008',coordinates=deepcopy(taipei['coordinates']),event_time=.95,lead_time=.65,strength=.35)
            # One authored focus at a time: arrival -> new destination -> the
            # held connection's actual origin. VFX/coordinates use that same
            # event clock instead of retaining Tokyo focus under a Taipei cue.
            scene['flat_map']['focus']=[
                dict(target_id=tokyo['id'],coordinates=deepcopy(tokyo['coordinates']),start_time=0.,end_time=.95,radius_degrees=5.,strength=.18),
                dict(target_id=taipei['id'],coordinates=deepcopy(taipei['coordinates']),start_time=.95,end_time=1.9,radius_degrees=5.,strength=.18),
                dict(target_id=tokyo['id'],coordinates=deepcopy(tokyo['coordinates']),start_time=1.9,end_time=3.,radius_degrees=5.,strength=.18)]
            scene['flat_map']['country_highlights']=[
                dict(country=country,source_id='natural_earth_countries',start_time=start,end_time=end,color='#c18b4b',opacity=.24)
                for country,start,end in [('JPN',.05,.95),('TWN',.95,1.9),('JPN',1.9,3.)]]
            scene['labels']=[_label(tokyo,0.,2.65),_label(taipei,.95)]
            scene['effects']=[dict(kind='RADAR',coordinates=deepcopy(taipei['coordinates']),time=.95,duration=.7,strength=.16),
                              dict(kind='WARNING',coordinates=deepcopy(tokyo['coordinates']),time=1.9,duration=.8,strength=.24)]
        if index==3:
            scene['labels']=[_label(tokyo),_label(taipei),_label(seoul)]
            scene['entity_actions'] += [dict(entity_id='aircraft_seoul_support',action='reroute',time=.8,route_id=r3['route_id'])]
            scene['effects']=[dict(kind='ROUTE_REROUTE',route_id=r3['route_id'],coordinates=deepcopy(seoul['coordinates']),time=.8,duration=.8,strength=.25)]
        if index==3:
            scene['transition_out']='FLAT_TO_EARTH'
            scene['map_transition']=dict(duration=.65)
        if index==4:
            scene['labels']=[_label(place,0.,3.) for place in (seoul,tokyo,taipei)]
            scene['transition_in']='FLAT_TO_EARTH'
            scene['map_transition']=dict(duration=.65)
        entry=deepcopy(previous) if previous else _state(poses[0],0.,[],[],lighting=light,countries=[])
        scene['entry_state']=entry
        scene['exit_state']=_state(poses[index+1],(index+1)*3.,scene['routes'],scene['entities'],lighting=light,countries=['KOR','JPN']+(['TWN'] if index>=2 else []))
        scenes.append(scene);previous=scene['exit_state']
    plan=deepcopy(base)
    for key in ('gate','approval','plan_hash','render_context'):plan.pop(key,None)
    plan.update(duration=15.,scenes=scenes,project_id='',version='v001')
    plan['request'].update(topic=TOPIC,duration=15.,tts=False,subtitles=False,bgm=True)
    plan['options'].update(tts=False,subtitles=False,bgm=True,quality=quality)
    plan['story'].update(hook=HOOK,claims=claims,pattern='civil-connection-reassignment',
                         conclusion='가정된 재배정 뒤 세 도시가 세 개의 검증된 좌표 기반 항로로 연결됩니다.',
                         beats=[dict(scene_id=s['scene_id'],role=s['role'],cause=scenes[i-1]['scene_id'] if i else None,summary=s['description']) for i,s in enumerate(scenes)],
                         limitations=['15초는 연출 시간이며 실제 비행시간이 아닙니다.','목적지 변경과 연결 종료는 민간 이동을 위한 가정이며 실제 공항 폐쇄를 주장하지 않습니다.','지도 윤곽은 Natural Earth GIS의 지리 참조이며 정치적 지위에 대한 주장이 아닙니다.'])
    plan['metadata']=dict(flat_map_preview=True,sample_builder='tools/build_flat_validation_sample.py',
        sample_scope='Additive 15-second explicit mixed flat/Earth visual validation; not a planner default or a 75-second final render.',
        coordinate_claim_targets={'F01':seoul['id'],'F02':tokyo['id'],'F03':taipei['id']},
        final_overview=overview,
        camera_provenance=[dict(boundary_time=i*3.,method='Verified city coordinates or GIS great-circle/network camera focus; not a new GIS place',source_ids=['natural_earth_places']) for i in range(6)],
        route_metric=dict(event_id='E005',scene_id='S002',route_id=r1['route_id'],scene_local_time=.8,actual_progress=progress,remaining_km=remaining,method='Exact Scene-local smoothstep; spherical radius 6371.0088 km'),
        sample_contract=validate_sample_contract(plan))
    plan['render_context']=dict(lighting_anchor=deepcopy(seoul['coordinates']),hero_anchor=deepcopy(taipei['coordinates']))
    plan['gate']=validate_plan(plan)
    if not plan['metadata']['sample_contract']['passed']:
        plan['gate']['passed']=False
        plan['gate']['errors'] += [dict(code='FLAT_SAMPLE_CONTRACT',message=x) for x in plan['metadata']['sample_contract']['errors']]
    return plan


def explanation(plan):
    return '\n'.join([
        '# Premium flat / MASTER V3 Earth — 15s validation sample','',
        'This is a new opt-in sample. No existing plan, result, cache, engine default or 75s job is changed.',
        'The 20s planner is reused only for its validated sources, claims and Scene contract; five new 3s Scenes are authored.',
        'The first four Scenes explicitly use FLAT_MAP_PREMIUM. The final Scene actually uses MASTER_V3_EARTH.',
        'GIS: Natural Earth Seoul/Tokyo/Taipei coordinates and KOR/JPN/TWN outlines. No Osaka coordinate is fabricated.',
        'Scenario: a fictional civil onward-connection reassignment after Tokyo; no actual airport closure, war, weather or flight forecast.',
        'Audio: BGM and timestamped effects on. TTS and subtitles off. Output quality: '+plan['options']['quality']+'.','',
        '| Time | Visible progression |','|---|---|',
        '| 0–3 | Korea outline, Seoul, authored route start, aircraft departure, Tokyo hint. |',
        '| 3–6 | Seoul–Tokyo chase; exact remaining geometric distance; Japan enters focus. |',
        '| 6–9 | Tokyo arrival; camera previews Taipei before the hypothetical next stop; the planned onward connection is held. |',
        '| 9–12 | The first aircraft stays at Tokyo. Two separate aircraft depart at their sourced Seoul/Tokyo origins; the Seoul–Taipei direct response and Tokyo–Taipei connection form two real new edges. |',
        '| 12–15 | Preserved MASTER V3 Earth renderer; actual three-edge network and final reward. |','',
        'Planning Gate: '+('PASS' if plan['gate']['passed'] else 'BLOCKED — no render or approval is requested.'),
        'Schema/provenance/Retention/real mixed-renderer semantic visibility remain mandatory before pixels. This plan is not proof of final raster quality.',
        'The builder never renders or approves. With --project-root it creates only a new ProjectStore project after a passing Gate. Review its Scene Plan and approve through the existing UI/API before Root starts the sample render.','',
    ])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='Exclusive new JSON path; existing files are never overwritten.')
    parser.add_argument('--quality',choices=('FAST','HIGH','CINEMA'),default='HIGH')
    parser.add_argument('--project-root',type=Path,help='Optional existing ProjectStore root; creates a new UUID project only after the Gate passes.')
    args=parser.parse_args(argv)
    md=args.output.with_suffix('.md')
    if args.output.exists() or md.exists():parser.error('Output JSON/MD already exists. Choose a new immutable sample path.')
    plan=build_validation_plan(args.quality)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as out:json.dump(plan,out,ensure_ascii=False,indent=2);out.write('\n')
    with md.open('x',encoding='utf-8') as out:out.write(explanation(plan))
    summary=dict(plan_path=str(args.output.resolve()),plan_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
                 explanation_path=str(md.resolve()),passed=plan['gate']['passed'],errors=plan['gate']['errors'],
                 approval_created=False,render_started=False)
    if plan['gate']['passed'] and args.project_root:
        created=ProjectStore(args.project_root).create(deepcopy(plan['request']),deepcopy(plan))
        summary.update(project_id=created['project']['id'],version=created['version'],plan_hash=created['plan']['plan_hash'],
                       stored_plan_gate_passed=created['plan']['gate']['passed'])
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if plan['gate']['passed'] else 2


if __name__=='__main__':
    raise SystemExit(main())
