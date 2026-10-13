#!/usr/bin/env python3
"""Read-only, full-video verification of the two explicitly authorized inputs.

All RGB frames are decoded once and compared with the preserved audit. Existing
contact sheets and their visual review remain valid only when every RGB hash and
presentation timestamp agrees. No source MP4 is rewritten or re-encoded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "reference-reproduction-v1"
EXPECTED = {
    "reference": "5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6",
    "candidate": "a9dd5e0280d302528c7bf68b7768593fe0f1820649a657e29f593ecab69ed7ba",
}
START = 5.181813
SAMPLE_TIMES = [0, .5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 149 / 30]
MAP_CROP = [0, 211, 1080, 2131]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_exact(stream, count):
    chunks = []
    while count:
        data = stream.read(count)
        if not data:
            break
        chunks.append(data)
        count -= len(data)
    return b"".join(chunks)


def video_metadata(path):
    cmd = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
    metadata = json.loads(subprocess.check_output(cmd))
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries", "frame=best_effort_timestamp_time,pts_time", "-of", "json", str(path)]
    times = json.loads(subprocess.check_output(cmd))["frames"]
    return metadata, [float(t["best_effort_timestamp_time"]) for t in times]


def screen_metrics(image):
    sample = image.resize((270, 480), Image.Resampling.BOX)
    rgb, hsv = np.asarray(sample), np.asarray(sample.convert("HSV"))
    # This is a deliberately central map ROI: no player title or bottom account
    # chrome, but badges may still contaminate screen fractions. Not land area.
    rgb, hsv = rgb[70:390, 38:225], hsv[70:390, 38:225]
    h, s, v = (hsv[:, :, i] for i in range(3))
    orange = (h < 30) & (s > 115) & (v > 60)
    purple = (h >= 170) & (h <= 225) & (s > 90) & (v > 45)
    answer = {}
    for name, mask in [("orange", orange), ("purple", purple)]:
        answer[name] = {"screen_fraction": round(float(mask.mean()), 6), "median_rgb": np.median(rgb[mask], axis=0).tolist() if mask.any() else None}
    luma = rgb @ np.asarray([.2126, .7152, .0722])
    answer["mean_luma"] = round(float(luma.mean()), 5)
    answer["rgb_standard_deviation"] = round(float(rgb.std()), 5)
    answer["blank_flag"] = bool(luma.mean() < 2 or rgb.std() < .5)
    answer["limitations"] = ["Screen fractions are not geographic area", "Badges and subtitles may affect RGB samples", "Camera pose changes screen fractions"]
    return answer


def visible_front_samples(image):
    """Sample only observed orange-above/purple-below ownership interfaces.

    RGB gating suppresses flag-red/blue, white badges and phone chrome. Where a
    badge occludes the interface, no point is invented. This screen-space trace
    is not a surveyed or independently georeferenced territorial boundary.
    """
    rgb = np.asarray(image.convert("RGB")).astype(np.float32)
    r, g, b = (rgb[:, :, i] for i in range(3))
    orange = (r > 75) & (r < 230) & (g > 14) & (g < 140) & (b < 90) & (b < g * .8) & (r > g * 1.5)
    purple = (b > 120) & (r > 35) & (r < 155) & (g < 110) & (b > r * 1.3) & (b > g * 1.5)
    points = []
    for x in range(200, 1040, 8):
        oc = orange[:, x - 5:x + 6].mean(axis=1)
        pc = purple[:, x - 5:x + 6].mean(axis=1)
        co, cp = np.r_[0, np.cumsum(oc)], np.r_[0, np.cumsum(pc)]
        ys = np.arange(580, 1150)
        oa = (co[ys - 4] - co[ys - 32]) / 28
        pb = (cp[ys + 32] - cp[ys + 4]) / 28
        score = oa * pb
        best = int(score.argmax())
        if score[best] > .24:
            points.append({"x": x, "y": int(ys[best]), "color_adjacency_score": round(float(score[best]), 4)})
    return {"coordinate_space": "SOURCE_MAP_CROP_SCREEN_PIXELS", "points": points, "method": "11px horizontal mean; orange support 4..32px above and purple support 4..32px below; maximum product in audited central frontier ROI", "missing_occluded_points_interpolated": False, "geographic_coordinates_claimed": False, "limits": ["Badges can occlude the true front", "Candidates outside the audited 580..1150px y band are omitted", "Color adjacency is not proof of surveyed territorial control", "Final geographic registration must reuse an independently measured coastline transform"]}


def decode_one(role, source, destination):
    source = source.resolve()
    before = digest(source)
    if before != EXPECTED[role]:
        raise RuntimeError(f"Unexpected {role} input identity: {before}")
    metadata, pts = video_metadata(source)
    video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    width, height = video["width"], video["height"]
    expected_dimensions, count = ((1080, 2520), 958) if role == "reference" else ((1080, 1920), 150)
    if (width, height) != expected_dimensions or len(pts) != count:
        raise RuntimeError(f"Unexpected {role} shape or frame count")
    if any(b <= a for a, b in zip(pts, pts[1:])):
        raise RuntimeError("Nonchronological presentation timestamps")
    prior_path = OLD / "evidence" / ("reference_audit" if role == "reference" else "candidate_audit") / "FRAMES.json"
    prior = json.loads(prior_path.read_text())
    selected = {min(range(len(pts)), key=lambda i: abs(pts[i] - (START + relative if role == "reference" else relative))): relative for relative in SAMPLE_TIMES}
    destination.mkdir(parents=True, exist_ok=True)
    save_json(destination / "FFPROBE.json", metadata)
    error_path = destination / "DECODE_STDERR.txt"
    rows, samples, mismatch = [], [], []
    command = ["ffmpeg", "-v", "error", "-threads", "2", "-i", str(source), "-map", "0:v:0", "-an", "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    started = time.monotonic()
    with error_path.open("wb") as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            for frame in range(count):
                raw = read_exact(process.stdout, width * height * 3)
                if len(raw) != width * height * 3:
                    raise RuntimeError(f"Incomplete {role} frame {frame}")
                rgb_sha = hashlib.sha256(raw).hexdigest()
                agrees = rgb_sha == prior[frame]["decoded_rgb_sha256"] and abs(pts[frame] - prior[frame]["pts_seconds"]) < 1e-6
                if not agrees:
                    mismatch.append(frame)
                image = Image.frombytes("RGB", (width, height), raw)
                frame_map = image.crop(tuple(MAP_CROP)) if role == "reference" else image
                metrics = screen_metrics(frame_map)
                rows.append({"frame": frame, "pts_seconds": pts[frame], "decoded_rgb_sha256": rgb_sha, "matches_preserved_rgb_and_pts": agrees, "screen_metrics": metrics})
                if frame in selected:
                    relative = selected[frame]
                    name = f"{role.upper()}_REL_{relative:06.3f}_FRAME_{frame:03d}.png"
                    frame_map.save(destination / name, optimize=True)
                    samples.append({"relative_requested_seconds": relative, "frame": frame, "actual_pts_seconds": pts[frame], "png": name, "png_sha256": digest(destination / name), "decoded_rgb_sha256": rgb_sha, "visible_front_screen_samples": visible_front_samples(frame_map)})
                if frame % 100 == 0 or frame == count - 1:
                    print(json.dumps({"role": role, "decoded": frame + 1, "prior_mismatches": len(mismatch)}), flush=True)
            extra = process.stdout.read(1)
            code = process.wait()
            if extra or code:
                raise RuntimeError(f"Unexpected {role} trailing RGB or FFmpeg exit {code}")
        except BaseException:
            process.kill()
            process.wait()
            raise
    after = digest(source)
    blank = [r["frame"] for r in rows if r["screen_metrics"]["blank_flag"]]
    report = {"schema": "QUALITY_REWORK_FULL_INPUT_DECODE_V2", "role": role, "status": "FULL_DECODE_IDENTICAL_TO_PRESERVED_AUDIT" if not mismatch and not blank and before == after else "FAIL", "source": str(source), "source_sha256_before": before, "source_sha256_after": after, "input_modified": False, "input_reencoded": False, "width": width, "height": height, "duration_seconds": float(metadata["format"]["duration"]), "frames": count, "strictly_chronological_pts": True, "prior_audit_frames": len(prior), "prior_frame_mismatches": mismatch, "blank_frames": blank, "decode_stderr_bytes": error_path.stat().st_size, "elapsed_seconds": round(time.monotonic() - started, 3), "command": command, "samples": samples, "visual_quality_pass_claimed": False, "required_temp_only": 0}
    save_json(destination / "FRAMES.json", rows)
    save_json(destination / "REPORT.json", report)
    if report["status"] == "FAIL" or report["decode_stderr_bytes"]:
        raise RuntimeError(f"{role} full input decode failed")
    return report


def compare_samples(reference, candidate, destination):
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 22)
    outputs = []
    for index, (left, right) in enumerate(zip(reference["samples"], candidate["samples"])):
        a = Image.open(destination / "reference" / left["png"]).convert("RGB")
        b = Image.open(destination / "candidate" / right["png"]).convert("RGB")
        figure = Image.new("RGB", (2184, 1990), "#111111")
        figure.paste(a, (0, 70))
        figure.paste(b, (1104, 70))
        draw = ImageDraw.Draw(figure)
        draw.text((18, 12), f"REFERENCE target rel {left['relative_requested_seconds']:.3f}s / PTS {left['actual_pts_seconds']:.6f}s", font=font, fill="white")
        draw.text((1122, 12), f"PRESERVED CANDIDATE / frame {right['frame']} / {right['actual_pts_seconds']:.6f}s", font=font, fill="white")
        name = f"INPUT_COMPARE_{index:02d}_REL_{left['relative_requested_seconds']:06.3f}.png"
        figure.save(destination / name, optimize=True)
        outputs.append({"file": name, "sha256": digest(destination / name), "reference": left, "candidate": right, "comparison": "Native resolution, same selected time; reference UI is retained in its source crop and not mistaken for content"})
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=OLD / "data/REFERENCE_65379_COMPRESSED.mp4")
    parser.add_argument("--candidate", type=Path, default=OLD / "public-review/WORLD_ENGINE_REFERENCE_65379_REPRODUCTION_5S.mp4")
    parser.add_argument("--output", type=Path, default=HERE / "evidence/input_audit")
    args = parser.parse_args()
    destination = args.output.resolve()
    reference = decode_one("reference", args.reference, destination / "reference")
    candidate = decode_one("candidate", args.candidate, destination / "candidate")
    comparisons = compare_samples(reference, candidate, destination)
    prior_visual = json.loads((OLD / "evidence/REFERENCE_AUDIT_SUMMARY.json").read_text())
    report = {"schema": "QUALITY_REWORK_INPUT_BINDING_V2", "status": "PASS", "reference": reference, "candidate": candidate, "exact_selected_interval_seconds": [START, START + 5], "time_series_comparisons": comparisons, "whole_reference_visual_review": {"method": "PRESERVED_ACTUAL_EVERY_FRAME_VISUAL_REVIEW_REBOUND_BY_FRESH_FULL_RGB_AND_PTS_EQUALITY", "prior_record": "recovery/reference-reproduction-v1/evidence/REFERENCE_AUDIT_SUMMARY.json", "chronological_frame_coverage": prior_visual["chronologicalVisualInspection"], "reference_timeline": prior_visual["timeline"], "new_full_decode_frames": reference["frames"], "all_previous_frame_pixels_confirmed": True, "native_video_playback_claimed": False}, "semantic_mode": "COUNTERFACTUAL_MODERN_REFERENCE_NOT_HISTORICAL_KOREAN_WAR", "quality_pass_claimed": False, "inputs_modified": False, "required_temp_only": 0}
    save_json(destination / "REPORT.json", report)
    print(json.dumps({"status": "PASS", "reference_frames": reference["frames"], "candidate_frames": candidate["frames"], "time_series_comparisons": len(comparisons)}), flush=True)


if __name__ == "__main__":
    main()
