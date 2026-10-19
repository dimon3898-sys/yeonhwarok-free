import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import preview_contract as preview


def original():
    return json.loads((HERE.parent / "verified-front-data-v4-recovery/VIDEO_PLAN_80S.json").read_bytes())


def bindings(raw=b"source"):
    return {"sourceCommit": "a" * 40, "sourceManifestSHA256": "b" * 64,
            "imageDigest": "sha256:" + "c" * 64, "originalPlanSHA256": hashlib.sha256(raw).hexdigest(),
            "completionProfileSHA256": "d" * 64, "sourceCatalogSHA256": "e" * 64}


class PreviewContractTests(unittest.TestCase):
    def test_actual_80s_selects_supplied_transitions_and_retains_source(self):
        plan = original()
        before = preview.canonical(plan)
        result = preview.compile_preview(plan, bindings=bindings())
        self.assertEqual(result["range"], {"startFrame": 1400, "endFrame": 1550, "fps": 30,
            "totalFrames": 2400, "frameCount": 150, "frameConvention": "GLOBAL_HALF_OPEN", "localPtsFrameOrigin": 0})
        self.assertEqual(result["selection"]["sourceActivityFrames"], 100)
        self.assertEqual(result["sceneSlices"][0]["sceneId"], "scene-0007")
        self.assertEqual(result["audioClock"]["sampleCount"], 240000)
        self.assertFalse(result["hardwareVerified"])
        self.assertEqual(before, preview.canonical(plan))

    def test_explicit_cross_workunit_range_keeps_original_scene_hashes(self):
        plan = original()
        result = preview.compile_preview(plan, bindings=bindings(), start_frame=400)
        self.assertEqual([(r["sceneId"], r["startFrame"], r["endFrame"]) for r in result["sceneSlices"]],
                         [("scene-0001", 400, 445), ("scene-0002", 445, 550)])
        self.assertEqual(sum(r["endFrame"] - r["startFrame"] for r in result["sceneSlices"]), 150)
        self.assertEqual(result["sceneSlices"][0]["originalSceneSHA256"],
                         preview.sha256(preview.canonical(plan["scenes"][1])))

    def test_other_region_and_long_duration_use_same_contract(self):
        plan = {"schema": "WORLD_ENGINE_UNIVERSAL_VIDEO_V2", "durationSeconds": 600, "fps": 30,
            "totalFrames": 18000, "resolution": {"width": 1080, "height": 1920}, "aspectRatio": "9:16",
            "legacyScenePlan": {"timing": {"total_frames": 18000, "fps": 30},
                                "camera_intent": {"anchor": [-70, -33]}},
            "scenes": [{"sceneId": "other-event", "startFrame": 0, "endFrame": 18000}]}
        result = preview.compile_preview(plan, bindings=bindings(), start_frame=17850)
        self.assertEqual(result["range"]["endFrame"], 18000)
        self.assertEqual(result["sceneSlices"][0]["sceneId"], "other-event")
        self.assertFalse(result["selection"]["geometryInterpolationAdded"])

    def test_range_cannot_request_full_scene_or_full_80s(self):
        for count in (0, True, 149, 151, 200, 2400):
            with self.subTest(count=count), self.assertRaisesRegex(preview.PreviewError, "ONLY_150"):
                preview.compile_preview(original(), bindings=bindings(), frame_count=count)

    def test_invalid_frame_and_fps_are_rejected(self):
        for frame in (-1, True, 2251, 1.5):
            with self.subTest(frame=frame), self.assertRaises(preview.PreviewError):
                preview.compile_preview(original(), bindings=bindings(), start_frame=frame)
        plan = original()
        plan["fps"] = 60
        with self.assertRaisesRegex(preview.PreviewError, "30FPS"):
            preview.compile_preview(plan, bindings=bindings())

    def test_original_scene_gap_overlap_and_reset_are_rejected(self):
        for value in (199, 201):
            plan = original()
            plan["scenes"][1]["startFrame"] = value
            with self.assertRaisesRegex(preview.PreviewError, "HALF_OPEN_COVERAGE"):
                preview.compile_preview(plan, bindings=bindings())
        plan = original()
        plan["legacyScenePlan"]["timing"]["total_frames"] = 150
        with self.assertRaisesRegex(preview.PreviewError, "GLOBAL_CLOCK"):
            preview.compile_preview(plan, bindings=bindings())

    def test_unknown_binding_or_malformed_digest_does_not_fall_back(self):
        for mutate in (lambda b: b.update(extra="ignored"), lambda b: b.update(imageDigest="latest"),
                       lambda b: b.update(sourceCommit="main")):
            b = bindings()
            mutate(b)
            with self.assertRaises(preview.PreviewError):
                preview.compile_preview(original(), bindings=b)

    def test_tampered_range_scene_and_unknown_field_rejected(self):
        plan = original()
        request = preview.compile_preview(plan, bindings=bindings())
        mutations = (lambda r: r["range"].update(startFrame=0),
                     lambda r: r["sceneSlices"][0].update(originalSceneSHA256="f" * 64),
                     lambda r: r.update(forceGPU=True), lambda r: r.update(renderAllowedByRequest=True))
        for mutate in mutations:
            changed = copy.deepcopy(request)
            mutate(changed)
            with self.assertRaisesRegex(preview.PreviewError, "SOURCE_OR_RANGE"):
                preview.validate_preview(changed, plan)

    def test_actual_raw_plan_hash_required_at_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            p, r = Path(directory) / "PLAN.json", Path(directory) / "PREVIEW_REQUEST.json"
            raw = json.dumps(original(), ensure_ascii=False).encode()
            p.write_bytes(raw)
            request = preview.compile_preview(json.loads(raw), bindings=bindings(raw))
            r.write_text(json.dumps(request))
            self.assertEqual(preview.verify_preview_request_file(r, p), request)
            p.write_bytes(raw + b"\n")
            with self.assertRaisesRegex(preview.PreviewError, "ACTUAL_PLAN_BYTES"):
                preview.verify_preview_request_file(r, p)

    def test_symlinked_source_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            actual, link = Path(directory) / "actual.json", Path(directory) / "link.json"
            actual.write_text("{}")
            link.symlink_to(actual)
            with self.assertRaisesRegex(preview.PreviewError, "REGULAR_SOURCE"):
                preview.verify_preview_request_file(link, actual)
            self.assertEqual(actual.read_text(), "{}")

    def test_trusted_operator_bindings_are_not_client_replaceable(self):
        plan = original()
        request = preview.compile_preview(plan, bindings=bindings())
        trusted = bindings()
        trusted["imageDigest"] = "sha256:" + "f" * 64
        with self.assertRaisesRegex(preview.PreviewError, "TRUSTED_BINDINGS"):
            preview.validate_preview(request, plan, bindings=trusted)


if __name__ == "__main__":
    unittest.main()
