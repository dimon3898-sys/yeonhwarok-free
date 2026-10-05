"""Fail-closed historical map requests and causal maritime narration.

These execute the real offline planner; they do not render Earth frames or modify
saved production plans. Route lengths come from the sourced waypoint geometry.
"""
from datetime import datetime,timedelta,timezone
import re,unittest
from engine.gis import great_circle_distance
from engine.planner import generate_plan
from engine.plugins import UnsupportedVisualRequirement

def plan(topic,duration=20):
    return generate_plan(dict(production_preset='LEGACY', topic=topic,duration=duration,quality='HIGH',tts=True))

class HistoricalMapGuardTests(unittest.TestCase):
    def test_recent_past_geographic_states_require_historical_gis(self):
        today=datetime.now(timezone.utc).date();past=today.year-1
        yesterday=today-timedelta(days=1)
        topics=[f'{past}년 미국과 중국 세계지도 비교',
                f'Map comparison of United States and China in {past}',
                f'{yesterday.isoformat()} 미국과 중국 지도 비교',
                f'{yesterday.year}년 {yesterday.month}월 {yesterday.day}일 미국과 중국 지도 비교',
                f'{yesterday:%Y/%m/%d} 미국과 중국 지도 비교',
                f'United States and China map comparison on {yesterday:%B} {yesterday.day}, {yesterday.year}',
                f'United States and China map comparison on {yesterday.day} {yesterday:%B %Y}']
        for topic in topics:
            with self.subTest(topic=topic):
                with self.assertRaises(UnsupportedVisualRequirement) as raised:plan(topic)
                self.assertTrue({'HISTORICAL_GIS','TIME_MORPH'}.issubset(raised.exception.modules))

    def test_current_geographic_comparison_remains_supported(self):
        today=datetime.now(timezone.utc).date()
        for topic in [f'{today.year}년 미국과 중국 세계지도 비교',f'{today.isoformat()} 미국과 중국 지도 비교',
                      f'{today.year}년 {today.month}월 {today.day}일 미국과 중국 지도 비교',
                      f'United States and China map comparison on {today:%B} {today.day}, {today.year}']:
            with self.subTest(topic=topic):
                result=plan(topic)
                self.assertTrue(result['gate']['passed'],result['gate']['errors'])
                self.assertEqual(result['story']['domain'],'comparison')

    def test_dates_alone_do_not_turn_a_modern_flight_into_historical_gis(self):
        past=datetime.now(timezone.utc).year-1
        for topic in [f'{past}년 뉴욕 → 런던 민간 항공 경로',
                      f'Civil aviation New York → London in {past}']:
            with self.subTest(topic=topic):
                result=plan(topic)
                self.assertTrue(result['gate']['passed'],result['gate']['errors'])
                self.assertEqual(result['story']['domain'],'aviation')

    def test_flight_identifiers_are_not_interpreted_as_map_years(self):
        for topic in ['뉴욕 → 런던 항공편 2010의 현대 지도',
                      'Flight 2010 New York → London modern map',
                      'Map comparison of United States and China in 75 seconds']:
            with self.subTest(topic=topic):
                result=plan(topic)
                self.assertTrue(result['gate']['passed'],result['gate']['errors'])

class ShippingNarrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shipping=plan('수에즈 운하가 7일 동안 막힌다면?',75)

    def test_75_second_script_progresses_causally_without_gis_implementation_jargon(self):
        scenes=self.shipping['scenes'];lines=[scene['narration'] for scene in scenes]
        self.assertEqual(len(lines),10)
        self.assertEqual(len(set(lines)),len(lines))
        self.assertFalse(any(word in line for line in lines for word in ['공개 해상 그래프','렌더','GIS','Scene']))
        self.assertIn('로테르담',lines[1]);self.assertIn('운하',lines[2]);self.assertIn('싱가포르',lines[3])
        self.assertIn('희망봉',lines[5]);self.assertIn('싱가포르',lines[8]);self.assertIn('예측은 아닙니다',lines[-1])
        blocked=[scene for scene in scenes if any(event['kind']=='route_blocked' for event in scene['visual_events'])]
        self.assertEqual(len(blocked),1)
        self.assertIn('7일',blocked[0]['narration']);self.assertIn('가정합니다',blocked[0]['narration'])
        self.assertIn('A01',blocked[0]['claim_ids'])
        self.assertEqual(next(claim for claim in self.shipping['story']['claims'] if claim['id']=='A01')['status'],'ASSUMPTION')

    def test_comparison_distance_is_derived_from_the_exact_authored_sea_routes(self):
        routes={route['route_id']:route for scene in self.shipping['scenes'] for route in scene['routes']}
        def distance(route):return sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:]))
        difference=round(distance(routes['R_CAPE'])-distance(routes['R_SUEZ']))
        narrated=next(scene for scene in self.shipping['scenes'] if '킬로미터' in scene['narration'])
        value=int(re.search(r'([\d,]+)킬로미터',narrated['narration']).group(1).replace(',',''))
        self.assertEqual(value,difference)
        self.assertTrue(all(route['source_ids'] for route in routes.values()))
        self.assertTrue(any(claim['status']=='SIMULATION' and 'A01' in claim['assumption_ids'] for claim in self.shipping['story']['claims']))

    def test_narration_budget_and_nonrepetition_hold_across_authored_video_lengths(self):
        for duration in [20,40,60,75,180,183.5]:
            with self.subTest(duration=duration):
                result=self.shipping if duration==75 else plan('수에즈 운하가 7일 동안 막힌다면?',duration)
                self.assertTrue(result['gate']['passed'],result['gate']['errors'])
                for scene in result['scenes']:
                    self.assertLessEqual(len(scene['narration'].replace(' ',''))/5.8,scene['duration']*.9)
                for before,after in zip(result['scenes'],result['scenes'][1:]):
                    self.assertNotEqual(before['narration'],after['narration'])
                if duration==20:self.assertTrue(any('희망봉' in scene['narration'] for scene in result['scenes']))

    def test_reference_arrival_at_suez_does_not_narrate_an_alternative_arrival_in_singapore(self):
        result=plan('수에즈 운하가 7일 동안 막힌다면?',180)
        alternative_start=min(scene['start_time']+route['start_time'] for scene in result['scenes'] for route in scene['routes'] if route['route_id']=='R_CAPE')
        canal_arrival=next(scene for scene in result['scenes'] if any(event['kind']=='arrival' and event['target_id']=='SUEZ_CANAL' for event in scene['visual_events']))
        self.assertLess(canal_arrival['start_time'],alternative_start)
        self.assertNotIn('싱가포르로 다가갑니다',canal_arrival['narration'])
        self.assertNotIn('우회한 배',canal_arrival['narration'])

if __name__=='__main__':unittest.main()
