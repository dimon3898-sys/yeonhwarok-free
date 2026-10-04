"""Voice-language selection tests with a recording adapter, without TTS/GL services.

The adapter emits a short PCM fixture; it is not documentary voice-quality evidence.
"""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import wavfile

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from engine.audio import SR, TTSProvider, _narration


class RecordingProvider(TTSProvider):
    name = "RECORDING_TEST_ADAPTER"

    def __init__(self):
        self.calls = []

    def synthesize(self, text, destination, *, language="en", speed=155):
        self.calls.append({"text": text, "language": language, "speed": speed})
        signal = np.full(round(SR * .125), 1200, dtype=np.int16)
        wavfile.write(destination, SR, signal)
        return {"provider": self.name, "language": language, "duration": len(signal) / SR,
                "file": str(destination), "word_alignment": False}


def read_fixture_stereo(path):
    sample_rate, signal = wavfile.read(path)
    if sample_rate != SR:
        raise AssertionError("Fixture sample rate unexpectedly changed")
    mono = signal.astype(np.float32) / 32768
    return np.column_stack((mono, mono))


class NarrationLanguageTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"duration": 6., "options": {"tts": True, "tts_speed": 162},
                     "scenes": [
                         {"scene_id": "S01", "start_time": 0., "duration": 2.,
                          "narration": "런던에서 새로운 여정을 시작합니다."},
                         {"scene_id": "S02", "start_time": 2., "duration": 2.,
                          "narration": "The next destination is Paris."},
                         {"scene_id": "S03", "start_time": 4., "duration": 2.,
                          "narration": "   "},
                     ]}

    def run_narration(self, plan):
        provider = RecordingProvider()
        with tempfile.TemporaryDirectory(prefix="world-audio-language-") as temporary:
            with patch("engine.audio._stereo", side_effect=read_fixture_stereo):
                signal, cues, metadata = _narration(plan, Path(temporary), provider)
        return provider.calls, signal, cues, metadata

    def test_mixed_language_scenes_select_each_voice_and_keep_scene_timing(self):
        calls, signal, cues, metadata = self.run_narration(self.plan)
        self.assertEqual([call["language"] for call in calls], ["ko", "en"])
        self.assertEqual([call["speed"] for call in calls], [162, 162])
        self.assertEqual([item["scene_id"] for item in metadata], ["S01", "S02"])
        self.assertEqual([item["language"] for item in metadata], ["ko", "en"])
        self.assertEqual(signal.shape, (6 * SR, 2))
        for cue, scene in zip(cues, self.plan["scenes"]):
            self.assertAlmostEqual(cue["start"], scene["start_time"] + .04)
            self.assertAlmostEqual(cue["end"] - cue["start"], .125)
            self.assertEqual(cue["timing_source"], "measured_scene_synthesis")
            start, end = round(cue["start"] * SR), round(cue["end"] * SR)
            self.assertTrue(np.all(signal[start:end] > 0))
        self.assertFalse(np.any(signal[4 * SR:]))

    def test_explicit_language_overrides_inference_for_every_nonempty_scene(self):
        for language in ("en", "ko", "fr"):
            with self.subTest(language=language):
                plan = copy.deepcopy(self.plan)
                plan["options"]["tts_language"] = language
                calls, _, cues, metadata = self.run_narration(plan)
                self.assertEqual([call["language"] for call in calls], [language, language])
                self.assertEqual([item["language"] for item in metadata], [language, language])
                self.assertEqual([cue["scene_id"] for cue in cues], ["S01", "S02"])


if __name__ == "__main__":
    unittest.main()
