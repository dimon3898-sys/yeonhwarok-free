import unittest,json
from pathlib import Path
from copy import deepcopy
from engine.frame_grid import FrameGrid,canonicalize_plan
from engine.reference_master import reference_blueprint

class IntegerFrameClock(unittest.TestCase):
    def test_durations_and_variable_scene_counts(self):
        for duration in (12,15,20,75,80):
            for count in (3,4,5,7,11):
                clock=FrameGrid(30);windows=clock.allocate(duration*30,[1]*count,[1]*count)
                self.assertEqual(sum(w['frame_count'] for w in windows),duration*30)
                self.assertEqual(windows[-1]['end_frame'],duration*30)
                self.assertEqual(windows[0]['start_frame'],0)
                for a,b in zip(windows,windows[1:]):self.assertEqual(a['end_frame'],b['start_frame'])
    def test_rational_fps(self):
        for fps in (24,25,30,60,'29.97','30000/1001'):
            clock=FrameGrid(fps)
            for duration in (12,15,20,75,80):
                total=clock.frames(duration);windows=clock.allocate(total,[1]*4,[1,1.2,1.4,1.7])
                self.assertEqual(sum(w['frame_count'] for w in windows),total)
                for w in windows:self.assertAlmostEqual(w['duration']*float(clock.fps),w['frame_count'],places=10)
    def test_preserved_v013_before_after(self):
        path=Path(__file__).resolve().parents[1]/'deployment/gcube/framegrid_v013_fixture.json'
        old=json.loads(path.read_text());fixed=canonicalize_plan(deepcopy(old))
        self.assertEqual([abs(s['duration']*30-round(s['duration']*30))<=1e-7 for s in old['scenes']],[False,False,True,False])
        self.assertEqual([w['frame_count'] for w in fixed['metadata']['frame_grid']['scenes']],[64,88,93,115])
        for a,b in zip(old['scenes'],fixed['scenes']):
            self.assertLess(abs(a['duration']-b['duration']),1e-6)
            for key in ('camera_start','camera_end','lighting_preset','render_quality','render_mode','effects'):self.assertEqual(a[key],b[key])
            for key in ('lighting','lighting_entry','entity_min_pixels_1080','route_width_1080','geography_floor'):self.assertEqual(a['direction'][key],b['direction'][key])
        self.assertEqual([round(s['direction']['perception_hold']*30) for s in fixed['scenes']],[52,43,48,61])
    def test_blueprint_integer_boundaries(self):
        for duration in (12,15,20,75,80):
            plan=reference_blueprint(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=duration,qa_mode=duration<20),count_override=4)
            self.assertEqual(sum(b['frame_count'] for b in plan['beats']),duration*30)
            for beat in plan['beats']:self.assertAlmostEqual(beat['duration']*30,beat['frame_count'],places=10)
    def test_invalid_budget(self):
        with self.assertRaises(ValueError):FrameGrid(0)
        with self.assertRaises(ValueError):FrameGrid().allocate(5,[3,3],[1,1])
    def test_finalizer_does_not_silently_absorb_total_mismatch(self):
        with self.assertRaises(ValueError):canonicalize_plan(dict(duration=12,scenes=[dict(scene_id='S001',duration=11)],metadata={}))

    def test_frame_receipt_tampering_is_rejected(self):
        from engine.frame_grid import validate_frame_plan
        p=canonicalize_plan(dict(duration=12,scenes=[dict(scene_id='S001',duration=12)],metadata={}))
        self.assertTrue(validate_frame_plan(p)['passed'])
        p['scenes'][0]['scene_end_frame']=359
        with self.assertRaises(ValueError):validate_frame_plan(p)
