"""Opt-in, event-bound original SFX after the unchanged silent video pipeline.

The preserved rhythm library supplies all audio. Rendering uses fixed-size
blocks and existing NumPy; SciPy is required only to reproduce the committed
original assets, never to play/mix them in the GPU image. No reference audio,
speech, music, renderer changes, or inferred historical events are involved.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import wave

import numpy as np

HERE = Path(__file__).resolve().parent
SR = 48000
BLOCK_SAMPLES = 48000
MAX_EVENTS = 10000
MAX_OVERLAP = 3
COOLDOWN_SAMPLES = 5760  # 120ms per public cue type, global event clock.
MAX_CUE_GAIN = .18       # Three peak-normalized layers sum to at most .54.
FADE_SAMPLES = 864      # 18ms smooth ending, including end-of-video truncation.
SOURCE_SHA256 = "95f52e8c384059a1670b063d58bf38decebc63ba28bbdd685400904b5e3e3f02"
TYPES = {
    "CLICK": "CITY_REVEAL",
    "MECHANICAL_TICK": "ROUTE_PROGRESS",
    "OCCUPATION_COMPLETE": "ROUTE_COMPLETE",
    "MARKER_POP": "ENTITY_SPAWN",
    "CAMERA_WHOOSH": "CAMERA_SOFT_MOVE",
    "EVENT_TRANSITION": "TRANSITION_LIGHT",
}


class AudioError(ValueError):
    """Safe code only; caller retains internal paths and detailed logs privately."""


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _timing(plan: dict) -> tuple[int, Fraction, int]:
    if not isinstance(plan, dict):
        raise AudioError("SFX_VIDEO_PLAN_INVALID")
    fps_value = plan.get("fps")
    if isinstance(fps_value, bool) or not isinstance(fps_value, (int, float)):
        raise AudioError("SFX_FPS_INVALID")
    if not math.isfinite(fps_value) or not 1 <= fps_value <= 120:
        raise AudioError("SFX_FPS_INVALID")
    fps = Fraction(str(fps_value))
    frames = plan.get("totalFrames")
    if type(frames) is not int or not 1 <= frames <= 72000:
        raise AudioError("SFX_TOTAL_FRAMES_INVALID")
    declared = plan.get("durationSeconds")
    if isinstance(declared, bool) or not isinstance(declared, (int, float)) or not math.isfinite(declared):
        raise AudioError("SFX_DURATION_INVALID")
    if abs(float(Fraction(frames, 1) / fps) - declared) > 1e-8:
        raise AudioError("SFX_DURATION_FRAME_MISMATCH")
    samples = _round_fraction(Fraction(frames * SR, 1) / fps)
    return frames, fps, samples


def _round_fraction(value: Fraction) -> int:
    # Positive rational round-half-up, independent of float representation.
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def _event_ranges(plan: dict) -> dict[str, list[tuple[int, int]]]:
    frames, _, _ = _timing(plan)
    ranges: dict[str, list[tuple[int, int]]] = {}
    entries = []
    production = plan.get("productionV3", {})
    legacy = plan.get("legacyScenePlan", {})
    if isinstance(production, dict):
        for row in production.get("eventChapters", []):
            if isinstance(row, dict):
                entries.append((row.get("eventId"), row.get("startFrame"), row.get("endFrame")))
    if isinstance(legacy, dict):
        for row in legacy.get("beats", []):
            if isinstance(row, dict):
                entries.append((row.get("id"), row.get("start_frame"), row.get("end_frame")))
    for event_id, start, end in entries:
        if (not isinstance(event_id, str) or not event_id or len(event_id) > 128
                or type(start) is not int or type(end) is not int or not 0 <= start < end <= frames):
            raise AudioError("SFX_PLAN_EVENT_RANGE_INVALID")
        ranges.setdefault(event_id, []).append((start, end))
    return ranges


def _gain(value, code: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise AudioError(code)
    return float(value)


def normalize_sfx(settings: dict | None, video_plan: dict) -> dict:
    """Validate structured cues against actual global event ranges.

    Missing ``cues`` means one transition at each supplied event-chapter start;
    explicit ``[]`` means no sounds. This never invents geographic/history data.
    At 30fps all cue/sample offsets are exact multiples of 1,600 samples.
    """
    ranges = _event_ranges(video_plan)
    if settings is None:
        settings = {}
    if not isinstance(settings, dict) or set(settings) - {"enabled", "gain", "exportWav", "cues"}:
        raise AudioError("SFX_SETTINGS_INVALID")
    enabled, export = settings.get("enabled", True), settings.get("exportWav", False)
    if type(enabled) is not bool or type(export) is not bool:
        raise AudioError("SFX_TOGGLE_INVALID")
    gain = _gain(settings.get("gain", .65), "SFX_GAIN_INVALID")
    cues = settings.get("cues")
    if cues is None:
        production = video_plan.get("productionV3", {})
        cues = [{"eventId": row["eventId"], "frame": row["startFrame"], "type": "EVENT_TRANSITION"}
                for row in production.get("eventChapters", [])] if isinstance(production, dict) else []
    if not isinstance(cues, list) or len(cues) > MAX_EVENTS:
        raise AudioError("SFX_CUES_INVALID")
    normalized = []
    identities = set()
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) - {"eventId", "frame", "type", "gain"}:
            raise AudioError("SFX_CUE_INVALID")
        event_id, frame, kind = cue.get("eventId"), cue.get("frame"), cue.get("type")
        if not isinstance(event_id, str) or event_id not in ranges:
            raise AudioError("SFX_EVENT_REFERENCE_MISSING")
        if type(frame) is not int or not any(a <= frame < b for a, b in ranges[event_id]):
            raise AudioError("SFX_FRAME_OUTSIDE_BOUND_EVENT")
        if not isinstance(kind, str) or kind not in TYPES:
            raise AudioError("SFX_TYPE_UNSUPPORTED")
        identity = (event_id, frame, kind)
        if identity in identities:
            raise AudioError("SFX_DUPLICATE_CUE")
        identities.add(identity)
        normalized.append({"eventId": event_id, "frame": frame, "type": kind,
                           "gain": _gain(cue.get("gain", 1.), "SFX_CUE_GAIN_INVALID")})
    normalized.sort(key=lambda c: (c["frame"], c["eventId"], c["type"]))
    return {"enabled": enabled, "gain": gain, "exportWav": export, "cues": normalized}


def asset_manifest() -> dict:
    path = HERE / "audio/ASSET_MANIFEST.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100000:
        raise AudioError("SFX_ASSET_MANIFEST_INVALID")
    manifest = json.loads(path.read_text())
    if (manifest.get("schema") != "WORLD_ENGINE_STUDIO_ORIGINAL_SFX_ASSETS_V1"
            or manifest.get("license") != "CC0-1.0" or manifest.get("commercialUseAllowed") is not True
            or manifest.get("referenceAudioSampled") is not False
            or manifest.get("sourceSha256") != SOURCE_SHA256
            or manifest.get("sampleRate") != SR or manifest.get("channels") != 2):
        raise AudioError("SFX_ASSET_LICENSE_OR_SOURCE_INVALID")
    frozen = HERE / "dependencies/rhythm_sound.py"
    if frozen.is_symlink() or not frozen.is_file() or _sha(frozen) != SOURCE_SHA256:
        raise AudioError("SFX_ORIGINAL_SOURCE_CHANGED")
    expected = {f"{category}_{i:02d}" for category in TYPES.values() for i in range(1, 4)}
    rows = manifest.get("assets")
    if not isinstance(rows, list) or {r.get("id") for r in rows if isinstance(r, dict)} != expected or len(rows) != 18:
        raise AudioError("SFX_ASSET_CATALOG_INVALID")
    if any(row.get("license") != "CC0-1.0" or row.get("source_sha256") != SOURCE_SHA256
           or row.get("sample_rate") != SR or row.get("channels") != 2 for row in rows):
        raise AudioError("SFX_ASSET_LICENSE_OR_SOURCE_INVALID")
    return manifest


def _read_asset(row: dict) -> np.ndarray:
    name = row.get("file")
    if not isinstance(name, str) or name != row["id"] + ".wav" or Path(name).name != name:
        raise AudioError("SFX_ASSET_PATH_INVALID")
    path = HERE / "audio" / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256000 or _sha(path) != row.get("sha256"):
        raise AudioError("SFX_ASSET_HASH_MISMATCH")
    with wave.open(str(path), "rb") as stream:
        if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth(), stream.getnframes(), stream.getcomptype()) != (
                SR, 2, 2, row.get("frames"), "NONE"):
            raise AudioError("SFX_ASSET_FORMAT_INVALID")
        raw = stream.readframes(stream.getnframes())
    if hashlib.sha256(raw).hexdigest() != row.get("pcmSha256"):
        raise AudioError("SFX_ASSET_PCM_HASH_MISMATCH")
    return np.frombuffer(raw, dtype="<i2").reshape(-1, 2).astype(np.float32) / 32767.


def verify_assets() -> dict:
    """Preflight actual source/licensing/file hashes; no GPU or audio sampling."""
    manifest = asset_manifest()
    for row in manifest["assets"]:
        _read_asset(row)
    return {"status": "PASS", "license": "CC0-1.0", "sourceSha256": SOURCE_SHA256,
            "manifestSha256": _sha(HERE / "audio/ASSET_MANIFEST.json"), "assetCount": len(manifest["assets"])}


def _new_output(path: Path) -> Path:
    path = Path(path)
    if path.exists() or path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
        raise AudioError("SFX_OUTPUT_MUST_BE_FRESH_PRIVATE_PATH")
    return path


def _publish(temporary: Path, destination: Path) -> None:
    # Existing results are never replaced, even if two callers race.
    os.link(temporary, destination, follow_symlinks=False)
    temporary.unlink()


def render_sfx(settings: dict | None, video_plan: dict, output_wav: Path) -> dict:
    """Stream a deterministic PCM16 stereo track in <=one-second blocks.

    At most three short source waveforms are mixed simultaneously. A fourth
    overlapping cue or same-type cue inside 120ms is omitted, never shifted
    away from its actual event. Every omission and exact sample offset appears
    in the private receipt. No hard limiter or global loudness pumping occurs.
    """
    started = time.monotonic()
    normalized = normalize_sfx(settings, video_plan)
    _, fps, total_samples = _timing(video_plan)
    base = {"schema": "WORLD_ENGINE_STUDIO_SFX_RENDER_V1", "enabled": normalized["enabled"],
            "sampleRate": SR, "channels": 2, "totalSamples": total_samples, "sampleWidth": 2,
            "audioDurationSeconds": total_samples / SR, "license": "CC0-1.0", "file": None,
            "sha256": None, "assets": [], "cues": [], "directListening": False,
            "referenceAudioSampled": False, "narration": False, "bgm": False}
    if not normalized["enabled"]:
        return {**base, "status": "DISABLED", "elapsedSeconds": time.monotonic() - started,
                "mixPolicy": {"blockSamples": BLOCK_SAMPLES, "maximumResidentMixSamples": 0}}
    destination = _new_output(output_wav)
    manifest = asset_manifest()
    catalog = {row["id"]: row for row in manifest["assets"]}
    resident_assets, last_variant, last_type, accepted, records = {}, {}, {}, [], []
    for cue in normalized["cues"]:
        offset = _round_fraction(Fraction(cue["frame"] * SR, 1) / fps)
        record = {**cue, "onsetSample": offset, "status": "RENDERED"}
        if offset - last_type.get(cue["type"], -COOLDOWN_SAMPLES) < COOLDOWN_SAMPLES:
            records.append({**record, "status": "OMITTED_TYPE_COOLDOWN"})
            continue
        category = TYPES[cue["type"]]
        names = [f"{category}_{i:02d}" for i in range(1, 4)]
        seed = int(hashlib.sha256(f"{cue['eventId']}:{cue['frame']}:{cue['type']}".encode()).hexdigest()[:8], 16)
        rotated = names[seed % 3:] + names[:seed % 3]
        variant = next(n for n in rotated if n != last_variant.get(category))
        row = catalog[variant]
        n = min(row["frames"], total_samples - offset)
        if sum(item["onsetSample"] <= offset < item["endSample"] for item in accepted) >= MAX_OVERLAP:
            records.append({**record, "status": "OMITTED_OVERLAP_LIMIT"})
            continue
        if variant not in resident_assets:
            resident_assets[variant] = _read_asset(row)
        record.update({"variant": variant, "endSample": offset + n, "assetSha256": row["sha256"],
                       "linearGain": normalized["gain"] * cue["gain"] * MAX_CUE_GAIN})
        records.append(record)
        accepted.append(record)
        last_type[cue["type"]], last_variant[category] = offset, variant
    handle, name = tempfile.mkstemp(prefix=".studio-sfx-", suffix=".wav", dir=destination.parent)
    os.close(handle)
    temporary = Path(name)
    peak, clipped, block_count, maximum_mix = 0., 0, 0, 0
    try:
        with wave.open(str(temporary), "wb") as stream:
            stream.setparams((2, 2, SR, total_samples, "NONE", "not compressed"))
            next_event, active = 0, []
            for start in range(0, total_samples, BLOCK_SAMPLES):
                end = min(start + BLOCK_SAMPLES, total_samples)
                mix = np.zeros((end - start, 2), dtype=np.float32)
                maximum_mix = max(maximum_mix, len(mix))
                while next_event < len(accepted) and accepted[next_event]["onsetSample"] < end:
                    active.append(accepted[next_event]); next_event += 1
                for event in active:
                    a, b = max(start, event["onsetSample"]), min(end, event["endSample"])
                    if b <= a:
                        continue
                    source_a, source_b = a - event["onsetSample"], b - event["onsetSample"]
                    clip = resident_assets[event["variant"]][source_a:source_b].copy()
                    # Apply final fade in source coordinates, stable over block boundaries.
                    n = event["endSample"] - event["onsetSample"]
                    fade = min(FADE_SAMPLES, n)
                    positions = np.arange(source_a, source_b)
                    envelope = np.minimum(1., (n - 1 - positions) / max(fade - 1, 1))
                    np.maximum(envelope, 0., out=envelope)
                    clip *= envelope[:, None] * event["linearGain"]
                    mix[a - start:b - start] += clip
                active = [event for event in active if event["endSample"] > end]
                local_peak = float(np.max(np.abs(mix))) if len(mix) else 0.
                peak = max(peak, local_peak)
                clipped += int(np.count_nonzero(np.abs(mix) > 1.))
                if clipped:
                    raise AudioError("SFX_UNEXPECTED_CLIPPING")
                stream.writeframesraw(np.rint(mix * 32767.).astype("<i2").tobytes())
                block_count += 1
        with wave.open(str(temporary), "rb") as stream:
            if stream.getnframes() != total_samples:
                raise AudioError("SFX_OUTPUT_SAMPLE_COUNT_MISMATCH")
        _publish(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    used = sorted(resident_assets)
    return {**base, "status": "PASS", "file": str(destination), "sha256": _sha(destination),
            "settings": normalized, "cues": records,
            "assets": [{"id": name, "sha256": catalog[name]["sha256"], "license": "CC0-1.0"} for name in used],
            "assetManifestSha256": _sha(HERE / "audio/ASSET_MANIFEST.json"), "sourceSha256": SOURCE_SHA256,
            "mixPolicy": {"blockSamples": BLOCK_SAMPLES, "blockCount": block_count,
                          "maximumResidentMixSamples": maximum_mix, "maxOverlap": MAX_OVERLAP,
                          "perTypeCooldownSamples": COOLDOWN_SAMPLES, "peakBudget": MAX_CUE_GAIN * MAX_OVERLAP,
                          "measuredPeak": peak, "clippedSamples": clipped,
                          "gain": normalized["gain"], "omissions": dict(Counter(c["status"] for c in records if c["status"] != "RENDERED")),
                          "maximumResidentAssetSamples": sum(len(a) for a in resident_assets.values()),
                          "sampleOffsetMethod": "nearest rational sample, half-up; exact frame grid when sampleRate/fps is integral"},
            "elapsedSeconds": time.monotonic() - started}


def _run(command: list[str], timeout: float) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise AudioError("SFX_FFMPEG_UNAVAILABLE_OR_TIMEOUT") from None
    if result.returncode:
        raise AudioError("SFX_FFMPEG_VALIDATION_FAILED")
    return result


def _probe(path: Path) -> dict:
    result = _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], 60)
    return json.loads(result.stdout)


def _video_signature(path: Path, timeout: float) -> dict:
    # Only small textual frame hashes enter memory, never decoded frame pixels.
    result = _run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-threads", "2", "-i", str(path),
                   "-map", "0:v:0", "-an", "-f", "framemd5", "-"], timeout)
    frames, pixels, timestamps = 0, hashlib.sha256(), hashlib.sha256()
    for raw in result.stdout.splitlines():
        if not raw or raw.startswith(b"#"):
            continue
        fields = [value.strip() for value in raw.split(b",")]
        if len(fields) != 6:
            raise AudioError("SFX_FRAME_HASH_OUTPUT_INVALID")
        pixels.update(fields[-1] + b"\n")
        timestamps.update(b",".join(fields[1:4]) + b"\n")
        frames += 1
    return {"frames": frames, "decodedFrameSequenceSha256": pixels.hexdigest(),
            "timestampSequenceSha256": timestamps.hexdigest()}


def _video_contract(meta: dict, plan: dict) -> None:
    frames, fps, _ = _timing(plan)
    videos = [stream for stream in meta["streams"] if stream["codec_type"] == "video"]
    if len(videos) != 1:
        raise AudioError("SFX_SINGLE_VIDEO_REQUIRED")
    video = videos[0]
    resolution = plan.get("resolution")
    if isinstance(resolution, dict):
        resolution = [resolution.get("width"), resolution.get("height")]
    if (video.get("codec_name") != "h264" or [video.get("width"), video.get("height")] != resolution
            or Fraction(video.get("avg_frame_rate", "0/1")) != fps
            or int(video.get("nb_frames", -1)) != frames):
        raise AudioError("SFX_VIDEO_PLAN_MISMATCH")


def mux_sfx(silent_mp4: Path, wav: Path | None, output_mp4: Path, plan: dict) -> dict:
    """Copy unchanged H.264 frames and add one AAC track, or keep SFX OFF.

    MP4/AAC can contain codec-frame padding. Verification separately measures
    the MP4 edit-list effective duration and actually decodes/trim-checks all
    intended audio samples; padding is reported, never called extra content.
    """
    started = time.monotonic()
    source, destination = Path(silent_mp4), _new_output(Path(output_mp4))
    if source.is_symlink() or not source.is_file() or source == destination:
        raise AudioError("SFX_SILENT_INPUT_INVALID")
    frames, _, total_samples = _timing(plan)
    duration = total_samples / SR
    timeout = max(120., duration * 20)
    before = _probe(source)
    _video_contract(before, plan)
    if any(s["codec_type"] == "audio" for s in before["streams"]):
        raise AudioError("SFX_INPUT_MUST_BE_VERIFIED_SILENT")
    before_signature = _video_signature(source, timeout)
    if before_signature["frames"] != frames:
        raise AudioError("SFX_VIDEO_FRAME_COUNT_MISMATCH")
    handle, name = tempfile.mkstemp(prefix=".studio-mux-", suffix=".mp4", dir=destination.parent)
    os.close(handle)
    temporary = Path(name)
    # FFmpeg -n needs a path that does not exist; tempfile selected a private unique name.
    temporary.unlink()
    audio_info = {"audioStreams": 0, "effectiveAudioSamples": 0, "audioDurationSeconds": 0.,
                  "codecPaddingSamples": 0, "sampleRate": SR}
    try:
        if wav is None:
            with temporary.open("xb") as out, source.open("rb") as inp:
                shutil.copyfileobj(inp, out, length=1024 * 1024)
        else:
            wav = Path(wav)
            if wav.is_symlink() or not wav.is_file():
                raise AudioError("SFX_WAV_INPUT_INVALID")
            with wave.open(str(wav), "rb") as stream:
                if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth(), stream.getnframes()) != (SR, 2, 2, total_samples):
                    raise AudioError("SFX_WAV_PLAN_MISMATCH")
            _run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-n", "-i", str(source), "-i", str(wav),
                  "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "-1", "-c:v", "copy", "-c:a", "aac",
                  "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-t", format(duration, ".12f"),
                  "-movflags", "+faststart", str(temporary)], timeout)
        after = _probe(temporary)
        _video_contract(after, plan)
        after_signature = _video_signature(temporary, timeout)
        if before_signature != after_signature:
            raise AudioError("SFX_MUX_CHANGED_VIDEO_FRAMES_OR_TIMESTAMPS")
        audios = [s for s in after["streams"] if s["codec_type"] == "audio"]
        if wav is None:
            if audios or _sha(source) != _sha(temporary):
                raise AudioError("SFX_OFF_CHANGED_SILENT_VIDEO")
        else:
            if len(audios) != 1 or audios[0].get("codec_name") != "aac" or audios[0].get("sample_rate") != str(SR) or audios[0].get("channels") != 2:
                raise AudioError("SFX_AAC_STREAM_INVALID")
            audio = audios[0]
            effective = Fraction(int(audio["duration_ts"])) * Fraction(audio["time_base"]) * SR
            if effective != total_samples or abs(float(audio.get("start_time", "0"))) > 1 / SR:
                raise AudioError("SFX_EFFECTIVE_AUDIO_DURATION_MISMATCH")
            # Decoded sample counts are obtained without buffering PCM in Python.
            decoded = _run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "frame=nb_samples",
                            "-of", "csv=p=0", str(temporary)], timeout)
            decoded_samples = sum(int(line) for line in decoded.stdout.splitlines() if line.strip())
            padding = decoded_samples - total_samples
            if not 0 <= padding < 1024:
                raise AudioError("SFX_AAC_PADDING_INVALID")
            trimmed = _run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-i", str(temporary), "-map", "0:a:0", "-vn",
                            "-af", f"atrim=end_sample={total_samples}", "-ar", str(SR), "-ac", "2", "-f", "hash", "-hash", "sha256", "-"], timeout)
            audio_info = {"audioStreams": 1, "effectiveAudioSamples": total_samples, "audioDurationSeconds": duration,
                          "decodedAudioSamplesIncludingPadding": decoded_samples, "codecPaddingSamples": padding,
                          "sampleRate": SR, "effectiveAudioDecodedHash": trimmed.stdout.decode("ascii").strip()}
        _publish(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {"schema": "WORLD_ENGINE_STUDIO_SFX_MUX_V1", "status": "PASS", "file": str(destination),
            "sha256": _sha(destination), "videoFrames": frames, "videoDecodedPixelsUnchanged": True,
            "videoFrameTimestampsUnchanged": True, "videoFrameSequenceSha256": before_signature["decodedFrameSequenceSha256"],
            "videoCodec": "h264", "fullDecode": "PASS", "videoBytesUnchanged": wav is None,
            "audioEnabled": wav is not None, **audio_info, "elapsedSeconds": time.monotonic() - started,
            "nvidiaVerification": "NOT_ASSERTED", "visualQuality": "USER_VIDEO_REVIEW_REQUIRED"}
