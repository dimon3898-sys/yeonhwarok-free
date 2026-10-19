#!/usr/bin/env python3
"""Compare newly captured frames and decoded movies without loading a full movie.

The input reports are renderer evidence, not proof of encoded-movie equality.
Both evidence streams and both decoded MP4s are independently compared.  No
historical, NVIDIA, perceptual-quality, or FINAL approval is inferred here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
from PIL import Image, ImageDraw, ImageFont


EXPECTED = {"width": 1080, "height": 1920, "fps": "30/1", "frames": 150, "seconds": 5.0}
CHECKPOINTS = {0: "CAMERA", 30: "TERRITORY", 75: "FRONTIER", 120: "LIGHTING", 149: "FINAL"}
STATE_FIELDS = {
    "camera_bounds": ("cameraBounds",),
    "camera_rotation": ("rotationDegrees",),
    "camera_full_state": ("diagnostic", "camera"),
    "scalar_territory": ("control",),
    "territory_material_and_state": ("diagnostic", "territory"),
    "frontier_light": ("diagnostic", "frontierLight"),
    "terrain_material": ("diagnostic", "terrain"),
    "presentation": ("presentation",),
    "national_units": ("units",),
    "protection": ("protection",),
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def at(value, parts):
    for part in parts:
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value


def first_difference(a, b, path="$"):
    if type(a) is not type(b):
        # JSON numbers may be serialized as 0 or 0.0 without a numeric change.
        if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool) and a == b:
            return None
        return {"path": path, "reason": "type_or_value", "original": safe_difference_value(a), "reproduction": safe_difference_value(b)}
    if isinstance(a, dict):
        if set(a) != set(b):
            return {"path": path, "reason": "keys", "onlyOriginal": sorted(set(a) - set(b)), "onlyReproduction": sorted(set(b) - set(a))}
        for key in a:
            difference = first_difference(a[key], b[key], f"{path}.{key}")
            if difference:
                return difference
    elif isinstance(a, list):
        if len(a) != len(b):
            return {"path": path, "reason": "length", "original": len(a), "reproduction": len(b)}
        for index, (left, right) in enumerate(zip(a, b)):
            difference = first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
    elif a != b:
        return {"path": path, "reason": "value", "original": safe_difference_value(a), "reproduction": safe_difference_value(b)}
    return None


def safe_difference_value(value):
    """Keep comparison reports small; never embed whole scene/state payloads."""
    if isinstance(value, (dict, list)) or isinstance(value, str) and len(value) > 256:
        return {"type": type(value).__name__, "length": len(value), "canonicalSha256": canonical_hash(value)}
    return value


def probe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-show_frames", "-show_entries", "frame=media_type,stream_index,best_effort_timestamp,best_effort_timestamp_time,pkt_duration,pkt_duration_time,pict_type,width,height", "-of", "json", str(path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    videos = [row for row in data["streams"] if row.get("codec_type") == "video"]
    if len(videos) != 1:
        raise ValueError(f"Expected exactly one video stream: {path.name}")
    video = videos[0]
    frames = [row for row in data.get("frames", []) if row.get("media_type") == "video"]
    pts = [row.get("best_effort_timestamp_time") for row in frames]
    checks = {
        "h264": video.get("codec_name") == "h264",
        "resolution": [video.get("width"), video.get("height")] == [EXPECTED["width"], EXPECTED["height"]],
        "fps": video.get("avg_frame_rate") == EXPECTED["fps"],
        "decodedFrameMetadataCount": len(frames) == EXPECTED["frames"],
        "duration": abs(float(video.get("duration", "nan")) - EXPECTED["seconds"]) < 1e-9,
        "silent": not any(row.get("codec_type") == "audio" for row in data["streams"]),
        "framePts": len(pts) == EXPECTED["frames"] and all(t is not None and abs(float(t) - i / 30) < 1e-6 for i, t in enumerate(pts)),
    }
    return {"checks": checks, "streams": data["streams"], "format": {key: value for key, value in data["format"].items() if key != "filename"}, "frames": frames, "framePtsSeconds": pts}


def decoder(path: Path):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "1", "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-vsync", "0", "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE), command


def read_frame(stream, size: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < size:
        block = stream.read(size - len(buffer))
        if not block:
            break
        buffer.extend(block)
    if buffer and len(buffer) != size:
        raise ValueError(f"Truncated decoded frame: {len(buffer)} of {size} bytes")
    return bytes(buffer)


def compare_report(original: dict, reproduction: dict):
    left, right = original.get("frames", []), reproduction.get("frames", [])
    order_left = [row.get("frame") for row in left]
    order_right = [row.get("frame") for row in right]
    result = {"originalFrames": len(left), "reproductionFrames": len(right), "originalFrameOrderValid": order_left == list(range(150)), "reproductionFrameOrderValid": order_right == list(range(150)), "rawRgbaMatches": 0, "pngMatches": 0, "stateFields": {key: {"matches": 0, "missing": [], "firstDifference": None} for key in STATE_FIELDS}, "firstRawMismatch": None, "firstPngMismatch": None}
    rows = []
    for index, (a, b) in enumerate(zip(left, right)):
        raw = isinstance(a.get("raw_rgba_sha256"), str) and a.get("raw_rgba_sha256") == b.get("raw_rgba_sha256")
        png = isinstance(a.get("png_sha256"), str) and a.get("png_sha256") == b.get("png_sha256")
        result["rawRgbaMatches"] += int(raw)
        result["pngMatches"] += int(png)
        if not raw and result["firstRawMismatch"] is None:
            result["firstRawMismatch"] = index
        if not png and result["firstPngMismatch"] is None:
            result["firstPngMismatch"] = index
        state_matches = {}
        for name, parts in STATE_FIELDS.items():
            exists_a, va = at(a, parts)
            exists_b, vb = at(b, parts)
            if not exists_a or not exists_b:
                result["stateFields"][name]["missing"].append({"frame": index, "original": not exists_a, "reproduction": not exists_b})
                state_matches[name] = False
                continue
            difference = first_difference(va, vb)
            equal = difference is None
            state_matches[name] = equal
            if equal:
                result["stateFields"][name]["matches"] += 1
            elif result["stateFields"][name]["firstDifference"] is None:
                result["stateFields"][name]["firstDifference"] = {"frame": index, **difference}
        rows.append({"frame": index, "rawRgbaMatch": raw, "pngMatch": png, "allStatesMatch": all(state_matches.values()), **state_matches})
    result["all150RawRgbaEqual"] = result["rawRgbaMatches"] == 150 and result["originalFrameOrderValid"] and result["reproductionFrameOrderValid"]
    result["all150PngEqual"] = result["pngMatches"] == 150 and result["originalFrameOrderValid"] and result["reproductionFrameOrderValid"]
    result["all150StatesEqual"] = all(row["matches"] == 150 and not row["missing"] for row in result["stateFields"].values()) and result["originalFrameOrderValid"] and result["reproductionFrameOrderValid"]
    return result, rows


def write_contact_sheet(checkpoints: dict, output: Path):
    scale = 3
    tile_width, tile_height = 1080 // scale, 1920 // scale
    header_height, row_header = 52, 40
    sheet = Image.new("RGB", (3 * tile_width, header_height + len(checkpoints) * (tile_height + row_header)), "#111820")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 21)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    for col, label in enumerate(["ORIGINAL 65422", "NEW REPRODUCTION", "ABSOLUTE RGB DIFF x4"]):
        draw.text((col * tile_width + 10, 15), label, font=small, fill="white")
    for row_number, (frame, (a, b)) in enumerate(sorted(checkpoints.items())):
        top = header_height + row_number * (tile_height + row_header)
        delta = np.minimum(np.abs(a.astype(np.int16) - b.astype(np.int16)) * 4, 255).astype(np.uint8)
        changed = int(np.any(a != b, axis=2).sum())
        label = f"FRAME {frame:03d} / {frame / 30:.3f}s / {CHECKPOINTS[frame]} / changed pixels: {changed}"
        draw.text((10, top + 9), label, font=font, fill="#f1db9b")
        for col, data in enumerate([a, b, delta]):
            thumbnail = Image.fromarray(data).resize((tile_width, tile_height), Image.Resampling.LANCZOS)
            sheet.paste(thumbnail, (col * tile_width, top + row_header))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-mp4", type=Path, required=True)
    parser.add_argument("--reproduction-mp4", type=Path, required=True)
    parser.add_argument("--original-report", type=Path, required=True)
    parser.add_argument("--reproduction-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--comparison-png", type=Path, required=True)
    args = parser.parse_args()
    for path in [args.original_mp4, args.reproduction_mp4, args.original_report, args.reproduction_report]:
        if not path.is_file():
            parser.error(f"Input does not exist: {path}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "ALL_150_FRAME_COMPARISON.json"
    if report_path.exists() or args.comparison_png.exists():
        parser.error("Refusing to overwrite existing comparison output; use a new output directory and PNG path")
    original_probe = probe(args.original_mp4)
    reproduction_probe = probe(args.reproduction_mp4)
    original = json.loads(args.original_report.read_text())
    reproduction = json.loads(args.reproduction_report.read_text())
    source_comparison, source_rows = compare_report(original, reproduction)
    processes = []
    commands = []
    for movie in [args.original_mp4, args.reproduction_mp4]:
        process, command = decoder(movie)
        processes.append(process)
        commands.append(command)
    size = EXPECTED["width"] * EXPECTED["height"] * 3
    frame_rows, checkpoints = [], {}
    squared_error_total, absolute_error_total, changed_pixels_total, components_total = 0, 0, 0, 0
    max_difference, first_mismatch, decode_error = 0, None, None
    try:
        for frame in range(151):
            values = [read_frame(process.stdout, size) for process in processes]
            if not values[0] and not values[1]:
                break
            if not values[0] or not values[1]:
                raise ValueError(f"Different decoded frame count at frame {frame}")
            if frame >= 150:
                raise ValueError("Movie contains more than 150 decoded frames")
            a, b = [np.frombuffer(value, dtype=np.uint8).reshape(1920, 1080, 3) for value in values]
            delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
            absolute_error = int(delta.sum(dtype=np.int64))
            squared_error = int(np.square(delta, dtype=np.int32).sum(dtype=np.int64))
            changed = int(np.any(delta != 0, axis=2).sum())
            max_delta = int(delta.max())
            equal = values[0] == values[1]
            if not equal and first_mismatch is None:
                first_mismatch = frame
            mse = squared_error / size
            psnr = None if mse == 0 else 10 * math.log10(255 * 255 / mse)
            frame_rows.append({"frame": frame, "originalDecodedRgbSha256": hashlib.sha256(values[0]).hexdigest(), "reproductionDecodedRgbSha256": hashlib.sha256(values[1]).hexdigest(), "decodedRgbEqual": equal, "maeRgb8": absolute_error / size, "maxAbsoluteChannelDifference": max_delta, "changedPixels": changed, "changedPixelFraction": changed / (1080 * 1920), "mseRgb8": mse, "psnrDb": psnr, "psnrInfinite": mse == 0, **(source_rows[frame] if frame < len(source_rows) else {})})
            squared_error_total += squared_error
            absolute_error_total += absolute_error
            changed_pixels_total += changed
            components_total += size
            max_difference = max(max_difference, max_delta)
            if frame in CHECKPOINTS:
                checkpoints[frame] = (a.copy(), b.copy())
    except Exception as exc:
        decode_error = f"{type(exc).__name__}: {exc}"
    finally:
        for process in processes:
            if decode_error and process.poll() is None:
                process.terminate()
        decoder_results = []
        for process in processes:
            stderr = process.stderr.read().decode("utf-8", errors="replace")
            code = process.wait(timeout=30)
            decoder_results.append({"exitCode": code, "stderr": stderr[:4000]})
    all_decode_equal = len(frame_rows) == 150 and first_mismatch is None and not decode_error and all(row["exitCode"] == 0 for row in decoder_results)
    probe_equal = all(original_probe["checks"].values()) and all(reproduction_probe["checks"].values()) and original_probe["framePtsSeconds"] == reproduction_probe["framePtsSeconds"]
    movie_hashes = [digest(args.original_mp4), digest(args.reproduction_mp4)]
    exact_reproduction = all_decode_equal and probe_equal and source_comparison["all150RawRgbaEqual"] and source_comparison["all150StatesEqual"]
    report = {
        "schema": "WORLD_ENGINE_EXACT_65422_COMPARISON_V1", "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "Original counterfactual 65422 scene; actual new software render compared with original software-render evidence and both complete decoded MP4s",
        "status": "REPRODUCTION_PIXEL_EXACT_SOFTWARE" if exact_reproduction else "REPRODUCTION_NEEDS_REWORK",
        "original": {"file": args.original_mp4.name, "sha256": movie_hashes[0], "bytes": args.original_mp4.stat().st_size, "rendererReportSha256": digest(args.original_report), "probe": original_probe},
        "reproduction": {"file": args.reproduction_mp4.name, "sha256": movie_hashes[1], "bytes": args.reproduction_mp4.stat().st_size, "rendererReportSha256": digest(args.reproduction_report), "probe": reproduction_probe},
        "encodedFileByteEqual": movie_hashes[0] == movie_hashes[1], "technicalAndPtsContractPass": probe_equal,
        "sourceCaptureAndStates": source_comparison,
        "decodedMovie": {"frameCount": len(frame_rows), "all150FramesPixelEqual": all_decode_equal, "firstDifferingFrame": first_mismatch, "meanAbsoluteRgb8Difference": absolute_error_total / components_total if components_total else None, "maxAbsoluteChannelDifference": max_difference, "changedPixelsAcrossAllFrames": changed_pixels_total, "meanSquaredRgb8Difference": squared_error_total / components_total if components_total else None, "decodeError": decode_error, "decoderResults": decoder_results},
        "comparisonCheckpoints": sorted(checkpoints), "comparisonPng": {"file": args.comparison_png.name},
        "audio": {"originalHasAudio": not original_probe["checks"]["silent"], "reproductionHasAudio": not reproduction_probe["checks"]["silent"], "originalSilentContractPreserved": original_probe["checks"]["silent"] and reproduction_probe["checks"]["silent"], "sfxSync": "NOT_APPLICABLE_ORIGINAL_SILENT_NO_AUDIO_ADDED"},
        "nvidiaGpuVerified": False, "userVideoApproved": False, "finalPromotion": False,
        "comparisonMethod": {"pixelFormat": "rgb24", "decodeCommands": commands, "sourceStateFields": {name: ".".join(parts) for name, parts in STATE_FIELDS.items()}, "stateNumericTolerance": 0, "boundedMemory": "One frame per decoder plus five comparison checkpoint pairs; no entire movie frame accumulation", "ffmpegVersion": subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]},
        "frames": frame_rows,
    }
    if len(checkpoints) == len(CHECKPOINTS):
        write_contact_sheet(checkpoints, args.comparison_png)
        report["comparisonPng"]["sha256"] = digest(args.comparison_png)
        report["comparisonPng"]["bytes"] = args.comparison_png.stat().st_size
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    csv_path = args.output_dir / "ALL_150_FRAME_COMPARISON.csv"
    if frame_rows:
        with csv_path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(frame_rows[0]))
            writer.writeheader()
            writer.writerows(frame_rows)
    print(json.dumps({"status": report["status"], "encodedFileByteEqual": report["encodedFileByteEqual"], "sourceRawFramesEqual": source_comparison["rawRgbaMatches"], "sourcePngFramesEqual": source_comparison["pngMatches"], "all150StatesEqual": source_comparison["all150StatesEqual"], "decoded": report["decodedMovie"], "report": str(report_path)}, indent=2))
    return 0 if exact_reproduction else 2


if __name__ == "__main__":
    sys.exit(main())
