"""Protect partial rendering, real metrics and opt-in legacy behavior."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from engine.assets import renderer_version
from engine.rendering import scene_cache_key
from engine.rhythm import apply_rhythm_policy,route_rhythm_progress,ramp_phase,DEFAULT_KNOTS
from engine.planner import refresh_clock_dependent_route_information,generate_plan
from engine.gis import great_circle_distance

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'projects-production-default-v1/project_f185ebb678ea/versions/v003/scene_plan.json'
# The publicly preserved same plan supports a clean repository checkout too.
if not SOURCE.is_file():SOURCE=ROOT.parent/'deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/scene_plan.json'


class RhythmIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=json.loads(SOURCE.read_text())

    def test_earth_pixel_input_and_old_approved_source_are_preserved(self):
        old=deepcopy(self.original);new=apply_rhythm_policy(old,preserve_earth_pixels=True)
        self.assertEqual(old,self.original)
        a=old['scenes'][-1];b=new['scenes'][-1]
        self.assertEqual(renderer_version(a),renderer_version(b))
        key=lambda s:scene_cache_key(s,{'assets':[]},{'fps':30},renderer_version(s))
        self.assertEqual(key(a),key(b))
        self.assertTrue(all('rhythm_visual' in s for s in new['scenes'][:-1]))
        self.assertNotIn('rhythm_visual',b)

    def test_audio_and_microbeat_changes_reuse_pixels_but_real_motion_invalidates(self):
        scene=apply_rhythm_policy(self.original,preserve_earth_pixels=True)['scenes'][0]
        key=lambda s:scene_cache_key(s,{'assets':[]},{'fps':30},renderer_version(s))
        audio=deepcopy(scene);audio['sound_events'][0]['gain']=.001
        audio['rhythm_micro_beats'][0]['music_energy']=.1
        self.assertEqual(key(scene),key(audio))
        visual=deepcopy(scene);visual['rhythm_visual']['camera']['knots'][1]['speed']=.8
        self.assertNotEqual(key(scene),key(visual))
        visual=deepcopy(scene);visual['text_events'][0]['text']='OTHER'
        self.assertNotEqual(key(scene),key(visual))

    def test_native_route_metric_changes_with_the_actual_component_clock(self):
        scene=apply_rhythm_policy(self.original,preserve_earth_pixels=True)['scenes'][1]
        event=next(e for e in scene['visual_events'] if e['kind']=='milestone_reveal')
        route=next(r for r in scene['routes'] if r['route_id']==event['target_id'])
        length=sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:]))
        self.assertEqual(event['value'],round(length*(1-route_rhythm_progress(scene,route,event['time']))))
        self.assertNotEqual(event['value'],599)
        trial=deepcopy(scene);trial['rhythm_visual']['routes'][0]['knots']=[{'phase':0,'speed':1},{'phase':1,'speed':1}]
        metric=refresh_clock_dependent_route_information(trial,trial['visual_events'][0])
        self.assertEqual(metric['progress'],route_rhythm_progress(trial,trial['routes'][0],metric['time']))

    def test_ramps_preserve_exact_endpoints_and_native_easing(self):
        scene=apply_rhythm_policy(self.original,preserve_earth_pixels=True)['scenes'][0]
        route=scene['routes'][0]
        self.assertEqual(ramp_phase(0,DEFAULT_KNOTS),0)
        self.assertEqual(ramp_phase(1,DEFAULT_KNOTS),1)
        self.assertEqual(route_rhythm_progress(scene,route,route['start_time']),route['progress_start'])
        self.assertEqual(route_rhythm_progress(scene,route,route['end_time']),route['progress_end'])
        linear=deepcopy(route);linear['speed_easing']='linear'
        t=linear['start_time']+(linear['end_time']-linear['start_time'])*.3
        self.assertNotEqual(route_rhythm_progress(scene,linear,t),route_rhythm_progress(scene,route,t))

    def test_sourced_place_hook_keeps_rendered_retention_binding(self):
        scene=apply_rhythm_policy(self.original,preserve_earth_pixels=True)['scenes'][0]
        hook=next(e for e in scene['visual_events'] if e['kind']=='hook_reveal')
        text=next(t for t in scene['labels'] if t.get('event_id')==hook['id'])
        self.assertEqual(hook['text'],'SEOUL')
        self.assertEqual(text['text'],'SEOUL')
        self.assertEqual(text['kind'],'hook_reveal')
        self.assertFalse(any(t['event_id']==hook['id'] for t in scene['text_events']))
        self.assertFalse(hook['meaningful'])

    def test_recommended_defaults_keep_explicit_user_audio_and_pace_choices(self):
        status=dict(active=True,preset='PRODUCTION_DEFAULT',recommended=dict(pace='FAST_PLUS',tts=False,subtitles=False))
        raw=dict(topic='서울에서 도쿄를 거쳐 타이베이로 이동하는 민간 항공 연결',duration=20)
        with patch('engine.production.production_default_status',return_value=status):
            recommended=generate_plan(raw)
            override=generate_plan({**raw,'pace':'NORMAL','tts':True,'subtitles':True})
        self.assertTrue(recommended['gate']['passed'],recommended['gate']['errors'])
        self.assertEqual(recommended['options']['pace'],'FAST_PLUS')
        self.assertFalse(recommended['options']['tts']);self.assertFalse(recommended['options']['subtitles'])
        self.assertTrue(override['gate']['passed'],override['gate']['errors'])
        self.assertEqual(override['options']['pace'],'NORMAL')
        self.assertTrue(override['options']['tts']);self.assertTrue(override['options']['subtitles'])


if __name__=='__main__':unittest.main()
