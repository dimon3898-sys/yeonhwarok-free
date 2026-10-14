"""Terrain byte parsing, source fidelity and unsupported-input boundaries."""
import json
import math
from pathlib import Path
import unittest
import uuid
import zipfile

import numpy as np
from osgeo import gdal, osr

from astra_cpu.model import DataError, sha256
from astra_cpu.terrain import parse_terrain


def tiff_bytes(values, *, transform=(20, .5, 0, 10, 0, -.5),
               crs="EPSG:4326", registration="Point", nodata=None,
               data_type=gdal.GDT_Float32, unit=None, scale=None, offset=None,
               mask=None, metadata=None, bands=1):
    """Create standalone synthetic TIFF bytes, including optional internal mask."""
    values = np.asarray(values)
    path = f"/vsimem/astra-terrain-test-{uuid.uuid4().hex}.tif"
    dataset = band = None
    try:
        with gdal.ExceptionMgr(), osr.ExceptionMgr(), gdal.config_option("GDAL_TIFF_INTERNAL_MASK", "YES"):
            dataset = gdal.GetDriverByName("GTiff").Create(
                path, values.shape[1], values.shape[0], bands, data_type)
            if transform is not None:
                dataset.SetGeoTransform(transform)
            if crs is not None:
                reference = osr.SpatialReference()
                reference.SetFromUserInput(crs)
                dataset.SetSpatialRef(reference)
            if registration is not None:
                dataset.SetMetadataItem("AREA_OR_POINT", registration)
            for key, value in (metadata or {}).items():
                dataset.SetMetadataItem(key, value)
            band = dataset.GetRasterBand(1)
            band.WriteArray(values)
            if nodata is not None:
                band.SetNoDataValue(nodata)
            if unit is not None:
                band.SetUnitType(unit)
            if scale is not None:
                band.SetScale(scale)
            if offset is not None:
                band.SetOffset(offset)
            if mask is not None:
                band.CreateMaskBand(gdal.GMF_PER_DATASET)
                band.GetMaskBand().WriteArray(np.asarray(mask, dtype=np.uint8) * 255)
            band = dataset = None
            return bytes(gdal.VSIGetMemFileBuffer_unsafe(path))
    finally:
        band = dataset = None
        gdal.Unlink(path)
        gdal.Unlink(path + ".msk")


