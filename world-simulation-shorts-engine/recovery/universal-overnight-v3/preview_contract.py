"""Five-second range metadata over an immutable, complete source timeline.

This is source/range validation, never GPU, fact, image, cost or quality admission.
No source scene is cropped, retimed or recompiled. Original global frames are
selected and only encoded output timestamps begin at zero.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
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


def select_preview_window(plan):
    """Rank existing frame windows; never invent a route, state or camera pose."""
    total = validate_plan(plan)
    prefix, chapters = _motion_frames(plan), _chapter_frames(plan)
    # Prefer source-authored geometry activity, then an existing chapter focus,
    # then the earliest equally informative window. No country/coordinate rule.
    start = max(range(total - FRAME_COUNT + 1), key=lambda a: (
        prefix[a + FRAME_COUNT] - prefix[a],
        sum(a <= f < a + FRAME_COUNT for f in chapters), -a))
    return start


def _scene_slices(plan, start, end):
    return [{"sceneId": row["sceneId"], "startFrame": max(start, row["startFrame"]),
             "endFrame": min(end, row["endFrame"]), "originalSceneSHA256": sha256(canonical(row))}
            for row in plan["scenes"] if row["startFrame"] < end and row["endFrame"] > start]


def compile_preview(plan, *, bindings, start_frame=None, frame_count=FRAME_COUNT):
    """Build an inert, exact range request. Trusted callers supply source hashes.

    Raw source SHA is checked by ``verify_preview_request_file`` at consumption;
    this function's metadata alone is not source/image or operator authority.
    """
    total = validate_plan(plan)
    bindings = validate_bindings(bindings)
    if type(frame_count) is not int or frame_count != FRAME_COUNT:
        _fail("PREVIEW_ONLY_150_FRAMES_SUPPORTED")
    automatic = start_frame is None
    start = select_preview_window(plan) if automatic else start_frame
    if type(start) is not int or not 0 <= start <= total - FRAME_COUNT:
        _fail("PREVIEW_GLOBAL_HALF_OPEN_RANGE_INVALID")
    end = start + FRAME_COUNT
    prefix, chapters = _motion_frames(plan), _chapter_frames(plan)
    result = {"schema": SCHEMA, "bindings": bindings, "planSemanticSHA256": sha256(canonical(plan)),
              "range": {"startFrame": start, "endFrame": end, "fps": FPS, "totalFrames": total,
                        "frameCount": FRAME_COUNT, "frameConvention": "GLOBAL_HALF_OPEN", "localPtsFrameOrigin": 0},
              "output": {"width": 1080, "height": 1920, "fps": FPS, "frameCount": FRAME_COUNT,
                         "codec": "h264", "container": "mp4", "durationSeconds": 5},
              "audioClock": {"sampleRate": SAMPLE_RATE, "startSample": start * 1600,
                             "endSample": end * 1600, "sampleCount": FRAME_COUNT * 1600,
                             "policy": "CLIP_ORIGINAL_GLOBAL_SFX_NO_RESEQUENCING"},
              "sceneSlices": _scene_slices(plan, start, end),
              "selection": {"method": "SOURCE_SCHEDULE_ACTIVITY_THEN_CHAPTER_FOCUS" if automatic else "EXPLICIT_GLOBAL_RANGE",
                            "sourceActivityFrames": prefix[end] - prefix[start],
                            "existingChapterFocusStarts": sum(start <= f < end for f in chapters),
                            "evidenceBasis": "CPU_SOURCE_SCHEDULE_NOT_VISUAL_QUALITY",
                            "sourceTimelineReset": False, "geometryInterpolationAdded": False},
              "renderAllowedByRequest": False, "hardwareVerified": False, "visualQualityApproved": False}
    return {**result, "requestSHA256": sha256(canonical(result))}


def validate_preview(request, plan, *, bindings=None):
    if not isinstance(request, dict) or request.get("schema") != SCHEMA:
        _fail("PREVIEW_REQUEST_SCHEMA_INVALID")
    if bindings is not None and request.get("bindings") != validate_bindings(bindings):
        _fail("PREVIEW_TRUSTED_BINDINGS_MISMATCH")
    automatic = request.get("selection", {}).get("method") == "SOURCE_SCHEDULE_ACTIVITY_THEN_CHAPTER_FOCUS"
    supplied_start = request.get("range", {}).get("startFrame")
    expected = compile_preview(plan, bindings=request.get("bindings"),
                               start_frame=None if automatic else supplied_start)
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


def verify_preview_request_file(request_file, plan_file, *, bindings=None):
    raw = _read_regular(plan_file)
    request = json.loads(_read_regular(request_file))
    if sha256(raw) != request.get("bindings", {}).get("originalPlanSHA256"):
        _fail("PREVIEW_ACTUAL_PLAN_BYTES_MISMATCH")
    return validate_preview(request, json.loads(raw), bindings=bindings)


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
