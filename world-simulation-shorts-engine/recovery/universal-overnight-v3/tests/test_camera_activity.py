"""Trusted trace contracts; synthetic poses are not GPU execution evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import camera_activity as camera
import preview_contract as preview


def fixture():
    plan = {"schema": "WORLD_ENGINE_UNIVERSAL_VIDEO_V2", "durationSeconds": 20, "fps": 30,
        "totalFrames": 600, "resolution": {"width": 1080, "height": 1920}, "aspectRatio": "9:16",
        "renderProfile": {"imageDigest": "sha256:" + "a" * 64},
        "legacyScenePlan": {"timing": {"total_frames": 600, "fps": 30}, "camera_intent": {"anchor": [-70, -33]}},
        "scenes": [{"sceneId": "other-region", "startFrame": 0, "endFrame": 600,
                    "renderProfile": {"imageDigest": "sha256:" + "a" * 64}}],
        "productionV3": {"eventChapters": [{"chapterId": "same-phase", "startFrame": 0,
                          "presentationPolicy": {"geometryStateIds": ["gamma", "delta"]}}],
            "geometrySchedule": [{"chapterId": "same-phase", "startFrame": 100, "endFrame": 150,
                "mode": "TRANSITION_SUPPLIED_SNAPSHOTS", "fromStateId": "gamma", "toStateId": "delta"}]}}
    bindings = {"sourceCommit": "a" * 40, "sourceManifestSHA256": "b" * 64,
        "imageDigest": "sha256:" + "a" * 64, "originalPlanSHA256": preview.sha256(preview.canonical(plan)),
        "completionProfileSHA256": "c" * 64, "sourceCatalogSHA256": "d" * 64}
    modules = {name: "e" * 64 for name in camera.CAMERA_MODULE_PATHS}
    proof = {"traceSourceCommit": "f" * 40, "framesSHA256": "0" * 64, "receiptSHA256": "1" * 64,
        "sourceManifestSHA256": "2" * 64, "frameCount": 200, "startFrame": 0, "endFrame": 200,
        "originalPlanSHA256": bindings["originalPlanSHA256"]}
    rows = [{"frame": frame, "bounds": [-80 + min(frame, 49) / 100, -40, -60 + min(frame, 49) / 100, -20],
             "rawRgbaSHA256": "3" * 64, "pngSHA256": "4" * 64, "sourceProofIndices": [0]} for frame in range(200)]
    body = {"schema": camera.SCHEMA,
        "binding": {"planCameraSemanticSHA256": camera.camera_semantic_sha(plan),
                    "completionProfileSHA256": bindings["completionProfileSHA256"], "cameraModuleSHA256": modules},
        "sourceProofs": [proof], "observations": rows, "qualification": camera.QUALIFICATION}
    evidence = {**body, "evidenceSHA256": camera.sha(camera.canonical(body))}
    return plan, bindings, modules, evidence


class CameraActivityTests(unittest.TestCase):
    def test_other_region_trace_prefers_actual_joint_motion_over_static(self):
        plan, bindings, modules, evidence = fixture()
        camera.validate_camera_evidence(evidence, plan, bindings, module_hashes=modules)
        # Without observations, source-only phase coherence favors a later hold.
        fallback = preview.compile_preview(plan, bindings=bindings)
        self.assertEqual(fallback["selection"]["cameraActivity"]["status"], "NOT_OBSERVED")
        request = preview.compile_preview(plan, bindings=bindings, camera_evidence=evidence)
        self.assertEqual(request["range"]["startFrame"], 0)
        self.assertEqual(request["selection"]["phaseCoherentTransitionFrames"], 50)
        self.assertEqual(request["selection"]["cameraActivity"]["motionPairs"], 49)
        self.assertEqual(request["selection"]["cameraActivity"]["status"], "OBSERVED_MOVING")
        self.assertTrue(request["selection"]["explicitSourceEvidence"]["measuredScopeOnly"])
        self.assertEqual(camera.camera_window_metrics(evidence, 50, 200)["status"], "OBSERVED_STATIC")
        self.assertFalse(request["hardwareVerified"])
        preview.validate_preview(request, plan, camera_evidence=evidence)

    def test_unknown_frames_are_not_zero_motion_or_interpolated_poses(self):
        plan, bindings, modules, evidence = fixture()
        unknown = camera.camera_window_metrics(evidence, 100, 250)
        self.assertEqual(unknown["status"], "NOT_FULLY_OBSERVED")
        self.assertEqual(unknown["observedFrames"], 100)
        self.assertIsNone(unknown["motionPairs"])
        self.assertIsNone(unknown["boundsVariants"])
        self.assertEqual(camera.measured_candidate_windows(evidence, 150), list(range(51)))

    def test_identity_ignores_only_existing_approved_image_slots(self):
        plan, bindings, modules, evidence = fixture()
        rebound = copy.deepcopy(plan)
        rebound["renderProfile"]["imageDigest"] = "sha256:" + "5" * 64
        rebound["scenes"][0]["renderProfile"]["imageDigest"] = "sha256:" + "5" * 64
        self.assertEqual(camera.camera_semantic_sha(rebound), camera.camera_semantic_sha(plan))
        camera.validate_camera_evidence(evidence, rebound, bindings, module_hashes=modules)
        changed = copy.deepcopy(rebound)
        changed["legacyScenePlan"]["camera_intent"]["anchor"] = [-69, -33]
        with self.assertRaisesRegex(camera.CameraEvidenceError, "NOT_THIS_SOURCE"):
            camera.validate_camera_evidence(evidence, changed, bindings, module_hashes=modules)
        changed = copy.deepcopy(rebound)
        changed["scenes"][0]["cameraProfile"] = {"imageDigest": "unrelated-not-an-approved-slot"}
        self.assertNotEqual(camera.camera_semantic_sha(changed), camera.camera_semantic_sha(plan))

    def test_profile_or_camera_module_change_cannot_reuse_trace(self):
        plan, bindings, modules, evidence = fixture()
        altered = dict(bindings, completionProfileSHA256="6" * 64)
        with self.assertRaisesRegex(camera.CameraEvidenceError, "NOT_THIS_SOURCE"):
            camera.validate_camera_evidence(evidence, plan, altered, module_hashes=modules)
        altered_modules = dict(modules)
        altered_modules[next(iter(modules))] = "7" * 64
        with self.assertRaisesRegex(camera.CameraEvidenceError, "BYTES_CHANGED"):
            camera.validate_camera_evidence(evidence, plan, bindings, module_hashes=altered_modules)

    def test_package_loader_source_mismatch_is_unknown_not_static(self):
        plan, bindings, modules, evidence = fixture()
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "trusted-test-evidence.json"
            file.write_bytes(camera.canonical(evidence))
            self.assertEqual(camera.load_bound_camera_evidence(plan, bindings, evidence_file=file,
                                                               module_hashes=modules), evidence)
            changed = copy.deepcopy(plan)
            changed["totalFrames"] += 1
            self.assertIsNone(camera.load_bound_camera_evidence(changed, bindings, evidence_file=file,
                                                               module_hashes=modules))

    def test_body_tampering_and_unobserved_gpu_claim_are_rejected(self):
        plan, bindings, modules, evidence = fixture()
        tampered = copy.deepcopy(evidence)
        tampered["observations"][0]["bounds"][0] += 1
        with self.assertRaisesRegex(camera.CameraEvidenceError, "BODY_CHANGED"):
            camera.validate_camera_evidence(tampered, plan, bindings, module_hashes=modules)
        tampered = copy.deepcopy(evidence)
        tampered["qualification"]["physicalNvidiaVerified"] = True
        with self.assertRaisesRegex(camera.CameraEvidenceError, "SCHEMA_INVALID"):
            camera.validate_camera_evidence(tampered, plan, bindings, module_hashes=modules)

    def test_actual_saved_200_frame_package_excludes_static_default(self):
        file = HERE / "CAMERA_ACTIVITY_EVIDENCE.json"
        self.assertTrue(file.is_file(), "Actual measured package fixture must be persisted")
        evidence = json.loads(file.read_bytes())
        plan = json.loads((HERE.parent / "verified-front-data-v4-recovery/VIDEO_PLAN_80S.json").read_bytes())
        bindings = {"sourceCommit": "a" * 40, "sourceManifestSHA256": "b" * 64,
            "imageDigest": "sha256:" + "a" * 64, "originalPlanSHA256": preview.sha256(preview.canonical(plan)),
            "completionProfileSHA256": evidence["binding"]["completionProfileSHA256"], "sourceCatalogSHA256": "d" * 64}
        camera.validate_camera_evidence(evidence, plan, bindings, module_hashes=camera.camera_module_hashes())
        request = preview.compile_preview(plan, bindings=bindings, camera_evidence=evidence)
        self.assertEqual(request["range"]["startFrame"], 1400)
        self.assertEqual(request["range"]["endFrame"], 1550)
        self.assertGreater(request["selection"]["cameraActivity"]["motionPairs"], 0)
        self.assertEqual(request["selection"]["cameraActivity"]["boundsVariants"], 48)
        self.assertEqual(request["selection"]["sourceActivityFrames"], 100)
        self.assertEqual(camera.camera_window_metrics(evidence, 1450, 1600)["status"], "OBSERVED_STATIC")
        self.assertEqual(request["selection"]["cameraHardwareVerification"], "GPU_PENDING")


if __name__ == "__main__":
    unittest.main()
