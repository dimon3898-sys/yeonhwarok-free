"""Opt-in captions for premium maps, positioned from post-render screen geometry.

The original ASS and its report remain immutable. Legacy Earth plans and subtitle
OFF return the original report without reading or writing anything. Placement is
stable for each timed caption; it never chases an object on every frame. This is
font-metric and supplied-audit validation, not OCR or a claim of human legibility.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from .audio import (SUBTITLE_FONT_SIZE, SUBTITLE_OUTLINE, SUBTITLE_SPACING, SUBTITLE_SAFE_BOUNDS, _ass_time,
                    _subtitle_font, _subtitle_line_width, _wrap_subtitle_text,
                    validate_subtitle_layout)

STYLE_VERSION = "PREMIUM_MAP_1"
PAD_X, PAD_Y, PROTECTED_MARGIN = 8., 4., 16.


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _frames(audits: list) -> list[dict]:
    result = []
    for audit in audits:
        if isinstance(audit, (str, Path)):
            audit = json.loads(Path(audit).read_text(encoding="utf-8"))
        if isinstance(audit, dict):
            if "t" in audit and "scene_id" in audit:
                result.append(audit)
                continue
            audit = audit.get("frames", audit.get("audits", []))
        if not isinstance(audit, list) or any(not isinstance(frame, dict) for frame in audit):
            raise RuntimeError("PREMIUM_SUBTITLE_AUDIT_INVALID")
        result.extend(audit)
    return result


def _box(record: dict, sx: float, sy: float) -> dict | None:
    values = [record.get(key) for key in ("x", "y", "width", "height")]
    if not all(_finite(value) for value in values) or values[2] <= 0 or values[3] <= 0:
        return None
    x, y, width, height = values
    return {"x": x*sx-PROTECTED_MARGIN, "y": y*sy-PROTECTED_MARGIN,
            "width": width*sx+2*PROTECTED_MARGIN, "height": height*sy+2*PROTECTED_MARGIN}


def _protected(frame: dict) -> tuple[list[dict], list[str]]:
    resolution = frame.get("renderResolution")
    if (not isinstance(resolution, list) or len(resolution) != 2
            or not all(_finite(value) and value > 0 for value in resolution)):
        return [], ["AUDIT_RESOLUTION_UNAVAILABLE"]
    sx, sy = 1080/resolution[0], 1920/resolution[1]
    records, warnings = [], []
    for label in frame.get("labels", []):
        if not isinstance(label, dict) or float(label.get("opacity", 1)) <= .1:
            continue
        records.append((label, "label:"+str(label.get("text", ""))))
    for entity in frame.get("entities", []):
        if (not isinstance(entity, dict) or entity.get("visible") is False
                or entity.get("screenVisible") is False or entity.get("occluded")
                or entity.get("context_culled")):
            continue
        geometry = entity.get("bbox", entity.get("screenBox", entity))
        if not isinstance(geometry, dict):
            geometry = {}
        if not all(key in geometry for key in ("width", "height")):
            radius = entity.get("screenRadius")
            if _finite(radius) and radius > 0 and _finite(entity.get("x")) and _finite(entity.get("y")):
                geometry = {"x": entity["x"]-radius, "y": entity["y"]-radius,
                            "width": radius*2, "height": radius*2}
        records.append((geometry, "entity:"+str(entity.get("id", ""))))
    # Both optional focus spellings refer to measured screen geometry, never GIS
    # coordinates or a planned camera target mistaken for an actual screen box.
    for key in ("focusTargetBox", "focus_box"):
        if isinstance(frame.get(key), dict):
            records.append((frame[key], "focus"))
    if frame.get("focusTarget") and not any(isinstance(frame.get(key), dict) for key in ("focusTargetBox", "focus_box")):
        warnings.append("PROTECTED_GEOMETRY_UNAVAILABLE:focus")
    for focus in frame.get("focusTargets", []):
        if isinstance(focus, dict) and focus.get("visible") is not False:
            records.append((focus.get("bbox", focus), "focus:"+str(focus.get("id", ""))))
    protected = []
    for geometry, kind in records:
        box = _box(geometry, sx, sy) if isinstance(geometry, dict) else None
        if box is None:
            warnings.append("PROTECTED_GEOMETRY_UNAVAILABLE:"+kind)
        else:
            protected.append({**box, "kind": kind})
    return protected, warnings


def _intersection(a: dict, b: dict) -> float:
    return (max(0., min(a["x"]+a["width"], b["x"]+b["width"])-max(a["x"], b["x"]))
            * max(0., min(a["y"]+a["height"], b["y"]+b["height"])-max(a["y"], b["y"])))


def _layout(lines: list[str], font, center_x: float, bottom: float) -> dict:
    ascent, descent = font.getmetrics()
    line_height = float(ascent+descent)
    widths = [_subtitle_line_width(line, font) for line in lines]
    height = line_height*len(lines)+2*SUBTITLE_OUTLINE
    top = bottom-height
    box = {"x": center_x-max(widths)/2, "y": top, "width": max(widths), "height": height}
    # libass normalizes its requested font height to the face ascent+descent.
    # Keep the larger legacy font boxes for conservative QC/collision checks,
    # while fitting the plate to that normalized line height rather than adding
    # a conspicuous empty band above the smaller rendered glyphs.
    ink_scale = SUBTITLE_FONT_SIZE/line_height
    ink_widths = [max(float(font.getlength(line)), float(font.getbbox(line)[2]-font.getbbox(line)[0]))*ink_scale
                  + max(0, len(line)-1)*SUBTITLE_SPACING+2*SUBTITLE_OUTLINE for line in lines]
    plate_height = SUBTITLE_FONT_SIZE*len(lines)+2*PAD_Y
    plate_width = max(ink_widths)+2*PAD_X
    return {"line_widths_px": widths,
            "line_boxes": [{"x": center_x-width/2, "y": top+line_height*i,
                            "width": width, "height": line_height+2*SUBTITLE_OUTLINE}
                           for i, width in enumerate(widths)],
            "box": box, "plate_box": {"x": center_x-plate_width/2, "y": bottom+PAD_Y-plate_height,
                                      "width": plate_width, "height": plate_height},
            "plate_metric_scale": ink_scale,
            "anchor": {"x": center_x, "bottom": bottom}}


def _choose(lines: list[str], font, frames: list[dict]) -> tuple[dict, dict]:
    width = max(_subtitle_line_width(line, font) for line in lines)
    left, right = SUBTITLE_SAFE_BOUNDS["left"]+PAD_X+width/2, SUBTITLE_SAFE_BOUNDS["right"]-PAD_X-width/2
    center = (SUBTITLE_SAFE_BOUNDS["left"]+SUBTITLE_SAFE_BOUNDS["right"])/2
    candidates = []
    # Prefer below-map captions. Upper alternatives are used only when actual
    # geography, entities, or labels occupy the lower candidates during the cue.
    for bottom in (1580., 1435., 1290., 435., 580., 725.):
        for x in dict.fromkeys((center, left, right)):
            layout = _layout(lines, font, x, bottom)
            plate = layout["plate_box"]
            if (plate["y"] < SUBTITLE_SAFE_BOUNDS["top"]
                    or plate["y"]+plate["height"] > SUBTITLE_SAFE_BOUNDS["bottom"]):
                continue
            text_box = layout["box"]
            protected_caption = {"x": min(plate["x"], text_box["x"]), "y": min(plate["y"], text_box["y"]),
                                 "width": max(plate["x"]+plate["width"], text_box["x"]+text_box["width"])-min(plate["x"], text_box["x"]),
                                 "height": max(plate["y"]+plate["height"], text_box["y"]+text_box["height"])-min(plate["y"], text_box["y"])}
            collisions = [sum(_intersection(protected_caption, box) for box in frame["protected"]) for frame in frames]
            overlaps = sum(value > 0 for value in collisions)
            candidates.append(((overlaps, sum(collisions), len(candidates)), layout))
    if not candidates:
        raise RuntimeError("PREMIUM_SUBTITLE_NO_SAFE_GEOMETRY")
    score, layout = min(candidates, key=lambda item: item[0])
    return layout, {"audited_frames": len(frames), "overlap_frames": score[0],
                    "total_intersection_px": score[1], "candidate_count": len(candidates),
                    "protected_boxes": sum(len(frame["protected"]) for frame in frames)}


def validate_premium_subtitle_layout(report: dict, duration: float | None = None) -> dict:
    result = validate_subtitle_layout(report, duration)
    errors = list(result["errors"])
    for caption in report.get("captions", []):
        plate = caption.get("plate_box", {})
        values = [plate.get(key) for key in ("x", "y", "width", "height")]
        if not all(_finite(value) for value in values):
            errors.append({"code": "PREMIUM_SUBTITLE_PLATE_INVALID", "caption_id": caption.get("id")})
            continue
        x, y, width, height = values
        if (x < SUBTITLE_SAFE_BOUNDS["left"]-.001 or y < SUBTITLE_SAFE_BOUNDS["top"]-.001
                or x+width > SUBTITLE_SAFE_BOUNDS["right"]+.001
                or y+height > SUBTITLE_SAFE_BOUNDS["bottom"]+.001 or width <= 0 or height <= 0):
            errors.append({"code": "PREMIUM_SUBTITLE_PLATE_OUTSIDE_SAFE_AREA", "caption_id": caption.get("id")})
    return {**result, "passed": not errors, "errors": errors}


def _ass(report: dict) -> str:
    lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 2", "",
             "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             "Style: MapText,Noto Sans CJK KR,44,&H00F5F7FA,&H000000FF,&H00071019,&HFF071019,0,0,0,0,100,100,0.4,0,1,2,0,2,125,160,335,1",
             "Style: MapPlate,Noto Sans CJK KR,44,&H63071019,&H63071019,&HFF071019,&HFF071019,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1", "",
             "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for caption in report["captions"]:
        start, end = _ass_time(caption["start"]), _ass_time(caption["end"])
        plate, anchor = caption["plate_box"], caption["anchor"]
        width, height, radius = plate["width"], plate["height"], 6.
        # Small rounded vector plate for this caption only, not a full-width bar.
        path = (f"m {radius:.2f} 0 l {width-radius:.2f} 0 b {width:.2f} 0 {width:.2f} 0 {width:.2f} {radius:.2f} "
                f"l {width:.2f} {height-radius:.2f} b {width:.2f} {height:.2f} {width:.2f} {height:.2f} {width-radius:.2f} {height:.2f} "
                f"l {radius:.2f} {height:.2f} b 0 {height:.2f} 0 {height:.2f} 0 {height-radius:.2f} "
                f"l 0 {radius:.2f} b 0 0 0 0 {radius:.2f} 0")
        lines.append(f"Dialogue: 0,{start},{end},MapPlate,,0,0,0,,{{\\an7\\pos({plate['x']:.3f},{plate['y']:.3f})\\p1\\fad(90,100)}}{path}")
        text = r"\N".join(caption["lines"])
        lines.append(f"Dialogue: 1,{start},{end},MapText,,0,0,0,,{{\\an2\\pos({anchor['x']:.3f},{anchor['bottom']-SUBTITLE_OUTLINE:.3f})\\fad(90,100)}}{text}")
    return "\n".join(lines)+"\n"


def adapt_flat_subtitles(plan: dict, subtitles: dict, audits: list, directory: Path) -> dict:
    """After Scene rendering, return a separate ASS/report or an exact legacy no-op.

    ``audits`` accepts native audit paths, frame arrays, or frame dictionaries.
    Call before ``finish_video`` and pass the returned report to both assembly and
    QC. An identical interrupted attempt reuses the verified new files; mismatch
    fails rather than replacing existing output.
    """
    if (not plan.get("options", {}).get("subtitles", False)
            or not any(scene.get("render_mode") == "FLAT_MAP_PREMIUM" for scene in plan.get("scenes", []))):
        return subtitles
    validation = validate_subtitle_layout(subtitles, float(plan["duration"]))
    if not validation["enabled"] or not validation["passed"]:
        raise RuntimeError("PREMIUM_SUBTITLE_SOURCE_INVALID: " + json.dumps(validation["errors"]))
    source_path = Path(subtitles["path"])
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    native = _frames(audits)
    input_hash = _digest({"style": STYLE_VERSION, "plan_hash": plan.get("plan_hash", _digest(plan)),
                          "source_ass_sha256": source_sha, "source_report": subtitles, "audits": native})
    directory = Path(directory)
    destination, report_path = directory/"subtitles_map_safe.ass", directory/"subtitle_report_map_safe.json"
    if report_path.exists():
        saved = json.loads(report_path.read_text(encoding="utf-8"))
        if (saved.get("adaptation_input_hash") != input_hash or not destination.is_file()
                or hashlib.sha256(destination.read_bytes()).hexdigest() != saved.get("ass_sha256")
                or not validate_premium_subtitle_layout(saved, float(plan["duration"]))["passed"]):
            raise RuntimeError("PREMIUM_SUBTITLE_CACHE_MISMATCH: existing files are preserved")
        return saved
    scene_starts = {scene["scene_id"]: float(scene["start_time"]) for scene in plan.get("scenes", [])}
    frames, geometry_warnings = [], set()
    for frame in native:
        if frame.get("scene_id") not in scene_starts:
            raise RuntimeError("PREMIUM_SUBTITLE_AUDIT_SCENE_UNKNOWN")
        if not _finite(frame.get("t")):
            raise RuntimeError("PREMIUM_SUBTITLE_AUDIT_TIME_INVALID")
        protected, missing = _protected(frame)
        geometry_warnings.update((str(frame.get("scene_id")), warning) for warning in missing)
        frames.append({"time": scene_starts.get(frame.get("scene_id"), 0)+float(frame["t"]),
                       "protected": protected})
    font, _ = _subtitle_font()
    maximum_width = SUBTITLE_SAFE_BOUNDS["right"]-SUBTITLE_SAFE_BOUNDS["left"]-2*PAD_X
    report = copy.deepcopy(subtitles)
    report.update({"subtitle_style": "PREMIUM_MAP", "style_version": STYLE_VERSION,
                   "captions": [], "path": str(destination), "adaptation_input_hash": input_hash,
                   "source_ass": str(source_path), "source_ass_sha256": source_sha,
                   "native_audit_frames": len(native), "audit_payload_sha256": _digest(native),
                   "plate_metric_scope": "Bundled-face ascent/descent normalization for libass; original larger font bounds remain conservative QC and collision bounds",
                   "placement_scope": "Stable per-caption placement against every provided post-render label/entity/focus screen box; not pixel OCR or human mobile review"})
    warnings = list(report.get("warnings", []))
    warnings.extend({"code": "PREMIUM_SUBTITLE_GEOMETRY_UNAVAILABLE", "scene_id": sid, "detail": warning}
                    for sid, warning in sorted(geometry_warnings))
    for original in subtitles["captions"]:
        text = str(original["text"]).replace("{", "").replace("}", "").replace("\\", "/")
        wrapped = _wrap_subtitle_text(text, font, maximum_width)
        chunks = [wrapped[i:i+2] for i in range(0, len(wrapped), 2)]
        interval = (original["end"]-original["start"])/max(1, len(chunks))
        for index, chunk in enumerate(chunks):
            start, end = round((original["start"]+index*interval)*100)/100, round((original["start"]+(index+1)*interval)*100)/100
            active = [frame for frame in frames if start <= frame["time"] < end]
            layout, placement = _choose(chunk, font, active)
            caption = {**original, **layout, "id": f"C{len(report['captions'])+1:04}",
                       "source_caption_id": original["id"], "start": start, "end": end,
                       "lines": chunk, "text": "\n".join(chunk), "placement": placement}
            report["captions"].append(caption)
            if not active:
                warnings.append({"code": "PREMIUM_SUBTITLE_NATIVE_FRAMES_UNAVAILABLE", "caption_id": caption["id"]})
            if placement["overlap_frames"]:
                warnings.append({"code": "PREMIUM_SUBTITLE_NO_CLEAR_PLACEMENT", "caption_id": caption["id"], **placement})
            if len(chunks) > 1 and interval < .8:
                warnings.append({"code": "SUBTITLE_READING_TIME_SHORT", "caption_id": caption["id"]})
    report["warnings"] = warnings
    report["map_avoidance_verified"] = not any(warning["code"].startswith("PREMIUM_SUBTITLE_") for warning in warnings)
    report["layout_validation"] = validate_premium_subtitle_layout(report, float(plan["duration"]))
    if not report["layout_validation"]["passed"]:
        raise RuntimeError("PREMIUM_SUBTITLE_LAYOUT_INVALID: " + json.dumps(report["layout_validation"]["errors"]))
    content = _ass(report)
    report["ass_sha256"] = hashlib.sha256(content.encode()).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != report["ass_sha256"]:
            raise FileExistsError("PREMIUM_SUBTITLE_EXISTING_ASS: existing file is preserved")
        # A crash between the two exclusive writes can recover the absent report
        # after proving this exact ASS already exists, without replacing its bytes.
    else:
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(content)
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return report
