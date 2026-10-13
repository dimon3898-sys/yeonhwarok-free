#!/usr/bin/env python3
"""Inspect the original encoded Planner proof without changing public media.

This is a focused Candidate inspection, not a Permanent Gate or historical
synthetic rerun. PASS requires an explicit review of actual decoded frames.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
ENGINE = ROOT.parents[1]
REPO = ROOT.parents[2]
PARENT = "7da699c07cddf618f5e8a93ca735db51d31bbb39"
VIDEO_NAME = "KOREAN_WAR_PLANNER_SCENE_JSON_V1_CANDIDATE.mp4"
DATES = ["1950-06-25", "1950-09-01", "1950-11-24", "1951-01-04", "1953-07-27"]
CHECKPOINTS = ["01_GEOGRAPHIC_CONTEXT.png", "02_INITIAL_FRONT.png", "03_PUSAN_PERIMETER.png",
               "04_NORTH_ADVANCE.png", "05_SEOUL_WITHDRAWAL.png", "06_ARMISTICE.png",
               "07_FRONT_COMPLETE.png", "08_FINAL_HOLD.png"]
WIDTH, HEIGHT = 1080, 1920


def require(condition, reason):
    if not condition:
        raise RuntimeError("PLANNER_VISUAL_AUDIT: " + reason)


def run(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_file(path):
    return json.loads(path.read_text())


def record(path):
    return {"file": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size}


def rgb_png(path):
    value = run("ffmpeg", "-v", "error", "-threads", "2", "-i", str(path),
                "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1")
    require(len(value) == WIDTH * HEIGHT * 3, "NATIVE_PNG_RGB_SIZE")
    return np.frombuffer(value, dtype=np.uint8).reshape(HEIGHT, WIDTH, 3)


def roi_mask(row):
    """Only event map ROIs; text is excluded from motion measurements."""
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    area = row.get("area") or {}
    annotation = area.get("annotation") or {}
    text_box = annotation.get("roi")
    for box in (area.get("graphics") or {}).get("rois", []):
        if box == text_box:
            continue
        x0, y0 = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
        x1, y1 = min(WIDTH, math.ceil(box[2])), min(HEIGHT, math.ceil(box[3]))
        mask[y0:y1, x0:x1] = True
    for item in row.get("protectedGraphics", []):
        box = item["box"]
        x0, y0 = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
        x1, y1 = min(WIDTH, math.ceil(box[2])), min(HEIGHT, math.ceil(box[3]))
        mask[y0:y1, x0:x1] = False
    if text_box:
        x0, y0 = max(0, math.floor(text_box[0])), max(0, math.floor(text_box[1]))
        x1, y1 = min(WIDTH, math.ceil(text_box[2])), min(HEIGHT, math.ceil(text_box[3]))
        mask[y0:y1, x0:x1] = False
    return mask


def decode_and_measure(video, rows, count, selected_frames, private):
    """Decode all frames and quantify 0.5-second map changes in actual pixels.

    Native material can already be cyan/gold. No color threshold is interpreted
    as visibility. Differences are measured only inside event geometry ROIs.
    """
    decoder = subprocess.Popen(["ffmpeg", "-v", "error", "-xerror", "-threads", "2", "-i", str(video),
                                "-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_size = WIDTH * HEIGHT * 3
    previous, previous_frame, previous_mask = None, None, None
    changes = []
    hashes = {}
    try:
        for frame in range(count):
            chunk = bytearray()
            while len(chunk) < frame_size:
                part = decoder.stdout.read(frame_size - len(chunk))
                require(part, "TRUNCATED_DECODED_FRAME_" + str(frame))
                chunk.extend(part)
            if frame in selected_frames:
                hashes[frame] = hashlib.sha256(chunk).hexdigest()
            if frame % 15 == 0 or frame == count - 1:
                pixels = np.frombuffer(chunk, dtype=np.uint8).reshape(HEIGHT, WIDTH, 3).copy()
                mask = roi_mask(rows[frame])
                if previous is not None:
                    combined = mask | previous_mask
                    difference = np.abs(pixels.astype(np.int16) - previous.astype(np.int16))
                    values = difference[combined]
                    changes.append({"startFrame": previous_frame, "endFrame": frame,
                                    "eventRoiPixels": int(np.count_nonzero(combined)),
                                    "meanAbsoluteChannelChange": round(float(np.mean(values)), 6) if values.size else 0,
                                    "eventPixelsChangedByAtLeast8": int(np.count_nonzero(np.any(difference >= 8, axis=2) & combined)),
                                    "cameraLockedAtBothFrames": bool(rows[previous_frame]["cameraLocked"] and rows[frame]["cameraLocked"])})
                previous, previous_frame, previous_mask = pixels, frame, mask
        require(decoder.stdout.read(1) == b"", "EXTRA_DECODED_FRAMES")
        errors = decoder.stderr.read().decode()
        require(decoder.wait() == 0, "DECODE_ERRORS: " + errors)
    finally:
        if decoder.poll() is None:
            decoder.kill()
            decoder.wait()

    expression = "+".join("eq(n\\," + str(frame) + ")" for frame in sorted(selected_frames))
    run("ffmpeg", "-v", "error", "-threads", "2", "-i", str(video), "-vf", "select=" + expression,
        "-fps_mode", "passthrough", "-threads", "2", "-y", str(private / "TEMP_%03d.png"))
    decoded = {}
    for index, frame in enumerate(sorted(selected_frames), 1):
        path = private / ("FRAME_%03d.png" % frame)
        (private / ("TEMP_%03d.png" % index)).replace(path)
        require(hashlib.sha256(rgb_png(path).tobytes()).hexdigest() == hashes[frame], "EXTRACTED_FRAME_RGB_BINDING")
        decoded[frame] = path
    return decoded, changes


def validate_scene(scene_path):
    module = str(ENGINE / "web/map_infographic_v1/planner_scene_v1.mjs")
    program = ("import fs from 'node:fs';import {validateScenePlan} from " + json.dumps(module) + ";"
               "const scene=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));"
               "console.log(JSON.stringify(validateScenePlan(scene)));")
    result = json.loads(run("node", "--input-type=module", "-e", program, str(scene_path)))
    require(result.get("valid") is True, "SCENE_SCHEMA_INVALID")
    return result


def source_bindings(source):
    paths = [ROOT / "fixtures/RUNTIME_FIXTURE.json", ROOT / "fixtures/SCENE_PLAN.json",
             ROOT / "planner_runtime.mjs", ROOT / "render_proof.mjs",
             ENGINE / "web/map_infographic_v1/planner_scene_v1.mjs",
             ENGINE / "web/map_infographic_v1/planner_engine_adapter_v1.mjs"]
    result = []
    for path in paths:
        relative = path.relative_to(REPO).as_posix()
        committed = run("git", "-C", str(REPO), "show", source + ":" + relative)
        require(committed == path.read_bytes(), "SOURCE_NOT_COMMITTED_BEFORE_RENDER: " + relative)
        result.append({"path": relative, "sha256": sha(path)})
    original = set(run("git", "-C", str(REPO), "ls-tree", "-r", "--name-only", PARENT).decode().splitlines())
    changed = set(run("git", "-C", str(REPO), "diff", "--name-only", PARENT).decode().splitlines())
    require(not original & changed, "PARENT_FINAL_TRACKED_SOURCE_CHANGED")
    return result, len(original)


def audit(visual_review):
    fixture_path, scene_path = ROOT / "fixtures/RUNTIME_FIXTURE.json", ROOT / "fixtures/SCENE_PLAN.json"
    report_path = ROOT / "evidence/proof/REPORT.json"
    fixture, scene, report = json_file(fixture_path), json_file(scene_path), json_file(report_path)
    require(report["status"] == "PASS" and report["state"] == "PLANNER_SCENE_JSON_V1_CANDIDATE", "RENDER_CANDIDATE_NOT_PASS")
    require(all(report.get(key) is False for key in ("userVideoApproved", "eventFinal", "permanentGateExecuted")), "UNAUTHORIZED_FINAL_GATE")
    count, fps = report["totalFrames"], report["fps"]
    require((report["width"], report["height"], fps, report["audio"]) == (WIDTH, HEIGHT, 30, False), "VIDEO_FORMAT")
    require(300 <= count <= 450 and report["durationSeconds"] == count / fps, "VIDEO_DURATION")
    require(count == fixture["presentation"]["totalFrames"] == scene["timing"]["total_frames"], "SCENE_RUNTIME_FRAME_BINDING")
    require(report["video"]["file"] == VIDEO_NAME, "EXPECTED_PUBLIC_VIDEO")
    video = ROOT / "public-review" / VIDEO_NAME
    require(sha(video) == report["video"]["sha256"], "ORIGINAL_ENCODED_MP4_BINDING")
    require((ROOT / "public-review/SCENE_PLAN.json").read_bytes() == scene_path.read_bytes(), "PUBLIC_SCENE_DIFFERS_FROM_EXECUTED_INPUT")
    schema = validate_scene(scene_path)
    bindings, protected_paths = source_bindings(report["sourceCommit"])
    require(scene["metadata"]["data_mode"] == "PRODUCTION" and scene["event_type"] == "WAR", "REAL_WAR_PROOF_REQUIRED")
    require(scene["selected_features"] == ["FRONT_LINE", "STATE_TRANSITION", "TIME_STEP", "AREA_HOLD"], "UNNECESSARY_PRIMITIVES")
    require(not scene.get("routes") and not scene.get("moving_objects") and not scene.get("propagations"), "WAR_FEATURE_DEMO_OVERLOAD")
    steps = scene["time_steps"]
    require([step["date"] for step in steps] == DATES, "HISTORICAL_CHRONOLOGY")
    require(scene["timing"]["blank_interstage_frames"] == 0, "PLANNED_DEAD_TIME")
    beats = scene["beats"]
    require(beats[0]["start_frame"] == 0 and beats[-1]["end_frame"] == count
            and all(a["end_frame"] == b["start_frame"] for a, b in zip(beats, beats[1:])), "NONCONTIGUOUS_STORY_BEATS")
    require(beats[-1]["type"] == "HOLD" and 24 <= beats[-1]["duration_frames"] <= 45, "FINAL_HOLD_RHYTHM")

    probe = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(video)))
    require(len(probe["streams"]) == 1, "AUDIO_OR_EXTRA_STREAM")
    stream = probe["streams"][0]
    require((stream["codec_type"], stream["codec_name"], stream["width"], stream["height"], stream["avg_frame_rate"])
            == ("video", "h264", WIDTH, HEIGHT, "30/1"), "PROBED_STREAM_FORMAT")
    require(int(stream["nb_read_frames"]) == count and float(stream["duration"]) == count / fps, "PROBED_TIMING")

    event_start = fixture["presentation"]["eventStartFrame"]
    require(event_start == scene["timing"]["event_start_frame"] == scene["timing"]["camera_lock_frame"], "SCENE_DETAIL_LOCK_CONTRACT")
    rows = report["frames"]
    require(len(rows) == count, "COMPLETE_NATIVE_FRAME_EVIDENCE")
    geometry_map = {item["id"]: item["geometry"] for item in scene["geometries"]}
    area_map = {item["id"]: geometry_map[item["geometry_ref"]] for item in scene["areas"]}
    front_map = {item["id"]: geometry_map[item["geometry_ref"]] for item in scene["front_lines"]}
    state_frames = defaultdict(list)
    order = []
    binding = None
    state_ids = [step["id"] for step in steps]
    for index, row in enumerate(rows):
        require(row["frame"] == index and row["glError"] == 0, "FRAME_ORDER_OR_GL_ERROR")
        area = row["area"]
        require(all(area["protection"][key] == 0 for key in
                    ("protectedChangedPixels", "markerChangedPixels", "outsideRoiChangedPixels", "safeAreaChangedPixels")), "CRITICAL_PROTECTED_PIXEL_CHANGE")
        require(area["geometryUnchanged"], "SOURCE_GEOMETRY_MUTATION")
        if index < event_start:
            require(not area["enabled"], "EVENT_BEFORE_CAMERA_LOCK")
            continue
        require(area["enabled"] and row["cameraLocked"] and area["graphics"]["nativeStateRestored"], "EVENT_LOCK_OR_GPU_STATE")
        controls = area["controls"]
        require(not controls["physicalSimulation"] and controls["cameraOwnership"] == "READ_ONLY"
                and controls["projectionOwnership"] == "EXISTING_NATIVE", "DUPLICATED_RENDERER_CAMERA_OR_SIMULATION")
        if binding is None:
            binding = controls["geometryBinding"]
        require(controls["geometryBinding"] == binding, "RUNTIME_GEOMETRY_BINDING_CHANGED")
        state_id = controls["stateId"]
        require(state_id in state_ids and area["annotation"]["id"] == state_id, "DATE_FRONT_STATE_MISMATCH")
        require(controls["timeLabel"] == steps[state_ids.index(state_id)]["date"], "HISTORICAL_DATE_RENDER_BINDING")
        require(area["annotation"]["fontSize"] == 40, "INHERITED_TEXT_FONT_STYLE")
        for item in controls["areas"]:
            require(item["geometry"] == area_map[item["id"]] and item["sourceGeometry"] == area_map[item["id"]], "AREA_AUTHORED_GEOMETRY_CHANGED")
        for item in controls["fronts"]:
            require(item["geometry"] == front_map[item["id"]], "FRONT_AUTHORED_GEOMETRY_CHANGED")
            require(item["linePrimitive"] is not None and item["lineReveal"] is not None, "EXISTING_ARC_LENGTH_LINE_ENGINE_NOT_USED")
        state_frames[state_id].append(index)
        if not order or order[-1] != state_id:
            order.append(state_id)
    require(order == state_ids, "RENDERED_TIME_STEPS_OUT_OF_ORDER")
    require(all(len(state_frames[step["id"]]) >= 24 for step in steps), "TIME_STEP_READ_WINDOW_TOO_SHORT")
    text = [item["content"] for item in scene.get("text", [])] + [step["label"] for step in steps]
    require(not any(re.search(r"예시|Planner\s*Test|테스트|전개도|기능\s*데모", value, re.I) for value in text), "PUBLIC_FEATURE_DEMO_TEXT")

    checkpoints = report["checkpoints"]
    expected = {(item["frame"], item["file"]) for item in fixture["presentation"]["checkpoints"]}
    require(len(checkpoints) == 8 and [item["file"] for item in checkpoints] == CHECKPOINTS, "EIGHT_PUBLIC_CHECKPOINT_NAMES")
    require({(item["frame"], item["file"]) for item in checkpoints} == expected, "CHECKPOINT_TIMING_BINDING")
    for item in checkpoints:
        checkpoint = ROOT / "public-review" / item["file"]
        require(sha(checkpoint) == item["sha256"] == rows[item["frame"]]["png_sha256"]
                and item["sourceMatchesEncodedNativeFrame"], "CHECKPOINT_NOT_ORIGINAL_NATIVE_ENCODER_INPUT")

    private = ROOT / "evidence/decoded-audit"
    private.mkdir(exist_ok=True)
    selected_frames = {item["frame"] for item in checkpoints} | {count - 1}
    for step in steps:
        selected_frames.add(min(count - 1, step["start_frame"] + step["transition_frames"] // 2))
        selected_frames.add(min(count - 1, step["start_frame"] + step["transition_frames"] - 1))
    decoded, changes = decode_and_measure(video, rows, count, selected_frames, private)
    fidelity = []
    for item in checkpoints:
        original = rgb_png(ROOT / "public-review" / item["file"]).astype(np.int16)
        encoded = rgb_png(decoded[item["frame"]]).astype(np.int16)
        difference = original - encoded
        mse = float(np.mean(difference.astype(np.float64) ** 2))
        psnr = 99 if mse == 0 else 10 * math.log10(255 * 255 / mse)
        require(psnr >= 34, "ENCODED_NATIVE_FRAME_FIDELITY")
        fidelity.append({"frame": item["frame"], "nativeInputSha256": item["sha256"],
                         "decodedPng": record(decoded[item["frame"]]), "psnrDb": round(psnr, 4),
                         "meanAbsoluteChannelError": round(float(np.mean(np.abs(difference))), 4)})

    require(any(item["cameraLockedAtBothFrames"] and item["eventPixelsChangedByAtLeast8"] > 100
                for item in changes), "NO_OBSERVABLE_EVENT_MAP_CHANGE_IN_DECODED_VIDEO")
    result = {"schema": 1, "status": "PASS" if visual_review else "TECHNICAL_PASS_VISUAL_REVIEW_REQUIRED",
              "scope": "ACTUAL_DECODED_PLANNER_SCENE_JSON_WAR_PROOF", "sourceCommit": report["sourceCommit"],
              "originalMp4": record(video), "renderReport": record(report_path), "executedScene": record(scene_path),
              "publicScene": record(ROOT / "public-review/SCENE_PLAN.json"), "sceneSchema": schema,
              "sourceBindings": bindings, "protectedOriginalTrackedPaths": protected_paths,
              "format": {"width": WIDTH, "height": HEIGHT, "fps": fps, "frames": count,
                         "durationSeconds": count / fps, "audio": False},
              "decodedVideoInspection": {"reviewerInspectedActualEncodedFrames": bool(visual_review),
                                         "frames": [record(decoded[frame]) for frame in sorted(decoded)],
                                         "checkpointFidelity": fidelity, "allFramesDecoded": count, "decodeErrors": 0},
              "story": {"selectedFeatures": scene["selected_features"], "beatTypes": [beat["type"] for beat in beats],
                        "renderedStateOrder": order, "historicalDates": DATES,
                        "stateReadWindows": [{"id": key, "firstFrame": value[0], "lastFrame": value[-1],
                                              "frames": len(value)} for key, value in state_frames.items()],
                        "plannedBlankInterstageFrames": 0, "finalHoldFrames": beats[-1]["duration_frames"],
                        "decodedEventRoiChangeMeasurement": "CONSECUTIVE_HALF_SECOND_RGB_DIFFERENCES_EXCLUDING_TEXT_AND_PROTECTED_NATIVE_GRAPHICS",
                        "decodedEventRoiChanges": changes, "publicText": text, "featureDemoText": False},
              "protection": {"checkedFrames": count, "protectedChangedPixels": 0, "markerChangedPixels": 0,
                             "outsideRoiChangedPixels": 0, "safeAreaChangedPixels": 0, "glErrors": 0,
                             "geometryUnchanged": True, "parentFinalSourceUnchanged": True, "lockBeforeEvent": True},
              "limitations": ["Authored historical front and held-core state sketches are illustrative, not archival surveyed military control boundaries.",
                               "Published reference bodies were not retrieved because the managed proxy denied access; no live document verification is claimed.",
                               "No military, fluid or weather physics is used."],
              "tools": {"python": platform.python_version(), "numpy": np.__version__,
                        "ffmpeg": run("ffmpeg", "-version").decode().splitlines()[0]},
              "userVideoApproved": False, "eventFinal": False, "permanentGateExecuted": False,
              "next": "USER_VIDEO_REVIEW_REQUIRED"}
    if visual_review:
        result["visualReview"] = {"basis": "ACTUAL_DECODED_1080X1920_AND_MOBILE_FRAME_INSPECTION",
                                  "camera": "PASS", "front": "PASS", "area": "PASS", "timeProgression": "PASS",
                                  "rhythm": "PASS", "text": "PASS", "contrast": "PASS", "criticalVisualErrors": []}
    (ROOT / "evidence/VISUAL_AUDIT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "frames": count, "durationSeconds": count / fps,
                      "videoSha256": result["originalMp4"]["sha256"], "renderedStateOrder": order,
                      "decodedFramesExtracted": len(decoded), "next": result["next"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual-review-pass", action="store_true",
                        help="Use only after inspecting actual decoded video frames; does not imply user approval.")
    audit(parser.parse_args().visual_review_pass)
