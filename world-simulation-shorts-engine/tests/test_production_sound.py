"""Production audio behavior and byte-stable legacy regression, without GL/TTS."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from engine.audio import create_audio, _production_ducking, _production_music, _production_energy_points
from engine.sfx_library import (SR, CATEGORIES, INTENSITIES, INTENSITY_GAIN, catalog, materialize_variant,
                               prepare_production_sound_events, select_sound_events, render_sound_events,
                               synthesize_variant)


def plan_fixture() -> dict:
    return {"duration": 4., "options": {"bgm": True, "tts": False, "subtitles": False},
            "scenes": [{"scene_id": "S01", "start_time": 0., "duration": 4., "narration": "",
                        "music_energy": .42, "sound_events": [
                            {"kind": "soft_pulse", "time": .1, "gain": .08},
                            {"kind": "low_whoosh", "time": 1.1, "duration": .8, "gain": .13},
                            {"kind": "deep_final_hit", "time": 2.2, "gain": .15}]}]}


def production_fixture() -> dict:
    result = plan_fixture()
    result["production_defaults"] = {"version": "v1"}
    result["request"] = {"pace": "FAST"}
    scene = result["scenes"][0]
    scene["visual_events"] = [
        {"id": "E01", "time": .11, "kind": "country_reveal"},
        {"id": "E02", "time": 1.10, "kind": "route_start"},
        {"id": "E03", "time": 2.2, "kind": "final_reveal", "role": "payoff"},
    ]
    scene["sound_events"] = [
        {"id": "A01", "time": .9, "kind": "soft_pulse", "visual_event_id": "E01"},
        {"id": "A02", "time": .3, "kind": "low_whoosh", "visual_event_id": "E02"},
        {"id": "A03", "time": 1.9, "kind": "deep_final_hit", "visual_event_id": "E03"},
    ]
    return result


class ProductionSoundTests(unittest.TestCase):
    def test_catalog_all_categories_three_unique_licensed_stereo_variants(self):
        details = catalog()
        self.assertEqual(len(details["variants"]), len(CATEGORIES)*3)
        hashes = set()
        for category in CATEGORIES:
            rows = [v for v in details["variants"] if v["category"] == category]
            self.assertEqual(len(rows), 3)
            for row in rows:
                signal = synthesize_variant(row)
                self.assertEqual(signal.shape[1], 2)
                self.assertTrue(np.all(np.isfinite(signal)))
                self.assertLessEqual(float(np.max(np.abs(signal))), 1.000001)
                self.assertGreater(float(np.sqrt(np.mean(signal**2))), .025)
                self.assertEqual(row["license"], "CC0-1.0")
                self.assertFalse(row["attribution_required"])
                hashes.add(hashlib.sha256(signal.tobytes()).hexdigest())
        self.assertEqual(len(hashes), len(details["variants"]))

    def test_variant_cache_immutable_and_source_content_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, metadata = materialize_variant("CITY_REVEAL_01", Path(temporary))
            path = Path(metadata["file"])
            before = path.stat().st_mtime_ns
            repeated, again = materialize_variant("CITY_REVEAL_01", Path(temporary))
            self.assertEqual(path.stat().st_mtime_ns, before)
            self.assertEqual(metadata["sha256"], again["sha256"])
            np.testing.assert_array_equal(first, repeated)
            path.write_bytes(b"changed by external writer")
            with self.assertRaises((RuntimeError, ValueError)):
                materialize_variant("CITY_REVEAL_01", Path(temporary))

    def test_bound_events_override_wrong_sound_timestamp_and_snap_visible_frame(self):
        source = production_fixture()
        before = copy.deepcopy(source)
        transformed = prepare_production_sound_events(source)
        self.assertEqual(source, before)
        events = select_sound_events(transformed)["events"]
        self.assertEqual([e["frame"] for e in events], [4, 33, 66])
        self.assertAlmostEqual(events[0]["absolute_time"], 4/30)
        self.assertEqual([e["sfx_category"] for e in events], ["COUNTRY_REVEAL", "ROUTE_START", "FINAL_REVEAL"])
        self.assertEqual([e["sfx_intensity"] for e in events], ["LOW", "MEDIUM", "PEAK"])
        self.assertTrue(all(0 <= e["sync_error_seconds"] < 1/30 for e in events))

    def test_repeated_category_avoids_consecutive_and_three_recent_choices(self):
        plan = production_fixture()
        scene = plan["scenes"][0]
        scene["visual_events"] = []
        scene["sound_events"] = [{"id": f"A{i}", "kind": "soft_pulse", "time": i*.2,
                                  "sfx_category": "CITY_REVEAL"} for i in range(9)]
        selection = select_sound_events(plan)
        variants = [e["sfx_variant"] for e in selection["events"]]
        self.assertEqual(len(set(variants[:3])), 3)
        self.assertTrue(all(a != b for a, b in zip(variants, variants[1:])))
        self.assertEqual(select_sound_events(plan), selection)
        history = selection["history"][:1]
        snapshot = copy.deepcopy(history)
        altered = copy.deepcopy(plan)
        altered["scenes"][0]["sound_events"] = [dict(scene["sound_events"][1])]
        next_choice = select_sound_events(altered, history)
        self.assertNotEqual(next_choice["events"][0]["sfx_variant"], history[-1]["sfx_variant"])
        self.assertEqual(history, snapshot)
        self.assertEqual(len(next_choice["history"]), 2)

    def test_six_decimal_frame_snapped_ir_does_not_accidentally_delay_one_frame(self):
        plan = production_fixture()
        plan["scenes"][0]["visual_events"][0]["time"] = 2.266667
        plan["scenes"][0]["sound_events"] = [plan["scenes"][0]["sound_events"][0]]
        event = select_sound_events(plan)["events"][0]
        self.assertEqual(event["frame"], 68)
        self.assertAlmostEqual(event["absolute_time"], 68/30)
        self.assertLess(abs(event["sync_error_seconds"]), .000001)

    def test_automatic_retention_event_binding_emits_complete_scene_json_sound_fields(self):
        plan = production_fixture()
        plan["scenes"][0]["sound_events"] = []
        transformed = prepare_production_sound_events(plan)
        sounds = transformed["scenes"][0]["sound_events"]
        self.assertEqual(len(sounds), 3)
        for event in sounds:
            self.assertTrue({"id", "kind", "time", "duration", "visual_event_id"}.issubset(event))
            self.assertGreater(event["duration"], 0)
            self.assertTrue(event["visual_event_id"])

    def test_explicit_choice_is_honored_and_repeat_is_disclosed(self):
        plan = production_fixture()
        scene = plan["scenes"][0]
        scene["visual_events"] = []
        scene["sound_events"] = [{"id": "A0", "kind": "soft_pulse", "time": .1,
                                  "sfx_category": "CITY_REVEAL", "sfx_variant": "CITY_REVEAL_01"},
                                 {"id": "A1", "kind": "soft_pulse", "time": .3,
                                  "sfx_category": "CITY_REVEAL", "sfx_variant": "CITY_REVEAL_01"}]
        report = select_sound_events(plan)
        self.assertEqual(report["events"][1]["sfx_variant"], "CITY_REVEAL_01")
        self.assertTrue(any(e["code"] == "SFX_CONSECUTIVE_EXPLICIT_REPEAT" for e in report["warnings"]))

    def test_bad_category_binding_variant_and_intensity_fail_before_mixing(self):
        for update in [{"sfx_category": "UNKNOWN"}, {"sfx_variant": "ROUTE_BLOCK_01"},
                       {"sfx_intensity": "LOUD"}, {"visual_event_id": "MISSING"}]:
            with self.subTest(update=update):
                plan = production_fixture()
                plan["scenes"][0]["sound_events"][0].update(update)
                with self.assertRaises(ValueError):
                    select_sound_events(plan)

    def test_actual_waveform_starts_at_frame_sample_and_intensity_scales(self):
        amplitudes = []
        with tempfile.TemporaryDirectory() as temporary:
            for intensity in INTENSITIES:
                plan = production_fixture()
                scene = plan["scenes"][0]
                scene["visual_events"] = []
                scene["sound_events"] = [{"id": "A", "kind": "pulse", "time": .51,
                    "sfx_category": "CITY_REVEAL", "sfx_variant": "CITY_REVEAL_01", "sfx_intensity": intensity}]
                signal, report = render_sound_events(plan, Path(temporary))
                at = report["events"][0]["onset_sample"]
                self.assertEqual(at, 16*1600)
                self.assertFalse(np.any(signal[:at]))
                self.assertTrue(np.any(signal[at:at+round(.01*SR)]))
                amplitudes.append(float(np.max(np.abs(signal))))
        np.testing.assert_allclose(amplitudes, [INTENSITY_GAIN[v] for v in INTENSITIES], rtol=1e-6)

    def test_sfx_off_is_silent_does_not_generate_or_destroy_library(self):
        plan = production_fixture()
        plan["options"]["sfx"] = False
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary)/"not-created"
            signal, report = render_sound_events(plan, library)
            self.assertFalse(np.any(signal))
            self.assertFalse(library.exists())
            self.assertFalse(report["enabled"])
            self.assertEqual(report["sources"], [])
            self.assertEqual(len(report["events"]), 3)

    def test_narration_priority_cues_and_untimed_voice_with_smooth_gain(self):
        duration = 3.
        t = np.arange(round(duration*SR))/SR
        narration = np.zeros((len(t), 2), np.float64)
        narration[(t >= 1.) & (t < 2.)] = .11
        for cues in [[], [{"start": 1., "end": 2.}]]:
            with self.subTest(cues=bool(cues)):
                music, sound, report = _production_ducking(cues, narration, duration)
                self.assertLessEqual(music[round(1.5*SR)], .161)
                self.assertLessEqual(sound[round(1.5*SR)], .251)
                self.assertGreater(music[round(.5*SR)], .95)
                self.assertGreater(sound[round(2.8*SR)], .95)
                self.assertLess(float(np.max(np.abs(np.diff(sound)))), .001)
                self.assertFalse(report["tts_speed_changed"])

    def test_music_responds_to_pace_peak_and_post_peak_breath(self):
        plan = production_fixture()
        scene = plan["scenes"][0]
        scene["visual_events"][1].update({"kind": "peak_reveal", "role": "peak"})
        points = dict(_production_energy_points(plan))
        self.assertGreater(points[1.1+.08], points[1.1+.56])
        self.assertGreater(points[2.2+.08], points[1.1+.08])
        fast, fast_report = _production_music(plan["duration"], plan)
        plan["request"]["pace"] = "CINEMATIC"
        cinema, cinema_report = _production_music(plan["duration"], plan)
        self.assertEqual(fast.shape, cinema.shape)
        self.assertGreater(fast_report["pulse_hz"], cinema_report["pulse_hz"])
        self.assertFalse(np.array_equal(fast, cinema))

    def test_legacy_unmarked_raw_pcm_hash_is_identical_to_pre_change_golden(self):
        # Recorded by the original audio.py on this unchanged representative
        # pulse/whoosh/deep-impact plan before production dispatch was added.
        with tempfile.TemporaryDirectory() as temporary:
            report = create_audio(plan_fixture(), Path(temporary))
            sha = hashlib.sha256((Path(temporary)/"mix_raw.wav").read_bytes()).hexdigest()
            self.assertEqual(sha, "6d99792c5f0ffa464188003c300b9e216cee6e474234849152e1d7cc35af1091")
            self.assertNotIn("production_defaults", report)
            self.assertFalse((Path(temporary)/"sfx_history.json").exists())

    def test_production_mix_persists_actual_files_sync_and_voice_priority_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            # Keep this test's materialized assets outside the shared library.
            from engine.sfx_library import render_sound_events as render_original
            def private_library(plan, _):
                return render_original(plan, path/"library")
            with patch("engine.audio.render_sound_events", side_effect=private_library):
                report = create_audio(production_fixture(), path/"output")
            self.assertEqual(report["duration"], 4.)
            self.assertLessEqual(report["peak_dbfs"], -2.45)
            self.assertEqual(report["production_defaults"], "v1")
            self.assertFalse(report["direct_listening"])
            self.assertEqual(len(report["sfx_library"]["sources"]), 3)
            persisted = json.loads((path/"output/sfx_history.json").read_text())
            self.assertEqual(persisted, report["sfx_library"]["history"])
            self.assertLess(report["sfx_library"]["max_sync_error_seconds"], 1/30)
            for source in report["sfx_library"]["sources"]:
                self.assertEqual(hashlib.sha256(Path(source["file"]).read_bytes()).hexdigest(), source["sha256"])


if __name__ == "__main__":
    unittest.main()
