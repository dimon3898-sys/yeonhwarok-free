"""v024 child admission, immutable native GIS and legacy transport; no GPU draw."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engine import bold_infographic as bold
from engine import infographic_contract as parent
from engine import terrain_infographic as terrain


class TerrainProfileTests(unittest.TestCase):
    def test_mirrored_profile_uses_terrain_preserving_color_blend(self):
        value = terrain.profile()
        self.assertEqual(terrain.PROFILE_PATH.read_bytes(), terrain.PUBLIC_PATH.read_bytes())
        self.assertEqual(value['profile_id'], 'VISUAL_TARGET_MAP_V024')
        self.assertEqual(value['parent_version'], 'v023')
        self.assertEqual(value['geometry']['blend_mode'], 'color')
        self.assertTrue(value['geometry']['preserve_holes'])
        self.assertGreaterEqual(value['geometry']['PRIMARY']['luminance_scale'], .80)
        self.assertGreaterEqual(value['geometry']['SECONDARY']['luminance_scale'], .80)
        self.assertEqual(value['geometry']['NEUTRAL']['luminance_scale'], 1)
        self.assertEqual(value['terrain_preservation']['base_material'], 'UNCHANGED')
        self.assertEqual(value['marker_and_text'], 'TIMING_LAYOUT_V022_CONTRAST_V024')
        self.assertEqual(value['contrast']['scope'], 'DRAW_ONLY_V022_TIMING_LAYOUT')
        self.assertEqual(value['contrast']['text_shadow_px'], 3)
        self.assertLessEqual(value['contrast']['marker_edge_px'], 5.5)

    def test_generic_primary_and_context_roles_have_visible_hierarchy(self):
        value = terrain.profile()
        primary, context = [value['geometry'][role] for role in ('PRIMARY', 'SECONDARY')]
        self.assertGreater(primary['fill_alpha'], context['fill_alpha'])
        self.assertGreater(primary['core_width_px'], context['core_width_px'])
        self.assertGreater(primary['edge_width_px'], primary['core_width_px'])
        self.assertGreater(context['edge_width_px'], context['core_width_px'])
        self.assertNotEqual(primary['fill_color'], context['fill_color'])
        for style in (primary, context):
            rgb = [int(style['fill_color'][i:i+2], 16) for i in (1, 3, 5)]
            self.assertGreaterEqual(max(rgb)-min(rgb), 24)
        self.assertEqual(set(value['semantic_roles']), {'PRIMARY', 'SECONDARY', 'NEUTRAL'})

    def test_only_primary_has_bounded_static_edge_halo(self):
        value = terrain.profile()
        self.assertEqual(value['glow_policy'], 'STATIC_PRIMARY_EDGE_ONLY')
        self.assertLessEqual(value['geometry']['PRIMARY']['glow_alpha'], .25)
        self.assertLessEqual(value['geometry']['PRIMARY']['glow_blur_px'], 6)
        self.assertEqual(value['geometry']['SECONDARY']['glow_alpha'], 0)
        self.assertEqual(value['geometry']['SECONDARY']['glow_blur_px'], 0)
        self.assertTrue(all(value['limits'][key] == 0
                            for key in ('added_routes', 'added_entities', 'added_sfx')))

    def test_wrong_blend_gray_context_and_secondary_glow_are_rejected(self):
        for change in (lambda value: value['geometry'].__setitem__('blend_mode', 'source-over'),
                       lambda value: value['geometry']['SECONDARY'].__setitem__('fill_color', '#777777'),
                       lambda value: value['geometry']['SECONDARY'].__setitem__('glow_alpha', .1),
                       lambda value: value['geometry']['PRIMARY'].__setitem__('glow_width_px', 0),
                       lambda value: value['geometry']['SECONDARY'].__setitem__('glow_alpha', False),
                       lambda value: value['geometry']['PRIMARY'].__setitem__('luminance_scale', .79),
                       lambda value: value['geometry']['SECONDARY'].__setitem__('luminance_scale', 1.01),
                       lambda value: value['geometry']['NEUTRAL'].__setitem__('luminance_scale', .9),
                       lambda value: value['geometry']['NEUTRAL'].__setitem__('fill_alpha', .2),
                       lambda value: value['geometry']['NEUTRAL'].__setitem__('fill_alpha', False),
                       lambda value: value['geometry']['NEUTRAL'].__setitem__('luminance_scale', True),
                       lambda value: value['limits'].__setitem__('primary_regions', True),
                       lambda value: value['limits'].__setitem__('added_sfx', False),
                       lambda value: value['geometry']['PRIMARY'].__setitem__('edge_alpha', .2),
                       lambda value: value['contrast'].__setitem__('text_shadow_px', 9),
                       lambda value: value['contrast'].__setitem__('marker_edge_px', 8),
                       lambda value: value['contrast'].__setitem__('font_size', 90),
                       lambda value: value['geometry']['PRIMARY'].__setitem__('fill_alpha', float('nan'))):
            value = deepcopy(terrain.profile())
            change(value)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'profile.json'
                path.write_text(json.dumps(value))
                with patch.object(terrain, 'PROFILE_PATH', path), patch.object(terrain, 'PUBLIC_PATH', path):
                    with self.assertRaises(ValueError):
                        terrain.profile()


class TerrainAdditiveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema, gpu_preflight, visibility, infographic_backend, semantic_timeline
        saved = (schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH,
                 visibility.TOOL, infographic_backend.infographic_command,
                 parent.renderer_version, parent.diagnostic_record, semantic_timeline.validate_production_plan)
        def restore():
            (schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH,
             visibility.TOOL, infographic_backend.infographic_command,
             parent.renderer_version, parent.diagnostic_record, semantic_timeline.validate_production_plan) = saved
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
        qa = generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',
            duration=24, direction_profile='MAP_INFOGRAPHIC_QA_V022', quality='HIGH',
            pace='FAST_PLUS', tts=False, subtitles=False, bgm=True, sfx=True))
        cls.baseline = bold.prepare_bold_infographic(qa)
        cls.old_cache = parent.renderer_version(cls.baseline['scenes'][0])
        cls.selected = terrain.prepare_terrain_infographic(cls.baseline)

    def test_on_adds_only_child_identity_and_admission_receipt(self):
        restored = deepcopy(self.selected)
        restored['metadata'].pop('terrain_infographic')
        for scene in restored['scenes']:
            scene.pop('terrain_infographic')
        restored['gate'] = deepcopy(self.baseline['gate'])
        self.assertEqual(restored, self.baseline)
        self.assertTrue(terrain.validate_terrain_infographic(self.selected)['passed'])

    def test_off_is_complete_v023_baseline_with_copy_isolation(self):
        snapshot = deepcopy(self.baseline)
        off = terrain.prepare_terrain_infographic(self.baseline, enabled=False)
        self.assertEqual(off, snapshot)
        off['scenes'][0]['labels'][0]['text'] = 'isolated'
        self.assertEqual(self.baseline, snapshot)
        with self.assertRaises(ValueError):
            terrain.prepare_terrain_infographic(self.selected, enabled=False)
        with self.assertRaises(ValueError):
            terrain.prepare_terrain_infographic(self.baseline, enabled=1)

    def test_original_geometry_and_event_contract_are_not_reselected(self):
        for before, after in zip(self.baseline['scenes'], self.selected['scenes']):
            self.assertEqual(before['bold_infographic'], after['bold_infographic'])
            self.assertEqual(before['infographic'], after['infographic'])
            selected = after['terrain_infographic']
            self.assertNotIn('regions', selected)
            self.assertNotIn('geometries', selected)
            self.assertNotIn('events', selected)
            self.assertEqual(selected['parent_bold_sha256'], parent.canonical_sha(before['bold_infographic']))

    def test_camera_material_timing_and_all_720_frames_remain_parent_owned(self):
        before, after = self.baseline['scenes'][0], self.selected['scenes'][0]
        self.assertEqual(parent._camera_snapshot(before), parent._camera_snapshot(after))
        self.assertEqual(parent._quality_snapshot(before), parent._quality_snapshot(after))
        self.assertEqual(parent.parent._source_snapshot(before), parent.parent._source_snapshot(after))
        self.assertEqual(after['frame_count'], 720)
        self.assertEqual(after['terrain_infographic']['total_frames'], 720)
        self.assertEqual(after['terrain_infographic']['fps'], before['bold_infographic']['fps'])
        self.assertEqual(float(after['terrain_infographic']['fps']), 30)
        self.assertEqual(self.baseline['metadata']['frame_grid'], self.selected['metadata']['frame_grid'])

    def test_profile_and_every_new_renderer_source_are_pinned(self):
        own = self.selected['scenes'][0]['terrain_infographic']
        self.assertEqual(own['profile_sha256'], terrain._sha(terrain.PROFILE_PATH))
        self.assertEqual(set(own['source_hashes']), set(terrain.SOURCES))
        self.assertEqual(own['source_hashes'], terrain.source_hashes())
        self.assertEqual(own['registry_sha256'], self.baseline['scenes'][0]['bold_infographic']['registry_sha256'])

    def test_forged_sources_profile_and_parent_snapshot_are_rejected(self):
        for change in (lambda selected: selected['source_hashes'].__setitem__('web/terrain_infographic_adapter.js', '0'*64),
                       lambda selected: selected.__setitem__('profile_id', 'BOLD_INFOGRAPHIC_V023'),
                       lambda selected: selected.__setitem__('parent_quality_sha256', '0'*64),
                       lambda selected: selected.__setitem__('total_frames', 450)):
            value = deepcopy(self.selected)
            change(value['scenes'][0]['terrain_infographic'])
            value['metadata']['terrain_infographic'] = terrain._metadata(value)
            self.assertFalse(terrain.validate_terrain_infographic(value)['passed'])

    def test_null_partial_and_orphan_children_fail_closed(self):
        from engine import schema
        for change in (lambda plan: plan['metadata'].pop('terrain_infographic'),
                       lambda plan: plan['scenes'][0].pop('terrain_infographic'),
                       lambda plan: plan['metadata'].__setitem__('terrain_infographic', None),
                       lambda plan: plan['scenes'][0].__setitem__('terrain_infographic', None)):
            value = deepcopy(self.selected)
            change(value)
            self.assertFalse(terrain.validate_terrain_infographic(value)['passed'])
            self.assertFalse(schema.validate_plan(value)['passed'])

    def test_parent_native_geometry_forgery_cannot_be_rehashed_into_v024(self):
        value = deepcopy(self.selected)
        value['scenes'][0]['bold_infographic']['geometries'][0]['coordinates'].append([0, 0])
        value['scenes'][0]['terrain_infographic'] = terrain.compile_terrain_scene(value['scenes'][0])
        value['metadata']['terrain_infographic'] = terrain._metadata(value)
        self.assertFalse(terrain.validate_terrain_infographic(value)['passed'])

    def test_backend_remaps_only_v024_page_and_preserves_transport(self):
        from engine import infographic_backend
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'scene.json'
            command = ['node', 'frozen-renderer', '--scene-json', str(path), '--url',
                'http://127.0.0.1:8000/static/render_production_earth.html?parent=1',
                '--browser', '/approved/chromium-wrapper', '--gpu-profile', 'nvidia-vulkan',
                '--output', str(Path(directory)/'output.mp4')]
            index = command.index('--url')+1
            path.write_text(json.dumps(self.selected['scenes'][0]))
            mapped = infographic_backend.infographic_command(command)
            self.assertEqual(mapped[index], 'http://127.0.0.1:8000/static/render_terrain_infographic_earth.html?parent=1')
            self.assertEqual(mapped[:index], command[:index])
            self.assertEqual(mapped[index+1:], command[index+1:])
            path.write_text(json.dumps(self.baseline['scenes'][0]))
            self.assertEqual(infographic_backend.infographic_command(command)[index],
                'http://127.0.0.1:8000/static/render_bold_infographic_earth.html?parent=1')

    def test_invalid_backend_child_never_silently_falls_back(self):
        from engine import infographic_backend
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'scene.json'
            scene = deepcopy(self.selected['scenes'][0])
            scene['terrain_infographic'] = None
            path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(RuntimeError, 'TERRAIN_INFOGRAPHIC_SCENE_SOURCE_MISMATCH'):
                infographic_backend.infographic_command(['node', '--scene-json', str(path), '--url',
                    'http://127.0.0.1:8000/static/render_production_earth.html'])

    def test_cache_separates_new_profile_and_preserves_exact_old_version(self):
        self.assertEqual(parent.renderer_version(self.baseline['scenes'][0]), self.old_cache)
        self.assertNotEqual(parent.renderer_version(self.selected['scenes'][0]), self.old_cache)
        self.assertEqual(parent.renderer_version(terrain.prepare_terrain_infographic(
            self.baseline, enabled=False)['scenes'][0]), self.old_cache)

    def test_diagnostic_contains_all_parent_evidence_without_gpu_claim(self):
        report = parent.diagnostic_record(self.selected)
        self.assertEqual(report['version'], 'v022')
        self.assertEqual(report['bold_infographic']['version'], 'v023')
        self.assertEqual(report['terrain_infographic']['profile_id'], terrain.PROFILE_ID)
        self.assertEqual(report['terrain_infographic']['physical_gpu'], 'NOT_RUN')
        self.assertEqual(report['terrain_infographic']['scenes'][0]['parent_bold_sha256'],
                         self.selected['scenes'][0]['terrain_infographic']['parent_bold_sha256'])
        self.assertNotIn('terrain_infographic', parent.diagnostic_record(self.baseline))

    def test_installer_preserves_parent_attributes_and_rebinds_preflight(self):
        from engine import schema, gpu_preflight, semantic_timeline
        terrain.install_runtime()
        bold.install_runtime()
        self.assertTrue(getattr(schema.validate_plan, 'terrain_infographic_wrapper', False))
        self.assertTrue(getattr(schema.validate_plan, 'bold_infographic_wrapper', False))
        self.assertTrue(getattr(schema.validate_plan, 'infographic_wrapper', False))
        self.assertTrue(getattr(semantic_timeline.validate_production_plan, 'terrain_infographic_wrapper', False))
        self.assertIs(gpu_preflight.validate_plan, schema.validate_plan)

    def test_runtime_reinstallation_does_not_admit_orphan_after_restored_callable(self):
        from engine import schema, gpu_preflight
        saved = schema.validate_plan, gpu_preflight.validate_plan
        try:
            schema.validate_plan = lambda plan: dict(passed=True, errors=[], warnings=[])
            gpu_preflight.validate_plan = schema.validate_plan
            terrain.install_runtime()
            value = deepcopy(self.selected)
            value['scenes'][0].pop('terrain_infographic')
            self.assertFalse(schema.validate_plan(value)['passed'])
            self.assertIs(gpu_preflight.validate_plan, schema.validate_plan)
        finally:
            schema.validate_plan, gpu_preflight.validate_plan = saved


if __name__ == '__main__':
    unittest.main()
