"""Pure evidence coverage for supplied data; never creates history or starts work.

Narrative chapters, source geometry clocks and archival snapshot slots are
different clocks.  This module intersects their half-open ranges and reports
what is actually supplied.  A contract check is never rendered-output evidence.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import math


class CoverageError(ValueError):
    """Stable public error code without raw source/environment values."""


def _fail(code):
    raise CoverageError(code)


def _ranges(rows, total, *, complete, identity):
    if not isinstance(rows, list) or (complete and not rows):
        _fail("COVERAGE_RANGE_LIST_REQUIRED")
    cursor = 0
    ids = set()
    for row in rows:
        if not isinstance(row, dict):
            _fail("COVERAGE_RANGE_OBJECT_REQUIRED")
        start, end = row.get("startFrame"), row.get("endFrame")
        if (type(start) is not int or type(end) is not int
                or not 0 <= start < end <= total or start < cursor
                or (complete and start != cursor)):
            _fail("COVERAGE_HALF_OPEN_PARTITION_INVALID")
        if identity:
            key = row.get(identity)
            if not isinstance(key, str) or not key or key in ids:
                _fail("COVERAGE_UNIQUE_RANGE_ID_REQUIRED")
            ids.add(key)
        cursor = end
    if complete and cursor != total:
        _fail("COVERAGE_HALF_OPEN_PARTITION_INVALID")


def _iso(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _asset_summary(metadata):
    if metadata is None:
        return {"status": "NOT_VERIFIED", "scope": "NO_ASSET_METADATA_SUPPLIED",
                "fullSceneCoverageVerified": False, "sources": {}}
    if not isinstance(metadata, dict) or not isinstance(metadata.get("sources"), dict):
        _fail("COVERAGE_ASSET_METADATA_REQUIRED")
    sources = {}
    for role, item in metadata["sources"].items():
        if not isinstance(item, dict):
            _fail("COVERAGE_ASSET_SOURCE_OBJECT_REQUIRED")
        source_bbox = item.get("coverage", {}).get("sourceBBox")
        if source_bbox is not None and (not isinstance(source_bbox, list) or len(source_bbox) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in source_bbox)
                or not -180 <= source_bbox[0] < source_bbox[2] <= 180
                or not -90 <= source_bbox[1] < source_bbox[3] <= 90):
            _fail("COVERAGE_ASSET_BBOX_INVALID")
        sources[role] = {key: deepcopy(item.get(key)) for key in
                         ("sourceId", "sourceVersion", "sourceURL", "CRS", "SHA-256",
                          "nativeResolution", "verticalDatum", "nodata")}
        sources[role].update(sourceBBox=deepcopy(source_bbox),
                             support="REGIONAL_SOURCE_EXTENT_ONLY_VALID_MASK_STILL_REQUIRED",
                             originalValuesPreservedByExistingProvider=True,
                             renderedOutputVerified=False)
    return {"status": "SUPPORTING", "scope": "REGIONAL_SAMPLES_WITH_BASE_MATERIAL_FALLBACK",
            "fullSceneCoverageVerified": False, "sources": sources,
            "signedElevationIsNotOceanMask": True,
            "coverageOwner": "EXISTING_NATIVE_GIS_LAND_SEA_COVERAGE",
            "sourceMissingPolicy": "EXISTING_MATERIAL_NO_PADDING_NO_INVENTED_HEIGHT_OR_DEPTH"}


def _segments(chapter, geometry_schedule, archival_schedule, fronts):
    start, end = chapter["startFrame"], chapter["endFrame"]
    cuts = {start, end}
    for row in geometry_schedule + archival_schedule:
        if row["startFrame"] < end and row["endFrame"] > start:
            cuts.update((max(start, row["startFrame"]), min(end, row["endFrame"])))
    result = []
    ordered = sorted(cuts)
    for left, right in zip(ordered, ordered[1:]):
        original = next(row for row in geometry_schedule
                        if row["startFrame"] <= left < row["endFrame"])
        archive = next((row for row in archival_schedule
                        if row["startFrame"] <= left < row["endFrame"]), None)
        row = {"startFrame": left, "endFrame": right, "frames": right - left,
               "originalGeometryScheduleId": original.get("scheduleId"),
               "sourceGeometryClock": {key: deepcopy(original.get(key)) for key in
                    ("mode", "sourceStartFrame", "sourceEndFrame", "sourceStateId",
                     "fromStateId", "toStateId", "snapshotDate", "snapshotLabel")}}
        if archive is not None:
            front = fronts[archive["frontId"]]
            row.update(kind="ARCHIVAL_PARTIAL_FRONT_HOLD", frontId=front["frontId"],
                       mapDate=front["mapDate"], eventDate=archive["eventDate"],
                       exactEventDateMatch=front["mapDate"] == archive["eventDate"],
                       sourceLabel=archive["sourceLabel"], areasAllowed=False,
                       coordinatesInterpolated=False, entireFrontCertified=False,
                       sourceGeoJsonSha256=front.get("geoJsonSha256"),
                       sourceFile=front.get("sourceFile"),
                       registrationResidualMeters=front.get("source", {}).get("registrationResidualMeters"),
                       totalPositionalAccuracyMeters=None)
        else:
            row.update(kind="SCHEMATIC_CONTEXT", areasAllowed=original["mode"] != "ARRIVAL_NO_EVENT",
                       measuredMilitaryControl=False,
                       observedDailyFrontInterpolation=False)
        result.append(row)
    return result


def build_coverage(plan, front_profile, *, asset_metadata=None, chronology_review=None):
    """Return coverage of supplied plans with independent data/output statuses.

    Inputs are ordinary JSON objects. This function has no file/network/GPU
    access, country-specific branches, source creation or renderer side effects.
    ``chronology_review`` may be the preserved scene-evidence connection receipt;
    without it event-date verification remains NOT_VERIFIED.
    """
    if not isinstance(plan, dict) or not isinstance(front_profile, dict):
        _fail("COVERAGE_PLAN_AND_PROFILE_REQUIRED")
    fps, total, duration = plan.get("fps"), plan.get("totalFrames"), plan.get("durationSeconds")
    if (type(fps) is not int or not 1 <= fps <= 120 or type(total) is not int
            or not 1 <= total <= 72000 or type(duration) not in (int, float)
            or not math.isfinite(duration) or abs(duration * fps - total) > 1e-7):
        _fail("COVERAGE_TIMING_INVALID")
    production = plan.get("productionV3")
    if not isinstance(production, dict):
        _fail("COVERAGE_PRODUCTION_CLOCK_REQUIRED")
    chapters, geometry = production.get("eventChapters"), production.get("geometrySchedule")
    _ranges(chapters, total, complete=True, identity="chapterId")
    _ranges(geometry, total, complete=True, identity="scheduleId")
    _ranges(plan.get("scenes"), total, complete=True, identity="sceneId")
    policy = front_profile.get("semanticPolicy", {})
    if any(policy.get(key) is not False for key in
           ("inferOccupiedAreas", "interpolateUnobservedDates", "exactMilitaryDemarcationLineClaimed")):
        _fail("COVERAGE_NO_INFERRED_HISTORY_REQUIRED")
    schedule = front_profile.get("schedule")
    _ranges(schedule, total, complete=False, identity=None)
    front_rows = front_profile.get("fronts")
    if not isinstance(front_rows, list):
        _fail("COVERAGE_FRONT_SOURCES_REQUIRED")
    fronts = {}
    for row in front_rows:
        if (not isinstance(row, dict) or not isinstance(row.get("frontId"), str)
                or row["frontId"] in fronts or _iso(row.get("mapDate")) is None
                or row.get("partialSegments") is not True
                or row.get("verifiedSourceExtent") != "PARTIAL_CONTROL_HULL"):
            _fail("COVERAGE_PARTIAL_DATED_FRONT_REQUIRED")
        fronts[row["frontId"]] = row
    for row in schedule:
        if (row.get("frontId") not in fronts or row.get("mode") != "ARCHIVAL_FRONT_ONLY"
                or _iso(row.get("eventDate")) is None
                or fronts[row["frontId"]]["mapDate"] > row["eventDate"]):
            _fail("COVERAGE_ARCHIVAL_SOURCE_BINDING_INVALID")
        if not any(ch["startFrame"] <= row["startFrame"] < row["endFrame"] <= ch["endFrame"]
                   and ch["chapterId"] == row.get("chapterId") for ch in chapters):
            _fail("COVERAGE_ARCHIVAL_CHAPTER_BINDING_INVALID")
    review_rows = (chronology_review or {}).get("rows", [])
    reviews = {row["chapterId"]: row for row in review_rows if isinstance(row, dict) and "chapterId" in row}
    assets = _asset_summary(asset_metadata)
    ownership = production.get("visualBindings", {})
    unit_positions = ownership.get("unitPositions", [])
    if not isinstance(unit_positions, list):
        _fail("COVERAGE_UNIT_POSITIONS_LIST_REQUIRED")
    rows = []
    for chapter in chapters:
        parts = _segments(chapter, geometry, schedule, fronts)
        archival = sum(part["frames"] for part in parts if part["kind"] == "ARCHIVAL_PARTIAL_FRONT_HOLD")
        context = sum(part["frames"] for part in parts if part["kind"] == "SCHEMATIC_CONTEXT")
        visible_context = sum(part["frames"] for part in parts if part["kind"] == "SCHEMATIC_CONTEXT" and part["areasAllowed"])
        crossfade = sum(part["frames"] for part in parts if part["kind"] == "SCHEMATIC_CONTEXT"
                        and part["sourceGeometryClock"]["mode"] == "TRANSITION_SUPPLIED_SNAPSHOTS")
        event_id = chapter.get("eventId")
        reviewed = reviews.get(chapter["chapterId"], {})
        rows.append({"chapterId": chapter["chapterId"], "eventId": event_id,
                     "title": chapter.get("title"), "displayDate": chapter.get("displayLabel"),
                     "startFrame": chapter["startFrame"], "endFrame": chapter["endFrame"],
                     "startSeconds": chapter["startFrame"] / fps, "endSeconds": chapter["endFrame"] / fps,
                     "frames": chapter["endFrame"] - chapter["startFrame"],
                     "chronology": {"status": reviewed.get("actualChronologyReviewStatus", "NOT_VERIFIED"),
                                    "verifiedEventDateOrRange": deepcopy(reviewed.get("verifiedEventDateOrRange")),
                                    "eventDateIsNotFrontCoordinateProof": True},
                     "dataStatus": "SUPPORTING", "outputStatus": "NOT_VERIFIED",
                     "map": {"sourceSupport": assets["scope"], "fullSceneCoverageVerified": False,
                             "coverageAndNoDataMasks": "EXISTING_GIS_AND_PROVIDER_VALIDITY_MASKS_REQUIRED",
                             "gpuMaterialOutput": "NOT_VERIFIED"},
                     "territory": {"schematicContextFrames": context,
                                   "visibleSchematicAreaFrames": visible_context,
                                   "schematicCrossfadeFrames": crossfade,
                                   "archivalAreaSuppressedFrames": archival,
                                   "bilateralOwnershipAvailable": ownership.get("opponentComplementAllowed") is True,
                                   "completeObservedOccupationAvailable": False},
                     "front": {"archivalPartialHoldFrames": archival,
                               "schematicContextFrames": context,
                               "continuousObservedHistoricalMorphAvailable": False,
                               "sourceLabelRequired": True,
                               "archivalPositionsHeldNotInterpolated": True},
                     "camera": {"profile": deepcopy(chapter.get("cameraIntent")),
                                "configuredOwner": plan.get("cameraProfile", {}).get("owner"),
                                "actualFrameSafetyVerified": False},
                     "units": {"historicalNationalPositions": len(unit_positions),
                               "verifiedHistoricalTracksAvailable": False,
                               "existingNativeGeographicMarkersPreserved": True,
                               "missingPositionsMustNotBeInferred": True},
                     "sfx": {"eventId": event_id,
                             "eventBoundFrameRange": [chapter["startFrame"], chapter["endFrame"]],
                             "schedulerAvailable": bool(event_id),
                             "basePlanAudioEnabled": plan.get("audioSettings", {}).get("enabled") is True,
                             "actualAudioOutputVerified": False},
                     "segments": parts,
                     "limitations": (["NO_COMPLETE_BILATERAL_OCCUPATION_DATA", "NO_VERIFIED_HISTORICAL_UNIT_TRACKS",
                                      "NO_OBSERVED_CONTINUOUS_FRONT_MORPH", "GPU_VISUAL_OUTPUT_NOT_VERIFIED"]
                                     + (["NO_ARCHIVAL_FRONT_SLOT_IN_THIS_CHAPTER"] if not archival else [])
                                     + (["SCHEMATIC_CONTEXT_RETAINS_ITS_OWN_SNAPSHOT_DATE"] if context else []))})
    archival_total = sum(row["front"]["archivalPartialHoldFrames"] for row in rows)
    return {"schema": "WORLD_ENGINE_TIMELINE_DATA_COVERAGE_V1", "durationSeconds": duration,
            "fps": fps, "totalFrames": total, "chapterCount": len(chapters),
            "workSegmentCount": len(plan["scenes"]), "halfOpenPartitionVerified": True,
            "geometryClockSeparateFromNarrativeClock": production.get("narrativeClockSeparateFromGeometryClock") is True,
            "summary": {"archivalPartialHoldFrames": archival_total,
                        "schematicContextFrames": total - archival_total,
                        "archivalScheduledFrameFraction": archival_total / total,
                        "archivalSnapshotCount": len(fronts),
                        "suppliedSchematicStateCount": len(plan.get("legacyScenePlan", {}).get("time_steps", [])),
                        "observedCompleteOccupationFrames": 0,
                        "verifiedHistoricalNationalUnitTracks": 0,
                        "observedContinuousFrontMorphFrames": 0},
            "assets": assets, "rows": rows,
            "allRequiredVisualModulesApplied": False, "actual80SecondOutputVerified": False,
            "renderAllowed": False, "renderPermissionOwner": "SEPARATE_AUTHENTICATED_GPU_AND_USER_QUALITY_GATES",
            "dataSafetyBlockers": ["MISSING_COMPLETE_BILATERAL_OWNERSHIP", "MISSING_VERIFIED_NATIONAL_UNIT_TRACKS",
                                   "MISSING_OBSERVED_CONTINUOUS_FRONT_TRANSITIONS"],
            "newHistoricalCoordinatesCreated": False}
