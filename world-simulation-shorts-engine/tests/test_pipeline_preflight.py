"""Native pose/strict audit and real media fixtures; no GPU rendering."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from engine.assets import APP_ROOT
from engine.failures import RenderProcessError, failure_record
from engine.qa_planner import generate_deployment_plan
from engine.pipeline_stability import checked_concat as _concat
from deployment.gcube.asset_audit import audit_assets
REQUEST=dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=12,qa_mode=True,quality='HIGH',pace='FAST_PLUS',tts=False,subtitles=False,bgm=True,sfx=True)
FIXTURE=APP_ROOT/'tests/fixtures/suez_qa12/v009_reconstructed_plan.json'
def node(source):
 return subprocess.run(['node','--input-type=module','-e',source],cwd=APP_ROOT,capture_output=True,text=True,timeout=90,check=True)
class PipelinePreflightTests(unittest.TestCase):
 def test_all_five_native_scenes_before_clipped_after_safe(self):
  with tempfile.TemporaryDirectory() as folder:
   fixed=Path(folder)/'fixed.json';fixed.write_text(json.dumps(generate_deployment_plan(REQUEST)))
   for name,fixture,expected in [('before',FIXTURE,False),('after',fixed,True)]:
    output=Path(folder)/(name+'.json')
    run=subprocess.run(['node',str(APP_ROOT/'tools/collect_all_preflight.mjs'),'--plan',str(fixture),'--output',str(output)],cwd=APP_ROOT,capture_output=True,text=True,timeout=90)
    self.assertEqual(run.returncode,0 if expected else 2,run.stderr)
    report=json.loads(output.read_text());self.assertEqual(report['passed'],expected)
    self.assertEqual(len(report['pose_records']),360)
    self.assertEqual({r['scene_id'] for r in report['scene_checks']},{'S001','S002','S003','S004','S005'})
    if not expected:
     bad=[r for r in report['failures'] if r['code']=='POSE_CLIPPING']
     self.assertEqual([(r['scene_id'],r['frame_index']) for r in bad],[('S004',47),('S004',48),('S004',49),('S004',50)])
     self.assertEqual(next(r for r in report['pose_records'] if r['scene_id']=='S002')['routeProgress'][0]['progress'],0.11821892)
    self.assertEqual(report['hardware_checks']['WebGL'],'NOT_RUN')
 def test_empty_errors_still_names_each_failed_invariant(self):
  node("""import assert from 'node:assert/strict';import {auditFailures} from './tools/scene_frame_contract.mjs';
  const good={webglError:0,textClipped:[],entityClipped:[],missingTextures:[],routeDiscontinuities:[],routeInsideEarth:false,fontReady:true,cameraPosition:[1,2,3],cameraQuaternion:[0,0,0,1],cameraFov:44,entities:[],routeProgress:[]};assert.deepEqual(auditFailures(good,[]),[]);
  for(const [field,value,rule] of [['webglError',1282,'WEBGL_ERROR'],['entityClipped',['ship_reference'],'ENTITY_CLIPPED'],['textClipped',[{}],'TEXT_CLIPPED'],['fontReady',false,'FONT_NOT_READY'],['missingTextures',['uDay'],'TEXTURE_MISSING'],['routeInsideEarth',true,'ROUTE_INSIDE_EARTH']])assert.ok(auditFailures({...good,[field]:value},[]).includes(rule));
  for(const value of [NaN,Infinity,null])assert.ok(auditFailures({...good,cameraPosition:[value,0,0]},[]).includes('CAMERA_NONFINITE'));assert.ok(auditFailures({},[]).length>0);""")
 def test_jpeg_guard_rejects_empty_truncated_decode_size_and_sequence(self):
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'frame.jpg';Image.new('RGB',(1080,1920),(30,60,90)).save(file,quality=99)
   with Image.open(file) as decoded:decoded.load();self.assertEqual(decoded.size,(1080,1920))
   node("""import fs from 'node:fs';import assert from 'node:assert/strict';import {validateJpeg} from './tools/scene_frame_contract.mjs';
   const b=fs.readFileSync(%s),o={width:1080,height:1920,decoded:[1080,1920],frameIndex:0,expectedIndex:0};assert.equal(validateJpeg(b,o),b);
   for(const [buffer,opts] of [[Buffer.alloc(0),o],[b.subarray(0,b.length-2),o],[b,{...o,decodeError:true}],[b,{...o,decoded:[1,2]}],[b,{...o,expectedIndex:1}]])assert.throws(()=>validateJpeg(buffer,opts),e=>e.code==='SCENE_FRAME_INVALID');"""%json.dumps(str(file)))
 def test_early_encoder_exit_is_observed_not_unhandled_or_hung(self):
  node("""import assert from 'node:assert/strict';import {FFmpegPipe} from './tools/scene_frame_contract.mjs';
  const pipe=new FFmpegPipe(['-e','process.exit(9)'],{executable:process.execPath});await pipe.closed;
  await assert.rejects(pipe.write(Buffer.alloc(500000)),e=>e.code==='FFMPEG_PIPE_FAILED');await pipe.abort();assert.equal(pipe.result.code,9);
  const missing=new FFmpegPipe([],{executable:'/nonexistent/encoder'});await missing.closed;await assert.rejects(missing.finish(),e=>e.code==='FFMPEG_PIPE_FAILED');await missing.abort();""")
 def test_scene_failure_root_survives_worker_exit(self):
  error=RenderProcessError(returncode=1,duration=2.577,stderr=['WORLD_ENGINE_RENDER_FAILURE '+json.dumps(dict(code='FRAME_AUDIT_FAILED',frame_index=0,failed_invariants=['WEBGL_ERROR'],secret='must_not_survive'))])
  result=failure_record(error,stage='scene_start',scene_id='S002')
  self.assertEqual(result['code'],'SCENE_RENDERER_EXIT');self.assertEqual(result['subprocess']['root_cause'],dict(code='FRAME_AUDIT_FAILED',frame_index=0,failed_invariants=['WEBGL_ERROR']));self.assertNotIn('must_not_survive',json.dumps(result))
 def test_pipeline_error_categories(self):
  for before,after in [('SCENE_ASSEMBLY_FAILED','CONCAT_FAILED'),('CONCAT_INPUT_INCOMPATIBLE','CONCAT_FAILED'),('FINAL_QC_FAILED','QC_FAILED'),('AUDIO_PIPELINE_FAILED','AUDIO_FAILED')]:self.assertEqual(failure_record(RuntimeError(before+': sensitive'))['code'],after)
 def test_deployed_asset_manifest(self):
  result=audit_assets();self.assertTrue(result['passed'],[r for r in result['assets'] if not r['readable'] or not r['non_zero']]);self.assertGreater(len(result['assets']),20);self.assertTrue(any('terrain_99a6' in r['path'] for r in result['assets']))
 def test_approved_visual_and_gpu_paths_stay_immutable_and_encoder_lazy(self):
  old=(APP_ROOT/'tools/render_production_scene.mjs').read_text();stable=(APP_ROOT/'tools/render_production_stable_scene.mjs').read_text()
  self.assertIn('if(errors.length||result.audit.webglError',old);self.assertLess(stable.index('const failures=auditFailures'),stable.index('new FFmpegPipe'));self.assertLess(stable.index('validateJpeg(buffer'),stable.index('new FFmpegPipe'))
  launch='headless:true,args:';self.assertEqual(old.split(launch)[1].split('});')[0],stable.split(launch)[1].split('});')[0]);self.assertIn('createImageBitmap(blob)',stable)
 def test_concat_rejects_empty_before_ffmpeg(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaisesRegex(RuntimeError,'CONCAT_INPUT_INVALID'):_concat([],Path(folder)/'output.mp4',dict(output_width=1080,output_height=1920))
 def test_corrected_qa_sound_insertion_preserves_normal_library(self):
  from engine.rhythm_sound import select_rhythm_sound_events
  from engine.audio_stability import select_events
  plan=generate_deployment_plan(REQUEST)
  old=select_rhythm_sound_events(plan);new=select_events(plan)
  lookup={r['id']:r for r in old['events']}
  actual={r['id']:r for r in new['events']}
  self.assertEqual([r['absolute_time'] for r in new['events']],sorted(r['absolute_time'] for r in new['events']))
  for history in new['history']:self.assertEqual(history['absolute_time'],actual[history['id']]['absolute_time'])
  for record in new['events']:
   original=lookup[record['id']]
   if record['visual_kind']=='route_start':
    self.assertEqual(record['frame'],original['frame']-1)
    self.assertEqual(record['sfx_variant'],original['sfx_variant'])
   else:self.assertEqual(record,original)
  plan['request']['qa_mode']=False
  self.assertEqual(select_events(plan),select_rhythm_sound_events(plan))
 def test_valid_jpeg_stream_ffmpeg_and_invalid_stream(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);frame=root/'frame.jpg';Image.new('RGB',(1080,1920),(30,60,90)).save(frame,quality=99)
   fixture=dict(internalWidth=1080,internalHeight=1920,outputWidth=1080,outputHeight=1920,fps=30,quality='HIGH',destination=str(root/'video.mp4'),frames=[dict(path=str(frame),decoded=[1080,1920])]*3)
   config=root/'pipe.json';config.write_text(json.dumps(fixture))
   run=subprocess.run(['node',str(APP_ROOT/'tools/check_jpeg_pipe.mjs'),str(config)],cwd=APP_ROOT,capture_output=True,text=True,timeout=30)
   self.assertEqual(run.returncode,0,run.stderr)
   bad=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','image2pipe','-vcodec','mjpeg','-framerate','30','-i','pipe:0','-an',str(root/'bad.mp4')],input=b'not JPEG',capture_output=True,timeout=15)
   self.assertNotEqual(bad.returncode,0)
   # FFmpeg versions report empty/invalid image2pipe streams differently.
   # The contract is failure, a diagnostic, and no usable video, not wording.
   self.assertTrue(bad.stderr)
   from engine.qc import valid_scene_file
   self.assertFalse(valid_scene_file(root/'bad.mp4',.1,1080,1920,30))
   empty=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','image2pipe','-vcodec','mjpeg','-framerate','30','-i','pipe:0','-an',str(root/'empty.mp4')],input=b'',capture_output=True,timeout=15)
   self.assertNotEqual(empty.returncode,0);self.assertTrue(empty.stderr)
