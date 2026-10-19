"""Actual preserved SFX revision engine; no media render or job start."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
PARENT = HERE.parent / "production-studio-mvp-v1"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(HERE))
import studio_contracts as original

_spec = importlib.util.spec_from_file_location("_completion_revision_bridge_under_test", HERE / "revision_bridge.py")
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)
_fixture_spec = importlib.util.spec_from_file_location("_completion_original_revision_fixture", PARENT / "tests/test_studio_contracts.py")
fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(fixture)
DIGEST = "sha256:" + "b" * 64


def submission(metadata=True):
    result = original.normalize_submission({"sceneJson": fixture.fixture(), "profile": "UNIVERSAL_V3"},
        image_digest=DIGEST, backend=fixture.FakeBackend())
    if metadata:
        result["integration"] = {"schema": "WORLD_ENGINE_UNIVERSAL_INTEGRATION_V1", "profile": "VISUAL_UNIFIED_V1",
            "visualProfile": {"territoryOpacity": .62, "frontCoreWidthPixels": 4.8,
                "frontGlowRadiusPixels": 10, "frontGlowGain": .42, "cameraApproachFrames": 48}}
        result["completionV2"] = {"schema": "WORLD_ENGINE_UNIVERSAL_COMPLETION_V2",
            "profile": "VISUAL_UNIFIED_COMPLETION_V2", "dataPolicy": "QUALIFIED_SOURCE_ONLY",
            "camera": {"mode": "V5_EVENT_TRACKING", "settleFrames": 18, "holdFrames": 24},
            "frontier": {"profile": "AUTHORED_FRONT_MOTION_V2", "enabled": True,
                         "motionResponse": True, "settledStrength": .2, "settleFrames": 18},
            "eventFlow": {"schema": "WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1", "events": [], "flows": [], "areas": []}}
    return result


class RevisionBridgeTests(unittest.TestCase):
    def revise(self, value, prompt="효과음 음량 40%", sfx=None, parent_revision=original.plan_revision):
        return bridge.plan_revision(value, 0, 20, prompt, sfx, parent_revision=parent_revision)

    def error(self, code, callback):
        with self.assertRaises(original.StudioContractError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_original_revision_preserves_metadata_and_frozen_video_exactly(self):
        old = submission()
        before = deepcopy(old)
        result = self.revise(old)
        expected = original.plan_revision(old, 0, 20, "효과음 음량 40%")
        self.assertEqual(result, expected)
        self.assertEqual(old, before)
        self.assertEqual(result["submission"]["integration"], old["integration"])
        self.assertEqual(result["submission"]["completionV2"], old["completionV2"])
        self.assertEqual(result["submission"]["videoPlan"], old["videoPlan"])
        self.assertFalse(result["impact"]["requiresGpu"])
        self.assertEqual(len(result["impact"]["reusedSceneIds"]), 4)
        self.assertNotEqual(result["submission"]["sfx"], old["sfx"])

    def test_original_v1_without_completion_is_unchanged(self):
        old = submission(metadata=False)
        self.assertEqual(self.revise(old), original.plan_revision(old, 0, 20, "효과음 음량 40%"))

    def test_existing_integration_only_metadata_is_preserved(self):
        old = submission()
        old.pop("completionV2")
        result = self.revise(old, prompt="효과음 끄기")
        self.assertEqual(result["submission"]["integration"], old["integration"])
        self.assertNotIn("completionV2", result["submission"])

    def test_original_visual_revision_rejection_is_preserved(self):
        self.error("STUDIO_VISUAL_REVISION_UNSUPPORTED", lambda: self.revise(submission(), "카메라를 확대해줘"))

    def test_exact_original_frame_validation_is_preserved(self):
        self.error("STUDIO_REVISION_TIME_INVALID", lambda: bridge.plan_revision(submission(), .01, 20,
            "효과음 끄기", parent_revision=original.plan_revision))

    def test_explicit_sfx_argument_keeps_existing_api(self):
        old = submission()
        result = self.revise(old, prompt="효과음", sfx={"enabled": False})
        self.assertEqual(result, original.plan_revision(old, 0, 20, "효과음", {"enabled": False}))

    def test_dropped_or_changed_integration_metadata_is_rejected(self):
        for field in ("integration", "completionV2", "videoPlan"):
            for action in ("drop", "change"):
                def bad(*args, _field=field, _action=action):
                    result = original.plan_revision(*args)
                    if _action == "drop":
                        result["submission"].pop(_field)
                    else:
                        result["submission"][_field] = {}
                    return result
                with self.subTest(field=field, action=action):
                    self.error("STUDIO_COMPLETION_REVISION_METADATA_CHANGED", lambda: self.revise(submission(), parent_revision=bad))

    def test_gpu_requiring_or_invalidating_revision_is_rejected(self):
        for key, value in (("requiresGpu", True), ("invalidatedSceneIds", ["scene-0"])):
            def bad(*args, _key=key, _value=value):
                result = original.plan_revision(*args)
                result["impact"][_key] = _value
                return result
            with self.subTest(key=key):
                self.error("STUDIO_VISUAL_REVISION_UNSUPPORTED", lambda: self.revise(submission(), parent_revision=bad))

    def test_incomplete_scene_reuse_is_rejected(self):
        def bad(*args):
            result = original.plan_revision(*args)
            result["impact"]["reusedSceneIds"].pop()
            return result
        self.error("STUDIO_COMPLETION_REVISION_REUSE_INVALID", lambda: self.revise(submission(), parent_revision=bad))

    def test_parent_mutation_is_rejected(self):
        def bad(parent, *args):
            result = original.plan_revision(parent, *args)
            parent["title"] = "unexpected mutation"
            return result
        self.error("STUDIO_COMPLETION_REVISION_PARENT_MUTATED", lambda: self.revise(submission(), parent_revision=bad))

    def test_invalid_parent_or_result_rejected(self):
        self.error("STUDIO_REVISION_PARENT_INVALID", lambda: self.revise([]))
        self.error("STUDIO_COMPLETION_REVISION_RESULT_INVALID", lambda: self.revise(submission(), parent_revision=lambda *args: {}))


if __name__ == "__main__":
    unittest.main()
