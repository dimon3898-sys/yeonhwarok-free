"""New presentation behavior plus native, canvas-free regression of four domains."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from engine.direction import apply_direction, direction_qc, reading_time, ROOT, SOURCES, VERSION
from engine.direction_backend import direction_command
from engine.qa_planner import generate_deployment_plan, configure_qa_schema


class DirectionFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory();cls.plans={};cls.native={}
        requests=json.loads((ROOT/'tests/fixtures/direction_requests.json').read_text())
        with patch.dict(os.environ,{'WORLD_ENGINE_DIRECTION_VERSION':'v012'}):
            for name,raw in requests.items():
                plan=generate_deployment_plan(dict(raw,quality='HIGH',pace='FAST_PLUS',tts=False,subtitle=False,bgm=True,sfx=True))
                path=Path(cls.folder.name)/(name+'.json');path.write_text(json.dumps(plan,ensure_ascii=False))
                out=Path(cls.folder.name)/(name+'-native.json')
                result=subprocess.run(['node',str(ROOT/'tools/collect_all_preflight.mjs'),'--plan',str(path),'--output',str(out)],cwd=ROOT,capture_output=True,text=True,timeout=180)
                if not out.is_file():raise AssertionError(result.stderr[-1000:])
                cls.plans[name]=plan;cls.native[name]=json.loads(out.read_text())
        configure_qa_schema()

    @classmethod
    def tearDownClass(cls): cls.folder.cleanup()

    def test_shipping_12_native(self): self.assertTrue(self.plans['shipping']['gate']['passed'],self.plans['shipping']['gate']['errors']);self.assertTrue(self.native['shipping']['passed'],self.native['shipping']['failures'])
    def test_aviation_12_native(self): self.assertTrue(self.plans['aviation']['gate']['passed'],self.plans['aviation']['gate']['errors']);self.assertTrue(self.native['aviation']['passed'],self.native['aviation']['failures'])
    def test_country_12_native(self): self.assertTrue(self.plans['country']['gate']['passed'],self.plans['country']['gate']['errors']);self.assertTrue(self.native['country']['passed'],self.native['country']['failures'])
    def test_world_network_production_planning_native(self): self.assertTrue(self.plans['network']['gate']['passed'],self.plans['network']['gate']['errors']);self.assertTrue(self.native['network']['passed'],self.native['network']['failures'])
    def test_every_domain_uses_same_version(self):
        self.assertEqual({s['direction']['version'] for p in self.plans.values() for s in p['scenes']},{VERSION})
    def test_no_actual_gpu_claim(self):
        for report in self.native.values(): self.assertEqual(report['hardware_checks']['WebGL'],'NOT_RUN')
    def test_production_read_time_not_scaled(self):
        for p in self.plans.values():
            for s in p['scenes']: self.assertGreaterEqual(s['direction']['settle'],.6)
    def test_result_minimum_settle_all_domains(self):
        for p in self.plans.values():
            last=p['scenes'][-1];self.assertEqual(last['direction']['intent'],'RESULT_HERO');self.assertGreaterEqual(last['direction']['settle'],1.05)
    def test_native_camera_budget(self):
        for report in self.native.values():
            for row in report['scene_checks']:self.assertLessEqual(row['numeric']['maxCameraAngleDegreesPerFrame'],2.5)
    def test_boundary_declared_state_preserved(self):
        for p in self.plans.values():
            for a,b in zip(p['scenes'],p['scenes'][1:]):self.assertEqual(a['exit_state'],b['entry_state'])
    def test_native_earth_boundary_quaternion_and_position(self):
        for name,p in self.plans.items():
            records=self.native[name]['pose_records']
            for a,b in zip(p['scenes'],p['scenes'][1:]):
                if a.get('render_mode')!=b.get('render_mode') or a.get('render_mode')=='FLAT_MAP_PREMIUM':continue
                left=[r for r in records if r['scene_id']==a['scene_id']][-1]
                right=[r for r in records if r['scene_id']==b['scene_id']][0]
                for x,y in zip(left['cameraPosition'],right['cameraPosition']):self.assertAlmostEqual(x,y,places=6)
                dot=sum(x*y for x,y in zip(left['cameraQuaternion'],right['cameraQuaternion']))
                self.assertAlmostEqual(abs(dot),1,places=6)
    def test_audio_and_visual_share_timestamp(self):
        for p in self.plans.values():
            for s in p['scenes']:
                events={e['id']:e for e in s['visual_events']}
                for sound in s['sound_events']:
                    if sound.get('visual_event_id') in events:self.assertAlmostEqual(sound['time'],events[sound['visual_event_id']]['time'],places=5)
    def test_frozen_actual_render_resolution(self):
        for report in self.native.values():self.assertEqual(report['resolution'],[2160,3840])
    def test_no_decorative_question(self):
        self.assertFalse(any(t.get('role')=='question' for p in self.plans.values() for s in p['scenes'] for t in s.get('text_events',[])))
    def test_version_does_not_upgrade_saved_plan(self):
        p=self.plans['shipping'];self.assertIs(apply_direction(p),p)
    def test_backend_selects_page_with_exact_source_contract(self):
        s=self.plans['shipping']['scenes'][0];path=Path(self.folder.name)/'scene.json';path.write_text(json.dumps(s))
        command=['node','render_production_scene.mjs','--scene-json',str(path),'--url','http://127.0.0.1:8000/static/render_production_earth.html']
        self.assertIn('/static/render_direction_earth.html',direction_command(command)[-1])
    def test_backend_rejects_missing_hash(self):
        s=deepcopy(self.plans['shipping']['scenes'][0]);s['direction']['source_hashes']={};path=Path(self.folder.name)/'bad.json';path.write_text(json.dumps(s))
        with self.assertRaisesRegex(RuntimeError,'SOURCE_SET'):direction_command(['node','render_production_scene.mjs','--scene-json',str(path),'--url','http://127.0.0.1/static/render_production_earth.html'])
    def test_backend_saved_legacy_command_unchanged(self):
        path=Path(self.folder.name)/'legacy.json';path.write_text(json.dumps(dict(scene_id='S001')))
        cmd=['node','render_production_scene.mjs','--scene-json',str(path),'--url','http://127.0.0.1/static/render_production_earth.html'];self.assertEqual(direction_command(cmd),cmd)
    def test_source_hashes_current(self):
        for p in self.plans.values():
            for s in p['scenes']:
                for f in SOURCES:self.assertEqual(s['direction']['source_hashes'][f],hashlib.sha256((ROOT/f).read_bytes()).hexdigest())
    def test_invalid_camera_is_critical(self):
        p=deepcopy(self.plans['shipping']);p['scenes'][0]['camera_start']['lat']=float('nan');self.assertFalse(direction_qc(p)['passed'])
    def test_warning_does_not_stop_render(self):
        p=deepcopy(self.plans['shipping']);p['scenes'][1]['direction']['angular_budget_deg_s']=.1
        result=direction_qc(p);self.assertTrue(result['passed']);self.assertIn('CAMERA_MOTION_OVERLOAD',[f['code'] for f in result['findings']])
    def test_actual_frame_artifacts_not_aesthetic_pass(self):
        for p in self.plans.values():self.assertEqual(direction_qc(p)['rendered_pixel_checks'],'NOT_RUN')


class DirectionReading(unittest.TestCase):
    def test_characters_adapt_settle(self):self.assertGreater(reading_time('LONG LOCATION NAME WITH CONTEXT'),reading_time('ROME'))
    def test_korean_reading_floor(self):self.assertGreaterEqual(reading_time('경로 변경',important=True),.82)
    def test_result_read_time(self):self.assertGreaterEqual(reading_time('ARRIVED',result=True),1.05)
    def test_read_time_is_bounded(self):self.assertLessEqual(reading_time('X'*500,result=True),1.5)
    def test_density_adapts_reading(self):self.assertGreaterEqual(reading_time('ROME',density=3),reading_time('ROME',density=1))
    def test_old_versions_not_modified(self):
        plan={'options':{'pace':'FAST'},'scenes':[{}]};self.assertIs(apply_direction(plan),plan)
    def test_shared_motion_clock_and_single_primary(self):
        code="""import fs from 'node:fs';import {pathToFileURL} from 'node:url';
