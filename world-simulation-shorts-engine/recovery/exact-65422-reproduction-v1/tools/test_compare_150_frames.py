"""Small regression tests for false-positive risks in the comparison tool."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("compare_150_frames", Path(__file__).with_name("compare_150_frames.py"))
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def evidence():
    frames = []
    for frame in range(150):
        camera = {"frame": frame, "bounds": [1, 2, 3, 4], "rollDegrees": frame / 100}
        frames.append({"frame": frame, "raw_rgba_sha256": f"raw-{frame}", "png_sha256": f"png-{frame}", "cameraBounds": [1, 2, 3, 4], "rotationDegrees": frame / 100, "control": {"frame": frame, "boundary": [3, 4]}, "presentation": {"frame": frame}, "units": {"frame": frame}, "protection": {"sourceUnchanged": True}, "diagnostic": {"camera": camera, "territory": {"frame": frame}, "frontierLight": {"frame": frame}, "terrain": {"frame": frame}}})
    return {"frames": frames}


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.original = evidence()
        self.new = copy.deepcopy(self.original)

    def test_identical_evidence_requires_all150(self):
        result, _ = comparison.compare_report(self.original, self.new)
        self.assertTrue(result["all150RawRgbaEqual"])
        self.assertTrue(result["all150PngEqual"])
        self.assertTrue(result["all150StatesEqual"])

    def test_late_camera_change_is_not_hidden_by_matching_hashes(self):
        self.new["frames"][149]["diagnostic"]["camera"]["rollDegrees"] += 0.001
        result, _ = comparison.compare_report(self.original, self.new)
        self.assertTrue(result["all150RawRgbaEqual"])
        self.assertFalse(result["all150StatesEqual"])
        self.assertEqual(result["stateFields"]["camera_full_state"]["firstDifference"]["frame"], 149)

    def test_missing_terrain_evidence_is_not_pass(self):
        del self.new["frames"][9]["diagnostic"]["terrain"]
        result, _ = comparison.compare_report(self.original, self.new)
        self.assertFalse(result["all150StatesEqual"])
        self.assertEqual(result["stateFields"]["terrain_material"]["missing"][0]["frame"], 9)

    def test_raw_pixel_difference_reports_first_frame(self):
        self.new["frames"][17]["raw_rgba_sha256"] = "changed"
        result, _ = comparison.compare_report(self.original, self.new)
        self.assertFalse(result["all150RawRgbaEqual"])
        self.assertEqual(result["firstRawMismatch"], 17)

    def test_reordered_frame_evidence_fails(self):
        self.new["frames"][0], self.new["frames"][1] = self.new["frames"][1], self.new["frames"][0]
        result, _ = comparison.compare_report(self.original, self.new)
        self.assertFalse(result["reproductionFrameOrderValid"])
        self.assertFalse(result["all150StatesEqual"])

    def test_truncated_evidence_fails(self):
        self.new["frames"].pop()
        result, _ = comparison.compare_report(self.original, self.new)
        self.assertFalse(result["all150RawRgbaEqual"])
        self.assertFalse(result["all150PngEqual"])
        self.assertFalse(result["all150StatesEqual"])

    def test_large_difference_payload_is_hash_summarized(self):
        value = {"privateScenePayload": "x" * 2000}
        result = comparison.first_difference(value, [])
        self.assertNotIn("privateScenePayload", result["original"])
        self.assertIn("canonicalSha256", result["original"])


if __name__ == "__main__":
    unittest.main()
