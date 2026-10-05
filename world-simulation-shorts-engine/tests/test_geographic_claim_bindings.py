"""Exact GIS target bindings for facts, including places sharing one source file."""
from copy import deepcopy
import unittest
from engine.gis import resolve_location
from engine.planner import generate_plan
from engine.schema import validate_plan


class GeographicClaimBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shipping=generate_plan(dict(production_preset='LEGACY', topic='수에즈 운하가 7일 동안 막힌다면?',duration=75,quality='HIGH'))
        cls.aviation=generate_plan(dict(production_preset='LEGACY', topic='서울 → 도쿄 → 싱가포르 민간 항공 경로',duration=75,quality='HIGH'))

    def test_shipping_destination_previews_use_the_singapore_fact_and_description(self):
        self.assertTrue(self.shipping['gate']['passed'],self.shipping['gate']['errors'])
        previews=[(scene,event) for scene in self.shipping['scenes'] for event in scene['visual_events'] if event['kind']=='destination_preview']
        by_id={event['id']:(scene,event) for scene,event in previews}
        self.assertTrue({'E004','E024'}.issubset(by_id),by_id.keys())
        for scene,event in previews:
            self.assertEqual(event['target_id'],'SINGAPORE_PORT')
            self.assertEqual(event['coordinates'],resolve_location('SINGAPORE_PORT')['coordinates'])
            self.assertEqual(event['claim_id'],'F03')
            self.assertIn(resolve_location('SINGAPORE_PORT')['name'],event['description'])
            self.assertNotIn(resolve_location('SUEZ_CANAL')['name'],event['description'])
        self.assertEqual(self.shipping['metadata']['coordinate_claim_targets']['F03'],'SINGAPORE_PORT')

    def test_all_coordinate_facts_match_aviation_and_shipping_event_places(self):
        for plan in [self.aviation,self.shipping]:
            with self.subTest(domain=plan['story']['domain']):
                self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
                targets=plan['metadata']['coordinate_claim_targets']
                claims={claim['id']:claim for claim in plan['story']['claims']}
                inspected=[]
                for scene in plan['scenes']:
                    for event in scene['visual_events']:
                        if event.get('claim_id') not in targets:continue
                        target=targets[event['claim_id']];inspected.append(event['id'])
                        self.assertEqual(event['target_id'],target)
                        self.assertEqual(event['coordinates']['location_id'],target)
                        self.assertEqual(event['coordinates'],resolve_location(target)['coordinates'])
                        self.assertIn(event['coordinates']['source_id'],claims[event['claim_id']]['source_ids'])
                        if event['kind']=='destination_preview':
                            self.assertIn(resolve_location(target)['name'],event['description'])
                self.assertTrue(inspected)

    def test_wrong_location_fact_is_blocked_even_when_both_use_the_same_source(self):
        bad=deepcopy(self.shipping)
        event=next(e for scene in bad['scenes'] for e in scene['visual_events'] if e['id']=='E004')
        original=deepcopy(event);event['claim_id']='F02'
        claims={claim['id']:claim for claim in bad['story']['claims']}
        self.assertEqual(claims['F02']['source_ids'],claims['F03']['source_ids'])
        report=validate_plan(bad)
        self.assertFalse(report['passed'])
        mismatch=next(error for error in report['errors'] if error['code']=='GEOGRAPHIC_EVENT_CLAIM_MISMATCH')
        self.assertEqual(mismatch['expected_location_id'],'SUEZ_CANAL')
        self.assertEqual(mismatch['coordinate_location_id'],'SINGAPORE_PORT')
        self.assertIsNone(report['semantic_visibility'],'Known provenance failure must be blocked before expensive visibility preflight')
        self.assertEqual(next(e for scene in self.shipping['scenes'] for e in scene['visual_events'] if e['id']=='E004'),original)

    def test_incomplete_or_unknown_typed_bindings_are_blocked_without_parsing_prose(self):
        for change,code in [('missing','INCOMPLETE_GEOGRAPHIC_CLAIM_BINDINGS'),('unknown','INVALID_GEOGRAPHIC_CLAIM_BINDING')]:
            with self.subTest(change=change):
                bad=deepcopy(self.shipping)
                if change=='missing':del bad['metadata']['coordinate_claim_targets']['F03']
                else:bad['metadata']['coordinate_claim_targets']['F03']='UNKNOWN_PORT'
                report=validate_plan(bad)
                self.assertFalse(report['passed'])
                self.assertIn(code,{error['code'] for error in report['errors']})


if __name__=='__main__':unittest.main()
