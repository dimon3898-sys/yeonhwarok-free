"""Bounded offline NL -> existing verified-facts Scene V1 -> long-video wrapper.

No external LLM is connected. Unknown topics, unavailable facts and unsupported
precision requests fail closed. Existing compileScenePlan owns event semantics.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from contracts import (SCHEMA, ContractError, canonical_json, canonical_sha256,
                       split_plan, total_frames, validate_plan)

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent.parent
DEFAULT_CATALOG = HERE / "HISTORY_CATALOG.json"
LEGACY_PLANNER = ENGINE / "web/map_infographic_v1/planner_scene_v1.mjs"
BLOCKED_PRECISION = re.compile(r"정밀.{0,12}(?:일별|매일|병력|부대)|실제.{0,8}부대.{0,8}(?:이동|위치)|고증.{0,8}정확|archival|day.by.day|precise.{0,12}(?:unit|front)", re.I)


class PlanningError(ContractError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def parse_request(topic: str, *, duration_seconds=None, fps: int = 30, resolution=None,
                  aspect_ratio: str | None = None, visual_style: str = "REFERENCE_VISUAL_V2") -> dict:
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 4000 or any(ord(c) < 32 for c in topic):
        raise PlanningError("INVALID_TOPIC")
    if visual_style != "REFERENCE_VISUAL_V2":
        raise PlanningError("UNSUPPORTED_VISUAL_STYLE")
    durations = []
    for match in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(초|분|seconds?|secs?|minutes?|mins?)(?![A-Za-z])", topic, re.I):
        multiplier = 60 if match.group(2).casefold() in {"분", "minute", "minutes", "min", "mins"} else 1
        durations.append(Fraction(match.group(1)) * multiplier)
    # Compound '1분 20초' is one duration; repeated duration choices are ambiguous.
    if len(durations) > 1:
        if len(durations) == 2 and re.search(r"\d+(?:\.\d+)?\s*(?:분|minutes?|mins?)\s*\d+(?:\.\d+)?\s*(?:초|seconds?|secs?)", topic, re.I):
            durations = [sum(durations)]
        elif len(set(durations)) > 1:
            raise PlanningError("AMBIGUOUS_DURATION")
        else:
            durations = durations[:1]
    parsed_duration = durations[0] if durations else None
    if duration_seconds is None:
        if parsed_duration is None:
            raise PlanningError("DURATION_REQUIRED", "Pass durationSeconds or include seconds/minutes in the topic")
        duration_seconds = float(parsed_duration)
    elif parsed_duration is not None and Fraction(str(duration_seconds)) != parsed_duration:
        raise PlanningError("DURATION_CONFLICT")
    frames = total_frames(duration_seconds, fps)
    mentioned_fps = {int(value) for value in re.findall(r"(?<!\d)(\d+)\s*fps\b", topic, re.I)}
    if mentioned_fps and mentioned_fps != {fps}:
        raise PlanningError("FPS_CONFLICT")
    mentioned_res = {(int(w), int(h)) for w, h in re.findall(r"(?<!\d)(\d{2,4})\s*[×xX]\s*(\d{2,4})(?!\d)", topic)}
    if len(mentioned_res) > 1:
        raise PlanningError("AMBIGUOUS_RESOLUTION")
    if resolution is None:
        if mentioned_res:
            width, height = next(iter(mentioned_res))
            resolution = {"width": width, "height": height}
        else:
            resolution = {"width": 1920, "height": 1080} if re.search(r"가로|landscape", topic, re.I) else {"width": 1080, "height": 1920}
    elif not isinstance(resolution, dict):
        raise PlanningError("INVALID_RESOLUTION")
    elif mentioned_res and (resolution.get("width"), resolution.get("height")) not in mentioned_res:
        raise PlanningError("RESOLUTION_CONFLICT")
    if not isinstance(resolution, dict) or set(resolution) != {"width", "height"} or any(isinstance(resolution[k], bool) or not isinstance(resolution[k], int) or not 2 <= resolution[k] <= 8192 or resolution[k] % 2 for k in ("width", "height")):
        raise PlanningError("INVALID_RESOLUTION")
    ratios = set(re.findall(r"(?<!\d)(\d{1,4}:\d{1,4})(?!\d)", topic))
    if len(ratios) > 1:
        raise PlanningError("AMBIGUOUS_ASPECT_RATIO")
    if aspect_ratio is None:
        if ratios:
            aspect_ratio = next(iter(ratios))
        else:
            from math import gcd
            w, h = resolution["width"], resolution["height"]
            divisor = gcd(w, h)
            aspect_ratio = f"{w // divisor}:{h // divisor}"
    elif ratios and ratios != {aspect_ratio}:
        raise PlanningError("ASPECT_RATIO_CONFLICT")
    return {"topic": topic.strip(), "durationSeconds": duration_seconds, "fps": fps,
            "totalFrames": frames, "resolution": deepcopy(resolution), "aspectRatio": aspect_ratio,
            "visualStyle": visual_style, "plannerMode": "OFFLINE_CONSTRAINED_FACT_CATALOG",
            "externalAIConnected": False}


def _bound_file(relative: str, expected_sha: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise PlanningError("CATALOG_PATH_INVALID", label)
    path = (ENGINE / relative).resolve()
    if not path.is_relative_to(ENGINE.resolve()) or not path.is_file():
        raise PlanningError("CATALOG_FILE_MISSING", label)
    if _sha(path) != expected_sha:
        raise PlanningError("CATALOG_SOURCE_HASH_MISMATCH", label)
    return path


def _entry(topic: str, catalog: dict) -> dict:
    if catalog.get("schema") != "WORLD_ENGINE_HISTORY_CATALOG_V1":
        raise PlanningError("UNSUPPORTED_CATALOG")
    normalized = _normalized(topic)
    matches = [entry for entry in catalog.get("entries", [])
               if any(_normalized(alias) in normalized for alias in entry.get("aliases", []) if alias)]
    if len(matches) != 1:
        raise PlanningError("FACT_CATALOG_TOPIC_REQUIRED" if not matches else "AMBIGUOUS_TOPIC")
    entry = matches[0]
    if entry.get("status") not in {"AVAILABLE_SCHEMATIC_ONLY", "AVAILABLE_VERIFIED"}:
        raise PlanningError("SOURCE_UNAVAILABLE")
    if entry.get("status") == "AVAILABLE_SCHEMATIC_ONLY" and BLOCKED_PRECISION.search(topic):
        raise PlanningError("HISTORICAL_PRECISION_NOT_SUPPORTED", "Only supplied illustrative keyframes are available")
    return entry


def _timing(request: dict, facts: dict) -> dict:
    """Generic allocation supported by the unchanged legacy Scene timing contract."""
    fps, frames = request["fps"], request["totalFrames"]
    transitions = len(facts.get("stages", [])) - 1
    if facts.get("subject", {}).get("event_family") != "WAR" or transitions < 1:
        raise PlanningError("LONG_TIMING_FAMILY_NOT_SUPPORTED", "Legacy compiler exists; long timing allocator currently supports state-timeline families only")
    lock = min(2 * fps, frames // 10)
    hold = min(2 * fps, frames // 10)
    initial = min(2 * fps, frames // 10)
    available = frames - lock - hold - initial
    if available < 2 * transitions or initial < 2:
        raise PlanningError("DURATION_TOO_SHORT_FOR_SUPPLIED_STATES")
    # Uniform old transitions require divisibility. Keep exact full duration by
    # assigning at most transitions-1 frames to initial reveal, not dropping EOF.
    initial += available % transitions
    transition = (frames - lock - hold - initial) // transitions
    action = initial + transition * transitions
    return {"fps": fps, "total_frames": frames, "duration_seconds": frames / fps,
            "camera_lock_frame": lock, "event_start_frame": lock,
            "initial_reveal_frames": initial, "state_transition_frames": transition,
            "final_hold_frames": hold, "action_frames": action,
            "frame_policy": "INTEGER_DETERMINISTIC", "blank_interstage_frames": 0}


def _compile_legacy(topic: str, facts: dict, output: dict, *, node: str) -> dict:
    script = "const p=JSON.parse(await new Response(process.stdin).text()); const m=await import(p.module); const v=m.compileScenePlan(p.request); process.stdout.write(JSON.stringify(v));"
    payload = {"module": LEGACY_PLANNER.as_uri(), "request": {"topic": topic, "facts": facts, "output": output}}
    try:
        result = subprocess.run([node, "--input-type=module", "-e", script], input=canonical_json(payload),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PlanningError("LEGACY_PLANNER_UNAVAILABLE", type(exc).__name__) from exc
    if result.returncode:
        raise PlanningError("LEGACY_PLANNER_REJECTED_FACTS", result.stderr.decode("utf-8", "replace")[-2000:])
    try:
        return json.loads(result.stdout)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PlanningError("LEGACY_PLANNER_INVALID_OUTPUT") from exc


def plan_topic(topic: str, *, duration_seconds=None, fps: int = 30, resolution=None,
               aspect_ratio: str | None = None, visual_style: str = "REFERENCE_VISUAL_V2",
               catalog_path=None, max_scene_frames=None, require_renderable: bool = False,
               node: str = "node") -> dict:
    request = parse_request(topic, duration_seconds=duration_seconds, fps=fps, resolution=resolution,
                            aspect_ratio=aspect_ratio, visual_style=visual_style)
    catalog_path = Path(catalog_path or DEFAULT_CATALOG).resolve()
    try:
        catalog = json.loads(catalog_path.read_bytes())
    except (OSError, ValueError) as exc:
        raise PlanningError("FACT_CATALOG_UNAVAILABLE") from exc
    entry = _entry(request["topic"], catalog)
    facts_path = _bound_file(entry["factsPath"], entry["factsSHA256"], "facts")
    provenance_path = _bound_file(entry["provenancePath"], entry["provenanceSHA256"], "provenance")
    refs_path = _bound_file(entry["sourceReferencesPath"], entry["sourceReferencesSHA256"], "sourceReferences")
    facts = json.loads(facts_path.read_bytes())
    if facts.get("subject", {}).get("id") != entry["subjectId"] or facts.get("semantic_mode") != entry["semanticMode"]:
        raise PlanningError("CATALOG_FACT_IDENTITY_MISMATCH")
    facts["scene_timing"] = _timing(request, facts)
    legacy = _compile_legacy(request["topic"], facts, {**request["resolution"], "fps": fps}, node=node)
    source = {"catalogSHA256": _sha(catalog_path), "factsPath": entry["factsPath"], "factsSHA256": entry["factsSHA256"],
              "provenancePath": entry["provenancePath"], "provenanceSHA256": _sha(provenance_path),
              "sourceReferencesPath": entry["sourceReferencesPath"], "sourceReferencesSHA256": _sha(refs_path),
              "legacyPlannerPath": str(LEGACY_PLANNER.relative_to(ENGINE)), "legacyPlannerSHA256": _sha(LEGACY_PLANNER),
              "records": deepcopy(facts["source_notes"]),
              "semanticPolicy": {"mode": entry["semanticMode"], "inventMissingHistory": False,
                                 "permittedVisualizations": entry["permittedVisualizations"],
                                 "historicalInterpolation": "INFOGRAPHIC_VISUAL_TRANSITION_NOT_OBSERVED_DAILY_CONTROL",
                                 "sourceArticleBodiesVerified": False}}
    profile = {"adapter": "UNIVERSAL_AREA_ASTRA_V2", "gpuMode": "gpu-required",
               "qualityProfile": "REFERENCE_VISUAL_MASTER_V2_F", "status": "BLOCKED_RENDERER_BINDING_REQUIRED",
               "rendererCapability": "POLYGON_STATE_TIMELINE",
               "reason": "Full-duration source-bound historical GPU adapter has not yet passed native payload and visual-composition validation",
               "nativePayload": None}
    label = facts["subject"]["label"]
    plan = {"schema": SCHEMA, **request, "subjectId": entry["subjectId"],
            "titleCandidates": [label, f"{label} — 지도에서 보는 변화"],
            "sourceManifest": source, "renderProfile": profile,
            "cameraProfile": {"owner": "EXISTING_CAMERA_DIRECTOR_V5_WITH_DETAIL_ADAPTER", "intent": deepcopy(legacy["camera_intent"]),
                              "continuityPolicy": "GLOBAL_FRAME_NO_SCENE_RESET", "candidateProfile": "REFERENCE_VISUAL_MASTER_V2"},
            "materialProfile": {"profileId": "REFERENCE_VISUAL_MASTER_V2_F", "fallback": "EXISTING_BASE_MATERIAL", "rebuildRenderer": False},
            "audioSettings": {"enabled": False, "mode": "SILENT"},
            "encoder": {"codec": "h264", "pixelFormat": "yuv420p", "fps": fps, "container": "mp4", "audio": False},
            "legacyScenePlan": legacy, "warnings": list(entry.get("warnings", [])),
            "qualityStatus": "USER_VIDEO_REVIEW_REQUIRED", "gpuValidation": "NOT_EXECUTED",
            "performanceTarget": {"seconds": 3600 if request["durationSeconds"] == 80 else None,
                                  "status": "UNMEASURED", "costApproved": False},
            "scenes": []}
    result = split_plan(plan, fps * 10 if max_scene_frames is None else max_scene_frames)
    validate_plan(result, require_renderable=require_renderable)
    return result


def bind_renderer(plan: dict, render_profile: dict) -> dict:
    """Attach a separately validated adapter/payload without rewriting Scene V1."""
    result = deepcopy(plan)
    result["renderProfile"] = deepcopy(render_profile)
    return split_plan(result, result["splitPolicy"]["maxSceneFrames"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic")
    parser.add_argument("--duration-seconds", type=float)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--max-scene-frames", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        plan = plan_topic(args.topic, duration_seconds=args.duration_seconds, fps=args.fps,
                          catalog_path=args.catalog, max_scene_frames=args.max_scene_frames)
        encoded = json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        # Exclusive creation protects every prior plan/job, including failed ones.
        with args.output.open("x", encoding="utf-8") as output:
            output.write(encoded)
    except (ContractError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "code": getattr(exc, "code", "OUTPUT_ERROR"), "message": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "PLANNED", "renderStatus": plan["renderProfile"]["status"], "frames": plan["totalFrames"],
                      "scenes": len(plan["scenes"]), "planSHA256": canonical_sha256(plan), "externalAIConnected": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
