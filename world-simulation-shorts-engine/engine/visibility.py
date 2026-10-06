"""Fail-closed, canvas-free semantic visibility certification before rendering.

The certificate forecasts the frozen Three.js renderer's primitive eligibility.
It is not final rendered-frame QC and never replaces that check.
"""
from __future__ import annotations

import hashlib
import json
import copy
from collections import OrderedDict
from pathlib import Path
import subprocess
import sys
import tempfile
import math
import unicodedata
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
TOOL = APP_ROOT / "tools" / "semantic_preflight.mjs"
_CERTIFICATES: OrderedDict[str, dict[str, Any]] = OrderedDict()


def analyze_duplicate_place_labels(plan: dict[str, Any], frames: list[dict[str, Any]],
                                   fps: float = 30.) -> dict[str, Any]:
    """Find distinct, concurrently drawn base/event labels for one place.

    Frozen native audits contain text and post-draw boxes, but not a place ID
    for persistent labels. Resolve that ID only from an unambiguous matching
    spatial Scene label and its live event. Identical names at different places
    cannot be resolved by text alone. Separately identified comparison panels,
    clip scenes, and information/caption labels are outside this check. A
    COMPARISON Scene type alone does not prove that two Earth views were drawn.
    """
    scenes = {scene["scene_id"]: scene for scene in plan.get("scenes", [])}
    findings: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    unresolved: set[tuple[str, str, str]] = set()
    exemptions: set[str] = set()

    def text_key(value: Any) -> str:
        return " ".join(unicodedata.normalize("NFKC", str(value or "")).split()).casefold()

    def place_ids(label: dict[str, Any]) -> set[str]:
        coordinates = label.get("coordinates")
        coordinates = coordinates if isinstance(coordinates, dict) else {}
        return {str(value) for value in [label.get("location_id"), label.get("target_id"),
                                        coordinates.get("location_id")] if value}

    def box(label: dict[str, Any]) -> tuple[float, float, float, float] | None:
        values = [label.get(key) for key in ("x", "y", "width", "height")]
        if (any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values)
                or values[2] <= 0 or values[3] <= 0):
            return None
        return tuple(float(value) for value in values)

    def view(label: dict[str, Any]) -> tuple[Any, Any]:
        return label.get("view_id"), label.get("panel_id")

    for frame_index, frame in enumerate(frames):
        sid = frame.get("scene_id")
        scene = scenes.get(sid)
        if scene is None:
            continue
        if scene.get("scene_type") == "CINEMATIC_CLIP":
            exemptions.add(str(sid))
            continue
        local_time = frame.get("t")
        if not isinstance(local_time, (int, float)) or not math.isfinite(local_time):
            continue
        drawn = [label for label in frame.get("labels", [])
                 if isinstance(label, dict) and label.get("kind") == "world_label"
                 and isinstance(label.get("opacity"), (int, float))
                 and math.isfinite(label["opacity"]) and label["opacity"] > .1
                 and text_key(label.get("text")) and box(label) is not None]
        base = [label for label in drawn if not label.get("event_id")]
        events = {event["id"]: event for event in scene.get("visual_events", [])
                  if isinstance(event, dict) and event.get("id")}
        for event_label in drawn:
            event_id = event_label.get("event_id")
            if not event_id:
                continue
            event = events.get(event_id)
            if not event:
                unresolved.add((str(sid), str(event_id), "UNKNOWN_SCENE_EVENT"))
                continue
            target = event.get("target_id")
            event_places = place_ids(event)
            if not target or event_places != {str(target)}:
                unresolved.add((str(sid), str(event_id), "EVENT_PLACE_TARGET_UNRESOLVED"))
                continue
            drawn_event_places = place_ids(event_label)
            if drawn_event_places and drawn_event_places != {str(target)}:
                continue
            key_text = text_key(event_label["text"])
            specs = [label for label in scene.get("labels", [])
                     if isinstance(label, dict) and not label.get("event_id")
                     and label.get("coordinates") and text_key(label.get("text")) == key_text
                     and float(label.get("start_time", 0)) <= local_time
                     < float(label.get("end_time", scene.get("duration", 0)))]
            spec_places = [place_ids(label) for label in specs]
            if (not specs or any(len(ids) != 1 for ids in spec_places)
                    or len(set.union(*spec_places)) != 1):
                if specs:
                    unresolved.add((str(sid), str(event_id), "BASE_PLACE_TARGET_AMBIGUOUS"))
                continue
            if set.union(*spec_places) != {str(target)}:
                continue
            for base_label in base:
                if text_key(base_label["text"]) != key_text or view(base_label) != view(event_label):
                    continue
                drawn_base_places = place_ids(base_label)
                if drawn_base_places and drawn_base_places != {str(target)}:
                    continue
                base_box, event_box = box(base_label), box(event_label)
                if base_box == event_box:
                    continue  # An identical duplicate audit record is not proof of two placements.
                bx, by, bw, bh = base_box
                ex, ey, ew, eh = event_box
                overlaps = bx < ex+ew and bx+bw > ex and by < ey+eh and by+bh > ey
                key = (str(sid), key_text, str(target), str(event_id))
                absolute = float(scene.get("start_time", 0))+float(local_time)
                if key not in findings:
                    findings[key] = {"code": "DUPLICATE_PLACE_LABEL", "scene_id": sid,
                                     "target_id": target, "text": event_label["text"], "event_id": event_id,
                                     "first_local_time": float(local_time), "last_local_time": float(local_time),
                                     "first_absolute_time": absolute, "last_absolute_time": absolute,
                                     "audited_frames": [], "sample": {"base_box": list(base_box),
                                     "event_box": list(event_box), "base_opacity": base_label["opacity"],
                                     "event_opacity": event_label["opacity"], "boxes_intersect": overlaps}}
                finding = findings[key]
                finding["first_local_time"] = min(finding["first_local_time"], float(local_time))
                finding["last_local_time"] = max(finding["last_local_time"], float(local_time))
                finding["first_absolute_time"] = min(finding["first_absolute_time"], absolute)
                finding["last_absolute_time"] = max(finding["last_absolute_time"], absolute)
                if not finding["audited_frames"] or finding["audited_frames"][-1] != frame_index:
                    finding["audited_frames"].append(frame_index)
    result = list(findings.values())
    for finding in result:
        finding["audited_frame_count"] = len(finding["audited_frames"])
        finding["audited_frame_equivalent_seconds"] = finding["audited_frame_count"]/fps
    return {"passed": not result, "findings": result,
            "unresolved_targets": [{"scene_id": sid, "event_id": eid, "reason": reason}
                                   for sid, eid, reason in sorted(unresolved)],
            "exempted_scene_ids": sorted(exemptions),
            "scope": "Post-draw world-label boxes with opacity > .1; distinct base/event placements for an unambiguous same place ID and text in one Earth view. Disjoint boxes also fail. Separately identified panels/views, clip scenes and information/caption labels are excluded; COMPARISON scene type alone is not exempt. Not OCR or a claim that unresolved targets are duplicate-free."}


