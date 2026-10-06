"""Reference-informed rhythm policy; original, immutable CC0 sound library v2.

This module is opt-in and never changes the v1 catalog or legacy mix law. Scene
JSON keeps authored visual timestamps; actual layers are bound first and only
then shifted to the renderer's first positive event frame. Reference recordings
are not synthesis inputs. Audio metrics are measurements, not listening claims.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import inspect
import json
import math
import os
import tempfile

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000
LIBRARY_VERSION = "production-sfx-v2"
CATEGORIES = (
    "CAMERA_SOFT_MOVE", "CAMERA_FAST_MOVE", "ZOOM_IN", "ZOOM_OUT",
    "COUNTRY_REVEAL", "REGION_REVEAL", "CITY_REVEAL", "ENTITY_SPAWN", "ENTITY_MOVE",
    "AIRCRAFT_PASS", "SHIP_PASS", "ROUTE_START", "ROUTE_PROGRESS", "ROUTE_COMPLETE",
    "ROUTE_BLOCK", "ROUTE_REROUTE", "RADAR", "SCAN", "WARNING", "ALERT",
    "IMPACT_LIGHT", "IMPACT_MEDIUM", "IMPACT_HEAVY", "SHOCKWAVE", "NETWORK_EXPAND",
    "NEW_VARIABLE", "COUNTER_RESPONSE", "TRANSITION_LIGHT", "TRANSITION_FAST",
    "TRANSITION_HEAVY", "MID_PEAK", "FINAL_PEAK", "FINAL_REVEAL",
)
INTENSITIES = ("SUBTLE", "LOW", "MEDIUM", "HIGH", "PEAK")
INTENSITY_GAIN = {"SUBTLE": .025, "LOW": .050, "MEDIUM": .090, "HIGH": .150, "PEAK": .235}
RECENT_SECONDS = 4.0
# Family, duration, pitch, noise ceiling. Front-loaded attacks separate an
# informational cue from the slower swells used in the preserved v1 library.
_PROFILES = {
    "CAMERA_SOFT_MOVE": ("sweep", .23, 92., 1300.),
    "CAMERA_FAST_MOVE": ("sweep", .27, 134., 2300.),
    "ZOOM_IN": ("sweep", .30, 166., 2450.),
    "ZOOM_OUT": ("sweep", .28, 106., 1900.),
    "COUNTRY_REVEAL": ("pulse", .25, 286., 1450.),
    "REGION_REVEAL": ("pulse", .32, 208., 1180.),
    "CITY_REVEAL": ("tick", .18, 438., 1900.),
    "ENTITY_SPAWN": ("pulse", .21, 326., 1420.),
    "ENTITY_MOVE": ("sweep", .24, 184., 1580.),
    "AIRCRAFT_PASS": ("pass", .46, 138., 2600.),
    "SHIP_PASS": ("pass", .62, 68., 690.),
    "ROUTE_START": ("sweep", .28, 210., 2120.),
    "ROUTE_PROGRESS": ("tick", .14, 526., 1600.),
    "ROUTE_COMPLETE": ("pulse", .23, 392., 1550.),
    "ROUTE_BLOCK": ("impact", .39, 112., 2100.),
    "ROUTE_REROUTE": ("sweep", .33, 232., 1900.),
    "RADAR": ("radar", .31, 712., 1560.),
    "SCAN": ("sweep", .39, 310., 2280.),
    "WARNING": ("warning", .29, 420., 1620.),
    "ALERT": ("warning", .26, 588., 2000.),
    "IMPACT_LIGHT": ("impact", .22, 204., 1950.),
    "IMPACT_MEDIUM": ("impact", .38, 124., 2150.),
    "IMPACT_HEAVY": ("impact", .58, 69., 2360.),
    "SHOCKWAVE": ("impact", .67, 48., 1280.),
    "NETWORK_EXPAND": ("sweep", .46, 242., 2480.),
    "NEW_VARIABLE": ("pulse", .32, 352., 1720.),
    "COUNTER_RESPONSE": ("pulse", .24, 256., 1740.),
    "TRANSITION_LIGHT": ("sweep", .18, 158., 1740.),
    "TRANSITION_FAST": ("sweep", .23, 226., 2640.),
    "TRANSITION_HEAVY": ("impact", .36, 84., 1800.),
    "MID_PEAK": ("impact", .60, 76., 2350.),
    "FINAL_PEAK": ("impact", .79, 52., 2700.),
    "FINAL_REVEAL": ("impact", .73, 61., 2520.),
}
_ALIASES = {"CAMERA_MOVE": "CAMERA_SOFT_MOVE", "FAST_ZOOM": "ZOOM_IN",
            "REROUTE": "ROUTE_REROUTE", "IMPACT": "IMPACT_MEDIUM", "TRANSITION": "TRANSITION_LIGHT"}
_EVENT_CATEGORY = {
    "country_reveal": "COUNTRY_REVEAL", "area_highlight": "COUNTRY_REVEAL",
    "region_reveal": "REGION_REVEAL", "city_reveal": "CITY_REVEAL",
    "destination_preview": "CITY_REVEAL", "arrival": "ROUTE_COMPLETE",
    "entity_spawn": "ENTITY_SPAWN", "entity_move": "ENTITY_MOVE", "entity_departure": "AIRCRAFT_PASS",
    "route_start": "ROUTE_START", "route_progress": "ROUTE_PROGRESS", "route_complete": "ROUTE_COMPLETE",
    "distance_reveal": "ROUTE_PROGRESS", "milestone_reveal": "ROUTE_PROGRESS",
    "route_blocked": "ROUTE_BLOCK", "route_block": "ROUTE_BLOCK",
    "alternate_route_reveal": "ROUTE_REROUTE", "route_choice": "ROUTE_REROUTE", "route_reroute": "ROUTE_REROUTE",
    "radar": "RADAR", "radar_scan": "SCAN", "scan": "SCAN", "warning": "WARNING", "alert": "ALERT",
    "impact": "IMPACT_MEDIUM", "shockwave": "SHOCKWAVE", "network_expand": "NETWORK_EXPAND",
    "connection_reveal": "NETWORK_EXPAND", "new_variable": "NEW_VARIABLE", "escalation": "NEW_VARIABLE",
    "peak_reveal": "MID_PEAK", "final_reveal": "FINAL_REVEAL", "response": "COUNTER_RESPONSE",
    "camera_move": "CAMERA_SOFT_MOVE", "camera_push": "ZOOM_IN", "camera_pull": "ZOOM_OUT",
    "zoom": "ZOOM_IN", "transition": "TRANSITION_LIGHT", "comparison_reveal": "COUNTRY_REVEAL",
    "consequence_reveal": "CITY_REVEAL",
}


def rhythm_audio_enabled(plan: dict) -> bool:
    return plan.get("rhythm_policy", {}).get("version") == "v1"


def synthesize_variant(variant: dict) -> np.ndarray:
    """Deterministic stereo texture with a measured attack, never sampled audio."""
    length = round(float(variant["duration"])*SR)
    t = np.arange(length, dtype=np.float64)/SR
    duration, frequency = length/SR, float(variant["frequency"])
    index = int(variant["variant_index"])
    rng = np.random.default_rng(int(hashlib.sha256(variant["id"].encode()).hexdigest()[:16], 16))
    noise = sosfilt(butter(3, [48., float(variant["noise_ceiling"])], btype="bandpass", fs=SR, output="sos"),
                   rng.normal(size=length))
    noise /= max(float(np.sqrt(np.mean(noise**2))), 1e-12)
    # 1.1–1.7ms onset and a brief transient place the impact near the visual
    # frame even for a whoosh; the longer envelope supplies its movement tail.
    attack = 1-np.exp(-t/(.0011+index*.0002))
    ending = np.clip((duration-t)/.025, 0, 1)
    phase = 2*np.pi*(frequency*t+frequency*.055*(1-np.exp(-t/.035)))
    family = variant["family"]
    if family == "impact":
        boom_phase = 2*np.pi*(frequency*.62*t+frequency*.038*(1-np.exp(-t/.024)))
        mono = (np.sin(boom_phase)*np.exp(-t/(duration*.28))
                + .28*noise*np.exp(-t/.016))*attack*ending
    elif family in {"pulse", "tick"}:
        decay = duration*(.16 if family == "tick" else .22)
        mono = (.74*np.sin(phase)+.13*np.sin(phase*1.49)+.10*noise*np.exp(-t/.013))*np.exp(-t/decay)*attack*ending
    elif family in {"warning", "radar"}:
        modulation = (.75+.25*np.cos(2*np.pi*(12. if family == "warning" else 8.)*t))
        chirp = phase+2*np.pi*frequency*.5*t*t/duration
        mono = (.65*np.sin(chirp)+.10*noise)*np.exp(-t/(duration*.30))*modulation*attack*ending
    else:
        swell = .42*np.exp(-t/.026)+np.sin(np.pi*t/duration)**1.6
        mono = (.38*noise+.15*np.sin(phase))*swell*attack*ending
    if family == "pass":
        pan = np.linspace(-.55, .55, length)
        stereo = np.column_stack((mono*np.sqrt((1-pan)/2), mono*np.sqrt((1+pan)/2)))
    else:
        reflection = np.zeros_like(mono)
        delay = round((.011+.003*index)*SR)
        reflection[delay:] = mono[:-delay]*.13
        stereo = np.column_stack((mono*.72+reflection*.24, mono*.68+reflection))
    return (stereo/max(float(np.max(np.abs(stereo))), 1e-12)).astype(np.float32)


def catalog() -> dict:
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    # Only sound content addresses the library; changing a reporting or mixing
    # function cannot silently alter a pinned library identity.
    content = json.dumps({"version": LIBRARY_VERSION, "sr": SR, "profiles": _PROFILES,
                          "algorithm": inspect.getsource(synthesize_variant)}, sort_keys=True).encode()
    content_sha = hashlib.sha256(content).hexdigest()
    variants = []
    for category in CATEGORIES:
        family, duration, frequency, ceiling = _PROFILES[category]
        for index in range(1, 4):
            variants.append({"id": f"{category}_{index:02d}", "category": category, "family": family,
                "duration": round(duration*(1+(index-2)*.075), 6),
                "frequency": frequency*(1+(index-2)*.13), "noise_ceiling": ceiling*(1+(index-2)*.08),
                "variant_index": index, "sample_rate": SR, "channels": 2,
                "source": "Original engine/rhythm_sound.py procedural synthesis; no recordings or reference samples",
                "source_url": "Repository://engine/rhythm_sound.py", "author": "Cinematic World Map project",
                "license": "CC0-1.0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "attribution_required": False, "source_sha256": source_sha, "library_content_sha256": content_sha})
    return {"version": LIBRARY_VERSION, "source_sha256": source_sha, "library_content_sha256": content_sha,
            "license": "CC0-1.0", "source_url": "Repository://engine/rhythm_sound.py",
            "categories": list(CATEGORIES), "intensities": list(INTENSITIES), "variants": variants,
            "scope": "Stylized map cues; not authentic aircraft/ship recordings or physical acoustics"}


def materialize_variant(variant_id: str, library_root: Path) -> tuple[np.ndarray, dict]:
    details = catalog()
    variant = next((v for v in details["variants"] if v["id"] == variant_id), None)
    if variant is None:
        raise ValueError("RHYTHM_SFX_VARIANT_MISSING: "+str(variant_id))
    root = Path(library_root)/details["library_content_sha256"][:16]
    root.mkdir(parents=True, exist_ok=True)
    path = root/(variant_id+".wav")
    signal = synthesize_variant(variant)
    if not path.exists():
        with tempfile.NamedTemporaryFile(prefix=variant_id+"-", suffix=".wav", dir=root, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            wavfile.write(temporary, SR, signal)
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
    rate, existing = wavfile.read(path)
    if rate != SR or existing.shape != signal.shape or not np.array_equal(existing, signal):
        raise RuntimeError("RHYTHM_SFX_ASSET_CHANGED: "+str(path))
    meta = {**variant, "file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "pcm_sha256": hashlib.sha256(signal.tobytes()).hexdigest(), "bytes": path.stat().st_size,
            "duration": len(signal)/SR, "library_version": LIBRARY_VERSION,
            "generated_date": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
    sidecar = path.with_suffix(".json")
    try:
        with sidecar.open("x", encoding="utf-8") as stream:
            json.dump(meta, stream, ensure_ascii=False, indent=2)
    except FileExistsError:
        recorded = json.loads(sidecar.read_text())
        if recorded.get("sha256") != meta["sha256"] or recorded.get("library_content_sha256") != details["library_content_sha256"]:
            raise RuntimeError("RHYTHM_SFX_METADATA_CHANGED: "+str(sidecar))
    return signal.astype(np.float64), meta


def _category(sound: dict, visual: dict | None, scene: dict, duration: float) -> str:
    explicit = sound.get("sfx_category")
    if explicit:
        result = _ALIASES.get(explicit, explicit)
    elif visual:
        if visual.get("kind") == "final_reveal" or visual.get("role") == "payoff":
            result = "FINAL_REVEAL"
        elif visual.get("role") == "peak":
            result = "FINAL_PEAK" if float(scene["start_time"])+float(visual["time"]) >= .8*duration else "MID_PEAK"
        else:
            result = _EVENT_CATEGORY.get(visual.get("kind"), "CITY_REVEAL")
    else:
        kind = str(sound.get("kind", "pulse")).lower()
        result = _EVENT_CATEGORY.get(kind, "IMPACT_MEDIUM" if "hit" in kind else
            "CAMERA_SOFT_MOVE" if "whoosh" in kind else "ROUTE_START" if "sweep" in kind else "CITY_REVEAL")
    if result not in CATEGORIES:
        raise ValueError("RHYTHM_SFX_CATEGORY_INVALID: "+str(result))
    if visual and visual.get("kind") == "entity_departure" and not explicit:
        entity = next((e for e in scene.get("entities", []) if e.get("id") == visual.get("target_id")), {})
        if entity.get("type") in {"ship", "cargo_ship"}:
            result = "SHIP_PASS"
        elif entity.get("type") not in {None, "aircraft"}:
            result = "ENTITY_MOVE"
    return result


def _intensity(sound: dict, category: str) -> str:
    if "sfx_intensity" in sound:
        result = sound["sfx_intensity"]
    elif category in {"CAMERA_SOFT_MOVE", "ROUTE_PROGRESS", "SCAN"}:
        result = "SUBTLE"
    elif category in {"COUNTRY_REVEAL", "REGION_REVEAL", "CITY_REVEAL", "RADAR", "TRANSITION_LIGHT"}:
        result = "LOW"
    elif category in {"FINAL_PEAK", "FINAL_REVEAL"}:
        result = "PEAK"
    elif category in {"MID_PEAK", "ROUTE_BLOCK", "WARNING", "ALERT", "IMPACT_HEAVY", "SHOCKWAVE", "NEW_VARIABLE"}:
        result = "HIGH"
    else:
        result = "MEDIUM"
    if result not in INTENSITIES:
        raise ValueError("RHYTHM_SFX_INTENSITY_INVALID: "+str(result))
    return result


def _recipes(category: str) -> list[dict]:
    if category in {"MID_PEAK", "FINAL_PEAK", "FINAL_REVEAL"}:
        return [{"layer": "pre", "category": "ZOOM_IN", "offset_seconds": -.20, "intensity": "SUBTLE", "reverse": True, "duration": .20},
                {"layer": "core", "category": category, "offset_seconds": 0.},
                {"layer": "post", "category": "RADAR", "offset_seconds": .10, "intensity": "SUBTLE", "duration": .23}]
    if category == "ROUTE_BLOCK":
        return [{"layer": "core", "category": category, "offset_seconds": 0.},
                {"layer": "post", "category": "WARNING", "offset_seconds": 1/30, "intensity": "SUBTLE", "duration": .19}]
    return [{"layer": "core", "category": category, "offset_seconds": 0.}]


def select_rhythm_sound_events(plan: dict, history: list[dict] | None = None) -> dict:
    """Canonical semantic binding precedes all visibility/pre/post offsets."""
    duration = float(plan["duration"])
    fps = float(plan.get("render", {}).get("fps", 30))
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("RHYTHM_SFX_FPS_INVALID")
    policy = plan.get("rhythm_policy", {})
    preserve_authored = bool(policy.get("preserve_authored_sfx_choices", False))
    offset_frames = policy.get("sfx_core_onset_offset_frames", 1)
    if not isinstance(offset_frames, int) or offset_frames < 0 or offset_frames > 1:
        raise ValueError("RHYTHM_SFX_ONSET_OFFSET_INVALID")
    candidates, warnings = [], []
    carried = deepcopy(history or [])
    for scene in plan.get("scenes", []):
        visuals = {e.get("id"): e for e in scene.get("visual_events", []) if isinstance(e, dict)}
        sounds = scene.get("sound_events", [])
        if not sounds:
            from .retention import MEANINGFUL
            sounds = [{"id": "A_"+e["id"], "kind": e["kind"], "time": e["time"], "visual_event_id": e["id"]}
                      for e in visuals.values() if e.get("kind") in MEANINGFUL and e.get("meaningful", True)]
        for ordinal, original in enumerate(sounds):
            sound = {"kind": original, "time": 0.} if isinstance(original, str) else deepcopy(original)
            visual = visuals.get(sound.get("visual_event_id"))
            if sound.get("visual_event_id") and visual is None:
                raise ValueError("RHYTHM_SFX_VISUAL_EVENT_MISSING: "+str(sound["visual_event_id"]))
            local = float(visual["time"] if visual else sound.get("time", sound.get("timestamp", 0.)))
            authored = float(scene["start_time"])+local
            if not math.isfinite(authored) or not 0 <= local < float(scene["duration"]) or not 0 <= authored < duration:
                raise ValueError("RHYTHM_SFX_EVENT_OUTSIDE_PROJECT")
            canonical = math.ceil(authored*fps-1e-4)
            visible = canonical+(offset_frames if visual else 0)
            if visible/fps >= duration:
                raise ValueError("RHYTHM_SFX_VISIBLE_FRAME_OUTSIDE_PROJECT")
            authored_category = _category(sound, visual, scene, duration)
            _intensity(sound, authored_category)  # Validate before overriding inherited defaults.
            requested_variant = sound.get("sfx_variant")
            if requested_variant:
                original_category = sound.get("sfx_category", authored_category)
                allowed = {f"{original_category}_{i:02d}" for i in range(1, 4)} | {f"{authored_category}_{i:02d}" for i in range(1, 4)}
                if requested_variant not in allowed:
                    raise ValueError("RHYTHM_SFX_VARIANT_CATEGORY_MISMATCH: "+str(requested_variant))
            semantic_sound = sound if preserve_authored or not visual else {
                key: value for key, value in sound.items() if key not in {"sfx_category", "sfx_intensity", "gain", "gain_db"}}
            category = _category(semantic_sound, visual, scene, duration)
            intensity = _intensity(semantic_sound, category)
            event_id = sound.get("id", f"A_{scene['scene_id']}_{ordinal:02d}")
            for recipe in _recipes(category):
                frame = visible+round(recipe["offset_seconds"]*fps)
                if frame < 0:
                    warnings.append({"code": "RHYTHM_PRE_HIT_OUTSIDE_PROJECT_OMITTED", "event_id": event_id})
                    continue
                if frame/fps >= duration:
                    warnings.append({"code": "RHYTHM_POST_HIT_OUTSIDE_PROJECT_OMITTED", "event_id": event_id})
                    continue
                core = recipe["layer"] == "core"
                requested = sound.get("sfx_variant") if core and (preserve_authored or not visual) else None
                if requested:
                    # Existing v1 prepared choices retain their numerical index
                    # when a category has a new name; arbitrary mismatches fail.
                    old = sound.get("sfx_category")
                    if old in _ALIASES and requested.startswith(old+"_"):
                        requested = _ALIASES[old]+requested[len(old):]
                    if not preserve_authored and visual and category != authored_category:
                        requested = None
                layer_category = recipe["category"]
                layer_intensity = recipe.get("intensity", intensity)
                event = {"id": event_id if core else event_id+"_"+recipe["layer"].upper(), "event_id": event_id,
                    "scene_id": scene["scene_id"], "visual_event_id": sound.get("visual_event_id"),
                    "visual_kind": visual.get("kind") if visual else None, "layer": recipe["layer"],
                    "primary_sync": core, "pre_hit": recipe["layer"] == "pre", "post_hit": recipe["layer"] == "post",
                    "authored_visual_time": authored, "visual_time": authored, "canonical_frame": canonical,
                    "first_positive_visual_frame": visible, "frame": frame, "absolute_time": frame/fps,
                    "time": frame/fps-float(scene["start_time"]), "semantic_binding": bool(visual),
                    "sync_error_seconds": (frame-visible)/fps if core else None,
                    "authored_offset_seconds": frame/fps-authored, "sfx_category": layer_category,
                    "sfx_intensity": layer_intensity, "sfx_variant": requested,
                    "explicit_variant": bool(requested), "reverse": bool(recipe.get("reverse")),
                    "linear_gain": INTENSITY_GAIN[layer_intensity],
                    "semantic_intensity_policy": bool(visual) and not preserve_authored,
                    "inherited_gain_ignored": core and bool(visual) and not preserve_authored and "gain" in sound}
                if core and "gain" in semantic_sound:
                    gain = float(semantic_sound["gain"])
                    if not math.isfinite(gain) or gain < 0:
                        raise ValueError("RHYTHM_SFX_GAIN_INVALID")
                    event["linear_gain"] *= gain/.12
                limit = recipe.get("duration", sound.get("duration") if core else None)
                if limit is not None:
                    if not math.isfinite(float(limit)) or float(limit) <= 0:
                        raise ValueError("RHYTHM_SFX_DURATION_INVALID")
                    event["duration"] = float(limit)
                candidates.append(event)
    candidates.sort(key=lambda e: (e["absolute_time"], e["scene_id"], e["id"]))
    for event in candidates:
        names = [f"{event['sfx_category']}_{i:02d}" for i in range(1, 4)]
        requested = event["sfx_variant"]
        if requested and requested not in names:
            raise ValueError("RHYTHM_SFX_VARIANT_CATEGORY_MISMATCH: "+str(requested))
        at = event["absolute_time"]
        recent = {h.get("sfx_variant") for h in carried if 0 <= at-float(h.get("absolute_time", -1e9)) <= RECENT_SECONDS}
        previous = carried[-1].get("sfx_variant") if carried else None
        seed = int(hashlib.sha256((event["scene_id"]+":"+event["id"]+":"+event["sfx_intensity"]).encode()).hexdigest()[:8], 16)
        rotated = names[seed % 3:]+names[:seed % 3]
        available = [name for name in rotated if name not in recent and name != previous]
        if not available:
            last = {name: max((float(h.get("absolute_time", -1e9)) for h in carried if h.get("sfx_variant") == name), default=-1e9) for name in names}
            available = sorted((name for name in rotated if name != previous), key=lambda name: last[name])
        variant = requested or available[0]
        if variant in recent:
            warnings.append({"code": "RHYTHM_SFX_RECENT_VARIANT_REUSE", "id": event["id"], "variant": variant, "explicit_user_override": bool(requested)})
        if variant == previous:
            warnings.append({"code": "RHYTHM_SFX_CONSECUTIVE_EXPLICIT_REPEAT", "id": event["id"], "variant": variant})
        event["sfx_variant"] = variant
        carried.append({key: event[key] for key in ("id", "scene_id", "absolute_time", "sfx_category", "sfx_variant", "sfx_intensity", "layer")})
    return {"events": candidates, "history": carried, "warnings": warnings, "fps": fps,
            "recent_seconds": RECENT_SECONDS,
            "preserve_authored_sfx_choices": preserve_authored,
            "onset_policy": {"version": "v1", "core_offset_frames": offset_frames,
                "method": "ceil authored visual frame (six-decimal tolerance), then bound core first-positive offset, then pre/post layer offsets",
                "scene_json_sound_times": "Canonical authored visual times remain unchanged", "scope": "Renderer first-positive frame policy; encoded-pixel verification remains separate"},
            "max_sync_error_seconds": max((abs(e["sync_error_seconds"]) for e in candidates if e["primary_sync"]), default=0.)}


def _pause_envelope(plan: dict, duration: float, minimum: float) -> tuple[np.ndarray, list[dict]]:
    envelope = np.ones(round(duration*SR), np.float64)
    records = []
    for original in plan.get("rhythm_policy", {}).get("micro_pauses", []):
        start, length = float(original["time"]), float(original["duration"])
        if not math.isfinite(start) or not math.isfinite(length) or length <= 0 or start < 0 or start+length > duration+1e-6:
            raise ValueError("RHYTHM_MICRO_PAUSE_OUTSIDE_PROJECT")
        end = min(duration, start+length)
        a, b = round(start*SR), min(len(envelope), round(end*SR))
        times = np.arange(a, b)/SR
        ramp = min(.016, length/4)
        gain = np.interp(times, [start, start+ramp, end-ramp, end], [1., minimum, minimum, 1.])
        envelope[a:b] = np.minimum(envelope[a:b], gain)
        records.append({**original, "start_sample": a, "end_sample": b, "minimum_gain": minimum,
                        "edge_ramp_seconds": ramp, "actual_duration": (b-a)/SR})
    return envelope, records


def render_rhythm_sound_events(plan: dict, library_root: Path) -> tuple[np.ndarray, dict]:
    selection = select_rhythm_sound_events(plan)
    details = catalog()
    pinned = plan.get("rhythm_policy", {}).get("sfx_library_content_sha256")
    if pinned and pinned != details["library_content_sha256"]:
        raise RuntimeError("RHYTHM_SFX_PINNED_LIBRARY_MISMATCH")
    duration = float(plan["duration"])
    audio = np.zeros((round(duration*SR), 2), np.float64)
    pause, pause_meta = _pause_envelope(plan, duration, .52)
    enabled = bool(plan.get("options", {}).get("sfx", True))
    sources = {}
    for event in selection["events"]:
        event["enabled"] = enabled
        offset = round(event["absolute_time"]*SR)
        event["onset_sample"] = offset
        if not enabled:
            continue
        signal, source = materialize_variant(event["sfx_variant"], library_root)
        sources[source["id"]] = source
        n = min(len(signal), len(audio)-offset)
        if "duration" in event:
            n = min(n, max(1, round(event["duration"]*SR)))
        clip = signal[:n].copy()
        if event["reverse"]:
            clip = clip[::-1].copy()
        fade = min(round(.018*SR), n)
        if fade:
            clip[-fade:] *= np.linspace(1., 0., fade)[:, None]
        if event["reverse"] and fade:
            clip[:min(fade, round(.008*SR))] *= np.linspace(0., 1., min(fade, round(.008*SR)))[:, None]
        rendered = clip*event["linear_gain"]*pause[offset:offset+n, None]
        audio[offset:offset+n] += rendered
        magnitude = np.max(np.abs(rendered), axis=1)
        significant = np.flatnonzero(magnitude >= max(float(np.max(magnitude))*.10, 1e-8))
        first = int(significant[0]) if len(significant) else None
        event.update({"rendered_duration": n/SR, "file": source["file"], "file_sha256": source["sha256"],
                      "rendered_pcm_sha256": hashlib.sha256(rendered.astype(np.float32).tobytes()).hexdigest(),
                      "layer_peak_dbfs": 20*math.log10(max(float(np.max(magnitude)), 1e-12)),
                      "layer_rms_dbfs": 20*math.log10(max(float(np.sqrt(np.mean(rendered**2))), 1e-12)),
                      "first_10percent_peak_sample": None if first is None else offset+first,
                      "attack_10percent_peak_seconds": None if first is None else first/SR})
    active = [e for e in selection["events"] if e["enabled"]]
    primary = [e for e in active if e["primary_sync"]]
    return audio, {**selection, "enabled": enabled, "sources": list(sources.values()), "catalog": details,
        "library_version": LIBRARY_VERSION, "library_content_sha256": details["library_content_sha256"],
        "micro_pause_gain": {"events": pause_meta, "minimum_gain": float(np.min(pause)) if len(pause) else 1.},
        "actual_layer_count": len(active), "actual_primary_event_count": len(primary),
        "actual_category_count": len({e["sfx_category"] for e in active}),
        "actual_variant_count": len({e["sfx_variant"] for e in active}),
        "consecutive_variant_repeats": sum(a["sfx_variant"] == b["sfx_variant"] for a, b in zip(active, active[1:])),
        "max_primary_attack_seconds": max((e["attack_10percent_peak_seconds"] or 0. for e in primary), default=0.),
        "license": "CC0-1.0", "direct_listening": False}


def rhythm_bgm_envelope(plan: dict, duration: float) -> tuple[np.ndarray, dict]:
    """Absolute energy curve for genuine beats, major hits and brief breaths."""
    points = {0.: .45, min(duration, .16): .62, duration: .025}
    default_energy = {"REVEAL": .64, "FOCUS": .54, "MOVE": .70, "RESPONSE": .73,
                      "IMPACT": .93, "NEXT_CUE": .76, "BUILD": .83, "PEAK": 1.10, "RELEASE": .44}
    for scene in plan.get("scenes", []):
        start = float(scene["start_time"])
        for beat in scene.get("rhythm_micro_beats", []):
            at = start+float(beat["time"])
            energy = float(beat.get("music_energy", default_energy.get(str(beat["kind"]).upper(), .64)))
            if not math.isfinite(at) or not 0 <= at < duration or not math.isfinite(energy) or not 0 <= energy <= 1.3:
                raise ValueError("RHYTHM_BGM_BEAT_INVALID")
            points[at] = energy
        for visual in scene.get("visual_events", []):
            at = start+float(visual["time"])+float(plan.get("rhythm_policy", {}).get("sfx_core_onset_offset_frames", 1))/float(plan.get("render", {}).get("fps", 30))
            if visual.get("role") in {"peak", "payoff"} or visual.get("kind") in {"peak_reveal", "final_reveal"}:
                points[max(0., at-.28)] = .82
                points[min(duration, at)] = 1.12
                points[min(duration, at+.18)] = .98
                points[min(duration, at+.40)] = .44
                points[min(duration, at+.68)] = .67
    points[duration] = .025
    ordered = sorted(points.items())
    times = np.arange(round(duration*SR))/SR
    curve = np.interp(times, [p[0] for p in ordered], [p[1] for p in ordered])
    pause, records = _pause_envelope(plan, duration, .56)
    curve *= pause
    return curve, {"energy_points": [list(p) for p in ordered], "micro_pauses": records,
                   "minimum_energy": float(np.min(curve)) if len(curve) else 0.,
                   "maximum_energy": float(np.max(curve)) if len(curve) else 0., "license": "CC0-1.0"}


def bgm_event_sidechain(plan: dict, events: list[dict], duration: float) -> tuple[np.ndarray, dict]:
    """Shallow, bounded music dips for important primary hits, never narration."""
    envelope = np.ones(round(duration*SR), np.float64)
    records = []
    enabled = bool(plan.get("rhythm_policy", {}).get("bgm_sidechain", True))
    if enabled:
        for event in events:
            if not event.get("enabled", True) or not event.get("primary_sync") or event.get("sfx_intensity") not in {"HIGH", "PEAK"}:
                continue
            at = float(event["absolute_time"])
            minimum = .72 if event["sfx_intensity"] == "PEAK" else .82
            attack, hold, release = .012, .035, .145
            a, b = max(0, round((at-attack)*SR)), min(len(envelope), round((at+hold+release)*SR))
            t = np.arange(a, b)/SR
            gain = np.interp(t, [at-attack, at, at+hold, at+hold+release], [1., minimum, minimum, 1.])
            envelope[a:b] = np.minimum(envelope[a:b], gain)
            records.append({"event_id": event["event_id"], "timestamp": at, "minimum_gain": minimum,
                            "attack_seconds": attack, "hold_seconds": hold, "release_seconds": release})
    return envelope, {"enabled": enabled, "events": records, "event_count": len(records),
        "minimum_gain": float(np.min(envelope)) if len(envelope) else 1.,
        "maximum_sample_gain_delta": float(np.max(np.abs(np.diff(envelope)))) if len(envelope) > 1 else 0.,
        "scope": "BGM only, minimum combination avoids stacked pumping; existing narration priority remains independent"}
