import hashlib,json,os,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from engine.gpu_bundle import DiagnosticBundle,Redactor,diagnostic_outputs,recover_bundle
from engine.qa_planner import configure_qa_schema,generate_deployment_plan
from engine.storage import ProjectStore
ROOT=Path(__file__).resolve().parents[1];JID='job_123456abcdef'
def make_plan():
 configure_qa_schema()
 return generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=12,quality='HIGH',pace='FAST_PLUS',qa_mode=True,tts=False,subtitles=False,bgm=True,sfx=True))
def node(source):return subprocess.run(['node','--input-type=module','-e',source],cwd=ROOT,capture_output=True,text=True,timeout=30)
class BundleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.plan=json.loads((ROOT/'tests/fixtures/suez_qa12/v009_reconstructed_plan.json').read_text())
 def bundle(self):return DiagnosticBundle(self.root,JID,self.plan)
 def unpack(self,path):
  with zipfile.ZipFile(path) as z:return {n:json.loads(z.read(n)) if n.endswith('.json') else z.read(n).decode() for n in z.namelist()}
 def test_all_actual_input_scenes_saved_before_first_frame(self):
  b=self.bundle()
  for s in self.plan['scenes']:self.assertEqual(json.loads((b.root/(s['scene_id']+'.json')).read_text()),Redactor().clean(s))
 def test_before_first_frame_failure_has_zip_and_no_fake_gpu_audit(self):
  d=self.unpack(self.bundle().finish(status='FAILED',error={'code':'SCENE_RENDERER_START_FAILED','scene_id':'S001'}));self.assertEqual(d['frame-audit.json'],[]);self.assertEqual(d['failed-invariant.json']['PRIMARY_ERROR'],'SCENE_RENDERER_START_FAILED');self.assertEqual(d['gpu-diagnostics.json']['measurement_status'],'NOT_AVAILABLE')
 def test_success_includes_qc_checkpoint_and_correct_manifest_hashes(self):
  b=self.bundle();(self.root/'renders').mkdir();(self.root/'renders/checkpoint.json').write_text('{"complete":true}')
  p=b.finish(status='SUCCESS',result={'qc':{'passed':True},'metrics':{'measured':True},'outputs':{}});d=self.unpack(p);self.assertTrue(d['qc.json']['passed']);self.assertTrue(d['checkpoint.json']['complete'])
  with zipfile.ZipFile(p) as z:
   for r in d['manifest.json']['files']:self.assertEqual(hashlib.sha256(z.read(r['name'])).hexdigest(),r['sha256'])
 def test_actual_predicate_failure_fsynced_before_exit_with_errors_empty(self):
  b=self.bundle();p=node(f"""import {{SceneJournal,frameEvidence}} from './tools/scene_diagnostic_journal.mjs';import {{auditFailures}} from './tools/scene_frame_contract.mjs';
 const audit={{shot:'ROUTE_CHASE',webglError:1282,textClipped:[],entityClipped:[],missingTextures:[],fontReady:true,cameraPosition:[1,2,3],cameraQuaternion:[0,0,0,1],cameraFov:50,routeProgress:[],routeDisplay:[],routeInsideEarth:false,routeDiscontinuities:[],entities:[],productionDefaults:{{version:'v1'}}}};
 const j=new SceneJournal({json.dumps(str(b.root))},'S002'),failed=auditFailures(audit,[]);j.frame(frameEvidence({{sceneId:'S002',frameIndex:0,t:0,audit,errors:[],renderer:{{renderer:'INJECTED_UNIT_FIXTURE',vendor:'NOT_ACTUAL_GPU',backend:'NOT_RUN'}},failedInvariants:failed,decoded:[2160,3840],decodeError:false}}));j.failure({{code:'FRAME_AUDIT_FAILED',scene_id:'S002',frame_index:0,failed_invariants:failed}});process.exit(1);""")
  self.assertEqual(p.returncode,1);d=self.unpack(b.finish(status='FAILED'));self.assertEqual(d['frame-audit.json'][0]['errors'],[]);self.assertEqual(d['frame-audit.json'][0]['webglError'],1282);self.assertEqual(d['failed-invariant.json']['FAILED_INVARIANT'],['WEBGL_ERROR'])
 def test_mid_scene_failure_keeps_all_written_frames(self):
  b=self.bundle();p=node(f"import {{SceneJournal}} from './tools/scene_diagnostic_journal.mjs';const j=new SceneJournal({json.dumps(str(b.root))},'S003');for(let i=0;i<18;i++)j.frame({{scene_id:'S003',frame_index:i,errors:[],source:'INJECTED_TEST'}});j.failure({{code:'FRAME_AUDIT_FAILED',scene_id:'S003',frame_index:17,failed_invariants:['ENTITY_CLIPPED']}});process.exit(1);");self.assertEqual(p.returncode,1);d=self.unpack(b.finish(status='FAILED'));self.assertEqual([r['frame_index'] for r in d['frame-audit.json']],list(range(18)))
 def test_parent_recovers_after_worker_kill(self):
  b=self.bundle();(b.root/'S002').mkdir();(b.root/'S002/frame-audit.jsonl').write_text('{"scene_id":"S002","frame_index":0,"webglError":1282}\n');d=self.unpack(recover_bundle(self.root,JID,'FAILED',{'code':'JOB_WORKER_EXIT'}));self.assertEqual(len(d['frame-audit.json']),1)
 def test_secret_redaction_and_explicit_export_allowlist(self):
  with patch.dict(os.environ,{'WORLD_ENGINE_OWNER_CODE':'test-value-938127','EXAMPLE_SECRET':'test-value-718231'}):
   b=self.bundle();b.write('renderer-diagnostics.json',{'Password':'hidden','cameraPosition':[1,2,3],'message':'test-value-938127','Cookie':'h','Authorization':'h','nested':{'token':'h'},'url':'https://example.invalid/?key=test-value-718231'});b.log('stderr','Authorization: test-value-718231');(b.root/'auth.json').write_text('{"password":"unrelated_file_value"}');p=b.finish(status='FAILED')
   with zipfile.ZipFile(p) as z:raw=b''.join(z.read(n) for n in z.namelist());self.assertNotIn('auth.json',z.namelist())
   for value in (b'test-value-938127',b'test-value-718231',b'unrelated_file_value',b'"Password"',b'"Cookie"',b'"Authorization"',b'"token"'):self.assertNotIn(value,raw)
 def test_nonfinite_and_undefined_not_silently_lost(self):
  p=node("import assert from 'node:assert/strict';import {redact} from './tools/scene_diagnostic_journal.mjs';assert.deepEqual(redact([NaN,Infinity,undefined]),[{non_finite:'NaN'},{non_finite:'Infinity'},{not_available:'undefined'}]);");self.assertEqual(p.returncode,0,p.stderr)
 def test_each_failed_predicate_names_invariant_without_force_pass(self):
  p=node("""import assert from 'node:assert/strict';import {auditFailures} from './tools/scene_frame_contract.mjs';const a={webglError:0,textClipped:[],entityClipped:[],missingTextures:[],fontReady:true,cameraPosition:[1,2,3],cameraQuaternion:[0,0,0,1],cameraFov:44,entities:[],routeProgress:[],routeInsideEarth:false,routeDiscontinuities:[]};for(const [k,v,r] of [['webglError',1286,'WEBGL_ERROR'],['textClipped',['SEOUL'],'TEXT_CLIPPED'],['entityClipped',['ship'],'ENTITY_CLIPPED'],['missingTextures',['terrain'],'TEXTURE_MISSING'],['fontReady',false,'FONT_NOT_READY'],['routeInsideEarth',true,'ROUTE_INSIDE_EARTH'],['routeDiscontinuities',['R'],'ROUTE_DISCONTINUITY'],['cameraPosition',[NaN,0,0],'CAMERA_NONFINITE'],['routeProgress',{},'ROUTE_PROGRESS_INVALID'],['entities',null,'ENTITY_DATA_INVALID']])assert.ok(auditFailures({...a,[k]:v},[]).includes(r));assert.ok(auditFailures(a,['console error']).includes('BROWSER_ERROR'));""");self.assertEqual(p.returncode,0,p.stderr)
 def test_secondary_error_never_replaces_primary(self):
  b=self.bundle();f=b.root/'S002';f.mkdir();(f/'failed-invariant.json').write_text(json.dumps({'code':'FRAME_AUDIT_FAILED','failed_invariants':['TEXT_CLIPPED']}));(f/'ffmpeg-diagnostics.json').write_text(json.dumps({'secondary_errors':[{'code':'ENCODER_EXIT_AFTER_PRIMARY','return_code':1}]}));d=self.unpack(b.finish(status='FAILED'));self.assertEqual(d['failed-invariant.json']['PRIMARY_ERROR'],'FRAME_AUDIT_FAILED');self.assertEqual(d['failed-invariant.json']['SECONDARY_ERROR'][0]['return_code'],1)
 def test_actual_browser_scene_capture_replaces_only_bundle_copy(self):
  b=self.bundle();f=b.root/'S002';f.mkdir();s={**self.plan['scenes'][1],'actual_browser_capture':True};(f/'scene-input.json').write_text(json.dumps(s));d=self.unpack(b.finish(status='FAILED'));self.assertTrue(d['S002.json']['actual_browser_capture']);self.assertNotIn('actual_browser_capture',self.plan['scenes'][1])
 def test_init_failure_retains_all_five_scene_inputs(self):
  d=self.unpack(self.bundle().finish(status='FAILED',error={'code':'ASSET_MISSING','scene_id':'S001'}));self.assertTrue(all('S%03d.json'%i in d for i in range(1,6)))
 def test_logs_keep_more_than_tail(self):
  b=self.bundle()
  for i in range(100):b.log('stdout',f'Frame {i}')
  d=self.unpack(b.finish(status='FAILED'));self.assertEqual(len(d['stdout.txt'].splitlines()),100)
 def test_flush_before_throw_and_valid_jpeg_before_encoder(self):
  s=(ROOT/'tools/render_production_stable_scene.mjs').read_text();self.assertLess(s.index('journal?.frame(frameEvidence'),s.index('if(failures.length)throw'));self.assertLess(s.index('validateJpeg(buffer'),s.index('if(!pipe){encoderStartedAt'));self.assertLess(s.index("canvas.toDataURL('image/jpeg'"),s.index('window.app.audit(t)'))
 def test_only_exact_diagnostic_zip_listed(self):
  b=self.bundle();p=b.finish(status='FAILED');self.assertEqual(len(diagnostic_outputs(self.root,'project_123456','v001')),1);(b.root/'arbitrary.zip').write_bytes(p.read_bytes());self.assertEqual(len(diagnostic_outputs(self.root,'project_123456','v001')),1)
 def test_reserve_released_and_excluded_from_archive(self):
  b=self.bundle();self.assertTrue(b.reserve.is_file());d=self.unpack(b.finish(status='FAILED'));self.assertFalse(b.reserve.exists());self.assertNotIn('zip-reserve.bin',d)
