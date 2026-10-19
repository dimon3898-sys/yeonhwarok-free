import importlib.util
import json
import math
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "camera_pixel_activity.py"
spec = importlib.util.spec_from_file_location("camera_pixel_activity_under_test", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assess = module.assess_camera_activity
rank = module.select_visible_camera_window
Error = module.CameraActivityError


def row(frame, west=-70, south=-40, east=-60, north=-30, **extra):
    return {"frame": frame, "bounds": [west, south, east, north], **extra}


class CameraPixelActivityTests(unittest.TestCase):
    def test_static_western_southern_context(self):
        measured = assess([row(frame) for frame in range(3)])
        self.assertEqual(measured["status"], "OBSERVED_STATIC")
        self.assertEqual(measured["maxDisplacementFromFirstPixels"], 0)
        self.assertFalse(measured["visualQualityPass"])
        self.assertIsNone(measured["rotationDegreesRange"])

    def test_numeric_change_below_one_pixel_does_not_claim_visibility(self):
        measured = assess([row(17), row(18, west=-69.995, east=-59.995)])
        self.assertEqual(measured["status"], "NUMERIC_SUBPIXEL_ONLY")
        self.assertEqual(measured["numericMotionPairs"], 1)
        self.assertAlmostEqual(measured["maxDisplacementFromFirstPixels"], .54)
        self.assertFalse(measured["meaningfulPixelScaleActivity"])

    def test_pixel_translation_is_activity_but_not_quality_pass(self):
        measured = assess([row(0), row(1, west=-69.9, east=-59.9)])
        self.assertEqual(measured["status"], "OBSERVED_PIXEL_SCALE_MOVEMENT")
        self.assertAlmostEqual(measured["maxDisplacementFromFirstPixels"], 10.8)
        self.assertFalse(measured["mobilePerceivedMotionVerified"])
        self.assertFalse(measured["gpuRenderingVerified"])

    def test_long_subpixel_jitter_path_cannot_upgrade_visibility(self):
        rows = [row(frame, west=-70 + .002 * (frame % 2), east=-60 + .002 * (frame % 2)) for frame in range(100)]
        measured = assess(rows)
        self.assertGreater(measured["maximumLatticePathLengthPixels"], 10)
        self.assertLess(measured["maxDisplacementFromFirstPixels"], 1)
        self.assertEqual(measured["status"], "NUMERIC_SUBPIXEL_ONLY")

    def test_zoom_uses_same_world_points_instead_of_center_only(self):
        measured = assess([row(0), row(1, west=-69, south=-39, east=-61, north=-31)])
        self.assertEqual(measured["status"], "OBSERVED_PIXEL_SCALE_MOVEMENT")
        self.assertAlmostEqual(measured["zoomScaleXRange"][1], 1.25)
        self.assertGreater(measured["maxDisplacementFromFirstPixels"], 100)

    def test_explicit_observed_roll_is_measured(self):
        measured = assess([row(0, rotationDegrees=0), row(1, rotationDegrees=1)])
        self.assertTrue(measured["rotationObserved"])
        self.assertEqual(measured["rotationDegreesRange"], [0, 1])
        self.assertGreater(measured["maxDisplacementFromFirstPixels"], 1)

    def test_partial_roll_context_rejected(self):
        with self.assertRaisesRegex(Error, "PARTIAL_ROTATION_TRACE"):
            assess([row(0, rotationDegrees=0), row(1)])

    def test_date_line_crossing_uses_short_geographic_continuity(self):
        measured = assess([row(0, west=179, east=-171), row(1, west=-179, east=-169)])
        self.assertTrue(measured["dateLineUnwrappingApplied"])
        self.assertAlmostEqual(measured["maxDisplacementFromFirstPixels"], 216)
        self.assertFalse(measured["possibleHardCutFrames"])

    def test_valid_polar_rectangular_box_no_mercator_assumption(self):
        measured = assess([row(0, west=-10, east=10, south=85, north=90), row(1, west=-9.99, east=10.01, south=85, north=90)])
        self.assertEqual(measured["status"], "NUMERIC_SUBPIXEL_ONLY")
        self.assertEqual(measured["projectionMeasurement"], "RECTANGULAR_EQUIRECTANGULAR_STABLE_WORLD_LATTICE")

    def test_polar_overflow_degenerate_nonfinite_bounds_rejected(self):
        for bounds in ([0, 85, 10, 91], [1, 0, 1, 10], [0, 1, 10, 1], [0, 0, math.nan, 1]):
            with self.subTest(bounds=bounds), self.assertRaises(Error):
                assess([row(0), {"frame": 1, "bounds": bounds}])

    def test_missing_context_rejected(self):
        for rows in ([], [row(0)], [{"frame": 0}, {"frame": 1}], [{"bounds": [0, 0, 1, 1]}, row(1)]):
            with self.subTest(rows=rows), self.assertRaises(Error):
                assess(rows)

    def test_duplicate_unordered_irregular_global_clock_rejected(self):
        for frames in ([0, 0], [1, 0], [0, 2]):
            with self.subTest(frames=frames), self.assertRaises(Error):
                assess([row(frame) for frame in frames])

    def test_conflicting_frame_or_bounds_alias_rejected(self):
        for bad in ({**row(1), "globalFrame": 9}, {**row(1), "cameraBounds": [0, 0, 1, 1]}):
            with self.subTest(bad=bad), self.assertRaises(Error):
                assess([row(0), bad])

    def test_resolution_and_threshold_validated(self):
        for arguments in ({"width": True}, {"height": 0}, {"min_visible_pixels": 0}, {"min_visible_pixels": math.inf}):
            with self.subTest(arguments=arguments), self.assertRaises(Error):
                assess([row(0), row(1)], **arguments)

    def test_large_jump_reported_and_not_ranked_as_continuous_motion(self):
        rows = [row(0), row(1, west=10, east=20)]
        measured = assess(rows)
        self.assertEqual(measured["possibleHardCutFrames"], [1])
        self.assertEqual(measured["continuityAssessment"], "POSSIBLE_HARD_CUT_NOT_INTERPOLATED")
        selected = rank(rows, frame_count=2)
        self.assertEqual(selected["status"], "NO_OBSERVED_VISIBLE_CAMERA_WINDOW")
        self.assertEqual(selected["rejectedLargeJumpWindows"], 1)

    def test_all_subpixel_windows_explicitly_blocked_without_new_pose(self):
        selected = rank([row(frame, west=-70 + frame * .0001, east=-60 + frame * .0001) for frame in range(5)], frame_count=3)
        self.assertEqual(selected["fullyObservedCandidateWindows"], 3)
        self.assertEqual(selected["rejectedSubpixelWindows"], 3)
        self.assertEqual(selected["status"], "NO_OBSERVED_VISIBLE_CAMERA_WINDOW")
        self.assertIsNone(selected["selectedRange"])
        self.assertEqual(selected["cameraPosesCreated"], 0)

    def test_rank_never_bridges_missing_frames(self):
        selected = rank([row(0), row(1), row(9, west=-69, east=-59), row(10, west=-68, east=-58)], frame_count=3)
        self.assertEqual(selected["fullyObservedCandidateWindows"], 0)
        self.assertIsNone(selected["selectedRange"])

    def test_known_visible_window_selected_without_retiming(self):
        selected = rank([row(frame, west=-70 + frame * .01, east=-60 + frame * .01) for frame in range(10, 15)], frame_count=3)
        self.assertEqual(selected["status"], "OBSERVED_VISIBLE_CAMERA_WINDOW")
        self.assertEqual(selected["selectedRange"][1] - selected["selectedRange"][0], 3)
        self.assertFalse(selected["sourceTimelineChanged"])
        self.assertFalse(selected["productionSelectorChanged"])

    def test_actual_preserved_new_150_frames_correct_numeric_misclassification(self):
        report = json.loads((SOURCE.parent / "reports/CAMERA_PIXEL_ACTIVITY.json").read_text())
        measured = assess(report["knownOvernightActual150Frames"]["actualObservations"])
        self.assertEqual(measured["observedFrames"], 150)
        self.assertEqual([measured["startFrame"], measured["endFrame"]], [1400, 1550])
        self.assertEqual(measured["numericMotionPairs"], 47)
        self.assertAlmostEqual(measured["maxDisplacementFromFirstPixels"], .6020653471876087)
        self.assertEqual(measured["status"], "NUMERIC_SUBPIXEL_ONLY")
        self.assertFalse(measured["visualQualityPass"])

    def test_actual_old_candidate_lattice_movement_is_materially_different(self):
        report = json.loads((SOURCE.parent / "reports/CAMERA_PIXEL_ACTIVITY.json").read_text())
        measured = assess(report["oldAdvancedActual150Frames"]["actualObservations"])
        self.assertEqual(measured["observedFrames"], 150)
        self.assertEqual(measured["status"], "OBSERVED_PIXEL_SCALE_MOVEMENT")
        self.assertGreater(measured["maxDisplacementFromFirstPixels"], 500)
        self.assertLess(measured["maxInterframeDisplacementPixels"], 100)
        self.assertTrue(measured["rotationObserved"])
        self.assertFalse(measured["gpuRenderingVerified"])


if __name__ == "__main__":
    unittest.main()
