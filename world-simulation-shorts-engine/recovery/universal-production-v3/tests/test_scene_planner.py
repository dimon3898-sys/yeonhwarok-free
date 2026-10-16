"""Focused CPU checks: actual old compiler, chapter source truth and clocks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scene_planner as production


@unittest.skipUnless(shutil.which('node'), 'BLOCKED: unchanged original Node planner required')
class ProductionSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = production.build_scene_plan('한국전쟁의 전선 변화를 80초 영상으로 만들어줘.')
        cls.contracts, cls.parent_planner, _ = production._parent()

    def test_persisted_fixture_passes_current_source_and_clock_validation(self):
        persisted = json.loads((ROOT / "fixtures/PLAN_80S.json").read_bytes())
        self.assertIs(production.validate_production_plan(persisted, require_renderable=True), persisted)

    def test_actual_parent_compiler_and_five_geometries_preserved(self):
        old = self.parent_planner.plan_topic('한국전쟁의 전선 변화를 80초 영상으로 만들어줘.')
        self.assertEqual(self.plan['legacyScenePlan'], old['legacyScenePlan'])
        self.assertEqual(len(self.plan['legacyScenePlan']['time_steps']), 5)
        self.assertEqual(self.plan['renderProfile']['adapter'], 'UNIVERSAL_AREA_ASTRA_V2')
        self.assertEqual(self.plan['renderProfile']['productionAdapter'], 'UNIVERSAL_PRODUCTION_V3')
        self.assertFalse(self.plan['productionV3']['newGeometryCreated'])
        self.assertFalse(self.plan['productionV3']['newHistoricalUnitPositionsCreated'])

    def test_80_seconds_exactly_12_chapters_and_work_scenes(self):
        self.assertEqual(self.plan['totalFrames'], 2400)
        self.assertEqual(len(self.plan['productionV3']['eventChapters']), 12)
        self.assertEqual(len(self.plan['scenes']), 12)
        self.assertEqual([chapter['startFrame'] for chapter in self.plan['productionV3']['eventChapters']], list(range(0, 2400, 200)))
        self.assertEqual(sum(scene['endFrame'] - scene['startFrame'] for scene in self.plan['scenes']), 2400)
        self.assertEqual([(s['startFrame'], s['endFrame']) for s in self.plan['scenes'][:3]], [(0, 200), (200, 445), (445, 600)])
        self.assertEqual(self.plan['scenes'][1]['chapterRefs'], ['chapter-02', 'chapter-03'])
        self.assertIs(production.validate_production_plan(self.plan, require_renderable=True), self.plan)

    def test_duration_matrix_same_allocator_no_frame_buffers(self):
        for seconds in (80, 120, 180, 300, 600):
            with self.subTest(seconds=seconds):
                plan = production.build_scene_plan('한국전쟁 전선 변화', duration_seconds=seconds)
                self.assertEqual(plan['totalFrames'], seconds * 30)
                self.assertEqual(len(plan['productionV3']['eventChapters']), 12)
                self.assertLessEqual(max(s['endFrame'] - s['startFrame'] for s in plan['scenes']), 300)
                self.assertEqual(sum(s['endFrame'] - s['startFrame'] for s in plan['scenes']), seconds * 30)
                self.assertNotIn('frameBuffers', plan)
                self.assertNotIn('frames', plan)

    def test_chapter_geometry_clock_covers_all_frames_once(self):
        cursor = 0
        for row in self.plan['productionV3']['geometrySchedule']:
            self.assertEqual(row['startFrame'], cursor)
            self.assertGreater(row['endFrame'], cursor)
            cursor = row['endFrame']
        self.assertEqual(cursor, 2400)
        sampled = [production.source_geometry_frame(self.plan, frame) for frame in range(2401)]
        self.assertTrue(all(isinstance(frame, int) and 60 <= frame < 2400 for frame in sampled))
        self.assertEqual(sampled, sorted(sampled))

    def test_reveal_waits_for_original_camera_lock(self):
        schedule = self.plan['productionV3']['geometrySchedule']
        self.assertEqual(schedule[0]['mode'], 'ARRIVAL_NO_EVENT')
        self.assertEqual(schedule[0]['endFrame'], self.plan['legacyScenePlan']['timing']['camera_lock_frame'])
        self.assertEqual(schedule[1]['mode'], 'REVEAL_SUPPLIED_SNAPSHOT')
        self.assertEqual(production.source_geometry_frame(self.plan, 60), 60)
        self.assertEqual(production.source_geometry_frame(self.plan, 119), 119)

    def test_source_retimming_endpoints_are_integer_and_exact(self):
        for row in self.plan['productionV3']['geometrySchedule']:
            self.assertEqual(production.source_geometry_frame(self.plan, row['startFrame']), row['sourceStartFrame'])
            self.assertEqual(production.source_geometry_frame(self.plan, row['endFrame'] - 1), row['sourceEndFrame'])
            self.assertIn('도식', row['snapshotLabel'])
            self.assertFalse(row['measuredMilitaryControl'])

    def test_china_entry_does_not_get_later_november_front(self):
        chapter = self.plan['productionV3']['eventChapters'][6]
        self.assertEqual(chapter['eventId'], 'CHINESE_INTERVENTION')
        self.assertEqual(chapter['eventTimeWindow']['value'], '1950-10-25')
        self.assertEqual(chapter['geometryStateIds'], ['BUSAN'])
        self.assertIn('1950.09.01', chapter['onScreenGeometryLabel'])
        selected = [row for row in self.plan['productionV3']['geometrySchedule'] if row['chapterId'] == chapter['chapterId']]
        self.assertTrue(all(row['sourceStateId'] == 'BUSAN' for row in selected))

    def test_north_advance_editorial_window_before_china_and_later_snapshot_deferred(self):
        chapters = self.plan['productionV3']['eventChapters']
        self.assertEqual(chapters[5]['presentationPolicy']['dateWindow']['end'], '1950-10-24')
        self.assertEqual(chapters[5]['geometryStateIds'], ['BUSAN'])
        self.assertEqual(chapters[7]['geometryStateIds'], ['NORTH_ADVANCE', 'SEOUL_WITHDRAWAL'])
        self.assertIn('1950.11.24', chapters[7]['onScreenGeometryLabel'])
        self.assertIn('1951.01.04', chapters[7]['onScreenGeometryLabel'])

    def test_unknown_event_fronts_cannot_gain_new_geometry_or_units(self):
        for chapter in self.plan['productionV3']['eventChapters']:
            self.assertEqual(chapter['newUnitPositions'], [])
            self.assertFalse(chapter['historicalUnitPositionsVerified'])
            self.assertEqual(chapter['styleIntent']['opponentComplementAllowed'], False)
            self.assertEqual(chapter['geometryLabelPolicy'], 'ACTIVE_SCHEDULE_SNAPSHOT_LABEL_OVERRIDES_CHAPTER_SUMMARY')
        self.assertEqual(self.plan['productionV3']['visualBindings']['unitPositions'], [])

    def test_area_ownership_is_only_exact_original_held_core(self):
        areas = {row['id']: row for row in self.plan['legacyScenePlan']['areas']}
        for binding in self.plan['productionV3']['visualBindings']['areaStyles']:
            self.assertEqual(binding['sourceGeometryRef'], areas[binding['areaId']]['geometry_ref'])
            self.assertEqual(binding['sourceProof']['factsSHA256'], self.plan['sourceManifest']['factsSHA256'])
            self.assertFalse(binding['measuredMilitaryControl'])
            self.assertFalse(binding['enemyComplementAdmitted'])
        self.assertEqual(len(areas), 5)

    def test_production_boundaries_preserve_parent_and_new_contracts_separately(self):
        for before, after in zip(self.plan['scenes'], self.plan['scenes'][1:]):
            self.assertEqual(before['boundaryEnd'], after['boundaryStart'])
            self.assertEqual(before['productionBoundaryEnd'], after['productionBoundaryStart'])
            self.assertIn('GPU_POSE_AND_PIXELS_PENDING', after['productionBoundaryStart']['validationBasis'])
        changed = deepcopy(self.plan)
        changed['scenes'][1]['productionBoundaryStart']['sourceGeometryFrame'] += 1
        with self.assertRaisesRegex(ValueError, 'V3_ACTUAL_PRODUCTION_BOUNDARY_OR_SPLIT_MISMATCH'):
            production.validate_production_plan(changed)

    def test_actual_work_cut_is_inside_production_transition(self):
        cuts = {scene['startFrame'] for scene in self.plan['scenes'][1:]}
        actual = [row for row in self.plan['productionV3']['geometrySchedule'] if row['mode'] == 'TRANSITION_SUPPLIED_SNAPSHOTS' and any(row['startFrame'] < cut < row['endFrame'] - 1 for cut in cuts)]
        self.assertTrue(actual)
        self.assertEqual(actual[0]['startFrame'], 400)
        self.assertEqual(actual[0]['endFrame'], 490)
        self.assertLess(production.source_geometry_frame(self.plan, 444), production.source_geometry_frame(self.plan, 445))
        self.assertEqual(self.plan['productionV3']['visualProfile']['geometryTransitionDurationSeconds'], 3.0)

    def test_source_clock_or_chapter_tamper_rejected(self):
        for change in (lambda p: p['productionV3']['geometrySchedule'][0].__setitem__('sourceEndFrame', 200),
                       lambda p: p['productionV3']['eventChapters'][6].__setitem__('displayLabel', 'wrong date'),
                       lambda p: p['productionV3']['visualBindings'].__setitem__('unitPositions', [[1, 2]])):
            plan = deepcopy(self.plan)
            change(plan)
            with self.assertRaisesRegex(ValueError, 'V3_CHAPTER_OR_GEOMETRY_METADATA_MISMATCH'):
                production.validate_production_plan(plan)

    def test_future_november_geometry_for_october_event_is_rejected(self):
        chronology = deepcopy(self.plan['productionV3']['chronology'])
        chronology['stages'][6]['presentationPolicy']['geometryStateIds'] = ['NORTH_ADVANCE']
        with self.assertRaisesRegex(ValueError, 'V3_FUTURE_SNAPSHOT_FOR_DATED_EVENT_FORBIDDEN'):
            production._metadata(self.plan, chronology, self.plan['productionV3']['ownershipEvidence'], self.plan['productionV3']['visualProfile'], self.plan['productionV3']['sourceBindings'])

    def test_new_or_unverified_ownership_rejected(self):
        ownership = deepcopy(self.plan['productionV3']['ownershipEvidence'])
        ownership['areaStyles'][0]['sourceProof']['factsSHA256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'V3_UNVERIFIED_OR_COMPLEMENT_OWNERSHIP_FORBIDDEN'):
            production._metadata(self.plan, self.plan['productionV3']['chronology'], ownership, self.plan['productionV3']['visualProfile'], self.plan['productionV3']['sourceBindings'])

    def test_official_retrieval_unverified_is_not_upgraded_by_planning(self):
        self.assertFalse(self.plan['productionV3']['officialSourceBodiesVerified'])
        history_records = [row for row in self.plan['sourceManifest']['records'] if row['id'].startswith('HISTORY_')]
        for row in history_records:
            self.assertEqual(row['retrieval_http_status'], 403)
            self.assertIsNone(row['original_body_sha256'])
        for chapter in self.plan['productionV3']['eventChapters']:
            self.assertFalse(chapter['eventTimeWindow']['officialBodyProofAvailable'])

    def test_frozen_parent_hash_verified(self):
        self.assertEqual(hashlib.sha256((production.PARENT / 'UNIVERSAL_FILES.json').read_bytes()).hexdigest(), production.PARENT_MANIFEST_SHA)
        self.assertFalse(self.plan['productionV3']['visualQualityApproved'])
        self.assertFalse(self.plan['performanceTarget']['costApproved'])

    def test_digest_is_optional_operator_input_not_hardware_attestation(self):
        self.assertNotIn('imageDigest', self.plan['renderProfile'])
        other = production.build_scene_plan('한국전쟁 전선 변화', duration_seconds=80, image_digest='sha256:' + '9' * 64)
        self.assertEqual(other['renderProfile']['imageDigest'], 'sha256:' + '9' * 64)
        self.assertEqual(other['renderProfile']['hardwareValidation'], 'NOT_EXECUTED')

    def test_cli_never_overwrites_existing_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'plan.json'
            target.write_bytes(b'protected prior plan')
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'scene_planner.py'), '한국전쟁 80초', '--output', str(target)], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_bytes(), b'protected prior plan')


if __name__ == '__main__':
    unittest.main()
