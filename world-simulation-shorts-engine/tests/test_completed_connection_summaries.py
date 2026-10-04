"""Post-arrival summaries retain long-duration support without inventing motion."""
from copy import deepcopy
import hashlib,json,tempfile,unittest
from pathlib import Path

from engine.gis import resolve_location
from engine.planner import generate_plan,replace_repeated_city_reveal_with_completed_connection,PlanningInputError
from engine.revisions import preview_revision
from engine.storage import ProjectStore
from test_retimed_route_metrics import rendered_metric

APP=Path(__file__).resolve().parents[1]


class CompletedConnectionSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plans={}
        for domain,topic,durations in [('aviation','런던 → 파리 → 로마 민간 항공 여행',[180,183.5,180.013]),('shipping','수에즈 운하가 7일 동안 막힌다면?',[180,183.5])]:
            for duration in durations:
                cls.plans[(domain,duration)]=generate_plan(dict(topic=topic,duration=duration,quality='HIGH'))

    def test_long_and_fractional_duration_plans_pass_strict_gates_on_the_integer_frame_grid(self):
        for (domain,requested),plan in self.plans.items():
            with self.subTest(domain=domain,duration=requested):
                self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
                self.assertEqual(sum(round(scene['duration']*30) for scene in plan['scenes']),round(plan['duration']*30))
                self.assertLessEqual(abs(plan['duration']-requested),1/60+1e-9)
                for scene in plan['scenes']:
                    self.assertAlmostEqual(scene['duration']*30,round(scene['duration']*30),places=6)
                scene=plan['scenes'][-1];event=next(event for event in scene['visual_events'] if event['id']=='E089')
                self.assertEqual(event['kind'],'connection_reveal')
                self.assertEqual(event['claim_id'],'M01')
                self.assertNotIn('REMAINING',event['text']);self.assertNotIn('TO THE NEXT CITY',event['text'])
                self.assertIn(' -> ',event['text'])
                metric=rendered_metric(scene,event)
                self.assertAlmostEqual(metric['progress'],1)
                self.assertEqual(event['value'],round(metric['total_km']))
                self.assertTrue(next(route for route in scene['routes'] if route['route_id']==event['target_id'])['source_ids'])

    def test_completed_summary_leaves_a_real_window_for_final_payoff_and_synced_sound(self):
        for key,plan in self.plans.items():
            with self.subTest(case=key):
                record=next(record for record in plan['metadata']['repeated_city_reveal_repairs'] if record['event_id']=='E089')
                self.assertTrue(record['completed']);self.assertAlmostEqual(record['progress'],1)
                scene=plan['scenes'][-1];event=next(event for event in scene['visual_events'] if event['id']=='E089')
                sound=next(sound for sound in scene['sound_events'] if sound['visual_event_id']==event['id'])
                self.assertEqual(sound['time'],event['time'])
                observed={row['event_id']:row for row in plan['gate']['semantic_visibility']['events']}
                payoff=next(event for event in scene['visual_events'] if event['kind']=='final_reveal')
                for event_id in [event['id'],payoff['id']]:
                    row=observed[event_id]
                    self.assertGreaterEqual(row['visible_seconds'],.1)
                    self.assertLessEqual(row['onset_latency_seconds'],row['allowed_onset_delay_seconds']+1e-6)
                if key[1] in [180,180.013]:self.assertLess(record['after']['time'],record['before']['time'])

    def test_incomplete_faint_or_unverified_curve_cannot_be_called_completed(self):
        base=deepcopy(self.plans[('aviation',180)]['scenes'][-1])
        summary=next(event for event in base['visual_events'] if event['id']=='E089')
        selected=next(route for route in base['routes'] if route['route_id']==summary['target_id'])
        location=resolve_location(selected['points'][-1]['location_id'])
        for fault in ['incomplete','faint','unverified']:
            with self.subTest(fault=fault):
                scene=deepcopy(base);event=next(event for event in scene['visual_events'] if event['id']=='E089')
                event.update(kind='region_reveal',target_id=location['id'],coordinates=deepcopy(location['coordinates']),text=location['name'].upper())
                for route in scene['routes']:
                    if route['points'][-1].get('location_id')!=location['id']:continue
                    if fault=='incomplete':route['progress_start']=.5;route['progress_end']=.8
                    elif fault=='faint':route['faint']=True
                    else:route['points'][0]['lon']+=1
                before=deepcopy(event)
                with self.assertRaises(PlanningInputError):replace_repeated_city_reveal_with_completed_connection(scene,event)
                self.assertEqual(event,before)

    def test_original_75_second_repair_still_changes_only_two_scenes_and_preserves_exact_input(self):
        source=APP/'docs/evidence/shipping75_label_progression_20261004T203922Z/production_plan_before_exact.json'
        before_bytes=source.read_bytes();original=json.loads(before_bytes)
        with tempfile.TemporaryDirectory(prefix='wss-completed-summary-b75-',dir='/tmp') as directory:
            store=ProjectStore(directory);base=store.create(deepcopy(original['request']),deepcopy(original))
            proposal=preview_revision(store,base['project']['id'],'v001','Scene2와Scene9 중복 도시명 대신 현재 항로의 남은 거리를 보여줘')
            self.assertTrue(proposal['plan']['gate']['passed'],proposal['plan']['gate']['errors'])
            self.assertFalse(proposal['approved']);self.assertEqual(proposal['affected_scenes'],['S002','S009'])
            changed={}
            for before,after in zip(original['scenes'],proposal['plan']['scenes']):
                fields=[key for key in before if before[key]!=after.get(key)]
                if fields:changed[before['scene_id']]=fields
            self.assertEqual(changed,{'S002':['visual_events','sound_events'],'S009':['visual_events','sound_events']})
            for index,event_id,value in [(1,'E008',13567),(8,'E034',681)]:
                event=next(event for event in proposal['plan']['scenes'][index]['visual_events'] if event['id']==event_id)
                self.assertEqual((event['kind'],event['value']),('milestone_reveal',value))
        self.assertEqual(source.read_bytes(),before_bytes)
        self.assertEqual(hashlib.sha256(before_bytes).hexdigest(),'7cf9775ffbff58a965884f7ba25bf34c3352432deb493f2a59ea6f21a3244fe5')


if __name__=='__main__':unittest.main()
