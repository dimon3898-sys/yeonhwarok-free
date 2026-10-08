import json,subprocess,tempfile,unittest,os
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from engine.return_wide_camera import PRESET,ROOT,validate_camera
from engine.qa_planner import generate_deployment_plan
from engine.return_wide_qc import camera_qc,apply_policy,PRODUCTION_ONLY

class ReturnWideCamera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema,visibility,gpu_preflight
        cls.saved=(schema.validate_plan,gpu_preflight.validate_plan,schema.SCHEMA_PATH,visibility.TOOL)
        cls.raw=dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=15,qa_mode=True,direction_profile=PRESET,quality='HIGH',tts=False,subtitles=False,bgm=True,sfx=True)
        cls.plan=generate_deployment_plan(cls.raw)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'plan.json';p.write_text(json.dumps(cls.plan));r=subprocess.run(['node','tools/test_return_wide_camera.mjs',str(p)],cwd=ROOT,capture_output=True,text=True,check=True);cls.geometry=json.loads(r.stdout)
        cls.rows=cls.geometry['audits']
    @classmethod
    def tearDownClass(cls):
        from engine import schema,visibility,gpu_preflight
        schema.validate_plan,gpu_preflight.validate_plan,schema.SCHEMA_PATH,visibility.TOOL=cls.saved
    def test_plan_gate(self):self.assertTrue(self.plan['gate']['passed'])
    def test_timeline(self):self.assertEqual([(s['state'],s['start_frame'],s['end_frame']) for s in self.plan['scenes'][0]['return_wide_camera']['timeline']],[('WIDE',0,60),('EVENT_LOCATION',60,90),('ZOOM_IN',90,150),('SETTLE',150,180),('EVENT_REVEAL',180,240),('EVENT_HOLD',240,330),('EVENT_RESOLVED',330,360),('ZOOM_OUT',360,420),('FINAL_WIDE',420,450)])
    def test_frame_total(self):self.assertEqual(self.plan['metadata']['frame_grid']['total_frames'],450)
    def test_v015_camera_preserved(self):self.assertTrue(self.geometry['baseline_first_360_identical'])
    def test_camera_qa(self):self.assertTrue(camera_qc(self.plan,self.rows)['passed'])
    def test_missing_resolution_rejected(self):
        rows=deepcopy(self.rows)
        for row in rows[330:360]:row['labels']=[]
        self.assertIn('EVENT_RESOLVED_PRESENT',camera_qc(self.plan,rows)['failures'])
    def test_early_zoomout_rejected(self):
        rows=deepcopy(self.rows);rows[340]['cameraPosition']=[0,0,3.5];self.assertFalse(camera_qc(self.plan,rows)['passed'])
    def test_missing_final_wide_rejected(self):
        rows=deepcopy(self.rows);rows[440]['cameraFov']=48;self.assertIn('FINAL_WIDE_PRESENT',camera_qc(self.plan,rows)['failures'])
    def test_frame_gap_rejected(self):self.assertFalse(camera_qc(self.plan,self.rows[:-1])['passed'])
    def test_unexpected_state_rejected(self):
        rows=deepcopy(self.rows);rows[260]['cameraState']='ORBIT';self.assertFalse(camera_qc(self.plan,rows)['passed'])
    def test_bad_plan_grid_rejected(self):
        p=deepcopy(self.plan);p['scenes'][0]['return_wide_camera']['timeline'][-1]['end_frame']=451;self.assertFalse(validate_camera(p)['passed'])
    def test_production_policy_is_preset_scoped(self):
        technical=dict(passed=False,failures=list(PRODUCTION_ONLY));camera=camera_qc(self.plan,self.rows)
        self.assertTrue(apply_policy(self.plan,technical,camera)['passed'])
        old=deepcopy(self.plan);old['metadata']['camera_test_preset']='REFERENCE_MASTER';self.assertIs(apply_policy(old,technical,camera),technical)
    def test_technical_failures_still_block(self):
        technical=dict(passed=False,failures=list(PRODUCTION_ONLY)+['BLACK_FRAME','VIDEO_DECODE_FAILED','WEBGL_ERROR'])
        self.assertEqual(apply_policy(self.plan,technical,camera_qc(self.plan,self.rows))['failures'],['BLACK_FRAME','VIDEO_DECODE_FAILED','WEBGL_ERROR'])
    def test_bad_actual_camera_not_promoted(self):
        self.assertFalse(apply_policy(self.plan,dict(passed=False,failures=list(PRODUCTION_ONLY)),camera_qc(self.plan,self.rows[:-1]))['passed'])
    def test_image_default(self):
        with patch.dict(os.environ,{'WORLD_ENGINE_RETURN_WIDE_TEST':'1'}):p=generate_deployment_plan({**self.raw,'direction_profile':'REFERENCE_MASTER'})
        self.assertEqual(p['request']['direction_profile'],PRESET)
    def test_backend_command(self):
        from engine.return_wide_backend import return_command
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'s.json';p.write_text(json.dumps(self.plan['scenes'][0]));cmd=return_command(['node','renderer','--scene-json',str(p),'--url','http://127.0.0.1/static/render_production_earth.html']);self.assertIn('http://127.0.0.1/static/render_return_wide_earth.html',cmd)

    def test_invalid_camera_rejected_without_crash(self):
        rows=deepcopy(self.rows);rows[50]['cameraPosition']=[0,0,0];self.assertFalse(camera_qc(self.plan,rows)['passed'])
    def test_actual_diagnostic_zip_retains_camera_state(self):
        from engine.gpu_bundle import DiagnosticBundle
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            version=Path(d);(version/'scene_json').mkdir()
            (version/'scene_plan.json').write_text(json.dumps(self.plan))
            bundle=DiagnosticBundle(version,'job_0123456789ab',self.plan)
            folder=bundle.root/'S001';folder.mkdir()
            (folder/'frame-audit.jsonl').write_text(json.dumps(self.rows[330])+'\n')
            bundle.finish(status='failed',error={'code':'TEST_INJECTED_FAILURE'})
            with zipfile.ZipFile(bundle.package()) as archive:
                rows=json.loads(archive.read('frame-audit.json'))
                self.assertEqual(rows[0]['cameraState'],'EVENT_RESOLVED')
                self.assertEqual(rows[0]['cameraFrame'],330)
