import json,subprocess,tempfile,unittest,os,math
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from engine.second_event_camera import PRESET,ROOT,validate_camera,TIMELINE
from engine.qa_planner import generate_deployment_plan
from engine.second_event_qc import camera_qc,apply_policy
from engine.return_wide_qc import PRODUCTION_ONLY

class SecondEventCamera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema,visibility,gpu_preflight
        cls.saved=(schema.validate_plan,gpu_preflight.validate_plan,schema.SCHEMA_PATH,visibility.TOOL)
        cls.raw=dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=24,qa_mode=True,direction_profile=PRESET,quality='HIGH',tts=False,subtitles=False,bgm=True,sfx=True)
        cls.plan=generate_deployment_plan(cls.raw)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'plan.json';p.write_text(json.dumps(cls.plan));r=subprocess.run(['node','tools/test_second_event_camera.mjs',str(p)],cwd=ROOT,capture_output=True,text=True,check=True);cls.geometry=json.loads(r.stdout)
        cls.rows=cls.geometry['audits']
    @classmethod
    def tearDownClass(cls):
        from engine import schema,visibility,gpu_preflight
        schema.validate_plan,gpu_preflight.validate_plan,schema.SCHEMA_PATH,visibility.TOOL=cls.saved
    def test_gate(self):self.assertTrue(self.plan['gate']['passed'])
    def test_exact_grid(self):
        self.assertEqual(self.plan['metadata']['frame_grid']['total_frames'],720);self.assertEqual(sum(b-a for _,a,b in TIMELINE),720)
        self.assertTrue(all(TIMELINE[i-1][2]==a for i,(_,a,b) in enumerate(TIMELINE) if i))
    def test_first_360_preserved(self):self.assertTrue(self.geometry['baseline_first_360_identical'])
    def test_camera_qa(self):self.assertTrue(camera_qc(self.plan,self.rows)['passed'])
    def test_context_closer_than_old_wide(self):self.assertLess(self.plan['scenes'][0]['second_event_camera']['adaptive_camera']['height'],2.5)
    def test_adaptive_wide(self):
        c=self.plan['scenes'][0]['second_event_camera'];self.assertEqual(c['adaptive_wide']['wide_type'],'CONTINENT_WIDE');self.assertTrue(c['adaptive_wide']['current_screen']['in_safe_area'] and c['adaptive_wide']['next_screen']['in_safe_area'])
    def test_location_after_wide(self):self.assertEqual(self.plan['scenes'][0]['labels'][1]['start_time'],15)
    def test_no_duplicate_singapore_label(self):
        s=self.plan['scenes'][0];self.assertEqual(sum(x['text']=='SINGAPORE' for x in s['labels']+s['text_events']),1)
    def test_no_new_audio(self):self.assertEqual([x['time'] for x in self.plan['scenes'][0]['sound_events']],[2,6])
    def test_three_major_motions_only(self):
        changes=[i for i in range(1,720) if self.rows[i]['cameraPosition']!=self.rows[i-1]['cameraPosition'] or self.rows[i]['cameraFov']!=self.rows[i-1]['cameraFov']]
        self.assertTrue(all(90<=i<=150 or 360<=i<=420 or 495<=i<=585 for i in changes))
    def test_missing_state_fails(self):
        rows=deepcopy(self.rows);rows[450]['cameraState']='ZOOM_OUT';self.assertFalse(camera_qc(self.plan,rows)['passed'])
    def test_early_singapore_fails(self):
        rows=deepcopy(self.rows);rows[419]['labels']=[dict(text='SINGAPORE',opacity=1)];self.assertIn('LOCATION_AFTER_WIDE_LOCK',camera_qc(self.plan,rows)['failures'])
    def test_unexpected_rotation_fails(self):
        rows=deepcopy(self.rows);rows[600]['cameraQuaternion']=[0,0,0,1];self.assertIn('NO_UNEXPECTED_ROTATION',camera_qc(self.plan,rows)['failures'])
    def test_missing_hold_fails(self):
        rows=deepcopy(self.rows);rows[700]['cameraFov']=64;self.assertIn('EVENT2_HOLD_PRESENT',camera_qc(self.plan,rows)['failures'])
    def test_invalid_camera_fails(self):
        rows=deepcopy(self.rows);rows[550]['cameraPosition']=[0,0,0];self.assertFalse(camera_qc(self.plan,rows)['passed'])
    def test_missing_frame_fails(self):self.assertFalse(camera_qc(self.plan,self.rows[:-1])['passed'])
    def test_null_camera_fails_without_crash(self):
        rows=deepcopy(self.rows);rows[550].update(cameraPosition=None,cameraQuaternion=None,cameraFov=None);self.assertFalse(camera_qc(self.plan,rows)['passed'])
    def test_bad_plan_fails(self):
        p=deepcopy(self.plan);p['scenes'][0]['second_event_camera']['timeline'][7]['end_frame']=449;self.assertFalse(validate_camera(p)['passed'])
    def test_malformed_config_fails(self):
        p=deepcopy(self.plan);p['scenes'][0]['second_event_camera']['next_coordinates']={};self.assertFalse(validate_camera(p)['passed'])
    def test_null_config_fails(self):
        p=deepcopy(self.plan);p['scenes'][0]['second_event_camera']=None;self.assertFalse(validate_camera(p)['passed'])
    def test_scoped_policy(self):
        t=dict(passed=False,failures=list(PRODUCTION_ONLY));c=camera_qc(self.plan,self.rows);self.assertTrue(apply_policy(self.plan,t,c)['passed'])
        p=deepcopy(self.plan);p['metadata']['camera_test_preset']='SINGLE_EVENT_RETURN_TO_WIDE_TEST';self.assertIs(apply_policy(p,t,c),t)
    def test_all_technical_failures_block(self):
        t=dict(passed=False,failures=list(PRODUCTION_ONLY)+['BLACK_FRAME','VIDEO_DECODE_FAILED','WEBGL_ERROR','TEXT_CLIPPED','BROKEN_ROUTE']);c=camera_qc(self.plan,self.rows);self.assertEqual(apply_policy(self.plan,t,c)['failures'],['BLACK_FRAME','BROKEN_ROUTE','TEXT_CLIPPED','VIDEO_DECODE_FAILED','WEBGL_ERROR'])
    def test_image_existing_form(self):
        with patch.dict(os.environ,{'WORLD_ENGINE_SECOND_EVENT_TEST':'1'}):p=generate_deployment_plan({**self.raw,'direction_profile':'REFERENCE_MASTER','qa_mode':False})
        self.assertEqual(p['request']['direction_profile'],PRESET);self.assertTrue(p['request']['qa_mode'])
    def test_backend_same_gpu_transport(self):
        from engine.second_event_backend import second_command
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'s.json';p.write_text(json.dumps(self.plan['scenes'][0]));cmd=second_command(['node','renderer','--scene-json',str(p),'--url','http://127.0.0.1/static/render_production_earth.html']);self.assertIn('http://127.0.0.1/static/render_second_event_earth.html',cmd)
    def test_zip_camera_evidence(self):
        from engine.gpu_bundle import DiagnosticBundle
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            version=Path(d);(version/'scene_json').mkdir();(version/'scene_plan.json').write_text(json.dumps(self.plan));bundle=DiagnosticBundle(version,'job_0123456789ab',self.plan);folder=bundle.root/'S001';folder.mkdir();(folder/'frame-audit.jsonl').write_text(json.dumps(self.rows[615])+'\n');bundle.finish(status='failed',error={'code':'TEST_INJECTED_FAILURE'})
            with zipfile.ZipFile(bundle.package()) as archive:
                row=json.loads(archive.read('frame-audit.json'))[0];self.assertEqual(row['cameraState'],'EVENT2_HOLD');self.assertEqual(row['cameraFrame'],615)
