"""Source-bound ownership admission. Partial fronts never imply complete owners.

This does not replace Area V3 or the original scalar control evaluator. The
retained history currently supplies no complete ownership field or supported
topology correspondence, so production owner morph remains explicitly blocked.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "WORLD_ENGINE_QUALIFIED_CONTROL_TIMELINE_V2"
BLOCKERS = ("FULL_CONTROL_GEOMETRY_MISSING", "CONTROL_TRANSITION_EVIDENCE_MISSING")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("CONTROL_DUPLICATE_JSON_KEY")
            value[key] = item
        return value
    def bad_constant(_):
        raise ValueError("CONTROL_FINITE_JSON_REQUIRED")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=bad_constant)


def _partition(rows, total):
    end = 0
    if not isinstance(rows, list) or not rows:
        raise ValueError("CONTROL_CONTIGUOUS_SOURCE_PARTITION_REQUIRED")
    for row in rows:
        if (not isinstance(row, dict) or type(row.get("startFrame")) is not int
                or type(row.get("endFrame")) is not int or row["startFrame"] != end
                or not end < row["endFrame"] <= total):
            raise ValueError("CONTROL_CONTIGUOUS_SOURCE_PARTITION_REQUIRED")
        end = row["endFrame"]
    if end != total:
        raise ValueError("CONTROL_EXACT_TOTAL_FRAMES_REQUIRED")


def build_control_timeline(profile_bytes, catalog_bytes):
    profile, catalog = parse(profile_bytes), parse(catalog_bytes)
    if (profile.get("schema") != "WORLD_ENGINE_QUALIFIED_EVENT_PROFILE_V2"
            or catalog.get("schema") != "WORLD_ENGINE_HISTORY_SOURCE_CATALOG_V2"
            or profile.get("sourcePlanSHA256") != catalog.get("sourcePlanSHA256")):
        raise ValueError("CONTROL_QUALIFIED_PROFILE_CATALOG_REQUIRED")
    total, fps = profile.get("totalFrames"), profile.get("fps")
    if type(total) is not int or total < 2 or type(fps) is not int or fps < 1:
        raise ValueError("CONTROL_GLOBAL_FRAME_CLOCK_REQUIRED")
    # Do not turn a new JSON claim into a new production field. A future owner
    # field adapter must validate complete masks and topology at its own boundary.
    if profile.get("fullControlStates") != [] or profile.get("controlTransitions") != []:
        raise ValueError("CONTROL_FULL_OWNER_SOURCE_ADAPTER_REQUIRED")
    chapters, schedule = profile.get("chapters"), profile.get("sourceSchedule")
    _partition(chapters, total)
    _partition(schedule, total)
    sources = catalog.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("CONTROL_SOURCE_CATALOG_REQUIRED")
    states = []
    for chapter in chapters:
        if chapter.get("controlStartState") is not None or chapter.get("controlEndState") is not None:
            raise ValueError("CONTROL_UNVERIFIED_ENDPOINT_NOT_NULL")
        states.append({"chapterId": chapter["chapterId"], "eventId": chapter["eventId"],
            "startFrame": chapter["startFrame"], "endFrame": chapter["endFrame"],
            "controlStartState": None, "controlEndState": None,
            "truthKind": "unknown", "ownerMasks": [], "sharedFront": None,
            "unknownMask": None, "unknownMaskStatus": "GEOMETRY_UNAVAILABLE",
            "contestedMask": None, "asOfDate": None, "interpolationProgress": None,
            "status": "BLOCKED_FULL_CONTROL_GEOMETRY_MISSING"})
    observations = []
    for row in schedule:
        ids = row.get("sourceIds")
        if not isinstance(ids, list) or any(x not in sources for x in ids):
            raise ValueError("CONTROL_SOURCE_REFERENCE_UNAVAILABLE")
        truth = row.get("truthKind")
        if truth not in {"observed", "schematic", "unknown", "illustrative_transition"}:
            raise ValueError("CONTROL_SOURCE_TRUTH_KIND_REQUIRED")
        if truth == "unknown" and (row.get("stateId") is not None or ids or row.get("sourceDate") is not None):
            raise ValueError("CONTROL_UNKNOWN_CANNOT_REUSE_PREVIOUS_STATE")
        if truth != "unknown" and (not ids or row.get("stateId") is None):
            raise ValueError("CONTROL_KNOWN_SOURCE_REFERENCE_REQUIRED")
        if not any(c["chapterId"] == row["chapterId"] and c["startFrame"] <= row["startFrame"]
                < row["endFrame"] <= c["endFrame"] for c in chapters):
            raise ValueError("CONTROL_SOURCE_CHAPTER_MISMATCH")
        observations.append({key: deepcopy(row.get(key)) for key in (
            "startFrame", "endFrame", "chapterId", "stateId", "kind", "truthKind",
            "sourceDate", "sourceIds", "visibleQualifier")})
    return {"schema": SCHEMA, "version": 2, "sourcePlanSHA256": profile["sourcePlanSHA256"],
        "eventProfileSHA256": sha(profile_bytes), "sourceCatalogSHA256": sha(catalog_bytes),
        "totalFrames": total, "fps": fps, "frameConvention": "GLOBAL_HALF_OPEN",
        "states": states, "sourceObservations": observations, "ownerFields": [], "transitions": [],
        "noUnknownComplement": True, "noPartialFrontClosure": True,
        "noPreviousStateFallback": True, "scalarEngineReused": False,
        "scalarEngineAvailability": "ORIGINAL_SCALAR_AVAILABLE_BUT_INPUT_BLOCKED",
        "scalarEngineSource": "web/map_infographic_v1/territory_control_adapter_v1.mjs",
        "scalarLimit": "Single latitude for each longitude, 2..64 knots; not a general polygon topology adapter",
        "renderingPolicy": "QUALIFIED_SOURCE_REVIEW_WITHOUT_FULL_OWNER_DRAW",
        "blockers": list(BLOCKERS), "productionReady": False,
        "nvidiaHardwareVerified": False, "visualQualityApproved": False}


def validate_control_timeline(document, request, resolved_documents):
    profile_bytes = (HERE / "fixtures/HISTORY_EVENT_PROFILE_V2.json").read_bytes()
    catalog_bytes = (HERE / "fixtures/HISTORY_SOURCE_CATALOG.json").read_bytes()
    expected = build_control_timeline(profile_bytes, catalog_bytes)
    if document != expected:
        raise ValueError("CONTROL_TIMELINE_ACTUAL_SOURCE_BINDING_CHANGED")
    if (request.get("sourcePlanSha256") != expected["sourcePlanSHA256"]
            or resolved_documents.get("eventDirectorProfileRef") != parse(profile_bytes)
            or resolved_documents.get("sourceCatalogRef") != parse(catalog_bytes)):
        raise ValueError("CONTROL_TIMELINE_REQUEST_SOURCE_MISMATCH")
    return {"ready": False, "reviewReady": request.get("purpose") == "QUALIFIED_SOURCE_REVIEW",
        "blockers": [{"code": code, "status": "BLOCKED", "path": "controlTimelineRef",
            "detail": "Partial observed fronts and schematic held-cores cannot define complete owner masks or morph."}
            for code in BLOCKERS], "ownerFieldAvailable": False, "historicalMorphAvailable": False,
        "sourceObservationsRetained": len(expected["sourceObservations"]),
        "eventProfileSHA256": expected["eventProfileSHA256"],
        "sourceCatalogSHA256": expected["sourceCatalogSHA256"], "noPreviousStateFallback": True,
        "actualDrawVerified": False, "visualQualityApproved": False}


if __name__ == "__main__":
    value = build_control_timeline((HERE / "fixtures/HISTORY_EVENT_PROFILE_V2.json").read_bytes(),
        (HERE / "fixtures/HISTORY_SOURCE_CATALOG.json").read_bytes())
    target = HERE / "fixtures/CONTROL_TIMELINE.json"
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "BLOCKED_OWNER_GEOMETRY_SOURCE_REVIEW_AVAILABLE",
        "path": str(target), "sha256": sha(target.read_bytes()), "productionReady": False}))
