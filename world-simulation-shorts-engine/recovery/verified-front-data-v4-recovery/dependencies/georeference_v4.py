"""Hash-bound, CPU-only affine map georeferencing evidence.

This module does not identify historical fronts, interpolate missing front
segments, infer a map's projection, or admit a candidate into a renderer.  A
small residual is a registration measurement, never proof of historical truth.
Input pixels are original, zero-based pixel centers.  The six affine
coefficients use GDAL pixel-corner coordinates, hence the explicit +0.5.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from osgeo import gdal, osr


SCHEMA = "WORLD_ENGINE_GEOREFERENCE_CANDIDATE_V1"


class GeoreferenceError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code, detail):
    raise GeoreferenceError(code, detail)


def _finite(value, field, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("INVALID_DATA", f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0) or (
        nonnegative and number < 0
    ):
        _fail("INVALID_DATA", f"{field} must be finite and in range")
    return number


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        _fail("INVALID_DATA", f"{field} requires a bounded, nonempty string")
    return value


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        _fail("INVALID_DATA", f"Candidate is not finite JSON: {type(exc).__name__}")


def _srs(definition):
    reference = osr.SpatialReference()
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    try:
        code = reference.SetFromUserInput(definition)
    except Exception:
        code = 1
    finally:
        gdal.PopErrorHandler()
    if code or not (reference.IsProjected() or reference.IsGeographic()):
        _fail("UNKNOWN_SOURCE_CRS", "A known horizontal source CRS is required")
    reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return reference


def _lonlat_transform(reference):
    return osr.CoordinateTransformation(reference, _srs("EPSG:4326"))


def _lonlat(transformation, coordinate):
    try:
        result = transformation.TransformPoint(*coordinate)
    except Exception:
        _fail("COORDINATE_TRANSFORM_FAILED", "Source coordinate is outside the CRS domain")
    longitude, latitude = result[:2]
    if not (math.isfinite(longitude) and math.isfinite(latitude)
            and -180 <= longitude <= 180 and -90 <= latitude <= 90):
        _fail("COORDINATE_TRANSFORM_FAILED", "Invalid WGS84 longitude/latitude")
    return [longitude, latitude]


def _distance_meters(actual, expected):
    # WGS84 azimuthal equidistant, centered on the expected point.  Its radial
    # distance is geodesic distance; residual units never depend on source units.
    local = osr.SpatialReference()
    local.SetWellKnownGeogCS("WGS84")
    local.SetAE(expected[1], expected[0], 0, 0)
    local.SetLinearUnits("metre", 1)
    local.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(_srs("EPSG:4326"), local)
    try:
        x, y, _ = transform.TransformPoint(*actual)
    except Exception:
        _fail("COORDINATE_TRANSFORM_FAILED", "Cannot measure geodesic residual")
    distance = math.hypot(x, y)
    if not math.isfinite(distance):
        _fail("COORDINATE_TRANSFORM_FAILED", "Nonfinite registration residual")
    return distance


def _hull(points):
    ordered = sorted(set(tuple(p) for p in points))
    if len(ordered) < 3:
        _fail("COLLINEAR_CONTROLS", "Control coverage must have nonzero area")

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    result = lower[:-1] + upper[:-1]
    if len(result) < 3 or _area(result) <= 1e-9:
        _fail("COLLINEAR_CONTROLS", "Control coverage must have nonzero area")
    return result


def _area(hull):
    return abs(sum(p[0] * q[1] - q[0] * p[1]
                   for p, q in zip(hull, hull[1:] + hull[:1]))) / 2


def _inside(point, hull):
    # Hull is counterclockwise; tolerance is numerical, not geographic expansion.
    tolerance = 1e-9
    return all((q[0] - p[0]) * (point[1] - p[1])
               - (q[1] - p[1]) * (point[0] - p[0]) >= -tolerance
               for p, q in zip(hull, hull[1:] + hull[:1]))


def _controls(items, field, minimum, width, height):
    if not isinstance(items, list) or not minimum <= len(items) <= 128:
        _fail("INSUFFICIENT_CONTROLS", f"{field} requires {minimum}..128 points")
    result = []
    for item in items:
        if not isinstance(item, dict):
            _fail("INVALID_DATA", f"{field} points require objects")
        point = {"id": _text(item.get("id"), "control id"),
                 "sourceReference": _text(item.get("sourceReference"), "control sourceReference")}
        for key in ("pixel", "coordinate"):
            raw = item.get(key)
            if not isinstance(raw, (list, tuple)) or len(raw) != 2:
                _fail("INVALID_DATA", f"{field}.{key} requires two numbers")
            point[key] = [_finite(v, f"{field}.{key}") for v in raw]
        x, y = point["pixel"]
        if not 0 <= x <= width - 1 or not 0 <= y <= height - 1:
            _fail("PIXEL_OUTSIDE_ORIGINAL", "Control pixel lies outside original raster centers")
        result.append(point)
    if len({p["id"] for p in result}) != len(result) or len(
        {tuple(p["pixel"]) for p in result}
    ) != len(result):
        _fail("DUPLICATE_CONTROLS", "Control IDs and pixel locations must be unique")
    return result


def _affine(coefficients, pixel):
    x, y = pixel[0] + 0.5, pixel[1] + 0.5
    a, b, c, d, e, f = coefficients
    return [a + b * x + c * y, d + e * x + f * y]


def fit_reference(map_path, spec):
    """Fit known-source-CRS pixels, retaining independent check evidence.

    ``spec`` must declare source scale, original hash/dimensions, source CRS and
    its map citation, finite uncertainty and acceptance budgets, >=4 fit points
    and >=3 held-out points.  SOURCE_MAP mode is still only a review candidate.
    """
    if not isinstance(spec, dict):
        _fail("INVALID_DATA", "Georeference specification must be an object")
    spec = copy.deepcopy(spec)
    _canonical(spec)
    map_id = _text(spec.get("mapId"), "mapId")
    mode = spec.get("mode")
    if mode not in ("SYNTHETIC", "SOURCE_MAP"):
        _fail("INVALID_DATA", "mode must distinguish SYNTHETIC from SOURCE_MAP")
    original_sha = spec.get("originalSHA256")
    if not isinstance(original_sha, str) or len(original_sha) != 64 or any(
        char not in "0123456789abcdef" for char in original_sha
    ):
        _fail("ORIGINAL_HASH_REQUIRED", "A lowercase SHA-256 of original map bytes is required")
    try:
        actual_sha = _sha(map_path)
    except OSError:
        _fail("ORIGINAL_UNAVAILABLE", "Original map bytes are unavailable")
    if actual_sha != original_sha:
        _fail("ORIGINAL_HASH_MISMATCH", "Original map bytes do not match the evidence")
    raster = spec.get("raster")
    if not isinstance(raster, dict):
        _fail("INVALID_DATA", "Original raster dimensions are required")
    width, height = raster.get("width"), raster.get("height")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 2 for v in (width, height)):
        _fail("INVALID_DATA", "Raster dimensions must be integers >=2")
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    try:
        dataset = gdal.Open(str(map_path), gdal.GA_ReadOnly)
    except Exception:
        dataset = None
    finally:
        gdal.PopErrorHandler()
    if dataset is None:
        _fail("INVALID_ORIGINAL_RASTER", "Original file is not a GDAL-readable raster")
    actual_dimensions = [dataset.RasterXSize, dataset.RasterYSize]
    dataset = None
    if actual_dimensions != [width, height]:
        _fail("ORIGINAL_DIMENSION_MISMATCH", "Pixels must refer to unchanged original dimensions")
    source_crs = spec.get("sourceCRS")
    if not isinstance(source_crs, dict) or source_crs.get("status") != "KNOWN_FROM_MAP":
        _fail("UNKNOWN_SOURCE_CRS", "Map projection/CRS must be known from original evidence")
    definition = _text(source_crs.get("definition"), "sourceCRS.definition")
    _text(source_crs.get("sourceReference"), "sourceCRS.sourceReference")
    reference = _srs(definition)
    to_lonlat = _lonlat_transform(reference)
    if spec.get("pixelConvention") != "PIXEL_CENTER":
        _fail("PIXEL_CONVENTION_REQUIRED", "Declare original zero-based PIXEL_CENTER convention")
    scale = spec.get("sourceScale")
    if not isinstance(scale, dict):
        _fail("SOURCE_SCALE_REQUIRED", "Original map scale and citation are required")
    _finite(scale.get("denominator"), "sourceScale.denominator", positive=True)
    _text(scale.get("sourceReference"), "sourceScale.sourceReference")
    uncertainty = _finite(spec.get("sourceUncertaintyMeters"), "sourceUncertaintyMeters", nonnegative=True)
    if mode == "SOURCE_MAP":
        _text(spec.get("sourceUncertaintyReference"), "sourceUncertaintyReference")
        if uncertainty <= 0:
            _fail("SOURCE_UNCERTAINTY_REQUIRED", "A source map cannot claim zero positional uncertainty")
    limits = spec.get("qualityLimits")
    if not isinstance(limits, dict):
        _fail("UNCERTAINTY_BUDGET_REQUIRED", "Explicit registration and combined error budgets are required")
    limits = {key: _finite(limits.get(key), key, positive=True) for key in (
        "maxFitResidualMeters", "maxCheckResidualMeters", "maxCombinedUncertaintyMeters"
    )}
    if uncertainty > limits["maxCombinedUncertaintyMeters"]:
        _fail("SOURCE_UNCERTAINTY_EXCEEDS_BUDGET", "Source uncertainty alone exceeds the declared budget")
    _text(spec.get("independentCheckDeclaration"), "independentCheckDeclaration")
    controls = _controls(spec.get("controls"), "controls", 4, width, height)
    checks = _controls(spec.get("checkControls"), "checkControls", 3, width, height)
    if reference.IsGeographic():
        longitudes = [p["coordinate"][0] for p in controls + checks]
        if max(longitudes) - min(longitudes) >= 180:
            _fail("ANTIMERIDIAN_REQUIRES_PROJECTED_CRS",
                  "Do not fit a longitude discontinuity; supply the original known projected CRS")
    if ({p["id"] for p in controls} & {p["id"] for p in checks}
            or {tuple(p["pixel"]) for p in controls} & {tuple(p["pixel"]) for p in checks}
            or {tuple(p["coordinate"]) for p in controls} & {tuple(p["coordinate"]) for p in checks}):
        _fail("CHECKS_NOT_INDEPENDENT", "Held-out points must not reuse fitted IDs, pixels, or coordinates")
    fit_hull = _hull([p["pixel"] for p in controls])
    check_hull = _hull([p["pixel"] for p in checks])
    if not all(_inside(p["pixel"], fit_hull) for p in checks):
        _fail("CHECK_OUTSIDE_FIT_COVERAGE", "Held-out validation must be within the fitted footprint")
    # A line or tiny cluster cannot independently validate a 2-D map footprint.
    check_to_fit = _area(check_hull) / _area(fit_hull)
    if check_to_fit < 0.1:
        _fail("INSUFFICIENT_CHECK_COVERAGE", "Held-out hull must cover >=10% of the fitted hull")
    pixels = np.array([p["pixel"] for p in controls], dtype=np.float64) + 0.5
    center, spread = pixels.mean(axis=0), pixels.std(axis=0)
    if np.any(spread <= 1e-12):
        _fail("COLLINEAR_CONTROLS", "Control points do not span both pixel axes")
    design = np.column_stack((np.ones(len(pixels)), (pixels - center) / spread))
    if np.linalg.matrix_rank(design) != 3 or np.linalg.cond(design) > 1e8:
        _fail("COLLINEAR_CONTROLS", "Affine registration is rank deficient or ill conditioned")
    values = np.array([p["coordinate"] for p in controls], dtype=np.float64)
    coefficients, _, _, _ = np.linalg.lstsq(design, values, rcond=None)
    slopes = coefficients[1:] / spread[:, None]
    offset = coefficients[0] - center @ slopes
    affine = [float(offset[0]), float(slopes[0, 0]), float(slopes[1, 0]),
              float(offset[1]), float(slopes[0, 1]), float(slopes[1, 1])]
    if abs(affine[1] * affine[5] - affine[2] * affine[4]) <= 1e-20:
        _fail("DEGENERATE_TRANSFORM", "Affine source-coordinate transform has zero area")

    def residuals(points):
        measured = []
        for point in points:
            actual = _lonlat(to_lonlat, _affine(affine, point["pixel"]))
            expected = _lonlat(to_lonlat, point["coordinate"])
            measured.append({"id": point["id"], "meters": _distance_meters(actual, expected)})
        distances = [p["meters"] for p in measured]
        return {"unit": "meters", "method": "WGS84_AZIMUTHAL_EQUIDISTANT_RADIAL_DISTANCE",
                "points": measured, "maximum": max(distances),
                "rms": math.sqrt(sum(d * d for d in distances) / len(distances))}

    fitted_residuals, check_residuals = residuals(controls), residuals(checks)
    if fitted_residuals["maximum"] > limits["maxFitResidualMeters"]:
        _fail("FIT_RESIDUAL_EXCEEDS_BUDGET", "Fitted control residual exceeds declared tolerance")
    if check_residuals["maximum"] > limits["maxCheckResidualMeters"]:
        _fail("CHECK_RESIDUAL_EXCEEDS_BUDGET", "Independent held-out residual exceeds declared tolerance")
    combined = uncertainty + max(fitted_residuals["maximum"], check_residuals["maximum"])
    if combined > limits["maxCombinedUncertaintyMeters"]:
        _fail("COMBINED_UNCERTAINTY_EXCEEDS_BUDGET", "Conservative additive uncertainty exceeds declared budget")
    report = {"schema": SCHEMA, "mapId": map_id, "mode": mode,
              "status": "TECHNICAL_CANDIDATE_REVIEW_REQUIRED", "runtimeAdmission": "NOT_ADMITTED",
              "historicalAccuracyVerified": False, "originalSHA256": original_sha,
              "raster": {"width": width, "height": height}, "sourceCRS": source_crs,
              "sourceCRSNormalizedWKT": reference.ExportToWkt(), "targetCRS": "EPSG:4326",
              "axisOrder": "SOURCE_X_Y_TO_LONGITUDE_LATITUDE",
              "transform": {"coefficients": affine, "method": "AFFINE_PIXEL_TO_CRS",
                            "pixelConvention": "PIXEL_CENTER", "gdalCornerOffset": [0.5, 0.5]},
              "controls": controls, "checkControls": checks,
              "residuals": {"fit": fitted_residuals, "independentCheck": check_residuals},
              "coverage": {"fitPixelHull": fit_hull, "checkPixelHull": check_hull,
                           "fitHullFractionOfOriginalRaster": _area(fit_hull) / ((width - 1) * (height - 1)),
                           "checkToFitHullRatio": check_to_fit,
                           "digitizationRule": "INSIDE_BOTH_HULLS_NO_EXTRAPOLATION"},
              "uncertainty": {"sourceMeters": uncertainty, "conservativeCombinedMeters": combined,
                              "sourceReference": spec.get("sourceUncertaintyReference", "SYNTHETIC declared fixture uncertainty"),
                              "combination": "SOURCE_PLUS_MAX_REGISTRATION_RESIDUAL",
                              "historicalAccuracyClaim": False},
              "software": {"gdal": gdal.VersionInfo("RELEASE_NAME"), "numpy": np.__version__},
              "inputSpec": spec}
    report["reportSHA256"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def transform_verified_vertices(map_path, report, vertices):
    """Return WGS84 lon/lat for confirmed source pixels, with no extrapolation.

    Verifies original bytes and the complete recomputed report.  This detects
    accidental/tampered evidence; it is not a signature or historical approval.
    Report generation and consumption use the recorded GDAL/numpy versions.
    """
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        _fail("INVALID_REPORT", "Expected a hash-bound georeference candidate report")
    recomputed = fit_reference(map_path, report.get("inputSpec"))
    if _canonical(recomputed) != _canonical(report):
        _fail("REPORT_MISMATCH", "Candidate report does not match original bytes and recomputed evidence")
    if not isinstance(vertices, list) or not 1 <= len(vertices) <= 100000:
        _fail("INVALID_VERTICES", "Source vertices require a bounded nonempty list")
    transformation = _lonlat_transform(_srs(report["sourceCRS"]["definition"]))
    result = []
    for vertex in vertices:
        if not isinstance(vertex, (list, tuple)) or len(vertex) != 2:
            _fail("INVALID_VERTICES", "Each original pixel requires [column,row]")
        point = [_finite(v, "source pixel") for v in vertex]
        if not all(_inside(point, report["coverage"][key])
                   for key in ("fitPixelHull", "checkPixelHull")):
            _fail("EXTRAPOLATION_FORBIDDEN", "Pixel lies outside fitted and independently checked coverage")
        result.append(_lonlat(transformation, _affine(report["transform"]["coefficients"], point)))
    return result
