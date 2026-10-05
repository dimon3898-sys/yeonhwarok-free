"""Real camera/route regression checks for bounded partial edits; no GL or video render."""
import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from engine.planner import generate_plan
from engine.revisions import preview_revision
from engine.storage import EngineError,ProjectStore

APP=Path(__file__).resolve().parents[1]

class RevisionGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shipping=generate_plan(dict(production_preset='LEGACY', topic='수에즈 운하가 7일 동안 막힌다면?',duration=75,quality='HIGH'))
        cls.europe=generate_plan(dict(production_preset='LEGACY', topic='런던 → 파리 → 로마 민간 항공 여행',duration=20,quality='HIGH'))
        cls.atlantic=generate_plan(dict(production_preset='LEGACY', topic='뉴욕 → 런던 → 두바이 민간 항공 여행',duration=20,quality='HIGH'))

    def proposal(self,plan,text):
        with tempfile.TemporaryDirectory(prefix='wss_revision_test_') as directory:
            store=ProjectStore(directory);project=store.create(copy.deepcopy(plan['request']),copy.deepcopy(plan))
            return preview_revision(store,project['project']['id'],project['version'],text)

    def test_ship_addition_uses_the_route_that_really_moves_in_requested_window(self):
        proposal=self.proposal(self.shipping,'32~38초 카메라를 조금 더 빠르게 하고 배 두 척 추가')
        self.assertTrue(proposal['plan']['gate']['passed'],proposal['plan']['gate']['errors'])
        self.assertFalse(proposal['approved'])
        self.assertEqual(proposal['affected_scenes'],['S005','S006'])
        added=[[e for e in scene['entities'] if e['id'].startswith('added_ship_')] for scene in proposal['plan']['scenes'][4:6]]
        self.assertEqual([e['id'] for e in added[0]],[e['id'] for e in added[1]])
        for ships in added:
            self.assertEqual(len(ships),2)
            self.assertTrue(all(e['route_id']=='R_CAPE' for e in ships))
            self.assertEqual([e['phase_offset'] for e in ships],[.005,.01])
        self.assertTrue(any('34.7초' in warning for warning in proposal['warnings']))

    def test_added_ship_models_pass_the_full_pure_renderer_contract(self):
        proposal=self.proposal(self.shipping,'32~38초 카메라를 조금 더 빠르게 하고 배 두 척 추가')
        with tempfile.TemporaryDirectory(prefix='wss_ship_numeric_') as directory:
            plan_path=Path(directory)/'plan.json';result_path=Path(directory)/'numeric.json'
            plan_path.write_text(json.dumps(proposal['plan']),encoding='utf-8')
            process=subprocess.run(['node',str(APP/'tools/renderer_contract_test.mjs'),str(plan_path),str(result_path)],cwd=APP,text=True,capture_output=True,timeout=20)
            self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            result=json.loads(result_path.read_text())
            self.assertTrue(result['passed'])
            self.assertTrue(all(r['entity_out_of_frame']==0 and r['entity_occluded_frames']==0 for r in result['results']))

    def test_extra_routes_are_actual_visible_network_events_with_synced_sound(self):
        proposal=self.proposal(self.europe,'Scene 2 항로 두 개 추가');scene=proposal['plan']['scenes'][1]
        self.assertTrue(proposal['plan']['gate']['passed'],proposal['plan']['gate']['errors'])
        events=[e for e in scene['visual_events'] if '_route_add_' in e['id']]
        self.assertEqual(len(events),2)
        self.assertTrue(all(e['kind']=='network_expand' for e in events))
        self.assertTrue(all(check['passed'] and check['qualified_frames']>=12 for check in proposal['geometry_checks']))
        for event in events:
            route=next(r for r in scene['routes'] if r['route_id']==event['target_id'])
            sound=next(s for s in scene['sound_events'] if s['visual_event_id']==event['id'])
            self.assertTrue(route['faint'])
            self.assertEqual(route['start_time'],event['time'])
            self.assertEqual(sound['time'],event['time'])
            self.assertGreaterEqual(event['time'],scene['duration']*.45)

    def test_hidden_atlantic_connections_are_rejected_before_approval(self):
        with self.assertRaises(EngineError) as raised:self.proposal(self.atlantic,'Scene 2 항로 두 개 추가')
        self.assertEqual(raised.exception.code,'UNSUPPORTED_VISUAL_REQUIREMENT')
        self.assertIn('VISIBLE_NETWORK_COMPOSITION',raised.exception.details['required_plugins'])

if __name__=='__main__':unittest.main()
