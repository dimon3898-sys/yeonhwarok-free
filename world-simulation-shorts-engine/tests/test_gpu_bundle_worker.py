"""Actual worker state/packaging boundaries with injected render outcomes, no GPU."""
import json,signal,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from deployment.mobile_server import worker
from deployment.security import private_json
from engine.storage import ProjectStore,plan_hash
from engine.gpu_bundle import DiagnosticBundle
from engine.failures import RenderProcessError
from tests.test_gpu_bundle import make_plan,JID
class WorkerBundleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.store=ProjectStore(self.root/'projects');p=make_plan();d=self.store.create(p['request'],p);self.pid=d['project']['id'];self.plan=self.store.get(self.pid)['plan'];self.store.approve(self.pid,'v001',self.plan['plan_hash']);self.version=self.store.version_path(self.pid,'v001');self.ticket=self.root/'jobs'/(JID+'.json')
  private_json(self.ticket,{'job_id':JID,'project_id':self.pid,'version':'v001','plan_hash':plan_hash(self.plan),'internal_url':'http://127.0.0.1:8001','selected_scene_ids':[s['scene_id'] for s in self.plan['scenes']]});previous=signal.getsignal(signal.SIGTERM);self.addCleanup(signal.signal,signal.SIGTERM,previous)
 def archive(self):
  path=self.version/'diagnostics'/JID/f'WORLD_ENGINE_GPU_DIAGNOSTIC_{JID}.zip';self.assertTrue(zipfile.is_zipfile(path));return path
 def failed_render(self,folder,plan,url,progress,**kwargs):
  progress({'stage':'scene_start','scene_id':'S002'});bundle=kwargs['diagnostic'];sub=bundle.root/'S002';sub.mkdir();private_json(sub/'failed-invariant.json',{'code':'FRAME_AUDIT_FAILED','scene_id':'S002','frame_index':0,'failed_invariants':['WEBGL_ERROR']})
  raise RenderProcessError(returncode=1,duration=2.577,stderr=['WORLD_ENGINE_RENDER_FAILURE '+json.dumps({'code':'FRAME_AUDIT_FAILED','frame_index':0,'failed_invariants':['WEBGL_ERROR']})])
 def test_failed_worker_packages_before_mobile_polling_can_finish(self):
  original=DiagnosticBundle.finish
  def finish(bundle,**values):
   self.assertTrue(self.store.status(self.pid,'v001')['diagnostic_pending']);self.assertEqual(values['error']['subprocess']['root_cause']['failed_invariants'],['WEBGL_ERROR']);return original(bundle,**values)
  with patch('engine.pipeline_stability.render_project',side_effect=self.failed_render),patch.object(DiagnosticBundle,'finish',finish):self.assertEqual(worker(self.ticket,self.root),1)
  state=self.store.status(self.pid,'v001');self.assertEqual(state['status'],'failed');self.assertFalse(state['diagnostic_pending']);self.archive()
 def test_success_worker_packages_qc_and_scenes_without_fake_gpu_pass(self):
  with patch('engine.pipeline_stability.render_project',return_value={'qc':{'passed':True},'outputs':{},'metrics':{}}),patch('deployment.resume_evidence.finalize_resume_evidence',return_value={'scope':'injected success only'}):self.assertEqual(worker(self.ticket,self.root),0)
  state=self.store.status(self.pid,'v001');self.assertEqual(state['status'],'complete');self.assertFalse(state['diagnostic_pending'])
  with zipfile.ZipFile(self.archive()) as z:self.assertTrue(json.loads(z.read('qc.json'))['passed']);self.assertTrue(all(f'S{i:03}.json' in z.namelist() for i in range(1,6)))
 def test_aggregate_failure_still_exports_native_failed_invariant(self):
  with patch('engine.pipeline_stability.render_project',side_effect=self.failed_render),patch.object(DiagnosticBundle,'finish',side_effect=OSError('injected aggregation failure')):self.assertEqual(worker(self.ticket,self.root),1)
  with zipfile.ZipFile(self.archive()) as z:self.assertEqual(json.loads(z.read('native-journals/S002/failed-invariant.json'))['failed_invariants'],['WEBGL_ERROR'])
  self.assertEqual(self.store.status(self.pid,'v001')['error']['code'],'SCENE_RENDERER_EXIT')
if __name__=='__main__':unittest.main()
