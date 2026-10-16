"""Additive, renderer-neutral long-video contracts. Existing Scene V1 stays unchanged.

All frame coordinates are GLOBAL and half-open. Boundary signatures certify the
supplied timeline contract, not unexecuted GPU pixel/camera continuity.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
import re
from typing import Any

SCHEMA = "WORLD_ENGINE_UNIVERSAL_VIDEO_V2"
ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
REQUIRED_SCENE = ("sceneId", "startFrame", "endFrame", "eventTimeline", "territoryState",
                  "frontierState", "cameraProfile", "materialProfile", "unitMarkers",
                  "audioSettings", "sourceManifest", "renderProfile", "boundaryStart", "boundaryEnd")


class ContractError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError("NON_CANONICAL_JSON", str(exc)) from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _integer(value: Any, code: str, minimum: int = 0, maximum: int = 10_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ContractError(code)
    return value


def total_frames(duration_seconds: Any, fps: Any) -> int:
    _integer(fps, "INVALID_FPS", 1, 120)
    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, (int, float)):
        raise ContractError("INVALID_DURATION")
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ContractError("INVALID_DURATION")
    frames = Fraction(str(duration_seconds)) * fps
    if frames.denominator != 1:
        raise ContractError("DURATION_NOT_INTEGER_FRAMES", "durationSeconds * fps must be exact")
    return _integer(int(frames), "INVALID_TOTAL_FRAMES", 1)


def _profile(profile: Any, require_renderable: bool = False) -> None:
    if not isinstance(profile, dict) or profile.get("gpuMode") != "gpu-required":
        raise ContractError("GPU_REQUIRED_PROFILE_REQUIRED")
    if not isinstance(profile.get("adapter"), str) or not ID.fullmatch(profile["adapter"]):
        raise ContractError("RENDER_ADAPTER_REQUIRED")
    status = profile.get("status")
    if status not in {"READY", "BLOCKED_NATIVE_PAYLOAD_REQUIRED", "BLOCKED_RENDERER_BINDING_REQUIRED"}:
        raise ContractError("INVALID_RENDER_STATUS")
    if status == "READY":
        payload = profile.get("nativePayload")
        if not isinstance(payload, dict) or not payload.get("path") or not SHA.fullmatch(str(payload.get("sha256", ""))) or payload.get("validationStatus") != "VERIFIED":
            raise ContractError("VERIFIED_NATIVE_PAYLOAD_REQUIRED")
    if require_renderable and status != "READY":
        raise ContractError("NATIVE_PAYLOAD_REQUIRED", profile.get("reason", ""))


def _source(source: Any) -> None:
    if not isinstance(source, dict) or not isinstance(source.get("records"), list) or not source["records"]:
        raise ContractError("SOURCE_MANIFEST_REQUIRED")
    for name in ("factsSHA256", "catalogSHA256", "legacyPlannerSHA256"):
        if not SHA.fullmatch(str(source.get(name, ""))):
            raise ContractError("SOURCE_HASH_REQUIRED", name)
    for row in source["records"]:
        if not isinstance(row, dict) or row.get("verification_status") not in {"VERIFIED", "SYNTHETIC_TEST"}:
            raise ContractError("UNVERIFIED_SOURCE")
    policy = source.get("semanticPolicy")
    if not isinstance(policy, dict) or policy.get("inventMissingHistory") is not False:
        raise ContractError("SOURCE_SEMANTIC_POLICY_REQUIRED")


def _legacy(legacy: Any, frames: int, fps: int) -> None:
    if not isinstance(legacy, dict) or legacy.get("metadata", {}).get("schema") != "PLANNER_SCENE_JSON_V1":
        raise ContractError("LEGACY_SCENE_REQUIRED")
    timing = legacy.get("timing", {})
    if timing.get("total_frames") != frames or timing.get("fps") != fps:
        raise ContractError("LEGACY_TIMING_MISMATCH")
    cursor = 0
    for event in legacy.get("beats", []):
        if event.get("start_frame") != cursor or not isinstance(event.get("end_frame"), int) or event["end_frame"] <= cursor:
            raise ContractError("LEGACY_EVENT_COVERAGE_INVALID")
        cursor = event["end_frame"]
    if cursor != frames:
        raise ContractError("LEGACY_EVENT_COVERAGE_INVALID")


def boundary_at(plan: dict, frame: int) -> dict:
    """Semantic sample at an absolute boundary, including virtual EOF.

    The same global frame produces the same descriptors across neighboring scenes.
    Actual renderer must evaluate its original global timeline, never reset at cuts.
    """
    _integer(frame, "BOUNDARY_FRAME_INVALID", 0, plan["totalFrames"])
    legacy = plan["legacyScenePlan"]
    steps = legacy.get("time_steps", [])
    current = None
    previous = None
    for step in steps:
        if step["start_frame"] > frame:
            break
        previous, current = current, step
    if current is None:
        state = {"state": "BEFORE_EVENT", "globalFrame": frame}
    else:
        length = max(1, current["transition_frames"])
        amount = min(length, max(0, frame - current["start_frame"]))
        state = {"fromStateId": (previous or current)["id"], "toStateId": current["id"],
                 "numerator": amount, "denominator": length,
                 "semanticMode": legacy["metadata"].get("semantic_mode")}
    camera = {"globalFrame": frame, "profile": plan["cameraProfile"], "source": "UNCHANGED_EXISTING_CAMERA_OWNER"}
    effect = {"globalFrame": frame, "mode": "GLOBAL_FRAME_NO_SCENE_RESET", "profile": plan["materialProfile"]}
    return {"frame": frame, "territorySignature": canonical_sha256(state),
            "frontierSignature": canonical_sha256(state), "cameraSignature": canonical_sha256(camera),
            "effectSignature": canonical_sha256(effect),
            "timelineSignature": canonical_sha256({"globalFrame": frame, "legacySceneSHA256": canonical_sha256(legacy)}),
            "validationBasis": "SEMANTIC_CONTRACT_ONLY_GPU_CONTINUITY_PENDING"}


def _scene(plan: dict, start: int, end: int, index: int) -> dict:
    legacy = plan["legacyScenePlan"]
    clipped = []
    for beat in legacy["beats"]:
        if beat["start_frame"] < end and beat["end_frame"] > start:
            clipped.append({"eventId": beat["id"], "type": beat["type"],
                            "startFrame": max(start, beat["start_frame"]), "endFrame": min(end, beat["end_frame"]),
                            "sourceStartFrame": beat["start_frame"], "sourceEndFrame": beat["end_frame"],
                            "stateId": beat.get("state_id")})
    state = {"mode": "LEGACY_TIME_STEPS", "legacySceneSHA256": canonical_sha256(legacy),
             "globalStartFrame": start, "globalEndFrame": end, "resetAtSceneStart": False}
    return {"sceneId": f"scene-{index:04d}", "startFrame": start, "endFrame": end,
            "globalFrameOffset": start, "eventTimeline": clipped,
            "territoryState": deepcopy(state), "frontierState": deepcopy(state),
            "cameraProfile": deepcopy(plan["cameraProfile"]), "materialProfile": deepcopy(plan["materialProfile"]),
            "unitMarkers": deepcopy(legacy.get("markers", [])), "audioSettings": deepcopy(plan["audioSettings"]),
            "sourceManifest": {"sha256": canonical_sha256(plan["sourceManifest"])},
            "renderProfile": deepcopy(plan["renderProfile"]),
            "boundaryStart": boundary_at(plan, start), "boundaryEnd": boundary_at(plan, end)}


def split_plan(plan: dict, max_scene_frames: int) -> dict:
    """Split only metadata; memory scales with scenes, never full frame buffers."""
    _integer(max_scene_frames, "INVALID_SCENE_BUDGET", 1)
    result = deepcopy(plan)
    frames = total_frames(result["durationSeconds"], result["fps"])
    if result.get("totalFrames") != frames:
        raise ContractError("TOTAL_FRAME_MISMATCH")
    stops = {0, frames}
    # Respect semantic beats, then cap each interval deterministically.
    for beat in result["legacyScenePlan"]["beats"]:
        stops.update((beat["start_frame"], beat["end_frame"]))
    ordered = sorted(stops)
    scenes = []
    for left, right in zip(ordered, ordered[1:]):
        for start in range(left, right, max_scene_frames):
            scenes.append(_scene(result, start, min(right, start + max_scene_frames), len(scenes)))
    result["scenes"] = scenes
    result["splitPolicy"] = {"maxSceneFrames": max_scene_frames, "halfOpen": True, "globalTimeline": True}
    validate_plan(result)
    return result


def validate_plan(plan: dict, *, require_renderable: bool = False) -> dict:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise ContractError("UNSUPPORTED_PLAN_SCHEMA")
    frames = total_frames(plan.get("durationSeconds"), plan.get("fps"))
    if plan.get("totalFrames") != frames:
        raise ContractError("TOTAL_FRAME_MISMATCH")
    resolution = plan.get("resolution")
    if not isinstance(resolution, dict):
        raise ContractError("RESOLUTION_REQUIRED")
    width = _integer(resolution.get("width"), "INVALID_WIDTH", 2, 8192)
    height = _integer(resolution.get("height"), "INVALID_HEIGHT", 2, 8192)
    if width % 2 or height % 2:
        raise ContractError("H264_EVEN_DIMENSIONS_REQUIRED")
    ratio = plan.get("aspectRatio", "")
    if not isinstance(ratio, str) or not re.fullmatch(r"[1-9]\d{0,3}:[1-9]\d{0,3}", ratio):
        raise ContractError("INVALID_ASPECT_RATIO")
    rw, rh = map(int, ratio.split(":"))
    if width * rh != height * rw:
        raise ContractError("ASPECT_RATIO_MISMATCH")
    _source(plan.get("sourceManifest"))
    _profile(plan.get("renderProfile"), require_renderable)
    _legacy(plan.get("legacyScenePlan"), frames, plan["fps"])
    if plan.get("audioSettings") != {"enabled": False, "mode": "SILENT"}:
        raise ContractError("UNSUPPORTED_AUDIO_CONFIGURATION")
    encoder = plan.get("encoder", {})
    if encoder.get("codec") != "h264" or encoder.get("pixelFormat") != "yuv420p" or encoder.get("fps") != plan["fps"]:
        raise ContractError("ENCODER_CONTRACT_INVALID")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ContractError("SCENES_REQUIRED")
    ids = set()
    cursor = 0
    previous = None
    source_sha = canonical_sha256(plan["sourceManifest"])
    legacy_sha = canonical_sha256(plan["legacyScenePlan"])
    for scene in scenes:
        if not isinstance(scene, dict) or any(name not in scene for name in REQUIRED_SCENE):
            raise ContractError("SCENE_FIELD_REQUIRED")
        if not isinstance(scene["sceneId"], str) or not ID.fullmatch(scene["sceneId"]) or scene["sceneId"] in ids:
            raise ContractError("INVALID_OR_DUPLICATE_SCENE_ID")
        ids.add(scene["sceneId"])
        start = _integer(scene["startFrame"], "INVALID_SCENE_START", 0, frames)
        end = _integer(scene["endFrame"], "INVALID_SCENE_END", 1, frames)
        if start != cursor or end <= start or scene.get("globalFrameOffset") != start:
            raise ContractError("SCENE_GAP_OVERLAP_OR_RESET")
        expected = _scene(plan, start, end, 0)
        for key in REQUIRED_SCENE[3:]:
            if scene[key] != expected[key]:
                raise ContractError("SCENE_BINDING_MISMATCH", key)
        if scene["sourceManifest"] != {"sha256": source_sha}:
            raise ContractError("SCENE_SOURCE_MISMATCH")
        for state in (scene["territoryState"], scene["frontierState"]):
            if state.get("legacySceneSHA256") != legacy_sha or state.get("resetAtSceneStart") is not False:
                raise ContractError("SCENE_STATE_RESET")
        if previous is not None and previous != scene["boundaryStart"]:
            raise ContractError("SCENE_BOUNDARY_DISCONTINUITY")
        previous = scene["boundaryEnd"]
        cursor = end
    if cursor != frames:
        raise ContractError("SCENE_TOTAL_FRAME_MISMATCH")
    return plan
