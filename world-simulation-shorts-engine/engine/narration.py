"""Declared Scene-context narration bindings; never lexical or ASR alignment.

The legacy event list describes the Scene's context. Late events may therefore
fall outside a short voice cue; that does not make them word-level anchors.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math

from .gis import UnknownLocation, resolve_location, verified_coordinate

SCOPE = ("Declared same-Scene event/GIS/claim references and measured or supplied cue intervals; "
         "not speech recognition, lexical verification, word alignment, or proof that a named word occurs at an event timestamp")
PLANNED_ROUTE_INFORMATION = {"comparison_reveal", "route_choice", "distance_reveal", "alternate_route_reveal",
                             "connection_reveal", "consequence_reveal", "new_variable", "escalation",
                             "peak_reveal", "final_reveal"}
PHYSICAL_EVENT_KINDS = {"route_start", "entity_departure", "arrival", "network_expand", "route_blocked"}


def validate_narration_bindings(plan: dict) -> dict:
    errors, warnings, reports = [], [], []
    scenes = plan.get("scenes", [])
    owners = {}
    planned_routes, route_signatures, route_scenes = {}, {}, {}
    conflicting_routes = set()
    global_entity_ids = set()
    for scene in scenes:
        global_entity_ids.update(entity.get("id") for entity in scene.get("entities", []))
        for route in scene.get("routes", []):
            rid = route.get("route_id", route.get("id"))
            if not rid:
                continue
            # Scene-local progress/time/style may change while the GIS route is
            # the same. Kind, ordered sourced points and source IDs identify it.
            signature = json.dumps({"kind": route.get("kind"), "points": route.get("points", []),
                                    "source_ids": sorted(route.get("source_ids", []))}, sort_keys=True)
            if rid in route_signatures and route_signatures[rid] != signature:
                conflicting_routes.add(rid)
            route_signatures.setdefault(rid, signature)
            planned_routes.setdefault(rid, route)
            route_scenes.setdefault(rid, set()).add(scene.get("scene_id"))
        for event in scene.get("visual_events", []):
            if isinstance(event, dict) and isinstance(event.get("id"), str):
                owners.setdefault(event["id"], set()).add(scene.get("scene_id"))
    errors.extend({"code": "CONFLICTING_NARRATION_ROUTE_ID", "route_id": rid,
                   "owner_scene_ids": sorted(str(sid) for sid in route_scenes[rid])}
                  for rid in sorted(conflicting_routes))
    claims = {claim["id"]: claim for claim in plan.get("story", {}).get("claims", [])}
    sources = {source["id"] for source in plan.get("sources", [])}
    for scene in scenes:
        sid = scene.get("scene_id")
        narrated = bool(str(scene.get("narration", "")).strip())
        raw_ids = scene.get("narration_event_ids", [])
        if not isinstance(raw_ids, list) or any(not isinstance(eid, str) or not eid for eid in raw_ids):
            errors.append({"code": "INVALID_NARRATION_EVENT_BINDINGS", "scene_id": sid})
            raw_ids = []
        if narrated and not raw_ids:
            errors.append({"code": "MISSING_NARRATION_EVENT_BINDINGS", "scene_id": sid})
        if len(raw_ids) != len(set(raw_ids)):
            errors.append({"code": "DUPLICATE_NARRATION_EVENT_BINDING", "scene_id": sid})
        local = {event["id"]: event for event in scene.get("visual_events", [])
                 if isinstance(event, dict) and isinstance(event.get("id"), str)}
        routes = {route.get("route_id", route.get("id")): route for route in scene.get("routes", [])}
        entities = {entity.get("id"): entity for entity in scene.get("entities", [])}
        scene_claim_ids = scene.get("claim_ids", [])
        scene_claims = []
        for cid in scene_claim_ids:
            if cid not in claims:
                errors.append({"code": "UNKNOWN_NARRATION_SCENE_CLAIM", "scene_id": sid, "claim_id": cid})
            else:
                claim = claims[cid]
                scene_claims.append({"claim_id": cid, "status": claim.get("status"),
                                     "source_ids": list(claim.get("source_ids", [])),
                                     "assumption_ids": list(claim.get("assumption_ids", []))})
        bindings = []
        for eid in dict.fromkeys(raw_ids):
            if eid not in local:
                errors.append({"code": "CROSS_SCENE_NARRATION_EVENT" if eid in owners else "UNKNOWN_NARRATION_EVENT",
                               "scene_id": sid, "event_id": eid,
                               "owner_scene_ids": sorted(str(owner) for owner in owners.get(eid, []))})
                continue
            event = local[eid]
            cid = event.get("claim_id")
            if cid and cid not in claims:
                errors.append({"code": "UNKNOWN_NARRATION_EVENT_CLAIM", "scene_id": sid,
                               "event_id": eid, "claim_id": cid})
            elif cid and cid not in scene_claim_ids:
                errors.append({"code": "NARRATION_CLAIM_OUTSIDE_SCENE", "scene_id": sid,
                               "event_id": eid, "claim_id": cid})
            target_id = event.get("target_id")
            target_kind = "scene_context"
            target_scope = "declared_in_scene"
            target_sources = []
            planned_target_scenes = []
            coordinates = []
            if target_id in routes:
                target_kind = "route"
                points = routes[target_id].get("points", [])
                target_sources = list(routes[target_id].get("source_ids", []))
                coordinates = [points[0], points[-1]] if points else []
            elif target_id in entities:
                target_kind = "entity"
                entity = entities[target_id]
                route = routes.get(entity.get("route_id"))
                if route and route.get("points"):
                    coordinates = [route["points"][0], route["points"][-1]]
                    target_sources = list(route.get("source_ids", []))
                elif entity.get("coordinates"):
                    coordinates = [entity["coordinates"]]
            elif (target_id in planned_routes and target_id not in conflicting_routes
                  and event.get("kind") in PLANNED_ROUTE_INFORMATION):
                target_kind = "planned_route"
                target_scope = "not_active_in_scene"
                route = planned_routes[target_id]
                points = route.get("points", [])
                coordinates = [points[0], points[-1]] if points else []
                target_sources = list(route.get("source_ids", []))
                planned_target_scenes = sorted(str(sid) for sid in route_scenes[target_id])
            elif (target_id in planned_routes or target_id in global_entity_ids) and event.get("kind") in PHYSICAL_EVENT_KINDS:
                target_kind = "unresolved_physical_target"
                target_scope = "not_active_in_scene"
                errors.append({"code": "OFF_SCENE_NARRATION_PHYSICAL_TARGET", "scene_id": sid,
                               "event_id": eid, "target_id": target_id})
            elif target_id:
                try:
                    location = resolve_location(target_id)
                    target_kind = "verified_gis_location"
                    coordinates = [location["coordinates"]]
                    target_sources = [location["coordinates"]["source_id"]]
                except UnknownLocation:
                    target_kind = "unresolved_target"
                    target_scope = "unresolved"
                    warnings.append({"code": "NARRATION_TARGET_ID_NOT_IN_GIS_CATALOG", "scene_id": sid,
                                     "event_id": eid, "target_id": target_id})
            if event.get("coordinates"):
                coordinates.append(event["coordinates"])
            if not coordinates and scene.get("coordinates"):
                coordinates = [scene["coordinates"]]
            gis = []
            unique = set()
            for coordinate in coordinates:
                key = tuple(coordinate.get(field) for field in ["lon", "lat", "source_id", "location_id"])
                if key in unique:
                    continue
                unique.add(key)
                verified = verified_coordinate(coordinate)
                source_id = coordinate.get("source_id")
                if not verified:
                    errors.append({"code": "UNVERIFIED_NARRATION_GIS_REFERENCE", "scene_id": sid, "event_id": eid})
                if source_id not in sources:
                    errors.append({"code": "MISSING_NARRATION_GIS_SOURCE", "scene_id": sid,
                                   "event_id": eid, "source_id": source_id})
                gis.append({**deepcopy(coordinate), "verified": verified})
            claim = claims.get(cid, {})
            for source_id in target_sources:
                if source_id not in sources:
                    errors.append({"code": "MISSING_NARRATION_TARGET_SOURCE", "scene_id": sid,
                                   "event_id": eid, "source_id": source_id})
            bindings.append({"event_id": eid, "kind": event.get("kind"), "scope": "scene_context",
                             "local_time": event.get("time"),
                             "absolute_time": float(scene.get("start_time", 0))+float(event.get("time", 0)),
                             "target_id": target_id, "target_kind": target_kind, "target_scope": target_scope,
                             "target_source_ids": target_sources, "target_source_ids_known": all(source in sources for source in target_sources),
                             "planned_route_scene_ids": planned_target_scenes,
                             "physical_activity_verified": False, "gis_references": gis,
                             "claim_id": cid, "claim_status": claim.get("status"),
                             "claim_source_ids": list(claim.get("source_ids", [])),
                             "word_anchor": False})
        reports.append({"scene_id": sid, "narration_present": narrated, "narration_event_ids": list(raw_ids),
                        "scope": "scene_context", "event_bindings": bindings, "claim_references": scene_claims,
                        "geographic_targets": list(scene.get("geographic_targets", [])), "word_alignment": False})
    return {"passed": not errors, "errors": errors, "warnings": warnings, "scenes": reports, "scope": SCOPE,
            "lexical_content_verified": False, "word_alignment": False}


def attach_narration_timing(plan: dict, binding_report: dict, cues: list[dict], narration_metadata: list[dict]) -> dict:
    """Record real Scene synthesis windows or explicit user cues without ASR claims."""
    report = deepcopy(binding_report)
    scenes = {scene["scene_id"]: scene for scene in plan.get("scenes", [])}
    metadata = {entry.get("scene_id"): entry for entry in narration_metadata if entry.get("scene_id")}
    external = any(entry.get("provider") == "USER_FILE" for entry in narration_metadata)
    external_duration = next((entry.get("duration") for entry in narration_metadata
                              if entry.get("provider") == "USER_FILE"), None)
    for cue in cues:
        sid = cue.get("scene_id")
        if sid is not None and sid not in scenes:
            report["errors"].append({"code": "UNKNOWN_NARRATION_CUE_SCENE", "scene_id": sid})
            continue
        start, end = cue.get("start"), cue.get("end")
        if (not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start
                or end > float(plan.get("duration", 0))+.05):
            report["errors"].append({"code": "INVALID_NARRATION_CUE_INTERVAL", "scene_id": sid})
        elif sid is not None:
            scene = scenes[sid]
            if start < float(scene["start_time"])-.05 or end > float(scene["start_time"])+float(scene["duration"])+.05:
                report["errors"].append({"code": "NARRATION_CUE_OUTSIDE_DECLARED_SCENE", "scene_id": sid})
        if (external and isinstance(end, (int, float)) and isinstance(external_duration, (int, float))
                and end > external_duration+.05):
            report["errors"].append({"code": "NARRATION_CUE_EXCEEDS_AUDIO_FILE", "scene_id": sid})
    for scene_report in report["scenes"]:
        sid = scene_report["scene_id"]
        scene = scenes[sid]
        scene_start, scene_end = float(scene["start_time"]), float(scene["start_time"])+float(scene["duration"])
        attached = []
        for cue in cues:
            if cue.get("scene_id") not in {None, sid}:
                continue
            start, end = cue.get("start"), cue.get("end")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                continue
            if not math.isfinite(start) or not math.isfinite(end) or min(end, scene_end) <= max(start, scene_start):
                continue
            attached.append({"start": float(start), "end": float(end),
                             "scene_overlap_start": max(float(start), scene_start),
                             "scene_overlap_end": min(float(end), scene_end),
                             "timing_source": cue.get("timing_source", "user_provided" if external else "unspecified"),
                             "measured_scene_synthesis": cue.get("timing_source") == "measured_scene_synthesis" and not external,
                             "declared_narration_event_ids": list(scene_report["narration_event_ids"]),
                             "declared_claim_ids": list(scene.get("claim_ids", [])), "word_alignment": False})
        status = ("USER_PROVIDED_CUES" if external and attached else "EXTERNAL_TIMING_UNAVAILABLE" if external
                  else "MEASURED_SCENE_SYNTHESIS" if sid in metadata and attached
                  else "NOT_MEASURED_TTS_OFF" if not plan.get("options", {}).get("tts")
                  else "NO_NARRATION_CUE")
        scene_report["timing"] = {"status": status, "cues": attached,
                                  "measured_scene_synthesis": status == "MEASURED_SCENE_SYNTHESIS",
                                  "word_alignment": False}
        if status == "NO_NARRATION_CUE" and scene_report["narration_present"]:
            report["errors"].append({"code": "MISSING_MEASURED_NARRATION_CUE", "scene_id": sid})
        for binding in scene_report["event_bindings"]:
            binding["authored_event_inside_voice_window"] = any(cue["start"] <= binding["absolute_time"] <= cue["end"] for cue in attached)
            binding["outside_voice_window_is_error"] = False  # Context links are not word anchors.
    if external:
        report["warnings"].append({"code": "EXTERNAL_NARRATION_CONTENT_NOT_RECOGNIZED",
                                    "message": "External cue times are user-provided; spoken content and word positions were not recognized."})
    report["passed"] = not report["errors"]
    return report
