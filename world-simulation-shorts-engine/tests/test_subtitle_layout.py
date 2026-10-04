"""Real bundled-font layout and timed audit-box tests; no media/GL rendering."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.audio import (_ass_time, _subtitle_font, _subtitle_line_width,
                          create_subtitles, validate_subtitle_layout)
from engine.qc import analyze_subtitle_layout


class SubtitleLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="subtitle-layout-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.plan = {"duration": 20., "options": {"subtitles": True, "quality": "HIGH"},
                     "scenes": [{"scene_id": "S001", "start_time": 10., "duration": 5.,
                                 "narration": "서울에서 출발합니다."}]}

    def subtitles(self, text, *, start=10.13, end=14.77):
        return create_subtitles(self.plan, self.directory,
                                [{"scene_id": "S001", "start": start, "end": end,
                                  "text": text, "timing_source": "explicit_cue"}])

    def test_korean_fixed_character_limit_would_overflow_but_font_wrapping_fits(self):
        text = "한"*70
        font, _ = _subtitle_font()
        self.assertGreater(_subtitle_line_width(text[:25], font), 795.)
        report = self.subtitles(text)
        flattened = [line for caption in report["captions"] for line in caption["lines"]]
        self.assertEqual("".join(flattened), text)
        self.assertTrue(all(width <= 795. for caption in report["captions"] for width in caption["line_widths_px"]))
        self.assertTrue(validate_subtitle_layout(report, self.plan["duration"])["passed"])
        self.assertTrue(all(len(caption["lines"]) <= 2 for caption in report["captions"]))

    def test_words_are_preserved_and_long_word_fallback_loses_no_letters(self):
        text = "The route from New York to Singapore stays readable. "*8
        report = self.subtitles(text)
        flattened = [line for caption in report["captions"] for line in caption["lines"]]
        self.assertEqual(" ".join(flattened), " ".join(text.split()))
        second = self.directory/"longword"
        second.mkdir()
        report = create_subtitles(self.plan, second, [{"start": 10., "end": 15., "text": "W"*90}])
        flattened = [line for caption in report["captions"] for line in caption["lines"]]
        self.assertEqual("".join(flattened), "W"*90)
        self.assertTrue(validate_subtitle_layout(report, 20.)["passed"])

    def test_exact_ass_times_and_font_spacing_outline_are_recorded(self):
        report = self.subtitles("서울에서 출발합니다.")
        self.assertEqual(report["font"]["size_px"], 44)
        self.assertEqual(report["font"]["spacing_px"], .4)
        self.assertEqual(report["font"]["outline_px"], 2)
        self.assertEqual(len(report["font"]["sha256"]), 64)
        ass = Path(report["path"]).read_text()
        for caption in report["captions"]:
            self.assertIn(f"Dialogue: 0,{_ass_time(caption['start'])},{_ass_time(caption['end'])}", ass)

    def test_invalid_caption_time_fails_before_ass_is_written(self):
        with self.assertRaisesRegex(RuntimeError, "SUBTITLE_LAYOUT_INVALID"):
            self.subtitles("서울", start=19., end=21.)
        self.assertFalse((self.directory/"subtitles.ass").exists())

    def test_unsafe_metadata_is_a_failure_not_a_clear_layout_claim(self):
        report = self.subtitles("서울")
        report = copy.deepcopy(report)
        report["captions"][0]["box"]["x"] = 124.
        checked = analyze_subtitle_layout(report, [], self.plan)
        self.assertFalse(checked["passed"])
        self.assertIn("SUBTITLE_OUTSIDE_SAFE_AREA", {error["code"] for error in checked["errors"]})

    def test_active_caption_overlap_scales_4k_labels_to_final_pixels(self):
        report = self.subtitles("서울에서 출발합니다.")
        box = report["captions"][0]["line_boxes"][0]
        label = {**{key: value*2 for key, value in box.items()}, "text": "SEOUL", "opacity": .9}
        audits = [{"scene_id": "S001", "t": 2., "renderResolution": [2160, 3840], "labels": [label]}]
        checked = analyze_subtitle_layout(report, audits, self.plan)
        self.assertTrue(checked["passed"])  # Overlap warns; safe geometry remains valid.
        self.assertEqual(len(checked["overlaps"]), 1)
        self.assertEqual(checked["overlaps"][0]["first_time"], 12.)
        self.assertAlmostEqual(checked["overlaps"][0]["maximum_intersection_pixels"], box["width"]*box["height"])
        for audit in audits:
            audit["t"] = 5.
        self.assertFalse(analyze_subtitle_layout(report, audits, self.plan)["overlaps"])

    def test_fast_output_overlap_is_scaled_without_inflating_intersection(self):
        report = self.subtitles("서울")
        box = report["captions"][0]["line_boxes"][0]
        label = {**{key: value/2 for key, value in box.items()}, "text": "SEOUL", "opacity": 1.}
        audits = [{"scene_id": "S001", "t": 2., "renderResolution": [540, 960], "labels": [label]}]
        checked = analyze_subtitle_layout(report, audits, self.plan, output_width=540, output_height=960)
        self.assertAlmostEqual(checked["overlaps"][0]["maximum_intersection_pixels"], box["width"]*box["height"]/4)

    def test_enabled_missing_metadata_fails_and_unknown_label_geometry_warns(self):
        self.assertFalse(analyze_subtitle_layout({"enabled": True}, [], self.plan)["passed"])
        report = self.subtitles("서울")
        audits = [{"scene_id": "S001", "t": 2., "labels": [{"text": "City", "kind": "clip_information"}]}]
        checked = analyze_subtitle_layout(report, audits, self.plan)
        self.assertTrue(checked["passed"])
        self.assertIn("SUBTITLE_LABEL_GEOMETRY_UNAVAILABLE", {warning["code"] for warning in checked["warnings"]})

    def test_disabled_subtitles_need_no_layout_metadata(self):
        self.plan["options"]["subtitles"] = False
        report = create_subtitles(self.plan, self.directory, [])
        self.assertTrue(analyze_subtitle_layout(report, [], self.plan)["passed"])
        self.assertFalse(report["enabled"])
        self.assertFalse((self.directory/"subtitles.ass").exists())


if __name__ == "__main__":
    unittest.main()
