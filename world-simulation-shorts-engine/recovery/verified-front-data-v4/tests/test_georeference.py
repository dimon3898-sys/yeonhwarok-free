"""Synthetic registration tests, never historical-map coordinate evidence."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from osgeo import gdal, osr


SPEC = importlib.util.spec_from_file_location(
    "verified_front_georeference", Path(__file__).parents[1] / "georeference.py"
)
georeference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(georeference)


class GeoreferenceSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "SYNTHETIC_NOT_HISTORY.tif"
        dataset = gdal.GetDriverByName("GTiff").Create(str(self.path), 128, 128, 1, gdal.GDT_Byte)
        dataset.SetMetadataItem("TEST_MODE", "SYNTHETIC_NOT_HISTORICAL")
        dataset = None
        self.spec = self.make_spec()

    def make_spec(self):
        def point(identifier, pixel):
            x, y = pixel
            return {"id": identifier, "pixel": pixel,
                    "coordinate": [-10 + x * 0.01, -20 + y * 0.01],
                    "sourceReference": "SYNTHETIC equation, not a historical point"}
        return {
            "mapId": "synthetic-arbitrary-southern-western-map",
            "mode": "SYNTHETIC", "originalSHA256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
            "raster": {"width": 128, "height": 128},
            "sourceCRS": {"definition": "EPSG:4326", "status": "KNOWN_FROM_MAP",
                          "sourceReference": "SYNTHETIC fixture declares geographic WGS84"},
            "pixelConvention": "PIXEL_CENTER",
            "sourceScale": {"denominator": 100000, "sourceReference": "SYNTHETIC scale for test only"},
            "sourceUncertaintyMeters": 25,
            "qualityLimits": {"maxFitResidualMeters": 1, "maxCheckResidualMeters": 1,
                              "maxCombinedUncertaintyMeters": 30},
            "controls": [point(f"fit-{i}", p) for i, p in enumerate(
                [[0, 0], [127, 0], [127, 127], [0, 127]])],
            "checkControls": [point(f"held-out-{i}", p) for i, p in enumerate(
                [[16, 16], [111, 16], [111, 111], [16, 111]])],
            "independentCheckDeclaration": "SYNTHETIC independently held-out equation coordinates",
        }

    def fit(self, spec=None):
        return georeference.fit_reference(self.path, self.spec if spec is None else spec)

    def assert_code(self, code, callback):
        with self.assertRaises(georeference.GeoreferenceError) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)

    def test_known_affine_southern_western_coordinates_and_no_historical_claim(self):
        report = self.fit()
        result = georeference.transform_verified_vertices(self.path, report, [[32, 32], [64, 64]])
        for actual, expected in zip(result, [[-9.68, -19.68], [-9.36, -19.36]]):
            for value, target in zip(actual, expected):
                self.assertAlmostEqual(value, target, places=10)
        self.assertEqual(report["mode"], "SYNTHETIC")
        self.assertEqual(report["status"], "TECHNICAL_CANDIDATE_REVIEW_REQUIRED")
        self.assertEqual(report["runtimeAdmission"], "NOT_ADMITTED")
        self.assertFalse(report["historicalAccuracyVerified"])
        self.assertLess(report["residuals"]["independentCheck"]["maximum"], 0.001)
        self.assertEqual(report["inputSpec"], self.spec)

    def test_pixel_center_to_gdal_corner_half_pixel_is_explicit(self):
        report = self.fit()
        coefficients = report["transform"]["coefficients"]
        self.assertAlmostEqual(coefficients[0], -10.005, places=10)
        self.assertAlmostEqual(coefficients[3], -20.005, places=10)
        self.assertEqual(report["transform"]["gdalCornerOffset"], [0.5, 0.5])
        self.spec["pixelConvention"] = "PIXEL_CORNER"
        self.assert_code("PIXEL_CONVENTION_REQUIRED", self.fit)

    def test_projected_crs_and_traditional_longitude_latitude_order(self):
        self.spec["sourceCRS"]["definition"] = "EPSG:3857"
        for p in self.spec["controls"] + self.spec["checkControls"]:
            x, y = p["pixel"]
            p["coordinate"] = [100000 + x * 50 + y * 4, -1000000 + y * 60 - x * 3]
        report = self.fit()
        actual = georeference.transform_verified_vertices(self.path, report, [[64, 64]])[0]
        source, target = osr.SpatialReference(), osr.SpatialReference()
        source.ImportFromEPSG(3857)
        target.ImportFromEPSG(4326)
        for reference in (source, target):
            reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        expected = osr.CoordinateTransformation(source, target).TransformPoint(103456, -996352)
        self.assertAlmostEqual(actual[0], expected[0], places=10)
        self.assertAlmostEqual(actual[1], expected[1], places=10)
        self.assertGreater(actual[0], 0)
        self.assertLess(actual[1], 0)

    def test_original_sha_and_original_dimensions_are_required(self):
        self.spec["originalSHA256"] = "0" * 64
        self.assert_code("ORIGINAL_HASH_MISMATCH", self.fit)
        self.spec = self.make_spec()
        self.spec["raster"]["width"] = 127
        self.assert_code("ORIGINAL_DIMENSION_MISMATCH", self.fit)

    def test_report_and_original_tampering_are_rejected(self):
        report = self.fit()
        report["transform"]["coefficients"][0] += 0.1
        self.assert_code("REPORT_MISMATCH", lambda: georeference.transform_verified_vertices(
            self.path, report, [[64, 64]]))
        report = self.fit()
        report["historicalAccuracyVerified"] = True
        self.assert_code("REPORT_MISMATCH", lambda: georeference.transform_verified_vertices(
            self.path, report, [[64, 64]]))
        report = self.fit()
        self.path.write_bytes(self.path.read_bytes() + b"TAMPER")
        self.assert_code("ORIGINAL_HASH_MISMATCH", lambda: georeference.transform_verified_vertices(
            self.path, report, [[64, 64]]))

    def test_json_round_trip_preserves_binding_and_input_pixels(self):
        report = json.loads(json.dumps(self.fit()))
        points = [[16, 16], [32.125, 64.5], [111, 111]]
        saved = copy.deepcopy(points)
        self.assertEqual(len(georeference.transform_verified_vertices(self.path, report, points)), 3)
        self.assertEqual(points, saved)

    def test_unknown_or_uncited_crs_fails_closed(self):
        self.spec["sourceCRS"]["status"] = "ASSUMED"
        self.assert_code("UNKNOWN_SOURCE_CRS", self.fit)
        self.spec = self.make_spec()
        self.spec["sourceCRS"]["definition"] = "EPSG:99999999"
        self.assert_code("UNKNOWN_SOURCE_CRS", self.fit)

    def test_insufficient_and_collinear_control_points_rejected(self):
        self.spec["controls"] = self.spec["controls"][:3]
        self.assert_code("INSUFFICIENT_CONTROLS", self.fit)
        self.spec = self.make_spec()
        for i, point in enumerate(self.spec["controls"]):
            point["pixel"] = [i * 30, i * 30]
        self.assert_code("COLLINEAR_CONTROLS", self.fit)
        self.spec = self.make_spec()
        for i, point in enumerate(self.spec["checkControls"]):
            point["pixel"] = [20 + i * 20, 60]
        self.assert_code("COLLINEAR_CONTROLS", self.fit)

    def test_reused_fit_controls_cannot_be_independent_checks(self):
        self.spec["checkControls"][0]["id"] = "fit-0"
        self.assert_code("CHECKS_NOT_INDEPENDENT", self.fit)
        self.spec = self.make_spec()
        self.spec["checkControls"][0]["pixel"] = [0, 0]
        self.assert_code("CHECKS_NOT_INDEPENDENT", self.fit)

    def test_held_out_residual_detects_error_not_visible_in_fit(self):
        self.spec["checkControls"][0]["coordinate"][0] += 0.01
        self.assert_code("CHECK_RESIDUAL_EXCEEDS_BUDGET", self.fit)

    def test_large_fitted_error_cannot_be_hidden_by_clean_checks(self):
        self.spec["controls"][0]["coordinate"][0] += 0.1
        self.assert_code("FIT_RESIDUAL_EXCEEDS_BUDGET", self.fit)

    def test_check_coverage_must_span_an_area_within_fit(self):
        for i, p in enumerate(self.spec["checkControls"]):
            p["pixel"] = [[60, 60], [65, 60], [65, 65], [60, 65]][i]
        self.assert_code("INSUFFICIENT_CHECK_COVERAGE", self.fit)

    def test_no_extrapolation_outside_independently_validated_footprint(self):
        report = self.fit()
        for vertex in ([0, 0], [127, 127], [-0.5, 64], [64, 200]):
            self.assert_code("EXTRAPOLATION_FORBIDDEN", lambda v=vertex:
                             georeference.transform_verified_vertices(self.path, report, [v]))

    def test_nonfinite_and_outside_original_control_pixels_are_rejected(self):
        self.spec["controls"][0]["coordinate"][0] = float("nan")
        self.assert_code("INVALID_DATA", self.fit)
        self.spec = self.make_spec()
        self.spec["controls"][0]["pixel"] = [-1, 0]
        self.assert_code("PIXEL_OUTSIDE_ORIGINAL", self.fit)
        report = self.fit(self.make_spec())
        self.assert_code("INVALID_DATA", lambda: georeference.transform_verified_vertices(
            self.path, report, [[float("inf"), 40]]))

    def test_scale_and_source_uncertainty_cannot_be_omitted(self):
        self.spec.pop("sourceScale")
        self.assert_code("SOURCE_SCALE_REQUIRED", self.fit)
        self.spec = self.make_spec()
        self.spec["sourceUncertaintyMeters"] = 50
        self.assert_code("SOURCE_UNCERTAINTY_EXCEEDS_BUDGET", self.fit)
        self.spec = self.make_spec()
        self.spec["mode"] = "SOURCE_MAP"
        self.assert_code("INVALID_DATA", self.fit)
        self.spec["sourceUncertaintyReference"] = "Original map marginal note, synthetic test only"
        self.spec["sourceUncertaintyMeters"] = 0
        self.assert_code("SOURCE_UNCERTAINTY_REQUIRED", self.fit)

    def test_geographic_antimeridian_cannot_create_false_affine_territory(self):
        self.spec["controls"][0]["coordinate"][0] = -179
        self.spec["controls"][1]["coordinate"][0] = 179
        self.assert_code("ANTIMERIDIAN_REQUIRES_PROJECTED_CRS", self.fit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
