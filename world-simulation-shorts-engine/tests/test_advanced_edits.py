"""Structural-edit regressions: immutable input, real joins and delayed visible results."""
from copy import deepcopy
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.advanced_revisions import apply_advanced_edit
from engine.planner import generate_plan
from engine.schema import validate_plan
from engine.storage import EngineError
from engine.gis import verified_coordinate

class AdvancedEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=generate_plan(dict(production_preset='LEGACY', topic='런던 → 파리 → 로마 민간 항공 여행',duration=20,quality='HIGH',tts=False,subtitles=False,bgm=True))
        assert cls.original['gate']['passed'],cls.original['gate']['errors']

    def test_simple_edit_and_aircraft_removal_are_not_scene_deletion(self):
        self.assertIsNone(apply_advanced_edit(self.original,['S002'],'장면 2 카메라를 빠르게'))
        self.assertIsNone(apply_advanced_edit(self.original,['S002'],'Scene 2 비행기 제거'))

    def test_delete_is_pure_and_removes_real_scene_without_renumbering(self):
        before=deepcopy(self.original)
        result=apply_advanced_edit(self.original,['S002'],'장면 2 삭제')
        self.assertEqual(self.original,before)
        plan=result['plan']
        self.assertEqual([s['scene_id'] for s in plan['scenes']],['S001','S003','S004','S005'])
        self.assertEqual(plan['duration'],16)
        self.assertEqual(plan['request']['duration'],16)
        self.assertEqual(result['affected_scenes'],['S002','S003'])
        self.assertTrue(validate_plan(plan)['passed'],validate_plan(plan)['errors'])

    def test_deleted_gap_connects_exact_camera_and_actual_route_state(self):
        plan=apply_advanced_edit(self.original,['S002'],'이 Scene 2는 삭제')['plan']
        for previous,following in zip(plan['scenes'],plan['scenes'][1:]):
            self.assertEqual(previous['exit_state'],following['entry_state'])
            self.assertEqual(following['camera_start'],previous['exit_state']['camera'])
        first,neighbor=plan['scenes'][:2]
        route_before={r['route_id']:r for r in first['routes']}
        for route in neighbor['routes']:
            if route['route_id'] in route_before:self.assertEqual(route['progress_start'],route_before[route['route_id']]['progress_end'])

    def test_only_timing_metadata_changes_after_first_impacted_neighbor(self):
        plan=apply_advanced_edit(self.original,['S002'],'Scene 2 delete')['plan']
        old={s['scene_id']:s for s in self.original['scenes']}
        self.assertEqual(plan['scenes'][0],old['S001'])
        for scene in plan['scenes'][2:]:
            self.assertEqual(scene['render_time_offset'],old[scene['scene_id']]['start_time'])
            restored=deepcopy(scene);restored['start_time']=old[scene['scene_id']]['start_time']
            if 'render_time_offset' not in old[scene['scene_id']]:restored.pop('render_time_offset')
            self.assertEqual(restored,old[scene['scene_id']])

    def test_missing_cause_resolves_to_surviving_real_ancestor(self):
        plan=apply_advanced_edit(self.original,['S002'],'delete scene 2')['plan']
        ids=set();removed={e['id'] for s in self.original['scenes'] if s['scene_id']=='S002' for e in s['visual_events']}
        for scene in plan['scenes']:
            for event in sorted(scene['visual_events'],key=lambda e:e['time']):
                self.assertNotIn(event.get('caused_by'),removed)
                if event.get('caused_by'):self.assertIn(event['caused_by'],ids)
                ids.add(event['id'])

    def test_opening_deletion_is_blocked_instead_of_restoring_original_hook(self):
        plan=apply_advanced_edit(self.original,['S001'],'장면 1 삭제')['plan']
        self.assertNotIn('S001',[s['scene_id'] for s in plan['scenes']])
        self.assertEqual(plan['story']['hook'],'')
        codes={e['code'] for e in validate_plan(plan)['errors']}
        self.assertIn('MISSING_HOOK',codes)

    def test_final_deletion_is_blocked_without_fabricated_reward(self):
        plan=apply_advanced_edit(self.original,['S005'],'마지막 장면 삭제')['plan']
        self.assertNotIn('S005',[s['scene_id'] for s in plan['scenes']])
        self.assertIn('EARLY_OR_MISSING_PAYOFF',{e['code'] for e in validate_plan(plan)['errors']})

    def test_all_scene_deletion_is_explicitly_blocked(self):
        ids=[s['scene_id'] for s in self.original['scenes']]
        result=apply_advanced_edit(self.original,ids,'모든 장면 삭제')
        self.assertEqual(result['plan']['scenes'],[])
        self.assertTrue(result['blocking_issues'])
        self.assertFalse(validate_plan(result['plan'])['passed'])

    def test_delay_moves_result_audio_narration_and_network_not_just_caption(self):
        original=deepcopy(self.original)
        result=apply_advanced_edit(original,['S004'],'14초 여기서 결론 공개하지마')
        self.assertEqual(original,self.original)
        plan=result['plan'];selected=next(s for s in plan['scenes'] if s['scene_id']=='S004');final=plan['scenes'][-1]
        moved=plan['revision']['moved_event_ids']
        self.assertTrue(moved)
        self.assertFalse(set(moved)&{e['id'] for e in selected['visual_events']})
        self.assertTrue(set(moved)<={e['id'] for e in final['visual_events']})
        self.assertFalse(any(r['route_id'].startswith('N_') for r in selected['routes']))
        self.assertEqual(selected['narration'],'')
        self.assertEqual(final['narration'],self.original['scenes'][3]['narration'])
        self.assertFalse(any(a.get('visual_event_id') in moved for a in selected['sound_events']))
        self.assertTrue(any(a.get('visual_event_id') in moved for a in final['sound_events']))
        self.assertEqual(result['affected_scenes'],['S004','S005'])
        report=validate_plan(plan);self.assertTrue(report['passed'],report['errors'])

    def test_delayed_scene_adds_only_verified_geographic_context(self):
        result=apply_advanced_edit(self.original,['S004'],'Scene 4 delay the conclusion')
        plan=result['plan'];selected=next(s for s in plan['scenes'] if s['scene_id']=='S004')
        context=[e for e in selected['visual_events'] if e['id'].endswith('_context')]
        self.assertEqual(len(context),1)
        self.assertEqual(context[0]['kind'],'country_reveal')
        self.assertTrue(verified_coordinate(context[0]['coordinates']))
        claim=next(c for c in plan['story']['claims'] if c['id']==context[0]['claim_id'])
        self.assertEqual(claim['status'],'FACT');self.assertTrue(claim['source_ids'])

    def test_last_scene_delay_has_persisted_blocking_issue(self):
        result=apply_advanced_edit(self.original,['S005'],'마지막 장면 결론 공개하지마')
        self.assertEqual(result['blocking_issues'][0]['code'],'CONCLUSION_DELAY_REQUIRES_LATER_SCENE')
        self.assertEqual(result['plan']['revision']['blocking_issues'],result['blocking_issues'])
        report=validate_plan(result['plan'])
        self.assertFalse(report['passed'])
        self.assertIn('CONCLUSION_DELAY_REQUIRES_LATER_SCENE',{e['code'] for e in report['errors']})

    def test_no_existing_result_reports_specific_instruction(self):
        with self.assertRaises(EngineError) as caught:apply_advanced_edit(self.original,['S001'],'첫 장면 결론 공개하지마')
        self.assertEqual(caught.exception.code,'NO_CONCLUSION_TO_DELAY')

    def test_deleted_duration_remains_valid_provenance_after_later_edit(self):
        reduced=apply_advanced_edit(self.original,['S002'],'장면 2 삭제')['plan']
        delayed=apply_advanced_edit(reduced,['S004'],'장면 4 결론 공개하지마')['plan']
        self.assertEqual(delayed['revision']['type'],'scene_delete')
        self.assertEqual(delayed['revision']['last_edit'],'conclusion_delay')
        self.assertEqual(delayed['duration'],16)
        self.assertTrue(validate_plan(delayed)['passed'],validate_plan(delayed)['errors'])

class PhysicalEventBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=generate_plan(dict(production_preset='LEGACY', topic='런던 → 파리 → 로마 민간 항공 여행',duration=20))

    def test_route_start_is_the_actual_animated_path_onset(self):
        for scene in self.plan['scenes']:
            routes={r['route_id']:r for r in scene['routes']}
            for event in scene['visual_events']:
                if event['kind']=='route_start':
                    self.assertIn(event['target_id'],routes)
                    self.assertAlmostEqual(event['time'],routes[event['target_id']]['start_time'],places=6)
                    self.assertEqual(routes[event['target_id']]['progress_start'],0)

    def test_departure_is_actual_entity_spawn_not_a_later_recount(self):
        departures=[(scene,event) for scene in self.plan['scenes'] for event in scene['visual_events'] if event['kind']=='entity_departure']
        self.assertEqual(len(departures),1)
        scene,event=departures[0];entity=next(e for e in scene['entities'] if e['id']==event['target_id'])
        self.assertEqual(scene['start_time']+event['time'],1.5)
        self.assertAlmostEqual(event['time'],entity['start_time'],places=6)
        later=self.plan['scenes'][1]
        milestone=next(e for e in later['visual_events'] if e['kind']=='milestone_reveal')
        self.assertIsInstance(milestone['value'],(int,float));self.assertEqual(milestone['unit'],'km')
        self.assertNotIn('alternate_route_reveal',{e['kind'] for s in self.plan['scenes'] for e in s['visual_events']})

    def test_arrival_matches_real_route_end(self):
        for scene in self.plan['scenes']:
            for event in scene['visual_events']:
                if event['kind']!='arrival':continue
                matching=[r for r in scene['routes'] if r['points'][-1].get('location_id')==event['target_id'] and abs(r['end_time']-event['time'])<1e-6]
                self.assertTrue(matching,(scene['scene_id'],event))
                self.assertTrue(any(abs(r['progress_end']-1)<1e-6 for r in matching))

    def test_country_comparison_does_not_claim_an_aircraft_departure(self):
        plan=generate_plan(dict(production_preset='LEGACY', topic='미국과 중국 국가 위치 비교',duration=20))
        self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
        self.assertFalse(any(e['kind']=='entity_departure' for s in plan['scenes'] for e in s['visual_events']))
        self.assertFalse(any(s['entities'] for s in plan['scenes']))


