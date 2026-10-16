"""Synthetic CPU evidence only; no test coordinate is a historical front."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from osgeo import gdal


SPEC = importlib.util.spec_from_file_location(
    "approximate_control_registration", Path(__file__).parents[1] / "control_registration.py")
registration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registration)


class ApproximateControlRegistrationSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.raster = self.root / "SYNTHETIC_NOT_ARCHIVAL.tif"
        dataset = gdal.GetDriverByName("GTiff").Create(str(self.raster), 128, 128, 1, gdal.GDT_Byte)
        dataset = None
        self.reference = self.root / "SYNTHETIC_NOT_CITY_REFERENCE.geojson"
        self.fit_pixels = [[10, 10], [117, 10], [117, 117], [10, 117]]
        self.check_pixels = [[30, 30], [97, 30], [97, 97], [30, 97]]
        self.dataset = {"type": "FeatureCollection", "features": []}
        for i, pixel in enumerate(self.fit_pixels + self.check_pixels):
            self.dataset["features"].append({"type": "Feature", "properties": {"stable_id": i},
                "geometry": {"type": "Point", "coordinates": self.coordinate(pixel)}})
        self.write_reference()
        def point(i, pixel):
            return {"id": f"source-control-{i}", "pixel": pixel, "referenceFeatureId": i,
                    "sourceReference": "SYNTHETIC symbol center; not an actual map place"}
        controls = [point(i, p) for i, p in enumerate(self.fit_pixels)]
        checks = [point(i + 4, p) for i, p in enumerate(self.check_pixels)]
        self.spec = {
            "mapId": "synthetic-southern-western-map", "mode": "SYNTHETIC",
            "method": registration.METHOD,
            "originalSHA256": hashlib.sha256(self.raster.read_bytes()).hexdigest(),
            "raster": {"width": 128, "height": 128},
            "sourceCRS": {"status": "UNKNOWN_FROM_MAP", "sourceReference": "SYNTHETIC unknown source projection"},
            "targetCRS": "EPSG:4326", "pixelConvention": "PIXEL_CENTER",
            "referenceDataset": {"sourceId": "synthetic-reference", "sourceVersion": "fixture-v1",
                "sourceURL": "https://example.invalid/SYNTHETIC-NOT-HISTORY", "license": "synthetic-test-fixture",
                "licenseReference": "Fixture generated for tests; no historical source claimed",
                "CRS": "EPSG:4326", "featureIdProperty": "stable_id",
                "SHA256": hashlib.sha256(self.reference.read_bytes()).hexdigest()},
            "controls": controls, "checkControls": checks,
            "splitDeclaration": {"predeclared": True, "fitIds": [p["id"] for p in controls],
                "checkIds": [p["id"] for p in checks], "sourceReference": "SYNTHETIC independent points declared before fit"},
            "uncertainty": {key: {"status": "UNQUANTIFIED", "sourceReference": "SYNTHETIC unquantified source error"}
                            for key in ("sourceMap", "referenceDataset")},
            "qualityProfile": {"grade": "FACT_BASED_VISUAL_GRADE", "profileId": "synthetic-known-equation",
                "sourceReference": "SYNTHETIC exact equation test",
                "selectionBasis": "Synthetic generated equation, limits fixed before fit; not a survey certificate",
                "limits": {"maxFitResidualMeters": 1, "maxCheckResidualMeters": 1,
                           "minCheckToFitHullRatio": 0.1}},
        }

    def coordinate(self, pixel):
        x, y = pixel
        return [-15 + x * 0.01 + y * 0.001, -25 + y * 0.01 - x * 0.001]

    def write_reference(self):
        self.reference.write_text(json.dumps(self.dataset))
        if hasattr(self, "spec"):
            self.spec["referenceDataset"]["SHA256"] = hashlib.sha256(self.reference.read_bytes()).hexdigest()

    def fit(self):
        return registration.fit_reference_controls(self.raster, self.reference, self.spec)

    def trace(self, parts, report=None):
        return registration.transform_traced_parts(self.raster, self.reference, report or self.fit(), parts)

    def assert_code(self, code, callback):
        with self.assertRaises(registration.RegistrationError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_known_equation_preserves_target_order_without_source_projection_claim(self):
        report = self.fit()
        result = self.trace([[[30, 30], [64, 64], [97, 97]]], report)
        for actual, expected in zip(result["lines"][0]["coordinates"], map(self.coordinate, [[30, 30], [64, 64], [97, 97]])):
            for a, b in zip(actual, expected):
                self.assertAlmostEqual(a, b, places=10)
        self.assertEqual(report["sourceCRS"]["status"], "UNKNOWN_FROM_MAP")
        self.assertFalse(report["sourceProjectionKnown"])
        self.assertEqual(report["targetCRS"], "EPSG:4326")
        self.assertEqual(report["runtimeAdmission"], "NOT_ADMITTED")
        self.assertFalse(report["historicalAccuracyVerified"])
        self.assertFalse(report["uncertainty"]["registrationResidualIsTotalAccuracy"])
        self.assertIsNone(report["uncertainty"]["totalPositionalAccuracyMeters"])
        self.assertFalse(report["splitPredeclarationExternallyVerified"])

    def test_half_pixel_corner_offset_is_explicit_and_correct(self):
        report = self.fit()
        self.assertEqual(report["transform"]["gdalCornerOffset"], [0.5, 0.5])
        self.assertAlmostEqual(report["transform"]["coefficients"][0], -15.0055, places=10)
        self.assertAlmostEqual(report["transform"]["coefficients"][3], -25.0045, places=10)
        self.spec["pixelConvention"] = "PIXEL_CORNER"
        self.assert_code("PIXEL_CONVENTION_REQUIRED", self.fit)

    def test_original_and_reference_hash_tampering_rejected(self):
        report = self.fit()
        self.reference.write_text(self.reference.read_text() + " ")
        self.assert_code("BOUND_FILE_HASH_MISMATCH", lambda: self.trace([[[50, 50], [60, 60]]], report))
        self.write_reference()
        self.raster.write_bytes(self.raster.read_bytes() + b"TAMPER")
        self.assert_code("BOUND_FILE_HASH_MISMATCH", self.fit)

    def test_original_dimensions_are_bound(self):
        self.spec["raster"]["width"] = 127
        self.assert_code("ORIGINAL_DIMENSION_MISMATCH", self.fit)

    def test_reference_coordinates_cannot_be_overridden(self):
        self.spec["controls"][0]["coordinate"] = [0, 0]
        self.assert_code("REFERENCE_COORDINATE_MISMATCH", self.fit)

    def test_missing_ambiguous_and_nonpoint_reference_rejected(self):
        self.spec["controls"][0]["referenceFeatureId"] = "unavailable"
        self.assert_code("REFERENCE_FEATURE_UNAVAILABLE", self.fit)
        self.spec["controls"][0]["referenceFeatureId"] = 0
        self.dataset["features"].append(copy.deepcopy(self.dataset["features"][0]))
        self.write_reference()
        self.assert_code("REFERENCE_FEATURE_UNAVAILABLE", self.fit)
        self.dataset["features"].pop()
        self.dataset["features"][0]["geometry"] = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
        self.write_reference()
        self.assert_code("REFERENCE_FEATURE_NOT_POINT", self.fit)

    def test_source_crs_cannot_be_forged_as_wgs84(self):
        self.spec["sourceCRS"]["definition"] = "EPSG:4326"
        self.assert_code("FALSE_SOURCE_CRS_CLAIM", self.fit)

    def test_insufficient_collinear_and_reused_controls_rejected(self):
        saved = copy.deepcopy(self.spec)
        self.spec["controls"] = self.spec["controls"][:3]
        self.assert_code("INSUFFICIENT_CONTROLS", self.fit)
        self.spec = copy.deepcopy(saved)
        for i, p in enumerate(self.spec["controls"]):
            p["pixel"] = [11 + i * 20, 13 + i * 20]
        self.assert_code("COLLINEAR_CONTROLS", self.fit)
        self.spec = copy.deepcopy(saved)
        self.spec["checkControls"][0]["referenceFeatureId"] = 0
        self.assert_code("CHECKS_NOT_INDEPENDENT", self.fit)

    def test_split_order_or_membership_changes_require_new_declaration(self):
        self.spec["controls"].reverse()
        self.assert_code("SPLIT_DECLARATION_MISMATCH", self.fit)

    def test_independent_error_is_not_hidden_by_small_fit_error(self):
        self.dataset["features"][4]["geometry"]["coordinates"][0] += 0.1
        self.write_reference()
        self.assert_code("CHECK_RESIDUAL_EXCEEDS_BUDGET", self.fit)

    def test_fit_error_is_not_hidden_by_relaxed_check_limit(self):
        self.spec["qualityProfile"]["limits"]["maxCheckResidualMeters"] = 100000
        self.dataset["features"][0]["geometry"]["coordinates"][0] += 0.1
        self.write_reference()
        self.assert_code("FIT_RESIDUAL_EXCEEDS_BUDGET", self.fit)

    def test_quality_limits_and_unknown_uncertainty_are_not_invented(self):
        saved = copy.deepcopy(self.spec)
        del self.spec["qualityProfile"]["limits"]["maxCheckResidualMeters"]
        self.assert_code("INVALID_DATA", self.fit)
        self.spec = copy.deepcopy(saved)
        self.spec["uncertainty"]["sourceMap"]["meters"] = 0
        self.assert_code("UNQUANTIFIED_ERROR_IS_NOT_ZERO", self.fit)
        self.spec = copy.deepcopy(saved)
        self.spec["mode"] = "SOURCE_MAP"
        self.spec["uncertainty"]["sourceMap"] = {"status": "SYNTHETIC_KNOWN", "meters": 0,
                                                       "sourceReference": "invented certainty"}
        self.assert_code("SYNTHETIC_UNCERTAINTY_ON_SOURCE", self.fit)

    def test_new_approximate_policy_check_hull_is_warning_not_trace_support(self):
        self.spec["qualityProfile"]["limits"]["minCheckToFitHullRatio"] = 0.8
        report = self.fit()
        self.assertIn("INDEPENDENT_CHECK_FOOTPRINT_SMALL_RELATIVE_TO_FIT", report["warnings"])
        self.assertEqual(report["coverage"]["checkHullRole"], "MODEL_VALIDATION_SPATIAL_DISTRIBUTION_WARNING_ONLY")
        result = self.trace([[[15, 15], [20, 20]]], report)
        self.assertEqual(result["retainedEdgeCount"], 1)

    def test_report_tampering_rejected_even_when_report_hash_recomputed(self):
        report = self.fit()
        report["runtimeAdmission"] = "ADMITTED"
        report["reportSHA256"] = hashlib.sha256(registration._canonical({
            k: v for k, v in report.items() if k != "reportSHA256"})).hexdigest()
        self.assert_code("REPORT_MISMATCH", lambda: self.trace([[[40, 40], [60, 60]]], report))

    def test_supported_subset_preserves_exact_vertices_and_accounts_every_edge(self):
        parts = [[[0, 50], [20, 50], [40, 50], [127, 50], [60, 60], [80, 80]],
                 [[90, 90], [100, 100]]]
        original = copy.deepcopy(parts)
        result = self.trace(parts)
        self.assertEqual(result["inputParts"], parts)
        self.assertEqual(parts, original)
        self.assertEqual([line["sourceVertexIndices"] for line in result["lines"]], [[1, 2], [4, 5], [0, 1]])
        self.assertEqual([line["sourcePartIndex"] for line in result["lines"]], [0, 0, 1])
        self.assertEqual(result["inputEdgeCount"], 6)
        self.assertEqual(result["retainedEdgeCount"], 3)
        self.assertEqual(result["excludedEdgeCount"], 3)
        self.assertEqual(result["inventedVertexCount"], 0)
        self.assertFalse(result["gapBridgingPerformed"])
        self.assertFalse(result["polygonInferred"])
        for line in result["lines"]:
            self.assertEqual(line["sourcePixels"], [parts[line["sourcePartIndex"]][i]
                                                    for i in line["sourceVertexIndices"]])

    def test_crossing_edge_without_supported_original_endpoints_is_excluded_not_clipped(self):
        result = self.trace([[[0, 64], [127, 64]]])
        self.assertEqual(result["lines"], [])
        self.assertEqual(result["excludedEdgeCount"], 1)
        self.assertEqual(result["inventedVertexCount"], 0)

    def test_original_gaps_remain_separate_even_if_parts_touch(self):
        result = self.trace([[[40, 40], [50, 50]], [[50, 50], [60, 60]]])
        self.assertEqual(len(result["lines"]), 2)
        self.assertEqual([p["sourcePartIndex"] for p in result["lines"]], [0, 1])

    def test_json_roundtrip_deterministic_and_no_vertex_loss(self):
        report = json.loads(json.dumps(self.fit()))
        parts = [[[20 + i / 10, 40] for i in range(160)]]
        result = self.trace(parts, report)
        self.assertEqual(len(result["lines"][0]["coordinates"]), 160)
        self.assertEqual(result["retainedEdgeCount"], 159)
        self.assertEqual(result, self.trace(json.loads(json.dumps(parts)), report))

    def test_unsupported_coordinates_and_nonfinite_pixels_rejected(self):
        self.assert_code("PIXEL_OUTSIDE_ORIGINAL", lambda: self.trace([[[-1, 50], [50, 50]]]))
        self.assert_code("INVALID_DATA", lambda: self.trace([[[float("nan"), 50], [50, 50]]]))
        self.assert_code("INVALID_TRACES", lambda: self.trace([[[50, 50]]]))

    def test_reference_crs_and_license_evidence_required(self):
        saved = copy.deepcopy(self.spec)
        self.spec["referenceDataset"]["CRS"] = "EPSG:3857"
        self.assert_code("REFERENCE_CRS_UNSUPPORTED", self.fit)
        self.spec = copy.deepcopy(saved)
        self.spec["referenceDataset"]["license"] = ""
        self.assert_code("INVALID_DATA", self.fit)

    def test_antimeridian_affine_fit_fails_explicitly(self):
        self.dataset["features"][0]["geometry"]["coordinates"][0] = 179
        self.dataset["features"][1]["geometry"]["coordinates"][0] = -179
        self.write_reference()
        self.assert_code("ANTIMERIDIAN_UNSUPPORTED", self.fit)


if __name__ == "__main__":
    unittest.main()
