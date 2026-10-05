#!/usr/bin/env python3
"""Prepare source-backed, lossless terrain ROI assets without rendering video.

Offline by design: the complete licensed GIS raster must already exist locally.
The original raster and metadata are never modified. Natural Earth shaded relief
is cartographic terrain color, not a survey DEM or current satellite observation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time

from PIL import Image


TOOL_VERSION = "1.0.0"
MAX_SOURCE_PIXELS = 250_000_000
MAX_OUTPUT_DIMENSION = 8192


class TerrainPreparationError(ValueError):
    """A source, geographic request or immutable cache entry is invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _world_file(path: Path) -> tuple[float, float, float, float]:
    try:
        values = [float(line.strip()) for line in path.read_text().splitlines()
                  if line.strip()]
    except (OSError, ValueError) as error:
        raise TerrainPreparationError("INVALID_WORLD_FILE") from error
    if len(values) != 6 or not all(math.isfinite(value) for value in values):
        raise TerrainPreparationError("INVALID_WORLD_FILE")
    x_step, y_rotation, x_rotation, y_step, x_center, y_center = values
    if abs(x_rotation) > 1e-12 or abs(y_rotation) > 1e-12:
        raise TerrainPreparationError("UNSUPPORTED_ROTATED_RASTER")
    if x_step <= 0 or y_step >= 0:
        raise TerrainPreparationError("UNSUPPORTED_RASTER_ORIENTATION")
    return x_step, y_step, x_center - x_step / 2, y_center - y_step / 2


def _projection(path: Path) -> None:
    # Accept the exact verified geographic world-file projection, not Web Mercator.
    value = path.read_text().upper()
    if (not value.lstrip().startswith("GEOGCS[") or "WGS_1984" not in value
            and "WGS 84" not in value or "UNIT[\"DEGREE\"" not in value):
        raise TerrainPreparationError("UNSUPPORTED_PROJECTION_REQUIRE_EPSG_4326")


