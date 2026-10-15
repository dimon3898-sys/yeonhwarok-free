"""Lossless CPU-to-WebGL2 upload handoff; never creates a GPU context.

The existing ASTRA providers own parsing, source validation, cache and Scene
configuration. This extension only serializes their already validated outputs.
Texture formats below are an upload contract, not a hardware capability claim.
"""
from collections.abc import Mapping
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import numpy as np

_CPU_ROOT = Path(__file__).resolve().parent.parent / "astra-cpu-data-v1"
if str(_CPU_ROOT) not in sys.path:
    sys.path.insert(0, str(_CPU_ROOT))

from astra_cpu.model import DataError, RasterData, sha256, validate_bbox
from astra_cpu.neutral import json_value
from astra_cpu.pipeline import CpuDataPipeline
from astra_cpu.providers import ProviderResult, STATUSES
from astra_cpu.scene import prepare_scene


SCHEMA = "ASTRA_GPU_UPLOAD_BUNDLE_V1"
MANIFEST_NAME = "UPLOAD_BUNDLE.json"
DEFAULT_MAX_BYTES = 64 * 1024 * 1024
HARD_MAX_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
_ROLES = ("terrain", "bathymetry", "surfaceTexture")
_FORMATS = {
    "terrain": {"internalFormat": "R32F", "format": "RED", "type": "FLOAT", "sampler": "sampler2D"},
    "bathymetry": {"internalFormat": "R16I", "format": "RED_INTEGER", "type": "SHORT", "sampler": "isampler2D"},
    "surfaceTexture": {"internalFormat": "RGBA8", "format": "RGBA", "type": "UNSIGNED_BYTE", "sampler": "sampler2D"},
}
_MASK_FORMAT = {"internalFormat": "R8UI", "format": "RED_INTEGER", "type": "UNSIGNED_BYTE", "sampler": "usampler2D"}
_QUANTITIES = {"terrain": "HEIGHT", "bathymetry": "SIGNED_ELEVATION", "surfaceTexture": "ENCODED_COLOR"}


def _digest(value, label):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise DataError(label + " must be a lowercase SHA-256")
    return value


def _integer(value, lower, upper, label):
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise DataError(f"{label} must be an integer in [{lower},{upper}]")


