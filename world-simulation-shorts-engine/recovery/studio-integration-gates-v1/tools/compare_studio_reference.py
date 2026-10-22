#!/usr/bin/env python3
"""Compare the actual new Studio G1 movie with original 65422, without rendering.

Reuses the preserved exact-reproduction decoder, probe and source-state comparison
algorithm read-only. Writes only a fresh directory in this new gate namespace.
Neither decoded similarity nor raw equality grants visual approval or GPU PASS.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import uniform_filter


HERE = Path(__file__).resolve().parent
NAMESPACE = HERE.parent
ORIGINAL_MOVIE_SHA256 = "f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6"
ORIGINAL_REPORT_SHA256 = "550c1d7db502b91dc94548284ddfb10ff27f8e52cdf7efac7e7df68bfa768656"
CHECKPOINTS = (0, 30, 60, 90, 120)


def load_preserved_algorithm():
    filename = NAMESPACE.parent / "exact-65422-reproduction-v1/tools/compare_150_frames.py"
    spec = importlib.util.spec_from_file_location("_preserved_exact_frame_comparison", filename)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def reject_symlinks(filename: Path):
    for parent in [filename, *filename.parents]:
        if parent.is_symlink():
            raise ValueError("COMPARISON_SYMLINK_PATH_REJECTED")


def fresh_output(filename: Path):
    absolute = filename.absolute()
    reject_symlinks(absolute)
    if not absolute.is_relative_to(NAMESPACE) or absolute == NAMESPACE:
        raise ValueError("COMPARISON_OUTPUT_MUST_BE_NEW_NAMESPACE_CHILD")
    absolute.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    absolute.mkdir(mode=0o700, exist_ok=False)
    return absolute


def source_rows_from_capture(report):
    """Map recorded diagnostic names to the unchanged original comparison contract."""
    result = {**report, "frames": []}
    for row in report["frames"]:
        diagnostic = row["diagnostic"]
        camera = diagnostic["camera"]
        result["frames"].append({**row,
            "cameraBounds": camera.get("bounds", camera.get("camera", {}).get("flatBounds", camera.get("flatBounds"))),
            "rotationDegrees": camera.get("rotationDegrees"),
            "control": row["scalarControl"], "presentation": diagnostic["presentation"]})
    return result


def ssim_rgb_uniform7(a, b):
    """Mean channel SSIM: 7x7 uniform window, sample covariance, range255.

    Uses the valid interior (three pixels cropped), K1=.01 and K2=.03,
    matching the standard uniform-window channel-average SSIM definition.
    Calculation is channel-at-a-time to bound working memory.
    """
    if np.array_equal(a, b):
        return 1.0
    constants = ((.01 * 255) ** 2, (.03 * 255) ** 2)
    scores = []
    for channel in range(3):
        x = a[..., channel].astype(np.float64)
        y = b[..., channel].astype(np.float64)
        ux, uy = uniform_filter(x, size=7), uniform_filter(y, size=7)
        vx = (49 / 48) * (uniform_filter(x * x, size=7) - ux * ux)
        vy = (49 / 48) * (uniform_filter(y * y, size=7) - uy * uy)
        covariance = (49 / 48) * (uniform_filter(x * y, size=7) - ux * uy)
        numerator = (2 * ux * uy + constants[0]) * (2 * covariance + constants[1])
        denominator = (ux * ux + uy * uy + constants[0]) * (vx + vy + constants[1])
        scores.append(float((numerator / denominator)[3:-3, 3:-3].mean(dtype=np.float64)))
    return float(np.mean(scores))


def font(size):
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)


def comparison_images(checkpoints, output, original_name, new_name):
    # These are decoded frames of the two real videos; no map content is drawn.
    width, height, title, row_title = 540, 960, 90, 42
    sheet = Image.new("RGB", (width * 2, title + len(CHECKPOINTS) * (height + row_title)), "#101820")
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), "Original 65422", fill="white", font=font(22))
    draw.text((width + 12, 10), "New Studio G1 / SOFTWARE PREVIEW", fill="white", font=font(19))
    draw.text((12, 46), original_name, fill="#c2cbd5", font=font(13))
    draw.text((width + 12, 46), new_name, fill="#c2cbd5", font=font(13))
    for index, frame in enumerate(CHECKPOINTS):
        top = title + index * (height + row_title)
        draw.text((12, top + 8), f"Frame {frame:03d} / {frame / 30:.0f}s / decoded MP4", fill="#edda9b", font=font(21))
        for column, image in enumerate(checkpoints[frame]):
            sheet.paste(Image.fromarray(image).resize((width, height), Image.Resampling.LANCZOS), (column * width, top + row_title))
    filename = output / "STUDIO_REFERENCE_SIDE_BY_SIDE.png"
    sheet.save(filename, optimize=True)
    tile_width, tile_height, header = 360, 640, 44
    temporal = Image.new("RGB", (tile_width * 5, 2 * (tile_height + header)), "#101820")
    temporal_draw = ImageDraw.Draw(temporal)
    for row, label in enumerate(["Original 65422", "New Studio G1"]):
        for column, frame in enumerate(CHECKPOINTS):
            top = row * (tile_height + header)
            temporal_draw.text((column * tile_width + 8, top + 10), f"{label} / {frame / 30:.0f}s", fill="white", font=font(19))
            temporal.paste(Image.fromarray(checkpoints[frame][row]).resize((tile_width, tile_height), Image.Resampling.LANCZOS),
                           (column * tile_width, top + header))
    temporal_filename = output / "STUDIO_REFERENCE_TEMPORAL_CONTACT.png"
    temporal.save(temporal_filename, optimize=True)
    return [filename, temporal_filename]


def compare(args):
    preserved = load_preserved_algorithm()
    for filename in [args.original_mp4, args.new_mp4, args.original_report, args.capture_report]:
        reject_symlinks(filename)
        if not filename.is_file():
            raise ValueError("COMPARISON_INPUT_MISSING")
    if preserved.digest(args.original_mp4) != ORIGINAL_MOVIE_SHA256:
        raise ValueError("COMPARISON_ORIGINAL_65422_HASH_MISMATCH")
    if preserved.digest(args.original_report) != ORIGINAL_REPORT_SHA256:
        raise ValueError("COMPARISON_ORIGINAL_REPORT_HASH_MISMATCH")
    original = json.loads(args.original_report.read_text())
    capture = json.loads(args.capture_report.read_text())
    if capture.get("schema") != "WORLD_ENGINE_STUDIO_REFERENCE_CAPTURE_V1" or capture.get("status") not in {
            "SOFTWARE_REFERENCE_RAW_MATCH_USER_REVIEW_REQUIRED", "REPRODUCTION_NEEDS_REWORK"}:
        raise ValueError("COMPARISON_FRESH_CAPTURE_NOT_COMPLETED")
    if capture.get("classification") != "SOFTWARE_PREVIEW" or capture.get("newlyRenderedFrames") != 150 or capture.get("reusedFrames") != 0:
        raise ValueError("COMPARISON_FRESH_150_DRAW_EVIDENCE_REQUIRED")
    if capture.get("fullDecode") != "PASS" or capture.get("video", {}).get("sha256") != preserved.digest(args.new_mp4):
        raise ValueError("COMPARISON_NEW_MOVIE_REPORT_HASH_MISMATCH")
    if not args.new_mp4.resolve().is_relative_to(NAMESPACE) or not args.capture_report.resolve().is_relative_to(NAMESPACE):
        raise ValueError("COMPARISON_NEW_CAPTURE_MUST_USE_NEW_NAMESPACE")
    output = fresh_output(args.output_dir)
    original_probe, new_probe = preserved.probe(args.original_mp4), preserved.probe(args.new_mp4)
    source_comparison, source_rows = preserved.compare_report(original, source_rows_from_capture(capture))
    processes, commands = [], []
    for movie in [args.original_mp4, args.new_mp4]:
        process, command = preserved.decoder(movie)
        processes.append(process); commands.append(command)
    size = 1080 * 1920 * 3
    absolute_total = squared_total = changed_total = components_total = 0
    first_mismatch = None
    max_difference = 0
    frame_rows, checkpoints = [], {}
    decode_error, decoder_results = None, []
    try:
        for frame in range(151):
            values = [preserved.read_frame(process.stdout, size) for process in processes]
            if not any(values):
                break
            if not all(values) or frame >= 150:
                raise ValueError("COMPARISON_DECODED_FRAME_COUNT_MISMATCH")
            a, b = [np.frombuffer(value, dtype=np.uint8).reshape(1920, 1080, 3) for value in values]
            delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
            absolute = int(delta.sum(dtype=np.int64))
            squared = int(np.square(delta, dtype=np.int32).sum(dtype=np.int64))
            changed = int(np.any(delta, axis=2).sum())
            maximum = int(delta.max())
            equal = values[0] == values[1]
            if not equal and first_mismatch is None:
                first_mismatch = frame
            mse = squared / size
            row = {"frame": frame, "timeSeconds": frame / 30,
                "originalDecodedRgbSHA256": hashlib.sha256(values[0]).hexdigest(),
                "newDecodedRgbSHA256": hashlib.sha256(values[1]).hexdigest(),
                "decodedRgbEqual": equal, "maeRgb8": absolute / size,
                "mseRgb8": mse, "psnrDb": None if mse == 0 else 10 * math.log10(255 * 255 / mse),
                "psnrInfinite": mse == 0, "ssimRgbUniform7": ssim_rgb_uniform7(a, b),
                "maxAbsoluteChannelDifference": maximum, "changedPixels": changed,
                "changedPixelFraction": changed / (1080 * 1920), **source_rows[frame]}
            frame_rows.append(row)
            absolute_total += absolute; squared_total += squared; changed_total += changed; components_total += size
            max_difference = max(max_difference, maximum)
            if frame in CHECKPOINTS:
                checkpoints[frame] = (a.copy(), b.copy())
    except Exception as error:
        decode_error = type(error).__name__ + ": " + str(error)
    finally:
        for process in processes:
            if decode_error and process.poll() is None:
                process.terminate()
        for process in processes:
            stderr = process.stderr.read().decode("utf8", errors="replace")
            try:
                code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill(); code = process.wait(timeout=5)
            decoder_results.append({"exitCode": code, "stderr": stderr[:4000]})
    movie_equal = len(frame_rows) == 150 and first_mismatch is None and decode_error is None and all(row["exitCode"] == 0 for row in decoder_results)
    technical = all(original_probe["checks"].values()) and all(new_probe["checks"].values()) and original_probe["framePtsSeconds"] == new_probe["framePtsSeconds"]
    source_equal = source_comparison["all150RawRgbaEqual"] and source_comparison["all150PngEqual"] and source_comparison["all150StatesEqual"]
    exact = technical and movie_equal and source_equal
    global_mse = squared_total / components_total if components_total else None
    report = {"schema": "WORLD_ENGINE_STUDIO_REFERENCE_COMPARISON_V1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(), "classification": "SOFTWARE_PREVIEW",
        "status": "SOFTWARE_PIXEL_MATCH_USER_REVIEW_REQUIRED" if exact else "REPRODUCTION_NEEDS_REWORK",
        "scope": "Actual authenticated Studio counterfactual source-regression capture; not historical80s, NVIDIA, or quality approval",
        "jobId": capture["jobId"], "requestSHA256": capture["requestSHA256"],
        "executionReceiptSHA256": capture["executionReceiptSHA256"], "controllerTraceStages": capture["controllerTraceStages"],
        "original": {"file": args.original_mp4.name, "sha256": preserved.digest(args.original_mp4), "bytes": args.original_mp4.stat().st_size,
            "rendererReportSHA256": preserved.digest(args.original_report), "probe": original_probe},
        "newStudio": {"file": args.new_mp4.name, "sha256": preserved.digest(args.new_mp4), "bytes": args.new_mp4.stat().st_size,
            "rendererReportSHA256": preserved.digest(args.capture_report), "probe": new_probe},
        "encodedFileByteEqual": preserved.digest(args.original_mp4) == preserved.digest(args.new_mp4),
        "technicalAndPTSContractPass": technical, "sourceCaptureAndStates": source_comparison,
        "decodedMovie": {"frameCount": len(frame_rows), "all150FramesPixelEqual": movie_equal, "firstDifferingFrame": first_mismatch,
            "meanAbsoluteRgb8Difference": absolute_total / components_total if components_total else None,
            "meanSquaredRgb8Difference": global_mse, "psnrDb": None if global_mse in (None, 0) else 10 * math.log10(255 * 255 / global_mse),
            "psnrInfinite": global_mse == 0, "meanSSIMRgbUniform7": float(np.mean([row["ssimRgbUniform7"] for row in frame_rows])) if frame_rows else None,
            "maxAbsoluteChannelDifference": max_difference, "changedPixelsAcrossAllFrames": changed_total,
            "decodeError": decode_error, "decoderResults": decoder_results},
        "audio": {"originalSilent": original_probe["checks"]["silent"], "newSilent": new_probe["checks"]["silent"],
                  "sfxSync": "NOT_APPLICABLE_ORIGINAL_SILENT_NO_AUDIO_ADDED"},
        "comparisonMethod": {"pixelFormat": "rgb24", "stateNumericTolerance": 0,
            "ssim": {"channels": "RGB averaged", "window": "7x7 uniform", "covariance": "sample49/48", "dataRange": 255, "K1": .01, "K2": .03, "borderCropPixels": 3},
            "decoderCommands": [[Path(command[0]).name, *[Path(item).name if item in (str(args.original_mp4), str(args.new_mp4)) else item for item in command[1:]]] for command in commands],
            "boundedMemory": "Two current decoded frames plus five checkpoint pairs; no full movie accumulation",
            "preservedComparisonAlgorithmSHA256": preserved.digest(NAMESPACE.parent / "exact-65422-reproduction-v1/tools/compare_150_frames.py")},
        "comparisonCheckpoints": sorted(checkpoints), "frames": frame_rows,
        "nvidiaGpuVerified": False, "userVideoApproved": False, "visualQualityApproved": False, "finalPromotion": False}
    images = comparison_images(checkpoints, output, args.original_mp4.name, args.new_mp4.name) if len(checkpoints) == 5 else []
    report["comparisonImages"] = [{"file": filename.name, "sha256": preserved.digest(filename), "bytes": filename.stat().st_size} for filename in images]
    report_file = output / "STUDIO_REFERENCE_ALL_150_FRAME_COMPARISON.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    csv_file = output / "STUDIO_REFERENCE_ALL_150_FRAME_COMPARISON.csv"
    if frame_rows:
        with csv_file.open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(frame_rows[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(frame_rows)
    sums_files = [report_file, csv_file, *images]
    (output / "SHA256SUMS").write_text("".join(preserved.digest(filename) + "  " + filename.name + "\n" for filename in sums_files if filename.is_file()))
    return report, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("original-mp4", "new-mp4", "original-report", "capture-report", "output-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    report, output = compare(parser.parse_args())
    print(json.dumps({"status": report["status"], "output": str(output),
        "sourceRawFramesEqual": report["sourceCaptureAndStates"]["rawRgbaMatches"],
        "sourcePNGFramesEqual": report["sourceCaptureAndStates"]["pngMatches"],
        "all150StatesEqual": report["sourceCaptureAndStates"]["all150StatesEqual"],
        "decoded": report["decodedMovie"]}, indent=2))
    return 0 if report["status"] == "SOFTWARE_PIXEL_MATCH_USER_REVIEW_REQUIRED" else 2


if __name__ == "__main__":
    sys.exit(main())
