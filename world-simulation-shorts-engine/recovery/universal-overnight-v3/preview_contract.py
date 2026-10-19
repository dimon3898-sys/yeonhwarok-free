"""Five-second range metadata over an immutable, complete source timeline.

This is source/range validation, never GPU, fact, image, cost or quality admission.
No source scene is cropped, retimed or recompiled. Original global frames are
selected and only encoded output timestamps begin at zero.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat

SCHEMA = "WORLD_ENGINE_PREVIEW_REQUEST_V3"
FRAME_COUNT = 150
FPS = 30
SAMPLE_RATE = 48000
BINDING_KEYS = frozenset({"sourceCommit", "sourceManifestSHA256", "imageDigest",
                          "originalPlanSHA256", "completionProfileSHA256", "sourceCatalogSHA256"})


class PreviewError(ValueError):
    pass


def _fail(code):
    raise PreviewError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def _hex(value, count=64):
    return isinstance(value, str) and len(value) == count and all(c in "0123456789abcdef" for c in value)


def validate_bindings(bindings):
    if not isinstance(bindings, dict) or set(bindings) != BINDING_KEYS:
        _fail("PREVIEW_EXACT_SOURCE_IMAGE_BINDINGS_REQUIRED")
    for key, value in bindings.items():
        if key == "sourceCommit":
            valid = _hex(value, 40)
        elif key == "imageDigest":
            valid = isinstance(value, str) and value.startswith("sha256:") and _hex(value[7:])
        else:
            valid = _hex(value)
        if not valid:
            _fail("PREVIEW_SOURCE_IMAGE_BINDING_INVALID")
    return deepcopy(bindings)


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get("schema") != "WORLD_ENGINE_UNIVERSAL_VIDEO_V2":
        _fail("PREVIEW_ORIGINAL_UNIVERSAL_PLAN_REQUIRED")
    total, fps = plan.get("totalFrames"), plan.get("fps")
    if type(total) is not int or not FRAME_COUNT <= total <= 72000 or type(fps) is not int or fps != FPS:
        _fail("PREVIEW_EXACT_30FPS_SOURCE_REQUIRED")
    duration = plan.get("durationSeconds")
    if type(duration) not in (int, float) or not math.isfinite(duration) or abs(duration * fps - total) > 1e-8:
        _fail("PREVIEW_ORIGINAL_DURATION_MISMATCH")
    if plan.get("resolution") != {"width": 1080, "height": 1920} or plan.get("aspectRatio") != "9:16":
        _fail("PREVIEW_ORIGINAL_RESOLUTION_REQUIRED")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 10000:
        _fail("PREVIEW_BOUNDED_ORIGINAL_SCENES_REQUIRED")
    end, ids = 0, set()
    for scene in scenes:
        if not isinstance(scene, dict):
            _fail("PREVIEW_ORIGINAL_SCENE_INVALID")
        sid, start, stop = scene.get("sceneId"), scene.get("startFrame"), scene.get("endFrame")
        if (not isinstance(sid, str) or not sid or len(sid) > 128 or sid in ids
                or type(start) is not int or type(stop) is not int or start != end or not start < stop <= total):
            _fail("PREVIEW_ORIGINAL_HALF_OPEN_COVERAGE_REQUIRED")
        ids.add(sid)
        end = stop
    if end != total:
        _fail("PREVIEW_ORIGINAL_HALF_OPEN_COVERAGE_REQUIRED")
    # A caller cannot assert a valid full clock with a different legacy clock.
    timing = plan.get("legacyScenePlan", {}).get("timing")
    if not isinstance(timing, dict) or timing.get("total_frames") != total or timing.get("fps") != fps:
        _fail("PREVIEW_ORIGINAL_GLOBAL_CLOCK_REQUIRED")
    return total


def _motion_frames(plan):
    """CPU schedule activity, not observed daily movement or pixel quality."""
    total = plan["totalFrames"]
    schedule = plan.get("productionV3", {}).get("geometrySchedule", [])
    if not isinstance(schedule, list) or len(schedule) > 10000:
        _fail("PREVIEW_BOUND_SOURCE_SCHEDULE_REQUIRED")
    active = bytearray(total)
    for row in schedule:
        if not isinstance(row, dict):
            _fail("PREVIEW_BOUND_SOURCE_SCHEDULE_REQUIRED")
        start, end = row.get("startFrame"), row.get("endFrame")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= total:
            _fail("PREVIEW_BOUND_SOURCE_SCHEDULE_REQUIRED")
        if row.get("mode") in {"TRANSITION_SUPPLIED_SNAPSHOTS", "REVEAL_SUPPLIED_SNAPSHOT"}:
            active[start:end] = b"\1" * (end - start)
    prefix = [0]
    for flag in active:
        prefix.append(prefix[-1] + flag)
    return prefix


def _chapter_frames(plan):
    chapters = plan.get("productionV3", {}).get("eventChapters", [])
    if not isinstance(chapters, list) or len(chapters) > 10000:
        _fail("PREVIEW_SOURCE_CHAPTERS_INVALID")
    result = []
    for row in chapters:
        if not isinstance(row, dict) or type(row.get("startFrame")) is not int or not 0 <= row["startFrame"] < plan["totalFrames"]:
            _fail("PREVIEW_SOURCE_CHAPTERS_INVALID")
        if row["startFrame"]:
            result.append(row["startFrame"])
    return result


def _phase_coherence(plan):
    """Count only source-declared within-chapter transitions as coherent.

    Missing phase metadata remains unknown. No date, state, country or motion
    is invented to improve the score, and the selected source state is not
    changed by this ranking.
    """
    total = plan["totalFrames"]
    chapters = plan.get("productionV3", {}).get("eventChapters", [])
    known = {}
    for chapter in chapters:
        declared = chapter.get("presentationPolicy", {}).get("geometryStateIds", chapter.get("geometryStateIds"))
        if declared is not None and (not isinstance(declared, list)
                or any(not isinstance(state, str) or not state for state in declared)):
            _fail("PREVIEW_DECLARED_PHASE_STATES_INVALID")
        if declared:
            known[chapter.get("chapterId")] = set(declared)
    coherent, outside = bytearray(total), bytearray(total)
    for row in plan.get("productionV3", {}).get("geometrySchedule", []):
        if row.get("mode") != "TRANSITION_SUPPLIED_SNAPSHOTS":
            continue
        states = known.get(row.get("chapterId"))
        endpoints = (row.get("fromStateId"), row.get("toStateId"))
        if states is None or any(not isinstance(value, str) or not value for value in endpoints):
            continue
        destination = coherent if all(value in states for value in endpoints) else outside
        start, end = row["startFrame"], row["endFrame"]
        destination[start:end] = b"\1" * (end - start)
    def prefix(flags):
        result = [0]
        for flag in flags:
            result.append(result[-1] + flag)
        return result
    return prefix(coherent), prefix(outside)


def _camera_activity():
    spec = importlib.util.spec_from_file_location("_overnight_preview_camera_activity", Path(__file__).with_name("camera_activity.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_preview_window(plan, *, camera_evidence=None):
    """Rank existing frame windows; never invent a route, state or camera pose."""
    total = validate_plan(plan)
    prefix, chapters = _motion_frames(plan), _chapter_frames(plan)
    coherent, outside = _phase_coherence(plan)
    camera = _camera_activity()
    measured = camera.measured_candidate_windows(camera_evidence, FRAME_COUNT)
    # A package-owned actual trace limits the claim to fully observed windows.
    # Missing frames are UNKNOWN, never a stationary pose or an interpolation.
    # If joint movement exists, stationary windows cannot outrank it merely by
    # avoiding a context snapshot. This does not alter any original source pose.
    def score(a):
        observed = camera.camera_window_metrics(camera_evidence, a, a + FRAME_COUNT)
        motion = observed["motionPairs"] or 0
        coherent_frames = coherent[a + FRAME_COUNT] - coherent[a]
        actual = (int(motion > 0 and coherent_frames > 0), min(motion, coherent_frames), motion) if measured else ()
        activity = prefix[a + FRAME_COUNT] - prefix[a]
        carry_in = outside[a + FRAME_COUNT] - outside[a]
        # Once actual joint motion is established, retain the fullest authored
        # activity before shaving a context-carry-in frame. Otherwise a tied
        # window can gain an isolated source cut while losing useful movement.
        source = (coherent_frames, activity, -carry_in) if measured else (coherent_frames, -carry_in, activity)
        return (*actual, *source,
                -sum(a < f < a + FRAME_COUNT for f in chapters),
                sum(a <= f < a + FRAME_COUNT for f in chapters), -a)
    # Prefer a transition whose endpoints both belong to its source-declared
    # chapter, avoid context carried in from another phase, then maximize
    # activity while avoiding a cut into the next chapter. Missing phase
    # metadata falls back to existing activity rather than being made up.
    start = max(measured if measured else range(total - FRAME_COUNT + 1), key=score)
    return start


def _scene_slices(plan, start, end):
    return [{"sceneId": row["sceneId"], "startFrame": max(start, row["startFrame"]),
             "endFrame": min(end, row["endFrame"]), "originalSceneSHA256": sha256(canonical(row))}
            for row in plan["scenes"] if row["startFrame"] < end and row["endFrame"] > start]


def compile_preview(plan, *, bindings, start_frame=None, frame_count=FRAME_COUNT, camera_evidence=None):
    """Build an inert, exact range request. Trusted callers supply source hashes.

    Raw source SHA is checked by ``verify_preview_request_file`` at consumption;
    this function's metadata alone is not source/image or operator authority.
    """
    total = validate_plan(plan)
    bindings = validate_bindings(bindings)
    camera = _camera_activity()
    if camera_evidence is not None:
        camera_evidence = camera.validate_camera_evidence(camera_evidence, plan, bindings)
    if type(frame_count) is not int or frame_count != FRAME_COUNT:
        _fail("PREVIEW_ONLY_150_FRAMES_SUPPORTED")
    automatic = start_frame is None
    start = select_preview_window(plan, camera_evidence=camera_evidence) if automatic else start_frame
    if type(start) is not int or not 0 <= start <= total - FRAME_COUNT:
        _fail("PREVIEW_GLOBAL_HALF_OPEN_RANGE_INVALID")
    end = start + FRAME_COUNT
    prefix, chapters = _motion_frames(plan), _chapter_frames(plan)
    coherent, outside = _phase_coherence(plan)
    observed = camera.camera_window_metrics(camera_evidence, start, end)
    measured_available = bool(camera.measured_candidate_windows(camera_evidence, FRAME_COUNT))
    method = ("MEASURED_CAMERA_AND_SOURCE_PHASE_ACTIVITY" if camera_evidence is not None and measured_available
              else "SOURCE_PHASE_COHERENCE_THEN_ACTIVITY")
    result = {"schema": SCHEMA, "bindings": bindings, "planSemanticSHA256": sha256(canonical(plan)),
              "range": {"startFrame": start, "endFrame": end, "fps": FPS, "totalFrames": total,
                        "frameCount": FRAME_COUNT, "frameConvention": "GLOBAL_HALF_OPEN", "localPtsFrameOrigin": 0},
              "output": {"width": 1080, "height": 1920, "fps": FPS, "frameCount": FRAME_COUNT,
                         "codec": "h264", "container": "mp4", "durationSeconds": 5},
              "audioClock": {"sampleRate": SAMPLE_RATE, "startSample": start * 1600,
                             "endSample": end * 1600, "sampleCount": FRAME_COUNT * 1600,
                             "policy": "CLIP_ORIGINAL_GLOBAL_SFX_NO_RESEQUENCING"},
              "sceneSlices": _scene_slices(plan, start, end),
              "selection": {"method": method if automatic else "EXPLICIT_GLOBAL_RANGE",
                            "sourceActivityFrames": prefix[end] - prefix[start],
                            "phaseCoherentTransitionFrames": coherent[end] - coherent[start],
                            "outsideChapterTransitionFrames": outside[end] - outside[start],
                            "internalChapterCuts": sum(start < f < end for f in chapters),
                            "existingChapterFocusStarts": sum(start <= f < end for f in chapters),
                            "explicitSourceEvidence": ({"schema": camera.SCHEMA,
                                "evidenceSHA256": camera_evidence["evidenceSHA256"],
                                "measuredScopeOnly": True, "unknownFramesAreStatic": False}
                                if camera_evidence is not None else None),
                            "cameraActivity": observed,
                            "cameraHardwareVerification": "GPU_PENDING",
                            "evidenceBasis": "CPU_SOURCE_SCHEDULE_NOT_VISUAL_QUALITY",
                            "sourceTimelineReset": False, "geometryInterpolationAdded": False},
              "renderAllowedByRequest": False, "hardwareVerified": False, "visualQualityApproved": False}
    return {**result, "requestSHA256": sha256(canonical(result))}


def validate_preview(request, plan, *, bindings=None, camera_evidence=None):
    if not isinstance(request, dict) or request.get("schema") != SCHEMA:
        _fail("PREVIEW_REQUEST_SCHEMA_INVALID")
    if bindings is not None and request.get("bindings") != validate_bindings(bindings):
        _fail("PREVIEW_TRUSTED_BINDINGS_MISMATCH")
    if camera_evidence is None:
        camera_evidence = _camera_activity().load_bound_camera_evidence(plan, request.get("bindings", {}))
    automatic = request.get("selection", {}).get("method") in {
        "SOURCE_PHASE_COHERENCE_THEN_ACTIVITY", "MEASURED_CAMERA_AND_SOURCE_PHASE_ACTIVITY"}
    supplied_start = request.get("range", {}).get("startFrame")
    expected = compile_preview(plan, bindings=request.get("bindings"),
                               start_frame=None if automatic else supplied_start, camera_evidence=camera_evidence)
    if request != expected:
        _fail("PREVIEW_REQUEST_SOURCE_OR_RANGE_MISMATCH")
    return deepcopy(expected)


def _read_regular(path):
    path = Path(path)
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        _fail("PREVIEW_BOUNDED_REGULAR_SOURCE_REQUIRED")
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    descriptor = None
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > 16 * 1024 * 1024:
            _fail("PREVIEW_BOUNDED_REGULAR_SOURCE_REQUIRED")
        chunks, remaining = [], before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                _fail("PREVIEW_SOURCE_CHANGED_DURING_READ")
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        if (after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns
                or after.st_ctime_ns != before.st_ctime_ns or os.read(descriptor, 1)):
            _fail("PREVIEW_SOURCE_CHANGED_DURING_READ")
        return b"".join(chunks)
    except OSError:
        _fail("PREVIEW_BOUNDED_REGULAR_SOURCE_REQUIRED")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def verify_preview_request_file(request_file, plan_file, *, bindings=None, camera_evidence=None):
    raw = _read_regular(plan_file)
    request = json.loads(_read_regular(request_file))
    if sha256(raw) != request.get("bindings", {}).get("originalPlanSHA256"):
        _fail("PREVIEW_ACTUAL_PLAN_BYTES_MISMATCH")
    plan = json.loads(raw)
    if camera_evidence is None:
        camera_evidence = _camera_activity().load_bound_camera_evidence(plan, request.get("bindings", {}))
    return validate_preview(request, plan, bindings=bindings, camera_evidence=camera_evidence)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-request", required=True)
    parser.add_argument("--plan-file", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_preview_request_file(args.verify_request, args.plan_file), ensure_ascii=False))
    except (PreviewError, ValueError, OSError) as error:
        print(json.dumps({"status": "BLOCKED", "errorCode": str(error) if isinstance(error, PreviewError)
                          else "PREVIEW_SOURCE_UNAVAILABLE", "hardwareVerified": False}))
        raise SystemExit(2)
