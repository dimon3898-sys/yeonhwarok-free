"""15-second isolated return-to-wide QA; v015 camera is reused without retiming."""
from copy import deepcopy
from pathlib import Path
import hashlib,json
from .single_event_camera import ROOT,generate as generate_single,install_validation
from .frame_grid import canonicalize_plan,validate_frame_plan
PRESET='SINGLE_EVENT_RETURN_TO_WIDE_TEST'
TIMELINE=[('WIDE',0,60),('EVENT_LOCATION',60,90),('ZOOM_IN',90,150),('SETTLE',150,180),('EVENT_REVEAL',180,240),('EVENT_HOLD',240,330),('EVENT_RESOLVED',330,360),('ZOOM_OUT',360,420),('FINAL_WIDE',420,450)]
SOURCES=('engine/return_wide_camera.py','engine/return_wide_qc.py','web/return_wide_camera.js','web/render_return_wide_earth.html','web/single_event_camera.js','tools/collect_all_preflight.mjs')
def timeline():return [dict(state=n,start_frame=a,end_frame=b,frame_count=b-a,start_seconds=a/30,end_seconds=b/30) for n,a,b in TIMELINE]
def validate_camera(plan):
    errors=[];scenes=plan.get('scenes',[])
    if plan.get('duration')!=15 or len(scenes)!=1:errors.append(dict(code='RETURN_WIDE_DURATION_INVALID'))
    else:
        s=scenes[0];c=s.get('return_wide_camera',{})
        if c.get('timeline')!=timeline() or c.get('end_state')!='END':errors.append(dict(code='RETURN_WIDE_TIMELINE_INVALID'))
        if s.get('direction') or s.get('routes') or s.get('entities'):errors.append(dict(code='RETURN_WIDE_NEXT_EVENT_INVALID'))
        a,b=s['camera_start'],c.get('event_camera',{})
        if a['lon']!=b['lon'] or a['lat']!=b['lat'] or (a['height'],a['fov'],b['height'],b['fov'])!=(2.5,64,.2,48) or c.get('final_camera')!=a or s['camera_end']!=a:errors.append(dict(code='RETURN_WIDE_CAMERA_INVALID'))
        if [(e['kind'],e['time']) for e in s['visual_events']]!=[('city_reveal',2),('route_blocked',6),('milestone_reveal',11)]:errors.append(dict(code='RETURN_WIDE_EVENT_SEQUENCE_INVALID'))
        if c.get('source_hashes')!={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}:errors.append(dict(code='RETURN_WIDE_SOURCE_MISMATCH'))
        try:validate_frame_plan(plan)
        except ValueError:errors.append(dict(code='RETURN_WIDE_FRAME_GRID_INVALID'))
    return dict(passed=not errors,errors=errors,warnings=[],scope='isolated return-to-wide QA camera contract')
def generate(raw):
    from . import planner,schema
    if raw.get('qa_mode') is not True or float(raw.get('duration',0))!=15:raise planner.PlanningInputError('Wide 복귀 카메라 테스트는 15초 QA 전용입니다.')
    plan=generate_single({**raw,'duration':12,'direction_profile':'SINGLE_EVENT_CAMERA_TEST'})
    s=plan['scenes'][0];s.pop('single_event_camera');s['duration']=15.;s['description']='Suez single-event return-to-wide camera test'
    close_camera=deepcopy(s['camera_end']);s['camera_end']=deepcopy(s['camera_start'])
    s['exit_state']['camera']=deepcopy(s['camera_start'])
    for label in s['labels']:label['end_time']=15.
    for label in s['text_events']:label['end_time']=11.
    e=deepcopy(s['visual_events'][1]);e.update(id='E003',kind='milestone_reveal',time=11.,duration=4.,text='CANAL OPEN',description='Single-event QA resolved state',role='payoff',caused_by='E002',meaningful=False)
    s['visual_events'].append(e)
    label=deepcopy(s['text_events'][0]);label.update(id='T_E003',event_id='E003',text='CANAL OPEN',start_time=11.,end_time=15.);s['text_events'].append(label)
    s['return_wide_camera']=dict(preset=PRESET,version='v016',timeline=timeline(),end_state='END',event_camera=close_camera,final_camera=deepcopy(s['camera_start']),source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES})
    plan['duration']=15.;plan['request'].update(duration=15,direction_profile=PRESET);plan['metadata']={'camera_test_preset':PRESET}
    canonicalize_plan(plan);install_validation();plan['gate']=schema.validate_plan(plan)
    if not plan['gate']['passed']:raise RuntimeError('RETURN_WIDE_PLAN_INVALID: '+json.dumps(plan['gate']['errors']))
    return plan
