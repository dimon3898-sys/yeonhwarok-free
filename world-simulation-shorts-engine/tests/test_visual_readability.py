"""Actual-output-driven presentation contracts; no software/GPU pixel claims."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from engine.assets import APP_ROOT,renderer_version
from engine.qa_planner import generate_deployment_plan
from engine.visual_readability import apply_readability_policy
from engine.readability_backend import readable_command

REQUEST=dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=12,qa_mode=True,quality='HIGH',pace='FAST_PLUS',tts=False,subtitles=False,bgm=True,sfx=True)

class ReadabilityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.plan=generate_deployment_plan(REQUEST)
 def test_all_five_scene_json_and_high_quality_gate(self):
  self.assertTrue(self.plan['gate']['passed'],self.plan['gate']['errors'])
  self.assertEqual(len(self.plan['scenes']),5)
  self.assertEqual(self.plan['duration'],12)
  for s in self.plan['scenes']:
   self.assertEqual(s['visual_readability']['version'],'readability_v011')
   self.assertEqual(s['render_quality'],'HIGH')
   self.assertEqual(s['pace'],'FAST_PLUS')
 def test_saved_legacy_plans_are_not_implicitly_upgraded(self):
  plan=copy.deepcopy(self.plan);plan['options']['pace']='NORMAL'
  for s in plan['scenes']:s.pop('visual_readability')
  before=copy.deepcopy(plan)
  self.assertEqual(apply_readability_policy(plan),before)
  self.assertEqual(plan,before)
 def test_scene_events_route_entity_clocks_and_audio_are_preserved(self):
  before=copy.deepcopy(self.plan)
  after=apply_readability_policy(before)
  self.assertEqual(before,self.plan)
  for a,b in zip(before['scenes'],after['scenes']):
   for key in ['visual_events','routes','entities','sound_events','text_events','start_time','duration','render_time_offset']:
    self.assertEqual(a.get(key),b.get(key),key)
 def test_camera_endpoints_and_declared_states_are_exact(self):
  for i,s in enumerate(self.plan['scenes']):
   self.assertEqual(s['entry_state']['camera'],s['camera_start'])
   self.assertEqual(s['exit_state']['camera'],s['camera_end'])
   if i:self.assertEqual(s['camera_start'],self.plan['scenes'][i-1]['camera_end'])
 def test_camera_windows_leave_reading_time_and_peak_settle(self):
  for s in self.plan['scenes']:
   p=s['visual_readability'];self.assertGreaterEqual(p['initial_hold'],.10)
   self.assertGreaterEqual(p['final_hold'],.35)
   self.assertLess(p['initial_hold']+p['final_hold'],s['duration'])
  self.assertGreaterEqual(self.plan['scenes'][2]['visual_readability']['initial_hold'],.7)
  self.assertLessEqual(self.plan['scenes'][-1]['duration']-self.plan['scenes'][-1]['visual_readability']['final_hold'],1.8+1e-9)
 def test_new_sources_have_truthful_plan_cache_input_hashes(self):
  for s in self.plan['scenes']:
   for name,digest in s['visual_readability']['source_hashes'].items():
    self.assertEqual(hashlib.sha256((APP_ROOT/name).read_bytes()).hexdigest(),digest)
 def test_page_dispatch_preserves_gpu_worker_and_existing_parameters(self):
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'S001.json';file.write_text(json.dumps(self.plan['scenes'][0]))
   cmd=['node',str(APP_ROOT/'tools/render_production_scene.mjs'),'--url','http://127.0.0.1:8000/static/render_production_earth.html?project=p&scene=S001','--scene-json',str(file),'--quality','HIGH']
   result=readable_command(cmd)
   self.assertEqual(result[:3],cmd[:3]);self.assertEqual(result[4:],cmd[4:])
   self.assertIn('/static/render_readable_earth.html?',result[3]);self.assertEqual(cmd[3].split('?')[1],result[3].split('?')[1])
 def test_real_production_root_page_is_redirected_to_available_static_page(self):
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'S001.json';file.write_text(json.dumps(self.plan['scenes'][0]))
   cmd=['node',str(APP_ROOT/'tools/render_production_scene.mjs'),'--url','http://127.0.0.1:8001/render_production_earth.html?scene=S001','--scene-json',str(file)]
   result=readable_command(cmd)
   self.assertEqual(result[3],'http://127.0.0.1:8001/static/render_readable_earth.html?scene=S001')
   self.assertTrue((APP_ROOT/'web/render_readable_earth.html').is_file())
 def test_modified_source_is_rejected_before_renderer_dispatch(self):
  with tempfile.TemporaryDirectory() as folder:
   s=copy.deepcopy(self.plan['scenes'][0]);s['visual_readability']['source_hashes']['web/readability_visual_adapter.js']='0'*64
   file=Path(folder)/'S001.json';file.write_text(json.dumps(s))
   cmd=['node',str(APP_ROOT/'tools/render_production_scene.mjs'),'--url','http://127.0.0.1:8000/static/render_production_earth.html','--scene-json',str(file)]
   with self.assertRaisesRegex(RuntimeError,'READABILITY_SOURCE_MISMATCH'):readable_command(cmd)
 def test_all_frames_numeric_visibility_and_clipping_remain_strict(self):
  with tempfile.TemporaryDirectory() as folder:
   plan=Path(folder)/'plan.json';output=Path(folder)/'poses.json';plan.write_text(json.dumps(self.plan))
   p=subprocess.run(['node',str(APP_ROOT/'tools/collect_all_preflight.mjs'),'--plan',str(plan),'--output',str(output)],cwd=APP_ROOT,capture_output=True,text=True,timeout=90)
   self.assertEqual(p.returncode,0,p.stderr)
   r=json.loads(output.read_text());self.assertEqual(len(r['pose_records']),360);self.assertEqual(r['failures'],[])
   for record in r['pose_records']:
    self.assertEqual(record['entityClipped'],[]);self.assertEqual(record['textClipped'],[])
   self.assertEqual(r['hardware_checks']['WebGL'],'NOT_RUN')
 def test_camera_phase_accelerates_decelerates_and_holds_without_global_clock(self):
  source=(APP_ROOT/'web/readability_visual_adapter.js').read_text().replace("import * as THREE from 'three';",'').replace("import {SceneProductionEarthRenderer} from './production_visual_adapter.js';",'').replace('export ','')
  code="const SceneProductionEarthRenderer=class {};"+source+"\nconst scene={duration:2.4,visual_readability:{initial_hold:.45,final_hold:.6,acceleration_fraction:.15}};const assert=(c)=>{if(!c)throw Error('contract');};assert(readableCameraPhase(0,scene)===0);assert(readableCameraPhase(.45,scene)===0);assert(readableCameraPhase(1.81,scene)===1);let prior=0;for(let i=0;i<=240;i++){let p=readableCameraPhase(i/100,scene);assert(p>=prior-1e-10&&p<=1);prior=p;}assert(readableCameraPhase(.451,scene)<1e-6);assert(1-readableCameraPhase(1.799,scene)<1e-6);const light=readableLighting(2.4,{...scene,start_time:0,visual_readability:{...scene.visual_readability,total_duration:12}},{exposure:1.3,surfaceFill:.15,cloudOpacity:.4,cityGain:1.2,hero:1});assert(light.exposure===1.14&&light.cloudOpacity===.22&&light.cityGain===1.2&&light.dayWeight>.6);"
  p=subprocess.run(['node','--input-type=module','-e',code],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr)
 def test_new20_second_production_retains_duration_and_schema(self):
  plan=generate_deployment_plan({**REQUEST,'duration':20,'qa_mode':False})
  self.assertEqual(plan['duration'],20)
  self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
 def test_twenty_second_native_preflight_keeps_all_strict_gates(self):
  # Explicit copy-only candidate replay; non-QA default stays certified.
  plan=apply_readability_policy(generate_deployment_plan({**REQUEST,'duration':20,'qa_mode':False}))
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'plan.json';path.write_text(json.dumps(plan))
   p=subprocess.run(['node',str(APP_ROOT/'tools/collect_all_preflight.mjs'),'--plan',str(path)],cwd=APP_ROOT,capture_output=True,text=True,timeout=90)
   report=json.loads(p.stdout)
   self.assertEqual(report['failures'],[])
   self.assertEqual(p.returncode,0,p.stderr)
   self.assertEqual(len(report['pose_records']),600)
 def test_normal_qa_motion_quality_options_are_retained(self):
  plan=generate_deployment_plan({**REQUEST,'pace':'NORMAL'})
  self.assertFalse(any(s.get('visual_readability') for s in plan['scenes']))
  self.assertEqual(plan['options']['quality'],'HIGH')

 def test_authenticated_gateway_serves_new_page_and_module(self):
  import http.client,secrets,threading
  from deployment.gcube.server import BoundedHTTPServer,GcubeApplication,GcubeHandler
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);access=root/'owner.txt';code=secrets.token_urlsafe(32);access.write_text(code);access.chmod(0o600)
   app=GcubeApplication(root/'runtime','http://127.0.0.1:8001',access,disk_floor=0)
   server=BoundedHTTPServer(('127.0.0.1',0),GcubeHandler,app);app.public_port=server.server_port
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   origin='https://quality-preview.service.gcube.ai:24999'
   headers={'Host':origin[8:],'X-Forwarded-Proto':'http','X-Forwarded-For':'8.8.8.8, 10.0.0.2','X-Envoy-External-Address':'10.0.0.2','Origin':origin,'Content-Type':'application/json'}
   try:
    conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10);conn.request('POST','/auth/login',json.dumps({'password':code}),headers);response=conn.getresponse();self.assertEqual(response.status,200);cookie=response.getheader('Set-Cookie').split(';')[0];response.read();conn.close()
    for path,needle in [('/static/render_readable_earth.html',b'SceneReadableEarthRenderer'),('/static/readability_visual_adapter.js',b'readableCameraPhase')]:
     conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10);conn.request('GET',path,headers={**headers,'Cookie':cookie});response=conn.getresponse();self.assertEqual(response.status,200);self.assertIn(needle,response.read());conn.close()
   finally:
    server.shutdown();server.server_close();thread.join(2);app.scheduler.close()
