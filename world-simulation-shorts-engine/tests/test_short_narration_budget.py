"""Actual offline speech timing for concise short-Scene defaults, without graphics."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from engine.audio import ESpeakProvider,_narration as synthesize_narration
from engine.gis import resolve_location
from engine.planner import generate_plan,_narration


class ShortNarrationBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider=ESpeakProvider()
        cls.request=dict(topic='뉴욕 → 런던 → 두바이 민간 항공 경로',duration=20,quality='HIGH',tts=True)
        cls.plan=generate_plan(cls.request)
        cls.virtual_plan=generate_plan(dict(topic='만약 서울에서 도쿄를 거치지 않고 싱가포르로 이동한다면?',duration=20,quality='HIGH',tts=True))

    def test_default_tts_on_20_second_plan_fits_actual_voice_with_reserve(self):
        for plan in [self.plan,self.virtual_plan]:
            self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
            self.assertTrue(plan['options']['tts'])
            self.assertNotIn('tts_speed',plan['options'])
            self.assertIn('?',plan['scenes'][2]['narration'])
            self.assertIn('다음 연결',plan['scenes'][2]['narration'])
            with TemporaryDirectory(prefix='wss-short-plan-tts-',dir='/tmp') as tmp:
                _,cues,measurements=synthesize_narration(plan,Path(tmp),self.provider)
            self.assertEqual(len(cues),5)
            for scene,cue,measured in zip(plan['scenes'],cues,measurements):
                with self.subTest(domain=plan['story']['domain'],scene=scene['scene_id']):
                    actual=cue['end']-cue['start']
                    self.assertLessEqual(actual,scene['duration']-.08)
                    if scene['role'] in {'variable','payoff'}:self.assertLessEqual(actual,(scene['duration']-.08)*.9)
                    self.assertEqual(measured['language'],'ko')
                    self.assertFalse(measured['word_alignment'])

    def test_six_short_scenes_share_a_20_second_actual_voice_budget(self):
        duration=20/6;location=resolve_location('London')
        roles=['hook','orientation','progression','variable','peak','payoff']
        scenes=[]
        for i,role in enumerate(roles):
            text=self.plan['scenes'][0]['narration'] if role=='hook' else _narration(role,location,'aviation',False,duration)
            scenes.append(dict(scene_id=f'S{i+1:03}',start_time=i*duration,duration=duration,narration=text))
        fixture=dict(duration=20.,options=dict(tts=True),scenes=scenes)
        with TemporaryDirectory(prefix='wss-short-six-tts-',dir='/tmp') as tmp:
            _,cues,_=synthesize_narration(fixture,Path(tmp),self.provider)
        self.assertEqual(len(cues),6)
        for scene,cue in zip(scenes,cues):
            with self.subTest(scene=scene['scene_id']):
                self.assertLessEqual(cue['end']-cue['start'],(duration-.08)*.9)

    def test_only_short_narration_changes_and_long_scene_wording_is_retained(self):
        # Generate the same design using the earlier full-length defaults. This
        # compares actual graph/source/preset/event outputs, rather than copying
        # the planner implementation into a test.
        def legacy(role,location,domain,conditional,duration=None):
            return _narration(role,location,domain,conditional)
        with patch('engine.planner._narration',side_effect=legacy):
            previous=generate_plan(self.request)
        current=deepcopy(self.plan);previous=deepcopy(previous)
        changed=[]
        for before,after in zip(previous['scenes'],current['scenes']):
            if before['narration']!=after['narration']:changed.append(after['scene_id'])
            before.pop('narration');after.pop('narration')
        for plan in [previous,current]:
            plan.pop('gate',None)
            plan['metadata'].pop('semantic_visibility',None)
        self.assertEqual(changed,['S003','S005'])
        self.assertEqual(previous,current,'Camera, GIS, routes, assets, events and claims must stay identical')
        location=resolve_location('London')
        for role in ['orientation','progression','variable','peak','payoff']:
            self.assertEqual(_narration(role,location,'aviation',False,7.5),_narration(role,location,'aviation',False))


if __name__=='__main__':unittest.main()
