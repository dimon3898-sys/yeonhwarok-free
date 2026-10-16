"""Focused synthetic builder tests; these fixtures are not historical evidence."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).parents[1]
builder = load("tested_front_builder", HERE / "build_front_profile.py")
control_tests = load("synthetic_control_fixture_for_builder", Path(__file__).with_name("test_control_registration.py"))


class ReproducibleFrontBuilderSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.helper = control_tests.ApproximateControlRegistrationSyntheticTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)
        self.root = self.helper.root
        self.spec = copy.deepcopy(self.helper.spec)
        self.spec["mode"] = "SOURCE_MAP"
        self.spec["source"] = {"pdfSHA256": "d" * 64, "pdfPageIndex0": 22, "frontDate": "1951-01-24"}
        self.front_id = "SYNTHETIC-NOT-HISTORY-front"
        self.trace = {"mapId": self.spec["mapId"], "frontDate": "1951-01-24",
            "originalSHA256": self.spec["originalSHA256"], "raster": self.spec["raster"],
            "pixelConvention": "PIXEL_CENTER", "sourcePage": {"pdfPageIndex0": 22},
            "sourcePixels": [[0, 50], [20, 50], [40, 50], [127, 50], [60, 60], [80, 80]]}
        self.admission = {"schema": builder.ADMISSION_SCHEMA, "frontId": self.front_id,
            "mapId": self.spec["mapId"], "mapDate": "1951-01-24", "classification": "OBSERVED_UN_FRONT",
            "documentSha256": "d" * 64, "rasterSha256": self.spec["originalSHA256"],
            "pixelTraceSha256": "", "pageIndex0": 22, "registrationMode": builder.REGISTRATION_MODE,
            "sourceCRSStatus": "UNKNOWN_FROM_MAP", "reviewStatus": "SOURCE_LINE_AND_TRACE_REVIEWED",
            "admission": "ADMITTED_APPROXIMATE_SOURCE_PARTIAL",
            "reviewerRole": "CODEX_SOURCE_REVIEW_NOT_HISTORIAN_CERTIFICATION",
            "cartographicAccuracy": "UNKNOWN_NOT_CERTIFIED", "arrowOrPhaseLine": False,
            "reference": "SYNTHETIC GENERATED CONTRACT FIXTURE, not an actual historical source"}
        self.plan = {"totalFrames": 60, "durationSeconds": 2, "fps": 30, "productionV3": {"eventChapters": [
            {"chapterId": "one", "startFrame": 0, "endFrame": 30},
            {"chapterId": "two", "startFrame": 30, "endFrame": 60}]}}
        self.recipe = {"schema": builder.RECIPE_SCHEMA, "semanticPolicy": copy.deepcopy(builder.SEMANTIC_POLICY),
            "basePlan": {}, "fronts": [{"frontId": self.front_id, "mapId": self.spec["mapId"]}],
            "schedule": [{"startFrame": 30, "endFrame": 60, "chapterId": "two", "eventDate": "1951-02-01",
                "mode": "ARCHIVAL_FRONT_ONLY", "frontId": self.front_id,
                "sourceLabel": "1951.01.24 SYNTHETIC-PARTIAL-SOURCE-NOT-HISTORY"}]}
        self.persist()

    def bound(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def persist(self):
        row = self.recipe["fronts"][0]
        row["mapRaster"] = {"path": self.helper.raster.name, "sha256": self.spec["originalSHA256"]}
        row["reference"] = {"path": self.helper.reference.name,
                            "sha256": hashlib.sha256(self.helper.reference.read_bytes()).hexdigest()}
        row["registrationSpec"] = self.bound("source/registration-spec.json", builder.serialized(self.spec))
        row["pixelTrace"] = self.bound("source/pixel-trace.json", builder.serialized(self.trace))
        self.admission["pixelTraceSha256"] = row["pixelTrace"]["sha256"]
        row["sourceAdmission"] = self.bound("source/review.json", builder.serialized(self.admission))
        self.recipe["basePlan"] = self.bound("source/parent-plan.json", builder.serialized(self.plan))
        self.bound("RECIPE.json", builder.serialized(self.recipe))

    def build(self):
        return builder.build_outputs(self.root)

    def assert_code(self, code, callback):
        with self.assertRaises(builder.BuildError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def stored(self, outputs):
        builder.materialize_outputs(outputs, self.root)
        return {name: json.loads(raw) for name, raw in outputs.items()}

    def rebind_generated(self, docs):
        """Keep every frozen byte/hash link valid when simulating tool versions."""
        reg_name = f"generated/{self.front_id}.registration.json"
        trace_name = f"generated/{self.front_id}.supported-trace.json"
        geo_name = f"generated/{self.front_id}.geojson"
        reg = docs[reg_name]
        reg.pop("reportSHA256", None)
        reg["reportSHA256"] = builder.digest(builder.registration._canonical(reg))
        trace = docs[trace_name]
        trace["registrationReportSHA256"] = reg["reportSHA256"]
        trace.pop("traceSHA256", None)
        trace["traceSHA256"] = builder.digest(builder.registration._canonical(trace))
        reg_file_sha = builder.digest(builder.serialized(reg))
        docs[geo_name]["features"][0]["properties"]["source"]["registrationReportSha256"] = reg_file_sha
        profile = docs["FRONT_PROFILE.json"]
        profile["fronts"][0]["source"]["registrationReportSha256"] = reg_file_sha
        profile["fronts"][0]["geoJsonSha256"] = builder.digest(builder.serialized(docs[geo_name]))
        report = docs["BUILD_REPRODUCTION.json"]
        report["outputs"] = {name: builder.digest(builder.serialized(value)) for name, value in docs.items()
                             if name != "BUILD_REPRODUCTION.json"}
        for name, value in docs.items():
            (self.root / name).write_bytes(builder.serialized(value))

    def test_recomputes_open_partial_geometry_and_runtime_profile_from_original_edges(self):
        outputs = self.build()
        profile = json.loads(outputs["FRONT_PROFILE.json"])
        front = profile["fronts"][0]
        geo = json.loads(outputs[front["sourceFile"]])
        self.assertEqual(front["geometry"], geo["features"][0]["geometry"])
        self.assertEqual(front["geoJsonSha256"], builder.digest(outputs[front["sourceFile"]]))
        self.assertEqual(front["geometry"]["type"], "MultiLineString")
        self.assertEqual([len(p) for p in front["geometry"]["coordinates"]], [2, 2])
        self.assertEqual(profile["semanticPolicy"], builder.SEMANTIC_POLICY)
        self.assertTrue(front["partialSegments"])
        self.assertEqual(front["source"]["cartographicAccuracy"], "UNKNOWN_NOT_CERTIFIED")
        self.assertFalse(front["source"]["historicalSurveyCertification"])
        self.assertGreaterEqual(front["source"]["registrationResidualMeters"], 0)
        report = json.loads(outputs["BUILD_REPRODUCTION.json"])
        self.assertEqual(report["totalFrames"], 60)
        self.assertEqual(report["eventChapters"], 2)
        self.assertFalse(report["basePlanModified"])
        self.assertEqual(report["fronts"][0]["originalEdgeCount"], 5)
        self.assertEqual(report["fronts"][0]["retainedEdgeCount"], 2)
        self.assertEqual(report["fronts"][0]["excludedEdgeCount"], 3)
        self.assertEqual(report["fronts"][0]["inventedVertexCount"], 0)

    def test_supported_coordinate_override_in_trace_is_ignored(self):
        before = self.build()
        self.trace["supportedCoordinates"] = [[[80, 80], [90, 90]]]
        self.persist()
        after = self.build()
        a, b = json.loads(before["FRONT_PROFILE.json"]), json.loads(after["FRONT_PROFILE.json"])
        self.assertEqual(a["fronts"][0]["geometry"], b["fronts"][0]["geometry"])

    def test_source_pixel_parts_keep_disconnected_source_gaps(self):
        points = self.trace.pop("sourcePixels")
        self.trace["sourcePixelParts"] = [points[:3], points[3:]]
        self.persist()
        result = json.loads(self.build()[f"generated/{self.front_id}.supported-trace.json"])
        self.assertEqual(result["inputPartCount"], 2)
        self.assertEqual([line["sourcePartIndex"] for line in result["lines"]], [0, 1])
        self.assertFalse(result["gapBridgingPerformed"])

    def test_only_one_source_part_representation_permitted(self):
        self.trace["sourceParts"] = [[[20, 20], [40, 40]]]
        self.persist()
        self.assert_code("UNAMBIGUOUS_ORIGINAL_TRACE_REQUIRED", self.build)

    def test_every_source_input_is_hash_bound(self):
        for key in ("mapRaster", "reference", "registrationSpec", "pixelTrace", "sourceAdmission"):
            with self.subTest(key=key):
                path = self.root / self.recipe["fronts"][0][key]["path"]
                raw = path.read_bytes()
                path.write_bytes(raw + b" ")
                self.assert_code("SOURCE_SHA_MISMATCH", self.build)
                path.write_bytes(raw)

    def test_review_cannot_change_map_document_page_date_or_trace(self):
        saved = copy.deepcopy(self.admission)
        for key, value, code in (
            ("mapId", "WRONG_MAP", "SOURCE_REVIEW_ID_MISMATCH"),
            ("documentSha256", "a" * 64, "SOURCE_DOCUMENT_DATE_PAGE_MISMATCH"),
            ("pageIndex0", 23, "SOURCE_DOCUMENT_DATE_PAGE_MISMATCH"),
            ("mapDate", "1951-01-25", "SOURCE_DOCUMENT_DATE_PAGE_MISMATCH"),
            ("rasterSha256", "a" * 64, "SOURCE_REVIEW_BYTES_MISMATCH"),
        ):
            with self.subTest(key=key):
                self.admission = copy.deepcopy(saved)
                self.admission[key] = value
                self.persist()
                self.assert_code(code, self.build)

    def test_arrows_phase_lines_unreviewed_and_false_certification_rejected(self):
        saved = copy.deepcopy(self.admission)
        for key, value in (("classification", "OPERATIONAL_PHASE_LINE"), ("arrowOrPhaseLine", True),
                           ("reviewStatus", "UNREVIEWED"), ("reviewerRole", "HUMAN_EXPERT_CERTIFIED"),
                           ("cartographicAccuracy", "SURVEY_CERTIFIED"), ("admission", "FORCE_ALLOW"),
                           ("arrowOrPhaseLine", 0)):
            with self.subTest(key=key, value=value):
                self.admission = copy.deepcopy(saved)
                self.admission[key] = value
                self.persist()
                self.assert_code("EXPLICIT_APPROXIMATE_SOURCE_REVIEW_REQUIRED", self.build)

    def test_no_invented_ownership_or_history_policy(self):
        self.recipe["semanticPolicy"]["inferOccupiedAreas"] = True
        self.persist()
        self.assert_code("NO_INFERRED_HISTORY_POLICY_REQUIRED", self.build)
        self.recipe["semanticPolicy"]["inferOccupiedAreas"] = 0
        self.persist()
        self.assert_code("NO_INFERRED_HISTORY_POLICY_REQUIRED", self.build)

    def test_future_source_overlap_and_crosschapter_schedule_rejected(self):
        saved = copy.deepcopy(self.recipe["schedule"])
        for mutate, code in (
            (lambda r: r[0].update(eventDate="1950-01-01"), "FUTURE_SOURCE_MAP_FORBIDDEN"),
            (lambda r: r.append(copy.deepcopy(r[0])), "SOURCE_SCHEDULE_BOUNDARY_MISMATCH"),
            (lambda r: r[0].update(startFrame=29), "SOURCE_SCHEDULE_CHAPTER_MISMATCH"),
            (lambda r: r[0].update(sourceLabel="NO_SEPARATED_QUALIFIER"), "MEASURED_DATE_GLYPH_LABEL_REQUIRED"),
        ):
            self.recipe["schedule"] = copy.deepcopy(saved)
            mutate(self.recipe["schedule"])
            self.persist()
            self.assert_code(code, self.build)

    def test_parent_duration_and_chapter_contiguity_are_not_changed(self):
        saved = copy.deepcopy(self.plan)
        self.plan["totalFrames"] = 61
        self.persist()
        self.assert_code("BASE_PLAN_FRAME_COUNT_MISMATCH", self.build)
        self.plan = copy.deepcopy(saved)
        self.plan["productionV3"]["eventChapters"][1]["startFrame"] = 31
        self.persist()
        self.assert_code("BASE_PLAN_CHAPTER_BOUNDARY_MISMATCH", self.build)

    def test_no_supported_edges_and_closed_source_rejected(self):
        self.trace["sourcePixels"] = [[0, 64], [127, 64]]
        self.persist()
        self.assert_code("NO_SUPPORTED_SOURCE_EDGES", self.build)
        self.trace["sourcePixels"] = [[20, 20], [30, 30], [20, 20]]
        self.persist()
        self.assert_code("CLOSED_SOURCE_FRONT_FORBIDDEN", self.build)

    def test_path_escape_and_symlink_input_rejected(self):
        saved = copy.deepcopy(self.recipe)
        self.recipe["fronts"][0]["mapRaster"]["path"] = "../outside.tif"
        self.bound("RECIPE.json", builder.serialized(self.recipe))
        self.assert_code("CANONICAL_RELATIVE_PATH_REQUIRED", self.build)
        self.recipe = saved
        alias = self.root / "alias.tif"
        alias.symlink_to(self.helper.raster)
        self.recipe["fronts"][0]["mapRaster"]["path"] = alias.name
        self.bound("RECIPE.json", builder.serialized(self.recipe))
        self.assert_code("SOURCE_SYMLINK_FORBIDDEN", self.build)

    def test_create_check_and_repeat_do_not_overwrite_existing_candidate(self):
        outputs = self.build()
        result = builder.materialize_outputs(outputs, self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(builder.materialize_outputs(outputs, self.root, check=True)["status"], "PASS")
        before = (self.root / "FRONT_PROFILE.json").read_bytes()
        changed = dict(outputs)
        changed["FRONT_PROFILE.json"] = b"different candidate"
        self.assert_code("GENERATED_OUTPUT_MISMATCH", lambda: builder.materialize_outputs(changed, self.root))
        self.assertEqual((self.root / "FRONT_PROFILE.json").read_bytes(), before)

    def test_numerical_verification_is_read_only_and_exact_on_same_tools(self):
        outputs = self.build()
        self.stored(outputs)
        before = {name: (self.root / name).read_bytes() for name in outputs}
        result = builder.verify_numerical_outputs(outputs, self.root)
        self.assertTrue(result["byteExactOutputs"])
        self.assertTrue(result["sourcePixelsAndEdgesExact"])
        self.assertFalse(result["gpuExecuted"])
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in outputs})

    def test_cross_version_software_difference_is_not_falsely_called_byte_exact(self):
        outputs = self.build()
        docs = self.stored(outputs)
        docs[f"generated/{self.front_id}.registration.json"]["software"] = {"gdal": "SYNTHETIC_OTHER_VERSION", "numpy": "TEST_OTHER"}
        self.rebind_generated(docs)
        result = builder.verify_numerical_outputs(outputs, self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["byteExactOutputs"])

    def test_numerical_tolerance_is_tight_and_cannot_be_expanded(self):
        outputs = self.build()
        docs = self.stored(outputs)
        geo_name = f"generated/{self.front_id}.geojson"
        docs[geo_name]["features"][0]["geometry"]["coordinates"][0][0][0] += 1e-5
        docs["FRONT_PROFILE.json"]["fronts"][0]["geometry"] = copy.deepcopy(docs[geo_name]["features"][0]["geometry"])
        self.rebind_generated(docs)
        self.assert_code("REPRODUCTION_NUMERICAL_MISMATCH", lambda: builder.verify_numerical_outputs(outputs, self.root))
        self.assert_code("REPRODUCTION_TOLERANCE_INVALID", lambda: builder.verify_numerical_outputs(
            outputs, self.root, coordinate_tolerance_degrees=1e-3))

    def test_declared_roundoff_tolerance_accepts_coordinates_without_changing_source_edges(self):
        outputs = self.build()
        docs = self.stored(outputs)
        geo_name = f"generated/{self.front_id}.geojson"
        trace_name = f"generated/{self.front_id}.supported-trace.json"
        delta = 2e-11
        docs[geo_name]["features"][0]["geometry"]["coordinates"][0][0][0] += delta
        docs["FRONT_PROFILE.json"]["fronts"][0]["geometry"] = copy.deepcopy(docs[geo_name]["features"][0]["geometry"])
        docs[trace_name]["lines"][0]["coordinates"][0][0] += delta
        self.rebind_generated(docs)
        result = builder.verify_numerical_outputs(outputs, self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["byteExactOutputs"])
        self.assertTrue(result["sourcePixelsAndEdgesExact"])

    def test_edge_disposition_tampering_is_rejected_even_with_rebound_hashes(self):
        outputs = self.build()
        docs = self.stored(outputs)
        docs[f"generated/{self.front_id}.supported-trace.json"]["excludedEdges"][0]["sourceVertexIndices"] = [1, 2]
        self.rebind_generated(docs)
        self.assert_code("REPRODUCTION_NUMERICAL_MISMATCH", lambda: builder.verify_numerical_outputs(outputs, self.root))

    def test_frozen_file_sha_and_profile_geometry_binding_are_checked(self):
        outputs = self.build()
        self.stored(outputs)
        path = self.root / "FRONT_PROFILE.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_code("FROZEN_OUTPUT_SHA_MISMATCH", lambda: builder.verify_numerical_outputs(outputs, self.root))

    def test_cli_read_only_verification_uses_documented_interface(self):
        outputs = self.build()
        self.stored(outputs)
        result = subprocess.run([sys.executable, "-B", str(HERE / "build_front_profile.py"), "--root", str(self.root),
            "--recipe", "RECIPE.json", "--output-root", str(self.root), "--verify-numerical"],
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["schema"], "WORLD_ENGINE_FRONT_NUMERICAL_REPRODUCTION_V1")


if __name__ == "__main__":
    unittest.main()
