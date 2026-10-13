#!/usr/bin/env python3
"""Decode the user-supplied target chronologically; never alter the input MP4.

Only source-derived audit PNG/JSON files are written. A visual reviewer must inspect
the contact sheets; successful decoding is explicitly not visual acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
EXPECTED_SHA = "5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6"
MAP_ROI = [24, 220, 915, 1810]
LABEL_HEIGHT = 24
TILE_W, TILE_H = 180, 420
SHEET_COLUMNS, SHEET_ROWS = 8, 4


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path: Path, data) -> None:
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def probe(source: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)]
    return json.loads(subprocess.check_output(command))


def timestamps(source: Path) -> list[dict]:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries", "frame=best_effort_timestamp,best_effort_timestamp_time,pts,pts_time,pkt_duration_time,pict_type,key_frame", "-of", "json", str(source)]
    return json.loads(subprocess.check_output(command))["frames"]


def color_metrics(image: Image.Image) -> dict:
    """Measured screen colors, not territorial/geographic area.

    The phone/player chrome is excluded. In-map badges/subtitles still occur in
    this ROI, and camera scale changes bias coverage. These limitations are kept
    beside the measurements instead of presenting screen area as land control.
    """
    small = image.crop(tuple(MAP_ROI)).resize((297, 530), Image.Resampling.BOX)
    rgb = np.asarray(small)
    hsv = np.asarray(small.convert("HSV"))
    hue, saturation, value = (hsv[:, :, i] for i in range(3))
    orange = (hue <= 35) & (saturation >= 115) & (value >= 65)
    purple = (hue >= 170) & (hue <= 225) & (saturation >= 90) & (value >= 45)
    total = orange.size
    output = {}
    for label, mask in [("orange", orange), ("purple", purple)]:
        selected = rgb[mask]
        output[label] = {
            "sample_pixels": int(mask.sum()),
            "screen_roi_fraction": round(float(mask.sum()) / total, 7),
            "median_rgb": np.median(selected, axis=0).round(1).tolist() if len(selected) else None,
            "mean_rgb": np.mean(selected, axis=0).round(2).tolist() if len(selected) else None,
            "mean_hsv": np.mean(hsv[mask], axis=0).round(2).tolist() if len(selected) else None,
        }
    output["roi_mean_luma"] = round(float(np.mean(rgb @ np.asarray([0.2126, 0.7152, 0.0722]))), 4)
    output["roi_rgb_standard_deviation"] = round(float(np.std(rgb)), 4)
    output["black_or_blank_flag"] = bool(output["roi_mean_luma"] < 2 or output["roi_rgb_standard_deviation"] < 0.5)
    return output


def read_exact(stream, length: int) -> bytes:
    chunks = []
    remaining = length
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=HERE / "data/REFERENCE_65379_COMPRESSED.mp4")
    parser.add_argument("--output", type=Path, default=HERE / "evidence/reference_audit")
    args = parser.parse_args()
    source, destination = args.input.resolve(), args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    input_sha = digest(source)
    if input_sha != EXPECTED_SHA:
        raise RuntimeError("The user-authorized target input SHA does not match the durable checkpoint")
    info = probe(source)
    video = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
    width, height = int(video["width"]), int(video["height"])
    if [width, height] != [1080, 2520]:
        raise RuntimeError("Unexpected source dimensions; update audited ROI explicitly")
    frame_times = timestamps(source)
    pts = [float(frame["best_effort_timestamp_time"]) for frame in frame_times]
    if any(b <= a for a, b in zip(pts, pts[1:])):
        raise RuntimeError("Reference presentation timestamps are not strictly chronological")
    save_json(destination / "FFPROBE.json", info)
    save_json(destination / "FRAME_TIMESTAMPS.json", frame_times)
    detail_targets = [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30]
    detail_frames = {min(range(len(pts)), key=lambda i: abs(pts[i] - target)): target for target in detail_targets}
    frame_rows, sheets, detail_rows = [], [], []
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 13) if font_path.exists() else ImageFont.load_default()
    sheet = None
    started = time.monotonic()
    command = ["ffmpeg", "-v", "error", "-threads", "2", "-i", str(source), "-map", "0:v:0", "-an", "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    stderr_path = destination / "DECODE_STDERR.txt"
    with stderr_path.open("wb") as error_handle:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_handle)
        if process.stdout is None:
            raise RuntimeError("FFmpeg did not provide a raw frame pipe")
        for frame_index in range(len(frame_times)):
            raw = read_exact(process.stdout, width * height * 3)
            if len(raw) != width * height * 3:
                process.kill()
                raise RuntimeError(f"Incomplete raw frame {frame_index}: {len(raw)} bytes")
            image = Image.frombytes("RGB", (width, height), raw)
            thumbnail = image.resize((TILE_W, TILE_H), Image.Resampling.LANCZOS)
            metrics = color_metrics(image)
            row = {
                "index": frame_index,
                "pts_seconds": pts[frame_index],
                "pts_source": frame_times[frame_index],
                "decoded_rgb_sha256": hashlib.sha256(raw).hexdigest(),
                "thumbnail_rgb_sha256": hashlib.sha256(thumbnail.tobytes()).hexdigest(),
                "screen_color_measurements": metrics,
            }
            frame_rows.append(row)
            tile_index = frame_index % (SHEET_COLUMNS * SHEET_ROWS)
            if tile_index == 0:
                sheet = Image.new("RGB", (SHEET_COLUMNS * TILE_W, SHEET_ROWS * (TILE_H + LABEL_HEIGHT)), "#111111")
            x = (tile_index % SHEET_COLUMNS) * TILE_W
            y = (tile_index // SHEET_COLUMNS) * (TILE_H + LABEL_HEIGHT)
            sheet.paste(thumbnail, (x, y))
            ImageDraw.Draw(sheet).text((x + 4, y + TILE_H + 4), f"{frame_index:03d} | {pts[frame_index]:07.3f}s", font=font, fill="white")
            if frame_index in detail_frames:
                target = detail_frames[frame_index]
                detail_path = destination / f"DETAIL_{target:02d}S_FRAME_{frame_index:03d}.png"
                image.save(detail_path, optimize=True)
                detail_rows.append({"target_seconds": target, "index": frame_index, "pts_seconds": pts[frame_index], "file": detail_path.name, "sha256": digest(detail_path)})
            if tile_index == SHEET_COLUMNS * SHEET_ROWS - 1 or frame_index == len(frame_times) - 1:
                sheet_index = len(sheets)
                first = frame_index - tile_index
                sheet_path = destination / f"CONTACT_{sheet_index:02d}_FRAMES_{first:03d}_{frame_index:03d}.png"
                sheet.save(sheet_path, optimize=True)
                sheets.append({"index": sheet_index, "first_frame": first, "last_frame": frame_index, "first_pts": pts[first], "last_pts": pts[frame_index], "file": sheet_path.name, "sha256": digest(sheet_path), "frame_count": tile_index + 1})
                save_json(destination / "CONTACT_SHEETS_INDEX.json", {"input_sha256": input_sha, "status": "IN_PROGRESS", "decoded_frames": len(frame_rows), "sheets": sheets})
                print(json.dumps({"contact_sheet_ready": sheet_path.name, "decoded_frames": len(frame_rows), "last_pts": pts[frame_index]}), flush=True)
        extra = process.stdout.read(1)
        return_code = process.wait()
        if extra or return_code:
            raise RuntimeError(f"Frame count/decode failure: extra={bool(extra)}, exit={return_code}")
    source_end_sha = digest(source)
    if source_end_sha != input_sha:
        raise RuntimeError("Input reference unexpectedly changed during read-only decode")
    save_json(destination / "FRAMES.json", frame_rows)
    deltas = np.diff(np.asarray(pts))
    report = {
        "status": "DECODE_AND_MEASUREMENT_PASS",
        "reference_role": "USER_AUTHORIZED_TARGET_REFERENCE",
        "input": str(source.relative_to(HERE)),
        "input_sha256_before": input_sha,
        "input_sha256_after": source_end_sha,
        "input_unchanged": source_end_sha == input_sha,
        "duration_seconds": float(info["format"]["duration"]),
        "width": width, "height": height,
        "decoded_frames": len(frame_rows),
        "ffprobe_frame_count": len(frame_times),
        "strictly_chronological_pts": True,
        "pts_interval_min_seconds": float(deltas.min()),
        "pts_interval_max_seconds": float(deltas.max()),
        "pts_interval_median_seconds": float(np.median(deltas)),
        "variable_frame_timing": bool(deltas.max() - deltas.min() > 0.001),
        "black_or_blank_frames": [row["index"] for row in frame_rows if row["screen_color_measurements"]["black_or_blank_flag"]],
        "decode_stderr_bytes": stderr_path.stat().st_size,
        "contact_sheet_count": len(sheets),
        "contact_sheet_frame_coverage": sum(sheet["frame_count"] for sheet in sheets),
        "every_frame_rgb_sha256_recorded": True,
        "every_thumbnail_rgb_sha256_recorded": True,
        "contact_sheets": sheets,
        "detail_stills": detail_rows,
        "color_measurement_contract": {
            "roi_source_pixels": MAP_ROI,
            "sample_width": 297, "sample_height": 530,
            "method": "Actual decoded RGB -> Pillow HSV; threshold faction-colored screen pixels",
            "orange_hsv_8bit": {"hue": [0,35], "saturation": [115,255], "value": [65,255]},
            "purple_hsv_8bit": {"hue": [170,225], "saturation": [90,255], "value": [45,255]},
            "limits": ["Screen pixel coverage is not geographic territory area", "Camera zoom/pan alters screen fractions", "Colored badges, yellow glow and occasional subtitles can contaminate ROI samples", "Opacity cannot be identified uniquely from composited footage", "No inferred camera geographic coordinates or false precision"],
        },
        "content_warning": "Visible phone title says '만약 지금 한국이 북한을 공격한다면?': hypothetical modern-war animation, not documentary historical Korean War.",
        "producer_full_visual_review_claimed": False,
        "visual_review_pending": "Inspect all 30 chronological contact sheets covering every decoded frame; inspect full-size selected boundary/camera stills separately",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "input_reencoded": False,
        "input_modified": False,
        "required_temp_only_files": 0,
    }
    save_json(destination / "DECODE_REPORT.json", report)
    save_json(destination / "CONTACT_SHEETS_INDEX.json", {"input_sha256": input_sha, "status": "PASS", "decoded_frames": len(frame_rows), "sheets": sheets})
    print(json.dumps({"status": report["status"], "frames": len(frame_rows), "contact_sheets": len(sheets), "blank_frames": report["black_or_blank_frames"], "elapsed_seconds": report["elapsed_seconds"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
