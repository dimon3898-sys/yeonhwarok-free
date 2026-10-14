"""Consume optional mapData as CPU configuration before legacy scene parsing.

The existing strict renderer/planner parsers do not gain a new field. This
independent wrapper removes only mapData and returns the original renderer
fields. It never loads a source, creates a cache, downloads, changes camera or
geometry, or activates GPU work. A later CPU pipeline executes the bindings.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
import json
import math

from .model import DataError, sha256, validate_bbox
from .providers import ArchiveCatalog, DataRequest, SourceSpec


_ROLES = {"terrain": "land_elevation", "bathymetry": "ocean_bathymetry",
          "surfaceTexture": "land_surface_texture"}
_MAP_FIELDS = {"enabled", "bbox", "crs", "targetGroundResolution", "cache", *_ROLES}
_CACHE_DEFAULTS = {"mode": "read_write", "maxBytes": 64*1024*1024,
                   "maxConcurrency": 2, "maxRetries": 2, "timeoutSeconds": 10,
                   "deadlineSeconds": 30, "retryAfterCeilingSeconds": 10, "resume": False}


def _json_value(value, depth=0):
    if depth > 64:
        raise DataError("scene JSON nesting exceeds supported depth")
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise DataError("scene JSON object keys must be strings")
        for item in value.values():
            _json_value(item, depth+1)
    elif isinstance(value, list):
        for item in value:
            _json_value(item, depth+1)
    elif isinstance(value, bool) or value is None or isinstance(value, str):
        return
    elif isinstance(value, (int, float)):
        try:
            finite = math.isfinite(float(value))
        except (TypeError, ValueError, OverflowError):
            finite = False
        if not finite:
            raise DataError("scene JSON numbers must be finite")
    else:
        raise DataError("scene must contain only JSON values")


def renderer_fingerprint(renderer_scene: dict) -> str:
    """SHA of the supplied renderer payload using documented canonical JSON.

    UTF-8 JSON uses sorted keys, ASCII escapes, compact separators and finite
    numbers. Compare with the same representation of the original renderer
    dictionary; this is not the original file-byte SHA or a native GPU receipt.
    """
    if not isinstance(renderer_scene, dict):
        raise DataError("scene must be a JSON object")
    _json_value(renderer_scene)
    try:
        payload = json.dumps(renderer_scene, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise DataError("invalid renderer JSON payload") from exc
    return sha256(payload)


def _object(value, fields, label):
    if not isinstance(value, dict):
        raise DataError(f"{label} must be an object")
    unknown = set(value) - fields
    if unknown:
        raise DataError(f"unknown {label} field: {sorted(unknown)[0]}")


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise DataError(f"{label} must be nonempty text of at most 1024 characters")


def _integer(value, label, minimum, maximum):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value)) or value != int(value)
            or not minimum <= value <= maximum):
        raise DataError(f"{label} must be an integer in [{minimum},{maximum}]")
    # JSON Schema integers include integral JSON numbers such as 2.0. Normalize
    # returned policy for DownloadManager while retaining original scene fields.
    return int(value)


def _seconds(value, label, *, positive=True):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value)) or not 0 <= value <= 3600 or positive and value == 0):
        raise DataError(f"{label} must be finite {'positive' if positive else 'nonnegative'} seconds up to 3600")


def _cache_policy(settings):
    _object(settings, set(_CACHE_DEFAULTS), "mapData.cache")
    result = {**_CACHE_DEFAULTS, **deepcopy(settings)}
    if not isinstance(result["mode"], str) or result["mode"] not in {"read_write", "read_only", "bypass"}:
        raise DataError("cache mode must be read_write, read_only or bypass")
    result["maxBytes"] = _integer(result["maxBytes"], "maxBytes", 1, 64*1024*1024)
    result["maxConcurrency"] = _integer(result["maxConcurrency"], "maxConcurrency", 1, 8)
    result["maxRetries"] = _integer(result["maxRetries"], "maxRetries", 0, 5)
    _seconds(result["timeoutSeconds"], "timeoutSeconds")
    _seconds(result["deadlineSeconds"], "deadlineSeconds")
    _seconds(result["retryAfterCeilingSeconds"], "retryAfterCeilingSeconds", positive=False)
    if not isinstance(result["resume"], bool):
        raise DataError("cache resume must be a boolean")
    return result


@dataclass(frozen=True)
class ScenePreparation:
    """Validated configuration and original renderer payload, with no artifacts."""
    renderer_scene: dict
    renderer_sha256: str
    map_data: dict | None
    enabled: bool
    request: DataRequest | None
    source_bindings: dict
    cache_policy: dict
    gpu_activation: bool = field(default=False, init=False)

    def to_dict(self):
        return {"rendererScene": deepcopy(self.renderer_scene),
                "rendererPayloadSha256": self.renderer_sha256,
                "mapData": deepcopy(self.map_data), "enabled": self.enabled,
                "request": None if self.request is None else {
                    "bbox": list(self.request.bbox), "crs": self.request.crs,
                    "targetGroundResolution": self.request.target_ground_resolution},
                "sourceBindings": {role: {"sourceId": spec.source_id, "version": spec.source_version,
                                           "dataClass": spec.data_class}
                                   for role, spec in self.source_bindings.items()},
                "cachePolicy": deepcopy(self.cache_policy),
                "configurationValidated": True, "sourceFetchExecuted": False,
                "cacheCreated": False, "gpuActivation": False}


def prepare_scene(scene: dict, sources=None) -> ScenePreparation:
    """Validate optional CPU mapData and bind caller-supplied source identities.

    ``sources`` may be ArchiveCatalog or a mapping ``sourceId -> SourceSpec``.
    Enabled configuration needs an explicit bbox and at least one complete
    terrain/bathymetry/surfaceTexture selector ``{sourceId, version}``. Source
    IDs, exact versions and data classes are checked; no country, source URL,
    geometry, camera setting, license approval or network grant is inferred.

    Missing/disabled mapData never resolves the catalog. Disabled settings may
    be incomplete, while present fields still receive structural/type/limit
    validation. Defaults apply only to returned configuration; input dictionaries
    and all original renderer fields remain untouched. Read-only/bypass cache
    modes are configuration for the caller, not operations performed here.
    """
    if not isinstance(scene, dict):
        raise DataError("scene must be a JSON object")
    _json_value(scene)
    renderer = deepcopy(scene)
    settings = renderer.pop("mapData", None)
    present = "mapData" in scene
    fingerprint = renderer_fingerprint(renderer)
    if not present:
        return ScenePreparation(renderer, fingerprint, None, False, None, {}, deepcopy(_CACHE_DEFAULTS))
    _object(settings, _MAP_FIELDS, "mapData")
    enabled = settings.get("enabled", False)
    if not isinstance(enabled, bool):
        raise DataError("mapData.enabled must be a boolean for CPU preparation only")
    if "bbox" in settings:
        if not isinstance(settings["bbox"], list):
            raise DataError("mapData.bbox must be a four-number JSON array")
        validate_bbox(settings["bbox"])
    crs = settings.get("crs", "EPSG:4326")
    if crs != "EPSG:4326":
        raise DataError("mapData.crs must be EPSG:4326; no implicit reprojection")
    resolution = settings.get("targetGroundResolution")
    if "targetGroundResolution" in settings:
        if (isinstance(resolution, bool) or not isinstance(resolution, (int, float))
                or not math.isfinite(float(resolution)) or resolution <= 0):
            raise DataError("targetGroundResolution must be finite positive meters")
    cache_policy = _cache_policy(settings.get("cache", {}))
    selected = []
    for role in _ROLES:
        if role not in settings:
            continue
        selector = settings[role]
        _object(selector, {"sourceId", "version"}, f"mapData.{role}")
        for key in selector:
            _text(selector[key], f"{role}.{key}")
        if enabled and set(selector) != {"sourceId", "version"}:
            raise DataError(f"enabled {role} requires explicit sourceId and version")
        selected.append((role, selector))
    if not enabled:
        return ScenePreparation(renderer, fingerprint, deepcopy(settings), False, None, {}, cache_policy)
    if "bbox" not in settings:
        raise DataError("enabled mapData requires an explicit bbox; scene geometry/camera is not a substitute")
    if not selected:
        raise DataError("enabled mapData requires at least one explicit source role")
    request = DataRequest(tuple(settings["bbox"]), crs, resolution)
    request.validate()
    registry = sources.sources if isinstance(sources, ArchiveCatalog) else sources
    if not isinstance(registry, Mapping):
        raise DataError("enabled mapData requires a caller-supplied source catalog or mapping")
    bindings = {}
    for role, selector in selected:
        source_id = selector["sourceId"]
        if source_id not in registry:
            raise DataError(f"unknown mapData sourceId for {role}: {source_id}")
        spec = registry[source_id]
        if not isinstance(spec, SourceSpec) or spec.source_id != source_id:
            raise DataError("source registry identity must match a supplied SourceSpec")
        if spec.source_version != selector["version"]:
            raise DataError(f"source version mismatch for {role}; explicit pinned version required")
        if spec.data_class != _ROLES[role]:
            raise DataError(f"source data class does not match selected {role} role")
        bindings[role] = spec
    return ScenePreparation(renderer, fingerprint, deepcopy(settings), True, request, bindings, cache_policy)
