"""Declared-context/timing regressions; no ASR, GL, or paid service calls."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.advanced_revisions import _delete_scenes
from engine.audio import SR, _narration, create_audio
from engine.gis import resolve_location
from engine.narration import validate_narration_bindings, attach_narration_timing


def fixture_plan():
    london = resolve_location("london")["coordinates"]
    paris = resolve_location("paris")["coordinates"]
    source = london["source_id"]
    return {"duration": 10., "request": {"duration": 10.},
            "options": {"tts": False, "subtitles": False, "bgm": False},
            "sources": [{"id": source}], "story": {"hook": "A journey", "beats": [], "claims": [
                {"id": "F01", "status": "FACT", "source_ids": [source]},
                {"id": "F02", "status": "FACT", "source_ids": [source]},
                {"id": "M01", "status": "SIMULATION", "source_ids": [source], "assumption_ids": ["A01"]}]},
            "scenes": [
                {"scene_id": "S001", "start_time": 0., "duration": 5., "narration": "London is the starting point.",
                 "coordinates": london, "geographic_targets": ["london"], "claim_ids": ["F01", "M01"],
                 "narration_event_ids": ["E001", "E002"], "routes": [], "entities": [], "sound_events": [],
                 "entry_state": {"camera": {}}, "exit_state": {"camera": {}, "entities": []},
                 "visual_events": [{"id": "E001", "kind": "city_reveal", "time": .6,
                                    "target_id": "london", "coordinates": london, "claim_id": "F01"},
                                   {"id": "E002", "kind": "milestone_reveal", "time": 4.7,
                                    "coordinates": london, "claim_id": "M01"}]},
                {"scene_id": "S002", "start_time": 5., "duration": 5., "narration": "Paris is next.",
                 "coordinates": paris, "geographic_targets": ["paris"], "claim_ids": ["F02"],
                 "narration_event_ids": ["E003"], "routes": [], "entities": [], "sound_events": [],
                 "entry_state": {"camera": {}}, "exit_state": {"camera": {}, "entities": []},
                 "visual_events": [{"id": "E003", "kind": "city_reveal", "time": .8,
                                    "target_id": "paris", "coordinates": paris, "claim_id": "F02"}]},
            ]}


class NarrationBindingTests(unittest.TestCase):
    def setUp(self):
        self.plan = fixture_plan()

    def codes(self, report):
        return {error["code"] for error in report["errors"]}

    def test_valid_late_scene_context_is_not_a_word_anchor(self):
        report = validate_narration_bindings(self.plan)
        self.assertTrue(report["passed"], report["errors"])
        self.assertFalse(report["word_alignment"])
        self.assertFalse(report["lexical_content_verified"])
        binding = report["scenes"][0]["event_bindings"][0]
        self.assertEqual(binding["target_kind"], "verified_gis_location")
        self.assertTrue(binding["gis_references"][0]["verified"])
        timed = attach_narration_timing(self.plan, report,
                                      [{"scene_id": "S001", "start": .04, "end": 1., "timing_source": "measured_scene_synthesis"}],
                                      [{"scene_id": "S001", "provider": "TEST_FIXTURE"}])
        late = timed["scenes"][0]["event_bindings"][1]
        self.assertFalse(late["authored_event_inside_voice_window"])
        self.assertFalse(late["outside_voice_window_is_error"])
        self.assertTrue(timed["passed"])

    def test_unknown_cross_scene_and_duplicate_references_are_distinct_failures(self):
        cases = [("E999", "UNKNOWN_NARRATION_EVENT"), ("E003", "CROSS_SCENE_NARRATION_EVENT")]
        for event, expected in cases:
            with self.subTest(event=event):
                plan = copy.deepcopy(self.plan)
                plan["scenes"][0]["narration_event_ids"] = [event]
                self.assertIn(expected, self.codes(validate_narration_bindings(plan)))
        self.plan["scenes"][0]["narration_event_ids"] = ["E001", "E001"]
        self.assertIn("DUPLICATE_NARRATION_EVENT_BINDING", self.codes(validate_narration_bindings(self.plan)))

    def test_missing_binding_blocks_audio_before_synthesis(self):
        del self.plan["scenes"][0]["narration_event_ids"]
        with tempfile.TemporaryDirectory() as temporary, patch("engine.audio._narration") as voice:
            with self.assertRaisesRegex(RuntimeError, "NARRATION_BINDING_INVALID"):
                create_audio(self.plan, Path(temporary))
            voice.assert_not_called()

    def test_actual_revision_deletion_preserves_live_refs_and_stale_deleted_id_fails(self):
        edited = _delete_scenes(self.plan, ["S002"])["plan"]
        self.assertTrue(validate_narration_bindings(edited)["passed"])
        self.assertEqual(edited["duration"], 5.)
        edited["scenes"][0]["narration_event_ids"].append("E003")
        self.assertIn("UNKNOWN_NARRATION_EVENT", self.codes(validate_narration_bindings(edited)))

    def test_bound_claim_must_exist_and_belong_to_the_scene(self):
        plan = copy.deepcopy(self.plan)
        plan["scenes"][0]["visual_events"][0]["claim_id"] = "F02"
        self.assertIn("NARRATION_CLAIM_OUTSIDE_SCENE", self.codes(validate_narration_bindings(plan)))
        plan["scenes"][0]["visual_events"][0]["claim_id"] = "NOT_A_CLAIM"
        self.assertIn("UNKNOWN_NARRATION_EVENT_CLAIM", self.codes(validate_narration_bindings(plan)))

    def planned_route(self):
        london = resolve_location("london")["coordinates"]
        paris = resolve_location("paris")["coordinates"]
        return {"route_id": "FUTURE_ROUTE", "kind": "great_circle", "points": [london, paris],
                "source_ids": [london["source_id"]], "start_time": 0., "end_time": 5.,
                "progress_start": 0., "progress_end": 1.}

    def test_future_route_comparison_uses_verified_planned_endpoints_without_activity_claim(self):
        self.plan["scenes"][1]["routes"] = [self.planned_route()]
        event = self.plan["scenes"][0]["visual_events"][1]
        event.update(kind="comparison_reveal", target_id="FUTURE_ROUTE")
        report = validate_narration_bindings(self.plan)
        self.assertTrue(report["passed"], report["errors"])
        binding = report["scenes"][0]["event_bindings"][1]
        self.assertEqual(binding["target_kind"], "planned_route")
        self.assertEqual(binding["target_scope"], "not_active_in_scene")
        self.assertEqual(binding["planned_route_scene_ids"], ["S002"])
        self.assertFalse(binding["physical_activity_verified"])
        self.assertEqual({reference["location_id"] for reference in binding["gis_references"]}, {"london", "paris"})
        self.assertTrue(all(reference["verified"] for reference in binding["gis_references"]))
        self.assertFalse(report["warnings"])

    def test_same_route_geometry_can_have_different_local_progress_windows(self):
        first = self.planned_route()
        second = copy.deepcopy(first)
        second.update(start_time=1., end_time=4., progress_start=.5, progress_end=.75, faint=True)
        self.plan["scenes"][0]["routes"] = [first]
        self.plan["scenes"][1]["routes"] = [second]
        report = validate_narration_bindings(self.plan)
        self.assertTrue(report["passed"], report["errors"])

    def test_reused_route_id_with_different_geography_fails_instead_of_choosing(self):
        first = self.planned_route()
        second = copy.deepcopy(first)
        second["points"][-1] = resolve_location("rome")["coordinates"]
        self.plan["scenes"][0]["routes"] = [first]
        self.plan["scenes"][1]["routes"] = [second]
        self.assertIn("CONFLICTING_NARRATION_ROUTE_ID", self.codes(validate_narration_bindings(self.plan)))

    def test_off_scene_physical_route_or_entity_cannot_be_resolved_as_information(self):
        self.plan["scenes"][1]["routes"] = [self.planned_route()]
        self.plan["scenes"][1]["entities"] = [{"id": "FUTURE_AIRCRAFT", "type": "aircraft", "route_id": "FUTURE_ROUTE"}]
        for target, kind in [("FUTURE_ROUTE", "route_start"), ("FUTURE_AIRCRAFT", "entity_departure")]:
            with self.subTest(target=target):
                self.plan["scenes"][0]["visual_events"][1].update(kind=kind, target_id=target)
                report = validate_narration_bindings(self.plan)
                self.assertIn("OFF_SCENE_NARRATION_PHYSICAL_TARGET", self.codes(report))
                binding = report["scenes"][0]["event_bindings"][1]
                self.assertEqual(binding["target_kind"], "unresolved_physical_target")
                self.assertFalse(binding["physical_activity_verified"])
                self.assertFalse(binding["planned_route_scene_ids"])

    def test_measured_tts_cues_keep_declared_refs_without_word_alignment(self):
        from test_audio_language import RecordingProvider, read_fixture_stereo
        self.plan["options"]["tts"] = True
        with tempfile.TemporaryDirectory() as temporary, patch("engine.audio._stereo", side_effect=read_fixture_stereo):
            _, cues, metadata = _narration(self.plan, Path(temporary), RecordingProvider())
        self.assertEqual(cues[0]["declared_narration_event_ids"], ["E001", "E002"])
        self.assertEqual(cues[0]["declared_claim_ids"], ["F01", "M01"])
        self.assertAlmostEqual(cues[0]["end"]-cues[0]["start"], .125)
        report = attach_narration_timing(self.plan, validate_narration_bindings(self.plan), cues, metadata)
        self.assertTrue(report["passed"])
        self.assertTrue(report["scenes"][0]["timing"]["measured_scene_synthesis"])
        self.assertFalse(report["word_alignment"])

    def test_tts_off_and_external_cues_are_not_claimed_measured_speech_alignment(self):
        report = validate_narration_bindings(self.plan)
        no_voice = attach_narration_timing(self.plan, report, [], [])
        self.assertEqual(no_voice["scenes"][0]["timing"]["status"], "NOT_MEASURED_TTS_OFF")
        external = attach_narration_timing(self.plan, report, [{"start": .5, "end": 1.5}],
                                          [{"provider": "USER_FILE", "duration": 10.}])
        self.assertTrue(external["passed"])
        self.assertEqual(external["scenes"][0]["timing"]["status"], "USER_PROVIDED_CUES")
        self.assertFalse(external["scenes"][0]["timing"]["measured_scene_synthesis"])
        self.assertIn("EXTERNAL_NARRATION_CONTENT_NOT_RECOGNIZED", {warning["code"] for warning in external["warnings"]})

    def test_explicit_external_scene_and_file_intervals_fail_when_inconsistent(self):
        report = validate_narration_bindings(self.plan)
        external = attach_narration_timing(self.plan, report,
                                          [{"scene_id": "S002", "start": .5, "end": 1.5}],
                                          [{"provider": "USER_FILE", "duration": 10.}])
        self.assertIn("NARRATION_CUE_OUTSIDE_DECLARED_SCENE", self.codes(external))
        external = attach_narration_timing(self.plan, report, [{"start": .5, "end": 1.5}],
                                          [{"provider": "USER_FILE", "duration": 1.}])
        self.assertIn("NARRATION_CUE_EXCEEDS_AUDIO_FILE", self.codes(external))

    def test_audio_report_persists_tts_off_context_without_claiming_measured_voice(self):
        class SilentPrimitives:
            def __init__(self, duration):
                self.audio = np.zeros((round(duration*SR), 2), np.float64)
        def write_fixture(command):
            wavfile.write(Path(command[-1]), SR, np.zeros((round(self.plan["duration"]*SR), 2), np.int16))
        def read_fixture(path):
            _, signal = wavfile.read(path)
            return signal.astype(np.float32)/32768
        with tempfile.TemporaryDirectory() as temporary, patch("engine.audio._synth_class", return_value=SilentPrimitives), \
                patch("engine.audio._run", side_effect=write_fixture), patch("engine.audio._stereo", side_effect=read_fixture):
            result = create_audio(self.plan, Path(temporary))
            persisted = json.loads(Path(result["narration_alignment_file"]).read_text())
            self.assertEqual(result["narration_alignment"], persisted)
            self.assertTrue(persisted["passed"])
            self.assertFalse(persisted["word_alignment"])
            self.assertEqual(persisted["scenes"][0]["timing"]["status"], "NOT_MEASURED_TTS_OFF")


if __name__ == "__main__":
    unittest.main()
