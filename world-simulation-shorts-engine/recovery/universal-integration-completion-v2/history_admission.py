"""Admit source-qualified infographic history without inventing missing facts.

This data-only assessment reuses the preserved coverage evaluator. It does not
grant GPU, user-quality, image-integrity or production approval. Country names,
event dates and geometry remain in the supplied source fixtures.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
RECOVERY = HERE.parent
_SHA = re.compile(r"[0-9a-f]{64}\Z")
REQUEST_FIELDS = frozenset({"completeOccupation", "nationalUnits", "movingUnits", "routes",
                            "combatImpacts", "observedDailyFronts", "fullSceneHighDetail",
                            "exactEventDates", "sourceEndpointTransitions"})
DEFAULT_REQUEST = {name: False for name in REQUEST_FIELDS}
DEFAULT_REQUEST["sourceEndpointTransitions"] = True


class HistoryAdmissionError(ValueError):
    pass


def _fail(code):
    raise HistoryAdmissionError(code)


def _coverage_module():
    path = RECOVERY / "universal-integration-v1/data_coverage.py"
    spec = importlib.util.spec_from_file_location("_completion_preserved_data_coverage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _same_json(left, right):
    return json.dumps(left, sort_keys=True, separators=(",", ":"), allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _request(value):
    if value is None:
        return deepcopy(DEFAULT_REQUEST)
    if not isinstance(value, dict) or set(value) - REQUEST_FIELDS or any(type(v) is not bool for v in value.values()):
        _fail("HISTORY_REQUEST_FIELD_OR_TYPE_UNSUPPORTED")
    return {**DEFAULT_REQUEST, **value}


def _source_checks(plan, front_profile, source_bindings):
    manifest = plan.get("sourceManifest", {})
    if not isinstance(manifest, dict) or not _SHA.fullmatch(str(manifest.get("factsSHA256", ""))):
        _fail("HISTORY_SCHEMATIC_FACTS_HASH_REQUIRED")
    archive = manifest.get("archivalFrontV4", {})
    if not isinstance(archive, dict) or any(not _SHA.fullmatch(str(archive.get(key, "")))
                                          for key in ("profileSha256", "sourceManifestSha256")):
        _fail("HISTORY_ARCHIVAL_SOURCE_BINDING_REQUIRED")
    checks = {"declaredFactsHashPresent": True, "declaredFrontProfileHashPresent": True,
              "declaredFrontManifestHashPresent": True, "actualSourceBytesVerifiedByThisAssessment": False,
              "authority": "PARENT_SOURCE_MANIFEST_GATE_AND_PRESERVED_HASH_RECEIPTS"}
    if source_bindings is not None:
        if not isinstance(source_bindings, dict):
            _fail("HISTORY_SOURCE_BINDINGS_INVALID")
        for key in ("VIDEO_PLAN_80S.json", "FRONT_PROFILE.json", "FRONT_FILES.json", "PARENT_PLAN_80S.json"):
            if not _SHA.fullmatch(str(source_bindings.get(key, ""))):
                _fail("HISTORY_SOURCE_BINDING_SHA_REQUIRED")
        if (source_bindings["FRONT_PROFILE.json"] != archive["profileSha256"]
                or source_bindings["FRONT_FILES.json"] != archive["sourceManifestSha256"]
                or source_bindings["PARENT_PLAN_80S.json"] != front_profile.get("unchangedBasePlanSha256")):
            _fail("HISTORY_SOURCE_BINDING_SHA_MISMATCH")
        checks["preservedReceiptCrossBindingsMatch"] = True
    else:
        checks["preservedReceiptCrossBindingsMatch"] = "NOT_VERIFIED"
    facts_sha = manifest["factsSHA256"]
    styles = plan.get("productionV3", {}).get("visualBindings", {}).get("areaStyles", [])
    areas = {row.get("id"): row for row in plan.get("legacyScenePlan", {}).get("areas", [])}
    if not styles or len(styles) != len(areas):
        _fail("HISTORY_HELD_CORE_ROLE_BINDINGS_REQUIRED")
    for style in styles:
        area = areas.get(style.get("areaId"))
        proof = style.get("sourceProof", {})
        if (not area or style.get("sourceGeometryRef") != area.get("geometry_ref")
                or style.get("sourceStateId") != area.get("stage_id")
                or style.get("enemyComplementAdmitted") is not False
                or style.get("measuredMilitaryControl") is not False
                or not isinstance(style.get("factionId"), str) or not style["factionId"]
                or proof.get("factsSHA256") != facts_sha
                or not proof.get("fields") or not proof.get("qualification")):
            _fail("HISTORY_SOURCE_QUALIFIED_HELD_CORE_REQUIRED")
    for front in front_profile.get("fronts", []):
        source = front.get("source", {})
        if (source.get("classification") != "OBSERVED_UN_FRONT"
                or source.get("reviewStatus") != "SOURCE_LINE_AND_TRACE_REVIEWED"
                or source.get("registrationMode") != "REFERENCE_CONTROL_AFFINE_APPROXIMATION"
                or any(not _SHA.fullmatch(str(source.get(key, ""))) for key in
                       ("documentSha256", "rasterSha256", "pixelTraceSha256", "registrationReportSha256"))):
            _fail("HISTORY_REVIEWED_PARTIAL_FRONT_PROOF_REQUIRED")
    checks["heldCoreSourceRolesAndNoOpponentComplement"] = True
    checks["archivalActualFrontNotAttackOrPhaseLine"] = True
    return checks


def assess_history(plan, front_profile, *, coverage=None, requested=None, source_bindings=None):
    """Return precise semantic data admission for a supplied qualified plan.

    ``coverage`` is an optional preserved report; its primary timeline counts
    and chapter/segment ranges are recomputed before reuse. Unknown capability
    requests fail. Missing optional datasets block those explicitly requested
    capabilities, rather than automatically blocking all qualified history.
    """
    request = _request(requested)
    calculated = _coverage_module().build_coverage(plan, front_profile)
    if coverage is not None:
        if (not isinstance(coverage, dict) or coverage.get("totalFrames") != calculated["totalFrames"]
                or coverage.get("fps") != calculated["fps"]
                or coverage.get("summary") != calculated["summary"]
                or len(coverage.get("rows", [])) != len(calculated["rows"])):
            _fail("HISTORY_PRESERVED_COVERAGE_MISMATCH")
        for original, derived in zip(coverage["rows"], calculated["rows"]):
            for field in ("chapterId", "eventId", "startFrame", "endFrame", "segments", "territory", "front"):
                if not _same_json(original.get(field), derived.get(field)):
                    _fail("HISTORY_PRESERVED_COVERAGE_MISMATCH")
        selected = deepcopy(coverage)
    else:
        selected = calculated
    bindings = source_bindings if source_bindings is not None else (coverage or {}).get("inputBindings")
    checks = _source_checks(plan, front_profile, bindings)
    base_admitted = all(row["front"]["archivalPartialHoldFrames"] + row["front"]["schematicContextFrames"] == row["frames"]
                        for row in selected["rows"])
    unavailable = {
        "completeOccupation": ("COMPLETE_BILATERAL_OWNERSHIP_MISSING", "Dated source-backed faction polygons; the held-core complement is not opponent territory."),
        "nationalUnits": ("DATED_HISTORICAL_UNIT_POSITIONS_MISSING", "Identity, role/time participation proof and dated source-backed positions are required."),
        "movingUnits": ("HISTORICAL_UNIT_TRACKS_MISSING", "Dated source-backed route/position sequences and role proof are required."),
        "routes": ("HISTORICAL_ROUTE_GEOMETRY_MISSING", "Source-backed route geometry, direction, times and event meaning are required; no decorative routes."),
        "combatImpacts": ("SOURCED_COMBAT_LOCATION_EVENT_MISSING", "Dated event locations/geometry and source-backed impact meaning are required."),
        "observedDailyFronts": ("OBSERVED_DAILY_FRONT_SEQUENCE_MISSING", "Actual intermediate dated fronts are required for an observed-daily claim."),
        "fullSceneHighDetail": ("FULL_SCENE_DEM_DEPTH_SUPPORT_MISSING", "Terrain/depth support must cover the required scene footprint; the supplied files are regional samples."),
    }
    optional = [{"capability": name, "status": "BLOCKED_BY_DATA", "requested": request[name],
                 "code": code, "missingInput": detail, "blocksQualifiedBasePlan": False}
                for name, (code, detail) in unavailable.items()]
    partial_dates = [row["chapterId"] for row in selected["rows"]
                     if "PARTIAL" in row.get("chronology", {}).get("status", "")
                     or row.get("chronology", {}).get("status") == "NOT_VERIFIED"]
    optional.append({"capability": "exactEventDates", "status": "BLOCKED_BY_DATA" if partial_dates else "SUPPORTING",
                     "requested": request["exactEventDates"], "code": "EXACT_EVENT_DATE_PROOF_PARTIAL" if partial_dates else None,
                     "affectedChapters": partial_dates, "blocksQualifiedBasePlan": False,
                     "missingInput": "Exact day evidence for partially verified chapters; otherwise display the reviewed phase/range with a qualifier."})
    essential = [{"code": row["code"], "capability": row["capability"], "missingInput": row["missingInput"]}
                 for row in optional if row["requested"] and row["status"] == "BLOCKED_BY_DATA"]
    if not base_admitted:
        essential.append({"code": "INCOMPLETE_SOURCE_QUALIFIED_TIMELINE", "capability": "qualifiedBasePlan"})
    chapter_rows = []
    for row in selected["rows"]:
        state_ids = {part["sourceGeometryClock"].get(key) for part in row["segments"]
                     for key in ("fromStateId", "toStateId", "sourceStateId")}
        held_roles = [deepcopy(style) for style in plan["productionV3"]["visualBindings"]["areaStyles"]
                      if style["sourceStateId"] in state_ids]
        selected_front_ids = {part.get("frontId") for part in row["segments"] if part.get("frontId")}
        archival_proofs = [{"frontId": item["frontId"], "mapDate": item["mapDate"],
                           "sourceFile": item["sourceFile"], "geoJsonSha256": item["geoJsonSha256"],
                           "source": deepcopy(item["source"]),
                           "partialSegments": item["partialSegments"],
                           "verifiedSourceExtent": item["verifiedSourceExtent"]}
                          for item in front_profile["fronts"] if item["frontId"] in selected_front_ids]
        chapter_rows.append({"chapterId": row["chapterId"], "eventId": row["eventId"],
                             "startFrame": row["startFrame"], "endFrame": row["endFrame"], "frames": row["frames"],
                             "chronology": deepcopy(row["chronology"]),
                             "territory": {**deepcopy(row["territory"]), "admission": "QUALIFIED_HELD_CORE_ONLY",
                                           "opponentComplementAllowed": False},
                             "front": {**deepcopy(row["front"]), "admission": "QUALIFIED_PARTIAL_SOURCE_HOLD_OR_SCHEMATIC",
                                       "vertexMorphOfUnobservedDatesAllowed": False},
                             "sourceSegments": deepcopy(row["segments"]),
                             "sourceEvidence": {"heldCoreRoleBindings": held_roles,
                                                "archivalFrontProofs": archival_proofs,
                                                "coverageMaskOwner": "EXISTING_NATIVE_GIS_AND_PROVIDER_VALIDITY",
                                                "outsideSourceSupport": "UNCHANGED_BASE_MATERIAL"},
                             "map": deepcopy(row["map"]), "camera": deepcopy(row["camera"]),
                             "units": {**deepcopy(row["units"]), "status": "BLOCKED_BY_DATA_IF_REQUESTED"},
                             "sfx": {**deepcopy(row["sfx"]), "status": "SUPPORTING_EVENT_BOUND_CUES"},
                             "moduleCoverage": {
                                 "PlannerScene": "SUPPORTING_SOURCE_BOUND_CHAPTER_AND_SEPARATE_GEOMETRY_CLOCK",
                                 "Area": "QUALIFIED_HELD_CORE_ONLY_SUPPRESSED_DURING_ARCHIVAL_FRONT_ONLY",
                                 "Frontier": "QUALIFIED_SCHEMATIC_OR_APPROXIMATE_PARTIAL_DATED_SOURCE",
                                 "Camera": "SUPPORTING_SOURCE_GEOMETRY_BOUNDS_NOT_RENDERED_SAFETY_PROOF",
                                 "MapAstra": "SUPPORTING_VALID_REGIONAL_SOURCES_WITH_EXISTING_FALLBACK",
                                 "FlowMovingObject": "BLOCKED_BY_MISSING_HISTORICAL_ROUTE_OR_POSITION_IF_REQUESTED",
                                 "MilitaryMarkers": "BLOCKED_BY_MISSING_DATED_UNIT_POSITION_AND_ROLE_IF_REQUESTED",
                                 "Event": "SUPPORTING_EXISTING_DATED_CHAPTER_NO_NEW_METRIC_FACTS",
                                 "Sfx": "SUPPORTING_EXISTING_CHAPTER_EVENT_FRAME_RANGE_NO_AUDIO_OUTPUT_PROOF",
                             },
                             "semanticDataStatus": "QUALIFIED_DATA_ADMITTED",
                             "actualRenderedOutputStatus": "NOT_VERIFIED"})
    return {"schema": "WORLD_ENGINE_HISTORY_ADMISSION_V2", "grade": "FACT_BASED_VISUAL_GRADE",
            "status": "QUALIFIED_DATA_ADMITTED" if not essential else "REQUESTED_CAPABILITY_DATA_BLOCKED",
            "dataAdmitted": not essential, "qualifiedBasePlanAdmitted": base_admitted,
            "essentialDataBlockers": essential, "optionalCapabilityBlockers": optional,
            "request": request, "sourceChecks": checks,
            "totalFrames": selected["totalFrames"], "fps": selected["fps"],
            "durationSeconds": selected["durationSeconds"], "chapterCount": selected["chapterCount"],
            "summary": deepcopy(selected["summary"]), "sourceBindings": deepcopy(bindings),
            "chapterCoverage": chapter_rows, "assets": deepcopy(selected.get("assets", {})),
            "endpointTransitions": {"requested": request["sourceEndpointTransitions"],
                                    "dataStatus": "SUPPORTING_WITH_QUALIFICATION",
                                    "schematicOriginalEndpointAlphaAllowed": True,
                                    "partialFrontOriginalGeometryCrossfadeDataAllowed": True,
                                    "partialFrontCrossfadeRendererConnected": "NOT_VERIFIED",
                                    "sourceDatesAndPartialExtentMustRemainVisible": True,
                                    "intermediateObservedFrontClaimAllowed": False,
                                    "vertexMorphOrGapBridgingAllowed": False,
                                    "inferredOccupationFillAllowed": False},
            "qualifications": ["SCHEMATIC_CONTEXT_IS_NOT_OBSERVED_DAILY_CONTROL",
                               "ARCHIVAL_FRONT_IS_APPROXIMATE_PARTIAL_AND_DATE_QUALIFIED",
                               "ARCHIVAL_FRONT_ONLY_SLOTS_SUPPRESS_OCCUPATION_FILL",
                               "NO_OPPONENT_COMPLEMENT_INFERENCE", "NO_INVENTED_NATIONAL_UNITS_OR_ROUTES",
                               "PARTIAL_DATE_REVIEW_MUST_NOT_BE_PROMOTED_TO_EXACT_DAY_PROOF",
                               "REGIONAL_ASTRA_USES_ORIGINAL_MASKS_AND_UNCHANGED_FALLBACK",
                               "SOURCE_ENDPOINT_ALPHA_IS_PRESENTATION_NOT_OBSERVED_HISTORY"],
            "partialExactDateChapterIds": partial_dates,
            "renderAllowed": False, "gpuOutputVerified": False, "userQualityApproved": False,
            "renderPermissionOwner": "SEPARATE_SOURCE_IMAGE_GPU_COST_AND_5S_USER_QUALITY_GATES",
            "newHistoricalCoordinatesCreated": False}


def load_default_admission(*, requested=None):
    """Assess the preserved acceptance fixture; no external data acquisition."""
    data = RECOVERY / "verified-front-data-v4-recovery"
    plan_path, profile_path = data / "VIDEO_PLAN_80S.json", data / "FRONT_PROFILE.json"
    coverage_path = RECOVERY / "universal-integration-v1/reports/TIMELINE_80S_COVERAGE.json"
    coverage = json.loads(coverage_path.read_text())
    bindings = coverage["inputBindings"]
    for name in ("VIDEO_PLAN_80S.json", "FRONT_PROFILE.json", "FRONT_FILES.json", "PARENT_PLAN_80S.json"):
        if hashlib.sha256((data / name).read_bytes()).hexdigest() != bindings[name]:
            _fail("HISTORY_PRESERVED_SOURCE_BYTES_CHANGED")
    result = assess_history(json.loads(plan_path.read_text()), json.loads(profile_path.read_text()),
                            coverage=coverage, requested=requested, source_bindings=bindings)
    result["sourceChecks"]["actualPrimaryPlanProfileManifestParentBytesVerified"] = True
    result["sourceChecks"]["archiveMembersRehashed"] = False
    result["sourceChecks"]["priorOriginalAssetIntegrityReceiptReused"] = True
    return result
