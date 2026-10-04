"""Decoded-file checks plus renderer audits; aesthetic approval stays explicit."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import hashlib
import copy
import json
import math
import re
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def probe_video(path: Path) -> dict:
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
                                               "-show_format", "-of", "json", str(path)]))


def valid_scene_file(path: Path, duration: float, width: int, height: int, fps: int = 30) -> bool:
    try:
        meta = probe_video(path)
        video = next(s for s in meta["streams"] if s["codec_type"] == "video")
        return (video["codec_name"] == "h264" and video["width"] == width and video["height"] == height
                and abs(float(Fraction(video["avg_frame_rate"]))-fps) < .001
                and abs(float(meta["format"]["duration"])-duration) < .075)
    except (ValueError, KeyError, StopIteration, subprocess.SubprocessError, OSError):
        return False


def _audit_frames(audits: list) -> list[dict]:
    result = []
    for audit in audits:
        if isinstance(audit, (str, Path)):
            audit = json.loads(Path(audit).read_text())
        if isinstance(audit, dict):
            if "t" in audit and "scene_id" in audit:
                result.append(audit)
                continue
            audit = audit.get("frames", audit.get("audits", []))
        result.extend(audit)
    return result


def _contact_times(plan: dict) -> list[float]:
    times = [0., min(1., plan["duration"]-.04), min(3., plan["duration"]-.04), max(0., plan["duration"]-1)]
    for scene in plan["scenes"]:
        times.append(scene["start_time"]+scene["duration"]*.5)
        for event in scene.get("visual_events", []):
            if isinstance(event, dict) and (event.get("kind") in {"peak_moment", "peak_reveal"}
                                          or event.get("role") in {"PEAK_MOMENT", "peak"}):
                times.append(scene["start_time"]+float(event.get("time", 0)))
    return sorted(set(round(max(0., min(plan["duration"]-.04, t)), 3) for t in times))


def analyze_rendered_retention(plan: dict, audits: list, fps: float = 30.) -> dict:
    """Validate unique event onsets actually drawn, separately from authored pacing.

    These are renderer evidence records, not computer-vision understanding of the
    film. The renderer records visible primitives after its draw passes; an event
    is never accepted merely because its timestamp appeared in Scene JSON.
    """
    from .retention import MEANINGFUL, analyze_retention
    allowed_primitives = {"information", "world_label", "geographic_pulse", "route_head",
                          "3D_entity", "route_barrier", "network", "clip_information"}
    physical_primitives = {"route_start": {"route_head"}, "entity_departure": {"3D_entity"},
                           "route_blocked": {"route_barrier"}, "network_expand": {"network"},
                           "arrival": {"geographic_pulse", "world_label"}}
    fade_allowances = {"information": .25, "world_label": .4, "3D_entity": .24,
                       "route_head": 0., "route_barrier": 0., "network": 0., "clip_information": .09}
    scenes = {scene["scene_id"]: scene for scene in plan["scenes"]}
    all_events = {event["id"]: (scene, event) for scene in plan["scenes"]
                  for event in scene.get("visual_events", []) if isinstance(event, dict)}
    expected = {eid: (scene, event) for eid, (scene, event) in all_events.items()
                if event.get("kind") in MEANINGFUL and event.get("meaningful", True)}
    seen: dict[str, dict] = {}
    errors = []
    hook_visible = False
    timestep = 1/max(fps, 1.)
    for index, audit in enumerate(_audit_frames(audits)):
        sid = audit.get("scene_id")
        scene = scenes.get(sid)
        if scene is None:
            errors.append({"code": "UNKNOWN_RENDERED_SCENE", "frame": index, "scene_id": sid})
            continue
        local = audit.get("t")
        if not isinstance(local, (int, float)) or not math.isfinite(local):
            errors.append({"code": "INVALID_RENDER_AUDIT_TIMESTAMP", "frame": index, "scene_id": sid})
            continue
        absolute = float(scene["start_time"])+float(local)
        if local < -1e-6 or local >= scene["duration"]+timestep:
            errors.append({"code": "RENDER_AUDIT_TIMESTAMP_OUTSIDE_SCENE", "frame": index, "scene_id": sid})
            continue
        if absolute < 3 and any(label.get("kind") == "hook_reveal" and label.get("text")
                                and float(label.get("opacity", 0)) > .1 for label in audit.get("labels", [])):
            hook_visible = True
        for record in audit.get("meaningfulEventsRendered", []):
            eid = record.get("event_id")
            if not eid:  # Untagged hook/decorative primitives never count as events.
                continue
            if eid not in all_events:
                errors.append({"code": "UNPLANNED_DRAWN_EVENT", "frame": index, "event_id": eid})
                continue
            if eid not in expected:
                continue  # Camera/particle/pulse events remain excluded even if drawn.
            owner, event = expected[eid]
            actual_time = record.get("actual_time")
            primitive = record.get("rendered_primitive")
            if (owner["scene_id"] != sid or record.get("kind") != event["kind"]
                    or primitive not in allowed_primitives or record.get("visible") is not True
                    or not isinstance(actual_time, (float, int)) or not math.isfinite(actual_time)
                    or abs(float(actual_time)-float(local)) > timestep+.00001):
                errors.append({"code": "INVALID_DRAWN_EVENT_EVIDENCE", "frame": index, "event_id": eid})
                continue
            if event["kind"] in physical_primitives and primitive not in physical_primitives[event["kind"]]:
                errors.append({"code": "PHYSICAL_EVENT_REQUIRES_PHYSICAL_PRIMITIVE", "frame": index,
                               "event_id": eid, "kind": event["kind"], "primitive": primitive})
                continue
            scheduled = float(event.get("time", 0))
            if local < scheduled-timestep-.00001:
                errors.append({"code": "EVENT_DRAWN_BEFORE_SCHEDULE", "frame": index, "event_id": eid})
                continue
            if primitive in {"information", "clip_information"} and not str(record.get("text", "")).strip():
                errors.append({"code": "EMPTY_INFORMATION_EVENT", "frame": index, "event_id": eid})
                continue
            onset = seen.setdefault(eid, {"event_id": eid, "scene_id": sid, "kind": event["kind"],
                                          "planned_local_time": scheduled, "first_local_time": float(local),
                                          "absolute_time": absolute, "first_primitive": primitive,
                                          "frame_indices": set(), "primitives": set()})
            onset["frame_indices"].add(index)
            onset["primitives"].add(primitive)
            if local < onset["first_local_time"]:
                onset["first_local_time"] = float(local)
                onset["absolute_time"] = absolute
                onset["first_primitive"] = primitive
    for eid, (scene, event) in expected.items():
        if eid not in seen:
            errors.append({"code": "MEANINGFUL_EVENT_NOT_RENDERED", "event_id": eid,
                           "scene_id": scene["scene_id"], "kind": event["kind"], "planned_time": event["time"]})
            continue
        evidence = seen[eid]
        latency = evidence["first_local_time"]-evidence["planned_local_time"]
        primitive = evidence["first_primitive"]
        allowance = (.04*float(event.get("duration", 1.25))
                     if primitive == "geographic_pulse" else fade_allowances[primitive])+timestep
        evidence["allowed_onset_delay_seconds"] = allowance
        if latency > allowance+.00001:
            errors.append({"code": "MEANINGFUL_EVENT_RENDERED_LATE", "event_id": eid,
                           "latency_seconds": round(latency, 4), "allowed_seconds": allowance,
                           "primitive": primitive})
        if len(evidence["frame_indices"])/fps < .10-1e-6:
            errors.append({"code": "MEANINGFUL_EVENT_TOO_BRIEF", "event_id": eid,
                           "visible_seconds": len(evidence["frame_indices"])/fps})
    if not hook_visible:
        errors.append({"code": "OPENING_HOOK_NOT_DRAWN", "message": "No visible hook label in the first three seconds"})
    actual_plan = copy.deepcopy(plan)
    for scene in actual_plan["scenes"]:
        events = []
        for event in scene["visual_events"]:
            if event["id"] in seen:
                event["time"] = seen[event["id"]]["first_local_time"]
                events.append(event)
        scene["visual_events"] = events
    actual_gate = analyze_retention(actual_plan)
    errors.extend({**error, "stage": "actual_drawn_event_onsets"} for error in actual_gate["errors"])
    onsets = [{**{key: value for key, value in record.items() if key not in {"frame_indices", "primitives"}},
               "visible_frames": len(record["frame_indices"]), "visible_seconds": len(record["frame_indices"])/fps,
               "rendered_primitives": sorted(record["primitives"]),
               "onset_latency_seconds": record["first_local_time"]-record["planned_local_time"]}
              for record in sorted(seen.values(), key=lambda record: record["absolute_time"])]
    return {"passed": not errors, "errors": errors, "metrics": actual_gate["metrics"], "events": onsets,
            "planned_meaningful_events": len(expected), "drawn_meaningful_events": len(onsets),
            "opening_hook_drawn": hook_visible, "camera_events_counted": False,
            "onset_delay_policy": {"primitive_fade_allowance_seconds": fade_allowances,
                                   "geographic_pulse": "0.04 × authored pulse duration (default 1.25s) + one frame",
                                   "frame_tolerance_seconds": timestep}, "minimum_visible_seconds": .10,
            "scope": "Unique first-visible onsets from post-draw primitive audits; not every frame, not camera motion, and not audience-retention measurement"}


def _audio_measurement(path: Path) -> dict:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                           "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                          capture_output=True, text=True)
    if proc.returncode:
        return {"error": proc.stderr[-1500:]}
    summary = proc.stderr.rsplit("Summary:", 1)[-1]
    integrated = re.search(r"I:\s+(-?[\d.]+)\s+LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[\d.]+)\s+dBFS", summary)
    return {"integrated_lufs": float(integrated.group(1)) if integrated else None,
            "true_peak_dbfs": float(peak.group(1)) if peak else None,
            "direct_listening": False}


def analyze_subtitle_layout(subtitles: dict | None, audits: list, plan: dict | None = None,
                            *, output_width: int = 1080, output_height: int = 1920) -> dict:
    """Check ASS layout and warn when active captions intersect drawn labels."""
    from .audio import validate_subtitle_layout
    plan = plan or {}
    if plan.get("options", {}).get("subtitles") and not subtitles:
        return {"passed": False, "enabled": True,
                "errors": [{"code": "SUBTITLE_LAYOUT_METADATA_MISSING"}], "warnings": [], "overlaps": []}
    validation = validate_subtitle_layout(subtitles, plan.get("duration"))
    if not validation["enabled"] or not validation["passed"]:
        return {**validation, "warnings": [], "overlaps": []}
    scenes = {scene["scene_id"]: scene for scene in plan.get("scenes", [])}
    layout_width, layout_height = subtitles["layout_resolution"]
    caption_scale = (output_width/layout_width, output_height/layout_height)
    overlaps = {}
    missing_geometry = set()
    for audit in _audit_frames(audits):
        sid = audit.get("scene_id")
        scene_start = float(scenes.get(sid, {}).get("start_time", 0))
        absolute = scene_start+float(audit.get("t", 0))
        active = [caption for caption in subtitles["captions"]
                  if caption["start"] < absolute < caption["end"]
                  and min((absolute-caption["start"])/max(.001, caption.get("fade_in_seconds", .09)),
                          (caption["end"]-absolute)/max(.001, caption.get("fade_out_seconds", .10))) > .1]
        if not active:
            continue
        resolution = audit.get("renderResolution")
        if (not isinstance(resolution, list) or len(resolution) != 2
                or any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 for value in resolution)):
            # Preserved map audits before this metadata used known mode dimensions.
            resolution = [540, 960] if plan.get("options", {}).get("quality", "HIGH") == "FAST" else [2160, 3840]
        label_scale = (output_width/resolution[0], output_height/resolution[1])
        for label in audit.get("labels", []):
            if float(label.get("opacity", 1)) <= .1:
                continue
            values = [label.get(key) for key in ["x", "y", "width", "height"]]
            if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
                missing_geometry.add((str(sid), str(label.get("kind", "label"))))
                continue
            x, y, width, height = values
            lx, ly, lw, lh = x*label_scale[0], y*label_scale[1], width*label_scale[0], height*label_scale[1]
            for caption in active:
                maximum_intersection = 0.
                for box in caption["line_boxes"]:
                    cx, cy = box["x"]*caption_scale[0], box["y"]*caption_scale[1]
                    cw, ch = box["width"]*caption_scale[0], box["height"]*caption_scale[1]
                    intersection = max(0., min(lx+lw, cx+cw)-max(lx, cx))*max(0., min(ly+lh, cy+ch)-max(ly, cy))
                    maximum_intersection = max(maximum_intersection, intersection)
                if maximum_intersection <= 0:
                    continue
                key = (caption["id"], str(sid), str(label.get("text", "")), str(label.get("event_id", "")))
                record = overlaps.setdefault(key, {"caption_id": caption["id"], "scene_id": sid,
                                                    "label_text": label.get("text", ""),
                                                    "label_event_id": label.get("event_id"),
                                                    "first_time": absolute, "last_time": absolute,
                                                    "overlap_frames": 0, "maximum_intersection_pixels": 0.})
                record["first_time"] = min(record["first_time"], absolute)
                record["last_time"] = max(record["last_time"], absolute)
                record["overlap_frames"] += 1
                record["maximum_intersection_pixels"] = max(record["maximum_intersection_pixels"], maximum_intersection)
    warnings = [{"code": "SUBTITLE_MAP_LABEL_OVERLAP", **record} for record in overlaps.values()]
    warnings.extend({"code": "SUBTITLE_LABEL_GEOMETRY_UNAVAILABLE", "scene_id": sid, "label_kind": kind}
                    for sid, kind in sorted(missing_geometry))
    return {**validation, "warnings": warnings, "overlaps": list(overlaps.values()),
            "output_resolution": [output_width, output_height],
            "scope": "Exact-font metric bounds and active-timestamp intersections with post-draw label boxes, scaled to final output; overlap warns, unsafe caption geometry fails; not pixel-level glyph recognition"}


def run_qc(video: Path, plan: dict, audits: list, outdir: Path, subtitles: dict | None = None) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    metadata = probe_video(video)
    stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    width, height = int(stream["width"]), int(stream["height"])
    fps = float(Fraction(stream["avg_frame_rate"]))
    actual_duration = float(metadata["format"]["duration"])
    preview = plan.get("options", {}).get("quality", "HIGH").upper() == "FAST"
    expected_size = (540, 960) if preview else (1080, 1920)
    failures, warnings = [], []
    if (width, height) != expected_size:
        failures.append("RESOLUTION_MISMATCH")
    if stream.get("codec_name") != "h264" or stream.get("pix_fmt") != "yuv420p":
        failures.append("CODEC_MISMATCH")
    if fps < 30 or abs(fps-30) > .01:
        failures.append("FPS_MISMATCH")
    if abs(actual_duration-float(plan["duration"])) > .075:
        failures.append("DURATION_MISMATCH")
    if stream.get("color_range") != "tv" or any(stream.get(key) != "bt709" for key in ["color_space", "color_transfer", "color_primaries"]):
        failures.append("COLOR_METADATA_MISMATCH")
    decoder = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "2",
                                "-i", str(video), "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_size = width*height*3
    count = 0
    black, duplicate = [], []
    previous_hash = None
    previous_coarse = None
    changes: list[float] = []
    frozen_run = longest_frozen = 0
    full_hash = hashlib.sha256()
    targets = {round(t*fps): t for t in _contact_times(plan)}
    captures = []
    mean_exposure = []
    try:
        assert decoder.stdout
        while True:
            data = decoder.stdout.read(frame_size)
            if not data:
                break
            if len(data) != frame_size:
                failures.append("PARTIAL_FRAME_DECODE")
                break
            digest = hashlib.sha256(data).digest()
            full_hash.update(data)
            if digest == previous_hash:
                duplicate.append(count)
            frame = np.frombuffer(data, np.uint8).reshape(height, width, 3)
            image = Image.fromarray(frame)
            # Average blocks suppress dithering/noise concealing a genuine freeze.
            coarse = np.asarray(image.resize((60, 108), Image.Resampling.BOX), np.float32)
            roi = coarse[12:101, 3:57]
            mean_exposure.append(float(roi.mean()))
            if float(frame.mean()) < .5 and float(np.quantile(frame[::8, ::8], .99)) < 3:
                black.append(count)
            if previous_coarse is not None:
                change = float(np.abs(roi-previous_coarse).mean())
                changes.append(change)
                frozen_run = frozen_run+1 if change < .055 else 0
                longest_frozen = max(longest_frozen, frozen_run)
            if count in targets:
                captures.append((targets[count], image.resize((270, 480), Image.Resampling.LANCZOS)))
            previous_hash = digest
            previous_coarse = roi
            count += 1
        _, error = decoder.communicate(timeout=20)
        if decoder.returncode:
            failures.append("VIDEO_DECODE_FAILED")
            warnings.append(error.decode(errors="replace")[-1000:])
    finally:
        if decoder.poll() is None:
            decoder.kill()
            decoder.wait()
    expected_frames = round(plan["duration"]*fps)
    if count != expected_frames:
        failures.append("FRAME_COUNT_MISMATCH")
    if black:
        failures.append("BLACK_FRAME")
    if duplicate:
        failures.append("EXACT_DUPLICATE_FRAME")
    if longest_frozen/fps >= 3:
        failures.append("FROZEN_INTERVAL")
    if changes and max(changes[:max(1, round(fps*.5))]) < .055:
        failures.append("FIRST_HALF_SECOND_STATIONARY")
    rendered = _audit_frames(audits)
    subtitle_layout = analyze_subtitle_layout(subtitles, rendered, plan, output_width=width, output_height=height)
    if not subtitle_layout["passed"]:
        failures.append("SUBTITLE_LAYOUT_FAILED")
    warnings.extend(subtitle_layout.get("warnings", []))
    clipping, gl_errors, missing, broken = [], [], [], []
    camera_angles, camera_steps = [], []
    previous = None
    for index, audit in enumerate(rendered):
        for field in ["textClipped", "entityClipped", "routeDiscontinuities"]:
            if audit.get(field):
                (clipping if field != "routeDiscontinuities" else broken).append({"frame": index, "field": field, "value": audit[field]})
        if audit.get("webglError"):
            gl_errors.append(index)
        if audit.get("fontReady") is False:
            missing.append({"frame": index, "code": "FONT_NOT_READY"})
        if audit.get("missingAssets") or audit.get("missingTextures"):
            missing.append({"frame": index, "assets": audit.get("missingAssets"), "textures": audit.get("missingTextures")})
        if audit.get("sourceTextureSize") is not None and audit["sourceTextureSize"] != [8192, 4096]:
            missing.append({"frame": index, "code": "V3_EARTH_TEXTURE_BASELINE_CHANGED"})
        numeric = []
        for field in ["cameraPosition", "cameraQuaternion", "cameraFov"]:
            value = audit.get(field)
            if isinstance(value, list):
                numeric.extend(value)
            elif value is not None:
                numeric.append(value)
        for entity in audit.get("entities", []):
            numeric.extend(entity.get("position", []))
            numeric.extend(entity.get("quaternion", []))
            if entity.get("visible") and float(entity.get("radius", 1.)) < 1.-1e-6:
                broken.append({"frame": index, "code": "ENTITY_INSIDE_EARTH", "entity": entity.get("id")})
        if any(not isinstance(value, (float, int)) or not math.isfinite(value) for value in numeric):
            broken.append({"frame": index, "code": "NONFINITE_CAMERA_OR_ENTITY_POSE"})
        if audit.get("routeInsideEarth"):
            broken.append({"frame": index, "code": "ROUTE_INSIDE_EARTH"})
        if previous is not None:
            position, old_position = audit.get("cameraPosition"), previous.get("cameraPosition")
            quaternion, old_quaternion = audit.get("cameraQuaternion"), previous.get("cameraQuaternion")
            if position and old_position:
                camera_steps.append(float(np.linalg.norm(np.array(position)-np.array(old_position))))
            if quaternion and old_quaternion:
                dot = min(1., max(-1., abs(float(np.dot(quaternion, old_quaternion)))))
                camera_angles.append(math.degrees(2*math.acos(dot)))
            # Route progress resets only when a new independent route is selected.
            if audit.get("scene_id") == previous.get("scene_id") and audit.get("routeProgress") is not None:
                progress, old_progress = audit["routeProgress"], previous.get("routeProgress")
                if isinstance(progress, list) and isinstance(old_progress, list) and len(progress) == len(old_progress):
                    old_values = {p["id"]: p["progress"] for p in old_progress if isinstance(p, dict)}
                    reversed_progress = any(p["progress"] < old_values.get(p["id"], p["progress"])-1e-6
                                            for p in progress if isinstance(p, dict))
                    if progress and not isinstance(progress[0], dict):
                        reversed_progress = any(p < q-1e-6 for p, q in zip(progress, old_progress))
                    if reversed_progress:
                        broken.append({"frame": index, "code": "ROUTE_PROGRESS_REVERSED"})
        previous = audit
    if rendered and len(rendered) != expected_frames:
        failures.append("RENDER_AUDIT_FRAME_COUNT_MISMATCH")
    if not rendered:
        failures.append("RENDER_AUDIT_MISSING")
    if clipping:
        failures.append("TEXT_OR_ENTITY_CLIPPING")
    if gl_errors:
        failures.append("WEBGL_ERROR")
    if missing:
        failures.append("MISSING_TEXTURE_OR_ASSET")
    if broken:
        failures.append("BROKEN_ROUTE")
    if camera_angles and max(camera_angles) > 6:
        failures.append("CAMERA_ORIENTATION_JUMP")
    if camera_steps and max(camera_steps) > .25:
        failures.append("CAMERA_POSITION_JUMP")
    # Geography brightness is an automatic review candidate, not a claim that
    # image intensity proves coastline correctness. Scene-specific visual review
    # and verified coordinate/route audits remain required.
    readability = []
    for scene in plan["scenes"]:
        first = round(scene["start_time"]*fps)
        last = min(count, round((scene["start_time"]+scene["duration"])*fps))
        exposure = float(np.median(mean_exposure[first:last])) if last > first else 0.
        if scene.get("lighting_preset") in {"GEOGRAPHY_READABILITY", "DAY_DOCUMENTARY"} and exposure < 8:
            readability.append({"scene_id": scene["scene_id"], "median_roi_rgb": exposure,
                                "recommendation": "increase GEOGRAPHY_READABILITY exposure / inspect target coastline"})
    if readability:
        failures.append("GEOGRAPHY_TOO_DARK_REVIEW_REQUIRED")
    audio_streams = [s for s in metadata["streams"] if s["codec_type"] == "audio"]
    if not audio_streams:
        failures.append("AUDIO_MISSING")
    audio = _audio_measurement(video) if audio_streams else {}
    if audio.get("error"):
        failures.append("AUDIO_MEASUREMENT_FAILED")
    if audio.get("true_peak_dbfs") is not None and audio["true_peak_dbfs"] > -1:
        failures.append("AUDIO_PEAK_EXCEEDED")
    if audio.get("integrated_lufs") is None and audio_streams:
        warnings.append("Audio loudness not finite; check intentional silence")
    # Plan-retention validation is independently executed after render as well.
    retention = None
    rendered_retention = None
    try:
        from .retention import analyze_retention
        retention = analyze_retention(plan)
        if not retention.get("passed", retention.get("ok", False)):
            failures.append("FINAL_RETENTION_GATE_FAILED")
        rendered_retention = analyze_rendered_retention(plan, rendered, fps)
        if not rendered_retention["passed"]:
            failures.append("ACTUAL_RENDER_RETENTION_GATE_FAILED")
    except ImportError:
        warnings.append("Retention analyzer import unavailable; final plan gate must be supplied by orchestrator")
    except (ValueError, KeyError, TypeError) as error:
        failures.append("FINAL_RETENTION_VALIDATION_ERROR")
        warnings.append(str(error))
    columns = 4
    rows = max(1, math.ceil(len(captures)/columns))
    sheet = Image.new("RGB", (columns*270, rows*520), "#07101a")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    for index, (time, image) in enumerate(captures):
        x, y = index%columns*270, index//columns*520
        sheet.paste(image, (x, y+30))
        draw.text((x+8, y+6), f"{time:.2f} s / 270px mobile", fill="white", font=font)
    contact = outdir / "contact_sheet.png"
    if contact.exists():
        raise FileExistsError(contact)
    sheet.save(contact)
    report = {"passed": not failures, "publication_quality": not preview, "failures": sorted(set(failures)),
              "warnings": warnings, "file": str(video), "dimensions": [width, height], "fps": fps,
              "duration": actual_duration, "codec": stream["codec_name"], "pixel_format": stream.get("pix_fmt"),
              "color_range": stream.get("color_range"), "color_space": stream.get("color_space"),
              "decoded_frames": count, "all_decoded_rgb_sha256": full_hash.hexdigest(), "black_frames": black,
              "exact_duplicate_frames": duplicate, "maximum_near_frozen_seconds": longest_frozen/fps,
              "first_half_second_coarse_changes": changes[:round(fps*.5)],
              "coarse_change_median": float(np.median(changes)) if changes else 0.,
              "render_audited_frames": len(rendered), "clipping": clipping, "webgl_errors": gl_errors,
              "missing_assets": missing, "broken_routes": broken,
              "maximum_camera_angle_step_degrees": max(camera_angles, default=0.),
              "maximum_camera_position_step_globe_radii": max(camera_steps, default=0.),
              "geography_readability_review": readability, "audio": audio, "retention": retention,
              "rendered_retention": rendered_retention,
              "subtitle_layout": subtitle_layout,
              "contact_sheet": str(contact),
              "review_scope": "Every encoded RGB frame decoded; technical checks complement direct full playback, mobile composition and aesthetic review. No audience-retention prediction or human listening claimed."}
    with (outdir / "qc_report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    text = ["# Automatic QC report", "", f"Status: {'PASS' if report['passed'] else 'FAIL'}",
            f"File: {video.name}; {width}×{height}; {fps:g} fps; {actual_duration:.3f} s; H.264",
            f"Decoded: {count} frames; black: {len(black)}; exact duplicates: {len(duplicate)}; longest coarse freeze: {longest_frozen/fps:.3f} s",
            "", "Failures: " + (", ".join(report["failures"]) or "none"),
            "Warnings: " + (", ".join(map(str, warnings)) or "none"), "", report["review_scope"], "",
            "Aesthetic approval and full playback must be recorded separately; an automatic PASS alone does not mean publication approval.", ""]
    with (outdir / "qc_report.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(text))
    return report
