"""Approximate reference-control registration of unchanged archival map pixels.

This is deliberately separate from the known-map-CRS georeferencer. WGS84 is
the reference data's target CRS, never a claim about the archival projection.
Registration residuals do not quantify the historical map's positional error.
Only original trace edges inside the fitted control footprint survive;
there is no extrapolation, clipping-intersection invention, or gap bridging.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import math

import numpy as np
from osgeo import gdal


FROZEN_MATH_DEPENDENCY = {
    "sourceCommit": "4c4f39a35f4618021bdf1541764fb5dc6eb334b6",
    "sourcePath": "world-simulation-shorts-engine/recovery/verified-front-data-v4/georeference.py",
    "packagedPath": "dependencies/georeference_v4.py",
    "SHA256": "caa495d4ef541fa0fc2959265327751bd0dc7cce2cca2a317e79b076e88aaa7c",
    "packaging": "EXACT_UNCHANGED_SOURCE_DEPENDENCY",
}
_dependency_path = Path(__file__).parent / FROZEN_MATH_DEPENDENCY["packagedPath"]
if hashlib.sha256(_dependency_path.read_bytes()).hexdigest() != FROZEN_MATH_DEPENDENCY["SHA256"]:
    raise ImportError("Frozen registration-math dependency hash mismatch")
_legacy_spec = importlib.util.spec_from_file_location(
    "v4_known_crs_registration_math", _dependency_path)
_legacy = importlib.util.module_from_spec(_legacy_spec)
_legacy_spec.loader.exec_module(_legacy)
RegistrationError = _legacy.GeoreferenceError
_fail, _text, _finite = _legacy._fail, _legacy._text, _legacy._finite
_canonical, _sha = _legacy._canonical, _legacy._sha
_hull, _inside, _area = _legacy._hull, _legacy._inside, _legacy._area
_affine, _distance_meters = _legacy._affine, _legacy._distance_meters

SCHEMA = "WORLD_ENGINE_APPROXIMATE_CONTROL_REGISTRATION_V1"
METHOD = "APPROXIMATE_REFERENCE_CONTROL_REGISTRATION"


def _hash(value, field):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        _fail("HASH_REQUIRED", f"{field} requires a lowercase SHA-256")
    return value


def _bind_file(path, expected, field):
    _hash(expected, field)
    try:
        actual = _sha(path)
    except OSError:
        _fail("BOUND_FILE_UNAVAILABLE", f"{field} bytes are unavailable")
    if actual != expected:
        _fail("BOUND_FILE_HASH_MISMATCH", f"{field} bytes do not match the recorded SHA-256")


def _pair(value, field):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        _fail("INVALID_DATA", f"{field} requires exactly two finite numbers")
    return [_finite(x, field) for x in value]


def _reference_features(path, spec):
    if not isinstance(spec, dict):
        _fail("INVALID_REFERENCE_DATA", "A licensed reference dataset is required")
    _bind_file(path, spec.get("SHA256"), "referenceDataset.SHA256")
    for field in ("sourceId", "sourceVersion", "sourceURL", "license", "licenseReference"):
        _text(spec.get(field), f"referenceDataset.{field}")
    if spec.get("CRS") != "EPSG:4326":
        _fail("REFERENCE_CRS_UNSUPPORTED", "Reference point geometry must explicitly use WGS84 lon/lat")
    key = _text(spec.get("featureIdProperty"), "referenceDataset.featureIdProperty")
    try:
        dataset = json.loads(Path(path).read_text())
    except (OSError, ValueError, UnicodeError):
        _fail("INVALID_REFERENCE_DATA", "Reference dataset must be valid GeoJSON")
    if (not isinstance(dataset, dict) or dataset.get("type") != "FeatureCollection"
            or not isinstance(dataset.get("features"), list)):
        _fail("INVALID_REFERENCE_DATA", "Reference dataset must be a GeoJSON FeatureCollection")
    crs = dataset.get("crs")
    if crs is not None and crs not in (
        {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        {"type": "name", "properties": {"name": "EPSG:4326"}},
    ):
        _fail("REFERENCE_CRS_UNSUPPORTED", "Reference GeoJSON declares an incompatible CRS")
    # IDs can repeat in an upstream dataset. A selected ambiguous ID is rejected,
    # rather than silently choosing one feature or filtering by a place name.
    by_id = {}
    for feature in dataset["features"]:
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
            continue
        identifier = feature["properties"].get(key)
        if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
            continue
        by_id.setdefault((type(identifier).__name__, identifier), []).append(feature)
    return by_id


def _controls(items, field, minimum, width, height, features):
    if not isinstance(items, list) or not minimum <= len(items) <= 128:
        _fail("INSUFFICIENT_CONTROLS", f"{field} requires {minimum}..128 original map points")
    points = []
    for item in items:
        if not isinstance(item, dict):
            _fail("INVALID_DATA", "Control points must be objects")
        identifier = _text(item.get("id"), "control.id")
        pixel = _pair(item.get("pixel"), "control.pixel")
        if not (0 <= pixel[0] <= width - 1 and 0 <= pixel[1] <= height - 1):
            _fail("PIXEL_OUTSIDE_ORIGINAL", "Control lies outside original raster pixel centers")
        reference_id = item.get("referenceFeatureId")
        if isinstance(reference_id, bool) or not isinstance(reference_id, (str, int)):
            _fail("REFERENCE_FEATURE_UNAVAILABLE", "A stable reference feature ID is required")
        matches = features.get((type(reference_id).__name__, reference_id), [])
        if len(matches) != 1:
            _fail("REFERENCE_FEATURE_UNAVAILABLE", "Reference feature ID is missing or ambiguous")
        geometry = matches[0].get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "Point":
            _fail("REFERENCE_FEATURE_NOT_POINT", "A control must bind a real reference Point")
        coordinate = _pair(geometry.get("coordinates"), "reference geometry")
        if not (-180 <= coordinate[0] <= 180 and -90 <= coordinate[1] <= 90):
            _fail("INVALID_REFERENCE_COORDINATE", "Reference point is outside WGS84 domain")
        # Never accept independently typed coordinates as an override of the
        # hash-bound dataset. An optional redundant value must agree exactly.
        if "coordinate" in item and _pair(item["coordinate"], "control.coordinate") != coordinate:
            _fail("REFERENCE_COORDINATE_MISMATCH", "Typed coordinate differs from bound reference point")
        points.append({"id": identifier, "pixel": pixel, "coordinate": coordinate,
                       "referenceFeatureId": reference_id,
                       "sourceReference": _text(item.get("sourceReference"), "control.sourceReference")})
    if (len({p["id"] for p in points}) != len(points)
            or len({tuple(p["pixel"]) for p in points}) != len(points)
            or len({(type(p["referenceFeatureId"]).__name__, p["referenceFeatureId"])
                    for p in points}) != len(points)):
        _fail("DUPLICATE_CONTROLS", "Control IDs, source pixels and reference features must be unique")
    return points


def _uncertainty(value, name):
    if not isinstance(value, dict):
        _fail("UNCERTAINTY_DECLARATION_REQUIRED", f"{name} uncertainty must be declared")
    status = value.get("status")
    if status not in ("UNQUANTIFIED", "DOCUMENTED_ESTIMATE", "SYNTHETIC_KNOWN"):
        _fail("UNCERTAINTY_DECLARATION_REQUIRED", f"{name} has unsupported uncertainty status")
    _text(value.get("sourceReference"), f"{name}.sourceReference")
    if status == "UNQUANTIFIED":
        if "meters" in value:
            _fail("UNQUANTIFIED_ERROR_IS_NOT_ZERO", "Unquantified source error cannot carry an invented number")
    else:
        _finite(value.get("meters"), f"{name}.meters", nonnegative=True)
    return copy.deepcopy(value)


def fit_reference_controls(map_path, reference_path, spec):
    """Measure an explicitly approximate affine registration, without admission.

    Quality limits are mandatory input from a documented visual-grade profile.
    A small fit/check residual never supplies unknown map/reference accuracy.
    A declared pre-fit split is preserved, but this function cannot authenticate
    when a researcher made that declaration; the report says so explicitly.
    """
    if not isinstance(spec, dict):
        _fail("INVALID_DATA", "A registration specification is required")
    spec = copy.deepcopy(spec)
    _canonical(spec)
    if spec.get("method") != METHOD or spec.get("mode") not in ("SOURCE_MAP", "SYNTHETIC"):
        _fail("INVALID_METHOD", "Use the separate approximate reference-control registration method")
    map_id = _text(spec.get("mapId"), "mapId")
    _bind_file(map_path, spec.get("originalSHA256"), "originalSHA256")
    raster = spec.get("raster")
    if not isinstance(raster, dict):
        _fail("INVALID_DATA", "Original raster dimensions are required")
    width, height = raster.get("width"), raster.get("height")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 2 for v in (width, height)):
        _fail("INVALID_DATA", "Original dimensions must be integer pixel counts >=2")
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    try:
        dataset = gdal.Open(str(map_path), gdal.GA_ReadOnly)
    except Exception:
        dataset = None
    finally:
        gdal.PopErrorHandler()
    if dataset is None:
        _fail("INVALID_ORIGINAL_RASTER", "Bound original is not a readable raster")
    dimensions = [dataset.RasterXSize, dataset.RasterYSize]
    dataset = None
    if dimensions != [width, height]:
        _fail("ORIGINAL_DIMENSION_MISMATCH", "Control pixels must use unchanged original dimensions")
    source_crs = spec.get("sourceCRS")
    if (not isinstance(source_crs, dict) or source_crs.get("status") != "UNKNOWN_FROM_MAP"
            or "definition" in source_crs):
        _fail("FALSE_SOURCE_CRS_CLAIM", "Do not assign the target CRS to an unknown archival map projection")
    _text(source_crs.get("sourceReference"), "sourceCRS.sourceReference")
    if spec.get("targetCRS") != "EPSG:4326":
        _fail("REFERENCE_CRS_UNSUPPORTED", "The supported reference target is explicitly WGS84 lon/lat")
    if spec.get("pixelConvention") != "PIXEL_CENTER":
        _fail("PIXEL_CONVENTION_REQUIRED", "Declare original zero-based PIXEL_CENTER coordinates")
    uncertainty = spec.get("uncertainty")
    if not isinstance(uncertainty, dict):
        _fail("UNCERTAINTY_DECLARATION_REQUIRED", "Map and reference uncertainty must be distinct")
    uncertainty = {key: _uncertainty(uncertainty.get(key), key)
                   for key in ("sourceMap", "referenceDataset")}
    if spec["mode"] != "SYNTHETIC" and any(
            u["status"] == "SYNTHETIC_KNOWN" for u in uncertainty.values()):
        _fail("SYNTHETIC_UNCERTAINTY_ON_SOURCE", "A real map cannot use synthetic certainty")
    profile = spec.get("qualityProfile")
    if not isinstance(profile, dict) or profile.get("grade") != "FACT_BASED_VISUAL_GRADE":
        _fail("QUALITY_PROFILE_REQUIRED", "Approximate mode needs an explicit visual-grade profile")
    for field in ("profileId", "sourceReference", "selectionBasis"):
        _text(profile.get(field), f"qualityProfile.{field}")
    limits = profile.get("limits")
    if not isinstance(limits, dict):
        _fail("QUALITY_LIMITS_REQUIRED", "Explicit fit, held-out and footprint limits are required")
    limits = {key: _finite(limits.get(key), key, positive=True) for key in (
        "maxFitResidualMeters", "maxCheckResidualMeters", "minCheckToFitHullRatio")}
    if limits["minCheckToFitHullRatio"] > 1:
        _fail("INVALID_DATA", "Minimum check/fit hull ratio cannot exceed one")
    features = _reference_features(reference_path, spec.get("referenceDataset"))
    controls = _controls(spec.get("controls"), "controls", 4, width, height, features)
    checks = _controls(spec.get("checkControls"), "checkControls", 3, width, height, features)
    if any({tuple(p[key]) if isinstance(p[key], list) else p[key] for p in controls}
           & {tuple(p[key]) if isinstance(p[key], list) else p[key] for p in checks}
           for key in ("id", "pixel", "coordinate", "referenceFeatureId")):
        _fail("CHECKS_NOT_INDEPENDENT", "Held-out points cannot reuse fit IDs, pixels, features or coordinates")
    split = spec.get("splitDeclaration")
    if (not isinstance(split, dict) or split.get("predeclared") is not True
            or split.get("fitIds") != [p["id"] for p in controls]
            or split.get("checkIds") != [p["id"] for p in checks]):
        _fail("SPLIT_DECLARATION_MISMATCH", "Preserve the exact declared independent fit/check split")
    _text(split.get("sourceReference"), "splitDeclaration.sourceReference")
    coordinates = [p["coordinate"] for p in controls + checks]
    if max(c[0] for c in coordinates) - min(c[0] for c in coordinates) >= 180:
        _fail("ANTIMERIDIAN_UNSUPPORTED", "An affine longitude fit cannot cross the longitude discontinuity")
    fit_hull, check_hull = _hull([p["pixel"] for p in controls]), _hull([p["pixel"] for p in checks])
    check_ratio = _area(check_hull) / _area(fit_hull)
    warnings = []
    if check_ratio < limits["minCheckToFitHullRatio"]:
        warnings.append("INDEPENDENT_CHECK_FOOTPRINT_SMALL_RELATIVE_TO_FIT")
    outside_checks = [p["id"] for p in checks if not _inside(p["pixel"], fit_hull)]
    if outside_checks:
        warnings.append("INDEPENDENT_CHECKS_OUTSIDE_FITTED_FOOTPRINT")
    pixels = np.array([p["pixel"] for p in controls], dtype=np.float64) + 0.5
    center, spread = pixels.mean(axis=0), pixels.std(axis=0)
    if np.any(spread <= 1e-12):
        _fail("COLLINEAR_CONTROLS", "Controls do not span both original pixel axes")
    design = np.column_stack((np.ones(len(pixels)), (pixels - center) / spread))
    if np.linalg.matrix_rank(design) != 3 or np.linalg.cond(design) > 1e8:
        _fail("COLLINEAR_CONTROLS", "Affine fit is rank deficient or ill conditioned")
    fitted, _, _, _ = np.linalg.lstsq(design, np.array([p["coordinate"] for p in controls]), rcond=None)
    slopes = fitted[1:] / spread[:, None]
    offset = fitted[0] - center @ slopes
    affine = [float(offset[0]), float(slopes[0, 0]), float(slopes[1, 0]),
              float(offset[1]), float(slopes[0, 1]), float(slopes[1, 1])]
    if abs(affine[1] * affine[5] - affine[2] * affine[4]) <= 1e-20:
        _fail("DEGENERATE_TRANSFORM", "Affine map has zero geographic area")

    def residuals(points):
        values = [{"id": p["id"], "meters": _distance_meters(_affine(affine, p["pixel"]), p["coordinate"])}
                  for p in points]
        distances = [p["meters"] for p in values]
        return {"unit": "meters", "method": "WGS84_AZIMUTHAL_EQUIDISTANT_RADIAL_DISTANCE",
                "points": values, "maximum": max(distances),
                "rms": math.sqrt(sum(v * v for v in distances) / len(distances))}

    fit_error, check_error = residuals(controls), residuals(checks)
    if fit_error["maximum"] > limits["maxFitResidualMeters"]:
        _fail("FIT_RESIDUAL_EXCEEDS_BUDGET", "Fit residual exceeds the declared visual-grade limit")
    if check_error["maximum"] > limits["maxCheckResidualMeters"]:
        _fail("CHECK_RESIDUAL_EXCEEDS_BUDGET", "Held-out residual exceeds the declared visual-grade limit")
    report = {"schema": SCHEMA, "method": METHOD, "mapId": map_id, "mode": spec["mode"],
              "status": "TECHNICAL_APPROXIMATION_REVIEW_REQUIRED", "runtimeAdmission": "NOT_ADMITTED",
              "historicalAccuracyVerified": False, "sourceProjectionKnown": False,
              "originalSHA256": spec["originalSHA256"], "raster": {"width": width, "height": height},
              "sourceCRS": source_crs, "targetCRS": "EPSG:4326", "axisOrder": "LONGITUDE_LATITUDE",
              "referenceDataset": spec["referenceDataset"],
              "transform": {"method": "AFFINE_PIXEL_TO_REFERENCE_LONLAT_APPROXIMATION",
                            "coefficients": affine, "pixelConvention": "PIXEL_CENTER",
                            "gdalCornerOffset": [0.5, 0.5]},
              "controls": controls, "checkControls": checks,
              "splitDeclaration": split, "splitPredeclarationExternallyVerified": False,
              "residuals": {"fit": fit_error, "independentCheck": check_error},
              "coverage": {"fitPixelHull": fit_hull, "checkPixelHull": check_hull,
                           "checkToFitHullRatio": check_ratio,
                           "outsideFitCheckIds": outside_checks,
                           "fitHullRole": "HARD_SOURCE_TRACE_SUPPORT_BOUNDARY",
                           "checkHullRole": "MODEL_VALIDATION_SPATIAL_DISTRIBUTION_WARNING_ONLY",
                           "checkFootprintThresholdRole": "WARNING_ONLY_IN_THIS_APPROXIMATE_METHOD",
                           "digitizationRule": "INSIDE_FIT_HULL_NO_EXTRAPOLATION_NO_SYNTHETIC_VERTICES"},
              "warnings": warnings,
              "uncertainty": {**uncertainty, "registrationResidualIsTotalAccuracy": False,
                              "totalPositionalAccuracyMeters": None,
                              "totalPositionalAccuracyStatus": "NOT_CERTIFIED"},
              "qualityProfile": profile,
              "software": {"gdal": gdal.VersionInfo("RELEASE_NAME"), "numpy": np.__version__},
              "frozenMathDependency": copy.deepcopy(FROZEN_MATH_DEPENDENCY),
              "inputSpec": spec}
    report["reportSHA256"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def transform_traced_parts(map_path, reference_path, report, parts):
    """Return exact supported source-edge subsets, retaining exclusion evidence.

    Never constructs a polygon or an intersection vertex. Unsupported edges
    remain explicitly recorded with their source indices and original pixels.
    Contiguous source parts remain separate even if they happen to touch.
    """
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        _fail("INVALID_REPORT", "An approximate reference-control report is required")
    recomputed = fit_reference_controls(map_path, reference_path, report.get("inputSpec"))
    if _canonical(recomputed) != _canonical(report):
        _fail("REPORT_MISMATCH", "Report differs from unchanged originals and recomputed measurements")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 10000:
        _fail("INVALID_TRACES", "Provide a bounded nonempty list of separate source trace parts")
    if sum(len(p) if isinstance(p, list) else 100001 for p in parts) > 100000:
        _fail("INVALID_TRACES", "At most 100000 original vertices may be supplied")
    width, height = report["raster"]["width"], report["raster"]["height"]
    lines, exclusions, dispositions = [], [], []
    for part_index, part in enumerate(parts):
        if not isinstance(part, list) or len(part) < 2:
            _fail("INVALID_TRACES", "Each source trace part requires at least two original vertices")
        pixels = [_pair(p, "trace vertex") for p in part]
        for pixel in pixels:
            if not (0 <= pixel[0] <= width - 1 and 0 <= pixel[1] <= height - 1):
                _fail("PIXEL_OUTSIDE_ORIGINAL", "A trace vertex lies outside original raster centers")
        supported = [_inside(p, report["coverage"]["fitPixelHull"]) for p in pixels]
        checked = [_inside(p, report["coverage"]["checkPixelHull"]) for p in pixels]
        dispositions.append({"partIndex": part_index, "vertices": [
            {"vertexIndex": i, "pixel": p, "insideSupportedFootprint": supported[i],
             "insideIndependentCheckFootprint": checked[i]}
            for i, p in enumerate(pixels)]})
        current = []

        def flush():
            if current:
                lines.append({"sourcePartIndex": part_index, "sourceVertexIndices": list(current),
                              "sourcePixels": [pixels[i] for i in current],
                              "coordinates": [_affine(report["transform"]["coefficients"], pixels[i])
                                              for i in current]})
                current.clear()

        for i in range(len(pixels) - 1):
            if supported[i] and supported[i + 1]:
                if not current:
                    current.append(i)
                current.append(i + 1)
            else:
                flush()
                exclusions.append({"sourcePartIndex": part_index, "sourceEdgeIndex": i,
                                   "sourceVertexIndices": [i, i + 1],
                                   "sourcePixels": [pixels[i], pixels[i + 1]],
                                   "reason": "OUTSIDE_FITTED_CONTROL_HULL"})
        flush()
    retained_count = sum(len(line["sourcePixels"]) for line in lines)
    retained_checked = sum(_inside(pixel, report["coverage"]["checkPixelHull"])
                           for line in lines for pixel in line["sourcePixels"])
    result = {"schema": "WORLD_ENGINE_SUPPORTED_SOURCE_TRACE_V1", "registrationReportSHA256": report["reportSHA256"],
              "status": "TECHNICAL_SOURCE_EDGE_SUBSET_REVIEW_REQUIRED", "historicalAccuracyVerified": False,
              "runtimeAdmission": "NOT_ADMITTED", "targetCRS": "EPSG:4326", "lines": lines,
              "excludedEdges": exclusions, "sourceVertexDispositions": dispositions,
              "inputParts": copy.deepcopy(parts), "inputPartCount": len(parts),
              "inputEdgeCount": sum(len(p) - 1 for p in parts),
              "retainedEdgeCount": sum(len(line["coordinates"]) - 1 for line in lines),
              "excludedEdgeCount": len(exclusions), "inventedVertexCount": 0,
              "independentCheckSpatialCoverage": {
                  "retainedVertexCount": retained_count,
                  "retainedVerticesInsideCheckHull": retained_checked,
                  "retainedVerticesOutsideCheckHull": retained_count - retained_checked,
                  "spatiallyUniformAccuracyCertified": False},
              "warnings": (["RETAINED_SOURCE_TRACE_NOT_FULLY_COVERED_BY_INDEPENDENT_CHECK_FOOTPRINT"]
                           if retained_checked != retained_count else []),
              "gapBridgingPerformed": False, "polygonInferred": False}
    if result["retainedEdgeCount"] + result["excludedEdgeCount"] != result["inputEdgeCount"]:
        _fail("INTERNAL_EDGE_ACCOUNTING_ERROR", "Every original edge must have exactly one disposition")
    result["traceSHA256"] = hashlib.sha256(_canonical(result)).hexdigest()
    return result
