"""Native GIS, visual hierarchy and additive admission; no GPU draw claims."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engine import bold_infographic as bold
from engine import infographic_contract as parent


class BoldNativeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = parent.load_registry()
        cls.records = {row['id']: row for row in cls.registry['geometries']}

    def test_native_country_hole_excludes_enclave_without_new_geometry(self):
        self.assertFalse(bold.polygon_contains_point(self.records['COUNTRY_ZAF'], [28.25, -29.5]))
        # Interior probes avoid asserting that a generalized 50m coastline
        # follows the exact edge of a real coastal city's harbour.
        self.assertTrue(bold.polygon_contains_point(self.records['COUNTRY_ZAF'], [28.05, -26.2]))

    def test_sourced_event_point_selects_actual_existing_country(self):
        self.assertTrue(bold.polygon_contains_point(self.records['COUNTRY_EGY'],
            self.records['LOCATION_SUEZ_CANAL']['coordinates']))
        self.assertTrue(bold.polygon_contains_point(self.records['COUNTRY_SGP'],
            self.records['LOCATION_SINGAPORE']['coordinates']))
        self.assertFalse(bold.polygon_contains_point(self.records['COUNTRY_EGY'],
            self.records['LOCATION_SINGAPORE']['coordinates']))

    def test_point_is_not_an_area(self):
        self.assertFalse(bold.polygon_contains_point(self.records['LOCATION_SUEZ_CANAL'], [32.38, 30.31]))
        self.assertEqual(bold._polygons(self.records['LOCATION_SUEZ_CANAL']), [])

    def test_native_dateline_parts_remain_separate(self):
        record = self.records['COUNTRY_FJI']
        self.assertGreater(len(bold._polygons(record)), 1)
        self.assertFalse(bold.polygon_contains_point(record, [0, -17.8]))
        self.assertTrue(bold.polygon_contains_point(record, [178.1, -17.8]))

    def test_real_land_neighbors_have_shared_original_edges(self):
        primary = self.records['COUNTRY_EGY']
        contexts = bold.select_context_regions(primary,
            self.records['LOCATION_SUEZ_CANAL']['coordinates'], self.registry)
        adjacent = {row['geometry_ref']: row for row in contexts
                    if row['selection_method'] == 'SHARED_NATIVE_BOUNDARY'}
        self.assertEqual(set(adjacent), {'COUNTRY_LBY', 'COUNTRY_SDN', 'COUNTRY_ISR', 'COUNTRY_PSX'})
        self.assertTrue(all(row['shared_edge_count'] > 0 for row in adjacent.values()))
        self.assertTrue(all(row['record'] == self.records[row['geometry_ref']] for row in contexts))

    def test_island_context_is_not_falsely_called_shared_border(self):
        contexts = bold.select_context_regions(self.records['COUNTRY_SGP'],
            self.records['LOCATION_SINGAPORE']['coordinates'], self.registry)
        selected = {row['geometry_ref']: row for row in contexts}
        self.assertIn('COUNTRY_MYS', selected)
        self.assertIn('COUNTRY_IDN', selected)
        self.assertTrue(all(row['selection_method'] == 'VERIFIED_GEOGRAPHIC_PROXIMITY'
                            and row['shared_edge_count'] == 0 for row in contexts))

    def test_context_is_bounded_and_does_not_paint_the_world(self):
        contexts = bold.select_context_regions(self.records['COUNTRY_EGY'],
            self.records['LOCATION_SUEZ_CANAL']['coordinates'], self.registry, maximum=3)
        self.assertEqual(len(contexts), 3)
        self.assertNotIn('COUNTRY_BRA', [row['geometry_ref'] for row in contexts])
        self.assertNotIn('COUNTRY_EGY', [row['geometry_ref'] for row in contexts])

    def test_visual_profile_preserves_terrain_and_hierarchy(self):
        profile = bold.profile()
        primary, secondary = [profile['geometry'][role] for role in ['PRIMARY', 'SECONDARY']]
        self.assertGreater(primary['fill_alpha'], secondary['fill_alpha'])
        self.assertLess(primary['fill_alpha'], 1)
        self.assertEqual(primary['core_width_px'], 8)
        self.assertEqual(secondary['core_width_px'], 3)
        self.assertGreater(primary['edge_width_px'], primary['core_width_px'])
        self.assertEqual(profile['geometry']['blend_mode'], 'source-over')
        self.assertEqual(profile['marker_and_text'], 'EXACT_V022')
        self.assertEqual(bold.PROFILE_PATH.read_bytes(), bold.PUBLIC_PATH.read_bytes())


class BoldAdditiveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema, gpu_preflight, visibility, infographic_backend
        saved = (schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH,
                 visibility.TOOL, infographic_backend.infographic_command,
                 parent.renderer_version, parent.diagnostic_record)
        def restore():
            (schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH,
             visibility.TOOL, infographic_backend.infographic_command,
             parent.renderer_version, parent.diagnostic_record) = saved
        cls.addClassCleanup(restore)
        environment = patch.dict(os.environ, {
            'WORLD_ENGINE_VISUAL_QUALITY_VERSION': 'v018',
            'WORLD_ENGINE_EVENT_QUALITY_VERSION': 'v019',
            'WORLD_ENGINE_REFERENCE_EFFECTS_VERSION': 'v020',
            'WORLD_ENGINE_STORY_PROGRESSION_VERSION': 'v021',
            'WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION': 'v022',
            'WORLD_ENGINE_DIRECTION_VERSION': 'v013',
            'WORLD_ENGINE_SECOND_EVENT_TEST': '1',
            'WORLD_ENGINE_RETURN_WIDE_TEST': '0',
            'WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST': '0',
        })
        environment.start()
        cls.addClassCleanup(environment.stop)
        from engine.qa_planner import generate_deployment_plan
        cls.baseline = generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',
            duration=24, direction_profile='MAP_INFOGRAPHIC_QA_V022', quality='HIGH',
            pace='FAST_PLUS', tts=False, subtitles=False, bgm=True, sfx=True))
        cls.selected = bold.prepare_bold_infographic(cls.baseline)

    def test_on_adds_only_visual_contract_and_gate_record(self):
        restored = deepcopy(self.selected)
        restored['metadata'].pop('bold_infographic')
        for scene in restored['scenes']:
            scene.pop('bold_infographic')
        restored['gate'] = deepcopy(self.baseline['gate'])
        self.assertEqual(restored, self.baseline)
        self.assertTrue(bold.validate_bold_infographic(self.selected)['passed'])

    def test_off_preserves_complete_v022_baseline_and_copy_isolation(self):
        snapshot = deepcopy(self.baseline)
        off = bold.prepare_bold_infographic(self.baseline, enabled=False)
        self.assertEqual(off, snapshot)
        off['scenes'][0]['labels'][0]['text'] = 'test isolation'
        self.assertEqual(self.baseline, snapshot)

    def test_camera_quality_and_all_event_state_data_are_unchanged(self):
        before, after = self.baseline['scenes'][0], self.selected['scenes'][0]
        self.assertEqual(parent._camera_snapshot(before), parent._camera_snapshot(after))
        self.assertEqual(parent._quality_snapshot(before), parent._quality_snapshot(after))
        self.assertEqual(before['infographic'], after['infographic'])
        self.assertEqual(parent.parent._source_snapshot(before), parent.parent._source_snapshot(after))
        self.assertEqual(after['frame_count'], 720)

    def test_primary_focus_persists_across_original_canal_states(self):
        rows = self.selected['scenes'][0]['bold_infographic']['regions']
        primary = [row for row in rows if row['role'] == 'PRIMARY']
        self.assertEqual([(row['geometry_ref'], row['start_frame'], row['end_frame']) for row in primary],
                         [('COUNTRY_EGY', 60, 450), ('COUNTRY_SGP', 450, 720)])
        self.assertTrue(all('state_after' not in row and 'state_before' not in row for row in rows))
        for frame in range(720):
            self.assertLessEqual(sum(row['start_frame'] <= frame < row['end_frame'] for row in primary), 1)

    def test_secondary_context_is_separate_sourced_geography(self):
        selected = self.selected['scenes'][0]['bold_infographic']
        originals = {row['id']: row for row in parent.load_registry()['geometries']}
        self.assertEqual(selected['geometry_ids'], sorted(row['id'] for row in selected['geometries']))
        self.assertTrue(all(row == originals[row['id']] for row in selected['geometries']))
        for row in selected['regions']:
            if row['role'] == 'SECONDARY':
                self.assertNotEqual(row['geometry_ref'], row['primary_geometry_ref'])
                self.assertIn(row['selection_method'], {'SHARED_NATIVE_BOUNDARY', 'VERIFIED_GEOGRAPHIC_PROXIMITY'})

    def test_mutated_native_geometry_and_country_state_forgery_fail(self):
        for mutate in [lambda selected: selected['geometries'][0]['coordinates'].append([0, 0]),
                       lambda selected: selected['regions'][0].__setitem__('geometry_ref', 'COUNTRY_BRA'),
                       lambda selected: selected['regions'][0].__setitem__('state_after', 'CLOSED'),
                       lambda selected: selected.__setitem__('parent_camera_sha256', '0'*64)]:
            changed = deepcopy(self.selected)
            mutate(changed['scenes'][0]['bold_infographic'])
            changed['metadata']['bold_infographic']['scene_contract_sha256'] = {
                scene['scene_id']: parent.canonical_sha(scene['bold_infographic']) for scene in changed['scenes']}
            self.assertFalse(bold.validate_bold_infographic(changed)['passed'])

    def test_partial_selection_and_visual_downgrade_fail_closed(self):
        for mutate in [lambda plan: plan['metadata'].pop('bold_infographic'),
                       lambda plan: plan['scenes'][0].pop('bold_infographic'),
                       lambda plan: plan['scenes'][0]['bold_infographic'].__setitem__('profile_id', 'V022_LEGACY')]:
            changed = deepcopy(self.selected)
            mutate(changed)
            self.assertFalse(bold.validate_bold_infographic(changed)['passed'])

    def test_backend_changes_only_opted_in_page_and_preserves_gpu_transport(self):
        from engine import infographic_backend
        with tempfile.TemporaryDirectory() as directory:
            scene_path = Path(directory) / 'scene.json'
            command = ['node', 'unchanged-renderer', '--scene-json', str(scene_path), '--url',
                'http://127.0.0.1:8000/static/render_production_earth.html?unchanged=1',
                '--browser', '/approved/chromium-wrapper', '--gpu-profile', 'nvidia-vulkan',
                '--output', str(Path(directory)/'output.mp4')]
            index = command.index('--url')+1
            scene_path.write_text(json.dumps(self.selected['scenes'][0]))
            mapped = infographic_backend.infographic_command(command)
            self.assertEqual(mapped[index], 'http://127.0.0.1:8000/static/render_bold_infographic_earth.html?unchanged=1')
            self.assertEqual(mapped[:index], command[:index])
            self.assertEqual(mapped[index+1:], command[index+1:])
            scene_path.write_text(json.dumps(self.baseline['scenes'][0]))
            legacy = infographic_backend.infographic_command(command)
            self.assertEqual(legacy[index], 'http://127.0.0.1:8000/static/render_infographic_earth.html?unchanged=1')

    def test_renderer_cache_identity_separates_profiles_and_preserves_off(self):
        scene = self.baseline['scenes'][0]
        old = parent.renderer_version(scene)
        self.assertEqual(parent.renderer_version(bold.prepare_bold_infographic(self.baseline, enabled=False)['scenes'][0]), old)
        self.assertNotEqual(parent.renderer_version(self.selected['scenes'][0]), old)

    def test_diagnostic_record_retains_original_and_child_source_evidence(self):
        record = parent.diagnostic_record(self.selected)
        self.assertEqual(record['version'], 'v022')
        child = record['bold_infographic']
        self.assertEqual(child['profile_id'], bold.PROFILE_ID)
        self.assertEqual(child['physical_gpu'], 'NOT_RUN')
        self.assertEqual(child['scenes'][0]['regions'], self.selected['scenes'][0]['bold_infographic']['regions'])
        self.assertNotIn('bold_infographic', parent.diagnostic_record(self.baseline))

    def test_runtime_validation_reinstalls_after_original_callable_restore(self):
        from engine import schema, gpu_preflight
        current = schema.validate_plan, gpu_preflight.validate_plan
        try:
            schema.validate_plan = lambda plan: dict(passed=True, errors=[], warnings=[])
            gpu_preflight.validate_plan = schema.validate_plan
            bold.install_runtime()
            changed = deepcopy(self.selected)
            changed['scenes'][0].pop('bold_infographic')
            self.assertFalse(schema.validate_plan(changed)['passed'])
            self.assertTrue(getattr(schema.validate_plan, 'bold_infographic_wrapper', False))
        finally:
            schema.validate_plan, gpu_preflight.validate_plan = current


if __name__ == '__main__':
    unittest.main()