def _encoded_json(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _numeric_bytes(array, dtype):
    """Only byte-order changes; never change numeric precision or NaN payloads."""
    target = np.dtype(dtype)
    if array.dtype.kind != target.kind or array.dtype.itemsize != target.itemsize:
        raise DataError("upload numeric conversion would change source precision")
    return np.ascontiguousarray(array.astype(target, casting="equiv", copy=False)).tobytes(order="C")


def _part(role, index, raster, source_hash, max_texture_size, max_part_bytes, artifacts, payloads):
    if not isinstance(raster, RasterData):
        raise DataError("provider parts must be existing RasterData objects")
    estimated_bytes = raster.values.nbytes + raster.valid.size + 8 * (raster.x.size + raster.y.size)
    if estimated_bytes > max_part_bytes:
        raise DataError("upload artifacts exceed the configured byte budget")
    # Revalidate nested metadata and arrays: RasterData is frozen but Python's
    # nested dictionaries can still have been modified after construction.
    checked = RasterData(raster.values, raster.x, raster.y, raster.valid, raster.metadata)
    metadata = checked.metadata
    if metadata.get("crs") != "EPSG:4326":
        raise DataError("upload supports EPSG:4326 only; no implicit reprojection")
    if metadata.get("inputSha256") != source_hash:
        raise DataError("raster input SHA does not match the provider source")
    bbox = list(checked.bbox)
    validate_bbox(bbox)
    rows, columns = checked.values.shape[:2]
    if not 1 <= rows <= max_texture_size or not 1 <= columns <= max_texture_size:
        raise DataError("raster exceeds the configured planning texture-size limit")
    if role == "terrain":
        if checked.values.ndim != 2 or checked.values.dtype.kind != "f" or checked.values.dtype.itemsize != 4:
            raise DataError("terrain upload requires original Float32 scalar values")
        if metadata.get("units") != "m":
            raise DataError("terrain upload requires declared metre units")
        dtype = "<f4"
    elif role == "bathymetry":
        if checked.values.ndim != 2 or checked.values.dtype.kind != "i" or checked.values.dtype.itemsize != 2:
            raise DataError("bathymetry upload requires original signed Int16 scalar values")
        if metadata.get("quantity") != "SIGNED_ELEVATION" or metadata.get("positive") != "up" or metadata.get("units") != "m":
            raise DataError("bathymetry must remain positive-up signed elevation in metres")
        dtype = "<i2"
    else:
        if checked.values.ndim != 3 or checked.values.shape[2] != 4 or checked.values.dtype != np.uint8:
            raise DataError("surface upload supports original RGBA8 only; RGB conversion is not implicit")
        dtype = "|u1"
    identity = f"{role}-{index:02d}"

    def artifact(kind, data):
        name = identity + "." + kind + ".bin"
        if name in payloads:
            raise DataError("duplicate upload artifact")
        reference = {"file": name, "bytes": len(data), "sha256": sha256(data), "kind": kind}
        payloads[name] = data
        artifacts.append(reference)
        return deepcopy(reference)

    values = artifact("values", _numeric_bytes(checked.values, dtype))
    valid = artifact("valid", checked.valid.astype(np.uint8).tobytes(order="C"))
    valid["format"] = deepcopy(_MASK_FORMAT)
    x = artifact("x", _numeric_bytes(checked.x, "<f8"))
    y = artifact("y", _numeric_bytes(checked.y, "<f8"))
    x.update(dtype="<f8", count=columns)
    y.update(dtype="<f8", count=rows)
    transform = [float(v) for v in metadata["transform"]]
    return {
        "id": identity, "dimensions": [columns, rows], "shape": list(checked.values.shape),
        "numericDtype": dtype, "sourceDtype": checked.values.dtype.str,
        "sourceValueBytesSHA256": sha256(checked.values.tobytes(order="C")),
        "byteOrderConversion": "NONE" if checked.values.dtype == np.dtype(dtype) else "BYTE_SWAP_ONLY",
        "format": deepcopy(_FORMATS[role]), "values": values, "valid": valid, "x": x, "y": y,
        "crs": "EPSG:4326", "transform": transform, "bbox": bbox,
        "coordinatesMeaning": "PIXEL_CENTERS", "transformMeaning": "GDAL_PIXEL_CORNER",
        "rowOrder": "NORTH_TO_SOUTH" if transform[5] < 0 else "SOUTH_TO_NORTH",
        "pixelRegistration": metadata.get("pixelRegistration", metadata.get("registration", "UNDECLARED")),
        "metadata": json_value(metadata), "quantity": _QUANTITIES[role],
        "fallback": "UNCHANGED_BASELINE_OUTSIDE_SOURCE_OR_INVALID",
        "requiresNativeGISCoverage": True, "requiresOceanMask": role == "bathymetry",
    }


def build_upload_bundle(results, *, renderer_payload_sha256, enabled=True,
                        max_texture_size=16384, max_bytes=DEFAULT_MAX_BYTES):
    """Return a bounded manifest and file->bytes map from existing provider outputs.

    ``available`` retains the provider's partial-support warning; it never means
    full-camera coverage. Unavailable/error states have no upload parts. No new
    provider request, source parsing, mask classification or resampling occurs.
    """
    _digest(renderer_payload_sha256, "renderer payload SHA")
    _integer(max_texture_size, 1, 32768, "planning texture size")
    _integer(max_bytes, 1, HARD_MAX_BYTES, "upload byte budget")
    if not isinstance(enabled, bool) or not isinstance(results, Mapping) or set(results) - set(_ROLES):
        raise DataError("upload results require explicit supported roles and a Boolean enabled state")
    if not enabled and results:
        raise DataError("disabled bundle cannot contain resolved provider results")
    artifacts, payloads, sources = [], {}, {}
    for role in _ROLES:
        if role not in results:
            continue
        result = results[role]
        if not isinstance(result, ProviderResult) or result.status not in STATUSES:
            raise DataError("upload requires existing typed provider results with known status")
        if not all(isinstance(v, str) and v.strip() and len(v) <= 4096
                   for v in (result.source_id, result.source_version, result.source_url)):
            raise DataError("provider source identity/version/URL are required")
        url = urlsplit(result.source_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
            raise DataError("provider provenance URL must be HTTPS without embedded credentials")
        source_hash = _digest(result.sha256, "provider source SHA")
        if result.crs != "EPSG:4326":
            raise DataError("provider upload CRS is unsupported")
        if len(result.rasters) > 16:
            raise DataError("provider exceeds bounded upload-part count")
        if result.status == "available" and not result.rasters:
            raise DataError("available source requires actual raster support")
        source = result.to_dict()
        source.pop("rasters", None)
        source["parts"] = []
        boxes = []
        # The existing provider may retain diagnostic nodata-only rasters in an
        # unavailable result. Preserve its status/error, never upload that data.
        for index, raster in enumerate(result.rasters if result.status == "available" else ()):
            remaining = max_bytes - sum(len(raw) for raw in payloads.values())
            part = _part(role, index, raster, source_hash, max_texture_size, remaining, artifacts, payloads)
            west, south, east, north = part["bbox"]
            if any(min(east, b[2]) > max(west, b[0]) + 1e-9 and
                   min(north, b[3]) > max(south, b[1]) + 1e-9 for b in boxes):
                raise DataError("overlapping source parts need an explicit selection policy")
            boxes.append(part["bbox"])
            source["parts"].append(part)
            if sum(len(raw) for raw in payloads.values()) > max_bytes:
                raise DataError("upload artifacts exceed the configured byte budget")
        sources[role] = source
    manifest = {
        "schema": SCHEMA, "enabled": enabled, "rendererPayloadSHA256": renderer_payload_sha256,
        "targetAPI": "WEBGL2_UPLOAD_CONTRACT_UNVERIFIED",
        "gpuUploadExecuted": False, "gpuRenderingVerified": False,
        "sampling": {"filter": "NEAREST", "texelFetch": True, "unpackAlignment": 1,
                     "flipY": False, "mipmaps": False, "rowOrder": "SOURCE_PRESERVED"},
        "sources": sources, "artifacts": artifacts,
        "artifactBytes": sum(len(raw) for raw in payloads.values()),
        "limits": {"maxTextureSize": max_texture_size, "maxBytes": max_bytes,
                   "meaning": "CPU_PLANNING_LIMIT_NOT_ACTUAL_HARDWARE_CAPABILITY"},
        "coastMask": {"provided": False, "policy": "REQUIRE_CURRENT_NATIVE_GIS_COVERAGE_AND_PROJECTION_BINDING"},
        "composition": {"placement": "BEFORE_OWNERSHIP_FRONTIER_PRESENTATION_UNITS",
                        "baselineFallbackRequired": True, "geometryCameraTimelineChanged": False},
    }
    if len(_encoded_json(manifest)) > MAX_MANIFEST_BYTES:
        raise DataError("upload manifest exceeds its byte limit")
    return manifest, payloads


def export_upload_bundle(results, output_dir, *, renderer_payload_sha256, enabled=True,
                         max_texture_size=16384, max_bytes=DEFAULT_MAX_BYTES):
    """Publish into a new directory only, manifest last; never overwrite outputs.

    Any incomplete directory remains inspectable and cannot be mistaken for a
    successful bundle because the manifest is only written after all artifacts.
    Parent directory must already exist; no source/cache tree is silently made.
    """
    manifest, payloads = build_upload_bundle(
        results, renderer_payload_sha256=renderer_payload_sha256, enabled=enabled,
        max_texture_size=max_texture_size, max_bytes=max_bytes)
    target = Path(output_dir)
    if not target.is_absolute() or target.name in ("", ".", ".."):
        raise DataError("upload output must be an explicit absolute new directory")
    parent_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory_fd = None
    try:
        os.mkdir(target.name, 0o700, dir_fd=parent_fd)
        directory_fd = os.open(target.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        for filename, raw in [*payloads.items(), (MANIFEST_NAME, _encoded_json(manifest))]:
            descriptor = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory_fd)
            with os.fdopen(descriptor, "wb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
        os.fsync(directory_fd)
        os.fsync(parent_fd)
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        os.close(parent_fd)
    return manifest


def prepare_upload_bundle(scene, catalog, output_dir, cache=None, *,
                          max_texture_size=16384, max_bytes=DEFAULT_MAX_BYTES):
    """Reuse existing Scene/provider/cache APIs, retaining the legacy payload.

    This wrapper performs no network operation or GPU activation. Cache policy
    and source licenses/version binding stay owned by the existing CPU layer.
    """
    preparation = prepare_scene(scene, catalog)
    result = CpuDataPipeline(catalog, cache, mode=preparation.cache_policy["mode"]).prepare(preparation)
    return export_upload_bundle(
        result.results, output_dir, renderer_payload_sha256=preparation.renderer_sha256,
        enabled=preparation.enabled, max_texture_size=max_texture_size, max_bytes=max_bytes)
