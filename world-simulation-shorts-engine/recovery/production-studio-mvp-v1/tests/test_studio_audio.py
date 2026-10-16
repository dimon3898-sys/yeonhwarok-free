"""Focused original SFX contract/streaming/real FFmpeg verification; no GPU."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("studio_audio_test_module", ROOT / "studio_audio.py")
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


def plan(seconds=2, fps=30):
    return {"durationSeconds": seconds, "fps": fps, "totalFrames": int(seconds * fps),
            "resolution": [64, 96], "audioSettings": {"enabled": False, "mode": "SILENT"},
            "productionV3": {"eventChapters": [{"eventId": "ACTUAL_EVENT", "startFrame": 0,
                                                  "endFrame": int(seconds * fps)}]},
            "legacyScenePlan": {"beats": [{"id": "BEAT", "start_frame": 0, "end_frame": int(seconds * fps)}]}}


def settings(kind="CLICK", frame=6, **extra):
    return {"enabled": True, "gain": .7, "exportWav": False,
            "cues": [{"eventId": "ACTUAL_EVENT", "frame": frame, "type": kind}], **extra}


class SfxContractTests(unittest.TestCase):
    def test_all_six_roles_reuse_original_licensed_assets(self):
        report = audio.verify_assets()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["license"], "CC0-1.0")
        self.assertEqual(report["assetCount"], 18)
        self.assertEqual(len(audio.TYPES), 6)
        frozen = ROOT / "dependencies/rhythm_sound.py"
        # Studio is installed outside the strict parent repository. The old
        # synthesizer is not a GPU runtime dependency and is not shipped there.
        # Its reviewed frozen source hash remains mandatory in both layouts.
        expected_source_sha = "95f52e8c384059a1670b063d58bf38decebc63ba28bbdd685400904b5e3e3f02"
        self.assertEqual(hashlib.sha256(frozen.read_bytes()).hexdigest(), expected_source_sha)
        manifest = json.loads((ROOT / "audio/ASSET_MANIFEST.json").read_text())
        self.assertTrue(all(row["source_sha256"] == expected_source_sha for row in manifest["assets"]))
        original = ROOT.parents[1] / "engine/rhythm_sound.py"
        if original.is_file():
            self.assertEqual(frozen.read_bytes(), original.read_bytes())

    def test_structured_settings_are_canonical_and_do_not_modify_video_plan(self):
        p = plan(); before = copy.deepcopy(p)
        source = settings(); snapshot = copy.deepcopy(source)
        value = audio.normalize_sfx(source, p)
        self.assertEqual(source, snapshot)
        self.assertEqual(p, before)
        self.assertEqual(audio.normalize_sfx(value, p), value)
        self.assertEqual(value["cues"][0]["gain"], 1.)
        self.assertEqual(p["audioSettings"], {"enabled": False, "mode": "SILENT"})

    def test_missing_cues_bind_only_supplied_chapters_and_explicit_empty_remains_empty(self):
        cues = audio.normalize_sfx({}, plan())["cues"]
        self.assertEqual(cues, [{"eventId": "ACTUAL_EVENT", "frame": 0,
                                 "type": "EVENT_TRANSITION", "gain": 1.}])
        self.assertEqual(audio.normalize_sfx({"cues": []}, plan())["cues"], [])
        p = plan(); p.pop("productionV3")
        self.assertEqual(audio.normalize_sfx({}, p)["cues"], [])

    def test_invalid_or_out_of_event_cues_are_rejected(self):
        mutations = [
            {"eventId": "INVENTED"}, {"frame": 60}, {"frame": -1}, {"frame": True},
            {"frame": 1.5}, {"type": "UNLICENSED_SAMPLE"}, {"gain": float("nan")},
            {"gain": -1}, {"gain": 1.1}, {"url": "https://untrusted.invalid/sound"},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                source = settings(); source["cues"][0].update(mutation)
                with self.assertRaises(audio.AudioError):
                    audio.normalize_sfx(source, plan())
        for update in [{"enabled": "true"}, {"exportWav": 1}, {"gain": True},
                       {"gain": float("inf")}, {"gain": -.01}, {"token": "not-allowed"}]:
            with self.subTest(update=update), self.assertRaises(audio.AudioError):
                audio.normalize_sfx({**settings(), **update}, plan())

    def test_legacy_beat_binding_and_half_open_ranges(self):
        source = settings(); source["cues"][0]["eventId"] = "BEAT"
        self.assertEqual(audio.normalize_sfx(source, plan())["cues"][0]["eventId"], "BEAT")
        p = plan(); p["productionV3"]["eventChapters"][0].update(startFrame=5, endFrame=10)
        for frame in (0, 10):
            with self.assertRaises(audio.AudioError):
                audio.normalize_sfx(settings(frame=frame), p)
        self.assertEqual(audio.normalize_sfx(settings(frame=9), p)["cues"][0]["frame"], 9)

    def test_duplicate_cues_and_invalid_plan_timing_fail_closed(self):
        source = settings(); source["cues"] *= 2
        with self.assertRaises(audio.AudioError):
            audio.normalize_sfx(source, plan())
        for mutation in [{"fps": 0}, {"fps": True}, {"totalFrames": 59}, {"durationSeconds": float("nan")}]:
            with self.subTest(mutation=mutation), self.assertRaises(audio.AudioError):
                audio.normalize_sfx({}, {**plan(), **mutation})

    def test_80_to_600_seconds_use_same_contract_and_exact_sample_grid(self):
        for seconds in (80, 120, 180, 300, 600):
            p = plan(seconds)
            source = settings(frame=seconds * 30 - 1)
            value = audio.normalize_sfx(source, p)
            frames, fps, samples = audio._timing(p)
            self.assertEqual(samples, seconds * 48000)
            self.assertEqual(frames, seconds * 30)
            self.assertEqual(audio._round_fraction(value["cues"][0]["frame"] * audio.Fraction(48000, fps)),
                             value["cues"][0]["frame"] * 1600)

    def test_corrupt_or_unlicensed_asset_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            shutil.copytree(ROOT / "audio", temp / "audio")
            shutil.copytree(ROOT / "dependencies", temp / "dependencies")
            first = next((temp / "audio").glob("*.wav"))
            first.write_bytes(b"damaged")
            with patch.object(audio, "HERE", temp), self.assertRaises(audio.AudioError):
                audio.verify_assets()
            manifest = temp / "audio/ASSET_MANIFEST.json"
            value = json.loads(manifest.read_text()); value["license"] = "UNKNOWN"
            manifest.write_text(json.dumps(value))
            with patch.object(audio, "HERE", temp), self.assertRaises(audio.AudioError):
                audio.asset_manifest()

    def test_individual_asset_license_or_source_mismatch_is_rejected(self):
        original = audio.asset_manifest()
        for update in ({"license": "UNKNOWN"}, {"source_sha256": "0" * 64},
                       {"sample_rate": 44100}, {"channels": 1}):
            value = copy.deepcopy(original)
            value["assets"][0].update(update)
            encoded = json.dumps(value)
            original_read = Path.read_text
            def replaced_read(path, *args, **kwargs):
                return encoded if path.name == "ASSET_MANIFEST.json" else original_read(path, *args, **kwargs)
            with self.subTest(update=update), patch.object(Path, "read_text", replaced_read), self.assertRaises(audio.AudioError):
                audio.asset_manifest()


class SfxRenderTests(unittest.TestCase):
    def test_six_roles_are_audible_and_frame_sample_aligned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in audio.TYPES:
                with self.subTest(kind=kind):
                    output = root / (kind + ".wav")
                    report = audio.render_sfx(settings(kind), plan(), output)
                    with wave.open(str(output), "rb") as stream:
                        self.assertEqual(stream.getnframes(), 96000)
                        samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").reshape(-1, 2)
                    onset = 6 * 1600
                    self.assertFalse(np.any(samples[:onset]))
                    self.assertTrue(np.any(samples[onset:onset + 480]))
                    self.assertEqual(report["cues"][0]["onsetSample"], onset)
                    self.assertEqual(report["mixPolicy"]["clippedSamples"], 0)
                    self.assertFalse(report["referenceAudioSampled"])

    def test_gain_zero_silence_and_gain_control(self):
        peaks = []
        with tempfile.TemporaryDirectory() as directory:
            for index, gain in enumerate((0, .5, 1)):
                report = audio.render_sfx(settings(gain=gain), plan(), Path(directory) / f"{index}.wav")
                peaks.append(report["mixPolicy"]["measuredPeak"])
        self.assertEqual(peaks[0], 0.)
        self.assertAlmostEqual(peaks[1] * 2, peaks[2], places=7)

    def test_off_creates_no_audio_file_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "not-created.wav"
            report = audio.render_sfx({"enabled": False, "cues": []}, plan(), output)
            self.assertFalse(output.exists())
            self.assertIsNone(report["file"])
            self.assertEqual(report["status"], "DISABLED")

    def test_cooldown_overlap_are_reported_not_shifted_and_no_clipping(self):
        cues = [{"eventId": "ACTUAL_EVENT", "frame": 0, "type": kind} for kind in audio.TYPES]
        cues.append({"eventId": "ACTUAL_EVENT", "frame": 1, "type": "CLICK"})
        with tempfile.TemporaryDirectory() as directory:
            report = audio.render_sfx({"gain": 1, "cues": cues}, plan(), Path(directory) / "mix.wav")
        rendered = [row for row in report["cues"] if row["status"] == "RENDERED"]
        self.assertEqual(len(rendered), 3)
        self.assertTrue(all(row["onsetSample"] == 0 for row in rendered))
        self.assertGreaterEqual(len(report["mixPolicy"]["omissions"]), 1)
        self.assertLessEqual(report["mixPolicy"]["measuredPeak"], .54001)
        self.assertEqual(report["mixPolicy"]["clippedSamples"], 0)

    def test_end_of_video_truncation_fades_and_keeps_exact_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "end.wav"
            report = audio.render_sfx(settings(frame=59), plan(), output)
            with wave.open(str(output), "rb") as stream:
                samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").reshape(-1, 2)
            self.assertTrue(np.any(samples[-1600:]))
            self.assertFalse(np.any(samples[-1]))
            self.assertEqual(report["totalSamples"], 96000)

    def test_repeated_render_is_byte_exact_and_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.wav", Path(directory) / "b.wav"
            first = audio.render_sfx(settings(), plan(), a)
            second = audio.render_sfx(settings(), plan(), b)
            self.assertEqual(first["sha256"], second["sha256"])
            with self.assertRaises(audio.AudioError):
                audio.render_sfx(settings(), plan(), a)
            self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(), first["sha256"])

    def test_600_second_real_streaming_uses_fixed_block_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "600s.wav"
            report = audio.render_sfx(settings(frame=17999), plan(600), output)
            with wave.open(str(output), "rb") as stream:
                self.assertEqual(stream.getnframes(), 600 * 48000)
                self.assertEqual(stream.getnchannels(), 2)
            self.assertEqual(report["mixPolicy"]["blockCount"], 600)
            self.assertLessEqual(report["mixPolicy"]["maximumResidentMixSamples"], 48000)
            self.assertLess(report["mixPolicy"]["maximumResidentAssetSamples"], 48000)
            self.assertLessEqual(output.stat().st_size, 600 * 48000 * 4 + 44)


class SfxIntervalRevisionTests(unittest.TestCase):
    def _render_pair(self, old, new):
        p = plan(80)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = audio.render_sfx(old, p, root / "before.wav")
            after = audio.render_sfx(new, p, root / "after.wav")
            def read(path):
                with wave.open(str(path), "rb") as stream:
                    return np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").reshape(-1, 2)
            first, second = read(root / "before.wav"), read(root / "after.wav")
            actual_changed = np.any(first != second, axis=1)
        impact = audio.audio_revision_impact(old, new, p)
        permitted = np.zeros(80 * 48000, dtype=bool)
        for start, end in impact["changedSampleIntervals"]:
            permitted[start:end] = True
        self.assertFalse(np.any(actual_changed & ~permitted))
        self.assertEqual(impact["comparison"], "CONSERVATIVE_AUTHORED_CUE_SUPPORT")
        self.assertFalse(impact["actualPcmCompared"])
        self.assertTrue(impact["outsideReportedIntervalsUnchangedByConstruction"])
        return before, after, impact, actual_changed

    def test_removing_25_second_cue_preserves_unchanged_36_second_pcm(self):
        cues = [{"eventId": "ACTUAL_EVENT", "frame": frame, "type": "CLICK"} for frame in (720, 750, 1080)]
        old = {"cues": cues}
        new = {"cues": [cues[0], cues[2]]}
        before, after, impact, changed = self._render_pair(old, new)
        self.assertEqual(before["cues"][-1]["variant"], after["cues"][-1]["variant"])
        self.assertFalse(np.any(changed[:25 * 48000]))
        self.assertFalse(np.any(changed[35 * 48000:]))
        self.assertTrue(np.any(changed[25 * 48000:35 * 48000]))
        self.assertEqual(impact["changedCues"], [{"eventId": "ACTUAL_EVENT", "frame": 750, "type": "CLICK"}])

    def test_dense_cooldown_chain_has_only_bounded_reported_neighbor_impact(self):
        cues = [{"eventId": "ACTUAL_EVENT", "frame": frame, "type": "CLICK"} for frame in range(747, 1201, 3)]
        old = {"cues": cues}
        new = {"cues": [cue for cue in cues if not 750 <= cue["frame"] < 1050]}
        before, after, impact, changed = self._render_pair(old, new)
        original = {row["frame"]: row for row in before["cues"]}
        outside_admission_changes = [row for row in after["cues"] if row["frame"] >= 1050
                                     and row["status"] != original[row["frame"]]["status"]]
        # The first remaining authored cue's predecessor changed, so it is
        # honestly reported. Later decisions cannot inherit that acceptance.
        self.assertEqual([row["frame"] for row in outside_admission_changes], [1050])
        self.assertTrue(any(row["frame"] == 1050 for row in impact["changedCues"]))
        limit = 35 * 48000 + impact["maximumSourceTailSamples"]
        self.assertFalse(np.any(changed[limit:]))
        self.assertLessEqual(max(end for _, end in impact["changedSampleIntervals"]), limit)

    def test_overlap_changes_and_cross_boundary_tail_are_reported(self):
        cues = [
            {"eventId": "ACTUAL_EVENT", "frame": 1049, "type": "CLICK"},
            {"eventId": "ACTUAL_EVENT", "frame": 1049, "type": "MARKER_POP"},
            {"eventId": "ACTUAL_EVENT", "frame": 1049, "type": "MECHANICAL_TICK"},
            {"eventId": "ACTUAL_EVENT", "frame": 1050, "type": "CAMERA_WHOOSH"},
            {"eventId": "ACTUAL_EVENT", "frame": 1200, "type": "CAMERA_WHOOSH"},
        ]
        old = {"cues": cues}
        new = {"cues": [cue for cue in cues if cue["frame"] >= 1050]}
        before, after, impact, changed = self._render_pair(old, new)
        self.assertEqual(before["cues"][3]["status"], "OMITTED_OVERLAP_LIMIT")
        self.assertEqual(after["cues"][0]["status"], "RENDERED")
        self.assertTrue(any(row["frame"] == 1050 for row in impact["changedCues"]))
        self.assertTrue(np.any(changed[35 * 48000:]))
        self.assertFalse(np.any(changed[36 * 48000:]))

    def test_export_choice_has_no_pcm_impact_and_global_gain_is_honestly_global(self):
        old = {"cues": [{"eventId": "ACTUAL_EVENT", "frame": 1200, "type": "CLICK"}], "gain": .5}
        none = audio.audio_revision_impact(old, {**old, "exportWav": True}, plan(80))
        self.assertEqual(none["changedSampleIntervals"], [])
        changed = audio.audio_revision_impact(old, {**old, "gain": 1.}, plan(80))
        self.assertEqual(changed["changedCues"][0]["frame"], 1200)
        self.assertEqual(changed["changedSampleIntervals"][0][0], 40 * 48000)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "BLOCKED: FFmpeg unavailable")
class SfxRealFfmpegTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.silent = self.root / "silent.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i",
                        "testsrc2=size=64x96:rate=30", "-frames:v", "60", "-c:v", "libx264", "-threads", "2",
                        "-pix_fmt", "yuv420p", "-an", str(self.silent)], check=True, capture_output=True, timeout=60)

    def tearDown(self):
        self.temp.cleanup()

    def test_real_mux_has_exact_effective_audio_and_unchanged_video(self):
        wav = self.root / "sfx.wav"
        audio.render_sfx(settings(), plan(), wav)
        output = self.root / "with-sfx.mp4"
        report = audio.mux_sfx(self.silent, wav, output, plan())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["videoFrames"], 60)
        self.assertTrue(report["videoDecodedPixelsUnchanged"])
        self.assertTrue(report["videoFrameTimestampsUnchanged"])
        self.assertEqual(report["audioStreams"], 1)
        self.assertEqual(report["effectiveAudioSamples"], 96000)
        self.assertGreaterEqual(report["codecPaddingSamples"], 0)
        self.assertLess(report["codecPaddingSamples"], 1024)
        self.assertEqual(report["fullDecode"], "PASS")
        self.assertEqual(report["nvidiaVerification"], "NOT_ASSERTED")

    def test_off_preserves_exact_mp4_bytes_without_audio(self):
        output = self.root / "off.mp4"
        report = audio.mux_sfx(self.silent, None, output, plan())
        self.assertEqual(output.read_bytes(), self.silent.read_bytes())
        self.assertEqual(report["audioStreams"], 0)
        self.assertTrue(report["videoBytesUnchanged"])
        with self.assertRaises(audio.AudioError):
            audio.mux_sfx(self.silent, None, output, plan())

    def test_wrong_length_wav_and_wrong_video_contract_fail_before_publication(self):
        short = self.root / "short.wav"
        audio.render_sfx(settings(), plan(1), short)
        output = self.root / "invalid.mp4"
        with self.assertRaises(audio.AudioError):
            audio.mux_sfx(self.silent, short, output, plan())
        self.assertFalse(output.exists())
        with self.assertRaises(audio.AudioError):
            audio.mux_sfx(self.silent, None, output, plan(1))
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
