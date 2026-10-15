"""Focused integration-boundary regressions; no hardware or old suite runs."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "check_integration.py"
spec = importlib.util.spec_from_file_location("astra_connection_audit", MODULE)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
REPO = MODULE.parents[3]


class CurrentBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anchors = audit_module.baseline_hashes(REPO)
        cls.current = audit_module.audit(REPO, anchors=cls.anchors)

    def test_actual_pinned_path_is_audited_without_claiming_gpu_or_integration_pass(self):
        self.assertEqual(self.current["auditStatus"], "PASS")
        self.assertEqual(self.current["integrationDecision"], "BLOCKED_PROTECTED_ACTIVE_SELECTOR")
        for key in ("gpuExecuted", "renderExecuted", "imageBuilt", "imageInspectionExecuted",
                    "oldFullTestsExecuted", "archiveMembersReaudited"):
            self.assertIs(self.current[key], False)

    def test_approved_renderer_camera_scene_and_frontier_match_existing_contract(self):
        self.assertEqual(self.current["sourcePreservation"], "PASS")
        original = self.current["selectedOriginalContractChecks"]
        for role in ("nativeRenderer", "cameraV5", "camera", "scenePlan", "nativeScene", "frontier"):
            self.assertIn({"path": audit_module.PATHS[role], "status": "PASS"}, original)
        for reference in self.current["protectedConnectionReferences"]:
            lines = (REPO / reference["path"]).read_text().splitlines()
            self.assertIn(reference["sourceText"], lines[reference["line"] - 1])

    def test_saved_sample_coverage_is_partial_without_forbidding_explicit_fallback(self):
        saved = self.current["savedCoverage"]
        self.assertTrue(saved["partialFallbackAllowed"])
        self.assertTrue(saved["partialIntegrationNotBlockedByCoverageAlone"])
        self.assertFalse(saved["cameraReevaluatedThisRun"])
        self.assertEqual(saved["actualFrameCountInSavedEvidence"], 150)
        for role in ("terrain", "bathymetry", "surfaceTexture"):
            coverage = saved["roles"][role]
            self.assertFalse(coverage["fullEnvelopeCovered"])
            self.assertGreater(coverage["envelopeDegreeAreaFraction"], 0)
            self.assertLess(coverage["envelopeDegreeAreaFraction"], 1)

    def test_existing_native_mask_is_not_misreported_missing(self):
        mask = next(item for item in self.current["classification"]
                    if item["feature"] == "native_gis_screen_coverage_mask")
        self.assertEqual(mask["state"], "IMPLEMENTED_BASELINE")
        self.assertIs(mask["geographicRasterMaskRequiredForGpuFragmentGating"], False)

    def test_original_contract_contains_cpu_and_archive_but_not_neutral_npz_bodies(self):
        packaged = self.current["imagePackagingEvidence"]
        self.assertTrue(packaged["originalSampleArchivePackaged"])
        self.assertGreater(len(packaged["cpuModulePaths"]), 10)
        self.assertEqual(len(packaged["neutralArtifacts"]), 3)
        self.assertFalse(any(item["selectedByOriginalContract"] for item in packaged["neutralArtifacts"]))
        self.assertIs(packaged["heightSourcePresent"], False)

    def test_cli_success_means_audit_finished_and_integration_stays_blocked(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = audit_module.main(["--repo-root", str(REPO)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["integrationDecision"], "BLOCKED_PROTECTED_ACTIVE_SELECTOR")


class MutatedBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anchors = audit_module.baseline_hashes(REPO)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        for relative in audit_module.PATHS.values():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO / relative).read_bytes())

    def tearDown(self):
        self.directory.cleanup()

    def check_rejected(self, role):
        result = audit_module.audit(self.root, anchors=self.anchors)
        self.assertEqual(result["auditStatus"], "FAIL")
        self.assertEqual(result["sourcePreservation"], "FAIL")
        self.assertEqual(result["integrationDecision"], "BLOCKED_SOURCE_AUDIT_REQUIRED")
        self.assertNotIn("connectionConditions", result)
        failed = next(item for item in result["sourceChecks"] if item["role"] == role)
        self.assertEqual(failed["status"], "FAIL")
        return result

    def test_changed_native_scene_cannot_pass_source_protection(self):
        path = self.root / audit_module.PATHS["nativeScene"]
        scene = json.loads(path.read_text())
        scene["primary_region_id"] = "different_explicit_fixture"
        path.write_text(json.dumps(scene))
        self.check_rejected("nativeScene")

    def test_unexpected_runtime_hook_is_unknown_not_misclassified_connected(self):
        path = self.root / audit_module.PATHS["hardwareRuntime"]
        with path.open("a") as stream:
            stream.write("\nawait import('/modules/unreviewed_astra_hook.mjs');\n")
        result = self.check_rejected("hardwareRuntime")
        self.assertEqual(result["classification"], [{"feature": "active_render_selection",
                                                     "state": "UNKNOWN_SOURCE_CHANGED"}])

    def test_modified_metadata_cannot_claim_global_coverage(self):
        path = self.root / audit_module.PATHS["sampleMetadata"]
        metadata = json.loads(path.read_text())
        metadata["terrain"]["actualBounds"] = [-180, -90, 180, 90]
        path.write_text(json.dumps(metadata))
        self.check_rejected("sampleMetadata")

    def test_missing_contract_fails_closed(self):
        (self.root / audit_module.PATHS["sourceContract"]).unlink()
        self.check_rejected("sourceContract")

    def test_source_symlink_is_rejected_even_if_bytes_match(self):
        path = self.root / audit_module.PATHS["hardwareCapture"]
        path.unlink()
        path.symlink_to(REPO / audit_module.PATHS["hardwareCapture"])
        self.check_rejected("hardwareCapture")


class GeographicBoundaryTests(unittest.TestCase):
    def test_arbitrary_western_southern_coverage(self):
        result = audit_module.coverage([-50, -40, -40, -30], [-60, -50, -30, -20])
        self.assertAlmostEqual(result["envelopeDegreeAreaFraction"], 1 / 9)
        self.assertEqual(result["intersectionBBox"], [-50, -40, -40, -30])

    def test_disjoint_extent_is_not_successful_support(self):
        result = audit_module.coverage([10, 10, 20, 20], [-30, -30, -20, -20])
        self.assertEqual(result["envelopeDegreeAreaFraction"], 0)
        self.assertIsNone(result["intersectionBBox"])
        self.assertFalse(result["fullEnvelopeCovered"])

    def test_covering_extent_is_marked_full(self):
        result = audit_module.coverage([-70, -50, -20, -10], [-60, -40, -30, -20])
        self.assertEqual(result["envelopeDegreeAreaFraction"], 1)
        self.assertTrue(result["fullEnvelopeCovered"])

    def test_unsupported_dateline_extent_is_explicit_not_normalized_wrongly(self):
        with self.assertRaisesRegex(audit_module.AuditError, "INVALID_SAVED_NON_WRAPPING_BBOX"):
            audit_module.coverage([170, -20, -170, 20], [-10, -10, 10, 10])

    def test_invalid_coordinates_and_nonnumeric_values_are_rejected(self):
        for bounds in ([0, 0, 181, 10], [0, -91, 10, 0], [False, 0, 1, 1], [0, 0, float("nan"), 1]):
            with self.subTest(bounds=bounds), self.assertRaises(audit_module.AuditError):
                audit_module.coverage(bounds, [-10, -10, 10, 10])


if __name__ == "__main__":
    unittest.main()
