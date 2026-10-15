"""Focused CPU bridge tests; fake data and supplied real data are separated."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from upload_bundle import (MANIFEST_NAME, build_upload_bundle, export_upload_bundle,
                           prepare_upload_bundle)
from astra_cpu.model import DataError, RasterData, sha256
from astra_cpu.providers import ArchiveCatalog, ProviderResult
from astra_cpu.scene import renderer_fingerprint

SOURCE_SHA = sha256(b"synthetic source bytes, not an actual supplier download")
RENDERER_SHA = sha256(b"unchanged synthetic legacy scene")


def raster(role="terrain", *, values=None, valid=None, transform=None, crs="EPSG:4326"):
    if values is None:
        values = {"terrain": np.array([[4.25, 6.5], [1.25, 3.5]], dtype=np.float32),
                  "bathymetry": np.array([[-13, 9], [-1, -125]], dtype=np.int16),
                  "surfaceTexture": np.array([[[255, 0, 12, 255], [1, 23, 45, 255]],
                                               [[65, 43, 21, 255], [18, 19, 20, 255]]], dtype=np.uint8)}[role]
    values = np.asarray(values)
    rows, columns = values.shape[:2]
    transform = transform or [12, .25, 0, -20, 0, -.25]
    metadata = {"transform": transform, "crs": crs, "units": "m" if role != "surfaceTexture" else "uint8_encoded_color",
                "inputSha256": SOURCE_SHA, "nodata": None, "pixelRegistration": "Point",
                "rowOrder": "NORTH_TO_SOUTH" if transform[5] < 0 else "SOUTH_TO_NORTH"}
    if role == "bathymetry":
        metadata.update(quantity="SIGNED_ELEVATION", positive="up", oceanMaskStatus="UNRESOLVED")
    if role == "surfaceTexture":
        metadata.update(colorConversion="NONE")
    return RasterData(values, transform[0] + (np.arange(columns) + .5) * transform[1],
                      transform[3] + (np.arange(rows) + .5) * transform[5],
                      np.ones((rows, columns), dtype=np.bool_) if valid is None else valid, metadata)


def result(role="terrain", *, item=None, status="available", complete=True):
    item = raster(role) if item is None else item
    return ProviderResult(status, "synthetic-" + role, "test-version-1", "https://example.invalid/pinned-source",
                          list(item.bbox), item.metadata["crs"], {"spacingDegrees": [.25, .25]},
                          [{"dimensions": [len(item.x), len(item.y)]}], "TEST_DECLARED_DATUM", None,
                          "Synthetic fixture; not source data", SOURCE_SHA,
                          None if status == "available" else {"code": "NO_SOURCE_COVERAGE"},
                          (item,), () if complete else ("PARTIAL_SOURCE_COVERAGE_NO_PADDING_OR_EXTRAPOLATION",),
                          {"complete": complete, "paddingApplied": False, "requestedBBox": [10, -25, 15, -15]})


class UploadBundleSyntheticTests(unittest.TestCase):
    def build(self, sources, **kwargs):
        return build_upload_bundle(sources, renderer_payload_sha256=RENDERER_SHA, **kwargs)

    def test_float32_nan_payload_signed_zero_and_original_bytes_preserved(self):
        bits = np.array([[0x7FC12345, 0xFFC54321], [0x80000000, 0x3FA00000]], dtype=np.uint32)
        item = raster(values=bits.view(np.float32), valid=np.array([[False, False], [True, True]]))
        item.metadata["nodata"] = float("nan")
        original = item.values.tobytes()
        manifest, files = self.build({"terrain": result(item=item)})
        part = manifest["sources"]["terrain"]["parts"][0]
        self.assertEqual(files[part["values"]["file"]], original)
        np.testing.assert_array_equal(np.frombuffer(files[part["values"]["file"]], dtype="<u4"), bits.reshape(-1))
        self.assertEqual(files[part["valid"]["file"]], bytes([0, 0, 1, 1]))
        self.assertEqual(part["metadata"]["nodata"], {"__numeric_metadata__": "NaN"})
        self.assertEqual(item.values.tobytes(), original)

    def test_byte_swap_only_preserves_big_endian_int16_signed_samples(self):
        item = raster("bathymetry", values=np.array([[-2000, -1], [4, 123]], dtype=">i2"))
        manifest, files = self.build({"bathymetry": result("bathymetry", item=item)})
        part = manifest["sources"]["bathymetry"]["parts"][0]
        self.assertEqual(part["sourceDtype"], ">i2")
        self.assertEqual(part["byteOrderConversion"], "BYTE_SWAP_ONLY")
        np.testing.assert_array_equal(np.frombuffer(files[part["values"]["file"]], dtype="<i2").reshape(2, 2), item.values)

    def test_ascending_latitude_and_point_half_pixel_registration_are_not_shifted(self):
        item = raster("bathymetry", transform=[-64, .25, 0, -38, 0, .25])
        manifest, files = self.build({"bathymetry": result("bathymetry", item=item)})
        part = manifest["sources"]["bathymetry"]["parts"][0]
        self.assertEqual(part["rowOrder"], "SOUTH_TO_NORTH")
        self.assertEqual(part["coordinatesMeaning"], "PIXEL_CENTERS")
        self.assertEqual(part["transformMeaning"], "GDAL_PIXEL_CORNER")
        np.testing.assert_array_equal(np.frombuffer(files[part["x"]["file"]], dtype="<f8"), [-63.875, -63.625])
        np.testing.assert_array_equal(np.frombuffer(files[part["y"]["file"]], dtype="<f8"), [-37.875, -37.625])
        self.assertEqual(part["transform"], [-64, .25, 0, -38, 0, .25])
        self.assertEqual(files[part["values"]["file"]], item.values.tobytes())

    def test_bathymetry_is_not_mislabelled_as_depth_or_negative_land_as_ocean(self):
        manifest, files = self.build({"bathymetry": result("bathymetry")})
        part = manifest["sources"]["bathymetry"]["parts"][0]
        self.assertEqual(part["quantity"], "SIGNED_ELEVATION")
        self.assertEqual(part["format"]["internalFormat"], "R16I")
        self.assertTrue(part["requiresOceanMask"])
        self.assertFalse(manifest["coastMask"]["provided"])
        self.assertEqual(files[part["values"]["file"]], raster("bathymetry").values.tobytes())
        with self.assertRaisesRegex(DataError, "signed elevation"):
            changed = raster("bathymetry")
            changed.metadata["quantity"] = "DERIVED_OCEAN_DEPTH"
            self.build({"bathymetry": result("bathymetry", item=changed)})

    def test_partial_coverage_preserves_explicit_fallback_and_original_support(self):
        source = result(complete=False)
        manifest, _ = self.build({"terrain": source})
        saved = manifest["sources"]["terrain"]
        self.assertFalse(saved["coverage"]["complete"])
        self.assertEqual(saved["warnings"], list(source.warnings))
        self.assertFalse(saved["coverage"]["paddingApplied"])
        self.assertEqual(saved["parts"][0]["fallback"], "UNCHANGED_BASELINE_OUTSIDE_SOURCE_OR_INVALID")

    def test_unavailable_region_or_nodata_only_result_never_exports_values(self):
        source = result(status="unavailable")
        manifest, files = self.build({"terrain": source})
        self.assertEqual(files, {})
        self.assertEqual(manifest["sources"]["terrain"]["status"], "unavailable")
        self.assertEqual(manifest["sources"]["terrain"]["parts"], [])
        self.assertEqual(manifest["sources"]["terrain"]["error"], {"code": "NO_SOURCE_COVERAGE"})

    def test_rgba_bytes_metadata_and_separate_mask_are_preserved(self):
        item = raster("surfaceTexture")
        item.metadata["colorInfo"] = {"icc_profile": None, "declaredSRGB": False}
        manifest, files = self.build({"surfaceTexture": result("surfaceTexture", item=item)})
        part = manifest["sources"]["surfaceTexture"]["parts"][0]
        self.assertEqual(files[part["values"]["file"]], item.values.tobytes())
        self.assertEqual(part["format"]["internalFormat"], "RGBA8")
        self.assertEqual(part["metadata"]["colorInfo"], item.metadata["colorInfo"])
        self.assertEqual(part["valid"]["format"]["internalFormat"], "R8UI")
        self.assertFalse(manifest["gpuUploadExecuted"])
        self.assertFalse(manifest["gpuRenderingVerified"])

    def test_unsupported_crs_precision_role_and_rgb_fail_explicitly(self):
        cases = [({"terrain": result(item=raster(crs="EPSG:3857"))}, "CRS"),
                 ({"terrain": result(item=raster(values=np.ones((2, 2), dtype=np.float64)))}, "Float32"),
                 ({"bathymetry": result("bathymetry", item=raster("bathymetry", values=np.ones((2, 2), dtype=np.uint16)))}, "Int16"),
                 ({"surfaceTexture": result("surfaceTexture", item=raster("surfaceTexture", values=np.zeros((2, 2, 3), dtype=np.uint8)))}, "RGBA8"),
                 ({"unsupported": result()}, "roles")]
        for sources, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(DataError, message):
                self.build(sources)

    def test_mismatched_source_hash_mutated_transform_and_overlapping_parts_rejected(self):
        item = raster()
        item.metadata["inputSha256"] = "0" * 64
        with self.assertRaisesRegex(DataError, "input SHA"):
            self.build({"terrain": result(item=item)})
        changed = raster()
        changed.metadata["transform"][0] += .125
        with self.assertRaisesRegex(DataError, "axes"):
            self.build({"terrain": result(item=changed)})
        source = result()
        with self.assertRaisesRegex(DataError, "overlapping"):
            self.build({"terrain": replace(source, rasters=(source.rasters[0], source.rasters[0]))})

    def test_limits_reject_before_publication_and_do_not_claim_device_capability(self):
        for options in ({"max_bytes": 1}, {"max_texture_size": 1}, {"max_bytes": True}, {"max_texture_size": 0}):
            with self.subTest(options=options), self.assertRaises(DataError):
                self.build({"terrain": result()}, **options)
        manifest, _ = self.build({"terrain": result()})
        self.assertIn("NOT_ACTUAL_HARDWARE", manifest["limits"]["meaning"])

    def test_every_payload_hash_length_and_total_are_bound(self):
        manifest, files = self.build({role: result(role) for role in ("terrain", "bathymetry", "surfaceTexture")})
        self.assertEqual(manifest["artifactBytes"], sum(len(data) for data in files.values()))
        self.assertEqual(len(manifest["artifacts"]), 12)
        for item in manifest["artifacts"]:
            self.assertEqual(item["bytes"], len(files[item["file"]]))
            self.assertEqual(item["sha256"], sha256(files[item["file"]]))
            self.assertNotIn("/", item["file"])
        self.assertEqual(manifest["sampling"], {"filter": "NEAREST", "texelFetch": True, "unpackAlignment": 1,
                                                 "flipY": False, "mipmaps": False, "rowOrder": "SOURCE_PRESERVED"})

    def test_exclusive_output_manifest_last_and_existing_results_preserved(self):
        with tempfile.TemporaryDirectory(prefix="astra-upload-test-", dir="/workspace") as temporary:
            output = Path(temporary) / "new-bundle"
            manifest = export_upload_bundle({"terrain": result()}, output, renderer_payload_sha256=RENDERER_SHA)
            files = {item.name: item.read_bytes() for item in output.iterdir()}
            self.assertEqual(json.loads(files[MANIFEST_NAME]), manifest)
            with self.assertRaises(FileExistsError):
                export_upload_bundle({"terrain": result()}, output, renderer_payload_sha256=RENDERER_SHA)
            self.assertEqual(files, {item.name: item.read_bytes() for item in output.iterdir()})
            alias = Path(temporary) / "output-alias"
            alias.symlink_to(output, target_is_directory=True)
            with self.assertRaises(FileExistsError):
                export_upload_bundle({"terrain": result()}, alias, renderer_payload_sha256=RENDERER_SHA)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all((output / name).stat().st_mode & 0o777 == 0o600 for name in files))

    def test_failed_write_keeps_partial_files_without_success_manifest(self):
        with tempfile.TemporaryDirectory(prefix="astra-upload-write-", dir="/workspace") as temporary:
            output = Path(temporary) / "interrupted"
            with patch("upload_bundle.os.fsync", side_effect=OSError("simulated disk failure")):
                with self.assertRaises(OSError):
                    export_upload_bundle({"terrain": result()}, output, renderer_payload_sha256=RENDERER_SHA)
            self.assertTrue(output.exists())
            self.assertFalse((output / MANIFEST_NAME).exists())

    def test_disabled_legacy_scene_preserves_payload_without_catalog_lookup(self):
        scene = {"schema": "UNCHANGED_LEGACY", "camera": {"bounds": [-55, -20, -50, -15]}, "timeline": [1, 2, 3]}
        before = deepcopy(scene)
        with tempfile.TemporaryDirectory(prefix="astra-upload-disabled-", dir="/workspace") as temporary:
            manifest = prepare_upload_bundle(scene, None, Path(temporary) / "bundle")
        self.assertEqual(scene, before)
        self.assertEqual(manifest["rendererPayloadSHA256"], renderer_fingerprint(scene))
        self.assertFalse(manifest["enabled"])
        self.assertEqual(manifest["sources"], {})


class UploadBundleSuppliedRealDataTests(unittest.TestCase):
    def test_scene_wrapper_reuses_all_three_providers_without_changing_renderer_payload(self):
        cpu_root = ROOT.parent / "astra-cpu-data-v1"
        archive = ROOT.parent / "astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip"
        catalog = ArchiveCatalog(archive, license_verified=True)
        scene = json.loads((cpu_root / "fixtures/LOCAL_DATA_SCENE.json").read_bytes())
        before = deepcopy(scene)
        legacy = deepcopy(scene)
        legacy.pop("mapData")
        with tempfile.TemporaryDirectory(prefix="astra-upload-real-", dir="/workspace") as temporary:
            output = Path(temporary) / "bundle"
            manifest = prepare_upload_bundle(scene, catalog, output)
            self.assertEqual(scene, before)
            self.assertEqual(manifest["rendererPayloadSHA256"], renderer_fingerprint(legacy))
            self.assertEqual(set(manifest["sources"]), {"terrain", "bathymetry", "surfaceTexture"})
            for role, source in manifest["sources"].items():
                self.assertEqual(source["status"], "available")
                part = source["parts"][0]
                self.assertEqual(part["metadata"]["inputSha256"], source["SHA-256"])
                self.assertTrue(part["requiresNativeGISCoverage"])
                self.assertEqual(part["format"]["internalFormat"], {"terrain": "R32F", "bathymetry": "R16I", "surfaceTexture": "RGBA8"}[role])
                for key in ("values", "valid", "x", "y"):
                    reference = part[key]
                    raw = (output / reference["file"]).read_bytes()
                    self.assertEqual(sha256(raw), reference["sha256"])
            self.assertFalse(manifest["gpuUploadExecuted"])


class UploadBundlePythonNodeContractTests(unittest.TestCase):
    """Use actual Python-produced files; the Node consumer never opens WebGL."""
    def crosscheck(self, sources, **options):
        with tempfile.TemporaryDirectory(prefix="astra-python-node-", dir="/workspace") as temporary:
            output = Path(temporary) / "bundle"
            manifest = export_upload_bundle(sources, output, renderer_payload_sha256=RENDERER_SHA, **options)
            raw = (output / MANIFEST_NAME).read_bytes()
            completed = subprocess.run(["node", str(ROOT / "crosscheck_bundle.mjs"), str(output), sha256(raw)],
                                       check=False, capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            response = json.loads(completed.stdout)
            self.assertEqual(response["status"], "PASS")
            self.assertTrue(response["cpuOnly"])
            self.assertFalse(response["gpuExecuted"])
            self.assertFalse(response["networkExecuted"])
            self.assertEqual(response["manifestSha256"], sha256(raw))
            self.assertEqual(response["roles"], sorted(sources))
            return manifest, len(raw)

    def test_python_big_endian_payloads_and_ascending_southern_latitude_reach_node(self):
        bits = np.array([[0x7FC12345, 0x80000000], [0x3F800000, 0xFFC54321]], dtype="<u4")
        # byteswap changes byte order only and retains both distinct NaN payloads.
        heights = bits.view("<f4").astype(">f4", casting="equiv")
        height = raster(values=heights, valid=np.array([[False, True], [True, False]]),
                        transform=[-64, .25, 0, -38, 0, .25])
        elevation = raster("bathymetry", values=np.array([[-2124, 151], [-25, -1]], dtype=">i2"),
                           transform=[-64, .25, 0, -38, 0, .25])
        manifest, _ = self.crosscheck({"terrain": result(item=height),
                                      "bathymetry": result("bathymetry", item=elevation)})
        for role in ("terrain", "bathymetry"):
            part = manifest["sources"][role]["parts"][0]
            self.assertEqual(part["byteOrderConversion"], "BYTE_SWAP_ONLY")
            self.assertEqual(part["rowOrder"], "SOUTH_TO_NORTH")

    def test_python_configured_texture_width_above_16384_reaches_node(self):
        item = raster(values=np.ones((1, 16385), dtype=np.float32), transform=[-64, .001, 0, -38, 0, .25])
        manifest, _ = self.crosscheck({"terrain": result(item=item)}, max_texture_size=32768)
        self.assertEqual(manifest["sources"]["terrain"]["parts"][0]["dimensions"], [16385, 1])

    def test_python_manifest_above_one_mib_and_below_two_mib_reaches_node(self):
        item = raster()
        item.metadata["preservedProviderAnnotation"] = "A" * (1024 * 1024)
        _, length = self.crosscheck({"terrain": result(item=item)})
        self.assertGreater(length, 1024 * 1024)
        self.assertLess(length, 2 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
