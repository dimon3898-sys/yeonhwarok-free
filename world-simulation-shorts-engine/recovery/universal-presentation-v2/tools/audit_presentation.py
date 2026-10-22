"""Audit real completed captures; never create renderer pixels or approve quality."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
OLD = HERE.parent / "universal-data-pipeline-v1/tools/audit_videos.py"


def load(path):
    return json.loads(Path(path).read_text())


def exclusive_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def planar_area(geometry):
    """A reproducible degree-squared display diagnostic, never ground acreage."""
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    total = 0.0
    for polygon in polygons:
        rings = []
        for ring in polygon:
            rings.append(abs(sum(a[0] * b[1] - b[0] * a[1]
                                 for a, b in zip(ring, ring[1:]))) / 2)
        total += rings[0] - sum(rings[1:])
    return total


def frames_audit(name, capture, output):
    receipt = load(capture / "CAPTURE_RECEIPT.json")
    request = load(capture / "REQUEST.json")
    runtime = load(capture / "RUNTIME.json")
    frames = load(capture / "FRAME_EVIDENCE.json")["frames"]
    total = request["totalFrames"]
    checks = {
        "completedCapture": receipt["status"] == "TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED",
        "requested180ActualFrames": total == 180 and len(frames) == 180,
        "exactGlobalFrameOrder": [f["frame"] for f in frames] == list(range(total)),
        "softwareOnlyExplicit": receipt["softwareOnly"] is True and receipt["nvidiaVerified"] is False,
        "noBrowserErrors": receipt["browserErrors"] == [],
        "inputTracePresent": bool(request.get("inputTrace")),
        "realSceneCuts": request["transitions"] == [
            {"type": "CUT", "frame": s["startFrame"]} for s in request["segments"][1:]],
        "sourceQualificationBound": receipt["sourceQualificationSHA256"] ==
            runtime["sourceQualificationSHA256"],
    }
    segments = []
    mapping = []
    for index, segment in enumerate(request["segments"]):
        selected = [f for f in frames if f["segmentIndex"] == index]
        expected = segment["endFrame"] - segment["startFrame"]
        cameras = [f["diagnostic"]["camera"] for f in selected]
        bounds = [c["bounds"] for c in cameras]
        centers = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in bounds]
        spans = [b[2] - b[0] for b in bounds]
        modes, area_states, coverages, area_masses, route_fractions, positions = set(), set(), [], [], [], []
        identity = []
        segment_checks = {
            "exactLocalFrameOrder": [f["localFrame"] for f in selected] == list(range(expected)),
            "globalLocalBinding": all(f["frame"] == f["localFrame"] + segment["startFrame"] for f in selected),
            "actualCameraUnlocked": all(c["actualCameraLocked"] is False and
                c["actualSettleLocked"] is False for c in cameras),
            "nativeProjectionRecorded": all(bool(c["actualFactory"]) for c in cameras),
            "sourceCoversEveryFrame": all(f["diagnostic"]["material"]["fullViewportCovered"] is True
                and f["diagnostic"]["material"]["minimumSourceGutterPixels"] >= 1 - 1e-8 for f in selected),
            "nativeLayoutValid": all(f["diagnostic"]["layout"]["valid"] is True for f in selected),
            "allFrameGLErrorsZero": all(f["diagnostic"]["glError"] == 0 for f in selected),
            "allLocationProjectionRecorded": all(f["diagnostic"]["suppliedLocations"] for f in selected),
            "currentSourceGeometryBound": all(bool(f["diagnostic"]["sourceGeometryBinding"]) for f in selected),
            "noInventedDEMClaim": all(f["diagnostic"]["material"]["demEnabled"] is False for f in selected),
        }
        source_routes = {t["id"]: t for t in segment["scene"].get("routes", [])}
        source_geometries = {t["id"]: t["geometry"] for t in segment["scene"]["geometries"]}
        source_areas = {t["id"]: t for t in segment["scene"].get("areas", [])}
        source_locations = {t["id"]: t for t in segment["scene"]["locations"]}
        highlights = segment["presentation"].get("highlights", [])
        highlight_rows = []
        for f in selected:
            d = f["diagnostic"]
            for highlight in highlights:
                expected_visible = highlight["startFrame"] <= f["localFrame"] < highlight["endFrame"]
                rendered = [m for m in d["markers"] if m["id"] == highlight["id"]]
                segment_checks["highlightExactFrameWindows"] = segment_checks.get(
                    "highlightExactFrameWindows", True) and len(rendered) == int(expected_visible)
                if rendered:
                    segment_checks["highlightSuppliedAnchorPreserved"] = segment_checks.get(
                        "highlightSuppliedAnchorPreserved", True) and rendered[0]["anchor"] == source_locations[
                            highlight["locationId"]]["anchor"]
                    highlight_rows.append({"frame": f["frame"], "id": highlight["id"],
                                           "scale": rendered[0]["scale"]})
            for feature in d["features"]:
                modes.add(feature["engine"])
                if feature["engine"] == "EXISTING_FLOW_V2":
                    route_fractions.append(feature["routeFraction"])
                    positions.append(feature["objectPosition"])
                    admission = feature["admission"]
                    identity.append(feature["geometry"] == source_geometries[
                        source_routes[feature["id"]]["geometry_ref"]])
                    segment_checks["movingAdmissionForEveryFlowFrame"] = segment_checks.get(
                        "movingAdmissionForEveryFlowFrame", True) and admission["status"] == "MOVING_PROJECTION_READY"
                    segment_checks["noOldMovingAdmissionClaim"] = segment_checks.get(
                        "noOldMovingAdmissionClaim", True) and admission["oldEventAdmissionClaimed"] is False
                else:
                    area_states.add(feature["state"])
                    coverages.extend(a["coverage"] for a in feature["sourceAreas"])
                    area_masses.append(sum(planar_area(a["geometry"]) * a["alpha"] * a["coverage"]
                                           for a in feature["sourceAreas"]))
                    identity.extend(a["geometry"] == source_geometries[source_areas[a["id"]]["geometry_ref"]]
                                    for a in feature["sourceAreas"])
                    # Native geometry hashes in sourceGeometryBinding bind each output to the supplied data.
            mapping.append({"frame": f["frame"], "segment": index, "localFrame": f["localFrame"],
                "sceneId": segment["sceneId"], "cameraBounds": d["camera"]["bounds"],
                "sourceOriginalSHA256": d["material"]["sourceOriginalSHA256"],
                "sourceGeometryBinding": d["sourceGeometryBinding"],
                "actualFeatureChangedPixels": d["featureChangedPixels"],
                "locations": d["suppliedLocations"],
                "features": [{k: v for k, v in feat.items() if k in
                    {"id", "engine", "state", "stateId", "routeFraction", "objectFraction", "objectPosition",
                     "sourceAreas", "sourceFronts"}} for feat in d["features"]],
                "markers": d["markers"], "actualRawSHA256": f["rawSHA256"],
                "actualBaseRawSHA256": f["baseRawSHA256"]})
        moved = max(((x-centers[0][0]) ** 2 + (y-centers[0][1]) ** 2) ** .5 for x, y in centers)
        changed_base = len({f["baseRawSHA256"] for f in selected})
        segment_checks["actualBasePixelsChangeWithCamera"] = moved > 1e-7 and changed_base > 1
        segment_checks["sourceGeometryExactlyPreserved"] = all(identity)
        if route_fractions:
            segment_checks["routeTimelineProgresses"] = max(route_fractions) > min(route_fractions)
            segment_checks["currentObjectPositionChanges"] = len({json.dumps(v) for v in positions}) > 1
        if area_masses:
            segment_checks["territoryTimelineProgresses"] = max(area_masses) - min(area_masses) > 1e-8
        if highlights:
            segment_checks["highlightPulseScaleChanges"] = len({r["scale"] for r in highlight_rows}) > 1
        segments.append({"index": index, "sceneId": segment["sceneId"],
            "globalFrameRange": [segment["startFrame"], segment["endFrame"]],
            "sourceStyleId": selected[0]["diagnostic"]["material"]["styleId"],
            "cameraProfile": cameras[0]["profile"], "maximumCenterDisplacementDegrees": moved,
            "longitudeSpanRangeDegrees": [min(spans), max(spans)],
            "actualUniqueBaseFrames": changed_base,
            "engines": sorted(modes), "areaStates": sorted(area_states),
            "territoryCoverageRange": [min(coverages), max(coverages)] if coverages else None,
            "alphaWeightedPlanarAreaDiagnostic": {"units": "degrees_squared_not_ground_area",
                "minimum": min(area_masses), "maximum": max(area_masses),
                "first": area_masses[0], "last": area_masses[-1]} if area_masses else None,
            "routeFractionRange": [min(route_fractions), max(route_fractions)] if route_fractions else None,
            "highlightFrameAndScaleRecords": highlight_rows,
            "checks": segment_checks,
            "status": "PASS" if all(segment_checks.values()) else "FAIL"})
    checks["allSegmentChecks"] = all(s["status"] == "PASS" for s in segments)
    exclusive_json(output / f"{name}_INPUT_SCENE_PIXEL_MAPPING.json", {
        "schema": "WORLD_ENGINE_UP2_INPUT_SCENE_PIXEL_MAPPING_V1", "sourceInputSHA256": request["sourceInputSHA256"],
        "inputTrace": request["inputTrace"], "frames": mapping})
    return {"name": name, "checks": checks, "segments": segments,
            "status": "PASS" if all(checks.values()) else "FAIL", "quality": "USER_REVIEW_REQUIRED"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="append", required=True, help="NAME=PRIVATE_CAPTURE_DIRECTORY")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("up2_existing_readonly_video_auditor", OLD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for value in args.capture:
        name, directory = value.split("=", 1)
        if not name or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in name):
            raise ValueError("SAFE_ARTIFACT_NAME_REQUIRED")
        directory = Path(directory)
        row = frames_audit(name, directory, args.output)
        row["encodedVideo"] = module.audit(name, directory / "VIDEO.mp4", args.output, 180)
        # The existing auditor generated these thumbnails only by decoding the
        # actual H.264 stream. Split the long sheet into readable 60-frame pages.
        with Image.open(args.output / f"{name}_ALL_FRAMES.png") as sheet:
            for page in range(3):
                sheet.crop((0, page * 6 * 342, sheet.width, (page + 1) * 6 * 342)).save(
                    args.output / f"{name}_FRAMES_{page * 60:03d}_{page * 60 + 59:03d}_CONTACT_SHEET.png")
        rows.append(row)
    result = {"schema": "WORLD_ENGINE_UP2_ACTUAL_MOVIES_AUDIT_V1", "movies": rows,
        "technicalStatus": "PASS" if all(r["status"] == "PASS" and
            r["encodedVideo"]["technicalStatus"] == "PASS" for r in rows) else "FAIL",
        "visualQuality": "USER_REVIEW_REQUIRED", "nvidiaVerified": False, "paidExecuted": False}
    exclusive_json(args.output / "ACTUAL_MOVIES_AUDIT.json", result)
    print(json.dumps({"technicalStatus": result["technicalStatus"], "movies": [
        {"name": r["name"], "status": r["status"], "checks": r["checks"],
         "segmentChecks": [s["checks"] for s in r["segments"]]} for r in rows]}, indent=2))
    return 0 if result["technicalStatus"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
