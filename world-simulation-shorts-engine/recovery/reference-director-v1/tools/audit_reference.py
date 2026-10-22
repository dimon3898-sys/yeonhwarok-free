#!/usr/bin/env python3
"""Verify supplied reference evidence without publishing or modifying the source."""
import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw


def load_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def require(condition, label):
    if not condition:
        raise ValueError(label)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.input_dir
    target = json.loads((evidence / "REFERENCE_DIRECTOR_TARGET_V1.json").read_text())
    expected_sha = target["reference"]["sha256"]
    source_sha = sha(args.video)
    require(source_sha == expected_sha, "REFERENCE_FILE_SHA_MISMATCH")
    logs = load_csv(evidence / "REFERENCE_FRAME_LOG_635.csv")
    plan = load_csv(evidence / "DIRECTOR_FRAME_PLAN_546.csv")
    camera = load_csv(evidence / "data/camera_motion_estimates.csv")
    hero = load_csv(evidence / "data/hero_pin_screen_track.csv")
    boundary = load_csv(evidence / "data/boundary_glow_screen_estimates.csv")
    require([int(r["frame_0_based"]) for r in logs] == list(range(635)), "REFERENCE_LOG_INDEX_GAP")
    require([int(r["frame"]) for r in camera] == list(range(575)), "CAMERA_ESTIMATE_INDEX_GAP")
    require([int(r["frame"]) for r in hero] == list(range(347, 575)), "HERO_ESTIMATE_INDEX_GAP")
    require([int(r["frame"]) for r in boundary] == list(range(457, 575)), "BOUNDARY_ESTIMATE_INDEX_GAP")
    for row in hero:
        require(abs(float(row["tip_u"]) - float(row["tip_x_source"]) / 822) < 1e-12, "HERO_U_NORMALIZATION")
        require(abs(float(row["tip_v"]) - (float(row["tip_y_source"]) - 160) / 1464) < 1e-12, "HERO_V_NORMALIZATION")
    require([int(r["core_frame"]) for r in plan] == list(range(546)), "CORE_INDEX_GAP")
    require([int(r["reference_frame"]) for r in plan] == list(range(29, 575)), "REFERENCE_PLAN_INDEX_GAP")
    windows = target["reviewWindows"]
    hero_samples = {r["frame"]: r["scale"] for r in next(e for e in target["events"] if e["id"] == "hero_pin")["sizeSamples"]}
    sizes = Counter()
    plan_errors = []
    for row in plan:
        f = int(row["reference_frame"])
        window = next(w for w in windows if w["sourceFrameRange"][0] <= f < w["sourceFrameRange"][1])
        sizes[row["review_window"]] += 1
        if row["review_window"] != window["id"] or int(row["local_output_frame"]) != f - window["sourceFrameRange"][0]:
            plan_errors.append({"frame": f, "field": "window_mapping"})
        if abs(float(row["core_sec"]) - (f - 29) / 30) > 1e-12:
            plan_errors.append({"frame": f, "field": "core_time"})
        reveal = min(1, max(0, (f - 455) / 30))
        if abs(float(row["boundary_design_reveal_fraction"]) - reveal) > 1e-12:
            plan_errors.append({"frame": f, "field": "boundary_reveal"})
        hero_scale = 0 if f < 333 else hero_samples.get(f, 1)
        if abs(float(row["hero_pin_design_scale"]) - hero_scale) > 1e-5:
            plan_errors.append({"frame": f, "field": "hero_pop_scale"})
        for key, starts in (("label_A_design_revealed_graphemes", (289, 293, 297)), ("label_B_design_revealed_graphemes", (311, 315, 319)), ("metric_design_revealed_glyphs", (487, 492, 497))):
            if int(row[key]) != sum(f >= start for start in starts):
                plan_errors.append({"frame": f, "field": key})
        if (row["metric_design_settled"] == "True") != (f >= 505):
            plan_errors.append({"frame": f, "field": "metric_settled"})
    require(not plan_errors, f"PLAN_CONTRACT_MISMATCH:{plan_errors[:3]}")
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(args.video)], text=True))
    stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    require((stream["width"], stream["height"], int(stream["nb_read_frames"])) == (822, 1920, 635), "SOURCE_VIDEO_CONTRACT")
    pts_data = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(args.video)], text=True))
    pts = [float(f["best_effort_timestamp_time"]) for f in pts_data["frames"]]
    require(len(pts) == 635, "PTS_COUNT")
    pts_error = max(abs(time - float(log["pts_seconds"])) for time, log in zip(pts, logs))
    require(pts_error <= 1e-6, "PTS_LOG_MISMATCH")
    keys = {30, 170, 270, 332, 350, 390, 420, 455, 485, 505, 540, 574}
    args.private_output.mkdir(parents=True, exist_ok=True)
    # Only requested keyframes are retained privately. Never encode a new movie
    # from these images or publish the user-supplied source through this tool.
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(args.video), "-map", "0:v:0", "-vsync", "0", "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    width, height = 822, 1920
    frame_bytes = width * height * 3
    mismatch = []
    hashes = []
    kept = {}
    frame_index = 0
    while True:
        data = bytearray()
        while len(data) < frame_bytes:
            chunk = proc.stdout.read(frame_bytes - len(data))
            if not chunk:
                break
            data.extend(chunk)
        if not data:
            break
        require(len(data) == frame_bytes, "TRUNCATED_DECODE_FRAME")
        digest = hashlib.sha256(data).hexdigest()
        hashes.append(digest)
        if frame_index >= len(logs) or digest != logs[frame_index]["decoded_pixel_sha256"]:
            mismatch.append(frame_index)
        if frame_index in keys:
            image = Image.frombytes("RGB", (width, height), bytes(data), "raw", "BGR").crop((0, 160, 822, 1624))
            image.save(args.private_output / f"source_f{frame_index:03d}_map_roi.png")
            kept[frame_index] = image
        frame_index += 1
    stderr = proc.stderr.read().decode("utf-8", "replace")
    require(proc.wait() == 0, "SOURCE_DECODE_FAILED:" + stderr[-1000:])
    require(frame_index == 635, "DECODED_FRAME_COUNT")
    # A decoder-dependent pixel mismatch is recorded rather than reinterpreted
    # as a different source file; the immutable file SHA is checked separately.
    sheet = Image.new("RGB", (4 * 220, 3 * 420), "#111111")
    draw = ImageDraw.Draw(sheet)
    for index, (frame, image) in enumerate(sorted(kept.items())):
        tile = image.copy()
        tile.thumbnail((216, 385))
        x, y = (index % 4) * 220, (index // 4) * 420
        sheet.paste(tile, (x, y + 24))
        draw.text((x + 5, y + 5), f"SOURCE f{frame} / core{frame-29}", fill="white")
    sheet.save(args.private_output / "REFERENCE_12_KEYFRAMES_PRIVATE.jpg", quality=90)
    listed_sheets = sorted({row["contact_sheet"] for row in logs})
    missing_sheets = [name for name in listed_sheets if not (evidence / name).is_file()]
    report = {
        "schema": "WORLD_ENGINE_REFERENCE_INPUT_AUDIT_V1",
        "referenceFileSha256": source_sha,
        "sourceIdentity": "USER_SUPPLIED_RENAMED_FILE_EXACT_SHA_MATCH",
        "sourceFilePublished": False,
        "dimensions": [width, height],
        "nominalFps": "30/1",
        "decodedFrames": frame_index,
        "decodedPixelFormat": "bgr24",
        "decodedPixelHashComparison": {"matched": frame_index - len(mismatch), "mismatchedFrames": mismatch, "method": "FFmpeg sequential BGR24 decode; byte SHA compared with supplied OpenCV decoded_pixel_sha256"},
        "ptsComparison": {"count": len(pts), "maxAbsoluteErrorSeconds": pts_error, "first": pts[0], "last": pts[-1]},
        "coreRange": [29, 575],
        "coreFrames": len(plan),
        "coreDurationSeconds": len(plan) / 30,
        "windowCounts": dict(sizes),
        "planContractErrors": plan_errors,
        "providedTableRows": {"sourceFrameLog": len(logs), "directorPlan": len(plan), "cameraMotionEstimates": len(camera), "heroPinScreenTrack": len(hero), "boundaryGlowScreenEstimates": len(boundary)},
        "excludedSourceRanges": [[0, 29], [575, 635]],
        "sourceAudio": [{k: s.get(k) for k in ("codec_name", "duration", "sample_rate", "channels")} for s in probe["streams"] if s["codec_type"] == "audio"],
        "targetAudio": "SILENT; SOURCE_AUDIO_NOT_ANALYZED_OR_REUSED",
        "zipContentLimits": {"missingReferencedContactSheets": missing_sheets, "allFramesDirectoryPresent": (evidence / "all_frames").is_dir(), "providedEvidenceFiles": sorted(str(p.relative_to(evidence)) for p in (evidence / "evidence").glob("*") if p.is_file()), "missingPackageChecksumFile": not (evidence / "SHA256SUMS").is_file(), "eventZoomSheetsProvided": False},
        "sourceCopyright": "User supplied for analysis; redistribution license not established. Original and decoded reference images remain private.",
        "privateDerivedEvidence": {"selectedReferenceFrames": sorted(keys), "mapRoi": [0, 160, 822, 1624], "retainedKeyframeCount": len(kept), "contactSheet": "REFERENCE_12_KEYFRAMES_PRIVATE.jpg"},
        "actualRendererFramesProducedByThisAudit": 0,
        "referenceVisualMatch": "NOT_EVALUATED_NO_RENDER_OUTPUT",
        "evidenceCategories": {"OBSERVED": "source pixels/object ordering", "ESTIMATED": "image positions/bboxes/2D motion/boundary angles", "AUTHORED": "event schedule/default fonts/styles/acceptance limits", "UNKNOWN": "original project/font/FOV/pitch/geographic detail truth/source redistribution license"},
        "inputFileSha256": {str(p.relative_to(evidence)): sha(p) for p in sorted(evidence.rglob("*")) if p.is_file()},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sourceFrames": frame_index, "matchedPixelHashes": report["decodedPixelHashComparison"]["matched"], "planFrames": len(plan), "windows": dict(sizes), "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
