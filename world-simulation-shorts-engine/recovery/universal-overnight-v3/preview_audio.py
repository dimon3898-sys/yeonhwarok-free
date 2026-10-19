"""Sample-exact preview clip of the unchanged global Studio SFX mixer.

The existing mixer chooses variants/cooldown on the complete authored clock.
Clipping afterwards preserves cues/tails at the preview boundary. No audio is
sampled from the reference and no sound is moved to a different source frame.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import wave

from preview_contract import validate_preview, sha256, canonical, PreviewError

HERE = Path(__file__).resolve().parent
PRESERVED_AUDIO = (Path('/opt/world-engine-production-studio/studio_audio.py') if HERE.is_relative_to('/opt')
                   else HERE.parent / "production-studio-mvp-v1/studio_audio.py")
PRESERVED_AUDIO_SHA256 = "03a9083aa71ac5acbe17806afd8dfb44e1fd155e886237aba6c00ae3552dca5d"


def _old_audio():
    # Preserve the deployed mixer exactly; a future change needs its own audit.
    raw = PRESERVED_AUDIO.read_bytes()
    if sha256(raw) != PRESERVED_AUDIO_SHA256:
        raise PreviewError("PREVIEW_PRESERVED_SFX_SOURCE_CHANGED")
    spec = importlib.util.spec_from_file_location("_overnight_preserved_studio_audio", PRESERVED_AUDIO)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fresh_output(path):
    path = Path(path)
    if (path.exists() or path.is_symlink() or not path.parent.is_dir()
            or any(p.is_symlink() for p in path.parents)):
        raise PreviewError("PREVIEW_AUDIO_FRESH_PRIVATE_OUTPUT_REQUIRED")
    return path


def _hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clip_pcm_wav(source, output, *, start_sample, end_sample):
    """Bounded PCM copy; no resampling, faded restart, or float requantization."""
    source, output = Path(source), _fresh_output(output)
    if (source.is_symlink() or not source.is_file() or any(p.is_symlink() for p in source.parents)
            or type(start_sample) is not int or type(end_sample) is not int or not 0 <= start_sample < end_sample):
        raise PreviewError("PREVIEW_AUDIO_SOURCE_RANGE_INVALID")
    handle, name = tempfile.mkstemp(prefix=".preview-audio-", suffix=".wav", dir=output.parent)
    os.close(handle)
    temporary, digest, copied = Path(name), hashlib.sha256(), 0
    try:
        with wave.open(str(source), "rb") as src:
            if (src.getnchannels(), src.getsampwidth(), src.getframerate(), src.getcomptype()) != (2, 2, 48000, "NONE"):
                raise PreviewError("PREVIEW_AUDIO_ORIGINAL_FORMAT_REQUIRED")
            if end_sample > src.getnframes():
                raise PreviewError("PREVIEW_AUDIO_RANGE_OUTSIDE_GLOBAL_TRACK")
            src.setpos(start_sample)
            with wave.open(str(temporary), "wb") as dst:
                dst.setparams((2, 2, 48000, end_sample - start_sample, "NONE", "not compressed"))
                remaining = end_sample - start_sample
                while remaining:
                    frames = min(48000, remaining)
                    raw = src.readframes(frames)
                    if len(raw) != frames * 4:
                        raise PreviewError("PREVIEW_AUDIO_TRUNCATED_SOURCE")
                    digest.update(raw)
                    dst.writeframesraw(raw)
                    copied += frames
                    remaining -= frames
        with wave.open(str(temporary), "rb") as checked:
            if checked.getnframes() != copied:
                raise PreviewError("PREVIEW_AUDIO_CLIP_SAMPLE_COUNT_MISMATCH")
        os.link(temporary, output, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)
    return {"startSample": start_sample, "endSample": end_sample, "sampleCount": copied,
            "sampleRate": 48000, "channels": 2, "pcmSha256": digest.hexdigest(),
            "sha256": _hash_file(output), "file": str(output), "resampled": False,
            "sourceGlobalCueSchedulingPreserved": True, "maximumResidentPcmSamples": 48000}


def render_preview_sfx(settings, plan, request, output_wav):
    request = validate_preview(request, plan)
    audio = _old_audio()
    normalized = audio.normalize_sfx(settings, plan)
    base = {"schema": "WORLD_ENGINE_PREVIEW_SFX_V3", "requestSHA256": request["requestSHA256"],
            "sourcePlanSemanticSHA256": request["planSemanticSHA256"],
            "sourceSfxSettingsSHA256": sha256(canonical(normalized)), "audioClock": request["audioClock"],
            "sourceMixerSHA256": PRESERVED_AUDIO_SHA256, "referenceAudioSampled": False,
            "hardwareVerification": "NOT_APPLICABLE_CPU_AUDIO", "visualQualityApproved": False}
    if not normalized["enabled"]:
        return {**base, "status": "DISABLED", "file": None}
    output = _fresh_output(output_wav)
    # Only the small CPU audio track is mixed in full, not an eighty-second
    # video. Reusing its scheduling avoids subtly different preview cue tails.
    with tempfile.TemporaryDirectory(prefix=".preview-sfx-source-", dir=output.parent) as directory:
        full_track = Path(directory) / "ORIGINAL_GLOBAL_SFX.wav"
        rendered = audio.render_sfx(normalized, plan, full_track)
        clipped = clip_pcm_wav(full_track, output, start_sample=request["audioClock"]["startSample"],
                               end_sample=request["audioClock"]["endSample"])
    cues = [{**row, "previewOnsetSample": row["onsetSample"] - clipped["startSample"]}
            for row in rendered["cues"] if row["onsetSample"] < clipped["endSample"]
            and row["endSample"] > clipped["startSample"]]
    return {**base, "status": "PASS", **clipped, "cues": cues,
            "sourceGlobalTrackSHA256": rendered["sha256"], "assetManifestSHA256": rendered["assetManifestSha256"],
            "license": rendered["license"], "mixPolicy": rendered["mixPolicy"],
            "fullVideoRendered": False, "temporaryGlobalAudioRetained": False}


def mux_preview_sfx(silent_mp4, wav, output_mp4, plan, request):
    """Reuse original mux/decode/hash checks with a media-clock-only descriptor."""
    request = validate_preview(request, plan)
    audio = _old_audio()
    clock = {"totalFrames": 150, "fps": 30, "durationSeconds": 5,
             "resolution": {"width": 1080, "height": 1920}}
    result = audio.mux_sfx(Path(silent_mp4), Path(wav) if wav is not None else None,
                           Path(output_mp4), clock)
    return {**result, "requestSHA256": request["requestSHA256"], "globalSourceRange": request["range"],
            "sourceSceneJsonChanged": False, "sampleClockOrigin": request["audioClock"]["startSample"]}


if __name__ == "__main__":
    import argparse
    from preview_contract import verify_preview_request_file
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--plan-file", required=True)
    parser.add_argument("--settings-file", required=True)
    parser.add_argument("--output-wav", required=True)
    args = parser.parse_args()
    try:
        request = verify_preview_request_file(args.request_file, args.plan_file)
        plan = json.loads(Path(args.plan_file).read_bytes())
        settings = json.loads(Path(args.settings_file).read_bytes())
        result = render_preview_sfx(settings, plan, request, args.output_wav)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"status": "BLOCKED", "errorCode": str(error) if isinstance(error, PreviewError)
                          else "PREVIEW_SFX_FAILED"}))
        raise SystemExit(2)
