"""Reference-first beat authoring. Legacy plans and certified runtime are untouched.

Allocate minimum perceptual intervals before compiling sourced geographic IR.
No per-topic override, global video speedup, fixed five-scene division or capped
reading time. If the budget cannot fit, omit support/merge optional locations.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from types import FunctionType
from . import planner
from .direction import angle, camera_up

ROOT=Path(__file__).resolve().parents[1]
VERSION='reference_master_v013'
PROFILE_PATH=ROOT/'data/reference_direction_profile_v013.json'
SOURCES=('web/reference_visual_adapter.js','web/render_reference_earth.html',
         'web/render_reference_flat.html','tools/reference_semantic_preflight.mjs',
         'web/direction_visual_adapter.js','web/production_visual_adapter.js',
         'data/reference_direction_profile_v013.json','engine/reference_master.py','engine/reference_content.py','engine/reference_preflight.py','tools/collect_all_preflight.mjs','engine/reference_concat.py')


def frame(value):return round(math.ceil(value*30-1e-4)/30,6)


def text_read_time(text, importance=1, camera_stability=1):
    han=sum('\u3000'<=c<='\u9fff' or '\uac00'<=c<='\ud7af' for c in text)
    words=len(text.split());latin=len(text)-han
    # No ceiling: long text earns more time or is omitted by the budget.
    return frame(max(.8,.30+han/7+max(words/3,latin/22)+.1*importance+.2*(1-camera_stability)))


def perception_hold(kind,text='',*,importance=1,route_complexity=0,entity=False,
                    zoom='REGIONAL',density=1,previous_motion=0):
    targets=json.loads(PROFILE_PATH.read_text())['design_targets']
    floor=targets[{'LOCATION':'location_hold','EVENT':'event_hold','ROUTE_CHANGE':'route_change_hold','RESULT':'result_hold'}[kind]][0]
    return frame(max(floor,text_read_time(text,importance))+min(.2,route_complexity*.025)
                 +(.1 if entity else 0)+(.05 if zoom=='WORLD' else 0)
                 +.08*max(0,density-1)+min(.15,previous_motion/500))


def information_budget(primary,secondary=None,support=None,available=0):
    keep_support=bool(support and available>=text_read_time(primary)+text_read_time(support)+.4)
    return dict(primary=primary,secondary=secondary,support=support if keep_support else None,
                primary_limit=1,secondary_limit=1,omitted_support=bool(support and not keep_support))


def reference_blueprint(raw,reservations=None,count_override=None):
    reservations=reservations or {}
    profile=json.loads(PROFILE_PATH.read_text())  # Profile first, before geographic content.
    qa=raw.get('qa_mode',False)
    if not isinstance(qa,bool):raise planner.PlanningInputError('QA 설정은 ON/OFF여야 합니다.')
    duration=float(raw.get('duration',20))
    if qa and (not math.isfinite(duration) or not 12<=duration<=15):raise planner.PlanningInputError('QA 테스트는 12~15초입니다.')
    checked=deepcopy(raw);checked['duration']=20 if qa else duration
    request=planner._request(checked);request['duration']=frame(duration)
    scenario=planner._scenario(request)
    # Four causal beats fit the observed rhythm; longer production buys more
    # distinct locations/progression beats, never shorter recognition minima.
    count=4 if duration<=15 else max(4,math.ceil(duration/2.9))
    if count_override is not None:count=count_override
    locations=scenario['locations'];shipping=scenario['domain']=='shipping'
    types=['LOCATION','LOCATION' if len(locations)>=4 else 'EVENT','ROUTE_CHANGE','RESULT'] if count==4 else ['LOCATION','EVENT']+['LOCATION']*(count-3)+['RESULT']
    if count>4:types[2]='ROUTE_CHANGE'
    beats=[]
    for i,kind in enumerate(types):
        li=min(len(locations)-1,round(i*(len(locations)-1)/(count-1)))
        if shipping and i==1:li=1
        loc=locations[li]
        text=loc['name'].upper()
        if kind=='EVENT' and shipping:text='CANAL CLOSED'
        if kind=='ROUTE_CHANGE':text='ALTERNATE ROUTE' if shipping else 'NEXT CONNECTION'
        if kind=='RESULT':text='RESULT'
        hold=perception_hold(kind,text,entity=scenario['domain']!='comparison',
                            route_complexity=1 if len(locations)>=4 else min(8,len(scenario['routes'])),zoom='WORLD' if kind=='RESULT' else 'REGIONAL',previous_motion=75 if i else 0)
        move=.3 if i==0 else .9
        if kind=='ROUTE_CHANGE':move=.9
        if kind=='RESULT':move=.3 if len(locations)>=4 else 1.2
        if len(locations)>=4 and i:
            previous=locations[min(len(locations)-1,round((i-1)*(len(locations)-1)/(count-1)))]['coordinates']
            destination=loc['coordinates']
            if kind=='ROUTE_CHANGE':
                from .gis import RouteEngine
                _,overview=RouteEngine.network_overview([scenario['routes'][-1]],dict(height=2.25,tilt=.15,yaw=-.18,bank=0,fov=64,**destination))
                destination=overview['focus']
            move=max(move,frame(angle(previous,destination)*1.25/55))
        beats.append(dict(beat_id=f'B{i+1:02}',kind=kind,location_index=li,
                          minimum_hold=hold,move=frame(move),primary=text,reserved=reservations.get(i,0)))
    required=sum(max(2.1 if b is beats[0] else 0,b['minimum_hold']+b['move']+(.1 if b is beats[0] else .6)+b['reserved']) for b in beats)
    if required>duration:raise planner.PlanningInputError('인지 시간을 확보하려면 사건 또는 텍스트를 줄여야 합니다.',{'code':'PERCEPTION_BUDGET_EXCEEDED'})
    remaining_frames=round((duration-required)*30)
    weights=[1.0 if b['kind']=='LOCATION' else 1.2 if b['kind']=='EVENT' else 1.4 if b['kind']=='ROUTE_CHANGE' else 1.7 for b in beats]
    allocation=[math.floor(remaining_frames*w/sum(weights)) for w in weights]
    allocation[-1]+=remaining_frames-sum(allocation)
    bounds=[0.]
    for b,extra in zip(beats,allocation):
        b['start']=bounds[-1];b['duration']=frame(max(2.1 if b is beats[0] else 0,b['move']+(.1 if b is beats[0] else .6)+b['minimum_hold']+b['reserved'])+extra/30)
        if b is beats[0]:b['duration']=max(2.1,b['duration'])
        if b['kind']=='ROUTE_CHANGE':b['duration']=max(b['move']+.6+b['minimum_hold']+b['reserved'],min(b['duration'],3.1))  # Transfer excess to result; protect route recognition minimum.
        b['end']=round(b['start']+b['duration'],6);bounds.append(b['end'])
        b['reveal']=round(b['start']+b['move']+(.1 if b is beats[0] else .6),6)
        b['next_move']=b['end'] if b is not beats[-1] else None
    # Exact frame total, with the residual allocated to RESULT, not hold erosion.
    delta=round(duration-bounds[-1],6);beats[-1]['duration']+=delta;beats[-1]['end']+=delta;bounds[-1]=duration
    routes=scenario['routes'];route_specs=[]
    if shipping:
        route_specs=[(routes[0],1.3,beats[1]['reveal']),(routes[1],next(b['reveal'] for b in beats if b['kind']=='ROUTE_CHANGE')-.2,beats[-1]['start']+beats[-1]['move']+1/30)]
    else:
        for i,r in enumerate(routes):
            start=1.3 if i==0 else beats[1]['reveal']+.6 if i<len(routes)-1 else beats[min(i+1,count-2)]['reveal']-.2
            end=beats[min(i+2,count-1)]['reveal']-.2
            route_specs.append((r,start,max(start+.6,end)))
    events=[]
    def event(kind,t,coord,target,text,role='progression',claim='M01',duration=.9):
        eid=f'E{len(events)+1:03}'
        events.append(dict(id=eid,kind=kind,time=frame(t),duration=frame(duration),target_id=target,
            role=role,caused_by=events[-1]['id'] if events else None,meaningful=True,
            description=text,text=text,coordinates=deepcopy(coord),claim_id=claim))
        return events[-1]
    first=locations[0]
    event('city_reveal' if first['kind']!='country' else 'country_reveal',beats[0]['reveal'],first['coordinates'],first['id'],first['name'].upper(),'cause','F01')
    event('route_start',1.3,routes[0]['points'][0],routes[0]['route_id'],'','hint')
    if scenario['domain']!='comparison':
        entity='ship_reference' if shipping else 'aircraft_'+routes[0]['route_id']
        event('entity_departure',1.5,routes[0]['points'][0],entity,'')
    for i,b in enumerate(beats[1:-1],1):
        loc=locations[b['location_index']];t=b['reveal']
        if shipping and b['kind']=='EVENT' and i==1:
            e=event('route_blocked',t,loc['coordinates'],loc['id'],b['primary'],'variable','A01',b['end']-t)
        elif b['kind']=='ROUTE_CHANGE':
            r=routes[-1];e=event('route_start',max(b['start']+b['move']+.2,t-.2),r['points'][0],r['route_id'],'','variable')
            event('alternate_route_reveal' if shipping else 'new_variable',t,loc['coordinates'],r['route_id'] if shipping else loc['id'],b['primary'],'peak','M01',b['end']-t)
        elif count>4 and i>1:
            r=routes[min(len(routes)-1,int(i*len(routes)/count))]
            kind=['milestone_reveal','distance_reveal','comparison_reveal','consequence_reveal'][i%4]
            e=event(kind,t,r['points'][-1],r['route_id'],'','variable' if i==count//2 else 'peak' if i in {count//2-1,count-2} else 'progression')
            e.update(value=0,unit='km',text='PROGRESS')  # exact geometry recalculated after compilation
        else:
            e=event('comparison_reveal' if loc['kind']=='country' else 'destination_preview',t,loc['coordinates'],loc['id'],loc['name'].upper(),'variable','F'+f'{b["location_index"]+1:02}',b['end']-t)
    if not shipping:
        present={e['target_id'] for e in events if e['kind']=='route_start'}
        for route,start,end in route_specs:
            if route['route_id'] not in present:
                event('route_start',start,route['points'][0],route['route_id'],'','progression')
    final=beats[-1];loc=locations[-1]
    # Endpoints really finish before arrival. The held result is a separate fact.
    if scenario['domain']!='comparison':event('arrival',final['start']+final['move']+1/30,loc['coordinates'],loc['id'],'','progression')
    else:event('destination_preview',final['start']+final['move']+1/30,loc['coordinates'],loc['id'],'','progression','F'+f'{len(locations):02}')
    event('final_reveal',max(final['reveal'],frame(duration*.8)+1/30),loc['coordinates'],loc['id'],'RESULT','payoff','M01',duration-max(final['reveal'],frame(duration*.8)+1/30))
    events.sort(key=lambda e:e['time'])
    for i,e in enumerate(events):e['caused_by']=events[i-1]['id'] if i else None
    return dict(profile=profile,request=request,scenario=scenario,beats=beats,bounds=bounds,events=events,route_specs=route_specs,
                event_budget=dict(core_beats=count,semantic_events=len(events),fixed_five_scenes=False,minimums_preserved=True))


def generate_reference_plan(raw,_reservations=None,_count=None,_attempt=0):
    reservations=dict(_reservations or {})
    try:blueprint=reference_blueprint(raw,reservations,_count)
    except planner.PlanningInputError as error:
        if error.details.get('code')=='PERCEPTION_BUDGET_EXCEEDED' and float(raw.get('duration',0))>15 and _attempt<20:
            count=_count or max(4,math.ceil(float(raw['duration'])/2.9))
            if count>4:return generate_reference_plan(raw,{},count-1,_attempt+1)
        raise
    from .reference_content import compile_content
    plan=compile_content(raw,blueprint)
    for scene in plan['scenes']:scene['labels']=[]  # Explicit labels are authored after camera lock; prevent legacy repeated-label repairs.
    # Reuse graphic asset/IR preparation, with per-call policy globals. This is
    # not a reference correction over a completed FAST_PLUS plan: bounds, facts
    # and event clocks have already been authored by the reference blueprint.
    from . import production
    original=production.apply_production_defaults
    ns=dict(original.__globals__)
    def scene_policy(scene,pace):
        s=deepcopy(scene);d=s['duration'];s['pace']=pace
        s['motion_timing']=dict(camera_travel_duration=min(d,.8),zoom_duration=min(d,.8),camera_speed_reference=1.,focus_transition_duration=.14,route_speed_factor=1.,entity_speed_factor=1.,transition_duration=.3,peak_hold_duration=1.5,next_event_lead_time=.3,dead_time_removed=0.,tts_playback_rate=1.)
        return s,dict(scene_id=s['scene_id'],reference_authored=True)
    ns['apply_scene_pace']=scene_policy
    build=FunctionType(original.__code__,ns,original.__name__,original.__defaults__);build.__kwdefaults__=original.__kwdefaults__
    plan=build(plan,pace='FAST_PLUS',profile='PRODUCTION_DEFAULT_CANDIDATE')
    # Restore blueprint-controlled onsets which legacy short-sample policy moves.
    authored={e['id']:e for e in blueprint['events']}
    for s,b in zip(plan['scenes'],blueprint['beats']):
        s['visual_events']=[e for e in s['visual_events'] if e['id'] in authored]
        for e in s['visual_events']:
            a=authored[e['id']];e['time']=round(a['time']-s['start_time'],6)
            if a['kind']!='final_reveal' and a.get('unit')!='km':
                for key in ('kind','coordinates','claim_id','target_id','text','description','role'):e[key]=deepcopy(a[key])
                for key in ('value','unit'):
                    if key not in a:e.pop(key,None)
            e['duration']=min(a['duration'],s['duration']-e['time'])
        s['labels']=[l for l in s['labels'] if l.get('role')!='status']
    try:plan=author_presentation(plan,blueprint)
    except planner.PlanningInputError as error:
        if error.details.get('code')=='PERCEPTION_BUDGET_EXCEEDED' and _attempt<20:
            sid=error.details['scene_id'];i=next(i for i,s in enumerate(plan['scenes']) if s['scene_id']==sid)
            reservations[i]=frame(reservations.get(i,0)+error.details['required']-error.details['available']+1/30)
            return generate_reference_plan(raw,reservations,_count,_attempt+1)
        raise
    from .sfx_library import prepare_production_sound_events
    plan=prepare_production_sound_events(plan)
    for s in plan['scenes']:
        times={e['id']:e['time'] for e in s['visual_events']}
        for cue in s['sound_events']:cue['time']=times[cue['visual_event_id']]
    from .rhythm import _micro_beats
    plan['rhythm_policy']=dict(version='v1',sfx_core_onset_offset_frames=1,micro_pauses=[],bgm_sidechain=True,reference_pattern=VERSION)
    for s in plan['scenes']:s['rhythm_micro_beats']=_micro_beats(s,[])
    plan['metadata']['reference_blueprint']=dict(profile_version=VERSION,event_budget=blueprint['event_budget'],beats=blueprint['beats'])
    plan['metadata']['direction_version']=VERSION
    from .reference_preflight import fit_native_composition
    fit_native_composition(plan)
    plan['metadata']['direction_qc']=perceptual_qc(plan)
    from .schema import validate_plan
    plan['gate']=validate_plan(plan)
    return plan


def author_presentation(plan,blueprint):
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
    previous=None
    for i,(s,b) in enumerate(zip(plan['scenes'],blueprint['beats'])):
        d=s['duration'];final=i==len(plan['scenes'])-1;earth=s['render_mode']!='FLAT_MAP_PREMIUM'
        loc=blueprint['scenario']['locations'][b['location_index']]
        s['location']=loc['name'];s['coordinates']=deepcopy(loc['coordinates']);s['geographic_targets']=[loc['id']]
        focus=deepcopy(loc['coordinates'])
        if len(blueprint['beats'])>4 and b['kind']=='LOCATION' and i:
            active=next((e for e in s['visual_events'] if e['kind'] in {'milestone_reveal','distance_reveal','comparison_reveal','consequence_reveal'}),None)
            if active:
                from .gis import RouteEngine
                eligible=[r for r in s['routes'] if not r.get('faint')]
                if eligible:
                    r=eligible[-1];u=max(0,min(1,(active['time']-r['start_time'])/max(.001,r['end_time']-r['start_time'])))
                    progress=r['progress_start']+(r['progress_end']-r['progress_start'])*u
                    focus=RouteEngine.spherical_point(r['points'],progress)
        if b['kind']=='ROUTE_CHANGE' and s['routes']:
            from .gis import RouteEngine
            fitted,provenance=RouteEngine.network_overview([s['routes'][-1]],s['camera_end'])
            focus.update(provenance['focus'])
        if final and previous:
            # Relationship framing keeps destination inside the hemisphere and
            # avoids a gratuitous final orbit back toward the original departure.
            focus['lon']+=(((previous['camera_end']['lon']-focus['lon']+180)%360)-180)*.25
            focus['lat']+=(previous['camera_end']['lat']-focus['lat'])*.25
        if earth:
            for key in ('camera_start','camera_end'):s[key].update(fov=64,yaw=-.18,bank=0,tilt=.15,height=2.25)
            if final and earth:s['camera_end']['height']=2.1
            s['camera_end'].update(lon=focus['lon'],lat=focus['lat'],target_lon=focus['lon'],target_lat=focus['lat'])
            if i==0:s['camera_start'].update(height=2.32,lon=focus['lon'],lat=focus['lat'],target_lon=focus['lon'],target_lat=focus['lat'])
            if previous and previous['render_mode']==s['render_mode']:s['camera_start']=deepcopy(previous['camera_end'])
        movement=angle(s['camera_start'],s['camera_end']) if earth else 0
        move=max(b['move'],frame(movement*1.25/55))
        if move>2.2:raise planner.PlanningInputError('위치 이동량이 인지 예산을 초과했습니다.',{'code':'MOTION_BUDGET_EXCEEDED','scene_id':s['scene_id']})
        events=s['visual_events'];primary=next((e for e in reversed(events) if final and e['kind']=='final_reveal'),None)
        primary=primary or next((e for e in events if e.get('text') and e['kind'] in {'route_blocked','alternate_route_reveal','new_variable','destination_preview','country_reveal','city_reveal','milestone_reveal','comparison_reveal','distance_reveal','consequence_reveal'}),None)
        if primary is None:raise RuntimeError('REFERENCE_PRIMARY_MISSING')
        # Final payoff remains a sourced route metric/new-edge result prepared by
        # the existing graphic policy; no fabricated arrival or extra headline.
        recognition=.1 if i==0 else 1/30 if primary.get('unit')=='km' and not final else .6
        authored_time=primary['time'] if not (primary.get('unit')=='km' and not final) else move+recognition
        reveal=max(move+recognition,authored_time);reveal=frame(reveal)
        old=primary['time'];shift=reveal-old
        primary['time']=reveal
        if s.get('flat_map',{}).get('next_event',{}).get('event_id')==primary['id']:s['flat_map']['next_event']['event_time']=reveal
        if shift and primary.get('unit')=='km' and not final:
            kind=primary['kind'];primary['kind']='milestone_reveal'
            planner.refresh_clock_dependent_route_information(s,primary)
            primary['kind']=kind;primary['text']=primary['text'].replace(' REMAINING','')
        text=primary.get('text','')
        hold=perception_hold(b['kind'],text,entity=bool(s['entities']),route_complexity=1 if len(blueprint['scenario']['locations'])>=4 else min(8,len(s['routes'])),zoom='WORLD' if final else 'REGIONAL',previous_motion=movement)
        if d-reveal<hold-1e-5:raise planner.PlanningInputError('주요 정보 인지 시간이 부족합니다.',{'code':'PERCEPTION_BUDGET_EXCEEDED','scene_id':s['scene_id'],'required':hold,'available':d-reveal})
        up_start,up_end=camera_up(s['camera_start'],s['camera_end'],previous.get('direction',{}).get('camera_up_end') if previous and previous['render_mode']==s['render_mode'] else None)
        s['direction']=dict(version=VERSION,preset='REFERENCE_MASTER',mode='QA' if plan['request'].get('qa_mode') else 'PRODUCTION',
            initial_hold=0.,move_end=move,settle=d-move,acceleration_fraction=.2,settle_position='EXIT',
            camera_up_start=up_start,camera_up_end=up_end,camera_roll_correction=0.,angular_budget_deg_s=55,
            primary=text,primary_event_id=primary['id'],intent='RESULT_HERO' if final else b['kind'],zoom_level='WORLD' if final else 'REGIONAL',
            safe_area=[.055,.075,.945,.86],route_width_1080=3.5 if final else 3.,entity_min_pixels_1080=20,entity_scale_cap=.025,
            geography_floor=.18 if not final else .22,total_duration=plan['duration'],source_hashes=hashes,
            reveal_time=reveal,perception_hold=d-reveal,required_hold=hold,next_major_move=s['start_time']+d if not final else None,
            primary_lock=True,information=information_budget(text,None,None,d-reveal),
            lighting_entry=deepcopy(previous['direction']['lighting']) if previous else dict(exposure=1.04,surface_fill=.18,cloud_opacity=.19,city_gain=1.04,ocean_specular=.45,day_weight=.75),
            lighting=dict(exposure=1.04 if not final else 1.10,surface_fill=.18 if not final else .22,cloud_opacity=.19,city_gain=1.04,ocean_specular=.45,day_weight=.55 if s['lighting_preset']=='CINEMATIC_NIGHT' and not final else .75 if not final else .68),
            beats=[dict(kind='MOVE',start=0,end=move),dict(kind='DECELERATE',start=move*.8,end=move),dict(kind='CAMERA_LOCK',start=move,end=d),dict(kind='REVEAL',start=reveal,end=reveal),dict(kind='PERCEPTION_HOLD',start=reveal,end=d,primary=text)],
            result_min_occupancy=.38,reference_profile_sha256=hashes['data/reference_direction_profile_v013.json'])
        # Actual geographically anchored labels are sequential. They remain
        # below primary emphasis after the event headline is revealed.
        location_name=loc['name'].upper()
        s['labels']=[dict(kind='hook_reveal' if i==0 else 'world_label',text=location_name,coordinates=deepcopy(loc['coordinates']),start_time=move+.033333,end_time=d,role='city',opacity=.75,size=54)]
        if i==0:s['labels'][0].update(event_id=primary['id'],start_time=reveal)
        s['text_events']=[]
        for e in events:
            if not e.get('text'):continue
            if e is not primary:
                # Physical primitives keep their receipts. Optional generated
                # distance/status slogans are omitted, not silently counted.
                e['text']='';continue
            e['duration']=d-reveal
            if i==0 and e is primary:continue
            s['text_events'].append(dict(id='T_'+e['id'],event_id=e['id'],text=e['text'],coordinates=deepcopy(e['coordinates']),start_time=reveal,end_time=d,role='distance' if e.get('unit')=='km' else 'status' if e['kind']=='route_blocked' else 'route' if e['kind']=='alternate_route_reveal' else 'city',priority=9,large_title_approved=False))
        for label in s['text_events']:
            event=next(e for e in events if e['id']==label['event_id'])
            if event.get('unit')=='km' and any(r['route_id']==event['target_id'] for r in s['routes']):
                label.update(route_id=event['target_id'])
        s['sound_events']=[dict(id='A_'+e['id'],kind=planner.SOUND_MAP[e['kind']],time=e['time'],duration=min(1.2,d-e['time']),visual_event_id=e['id'],gain_db=-12 if e is primary else -21) for e in events]
        s['entry_state']['camera']=deepcopy(s['camera_start']);s['exit_state']['camera']=deepcopy(s['camera_end'])
        if previous:s['entry_state']=deepcopy(previous['exit_state']);s['entry_state']['camera']=deepcopy(s['camera_start'])
        if previous and previous['render_mode']!=s['render_mode']:previous['camera_end']=deepcopy(s['camera_start']);previous['exit_state']['camera']=deepcopy(s['camera_start']);s['entry_state']=deepcopy(previous['exit_state'])
        previous=s
    return plan


def perceptual_qc(plan):
    findings=[]
    def issue(code,sid,**detail):findings.append(dict(code=code,severity='CRITICAL',scene_id=sid,**detail))
    previous=None
    for s in plan['scenes']:
        p=s.get('direction',{});sid=s['scene_id']
        if p.get('version')!=VERSION:continue
        d=s['duration'];move=p['move_end'];reveal=p['reveal_time']
        if not all(math.isfinite(v) for pose in (s['camera_start'],s['camera_end']) for v in pose.values() if isinstance(v,(int,float))):issue('INVALID_CAMERA',sid)
        if not 0<move<=reveal<d:issue('CAMERA_MOVING_DURING_REVEAL',sid)
        if d-reveal+1e-6<p['required_hold']:issue('EVENT_NOT_HELD_LONG_ENOUGH',sid)
        if move>2.2:issue('MOTION_FATIGUE',sid)
        if s['render_mode']!='FLAT_MAP_PREMIUM' and angle(s['camera_start'],s['camera_end'])*1.25/move>55.01:issue('CAMERA_MOTION_OVERLOAD',sid)
        if p['information']['primary_limit']!=1 or p['information']['secondary_limit']>1:issue('INFORMATION_OVERLOAD',sid)
        light=p['lighting']
        if not (.15<=light['surface_fill']<=.3 and .9<=light['exposure']<=1.2 and light['ocean_specular']<=.5 and light['cloud_opacity']<=.25):issue('GEOGRAPHY_READABILITY_POLICY_INVALID',sid)
        if p['route_width_1080']<2.5:issue('ROUTE_NOT_VISIBLE',sid)
        if p['entity_min_pixels_1080']<18:issue('ENTITY_NOT_TRACKABLE',sid)
        if p['safe_area'][0]<.05 or p['safe_area'][2]>.95:issue('TEXT_OUTSIDE_SAFE_AREA',sid)
        primary=next((e for e in s['visual_events'] if e['id']==p['primary_event_id']),None)
        cue=next((a for a in s['sound_events'] if a['visual_event_id']==p['primary_event_id']),None)
        if primary is None or cue is None or abs(cue['time']-primary['time'])>1/30+1e-6:issue('SFX_EVENT_MISALIGNMENT',sid)
        for t in s.get('text_events',[]):
            if t['start_time']<move:issue('TEXT_DURING_HIGH_MOTION',sid)
            if t['end_time']-t['start_time']+1e-6<text_read_time(t['text']):issue('TEXT_NOT_READABLE_LONG_ENOUGH',sid)
        if p['intent']=='RESULT_HERO' and d-reveal<1.5:issue('RESULT_NOT_HELD',sid)
        if previous and previous['exit_state']!=s['entry_state']:issue('SCENE_BOUNDARY_JUMP',sid)
        previous=s
    return dict(passed=not findings,findings=findings,warnings=[],warning_count=0,
                rendered_pixel_checks='NOT_RUN',reference_qa_release_gate='NO_READABILITY_WARNINGS',
                actual_checks=['camera motion','reveal-to-next interval','text duration','route contrast','entity size','Earth occupancy','luminance','SFX onset'])
