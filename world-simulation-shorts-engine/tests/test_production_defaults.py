"""Approved-renderer selection, real local pacing and legacy-plan isolation."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engine.pace import apply_scene_pace,retime_scene_plan,analyze_dead_time,normalize_pace,frame_time
from engine.production import apply_production_defaults,requested_production_profile,production_default_status,validate_production_plan
from engine.retention import analyze_retention
from engine.schema import validate_plan,SCHEMA_PATH
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]
APPROVED=ROOT.parent/'deliverables/WORLD_SIMULATION_ENGINE/PREMIUM_FLAT_MAP_15S_v004/scene_plan.json'

class ProductionDefaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=json.loads(APPROVED.read_text())

    def sample(self,pace='FAST'):
        source=deepcopy(self.original)
        source['scenes'][2]['narration']='타이베이로 바뀐다면?'
        source['scenes'][4]['narration']='세 도시가 연결됩니다.'
        return apply_production_defaults(retime_scene_plan(source,[2.5,2.5,2.5,2.5,2.0]),pace=pace,final_context_node='Shanghai')

    def test_source_approved_version_is_not_mutated(self):
        before=json.dumps(self.original,sort_keys=True)
        self.sample()
        self.assertEqual(json.dumps(self.original,sort_keys=True),before)
        self.assertNotIn('production_defaults',self.original)

    def test_fast_scene_timing_not_video_speed_or_tts_speed(self):
        source=self.original['scenes'][0]
        fast,proof=apply_scene_pace(source,'FAST')
        normal,_=apply_scene_pace(source,'NORMAL')
        cinema,_=apply_scene_pace(source,'CINEMATIC')
        self.assertEqual(fast['duration'],source['duration'])
        self.assertEqual(fast['narration'],source['narration'])
        self.assertEqual(fast['entities'][0]['end_time'],source['entities'][0]['end_time'])
        self.assertTrue(proof['entity_display_lifetime_preserved'])
        self.assertEqual(fast['motion_timing']['camera_speed_reference'],source['camera_speed'])
        self.assertEqual(fast['routes'][0]['points'],source['routes'][0]['points'])
        self.assertLess(fast['routes'][0]['end_time'],normal['routes'][0]['end_time'])
        self.assertLess(fast['motion_timing']['camera_travel_duration'],normal['motion_timing']['camera_travel_duration'])
        self.assertLess(normal['motion_timing']['camera_travel_duration'],cinema['motion_timing']['camera_travel_duration'])
        self.assertEqual(fast['motion_timing']['tts_playback_rate'],1.0)
        self.assertFalse(proof['ffmpeg_speed_filter'])

    def test_optional_scene_retime_changes_all_clocks_keeps_shared_state(self):
        source=deepcopy(self.original)
        source['scenes'][2]['narration']='타이베이로 바뀐다면?';source['scenes'][4]['narration']='세 도시가 연결됩니다.'
        output=retime_scene_plan(source,[2.5,2.5,2.5,2.5,2.0])
        self.assertEqual(output['duration'],12)
        self.assertEqual([s['start_time'] for s in output['scenes']],[0,2.5,5,7.5,10])
        self.assertEqual(output['scenes'][2]['flat_map']['next_event']['event_time'],round(.95*2.5/3,6))
        for old,new in zip(source['scenes'],output['scenes']):
            self.assertEqual(old['camera_end'],new['camera_end'])
            self.assertEqual(old['routes'][0]['progress_end'],new['routes'][0]['progress_end'])
        for previous,current in zip(output['scenes'],output['scenes'][1:]):
            self.assertEqual(previous['exit_state'],current['entry_state'])

    def test_retime_rejects_unreadable_narration_instead_of_accelerating_tts(self):
        with self.assertRaisesRegex(ValueError,'NARRATION_TOO_LONG'):
            retime_scene_plan(self.original,[2.5,2.5,2.5,2.5,2.0])

    def test_approved_v004_and_minimal_geographic_text(self):
        sample=self.sample()
        for scene in sample['scenes']:
            self.assertEqual(scene['visual_polish']['version'],'v004')
            if scene['render_mode']=='FLAT_MAP_PREMIUM':self.assertEqual(scene['visual_polish']['entity_separation'],'v1')
            self.assertEqual(scene['text_density'],'MINIMAL')
            self.assertFalse(scene['production_defaults']['large_titles'])
            self.assertFalse(any(text['role']=='title' for text in scene['text_events']))
            self.assertFalse(any('THREE CITIES' in event.get('text','') for event in scene['visual_events']))
        self.assertEqual(sample['scenes'][-1]['visual_mode'],'HERO')
        self.assertTrue(any(text['role']=='question' and text['text']=='NEXT?' for text in sample['scenes'][0]['text_events']))
        self.assertEqual(sample['scenes'][2]['text_events'][0]['text'],'ARRIVED')
        self.assertTrue(any(text['text']=='ASSUMPTION' for text in sample['scenes'][2]['text_events']))

    def test_country_reveal_does_not_count_an_already_activated_tint(self):
        sample=self.sample();scene=sample['scenes'][1]
        event=next(e for e in scene['visual_events'] if e['id']=='E006')
        selected=next(h for h in scene['flat_map']['country_highlights'] if h['country']=='JPN')
        self.assertEqual(selected['start_time'],event['time'])
        colors={h['country']:h['color'] for s in sample['scenes'] for h in s.get('flat_map',{}).get('country_highlights',[])}
        self.assertEqual(len(set(colors.values())),len(colors))

    def test_final_payoff_activates_a_fresh_verified_edge_and_read_hold(self):
        sample=self.sample();scene=sample['scenes'][-1]
        event=next(e for e in scene['visual_events'] if e['kind']=='final_reveal')
        route=next(r for r in scene['routes'] if r['route_id']==event['target_id'])
        self.assertEqual(route['progress_start'],0)
        self.assertEqual(route['start_time'],event['time'])
        self.assertGreaterEqual(scene['duration']-event['time'],.8-1e-6)
        self.assertTrue(route['faint'])
        self.assertEqual(route['source_ids'],['natural_earth_places'])

    def test_plan_passes_all_actual_numeric_gates(self):
        sample=self.sample()
        report=validate_plan(sample)
        self.assertTrue(report['passed'],report['errors'])
        self.assertTrue(report['semantic_visibility']['passed'])
        self.assertTrue(analyze_dead_time(sample)['passed'])
        retention=analyze_retention(sample)
        self.assertTrue(retention['passed'],retention['errors'])
        self.assertFalse(retention['metrics']['camera_events_counted'])
        self.assertGreaterEqual(retention['metrics']['average_event_interval'],1)

    def test_production_gate_rejects_long_transition_and_camera_only_dead_time(self):
        sample=self.sample();sample['scenes'][3]['map_transition']['duration']=1.2
        sample['scenes'][1]['visual_events']=[]
        codes={e['code'] for e in analyze_dead_time(sample)['errors']}
        self.assertIn('DEAD_TIME_LONG_TRANSITION',codes)
        self.assertIn('DEAD_TIME_CAMERA_ONLY_OR_UNCHANGED',codes)

    def test_legacy_optional_fields_and_saved_plan_are_schema_compatible(self):
        validator=Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
        self.assertFalse(list(validator.iter_errors(self.original)))
        self.assertFalse(list(validator.iter_errors(self.sample())))
        invalid=self.sample();invalid['scenes'][0]['pace']='DOUBLE_SPEED'
        self.assertTrue(list(validator.iter_errors(invalid)))
        invalid=self.sample();invalid['scenes'][0]['motion_timing']['tts_playback_rate']=1.2
        self.assertTrue(list(validator.iter_errors(invalid)))
        self.assertEqual(validate_production_plan(self.original),dict(passed=True,errors=[],warnings=[],legacy=True))

    def test_unpromoted_defaults_remain_legacy_explicit_candidate_and_pace_aliases(self):
        with patch('engine.production.production_default_status',return_value={'active':False}):
            self.assertIsNone(requested_production_profile({}))
            self.assertIsNone(requested_production_profile({'production_preset':'LEGACY'}))
            self.assertEqual(requested_production_profile({'production_preset':'PRODUCTION_DEFAULT_CANDIDATE'}),'PRODUCTION_DEFAULT_CANDIDATE')
            with self.assertRaisesRegex(ValueError,'NOT_PROMOTED'):requested_production_profile({'production_preset':'PRODUCTION_DEFAULT'})
        self.assertEqual(normalize_pace('PACE_FAST'),'FAST')
        self.assertEqual(normalize_pace('PACE_NORMAL'),'NORMAL')
        self.assertEqual(normalize_pace('PACE_CINEMATIC'),'CINEMATIC')
        self.assertEqual(frame_time(2.266667),round(68/30,6))

    def test_active_default_uses_production_and_explicit_legacy_retains_baseline(self):
        from engine.planner import generate_plan
        request=dict(topic='서울에서 도쿄를 거쳐 타이베이로 이동하는 민간 항공 연결',duration=20,tts=False)
        with patch('engine.production.production_default_status',return_value={'active':True,'preset':'PRODUCTION_DEFAULT'}):
            self.assertEqual(requested_production_profile(request),'PRODUCTION_DEFAULT')
            current=generate_plan(deepcopy(request))
            legacy=generate_plan({**request,'production_preset':'LEGACY'})
        self.assertTrue(current['gate']['passed'],current['gate']['errors'])
        self.assertEqual(current['production_defaults']['profile'],'PRODUCTION_DEFAULT')
        self.assertEqual(current['options']['pace'],'FAST')
        self.assertTrue(current['options']['sfx'])
        self.assertTrue(any(scene['render_mode']=='FLAT_MAP_PREMIUM' and scene['visual_polish']['version']=='v004' for scene in current['scenes']))
        self.assertTrue(legacy['gate']['passed'],legacy['gate']['errors'])
        self.assertNotIn('production_defaults',legacy)
        self.assertFalse(any('production_defaults' in scene for scene in legacy['scenes']))
        self.assertNotIn('production_preset',request)

    def test_global_aviation_shipping_and_hypothetical_planning_are_preserved(self):
        from engine.planner import generate_plan
        requests=[('서울에서 도쿄를 거쳐 타이베이로 이동하는 민간 항공 연결',20),
                  ('수에즈 운하가 7일 동안 막힌다면?',75),
                  ('만약 런던과 파리의 직접 연결이 달라진다면?',40)]
        for topic,duration in requests:
            with self.subTest(topic=topic):
                plan=generate_plan(dict(topic=topic,duration=duration,production_preset='PRODUCTION_DEFAULT_CANDIDATE'))
                self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
                self.assertEqual(plan['duration'],duration)
                self.assertTrue(plan['options']['sfx'])
                self.assertEqual(plan['options']['pace'],'FAST')
                self.assertTrue(any(text['role']=='question' for text in plan['scenes'][0]['text_events']))
                if '수에즈' in topic:
                    self.assertTrue(any(text['text']=='7 DAYS?' for text in plan['scenes'][0]['text_events']))
                    self.assertFalse(any(route['route_id'].startswith('P_FINAL_') for scene in plan['scenes'] for route in scene['routes']))
                if '런던' in topic:
                    self.assertTrue(all(scene['render_mode']=='MASTER_V3_EARTH' for scene in plan['scenes']))
                    self.assertTrue(any(row['selection']=='READABLE_MASTER_V3_COVERAGE_FALLBACK' for row in plan['metadata']['production_coverage']))

    def test_unsupported_visual_requirements_are_not_replaced_by_flat_effects(self):
        from engine.planner import generate_plan
        from engine.plugins import UnsupportedVisualRequirement
        with self.assertRaises(UnsupportedVisualRequirement) as raised:
            generate_plan(dict(topic='판게아 대륙 분리 시뮬레이션',duration=20,production_preset='PRODUCTION_DEFAULT_CANDIDATE'))
        self.assertIn('GEOGRAPHY_MORPH',raised.exception.modules)
        self.assertIn('TIME_MORPH',raised.exception.modules)

    def test_missing_or_forged_promotion_evidence_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'promotion.json'
            self.assertFalse(production_default_status(path)['active'])
            path.write_text(json.dumps(dict(version='v1',promoted=True,evidence_path='missing',evidence_sha256='fake')))
            self.assertFalse(production_default_status(path)['active'])

if __name__=='__main__':unittest.main()
