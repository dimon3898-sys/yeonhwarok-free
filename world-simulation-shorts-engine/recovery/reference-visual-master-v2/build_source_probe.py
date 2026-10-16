"""Bounded synthetic CPU recipe for the explicit software source-grade probe.

Uses the existing ASTRA models and upload producer; no provider acquisition,
network, supplier raster, interpolation, renderer, or GPU code is implemented.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "astra-cpu-data-v1"))
sys.path.insert(0, str(HERE.parent / "astra-gpu-integration-v1"))
from astra_cpu.model import RasterData
from astra_cpu.providers import ProviderResult
from upload_bundle import export_upload_bundle, MANIFEST_NAME


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture_sources():
    size, step, west, south = 64, .0001, 10., 20.
    sources = {}
    for role in ("terrain", "bathymetry", "surfaceTexture"):
        north_up = role != "bathymetry"
        transform = [west, step, 0, south + size * step if north_up else south, 0, -step if north_up else step]
        x = west + (np.arange(size) + .5) * step
        y = transform[3] + (np.arange(size) + .5) * transform[5]
        u, v = np.meshgrid((x - west) / (size * step), (y - south) / (size * step))
        hole = (u > .4) & (u < .6) & (v > .4) & (v < .6)
        valid = ~hole
        metadata = {"transform": transform, "crs": "EPSG:4326", "pixelRegistration": "Point",
                    "rowOrder": "NORTH_TO_SOUTH" if north_up else "SOUTH_TO_NORTH",
                    "verticalDatum": "SYNTHETIC_TEST_DATUM_NOT_SUPPLIER_DATA"}
        if role == "terrain":
            values = np.full((size, size), 420., dtype=np.float32)
            values[(u < .4) & (v < .4)] = -30.
            values[hole] = np.nan
            metadata.update(units="m", nodata=float("nan"))
        elif role == "bathymetry":
            values = np.full((size, size), -300, dtype=np.int16)
            values[(u > .6) & (v < .4)] = 12
            values[hole] = -32767
            metadata.update(units="m", nodata=-32767, quantity="SIGNED_ELEVATION", positive="up", pixelRegistration="CELL_CENTER")
        else:
            values = np.empty((size, size, 4), dtype=np.uint8)
            values[:] = [70, 95, 50, 255]
            values[hole, 3] = 0
            metadata.update(units="uint8_encoded_color", nodata=None, colorConversion="NONE",
                            colorSpace="SYNTHETIC_ENCODED_RGBA_BYTES")
        raw_sha = sha(values.tobytes())
        metadata["inputSha256"] = raw_sha
        raster = RasterData(values, x, y, valid, metadata)
        sources[role] = ProviderResult("available", "synthetic-source-grade-" + role, "software-probe-v2",
            "https://example.invalid/synthetic-source-grade/" + role, list(raster.bbox), "EPSG:4326",
            {"spacingDegrees": [step, step]}, [{"dimensions": [size, size]}],
            metadata["verticalDatum"], metadata["nodata"], "EXPLICIT SYNTHETIC TEST FIXTURE; NO SUPPLIER DATA",
            raw_sha, None, (raster,), (), {"complete": False, "paddingApplied": False})
    return sources, {"schema": "REFERENCE_SOURCE_GRADE_SYNTHETIC_FIXTURE_V2", "testOnly": True,
        "sourceClassification": "SYNTHETIC_TEST_NOT_REAL_WORLD_DATA", "sourceBounds": [west, south, west + size * step, south + size * step],
        "cameraBounds": [west - .001, south - .001, west + size * step + .001, south + size * step + .001],
        "dimensions": [1080, 1920], "oceanTint": [33 / 255, 90 / 255, 104 / 255],
        "points": {"outside": [west - .0006, south + .002], "noData": [west + .0032, south + .0032],
                   "negativeDemLand": [west + .0016, south + .0016], "positiveGebcoOcean": [west + .0048, south + .0016],
                   "validLand": [west + .0016, south + .0048], "validOcean": [west + .0048, south + .0048]},
        "nvidiaHardwareVerified": False, "videoQualityApproved": False}


def build(output):
    sources, fixture = fixture_sources()
    manifest = export_upload_bundle(sources, output, renderer_payload_sha256=sha(b"EXPLICIT_SOURCE_GRADE_SYNTHETIC_PROBE_V2"),
                                    max_texture_size=128, max_bytes=1024 * 1024)
    target = Path(output)
    fixture["manifestSha256"] = sha((target / MANIFEST_NAME).read_bytes())
    descriptor = target / "SOURCE_PROBE.json"
    descriptor.write_bytes((json.dumps(fixture, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())
    descriptor.chmod(0o600)
    names = [MANIFEST_NAME, "SOURCE_PROBE.json", *[item["file"] for item in manifest["artifacts"]]]
    bindings = [{"name": name, "bytes": (target / name).stat().st_size, "sha256": sha((target / name).read_bytes())} for name in names]
    return {"schema": "REFERENCE_SOURCE_PROBE_BINDINGS_V2", "directory": str(target), "manifestSHA256": fixture["manifestSha256"],
            "fixtureSHA256": sha(descriptor.read_bytes()), "testOnly": True, "externalDownloadExecuted": False, "bindings": bindings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output), sort_keys=True))
