import json,subprocess,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from engine.qa_planner import generate_deployment_plan
from engine.single_event_camera import validate_camera,ROOT,PRESET

class SingleEventCamera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema,visibility,gpu_preflight
        cls.saved=(schema.validate_plan,gpu_preflight.validate_plan,schema.SCHEMA_PATH,visibility.TOOL)
        cls.plan=generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=12,qa_mode=True,direction_profile=PRESET,quality='HIGH',tts=False,subtitles=False,bgm=True,sfx=True))
    @classmethod
    def tearDownClass(cls):
        from engine import schema,visibility,gpu_preflight
        schema.validate_plan,gpu_preflight.validate_plan,schema.SCHEMA_PATH,visibility.TOOL=cls.saved
    def test_timeline(self):
        s=self.plan['scenes'][0];self.assertEqual([(x['state'],x['start_frame'],x['end_frame']) for x in s['single_event_camera']['timeline']],[('WIDE',0,60),('EVENT_LOCATION',60,90),('ZOOM_IN',90,150),('SETTLE',150,180),('EVENT_REVEAL',180,240),('EVENT_HOLD',240,360)])
    def test_integer_total(self):self.assertEqual(self.plan['scenes'][0]['frame_count'],360)
    def test_one_scene_one_event(self):self.assertEqual(len(self.plan['scenes']),1);self.assertEqual([e['kind'] for e in self.plan['scenes'][0]['visual_events']],['city_reveal','route_blocked'])
    def test_directors_absent(self):self.assertNotIn('direction',self.plan['scenes'][0])
    def test_plan_gate(self):self.assertTrue(self.plan['gate']['passed'],self.plan['gate']['errors'])
    def test_extra_state_rejected(self):
        p=deepcopy(self.plan);p['scenes'][0]['single_event_camera']['timeline'].append(dict(state='ORBIT'));self.assertFalse(validate_camera(p)['passed'])
    def test_foreign_move_rejected(self):
        p=deepcopy(self.plan);p['scenes'][0]['camera_end']['lon']+=1;self.assertFalse(validate_camera(p)['passed'])
    def test_real_camera_math_full_360(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'plan.json';p.write_text(json.dumps(self.plan));r=subprocess.run(['node','tools/test_single_event_camera.mjs',str(p)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);out=json.loads(r.stdout);self.assertTrue(out['passed']);self.assertGreater(out['event']['earth_screen_occupancy'],out['wide']['earth_screen_occupancy']*2)
    def test_command_selection(self):
        from engine.single_event_backend import single_command
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'scene.json';p.write_text(json.dumps(self.plan['scenes'][0]));command=single_command(['node','render_production_scene.mjs','--scene-json',str(p),'--url','http://127.0.0.1/static/render_production_earth.html']);self.assertIn('http://127.0.0.1/static/render_single_event_earth.html',command)

    def test_image_default_selects_single_camera(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{'WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST':'1'}):
            p=generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=12,qa_mode=True,direction_profile='REFERENCE_MASTER',quality='HIGH',tts=False,subtitles=False,bgm=True,sfx=True))
        self.assertEqual(p['request']['direction_profile'],PRESET)
        self.assertEqual(p['scenes'][0]['frame_count'],360)