class SyntheticTerrainTests(unittest.TestCase):
    def test_point_and_area_centers_use_gdal_corner_without_second_shift(self):
        values = np.array([[11.25, -2], [34.5, 67.75]], dtype=np.float32)
        transform = (-71.125, .25, 0, 41.125, 0, -.25)
        for registration in ("Point", "Area"):
            with self.subTest(registration=registration):
                raster = parse_terrain(tiff_bytes(values, transform=transform, registration=registration))
                np.testing.assert_array_equal(raster.values, values)
                np.testing.assert_array_equal(raster.x, [-71, -70.75])
                np.testing.assert_array_equal(raster.y, [41, 40.75])
                self.assertEqual(raster.metadata["transform"], list(transform))
                self.assertEqual(raster.metadata["pixelRegistration"], registration)
                self.assertEqual(raster.metadata["units"], "m")
                self.assertIsNone(raster.metadata["sourceUnit"])
                self.assertIsNone(raster.metadata["verticalDatum"])
                self.assertEqual(raster.metadata["verticalDatumSource"], "UNDECLARED")

    def test_nodata_nan_infinity_zero_and_negative_values_are_retained(self):
        values = np.array([[0, -7.5, -9999], [np.nan, np.inf, -np.inf]], dtype=np.float32)
        raster = parse_terrain(tiff_bytes(values, nodata=-9999, unit="m"))
        np.testing.assert_array_equal(raster.values, values)
        np.testing.assert_array_equal(raster.valid, [[True, True, False], [False, False, False]])
        self.assertEqual(raster.values.dtype, np.dtype(np.float32))
        self.assertEqual(raster.metadata["nodata"], -9999)
        self.assertEqual(raster.metadata["sourceUnit"], "m")
        self.assertFalse(raster.values.flags.writeable)
        self.assertFalse(raster.valid.flags.writeable)

    def test_point_georeferencing_uses_spec_even_when_legacy_ignore_option_is_set(self):
        transform = (-71.125, .25, 0, 41.125, 0, -.25)
        data = tiff_bytes([[1, 2]], transform=transform, registration="Point")
        with gdal.config_option("GTIFF_POINT_GEO_IGNORE", "YES"):
            raster = parse_terrain(data)
            self.assertEqual(gdal.GetConfigOption("GTIFF_POINT_GEO_IGNORE"), "YES")
        self.assertEqual(raster.metadata["transform"], list(transform))
        np.testing.assert_array_equal(raster.x, [-71, -70.75])
        np.testing.assert_array_equal(raster.y, [41])

    def test_declared_nan_nodata_remains_nan(self):
        values = np.array([[np.nan, 0, 2.5]], dtype=np.float32)
        raster = parse_terrain(tiff_bytes(values, nodata=np.nan))
        self.assertTrue(math.isnan(raster.metadata["nodata"]))
        self.assertTrue(math.isnan(raster.values[0, 0]))
        np.testing.assert_array_equal(raster.valid, [[False, True, True]])

    def test_internal_support_mask_is_independent_of_values(self):
        values = np.array([[12.25, 83.5], [np.nan, -22]], dtype=np.float32)
        raster = parse_terrain(tiff_bytes(values, mask=[[1, 0], [1, 1]]))
        np.testing.assert_array_equal(raster.values, values)
        np.testing.assert_array_equal(raster.valid, [[True, False], [False, True]])
        self.assertEqual(raster.metadata["maskFlags"], gdal.GMF_PER_DATASET)
        self.assertIsNone(raster.metadata["nodata"])

    def test_explicit_mask_does_not_make_declared_zero_nodata_valid(self):
        values = np.array([[0, 12.5], [-1, np.nan]], dtype=np.float32)
        raster = parse_terrain(tiff_bytes(values, nodata=0, mask=[[1, 0], [1, 1]]))
        np.testing.assert_array_equal(raster.values, values)
        np.testing.assert_array_equal(raster.valid, [[False, False], [True, False]])
        self.assertEqual(raster.metadata["nodata"], 0)

    def test_float32_bit_patterns_including_nan_payload_and_signed_zero_are_preserved(self):
        bits = np.array([[0x00000000, 0x80000000, 0x7FC01234, 0x3F800001]], dtype=np.uint32)
        raster = parse_terrain(tiff_bytes(bits.view(np.float32)))
        np.testing.assert_array_equal(raster.values.view(np.uint32), bits)
        np.testing.assert_array_equal(raster.valid, [[True, True, False, True]])

    def test_south_up_grid_can_be_losslessly_reordered_and_cropped(self):
        values = np.array([[1, 2, 3], [4, -9999, 6], [7, 8, 9]], dtype=np.float32)
        raster = parse_terrain(tiff_bytes(values, transform=(-61, .5, 0, -34, 0, .5), nodata=-9999))
        np.testing.assert_array_equal(raster.y, [-33.75, -33.25, -32.75])
        self.assertEqual(raster.metadata["rowOrder"], "SOUTH_TO_NORTH")
        normalized = raster.north_up()
        np.testing.assert_array_equal(normalized.values, values[::-1])
        np.testing.assert_array_equal(normalized.valid, raster.valid[::-1])
        np.testing.assert_array_equal(normalized.y, raster.y[::-1])
        self.assertEqual(normalized.metadata["transform"], [-61, .5, 0, -32.5, 0, -.5])
        crop = raster.crop([-60.5, -33.5, -59.5, -32.5])
        np.testing.assert_array_equal(crop.values, values[1:, 1:])
        np.testing.assert_array_equal(crop.valid, raster.valid[1:, 1:])
        self.assertEqual(crop.metadata["transform"], [-60.5, .5, 0, -33.5, 0, .5])
        self.assertEqual(crop.metadata["inputSha256"], raster.metadata["inputSha256"])
        self.assertEqual(crop.metadata["nodata"], -9999)

    def test_geographic_grids_in_all_hemispheres_and_across_equator(self):
        values = np.array([[-8.25, 0], [2.75, 9.5]], dtype=np.float32)
        for west, north in [(-132, 49), (-74, -16), (139, 40), (150, -33), (-.5, .5), (179, 1)]:
            with self.subTest(west=west, north=north):
                raster = parse_terrain(tiff_bytes(values, transform=(west, .5, 0, north, 0, -.5)))
                np.testing.assert_array_equal(raster.values, values)
                np.testing.assert_array_equal(raster.x, [west + .25, west + .75])
                np.testing.assert_array_equal(raster.y, [north - .25, north - .75])
                self.assertTrue(raster.valid.all())

    def test_wgs84_longitude_first_crs_is_supported(self):
        raster = parse_terrain(tiff_bytes([[1, 2]], crs="OGC:CRS84"))
        self.assertEqual(raster.metadata["crs"], "EPSG:4326")
        np.testing.assert_array_equal(raster.x, [20.25, 20.75])

    def test_input_hash_is_verified_before_decoding_and_reported(self):
        data = tiff_bytes([[1, 2]])
        digest = sha256(data)
        raster = parse_terrain(data, expected_sha256=digest.upper())
        self.assertEqual(raster.metadata["inputSha256"], digest)
        with self.assertRaisesRegex(DataError, "SHA-256 mismatch"):
            parse_terrain(data, expected_sha256="0" * 64)
        with self.assertRaisesRegex(DataError, "SHA-256 mismatch"):
            parse_terrain(b"broken", expected_sha256=digest)
        for expected in ("", "short", "g" * 64, 7):
            with self.subTest(expected=expected), self.assertRaisesRegex(DataError, "64-character"):
                parse_terrain(data, expected_sha256=expected)

    def test_declared_vertical_datum_and_source_metadata_are_preserved(self):
        data = tiff_bytes([[1]], metadata={"VERTICAL_DATUM": "Synthetic source datum"})
        declared = parse_terrain(data)
        self.assertEqual(declared.metadata["verticalDatum"], "Synthetic source datum")
        self.assertEqual(declared.metadata["verticalDatumSource"], "TIFF_METADATA")
        self.assertEqual(declared.metadata["sourceMetadata"]["VERTICAL_DATUM"], "Synthetic source datum")
        supplied = parse_terrain(data, vertical_datum="Documented external datum")
        self.assertEqual(supplied.metadata["verticalDatum"], "Documented external datum")
        self.assertEqual(supplied.metadata["verticalDatumSource"], "CALLER")
        self.assertEqual(supplied.metadata["sourceMetadata"], declared.metadata["sourceMetadata"])
        for datum in ("", " ", 123):
            with self.subTest(datum=datum), self.assertRaisesRegex(DataError, "vertical_datum"):
                parse_terrain(data, vertical_datum=datum)

    def test_non_float32_and_multiple_bands_are_explicitly_rejected(self):
        for dtype in (gdal.GDT_Int16, gdal.GDT_Float64):
            with self.subTest(dtype=dtype), self.assertRaisesRegex(DataError, "Float32"):
                parse_terrain(tiff_bytes([[1, 2]], data_type=dtype))
        with self.assertRaisesRegex(DataError, "single-band"):
            parse_terrain(tiff_bytes([[1]], bands=2))

    def test_missing_projected_and_other_crs_are_explicitly_rejected(self):
        for crs in (None, "EPSG:3857", "EPSG:4269", "EPSG:4979", "EPSG:9518"):
            with self.subTest(crs=crs), self.assertRaisesRegex(DataError, "CRS"):
                parse_terrain(tiff_bytes([[1, 2]], crs=crs))

    def test_missing_rotated_zero_and_westward_transforms_are_rejected(self):
        transforms = [None, (20, .5, .01, 10, 0, -.5), (20, .5, 0, 10, .01, -.5),
                      (20, -.5, 0, 10, 0, -.5), (20, .5, 0, 10, 0, 0),
                      (float("nan"), .5, 0, 10, 0, -.5), (20, .5, 0, float("inf"), 0, -.5)]
        for transform in transforms:
            with self.subTest(transform=transform), self.assertRaisesRegex(DataError, "transform"):
                parse_terrain(tiff_bytes([[1, 2]], transform=transform))

    def test_out_of_range_sample_coordinates_are_rejected(self):
        for transform in [(181, .5, 0, 10, 0, -.5), (20, .5, 0, 91, 0, -.5)]:
            with self.subTest(transform=transform), self.assertRaisesRegex(DataError, "geographic"):
                parse_terrain(tiff_bytes([[1, 2]], transform=transform))

    def test_declared_non_meter_or_packed_samples_are_rejected(self):
        for options in ({"unit": "ft"}, {"scale": .1}, {"offset": 2}):
            with self.subTest(options=options), self.assertRaisesRegex(DataError, "meters|scale/offset"):
                parse_terrain(tiff_bytes([[1, 2]], **options))
        raster = parse_terrain(tiff_bytes([[1, 2]], unit="metre", scale=1, offset=0))
        self.assertEqual(raster.metadata["units"], "m")

    def test_invalid_or_non_tiff_bytes_fail_without_a_raster(self):
        for data in (b"", None, bytearray(b"bad"), b"not a TIFF", b"II*\x00"):
            with self.subTest(data_type=type(data).__name__), self.assertRaises(DataError):
                parse_terrain(data)

    def test_in_memory_inputs_are_released_after_success_and_decode_failure(self):
        good = tiff_bytes([[1, 2]])
        unsupported = tiff_bytes([[1, 2]], data_type=gdal.GDT_Int16)
        before = {name for name in (gdal.ReadDir("/vsimem") or []) if name.startswith("astra-terrain-")}
        parse_terrain(good)
        for data in (unsupported, b"bad TIFF"):
            with self.assertRaises(DataError):
                parse_terrain(data)
        after = {name for name in (gdal.ReadDir("/vsimem") or []) if name.startswith("astra-terrain-")}
        self.assertEqual(after, before)


class SourceTerrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive = (Path(__file__).resolve().parents[2] / "astra-map-quality-v1"
                   / "inputs" / "ESSENTIAL_MAP_SAMPLES.zip")
        with zipfile.ZipFile(archive) as bundle:
            manifest = json.loads(bundle.read("DATA_MANIFEST.json"))
            cls.entry = next(entry for entry in manifest["datasets"] if entry["data_class"] == "land_elevation")
            cls.data = bundle.read(cls.entry["relative_path"])
        cls.raster = parse_terrain(cls.data, expected_sha256=cls.entry["sha256"],
                                   vertical_datum=cls.entry["vertical_datum"])

    def test_real_bytes_preserve_manifest_hash_float32_meters_and_point_registration(self):
        raster, entry = self.raster, self.entry
        self.assertEqual(raster.metadata["inputSha256"], entry["sha256"])
        self.assertEqual(raster.values.shape, tuple(reversed(entry["dimensions"])))
        self.assertEqual(raster.values.dtype, np.dtype(np.float32))
        self.assertEqual(raster.metadata["pixelRegistration"], entry["pixel_registration"])
        self.assertEqual(raster.metadata["units"], entry["vertical_units"])
        self.assertEqual(raster.metadata["verticalDatum"], entry["vertical_datum"])
        self.assertEqual(raster.metadata["nodata"], entry["nodata"])
        self.assertTrue(raster.valid.all())
        np.testing.assert_allclose(raster.bbox, entry["sample_extent"], rtol=0, atol=1e-12)
        np.testing.assert_allclose([raster.x[0], raster.y[0]], entry["first_pixel_center_lonlat"], rtol=0, atol=1e-12)
        np.testing.assert_allclose([raster.x[-1], raster.y[-1]], entry["last_pixel_center_lonlat"], rtol=0, atol=1e-12)

    def test_real_values_and_transform_equal_independent_gdal_decode(self):
        path = f"/vsimem/astra-source-test-{uuid.uuid4().hex}.tif"
        dataset = None
        try:
            with gdal.ExceptionMgr():
                gdal.FileFromMemBuffer(path, self.data)
                dataset = gdal.OpenEx(path, gdal.OF_READONLY | gdal.OF_RASTER, allowed_drivers=["GTiff"])
                np.testing.assert_array_equal(self.raster.values, dataset.ReadAsArray())
                self.assertEqual(self.raster.metadata["transform"], list(dataset.GetGeoTransform()))
        finally:
            dataset = None
            gdal.Unlink(path)

    def test_real_bbox_crop_preserves_selected_source_cells_and_provenance(self):
        raster = self.raster
        # Bounds chosen from sample centers, independent of geographic fixture numbers.
        west, east = raster.x[12], raster.x[19]
        south, north = raster.y[24], raster.y[16]
        crop = raster.crop([west, south, east, north])
        np.testing.assert_array_equal(crop.values, raster.values[17:25, 12:19])
        np.testing.assert_array_equal(crop.valid, raster.valid[17:25, 12:19])
        np.testing.assert_array_equal(crop.x, raster.x[12:19])
        np.testing.assert_array_equal(crop.y, raster.y[17:25])
        self.assertEqual(crop.metadata["inputSha256"], self.entry["sha256"])
        self.assertEqual(crop.metadata["verticalDatum"], self.entry["vertical_datum"])
        self.assertEqual(crop.metadata["pixelRegistration"], "Point")
        with self.assertRaisesRegex(DataError, "no supplied sample centers"):
            raster.crop([-120, -20, -119, -19])


if __name__ == "__main__":
    unittest.main()
