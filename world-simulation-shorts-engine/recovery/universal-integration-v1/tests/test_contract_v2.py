"""Focused CPU-only V2 tests. Fixture and real-backend evidence are separate.

No admission, subprocess render, GPU request, claim or private-state write is
performed. The original contract fixture backend is explicitly a test double.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
PARENT = HERE.parent / "production-studio-mvp-v1"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(HERE))
import studio_contracts as parent
import contract_v2 as contract

_spec = importlib.util.spec_from_file_location("_integration_preserved_contract_fixture", PARENT / "tests/test_studio_contracts.py")
_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixtures)
DIGEST = "sha256:" + "b" * 64


def prompt(**extras):
    return {"schema": contract.PROMPT_SCHEMA, "preset": contract.PRESET,
            "durationSeconds": 80, **extras}


def envelope(inner=None, **extras):
    return {"prompt": json.dumps(prompt() if inner is None else inner, ensure_ascii=False), **extras}


class FixtureContractTests(unittest.TestCase):
    """Existing fixture backend validates contracts; this is not real-source admission."""

    def setUp(self):
        self.backend = _fixtures.FakeBackend()

    def normalize(self, value):
        return contract.normalize_submission(value, image_digest=DIGEST, backend=self.backend,
                                             parent_normalize=parent.normalize_submission)

    def error(self, code, value):
        with self.assertRaises(parent.StudioContractError) as caught:
            self.normalize(value)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_v1_callback_gets_original_object_and_return_identity(self):
        value = {"prompt": "unchanged legacy contract input"}
        expected = {"a": [1, 2]}
        seen = []
        def original(arg, **kwargs):
            seen.append((arg, kwargs))
            return expected
        result = contract.normalize_submission(value, image_digest=DIGEST, backend=self.backend,
                                               parent_normalize=original)
        self.assertIs(result, expected)
        self.assertIs(seen[0][0], value)
        self.assertEqual(seen[0][1], {"image_digest": DIGEST, "backend": self.backend})

    def test_v1_normalized_result_exactly_preserved(self):
        value = envelope({"schema": "WORLD_ENGINE_STUDIO_PROMPT_V1", "preset": contract.PRESET,
                          "durationSeconds": 80, "sfx": {"enabled": False}})
        expected = parent.normalize_submission(value, image_digest=DIGEST, backend=_fixtures.FakeBackend())
        self.assertEqual(expected, self.normalize(value))
        self.assertNotIn("integration", expected)

    def test_direct_scene_with_nonjson_memo_stays_original(self):
        value = {"sceneJson": _fixtures.fixture(), "profile": "UNIVERSAL_V3", "prompt": "기획 메모"}
        expected = parent.normalize_submission(value, image_digest=DIGEST, backend=_fixtures.FakeBackend())
        self.assertEqual(expected, self.normalize(value))

    def test_v2_adds_sibling_metadata_without_changing_frozen_plan(self):
        value = envelope(prompt(title="검증된 부분 자료 시각 통합"))
        before = deepcopy(value)
        result = self.normalize(value)
        lowered = envelope({"schema": "WORLD_ENGINE_STUDIO_PROMPT_V1", "preset": contract.PRESET,
                            "durationSeconds": 80, "title": "검증된 부분 자료 시각 통합"})
        expected = parent.normalize_submission(lowered, image_digest=DIGEST, backend=_fixtures.FakeBackend())
        self.assertEqual(result["videoPlan"], expected["videoPlan"])
        self.assertEqual(result["sfx"], expected["sfx"])
        self.assertEqual(value, before)
        self.assertEqual(result["promptText"], value["prompt"])
        self.assertEqual(result["integration"], {"schema": contract.INTEGRATION_SCHEMA,
                         "profile": contract.INTEGRATION_PROFILE, "visualProfile": contract.VISUAL_DEFAULTS})
        self.assertEqual(self.backend.calls, [("preset", contract.PROFILE), ("bind", contract.PROFILE),
                                              ("validate", contract.PROFILE)])

    def test_visual_overrides_all_actual_consumed_fields(self):
        fields = {"territoryOpacity": .7, "frontCoreWidthPixels": 6,
                  "frontGlowRadiusPixels": 12, "frontGlowGain": .5, "cameraApproachFrames": 60}
        result = self.normalize(envelope(prompt(visualProfile=fields)))
        self.assertEqual(result["integration"]["visualProfile"], fields)
        self.assertNotIn("visualProfile", result["videoPlan"])

    def test_fenced_v2_prompt_retains_original_text(self):
        text = "```json\n" + json.dumps(prompt()) + "\n```"
        result = self.normalize({"prompt": text, "profile": contract.PROFILE, "durationSeconds": 80})
        self.assertEqual(result["promptText"], text)

    def test_outer_ui_audio_is_explicitly_used_when_inner_absent(self):
        result = self.normalize(envelope(sfx={"enabled": False, "gain": .7}))
        self.assertFalse(result["sfx"]["enabled"])
        self.assertEqual(result["sfx"]["gain"], .7)

    def test_identical_inner_outer_audio_allowed(self):
        audio = {"enabled": True, "gain": .4}
        result = self.normalize(envelope(prompt(sfx=audio), sfx=audio))
        self.assertEqual(result["sfx"]["gain"], .4)

    def test_conflicting_audio_rejected_instead_of_ignored(self):
        self.error("STUDIO_V2_SFX_CONFLICT", envelope(prompt(sfx={"enabled": False}),
                                                    sfx={"enabled": True, "gain": .7}))
        self.assertEqual(self.backend.calls, [])

    def test_direct_scene_attachment_cannot_silently_bypass_v2(self):
        self.error("STUDIO_V2_SCENE_CONFLICT", envelope(sceneJson=_fixtures.fixture()))
        self.assertEqual(self.backend.calls, [])

    def test_missing_preset_and_unsupported_preset_rejected(self):
        for value in (None, "OTHER"):
            item = prompt()
            if value is None:
                del item["preset"]
            else:
                item["preset"] = value
            with self.subTest(value=value):
                self.error("STUDIO_V2_PRESET_REQUIRED", envelope(item))

    def test_inner_outer_profile_conflicts_rejected(self):
        self.error("STUDIO_V2_PROFILE_CONFLICT", envelope(prompt(profile="UNIVERSAL_V3")))
        self.error("STUDIO_V2_PROFILE_CONFLICT", envelope(profile="UNIVERSAL_V3"))

    def test_duration_is_explicit_integer_80(self):
        for duration in (None, True, 80.0, 120, "80"):
            item = prompt()
            if duration is None:
                del item["durationSeconds"]
            else:
                item["durationSeconds"] = duration
            with self.subTest(duration=duration):
                self.error("STUDIO_V2_DURATION_80_REQUIRED", envelope(item))

    def test_outer_duration_conflict_rejected(self):
        for duration in (120, 80.0, True):
            with self.subTest(duration=duration):
                self.error("STUDIO_DURATION_CONFLICT", envelope(durationSeconds=duration))

    def test_unknown_outer_and_inner_fields_rejected(self):
        self.error("STUDIO_SUBMISSION_INVALID", envelope(ownerOverride=True))
        for key in ("sceneJson", "camera", "militaryUnits", "route", "approval", "imageDigest", "profileSha256"):
            with self.subTest(field=key):
                self.error("STUDIO_PROMPT_FIELD_UNSUPPORTED", envelope(prompt(**{key: {}})))

    def test_unimplemented_visual_fields_and_null_rejected(self):
        for fields in ({"cameraRollDegrees": 15}, {"unitMarkerScale": 2}, {"foo": 1}, None, []):
            with self.subTest(fields=fields):
                self.error("STUDIO_V2_VISUAL_FIELD_UNSUPPORTED", envelope(prompt(visualProfile=fields)))

    def test_visual_lower_upper_bounds_and_types(self):
        for name, (low, high) in contract.VISUAL_LIMITS.items():
            for value in (low, high):
                with self.subTest(field=name, value=value):
                    self.assertEqual(self.normalize(envelope(prompt(visualProfile={name: value})))
                                     ["integration"]["visualProfile"][name], value)
            for value in (low - 1, high + 1, True, str(low)):
                with self.subTest(field=name, invalid=value):
                    self.error("STUDIO_V2_VISUAL_VALUE_INVALID", envelope(prompt(visualProfile={name: value})))
        self.error("STUDIO_V2_VISUAL_VALUE_INVALID", envelope(prompt(visualProfile={"cameraApproachFrames": 48.0})))

    def test_duplicate_keys_and_nonfinite_are_rejected_by_preserved_parser(self):
        duplicate = '{"schema":"WORLD_ENGINE_STUDIO_PROMPT_V2","durationSeconds":80,"durationSeconds":80}'
        self.error("STUDIO_DUPLICATE_JSON_KEY", {"prompt": duplicate})
        nonfinite = '{"schema":"WORLD_ENGINE_STUDIO_PROMPT_V2","visualProfile":{"frontGlowGain":NaN}}'
        self.error("STUDIO_JSON_VALUE_INVALID", {"prompt": nonfinite})

    def test_parent_source_rejection_is_preserved_and_sanitized(self):
        self.backend.reject = True
        error = self.error("STUDIO_RENDER_PLAN_REJECTED", envelope())
        self.assertNotIn("PRIVATE_LOCAL", error.message)

    def test_invalid_image_digest_still_rejected_by_parent(self):
        with self.assertRaises(parent.StudioContractError) as caught:
            contract.normalize_submission(envelope(), image_digest="not-an-image-digest", backend=self.backend,
                                          parent_normalize=parent.normalize_submission)
        self.assertEqual(caught.exception.code, "STUDIO_IMAGE_DIGEST_REQUIRED")

    def test_schema_and_examples_validate_with_jsonschema(self):
        import jsonschema
        schema = json.loads((HERE / "STUDIO_PROMPT_V2.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(prompt())
        validator.validate(prompt(visualProfile=contract.VISUAL_DEFAULTS))
        for bad in (prompt(visualProfile={"cameraRollDegrees": 15}), prompt(camera={}), prompt(durationSeconds=120)):
            self.assertTrue(list(validator.iter_errors(bad)))


class RealFrozenBackendTests(unittest.TestCase):
    """Actual protected parent validators, no GPU/admission or job start."""

    def test_v2_uses_actual_frozen_v4_plan_unchanged(self):
        import studio_runtime as backend
        try:
            backend.default_plan(contract.PROFILE)
            old = parent.normalize_submission(envelope({"schema": "WORLD_ENGINE_STUDIO_PROMPT_V1",
                "preset": contract.PRESET, "durationSeconds": 80}), image_digest=DIGEST, backend=backend)
        except FileNotFoundError:
            self.skipTest("Real frozen source closure not hydrated in this CPU checkout")
        result = contract.normalize_submission(envelope(prompt(visualProfile={"frontGlowGain": .5})),
            image_digest=DIGEST, backend=backend, parent_normalize=parent.normalize_submission)
        self.assertEqual(result["videoPlan"], old["videoPlan"])
        self.assertEqual(result["videoPlan"]["totalFrames"], 2400)
        self.assertEqual(len(result["videoPlan"]["scenes"]), 12)
        self.assertEqual(result["videoPlan"]["sourceManifest"]["archivalFrontV4"]["profileId"],
                         "VERIFIED_ARCHIVAL_FRONT_V4")
        backend.validate_render_plan(result["videoPlan"], contract.PROFILE, DIGEST)
        self.assertEqual(result["integration"]["visualProfile"]["frontGlowGain"], .5)


if __name__ == "__main__":
    unittest.main()
