"""Read actual completed capture PNGs; quantify isolated existing-pass pixels.

This does not draw or encode any map frame. It never grants historical, GPU or
visual-quality approval. All original PNG files are retained byte-for-byte.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]


def fail(code):
    raise ValueError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def pixel_metrics(first, second):
    """Exact PNG RGB differences, not SSIM/quality scores or visual approval."""
    a, b = np.asarray(first.convert("RGB")), np.asarray(second.convert("RGB"))
    if a.shape != b.shape or a.ndim != 3 or a.shape[2] != 3:
        fail("PIXEL_PROOF_IMAGE_DIMENSIONS_DIFFER")
    difference = np.abs(a.astype(np.int16) - b.astype(np.int16))
    changed = np.any(difference != 0, axis=2)
    count = int(np.count_nonzero(changed))
    if count:
        y, x = np.nonzero(changed)
        box = [int(x.min()), int(y.min()), int(x.max() + 1), int(y.max() + 1)]
    else:
        box = None
    return {"changedPixels": count, "changedPixelFraction": count / changed.size,
        "changedPixelBox": box, "meanAbsoluteRgb8Difference": float(difference.mean()),
        "maximumChannelDifference": int(difference.max()), "pixelContributionObserved": count > 0,
        "moreThanSinglePixel": count > 1}


def _geometry(rows):
    return [{"factionId": row.get("factionId"), "geometry": row.get("geometry")} for row in rows]


def frame_checks(frames):
    """Interpret actual source-field/camera diagnostics without inventing state."""
    result = {"allSameFieldAndClock": True, "allNativeCameraMatchesV5": True,
        "allCameraNumericallyAdmitted": True, "allLocalGuardsRetained": True,
        "allGlErrorsZero": True, "allMarkerSafeArea": True, "allReservationsInsideSafeArea": True,
        "sourceFieldFrameErrors": [], "cameraErrors": [], "safeAreaErrors": []}
    centers, extents, projected = [], [], []
    owner_changes = front_changes = 0
    previous_owner = previous_front = None
    for row in frames:
        diagnostic, global_frame = row.get("diagnostic", {}), row.get("globalFrame")
        frame, field_id = diagnostic.get("sourceControlFrame"), diagnostic.get("fieldId")
        masks = [*diagnostic.get("ownerMasks", []), diagnostic.get("unknownMask", {}),
                 diagnostic.get("contestedMask", {}), diagnostic.get("sharedFront", {})]
        consistent = (isinstance(field_id, str) and frame == global_frame
            and all(isinstance(mask, dict) and mask.get("fieldId") == field_id and mask.get("frame") == frame for mask in masks))
        if not consistent:
            result["allSameFieldAndClock"] = False
            result["sourceFieldFrameErrors"].append(row.get("frame"))
        camera = diagnostic.get("camera", {})
        native_bounds = diagnostic.get("actualCamera", {}).get("bounds")
        v5_bounds = camera.get("camera", {}).get("flatBounds")
        actual_camera = (isinstance(native_bounds, list) and len(native_bounds) == 4
            and native_bounds == v5_bounds and all(type(n) in (int, float) and math.isfinite(n) for n in native_bounds))
        if not actual_camera:
            result["allNativeCameraMatchesV5"] = False
            result["cameraErrors"].append(row.get("frame"))
        else:
            centers.append([(native_bounds[0] + native_bounds[2]) / 2, (native_bounds[1] + native_bounds[3]) / 2])
            extents.append([native_bounds[2] - native_bounds[0], native_bounds[3] - native_bounds[1]])
        if diagnostic.get("cameraNumericalAgreement", {}).get("matches") is not True:
            result["allCameraNumericallyAdmitted"] = False
        if camera.get("admission", {}).get("localUsed") is not False:
            result["allLocalGuardsRetained"] = False
        if diagnostic.get("glError") != 0:
            result["allGlErrorsZero"] = False
        if diagnostic.get("marker", {}).get("safeArea") is not True:
            result["allMarkerSafeArea"] = False
            result["safeAreaErrors"].append({"frame": row.get("frame"), "kind": "MARKER"})
        point = diagnostic.get("projectEventPoint")
        if isinstance(point, list) and len(point) == 2:
            projected.append(point)
        for draw in diagnostic.get("fillDraws", []):
            graphics = draw.get("graphics", {})
            safe = graphics.get("safeArea")
            if not isinstance(safe, list) or len(safe) != 4:
                result["allReservationsInsideSafeArea"] = False
                result["safeAreaErrors"].append({"frame": row.get("frame"), "kind": "SAFE_AREA_NOT_RECORDED"})
                continue
            for reservation in graphics.get("protectedReservations", []):
                box = reservation.get("box")
                if (not isinstance(box, list) or len(box) != 4
                        or not (safe[0] <= box[0] < box[2] <= safe[2] and safe[1] <= box[1] < box[3] <= safe[3])):
                    result["allReservationsInsideSafeArea"] = False
                    result["safeAreaErrors"].append({"frame": row.get("frame"), "kind": reservation.get("kind")})
        owner = canonical(_geometry(diagnostic.get("ownerMasks", [])))
        front = canonical(diagnostic.get("sharedFront", {}).get("geometry"))
        if previous_owner is not None and owner != previous_owner:
            owner_changes += 1
        if previous_front is not None and front != previous_front:
            front_changes += 1
        previous_owner, previous_front = owner, front
    result["sourceOwnerGeometryChangedAdjacentFrames"] = owner_changes
    result["sourceSharedFrontGeometryChangedAdjacentFrames"] = front_changes
    if centers:
        result["cameraMeasurements"] = {"startCenter": centers[0], "endCenter": centers[-1],
            "startExtentDegrees": extents[0], "endExtentDegrees": extents[-1],
            "minimumExtentDegrees": [min(v[axis] for v in extents) for axis in range(2)],
            "maximumExtentDegrees": [max(v[axis] for v in extents) for axis in range(2)],
            "maximumZoomRelativeToStart": [extents[0][axis] / min(v[axis] for v in extents) for axis in range(2)],
            "maximumCenterDistanceFromStartDegrees": max(math.dist(center, centers[0]) for center in centers),
            "maximumAdjacentCenterStepDegrees": max((math.dist(b, a) for a, b in zip(centers, centers[1:])), default=0),
            "maximumAdjacentProjectedEventStepPixels": max((math.dist(b, a) for a, b in zip(projected, projected[1:])), default=0),
            "globalDerivativeContinuityClaimed": False}
    return result


def _read_image(public, item):
    name = item.get("file")
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".png"):
        fail("PIXEL_PROOF_IMAGE_NAME_INVALID")
    path = public / name
    if path.is_symlink() or not path.is_file():
        fail("PIXEL_PROOF_IMAGE_MISSING_OR_SYMLINK")
    raw = path.read_bytes()
    expected = item.get("sha256", item.get("pngSHA256"))
    if hashlib.sha256(raw).hexdigest() != expected:
        fail("PIXEL_PROOF_IMAGE_HASH_MISMATCH")
    image = Image.open(path)
    image.load()
    if image.size != (1080, 1920):
        fail("PIXEL_PROOF_CANONICAL_IMAGE_REQUIRED")
    return image.convert("RGB")


def analyze(capture_root, *, report_out=None, comparison_out=None):
    capture_root = Path(capture_root)
    capture_file, public = capture_root / "proof/CAPTURE_REPORT.json", capture_root / "public-review"
    raw = capture_file.read_bytes()
    report = json.loads(raw)
    frames, total = report.get("frames", []), report.get("totalFrames")
    if (report.get("schema") != "WORLD_ENGINE_SOURCE_SCENE_CAPTURE_V2"
            or report.get("status") != "SOFTWARE_PREVIEW_COMPLETE" or report.get("fullDecode") != "PASS"
            or type(total) is not int or report.get("newlyRenderedFrames") != total or len(frames) != total
            or [f.get("frame") for f in frames] != list(range(total))):
        fail("PIXEL_PROOF_COMPLETED_ACTUAL_CAPTURE_REQUIRED")
    start = report.get("globalFrameRange", [None])[0]
    if type(start) is not int or [f.get("globalFrame") for f in frames] != list(range(start, start + total)):
        fail("PIXEL_PROOF_GLOBAL_FRAME_GAP")
    video = report.get("video", {})
    video_name = video.get("file")
    if not isinstance(video_name, str) or Path(video_name).name != video_name or not video_name.endswith(".mp4"):
        fail("PIXEL_PROOF_VIDEO_NAME_INVALID")
    video_path = public / video_name
    if video_path.is_symlink() or not video_path.is_file():
        fail("PIXEL_PROOF_VIDEO_MISSING_OR_SYMLINK")
    video_hash = hashlib.sha256(video_path.read_bytes()).hexdigest()
    if video_hash != video.get("sha256") or video_path.stat().st_size != video.get("bytes"):
        fail("PIXEL_PROOF_VIDEO_HASH_MISMATCH")
    streams = report.get("ffprobe", {}).get("streams", [])
    if (len(streams) != 1 or streams[0].get("codec_name") != "h264"
            or streams[0].get("width") != 1080 or streams[0].get("height") != 1920
            or streams[0].get("avg_frame_rate") != "30/1" or int(streams[0].get("nb_frames", -1)) != total):
        fail("PIXEL_PROOF_VIDEO_METADATA_INCOMPLETE")
    expected_checkpoints = sorted({0, 30, 60, 90, 120, 150, total - 1} & set(range(total)))
    checkpoints = report.get("checkpoints", [])
    if [r.get("frame") for r in checkpoints] != expected_checkpoints:
        fail("PIXEL_PROOF_CHECKPOINT_SEQUENCE_INCOMPLETE")
    images = {row["frame"]: _read_image(public, row) for row in checkpoints}
    for row in checkpoints:
        if row["sha256"] != frames[row["frame"]].get("pngSHA256"):
            fail("PIXEL_PROOF_CHECKPOINT_NOT_MAIN_DRAW")
    ablations = {row["id"]: row for row in report.get("ablations", [])}
    if set(ablations) != {"CONTROL_OFF", "FRONT_OFF", "ALL_ON"}:
        fail("PIXEL_PROOF_ABLATIONS_INCOMPLETE")
    probe = total // 2
    if any(row.get("frame") != probe for row in ablations.values()):
        fail("PIXEL_PROOF_ABLATION_FRAME_MISMATCH")
    views = {key: _read_image(public, value) for key, value in ablations.items()}
    diagnostics = [row["diagnostic"] for row in ablations.values()]
    ablation_same_inputs = all(canonical({key: d.get(key) for key in ("camera", "actualCamera", "fieldId", "ownerMasks", "sharedFront", "sourceControlFrame")}) ==
        canonical({key: diagnostics[0].get(key) for key in ("camera", "actualCamera", "fieldId", "ownerMasks", "sharedFront", "sourceControlFrame")}) for d in diagnostics)
    deterministic = ablations["ALL_ON"].get("rawSHA256") == frames[probe].get("rawSHA256")
    checks = frame_checks(frames)
    result = {"schema": "WORLD_ENGINE_ACTUAL_SOURCE_PIXEL_PROOF_V2", "captureReportSHA256": hashlib.sha256(raw).hexdigest(),
        "jobId": report.get("jobId"), "classification": report.get("classification"),
        "actualMainFrames": total, "actualCheckpointCount": len(checkpoints), "globalFrameRange": report.get("globalFrameRange"),
        "videoSHA256": video_hash, "videoMetadataAndHashVerified": True,
        "sameFrameAblationInputs": ablation_same_inputs, "sameFrameRandomAccessRedrawRawExact": deterministic,
        "ablationProbeFrame": probe, "frames": checks,
        "isolatedFrontContribution": pixel_metrics(views["ALL_ON"], views["FRONT_OFF"]),
        "isolatedFillContribution": pixel_metrics(views["FRONT_OFF"], views["CONTROL_OFF"]),
        "firstToLastCombinedCameraAndFieldDifference": pixel_metrics(images[0], images[total - 1]),
        "interpretation": {"CONTROL_OFF": "Disables both control fills and shared-front passes; marker/caption/native terrain retained",
            "FRONT_OFF": "Control fills on, shared-front passes off",
            "ALL_ON": "Control fills and shared-front passes on",
            "isolationCondition": "Ablations use identical actual V5 camera/current field; ALL_ON must reproduce main probe raw hash",
            "firstLastLimitation": "Combined camera and source-field change, not an isolated fill or frontier motion measure"},
        "renderEvidenceChecks": {"sameFrameInputs": ablation_same_inputs, "deterministicSameFramePixels": deterministic,
            "sameFieldAndClock": checks["allSameFieldAndClock"], "nativeCameraConsumer": checks["allNativeCameraMatchesV5"],
            "cameraNumericalContract": checks["allCameraNumericallyAdmitted"],
            "localGuardRetained": checks["allLocalGuardsRetained"], "glErrorsZero": checks["allGlErrorsZero"],
            "markerSafeArea": checks["allMarkerSafeArea"], "reservationSafeArea": checks["allReservationsInsideSafeArea"],
            "ownerGeometryChangesRecorded": checks["sourceOwnerGeometryChangedAdjacentFrames"] > 0,
            "sharedFrontGeometryChangesRecorded": checks["sourceSharedFrontGeometryChangedAdjacentFrames"] > 0,
            "frontMoreThanOnePixel": False, "fillMoreThanOnePixel": False},
        "technicalPixelEvidenceStatus": "UNVERIFIED", "historicalG3Achieved": False,
        "nvidiaVerified": False, "userApproved": False, "visualQualityApproved": False,
        "limitations": ["This is the explicitly authored non-historical demo, not Incheon historical footage.",
            "Polygon/source changes and camera motion are measured separately; no invented ownership or troop positions are validated.",
            "Frame/PNG proof and whole-file decode do not establish final video quality or physical-mobile review.",
            "Safe-area checks use actual recorded marker/reservation boxes; full image semantic collision adjudication remains user review.",
            "No claim of comparison with unavailable64306 actual original pixels."]}
    result["renderEvidenceChecks"]["frontMoreThanOnePixel"] = result["isolatedFrontContribution"]["moreThanSinglePixel"]
    result["renderEvidenceChecks"]["fillMoreThanOnePixel"] = result["isolatedFillContribution"]["moreThanSinglePixel"]
    result["technicalPixelEvidenceStatus"] = "PASS" if all(result["renderEvidenceChecks"].values()) else "NEEDS_REWORK"
    if comparison_out is not None:
        destination = Path(comparison_out)
        _new_target(destination)
        width, height, label_height = 360, 640, 38
        contact = Image.new("RGB", (width * 3, height + label_height), "#101820")
        draw = ImageDraw.Draw(contact)
        for index, key in enumerate(("CONTROL_OFF", "FRONT_OFF", "ALL_ON")):
            contact.paste(views[key].resize((width, height), Image.Resampling.LANCZOS), (index * width, label_height))
            draw.text((index * width + 8, 11), key + f" / actual f{probe}", fill="white")
        contact.save(destination, "PNG")
        result["comparisonPNG"] = {"file": destination.name, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "meaning": "Three resized actual same-frame ablation PNGs; original full-resolution PNGs retained"}
    if report_out is not None:
        destination = Path(report_out)
        _new_target(destination)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return result


def _new_target(path):
    if not path.resolve().is_relative_to(HERE) or any(p.is_symlink() for p in (path, *path.parents)):
        fail("PIXEL_PROOF_OUTPUT_NEW_NAMESPACE_REQUIRED")
    if path.exists():
        fail("PIXEL_PROOF_REFUSE_OVERWRITE")
    path.parent.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, default=HERE / "reports/ACTUAL_PIXEL_PROOF.json")
    parser.add_argument("--comparison-out", type=Path, default=HERE / "public-review/DEMO_ABLATION_COMPARISON.png")
    arguments = parser.parse_args()
    facts = analyze(arguments.capture_root, report_out=arguments.report_out, comparison_out=arguments.comparison_out)
    print(json.dumps({key: facts[key] for key in ("technicalPixelEvidenceStatus", "actualMainFrames", "sameFrameRandomAccessRedrawRawExact", "isolatedFrontContribution", "isolatedFillContribution")}))
