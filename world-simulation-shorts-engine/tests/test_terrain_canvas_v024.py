"""Actual native Canvas color-composite and production helper detector tests."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TerrainCanvasV024(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory(prefix='v024-canvas-detector-') as folder:
            result = subprocess.run(['node', 'tools/terrain_canvas_preview_v024.mjs',
                                     '--detector-only', '--output', folder], cwd=ROOT,
                                    capture_output=True, text=True, check=True, timeout=120)
        cls.receipt = json.loads(result.stdout)
        cls.checks = {row['id']: row for row in cls.receipt['checks']}

    def test_native_color_matches_measured_geometry_local_tone_without_hiding_raw_luminance(self):
        check = self.checks['NATIVE_COLOR_MATCHES_LOCAL_SCALED_W3C_LUMINANCE']
        self.assertTrue(check['passed'])
        measured = check['measured']['luminance']['W3C']
        self.assertLess(measured['mean_absolute_error_against_scaled_source'], .005)
        self.assertIn('mean_absolute_error', measured)
        self.assertGreaterEqual(measured['expected_local_luminance_scale'], .80)

    def test_native_color_preserves_three_measured_terrain_scales(self):
        self.assertTrue(self.checks['NATIVE_COLOR_RETAINS_THREE_DETAIL_SCALES']['passed'])

    def test_previous_v023_source_over_attenuation_is_measured(self):
        self.assertTrue(self.checks['OLD_SOURCE_OVER_ATTENUATION_MEASURED']['passed'])

    def test_primary_output_core_is_measured_from_actual_pixels(self):
        check = self.checks['PRIMARY_ACTUAL_CORE_WIDTH']
        self.assertTrue(check['passed'])
        self.assertAlmostEqual(check['measured']['width_px_median'], 8, delta=.3)

    def test_secondary_output_core_is_measured_from_actual_pixels(self):
        check = self.checks['SECONDARY_ACTUAL_CORE_WIDTH']
        self.assertTrue(check['passed'])
        self.assertAlmostEqual(check['measured']['width_px_median'], 3, delta=.3)

    def test_primary_halo_has_actual_finite_threshold_reach(self):
        check = self.checks['PRIMARY_HALO_ACTUAL_BOUNDED_REACH']
        self.assertTrue(check['passed'])
        self.assertLessEqual(check['measured']['reach_from_native_edge_px_max'], 16)
        self.assertEqual(check['measured']['sampling_limit_hits'], 0)

    def test_secondary_region_has_no_halo_pixels(self):
        self.assertTrue(self.checks['SECONDARY_HAS_ZERO_GLOW_PIXELS']['passed'])

    def test_disabled_terrain_profile_preserves_exact_v023_pixels(self):
        self.assertTrue(self.checks['OFF_EXACT_V023_PIXELS']['passed'])

    def test_canvas_state_is_restored_after_color_fill_and_halo(self):
        self.assertTrue(self.checks['NATIVE_CONTEXT_STATE_RESTORED']['passed'])

    def test_canvas_run_has_no_webgl_or_gpu_quality_pass(self):
        self.assertEqual(self.receipt['webgl_context_attempts'], 0)
        self.assertEqual(self.receipt['GPU'], 'NOT_RUN')
        self.assertEqual(self.receipt['visual_quality_acceptance'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
