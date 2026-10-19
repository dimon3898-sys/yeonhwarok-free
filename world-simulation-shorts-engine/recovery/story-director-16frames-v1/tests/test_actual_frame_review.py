"""Synthetic source-vs-consumer checks; not historical or render verification."""
import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('director_actual_review', ROOT / 'tools/review_actual_frames.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class ActualFrameReviewTests(unittest.TestCase):
    def expected(self, kind):
        return {'chapterId': 'synthetic-chapter', 'eventId': 'synthetic-event',
                'geometryTruthKind': kind, 'frontId': 'synthetic-partial-line'}

    def diagnostic(self):
        return {'productionV3': {'chapter': {'chapterId': 'synthetic-chapter', 'eventId': 'synthetic-event'}},
                'area': {'controls': {'areas': [], 'fronts': []}},
                'sourceIntegrity': {'fictional65422SceneUsed': False}}

    def test_partial_line_does_not_authorize_area_fill(self):
        d = self.diagnostic(); d['area']['controls']['fronts'] = [{'id': 'synthetic-partial-line'}]
        self.assertTrue(m.compare_source(self.expected('ARCHIVAL_PARTIAL_FRONT'), d)[1])
        d['area']['controls']['areas'] = [{'id': 'UNAUTHORIZED_AREA'}]
        self.assertFalse(m.compare_source(self.expected('ARCHIVAL_PARTIAL_FRONT'), d)[1])

    def test_no_geometry_opening_does_not_invent_event_front(self):
        d = self.diagnostic()
        self.assertTrue(m.compare_source(self.expected('NO_EVENT_GEOMETRY'), d)[1])
        d['area']['controls']['fronts'] = [{'id': 'INVENTED'}]
        self.assertFalse(m.compare_source(self.expected('NO_EVENT_GEOMETRY'), d)[1])

    def test_chapter_time_mismatch_is_a_failure(self):
        d = self.diagnostic(); d['productionV3']['chapter']['eventId'] = 'OTHER_EVENT'
        self.assertFalse(m.compare_source(self.expected('NO_EVENT_GEOMETRY'), d)[0])

    def test_native_location_dot_is_not_a_national_military_unit(self):
        d = self.diagnostic(); d['foreground'] = {'items': [{'kind': 'MARKER', 'role': 'LOCATION'}]}
        d['productionV3']['noInferredHistoricalUnits'] = True
        self.assertEqual((1, 0), m.unit_counts(d))

    def test_hidden_native_title_is_not_claimed_as_actually_drawn_text(self):
        d = self.diagnostic(); d['foreground'] = {'items': [{'kind': 'TEXT', 'role': 'EVENT_TITLE', 'text': 'HIDDEN'}, {'kind': 'TEXT', 'role': 'LOCATION_LABEL', 'text': 'VISIBLE'}], 'visibleRoles': ['LOCATION_LABEL']}
        self.assertEqual(['VISIBLE'], m.labels_and_layout(d)[0])

    def test_cpu_camera_profile_without_actual_native_projection_is_not_a_pixel_witness(self):
        d = self.diagnostic(); d['camera'] = {'flatBounds': [1, 2, 3, 4], 'productionCamera': {'storyDirector': {'pixelsPerDegree': [3, 4]}}}
        _, native, _ = m.camera_actual(d)
        self.assertEqual({}, native)


if __name__ == '__main__':
    unittest.main()
