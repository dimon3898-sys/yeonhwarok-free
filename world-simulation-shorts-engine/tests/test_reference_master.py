"""Reference-first planning and adversarial perceptual admission, no GPU claims."""
from copy import deepcopy
import hashlib
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from engine.reference_master import (ROOT, VERSION, SOURCES, reference_blueprint,
    perception_hold, text_read_time, information_budget, perceptual_qc)
from engine.reference_backend import reference_command
from engine.qa_planner import configure_qa_schema, generate_deployment_plan
from deployment.gcube.reference_preflight import REQUESTS, run


class ReferenceFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {'WORLD_ENGINE_DIRECTION_VERSION':'v013'}):
            cls.report=run(cls.folder.name)
        cls.plans={name:json.loads((Path(cls.folder.name)/(name+'.json')).read_text()) for name in REQUESTS}
        configure_qa_schema()

    @classmethod
    def tearDownClass(cls):cls.folder.cleanup()

    def test_shipping(self):self.assertTrue(self.report['fixtures'][0]['passed'],self.report['fixtures'][0])
    def test_aviation(self):self.assertTrue(self.report['fixtures'][1]['passed'],self.report['fixtures'][1])
    def test_country(self):self.assertTrue(self.report['fixtures'][2]['passed'],self.report['fixtures'][2])
    def test_global_network(self):self.assertTrue(self.report['fixtures'][3]['passed'],self.report['fixtures'][3])
    def test_every_fixture_same_profile(self):
        self.assertEqual({s['direction']['version'] for p in self.plans.values() for s in p['scenes']},{VERSION})
    def test_four_causal_beats_not_five_equal_scenes(self):
        p=self.plans['shipping'];self.assertEqual(len(p['scenes']),4)
        self.assertGreater(len({s['duration'] for s in p['scenes']}),1)
        self.assertEqual(sum(round(s['duration']*30) for s in p['scenes']),360)
    def test_every_frame_native_camera_lock(self):
        for f in self.report['fixtures']:self.assertTrue(f['perceptual']['passed'],f['perceptual']['findings'])
    def test_no_shader_or_gpu_claim(self):
        self.assertEqual(self.report['GPU'],'NOT_RUN')
        for f in self.report['fixtures']:
            for m in f['perceptual']['metrics']:self.assertEqual(m['GPU_draw'],'NOT_RUN')
    def test_zero_planning_readability_warnings(self):
        for f in self.report['fixtures']:self.assertEqual(f['planning']['warning_count'],0)
    def test_geographic_sources_preserved(self):
        for p in self.plans.values():
            self.assertTrue(p['sources']);self.assertTrue(p['story']['claims'])
            for s in p['scenes']:self.assertTrue(s['coordinates']['source_id'])
    def test_reveal_to_next_not_settle_substitution(self):
        for p in self.plans.values():
            for s in p['scenes']:
                d=s['direction'];self.assertAlmostEqual(d['perception_hold'],s['duration']-d['reveal_time'])
                self.assertGreater(d['settle'],d['perception_hold'])
    def test_result_is_locked_and_protected(self):
        for p in self.plans.values():
            d=p['scenes'][-1]['direction'];self.assertEqual(d['intent'],'RESULT_HERO');self.assertGreaterEqual(d['perception_hold'],1.5)
    def test_no_boundary_reset(self):
        for p in self.plans.values():
            for a,b in zip(p['scenes'],p['scenes'][1:]):self.assertEqual(a['exit_state'],b['entry_state'])
    def test_profiles_are_content_independent(self):
        p=json.loads((ROOT/'data/reference_direction_profile_v013.json').read_text())
        serialized=json.dumps(p)
        for text in ('ROTTERDAM','SUEZ','SINGAPORE','SEOUL','TAIPEI'):self.assertNotIn(text,serialized.upper())
    def test_read_time_has_no_short_video_ceiling(self):self.assertGreater(text_read_time('긴 정보 설명 '*30),text_read_time('짧은 설명'))
    def test_complexity_increases_hold(self):self.assertGreater(perception_hold('ROUTE_CHANGE','ROUTE',route_complexity=6,entity=True,density=2),perception_hold('LOCATION','ROUTE'))
    def test_support_removed_before_read_time_shortened(self):self.assertIsNone(information_budget('LOCATION',support='Long support data',available=.8)['support'])
    def test_budget_rejects_unreadable_long_primary(self):
        from engine.planner import PlanningInputError
        with self.assertRaises(PlanningInputError):reference_blueprint(dict(REQUESTS['shipping'],duration=8))
    def test_75s_planning_minimums_not_proportionally_scaled(self):
        b=reference_blueprint(dict(REQUESTS['shipping'],duration=75,qa_mode=False))
        self.assertEqual(b['bounds'][-1],75)
        self.assertGreater(len(b['beats']),4)
        for beat in b['beats']:self.assertGreaterEqual(beat['duration']-beat['move']-.6,beat['minimum_hold']-1e-5)
    def test_75s_full_geographic_plan_without_render(self):
        with patch.dict(os.environ,{'WORLD_ENGINE_DIRECTION_VERSION':'v013'}):
            p=generate_deployment_plan(dict(REQUESTS['shipping'],duration=75,qa_mode=False,direction_profile='REFERENCE_MASTER',quality='HIGH',pace='FAST_PLUS',tts=False,subtitles=False,bgm=True,sfx=True))
        configure_qa_schema()
        self.assertTrue(p['gate']['passed'],p['gate']['errors']);self.assertTrue(p['metadata']['reference_native_qc']['passed'],p['metadata']['reference_native_qc']['findings'])

    def test_actual_metric_capture_installed(self):
        source=(ROOT/'web/reference_visual_adapter.js').read_text()
        for field in ('reveal_to_next_move','text_visibility','pixel_metrics','earth_screen_occupancy','route_head_contrast'):self.assertIn(field,source)
    def test_wrong_source_hash_refused_before_launch(self):
        s=deepcopy(self.plans['shipping']['scenes'][0]);s['direction']['source_hashes'][SOURCES[0]]='0'*64
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'scene.json';file.write_text(json.dumps(s))
            with self.assertRaisesRegex(RuntimeError,'SOURCE_MISMATCH'):reference_command(['node','render_production_scene.mjs','--scene-json',str(file),'--url','http://localhost:8000/render_production_earth.html'])
    def test_reference_hold_excludes_motion_overlap(self):
        p=json.loads((ROOT/'data/reference_direction_profile_v013.json').read_text())
        for beat in p['beats']:
            self.assertEqual(beat['perception_hold'],beat['stationary_after_reveal'])
            if beat['motion_overlap_after_reveal']:self.assertLess(beat['perception_hold'],beat['reveal_to_next_new_move'])

    def test_actual_telemetry_uses_observed_pose_and_visibility(self):
        result=subprocess.run(['node',str(ROOT/'tests/reference_telemetry.mjs')],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertIn('PASS',result.stdout)

    def test_current_source_hashes_bound(self):
        for s in self.plans['shipping']['scenes']:
            for name,digest in s['direction']['source_hashes'].items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)

    def reject(self,mutate,code):
        p=deepcopy(self.plans['shipping']);mutate(p['scenes'][1]);q=perceptual_qc(p)
        self.assertFalse(q['passed']);self.assertIn(code,[x['code'] for x in q['findings']])
    def test_short_hold_refused(self):self.reject(lambda s:s['direction'].update(required_hold=99),'EVENT_NOT_HELD_LONG_ENOUGH')
    def test_reveal_while_moving_refused(self):self.reject(lambda s:s['direction'].update(reveal_time=.1),'CAMERA_MOVING_DURING_REVEAL')
    def test_motion_fatigue_refused(self):self.reject(lambda s:s['direction'].update(move_end=9),'MOTION_FATIGUE')
    def test_multiple_primaries_refused(self):self.reject(lambda s:s['direction']['information'].update(primary_limit=2),'INFORMATION_OVERLOAD')
    def test_long_text_without_read_time_refused(self):self.reject(lambda s:s['text_events'][0].update(text='Long unreadable explanation '*40),'TEXT_NOT_READABLE_LONG_ENOUGH')
    def test_low_route_size_refused(self):self.reject(lambda s:s['direction'].update(route_width_1080=.1),'ROUTE_NOT_VISIBLE')
    def test_small_entity_refused(self):self.reject(lambda s:s['direction'].update(entity_min_pixels_1080=2),'ENTITY_NOT_TRACKABLE')
    def test_darkness_policy_refused(self):self.reject(lambda s:s['direction']['lighting'].update(surface_fill=0),'GEOGRAPHY_READABILITY_POLICY_INVALID')
    def test_misaligned_event_sound_refused(self):self.reject(lambda s:s['sound_events'][0].update(time=99),'SFX_EVENT_MISALIGNMENT')
    def test_safe_area_refused(self):self.reject(lambda s:s['direction'].update(safe_area=[0,0,1,1]),'TEXT_OUTSIDE_SAFE_AREA')
    def test_invalid_camera_refused(self):self.reject(lambda s:s['camera_end'].update(height=float('nan')),'INVALID_CAMERA')
    def test_legacy_profile_keeps_v012_sources(self):
        with patch.dict(os.environ,{'WORLD_ENGINE_DIRECTION_VERSION':'v013'}):
            p=generate_deployment_plan(dict(REQUESTS['shipping'],direction_profile='FAST_PLUS_LEGACY',quality='HIGH',pace='FAST_PLUS',tts=False,subtitles=False,bgm=True,sfx=True))
        configure_qa_schema()
        from engine.direction import VERSION as legacy_version
        self.assertEqual({s['direction']['version'] for s in p['scenes']},{legacy_version})
        self.assertEqual(len(p['scenes']),5)

    def test_profile_is_visible_in_ui(self):self.assertIn('REFERENCE_MASTER',(ROOT/'web/app.js').read_text());self.assertIn('FAST_PLUS_LEGACY',(ROOT/'web/app.js').read_text())


if __name__=='__main__':unittest.main()