class DerivedCameraAnchorTests(unittest.TestCase):
    def test_intercontinental_camera_anchors_match_actual_route_boundary(self):
        from engine.gis import RouteEngine
        plan=generate_plan(dict(production_preset='LEGACY', topic='뉴욕 → 런던 → 두바이 민간 항공 여행',duration=20))
        self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
        provenance={p['time']:p for p in plan['metadata']['camera_provenance']}
        for scene in plan['scenes']:
            record=provenance[scene['start_time']+scene['duration']]
            if record.get('network_overview'):
                self.assertEqual(scene['camera_end']['target_lon'],plan['metadata']['final_overview']['focus']['lon'])
                self.assertEqual(scene['camera_end']['target_lat'],plan['metadata']['final_overview']['focus']['lat'])
                self.assertNotIn('location_id',scene['camera_end'])
                continue
            route=next(r for r in scene['routes'] if r['route_id']==record['route_id'])
            point=RouteEngine.spherical_point(route['points'],record['progress'])
            for key in ['lon','lat']:
                self.assertAlmostEqual(scene['camera_end'][key],point[key],places=10)
                self.assertEqual(scene['camera_end']['target_'+key],scene['camera_end'][key])
            self.assertNotIn('location_id',scene['camera_end'])
            self.assertTrue(record['source_ids'])
        self.assertEqual(plan['scenes'][0]['camera_start']['location_id'],'new_york')
        for before,after in zip(plan['scenes'],plan['scenes'][1:]):
            self.assertEqual(before['camera_end'],after['camera_start'])
            self.assertEqual(before['exit_state'],after['entry_state'])

    def test_sea_camera_interpolates_licensed_graph_without_guessing_ports(self):
        from engine.gis import RouteEngine
        points=RouteEngine.sea('ROTTERDAM_SINGAPORE_SUEZ')
        self.assertAlmostEqual(RouteEngine.spherical_point(points,0)['lon'],points[0]['lon'],places=10)
        self.assertAlmostEqual(RouteEngine.spherical_point(points,1)['lat'],points[-1]['lat'],places=10)
        midpoint=RouteEngine.spherical_point(points,.40194431692212046)
        self.assertAlmostEqual(midpoint['lon'],32.382202,places=5)
        self.assertAlmostEqual(midpoint['lat'],30.318359,places=5)
        self.assertNotIn('location_id',midpoint)

    def test_milestone_numeric_value_matches_renderer_scene_easing(self):
        from engine.gis import great_circle_distance
        plan=generate_plan(dict(production_preset='LEGACY', topic='뉴욕 → 런던 → 두바이 민간 항공 여행',duration=20))
        for scene in plan['scenes']:
            for event in scene['visual_events']:
                if event['kind']!='milestone_reveal':continue
                route=next(r for r in scene['routes'] if r['route_id']==event['target_id'])
                u=max(0,min(1,(event['time']-route['start_time'])/max(.001,route['end_time']-route['start_time'])))
                u=u*u*(3-2*u)
                progress=route['progress_start']+(route['progress_end']-route['progress_start'])*u
                length=route.get('length_km',sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:])))
                self.assertAlmostEqual(event['value'],round(length*(1-progress)),delta=1)

    def test_final_overview_fits_entire_long_haul_network_without_city_invention(self):
        plan=generate_plan(dict(production_preset='LEGACY', topic='뉴욕 → 런던 → 두바이 민간 항공 여행',duration=20))
        framing=plan['metadata']['final_overview'];camera=plan['scenes'][-1]['camera_end']
        self.assertEqual(set(framing['route_ids']),{'R_01','R_02'})
        self.assertNotIn('location_id',camera)
        self.assertEqual(camera['fov'],44)
        self.assertLessEqual(camera['height'],6)
        self.assertLess(camera['target_lon'],10)
        self.assertGreater(camera['target_lon'],-10)
        self.assertGreaterEqual(framing['screen_bounds']['x_min'],.13)
        self.assertLessEqual(framing['screen_bounds']['x_max'],.83)
        self.assertGreaterEqual(framing['screen_bounds']['y_min'],.10)
        self.assertLessEqual(framing['screen_bounds']['y_max'],.78)
        self.assertEqual({label['coordinates']['location_id'] for label in plan['scenes'][-1]['labels']},{'new_york','london','dubai'})


