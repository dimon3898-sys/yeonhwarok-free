#!/usr/bin/env python3
"""Observe the selected source interface without repeating the whole decode.

Each still is SHA-bound to the full input audit. Screen-to-geographic conversion
reuses the camera registration and its actual measured relative similarity. The
output contains observed samples, not a replacement GIS object or a simulation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "reference-reproduction-v1"
START = 5.181813


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def screen_curve(image):
    rgb = np.asarray(image.convert("RGB")).astype(np.float32)
    r, g, b = (rgb[:, :, i] for i in range(3))
    orange = (r > 75) & (r < 230) & (g > 14) & (g < 140) & (b < 90) & (b < g * .8) & (r > g * 1.5)
    # Compared with preflight B>120, B>80 admits actual terrain-shadowed Purple.
    # It still rejects blue water and saturated pure flag-blue using R>25.
    purple = (b > 80) & (r > 25) & (r < 155) & (g < 110) & (b > r * 1.15) & (b > g * 1.5)
    points = []
    for x in range(200, 1040, 8):
        oc, pc = orange[:, x - 5:x + 6].mean(axis=1), purple[:, x - 5:x + 6].mean(axis=1)
        co, cp = np.r_[0, np.cumsum(oc)], np.r_[0, np.cumsum(pc)]
        ys = np.arange(580, 1150)
        score = (co[ys - 4] - co[ys - 32]) / 28 * (cp[ys + 32] - cp[ys + 4]) / 28
        best = int(score.argmax())
        if score[best] >= .24:
            points.append({"screen": [x, int(ys[best])], "color_adjacency_score": round(float(score[best]), 4), "confidence": "HIGH_COLOR_SUPPORT" if score[best] >= .60 else "PARTIAL_COLOR_SUPPORT"})
    return points


def relative_pose(seconds, records):
    values = []
    for r in records:
        pose = r["camera_screen_tracking"]
        values.append((r["actual_pts_seconds"] - START, np.asarray([pose["scale"], pose["screen_rotation_degrees"], *pose["map_crop_center_displacement_pixels"]], dtype=float)))
    if seconds <= values[0][0]:
        result, bracket = values[0][1], [values[0][0], values[0][0]]
    elif seconds >= values[-1][0]:
        result, bracket = values[-1][1], [values[-1][0], values[-1][0]]
    else:
        index = next(i for i in range(len(values) - 1) if values[i][0] <= seconds <= values[i + 1][0])
        a, b = values[index], values[index + 1]
        weight = (seconds - a[0]) / (b[0] - a[0])
        result, bracket = a[1] * (1 - weight) + b[1] * weight, [a[0], b[0]]
    return {"scale": float(result[0]), "relative_roll_degrees": float(result[1]), "map_center_displacement_pixels": result[2:].tolist(), "measured_time_bracket_seconds": bracket, "between_measurements": bracket[0] != bracket[1] and seconds not in bracket, "interpolation": "LINEAR_BETWEEN_ACTUAL_MEASURED_SCREEN_SIMILARITIES"}


def screen_to_geo(point, bounds, initial_roll, pose):
    x, y = point
    dx, dy = pose["map_center_displacement_pixels"]
    angle = math.radians(initial_roll + pose["relative_roll_degrees"])
    qx, qy = x - 540 - dx, y - 960 - dy
    px = 540 + (math.cos(angle) * qx + math.sin(angle) * qy) / pose["scale"]
    py = 960 + (-math.sin(angle) * qx + math.cos(angle) * qy) / pose["scale"]
    west, south, east, north = bounds
    return [west + px / 1080 * (east - west), north - py / 1920 * (north - south)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration", type=Path, default=HERE / "evidence/camera_registration/ROTATION_DIAGNOSTIC.json")
    parser.add_argument("--output", type=Path, default=HERE / "evidence/front_reference")
    args = parser.parse_args()
    args.registration = args.registration.resolve()
    args.output = args.output.resolve()
    reg = json.loads(args.registration.read_text())
    audit_path = HERE / "evidence/input_audit/reference/REPORT.json"
    audit = json.loads(audit_path.read_text())
    tracking_path = OLD / "evidence/reference_tracking/TRACKING_REPORT.json"
    tracking = json.loads(tracking_path.read_text())
    if audit["status"] != "FULL_DECODE_IDENTICAL_TO_PRESERVED_AUDIT" or not reg["inputGeometryUnchanged"]:
        raise RuntimeError("Actual input binding or immutable GIS gate failed")
    bounds, initial_roll = reg["startBounds"], reg.get("initialRollDegrees", 0)
    args.output.mkdir(parents=True, exist_ok=True)
    samples = []
    for sample in audit["samples"]:
        path = audit_path.parent / sample["png"]
        if digest(path) != sample["png_sha256"]:
            raise RuntimeError("Source audit PNG changed")
        image = Image.open(path).convert("RGB")
        relative = sample["actual_pts_seconds"] - START
        pose = relative_pose(relative, tracking["records"])
        points = screen_curve(image)
        for point in points:
            point["geographic_approximation"] = screen_to_geo(point["screen"], bounds, initial_roll, pose)
        overlay = image.copy()
        draw = ImageDraw.Draw(overlay)
        for p in points:
            x, y = p["screen"]
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#00ffff" if p["confidence"] == "HIGH_COLOR_SUPPORT" else "#ffff00")
        frame = min(149, round(sample["relative_requested_seconds"] * 30))
        name = f"FRONT_{frame:03d}.png"
        overlay.save(args.output / name, optimize=True)
        samples.append({"candidate_frame": frame, "requested_relative_seconds": sample["relative_requested_seconds"], "actual_relative_seconds": relative, "source_frame": sample["frame"], "source_pts_seconds": sample["actual_pts_seconds"], "source_png": sample["png"], "source_png_sha256": sample["png_sha256"], "pose": pose, "points": points, "high_confidence_points": sum(p["confidence"] == "HIGH_COLOR_SUPPORT" for p in points), "diagnostic_png": name, "diagnostic_png_sha256": digest(args.output / name)})
    report = {"schema": "OBSERVED_REFERENCE_FRONT_MEASUREMENTS_V2", "status": "OBSERVED_SAMPLES_READY_FOR_GENERIC_FIELD_AUTHORING", "reference_sha256": audit["source_sha256_before"], "selected_interval_seconds": [START, START + 5], "registration_path": str(args.registration.relative_to(HERE.parent.parent)), "registration_sha256": digest(args.registration), "registered_start_bounds": bounds, "initial_absolute_roll_degrees": initial_roll, "registration_metrics": reg["metrics"], "tracking_path": str(tracking_path.relative_to(HERE.parent.parent)), "tracking_sha256": digest(tracking_path), "samples": samples, "method": "Actual SHA-bound RGB PNG -> terrain-shadow-tolerant faction colour adjacency -> inverse SAME fitted screen camera", "missing_points_invented": False, "occluded_curve_interpolated": False, "temporal_monotonic_correction_applied": False, "source_geometry_modified": False, "source_video_modified": False, "quality_pass_claimed": False, "limits": ["Source itself is a counterfactual infographic, not factual combat geometry", "Badge-occluded samples remain missing", "Boundary samples are screen colour measurements with finite support, not exact GIS coordinates", "Intermediate camera poses use documented linear interpolation between measured samples", "Existing simplified coastline limits absolute registration precision", "Root field builder must disclose any noise/occlusion interpolation or temporal monotone correction"], "required_temp_only": 0}
    (args.output / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "samples": len(samples), "initial_roll_degrees": initial_roll, "points": [len(s["points"]) for s in samples]}), flush=True)


if __name__ == "__main__":
    main()
