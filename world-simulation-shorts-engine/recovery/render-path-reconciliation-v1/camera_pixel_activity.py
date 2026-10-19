"""Measure observed camera bounds in output pixels; never author camera poses.

This is a separate reconciliation/report owner. It does not change the original
V5 camera, preview selector, Scene, renderer, or source-coordinate authority.
Bounds are W,S,E,N in geographic degrees. A W>E box explicitly crosses the date
line. A stable 3x3 world lattice in the first observed box is mapped through each
subsequent observed box, with optional *explicitly observed* rotationDegrees.

The pixel classification is an evidence threshold, not a visual-quality PASS.
It assumes the source's rectangular equirectangular screen mapping; another
projection must supply a separately validated projection-specific measurement.
"""
from __future__ import annotations

from math import cos, hypot, isfinite, radians, sin

SCHEMA = "WORLD_ENGINE_OBSERVED_CAMERA_PIXEL_ACTIVITY_V1"
MAX_OBSERVATIONS = 24000


class CameraActivityError(ValueError):
    """Input does not establish a contiguous, finite source observation trace."""


def _fail(code):
    raise CameraActivityError(code)


def _finite(value):
    return type(value) in (int, float) and isfinite(value)


def _settings(width, height, min_visible_pixels):
    if (type(width) is not int or type(height) is not int
            or not 1 <= width <= 16384 or not 1 <= height <= 16384):
        _fail("CAMERA_PIXEL_RESOLUTION_INVALID")
    if not _finite(min_visible_pixels) or not 0 < min_visible_pixels <= hypot(width, height):
        _fail("CAMERA_PIXEL_VISIBILITY_THRESHOLD_INVALID")


def _observations(rows, *, contiguous):
    if not isinstance(rows, (list, tuple)) or not 2 <= len(rows) <= MAX_OBSERVATIONS:
        _fail("CAMERA_PIXEL_ACTUAL_OBSERVATIONS_REQUIRED")
    result, previous_frame, previous_center = [], None, None
    explicit_rotation = None
    for row in rows:
        if not isinstance(row, dict):
            _fail("CAMERA_PIXEL_OBSERVATION_INVALID")
        frames = [row[key] for key in ("frame", "globalFrame") if key in row]
        if (not frames or any(type(frame) is not int or frame < 0 for frame in frames)
                or any(frame != frames[0] for frame in frames)):
            _fail("CAMERA_PIXEL_GLOBAL_FRAME_REQUIRED")
        frame = frames[0]
        if previous_frame is not None and frame <= previous_frame:
            _fail("CAMERA_PIXEL_DUPLICATE_OR_UNORDERED_FRAME")
        if contiguous and previous_frame is not None and frame != previous_frame + 1:
            _fail("CAMERA_PIXEL_NONCONTIGUOUS_GLOBAL_CLOCK")
        boxes = [row[key] for key in ("bounds", "cameraBounds") if key in row]
        if (not boxes or any(box != boxes[0] for box in boxes)
                or not isinstance(boxes[0], (list, tuple)) or len(boxes[0]) != 4
                or not all(_finite(value) for value in boxes[0])):
            _fail("CAMERA_PIXEL_ACTUAL_BOUNDS_REQUIRED")
        west, south, east, north = boxes[0]
        if not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south < north <= 90):
            _fail("CAMERA_PIXEL_GEOGRAPHIC_BOUNDS_INVALID")
        span = east - west
        crosses = span < 0
        if crosses:
            span += 360
        if not 1e-9 < span <= 360 or north - south <= 1e-9:
            _fail("CAMERA_PIXEL_DEGENERATE_BOUNDS")
        center = west + span / 2
        shift = 0 if previous_center is None else 360 * round((previous_center - center) / 360)
        unwrapped = (west + shift, south, west + span + shift, north)
        has_rotation = "rotationDegrees" in row
        if explicit_rotation is None:
            explicit_rotation = has_rotation
        if has_rotation != explicit_rotation:
            _fail("CAMERA_PIXEL_PARTIAL_ROTATION_TRACE")
        angle = row.get("rotationDegrees", 0)
        if not _finite(angle) or abs(angle) > 36000:
            _fail("CAMERA_PIXEL_ROTATION_INVALID")
        result.append({"frame": frame, "bounds": unwrapped, "inputBounds": tuple(boxes[0]),
                       "rotationDegrees": angle, "dateLineUnwrapped": crosses or bool(shift)})
        previous_frame, previous_center = frame, center + shift
    return result, explicit_rotation


def _project(point, bounds, width, height, rotation):
    west, south, east, north = bounds
    x = (point[0] - west) * width / (east - west)
    y = (north - point[1]) * height / (north - south)
    if rotation:
        angle, dx, dy = radians(rotation), x - width / 2, y - height / 2
        x = width / 2 + dx * cos(angle) - dy * sin(angle)
        y = height / 2 + dx * sin(angle) + dy * cos(angle)
    return x, y


