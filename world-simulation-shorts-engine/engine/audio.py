"""Optional offline narration, event-synchronous original sound, music and subtitles.

Narration cues are actual synthesized/file timings, never claimed word alignment.
The preserved synthesis module is imported without calling its fixed-film build().
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import importlib.util
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
import numpy as np
from PIL import ImageFont
from scipy.io import wavfile
from scipy.signal import resample_poly

from .assets import APP_ROOT, V3_ROOT, resolve_user_asset
from .narration import validate_narration_bindings, attach_narration_timing
from .sfx_library import production_audio_enabled, render_sound_events
from .rhythm_sound import (rhythm_audio_enabled, render_rhythm_sound_events,
                           rhythm_bgm_envelope, bgm_event_sidechain)

SR = 48000


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("AUDIO_PIPELINE_FAILED: " + result.stderr[-3000:])


def _probe(path: Path) -> dict:
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
                                               "-show_format", "-of", "json", str(path)]))


def _stereo(path: Path) -> np.ndarray:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                             "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                            capture_output=True)
    if result.returncode:
        raise RuntimeError("NARRATION_DECODE_FAILED: " + result.stderr.decode(errors="replace"))
    return np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2).copy()


class TTSProvider(ABC):
    name: str

    @abstractmethod
    def synthesize(self, text: str, destination: Path, *, language: str = "en", speed: int = 155) -> dict:
        """Return real measured duration and voice metadata; do not infer alignment."""


class ESpeakProvider(TTSProvider):
    """A free offline fallback, distinctly less natural than a supplied studio voice."""
    name = "ESPEAK_OFFLINE"

    def __init__(self, executable: str | None = None):
        local = APP_ROOT / "tools/runtime/usr/bin/espeak-ng"
        self.executable = executable or shutil.which("espeak-ng") or shutil.which("espeak")
        if not self.executable and local.is_file():
            self.executable = str(local)
        if not self.executable:
            raise RuntimeError("TTS_PROVIDER_UNAVAILABLE: install espeak-ng, disable TTS, or supply narration_file")

    def synthesize(self, text: str, destination: Path, *, language: str = "en", speed: int = 155) -> dict:
        if destination.exists():
            raise FileExistsError(destination)
        command = [self.executable, "-v", language, "-s", str(speed), "-w", str(destination), "--stdin"]
        environment = None
        local = APP_ROOT / "tools/runtime"
        if str(self.executable).startswith(str(local)):
            import os
            environment = dict(os.environ)
            libraries = [local / "usr/lib/x86_64-linux-gnu", local / "lib/x86_64-linux-gnu"]
            environment["LD_LIBRARY_PATH"] = ":".join(map(str, libraries))
            data = local / "usr/lib/x86_64-linux-gnu/espeak-ng-data"
            if not data.is_dir():
                data = local / "usr/lib/espeak-ng-data"
            environment["ESPEAK_DATA_PATH"] = str(data)
            environment["XDG_CONFIG_HOME"] = str(local / "config")
            command.insert(1, "--path=" + str(data))
        result = subprocess.run(command, input=text, text=True, capture_output=True, env=environment)
        if result.returncode or not destination.is_file():
            raise RuntimeError("TTS_SYNTHESIS_FAILED: " + result.stderr[-1500:])
        meta = _probe(destination)
        return {"provider": self.name, "language": language,
                "duration": float(meta["format"]["duration"]), "file": str(destination),
                "word_alignment": False,
                "quality_notice": "Offline fallback voice; use supplied narration for natural documentary narration."}


def script_timing_validation(plan: dict) -> dict:
    """Preflight estimate only. Actual synthesis must still fit before assembly."""
    warnings = []
    for scene in plan.get("scenes", []):
        text = scene.get("narration", "").strip()
        if not text:
            continue
        korean = sum("\uac00" <= char <= "\ud7a3" for char in text)
        estimate = korean / 5.0 if korean > len(text) * .25 else len(text.split()) / 2.6
        if estimate > scene["duration"]:
            warnings.append({"scene_id": scene["scene_id"], "estimated_seconds": round(estimate, 2),
                             "duration": scene["duration"],
                             "suggestions": ["shorten narration", "lengthen scene", "split scene"]})
    return {"passed": not warnings, "warnings": warnings,
            "method": "Language-dependent reading-rate estimate; not measured TTS timing"}


def _narration(plan: dict, audio_dir: Path, provider: TTSProvider | None = None) -> tuple[np.ndarray, list[dict], list[dict]]:
    options = plan.get("options", {})
    duration = float(plan["duration"])
    result = np.zeros((round(duration * SR), 2), np.float64)
    cues: list[dict] = []
    metadata: list[dict] = []
    request = plan.get("request", {})
    supplied = options.get("narration_file") or request.get("narration_audio")
    if supplied:
        source = resolve_user_asset(supplied)
        signal = _stereo(source)
        if len(signal) > len(result) + round(.10 * SR):
            raise RuntimeError("NARRATION_DURATION_EXCEEDS_PROJECT")
        result[:min(len(signal), len(result))] = signal[:len(result)]
        supplied_cues = options.get("narration_timing") or request.get("narration_cues", [])
        if options.get("subtitles") and not supplied_cues:
            raise RuntimeError("NARRATION_TIMING_REQUIRED: external narration subtitles need explicit timed cues")
        for cue in supplied_cues:
            start, end = float(cue["start"]), float(cue["end"])
            if start < 0 or end <= start or end > duration + .05:
                raise RuntimeError("NARRATION_TIMING_INVALID")
            cues.append(dict(cue))
        metadata.append({"provider": "USER_FILE", "source": str(source),
                         "duration": len(signal) / SR, "word_alignment": False,
                         "timing_source": "user-provided" if cues else "unavailable"})
        return result, cues, metadata
    if not options.get("tts", False):
        return result, cues, metadata
    provider = provider or ESpeakProvider()
    explicit_language = options.get("tts_language")
    for scene in plan["scenes"]:
        text = scene.get("narration", "").strip()
        if not text:
            continue
        language = explicit_language or ("ko" if re.search(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]", text)
                                        else "en")
        destination = audio_dir / (scene["scene_id"] + "_narration.wav")
        info = provider.synthesize(text, destination, language=language,
                                   speed=int(options.get("tts_speed", 155)))
        signal = _stereo(destination)
        actual_seconds = len(signal) / SR
        if actual_seconds > float(scene["duration"]) - .08:
            raise RuntimeError(f"NARRATION_EXCEEDS_SCENE: {scene['scene_id']} needs {actual_seconds:.2f}s, "
                               f"scene has {scene['duration']}s; shorten script or lengthen scene")
        start = float(scene["start_time"]) + .04
        offset = round(start * SR)
        n = min(len(signal), len(result) - offset)
        result[offset:offset+n] += signal[:n] * .78
        cues.append({"start": start, "end": start + actual_seconds, "text": text,
                     "scene_id": scene["scene_id"], "timing_source": "measured_scene_synthesis",
                     "declared_narration_event_ids": list(scene.get("narration_event_ids", [])),
                     "declared_claim_ids": list(scene.get("claim_ids", [])), "word_alignment": False})
        metadata.append({**info, "scene_id": scene["scene_id"], "placed_start": start})
    return result, cues, metadata


def _synth_class():
    path = V3_ROOT / "tools/sound.py"
    spec = importlib.util.spec_from_file_location("preserved_world_sound_primitives", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SoundEngine


def _music(duration: float, plan: dict) -> np.ndarray:
    music = np.zeros((round(duration * SR), 2), np.float64)
    t = np.arange(len(music)) / SR
    points = [(0., .9)]
    for scene in plan["scenes"]:
        energy = float(scene.get("music_energy", .5))
        points += [(float(scene["start_time"]) + .25, max(.18, min(1.3, energy)))]
    points.append((duration, .08))
    points.sort()
    energy = np.interp(t, [p[0] for p in points], [p[1] for p in points])
    envelope = (1-np.exp(-t*7))*np.clip((duration-t)/.25, 0, 1)*energy
    for k, (frequency, amplitude) in enumerate([(36.708, .027), (55, .012), (73.416, .018),
                                                (110, .009), (146.832, .006), (174.614, .0038),
                                                (220, .0025), (293.665, .0012)]):
        signal = amplitude*np.sin(2*np.pi*frequency*t+.16*np.sin(t*(.13+k*.018)))*envelope
        music[:, 0] += signal*.73
        music[:, 1] += np.roll(signal, 11+k*7)*.72
    return music


def _ducking(cues: list[dict], duration: float) -> np.ndarray:
    # Piecewise ramps give a 180 ms attack / 450 ms recovery and are deterministic.
    envelope = np.ones(round(duration*SR), np.float64)
    for cue in cues:
        start, end = float(cue["start"]), float(cue["end"])
        a, b = max(0, round((start-.18)*SR)), min(len(envelope), round((end+.45)*SR))
        times = np.arange(a, b) / SR
        gain = np.interp(times, [start-.18, start, end, end+.45], [1., .28, .28, 1.])
        envelope[a:b] = np.minimum(envelope[a:b], gain)
    return envelope


def _production_energy_points(plan: dict) -> list[tuple[float, float]]:
    """Event/pace energy, including a short breath after each narrative peak."""
    duration = float(plan["duration"])
    fast = str(plan.get("request", {}).get("pace", plan.get("options", {}).get("pace", "FAST"))).replace("PACE_", "") == "FAST"
    points = {0.: .82, min(duration, .30 if fast else .55): .98,
              min(duration, 1.75 if fast else 2.3): .53, duration: .025}
    for scene in plan.get("scenes", []):
        start = float(scene["start_time"])
        base = max(.20, min(.80, float(scene.get("music_energy", .5))*.82))
        if start > 0:
            points[min(duration, start+.18)] = base
        for event in scene.get("visual_events", []):
            if not isinstance(event, dict):
                continue
            at = start+float(event.get("time", 0.))
            kind, role = event.get("kind"), event.get("role")
            if kind == "new_variable" or role == "variable":
                points[max(0., at-.20)] = base
                points[min(duration, at+.14)] = .81
            if role == "peak" or kind == "peak_reveal":
                points[max(0., at-.34)] = max(base, .62)
                points[min(duration, at+.08)] = .98
                points[min(duration, at+.56)] = .40
                points[min(duration, at+.94)] = .65
            if role == "payoff" or kind == "final_reveal":
                points[max(0., at-.34)] = .76
                points[min(duration, at+.08)] = 1.12
                points[min(duration, at+.48)] = .82
    # Ending always resolves, even if a late event wrote the endpoint above.
    points[duration] = .025
    return sorted(points.items())


def _production_music(duration: float, plan: dict) -> tuple[np.ndarray, dict]:
    """Original low-mid score, rhythmic swells rather than full-film speed-up."""
    music = np.zeros((round(duration*SR), 2), np.float64)
    t = np.arange(len(music))/SR
    points = _production_energy_points(plan)
    energy = np.interp(t, [p[0] for p in points], [p[1] for p in points])
    envelope = (1-np.exp(-t*10))*np.clip((duration-t)/.16, 0, 1)*energy
    pace = str(plan.get("request", {}).get("pace", plan.get("options", {}).get("pace", "FAST"))).replace("PACE_", "")
    # A very quiet pulse under the sustained score accelerates energy without
    # changing narration timing or using an intrusive midrange melody.
    pulse_hz = {"FAST_PLUS": 1.38, "FAST": 1.15, "NORMAL": .82, "CINEMATIC": .56}.get(pace, .82)
    rhythm = .88+.12*(.5+.5*np.sin(2*np.pi*pulse_hz*t))**3
    for k, (frequency, amplitude) in enumerate([(36.708, .022), (55., .010), (73.416, .015),
                                                (110., .0065), (146.832, .0038), (174.614, .0018),
                                                (220., .0012), (293.665, .0005)]):
        signal = amplitude*np.sin(2*np.pi*frequency*t+.12*np.sin(t*(.13+k*.018)))*envelope*rhythm
        music[:, 0] += signal*.73
        delayed = np.zeros_like(signal)
        delay = 11+k*7
        delayed[delay:] = signal[:-delay]
        music[:, 1] += delayed*.72
    return music, {"pace": pace, "pulse_hz": pulse_hz, "energy_points": [list(p) for p in points],
                   "source": "Original engine/audio.py procedural composition", "license": "CC0-1.0",
                   "speech_band_notice": "No midrange lead; the mix still requires final listening with the chosen voice"}


def _production_ducking(cues: list[dict], narration: np.ndarray, duration: float) -> tuple[np.ndarray, np.ndarray, dict]:
    """Speech has priority over effects/music; external un-timed voice is detected."""
    from scipy.ndimage import uniform_filter1d, maximum_filter1d
    # Reuse measured scene-cue ramps. Actual signal RMS adds coverage for a
    # supplied narration file without cues, including the subtitles-OFF case.
    cue_duck = _ducking(cues, duration)
    # The running-sum filter can leave tiny negative roundoff after silence.
    activity = np.sqrt(np.maximum(0., uniform_filter1d(np.mean(narration**2, axis=1), size=round(.025*SR))))
    active = (activity > 10**(-46/20)).astype(np.float64)
    # Conservative nearby-speech reservation and smoothing avoid abrupt gain
    # changes or a peak effect masking the beginning of the next sentence.
    reserved = maximum_filter1d(active, size=round(.30*SR)+1, mode="constant")
    smoothed = uniform_filter1d(reserved, size=round(.14*SR), mode="nearest")
    speech = np.maximum(np.clip((1-cue_duck)/.72, 0, 1), smoothed)
    music_duck = 1-.84*speech
    sound_duck = 1-.75*speech
    return music_duck, sound_duck, {"bgm_minimum_gain": .16, "sfx_minimum_gain": .25,
            "cue_attack_seconds": .18, "cue_release_seconds": .45,
            "signal_rms_window_seconds": .025, "signal_threshold_dbfs": -46,
            "signal_reservation_seconds": .30, "signal_smoothing_seconds": .14,
            "speech_reserved_fraction": float(np.mean(speech > .5)), "tts_speed_changed": False,
            "scope": "Measured cue / amplitude-based priority envelopes; not word ASR or guaranteed perceptual intelligibility"}


def create_audio(plan: dict, directory: Path, provider: TTSProvider | None = None) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    binding_report = validate_narration_bindings(plan)
    if not binding_report["passed"]:
        raise RuntimeError("NARRATION_BINDING_INVALID: " + json.dumps(binding_report["errors"], ensure_ascii=False))
    duration = float(plan["duration"])
    narration, cues, narration_meta = _narration(plan, directory, provider)
    alignment = attach_narration_timing(plan, binding_report, cues, narration_meta)
    if not alignment["passed"]:
        raise RuntimeError("NARRATION_TIMING_BINDING_INVALID: " + json.dumps(alignment["errors"], ensure_ascii=False))
    alignment_path = directory / "narration_alignment.json"
    with alignment_path.open("x", encoding="utf-8") as stream:
        json.dump(alignment, stream, ensure_ascii=False, indent=2)
    rhythm = rhythm_audio_enabled(plan)
    production = production_audio_enabled(plan) or rhythm
    production_sound = production_music = production_duck = None
    rhythm_energy = rhythm_sidechain = None
    if production:
        if rhythm:
            effects, production_sound = render_rhythm_sound_events(plan, APP_ROOT / "assets/audio/production_sfx_v2")
        else:
            effects, production_sound = render_sound_events(plan, APP_ROOT / "assets/audio/production_sfx_v1")
        events = production_sound["events"]
        music, production_music = _production_music(duration, plan)
        if rhythm:
            energy, rhythm_energy = rhythm_bgm_envelope(plan, duration)
            times = np.arange(len(music))/SR
            old_points = _production_energy_points(plan)
            old_energy = np.interp(times, [p[0] for p in old_points], [p[1] for p in old_points])
            music *= (energy/np.maximum(old_energy, .001))[:, None]
            sidechain, rhythm_sidechain = bgm_event_sidechain(plan, events, duration)
            music *= sidechain[:, None]
            production_music.update({"rhythm_energy": rhythm_energy, "event_sidechain": rhythm_sidechain})
        if not plan.get("options", {}).get("bgm", True):
            music[:] = 0
        duck, sound_gain, production_duck = _production_ducking(cues, narration, duration)
        for name, record in [("sfx_history.json", production_sound["history"]),
                             ("sfx_cues.json", production_sound), ("sfx_sources.json", production_sound["sources"])]:
            with (directory / name).open("x", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2)
    else:
        synthesis = _synth_class()(duration)
        events = []
        for scene in plan["scenes"]:
            for event in scene.get("sound_events", []) if plan.get("options", {}).get("sfx", True) else []:
                if isinstance(event, str):
                    event = {"kind": event, "time": 0.}
                time = float(scene["start_time"]) + float(event.get("time", event.get("timestamp", 0)))
                if time < 0 or time >= duration:
                    raise RuntimeError(f"SOUND_EVENT_OUTSIDE_PROJECT: {event}")
                kind = event.get("kind", event.get("type", "soft_pulse")).lower()
                level = float(event["gain"]) if "gain" in event else (10**(float(event["gain_db"])/20)
                                                                      if "gain_db" in event else .12)
                if "whoosh" in kind or "riser" in kind or "sweep" in kind:
                    synthesis.whoosh(time, min(float(event.get("duration", 1.2)), duration-time), level)
                elif "pass" in kind or "engine" in kind:
                    length = min(float(event.get("duration", 1.2)), duration-time)
                    offset = round(time*SR)
                    end = min(len(synthesis.audio), offset+round(length*SR))
                    before = synthesis.audio[offset:end].copy()
                    synthesis.passby(time, length)
                    synthesis.audio[offset:end] = before+(synthesis.audio[offset:end]-before)*(level/.17)
                elif "hit" in kind or "impact" in kind:
                    synthesis.hit(time, level, deep=("deep" in kind or "final" in kind))
                else:
                    synthesis.pulse(time, level*.4)
                events.append({**event, "absolute_time": time, "linear_gain": level, "scene_id": scene["scene_id"]})
        effects = synthesis.audio
        music = _music(duration, plan) if plan.get("options", {}).get("bgm", True) else np.zeros_like(narration)
        duck = _ducking(cues, duration)
        sound_gain = np.sqrt(duck)  # Preserved legacy mix law.
    mix = effects*sound_gain[:, None] + music*duck[:, None] + narration
    fade = np.clip((duration-np.arange(len(mix))/SR)/.12, 0, 1)
    mix *= fade[:, None]
    peak = float(np.max(np.abs(mix))) if len(mix) else 0.
    limiter = min(1., .72/max(peak, 1e-12))
    mix *= limiter
    rhythm_stems = None
    if rhythm:
        # These share the actual mix's ducking, fade and safety gain. They are
        # explicitly before integrated mastering, whose filter is not linear.
        rhythm_stems = {}
        for name, stem in [("sfx", effects*sound_gain[:, None]),
                           ("bgm", music*duck[:, None]), ("narration", narration)]:
            stem = (stem*fade[:, None]*limiter).astype(np.float32)
            path = directory/(name+"_stem.wav")
            with path.open("xb") as stream:
                wavfile.write(stream, SR, stem)
            rhythm_stems[name] = {"file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "pcm_sha256": hashlib.sha256(stem.tobytes()).hexdigest(), "duration": len(stem)/SR,
                "sample_rate": SR, "channels": 2,
                "peak_dbfs": 20*np.log10(max(float(np.max(np.abs(stem))), 1e-12)),
                "rms_dbfs": 20*np.log10(max(float(np.sqrt(np.mean(stem.astype(np.float64)**2))), 1e-12)),
                "stage": "Actual mix contribution after narration duck / rhythm envelope / event sidechain / shared fade and limiter, before integrated loudness mastering",
                "shared_limiter_gain": limiter, "shared_end_fade_seconds": .12}
    destination = directory / "mix.wav"
    raw = directory / "mix_raw.wav"
    if destination.exists() or raw.exists():
        raise FileExistsError(destination)
    wavfile.write(raw, SR, mix.astype(np.float32))
    normalization = {"target_lufs": -18., "target_true_peak_dbfs": -2.5, "measured": False}
    if float(np.max(np.abs(mix))) > 1e-9:
        measure = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(raw), "-af",
                                  "loudnorm=I=-18:TP=-2.5:LRA=8:print_format=json", "-f", "null", "-"],
                                 capture_output=True, text=True)
        matches = re.findall(r'\{\s*"input_i"[\s\S]*?\}', measure.stderr)
        if measure.returncode or not matches:
            raise RuntimeError("AUDIO_LOUDNESS_ANALYSIS_FAILED")
        measured = json.loads(matches[-1])
        filt = ("loudnorm=I=-18:TP=-2.5:LRA=8:linear=true:"
                f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
                f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
                f"offset={measured['target_offset']}")
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(raw), "-af", filt,
              "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s24le", "-t", str(duration), str(destination)])
        normalization.update({"measured": True, "first_pass": measured})
    else:
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(raw),
              "-c:a", "pcm_s24le", "-ar", str(SR), str(destination)])
        normalization["intentional_silence"] = True
    final_signal = _stereo(destination)
    report = {"file": str(destination), "sample_rate": SR, "channels": 2, "duration": len(mix)/SR,
              "peak_dbfs": 20*np.log10(max(float(np.max(np.abs(final_signal))), 1e-12)),
              "raw_peak_dbfs": 20*np.log10(max(float(np.max(np.abs(mix))), 1e-12)),
              "normalization": normalization,
              "bgm": bool(plan.get("options", {}).get("bgm", True)), "narration": narration_meta,
              "narration_cues": cues, "sound_events": events, "ducking_attack_seconds": .18,
              "narration_alignment": alignment, "narration_alignment_file": str(alignment_path),
              "ducking_release_seconds": .45, "direct_listening": False,
              "license": "Procedural music/effects CC0-1.0; no reference audio sampled."}
    if production:
        report.update({"production_defaults": "v1", "sfx": bool(plan.get("options", {}).get("sfx", True)),
                       "sfx_library": production_sound, "music_energy": production_music,
                       "speech_priority": production_duck,
                       "sfx_history_file": str(directory / "sfx_history.json"),
                       "sfx_sources_file": str(directory / "sfx_sources.json")})
    if rhythm:
        report.update({"rhythm_policy_version": "v1", "rhythm_energy": rhythm_energy,
                       "bgm_event_sidechain": rhythm_sidechain, "stems": rhythm_stems,
                       "sfx_onset_policy": production_sound["onset_policy"],
                       "sfx_library_content_sha256": production_sound["library_content_sha256"],
                       "stem_mastering_notice": "Stem samples sum to mix_raw within float32 rounding; final mix applies measured integrated loudness normalization. SFX-only comparison can reuse identical muted video without any visual render."})
    with (directory / "audio_report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return report


def _ass_time(seconds: float) -> str:
    centiseconds = round(seconds*100)
    return f"{centiseconds//360000}:{centiseconds//6000%60:02}:{centiseconds//100%60:02}.{centiseconds%100:02}"


SUBTITLE_FONT_SIZE = 44
SUBTITLE_SPACING = .4
SUBTITLE_OUTLINE = 2
SUBTITLE_LAYOUT_SIZE = (1080, 1920)
SUBTITLE_SAFE_BOUNDS = {"left": 125., "top": 240., "right": 920., "bottom": 1600.}


def _subtitle_font():
    path = APP_ROOT / "web/fonts/NotoSansCJKkr-Regular.otf"
    if not path.is_file():
        raise RuntimeError("SUBTITLE_FONT_MISSING: bundled licensed Korean font is required")
    return ImageFont.truetype(str(path), SUBTITLE_FONT_SIZE), path


def _subtitle_line_width(text: str, font) -> float:
    left, _, right, _ = font.getbbox(text)
    return (max(float(font.getlength(text)), float(right-left))
            + max(0, len(text)-1)*SUBTITLE_SPACING + 2*SUBTITLE_OUTLINE)


def _wrap_subtitle_text(text: str, font, maximum_width: float) -> list[str]:
    """Use the exact bundled font, retaining words and splitting only long words."""
    wrapped = []
    for paragraph in text.splitlines():
        current = ""
        for word in paragraph.split():
            candidate = (current+" "+word).strip()
            if _subtitle_line_width(candidate, font) <= maximum_width:
                current = candidate
                continue
            if current:
                wrapped.append(current)
                current = ""
            clusters = []
            for character in word:
                if clusters and (unicodedata.combining(character) or character == "\u200d"
                                 or "\ufe00" <= character <= "\ufe0f" or clusters[-1].endswith("\u200d")):
                    clusters[-1] += character
                else:
                    clusters.append(character)
            for cluster in clusters:
                if _subtitle_line_width(cluster, font) > maximum_width:
                    raise RuntimeError("SUBTITLE_GLYPH_EXCEEDS_SAFE_WIDTH")
                if current and _subtitle_line_width(current+cluster, font) > maximum_width:
                    wrapped.append(current)
                    current = ""
                current += cluster
        if current:
            wrapped.append(current)
    return wrapped


def validate_subtitle_layout(subtitles: dict | None, duration: float | None = None) -> dict:
    """Verify metric-derived ASS geometry; this is not pixel-level glyph detection."""
    if not subtitles or not subtitles.get("enabled"):
        return {"passed": True, "enabled": False, "errors": [], "caption_count": 0}
    errors = []
    captions = subtitles.get("captions")
    if not isinstance(captions, list):
        return {"passed": False, "enabled": True, "errors": [{"code": "SUBTITLE_LAYOUT_METADATA_MISSING"}],
                "caption_count": 0}
    font, path = _subtitle_font()
    if subtitles.get("layout_resolution") != list(SUBTITLE_LAYOUT_SIZE):
        errors.append({"code": "SUBTITLE_LAYOUT_RESOLUTION_INVALID"})
    metadata = subtitles.get("font", {})
    if (metadata.get("size_px") != SUBTITLE_FONT_SIZE or metadata.get("spacing_px") != SUBTITLE_SPACING
            or metadata.get("outline_px") != SUBTITLE_OUTLINE
            or metadata.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest()):
        errors.append({"code": "SUBTITLE_FONT_METRICS_MISMATCH"})
    maximum = SUBTITLE_SAFE_BOUNDS["right"]-SUBTITLE_SAFE_BOUNDS["left"]
    for caption in captions:
        cid = caption.get("id")
        start, end = caption.get("start"), caption.get("end")
        if (not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not np.isfinite(start) or not np.isfinite(end) or start < 0 or end <= start
                or (duration is not None and end > duration+.005)):
            errors.append({"code": "SUBTITLE_TIMESTAMP_INVALID", "caption_id": cid})
        text_lines = caption.get("lines", [])
        if not text_lines or len(text_lines) > 2:
            errors.append({"code": "SUBTITLE_LINE_COUNT_INVALID", "caption_id": cid})
        if any(_subtitle_line_width(str(line), font) > maximum+.001 for line in text_lines):
            errors.append({"code": "SUBTITLE_EXCEEDS_SAFE_WIDTH", "caption_id": cid})
        boxes = caption.get("line_boxes", [])
        if len(boxes) != len(text_lines):
            errors.append({"code": "SUBTITLE_LINE_BOXES_MISSING", "caption_id": cid})
        for box in [caption.get("box", {}), *boxes]:
            values = [box.get(key) for key in ["x", "y", "width", "height"]]
            if any(not isinstance(value, (int, float)) or not np.isfinite(value) for value in values):
                errors.append({"code": "SUBTITLE_BOX_INVALID", "caption_id": cid})
                continue
            x, y, width, height = values
            if (width <= 0 or height <= 0 or x < SUBTITLE_SAFE_BOUNDS["left"]-.001
                    or y < SUBTITLE_SAFE_BOUNDS["top"]-.001
                    or x+width > SUBTITLE_SAFE_BOUNDS["right"]+.001
                    or y+height > SUBTITLE_SAFE_BOUNDS["bottom"]+.001):
                errors.append({"code": "SUBTITLE_OUTSIDE_SAFE_AREA", "caption_id": cid, "box": box})
    return {"passed": not errors, "enabled": True, "errors": errors, "caption_count": len(captions),
            "scope": "Exact bundled-font metrics including spacing/outline; conservative ASS layout bounds, not encoded-pixel glyph detection"}


def create_subtitles(plan: dict, directory: Path, cues: list[dict]) -> dict:
    if not plan.get("options", {}).get("subtitles", False):
        return {"enabled": False, "path": None, "warnings": []}
    # With TTS off, script cues are explicitly scene-level captions, not inferred
    # narration timing. With external audio, create_audio required real cue input.
    if not cues:
        cues = [{"start": scene["start_time"]+.10,
                 "end": scene["start_time"]+scene["duration"]-.10,
                 "text": scene.get("narration", ""), "timing_source": "scene_caption"}
                for scene in plan["scenes"] if scene.get("narration")]
    font, font_path = _subtitle_font()
    ascent, descent = font.getmetrics()
    maximum_width = SUBTITLE_SAFE_BOUNDS["right"]-SUBTITLE_SAFE_BOUNDS["left"]
    line_height = float(ascent+descent)
    center_x = (SUBTITLE_SAFE_BOUNDS["left"]+SUBTITLE_SAFE_BOUNDS["right"])/2
    anchor_bottom = 1920-335+SUBTITLE_OUTLINE
    captions = []
    lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 2", "",
             "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             "Style: Default,Noto Sans CJK KR,44,&H00F5F7FA,&H000000FF,&HCD071019,&H90071019,0,0,0,0,100,100,0.4,0,1,2,0,2,125,160,335,1", "",
             "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    warnings = []
    for cue in cues:
        text = str(cue["text"]).replace("{", "").replace("}", "").replace("\\", "/").strip()
        if not text:
            continue
        # Up to two lines at a time; longer narration is split over its measured
        # cue interval, clearly recorded as uniform caption timing, not ASR.
        wrapped = _wrap_subtitle_text(text, font, maximum_width)
        chunks = [wrapped[i:i+2] for i in range(0, len(wrapped), 2)]
        interval = (float(cue["end"])-float(cue["start"]))/max(1, len(chunks))
        if interval < .8:
            warnings.append({"code": "SUBTITLE_READING_TIME_SHORT", "scene_id": cue.get("scene_id")})
        for index, chunk in enumerate(chunks):
            start = round((float(cue["start"])+interval*index)*100)/100
            end = round((float(cue["start"])+interval*(index+1))*100)/100
            widths = [_subtitle_line_width(line, font) for line in chunk]
            height = line_height*len(chunk)+2*SUBTITLE_OUTLINE
            top = anchor_bottom-height
            line_boxes = [{"x": center_x-width/2, "y": top+line_height*i,
                           "width": width, "height": line_height+2*SUBTITLE_OUTLINE}
                          for i, width in enumerate(widths)]
            captions.append({"id": f"C{len(captions)+1:04}", "start": start, "end": end,
                             "scene_id": cue.get("scene_id"), "lines": chunk, "text": "\n".join(chunk),
                             "line_widths_px": widths, "line_boxes": line_boxes,
                             "box": {"x": center_x-max(widths)/2, "y": top,
                                     "width": max(widths), "height": height},
                             "fade_in_seconds": .09, "fade_out_seconds": .10,
                             "timing_source": cue.get("timing_source", "explicit_cue"),
                             "caption_division": "uniform within supplied/measured scene cue; not word alignment"})
            caption = r"\N".join(chunk)
            lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{{\\fad(90,100)}}{caption}")
    report = {"enabled": True, "warnings": warnings, "captions": captions,
              "layout_resolution": list(SUBTITLE_LAYOUT_SIZE),
              "font": {"family": "Noto Sans CJK KR", "path": str(font_path),
                       "sha256": hashlib.sha256(font_path.read_bytes()).hexdigest(), "size_px": SUBTITLE_FONT_SIZE,
                       "spacing_px": SUBTITLE_SPACING, "outline_px": SUBTITLE_OUTLINE,
                       "ascent_px": ascent, "descent_px": descent},
              "safe_area": {"horizontal_margins": [125, 160], "bottom_margin": 335,
                            "bounds": dict(SUBTITLE_SAFE_BOUNDS)},
              "timing_scope": "Measured scene-level narration / explicit external cues; multi-caption division is uniform, not word alignment"}
    validation = validate_subtitle_layout(report, float(plan["duration"]))
    if not validation["passed"]:
        raise RuntimeError("SUBTITLE_LAYOUT_INVALID: " + json.dumps(validation["errors"], ensure_ascii=False))
    report["layout_validation"] = validation
    path = directory / "subtitles.ass"
    with path.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines)+"\n")
    return {**report, "path": str(path)}


def finish_video(muted_input: Path, final_dir: Path, plan: dict, audio: dict, subtitles: dict) -> dict:
    final_dir.mkdir(parents=True, exist_ok=True)
    muted = final_dir / "final_muted.mp4"
    final = final_dir / "final.mp4"
    if muted.exists() or final.exists():
        raise FileExistsError("Refusing to overwrite an existing final version")
    if subtitles.get("enabled"):
        # Escape FFmpeg filter syntax independently of shell syntax; subprocess
        # receives an argument vector and never executes a shell command.
        path = str(Path(subtitles["path"]).resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        fonts = str(APP_ROOT / "web/fonts").replace("'", "\\'")
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(muted_input),
              "-vf", f"ass=filename='{path}':fontsdir='{fonts}'", "-c:v", "libx264", "-preset", "slow",
              "-crf", "15", "-threads", "4", "-pix_fmt", "yuv420p", "-color_range", "tv",
              "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
              "-movflags", "+faststart", "-an", str(muted)])
    else:
        shutil.copyfile(muted_input, muted)
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(muted),
          "-i", audio["file"], "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
          "-b:a", "320k", "-ar", str(SR), "-ac", "2", "-t", str(plan["duration"]),
          "-metadata", "comment=Earth textures: Solar System Scope (CC BY 4.0); original procedural audio CC0. See source_report.md.",
          "-movflags", "+faststart", str(final)])
    return {"final": str(final), "muted": str(muted), "subtitles": subtitles}
