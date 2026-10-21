"""Source resolution audit and fail-closed requested camera admission.

This owner does not alter LOCAL_DETAIL_ADMISSION_V1 or create a replacement
certificate. A separately requested Regional source review is not a successful
execution of the tighter camera design.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[1]
REGIONAL = HERE.parent / "planner-scene-json-v1/fixtures/REGIONAL-plan.json"
SAMPLES = HERE.parent / "astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip"
SCHEMA = "WORLD_ENGINE_EVENT_DIRECTOR_CAMERA_ADMISSION_V2"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bounds(value):
    return (isinstance(value, list) and len(value) == 4
        and all(type(x) in (int, float) and math.isfinite(x) for x in value)
        and -180 <= value[0] < value[2] <= 180
        and -90 <= value[1] < value[3] <= 90)


def contains(outer, inner):
    return bounds(outer) and bounds(inner) and all((
        outer[0] <= inner[0], outer[1] <= inner[1],
        outer[2] >= inner[2], outer[3] >= inner[3]))


def source_resolution_assessment(source, extent, output=(1080, 1920)):
    """Preserve native spacing; an enlarged PNG never improves this result."""
    if not bounds(extent):
        raise ValueError("DIRECTOR_CAMERA_GEOGRAPHIC_BOUNDS_REQUIRED")
    spacing = source.get("pixelSpacing")
    valid = (isinstance(spacing, list) and len(spacing) == 2
        and all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in spacing))
    density = ([spacing[0] * output[0] / (extent[2] - extent[0]),
                spacing[1] * output[1] / (extent[3] - extent[1])] if valid else None)
    covered = contains(source.get("bounds"), extent)
    return {"sourceId": source.get("sourceId"), "sourceSHA256": source.get("sha256"),
        "sourceBounds": deepcopy(source.get("bounds")), "nativePixelSpacing": deepcopy(spacing),
        "requestedBounds": deepcopy(extent), "output": list(output),
        "outputPixelsPerNativeTexel": density, "completeSourceFootprint": covered,
        "nativeDensitySufficient": valid and max(density) <= 1,
        "strictSamplingReady": valid and max(density) <= 1 and covered,
        "minimumExtentFromNativeSampling": ([spacing[0] * output[0], spacing[1] * output[1]] if valid else None),
        "absoluteAccuracyCertified": False,
        "samplingReadinessIsNotPositionalAccuracy": True}


def actual_source_descriptors():
    """Read retained descriptors, not a new dataset or a provider claim."""
    regional = json.loads(REGIONAL.read_bytes())
    with zipfile.ZipFile(SAMPLES) as archive:
        manifest_raw = archive.read("DATA_MANIFEST.json")
        original = json.loads(manifest_raw)
    sources = []
    terrain = regional["assets"]["terrain"]
    sources.append({"sourceId": "PRESERVED_NE1_BASELINE", "sha256": terrain["sha256"],
        "bounds": terrain["bounds"], "dimensions": terrain["dimensions"],
        "pixelSpacing": terrain["pixelSpacing"], "license": terrain["license"],
        "sourceURL": terrain["source"]["url"], "role": "baselineBakedRelief",
        "absoluteAccuracyCertified": False})
    for dataset in original["datasets"]:
        sources.append({"sourceId": dataset["id"], "sha256": dataset["sha256"],
            "bounds": dataset["sample_extent"], "dimensions": dataset["dimensions"],
            "pixelSpacing": dataset.get("sample_resolution_degrees"),
            "license": dataset["license"], "licenseURL": dataset["license_url"],
            "sourceURL": dataset["original_url"], "role": dataset["data_class"],
            "absoluteAccuracyCertified": False,
            "historicalCollectionCompatibility": dataset["engine_compatibility"]})
    return {"regionalPlanSHA256": sha(REGIONAL.read_bytes()),
        "nativeMinimumBounds": regional["framing"]["bounds"],
        "nativeSafeArea": regional["layout"]["safe"],
        "sampleArchiveSHA256": sha(SAMPLES.read_bytes()),
        "sampleManifestSHA256": sha(manifest_raw), "sources": sources,
        "geometry": {"cartographicScaleDenominator": 50_000_000,
            "positionalErrorMeters": None, "absoluteAccuracyCertified": False,
            "strictGeometryAdmission": "BLOCKED_UNVERIFIED_SOURCE_POSITIONAL_ACCURACY"}}


def build_camera_admission(*, source_plan_sha256, camera_profile_sha256, requested_design):
    actual = actual_source_descriptors()
    requests = []
    for row in requested_design:
        extent = row["requestedBounds"]
        assessments = [source_resolution_assessment(source, extent) for source in actual["sources"]]
        # Unknown positional accuracy and missing source-qualified complete event
        # geometry remain blockers even when one colour raster has enough texels.
        requests.append({**deepcopy(row), "status": "BLOCKED_REQUESTED_LOCAL",
            "admitted": False, "substituteBounds": None,
            "sourceAssessments": assessments,
            "blockers": ["CAMERA_LOCAL_ADMISSION_REQUIRED", "VERIFIED_LOCAL_GIS_ACCURACY_REQUIRED",
                "DETAILED_EVENT_GEOMETRY_REQUIRED"],
            "strictNativePolicyChanged": False})
    return {"schema": SCHEMA, "version": 2, "sourcePlanSHA256": source_plan_sha256,
        "cameraProfileSHA256": camera_profile_sha256,
        "sourceEvidence": actual,
        "requestedCamera": {"purpose": "REQUESTED_LOCAL", "status": "BLOCKED",
            "ready": False, "requests": requests, "automaticWideningAllowed": False},
        "regionalSourceReview": {"purpose": "REGIONAL_SOURCE_REVIEW",
            "readyForSeparateSoftwarePreflight": True,
            "minimumBounds": deepcopy(actual["nativeMinimumBounds"]),
            "localCertificate": False, "requestedLocalContractSatisfied": False,
            "originalRegionalFloorPreserved": True,
            "nativeLayoutValidationRequiredBeforeDraw": True,
            "actualPixelsRequiredForReview": True},
        "productionEligible": False, "nvidiaHardwareVerified": False,
        "visualQualityApproved": False}


def validate_camera_admission(document, request, resolved_documents):
    """Server-owned P1 callback, returning separate production/review readiness."""
    if document.get("schema") != SCHEMA or document.get("version") != 2:
        raise ValueError("DIRECTOR_CAMERA_ADMISSION_VERSION_UNSUPPORTED")
    profile_path = HERE / "fixtures/CAMERA_REVIEW_PROFILE.json"
    raw = profile_path.read_bytes()
    profile = json.loads(raw)
    if (document.get("sourcePlanSHA256") != request["sourcePlanSha256"]
            or profile.get("sourcePlanSHA256") != request["sourcePlanSha256"]):
        raise ValueError("DIRECTOR_CAMERA_SOURCE_PLAN_MISMATCH")
    if (profile.get("cameraPurpose") != "REGIONAL_SOURCE_REVIEW"
            or profile.get("requestedLocalContractSatisfied") is not False):
        raise ValueError("DIRECTOR_CAMERA_EXPLICIT_REVIEW_PURPOSE_REQUIRED")
    expected = build_camera_admission(source_plan_sha256=request["sourcePlanSha256"],
        camera_profile_sha256=sha(raw), requested_design=profile["requestedLocalDesign"])
    if document != expected:
        raise ValueError("DIRECTOR_CAMERA_ADMISSION_SOURCE_OR_POLICY_CHANGED")
    event_profile = resolved_documents.get("eventDirectorProfileRef")
    event_raw = (HERE / "fixtures/HISTORY_EVENT_PROFILE_V2.json").read_bytes()
    if (not isinstance(event_profile, dict)
            or event_profile != json.loads(event_raw)
            or profile["eventProfileSHA256"] != sha(event_raw)):
        raise ValueError("DIRECTOR_CAMERA_EVENT_PROFILE_SOURCE_MISMATCH")
    review = request.get("purpose") == "QUALIFIED_SOURCE_REVIEW"
    return {"ready": False, "reviewReady": review,
        "blockers": [{"code": "CAMERA_LOCAL_ADMISSION_REQUIRED", "status": "BLOCKED",
            "path": "cameraAdmissionRef.requestedCamera", "detail":
            "Requested Local camera is not admitted. Regional source review is an explicit separate software purpose."}],
        "requestedCameraStatus": "BLOCKED_REQUESTED_LOCAL",
        "reviewCameraPurpose": "REGIONAL_SOURCE_REVIEW" if review else None,
        "originalRegionalFloorPreserved": True, "localCertificate": False,
        "nativeLayoutAndActualDrawStillRequired": True,
        "sourceEvidenceSHA256": sha(json.dumps(expected["sourceEvidence"], sort_keys=True,
            separators=(",", ":")).encode()),
        "nvidiaHardwareVerified": False, "visualQualityApproved": False}
