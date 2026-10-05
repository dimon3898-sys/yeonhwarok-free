"""Original, licensed event sound variants for Production Default v1.

No recordings, reference audio, API, or random selection at playback time. Named
variants are synthesized deterministically, then kept in an immutable local WAV
library. A project's chronological selection history accompanies every mix.
Generated sounds and composition: Cinematic World Map project, CC0-1.0.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import tempfile

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000
LIBRARY_VERSION = "production-sfx-v1"
CATEGORIES = (
    "CAMERA_MOVE", "FAST_ZOOM", "COUNTRY_REVEAL", "CITY_REVEAL", "ENTITY_SPAWN",
    "AIRCRAFT_PASS", "SHIP_PASS", "ROUTE_START", "ROUTE_PROGRESS", "ROUTE_BLOCK",
    "REROUTE", "RADAR", "WARNING", "IMPACT", "SHOCKWAVE", "NETWORK_EXPAND",
    "NEW_VARIABLE", "MID_PEAK", "FINAL_PEAK", "FINAL_REVEAL", "TRANSITION",
)
INTENSITIES = ("LOW", "MEDIUM", "HIGH", "PEAK")
INTENSITY_GAIN = {"LOW": .048, "MEDIUM": .090, "HIGH": .145, "PEAK": .235}
RECENT_SECONDS = 4.0

# Family, default length, tonal center, low-pass/noise ceiling. Restrained
# harmonics and sub/low-mid texture leave the speech band available for TTS.
_PROFILES = {
    "CAMERA_MOVE": ("sweep", .52, 62., 620.),
    "FAST_ZOOM": ("sweep", .42, 74., 1050.),
    "COUNTRY_REVEAL": ("pulse", .46, 226., 960.),
    "CITY_REVEAL": ("pulse", .40, 276., 1080.),
    "ENTITY_SPAWN": ("pulse", .34, 191., 820.),
    "AIRCRAFT_PASS": ("pass", .74, 110., 1450.),
    "SHIP_PASS": ("pass", .86, 66., 580.),
    "ROUTE_START": ("sweep", .54, 158., 1280.),
    "ROUTE_PROGRESS": ("sweep", .36, 172., 1020.),
    "ROUTE_BLOCK": ("impact", .68, 84., 1060.),
    "REROUTE": ("sweep", .60, 142., 1330.),
    "RADAR": ("pulse", .52, 331., 940.),
    "WARNING": ("impact", .56, 104., 970.),
    "IMPACT": ("impact", .74, 82., 1240.),
    "SHOCKWAVE": ("impact", .96, 52., 720.),
    "NETWORK_EXPAND": ("sweep", .88, 109., 1240.),
    "NEW_VARIABLE": ("sweep", .70, 126., 980.),
    "MID_PEAK": ("impact", 1.04, 68., 1180.),
    "FINAL_PEAK": ("impact", 1.22, 53., 1320.),
    "FINAL_REVEAL": ("impact", 1.16, 58., 1180.),
    "TRANSITION": ("sweep", .58, 91., 990.),
}
_EVENT_CATEGORY = {
    "country_reveal": "COUNTRY_REVEAL", "area_highlight": "COUNTRY_REVEAL",
    "region_reveal": "COUNTRY_REVEAL", "city_reveal": "CITY_REVEAL",
    "destination_preview": "CITY_REVEAL", "arrival": "CITY_REVEAL",
    "entity_spawn": "ENTITY_SPAWN", "entity_departure": "AIRCRAFT_PASS",
    "route_start": "ROUTE_START", "milestone_reveal": "ROUTE_PROGRESS",
    "distance_reveal": "ROUTE_PROGRESS", "route_blocked": "ROUTE_BLOCK",
    "route_block": "ROUTE_BLOCK", "alternate_route_reveal": "REROUTE",
    "route_choice": "REROUTE", "route_reroute": "REROUTE",
    "radar": "RADAR", "radar_scan": "RADAR", "warning": "WARNING",
    "impact": "IMPACT", "shockwave": "SHOCKWAVE", "network_expand": "NETWORK_EXPAND",
    "new_variable": "NEW_VARIABLE", "escalation": "NEW_VARIABLE",
    "peak_reveal": "MID_PEAK", "final_reveal": "FINAL_REVEAL",
    "camera_move": "CAMERA_MOVE", "camera_push": "CAMERA_MOVE", "camera_pull": "CAMERA_MOVE",
    "zoom": "FAST_ZOOM", "transition": "TRANSITION",
    "response": "REROUTE", "connection_reveal": "NETWORK_EXPAND",
    "comparison_reveal": "COUNTRY_REVEAL", "consequence_reveal": "CITY_REVEAL",
}


def production_audio_enabled(plan: dict) -> bool:
    return plan.get("production_defaults", {}).get("version") == "v1"


def catalog() -> dict:
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    variants = []
    for category in CATEGORIES:
        family, duration, frequency, ceiling = _PROFILES[category]
        for index in range(1, 4):
            name = f"{category}_{index:02d}"
            variants.append({
                "id": name, "category": category, "family": family,
                "duration": round(duration * (1 + (index-2)*.085), 6),
                "frequency": frequency * (1 + (index-2)*.115),
                "noise_ceiling": ceiling * (1 + (index-2)*.07), "variant_index": index,
                "source": "Repository original engine/sfx_library.py; no sampled audio",
                "source_url": "Repository://engine/sfx_library.py", "author": "Cinematic World Map project",
                "license": "CC0-1.0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "attribution": "Not required", "attribution_required": False,
                "source_sha256": source_sha, "download_date": "Not downloaded; original procedural synthesis",
                "sample_rate": SR, "channels": 2,
            })
    return {"version": LIBRARY_VERSION, "source_sha256": source_sha, "variants": variants,
            "categories": list(CATEGORIES), "intensities": list(INTENSITIES),
            "scope": "Stylized map cues, not authentic aircraft/ship recordings or physical acoustic simulation"}


def _category(sound: dict, visual: dict | None, scene: dict) -> str:
    explicit = sound.get("sfx_category")
    if explicit:
        if explicit not in CATEGORIES:
            raise ValueError("UNSUPPORTED_SFX_CATEGORY: " + str(explicit))
        return explicit
    if visual:
        if visual.get("kind") == "final_reveal" or visual.get("role") == "payoff":
            return "FINAL_REVEAL"
        if visual.get("role") == "peak":
            return "FINAL_PEAK" if visual.get("time", 0) + scene.get("start_time", 0) > .8*scene.get("project_duration", float("inf")) else "MID_PEAK"
        result = _EVENT_CATEGORY.get(visual.get("kind"), "CITY_REVEAL")
        if visual.get("kind") == "entity_departure":
            entity = next((e for e in scene.get("entities", []) if e.get("id") == visual.get("target_id")), {})
            if entity.get("type") in {"ship", "cargo_ship"}:
                result = "SHIP_PASS"
            elif entity.get("type") not in {None, "aircraft"}:
                result = "ENTITY_SPAWN"
        return result
    kind = str(sound.get("kind", "soft_pulse")).lower()
    if "final" in kind or "deep" in kind:
        return "FINAL_REVEAL"
    if "warning" in kind:
        return "WARNING"
    if "hit" in kind or "impact" in kind:
        return "IMPACT"
    if "pass" in kind or "engine" in kind:
        return "AIRCRAFT_PASS"
    if "transition" in kind:
        return "TRANSITION"
    if "sweep" in kind or "riser" in kind:
        return "ROUTE_START"
    if "whoosh" in kind:
        return "CAMERA_MOVE"
    return "CITY_REVEAL"


def _intensity(sound: dict, visual: dict | None, scene: dict, category: str) -> str:
    explicit = sound.get("sfx_intensity")
    if explicit:
        if explicit not in INTENSITIES:
            raise ValueError("INVALID_SFX_INTENSITY: " + str(explicit))
        return explicit
    if category in {"CAMERA_MOVE", "CITY_REVEAL", "COUNTRY_REVEAL", "RADAR", "ROUTE_PROGRESS"}:
        return "LOW"
    if category in {"FINAL_PEAK", "FINAL_REVEAL"}:
        return "PEAK"
    if category in {"MID_PEAK", "ROUTE_BLOCK", "WARNING", "IMPACT", "SHOCKWAVE", "NEW_VARIABLE"}:
        return "HIGH"
    return scene.get("sfx_intensity", "MEDIUM")


def select_sound_events(plan: dict, history: list[dict] | None = None) -> dict:
    """Bind frame-aligned sounds and select named variants chronologically.

    History is project-local, never mutated, and is persisted in sfx_history.json.
    Selection is deterministic for a plan. Explicit user variants take priority
    and are reported if they deliberately override the anti-repeat preference.
    """
    fps = float(plan.get("render", {}).get("fps", 30))
    duration = float(plan["duration"])
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError("SFX_FPS_INVALID")
    selected, warnings = [], []
    carried = deepcopy(history or [])
    candidates = []
    for scene in plan.get("scenes", []):
        visuals = {e.get("id"): e for e in scene.get("visual_events", []) if isinstance(e, dict)}
        sounds = scene.get("sound_events", [])
        # Production plans can omit hand-authored sounds: bind their actual
        # meaningful events, rather than camera movement masquerading as events.
        if not sounds:
            from .retention import MEANINGFUL
            sounds = [{"id": "A_"+e["id"], "kind": e["kind"], "time": e["time"],
                       "visual_event_id": e["id"]} for e in visuals.values()
                      if e.get("kind") in MEANINGFUL and e.get("meaningful", True)]
        for ordinal, original in enumerate(sounds):
            sound = {"kind": original, "time": 0.} if isinstance(original, str) else dict(original)
            visual = visuals.get(sound.get("visual_event_id"))
            if sound.get("visual_event_id") and visual is None:
                raise ValueError("SFX_VISUAL_EVENT_MISSING: " + str(sound["visual_event_id"]))
            local_time = float(visual["time"] if visual else sound.get("time", sound.get("timestamp", 0.)))
            absolute = float(scene["start_time"]) + local_time
            # Scene IR uses six-decimal timestamps. A 68th-frame value such as
            # 2.266667 must remain frame 68 rather than jumping to frame 69 due
            # to sub-microsecond decimal representation error.
            frame = math.ceil(absolute * fps - 1e-4)
            time = frame/fps
            if not np.isfinite(time) or time < 0 or time >= duration:
                raise ValueError("SFX_EVENT_OUTSIDE_PROJECT")
            if not 0 <= local_time < float(scene["duration"]) or time >= float(scene["start_time"])+float(scene["duration"])+1e-6:
                raise ValueError("SFX_EVENT_OUTSIDE_SCENE")
            scoped = {**scene, "project_duration": duration}
            category = _category(sound, visual, scoped)
            intensity = _intensity(sound, visual, scene, category)
            if intensity not in INTENSITIES:
                raise ValueError("INVALID_SFX_INTENSITY: " + str(intensity))
            candidates.append({**sound, "id": sound.get("id", f"A_{scene['scene_id']}_{ordinal:02d}"),
                               "scene_id": scene["scene_id"], "time": time-float(scene["start_time"]),
                               "absolute_time": time, "visual_time": absolute, "frame": frame,
                               "visual_kind": visual.get("kind") if visual else None,
                               "sync_error_seconds": time-absolute, "sfx_category": category,
                               "sfx_intensity": intensity, "semantic_binding": bool(visual),
                               "explicit_variant": bool(sound.get("sfx_variant"))})
    candidates.sort(key=lambda e: (e["absolute_time"], e["scene_id"], e["id"]))
    for event in candidates:
        category = event["sfx_category"]
        names = [f"{category}_{i:02d}" for i in range(1, 4)]
        requested = event.get("sfx_variant")
        if requested and requested not in names:
            raise ValueError("SFX_VARIANT_CATEGORY_MISMATCH: " + str(requested))
        recent = {h.get("sfx_variant") for h in carried if 0 <= event["absolute_time"]-float(h.get("absolute_time", -1e9)) <= RECENT_SECONDS}
        previous = carried[-1].get("sfx_variant") if carried else None
        seed = int(hashlib.sha256((event["scene_id"]+":"+event["id"]+":"+category).encode()).hexdigest()[:8], 16)
        rotated = names[seed % 3:] + names[:seed % 3]
        available = [v for v in rotated if v not in recent and v != previous]
        if not available:
            # Limited category palette: never immediately repeat; choose the
            # least recently used valid variant if all were used inside 4s.
            last_used = {v: max((float(h.get("absolute_time", -1e9)) for h in carried if h.get("sfx_variant") == v), default=-1e9) for v in names}
            available = sorted((v for v in rotated if v != previous), key=lambda v: last_used[v])
        variant = requested or available[0]
        if variant in recent:
            warnings.append({"code": "SFX_RECENT_VARIANT_REUSE", "event_id": event["id"],
                             "explicit_user_override": bool(requested), "variant": variant})
        if variant == previous:
            warnings.append({"code": "SFX_CONSECUTIVE_EXPLICIT_REPEAT", "event_id": event["id"], "variant": variant})
        event["sfx_variant"] = variant
        event["linear_gain"] = INTENSITY_GAIN[event["sfx_intensity"]]
        if "gain" in event:
            event["linear_gain"] *= float(event["gain"])/.12
        # Legacy gain_db is replaced by the documented intensity mix law for
        # production. It remains intact in the legacy audio branch.
        selected.append(event)
        carried.append({"id": event["id"], "scene_id": event["scene_id"], "absolute_time": event["absolute_time"],
                        "sfx_category": category, "sfx_variant": variant, "sfx_intensity": event["sfx_intensity"]})
    return {"events": selected, "history": carried, "warnings": warnings, "fps": fps,
            "recent_seconds": RECENT_SECONDS, "method": "Deterministic category-compatible variants with project-local chronological history; explicit user choices have priority",
            "max_sync_error_seconds": max((e["sync_error_seconds"] for e in selected), default=0.)}


def prepare_production_sound_events(plan: dict, history: list[dict] | None = None) -> dict:
    result = deepcopy(plan)
    if not production_audio_enabled(result):
        return result
    selection = select_sound_events(result, history)
    permitted = {"id", "kind", "type", "time", "timestamp", "duration", "visual_event_id", "gain", "gain_db",
                 "sfx_category", "sfx_variant", "sfx_intensity"}
    for scene in result.get("scenes", []):
        scene["sound_events"] = [{k: v for k, v in e.items() if k in permitted}
                                 for e in selection["events"] if e["scene_id"] == scene["scene_id"]]
        for event in scene["sound_events"]:
            event.setdefault("visual_event_id", None)
            event.setdefault("duration", _PROFILES[event["sfx_category"]][1])
            event["duration"] = min(event["duration"], float(scene["duration"])-event["time"])
    return result


def synthesize_variant(variant: dict) -> np.ndarray:
    """Return peak-normalized stereo float32 at a reproducible 48 kHz."""
    length = round(float(variant["duration"])*SR)
    t = np.arange(length, dtype=np.float64)/SR
    duration, frequency = length/SR, float(variant["frequency"])
    index = int(variant["variant_index"])
    rng = np.random.default_rng(int(hashlib.sha256(variant["id"].encode()).hexdigest()[:16], 16))
    noise = sosfilt(butter(3, [44., float(variant["noise_ceiling"])], btype="bandpass", fs=SR, output="sos"), rng.normal(size=length))
    onset = 1-np.exp(-t/(.006+.001*index))
    ending = np.clip((duration-t)/.09, 0, 1)
    family = variant["family"]
    if family == "impact":
        phase = 2*np.pi*(frequency*.50*t+frequency*.055*(1-np.exp(-t/.09)))
        mono = (np.sin(phase)*np.exp(-t/(duration*.30))+.22*noise*np.exp(-t/.095))*onset*ending
    elif family == "pulse":
        phase = 2*np.pi*(frequency*.66*t+frequency*.033*(1-np.exp(-t/.12)))
        mono = (.75*np.sin(phase)+.15*np.sin(phase*1.5)+.06*noise)*np.exp(-t/(duration*.22))*onset*ending
    else:
        envelope = np.sin(np.pi*t/duration)**(1.65 if family == "pass" else 1.25)
        phase = 2*np.pi*(frequency*t+frequency*.035*duration/np.pi*np.sin(np.pi*t/duration))
        mono = (noise+.09*np.sin(phase))*envelope*onset*ending
    if family == "pass":
        pan = np.linspace(-.37, .37, length)
        stereo = np.column_stack((mono*np.sqrt((1-pan)/2), mono*np.sqrt((1+pan)/2)))
    else:
        # Short stereo reflection, zero padded, never wrapped before its onset.
        reflection = np.zeros_like(mono)
        delay = round((.016+.006*index)*SR)
        reflection[delay:] = mono[:-delay]*.10
        stereo = np.column_stack((mono*.71+reflection*.30, mono*.69+reflection))
    peak = float(np.max(np.abs(stereo)))
    return (stereo/max(peak, 1e-12)).astype(np.float32)


def materialize_variant(variant_id: str, library_root: Path) -> tuple[np.ndarray, dict]:
    details = catalog()
    variant = next((row for row in details["variants"] if row["id"] == variant_id), None)
    if variant is None:
        raise ValueError("SFX_VARIANT_MISSING: " + variant_id)
    # Source-content addressed directories preserve older generated libraries.
    root = library_root / details["source_sha256"][:16]
    root.mkdir(parents=True, exist_ok=True)
    path = root / (variant_id+".wav")
    signal = synthesize_variant(variant)
    if not path.exists():
        with tempfile.NamedTemporaryFile(prefix=variant_id+"-", suffix=".wav", dir=root, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            wavfile.write(temporary, SR, signal)
            # Exclusive hard-link publication cannot replace an existing file.
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
    rate, existing = wavfile.read(path)
    if rate != SR or existing.shape != signal.shape or not np.array_equal(existing, signal):
        raise RuntimeError("SFX_LIBRARY_ASSET_CHANGED: " + str(path))
    meta = {**variant, "file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size, "generated_date": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "duration": len(signal)/SR, "library_version": LIBRARY_VERSION}
    sidecar = path.with_suffix(".json")
    try:
        with sidecar.open("x", encoding="utf-8") as stream:
            json.dump(meta, stream, ensure_ascii=False, indent=2)
    except FileExistsError:
        recorded = json.loads(sidecar.read_text())
        if recorded.get("sha256") != meta["sha256"] or recorded.get("source_sha256") != details["source_sha256"]:
            raise RuntimeError("SFX_LIBRARY_METADATA_CHANGED: " + str(sidecar))
    return signal.astype(np.float64), meta


def render_sound_events(plan: dict, library_root: Path) -> tuple[np.ndarray, dict]:
    selection = select_sound_events(plan)
    audio = np.zeros((round(float(plan["duration"])*SR), 2), np.float64)
    sources = {}
    enabled = bool(plan.get("options", {}).get("sfx", True))
    for event in selection["events"]:
        event["enabled"] = enabled
        event["onset_sample"] = round(event["absolute_time"]*SR)
        if not enabled:
            continue
        signal, source = materialize_variant(event["sfx_variant"], library_root)
        sources[source["id"]] = source
        offset = event["onset_sample"]
        n = min(len(signal), len(audio)-offset)
        if event.get("duration") is not None:
            n = min(n, max(1, round(float(event["duration"])*SR)))
        clip = signal[:n].copy()
        # A clipped short cue ends smoothly; onset remains on the event frame.
        fade = min(round(.025*SR), n)
        if fade:
            clip[-fade:] *= np.linspace(1., 0., fade)[:, None]
        audio[offset:offset+n] += clip*event["linear_gain"]
        event["rendered_duration"] = n/SR
        event["file_sha256"] = source["sha256"]
        event["file"] = source["file"]
    return audio, {**selection, "enabled": enabled, "sources": list(sources.values()),
                   "library_version": LIBRARY_VERSION, "catalog": catalog(),
                   "license": "CC0-1.0", "direct_listening": False}
