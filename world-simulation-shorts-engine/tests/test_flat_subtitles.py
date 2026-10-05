"""Bundled-font, measured screen-box and one-frame libass caption checks."""
from __future__ import annotations

import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.assets import APP_ROOT
from engine.audio import create_subtitles, _subtitle_font, _subtitle_line_width, validate_subtitle_layout
from engine.flat_subtitles import adapt_flat_subtitles, validate_premium_subtitle_layout


class PremiumMapSubtitleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="premium-map-caption-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.plan = {"duration": 5., "options": {"subtitles": True, "quality": "HIGH"},
                     "scenes": [{"scene_id": "S001", "start_time": 0., "duration": 5.,
                                 "render_mode": "FLAT_MAP_PREMIUM", "narration": "서울에서 출발합니다."}]}

    def source(self, text="서울에서 출발합니다.", start=.1, end=4.8):
        return create_subtitles(self.plan, self.directory,
                                [{"scene_id": "S001", "start": start, "end": end, "text": text,
                                  "timing_source": "explicit_cue"}])

    def frame(self, *, t=1., resolution=(2160, 3840), **kwargs):
        return {"scene_id": "S001", "t": t, "renderResolution": list(resolution),
                "labels": [], "entities": [], **kwargs}

    def test_legacy_is_exact_no_io_noop(self):
        self.plan["scenes"][0].pop("render_mode")
        original = {"enabled": True, "path": "unchanged-subtitles.ass"}
        self.assertIs(adapt_flat_subtitles(self.plan, original, ["nonexistent.audit.json"],
                                          self.directory/"must-not-create"), original)
        self.assertFalse((self.directory/"must-not-create").exists())

    def test_off_is_exact_noop_even_with_explicit_flat_scene(self):
        self.plan["options"]["subtitles"] = False
        original = {"enabled": False, "path": None}
        self.assertIs(adapt_flat_subtitles(self.plan, original, ["nonexistent.audit.json"], self.directory), original)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_original_ass_and_report_preserved_and_layout_compatible(self):
        source = self.source()
        untouched, source_bytes = copy.deepcopy(source), Path(source["path"]).read_bytes()
        original_report = self.directory/"subtitle_report.json"
        original_report.write_text(json.dumps(source))
        report_bytes = original_report.read_bytes()
        report = adapt_flat_subtitles(self.plan, source, [self.frame()], self.directory)
        self.assertEqual(source, untouched)
        self.assertEqual(Path(source["path"]).read_bytes(), source_bytes)
        self.assertEqual(original_report.read_bytes(), report_bytes)
        self.assertEqual(report["font"], source["font"])
        self.assertEqual(report["subtitle_style"], "PREMIUM_MAP")
        self.assertTrue(validate_subtitle_layout(report, 5.)["passed"])
        self.assertTrue(validate_premium_subtitle_layout(report, 5.)["passed"])
        self.assertEqual(report["source_ass_sha256"], hashlib.sha256(source_bytes).hexdigest())
        self.assertEqual(report["captions"][0]["start"], source["captions"][0]["start"])
        ass = Path(report["path"]).read_text()
        self.assertIn(r"\an2\pos(", ass)
        self.assertIn("MapPlate", ass)
        self.assertIn(r"\p1\fad(90,100)", ass)
        self.assertTrue((self.directory/"subtitle_report_map_safe.json").is_file())

    def test_actual_label_geometry_scales_from_4k_and_avoids_bottom(self):
        source = self.source()
        label = {"text": "SEOUL", "opacity": 1., "x": 250., "y": 2800., "width": 1590., "height": 400.}
        report = adapt_flat_subtitles(self.plan, source, [self.frame(labels=[label])], self.directory)
        caption = report["captions"][0]
        self.assertLess(caption["anchor"]["bottom"], 1400.)
        self.assertEqual(caption["placement"]["overlap_frames"], 0)
        self.assertEqual(caption["placement"]["protected_boxes"], 1)
        self.assertTrue(report["map_avoidance_verified"])

    def test_entity_motion_and_focus_boxes_use_one_stable_cue_placement(self):
        source = self.source()
        native = [self.frame(t=t, entities=[{"id": "flight", "x": x, "y": 3080., "screenRadius": 160.,
                                            "screenVisible": True, "occluded": False}],
                             focusTargetBox={"x": 240., "y": 2850., "width": 1600., "height": 300.})
                  for t, x in ((1., 700.), (2., 1400.))]
        report = adapt_flat_subtitles(self.plan, source, native, self.directory)
        caption = report["captions"][0]
        self.assertEqual(len(report["captions"]), 1)
        self.assertEqual(caption["placement"]["audited_frames"], 2)
        self.assertEqual(caption["placement"]["protected_boxes"], 4)
        self.assertEqual(caption["placement"]["overlap_frames"], 0)
        self.assertLess(caption["anchor"]["bottom"], 1400.)

    def test_future_inactive_and_occluded_objects_do_not_move_caption(self):
        source = self.source(end=2.)
        full = {"x": 0., "y": 0., "width": 2160., "height": 3840.}
        native = [self.frame(t=1., labels=[{**full, "opacity": 0.}],
                             entities=[{"id": "behind", **full, "occluded": True}]),
                  self.frame(t=3., labels=[{**full, "opacity": 1.}])]
        report = adapt_flat_subtitles(self.plan, source, native, self.directory)
        self.assertEqual(report["captions"][0]["anchor"]["bottom"], 1580.)
        self.assertEqual(report["captions"][0]["placement"]["protected_boxes"], 0)

    def test_crowded_scene_warns_rather_than_claiming_clear_map(self):
        source = self.source()
        full = {"x": 0., "y": 0., "width": 2160., "height": 3840.}
        report = adapt_flat_subtitles(self.plan, source, [self.frame(focusTargetBox=full)], self.directory)
        self.assertFalse(report["map_avoidance_verified"])
        self.assertGreater(report["captions"][0]["placement"]["overlap_frames"], 0)
        self.assertIn("PREMIUM_SUBTITLE_NO_CLEAR_PLACEMENT", {item["code"] for item in report["warnings"]})
        self.assertTrue(report["layout_validation"]["passed"])

    def test_missing_measured_geometry_and_no_active_frames_are_reported(self):
        source = self.source()
        frame = self.frame(labels=[{"text": "SEOUL", "opacity": 1.}])
        report = adapt_flat_subtitles(self.plan, source, [frame], self.directory)
        self.assertFalse(report["map_avoidance_verified"])
        self.assertIn("PREMIUM_SUBTITLE_GEOMETRY_UNAVAILABLE", {item["code"] for item in report["warnings"]})
        other = self.directory/"empty"
        other.mkdir()
        report = adapt_flat_subtitles(self.plan, source, [], other)
        self.assertFalse(report["map_avoidance_verified"])
        self.assertIn("PREMIUM_SUBTITLE_NATIVE_FRAMES_UNAVAILABLE", {item["code"] for item in report["warnings"]})

    def test_font_metric_rewrap_preserves_letters_timing_and_max_two_lines(self):
        font, _ = _subtitle_font()
        count = next(n for n in range(1, 200) if 779 < _subtitle_line_width("i"*n, font) <= 795)
        text = "i"*(count*2)
        source = self.source(text)
        report = adapt_flat_subtitles(self.plan, source, [self.frame(t=n/30) for n in range(150)], self.directory)
        self.assertEqual("".join(line for caption in report["captions"] for line in caption["lines"]), text)
        self.assertTrue(all(len(caption["lines"]) <= 2 for caption in report["captions"]))
        self.assertTrue(all(width <= 779.001 for caption in report["captions"] for width in caption["line_widths_px"]))
        self.assertEqual(report["captions"][0]["start"], source["captions"][0]["start"])
        self.assertEqual(report["captions"][-1]["end"], source["captions"][-1]["end"])
        self.assertTrue(validate_premium_subtitle_layout(report, 5.)["passed"])

    def test_paths_and_same_attempt_reuse_verified_immutable_output(self):
        source = self.source()
        native_path = self.directory/"native.audit.json"
        native_path.write_text(json.dumps([self.frame()]))
        first = adapt_flat_subtitles(self.plan, source, [native_path], self.directory)
        snapshots = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.directory.iterdir()}
        second = adapt_flat_subtitles(self.plan, source, [native_path], self.directory)
        self.assertEqual(first, second)
        self.assertEqual(snapshots, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.directory.iterdir()})
        with self.assertRaisesRegex(RuntimeError, "PREMIUM_SUBTITLE_CACHE_MISMATCH"):
            adapt_flat_subtitles(self.plan, source, [self.frame(t=2.)], self.directory)
        self.assertEqual(snapshots, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.directory.iterdir()})

    def test_orphan_or_damaged_output_is_never_overwritten(self):
        source = self.source()
        protected = self.directory/"subtitles_map_safe.ass"
        protected.write_text("pre-existing output")
        with self.assertRaises(FileExistsError):
            adapt_flat_subtitles(self.plan, source, [self.frame()], self.directory)
        self.assertEqual(protected.read_text(), "pre-existing output")

    def test_interrupted_report_write_recovers_verified_ass_without_rewriting_it(self):
        source = self.source()
        report = adapt_flat_subtitles(self.plan, source, [self.frame()], self.directory)
        path = Path(report["path"])
        original_bytes, original_mtime = path.read_bytes(), path.stat().st_mtime_ns
        (self.directory/"subtitle_report_map_safe.json").unlink()
        recovered = adapt_flat_subtitles(self.plan, source, [self.frame()], self.directory)
        self.assertEqual(report, recovered)
        self.assertEqual(path.read_bytes(), original_bytes)
        self.assertEqual(path.stat().st_mtime_ns, original_mtime)

    def test_unknown_scene_or_invalid_native_time_fails_before_new_ass(self):
        source = self.source()
        for frame in (self.frame(scene_id="S999"), self.frame(t=float("nan"))):
            with self.assertRaisesRegex(RuntimeError, "PREMIUM_SUBTITLE_AUDIT_"):
                adapt_flat_subtitles(self.plan, source, [frame], self.directory)
            self.assertFalse((self.directory/"subtitles_map_safe.ass").exists())

    def test_plate_geometry_is_checked_separately_from_legacy_text_boxes(self):
        source = self.source()
        report = adapt_flat_subtitles(self.plan, source, [self.frame()], self.directory)
        report["captions"][0]["plate_box"]["x"] = 120.
        self.assertTrue(validate_subtitle_layout(report, 5.)["passed"])
        checked = validate_premium_subtitle_layout(report, 5.)
        self.assertFalse(checked["passed"])
        self.assertIn("PREMIUM_SUBTITLE_PLATE_OUTSIDE_SAFE_AREA", {item["code"] for item in checked["errors"]})

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg unavailable")
    def test_actual_libass_frame_has_fitted_dark_plate_and_visible_glyphs(self):
        source = self.source("서울 → 도쿄")
        report = adapt_flat_subtitles(self.plan, source, [self.frame()], self.directory)
        path = str(Path(report["path"]).resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        fonts = str(APP_ROOT/"web/fonts").replace("'", "\\'")
        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                 "color=c=0xf4ecd9:s=1080x1920:r=1:d=2", "-vf",
                                 f"ass=filename='{path}':fontsdir='{fonts}'", "-ss", "1", "-frames:v", "1",
                                 "-threads", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        pixels = np.asarray(Image.open(BytesIO(result.stdout)).convert("RGB"))
        plate = report["captions"][0]["plate_box"]
        x0, y0 = math_floor(plate["x"]), math_floor(plate["y"])
        x1, y1 = math_ceil(plate["x"]+plate["width"]), math_ceil(plate["y"]+plate["height"])
        crop = pixels[y0:y1, x0:x1]
        self.assertGreater(int(np.count_nonzero(crop[:, :, 2] < 140)), 1000)
        self.assertGreater(int(np.count_nonzero((crop[:, :, 0] > 220) & (crop[:, :, 2] > 230))), 50)
        # A tightly fitted caption plate leaves the rest of the frame unchanged.
        self.assertGreater(float(pixels[1300:1400, 125:920, 2].mean()), 200.)
        self.assertLess(plate["width"], 795.)


def math_floor(value):
    return int(np.floor(value))


def math_ceil(value):
    return int(np.ceil(value))


if __name__ == "__main__":
    unittest.main()
