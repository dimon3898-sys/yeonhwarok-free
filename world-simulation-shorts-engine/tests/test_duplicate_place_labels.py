"""Native-label regression and narrowly scoped false-positive protection.

The Rotterdam fixture preserves the actual S002 base/event box structure. These
synthetic unit tests do not render Earth frames or assert video publication QC.
"""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engine.qc import run_qc
from engine.visibility import analyze_duplicate_place_labels


def native_fixture():
    coordinates = {"lon": 4.442447, "lat": 51.904383,
                   "source_id": "SEAROUTE_1_6_0", "location_id": "ROTTERDAM_PORT"}
    scene = {"scene_id": "S002", "scene_type": "CITY_FOCUS", "start_time": 7.5, "duration": 7.5,
             "labels": [{"text": "ROTTERDAM", "coordinates": coordinates, "start_time": .1,
                         "end_time": 7.5, "role": "city", "opacity": .9}],
             "visual_events": [{"id": "E008", "kind": "region_reveal", "time": 3.45,
                                "target_id": "ROTTERDAM_PORT", "text": "ROTTERDAM",
                                "coordinates": coordinates}]}
    frame = {"scene_id": "S002", "t": 3.9, "renderResolution": [2160, 3840],
             "labels": [{"text": "ROTTERDAM", "event_id": None, "kind": "world_label",
                         "opacity": .9, "x": 1223.2503906250001, "y": 728.3241265943129,
                         "width": 569.5496093749999, "height": 110.39999999999999},
                        {"text": "ROTTERDAM", "event_id": "E008", "kind": "world_label",
                         "opacity": .96, "x": 1223.2503906250001, "y": 995.1241265943129,
                         "width": 569.5496093749999, "height": 110.39999999999999}]}
    return {"duration": 15., "scenes": [scene]}, [frame]


class DuplicatePlaceLabelTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.frames = native_fixture()

    def check_clear(self):
        report = analyze_duplicate_place_labels(self.plan, self.frames)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["findings"], [])
        return report

    def test_disjoint_native_base_event_boxes_same_place_fail(self):
        report = analyze_duplicate_place_labels(self.plan, self.frames)
        self.assertFalse(report["passed"])
        self.assertEqual(len(report["findings"]), 1)
        finding = report["findings"][0]
        self.assertEqual(finding["code"], "DUPLICATE_PLACE_LABEL")
        self.assertEqual(finding["target_id"], "ROTTERDAM_PORT")
        self.assertEqual(finding["event_id"], "E008")
        self.assertFalse(finding["sample"]["boxes_intersect"])
        self.assertAlmostEqual(finding["first_absolute_time"], 11.4)

    def test_consecutive_native_frames_are_aggregated_without_recounting_pairs(self):
        frames = [copy.deepcopy(self.frames[0]) for _ in range(4)]
        for index, frame in enumerate(frames):
            frame["t"] = 3.9+index/30
            frame["labels"].append(copy.deepcopy(frame["labels"][0]))
        finding = analyze_duplicate_place_labels(self.plan, frames)["findings"][0]
        self.assertEqual(finding["audited_frame_count"], 4)
        self.assertAlmostEqual(finding["last_local_time"], 4.)
        self.assertAlmostEqual(finding["audited_frame_equivalent_seconds"], 4/30)

    def test_city_reveal_or_arrival_event_owned_world_labels_are_also_checked(self):
        for kind in ["city_reveal", "arrival"]:
            with self.subTest(kind=kind):
                self.plan["scenes"][0]["visual_events"][0]["kind"] = kind
                self.assertFalse(analyze_duplicate_place_labels(self.plan, self.frames)["passed"])

    def test_explicit_drawn_place_id_cannot_be_overridden_by_matching_text(self):
        self.frames[0]["labels"][0]["location_id"] = "OTHER_ROTTERDAM"
        self.check_clear()

    def test_faded_event_box_does_not_count_as_visible_duplicate(self):
        self.frames[0]["labels"][1]["opacity"] = .1
        self.check_clear()

    def test_planned_duplicate_without_actual_drawn_box_is_not_a_finding(self):
        self.frames[0]["labels"] = self.frames[0]["labels"][:1]
        self.check_clear()

    def test_story_information_voice_subtitle_and_clip_labels_are_excluded(self):
        for kind in ["region_reveal", "information", "subtitle", "narration", "clip_information"]:
            with self.subTest(kind=kind):
                self.frames[0]["labels"][1]["kind"] = kind
                self.check_clear()

    def test_same_city_name_at_distinct_location_ids_is_not_a_duplicate(self):
        event = self.plan["scenes"][0]["visual_events"][0]
        event["target_id"] = "OTHER_ROTTERDAM"
        event["coordinates"] = {"lon": -74., "lat": 42., "location_id": "OTHER_ROTTERDAM"}
        self.check_clear()

    def test_ambiguous_same_name_base_targets_are_not_guessed_from_text(self):
        other = copy.deepcopy(self.plan["scenes"][0]["labels"][0])
        other["coordinates"] = {"lon": -74., "lat": 42., "location_id": "OTHER_ROTTERDAM"}
        self.plan["scenes"][0]["labels"].append(other)
        report = self.check_clear()
        self.assertEqual(report["unresolved_targets"][0]["reason"], "BASE_PLACE_TARGET_AMBIGUOUS")

    def test_unknown_event_id_is_not_resolved_from_matching_text(self):
        self.frames[0]["labels"][1]["event_id"] = "OTHER_SCENE_EVENT"
        report = self.check_clear()
        self.assertEqual(report["unresolved_targets"][0]["reason"], "UNKNOWN_SCENE_EVENT")

    def test_mismatched_event_coordinates_and_target_are_not_resolved(self):
        event = self.plan["scenes"][0]["visual_events"][0]
        event["coordinates"] = dict(event["coordinates"], location_id="ANOTHER_CITY")
        report = self.check_clear()
        self.assertEqual(report["unresolved_targets"][0]["reason"], "EVENT_PLACE_TARGET_UNRESOLVED")

    def test_explicit_separate_comparison_panels_are_exempt(self):
        self.plan["scenes"][0]["scene_type"] = "COMPARISON"
        self.frames[0]["labels"][0]["panel_id"] = "left"
        self.frames[0]["labels"][1]["panel_id"] = "right"
        self.check_clear()

    def test_same_panel_duplicate_still_fails(self):
        for label in self.frames[0]["labels"]:
            label["panel_id"] = "same_earth_view"
        self.assertFalse(analyze_duplicate_place_labels(self.plan, self.frames)["passed"])

    def test_single_earth_comparison_is_not_exempt_just_by_scene_type(self):
        self.plan["scenes"][0]["scene_type"] = "COMPARISON"
        self.assertFalse(analyze_duplicate_place_labels(self.plan, self.frames)["passed"])

    def test_clip_scene_annotations_are_outside_earth_place_label_scope(self):
        self.plan["scenes"][0]["scene_type"] = "CINEMATIC_CLIP"
        report = self.check_clear()
        self.assertEqual(report["exempted_scene_ids"], ["S002"])

    def test_identical_repeated_audit_record_does_not_prove_two_placements(self):
        self.frames[0]["labels"][1].update({key: self.frames[0]["labels"][0][key]
                                         for key in ["x", "y", "width", "height"]})
        self.check_clear()

    def test_invalid_or_empty_box_is_not_treated_as_a_drawn_label(self):
        for key, value in [("width", 0), ("height", -1), ("x", float("nan"))]:
            with self.subTest(key=key):
                frame = copy.deepcopy(self.frames[0])
                frame["labels"][1][key] = value
                self.assertTrue(analyze_duplicate_place_labels(self.plan, [frame])["passed"])

    def test_qc_hook_persists_duplicate_finding_and_fail_code(self):
        # Mock a single decoded preview frame only to test QC dispatch/reporting.
        # This deliberately does not pass unrelated video-duration/frame gates.
        self.plan["options"] = {"quality": "FAST"}
        metadata = {"format": {"duration": "15"}, "streams": [
            {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p",
             "width": 540, "height": 960, "avg_frame_rate": "30/1",
             "color_range": "tv", "color_space": "bt709", "color_transfer": "bt709",
             "color_primaries": "bt709"}, {"codec_type": "audio"}]}

        class Decoder:
            stdout = io.BytesIO(bytes([24, 48, 72])*540*960)
            returncode = 0

            def communicate(self, timeout=None):
                return b"", b""

            def poll(self):
                return 0

        with tempfile.TemporaryDirectory(prefix="duplicate-place-qc-test-") as directory, \
                patch("engine.qc.probe_video", return_value=metadata), \
                patch("engine.qc.subprocess.Popen", return_value=Decoder()), \
                patch("engine.qc._audio_measurement", return_value={"true_peak_dbfs": -2., "integrated_lufs": -18.}), \
                patch("engine.retention.analyze_retention", return_value={"passed": True}), \
                patch("engine.qc.analyze_rendered_retention", return_value={"passed": True}):
            report = run_qc(Path(directory)/"mock-not-real.mp4", self.plan, self.frames, Path(directory)/"qc")
            self.assertIn("DUPLICATE_PLACE_LABEL", report["failures"])
            self.assertFalse(report["passed"])
            saved = json.loads((Path(directory)/"qc/qc_report.json").read_text())
            self.assertEqual(saved["duplicate_place_labels"]["findings"][0]["event_id"], "E008")


if __name__ == "__main__":
    unittest.main()