const THREE=await import(pathToFileURL('../cinematic-world-map/node_modules/three/build/three.module.js'));
const source=fs.readFileSync('web/direction_visual_adapter.js','utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const api=new Function('THREE','SceneProductionEarthRenderer','SceneProductionFlatRenderer','SceneReadableEarthRenderer','installReadableEntities','readableEntityScale',source+';return {directionPhase,directionLabelsAt,installDirectionCamera,installDirectionFlat};')(THREE,class{},class{},class{},()=>{},()=>{});
const scene={duration:2.4,direction:{initial_hold:.2,move_end:1.4,camera_up_start:[0,1,0]},labels:[{text:'CITY',role:'city',start_time:0,end_time:2.4},{text:'ARRIVED',role:'status',event_id:'E1',start_time:1.4,end_time:2.4},{text:'10 km',role:'distance',event_id:'E2',start_time:1.4,end_time:2.4}]};
const labels=api.directionLabelsAt(scene,1.6);if(labels.filter(l=>l.opacity===.98).length!==1)throw Error('MULTIPLE_PRIMARY');
if(api.directionPhase(0,scene)!==0||api.directionPhase(1.5,scene)!==1||api.directionPhase(2.39,scene)!==1)throw Error('HOLD_NOT_STATIONARY');
const cam={scene,start:{lon:0,lat:0,height:2,tilt:.3,yaw:-.18,bank:0,fov:62},end:{lon:80,lat:0,height:3,tilt:.3,yaw:-.18,bank:0,fov:62},update:()=>{},camera:new THREE.PerspectiveCamera()};api.installDirectionCamera(cam);
if(cam.values(.6).height!==2||Math.abs(cam.values(1.25).lon-80)>1e-6)throw Error('SIMULTANEOUS_STRONG_AXES');
const endpoint={lon:0,lat:0,span_degrees:40,tilt:.3,rotation:0,bank:0};
const flat={sceneSpec:{...scene,transition_in:'EARTH_TO_FLAT',transition_out:'FLAT_TO_EARTH'},cam:{start:endpoint,end:endpoint,projection:{point:()=>new THREE.Vector3()}}};api.installDirectionFlat(flat);
if(Math.abs(flat.cam.values(0).span-51.2)>1e-6||flat.cam.values(0).projectionHandoff!==1||Math.abs(flat.cam.values(2.4).tilt-.15)>1e-6)throw Error('PROJECTION_HANDOFF_CHANGED');
console.log('PASS');"""
        r=subprocess.run(['node','--input-type=module','-e',code],cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('PASS',r.stdout)


class DirectionProduction75(unittest.TestCase):
    def test_long_production_plan_keeps_readability_floor(self):
        with patch.dict(os.environ,{'WORLD_ENGINE_DIRECTION_VERSION':'v012'}):
            p=generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=75,
                quality='HIGH',pace='FAST_PLUS',tts=False,subtitle=False,bgm=True,sfx=True))
            self.assertTrue(p['gate']['passed'],p['gate']['errors'])
            self.assertTrue(all(s['direction']['mode']=='PRODUCTION' and s['direction']['settle']>=.6 for s in p['scenes']))
            self.assertGreaterEqual(p['scenes'][-1]['direction']['settle'],1.05)
        configure_qa_schema()
