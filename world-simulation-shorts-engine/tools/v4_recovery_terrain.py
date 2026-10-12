#!/usr/bin/python3
"""Build the admitted V4 native terrain without resampling or replacing sources.

Run with the system Python: GDAL 3.10.3, NumPy 2.2.4, Pillow 11.1.0,
zlib 1.3.1. Network acquisition is opt-in and uses inherited proxy/CA trust.
Existing files are reused only after verification and are never overwritten.
The original input manifest and historical expected hashes remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request
import zlib

import numpy as np
from osgeo import gdal, osr
from PIL import Image
import PIL

NE1_SHA = "b47bdddd1336b07f498c50eba5d70699ec57dd726a7ea0a85d2dca243236c9eb"
NE1_BYTES = 699969932
PINNED_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-raster/f04832c819e7a203d159dffe93cd9245332d6b33/10m_rasters/NE1_HR_LC_SR_W_DR/NE1_HR_LC_SR_W_DR.tif"
CONTEXT_WINDOW = (11222, 1605, 3054, 5065)
CONTEXT_SHA = "6bafd19fd3d74d0786a52cd0f0be41863bf00b9acebf94e56edc4e2532468b4d"
HEIGHT_SHA = "08a1b86fbe9c47a9495336e0e83d0bfdea014a4e5c7b36beaaa544aa283fd5a8"
HEIGHT_BYTES = 207360000
SOURCE_RECORD = "library/flat/terrain/ORIGINAL_SOURCE_RECORD.json"
INPUT_MANIFEST = "recovery/v4/V4-state-records/input-manifest.json"
ORIGINALS = "recovery/v4/past-paths/tmp/world-suez-dem-gate1b/originals"
CANONICAL_COGS = "library/flat/dem/copernicus-glo30/originals"
COG_SHAS = {
    "Copernicus_DSM_COG_10_N29_00_E032_00_DEM.tif": "9dde480c3dc61c80c578026af04ccebfed5496ae911f9aef924c72c38f4642b7",
    "Copernicus_DSM_COG_10_N29_00_E033_00_DEM.tif": "b8db1296d52ede364adcb45285154b094731d483ae438fad1f438038730959c0",
    "Copernicus_DSM_COG_10_N30_00_E032_00_DEM.tif": "624a6d62e87ea02b718efab427859914115f1ad82aaa40eea62705fd9dcc9f5f",
    "Copernicus_DSM_COG_10_N30_00_E033_00_DEM.tif": "67f44f3a5e64ef89d234030bc9c05f2486c5db2a2beb208dda7feca24abb1df8",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def facts(path):
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}


def verify(path, expected_sha, expected_bytes=None):
    require(path.is_file() and not path.is_symlink(), f"Missing regular file: {path}")
    value = facts(path)
    require(value["sha256"] == expected_sha, f"Source SHA mismatch: {path.name}")
    if expected_bytes is not None:
        require(value["bytes"] == expected_bytes, f"Source size mismatch: {path.name}")
    return value


def temporary_for(destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".part", dir=destination.parent)
    os.close(fd)
    return Path(name)


def publish(temp, destination, expected_sha):
    """Link a verified same-filesystem temporary file without replacing a path."""
    require(digest(temp) == expected_sha, "Temporary output SHA changed before publication")
    try:
        os.link(temp, destination)
    except FileExistsError:
        verify(destination, expected_sha, temp.stat().st_size)
    finally:
        temp.unlink(missing_ok=True)
    return facts(destination)


def copy_verified(source, destination, expected_sha, expected_bytes=None):
    verify(source, expected_sha, expected_bytes)
    if destination.exists() or destination.is_symlink():
        return verify(destination, expected_sha, expected_bytes)
    temp = temporary_for(destination)
    try:
        shutil.copyfile(source, temp)
        verify(temp, expected_sha, expected_bytes)
        return publish(temp, destination, expected_sha)
    finally:
        temp.unlink(missing_ok=True)


def near(actual, expected, message, tolerance=1e-10):
    require(len(actual) == len(expected) and all(math.isclose(a, b, rel_tol=0, abs_tol=tolerance) for a, b in zip(actual, expected)), message)


def projection_4326(dataset):
    s = osr.SpatialReference()
    require(bool(dataset.GetProjection()), "Missing raster projection")
    s.ImportFromWkt(dataset.GetProjection())
    s.AutoIdentifyEPSG()
    require(s.GetAuthorityCode(None) == "4326", "Raster CRS is not EPSG:4326")


def acquire_ne1(engine, args, source_record):
    destination = engine / source_record["source_original_file"]
    if destination.exists() or destination.is_symlink():
        return destination, verify(destination, NE1_SHA, NE1_BYTES)
    if args.ne1_source:
        return destination, copy_verified(args.ne1_source, destination, NE1_SHA, NE1_BYTES)
    require(args.download_ne1, "NE1 is absent; supply --ne1-source or opt in with --download-ne1")
    temp = temporary_for(destination)
    try:
        # Default urllib handlers retain inherited HTTP(S) proxy and system CA trust.
        with urllib.request.urlopen(source_record["url"], timeout=60) as response, temp.open("wb") as f:
            require(response.status == 200, "NE1 acquisition did not return HTTP 200")
            require(response.url == PINNED_URL, "Unexpected NE1 download redirect")
            shutil.copyfileobj(response, f, 1024 * 1024)
        verify(temp, NE1_SHA, NE1_BYTES)
        return destination, publish(temp, destination, NE1_SHA)
    finally:
        temp.unlink(missing_ok=True)


def build_context(engine, source_record, context, source_path):
    # World-file and projection provenance are required; GDAL may read these sidecars.
    for key, hash_key in [("world_file", "world_file_sha256"), ("projection_file", "projection_file_sha256")]:
        verify(engine / source_record[key], source_record[hash_key])
    ds = gdal.Open(str(source_path), gdal.GA_ReadOnly)
    require((ds.RasterXSize, ds.RasterYSize, ds.RasterCount) == (21600, 10800, 3), "NE1 dimensions/bands differ")
    projection_4326(ds)
    gt = ds.GetGeoTransform()
    near(gt, [-180, 1 / 60, 0, 90, 0, -1 / 60], "NE1 native grid differs")
    interpretations = [ds.GetRasterBand(n).GetColorInterpretation() for n in (1, 2, 3)]
    require(interpretations == [gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand], "NE1 source bands are not native RGB order")
    require(all(ds.GetRasterBand(n).DataType == gdal.GDT_Byte for n in (1, 2, 3)), "NE1 is not Byte RGB")
    x, y, w, h = CONTEXT_WINDOW
    bounds = [gt[0] + x * gt[1], gt[3] + (y + h) * gt[5], gt[0] + (x + w) * gt[1], gt[3] + y * gt[5]]
    near(bounds, context["bounds"], "Context bounds differ from the historical contract")
    near([gt[1], -gt[5]], context["pixelSpacing"], "Context spacing differs")
    rgb = np.ascontiguousarray(np.moveaxis(ds.ReadAsArray(x, y, w, h), 0, -1))
    require(rgb.shape == (h, w, 3) and rgb.dtype == np.uint8, "Unexpected context native samples")
    pixels_sha = hashlib.sha256(rgb.tobytes(order="C")).hexdigest()
    destination = engine / "web/camera-v4-assets/context-native.png"
    temp = temporary_for(destination)
    try:
        Image.fromarray(rgb).save(temp, format="PNG", compress_level=6, optimize=False)
        with Image.open(temp) as image:
            require(image.mode == "RGB" and image.size == (w, h), "PNG mode/dimensions changed")
            decoded = np.asarray(image)
            require(np.array_equal(decoded, rgb), "PNG decoded pixels differ from native source")
        output = publish(temp, destination, digest(temp))
    finally:
        temp.unlink(missing_ok=True)
    output.update({
        "dimensions": [w, h], "mode": "RGB", "source_window": list(CONTEXT_WINDOW),
        "bounds": bounds, "pixel_spacing": [gt[1], -gt[5]], "source_band_order": "RGB",
        "source_dtype": "uint8", "decoded_pixels_sha256": pixels_sha,
        "native_pixel_equality": True, "different_pixels": 0, "max_channel_difference": 0,
        "historical_expected_sha256": CONTEXT_SHA,
        "historical_byte_hash_match": output["sha256"] == CONTEXT_SHA,
        "status": "BYTE_IDENTICAL_ORIGINAL" if output["sha256"] == CONTEXT_SHA else "NATIVE_PIXEL_EQUIVALENT_NEW_PNG_ENCODING",
        "encoder": {"Pillow": PIL.__version__, "zlib": zlib.ZLIB_RUNTIME_VERSION, "compress_level": 6, "optimize": False, "metadata_chunks_supplied": False},
        "processing": "Native window only; no resize, resampling, color conversion, alpha, sharpening, or synthetic pixels",
    })
    ds = None
    return output


def build_height(engine, height):
    destination = engine / "web/dem/glo30/height.f32"
    temp = temporary_for(destination)
    source_checks = []
    try:
        atlas = np.memmap(temp, dtype="<f4", mode="w+", shape=(7200, 7200), order="C")
        for original in height["originals"]:
            basename = Path(original["file"]).name
            source = engine / CANONICAL_COGS / basename
            value = copy_verified(engine / ORIGINALS / basename, source, original["sha256"])
            ds = gdal.Open(str(source), gdal.GA_ReadOnly)
            require((ds.RasterXSize, ds.RasterYSize, ds.RasterCount) == (3600, 3600, 1), "COG dimensions/bands differ")
            projection_4326(ds)
            band = ds.GetRasterBand(1)
            require(band.DataType == gdal.GDT_Float32, "COG sample type differs")
            scale, offset = band.GetScale(), band.GetOffset()
            require(band.GetNoDataValue() is None and scale in (None, 1) and offset in (None, 0), "COG NoData/scale/offset differs")
            x, y = original["atlasOffset"]
            require((x, y) in ((0, 0), (3600, 0), (0, 3600), (3600, 3600)), "Invalid COG placement")
            expected_gt = [height["footprint"][0] + x / 3600, 1 / 3600, 0, height["footprint"][3] - y / 3600, 0, -1 / 3600]
            near(ds.GetGeoTransform(), expected_gt, "COG grid/placement differs")
            native = band.ReadAsArray()
            require(native.shape == (3600, 3600) and native.dtype == np.float32, "Unexpected native Float32 data")
            require(bool(np.isfinite(native).all()), "COG contains nonfinite samples")
            require(float(native.min()) == original["min"] and float(native.max()) == original["max"], "COG native sample range differs")
            little = np.asarray(native, dtype="<f4", order="C")
            atlas[y:y + 3600, x:x + 3600] = little
            require(np.array_equal(atlas[y:y + 3600, x:x + 3600].view("<u4"), little.view("<u4")), "Height sample bits changed")
            value.update({"atlas_offset_column_row": [x, y], "dimensions": [3600, 3600], "sample_bits_equal_after_placement": True, "finite_samples": int(np.isfinite(native).sum()), "min": float(native.min()), "max": float(native.max()), "geo_transform": list(ds.GetGeoTransform()), "NoData": None, "scale": 1, "offset": 0})
            source_checks.append(value)
            ds = None
        atlas.flush()
        finite_samples = int(np.isfinite(atlas).sum())
        min_value, max_value = float(atlas.min()), float(atlas.max())
        del atlas
        verify(temp, HEIGHT_SHA, HEIGHT_BYTES)
        output = publish(temp, destination, HEIGHT_SHA)
    finally:
        temp.unlink(missing_ok=True)
    output.update({"status": "BYTE_IDENTICAL_ORIGINAL", "historical_expected_sha256": HEIGHT_SHA,
        "dimensions": [7200, 7200], "dtype": "<f4", "order": "C north-up row-major",
        "finite_samples": finite_samples, "min": min_value, "max": max_value,
        "source_cogs": source_checks, "footprint": height["footprint"], "pixel_spacing": height["pixelSpacing"],
        "processing": "Complete native bands, geographic placements, unchanged Float32 samples; no resampling, row flip, header, masking, NoData substitution, scale, offset, or vertical transformation"})
    require(finite_samples == height["validSamples"], "Height finite count differs")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, default=Path(__file__).resolve().parents[1])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--ne1-source", type=Path, help="Already downloaded exact original TIFF")
    source.add_argument("--download-ne1", action="store_true", help="Acquire the pinned original through the inherited proxy and CA trust")
    parser.add_argument("--evidence", type=Path, required=True, help="New JSON evidence file, normally outside the checkout")
    args = parser.parse_args()
    require(not args.evidence.exists(), "Evidence already exists; choose a new path")
    engine = args.engine_root.resolve()
    versions = {"python": sys.version.split()[0], "GDAL": gdal.VersionInfo("RELEASE_NAME"), "NumPy": np.__version__, "Pillow": PIL.__version__, "zlib": zlib.ZLIB_RUNTIME_VERSION}
    require(versions == {"python": "3.13.5", "GDAL": "3.10.3", "NumPy": "2.2.4", "Pillow": "11.1.0", "zlib": "1.3.1"}, "Use the documented pinned system toolchain")
    gdal.UseExceptions()
    gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")
    source_record_path, manifest_path = engine / SOURCE_RECORD, engine / INPUT_MANIFEST
    before = {str(p): facts(p) for p in [source_record_path, manifest_path]}
    source_record = json.loads(source_record_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    context, height = manifest["contextTerrain"], manifest["heightSource"]
    require(source_record["url"] == PINNED_URL and source_record["source_original_sha256"] == NE1_SHA and source_record["source_original_bytes"] == NE1_BYTES, "NE1 provenance record differs")
    require(context["sha256"] == CONTEXT_SHA and tuple(context["lodPreparation"]["window"]) == CONTEXT_WINDOW and context["dimensions"] == [3054, 5065], "Context historical contract differs")
    require(height["sha256"] == HEIGHT_SHA and height["byteLength"] == HEIGHT_BYTES and height["dimensions"] == [7200, 7200] and height["NoData"] is None and height["scale"] == 1 and height["offset"] == 0, "Height historical contract differs")
    require(sorted(tuple(o["atlasOffset"]) for o in height["originals"]) == [(0, 0), (0, 3600), (3600, 0), (3600, 3600)], "COG placement does not cover the atlas exactly once")
    require({Path(o["file"]).name: o["sha256"] for o in height["originals"]} == COG_SHAS, "Original COG identities differ")
    ne1_path, ne1 = acquire_ne1(engine, args, source_record)
    ne1.update({"status": "BYTE_IDENTICAL_ORIGINAL", "pinned_public_source_url": PINNED_URL})
    context_result = build_context(engine, source_record, context, ne1_path)
    height_result = build_height(engine, height)
    require(before == {str(p): facts(p) for p in [source_record_path, manifest_path]}, "Original metadata changed during build")
    result = {"status": "TERRAIN_BUILD_VERIFIED", "toolchain": versions, "source_records_unchanged": before,
        "NE1": ne1, "context": context_result, "height": height_result, "original_expected_hashes_modified": False,
        "fresh_v4_render_executed": False, "camera_or_engine_sources_changed": False}
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    with args.evidence.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps({"status": result["status"], "NE1_sha": ne1["sha256"], "context_status": context_result["status"], "context_sha": context_result["sha256"], "height_sha": height_result["sha256"], "evidence": str(args.evidence)}))


if __name__ == "__main__":
    main()
