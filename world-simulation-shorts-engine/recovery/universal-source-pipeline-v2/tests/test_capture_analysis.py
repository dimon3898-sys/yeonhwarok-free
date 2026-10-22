"""Small metric/clock tests, never represented as real renderer frames."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_unit_source_capture_analysis", HERE / "tools/analyze_capture.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class CaptureAnalysisTests(unittest.TestCase):
    def test_identical_images_have_zero_contribution(self):
        image = Image.new("RGB", (4, 3), (10, 20, 30))
        result = module.pixel_metrics(image, image.copy())
        self.assertEqual(result["changedPixels"], 0)
        self.assertIsNone(result["changedPixelBox"])
        self.assertFalse(result["pixelContributionObserved"])

    def test_single_pixel_cannot_be_called_more_than_one_pixel(self):
        a = Image.new("RGB", (4, 3), (0, 0, 0))
        b = a.copy()
        b.putpixel((2, 1), (255, 0, 0))
        result = module.pixel_metrics(a, b)
        self.assertEqual(result["changedPixels"], 1)
        self.assertEqual(result["changedPixelBox"], [2, 1, 3, 2])
        self.assertEqual(result["changedPixelFraction"], 1 / 12)
        self.assertFalse(result["moreThanSinglePixel"])

    def test_dimensions_differ_rejected(self):
        with self.assertRaisesRegex(ValueError, "PIXEL_PROOF_IMAGE_DIMENSIONS_DIFFER"):
            module.pixel_metrics(Image.new("RGB", (2, 2)), Image.new("RGB", (3, 2)))

    def frame(self, *, global_frame=600):
        box = [1.0, 2.0, 3.0, 4.0]
        mask = {"fieldId": "unit-field", "frame": global_frame, "geometry": {"type": "Polygon", "coordinates": []}}
        diagnostic = {"sourceControlFrame": global_frame, "fieldId": "unit-field",
            "ownerMasks": [{**mask, "factionId": "A"}], "unknownMask": deepcopy(mask),
            "contestedMask": deepcopy(mask), "sharedFront": deepcopy(mask),
            "actualCamera": {"bounds": box}, "camera": {"camera": {"flatBounds": list(box)}, "admission": {"localUsed": False}},
            "cameraNumericalAgreement": {"matches": True}, "glError": 0, "marker": {"safeArea": True},
            "projectEventPoint": [540, 960], "fillDraws": [{"graphics": {"safeArea": [0, 0, 1080, 1920],
                "protectedReservations": [{"kind": "MARKER", "box": [500, 900, 580, 980]}]}}]}
        return {"frame": 0, "globalFrame": global_frame, "diagnostic": diagnostic}

    def test_global_frame_clock_is_not_reset_to_zero(self):
        result = module.frame_checks([self.frame()])
        self.assertTrue(result["allSameFieldAndClock"])
        self.assertTrue(result["allNativeCameraMatchesV5"])

    def test_unknown_mask_from_another_frame_is_not_admitted(self):
        frame = self.frame()
        frame["diagnostic"]["unknownMask"]["frame"] = 599
        self.assertFalse(module.frame_checks([frame])["allSameFieldAndClock"])

    def test_safe_area_and_native_camera_errors_are_separate(self):
        frame = self.frame()
        frame["diagnostic"]["actualCamera"]["bounds"] = [1, 2, 3.1, 4]
        frame["diagnostic"]["fillDraws"][0]["graphics"]["protectedReservations"][0]["box"] = [-1, 900, 580, 980]
        result = module.frame_checks([frame])
        self.assertFalse(result["allNativeCameraMatchesV5"])
        self.assertFalse(result["allReservationsInsideSafeArea"])
        self.assertTrue(result["allMarkerSafeArea"])

    def test_output_cannot_leave_new_namespace(self):
        with self.assertRaisesRegex(ValueError, "PIXEL_PROOF_OUTPUT_NEW_NAMESPACE_REQUIRED"):
            module._new_target(HERE.parent / "studio-integration-gates-v1/old-proof.png")


if __name__ == "__main__":
    unittest.main()
