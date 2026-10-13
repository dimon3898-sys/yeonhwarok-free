#!/usr/bin/env python3
"""Focused proof audit. Decodes the original MP4; never changes public media."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def record(path):
    return {"file": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size}


def rgba_png(path):
    value = run("ffmpeg", "-v", "error", "-threads", "2", "-i", str(path),
                "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1")
    require(len(value) == 1080 * 1920 * 3, "PNG_RGB_SIZE")
    return np.frombuffer(value, dtype=np.uint8).reshape(1920, 1080, 3)


def contiguous(frames):
    return not frames or frames == list(range(frames[0], frames[-1] + 1))


def measure_colors(video, rows, count):
    """Read original decoded pixels inside event geometry ROIs, excluding text."""
    decoder = subprocess.Popen(["ffmpeg", "-v", "error", "-xerror", "-threads", "2", "-i", str(video),
                                "-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    colors = []
    frame_size = 1080 * 1920 * 3
    date_only_pixels = rows[-1]["wave"]["protection"]["changedPixels"]
    for frame in range(count):
        chunk = bytearray()
        while len(chunk) < frame_size:
            part = decoder.stdout.read(frame_size - len(chunk))
            require(part, "COMPLETE_DECODED_RGB_FRAME")
            chunk.extend(part)
        pixels = np.frombuffer(chunk, dtype=np.uint8).reshape(-1, 3)
        r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
        # Native terrain contains a few cyan pixels. Restrict detection to
        # actual projected event geometry ROIs and exclude the date glyph ROI.
        roi_mask = np.zeros((1920, 1080), dtype=bool)
        wave = rows[frame]["wave"]
        graphics = wave.get("graphics") or {}
        annotation = wave.get("annotation") or {}
        annotation_box = annotation.get("roi")
        if wave["protection"]["changedPixels"] > date_only_pixels:
            for box in graphics.get("rois", []):
                if box == annotation_box:
                    continue
                x0, y0 = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
                x1, y1 = min(1080, math.ceil(box[2])), min(1920, math.ceil(box[3]))
                roi_mask[y0:y1, x0:x1] = True
        roi_mask = roi_mask.reshape(-1)
        teal = (r < 90) & (g > 135) & (b > 110) & roi_mask
        contact = (r > 125) & (b > 125) & (g < 120) & roi_mask
        colors.append({"frame": frame, "tealWavePixels": int(np.count_nonzero(teal)),
                       "magentaContactPixels": int(np.count_nonzero(contact))})
    require(decoder.stdout.read(1) == b"", "NO_EXTRA_DECODED_FRAMES")
    error = decoder.stderr.read().decode()
    require(decoder.wait() == 0, "FULL_DECODE_ERROR: " + error)
    active = [row["frame"] for row in colors if row["tealWavePixels"] + row["magentaContactPixels"] >= 12]
    require(len(active) > 0, "NO_VISIBLE_WAVE_PIXELS")
    return colors, active, date_only_pixels


def measurement_fields(colors, active, count, date_only_pixels):
    return {"firstVisibleWavePixelFrame": active[0], "lastVisibleWavePixelFrame": active[-1],
            "decodedColorMeasurement": "MINIMUM_12_TEAL_MAGENTA_PIXELS_INSIDE_EVENT_GEOMETRY_ROIS_EXCLUDING_DATE_AND_DATE_ONLY_FRAMES",
            "dateOnlyNativeChangedPixelBaseline": date_only_pixels,
            "decodedMapHoldFrames": count - 1 - active[-1],
            "observedFinalMapHoldFrames": count - 1 - active[-1], "decodedColorPixelsByFrame": colors}


def refresh_measurement():
    """A focused correction reruns only decoded color measurement, not gates."""
    path = ROOT / "evidence/VISUAL_AUDIT.json"
    value = json.loads(path.read_text())
    report_path = ROOT / "evidence/proof/REPORT.json"
    report = json.loads(report_path.read_text())
    video = ROOT / value["originalMp4"]["file"]
    require(value["status"] == "PASS", "EXISTING_VISUAL_AUDIT_PASS_REQUIRED")
    require(sha(video) == value["originalMp4"]["sha256"] == report["video"]["sha256"], "ORIGINAL_MP4_UNCHANGED")
    require(sha(report_path) == value["renderReport"]["sha256"], "RENDER_REPORT_UNCHANGED")
    colors, active, baseline = measure_colors(video, report["frames"], report["totalFrames"])
    value["wave"].update(measurement_fields(colors, active, report["totalFrames"], baseline))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": value["status"], "scope": "DECODED_VISIBLE_MEASUREMENT_ONLY",
                      "lastVisibleWavePixelFrame": active[-1], "observedFinalMapHoldFrames": report["totalFrames"] - 1 - active[-1]}))


def audit(visual_review):
    fixture_path = ROOT / "fixtures/REAL_FIXTURE.json"
    report_path = ROOT / "evidence/proof/REPORT.json"
    fixture = json.loads(fixture_path.read_text())
    report = json.loads(report_path.read_text())
    require(report["status"] == "PASS", "RENDER_REPORT_NOT_PASS")
    require(report["state"] == "EVENT_FEATURE_BUNDLE_V3_TSUNAMI_WAVE_POLISH_CANDIDATE", "CANDIDATE_STATE")
    require(all(report.get(k) is False for k in ("userVideoApproved", "eventFinal", "permanentGateExecuted")), "APPROVAL_GATE")
    count = report["totalFrames"]
    require(240 <= count <= 300 and report["durationSeconds"] == count / 30, "PROOF_DURATION")
    require((report["width"], report["height"], report["fps"], report["audio"]) == (1080, 1920, 30, False), "PROOF_FORMAT")
    require(count == fixture["presentation"]["totalFrames"], "FIXTURE_FRAME_COUNT")
    video = ROOT / "public-review" / report["video"]["file"]
    require(sha(video) == report["video"]["sha256"], "ORIGINAL_MP4_BINDING")
    source = report["sourceCommit"]
    require(run("git", "-C", str(REPO), "rev-parse", source + "^{commit}").decode().strip() == source, "SOURCE_COMMIT")
    source_files = [fixture_path, ROOT / "wave_runtime.mjs", ROOT / "render_proof.mjs",
                    ROOT.parents[1] / "web/map_infographic_v1/wave_visual_v3.mjs",
                    ROOT.parents[1] / "web/map_infographic_v1/wave_gpu_adapter_v3.mjs"]
    source_bindings = []
    for path in source_files:
        # Source files are the exact already committed inputs used for rendering.
        committed = run("git", "-C", str(REPO), "show", source + ":" + str(path.relative_to(REPO)))
        require(committed == path.read_bytes(), "RENDER_SOURCE_CHANGED: " + str(path))
        source_bindings.append({"path": str(path.relative_to(REPO)), "sha256": sha(path)})
    probe = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(video)))
    require(len(probe["streams"]) == 1, "SILENT_SINGLE_STREAM")
    stream = probe["streams"][0]
    require((stream["codec_type"], stream["codec_name"], stream["width"], stream["height"], stream["avg_frame_rate"])
            == ("video", "h264", 1080, 1920, "30/1"), "PROBED_FORMAT")
    require(int(stream["nb_read_frames"]) == count and float(stream["duration"]) == count / 30, "PROBED_TIMING")

    rows = report["frames"]
    require(len(rows) == count, "ALL_RENDERED_FRAMES")
    contact_frames = defaultdict(list)
    pulse_frames, major_frames = [], []
    contact_order = None
    complete_frame, hold_frames = None, None
    max_contacts = 0
    event_start = fixture["presentation"]["eventStartFrame"]
    for index, row in enumerate(rows):
        require(row["frame"] == index and row["glError"] == 0, "FRAME_ORDER_OR_GL_ERROR")
        wave = row["wave"]
        require(all(wave["protection"][key] == 0 for key in
                    ("protectedChangedPixels", "markerChangedPixels", "outsideRoiChangedPixels", "safeAreaChangedPixels")), "PROTECTED_PIXEL_CHANGE")
        require(wave["geometryUnchanged"] and wave["nativeSourceUnchanged"] and not wave["closedPropagationRing"], "PROTECTED_CORE_OR_RING")
        if index < event_start:
            require(not wave["enabled"], "EVENT_BEFORE_LOCK")
            continue
        require(wave["enabled"] and row["cameraLocked"], "EVENT_DETAIL_LOCK")
        d = wave["diagnostics"]
        require(d["closedRingCount"] == 0 and 0 <= d["majorFrontCount"] <= 3, "OPEN_MAJOR_FRONT_COUNT")
        require(not d["sourceGeometryMutation"] and not d["physicalSimulation"] and not d["repeatBlink"], "VISUAL_SEMANTICS")
        require(d["singleOriginPulse"], "SINGLE_ORIGIN_PULSE")
        require(wave["graphics"]["nativeStateRestored"], "NATIVE_GPU_STATE")
        for item in wave["controls"]["propagations"]:
            coordinates = item["geometry"]["coordinates"]
            require(len(coordinates) >= 2 and coordinates[0] != coordinates[-1], "CLOSED_PROPAGATION_GEOMETRY")
        if wave.get("originPulse", {}).get("active"):
            pulse_frames.append(index)
        major_frames.append({"frame": index, "majorFronts": d["majorFrontCount"]})
        max_contacts = max(max_contacts, d["coastContactCount"])
        for contact_id in d["coastContactIds"]:
            contact_frames[contact_id].append(index)
        if contact_order is None:
            contact_order = d["coastArrivalOrder"]
            complete_frame = event_start + d["completeFrame"]
            hold_frames = d["holdFrames"]
        require(contact_order == d["coastArrivalOrder"] and hold_frames == d["holdFrames"], "DETERMINISTIC_CONTACT_PLAN")
    require(contiguous(pulse_frames) and len(pulse_frames) > 0, "ONE_CONTINUOUS_ORIGIN_PULSE")
    require(max(row["majorFronts"] for row in major_frames) == 3, "THREE_DISTINCT_MAJOR_FRONTS")
    require(len(contact_frames) == len(contact_order), "ALL_LOCAL_COAST_CONTACTS")
    require(all(contiguous(value) for value in contact_frames.values()), "CONTACT_REPEATED_BLINK")
    require(max_contacts < len(contact_order), "SIMULTANEOUS_WHOLE_COAST_FLASH")
    expected_order = [row["id"] for row in contact_order]
    actual_order = [key for key, _ in sorted(contact_frames.items(), key=lambda item: (item[1][0], expected_order.index(item[0])))]
    require(actual_order == expected_order, "SEQUENTIAL_COAST_ARRIVAL_ORDER")
    annotations = fixture["presentation"]["annotations"]
    text = [row["display_value"] + " " + row.get("unit", "") for row in annotations]
    require(text == ["2011.03.11 발생"], "MINIMAL_FACT_TEXT")
    require(all("해안 도달" not in value and "전개도" not in value and "개념도" not in value for value in text), "TEST_TEXT_REMOVED")

    checkpoints = report["checkpoints"]
    require(len(checkpoints) == 8, "EIGHT_CHECKPOINTS")
    expected = {(row["frame"], row["file"]) for row in fixture["presentation"]["checkpoints"]}
    require({(row["frame"], row["file"]) for row in checkpoints} == expected, "CHECKPOINT_FRAME_BINDING")
    for row in checkpoints:
        path = ROOT / "public-review" / row["file"]
        require(sha(path) == row["sha256"] == rows[row["frame"]]["png_sha256"] and row["sourceMatchesEncodedNativeFrame"], "EXACT_NATIVE_CHECKPOINT_INPUT")

    private = ROOT / "evidence/decoded-audit"
    private.mkdir(exist_ok=True)
    decoded_frames = sorted({row["frame"] for row in checkpoints} | {54, 110, 135, 208, count - 1})
    expression = "+".join("eq(n\\," + str(frame) + ")" for frame in decoded_frames)
    run("ffmpeg", "-v", "error", "-threads", "2", "-i", str(video), "-vf", "select=" + expression,
        "-fps_mode", "passthrough", "-threads", "2", "-y", str(private / "TEMP_%03d.png"))
    decoded_files = {}
    for index, frame in enumerate(decoded_frames, 1):
        path = private / ("FRAME_%03d.png" % frame)
        (private / ("TEMP_%03d.png" % index)).replace(path)
        decoded_files[frame] = path

    fidelity = []
    for row in checkpoints:
        original = rgba_png(ROOT / "public-review" / row["file"]).astype(np.int16)
        decoded = rgba_png(decoded_files[row["frame"]]).astype(np.int16)
        diff = original - decoded
        mse = float(np.mean(diff.astype(np.float64) ** 2))
        psnr = 99 if mse == 0 else 10 * math.log10(255 * 255 / mse)
        require(psnr >= 34, "ENCODED_FRAME_VISUAL_FIDELITY")
        fidelity.append({"frame": row["frame"], "nativeInputSha256": row["sha256"],
                         "decodedPng": record(decoded_files[row["frame"]]), "psnrDb": round(psnr, 4),
                         "meanAbsoluteChannelError": round(float(np.mean(np.abs(diff))), 4)})

    # Measured from actual decoded pixels, not inferred from a timeline diagnostic.
    colors, active, baseline = measure_colors(video, rows, count)
    result = {
        "schema": 1, "status": "PASS" if visual_review else "TECHNICAL_PASS_VISUAL_REVIEW_REQUIRED",
        "scope": "ACTUAL_DECODED_TSUNAMI_WAVE_VISUAL_PROOF", "originalMp4": record(video),
        "renderReport": record(report_path), "sourceCommit": source, "sourceBindings": source_bindings,
        "format": {"width": 1080, "height": 1920, "fps": 30, "frames": count, "durationSeconds": count / 30, "audio": False},
        "decodedVideoInspection": {"reviewerInspectedActualEncodedFrames": bool(visual_review),
                                   "frameFiles": [record(decoded_files[frame]) for frame in decoded_frames],
                                   "checkpointFidelity": fidelity, "allFramesDecoded": count, "decodeErrors": 0},
        "wave": {"closedPropagationRings": 0, "maximumMajorFronts": 3, "singleOriginPulseFrames": pulse_frames,
                 "contactOrder": actual_order, "maximumSimultaneousLocalContacts": max_contacts,
                 "contactWindows": [{"id": key, "firstFrame": value[0], "lastFrame": value[-1]} for key, value in contact_frames.items()],
                 "oneAccentPerCoastInterval": True, "repeatBlink": False, "wholeCountryFlash": False,
                 "completeFrame": complete_frame, "compiledHorizonHoldFrames": hold_frames,
                 "timelineHoldInProofFrames": max(0, count - complete_frame),
                 **measurement_fields(colors, active, count, baseline)},
        "protection": {"checkedFrames": count, "protectedChangedPixels": 0, "markerChangedPixels": 0,
                       "outsideRoiChangedPixels": 0, "safeAreaChangedPixels": 0, "glErrors": 0},
        "publicText": text, "testExplanatoryTextRemoved": True,
        "physicalSimulation": False, "actualMeasuredWaveArrivalTimeClaim": False,
        "areaWarCoreRedeveloped": False, "permanentGateExecuted": False,
        "tools": {"python": platform.python_version(), "numpy": np.__version__,
                  "ffmpeg": run("ffmpeg", "-version").decode().splitlines()[0]},
        "next": "USER_VIDEO_REVIEW_REQUIRED",
    }
    if visual_review:
        result["visualReview"] = {"waveShape": "OPEN_COAST_REFERENCED_CURVES_WITH_DISTINCT_PROFILE_VARIATION",
                                  "direction": "ORIGIN_TO_PACIFIC_COAST", "arrival": "SHORT_ORDERED_LOCAL_COAST_ACCENTS",
                                  "mobileReadability": "PASS", "contrast": "PASS", "rhythm": "PASS",
                                  "limitations": ["Illustrative wave and arrival timing; not a physical tsunami or inundation model."]}
        observed_hold = result["wave"]["observedFinalMapHoldFrames"]
        if observed_hold > 45:
            result["visualReview"]["warnings"] = [
                f"Compiled horizon hold: {hold_frames} frames ({hold_frames / 30:.2f} s); "
                f"timeline hold inside this proof: {max(0, count - complete_frame)} frames. "
                f"Measured map/date-only hold after the last >=12-pixel decoded wave/contact signal: {observed_hold} frames "
                f"({observed_hold / 30:.2f} s); keep as an explicit user rhythm review point."]
    (ROOT / "evidence/VISUAL_AUDIT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "videoSha256": result["originalMp4"]["sha256"],
                      "frames": count, "lastVisibleWavePixelFrame": active[-1],
                      "observedFinalMapHoldFrames": count - 1 - active[-1]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual-review-pass", action="store_true", help="Use only after inspecting the extracted actual decoded video frames.")
    parser.add_argument("--refresh-visible-measurement", action="store_true", help="Correct only the visible-pixel measurement in an existing PASS receipt; do not repeat gates.")
    args = parser.parse_args()
    if args.refresh_visible_measurement:
        refresh_measurement()
    else:
        audit(args.visual_review_pass)