def _source_fingerprint(plan: dict[str, Any] | None = None) -> str:
    legacy = APP_ROOT.parent / "cinematic-world-map"
    paths = [TOOL, Path(__file__), APP_ROOT / "web" / "earth_adapter.js", APP_ROOT / "engine" / "retention.py",
             APP_ROOT / "engine" / "assets.py", APP_ROOT / "engine" / "rendering.py",
             legacy / "src" / "renderer_v3.js", legacy / "src" / "aircraft_v3.js",
             legacy / "node_modules" / "three" / "build" / "three.module.js",
             legacy / "assets" / "v3" / "fonts" / "OpenSans-Light.ttf",
             APP_ROOT / "web" / "fonts" / "NotoSansCJKkr-Regular.otf"]
    paths += [APP_ROOT/'web/flat_semantics.js', APP_ROOT/'web/map_transition.js']
    if any(scene.get('production_defaults', {}).get('version') == 'v1' for scene in (plan or {}).get('scenes', [])):
        paths += [APP_ROOT/'web/production_visual_adapter.js', APP_ROOT/'web/flat_polish_renderer.js',
                  APP_ROOT/'web/flat_entity_separation_polish.js', APP_ROOT/'web/earth_polish_adapter.js',
                  APP_ROOT/'web/geographic_polish_transition.js']
    if any(scene.get('rhythm_visual', {}).get('version') == 'v1' for scene in (plan or {}).get('scenes', [])):
        paths += [APP_ROOT/'web/rhythm_visual_adapter.js']
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def semantic_input_hash(plan: dict[str, Any]) -> str:
    """Exclude gate/certificate metadata so recording a report cannot invalidate it."""
    inputs = {key: plan[key] for key in ("scenes", "story", "story_plan", "hook", "render_context")
              if key in plan}
    return hashlib.sha256(json.dumps(inputs, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def certify_semantic_visibility(plan: dict[str, Any], *, scene_ids: list[str] | None = None,
                                timeout_seconds: float = 45) -> dict[str, Any]:
    """Return an explicit failed certificate for tool/runtime/layout errors.

    scene_ids enables scoped revision preflight; it deliberately does not assert
    opening-hook coverage for a fragment. Cinematic clips delegate to their actual
    annotation/source validator, never accept unverified physical map events.
    """
    digest = semantic_input_hash(plan)
    try:
        if not TOOL.is_file():
            raise FileNotFoundError("Semantic visibility tool is missing")
        source_fingerprint = _source_fingerprint(plan)
        # User-provided bytes can change at an identical path. Mixed clip plans
        # always recheck actual scoped media/bytes/license/metadata, without cache.
        contains_clip = any(scene.get("scene_type") == "CINEMATIC_CLIP" for scene in plan.get("scenes", []))
        key = hashlib.sha256(json.dumps([digest, source_fingerprint, sorted(scene_ids or [])],
                                        separators=(",", ":")).encode()).hexdigest()
        if not contains_clip and key in _CERTIFICATES:
            _CERTIFICATES.move_to_end(key)
            cached = copy.deepcopy(_CERTIFICATES[key])
            cached["certificate_cache_hit"] = True
            return cached
        with tempfile.TemporaryDirectory(prefix="wss_visibility_") as directory:
            plan_path = Path(directory) / "scene_plan.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            command = ["node", str(TOOL), "--plan", str(plan_path), "--python", sys.executable]
            if scene_ids:
                command.extend(["--scene", ",".join(scene_ids)])
            result = subprocess.run(command, cwd=APP_ROOT, text=True, capture_output=True,
                                    timeout=timeout_seconds, check=False)
            if result.returncode not in (0, 2):
                raise RuntimeError(f"Certifier exited {result.returncode}: {result.stderr[-1800:]}")
            report = json.loads(result.stdout)
            if (not isinstance(report, dict) or not isinstance(report.get("passed"), bool)
                    or not isinstance(report.get("failures"), list)
                    or result.returncode == 0 and not report["passed"]
                    or result.returncode == 2 and report["passed"]):
                raise ValueError("Invalid semantic certificate contract")
            report.pop("plan_path", None)  # Temporary path is not a deliverable.
            report["semantic_input_sha256"] = digest
            # The meaningful-input hash, not metadata/gate formatting, identifies
            # a reusable certificate. Preserve the initial forensic byte hash.
            report["certified_plan_bytes_sha256"] = report.pop("plan_sha256", None)
            report["certificate_source_fingerprint"] = source_fingerprint
            report["certificate_cache_hit"] = False
            if not contains_clip:
                _CERTIFICATES[key] = copy.deepcopy(report)
            while len(_CERTIFICATES) > 64:
                _CERTIFICATES.popitem(last=False)
            return report
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as error:
        return {"schema_version": 1, "passed": False, "semantic_input_sha256": digest,
                "scoped_scene_ids": scene_ids, "events": [],
                "failures": [{"code": "SEMANTIC_CERTIFICATION_FAILED", "detail": str(error)}],
                "scope": "Pre-render visibility certification failed closed; rendering must not start."}
