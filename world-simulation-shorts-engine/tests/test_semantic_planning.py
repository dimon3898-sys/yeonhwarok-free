"""Real scoped correction and pre-render semantic timing/framing regressions."""
from copy import deepcopy
import json,tempfile,unittest
from pathlib import Path
from engine.planner import generate_plan
from engine.revisions import preview_revision,approve_revision
from engine.schema import validate_plan
from engine.storage import ProjectStore

APP=Path(__file__).resolve().parents[1]

class SemanticPlanningTests(unittest.TestCase):
    def test_natural_correction_changes_only_the_invisible_event_and_its_synced_sound(self):
        original=generate_plan(dict(topic='뉴욕 → 런던 → 두바이 민간 항공 여행',duration=20,quality='HIGH'))
        legacy_event=next(event for event in json.loads((APP/'tests/fixtures/semantic_e006_regression.json').read_text())['scenes'][0]['visual_events'] if event['id']=='E006')
        original['scenes'][1]['visual_events']=[deepcopy(legacy_event) if event['id']=='E006' else event for event in original['scenes'][1]['visual_events']]
        next(sound for sound in original['scenes'][1]['sound_events'] if sound['visual_event_id']=='E006')['kind']='soft_impact'
        self.assertFalse(validate_plan(original)['passed'])
        with tempfile.TemporaryDirectory(prefix='wss_semantic_revision_') as directory:
            store=ProjectStore(directory);base=store.create(deepcopy(original['request']),deepcopy(original));pid=base['project']['id']
            base_path=store.version_path(pid,'v001')/'scene_plan.json';base_bytes=base_path.read_bytes()
            proposal=preview_revision(store,pid,'v001','S002 화면 밖 국가 강조 대신 현재 항로의 남은 거리를 보여줘')
            self.assertTrue(proposal['plan']['gate']['passed'],proposal['plan']['gate']['errors'])
            self.assertEqual(proposal['affected_scenes'],['S002'])
            self.assertEqual({change['field'] for change in proposal['diff']},{'visual_events','sound_events'})
            corrected=proposal['plan']['scenes'][1];event=next(event for event in corrected['visual_events'] if event['id']=='E006')
            self.assertEqual((event['kind'],event['target_id'],event['claim_id'],event['value']),('milestone_reveal','R_01','M01',1568))
            self.assertEqual((event['time'],event['caused_by']),(2.65,'E005'))
            sound=next(sound for sound in corrected['sound_events'] if sound['visual_event_id']=='E006')
            old_sound=next(sound for sound in base['plan']['scenes'][1]['sound_events'] if sound['visual_event_id']=='E006')
            self.assertEqual(sound['time'],event['time']);self.assertEqual(sound['gain_db'],old_sound['gain_db'])
            for field in ('camera_start','camera_end','camera_speed','routes','entities','entry_state','exit_state'):
                self.assertEqual(corrected[field],base['plan']['scenes'][1][field])
            for index in (0,2,3,4):self.assertEqual(proposal['plan']['scenes'][index],base['plan']['scenes'][index])
            result=approve_revision(store,pid,proposal['revision_id'])
            self.assertEqual(result['version'],'v002');self.assertEqual(base_path.read_bytes(),base_bytes)

    def test_shipping_physical_barrier_arrival_and_final_payoff_have_real_draw_windows(self):
        result=generate_plan(dict(topic='수에즈 운하가 7일 동안 막힌다면?',duration=75,quality='HIGH'))
        self.assertTrue(result['gate']['passed'],result['gate']['errors'])
        certificate=result['gate']['semantic_visibility'];observed={row['event_id']:row for row in certificate['events']}
        for scene in result['scenes']:
            for event in scene['visual_events']:
                if not event.get('meaningful',True):continue
                row=observed[event['id']]
                self.assertGreaterEqual(row['visible_seconds'],.1)
                self.assertLessEqual(row['onset_latency_seconds'],row['allowed_onset_delay_seconds']+.00001)
                if event['kind']=='route_blocked':self.assertIn('route_barrier',row['eligible_primitives'])
                if event['kind']=='arrival':self.assertTrue(set(row['eligible_primitives'])&{'geographic_pulse','world_label'})
        repaired={row['event_id'] for row in result['metadata']['semantic_visibility_repairs']}
        self.assertTrue({'E014','E022','E026','E028'}.issubset(repaired))
        self.assertFalse(any(event['kind']!='arrival' for scene in result['scenes'] for event in scene['visual_events'] if event['id']=='E018'))
        timing=result['metadata']['semantic_information_timing_repairs'][0]
        self.assertEqual(timing['event_id'],'E040');self.assertLess(timing['after_time'],timing['before_time'])
        for before,after in zip(result['scenes'],result['scenes'][1:]):self.assertEqual(before['exit_state'],after['entry_state'])

    def test_information_next_to_scene_boundary_gets_an_actual_readable_window(self):
        result=generate_plan(dict(topic='만약 서울과 싱가포르를 직접 연결한다면?',duration=40))
        self.assertTrue(result['gate']['passed'],result['gate']['errors'])
        repairs=result['metadata']['scene_event_window_repairs'];self.assertTrue(repairs)
        observed={row['event_id']:row for row in result['gate']['semantic_visibility']['events']}
        for repair in repairs:
            self.assertLess(repair['after_time'],repair['before_time'])
            self.assertGreaterEqual(observed[repair['event_id']]['visible_seconds'],.1)

if __name__=='__main__':unittest.main()
