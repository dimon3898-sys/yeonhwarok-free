import importlib.util
import json
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('astra_history_builder', ROOT / 'tools/build_history_profile.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
REPLAY = json.loads((ROOT / 'reports/ORIGINAL_SOURCE_REPLAY.json').read_bytes())
PLAN = Path(REPLAY['preparedPath']).parent / 'PLAN.json'


class QualifiedHistoryProfileTest(unittest.TestCase):
    def test_original_ids_frames_source_shapes_and_explicit_unknown(self):
        profile, catalog, report = builder.build(PLAN)
        original = json.loads(PLAN.read_bytes())
        self.assertEqual([(x['chapterId'], x['eventId'], x['startFrame'], x['endFrame']) for x in profile['chapters']],
                         [(x['chapterId'], x['eventId'], x['startFrame'], x['endFrame']) for x in original['productionV3']['eventChapters']])
        frames = [row for row in profile['sourceSchedule'] for _ in range(row['startFrame'], row['endFrame'])]
        self.assertEqual(len(frames), 2400)
        self.assertEqual({x['chapterId'] for x in frames if x['stateId'] == 'BUSAN'}, {'chapter-03'})
        self.assertTrue(all(frames[f]['stateId'] is None for f in range(600, 1400)))
        dates = [x['sourceDate'] for x in profile['sourceSchedule'] if x['sourceDate']]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(profile['fullControlStates'], [])
        self.assertEqual(profile['controlTransitions'], [])
        self.assertFalse(report['fullHistoricalControlAndMorphReady'])
        self.assertEqual(len([v for v in catalog['sources'].values() if v.get('partialSegments')]), 9)
        self.assertEqual(frames[300]['truthKind'], 'observed')
        self.assertEqual(frames[300]['sourceDate'], '1950-06-28')
        source = catalog['sources'][frames[300]['stateId']]
        self.assertEqual(source['classification'], 'OBSERVED_ROK_FRONT')
        self.assertFalse(source['fullControlPolygon'])
        self.assertEqual(source['renderConsumer'], 'DIRECTOR_ADDITIONAL_PARTIAL_FRONT')

    def test_control_boundary_unknown_not_filled_by_previous_event(self):
        profile, _, _ = builder.build(PLAN)
        for previous, next_chapter in zip(profile['chapters'], profile['chapters'][1:]):
            self.assertIsNone(previous['controlEndState'])
            self.assertIsNone(next_chapter['controlStartState'])
        self.assertFalse(profile['audio']['enabled'])
        self.assertEqual(profile['audio']['cues'], [])
        self.assertEqual(profile['markerEvidence'], [])

    def test_schematic_and_geographic_context_are_not_observed_troop_positions(self):
        profile, catalog, _ = builder.build(PLAN)
        self.assertTrue(all(not loc['troopPosition'] and loc['role'] == 'GEOGRAPHIC_CONTEXT_ONLY' for loc in profile['locations']))
        self.assertEqual(len([loc for loc in profile['locations'] if loc['id'] == 'INCHEON']), 1)
        self.assertEqual(catalog['sources']['BUSAN']['truthKind'], 'schematic')
        self.assertFalse(catalog['sources']['BUSAN']['enemyComplementAdmitted'])
        self.assertFalse(catalog['sources']['BUSAN']['fullControlPolygon'])

    def test_wrong_actual_source_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'PLAN.json'
            file.write_bytes(PLAN.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'SOURCE_HASH_MISMATCH'):
                builder.build(file)

    def test_date_regression_and_timeline_gap_rejected(self):
        for mutation, error in [('date', 'HISTORY_SOURCE_DATE_REGRESSION'), ('gap', 'HISTORY_CONTIGUOUS_HALF_OPEN_SCHEDULE_REQUIRED')]:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'fixtures').mkdir()
                shutil.copytree(ROOT / 'source-review', root / 'source-review', ignore=shutil.ignore_patterns('*.png'))
                edits = json.loads((ROOT / 'fixtures/HISTORY_EDITS.json').read_bytes())
                if mutation == 'date':
                    edits['sourceSchedule'][10]['sourceDate'] = '1950-11-24'
                else:
                    edits['sourceSchedule'][1]['startFrame'] += 1
                (root / 'fixtures/HISTORY_EDITS.json').write_text(json.dumps(edits))
                with patch.object(builder, 'ROOT', root), self.assertRaisesRegex(ValueError, error):
                    builder.build(PLAN)


if __name__ == '__main__':
    unittest.main()
