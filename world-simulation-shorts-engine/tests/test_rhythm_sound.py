"""Actual PCM, event policy and legacy protection without any visual renderer."""
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
from scipy.io import wavfile

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from engine.audio import SR, TTSProvider, create_audio
from engine.rhythm_sound import (CATEGORIES, INTENSITIES, INTENSITY_GAIN, catalog, synthesize_variant,
    materialize_variant, rhythm_audio_enabled, select_rhythm_sound_events, render_rhythm_sound_events,
    rhythm_bgm_envelope, bgm_event_sidechain)
from engine.sfx_library import catalog as v1_catalog, INTENSITIES as V1_INTENSITIES


def fixture() -> dict:
    return {"duration": 4., "render": {"fps": 30}, "request": {"pace": "FAST_PLUS"},
        "production_defaults": {"version": "v1"}, "options": {"bgm": True, "sfx": True, "tts": False, "subtitles": False},
        "rhythm_policy": {"version": "v1", "sfx_core_onset_offset_frames": 1, "bgm_sidechain": True,
            "micro_pauses": [{"id": "P01", "time": 2.066667, "duration": .166667, "scene_id": "S01", "event_id": "E03"}]},
        "scenes": [{"scene_id": "S01", "start_time": 0., "duration": 4., "narration": "",
            "music_energy": .48,
            "visual_events": [{"id": "E01", "time": .11, "kind": "country_reveal"},
                {"id": "E02", "time": 1.1, "kind": "route_blocked"},
                {"id": "E03", "time": 2.2, "kind": "final_reveal", "role": "payoff"}],
            "sound_events": [{"id": "A01", "time": .11, "kind": "pulse", "visual_event_id": "E01", "sfx_intensity": "MEDIUM", "gain": .01},
                {"id": "A02", "time": 1.1, "kind": "impact", "visual_event_id": "E02", "sfx_intensity": "MEDIUM"},
                {"id": "A03", "time": 2.2, "kind": "final_hit", "visual_event_id": "E03", "sfx_intensity": "MEDIUM"}],
            "rhythm_micro_beats": [{"id": "B01", "time": 0., "duration": .42, "kind": "REVEAL", "music_energy": .60},
                {"id": "B02", "time": .42, "duration": .31, "kind": "FOCUS", "music_energy": .54},
                {"id": "B03", "time": .73, "duration": .58, "kind": "MOVE", "music_energy": .72}]}]}


class FixtureVoice(TTSProvider):
    name = "TEST_PCM_VOICE"

    def __init__(self):
        self.calls = []

    def synthesize(self, text, destination, *, language="en", speed=155):
        self.calls.append((text, language, speed))
        t = np.arange(round(SR*1.4))/SR
        voice = (.15*np.sin(2*np.pi*310*t)).astype(np.float32)
        wavfile.write(destination, SR, np.column_stack((voice, voice)))
        return {"provider": self.name, "file": str(destination), "duration": 1.4,
                "language": language, "word_alignment": False}


