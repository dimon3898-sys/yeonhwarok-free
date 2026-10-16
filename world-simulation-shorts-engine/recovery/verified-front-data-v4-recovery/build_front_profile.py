#!/usr/bin/env python3
"""Rebuild reviewed partial source fronts from hash-bound original map pixels.

The admission record is an explicit source/trace review by Codex, not a survey
or expert historical certificate. It cannot make an unobserved date or occupied
area factual. Coordinates always come from the measured registration and the
supported original edges, never from coordinates copied into a review record.
"""

from __future__ import annotations

import argparse
import copy
from datetime import date
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile


HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("v4_approximate_control_builder", HERE / "control_registration.py")
registration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(registration)

RECIPE_SCHEMA = "WORLD_ENGINE_VERIFIED_FRONT_BUILD_RECIPE_V1"
ADMISSION_SCHEMA = "WORLD_ENGINE_SOURCE_FRONT_ADMISSION_REVIEW_V1"
PROFILE_SCHEMA = "WORLD_ENGINE_VERIFIED_FRONT_PROFILE_V4"
RUNTIME_PROFILE = "VERIFIED_ARCHIVAL_FRONT_V4"
REGISTRATION_MODE = "REFERENCE_CONTROL_AFFINE_APPROXIMATION"
SHA = re.compile(r"[a-f0-9]{64}\Z")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
SEMANTIC_POLICY = {"inferOccupiedAreas": False, "interpolateUnobservedDates": False,
                   "exactMilitaryDemarcationLineClaimed": False}


class BuildError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(f"{code}: {detail}")


def fail(code, detail):
    raise BuildError(code, detail)


def serialized(value):
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    except (TypeError, ValueError):
        fail("FINITE_JSON_REQUIRED", "Recipe and generated results must be finite JSON")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        fail("TEXT_REQUIRED", f"{field} requires nonempty bounded text")
    return value


def hash_value(value, field):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        fail("SHA256_REQUIRED", f"{field} requires a lowercase SHA-256")
    return value


