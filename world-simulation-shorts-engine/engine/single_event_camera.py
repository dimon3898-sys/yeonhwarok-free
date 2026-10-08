"""Opt-in fixed 12s Suez camera test; existing directors and old plans remain intact."""
from copy import deepcopy
from pathlib import Path
from types import FunctionType
import json,hashlib
from .frame_grid import canonicalize_plan,validate_frame_plan
ROOT=Path(__file__).resolve().parents[1]
PRESET='SINGLE_EVENT_CAMERA_TEST'
SOURCES=('engine/single_event_camera.py','web/single_event_camera.js','web/render_single_event_earth.html','tools/collect_all_preflight.mjs')
TIMELINE=[('WIDE',0,60),('EVENT_LOCATION',60,90),('ZOOM_IN',90,150),('SETTLE',150,180),('EVENT_REVEAL',180,240),('EVENT_HOLD',240,360)]

def validate_camera(plan):
    errors=[]
    if len(plan.get('scenes',[]))!=1 or plan.get('duration')!=12:errors.append({'code':'SINGLE_TEST_DURATION_OR_SCENE_INVALID'})
    if not errors:
        s=plan['scenes'][0];c=s.get('single_event_camera',{})
        expected=[dict(state=n,start_frame=a,end_frame=b,frame_count=b-a,start_seconds=a/30,end_seconds=b/30) for n,a,b in TIMELINE]
        if c.get('timeline')!=expected:errors.append({'code':'SINGLE_CAMERA_TIMELINE_INVALID'})
        if s.get('direction') or s['camera_start']['lon']!=s['camera_end']['lon'] or s['camera_start']['lat']!=s['camera_end']['lat']:errors.append({'code':'SINGLE_CAMERA_FOREIGN_MOTION'})
        if s['camera_start']['height']!=2.5 or s['camera_end']['height']!=.2 or s['camera_start']['fov']!=64 or s['camera_end']['fov']!=48:errors.append({'code':'SINGLE_CAMERA_ZOOM_INVALID'})
        if [(e['kind'],e['time']) for e in s['visual_events']]!=[('city_reveal',2),('route_blocked',6)]:errors.append({'code':'SINGLE_EVENT_SEQUENCE_INVALID'})
        if c.get('source_hashes')!={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}:errors.append({'code':'SINGLE_CAMERA_SOURCE_MISMATCH'})
        try:validate_frame_plan(plan)
        except ValueError:errors.append({'code':'SINGLE_FRAME_GRID_INVALID'})
    return dict(passed=not errors,errors=errors,warnings=[],scope='single-event camera test admission; no production retention score')

def install_validation():
    from . import schema
    if getattr(schema.validate_plan,'single_test_wrapper',False):return
    original=schema.validate_plan
    def checked(plan):
        preset=plan.get('metadata',{}).get('camera_test_preset')
        if preset==PRESET:admit=validate_camera
        elif preset=='SINGLE_EVENT_RETURN_TO_WIDE_TEST':
            from .return_wide_camera import validate_camera as admit
        elif preset=='SECOND_EVENT_ADAPTIVE_WIDE_TEST':
            from .second_event_camera import validate_camera as admit
        else:return original(plan)
        admission=admit(plan)
        if not admission['passed']:return admission
        # Only narrative multi-event retention is replaced with this explicit
        # single-event test contract. GIS/schema/asset/native/GPU checks remain.
        ns=dict(original.__globals__);ns['analyze_retention']=admit
        fn=FunctionType(original.__code__,ns,original.__name__,original.__defaults__)
        return fn(plan)
    checked.single_test_wrapper=True;schema.validate_plan=checked
    from . import gpu_preflight
    gpu_preflight.validate_plan=checked

