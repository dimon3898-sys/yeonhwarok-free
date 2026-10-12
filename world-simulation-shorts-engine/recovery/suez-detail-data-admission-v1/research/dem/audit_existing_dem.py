#!/usr/bin/python3
"""Read-only audit of existing native heights and geometry-derived extents.

No downloads, raster derivatives, interpolation, rendering, Admission changes,
or writes to existing sources. Run with /usr/bin/python3 -B. The generated
candidate extents are research measurements, not certified camera targets.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from osgeo import gdal, osr


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def intersects(a, b):
    return [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]


def contains(a, b):
    return a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]


def coverage(a, b):
    i = intersects(a, b)
    return max(0, i[2] - i[0]) * max(0, i[3] - i[1]) / ((b[2] - b[0]) * (b[3] - b[1]))


def project(point, bounds, output):
    return [(point[0] - bounds[0]) * output[0] / (bounds[2] - bounds[0]),
            (bounds[3] - point[1]) * output[1] / (bounds[3] - bounds[1])]


def length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def segment_inside_fraction(a, b, box):
    # Liang-Barsky, used only to measure original segment coverage.
    lo, hi = 0.0, 1.0
    for axis in (0, 1):
        delta = b[axis] - a[axis]
        if abs(delta) < 1e-15:
            if not box[axis] <= a[axis] <= box[axis + 2]:
                return 0.0
            continue
        first = (box[axis] - a[axis]) / delta
        last = (box[axis + 2] - a[axis]) / delta
        if first > last:
            first, last = last, first
        lo, hi = max(lo, first), min(hi, last)
        if lo >= hi:
            return 0.0
    return max(0.0, hi - lo)


def ground_spacing(lat, spacing):
    # Same WGS84 ellipsoid differential as scale_contract.mjs.
    a, e2 = 6378137, 6.6943799901413165e-3
    phi = math.radians(lat)
    q = 1 - e2 * math.sin(phi) ** 2
    east = a * math.cos(phi) / math.sqrt(q)
    north = a * (1 - e2) / q ** 1.5
    return [east * math.radians(spacing[0]), north * math.radians(spacing[1])]


def measurements(bounds, coordinates, height, output, safe, margin):
    points = [project(p, bounds, output) for p in coordinates]
    box = [min(p[0] for p in points), min(p[1] for p in points),
           max(p[0] for p in points), max(p[1] for p in points)]
    density = [height["pixelSpacing"][0] * output[0] / (bounds[2] - bounds[0]),
               height["pixelSpacing"][1] * output[1] / (bounds[3] - bounds[1])]
    safe_box = [safe[0] + margin, safe[1] + margin, safe[2] - margin, safe[3] - margin]
    current_length = length(points)
    length_inside = sum(math.dist(a, b) * segment_inside_fraction(ga, gb, height["footprint"])
                        for a, b, ga, gb in zip(points, points[1:], coordinates, coordinates[1:]))
    # Existing Renderer.demWeight requires complete real-height neighbourhoods.
    # Quantify its unchanged guard separately from the registered cell footprint.
    step = [max(height["pixelSpacing"][axis], (bounds[axis + 2] - bounds[axis]) / output[axis] * 0.5)
            for axis in (0, 1)]
    sample_box = [height["firstSample"][0],
                  height["firstSample"][1] - height["pixelSpacing"][1] * (height["dimensions"][1] - 1),
                  height["firstSample"][0] + height["pixelSpacing"][0] * (height["dimensions"][0] - 1),
                  height["firstSample"][1]]
    dem_guard = {}
    for name, factor in (("positive_weight", 1.5), ("full_weight", 2.5)):
        guarded_box = [sample_box[0] + factor * step[0], sample_box[1] + factor * step[1],
                       sample_box[2] - factor * step[0], sample_box[3] - factor * step[1]]
        guarded_length = sum(math.dist(a, b) * segment_inside_fraction(ga, gb, guarded_box)
                             for a, b, ga, gb in zip(points, points[1:], coordinates, coordinates[1:]))
        dem_guard[name] = {"bounds": guarded_box, "viewport_area_fraction": coverage(guarded_box, bounds),
                           "axis_projected_length_fraction": guarded_length / current_length}
    center = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2]
    return {
        "bounds": bounds, "center": center,
        "width_degrees": bounds[2] - bounds[0], "height_degrees": bounds[3] - bounds[1],
        "projected_axis_length_pixels": current_length, "projected_axis_bounds_pixels": box,
        "safe_area_geometry_coverage": {
            "width_fraction": (box[2] - box[0]) / (safe[2] - safe[0]),
            "height_fraction": (box[3] - box[1]) / (safe[3] - safe[1])},
        "full_event_geometry_inside_safe_area_with_padding": contains(safe_box, box),
        "dem_projected_pixels_per_native_sample": density,
        "dem_native_spacing_meters_at_extent_center": ground_spacing(center[1], height["pixelSpacing"]),
        "output_ground_spacing_meters_at_extent_center": ground_spacing(center[1], [
            (bounds[2] - bounds[0]) / output[0], (bounds[3] - bounds[1]) / output[1]]),
        "dem_density_pass_unchanged_max_one_pixel_per_sample": max(density) <= 1,
        "dem_extent_coverage_fraction": coverage(height["footprint"], bounds),
        "dem_full_extent_coverage": contains(height["footprint"], bounds),
        "dem_axis_projected_length_coverage_fraction": length_inside / current_length,
        "dem_unchanged_renderer_neighbourhood_guard": {"source": "renderer.mjs demWeight smoothstep(1.5,2.5), demStep=max(nativeSpacing,canonicalPixelDegrees*.5)",
                                                       "step_degrees": step, "regions": dem_guard,
                                                       "measurement_type": "Analytic existing shader support bounds; not a rendered pixel claim"},
        "dem_axis_original_nodes_covered": sum(contains(height["footprint"], [p[0], p[1], p[0], p[1]]) for p in coordinates),
        "dem_northernmost_axis_node_covered": contains(height["footprint"], [coordinates[0][0], coordinates[0][1], coordinates[0][0], coordinates[0][1]]),
        "dem_sampling_resolution_status": "SUFFICIENT" if max(density) <= 1 else "INSUFFICIENT",
        "dem_full_real_relief_status": "SUFFICIENT" if contains(height["footprint"], bounds) and max(density) <= 1 else "INSUFFICIENT_SPATIAL_COVERAGE",
        "certified_safe_detail_extent": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("EXISTING_DEM_AUDIT.json"))
    parser.add_argument("--target-lengths", type=float, nargs="+", default=[350, 550, 800])
    args = parser.parse_args()
    engine = args.engine_root.resolve()
    gdal.UseExceptions()
    gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")
    height_path = engine / "recovery/v4/past-paths/tmp/world-korean-layout-micro/iteration-01/height-source.json"
    fixture_path = engine / "recovery/event-data/suez-full-canal-20261012/fixture.json"
    scene_path = engine / "recovery/v5/inputs/scene.json"
    camera_path = engine / "recovery/v5/inputs/camera-plan.json"
    height = json.loads(height_path.read_text())
    fixture = json.loads(fixture_path.read_text())
    scene = json.loads(scene_path.read_text())
    camera = json.loads(camera_path.read_text())
    coordinates = fixture["intent"]["line"]["geometry"]["coordinates"]
    output = scene["canonical_output"]
    if isinstance(output, dict):
        output = [output["width"], output["height"]]
    safe = scene["safe_area"]
    regional = camera["admission"]["stopBounds"]
    raw_path = engine / "web/dem/glo30/height.f32"
    raw_sha = digest(raw_path)
    assert raw_sha == height["sha256"]
    assert raw_path.stat().st_size == height["byteLength"]
    raw = np.memmap(raw_path, dtype="<f4", mode="r", shape=(height["dimensions"][1], height["dimensions"][0]))
    native = {"path": str(raw_path.relative_to(engine)), "bytes": raw_path.stat().st_size,
              "sha256": raw_sha, "dimensions": height["dimensions"], "dtype": "<f4",
              "finite_samples": int(np.isfinite(raw).sum()), "min_meters": float(raw.min()),
              "max_meters": float(raw.max()), "all_samples_finite": bool(np.isfinite(raw).all())}
    assert native["finite_samples"] == height["validSamples"]
    cog_reports = []
    for original in height["originals"]:
        path = engine / "library/flat/dem/copernicus-glo30/originals" / Path(original["file"]).name
        sha = digest(path)
        assert sha == original["sha256"]
        ds = gdal.Open(str(path), gdal.GA_ReadOnly)
        band = ds.GetRasterBand(1)
        crs = osr.SpatialReference()
        crs.ImportFromWkt(ds.GetProjection())
        crs.AutoIdentifyEPSG()
        array = band.ReadAsArray()
        x, y = original["atlasOffset"]
        bits_equal = np.array_equal(raw[y:y + ds.RasterYSize, x:x + ds.RasterXSize].view("<u4"), array.view("<u4"))
        assert bits_equal and bool(np.isfinite(array).all())
        assert crs.GetAuthorityCode(None) == "4326"
        cog_reports.append({"path": str(path.relative_to(engine)), "sha256": sha,
                            "bytes": path.stat().st_size, "dimensions": [ds.RasterXSize, ds.RasterYSize],
                            "crs": "EPSG:4326", "geo_transform": list(ds.GetGeoTransform()),
                            "band_type": gdal.GetDataTypeName(band.DataType), "NoData": band.GetNoDataValue(),
                            "min_meters": float(array.min()), "max_meters": float(array.max()),
                            "atlas_native_sample_bits_equal": bits_equal})
    geo_box = [min(p[0] for p in coordinates), min(p[1] for p in coordinates),
               max(p[0] for p in coordinates), max(p[1] for p in coordinates)]
    margin = 12  # Generic core/glow reservation margin; no geometry change.
    baseline = measurements(regional, coordinates, height, output, safe, margin)
    aspect = (regional[2] - regional[0]) / (regional[3] - regional[1])
    center = [(geo_box[0] + geo_box[2]) / 2, (geo_box[1] + geo_box[3]) / 2]
    safe_center = [(safe[0] + safe[2]) / 2, (safe[1] + safe[3]) / 2]
    result = []
    for number, target in enumerate(args.target_lengths, start=1):
        scale = baseline["projected_axis_length_pixels"] / target
        w = (regional[2] - regional[0]) * scale
        h = (regional[3] - regional[1]) * scale
        # Fit all source coordinates inside padded safe area; no cropping.
        enlarge = max(1, (geo_box[2] - geo_box[0]) * output[0] / ((safe[2] - safe[0] - 2 * margin) * w),
                      (geo_box[3] - geo_box[1]) * output[1] / ((safe[3] - safe[1] - 2 * margin) * h))
        w, h = w * enlarge, h * enlarge
        cx = center[0] - (safe_center[0] / output[0] - 0.5) * w
        cy = center[1] + (safe_center[1] / output[1] - 0.5) * h
        bounds = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        measure = measurements(bounds, coordinates, height, output, safe, margin)
        measure.update({"id": f"D{number}", "requested_axis_length_pixels": target,
                        "construction": "Full unchanged axis bounds, inherited regional aspect, safe-area-centered projection, target screen length; enlargement only if full-axis padding requires it",
                        "inherited_geographic_aspect": aspect})
        result.append(measure)
    report = {
        "schema": "DETAIL_EXISTING_DEM_AUDIT_V1", "audit_time_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Existing GLO-30 only; no data download or derivative generation",
        "toolchain": {"python": sys.version.split()[0], "numpy": np.__version__, "gdal": gdal.VersionInfo("RELEASE_NAME")},
        "inputs": [{"path": str(p.relative_to(engine)), "sha256": digest(p)} for p in (height_path, fixture_path, scene_path, camera_path)],
        "axis": {"original_coordinates": len(coordinates), "original_segments": len(coordinates) - 1,
                 "geographic_bounds": geo_box, "coordinates_interpolated": False, "coordinates_modified": False},
        "registered_height_contract": height, "actual_native_height": native, "actual_cogs": cog_reports,
        "source_provenance_limitations": {"source": height["source"], "license_record_in_registered_height_metadata": None,
                                           "original_retrieval_date_in_registered_height_metadata": None,
                                           "product_convention": "Copernicus GLO-30 DSM, meter units, EGM2008 vertical datum, one arc-second geographic spacing",
                                           "new_source_license_verified_this_audit": False},
        "baseline": baseline, "research_candidates": result,
        "conclusion": {
            "native_resolution": "EXISTING_SUFFICIENT_FOR_ALL_RESEARCH_CANDIDATES",
            "full_real_dem_spatial_coverage": "INSUFFICIENT_FOR_ALL_RESEARCH_CANDIDATES",
            "full_detail_relief_if_mandatory": "NEW_DATA_REQUIRED",
            "if_real_dem_is_optional": "EXISTING_PARTIAL_DEM_WITH_NATIVE_TERRAIN_FALLBACK; no DEM download required merely for sampling resolution",
            "unchanged_admission_semantics": "LocalDetailAdmission.dem remains INSUFFICIENT; requireRealDEM=true blocks partial coverage. If requireRealDEM=false, partial DEM is explicitly optional, but terrain/GIS/event checks must all pass independently.",
            "cannot_claim": "Unqualified DEM_EXISTING_SUFFICIENT for whole detail extent, or full real DEM coverage of entire canal",
            "automatic_new_dem_download": False,
            "admission_override": False,
        }}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "native_sha256": raw_sha,
                      "baseline_length_pixels": baseline["projected_axis_length_pixels"],
                      "candidates": [{k: c[k] for k in ("id", "bounds", "projected_axis_length_pixels", "dem_projected_pixels_per_native_sample", "dem_extent_coverage_fraction", "dem_axis_projected_length_coverage_fraction")} for c in result],
                      "conclusion": report["conclusion"]}, indent=2))


if __name__ == "__main__":
    main()