def day(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail("CALENDAR_DATE_REQUIRED", f"{field} requires YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError:
        fail("CALENDAR_DATE_REQUIRED", f"{field} must be a real calendar date")
    return value


def integer(value, field, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        fail("INTEGER_REQUIRED", f"{field} requires an integer >= {minimum}")
    return value


def canonical_path(value):
    if (not isinstance(value, str) or not value or "\\" in value or "\x00" in value
            or PurePosixPath(value).is_absolute() or str(PurePosixPath(value)) != value
            or any(part in ("", ".", "..") for part in value.split("/"))):
        fail("CANONICAL_RELATIVE_PATH_REQUIRED", "Inputs must be canonical package-relative paths")
    return value


def source_path(root, name):
    canonical_path(name)
    cursor = Path(root)
    if cursor.is_symlink():
        fail("SOURCE_SYMLINK_FORBIDDEN", "Package root cannot be a symlink")
    for part in name.split("/"):
        cursor /= part
        if cursor.is_symlink():
            fail("SOURCE_SYMLINK_FORBIDDEN", "Input source path cannot contain a symlink")
    return cursor


def read_source(root, name):
    path = source_path(root, name)
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= 64 * 1024**2:
            fail("BOUNDED_SOURCE_REQUIRED", "Source must be a nonempty regular file <=64 MiB")
        return path.read_bytes()
    except OSError:
        fail("SOURCE_UNAVAILABLE", "Required source bytes are unavailable")


def parsed(raw, field):
    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError):
        fail("VALID_JSON_REQUIRED", f"{field} is not valid JSON")
    serialized(value)
    if not isinstance(value, dict):
        fail("JSON_OBJECT_REQUIRED", f"{field} must be a JSON object")
    return value


def read_bound(root, row, field):
    if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
        fail("BOUND_INPUT_REQUIRED", f"{field} requires only path and sha256")
    raw = read_source(root, row["path"])
    if digest(raw) != hash_value(row["sha256"], field):
        fail("SOURCE_SHA_MISMATCH", f"{field} bytes differ from the bound recipe")
    return raw


def parent_plan(value):
    total = integer(value.get("totalFrames"), "basePlan.totalFrames", 1)
    fps = integer(value.get("fps"), "basePlan.fps", 1)
    duration = value.get("durationSeconds")
    if (isinstance(duration, bool) or not isinstance(duration, (int, float))
            or not math.isfinite(duration) or duration <= 0 or duration * fps != total):
        fail("BASE_PLAN_FRAME_COUNT_MISMATCH", "Duration, fps and totalFrames must agree exactly")
    production = value.get("productionV3")
    chapters = production.get("eventChapters") if isinstance(production, dict) else None
    if not isinstance(chapters, list) or not chapters or len(chapters) > 10000:
        fail("BASE_PLAN_CHAPTERS_REQUIRED", "The existing production chapters are required")
    expected, ids = 0, set()
    for chapter in chapters:
        if not isinstance(chapter, dict):
            fail("BASE_PLAN_CHAPTERS_REQUIRED", "Chapter entries must be objects")
        chapter_id = text(chapter.get("chapterId"), "chapterId")
        start, end = integer(chapter.get("startFrame"), "chapter.startFrame"), integer(chapter.get("endFrame"), "chapter.endFrame", 1)
        if chapter_id in ids or start != expected or end <= start or end > total:
            fail("BASE_PLAN_CHAPTER_BOUNDARY_MISMATCH", "Existing chapters must cover all frames exactly once")
        expected = end
        ids.add(chapter_id)
    if expected != total:
        fail("BASE_PLAN_CHAPTER_BOUNDARY_MISMATCH", "Existing chapters must cover the complete duration")
    return total, fps, duration, chapters


def validate_review(row, spec, trace, bindings):
    if (row.get("schema") != ADMISSION_SCHEMA or row.get("frontId") != bindings["frontId"]
            or row.get("mapId") != bindings["mapId"]):
        fail("SOURCE_REVIEW_ID_MISMATCH", "Source review must bind the exact map and front")
    for key, expected in {
        "classification": "OBSERVED_UN_FRONT", "registrationMode": REGISTRATION_MODE,
        "sourceCRSStatus": "UNKNOWN_FROM_MAP", "reviewStatus": "SOURCE_LINE_AND_TRACE_REVIEWED",
        "admission": "ADMITTED_APPROXIMATE_SOURCE_PARTIAL",
        "reviewerRole": "CODEX_SOURCE_REVIEW_NOT_HISTORIAN_CERTIFICATION",
        "cartographicAccuracy": "UNKNOWN_NOT_CERTIFIED", "arrowOrPhaseLine": False,
    }.items():
        if key not in row or (row[key] is not expected if isinstance(expected, bool) else row[key] != expected):
            fail("EXPLICIT_APPROXIMATE_SOURCE_REVIEW_REQUIRED", f"Source review must explicitly preserve {key}")
    map_date = day(row.get("mapDate"), "sourceAdmission.mapDate")
    raster_sha = hash_value(row.get("rasterSha256"), "sourceAdmission.rasterSha256")
    trace_sha = hash_value(row.get("pixelTraceSha256"), "sourceAdmission.pixelTraceSha256")
    document_sha = hash_value(row.get("documentSha256"), "sourceAdmission.documentSha256")
    page = integer(row.get("pageIndex0"), "sourceAdmission.pageIndex0")
    text(row.get("reference"), "sourceAdmission.reference")
    source = spec.get("source")
    if not isinstance(source, dict):
        fail("REGISTRATION_DOCUMENT_BINDING_REQUIRED", "Registration spec must preserve its source document metadata")
    if (source.get("pdfSHA256") != document_sha or source.get("pdfPageIndex0") != page
            or source.get("frontDate") != map_date):
        fail("SOURCE_DOCUMENT_DATE_PAGE_MISMATCH", "Review and measured map source must agree on document, page and map date")
    if (raster_sha != bindings["mapRaster"]["sha256"] or raster_sha != spec.get("originalSHA256")
            or raster_sha != trace.get("originalSHA256")
            or trace_sha != bindings["pixelTrace"]["sha256"]):
        fail("SOURCE_REVIEW_BYTES_MISMATCH", "Review must bind the unchanged original raster and source pixel trace")
    if (spec.get("mapId") != bindings["mapId"] or trace.get("mapId") != bindings["mapId"]
            or trace.get("frontDate") != map_date or trace.get("pixelConvention") != "PIXEL_CENTER"
            or trace.get("raster") != spec.get("raster")):
        fail("SOURCE_TRACE_BINDING_MISMATCH", "Original trace map, date, pixels and dimensions must match the registration")
    if (not isinstance(trace.get("sourcePage"), dict)
            or trace["sourcePage"].get("pdfPageIndex0") != page):
        fail("SOURCE_TRACE_PAGE_MISMATCH", "Pixel trace must bind the exact original PDF page")
    return map_date


def original_parts(trace):
    keys = [key for key in ("sourceParts", "sourcePixelParts", "sourcePixels") if key in trace]
    if len(keys) != 1:
        fail("UNAMBIGUOUS_ORIGINAL_TRACE_REQUIRED", "Specify exactly one original source-part representation")
    parts = [trace["sourcePixels"]] if keys[0] == "sourcePixels" else trace[keys[0]]
    if not isinstance(parts, list):
        fail("ORIGINAL_SOURCE_PARTS_REQUIRED", "Original source parts must be explicit arrays")
    for part in parts:
        if not isinstance(part, list) or len(part) < 2:
            fail("ORIGINAL_SOURCE_PARTS_REQUIRED", "Every source part requires at least two original vertices")
        if part[0] == part[-1]:
            fail("CLOSED_SOURCE_FRONT_FORBIDDEN", "Open fronts cannot become an occupied-area perimeter")
        if any(a == b for a, b in zip(part, part[1:])):
            fail("DUPLICATE_SOURCE_VERTEX", "Repeated adjacent source pixels are not a meaningful front edge")
    return parts


def validate_schedule(schedule, fronts, total, chapters):
    if not isinstance(schedule, list) or not 1 <= len(schedule) <= 10000:
        fail("EXPLICIT_FRONT_SCHEDULE_REQUIRED", "At least one explicit reviewed-source interval is required")
    by_id = {f["frontId"]: f for f in fronts}
    previous_end = 0
    result = copy.deepcopy(schedule)
    for row in result:
        if not isinstance(row, dict):
            fail("EXPLICIT_FRONT_SCHEDULE_REQUIRED", "Source schedule entries must be objects")
        start = integer(row.get("startFrame"), "schedule.startFrame")
        end = integer(row.get("endFrame"), "schedule.endFrame", 1)
        front = by_id.get(row.get("frontId"))
        if (start < previous_end or end <= start or end > total or front is None
                or row.get("mode") != "ARCHIVAL_FRONT_ONLY"):
            fail("SOURCE_SCHEDULE_BOUNDARY_MISMATCH", "Source intervals must be ordered, nonoverlapping, and within the parent plan")
        chapter_id = text(row.get("chapterId"), "schedule.chapterId")
        if not any(ch["chapterId"] == chapter_id and start >= ch["startFrame"] and end <= ch["endFrame"] for ch in chapters):
            fail("SOURCE_SCHEDULE_CHAPTER_MISMATCH", "Each source interval must belong to one unchanged event chapter")
        event_date = day(row.get("eventDate"), "schedule.eventDate")
        if front["mapDate"] > event_date:
            fail("FUTURE_SOURCE_MAP_FORBIDDEN", "A later source map cannot describe an earlier event")
        label = text(row.get("sourceLabel"), "schedule.sourceLabel")
        if " " not in label.strip():
            fail("MEASURED_DATE_GLYPH_LABEL_REQUIRED", "Visible date qualifier must retain the existing two-part glyph layout")
        previous_end = end
    return result


def build_outputs(root, recipe_name="RECIPE.json"):
    """Return deterministic output bytes, without modifying sources or outputs."""
    root = Path(root)
    recipe_raw = read_source(root, recipe_name)
    recipe = parsed(recipe_raw, "RECIPE")
    if recipe.get("schema") != RECIPE_SCHEMA:
        fail("BUILD_RECIPE_SCHEMA_REQUIRED", "A versioned reproducible front recipe is required")
    policy = recipe.get("semanticPolicy")
    if (not isinstance(policy, dict) or set(policy) != set(SEMANTIC_POLICY)
            or any(value is not False for value in policy.values())):
        fail("NO_INFERRED_HISTORY_POLICY_REQUIRED", "All three historical inference policies must be explicitly false")
    plan_raw = read_bound(root, recipe.get("basePlan"), "basePlan")
    total, fps, duration, chapters = parent_plan(parsed(plan_raw, "basePlan"))
    rows = recipe.get("fronts")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
        fail("BOUND_FRONTS_REQUIRED", "A bounded list of reviewed source front recipes is required")
    outputs, fronts, measurements, all_inputs, seen = {}, [], [], [], set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("frontId"), str) or not ID.fullmatch(row["frontId"]):
            fail("CANONICAL_FRONT_ID_REQUIRED", "Front IDs must be safe stable alphanumeric identifiers")
        front_id = row["frontId"]
        map_id = text(row.get("mapId"), "front.mapId")
        if front_id in seen:
            fail("DUPLICATE_FRONT_ID", "Every reviewed source front needs a unique ID")
        seen.add(front_id)
        raw = {field: read_bound(root, row.get(field), f"front.{field}")
               for field in ("mapRaster", "reference", "registrationSpec", "pixelTrace", "sourceAdmission")}
        for field in raw:
            all_inputs.append({"frontId": front_id, "role": field, **row[field]})
        spec = parsed(raw["registrationSpec"], "registrationSpec")
        trace = parsed(raw["pixelTrace"], "pixelTrace")
        admission = parsed(raw["sourceAdmission"], "sourceAdmission")
        map_date = validate_review(admission, spec, trace, row)
        reference = spec.get("referenceDataset")
        if not isinstance(reference, dict) or reference.get("SHA256") != row["reference"]["sha256"]:
            fail("REGISTRATION_REFERENCE_BINDING_MISMATCH", "Measured registration must bind the recipe's original reference dataset")
        if spec.get("mode") != "SOURCE_MAP":
            fail("SYNTHETIC_FRONT_ADMISSION_FORBIDDEN", "Synthetic control tests cannot be packaged as a historical source")
        map_path, ref_path = source_path(root, row["mapRaster"]["path"]), source_path(root, row["reference"]["path"])
        report = registration.fit_reference_controls(map_path, ref_path, spec)
        transformed = registration.transform_traced_parts(map_path, ref_path, report, original_parts(trace))
        coords = [line["coordinates"] for line in transformed["lines"]]
        if not coords:
            fail("NO_SUPPORTED_SOURCE_EDGES", "No original source edge survives the fitted control footprint")
        geometry = {"type": "LineString", "coordinates": coords[0]} if len(coords) == 1 else {"type": "MultiLineString", "coordinates": coords}
        # Recheck target geographic bounds after fitting, before browser loading.
        for part in coords:
            if part[0] == part[-1]:
                fail("CLOSED_TRANSFORMED_FRONT_FORBIDDEN", "Measured source cannot become a closed occupied-area boundary")
            for i, point in enumerate(part):
                if (len(point) != 2 or not all(math.isfinite(v) for v in point)
                        or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90
                        or (i and abs(point[0] - part[i - 1][0]) > 180)):
                    fail("INVALID_TARGET_FRONT", "Source registration produced unsupported geographic coordinates")
        stem = "generated/" + front_id
        registration_name, trace_name, geometry_name = stem + ".registration.json", stem + ".supported-trace.json", stem + ".geojson"
        outputs[registration_name] = serialized(report)
        outputs[trace_name] = serialized(transformed)
        source = {"classification": "OBSERVED_UN_FRONT", "documentSha256": admission["documentSha256"],
                  "rasterSha256": admission["rasterSha256"], "pageIndex0": admission["pageIndex0"],
                  "registrationMode": REGISTRATION_MODE,
                  "registrationResidualMeters": report["residuals"]["independentCheck"]["maximum"],
                  "cartographicAccuracy": "UNKNOWN_NOT_CERTIFIED", "reviewStatus": "SOURCE_LINE_AND_TRACE_REVIEWED",
                  "reference": admission["reference"], "reviewerRole": admission["reviewerRole"],
                  "admissionReviewSha256": row["sourceAdmission"]["sha256"],
                  "registrationReportSha256": digest(outputs[registration_name]),
                  "pixelTraceSha256": row["pixelTrace"]["sha256"],
                  "sourceAccuracyMeters": None, "totalPositionalAccuracyMeters": None,
                  "historicalSurveyCertification": False}
        geojson = {"type": "FeatureCollection", "features": [{"type": "Feature", "id": front_id,
            "properties": {"frontId": front_id, "mapId": map_id, "mapDate": map_date,
                "partialSegments": True, "verifiedSourceExtent": "PARTIAL_CONTROL_HULL", "source": source},
            "geometry": geometry}]}
        outputs[geometry_name] = serialized(geojson)
        fronts.append({"frontId": front_id, "mapId": map_id, "mapDate": map_date, "geometry": geometry,
            "sourceFile": geometry_name, "geoJsonSha256": digest(outputs[geometry_name]),
            "partialSegments": True, "verifiedSourceExtent": "PARTIAL_CONTROL_HULL", "source": source})
        measurements.append({"frontId": front_id, "mapId": map_id, "mapDate": map_date,
            "originalEdgeCount": transformed["inputEdgeCount"], "retainedEdgeCount": transformed["retainedEdgeCount"],
            "excludedEdgeCount": transformed["excludedEdgeCount"], "inventedVertexCount": 0,
            "registrationResidualMeters": copy.deepcopy(report["residuals"]),
            "coverage": copy.deepcopy(report["coverage"]),
            "independentCheckSpatialCoverage": copy.deepcopy(transformed["independentCheckSpatialCoverage"]),
            "warnings": report["warnings"] + transformed["warnings"], "sourceAccuracyMeters": None,
            "totalPositionalAccuracyMeters": None, "technicalRegistrationAutomaticallyAdmitted": False,
            "admission": "ADMITTED_APPROXIMATE_SOURCE_PARTIAL", "admissionReviewSha256": row["sourceAdmission"]["sha256"]})
    schedule = validate_schedule(recipe.get("schedule"), fronts, total, chapters)
    profile = {"schema": PROFILE_SCHEMA, "runtimeProfile": RUNTIME_PROFILE,
        "semanticPolicy": copy.deepcopy(SEMANTIC_POLICY), "fronts": fronts, "schedule": schedule,
        "buildRecipeSha256": digest(recipe_raw), "unchangedBasePlanSha256": digest(plan_raw),
        "historicalSurveyCertification": False}
    outputs["FRONT_PROFILE.json"] = serialized(profile)
    build_report = {"schema": "WORLD_ENGINE_FRONT_BUILD_REPRODUCTION_V1", "status": "REPRODUCIBLE_SOURCE_BUILD",
        "recipe": {"path": recipe_name, "sha256": digest(recipe_raw)}, "basePlan": copy.deepcopy(recipe["basePlan"]),
        "durationSeconds": duration, "fps": fps, "totalFrames": total, "eventChapters": len(chapters),
        "basePlanModified": False, "inputs": all_inputs, "fronts": measurements,
        "outputs": {name: digest(raw) for name, raw in sorted(outputs.items())},
        "coordinateSource": "RECOMPUTED_AFFINE_FROM_BOUND_ORIGINAL_PIXELS_AND_REFERENCE_POINTS",
        "inferredOccupiedAreas": False, "interpolatedUnobservedDates": False,
        "exactMilitaryDemarcationLineClaimed": False, "historicalTruthCertified": False,
        "gpuExecuted": False, "frozenMathDependency": copy.deepcopy(registration.FROZEN_MATH_DEPENDENCY)}
    outputs["BUILD_REPRODUCTION.json"] = serialized(build_report)
    return outputs


def materialize_outputs(outputs, output_root, *, check=False):
    """Check or create identical outputs; never overwrite differing existing bytes."""
    output_root = Path(output_root)
    for name, raw in sorted(outputs.items()):
        path = source_path(output_root, name)
        if path.exists():
            if not path.is_file() or path.read_bytes() != raw:
                fail("GENERATED_OUTPUT_MISMATCH", "Existing generated output differs from the reproducible build")
            continue
        if check:
            fail("GENERATED_OUTPUT_MISSING", "A required generated output is absent")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic no-replace creation prevents a concurrent process from silently
        # replacing either an existing candidate or its own completed output.
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(prefix=".front-build-", dir=path.parent, delete=False) as stream:
                temp_name = stream.name
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temp_name, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
                fail("GENERATED_OUTPUT_MISMATCH", "Concurrent output differs from this reproducible build")
        finally:
            if temp_name is not None:
                os.unlink(temp_name)
    return {"status": "PASS", "mode": "CHECK" if check else "CREATE_OR_IDENTICAL",
            "files": len(outputs), "outputSha256": {k: digest(v) for k, v in sorted(outputs.items())},
            "gpuExecuted": False}


def _compare_numerical(expected, actual, *, coordinate_tolerance, residual_tolerance, path=()):
    """Compare only declared numerical result fields approximately, not inputs."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        if type(expected) is not type(actual) or expected != actual:
            fail("REPRODUCTION_VALUE_MISMATCH", "A boolean result or source declaration changed")
        return
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            fail("REPRODUCTION_STRUCTURE_MISMATCH", "Generated result fields changed")
        for key in expected:
            _compare_numerical(expected[key], actual[key], coordinate_tolerance=coordinate_tolerance,
                               residual_tolerance=residual_tolerance, path=path + (key,))
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            fail("REPRODUCTION_STRUCTURE_MISMATCH", "Original trace parts, vertices or edges changed")
        for index, (a, b) in enumerate(zip(expected, actual)):
            _compare_numerical(a, b, coordinate_tolerance=coordinate_tolerance,
                               residual_tolerance=residual_tolerance, path=path + (index,))
        return
    if isinstance(expected, (float, int)) and isinstance(actual, (float, int)):
        tolerance = 0
        # The source-pixel arrays, reference coordinates, input specification,
        # quality limits and all counts remain EXACT comparisons.
        if "inputSpec" not in path and "controls" not in path and "checkControls" not in path:
            if "coordinates" in path or "coefficients" in path:
                tolerance = coordinate_tolerance
            elif (path and path[-1] == "registrationResidualMeters") or (
                ("residuals" in path or "registrationResidualMeters" in path)
                    and path[-1] in ("meters", "maximum", "rms")):
                tolerance = residual_tolerance
        if (not math.isfinite(expected) or not math.isfinite(actual)
                or abs(expected - actual) > tolerance):
            fail("REPRODUCTION_NUMERICAL_MISMATCH", "A measured result exceeds its declared numerical tolerance")
        return
    if type(expected) is not type(actual) or expected != actual:
        fail("REPRODUCTION_VALUE_MISMATCH", "An exact source, edge, semantic policy or binding changed")


def _internal_hash(document, field):
    value = copy.deepcopy(document)
    expected = value.pop(field, None)
    hash_value(expected, field)
    if digest(registration._canonical(value)) != expected:
        fail("GENERATED_INTERNAL_HASH_MISMATCH", "Stored registration/trace report has an invalid internal hash")


def verify_numerical_outputs(outputs, output_root, *, coordinate_tolerance_degrees=1e-10,
                             residual_tolerance_meters=1e-3):
    """Read-only reproducibility check across GDAL/numpy versions.

    Source bytes, source pixels, edge membership, parts, schedule and review
    declarations remain exact. Only derived lon/lat/affine results and measured
    residuals use the declared tight numerical tolerances. Frozen file hashes
    are checked against their own recorded files; tool-version differences do
    not rewrite the candidate or become a false byte-exact reproduction claim.
    """
    for value, maximum in ((coordinate_tolerance_degrees, 1e-10), (residual_tolerance_meters, 1e-3)):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0 <= value <= maximum):
            fail("REPRODUCTION_TOLERANCE_INVALID", "Tolerance cannot exceed the documented numerical-only ceiling")
    stored_raw = {name: read_source(output_root, name) for name in outputs}
    stored = {name: parsed(raw, name) for name, raw in stored_raw.items()}
    regenerated = {name: parsed(raw, name) for name, raw in outputs.items()}
    frozen_report, current_report = stored["BUILD_REPRODUCTION.json"], regenerated["BUILD_REPRODUCTION.json"]
    expected_names = set(outputs) - {"BUILD_REPRODUCTION.json"}
    if set(frozen_report.get("outputs", {})) != expected_names:
        fail("FROZEN_OUTPUT_SET_MISMATCH", "Frozen build report must account for every generated artifact")
    for name, expected_sha in frozen_report["outputs"].items():
        if digest(stored_raw[name]) != hash_value(expected_sha, "stored output"):
            fail("FROZEN_OUTPUT_SHA_MISMATCH", "A frozen generated artifact differs from its own manifest")
    frozen_profile = stored["FRONT_PROFILE.json"]
    for front in frozen_profile.get("fronts", []):
        name = front.get("sourceFile")
        if name not in expected_names or digest(stored_raw[name]) != front.get("geoJsonSha256"):
            fail("FROZEN_GEOMETRY_BINDING_MISMATCH", "Frozen front must bind its exact persisted GeoJSON bytes")
        features = stored[name].get("features")
        if (not isinstance(features, list) or len(features) != 1
                or features[0].get("geometry") != front.get("geometry")
                or features[0].get("properties", {}).get("source") != front.get("source")):
            fail("FROZEN_GEOMETRY_BINDING_MISMATCH", "Frozen profile and original generated GeoJSON disagree")
    versions = {}
    for name in outputs:
        expected, actual = copy.deepcopy(stored[name]), copy.deepcopy(regenerated[name])
        if name.endswith(".registration.json"):
            _internal_hash(expected, "reportSHA256")
            _internal_hash(actual, "reportSHA256")
            versions[name] = {"frozen": expected.pop("software"), "recomputed": actual.pop("software")}
            expected.pop("reportSHA256")
            actual.pop("reportSHA256")
        elif name.endswith(".supported-trace.json"):
            _internal_hash(expected, "traceSHA256")
            _internal_hash(actual, "traceSHA256")
            registration_name = name.removesuffix(".supported-trace.json") + ".registration.json"
            if (expected["registrationReportSHA256"] != stored[registration_name]["reportSHA256"]
                    or actual["registrationReportSHA256"] != regenerated[registration_name]["reportSHA256"]):
                fail("FROZEN_REGISTRATION_BINDING_MISMATCH", "Source trace must bind its corresponding registration result")
            for value in (expected, actual):
                value.pop("traceSHA256")
                value.pop("registrationReportSHA256")
        elif name.endswith(".geojson"):
            registration_name = name.removesuffix(".geojson") + ".registration.json"
            for value, raw_outputs in ((expected, stored_raw), (actual, outputs)):
                source = value["features"][0]["properties"]["source"]
                if source["registrationReportSha256"] != digest(raw_outputs[registration_name]):
                    fail("FROZEN_REGISTRATION_BINDING_MISMATCH", "GeoJSON must bind its exact registration report bytes")
                source.pop("registrationReportSha256")
        elif name == "FRONT_PROFILE.json":
            for value, raw_outputs in ((expected, stored_raw), (actual, outputs)):
                for front in value["fronts"]:
                    if front["geoJsonSha256"] != digest(raw_outputs[front["sourceFile"]]):
                        fail("FROZEN_GEOMETRY_BINDING_MISMATCH", "Profile must bind its exact GeoJSON bytes")
                    registration_name = front["sourceFile"].removesuffix(".geojson") + ".registration.json"
                    if front["source"]["registrationReportSha256"] != digest(raw_outputs[registration_name]):
                        fail("FROZEN_REGISTRATION_BINDING_MISMATCH", "Profile must bind its exact registration report bytes")
                    front.pop("geoJsonSha256")
                    front["source"].pop("registrationReportSha256")
        elif name == "BUILD_REPRODUCTION.json":
            expected.pop("outputs")
            actual.pop("outputs")
        _compare_numerical(expected, actual, coordinate_tolerance=coordinate_tolerance_degrees,
                           residual_tolerance=residual_tolerance_meters)
    return {"schema": "WORLD_ENGINE_FRONT_NUMERICAL_REPRODUCTION_V1", "status": "PASS",
        "mode": "READ_ONLY_NUMERICAL_REPRODUCTION", "files": len(outputs),
        "sourcePixelsAndEdgesExact": True, "frozenGeneratedHashesVerified": True,
        "coordinateToleranceDegrees": coordinate_tolerance_degrees,
        "registrationResidualToleranceMeters": residual_tolerance_meters,
        "byteExactOutputs": all(stored_raw[name] == outputs[name] for name in outputs),
        "toolVersions": versions, "gpuExecuted": False, "historicalAccuracyCertified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE)
    parser.add_argument("--recipe", default="RECIPE.json")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify-numerical", action="store_true")
    args = parser.parse_args()
    try:
        outputs = build_outputs(args.root, args.recipe)
        if args.verify_numerical:
            result = verify_numerical_outputs(outputs, args.output_root or args.root)
        else:
            result = materialize_outputs(outputs, args.output_root or args.root, check=args.check)
    except (BuildError, registration.RegistrationError) as error:
        print(json.dumps({"status": "FAIL", "errorCode": error.code, "gpuExecuted": False}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