def generate(raw):
    from . import planner,schema,visibility
    schema.SCHEMA_PATH=ROOT/'data/reference_scene_plan.schema.json'
    visibility.TOOL=ROOT/'tools/reference_semantic_preflight.mjs'
    if float(raw.get('duration',0))!=12 or raw.get('qa_mode') is not True:raise planner.PlanningInputError('단일 사건 카메라 테스트는 12초 QA 전용입니다.')
    checked=deepcopy(raw);checked['duration']=20;request=planner._request(checked)
    if planner._scenario(request)['domain']!='shipping':raise planner.PlanningInputError('단일 사건 카메라 테스트는 수에즈 주제 전용입니다.')
    plan=json.loads((ROOT/'deployment/gcube/framegrid_v013_fixture.json').read_text());scene=deepcopy(plan['scenes'][1])
    for key in ('direction','rhythm_micro_beats','flat_map','flat_transition','visual_readability','focus_target'):scene.pop(key,None)
    scene.update(scene_id='S001',scene_type='CITY_FOCUS',directing_presets=['CITY_REVEAL'],description='Suez single-event camera test',start_time=0.,duration=12.,hook='',routes=[],entities=[],entity_actions=[],narration='수에즈 운하가 봉쇄된다.',narration_event_ids=['E002'],camera_preset='COUNTRY_APPROACH',camera_speed=1.,transition_in='camera_continuity',transition_out='camera_continuity')
    coord=scene['coordinates'];camera=dict(scene['camera_start']);camera.update(lon=coord['lon'],lat=coord['lat'],target_lon=coord['lon'],target_lat=coord['lat'],height=2.5,fov=64,tilt=0.,yaw=0.,bank=0.)
    scene['camera_start']=camera;scene['camera_end']={**camera,'height':.2,'fov':48}
    scene['entry_state']['camera']=deepcopy(camera);scene['exit_state']['camera']=deepcopy(scene['camera_end'])
    for state in ('entry_state','exit_state'):scene[state].update(active_routes=[],entities=[])
    location=dict(id='E001',kind='city_reveal',time=2.,duration=10.,target_id=coord['location_id'],coordinates=deepcopy(coord),text='',description='SUEZ CANAL',role='cause',caused_by=None,meaningful=True,claim_id='F02')
    event=deepcopy(next(e for e in scene['visual_events'] if e['kind']=='route_blocked'));event.update(id='E002',time=6.,duration=6.,role='variable',caused_by='E001')
    scene['visual_events']=[location,event]
    for label in scene['labels']:label.update(start_time=2.,end_time=12.);label.pop('event_id',None)
    for label in scene['text_events']:label.update(id='T_E002',event_id='E002',start_time=6.,end_time=12.)
    location_sound=deepcopy(plan['scenes'][0]['sound_events'][0]);event_sound=deepcopy(scene['sound_events'][0])
    for cue,e in ((location_sound,location),(event_sound,event)):
        cue.update(id='A_'+e['id'],time=e['time'],visual_event_id=e['id'])
    scene['sound_events']=[location_sound,event_sound]
    scene['single_event_camera']=dict(preset=PRESET,version='v015',timeline=[dict(state=n,start_frame=a,end_frame=b,frame_count=b-a,start_seconds=a/30,end_seconds=b/30) for n,a,b in TIMELINE],end_state='END',source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES})
    plan.update(scenes=[scene],duration=12.)
    for key in ('production_defaults','rhythm_policy','gate','plan_hash'):plan.pop(key,None)
    plan['request'].update(topic=raw['topic'],duration=12,qa_mode=True,direction_profile=PRESET)
    for key in ('tts','subtitles','bgm','sfx','quality'):
        if key in request:plan['options'][key]=request[key]
    plan['metadata']={'camera_test_preset':PRESET}
    plan['story']['hook']=''
    plan['story']['beats']=[dict(scene_id='S001',role='variable',cause=None,summary='Suez Canal closure')]
    canonicalize_plan(plan);install_validation()
    from .schema import validate_plan
    plan['gate']=validate_plan(plan)
    if not plan['gate']['passed']:raise RuntimeError('SINGLE_EVENT_PLAN_INVALID: '+json.dumps(plan['gate']['errors']))
    return plan
