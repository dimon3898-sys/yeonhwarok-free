"""Repeated active-city filler labels and their bounded natural-language repair.

Real counterexamples: B75 S002/E008 and S009/E034. No GL, renderer, production
version, approval, or media files are changed by these planning regressions.
"""
from copy import deepcopy
import hashlib
import tempfile
import unittest

from engine.gis import resolve_location
from engine.planner import generate_plan,repeated_city_reveal_events,replace_geographic_event_with_milestone,PlanningInputError
from engine.revisions import preview_revision
from engine.storage import ProjectStore
from engine.schema import validate_plan
from test_retimed_route_metrics import rendered_metric


class PlanningLabelRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=generate_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=75,style='긴장감 있는 세계 시뮬레이션',quality='HIGH',tts=True,subtitles=True,bgm=True))
        cls.legacy=deepcopy(cls.plan)
        for index,event_id,location_id,claim_id in [(1,'E008','ROTTERDAM_PORT','F01'),(8,'E034','SINGAPORE_PORT','F03')]:
            scene=cls.legacy['scenes'][index];location=resolve_location(location_id)
            event=next(event for event in scene['visual_events'] if event['id']==event_id)
            event.update(kind='region_reveal',target_id=location_id,text=location['name'].upper(),coordinates=deepcopy(location['coordinates']),value=None,unit='',claim_id=claim_id,description='다음 지역의 위치 공개')
            next(sound for sound in scene['sound_events'] if sound['visual_event_id']==event_id)['kind']='soft_impact'

    def test_actual_long_scene_counterexamples_repeat_the_same_active_city_label(self):
        detected={(scene['scene_id'],event['id']) for scene in self.legacy['scenes'] for event in repeated_city_reveal_events(scene)}
        self.assertEqual(detected,{('S002','E008'),('S009','E034')})
        # A first city introduction and a real arrival are different events.
        self.assertFalse(repeated_city_reveal_events(self.legacy['scenes'][0]))
        arrival=next(event for event in self.legacy['scenes'][8]['visual_events'] if event['id']=='E035')
        self.assertEqual(arrival['kind'],'arrival')

    def test_known_duplicate_plan_fails_before_render_while_real_city_and_arrival_are_not_rejected(self):
        report=validate_plan(self.legacy)
        self.assertFalse(report['passed'])
        duplicates={(error['scene_id'],error['event_id']) for error in report['errors'] if error['code']=='PLAN_DUPLICATE_PLACE_LABEL'}
        self.assertEqual(duplicates,{('S002','E008'),('S009','E034')})
        self.assertIsNone(report['semantic_visibility'])
        self.assertTrue(self.plan['gate']['passed'],self.plan['gate']['errors'])
        self.assertEqual(next(e for e in self.plan['scenes'][0]['visual_events'] if e['id']=='E001')['kind'],'city_reveal')
        self.assertEqual(next(e for e in self.plan['scenes'][8]['visual_events'] if e['id']=='E035')['kind'],'arrival')

    def test_new_75_second_plan_uses_exact_rendered_remaining_distance_and_keeps_arrival(self):
        self.assertTrue(self.plan['gate']['passed'],self.plan['gate']['errors'])
        self.assertEqual({record['event_id'] for record in self.plan['metadata']['repeated_city_reveal_repairs']},{'E008','E034'})
        for index,event_id,route_id in [(1,'E008','R_SUEZ'),(8,'E034','R_CAPE')]:
            scene=self.plan['scenes'][index];event=next(e for e in scene['visual_events'] if e['id']==event_id)
            old=next(e for e in self.legacy['scenes'][index]['visual_events'] if e['id']==event_id)
            self.assertEqual((event['kind'],event['target_id'],event['claim_id']),('milestone_reveal',route_id,'M01'))
            self.assertEqual((event['id'],event['time'],event['caused_by']),(old['id'],old['time'],old['caused_by']))
            actual=rendered_metric(scene,event)
            self.assertEqual(event['value'],round(actual['remaining_km']))
            self.assertGreater(actual['progress'],0);self.assertLess(actual['progress'],1)
            self.assertIn('REMAINING',event['text'])
            self.assertFalse(repeated_city_reveal_events(scene))
        self.assertEqual(next(e for e in self.plan['scenes'][8]['visual_events'] if e['id']=='E035'),next(e for e in self.legacy['scenes'][8]['visual_events'] if e['id']=='E035'))

    def test_multi_scene_natural_revision_changes_only_two_events_and_paired_sound_kinds(self):
        with tempfile.TemporaryDirectory(prefix='wss-label-revision-',dir='/tmp') as directory:
            store=ProjectStore(directory);base=store.create(deepcopy(self.legacy['request']),deepcopy(self.legacy));pid=base['project']['id']
            path=store.version_path(pid,'v001')/'scene_plan.json';before_bytes=path.read_bytes();before_sha=hashlib.sha256(before_bytes).hexdigest()
            proposal=preview_revision(store,pid,'v001','Scene2와Scene9 중복 도시명 대신 현재 항로의 남은 거리를 보여줘')
            self.assertFalse(proposal['approved'])
            self.assertTrue(proposal['plan']['gate']['passed'],proposal['plan']['gate']['errors'])
            self.assertEqual(proposal['affected_scenes'],['S002','S009'])
            self.assertEqual({(change['scene_id'],change['field']) for change in proposal['diff']},{('S002','visual_events'),('S002','sound_events'),('S009','visual_events'),('S009','sound_events')})
            for before,after in zip(base['plan']['scenes'],proposal['plan']['scenes']):
                if before['scene_id'] not in {'S002','S009'}:self.assertEqual(before,after);continue
                for key in before:
                    if key not in {'visual_events','sound_events'}:self.assertEqual(before[key],after[key])
                changed={event['id'] for event,other in zip(before['visual_events'],after['visual_events']) if event!=other}
                self.assertEqual(changed,{'E008'} if before['scene_id']=='S002' else {'E034'})
                for old_sound,sound in zip(before['sound_events'],after['sound_events']):
                    self.assertEqual({k:v for k,v in old_sound.items() if k!='kind'},{k:v for k,v in sound.items() if k!='kind'})
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before_sha)
            self.assertEqual(path.read_bytes(),before_bytes)
            self.assertFalse((store.version_path(pid,'v001')/'approval.json').exists())

    def test_20_second_gates_and_typed_claims_stay_valid_and_stationary_route_is_not_faked(self):
        for topic in ['뉴욕 → 런던 → 두바이 민간 항공 여행','만약 수에즈 운하가 7일 동안 막힌다면?']:
            plan=generate_plan(dict(topic=topic,duration=20,quality='HIGH'))
            self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
            targets=plan['metadata']['coordinate_claim_targets']
            for scene in plan['scenes']:
                for event in scene['visual_events']:
                    if event.get('claim_id') in targets:
                        self.assertEqual(event['target_id'],targets[event['claim_id']])
                        self.assertEqual(event['coordinates']['location_id'],targets[event['claim_id']])
        scene=deepcopy(self.legacy['scenes'][1]);event=next(e for e in scene['visual_events'] if e['id']=='E008')
        for entity in scene['entities']:entity['action']='stop'
        before=deepcopy(event)
        with self.assertRaises(PlanningInputError):replace_geographic_event_with_milestone(scene,event)
        self.assertEqual(event,before)


if __name__=='__main__':unittest.main()
