#!/usr/bin/env python3
"""Build native-resolution regional detail from existing public-domain data.

The original MASTER V3 textures remain intact. This tool crops genuine raster
samples without resizing, sharpening, synthetic relief, or color adjustment.
Mask geometry comes from the repository's Natural Earth 1:50m country polygons,
including their interior rings. It is a material land mask, not a border overlay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


APP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = APP_ROOT.parent
RASTER = APP_ROOT / "library/flat/terrain/NE1_HR_LC_SR_W_DR.tif"
COUNTRIES = REPOSITORY_ROOT / "cinematic-world-map/assets/gis/countries_50m.geojson"
PLAN = REPOSITORY_ROOT / "deliverables/WORLD_SIMULATION_ENGINE/SECOND_EVENT_CAMERA_v017/SCENE_PLAN.json"
RASTER_SHA256 = "b47bdddd1336b07f498c50eba5d70699ec57dd726a7ea0a85d2dca243236c9eb"
COUNTRIES_SHA256 = "3e458fc036ad0a66411f2c1e6cac49c5d7bfb81cb1123bc513b22511a2b7fdeb"
NATIVE_RESOLUTION = (21600, 10800)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def native_crop_window(
    lon: float, lat: float, size: tuple[int, int],
    longitude_radius: float = 12, latitude_radius: float = 14,
) -> tuple[tuple[int, int, int, int], list[float]]:
    """Snap crop edges to existing source pixels; return exact geographic bounds.

    Regional tiles crossing the antimeridian need two source windows and are
    deliberately rejected instead of silently wrapping or duplicating pixels.
    The v017 baseline's two event centers do not cross it.
    """
    if not all(math.isfinite(v) for v in (lon, lat, longitude_radius, latitude_radius)):
        raise ValueError("REGIONAL_TILE_COORDINATE_INVALID")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("REGIONAL_TILE_COORDINATE_INVALID")
    if longitude_radius <= 0 or latitude_radius <= 0:
        raise ValueError("REGIONAL_TILE_SPAN_INVALID")
    west, east = lon - longitude_radius, lon + longitude_radius
    south, north = max(-90, lat - latitude_radius), min(90, lat + latitude_radius)
    if west < -180 or east > 180:
        raise ValueError("REGIONAL_TILE_ANTIMERIDIAN_REQUIRES_SPLIT")
    width, height = size
    left = round((west + 180) / 360 * width)
    right = round((east + 180) / 360 * width)
    top = round((90 - north) / 180 * height)
    bottom = round((90 - south) / 180 * height)
    if right <= left or bottom <= top:
        raise ValueError("REGIONAL_TILE_WINDOW_EMPTY")
    bounds = [left / width * 360 - 180, 90 - bottom / height * 180,
              right / width * 360 - 180, 90 - top / height * 180]
    return (left, top, right, bottom), bounds


def unwrap_ring(ring: list, center_lon: float) -> list[tuple[float, float]]:
    """Preserve ring continuity when source geometry crosses +/-180 longitude."""
    if not ring:
        return []
    points = []
    previous = float(ring[0][0])
    for point in ring:
        lon, lat = float(point[0]), float(point[1])
        while lon - previous > 180:
            lon -= 360
        while lon - previous < -180:
            lon += 360
        points.append((lon, lat))
        previous = lon
    middle = (min(p[0] for p in points) + max(p[0] for p in points)) / 2
    shift = 360 * round((center_lon - middle) / 360)
    return [(lon + shift, lat) for lon, lat in points]


def rasterize_land_mask(
    features: list, bounds: list[float], size: tuple[int, int],
) -> tuple[Image.Image, int]:
    """Union true polygon interiors at tile resolution; preserve water holes."""
    west, south, east, north = bounds
    width, height = size
    output = Image.new("L", size, 0)
    count = 0
    center_lon = (west + east) / 2

    def pixels(ring):
        return [((lon - west) / (east - west) * width - .5,
                 (north - lat) / (north - south) * height - .5)
                for lon, lat in ring]

    for feature in features:
        geometry = feature.get("geometry") or {}
        kind = geometry.get("type")
        polygons = [geometry.get("coordinates", [])] if kind == "Polygon" else geometry.get("coordinates", []) if kind == "MultiPolygon" else []
        for polygon in polygons:
            if not polygon:
                continue
            exterior = unwrap_ring(polygon[0], center_lon)
            if len(exterior) < 3:
                continue
            xs, ys = zip(*exterior)
            if max(xs) < west or min(xs) > east or max(ys) < south or min(ys) > north:
                continue
            # A separate mask prevents one country's interior ring from erasing
            # an enclave that is land in another feature's exterior polygon.
            mask = Image.new("L", size, 0)
            draw = ImageDraw.Draw(mask)
            draw.polygon(pixels(exterior), fill=255)
            for interior in polygon[1:]:
                hole = unwrap_ring(interior, center_lon)
                if len(hole) >= 3:
                    draw.polygon(pixels(hole), fill=0)
            output = ImageChops.lighter(output, mask)
            count += 1
    return output, count


def event_centers(plan: dict) -> list[dict]:
    """Read event coordinates generically, without place-name branching."""
    result = []
    seen = set()
    for scene in plan.get("scenes", []):
        config = scene.get("second_event_camera") or {}
        for key, camera in config.items():
            if not key.startswith("event") or not key.endswith("_camera") or not isinstance(camera, dict):
                continue
            lon, lat = float(camera["lon"]), float(camera["lat"])
            if (lon, lat) not in seen:
                result.append({"lon": lon, "lat": lat})
                seen.add((lon, lat))
    if not result:
        raise ValueError("REGIONAL_DETAIL_EVENT_CENTERS_MISSING")
    return result


def build_assets(plan_path: Path, output: Path) -> dict:
    if sha256(RASTER) != RASTER_SHA256:
        raise ValueError("REGIONAL_DETAIL_SOURCE_HASH_MISMATCH")
    if sha256(COUNTRIES) != COUNTRIES_SHA256:
        raise ValueError("REGIONAL_DETAIL_COAST_SOURCE_HASH_MISMATCH")
    # This trusted, SHA-verified raster is larger than Pillow's default threshold.
    Image.MAX_IMAGE_PIXELS = None
    source = Image.open(RASTER)
    if source.size != NATIVE_RESOLUTION or source.mode != "RGB":
        raise ValueError("REGIONAL_DETAIL_NATIVE_SOURCE_FORMAT_MISMATCH")
    features = json.loads(COUNTRIES.read_text())["features"]
    centers = event_centers(json.loads(plan_path.read_text()))
    output.mkdir(parents=True, exist_ok=True)
    textures = []
    for index, center in enumerate(centers):
        region_id = f"detail_{index}"
        window, bounds = native_crop_window(center["lon"], center["lat"], source.size)
        tile = source.crop(window)
        rgb_path = output / f"{region_id}.png"
        tile.save(rgb_path, compress_level=9)
        mask, polygon_count = rasterize_land_mask(features, bounds, tile.size)
        mask_path = output / f"{region_id}_land.png"
        mask.save(mask_path, compress_level=9)
        common = {"region_id": region_id, "width": tile.width, "height": tile.height,
                  "bounds": bounds, "center": center,
                  "source_pixel_window": list(window), "projection": "equirectangular",
                  "orientation": "north_up", "resized": False, "sharpened": False}
        for role, path in [("regional_day_relief", rgb_path), ("regional_land_mask", mask_path)]:
            record = dict(common, id=path.stem, file=f"web/earth-detail/v018/{path.name}",
                          url=f"/static/earth-detail/v018/{path.name}", role=role,
                          sha256=sha256(path), bytes=path.stat().st_size,
                          source_resolution=list(NATIVE_RESOLUTION),
                          source_id="natural_earth_1_native_raster" if role == "regional_day_relief" else "natural_earth_50m_country_polygons")
            if role == "regional_land_mask":
                record.update(source_resolution=None, polygon_count=polygon_count,
                              mask_values={"ocean_or_polygon_hole": 0, "land": 255},
                              geographic_detail="Natural Earth 1:50m coastline; not survey-grade coastline")
            textures.append(record)
    source.close()
    manifest = {"version": "v018", "source": {
        "id": "natural_earth_1_native_raster", "file": "library/flat/terrain/NE1_HR_LC_SR_W_DR.tif",
        "sha256": RASTER_SHA256, "resolution": list(NATIVE_RESOLUTION),
        "license": "Public domain", "url": "https://www.naturalearthdata.com/downloads/10m-raster-data/10m-natural-earth-1/",
        "kind": "Existing Natural Earth shaded relief and land cover cartography; not new DEM or satellite imagery"},
        "coast_source": {"id": "natural_earth_50m_country_polygons", "file": "cinematic-world-map/assets/gis/countries_50m.geojson",
            "sha256": COUNTRIES_SHA256, "license": "Public domain", "scale": "1:50m",
            "url": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson"},
        "plan": {"file": "deliverables/WORLD_SIMULATION_ENGINE/SECOND_EVENT_CAMERA_v017/SCENE_PLAN.json", "sha256": sha256(plan_path),
                 "use": "Coordinates only; camera values and timing are not modified"},
        "generation": {"longitude_radius_degrees": 12, "latitude_radius_degrees": 14,
            "native_texels_per_degree": 60, "resampling": "NONE", "global_master_textures": "UNCHANGED",
            "terrain_dem": "Original 2048x1024 topology retained; this raster adds genuine color/shaded relief detail only",
            "night_texture": "Original 8192x4096 night data retained; no invented higher-resolution light data",
            "antimeridian": "Requested tile crossing +/-180 rejected with explicit split-required error",
            "land_mask": "Polygon interior union with holes, rasterized at regional tile density; no coastline stroke"},
        "textures": textures}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "LICENSE.txt").write_text(
        "Natural Earth raster and vector data are in the public domain.\n"
        "https://www.naturalearthdata.com/about/terms-of-use/\n"
        "These PNG files are native, unresized crops of the existing NE1_HR_LC_SR_W_DR.tif\n"
        "and material land masks derived from the repository's countries_50m.geojson.\n"
        "They do not constitute new satellite imagery, elevation data, or surveyed coastlines.\n"
        "Original data SHA256, geographic bounds, and source pixel windows are in manifest.json.\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--output", type=Path, default=APP_ROOT / "web/earth-detail/v018")
    args = parser.parse_args()
    manifest = build_assets(args.plan, args.output)
    print(json.dumps({"version": manifest["version"], "textures": [{"id": t["id"], "width": t["width"], "height": t["height"], "sha256": t["sha256"]} for t in manifest["textures"]]}, indent=2))


if __name__ == "__main__":
    main()
