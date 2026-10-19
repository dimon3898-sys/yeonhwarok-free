"""Private metadata and real frozen loader tests; parent renderer is never run."""
import importlib.util,json,os,sys,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import execution_manager
spec=importlib.util.spec_from_file_location('_handoff_bridge',HERE/'runtime_bridge.py');bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
class ExecutionHandoffTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='unified-handoff-');self.root=Path(self.tmp.name)
  self.plan=json.loads((HERE.parent/'verified-front-data-v4-recovery/VIDEO_PLAN_80S.json').read_bytes())
  self.sub={'videoPlan':self.plan,'profile':'V4_ARCHIVAL_80S','integration':{'schema':'WORLD_ENGINE_UNIVERSAL_INTEGRATION_V1','profile':'VISUAL_UNIFIED_V1','visualProfile':{
   'territoryOpacity':.74,'frontCoreWidthPixels':6.4,'frontGlowRadiusPixels':14,'frontGlowGain':.58,'cameraApproachFrames':72}}}
  self.digest=self.plan['renderProfile']['imageDigest'];self.req=bridge.prepare_runtime_request(self.sub,image_digest=self.digest)
  rt=execution_manager.runtime()
  with rt._cache().PrivateTree(self.root) as p:p.write_json('INTEGRATION_REQUEST.json',self.req)
  self.file=self.root/'INTEGRATION_REQUEST.json'
 def tearDown(self):self.tmp.cleanup()
 def test_frozen_worker_instance_uses_only_new_capture_entry(self):
  rt=execution_manager.runtime();self.assertEqual(rt.HERE,HERE)
  self.assertEqual(rt.PROFILES['V4_ARCHIVAL_80S'],'universal-integration-v1')
  self.assertEqual(rt.RECOVERY,HERE.parent)
 def test_request_identity_read_and_environment_restored(self):
  original=os.environ.get(execution_manager.ENV)
  with execution_manager.request_environment(self.file):self.assertEqual(execution_manager.read_request(),self.req)
  self.assertEqual(os.environ.get(execution_manager.ENV),original)
 def test_changed_visual_sidecar_rejected(self):
  rt=execution_manager.runtime();bad=dict(self.req);bad['imageDigest']='sha256:'+'0'*64
  with rt._cache().PrivateTree(self.root) as p:p.write_json('INTEGRATION_REQUEST.json',bad,replace=True)
  with execution_manager.request_environment(self.file),self.assertRaisesRegex(RuntimeError,'INTEGRATION_PRIVATE_REQUEST_CHANGED'):
   execution_manager.read_request()
 def test_parent_renderer_receives_same_plan_and_source_sidecar(self):
  spec=importlib.util.spec_from_file_location('_handoff_adapter',HERE/'render_adapter.py');adapter=importlib.util.module_from_spec(spec);sys.modules[spec.name]=adapter;spec.loader.exec_module(adapter)
  rt=execution_manager.runtime()
  with rt._cache().PrivateTree(self.root) as p:
   with p.child('attempt',create=True) as attempt:output=attempt.path
  # Explicit CPU spy replaces only the parent invocation; no hardware PASS.
  with execution_manager.request_environment(self.file),patch.object(execution_manager,'authorize_request',return_value=None),patch.object(adapter.parent,'render_segment',return_value={'testOnly':True}) as spy:
   result=adapter.render_segment(self.plan,self.plan['scenes'][0],output,approval={})
  self.assertTrue(result['testOnly']);self.assertEqual(spy.call_args.args[0],self.plan)
  with rt._cache().PrivateTree(output) as p:self.assertEqual(p.json('INTEGRATION_REQUEST.json'),self.req)
 def test_isolated_worker_finds_actual_frozen_audio_and_delivery(self):
  code="import sys,json,pathlib;sys.path.insert(0,sys.argv[1]);import execution_manager;rt=execution_manager.runtime();import studio_delivery;plan=json.loads((pathlib.Path(sys.argv[1]).parent/'verified-front-data-v4-recovery/VIDEO_PLAN_80S.json').read_bytes());result=rt._normalized_audio({'enabled':False},plan);assert result['enabled'] is False"
  r=subprocess.run([sys.executable,'-I','-B','-c',code,str(HERE)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  self.assertEqual(r.returncode,0,r.stderr.decode())
 def test_direct_start_cannot_bypass_source_data_gate(self):
  before=sorted(p.name for p in self.root.iterdir())
  with self.assertRaisesRegex(RuntimeError,'INTEGRATION_REQUIRED_DATA_BLOCKED'):
   execution_manager.start(self.sub,None,{},'cpu-only-direct',control_root=self.root,export_root=self.root,image_digest=self.digest)
  self.assertEqual(before,sorted(p.name for p in self.root.iterdir()))
 def test_job_index_routes_status_to_capture_scope_without_scan(self):
  m=execution_manager.runtime();signature=self.req['captureSignature'];job_id='studio-'+'a'*32
  with m._cache().PrivateTree(self.root) as root:
   with root.child('runtime_inputs',create=True) as inputs:
    with inputs.child(signature,create=True) as scope:scope.write_json('INTEGRATION_REQUEST.json',self.req)
  execution_manager._index_job(self.root,job_id,signature)
  with patch.object(m,'studio_status',return_value={'state':'CPU_TEST_ONLY'}) as spy:
   result=execution_manager.status(job_id,control_root=self.root,export_root=self.root)
  self.assertEqual(result['state'],'CPU_TEST_ONLY')
  self.assertEqual(spy.call_args.kwargs['control_root'],self.root/'runtime_inputs'/signature)
  with self.assertRaisesRegex(RuntimeError,'INTEGRATION_JOB_SCOPE_COLLISION'):
   execution_manager._index_job(self.root,job_id,'b'*64)
if __name__=='__main__':unittest.main()
