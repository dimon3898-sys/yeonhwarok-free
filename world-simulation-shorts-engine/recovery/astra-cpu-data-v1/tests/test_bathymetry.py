"""CPU-only NetCDF reader checks, including the supplied independent ASCII grid."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as C
import ctypes.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zipfile

import numpy as np

from astra_cpu import bathymetry
from astra_cpu.bathymetry import depth_with_ocean_mask, parse_bathymetry
from astra_cpu.model import DataError, sha256


_ARCHIVE = (Path(__file__).resolve().parents[2] / "astra-map-quality-v1" /
            "inputs" / "ESSENTIAL_MAP_SAMPLES.zip")
_NC_MEMBER = "samples/GEBCO_2026_Korea_EastSea_subset.nc"
_ASCII_MEMBER = "provenance/GEBCO_2026_subset_opendap.ascii"
_ASCII_SHA = "333a0f7e726df831cc708962db1a3643bca691bfbaff6f5762ee7112837e242f"
_NC_TYPES = {"int8": 1, "int16": 3, "int32": 4, "float32": 5,
             "float64": 6, "uint8": 7, "uint16": 8, "uint32": 9,
             "int64": 10, "uint64": 11}


def _fixture(values=None, *, x=None, y=None, elevation_attrs=None,
             global_attrs=None, crs_attrs=None, lon_attrs=None,
             reverse_dims=False, with_crs=True):
    """Write small synthetic NetCDF4 with the existing C library, no new package."""
    values = np.asarray([[-30, 7, -11], [-20, 0, 4]], dtype=np.int16) if values is None else np.asarray(values)
    rows, columns = values.shape
    x = np.asarray(np.arange(columns) + 10.25 if x is None else x, dtype=np.float64)
    y = np.asarray(np.arange(rows) + 20.25 if y is None else y, dtype=np.float64)
    elevation_attrs = dict({"standard_name": "height_above_mean_sea_level", "units": "m",
                            **({"grid_mapping": "crs"} if with_crs else {})},
                           **(elevation_attrs or {}))
    global_attrs = dict({"geospatial_bounds_vertical_crs": "EPSG:5831",
                        "node_offset": 1}, **(global_attrs or {}))
    crs_attrs = dict({"grid_mapping_name": "latitude_longitude", "epsg_code": "EPSG:4326"},
                    **(crs_attrs or {}))
    lon_attrs = dict({"units": "degrees_east", "standard_name": "longitude"}, **(lon_attrs or {}))
    lib = C.CDLL(ctypes.util.find_library("netcdf"))
    integer = C.POINTER(C.c_int)
    for name, args in {
        "nc_create": [C.c_char_p, C.c_int, integer], "nc_close": [C.c_int],
        "nc_def_dim": [C.c_int, C.c_char_p, C.c_size_t, integer],
        "nc_def_var": [C.c_int, C.c_char_p, C.c_int, C.c_int, integer, integer],
        "nc_put_att_text": [C.c_int, C.c_int, C.c_char_p, C.c_size_t, C.c_char_p],
        "nc_put_att": [C.c_int, C.c_int, C.c_char_p, C.c_int, C.c_size_t, C.c_void_p],
        "nc_enddef": [C.c_int], "nc_put_var": [C.c_int, C.c_int, C.c_void_p],
    }.items():
        getattr(lib, name).argtypes = args
        getattr(lib, name).restype = C.c_int
    lib.nc_strerror.argtypes, lib.nc_strerror.restype = [C.c_int], C.c_char_p
    # Synthetic writing has the same harmless HDF5 nonexistent-file probe.
    lib.H5Eget_auto2.argtypes = [C.c_longlong, C.POINTER(C.c_void_p), C.POINTER(C.c_void_p)]
    lib.H5Eset_auto2.argtypes = [C.c_longlong, C.c_void_p, C.c_void_p]

    def check(result):
        if result:
            raise RuntimeError(lib.nc_strerror(result).decode())

    def attrs(ncid, varid, attributes, variable_dtype=None):
        for name, value in attributes.items():
            if value is None:
                continue
            if isinstance(value, str):
                encoded = value.encode()
                check(lib.nc_put_att_text(ncid, varid, name.encode(), len(encoded), encoded))
            else:
                array = np.asarray(value, dtype=variable_dtype if name == "_FillValue" else None).reshape(-1)
                array = np.ascontiguousarray(array)
                check(lib.nc_put_att(ncid, varid, name.encode(), _NC_TYPES[str(array.dtype)],
                                     array.size, array.ctypes.data))

    with tempfile.TemporaryDirectory(prefix="astra-bathymetry-") as folder:
        path = Path(folder) / "fixture.nc"
        ncid = C.c_int()
        callback, context = C.c_void_p(), C.c_void_p()
        check(lib.H5Eget_auto2(0, C.byref(callback), C.byref(context)))
        check(lib.H5Eset_auto2(0, None, None))
        try:
            check(lib.nc_create(str(path).encode(), 0x1000, C.byref(ncid)))  # NC_NETCDF4
        except Exception:
            check(lib.H5Eset_auto2(0, callback, context))
            raise
        try:
            lat_dim, lon_dim = C.c_int(), C.c_int()
            check(lib.nc_def_dim(ncid.value, b"lat", rows, C.byref(lat_dim)))
            check(lib.nc_def_dim(ncid.value, b"lon", columns, C.byref(lon_dim)))
            arrays = [("lat", 6, [lat_dim.value], y,
                       {"units": "degrees_north", "standard_name": "latitude"}),
                      ("lon", 6, [lon_dim.value], x, lon_attrs)]
            if with_crs:
                arrays.append(("crs", 4, [], np.asarray(4326, dtype=np.int32), crs_attrs))
            dims = [lon_dim.value, lat_dim.value] if reverse_dims else [lat_dim.value, lon_dim.value]
            arrays.append(("elevation", _NC_TYPES[str(values.dtype)], dims, values, elevation_attrs))
            variables = []
            for name, kind, dims, array, attributes in arrays:
                varid = C.c_int()
                dimids = (C.c_int * len(dims))(*dims)
                check(lib.nc_def_var(ncid.value, name.encode(), kind, len(dims), dimids, C.byref(varid)))
                attrs(ncid.value, varid.value, attributes, array.dtype)
                variables.append((varid.value, array))
            attrs(ncid.value, -1, global_attrs)
            check(lib.nc_enddef(ncid.value))
            for varid, array in variables:
                array = np.ascontiguousarray(array)
                check(lib.nc_put_var(ncid.value, varid, array.ctypes.data))
        finally:
            try:
                check(lib.nc_close(ncid.value))
            finally:
                check(lib.H5Eset_auto2(0, callback, context))
        return path.read_bytes()


class BathymetrySampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(_ARCHIVE) as archive:
            cls.data = archive.read(_NC_MEMBER)
            cls.ascii = archive.read(_ASCII_MEMBER)
            manifest = json.loads(archive.read("DATA_MANIFEST.json"))
        cls.entry = next(d for d in manifest["datasets"] if d["relative_path"] == _NC_MEMBER)
        cls.raster = parse_bathymetry(cls.data, expected_sha256=cls.entry["sha256"])

    def test_real_sample_metadata_signed_storage_and_complete_mask(self):
        r = self.raster
        self.assertEqual(sha256(self.data), self.entry["sha256"])
        self.assertEqual(r.values.shape, (480, 480))
        self.assertEqual(r.values.dtype, np.dtype("int16"))
        self.assertEqual((int(r.values.min()), int(r.values.max())), (-2124, 1613))
        self.assertEqual(int(np.count_nonzero(r.values < 0)), 142575)
        self.assertEqual(int(r.valid.sum()), 230400)
        self.assertEqual(r.metadata["crs"], "EPSG:4326")
        self.assertEqual(r.metadata["verticalDatum"], "EPSG:5831")
        self.assertEqual(r.metadata["units"], "m")
        self.assertIsNone(r.metadata["nodata"])
        self.assertEqual(r.metadata["oceanMaskStatus"], "UNRESOLVED")
        self.assertEqual(r.metadata["sourceAttributes"]["global"]["node_offset"], 1)
        self.assertIn("heterogeneous", r.metadata["sourceAttributes"]["global"]["comment"])

    def test_exact_complete_equality_to_independently_parsed_bundled_ascii(self):
        self.assertEqual(sha256(self.ascii), _ASCII_SHA)
        text = self.ascii.decode()
        values_text = text.split("elevation.elevation[480][480]\n", 1)[1].split("elevation.lat[480]", 1)[0]
        rows = [np.fromstring(line.split(",", 1)[1], sep=",", dtype=np.int16)
                for line in values_text.splitlines() if re.match(r"^\[\d+\],", line)]
        self.assertEqual(len(rows), 480)
        np.testing.assert_array_equal(self.raster.values, np.stack(rows))
        lat = text.split("elevation.lat[480]\n", 1)[1].split("elevation.lon[480]", 1)[0]
        lon = text.split("elevation.lon[480]\n", 1)[1]
        np.testing.assert_array_equal(self.raster.y, np.fromstring(lat, sep=",", dtype=np.float64))
        np.testing.assert_array_equal(self.raster.x, np.fromstring(lon, sep=",", dtype=np.float64))

    def test_actual_ascending_centers_and_cell_edges(self):
        r = self.raster
        self.assertEqual(r.x.dtype, np.dtype("float64"))
        self.assertEqual(r.y.dtype, np.dtype("float64"))
        self.assertTrue(np.all(np.diff(r.y) > 0))
        self.assertEqual(r.x[0], 128.0020833333333)
        self.assertEqual(r.x[-1], 129.99791666666664)
        self.assertEqual(r.y[0], 37.00208333333333)
        self.assertEqual(r.y[-1], 38.99791666666667)
        np.testing.assert_allclose(r.bbox, [128, 37, 130, 39], rtol=0, atol=1e-12)
        self.assertGreater(r.metadata["transform"][5], 0)
        self.assertEqual(r.metadata["registration"], "CELL_CENTER")

    def test_row_flip_and_crop_preserve_signed_values_coordinates_and_hash(self):
        r = self.raster
        north = r.north_up()
        np.testing.assert_array_equal(north.values, r.values[::-1])
        np.testing.assert_array_equal(north.y, r.y[::-1])
        np.testing.assert_array_equal(north.valid, r.valid[::-1])
        self.assertLess(north.metadata["transform"][5], 0)
        np.testing.assert_allclose(north.bbox, r.bbox, rtol=0, atol=1e-12)
        bbox = [128.25, 37.25, 128.75, 37.75]
        crop = r.crop(bbox)
        xi = (r.x >= bbox[0]) & (r.x < bbox[2])
        yi = (r.y >= bbox[1]) & (r.y < bbox[3])
        np.testing.assert_array_equal(crop.values, r.values[np.ix_(yi, xi)])
        np.testing.assert_array_equal(crop.x, r.x[xi])
        np.testing.assert_array_equal(crop.y, r.y[yi])
        np.testing.assert_array_equal(crop.north_up().values, north.crop(bbox).values)
        self.assertEqual(crop.metadata["inputSha256"], self.entry["sha256"])
        self.assertFalse(r.values.flags.writeable)


class BathymetrySyntheticTests(unittest.TestCase):
    def test_synthetic_scalar_crs_and_south_or_north_row_order(self):
        for y, order in (([20.25, 21.25], "SOUTH_TO_NORTH"), ([21.25, 20.25], "NORTH_TO_SOUTH")):
            with self.subTest(order=order):
                r = parse_bathymetry(_fixture(y=y))
                np.testing.assert_array_equal(r.y, y)
                np.testing.assert_array_equal(r.values, [[-30, 7, -11], [-20, 0, 4]])
                self.assertEqual(r.metadata["rowOrder"], order)
                self.assertEqual(r.metadata["sourceAttributes"]["crs"]["epsg_code"], "EPSG:4326")

    def test_fill_missing_value_and_implicit_fill_are_invalid_without_coercion(self):
        original = np.asarray([[-9999, -777, -32767], [-5, 0, 9]], dtype=np.int16)
        r = parse_bathymetry(_fixture(original, elevation_attrs={"_FillValue": -9999,
                                                               "missing_value": [-777, -888]}))
        np.testing.assert_array_equal(r.values, original)
        np.testing.assert_array_equal(r.valid, [[False, False, True], [True, True, True]])
        self.assertEqual(r.metadata["nodata"], [-9999, -777, -888])
        implicit = parse_bathymetry(_fixture(original))
        self.assertFalse(implicit.valid[0, 2])
        self.assertEqual(implicit.values[0, 2], -32767)
        self.assertEqual(implicit.metadata["defaultFillValue"], -32767)

    def test_nonfinite_raw_elevation_remains_present_and_invalid(self):
        original = np.asarray([[np.nan, np.inf, -np.inf], [-5, 0, 9]], dtype=np.float32)
        r = parse_bathymetry(_fixture(original))
        np.testing.assert_array_equal(r.values, original)
        np.testing.assert_array_equal(r.valid, [[False, False, False], [True, True, True]])
        self.assertEqual(r.values.dtype, np.dtype("float32"))

    def test_source_valid_range_masks_without_replacing_values(self):
        original = np.asarray([[-30, 7, -11], [-20, 0, 4]], dtype=np.int16)
        r = parse_bathymetry(_fixture(original, elevation_attrs={"valid_range": [-20, 5]}))
        np.testing.assert_array_equal(r.values, original)
        np.testing.assert_array_equal(r.valid, [[False, False, True], [True, True, True]])

    def test_malformed_validity_metadata_is_rejected_explicitly(self):
        for attrs in ({"valid_range": [5, -20]}, {"valid_range": [np.nan, 5]},
                      {"valid_range": "-20,5"}, {"valid_min": [-20, 0]},
                      {"valid_max": "five"}, {"valid_min": 8, "valid_max": 4}):
            with self.subTest(attrs=attrs), self.assertRaises(DataError):
                parse_bathymetry(_fixture(elevation_attrs=attrs))

    def test_coordinate_fill_validity_and_conflicting_semantics_are_errors(self):
        for attrs in ({"_FillValue": 11.25}, {"missing_value": 11.25},
                      {"valid_range": [10., 11.]}, {"standard_name": "latitude"},
                      {"axis": "Y"}):
            with self.subTest(attrs=attrs), self.assertRaises(DataError):
                parse_bathymetry(_fixture(lon_attrs=attrs))

    def test_nonidentity_packing_and_unsigned_reinterpretation_are_errors(self):
        for attrs in ({"scale_factor": .1}, {"add_offset": 3}, {"_Unsigned": "true"}):
            with self.subTest(attrs=attrs), self.assertRaisesRegex(DataError, "unsupported"):
                parse_bathymetry(_fixture(elevation_attrs=attrs))
        r = parse_bathymetry(_fixture(elevation_attrs={"scale_factor": 1., "add_offset": 0.}))
        self.assertEqual(r.values[0, 0], -30)

    def test_unsupported_units_and_sign_are_explicit_errors(self):
        for attrs in ({"units": "ft"}, {"units": None}, {"positive": "down"},
                      {"standard_name": None}, {"scale_factor": "0.1"}):
            with self.subTest(attrs=attrs), self.assertRaises(DataError):
                parse_bathymetry(_fixture(elevation_attrs=attrs))
        with self.assertRaisesRegex(DataError, "coordinate units"):
            parse_bathymetry(_fixture(lon_attrs={"units": "radians"}))

    def test_unknown_vertical_datum_and_explicit_declaration_preserve_provenance(self):
        data = _fixture(global_attrs={"geospatial_bounds_vertical_crs": None})
        r = parse_bathymetry(data)
        self.assertIsNone(r.metadata["verticalDatum"])
        self.assertEqual(r.metadata["verticalDatumStatus"], "UNRESOLVED")
        declared = parse_bathymetry(data, vertical_datum="caller-declared local sea level")
        self.assertEqual(declared.metadata["verticalDatum"], "caller-declared local sea level")
        self.assertEqual(declared.metadata["inputSha256"], sha256(data))
        with self.assertRaises(DataError):
            parse_bathymetry(data, vertical_datum=" ")

    def test_irregular_nonfinite_descending_longitude_or_singleton_axes_rejected(self):
        cases = ({"x": [10.25, 11.25, 12.5]}, {"x": [12.25, 11.25, 10.25]},
                 {"x": [10.25, np.nan, 12.25]}, {"y": [np.inf, 21.25]},
                 {"y": [90.25, 91.25]}, {"x": [180.25, 181.25, 182.25]},
                 {"values": np.asarray([[-5, -4, -3]], dtype=np.int16)})
        for args in cases:
            with self.subTest(args=args), self.assertRaises(DataError):
                parse_bathymetry(_fixture(**args))

    def test_wrong_dimension_order_projected_missing_or_conflicting_crs_rejected(self):
        cases = ({"reverse_dims": True}, {"with_crs": False},
                 {"crs_attrs": {"epsg_code": "EPSG:3857"}},
                 {"crs_attrs": {"grid_mapping_name": "rotated_latitude_longitude"}},
                 {"global_attrs": {"geospatial_bounds_crs": "EPSG:4269"}})
        for args in cases:
            with self.subTest(args=args), self.assertRaises(DataError):
                parse_bathymetry(_fixture(**args))

    def test_grid_node_registration_is_not_silently_claimed_as_cell_center(self):
        with self.assertRaisesRegex(DataError, "grid-node registration"):
            parse_bathymetry(_fixture(global_attrs={"node_offset": 0}))

    def test_hash_mismatch_is_rejected_before_native_parser(self):
        data = _fixture()
        with mock.patch.object(bathymetry, "_Dataset") as reader:
            with self.assertRaisesRegex(DataError, "SHA-256 mismatch"):
                parse_bathymetry(data, expected_sha256="0" * 64)
            reader.assert_not_called()
        r = parse_bathymetry(data, expected_sha256=sha256(data).upper())
        self.assertEqual(r.metadata["inputSha256"], sha256(data))
        for expected in ("abc", 7):
            with self.subTest(expected=expected), self.assertRaises(DataError):
                parse_bathymetry(data, expected_sha256=expected)

    def test_invalid_or_empty_netcdf_does_not_fabricate_grid(self):
        for data in (b"", b"not a NetCDF file", "not bytes"):
            with self.subTest(data=data), self.assertRaises(DataError):
                parse_bathymetry(data)

    def test_native_handles_closed_on_success_and_semantic_failure(self):
        original_close = bathymetry._Dataset.close
        with mock.patch.object(bathymetry._Dataset, "close", autospec=True,
                               side_effect=original_close) as close:
            parse_bathymetry(_fixture())
            with self.assertRaises(DataError):
                parse_bathymetry(_fixture(elevation_attrs={"units": "ft"}))
            self.assertEqual(close.call_count, 2)

    def test_concurrent_readers_return_identical_raw_arrays(self):
        data = _fixture()
        with ThreadPoolExecutor(max_workers=4) as pool:
            rasters = list(pool.map(parse_bathymetry, [data] * 24))
        for r in rasters:
            np.testing.assert_array_equal(r.values, rasters[0].values)
            self.assertEqual(r.metadata["inputSha256"], sha256(data))


class OceanDepthTests(unittest.TestCase):
    def setUp(self):
        self.original = np.asarray([[-32768, -50, -9999], [5, 0, -8]], dtype=np.int16)
        self.raster = parse_bathymetry(_fixture(self.original, elevation_attrs={"_FillValue": -9999}))

    def test_absent_ocean_mask_is_unresolved(self):
        with self.assertRaisesRegex(DataError, "ocean mask unresolved"):
            depth_with_ocean_mask(self.raster)
        self.assertEqual(self.raster.metadata["oceanMaskStatus"], "UNRESOLVED")

    def test_external_mask_controls_depth_including_negative_land_and_int16_extreme(self):
        mask = np.asarray([[True, False, True], [True, True, True]])
        depth = depth_with_ocean_mask(self.raster, mask)
        np.testing.assert_array_equal(depth.valid, [[True, False, False], [True, True, True]])
        np.testing.assert_array_equal(depth.values, [[32768., np.nan, np.nan], [0., 0., 8.]])
        np.testing.assert_array_equal(self.raster.values, self.original)
        self.assertEqual(depth.values.dtype, np.dtype("float64"))
        self.assertEqual(depth.metadata["quantity"], "DERIVED_OCEAN_DEPTH")
        self.assertEqual(depth.metadata["sourcePositive"], "up")
        self.assertEqual(depth.metadata["inputSha256"], self.raster.metadata["inputSha256"])
        self.assertEqual(depth.metadata["oceanMaskSha256"], sha256(mask.astype(np.uint8).tobytes()))

    def test_all_land_mask_keeps_every_derived_cell_unsupported_nan(self):
        depth = depth_with_ocean_mask(self.raster, np.zeros(self.original.shape, dtype=bool))
        self.assertFalse(depth.valid.any())
        self.assertTrue(np.isnan(depth.values).all())

    def test_mask_type_shape_and_rederivation_fail_explicitly(self):
        for mask in (np.ones(self.original.shape, dtype=np.uint8), np.ones((2, 1), dtype=bool),
                     True, [[True], [False, True]]):
            with self.subTest(mask=mask), self.assertRaisesRegex(DataError, "boolean HxW"):
                depth_with_ocean_mask(self.raster, mask)
        mask = np.ones(self.original.shape, dtype=bool)
        with self.assertRaises(DataError):
            depth_with_ocean_mask(depth_with_ocean_mask(self.raster, mask), mask)


if __name__ == "__main__":
    unittest.main()
