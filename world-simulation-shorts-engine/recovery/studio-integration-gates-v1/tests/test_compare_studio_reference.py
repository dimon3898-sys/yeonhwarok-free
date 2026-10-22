"""CPU-only checks for the newly added comparison metric and evidence adapter."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("_new_studio_comparison", ROOT / "tools/compare_studio_reference.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ComparisonTests(unittest.TestCase):
    def test_exact_ssim(self):
        values = np.arange(24 * 24 * 3, dtype=np.uint8).reshape(24, 24, 3)
        self.assertEqual(MODULE.ssim_rgb_uniform7(values, values), 1.0)

    def test_constant_images_have_known_ssim(self):
        black = np.zeros((24, 24, 3), dtype=np.uint8)
        white = np.full_like(black, 255)
        expected = (.01 * 255) ** 2 / (255 ** 2 + (.01 * 255) ** 2)
        self.assertAlmostEqual(MODULE.ssim_rgb_uniform7(black, white), expected, places=12)

    def test_ssim_channel_average_and_symmetry(self):
        rng = np.random.default_rng(11)
        original = rng.integers(0, 256, (24, 24, 3), dtype=np.uint8)
        changed = original.copy()
        changed[5:15, 8:18, 0] = 50
        score = MODULE.ssim_rgb_uniform7(original, changed)
        self.assertGreater(score, 0)
        self.assertLess(score, 1)
        self.assertAlmostEqual(score, MODULE.ssim_rgb_uniform7(changed, original), places=12)

    def test_evidence_adapter_reads_actual_diagnostic(self):
        row = {"scalarControl": {"actual": 3}, "diagnostic": {"camera": {"bounds": [1, 2, 3, 4], "rotationDegrees": 7},
               "presentation": {"actual": True}}, "raw_rgba_sha256": "a" * 64}
        original = {"frames": [row]}
        adapted = MODULE.source_rows_from_capture(original)
        self.assertEqual(adapted["frames"][0]["control"], row["scalarControl"])
        self.assertEqual(adapted["frames"][0]["cameraBounds"], [1, 2, 3, 4])
        self.assertEqual(adapted["frames"][0]["rotationDegrees"], 7)
        self.assertNotIn("control", row)

    def test_output_outside_new_namespace_rejected_before_creation(self):
        with self.assertRaisesRegex(ValueError, "COMPARISON_OUTPUT_MUST_BE_NEW_NAMESPACE_CHILD"):
            MODULE.fresh_output(ROOT.parent / "exact-65422-reproduction-v1/do-not-create")


if __name__ == "__main__":
    unittest.main()
