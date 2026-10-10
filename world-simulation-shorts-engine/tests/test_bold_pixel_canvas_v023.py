"""Real Chromium CPU Canvas pixel detector tests; no WebGL/NVIDIA execution."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BoldPixelCanvasV023(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['node', 'tools/test_bold_pixel_canvas_v023.mjs'], cwd=ROOT,
                                check=True, capture_output=True, text=True, timeout=90)
        cls.receipt = json.loads(result.stdout)
        cls.checks = {check['id']: check for check in cls.receipt['checks']}

    def test_six_eight_ten_pixel_cores_measured_at_output_resolution(self):
        for width in [6, 8, 10]:
            check = self.checks[f'ACTUAL_CANVAS_WIDTH_{width}']
            self.assertTrue(check['passed'])
            self.assertAlmostEqual(check['measured']['width_px_median'], width, delta=.1)

    def test_secondary_two_four_pixel_widths_are_measured(self):
        for width in [2, 4]:
            self.assertTrue(self.checks[f'ACTUAL_CANVAS_WIDTH_{width}']['passed'])

    def test_dark_outer_edge_does_not_inflate_bright_core(self):
        self.assertTrue(self.checks['BRIGHT_CORE_EXCLUDES_DARK_EDGE']['passed'])

    def test_real_alpha_blend_preserves_terrain_edge_correlation(self):
        self.assertTrue(self.checks['ACTUAL_ALPHA_FILL_KEEPS_TERRAIN']['passed'])

    def test_real_opaque_fill_is_detected_as_terrain_erasure(self):
        self.assertTrue(self.checks['ACTUAL_OPAQUE_FILL_ERASES_TERRAIN']['passed'])

    def test_real_outside_geometry_pixel_leak_is_detected(self):
        self.assertEqual(self.checks['ACTUAL_OCEAN_LEAK_DETECTED']['measured']
                         ['outside_native_fill_pixels'], 16)

    def test_off_pixels_are_exact(self):
        self.assertTrue(self.checks['OFF_EXACT_CHANNELS']['passed'])

    def test_canvas_detector_does_not_claim_gpu_quality_pass(self):
        self.assertEqual(self.receipt['GPU'], 'NOT_RUN')
        self.assertEqual(self.receipt['visual_quality_acceptance'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
