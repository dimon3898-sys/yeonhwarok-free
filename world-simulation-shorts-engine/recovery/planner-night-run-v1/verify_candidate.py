#!/usr/bin/env python3
"""Focused technical inspection of all 420 encoded frames; never claims visual approval."""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import numpy as np
from build_manifest import (REPO, BASE, OLD, SOURCE_PARENT, MP4, SCENE_JSON,
                            H, record, require, load, git, encode, protection,
                            public_files, scene_document, OPTIONAL_OVERRIDES)

ROOT = REPO / BASE
WIDTH, HEIGHT, COUNT, FPS = 1080, 1920, 420, 30
DATES = ["1950-06-25", "1950-09-01", "1950-11-24", "1951-01-04", "1953-07-27"]
PIXEL_KEYS = ("protectedChangedPixels", "markerChangedPixels", "textChangedPixels",
              "outsideRoiChangedPixels", "safeAreaChangedPixels", "protectedBoundaryChangedPixels")


def run(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def local_record(path):
    return record(path.relative_to(REPO).as_posix())


def source_bindings(source):
    require(re.fullmatch(r"[0-9a-f]{40}", source or ""), "RENDER_SOURCE_COMMIT_REQUIRED")
    require(git("rev-parse", source + "^{commit}").decode().strip() == source, "RENDER_SOURCE_UNKNOWN")
    require(git("merge-base", SOURCE_PARENT, source).decode().strip() == SOURCE_PARENT, "RENDER_SOURCE_WRONG_PARENT")
    paths = set(OPTIONAL_OVERRIDES)
    paths.update(p.relative_to(REPO).as_posix() for p in ROOT.glob("*.mjs"))
    paths.update(p.relative_to(REPO).as_posix() for p in (ROOT / "fixtures").rglob("*") if p.is_file())
    paths.update(p.relative_to(REPO).as_posix() for p in (REPO / "world-simulation-shorts-engine/web/map_infographic_v1").glob("planner_causal*.mjs"))
    rows = [H.protected_record(source, path) for path in sorted(paths)]
    require(not git("ls-tree", "-r", "--name-only", source, "--", BASE + "/public-review", BASE + "/evidence/proof").strip(),
            "ORIGINAL_OUTPUTS_ALREADY_PRESENT_AT_RENDER_SOURCE")
    return rows


def validate_story(scene, rows):
    old = load(OLD + "/fixtures/SCENE_PLAN.json")
    require(scene["metadata"]["data_mode"] == "PRODUCTION" and scene["event_type"] == "WAR", "PRODUCTION_HISTORICAL_FIXTURE_REQUIRED")
    require(scene["metadata"]["output"] == {"width": WIDTH, "height": HEIGHT, "fps": FPS, "audio": False}, "SCENE_OUTPUT")
    for key in ("areas", "front_lines"):
        require(scene[key] == old[key], "ORIGINAL_HISTORICAL_" + key.upper() + "_CHANGED")
    geometries = {row["id"]: row["geometry"] for row in scene["geometries"]}
    for item in old["geometries"]:
        require(geometries.get(item["id"]) == item["geometry"], "ORIGINAL_SOURCE_GEOMETRY_CHANGED: " + item["id"])
    sources = {row["id"]: row for row in scene["source_notes"]}
    for item in old["source_notes"]:
        require(sources.get(item["id"]) == item, "ORIGINAL_HISTORICAL_SOURCE_CHANGED: " + item["id"])
    steps = scene["time_steps"]
    require([step["date"] for step in steps] == DATES, "HISTORICAL_FIVE_BEAT_ORDER")
    historical_keys = ("id", "date", "label", "area_ids", "front_line_ids")
    require([{k: step[k] for k in historical_keys} for step in steps] ==
            [{k: step[k] for k in historical_keys} for step in old["time_steps"]], "ORIGINAL_HISTORICAL_FACT_BINDING_CHANGED")
    timing = scene["timing"]
    require((timing["total_frames"], timing["fps"], timing["duration_seconds"]) == (COUNT, FPS, 14), "SCENE_TIMING")
    require(timing["blank_interstage_frames"] == 0 and timing["frame_policy"] == "INTEGER_DETERMINISTIC", "PLANNED_BLANK_OR_NONINTEGER_TIMING")
    require(timing["event_start_frame"] == timing["camera_lock_frame"] == 0, "IMMEDIATE_EVENT_CUE_REQUIRED")
    beats = scene["beats"]
    require(beats[0]["start_frame"] == 0 and beats[-1]["end_frame"] == COUNT and
            all(a["end_frame"] == b["start_frame"] for a, b in zip(beats, beats[1:])), "STORY_BEAT_GAP")
    require(beats[-1]["type"] == "HOLD" and 24 <= beats[-1]["duration_frames"] <= 45, "FINAL_HOLD_WINDOW")
    state_ids = [step["id"] for step in steps]
    area_map = {item["id"]: geometries[item["geometry_ref"]] for item in scene["areas"]}
    front_map = {item["id"]: geometries[item["geometry_ref"]] for item in scene["front_lines"]}
    order, state_frames, binding = [], defaultdict(list), None
    for index, row in enumerate(rows):
        require(row["frame"] == index and row["glError"] == 0, "FRAME_ORDER_OR_GPU_ERROR")
        pixel = row.get("protection", row["area"].get("protection", {}))
        require(pixel.get("checked") is True and all(pixel.get(key) == 0 for key in PIXEL_KEYS), "NATIVE_PIXEL_PROTECTION_UNCHECKED_OR_CHANGED")
        require(row.get("nativeDrawCount") == 1, "NATIVE_DRAW_OWNERSHIP")
        area = row["area"]
        require(area["geometryUnchanged"] is True and area["enabled"] is True and row["cameraLocked"] is True, "SOURCE_GEOMETRY_OR_LOCK")
        require(area["graphics"]["nativeStateRestored"] is True, "AREA_NATIVE_GPU_STATE_NOT_RESTORED")
        controls = area["controls"]
        require(controls["physicalSimulation"] is False and controls["cameraOwnership"] == "READ_ONLY" and
                controls["projectionOwnership"] == "EXISTING_NATIVE", "FINAL_ENGINE_OWNERSHIP_CHANGED")
        if binding is None:
            binding = controls["geometryBinding"]
        require(controls["geometryBinding"] == binding, "RUNTIME_GEOMETRY_BINDING_CHANGED")
        state = controls["stateId"]
        require(state in state_ids and area["annotation"]["id"] == state, "RENDERED_DATE_STATE_BINDING")
        require(controls["timeLabel"] == steps[state_ids.index(state)]["date"] and area["annotation"]["fontSize"] == 40, "HISTORICAL_DATE_OR_TEXT_STYLE")
        for item in controls["areas"]:
            require(item["geometry"] == area_map[item["id"]] and item["sourceGeometry"] == area_map[item["id"]], "RENDERED_AREA_GEOMETRY_MUTATION")
        for item in controls["fronts"]:
            require(item["geometry"] == front_map[item["id"]] and item.get("linePrimitive") is not None and
                    item.get("lineReveal") is not None, "RENDERED_FRONT_GEOMETRY_OR_FROZEN_LINE_ENGINE")
        state_frames[state].append(index)
        if not order or order[-1] != state:
            order.append(state)
    require(order == state_ids, "RENDERED_HISTORICAL_STATE_ORDER")
    require(all(len(state_frames[state]) >= 24 for state in state_ids), "HISTORICAL_STATE_READ_WINDOW")
    tracks = scene.get("causal_tracks", [])
    require(len(tracks) == len(steps) - 1, "FOUR_ADJACENT_HISTORICAL_CAUSAL_TRACKS_REQUIRED")
    motion_results = []
    for track, before, after in zip(tracks, steps, steps[1:]):
        require(track["from_state_id"] == before["id"] and track["to_state_id"] == after["id"], "CAUSAL_STATE_ORDER")
        start, contact, control, end_control, end = [track[k] for k in
            ("motion_start_frame", "contact_frame", "control_start_frame", "control_end_frame", "end_frame")]
        require(0 <= start < contact <= control < end_control <= end <= COUNT, "CAUSAL_FRAME_ORDER")
        require(track["semantic_mode"] == "SCHEMATIC_STATE_TRANSITION" and track["represents_historical_unit"] is False, "PRECISE_HISTORICAL_UNIT_CLAIM")
        require(state_frames[after["id"]][0] >= control and state_frames[before["id"]][-1] >= contact,
                "CONTROL_CHANGED_BEFORE_VISIBLE_MOTION_CONTACT")
        if track["contact_kind"] == "NONE":
            require(track["action_kind"] in {"SETTLEMENT", "CONTROL_ONLY"} and "object_id" not in track and "route_id" not in track, "ACTOR_FREE_SETTLEMENT_CONTRACT")
            require(not any(flow["id"] == track["id"] for row in rows for flow in row.get("flowTracks", [])), "SETTLEMENT_ATTACK_FABRICATED")
            continue
        require(track["source_id"] in sources and sources[track["source_id"]]["verification_status"] == "VERIFIED", "TRACK_SOURCE_UNVERIFIED")
        active = [(row["frame"], flow) for row in rows for flow in row.get("flowTracks", []) if flow["id"] == track["id"]]
        require(active, "CAUSAL_ACTOR_NOT_RENDERED: " + track["id"])
        positions, fractions, arrival_frames, visible_frames = [], [], [], []
        for frame, flow in active:
            require(flow["track"] == track and flow["enabled"] is True, "FLOW_SCENE_TRACK_BINDING")
            preflight, motion, graphics = flow["preflight"], flow["motion"], flow["graphics"]
            require(preflight["passed"] and preflight["fullRouteAndSweptSupport"] and preflight["nativeGeometryUnchanged"] and
                    preflight["noBoundaryOcclusionException"] and preflight["boundarySegmentCount"] > 0 and
                    preflight["minimumClearancePixels"] > 0, "FLOW_NATIVE_BOUNDARY_CLEARANCE")
            require(motion["engine"] == "UNCHANGED_FLOW_CORE_V2" and motion["heading"] == "UNCHANGED_FLOW_SAMPLE_ROUTE" and
                    motion["objectPositionUnchanged"] and motion["objectHeadingUnchanged"] and motion["physics"] is False,
                    "FLOW_CORE_POSITION_HEADING_OWNERSHIP")
            require(graphics["nativeStateRestored"] and flow["sourceControls"]["productionEligible"], "FLOW_GPU_STATE_OR_PRODUCTION")
            source = flow["sourceControls"]
            require(source["objectPosition"] == flow["controls"]["objectPosition"] and source["heading"] == flow["controls"]["heading"], "SOURCE_FLOW_MOTION_CHANGED")
            if frame < contact:
                positions.append(source["objectPosition"])
                fractions.append(source["objectFraction"])
            if graphics.get("object") and flow.get("actorVisible") is True and flow.get("objectOpacity", 0) > 0:
                visible_frames.append(frame)
            if any(pulse["endpoint"] == "ARRIVAL" and pulse["alpha"] > 0 for pulse in graphics["pulses"]):
                arrival_frames.append(frame)
                require(frame >= contact, "CONTACT_CUE_BEFORE_ACTOR_ARRIVAL")
        require(len(positions) >= 2 and all(a <= b + 1e-12 for a, b in zip(fractions, fractions[1:])), "NONMONOTONIC_ACTOR_MOTION")
        displacement = math.dist(positions[0], positions[-1])
        require(displacement > 5 and any(frame < contact for frame in visible_frames), "VISIBLE_APPROACH_MOTION_MISSING")
        require(arrival_frames and min(arrival_frames) < control, "VISIBLE_CONTACT_MUST_PRECEDE_CONTROL_CHANGE")
        motion_results.append({"id": track["id"], "approachStartFrame": start, "firstVisibleFrame": min(visible_frames),
                               "contactFrame": contact, "visibleArrivalFrames": arrival_frames, "controlStartFrame": control,
                               "controlEndFrame": end_control, "screenDisplacementPixels": round(displacement, 4)})
    require(motion_results and min(row["firstVisibleFrame"] for row in motion_results) < FPS, "NO_FIRST_SECOND_EVENT_CUE")
    require(tracks[-1]["contact_kind"] == "NONE", "ARMISTICE_MUST_NOT_BE_RENDERED_AS_ATTACK")
    require(not scene.get("impact_zones") and "IMPACT_ZONE" not in scene["selected_features"], "UNSUPPORTED_WAR_IMPACT")
    return {"historicalDates": DATES, "renderedStateOrder": order, "sourceGeometryUnchanged": True,
            "motionContactControl": motion_results, "finalActorFreeSettlement": True,
            "stateReadWindows": [{"id": key, "firstFrame": value[0], "lastFrame": value[-1], "frames": len(value)} for key, value in state_frames.items()]}


def map_mask(row):
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    boxes = row.get("rois") or row["area"]["graphics"].get("rois", [])
    for box in boxes:
        x0, y0 = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
        x1, y1 = min(WIDTH, math.ceil(box[2])), min(HEIGHT, math.ceil(box[3]))
        mask[y0:y1, x0:x1] = True
    excluded = [item["box"] for item in row.get("protectedGraphics", [])]
    text = row["area"].get("annotation") or {}
    if text.get("roi"):
        excluded.append(text["roi"])
    for box in excluded:
        x0, y0 = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
        x1, y1 = min(WIDTH, math.ceil(box[2])), min(HEIGHT, math.ceil(box[3]))
        mask[y0:y1, x0:x1] = False
    return mask


def decode(video, rows, selected):
    private = ROOT / "evidence/decoded-audit"
    private.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(["ffmpeg", "-v", "error", "-xerror", "-threads", "2", "-i", str(video),
                                "-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_size, previous, previous_mask, previous_frame = WIDTH * HEIGHT * 3, None, None, None
    frame_metrics, changes, hashes = [], [], {}
    try:
        for frame in range(COUNT):
            chunk = bytearray()
            while len(chunk) < frame_size:
                part = process.stdout.read(frame_size - len(chunk))
                require(part, "TRUNCATED_DECODE_AT_FRAME_" + str(frame))
                chunk.extend(part)
            pixels = np.frombuffer(chunk, dtype=np.uint8).reshape(HEIGHT, WIDTH, 3)
            # Test every frame, including those never selected for human-style inspection.
            luma = pixels[:, :, 0] * .2126 + pixels[:, :, 1] * .7152 + pixels[:, :, 2] * .0722
            mean, deviation = float(luma.mean()), float(luma.std())
            black_fraction = float(np.mean(luma < 16))
            require(mean > 2 and deviation > 2 and black_fraction < .995, "BLACK_OR_BLANK_FRAME_" + str(frame))
            frame_metrics.append({"frame": frame, "meanLuma": round(mean, 4), "lumaStdDev": round(deviation, 4), "blackPixelFraction": round(black_fraction, 6)})
            if frame in selected:
                hashes[frame] = hashlib.sha256(chunk).hexdigest()
            if frame % 15 == 0 or frame == COUNT - 1:
                mask = map_mask(rows[frame])
                if previous is not None:
                    combined = mask | previous_mask
                    difference = np.abs(pixels.astype(np.int16) - previous.astype(np.int16))
                    values = difference[combined]
                    changes.append({"startFrame": previous_frame, "endFrame": frame, "eventRoiPixels": int(combined.sum()),
                                    "meanAbsoluteChannelChange": round(float(values.mean()), 6) if values.size else 0,
                                    "eventPixelsChangedByAtLeast8": int(np.count_nonzero(np.any(difference >= 8, axis=2) & combined))})
                previous, previous_mask, previous_frame = pixels.copy(), mask, frame
        require(process.stdout.read(1) == b"", "MORE_THAN_420_DECODED_FRAMES")
        errors = process.stderr.read().decode()
        require(process.wait() == 0 and not errors.strip(), "DECODE_ERROR: " + errors)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    require(any(item["endFrame"] <= FPS and item["eventPixelsChangedByAtLeast8"] > 100 for item in changes), "DECODED_FIRST_SECOND_MAP_CUE_MISSING")
    action_end = COUNT - 36
    static_run, longest_static = 0, 0
    for item in changes:
        if item["startFrame"] >= action_end:
            continue
        static_run = static_run + (item["endFrame"] - item["startFrame"]) if item["eventPixelsChangedByAtLeast8"] <= 100 else 0
        longest_static = max(longest_static, static_run)
    require(longest_static < 60, "TWO_SECONDS_OF_UNCHANGING_ACTION_MAP")
    expression = "+".join("eq(n\\," + str(frame) + ")" for frame in sorted(selected))
    run("ffmpeg", "-v", "error", "-threads", "2", "-i", str(video), "-vf", "select=" + expression,
        "-fps_mode", "passthrough", "-threads", "2", "-y", str(private / "SELECT_%03d.png"))
    decoded = {}
    for index, frame in enumerate(sorted(selected), 1):
        path = private / ("FRAME_%03d.png" % frame)
        (private / ("SELECT_%03d.png" % index)).replace(path)
        rgb = run("ffmpeg", "-v", "error", "-threads", "2", "-i", str(path), "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1")
        require(hashlib.sha256(rgb).hexdigest() == hashes[frame], "SELECTED_FRAME_DECODE_BINDING")
        decoded[frame] = path
    return {"allFramesDecoded": COUNT, "blackFrames": 0, "blankFrames": 0, "decodeErrors": 0,
            "frameMetrics": frame_metrics, "mapChanges": changes, "longestStaticActionFrames": longest_static,
            "measurement": "Half-second decoded RGB differences within union event ROIs excluding native protected graphics and annotation text",
            "extractedFrames": [{"frame": frame, **local_record(path)} for frame, path in decoded.items()]}, decoded


def audit():
    report = load(BASE + "/evidence/proof/REPORT.json")
    fixture = load(BASE + "/fixtures/RUNTIME_FIXTURE.json")
    require(report["status"] == "PASS", "RENDER_NOT_PASS")
    require(all(report.get(key) is False for key in ("userVideoApproved", "eventFinal", "plannerFinal", "permanentGateExecuted")), "UNAUTHORIZED_FINAL_OR_APPROVAL")
    require((report["totalFrames"], report["fps"], report["durationSeconds"], report["width"], report["height"], report["audio"]) ==
            (COUNT, FPS, 14, WIDTH, HEIGHT, False), "EXACT_14_SECOND_REVIEW_FORMAT")
    require(report["video"]["file"] == MP4 and fixture["presentation"]["totalFrames"] == COUNT, "REVIEW_VIDEO_OR_FIXTURE_BINDING")
    video = ROOT / "public-review" / MP4
    require(all(local_record(video)[key] == report["video"][key] for key in ("sha256", "bytes")), "ORIGINAL_ENCODED_VIDEO_BODY")
    public_files(report)
    protected = protection()
    bindings = source_bindings(report["sourceCommit"])
    scene_validation, scene = scene_document(BASE + "/fixtures/" + SCENE_JSON)
    rows = report["frames"]
    require(len(rows) == COUNT, "ALL_420_NATIVE_DIAGNOSTIC_ROWS_REQUIRED")
    story = validate_story(scene, rows)
    for key in PIXEL_KEYS:
        require(report.get("protection", {}).get(key) == 0, "AGGREGATE_PIXEL_PROTECTION: " + key)
    points = report["checkpoints"]
    for point in points:
        frame = point["frame"]
        require(isinstance(frame, int) and 0 <= frame < COUNT, "CHECKPOINT_FRAME")
        require(point.get("sourceMatchesEncodedNativeFrame") is True and rows[frame]["png_sha256"] == point["sha256"], "CHECKPOINT_NOT_ORIGINAL_ENCODER_INPUT")
        require(all(local_record(ROOT / "public-review" / point["file"])[key] == point[key] for key in ("sha256", "bytes")), "CHECKPOINT_BODY")
    probe = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(video)))
    require(len(probe["streams"]) == 1, "SILENT_SINGLE_STREAM_REQUIRED")
    stream = probe["streams"][0]
    require((stream["codec_type"], stream["codec_name"], stream["width"], stream["height"], stream["avg_frame_rate"]) ==
            ("video", "h264", WIDTH, HEIGHT, "30/1"), "FFPROBE_FORMAT")
    require(int(stream["nb_read_frames"]) == COUNT and float(stream["duration"]) == 14 and float(probe["format"]["duration"]) == 14, "FFPROBE_TIMING")
    selected = {point["frame"] for point in points} | {0, 15, 29, COUNT - 1}
    for track in scene["causal_tracks"]:
        selected.update({track["motion_start_frame"], track["contact_frame"], track["control_start_frame"], track["control_end_frame"] - 1})
    technical, decoded = decode(video, rows, selected)
    for track in story["motionContactControl"]:
        require(any(change["startFrame"] >= track["approachStartFrame"] and change["endFrame"] <= track["contactFrame"]
                    and change["eventPixelsChangedByAtLeast8"] > 100 for change in technical["mapChanges"]),
                "DECODED_APPROACH_HAS_NO_MEANINGFUL_MAP_CHANGE: " + track["id"])
    fidelity = []
    for point in points:
        original = run("ffmpeg", "-v", "error", "-threads", "2", "-i", str(ROOT / "public-review" / point["file"]), "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1")
        encoded = run("ffmpeg", "-v", "error", "-threads", "2", "-i", str(decoded[point["frame"]]), "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1")
        difference = np.frombuffer(original, np.uint8).astype(np.float64) - np.frombuffer(encoded, np.uint8).astype(np.float64)
        mse = float(np.mean(difference ** 2))
        psnr = 99 if mse == 0 else 10 * math.log10(255 ** 2 / mse)
        require(psnr >= 34, "CHECKPOINT_ENCODED_FRAME_FIDELITY")
        fidelity.append({"file": point["file"], "frame": point["frame"], "psnrDb": round(psnr, 4)})
    technical["checkpointFidelity"] = fidelity
    result = {"schema": 1, "status": "PASS", "scope": "FOCUSED_ACTUAL_420_FRAME_TECHNICAL_INSPECTION",
              "sourceCommit": report["sourceCommit"], "sourceBindings": bindings,
              "video": local_record(video), "scene": scene_validation, "renderReport": local_record(ROOT / "evidence/proof/REPORT.json"),
              "ffprobe": probe, "format": {"frames": COUNT, "fps": FPS, "durationSeconds": 14, "width": WIDTH, "height": HEIGHT, "audio": False},
              "technicalInspection": technical, "story": story,
              "protection": {"checkedFrames": COUNT, **{key: 0 for key in PIXEL_KEYS}, "gpuErrors": 0,
                             "sourceGeometryUnchanged": True, "protectedSource": protected},
              "visualInspection": {"scope": "NOT_PERFORMED_BY_THIS_TECHNICAL_HELPER", "sampleFramesAvailable": sorted(selected),
                                   "humanStyleSampleInspectionPerformed": False, "fullVideoVisualReviewPerformed": False},
              "fullVisualReviewClaimed": False,
              "limitations": ["Reference 65379.mp4 and prior upload 65378.mp4 were not mounted; direct reference matching is unverified.",
                              "Historical chronology and geometry reuse curated existing facts; original citations were not live retrieved.",
                              "Actor paths are schematic direction cues, not observed historical military unit routes."],
              "userVideoApproved": False, "plannerFinal": False, "eventFinal": False,
              "permanentGateExecuted": False, "next": "USER_VIDEO_REVIEW_REQUIRED"}
    (ROOT / "evidence/CANDIDATE_AUDIT.json").write_bytes(encode(result))
    print(json.dumps({"status": "PASS", "allFramesDecoded": COUNT, "blackOrBlankFrames": 0,
                      "videoSha256": result["video"]["sha256"], "fullVisualReviewClaimed": False,
                      "sampleFramesExtracted": len(selected), "next": result["next"]}))


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    audit()
