#!/usr/bin/env python3
"""Compare existing 10–20s encoded samples; never invoke a video renderer.

The original output frames and 375px phone views are captured independently
from both MP4s. Five PNG sheets arrange those real pixels without recoloring
or modifying the source movies. Uploaded reference images are never included.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont


APP = Path(__file__).resolve().parents[1]
DEFAULT_CHOICES = [
    {"role": "flat_start", "time": 0.5, "sheet": "flat"},
    {"role": "country_focus", "time": 2.0, "sheet": "country_focus"},
    {"role": "entity_departure", "time": 1.8, "sheet": "entity_route"},
    {"role": "entity_route", "time": 4.5, "sheet": "entity_route"},
    {"role": "next_focus", "time": 7.0, "sheet": "country_focus"},
    {"role": "network_route", "time": 10.8, "sheet": "entity_route"},
    {"role": "transition_pre", "time": 11.9, "sheet": "transition"},
    {"role": "transition_mid", "time": 12.1, "sheet": "transition"},
    {"role": "transition_post", "time": 12.4, "sheet": "transition"},
    {"role": "final_earth", "time": 14.9, "sheet": "earth"},
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def probe_sample(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"Existing sample MP4 is absent: {path}; no capture started")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        text=True, capture_output=True, check=True, timeout=25,
    )
    data = json.loads(result.stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ValueError("Sample has no video stream")
    duration = float(data["format"]["duration"])
    fps = float(Fraction(video["avg_frame_rate"]))
    if not 10 <= duration <= 20:
        raise ValueError("Only existing 10–20s sample comparison is allowed; a 75s movie is never decoded")
    if not math.isfinite(fps) or fps < 30:
        raise ValueError("Comparison requires valid 30fps-or-higher samples")
    if (video["width"], video["height"]) != (1080, 1920):
        raise ValueError("Comparison requires native 1080×1920 output; no disguised frame upscaling")
    return {"raw_ffprobe": data, "fps": fps, "duration": duration, "width": 1080, "height": 1920}


def frame_choices(raw: list[dict], fps: float, duration: float) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("At least one comparison time is required")
    if len(raw) > 24:
        raise ValueError("A bounded comparison supports at most 24 timepoints")
    result = []
    roles = set()
    indices = set()
    for choice in raw:
        role, sheet = str(choice["role"]), str(choice["sheet"])
        if not role or not sheet or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in role + sheet):
            raise ValueError("Role/sheet names must be plain ASCII identifiers")
        nominal = float(choice["time"])
        if not math.isfinite(nominal) or nominal < 0:
            raise ValueError("Frame time must be finite and nonnegative")
        index = math.floor(nominal * fps + 0.5)
        if index / fps >= duration:
            raise ValueError(f"Timepoint {nominal} lies outside the actual existing video")
        if role in roles or index in indices:
            raise ValueError("Duplicate role or frame-grid timepoint")
        roles.add(role)
        indices.add(index)
        result.append({"role": role, "sheet": sheet, "requested_seconds": nominal,
                       "frame_index_zero_based": index, "actual_seconds": index / fps})
    if len({c["sheet"] for c in result}) > 8 or any(sum(x["sheet"] == c["sheet"] for x in result) > 4 for c in result):
        raise ValueError("Comparison sheets are bounded to at most eight sheets and four rows per sheet")
    return sorted(result, key=lambda item: item["frame_index_zero_based"])


def capture(path: Path, directory: Path, choices: list[dict]) -> tuple[list[dict], list[str]]:
    directory.mkdir(exist_ok=False)
    expression = "+".join(f"eq(n\\,{c['frame_index_zero_based']})" for c in choices)
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(path),
               "-vf", "select=" + expression, "-fps_mode", "vfr", "-frames:v", str(len(choices)),
               "-n", str(directory / "capture_%02d.png")]
    subprocess.run(command, text=True, capture_output=True, check=True, timeout=60)
    result = []
    for index, choice in enumerate(choices, 1):
        native = directory / f"{choice['role']}_1080.png"
        (directory / f"capture_{index:02d}.png").rename(native)
        phone = directory / f"{choice['role']}_375.png"
        with Image.open(native) as frame:
            if frame.size != (1080, 1920):
                raise ValueError("Decoder frame dimensions differ from validated native output")
            # Only a phone-view derivative is resampled. The native PNG remains exact.
            frame.resize((375, 667), Image.Resampling.LANCZOS).save(phone)
        result.append({**choice, "native_png": file_record(native), "phone_png": file_record(phone)})
    return result, command


def font(size: int):
    path = APP.parent / "cinematic-world-map/assets/v3/fonts/OpenSans-Light.ttf"
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def composition(output: Path, before: list[dict], after: list[dict]) -> list[dict]:
    sheets = []
    for sheet in dict.fromkeys(choice["sheet"] for choice in before):
        rows = [(left, right) for left, right in zip(before, after) if left["sheet"] == sheet]
        gutter, header, footer, row_height = 30, 88, 36, 2044
        native_width, phone_width = 1080, 375
        width = native_width * 2 + phone_width * 2 + gutter * 5
        image = Image.new("RGB", (width, len(rows) * row_height), "#11191f")
        draw = ImageDraw.Draw(image)
        for row_index, (left, right) in enumerate(rows):
            y = row_index * row_height
            draw.text((gutter, y + 8),
                      f"{left['role']} | requested {left['requested_seconds']:.4f}s | frame {left['frame_index_zero_based']} / actual {left['actual_seconds']:.4f}s",
                      fill="#e8ecee", font=font(32))
            columns = [("BEFORE / native1080", left["native_png"], native_width),
                       ("AFTER / native1080", right["native_png"], native_width),
                       ("BEFORE / phone375", left["phone_png"], phone_width),
                       ("AFTER / phone375", right["phone_png"], phone_width)]
            x = gutter
            for label, record, column_width in columns:
                draw.text((x, y + 48), label, fill="#a5b8c5", font=font(22))
                with Image.open(record["path"]) as frame:
                    image.paste(frame.convert("RGB"), (x, y + header))
                x += column_width + gutter
            draw.text((gutter, y + header + 1920 + 8),
                      "Encoded frames only. Native pixels are not recolored. Phone view: Lanczos375px. No uploaded reference images.",
                      fill="#899ca8", font=font(21))
        path = output / f"before_after_{sheet}.png"
        image.save(path)
        sheets.append({"sheet": sheet, "rows": [left["role"] for left, _ in rows],
                       "composition_size": list(image.size), **file_record(path)})
    return sheets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="Existing v003 sample MP4")
    parser.add_argument("--after", type=Path, required=True, help="Existing finished v004 sample MP4")
    parser.add_argument("--output", type=Path, help="NEW exclusive evidence directory")
    parser.add_argument("--choices", type=Path, help="Optional JSON list of role/time/sheet definitions")
    parser.add_argument("--allow-identical-input-for-test", action="store_true", help="Explicit fixture-only opt-in; never evidence of improvement")
    args = parser.parse_args()
    left, right = args.before.resolve(), args.after.resolve()
    if left == right and not args.allow_identical_input_for_test:
        raise ValueError("Before/after must be different existing files")
    left_probe, right_probe = probe_sample(left), probe_sample(right)
    if abs(left_probe["fps"] - right_probe["fps"]) > 1e-7 or abs(left_probe["duration"] - right_probe["duration"]) > 1 / left_probe["fps"]:
        raise ValueError("Time-aligned comparison requires matching FPS and duration")
    raw = json.loads(args.choices.read_text()) if args.choices else DEFAULT_CHOICES
    choices = frame_choices(raw, left_probe["fps"], min(left_probe["duration"], right_probe["duration"]))
    before_sources = {"before": file_record(left), "after": file_record(right)}
    output = args.output.resolve() if args.output else APP / "docs/evidence" / ("visual_polish_comparison_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=False, exist_ok=False)
    started = time.monotonic()
    try:
        before, before_command = capture(left, output / "before_frames", choices)
        after, after_command = capture(right, output / "after_frames", choices)
        sheets = composition(output, before, after)
        after_sources = {"before": file_record(left), "after": file_record(right)}
        if before_sources != after_sources:
            raise RuntimeError("Existing source movie changed during readonly comparison")
        report = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                  "scope": "Read-only decode of two existing10–20s samples, exact native-frame arrangements and phone downscales. No video renderer, quality claim, old75 decode or uploaded reference publication.",
                  "sources_before": before_sources, "sources_after": after_sources,
                  "source_bytes_unchanged": True, "before_ffprobe": left_probe, "after_ffprobe": right_probe,
                  "before_frames": before, "after_frames": after, "comparison_sheets": sheets,
                  "capture_commands": [before_command, after_command],
                  "elapsed_comparison_seconds": time.monotonic() - started,
                  "fixture_only": left == right, "manual_quality_review": "PENDING",
                  "full_playback_or_direct_audio_listening_claimed": False}
        (output / "COMPARISON_MANIFEST.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"output": str(output), "timepoints": len(choices), "sheets": len(sheets), "sources_unchanged": True}))
    except Exception as error:
        # Preserve completed captures and source evidence. Never delete or retry renders.
        (output / "COMPARISON_FAILED.json").write_text(json.dumps({"error": str(error), "sources_before": before_sources, "completed_work_preserved": True}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
