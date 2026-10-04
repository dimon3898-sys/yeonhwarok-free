"""Read-only CPU scene-render predictions from successful native render evidence.

Predictions always have measured=False. Failed final QC, stale renderer versions,
clips and unobserved quality/sample configurations never provide timing evidence.
Large media/8K assets are not reread for every planning request; completed records,
source hashes and bounded path/stat checks are used instead.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median

from .assets import APP_ROOT, V3_ROOT, asset_registry, renderer_version, sha256_file
from .backends import QUALITY_SETTINGS
from .presets import LIGHTING_PRESETS
from .storage import plan_hash

SCOPE = "uncached_scene_render_only"
SHA = re.compile(r"[a-f0-9]{64}")
MAX_METADATA_BYTES = 16 * 1024 * 1024
LIMITATIONS = [
    "Prediction for rendering all selected Scenes without cache; not an actual measured completion time.",
    "Audio, TTS, subtitles, assembly, QC, planning, queueing and recovery wall time are excluded.",
    "No cache-hit speedup, GPU cost or CINEMA multiplier is inferred from HIGH.",
    "Camera, visible terrain/clouds, entity/network complexity and machine load can change rendering cost.",
    "Recorded successful-QC hashes and matching native source provenance are used; large media/asset bytes are not rehashed for each request.",
    "Bounded path/mtime checks detect missing or subsequently modified media, not deliberate same-mtime content tampering; final delivery requires full hash verification.",
]


class _ReferenceRejected(ValueError):
    pass


def _positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value > 0 else None


def _read(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_METADATA_BYTES:
        raise _ReferenceRejected("MISSING_OR_OVERSIZE_METADATA")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise _ReferenceRejected("METADATA_OBJECT_REQUIRED")
    return value


def _path(base: Path, value) -> Path:
    if not isinstance(value, str) or not value:
        raise _ReferenceRejected("MEDIA_POINTER_REQUIRED")
    candidate = Path(value)
    candidate = (candidate if candidate.is_absolute() else base / candidate).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
        raise _ReferenceRejected("MISSING_OR_UNSCOPED_POINTER")
    return candidate


def _media(version: Path, value, digest, certificate_mtime: int) -> Path:
    if not isinstance(digest, str) or SHA.fullmatch(digest) is None:
        raise _ReferenceRejected("RECORDED_MEDIA_SHA_REQUIRED")
    candidate = _path(version, value)
    stat = candidate.stat()
    if not stat.st_size or stat.st_mtime_ns > certificate_mtime:
        raise _ReferenceRejected("EMPTY_OR_MODIFIED_AFTER_CERTIFICATE")
    return candidate


def _asset_key(item: dict) -> str:
    if isinstance(item.get("file"), str) and item["file"]:
        return item["file"]
    # The Korean registry entry records an absolute path rather than a file key.
    if isinstance(item.get("path"), str):
        path = Path(item["path"]).resolve()
        for root in (V3_ROOT.resolve(), APP_ROOT.resolve()):
            if path.is_relative_to(root):
                return path.relative_to(root).as_posix()
    raise _ReferenceRejected("ASSET_LIBRARY_KEY_REQUIRED")


def _current_provenance() -> dict:
    """Hash only small renderer sources; use validated-library asset source records."""
    sources = {"adapter": APP_ROOT / "web/earth_adapter.js",
               "render_html": APP_ROOT / "web/render.html",
               "render_tool": APP_ROOT / "tools/render_scene.mjs"}
    sources.update({name: V3_ROOT / name for name in
                    ("src/renderer_v3.js", "src/engine_v3.js", "src/core_v1_preserved.js", "src/aircraft_v3.js")})
    if any(not path.is_file() for path in sources.values()):
        raise _ReferenceRejected("CURRENT_RENDERER_SOURCE_MISSING")
    hashes = {name: sha256_file(path) for name, path in sources.items()}
    registry = asset_registry()
    asset_hashes = {}
    for item in registry:
        if not Path(item["path"]).is_file() or SHA.fullmatch(item.get("sha256", "")) is None:
            raise _ReferenceRejected("CURRENT_ASSET_SOURCE_RECORD_INVALID")
        asset_hashes[_asset_key(item)] = item["sha256"]
    native_assets = {name: asset_hashes[name] for name in
                     ("assets/v3/earth/earth-day-8k.jpg", "assets/v3/earth/earth-night-8k.jpg",
                      "assets/v3/earth/earth-clouds-8k.jpg", "assets/v3/fonts/OpenSans-Light.ttf",
                      "assets/gis/earth-topology.png", "assets/gis/countries_50m.geojson")}
    hashes.update(native_assets)
    hashes["korean_font"] = asset_hashes["web/fonts/NotoSansCJKkr-Regular.otf"]
    return {"renderer_version": renderer_version(), "native_hashes": hashes,
            "native_assets": native_assets, "asset_hashes": asset_hashes}


def _quality(scene: dict, global_quality: str = "HIGH") -> str | None:
    value = scene.get("render_quality", global_quality)
    if isinstance(value, dict):
        value = value.get("preset", value.get("mode"))
    if global_quality == "FAST":
        value = "FAST"  # Mirrors the all-FAST preview pipeline override.
    return value if isinstance(value, str) and value in QUALITY_SETTINGS else None


def _reference_version(result_path: Path, provenance: dict) -> list[dict]:
    version = result_path.parent.parent.resolve()
    if version.parent.name != "versions" or re.fullmatch(r"v\d{3,}", version.name) is None:
        raise _ReferenceRejected("IMMUTABLE_VERSION_REQUIRED")
    plan = _read(version / "scene_plan.json")
    result = _read(result_path)
    approval = _read(version / "approval.json")
    checkpoint = _read(version / "renders/checkpoint.json")
    digest = plan_hash(plan)
    if (plan.get("project_id") != version.parent.parent.name or plan.get("version") != version.name or
            plan.get("plan_hash") != digest or result.get("plan_hash") != digest or
            approval.get("plan_hash") != digest or checkpoint.get("plan_hash") != digest or
            approval.get("user_approval") is not True):
        raise _ReferenceRejected("EXACT_APPROVED_PLAN_REQUIRED")
    if (result.get("qc", {}).get("passed") is not True or checkpoint.get("complete") is not True or
            checkpoint.get("qc_passed") is not True):
        raise _ReferenceRejected("SUCCESSFUL_FINAL_QC_REQUIRED")
    if (result.get("metrics", {}).get("measured") is not True or
            result.get("metrics", {}).get("backend") != "CPU_LOCAL"):
        raise _ReferenceRejected("MEASURED_CPU_REFERENCE_REQUIRED")
    if result.get("renderer_version") != provenance["renderer_version"]:
        raise _ReferenceRejected("CURRENT_RENDERER_REFERENCE_REQUIRED")
    if any(document.get("synthetic") is True or document.get("test_fixture") is True
           for document in (plan, result, result.get("metrics", {}))):
        raise _ReferenceRejected("SYNTHETIC_REFERENCE_FORBIDDEN")
    assets = result.get("assets", {})
    if (assets.get("passed") is not True or assets.get("errors") or
            assets.get("renderer_version") != provenance["renderer_version"]):
        raise _ReferenceRejected("SUCCESSFUL_ASSET_PROVENANCE_REQUIRED")
    recorded_assets = {_asset_key(item): item for item in assets.get("assets", [])}
    for name, expected in provenance["asset_hashes"].items():
        item = recorded_assets.get(name, {})
        if item.get("sha256") != expected or item.get("actual_sha256") != expected or not item.get("license"):
            raise _ReferenceRejected("CURRENT_ASSET_PROVENANCE_MISMATCH")
    certificate_mtime = result_path.stat().st_mtime_ns
    outputs = result.get("outputs", {})
    for key in ("final", "muted"):
        _media(version, outputs.get(key), result.get("final_sha256", {}).get(key), certificate_mtime)
    qc_path = _path(version, outputs.get("qc_report"))
    if _read(qc_path.with_suffix(".json")) != result["qc"]:
        raise _ReferenceRejected("RESOLVED_QC_REPORT_MISMATCH")
    scenes = plan.get("scenes", [])
    entries = result.get("scenes", [])
    ids = [scene["scene_id"] for scene in scenes]
    if not ids or [entry.get("scene_id") for entry in entries] != ids or len(set(ids)) != len(ids):
        raise _ReferenceRejected("COMPLETE_ORDERED_SCENES_REQUIRED")
    if checkpoint.get("completed_scenes") != len(ids) or checkpoint.get("total_scenes") != len(ids):
        raise _ReferenceRejected("COMPLETED_CHECKPOINT_COUNT_REQUIRED")
    scene_results = _read(version / "renders/scene_results.json")
    if scene_results.get("plan_hash") != digest or scene_results.get("scenes") != entries:
        raise _ReferenceRejected("SCENE_RESULTS_DISAGREE")
    references = []
    for scene, entry in zip(scenes, entries):
        movie = _media(version, entry.get("movie"), entry.get("video_sha256"), certificate_mtime)
        audit = _media(version, entry.get("audit"), entry.get("audit_sha256"), certificate_mtime)
        if entry.get("complete") is not True or entry.get("renderer_version") != provenance["renderer_version"]:
            raise _ReferenceRejected("SCENE_COMPLETION_OR_RENDERER_MISMATCH")
        if scene.get("scene_type") == "CINEMATIC_CLIP":
            continue
        quality = _quality(scene, plan.get("options", {}).get("quality", "HIGH"))
        if quality is None or scene.get("lighting_preset") not in LIGHTING_PRESETS:
            raise _ReferenceRejected("REFERENCE_QUALITY_OR_LIGHTING_UNKNOWN")
        settings = QUALITY_SETTINGS[quality]
        native = entry.get("native_manifest", {})
        duration = _positive(native.get("duration"))
        seconds = _positive(native.get("elapsedSeconds"))
        temporal = settings.get("temporal_samples", 1)
        if (native.get("complete") is not True or native.get("renderer") != "MASTER_V3_SCENE_ADAPTER" or
                native.get("scene_id") != scene["scene_id"] or duration is None or seconds is None or
                abs(duration - float(scene["duration"])) > 1e-8 or native.get("fps") != settings["fps"] or
                native.get("frames") != round(duration * settings["fps"]) or
                native.get("quality") != quality or isinstance(native.get("temporalSceneSamples"), bool) or
                native.get("temporalSceneSamples") != temporal or
                native.get("internalResolution") != [settings["internal_width"], round(settings["internal_width"] * 16 / 9)] or
                native.get("outputResolution") != [settings["output_width"], settings["output_height"]]):
            raise _ReferenceRejected("COMPLETE_NATIVE_RENDER_TIMING_REQUIRED")
        if (entry.get("quality", {}).get("quality") != quality or
                entry.get("quality", {}).get("lighting") != scene["lighting_preset"]):
            raise _ReferenceRejected("SCENE_QUALITY_LIGHTING_MISMATCH")
        numeric = native.get("numericPreflight", {})
        if (numeric.get("finite") is not True or any(numeric.get(key) is not False for key in
                                                       ("cameraWithinEarth", "routeWithinEarth", "entityWithinEarth"))):
            raise _ReferenceRejected("SUCCESSFUL_NATIVE_NUMERIC_PREFLIGHT_REQUIRED")
        hashes = native.get("sourceHashes", {})
        if any(hashes.get(key) != expected for key, expected in provenance["native_hashes"].items()):
            raise _ReferenceRejected("NATIVE_SOURCE_PROVENANCE_MISMATCH")
        if not isinstance(hashes.get("scene_json"), str) or SHA.fullmatch(hashes["scene_json"]) is None:
            raise _ReferenceRejected("NATIVE_SCENE_SOURCE_SHA_REQUIRED")
        native_assets = {item.get("path"): item.get("sha256") for item in native.get("sourceAssets", [])}
        if any(native_assets.get(key) != expected for key, expected in provenance["native_assets"].items()):
            raise _ReferenceRejected("NATIVE_ASSET_PROVENANCE_MISMATCH")
        source_movie = _path(version.parent.parent.parent, native.get("output"))
        source_audit = _path(version.parent.parent.parent, native.get("audit"))
        if (source_movie.stat().st_mtime_ns > certificate_mtime or
                source_audit.stat().st_mtime_ns > certificate_mtime):
            raise _ReferenceRejected("NATIVE_POINTER_MODIFIED_AFTER_CERTIFICATE")
        sidecar = source_movie.with_suffix(".manifest.json")
        if not sidecar.is_file() or _read(sidecar) != native:
            raise _ReferenceRejected("NATIVE_SIDECAR_DISAGREES")
        source_json = source_movie.parents[2] / "scene_json" / (scene["scene_id"] + ".json")
        if not source_json.is_file() or source_json.stat().st_size > MAX_METADATA_BYTES or sha256_file(source_json) != hashes["scene_json"]:
            raise _ReferenceRejected("NATIVE_SCENE_SOURCE_CONTENT_MISMATCH")
        references.append({"project_id": plan["project_id"], "version": plan["version"],
                           "scene_id": scene["scene_id"], "quality": quality,
                           "lighting_preset": scene["lighting_preset"], "temporal_samples": temporal,
                           "native_elapsed_seconds": seconds, "native_duration_seconds": duration,
                           "seconds_per_video_second": seconds / duration,
                           "video_sha256": entry["video_sha256"], "plan_hash": digest,
                           "renderer_version": provenance["renderer_version"],
                           "result_path": str(result_path), "result_metadata_sha256": sha256_file(result_path),
                           "resolved_movie": str(movie), "resolved_audit": str(audit),
                           "native_movie": str(source_movie), "native_audit": str(source_audit),
                           "native_scene_json_sha256": hashes["scene_json"],
                           "reused_in_this_completed_version": entry.get("reused", False) is True})
    return references


def estimate_cpu_render(plan: dict, projects_root: str | Path | None = None,
                        *, current_renderer_version: str | None = None) -> dict:
    """Predict uncached Scene-only time; return seconds=None when evidence is unknown.