def _bounds(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    try:
        west, south, east, north = map(float, value)
    except (TypeError, ValueError) as error:
        raise TerrainPreparationError("INVALID_GEOGRAPHIC_BOUNDS") from error
    if not all(math.isfinite(x) for x in (west, south, east, north)):
        raise TerrainPreparationError("INVALID_GEOGRAPHIC_BOUNDS")
    if not (-180 <= west <= 180 and -180 <= east <= 180
            and -90 <= south <= 90 and -90 <= north <= 90):
        raise TerrainPreparationError("INVALID_GEOGRAPHIC_BOUNDS")
    if east <= west:
        raise TerrainPreparationError("UNSUPPORTED_DATELINE_WRAP_OR_EMPTY_BOUNDS")
    if north <= south:
        raise TerrainPreparationError("INVALID_GEOGRAPHIC_BOUNDS")
    # Flat source crops at the poles require a dedicated projection, not stretching.
    if south <= -85 or north >= 85:
        raise TerrainPreparationError("UNSUPPORTED_POLAR_CROP_USE_EARTH_FALLBACK")
    return west, south, east, north


def prepare_flat_terrain(*, source: Path, source_record: dict, world_file: Path,
                         projection_file: Path, license_notice: Path,
                         bounds: tuple[float, float, float, float], cache_dir: Path,
                         max_width: int = 4096, max_height: int = 4096) -> dict:
    """Return an immutable geographic texture cache entry, reusing verified bytes.

    Geographic requests are rounded outwards to native source pixel boundaries.
    Returned geographic_bounds describe those actual pixel edges for shader UVs.
    Output can downsample to the requested cap, but never upscales source detail.
    A mismatched/partial prior cache entry fails without overwriting either file.
    """
    started = time.monotonic()
    source, world_file, projection_file, license_notice, cache_dir = map(
        Path, (source, world_file, projection_file, license_notice, cache_dir))
    requested = _bounds(bounds)
    if (type(max_width) is not int or type(max_height) is not int
            or not 1 <= max_width <= MAX_OUTPUT_DIMENSION
            or not 1 <= max_height <= MAX_OUTPUT_DIMENSION):
        raise TerrainPreparationError("INVALID_OUTPUT_SIZE_LIMIT")
    for path in (source, world_file, projection_file, license_notice):
        if not path.is_file():
            raise TerrainPreparationError("LOCAL_SOURCE_OR_NOTICE_MISSING: " + str(path))
    expected_sha = source_record.get("source_original_sha256", "")
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise TerrainPreparationError("PINNED_SOURCE_SHA256_REQUIRED")
    required = ("url", "author", "license", "source_pinned_commit")
    if any(not isinstance(source_record.get(key), str) or not source_record[key]
           for key in required):
        raise TerrainPreparationError("SOURCE_AND_LICENSE_PROVENANCE_REQUIRED")
    if source_record["license"].strip().upper() in {"UNKNOWN", "UNVERIFIED", "TBD", "NONE"}:
        raise TerrainPreparationError("VERIFIED_LICENSE_REQUIRED")
    if not license_notice.read_text().strip():
        raise TerrainPreparationError("LICENSE_NOTICE_EMPTY")
    if not re.fullmatch(r"[0-9a-f]{40}", source_record["source_pinned_commit"]):
        raise TerrainPreparationError("PINNED_SOURCE_COMMIT_REQUIRED")
    _projection(projection_file)
    x_step, y_step, raster_west, raster_north = _world_file(world_file)
    world_sha, projection_sha, license_sha = [sha256_file(path)
                                            for path in (world_file, projection_file, license_notice)]
    for key, actual in (("world_file_sha256", world_sha),
                        ("projection_file_sha256", projection_sha)):
        if source_record.get(key) != actual:
            raise TerrainPreparationError("SOURCE_GEOREFERENCE_HASH_MISMATCH: " + key)
    stat_before = source.stat()
    hash_started = time.monotonic()
    actual_sha = sha256_file(source)
    hash_seconds = time.monotonic() - hash_started
    if actual_sha != expected_sha:
        raise TerrainPreparationError("SOURCE_SHA256_MISMATCH")
    previous_pixel_limit = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = MAX_SOURCE_PIXELS
        with Image.open(source) as image:
            width, height = image.size
            if width * height > MAX_SOURCE_PIXELS or image.mode != "RGB":
                raise TerrainPreparationError("UNSUPPORTED_SOURCE_SIZE_OR_MODE")
            if list(image.size) != source_record.get("source_original_dimensions"):
                raise TerrainPreparationError("SOURCE_DIMENSION_MISMATCH")
            raster_east = raster_west + width * x_step
            raster_south = raster_north + height * y_step
            west, south, east, north = requested
            tolerance = 1e-7
            if (west < raster_west - tolerance or east > raster_east + tolerance
                    or south < raster_south - tolerance or north > raster_north + tolerance):
                raise TerrainPreparationError("BOUNDS_OUTSIDE_SOURCE_USE_EARTH_FALLBACK")
            box = (max(0, math.floor((west - raster_west) / x_step + tolerance)),
                   max(0, math.floor((raster_north - north) / -y_step + tolerance)),
                   min(width, math.ceil((east - raster_west) / x_step - tolerance)),
                   min(height, math.ceil((raster_north - south) / -y_step - tolerance)))
            crop_width, crop_height = box[2] - box[0], box[3] - box[1]
            if crop_width <= 0 or crop_height <= 0:
                raise TerrainPreparationError("EMPTY_SOURCE_CROP")
            ratio = min(1.0, max_width / crop_width, max_height / crop_height)
            output_size = (max(1, math.floor(crop_width * ratio)),
                           max(1, math.floor(crop_height * ratio)))
            actual_bounds = dict(west=raster_west + box[0] * x_step,
                                 south=raster_north + box[3] * y_step,
                                 east=raster_west + box[2] * x_step,
                                 north=raster_north + box[1] * y_step)
            recipe = {"tool_version": TOOL_VERSION, "source_sha256": actual_sha,
                      "source_dimensions": [width, height],
                      "world_file_sha256": world_sha, "projection_file_sha256": projection_sha,
                      "license_notice_sha256": license_sha,
                      "provenance": {key: source_record[key] for key in required},
                      "requested_bounds": dict(zip(("west", "south", "east", "north"), requested)),
                      "geographic_bounds": actual_bounds, "source_pixel_box": list(box),
                      "output_dimensions": list(output_size),
                      "settings": {"max_width": max_width, "max_height": max_height,
                                   "format": "PNG", "compress_level": 6,
                                   "resampling": "LANCZOS_IF_DOWNSAMPLING", "upscale": False}}
            key = hashlib.sha256(_canonical(recipe)).hexdigest()
            png = cache_dir / ("terrain_" + key + ".png")
            metadata_file = cache_dir / ("terrain_" + key + ".json")
            if png.exists() or metadata_file.exists():
                if not png.is_file() or not metadata_file.is_file():
                    raise TerrainPreparationError("INCOMPLETE_IMMUTABLE_TERRAIN_CACHE")
                try:
                    metadata = json.loads(metadata_file.read_text())
                    if (metadata["cache_key"] != key or metadata["recipe"] != recipe
                            or sha256_file(png) != metadata["sha256"]):
                        raise TerrainPreparationError("TERRAIN_CACHE_METADATA_OR_SHA_MISMATCH")
                    with Image.open(png) as cached:
                        if cached.format != "PNG" or cached.mode != "RGB" or cached.size != output_size:
                            raise TerrainPreparationError("TERRAIN_CACHE_DIMENSION_MISMATCH")
                        cached.verify()
                except (OSError, KeyError, json.JSONDecodeError) as error:
                    raise TerrainPreparationError("INVALID_IMMUTABLE_TERRAIN_CACHE") from error
                return {**metadata, "cache_hit": True,
                        "source_hash_seconds_this_call": hash_seconds,
                        "elapsed_seconds_this_call": time.monotonic() - started}
            cache_dir.mkdir(parents=True, exist_ok=True)
            # Exclusive reservation also prevents races with another asset-prep worker.
            with metadata_file.open("x", encoding="utf-8") as metadata_stream:
                crop = image.crop(box)
                if crop.size != output_size:
                    crop = crop.resize(output_size, Image.Resampling.LANCZOS)
                with png.open("xb") as output:
                    crop.save(output, "PNG", compress_level=6)
                stat_after = source.stat()
                if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
                    raise TerrainPreparationError("SOURCE_CHANGED_DURING_PREPARATION")
                metadata = {"id": "flat-terrain-" + key, "cache_key": key,
                            "file": str(png.resolve()), "sha256": sha256_file(png),
                            "bytes": png.stat().st_size, "recipe": recipe,
                            "geographic_bounds": actual_bounds,
                            "dimensions": list(output_size), "native_crop_dimensions": [crop_width, crop_height],
                            "source_original_sha256": actual_sha,
                            "source_original_dimensions": [width, height],
                            "source_pixel_box": list(box), "url": source_record["url"],
                            "author": source_record["author"], "license": source_record["license"],
                            "license_url": source_record.get("license_url", ""),
                            "attribution_required": source_record.get("attribution_required", True),
                            "download_date": source_record.get("download_date", "local preserved source"),
                            "license_notice": str(license_notice.resolve()),
                            "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
                            "cache_hit": False, "upscaled": False,
                            "preparation_seconds": time.monotonic() - started,
                            "source_hash_seconds": hash_seconds,
                            "limitations": ["Cartographic shaded relief is not a survey DEM",
                                            "A crop is valid only inside its documented geographic bounds",
                                            "No dateline-wrap, polar projection, generated geography or network download"]}
                json.dump(metadata, metadata_stream, ensure_ascii=False, indent=2)
                metadata_stream.write("\n")
            return metadata
    finally:
        Image.MAX_IMAGE_PIXELS = previous_pixel_limit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-record", type=Path, required=True)
    parser.add_argument("--world-file", type=Path, required=True)
    parser.add_argument("--projection-file", type=Path, required=True)
    parser.add_argument("--license-notice", type=Path, required=True)
    parser.add_argument("--bounds", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"), required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--max-width", type=int, default=4096)
    parser.add_argument("--max-height", type=int, default=4096)
    args = vars(parser.parse_args())
    args["source_record"] = json.loads(args["source_record"].read_text())
    try:
        result = prepare_flat_terrain(**args)
    except (TerrainPreparationError, OSError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