def assess_camera_activity(rows, width=1080, height=1920, min_visible_pixels=1.0):
    """Classify a fully observed contiguous source window without interpolation.

    `rows` must contain frame/globalFrame plus bounds/cameraBounds. Optional
    rotationDegrees is used only if observed for every row. Missing rotation is
    UNKNOWN, never inferred as a proved zero-roll camera. No timestamps, motion
    pixels, or historical states are generated. Path length is reported but
    cannot upgrade subpixel jitter to pixel-scale activity.
    """
    _settings(width, height, min_visible_pixels)
    observations, rotation_observed = _observations(rows, contiguous=True)
    first = observations[0]["bounds"]
    lattice = [(first[0] + (first[2] - first[0]) * x,
                first[1] + (first[3] - first[1]) * y)
               for x in (0, .5, 1) for y in (0, .5, 1)]
    projected = [[_project(point, row["bounds"], width, height, row["rotationDegrees"])
                  for point in lattice] for row in observations]
    initial = projected[0]
    maxima, steps, paths = [], [], [0.0] * len(lattice)
    for index, points in enumerate(projected):
        maxima.append(max(hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(points, initial)))
        if index:
            distances = [hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(points, projected[index - 1])]
            paths = [a + b for a, b in zip(paths, distances)]
            steps.append(max(distances))
    numeric_pairs = sum(a["bounds"] != b["bounds"] or a["rotationDegrees"] != b["rotationDegrees"]
                        for a, b in zip(observations, observations[1:]))
    maximum, maximum_step = max(maxima), max(steps, default=0.0)
    visible = maximum >= min_visible_pixels
    status = ("OBSERVED_PIXEL_SCALE_MOVEMENT" if visible else
              "NUMERIC_SUBPIXEL_ONLY" if numeric_pairs else "OBSERVED_STATIC")
    jump_threshold = hypot(width, height) * .25
    jumps = [observations[index + 1]["frame"] for index, value in enumerate(steps) if value > jump_threshold]
    scales = [(first[2] - first[0]) / (row["bounds"][2] - row["bounds"][0]) for row in observations]
    y_scales = [(first[3] - first[1]) / (row["bounds"][3] - row["bounds"][1]) for row in observations]
    rotations = [row["rotationDegrees"] for row in observations]
    return {"schema": SCHEMA, "status": status, "observedFrames": len(observations),
            "startFrame": observations[0]["frame"], "endFrame": observations[-1]["frame"] + 1,
            "frameConvention": "GLOBAL_HALF_OPEN", "resolution": [width, height],
            "minVisiblePixels": min_visible_pixels, "numericMotionPairs": numeric_pairs,
            "boundsVariants": len({row["bounds"] for row in observations}),
            "stableWorldLatticePointCount": len(lattice),
            "maxDisplacementFromFirstPixels": maximum,
            "endDisplacementFromFirstPixels": maxima[-1],
            "maxInterframeDisplacementPixels": maximum_step,
            "maximumLatticePathLengthPixels": max(paths),
            "zoomScaleXRange": [min(scales), max(scales)],
            "zoomScaleYRange": [min(y_scales), max(y_scales)],
            "rotationObserved": rotation_observed,
            "rotationDegreesRange": [min(rotations), max(rotations)] if rotation_observed else None,
            "rotationNotInferableFromBounds": not rotation_observed,
            "dateLineUnwrappingApplied": any(row["dateLineUnwrapped"] for row in observations),
            "projectionMeasurement": "RECTANGULAR_EQUIRECTANGULAR_STABLE_WORLD_LATTICE",
            "largeInterframeJumpThresholdPixels": jump_threshold,
            "possibleHardCutFrames": jumps,
            "continuityAssessment": "POSSIBLE_HARD_CUT_NOT_INTERPOLATED" if jumps else "NO_LARGE_JUMP_OBSERVED",
            "meaningfulPixelScaleActivity": visible, "mobilePerceivedMotionVerified": False,
            "visualQualityPass": False, "cameraPosesCreated": 0, "sourceTimelineChanged": False,
            "gpuRenderingVerified": False}


def select_visible_camera_window(rows, frame_count=150, width=1080, height=1920, min_visible_pixels=1.0):
    """Select only fully observed contiguous windows; gaps stay unobserved.

    A large jump cannot win a continuous-motion ranking. Numeric-only windows
    return an explicit no-candidate result; no unseen window or pose is invented.
    This optional helper is not wired into an old selector or production camera.
    """
    _settings(width, height, min_visible_pixels)
    if type(frame_count) is not int or not 2 <= frame_count <= MAX_OBSERVATIONS:
        _fail("CAMERA_PIXEL_WINDOW_LENGTH_INVALID")
    observed, rotation_observed = _observations(rows, contiguous=False)
    candidates, rejected_subpixel, rejected_jumps, fully_observed = [], 0, 0, 0
    for index in range(len(observed) - frame_count + 1):
        window = observed[index:index + frame_count]
        if window[-1]["frame"] - window[0]["frame"] != frame_count - 1:
            continue
        fully_observed += 1
        actual = [{"frame": row["frame"], "bounds": row["inputBounds"],
                   **({"rotationDegrees": row["rotationDegrees"]} if rotation_observed else {})} for row in window]
        measured = assess_camera_activity(actual, width, height, min_visible_pixels)
        if not measured["meaningfulPixelScaleActivity"]:
            rejected_subpixel += 1
        elif measured["possibleHardCutFrames"]:
            rejected_jumps += 1
        else:
            candidates.append(measured)
    best = max(candidates, key=lambda value: (value["maxDisplacementFromFirstPixels"], -value["startFrame"])) if candidates else None
    return {"schema": "WORLD_ENGINE_OBSERVED_VISIBLE_CAMERA_WINDOW_V1",
            "status": "OBSERVED_VISIBLE_CAMERA_WINDOW" if best else "NO_OBSERVED_VISIBLE_CAMERA_WINDOW",
            "frameCount": frame_count, "fullyObservedCandidateWindows": fully_observed,
            "rejectedSubpixelWindows": rejected_subpixel, "rejectedLargeJumpWindows": rejected_jumps,
            "selectedRange": [best["startFrame"], best["endFrame"]] if best else None,
            "selectedActivity": best, "unknownWindowsRenderedOrAssumed": False,
            "cameraPosesCreated": 0, "sourceTimelineChanged": False,
            "productionSelectorChanged": False, "visualQualityPass": False}