An exact quality+temporal-sample+lighting median is preferred. Missing lighting
buckets may use an explicitly identified same-quality/sample median. Quality or
sample configurations are never extrapolated across buckets.
"""
    response = {"backend": "CPU_LOCAL", "measured": False, "prediction": True, "scope": SCOPE,
                "seconds": None, "cost_usd": None, "method": "median native elapsedSeconds / duration, applied to requested Scene durations",
                "limitations": list(LIMITATIONS), "sources": [], "scenes": [],
                "eligible_reference_count": 0, "rejected_reference_counts": {}}
    global_quality = plan.get("options", {}).get("quality", "HIGH")
    if (not isinstance(global_quality, str) or global_quality not in QUALITY_SETTINGS or
            not isinstance(plan.get("scenes"), list) or not plan["scenes"]):
        response["reason"] = "UNKNOWN_QUALITY_OR_EMPTY_PLAN"
        return response
    for scene in plan["scenes"]:
        if not isinstance(scene, dict):
            response["reason"] = "INVALID_SCENE_INPUT"
            return response
        if scene.get("scene_type") == "CINEMATIC_CLIP":
            response["reason"] = "CINEMATIC_CLIP_TIMING_NOT_MODELLED"
            return response
        if (_quality(scene, global_quality) is None or _positive(scene.get("duration")) is None or
                scene.get("lighting_preset") not in LIGHTING_PRESETS):
            response["reason"] = "UNKNOWN_SCENE_QUALITY_LIGHTING_OR_DURATION"
            return response
    try:
        provenance = _current_provenance()
        if current_renderer_version is not None and current_renderer_version != provenance["renderer_version"]:
            response["reason"] = "REQUESTED_RENDERER_IS_NOT_CURRENT"
            return response
    except (OSError, ValueError, KeyError, TypeError) as error:
        response["reason"] = "CURRENT_PROVENANCE_UNAVAILABLE"
        response["detail"] = str(error)
        return response
    response["renderer_version"] = provenance["renderer_version"]
    root = Path(projects_root) if projects_root is not None else APP_ROOT / "projects"
    unique = {}
    rejected = Counter()
    for path in sorted(root.resolve().glob("project_*/versions/v*/renders/project_result.json")):
        try:
            for reference in _reference_version(path, provenance):
                unique.setdefault(reference["video_sha256"], reference)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            rejected[str(error) if isinstance(error, _ReferenceRejected) else type(error).__name__] += 1
    references = list(unique.values())
    response["eligible_reference_count"] = len(references)
    response["rejected_reference_counts"] = dict(sorted(rejected.items()))
    if not references:
        response["reason"] = "NO_QUALIFIED_SUCCESSFUL_CPU_REFERENCE"
        return response
    used = {}
    total = 0.
    unknown = False
    for scene in plan["scenes"]:
        quality = _quality(scene, global_quality)
        samples = QUALITY_SETTINGS[quality].get("temporal_samples", 1)
        candidates = [reference for reference in references
                      if reference["quality"] == quality and reference["temporal_samples"] == samples]
        exact = [reference for reference in candidates if reference["lighting_preset"] == scene["lighting_preset"]]
        selected = exact or candidates
        estimate = {"scene_id": scene.get("scene_id"), "quality": quality,
                    "lighting_preset": scene["lighting_preset"], "temporal_samples": samples,
                    "duration_seconds": scene["duration"], "seconds": None, "measured": False,
                    "reference_count": len(selected), "lighting_bucket_fallback": bool(selected and not exact)}
        if not selected:
            estimate["reason"] = "NO_SAME_QUALITY_AND_TEMPORAL_SAMPLE_REFERENCE"
            unknown = True
        else:
            rate = median(reference["seconds_per_video_second"] for reference in selected)
            estimate["median_seconds_per_video_second"] = rate
            estimate["seconds"] = float(scene["duration"]) * rate
            estimate["source_video_sha256"] = [reference["video_sha256"] for reference in selected]
            if not exact:
                estimate["fallback_note"] = "Same quality/sample references from other lighting presets; requested lighting/HERO complexity is unmeasured."
            if len(selected) == 1:
                estimate["sample_warning"] = "One qualified native observation; uncertainty is not statistically quantified."
            total += estimate["seconds"]
            used.update({reference["video_sha256"]: reference for reference in selected})
        response["scenes"].append(estimate)
    response["sources"] = list(used.values())
    response["seconds"] = None if unknown else total
    response["reason"] = "SOME_SCENE_BUCKETS_UNKNOWN" if unknown else "UNCACHED_SCENE_PREDICTION_FROM_QUALIFIED_NATIVE_REFERENCES"
    return response
