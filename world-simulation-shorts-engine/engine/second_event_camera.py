"""24s camera-only QA: immutable first event, fitted context, second location."""
from copy import deepcopy
import hashlib,json
from .single_event_camera import ROOT,install_validation
from .return_wide_camera import generate as generate_return
from .adaptive_wide import adaptive_wide
from .frame_grid import canonicalize_plan,validate_frame_plan
from .gis import resolve_location
PRESET='SECOND_EVENT_ADAPTIVE_WIDE_TEST'
TIMELINE=[('EVENT1_WIDE',0,60),('EVENT1_LOCATION',60,90),('EVENT1_ZOOM_IN',90,150),('EVENT1_VIEW',150,180),('EVENT1_HOLD',180,330),('EVENT1_RESOLVED',330,360),('ZOOM_OUT',360,420),('ADAPTIVE_WIDE',420,450),('EVENT2_LOCATION',450,495),('EVENT2_ZOOM_IN',495,585),('EVENT2_VIEW',585,615),('EVENT2_HOLD',615,720)]
SOURCES=('engine/second_event_camera.py','engine/adaptive_wide.py','engine/second_event_qc.py','web/second_event_camera.js','web/render_second_event_earth.html','web/single_event_camera.js','web/return_wide_camera.js','tools/collect_all_preflight.mjs')
def timeline():return [dict(state=n,start_frame=a,end_frame=b,frame_count=b-a,start_seconds=a/30,end_seconds=b/30) for n,a,b in TIMELINE]
def hashes():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
def _validate_camera(plan):
    errors=[];scenes=plan.get('scenes',[])
    def fail(code):errors.append(dict(code=code))
    if plan.get('duration')!=24 or len(scenes)!=1:fail('SECOND_EVENT_DURATION_INVALID')
    else:
        s=scenes[0];c=s.get('second_event_camera',{})
        if c.get('preset')!=PRESET or c.get('timeline')!=timeline() or c.get('end_state')!='END':fail('SECOND_EVENT_TIMELINE_INVALID')
        if s.get('direction') or s.get('routes') or s.get('entities'):fail('SECOND_EVENT_FOREIGN_MOTION')
        a=s['camera_start'];b=c.get('event1_camera',{})
        if (a.get('height'),a.get('fov'),b.get('height'),b.get('fov'))!=(2.5,64,.2,48) or any(a.get(k)!=b.get(k) for k in ('lon','lat','yaw','tilt','bank')):fail('EVENT1_CAMERA_CHANGED')
        expected=adaptive_wide(s['coordinates'],c.get('next_coordinates',{}))
        if c.get('adaptive_wide')!=expected or c.get('adaptive_camera')!={**a,**expected['camera'], 'target_lon':expected['camera']['lon'],'target_lat':expected['camera']['lat']}:fail('ADAPTIVE_WIDE_INVALID')
        close=c.get('event2_camera',{});coord=c.get('next_coordinates',{})
        if close.get('height')!=.2 or close.get('fov')!=48 or close.get('lon')!=coord.get('lon') or close.get('lat')!=coord.get('lat') or s.get('camera_end')!=close or s.get('exit_state',{}).get('camera')!=close:fail('EVENT2_CAMERA_INVALID')
        if [(e['kind'],e['time']) for e in s['visual_events']]!=[('city_reveal',2),('route_blocked',6),('milestone_reveal',11),('city_reveal',15),('milestone_reveal',20.5)]:fail('SECOND_EVENT_SEQUENCE_INVALID')
        if c.get('source_hashes')!=hashes():fail('SECOND_EVENT_SOURCE_MISMATCH')
        try:validate_frame_plan(plan)
        except ValueError:fail('SECOND_EVENT_FRAME_GRID_INVALID')
    return dict(passed=not errors,errors=errors,warnings=[],scope='two-location camera QA; technical validation unchanged')
def validate_camera(plan):
    try:return _validate_camera(plan)
    except (KeyError,TypeError,ValueError,AttributeError):return dict(passed=False,errors=[dict(code='SECOND_EVENT_CONFIG_INVALID')],warnings=[])
def generate(raw):
    from . import planner,schema
    if raw.get('qa_mode') is not True or float(raw.get('duration',0))!=24:raise planner.PlanningInputError('두 사건 카메라 테스트는 24초 QA 전용입니다.')
    plan=generate_return({**raw,'duration':15,'direction_profile':'SINGLE_EVENT_RETURN_TO_WIDE_TEST'})
    s=plan['scenes'][0];old=s.pop('return_wide_camera');coord=resolve_location('Singapore')['coordinates'];wide=adaptive_wide(s['coordinates'],coord)
    adaptive={**s['camera_start'],**wide['camera'],'target_lon':wide['camera']['lon'],'target_lat':wide['camera']['lat']}
    close={**old['event_camera'],'lon':coord['lon'],'lat':coord['lat'],'target_lon':coord['lon'],'target_lat':coord['lat']}
    s.update(duration=24.,description='Two-event adaptive-wide camera QA',camera_end=deepcopy(close))
    s['exit_state']['camera']=deepcopy(close)
    # Existing Suez labels/events/sound cues retain their exact first-15s timing
    # and design. Only second location and its stable view receipt are added.
    e=deepcopy(s['visual_events'][0]);e.update(id='E004',time=15.,duration=9.,coordinates=deepcopy(coord),target_id=coord['location_id'],description='SINGAPORE',caused_by='E003',role='transition',meaningful=False,claim_id='F03')
    s['visual_events'].append(e)
    e=deepcopy(s['visual_events'][2]);e.update(id='E005',time=20.5,duration=3.5,coordinates=deepcopy(coord),target_id=coord['location_id'],text='',description='Second event stable view',caused_by='E004',meaningful=False,claim_id='F03')
    s['visual_events'].append(e)
    label=deepcopy(s['labels'][0]);label.update(text='SINGAPORE',coordinates=deepcopy(coord),start_time=15.,end_time=24.);s['labels'].append(label)
    s['second_event_camera']=dict(preset=PRESET,version='v017',timeline=timeline(),end_state='END',event1_camera=old['event_camera'],event2_camera=deepcopy(close),adaptive_camera=adaptive,adaptive_wide=wide,next_coordinates=deepcopy(coord),source_hashes=hashes())
    plan['duration']=24.;plan['request'].update(duration=24,qa_mode=True,direction_profile=PRESET);plan['metadata']={'camera_test_preset':PRESET}
    canonicalize_plan(plan);install_validation();plan['gate']=schema.validate_plan(plan)
    if not plan['gate']['passed']:raise RuntimeError('SECOND_EVENT_PLAN_INVALID: '+json.dumps(plan['gate']['errors']))
    return plan
