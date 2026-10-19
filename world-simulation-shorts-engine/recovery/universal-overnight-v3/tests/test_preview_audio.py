import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import preview_audio
import preview_contract


def plan_and_request(start=1400):
    raw = (HERE.parent / "verified-front-data-v4-recovery/VIDEO_PLAN_80S.json").read_bytes()
    plan = json.loads(raw)
    bindings = {"sourceCommit": "a" * 40, "sourceManifestSHA256": "b" * 64,
        "imageDigest": "sha256:" + "c" * 64, "originalPlanSHA256": hashlib.sha256(raw).hexdigest(),
        "completionProfileSHA256": "d" * 64, "sourceCatalogSHA256": "e" * 64}
    return plan, preview_contract.compile_preview(plan, bindings=bindings, start_frame=start)


class PreviewAudioTests(unittest.TestCase):
    def test_pcm_clip_preserves_exact_samples_including_preexisting_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "source.wav", Path(directory) / "preview.wav"
            raw = b"".join((i % 30000).to_bytes(2, "little", signed=True) * 2 for i in range(96000))
            with wave.open(str(source), "wb") as w:
                w.setparams((2, 2, 48000, 96000, "NONE", "not compressed"))
                w.writeframes(raw)
            result = preview_audio.clip_pcm_wav(source, output, start_sample=12345, end_sample=72345)
            with wave.open(str(output), "rb") as w:
                self.assertEqual(w.getnframes(), 60000)
                self.assertEqual(w.readframes(60000), raw[12345 * 4:72345 * 4])
            self.assertEqual(result["pcmSha256"], hashlib.sha256(raw[12345 * 4:72345 * 4]).hexdigest())
            self.assertFalse(result["resampled"])
            self.assertTrue(source.is_file())

    def test_actual_original_sfx_global_schedule_and_clip_match(self):
        plan, request = plan_and_request(1399)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "preview.wav"
            settings = {"enabled": True, "gain": .65}
            result = preview_audio.render_preview_sfx(settings, plan, request, output)
            self.assertEqual(result["sampleCount"], 240000)
            self.assertEqual(result["startSample"], 1399 * 1600)
            self.assertEqual(result["sourceMixerSHA256"], preview_audio.PRESERVED_AUDIO_SHA256)
            self.assertTrue(any(cue["frame"] == 1400 and cue["previewOnsetSample"] == 1600 for cue in result["cues"]))
            original = Path(directory) / "original.wav"
            preview_audio._old_audio().render_sfx(settings, plan, original)
            with wave.open(str(original), "rb") as full, wave.open(str(output), "rb") as clipped:
                full.setpos(result["startSample"])
                self.assertEqual(full.readframes(240000), clipped.readframes(240000))
            self.assertFalse(result["fullVideoRendered"])
            self.assertEqual(result["license"], "CC0-1.0")

    def test_disabled_sfx_does_not_write_or_overwrite_audio(self):
        plan, request = plan_and_request()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "preview.wav"
            result = preview_audio.render_preview_sfx({"enabled": False}, plan, request, output)
            self.assertEqual(result["status"], "DISABLED")
            self.assertFalse(output.exists())

    def test_output_collision_preserves_existing_file(self):
        plan, request = plan_and_request()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "preview.wav"
            output.write_bytes(b"existing-result")
            with self.assertRaisesRegex(preview_contract.PreviewError, "FRESH_PRIVATE"):
                preview_audio.render_preview_sfx({"enabled": True}, plan, request, output)
            self.assertEqual(output.read_bytes(), b"existing-result")


if __name__ == "__main__":
    unittest.main()