class RhythmSoundTests(unittest.TestCase):
    def test_v2_catalog_has_99_unique_stereo_original_variants_and_v1_unchanged(self):
        details = catalog()
        self.assertEqual(len(CATEGORIES), 33)
        self.assertEqual(len(details["variants"]), 99)
        self.assertEqual(INTENSITIES, ("SUBTLE", "LOW", "MEDIUM", "HIGH", "PEAK"))
        self.assertNotIn("SUBTLE", V1_INTENSITIES)
        self.assertEqual(v1_catalog()["version"], "production-sfx-v1")
        self.assertEqual(v1_catalog()["source_sha256"], "dc90d7a74125da8914a56c6446d1b1d4e44ba7259fef7095603012663ad9ec9a")
        hashes = set()
        for row in details["variants"]:
            first, second = synthesize_variant(row), synthesize_variant(row)
            np.testing.assert_array_equal(first, second)
            self.assertEqual(first.shape[1], 2)
            self.assertTrue(np.all(np.isfinite(first)))
            self.assertLessEqual(float(np.max(np.abs(first))), 1.000001)
            self.assertGreater(float(np.sqrt(np.mean(first**2))), .025)
            self.assertEqual(row["license"], "CC0-1.0")
            self.assertFalse(row["attribution_required"])
            hashes.add(hashlib.sha256(first.tobytes()).hexdigest())
        self.assertEqual(len(hashes), 99)

    def test_immutable_content_addressed_waveform_and_sidecar_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, meta = materialize_variant("ROUTE_START_02", Path(temporary))
            path = Path(meta["file"])
            before = path.stat().st_mtime_ns
            again, second = materialize_variant("ROUTE_START_02", Path(temporary))
            self.assertEqual(path.stat().st_mtime_ns, before)
            np.testing.assert_array_equal(first, again)
            self.assertEqual(second["sha256"], meta["sha256"])
            self.assertEqual(path.parent.name, catalog()["library_content_sha256"][:16])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), meta["sha256"])
            path.write_bytes(b"external tamper")
            with self.assertRaises((ValueError, RuntimeError)):
                materialize_variant("ROUTE_START_02", Path(temporary))

    def test_onset_offset_happens_after_binding_without_mutating_canonical_plan(self):
        plan = fixture()
        snapshot = copy.deepcopy(plan)
        plan["scenes"][0]["sound_events"][0]["time"] = .9
        original = copy.deepcopy(plan)
        result = select_rhythm_sound_events(plan)
        self.assertEqual(plan, original)
        core = [e for e in result["events"] if e["primary_sync"]]
        self.assertEqual([e["canonical_frame"] for e in core], [4, 33, 66])
        self.assertEqual([e["frame"] for e in core], [5, 34, 67])
        self.assertTrue(all(e["sync_error_seconds"] == 0 for e in core))
        self.assertAlmostEqual(core[0]["absolute_time"], 5/30)
        self.assertEqual(snapshot["scenes"][0]["visual_events"], plan["scenes"][0]["visual_events"])

    def test_six_decimal_frame_and_zero_offset_mode(self):
        plan = fixture()
        plan["scenes"][0]["visual_events"][0]["time"] = 2.266667
        plan["scenes"][0]["sound_events"] = [plan["scenes"][0]["sound_events"][0]]
        result = select_rhythm_sound_events(plan)["events"][0]
        self.assertEqual((result["canonical_frame"], result["frame"]), (68, 69))
        plan["rhythm_policy"]["sfx_core_onset_offset_frames"] = 0
        self.assertEqual(select_rhythm_sound_events(plan)["events"][0]["frame"], 68)

    def test_roles_replace_inherited_blanket_levels_and_gain_but_user_override_available(self):
        plan = fixture()
        cores = [e for e in select_rhythm_sound_events(plan)["events"] if e["primary_sync"]]
        self.assertEqual([e["sfx_intensity"] for e in cores], ["LOW", "HIGH", "PEAK"])
        self.assertEqual(cores[0]["linear_gain"], INTENSITY_GAIN["LOW"])
        self.assertTrue(cores[0]["inherited_gain_ignored"])
        plan["rhythm_policy"]["preserve_authored_sfx_choices"] = True
        authored = [e for e in select_rhythm_sound_events(plan)["events"] if e["primary_sync"]]
        self.assertEqual([e["sfx_intensity"] for e in authored], ["MEDIUM"]*3)
        self.assertAlmostEqual(authored[0]["linear_gain"], INTENSITY_GAIN["MEDIUM"]*.01/.12)

    def test_peak_layers_precede_and_follow_bound_core_maximum_three(self):
        result = select_rhythm_sound_events(fixture())
        peak = [e for e in result["events"] if e["event_id"] == "A03"]
        self.assertEqual([e["layer"] for e in peak], ["pre", "core", "post"])
        self.assertEqual([e["frame"] for e in peak], [61, 67, 70])
        self.assertTrue(peak[0]["pre_hit"] and peak[0]["reverse"])
        self.assertTrue(peak[2]["post_hit"])
        self.assertEqual(len(result["events"]), 6)

    def test_history_is_deterministic_compatible_and_never_consecutively_repeats(self):
        plan = fixture()
        scene = plan["scenes"][0]
        scene["visual_events"] = []
        scene["sound_events"] = [{"id": f"A{i}", "kind": "tick", "time": i*.2,
            "sfx_category": "ROUTE_PROGRESS", "sfx_intensity": "SUBTLE"} for i in range(10)]
        result = select_rhythm_sound_events(plan)
        variants = [e["sfx_variant"] for e in result["events"]]
        self.assertEqual(len(set(variants[:3])), 3)
        self.assertTrue(all(a != b for a, b in zip(variants, variants[1:])))
        self.assertEqual(result, select_rhythm_sound_events(plan))
        history = result["history"][:1]
        old = copy.deepcopy(history)
        scene["sound_events"] = [scene["sound_events"][1]]
        next_result = select_rhythm_sound_events(plan, history)
        self.assertEqual(history, old)
        self.assertNotEqual(next_result["events"][0]["sfx_variant"], history[0]["sfx_variant"])

    def test_explicit_repeat_is_honored_and_disclosed(self):
        plan = fixture()
        scene = plan["scenes"][0]
        scene["visual_events"] = []
        scene["sound_events"] = [{"id": f"A{i}", "time": .1+i*.2, "sfx_category": "RADAR",
            "sfx_variant": "RADAR_01", "sfx_intensity": "LOW"} for i in range(2)]
        result = select_rhythm_sound_events(plan)
        self.assertEqual(result["events"][1]["sfx_variant"], "RADAR_01")
        self.assertTrue(any(w["code"] == "RHYTHM_SFX_CONSECUTIVE_EXPLICIT_REPEAT" for w in result["warnings"]))

    def test_invalid_binding_category_variant_intensity_and_pin_fail(self):
        for update in [{"sfx_category": "UNKNOWN"}, {"sfx_variant": "WARNING_01"},
                       {"sfx_intensity": "LOUD"}, {"visual_event_id": "MISSING"}]:
            with self.subTest(update=update):
                plan = fixture()
                plan["scenes"][0]["sound_events"][0].update(update)
                with self.assertRaises(ValueError):
                    select_rhythm_sound_events(plan)
        plan = fixture()
        plan["rhythm_policy"]["sfx_library_content_sha256"] = "0"*64
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "PINNED_LIBRARY"):
                render_rhythm_sound_events(plan, Path(temporary))

    def test_actual_pcm_onset_intensity_and_primary_attack_under_ten_ms(self):
        maxima = []
        with tempfile.TemporaryDirectory() as temporary:
            for intensity in INTENSITIES:
                plan = fixture()
                plan["scenes"][0]["visual_events"] = []
                plan["scenes"][0]["sound_events"] = [{"id": "A", "time": .51, "kind": "tick",
                    "sfx_category": "CITY_REVEAL", "sfx_variant": "CITY_REVEAL_01", "sfx_intensity": intensity}]
                signal, report = render_rhythm_sound_events(plan, Path(temporary))
                at = report["events"][0]["onset_sample"]
                self.assertEqual(at, 16*1600)
                self.assertFalse(np.any(signal[:at]))
                self.assertTrue(np.any(signal[at:at+480]))
                self.assertLessEqual(report["max_primary_attack_seconds"], .010)
                maxima.append(float(np.max(np.abs(signal))))
        np.testing.assert_allclose(maxima, [INTENSITY_GAIN[level] for level in INTENSITIES], rtol=1e-6)

    def test_sfx_off_all_layers_silent_no_library_generation(self):
        plan = fixture()
        plan["options"]["sfx"] = False
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"absent"
            signal, report = render_rhythm_sound_events(plan, path)
            self.assertFalse(np.any(signal))
            self.assertFalse(path.exists())
            self.assertEqual(report["actual_layer_count"], 0)
            self.assertEqual(report["sources"], [])

    def test_micro_pause_energy_and_sidechain_recover_smoothly_without_stacked_pumping(self):
        plan = fixture()
        energy, report = rhythm_bgm_envelope(plan, 4.)
        dry = copy.deepcopy(plan)
        dry["rhythm_policy"]["micro_pauses"] = []
        original, _ = rhythm_bgm_envelope(dry, 4.)
        at = round(2.15*SR)
        self.assertAlmostEqual(energy[at]/original[at], .56)
        self.assertAlmostEqual(report["micro_pauses"][0]["actual_duration"], .166667, places=4)
        selected = select_rhythm_sound_events(plan)["events"]
        gain, sidechain = bgm_event_sidechain(plan, selected, 4.)
        self.assertEqual(sidechain["event_count"], 2)
        self.assertGreaterEqual(float(np.min(gain)), .72)
        self.assertLess(sidechain["maximum_sample_gain_delta"], .001)
        self.assertEqual(gain[round(3.*SR)], 1.)
        self.assertTrue(np.all(np.isfinite(energy)))
        plan["rhythm_policy"]["bgm_sidechain"] = False
        disabled, disabled_report = bgm_event_sidechain(plan, selected, 4.)
        self.assertTrue(np.all(disabled == 1.))
        self.assertEqual(disabled_report["event_count"], 0)

    def test_actual_mix_stems_sum_to_raw_and_report_only_measured_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            def private_library(plan, _):
                return render_rhythm_sound_events(plan, path/"library")
            with patch("engine.audio.render_rhythm_sound_events", side_effect=private_library):
                report = create_audio(fixture(), path/"mix")
            total = None
            for stem in report["stems"].values():
                stem_path = Path(stem["file"])
                self.assertEqual(hashlib.sha256(stem_path.read_bytes()).hexdigest(), stem["sha256"])
                rate, pcm = wavfile.read(stem_path)
                self.assertEqual(rate, SR)
                total = pcm.astype(np.float64) if total is None else total+pcm
            _, raw = wavfile.read(path/"mix/mix_raw.wav")
            np.testing.assert_allclose(total, raw, rtol=1e-6, atol=2e-8)
            self.assertEqual(report["rhythm_policy_version"], "v1")
            self.assertEqual(report["normalization"]["target_lufs"], -18.)
            self.assertLessEqual(report["peak_dbfs"], -2.45)
            self.assertFalse(report["direct_listening"])
            self.assertEqual(report["sfx_library"]["actual_layer_count"], 6)
            self.assertEqual(report["sfx_library"]["max_sync_error_seconds"], 0.)
            self.assertLessEqual(report["sfx_library"]["max_primary_attack_seconds"], .01)
            history = json.loads((path/"mix/sfx_history.json").read_text())
            self.assertEqual(history, report["sfx_library"]["history"])
            with self.assertRaises(FileExistsError):
                create_audio(fixture(), path/"mix")

    def test_optional_tts_stays_available_and_voice_priority_is_preserved(self):
        plan = fixture()
        plan["options"]["tts"] = True
        plan["scenes"][0]["narration"] = "A short fixture voice."
        plan["scenes"][0]["narration_event_ids"] = ["E01", "E02", "E03"]
        voice = FixtureVoice()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            def private_library(plan, _):
                return render_rhythm_sound_events(plan, path/"library")
            with patch("engine.audio.render_rhythm_sound_events", side_effect=private_library):
                report = create_audio(plan, path/"mix", voice)
            self.assertEqual(len(voice.calls), 1)
            self.assertFalse(report["speech_priority"]["tts_speed_changed"])
            self.assertGreater(report["speech_priority"]["speech_reserved_fraction"], .25)
            self.assertGreater(report["stems"]["narration"]["peak_dbfs"], -30)
            self.assertEqual(len(report["narration_cues"]), 1)
            self.assertTrue(report["narration_alignment"]["passed"])

    def test_policy_absence_preserves_dispatch(self):
        plan = fixture()
        self.assertTrue(rhythm_audio_enabled(plan))
        plan.pop("rhythm_policy")
        self.assertFalse(rhythm_audio_enabled(plan))


if __name__ == "__main__":
    unittest.main()