class RecoveryBoundaryTests(unittest.TestCase):
 setUp=BundleTests.setUp
 bundle=BundleTests.bundle
 unpack=BundleTests.unpack
 def test_real_sigkill_retains_fsynced_frames_for_gateway_recovery(self):
  import signal
  b=self.bundle();source=f"import {{SceneJournal}} from './tools/scene_diagnostic_journal.mjs';const j=new SceneJournal({json.dumps(str(b.root))},'S002');j.frame({{scene_id:'S002',frame_index:0,webglError:1282}});console.log('DURABLE');setInterval(()=>{{}},1000);"
  p=subprocess.Popen(['node','--input-type=module','-e',source],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertEqual(p.stdout.readline().strip(),'DURABLE');p.send_signal(signal.SIGKILL);p.wait(timeout=10)
   d=self.unpack(recover_bundle(self.root,JID,'FAILED',{'code':'JOB_WORKER_EXIT'}));self.assertEqual(d['frame-audit.json'][0]['webglError'],1282)
  finally:
   if p.poll() is None:p.kill();p.wait()
   p.stdout.close();p.stderr.close()
 def test_real_sigterm_flushes_invariant_before_exit(self):
  import signal
  b=self.bundle();source=f"import {{SceneJournal}} from './tools/scene_diagnostic_journal.mjs';const j=new SceneJournal({json.dumps(str(b.root))},'S004');process.on('SIGTERM',()=>{{j.failure({{code:'RENDERER_SIGNAL',scene_id:'S004',frame_index:8,failed_invariants:[],signal:'SIGTERM'}});process.exit(143);}});console.log('READY');setInterval(()=>{{}},1000);"
  p=subprocess.Popen(['node','--input-type=module','-e',source],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertEqual(p.stdout.readline().strip(),'READY');p.send_signal(signal.SIGTERM);p.wait(timeout=10);self.assertEqual(p.returncode,143)
   d=self.unpack(b.finish(status='FAILED'));self.assertEqual(d['failed-invariant.json']['PRIMARY_ERROR'],'RENDERER_SIGNAL');self.assertEqual(d['renderer-diagnostics.json'][0]['record']['signal'],'SIGTERM')
  finally:
   if p.poll() is None:p.kill();p.wait()
   p.stdout.close();p.stderr.close()
 def test_aggregation_write_failure_preserves_native_journals_in_fallback_zip(self):
  b=self.bundle();folder=b.root/'S002';folder.mkdir();(folder/'frame-audit.jsonl').write_text('{"scene_id":"S002","frame_index":0,"webglError":1282}\n');(folder/'failed-invariant.json').write_text('{"code":"FRAME_AUDIT_FAILED","failed_invariants":["WEBGL_ERROR"]}')
  original=b.write
  def broken(name,value):
   if name=='frame-audit.json':raise OSError('injected aggregation failure')
   return original(name,value)
  with patch.object(b,'write',side_effect=broken):
   with self.assertRaises(OSError):b.finish(status='FAILED')
  d=self.unpack(b.package());self.assertIn('native-journals/S002/frame-audit.jsonl',d);self.assertEqual(d['native-journals/S002/failed-invariant.json']['failed_invariants'],['WEBGL_ERROR']);self.assertTrue(all('S%03d.json'%i in d for i in range(1,6)))
 def test_truncated_last_journal_line_does_not_destroy_zip(self):
  b=self.bundle();folder=b.root/'S002';folder.mkdir();(folder/'frame-audit.jsonl').write_text('{"scene_id":"S002","frame_index":0}\n{"incomplete":')
  d=self.unpack(b.finish(status='FAILED'));self.assertEqual(len(d['frame-audit.json']),1);self.assertEqual(d['failed-invariant.json']['SECONDARY_ERROR'][0]['code'],'TRUNCATED_AUDIT_JOURNAL');self.assertNotIn('incomplete',d['native-journals/S002/frame-audit.jsonl'])
 def test_owner_file_secret_redacted_even_after_startup_removes_environment(self):
  state=self.root/'state';state.mkdir();value='private-value-7391452';f=state/'owner-code.txt';f.write_text(value);f.chmod(0o600)
  b=DiagnosticBundle(self.root,JID,self.plan,state_root=state);b.log('stderr',value);d=self.unpack(b.finish(status='FAILED'));self.assertNotIn(value,d['stderr.txt'])
  p=node(f"import {{registerRedactionFile,redact}} from './tools/scene_diagnostic_journal.mjs';registerRedactionFile({json.dumps(str(f))});console.log(redact({json.dumps(value)}));");self.assertEqual(p.returncode,0,p.stderr);self.assertNotIn(value,p.stdout)
 def test_existing_archive_is_immutable_on_gateway_recovery(self):
  b=self.bundle();p=b.finish(status='FAILED');previous=p.read_bytes();self.assertEqual(recover_bundle(self.root,JID,'FAILED'),p);self.assertEqual(p.read_bytes(),previous)
 def test_cached_native_audit_keeps_existing_identity_fields_without_crash(self):
  b=self.bundle();folder=self.root/'renders';folder.mkdir();audit=folder/'native.json';audit.write_text('[{"scene_id":"S001","frame_index":0,"webglError":0}]')
  (folder/'scene_results.json').write_text(json.dumps({'scenes':[{'scene_id':'S001','audit':str(audit),'audit_sha256':hashlib.sha256(audit.read_bytes()).hexdigest()}]}));d=self.unpack(b.finish(status='FAILED'));self.assertEqual(d['frame-audit.json'][0]['source'],'cached_native_audit');self.assertEqual(d['frame-audit.json'][0]['errors']['not_available'],'not recorded by original cached worker')
 def test_atomic_flush_failure_does_not_replace_existing_record(self):
  from engine.gpu_bundle import durable_json
  path=self.root/'record.json';durable_json(path,{'original':True})
  with patch('engine.gpu_bundle.os.fsync',side_effect=OSError('injected disk fault')):
   with self.assertRaises(OSError):durable_json(path,{'replacement':True})
  self.assertEqual(json.loads(path.read_text()),{'original':True});self.assertFalse(list(self.root.glob('*.writing')))

class ProcessEvidenceTests(unittest.TestCase):
 setUp=BundleTests.setUp
 bundle=BundleTests.bundle
 def test_real_ffmpeg_exit_and_duration_recorded_without_changing_result(self):
  b=self.bundle()
  with b.record_processes():p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=size=32x32:duration=0.1','-f','null','-'],capture_output=True)
  self.assertEqual(p.returncode,0);rows=json.loads((b.root/'subprocess-diagnostics.json').read_text());self.assertEqual(rows[0]['return_code'],0);self.assertGreater(rows[0]['duration_seconds'],0)
 def test_check_true_original_exception_and_nonzero_exit_survive(self):
  b=self.bundle();original=subprocess.run
  with b.record_processes():
   with self.assertRaises(subprocess.CalledProcessError):subprocess.run(['ffmpeg','-unsupported-test-only-option'],capture_output=True,check=True)
  self.assertIs(subprocess.run,original);rows=json.loads((b.root/'subprocess-diagnostics.json').read_text());self.assertNotEqual(rows[0]['return_code'],0);self.assertEqual(rows[0]['exception_type'],'CalledProcessError')
 def test_renderer_public_tail_redacts_runtime_owner_value_after_env_removed(self):
  import sys
  from engine.backends import CPULocalBackend
  from engine.failures import RenderProcessError
  state=self.root/'state';state.mkdir();value='private_value_7931452';f=state/'owner-code.txt';f.write_text(value);f.chmod(0o600)
  b=DiagnosticBundle(self.root,JID,self.plan,state_root=state)
  with self.assertRaises(RenderProcessError) as captured:CPULocalBackend(diagnostic=b).run([sys.executable,'-c',f'import sys;print({value!r},file=sys.stderr);sys.exit(1)'],ROOT,lambda event:None)
  self.assertNotIn(value,json.dumps(captured.exception.diagnostics))
 def test_recorder_failure_does_not_replace_original_media_error(self):
  b=self.bundle()
  with patch.object(b,'write',side_effect=OSError('injected recording failure')),b.record_processes():
   with self.assertRaises(subprocess.CalledProcessError):subprocess.run(['ffmpeg','-unsupported-test-only-option'],capture_output=True,check=True)

class PreflightTests(unittest.TestCase):
 def create(self,folder):
  store=ProjectStore(Path(folder)/'projects');p=make_plan();d=store.create(p['request'],p);pid=d['project']['id'];return store.version_path(pid,'v001'),store.get(pid)['plan']
 def test_all_five_suez_qa12_native_checks_and_repeat_audio_pass(self):
  from engine.gpu_preflight import collect_all
  with tempfile.TemporaryDirectory() as f:
   v,p=self.create(f);b=DiagnosticBundle(v,JID,p);r=collect_all(v,p,b);self.assertTrue(r['passed']);self.assertEqual(len(r['scenes']),5);self.assertTrue(all(s['passed'] for s in r['scenes']));self.assertEqual(r['gpu_draw'],'NOT_RUN');self.assertTrue(collect_all(v,p,b)['passed'])
 def test_collect_all_keeps_auxiliary_results_after_non_numeric_scene_duration(self):
  from engine.gpu_preflight import collect_all
  with tempfile.TemporaryDirectory() as f:
   v,p=self.create(f);p['scenes'][1]['duration']=None;b=DiagnosticBundle(v,JID,p)
   with self.assertRaisesRegex(RuntimeError,'COLLECT_ALL_PREFLIGHT_FAILED'):collect_all(v,p,b)
   report=json.loads((b.root/'preflight.json').read_text());self.assertEqual(len(report['scenes']),5);self.assertTrue(any(c['name']=='Audio_Subtitle' for c in report['checks']));self.assertFalse(next(c for c in report['checks'] if c['name']=='Concat_QC_policy')['passed'])
 def test_collect_all_continues_after_bad_s002(self):
  from engine.gpu_preflight import collect_all
  with tempfile.TemporaryDirectory() as f:
   v,p=self.create(f);p['scenes'][1]['duration']=float('nan');b=DiagnosticBundle(v,JID,p)
   with self.assertRaisesRegex(RuntimeError,'COLLECT_ALL_PREFLIGHT_FAILED'):collect_all(v,p,b)
   r=json.loads((b.root/'preflight.json').read_text());self.assertEqual(len(r['scenes']),5);self.assertFalse(r['scenes'][1]['passed']);self.assertTrue(r['scenes'][-1]['passed'])
if __name__=='__main__':unittest.main()
