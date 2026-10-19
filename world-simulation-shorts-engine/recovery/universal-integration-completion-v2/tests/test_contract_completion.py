"""Completion request validation: fixtures are separate from real source proof."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
ORIGINAL = HERE.parent / "production-studio-mvp-v1"
sys.path.insert(0, str(ORIGINAL))
import studio_contracts as original

_spec = importlib.util.spec_from_file_location("_completion_contract_under_test", HERE / "contract_v2.py")
contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(contract)
_fixture_spec = importlib.util.spec_from_file_location("_completion_preserved_backend_fixture", ORIGINAL / "tests/test_studio_contracts.py")
fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(fixture)
DIGEST = "sha256:" + "b" * 64


def completion(**extras):
    return {"schema": contract.SCHEMA, "profile": contract.PROFILE, **extras}


def prompt(include_completion=True, **extras):
    value = {"schema": "WORLD_ENGINE_STUDIO_PROMPT_V2", "preset": "VERIFIED_FRONT_V4_80S",
             "durationSeconds": 80, **extras}
    if include_completion and "completion" not in value:
        value["completion"] = completion()
    return value


def envelope(inner=None, **extras):
    return {"prompt": json.dumps(prompt() if inner is None else inner), **extras}


class StructuralContractFixtureTests(unittest.TestCase):
    """Uses existing fake backend and explicit eventFlow validator stub only."""
    def setUp(self):
        self.backend = fixture.FakeBackend()
        self.event_validator = patch.object(contract, "_event_flow", side_effect=deepcopy)
        self.event_validator.start()
        self.addCleanup(self.event_validator.stop)

    def normalize(self, value):
        return contract.normalize_submission(value, image_digest=DIGEST, backend=self.backend,
                                             parent_normalize=original.normalize_submission)

    def error(self, code, value):
        with self.assertRaises(original.StudioContractError) as caught:
            self.normalize(value)
        self.assertEqual(caught.exception.code, code)

    def test_completion_is_sibling_preserving_original_plan_and_five_knobs(self):
        value = envelope(prompt(visualProfile={"frontGlowGain": .5}))
        before = deepcopy(value)
        actual = self.normalize(value)
        base = contract.preserved_contract().normalize_submission(envelope(prompt(False, visualProfile={"frontGlowGain": .5})),
            image_digest=DIGEST, backend=fixture.FakeBackend(), parent_normalize=original.normalize_submission)
        self.assertEqual(actual["videoPlan"], base["videoPlan"])
        self.assertEqual(actual["integration"], base["integration"])
        self.assertEqual(actual["sfx"], base["sfx"])
        self.assertEqual(actual["completionV2"], contract.normalize_completion(completion()))
        self.assertEqual(actual["promptText"], value["prompt"])
        self.assertEqual(value, before)

    def test_old_v2_without_completion_is_exact(self):
        value = envelope(prompt(False))
        expected = contract.preserved_contract().normalize_submission(value, image_digest=DIGEST,
            backend=fixture.FakeBackend(), parent_normalize=original.normalize_submission)
        self.assertEqual(self.normalize(value), expected)
        self.assertNotIn("completionV2", expected)

    def test_old_v1_result_identity_and_input_identity(self):
        value, expected, calls = {"prompt": "legacy memo"}, {"legacy": True}, []
        def parent(value, **kwargs):
            calls.append(value)
            return expected
        result = contract.normalize_submission(value, image_digest=DIGEST, backend=self.backend, parent_normalize=parent)
        self.assertIs(result, expected)
        self.assertIs(calls[0], value)

    def test_completion_defaults_are_named_and_source_qualified(self):
        actual = contract.normalize_completion(completion())
        self.assertEqual(actual["dataPolicy"], "QUALIFIED_SOURCE_ONLY")
        self.assertEqual(actual["camera"], {"mode": "V5_EVENT_TRACKING", "settleFrames": 18, "holdFrames": 24})
        self.assertEqual(actual["frontier"], contract.FRONTIER_DEFAULTS)
        self.assertEqual(actual["eventFlow"], contract.EVENT_FLOW_DEFAULTS)

    def test_unknown_completion_and_forged_source_or_approval_fields_rejected(self):
        for key in ("sourceStatus", "imageDigest", "sourceManifestSha256", "approved", "units", "terrainLighting"):
            with self.subTest(field=key):
                self.error("STUDIO_COMPLETION_FIELD_UNSUPPORTED", envelope(prompt(completion=completion(**{key: True}))))

    def test_wrong_profile_schema_policy_and_null_rejected(self):
        for fields in ({"schema": "other"}, {"profile": "other"}):
            self.error("STUDIO_COMPLETION_PROFILE_REQUIRED", envelope(prompt(completion=completion(**fields))))
        self.error("STUDIO_COMPLETION_DATA_POLICY_UNSUPPORTED", envelope(prompt(completion=completion(dataPolicy="INFER_OPPONENT"))))
        for value in (None, [], True):
            self.error("STUDIO_COMPLETION_FIELD_UNSUPPORTED", envelope(prompt(completion=value)))
        for field in ("camera", "frontier", "eventFlow"):
            self.error("STUDIO_COMPLETION_FIELD_INVALID", envelope(prompt(completion=completion(**{field: None}))))

    def test_v5_camera_limits_and_types(self):
        for name, values in (("settleFrames", (6, 60)), ("holdFrames", (0, 120))):
            for value in values:
                actual = contract.normalize_completion(completion(camera={name: value}))
                self.assertEqual(actual["camera"][name], value)
        for name, value in (("settleFrames", 5), ("settleFrames", 61), ("holdFrames", -1),
                            ("holdFrames", 121), ("settleFrames", 18.0), ("holdFrames", True)):
            self.error("STUDIO_COMPLETION_CAMERA_VALUE_INVALID", envelope(prompt(completion=completion(camera={name: value}))))

    def test_preserve_camera_rejects_ignored_settings(self):
        actual = contract.normalize_completion(completion(camera={"mode": "PRESERVE_PARENT"}))
        self.assertEqual(actual["camera"], {"mode": "PRESERVE_PARENT"})
        self.error("STUDIO_COMPLETION_CAMERA_SETTING_CONFLICT", envelope(prompt(completion=completion(camera={"mode": "PRESERVE_PARENT", "settleFrames": 18}))))
        self.error("STUDIO_COMPLETION_CAMERA_MODE_UNSUPPORTED", envelope(prompt(completion=completion(camera={"mode": "FORCED_ROLL"}))))
        self.error("STUDIO_COMPLETION_CAMERA_FIELD_UNSUPPORTED", envelope(prompt(completion=completion(camera={"rollDegrees": 20}))))

    def test_frontier_limits_and_types(self):
        for name, values in (("settledStrength", (0, 1)), ("settleFrames", (1, 120))):
            for value in values:
                self.assertEqual(contract.normalize_completion(completion(frontier={name: value}))["frontier"][name], value)
        for name, value in (("settledStrength", -.1), ("settledStrength", 1.1), ("settledStrength", True),
                            ("settleFrames", 0), ("settleFrames", 121), ("settleFrames", 18.0), ("enabled", 1)):
            self.error("STUDIO_COMPLETION_FRONTIER_VALUE_INVALID", envelope(prompt(completion=completion(frontier={name: value}))))
        self.error("STUDIO_COMPLETION_FRONTIER_PROFILE_UNSUPPORTED", envelope(prompt(completion=completion(frontier={"profile": "SCALAR_TERRITORY"}))))
        self.error("STUDIO_COMPLETION_FRONTIER_FIELD_UNSUPPORTED", envelope(prompt(completion=completion(frontier={"fakeFront": True}))))

    def test_disabled_frontier_and_disabled_motion_reject_ignored_knobs(self):
        self.assertEqual(contract.normalize_completion(completion(frontier={"enabled": False}))["frontier"],
                         {"profile": "AUTHORED_FRONT_MOTION_V2", "enabled": False})
        self.assertEqual(contract.normalize_completion(completion(frontier={"motionResponse": False}))["frontier"],
                         {"profile": "AUTHORED_FRONT_MOTION_V2", "enabled": True, "motionResponse": False})
        for fields in ({"enabled": False, "motionResponse": True}, {"enabled": False, "settleFrames": 18},
                       {"motionResponse": False, "settledStrength": .2}):
            self.error("STUDIO_COMPLETION_FRONTIER_SETTING_CONFLICT", envelope(prompt(completion=completion(frontier=fields))))

    def test_original_unknown_fields_and_scene_sfx_conflicts_still_rejected(self):
        self.error("STUDIO_PROMPT_FIELD_UNSUPPORTED", envelope(prompt(unknown=True)))
        self.error("STUDIO_V2_SCENE_CONFLICT", envelope(sceneJson=fixture.fixture()))
        self.error("STUDIO_V2_SFX_CONFLICT", envelope(prompt(sfx={"enabled": False}), sfx={"enabled": True}))

    def test_original_preset_and_backend_source_admission_preserved(self):
        self.error("STUDIO_V2_PRESET_REQUIRED", envelope(prompt(preset="OTHER")))
        self.backend.reject = True
        self.error("STUDIO_RENDER_PLAN_REJECTED", envelope())

    def test_parent_contract_hash_is_required(self):
        with patch.object(contract, "PRIOR_CONTRACT_SHA256", "0" * 64):
            self.error("STUDIO_COMPLETION_PARENT_SOURCE_CHANGED", envelope())

    def test_schema_is_valid_and_camera_frontier_branches_are_exact(self):
        import jsonschema
        schema = json.loads((HERE / "STUDIO_PROMPT_V2.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        camera = jsonschema.Draft202012Validator(schema["$defs"]["completionCamera"])
        frontier = jsonschema.Draft202012Validator(schema["$defs"]["completionFrontier"])
        for value in ({}, {"mode": "PRESERVE_PARENT"}, contract.CAMERA_DEFAULTS):
            camera.validate(value)
        self.assertTrue(list(camera.iter_errors({"mode": "PRESERVE_PARENT", "settleFrames": 18})))
        for value in ({}, {"enabled": False}, {"motionResponse": False}, contract.FRONTIER_DEFAULTS):
            frontier.validate(value)
        self.assertTrue(list(frontier.iter_errors({"enabled": False, "settleFrames": 18})))
        # Resolve the shipped local schema, without fetching external network data.
        from referencing import Registry, Resource
        event_schema = json.loads((HERE / "EVENT_FLOW_REQUEST.schema.json").read_text())
        registry = Registry().with_resource("EVENT_FLOW_REQUEST.schema.json", Resource.from_contents(event_schema))
        validator = jsonschema.Draft202012Validator(schema, registry=registry)
        validator.validate(prompt(completion=completion(eventFlow=contract.EVENT_FLOW_DEFAULTS)))
        self.assertTrue(list(validator.iter_errors(prompt(completion=completion(eventFlow={**contract.EVENT_FLOW_DEFAULTS, "unknown": True})))))


class RealFrozenCompletionTests(unittest.TestCase):
    @unittest.skipUnless((HERE / "event_flow_contract.py").is_file(), "Event/Flow structural module not yet available")
    def test_actual_frozen_plan_and_actual_event_flow_empty_request(self):
        import studio_runtime as backend
        old = contract.preserved_contract().normalize_submission(envelope(prompt(False)), image_digest=DIGEST,
            backend=backend, parent_normalize=original.normalize_submission)
        actual = contract.normalize_submission(envelope(), image_digest=DIGEST,
            backend=backend, parent_normalize=original.normalize_submission)
        self.assertEqual(actual["videoPlan"], old["videoPlan"])
        self.assertEqual(actual["integration"], old["integration"])
        self.assertEqual(actual["videoPlan"]["totalFrames"], 2400)
        self.assertEqual(len(actual["videoPlan"]["scenes"]), 12)
        self.assertEqual(actual["completionV2"]["eventFlow"], contract.EVENT_FLOW_DEFAULTS)
        backend.validate_render_plan(actual["videoPlan"], "V4_ARCHIVAL_80S", DIGEST)


if __name__ == "__main__":
    unittest.main()