class FrameGridTests(unittest.TestCase):
    def test_arbitrary_duration_uses_cumulative_integer_frame_boundaries(self):
        for duration in (20,75,183.5,180.013,31.71):
            with self.subTest(duration=duration):
                plan=generate_plan(dict(production_preset='LEGACY', topic='런던 → 파리 → 로마 민간 항공 여행',duration=duration))
                self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
                self.assertEqual(sum(round(s['duration']*30) for s in plan['scenes']),round(plan['duration']*30))
                for scene in plan['scenes']:
                    self.assertLessEqual(abs(scene['duration']*30-round(scene['duration']*30)),1e-6)
                self.assertAlmostEqual(sum(s['duration'] for s in plan['scenes']),plan['duration'],places=8)
                self.assertLessEqual(abs(plan['duration']-duration),1/60+1e-9)


class DomainAndStyleTests(unittest.TestCase):
    def test_ground_transport_and_historical_maps_do_not_become_modern_flights(self):
        from engine.plugins import UnsupportedVisualRequirement
        cases=[('런던 → 파리 자동차 여행','LAND_ROUTING'),('from London to Paris road trip','LAND_ROUTING'),('1900년 세계지도에서 런던 → 파리','HISTORICAL_GIS'),('역사적 국경 지도 미국과 중국 비교','TIME_MORPH')]
        for topic,module in cases:
            with self.subTest(topic=topic),self.assertRaises(UnsupportedVisualRequirement) as raised:
                generate_plan(dict(production_preset='LEGACY', topic=topic,duration=20))
            self.assertIn(module,raised.exception.modules)
        modern=generate_plan(dict(production_preset='LEGACY', topic='2025년 뉴욕 → 런던 민간 항공 경로',duration=20))
        self.assertTrue(modern['gate']['passed'],modern['gate']['errors'])

    def test_style_changes_real_scene_lighting_and_speed_with_exact_joins(self):
        baseline=generate_plan(dict(production_preset='LEGACY', topic='뉴욕 → 런던 → 두바이 민간 항공 여행',duration=20))
        travel=generate_plan({**baseline['request'],'style':'차분한 여행과 탐험'})
        documentary=generate_plan({**baseline['request'],'style':'시네마틱 지리 다큐멘터리'})
        network=generate_plan({**baseline['request'],'style':'역동적인 국제 네트워크'})
        self.assertEqual(travel['scenes'][0]['lighting_preset'],'DAY_DOCUMENTARY')
        self.assertEqual(documentary['scenes'][0]['lighting_preset'],'GEOGRAPHY_READABILITY')
        for plan,factor in [(travel,.85),(documentary,1),(network,1.1)]:
            self.assertTrue(plan['gate']['passed'],plan['gate']['errors'])
            self.assertEqual(plan['metadata']['story_pattern'],'journey-network-reveal')
            for original,changed in zip(baseline['scenes'],plan['scenes']):
                self.assertAlmostEqual(changed['camera_speed'],original['camera_speed']*factor)
                self.assertEqual(original['visual_events'],changed['visual_events'])
                self.assertEqual(original['camera_end']['lon'],changed['camera_end']['lon'])
                self.assertEqual(original['camera_end']['lat'],changed['camera_end']['lat'])
            for before,after in zip(plan['scenes'],plan['scenes'][1:]):self.assertEqual(before['exit_state'],after['entry_state'])
        self.assertEqual(travel['scenes'][3]['lighting_preset'],'HERO')

    def test_unknown_style_is_not_silently_ignored(self):
        from engine.planner import PlanningInputError
        with self.assertRaises(PlanningInputError) as raised:
            generate_plan(dict(production_preset='LEGACY', topic='런던 → 파리',duration=20,style='unimplemented comic style'))
        self.assertEqual(raised.exception.as_dict()['code'],'UNSUPPORTED_STYLE')

if __name__=='__main__':unittest.main()
