"""Focused pure input/interval tests; a fake backend is not NVIDIA evidence."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from studio_contracts import (SCHEMA, StudioContractError, normalize_submission,
                              plan_revision)

DIGEST = "sha256:" + "b" * 64


def fixture(duration=80):
    total = duration * 30
    return {"schema": "WORLD_ENGINE_PRODUCTION_SCENE_V3", "durationSeconds": duration,
            "fps": 30, "totalFrames": total, "resolution": {"width": 1080, "height": 1920},
            "aspectRatio": "9:16", "topic": "Supplied source-bound test topic",
            "titleCandidates": ["검증된 데이터 제작"],
            "sourceManifest": {"fixtureOnly": True}, "renderProfile": {"imageDigest": "sha256:" + "a" * 64},
            "productionV3": {"eventChapters": [{"eventId": "SUPPLIED_EVENT", "startFrame": 0, "endFrame": total}]},
            "legacyScenePlan": {"beats": []},
            "scenes": [{"sceneId": f"scene-{i}", "startFrame": total * i // 4,
                        "endFrame": total * (i + 1) // 4} for i in range(4)]}


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.reject = False

    def default_plan(self, profile):
        self.calls.append(("preset", profile))
        return fixture()

    def bind_render_image(self, plan, profile, image_digest):
        self.calls.append(("bind", profile))
        result = deepcopy(plan)
        result["renderProfile"]["imageDigest"] = image_digest
        return result

    def validate_render_plan(self, plan, profile, image_digest=None):
        self.calls.append(("validate", profile))
        if self.reject:
            raise ValueError("PRIVATE_LOCAL_PATH_OR_PROVIDER_MESSAGE")
        if plan.get("sourceManifest") != {"fixtureOnly": True}:
            raise ValueError("fixture requires source")
        return plan


class InputTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()

    def normalize(self, value):
        return normalize_submission(value, image_digest=DIGEST, backend=self.backend)

    def raises_code(self, code, value):
        with self.assertRaises(StudioContractError) as context:
            self.normalize(value)
        self.assertEqual(code, context.exception.code)
        return context.exception

    def test_direct_scene_bypasses_free_prompt_interpretation_and_preserves_input(self):
        plan = fixture()
        before = deepcopy(plan)
        result = self.normalize({"sceneJson": plan, "profile": "UNIVERSAL_V3", "prompt": "외부 기획 메모, 적용하지 않음"})
        self.assertEqual(plan, before)
        expected = deepcopy(plan)
        expected["renderProfile"]["imageDigest"] = DIGEST
        self.assertEqual(result["videoPlan"], expected)
        self.assertEqual(self.backend.calls, [("bind", "UNIVERSAL_V3"), ("validate", "UNIVERSAL_V3")])
        self.assertEqual(result["title"], "검증된 데이터 제작")

    def test_structured_preset_and_fenced_json(self):
        prompt = {"schema": "WORLD_ENGINE_STUDIO_PROMPT_V1", "preset": "VERIFIED_FRONT_V4_80S",
                  "title": "공식 자료 기반 80초", "durationSeconds": 80, "profile": "V4_ARCHIVAL_80S",
                  "sfx": {"enabled": False, "gain": .4}}
        result = self.normalize({"prompt": "```json\n" + json.dumps(prompt) + "\n```"})
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["title"], prompt["title"])
        self.assertFalse(result["sfx"]["enabled"])
        self.assertEqual(self.backend.calls[0], ("preset", "V4_ARCHIVAL_80S"))

    def test_direct_scene_json_in_prompt(self):
        result = self.normalize({"prompt": json.dumps(fixture()), "profile": "UNIVERSAL_V3"})
        self.assertEqual(result["videoPlan"]["totalFrames"], 2400)

    def test_all_lengths_use_the_same_external_plan_path(self):
        for duration in (80, 120, 180, 300, 600):
            with self.subTest(duration=duration):
                result = self.normalize({"sceneJson": fixture(duration), "profile": "UNIVERSAL_V3", "durationSeconds": duration})
                self.assertEqual(result["videoPlan"]["totalFrames"], duration * 30)
                self.assertEqual(len(result["videoPlan"]["scenes"]), 4)

    def test_plain_natural_language_does_not_invent_history(self):
        error = self.raises_code("STUDIO_STRUCTURED_PROMPT_REQUIRED", {"prompt": "새 전쟁 전선을 조사해 80초로 만들어줘"})
        self.assertIn("sceneJson", error.fields)
        self.assertEqual(self.backend.calls, [])

    def test_empty_input_reports_required_fields(self):
        self.raises_code("STUDIO_SCENE_OR_PROMPT_REQUIRED", {})

    def test_duplicate_json_keys_are_rejected(self):
        self.raises_code("STUDIO_DUPLICATE_JSON_KEY", {"prompt": '{"schema":"x","schema":"y"}'})

    def test_nonfinite_json_is_rejected(self):
        self.raises_code("STUDIO_JSON_VALUE_INVALID", {"prompt": '{"fps":NaN}'})
        self.raises_code("STUDIO_JSON_VALUE_INVALID", {"sceneJson": {"fps": float("inf")}})

    def test_invalid_unicode_is_safe_error(self):
        self.raises_code("STUDIO_JSON_VALUE_INVALID", {"prompt": "\ud800"})

    def test_invalid_profile_type_is_safe_error(self):
        self.raises_code("STUDIO_PROFILE_UNSUPPORTED", {"sceneJson": fixture(), "profile": {}})

    def test_unknown_top_level_fields_are_not_silently_ignored(self):
        self.raises_code("STUDIO_SUBMISSION_INVALID", {"sceneJson": fixture(), "apiToken": "not-a-secret"})

    def test_length_mismatch_never_stretches_history(self):
        self.raises_code("STUDIO_DURATION_CONFLICT", {"sceneJson": fixture(), "durationSeconds": 120})

    def test_boolean_duration_is_not_accepted_as_integer(self):
        self.raises_code("STUDIO_DURATION_UNSUPPORTED", {"sceneJson": fixture(), "durationSeconds": True})

    def test_archival_profile_cannot_retime_to_600_seconds(self):
        self.raises_code("STUDIO_ARCHIVAL_PRESET_80S_ONLY", {"sceneJson": fixture(600), "profile": "V4_ARCHIVAL_80S"})

    def test_ui_and_structured_profile_must_agree(self):
        self.raises_code("STUDIO_PROFILE_CONFLICT", {"profile": "UNIVERSAL_V3", "prompt": json.dumps({
            "schema": "WORLD_ENGINE_STUDIO_PROMPT_V1", "preset": "VERIFIED_FRONT_V4_80S", "profile": "V4_ARCHIVAL_80S"})})

    def test_source_rejection_is_not_reported_as_success_or_leaked(self):
        self.backend.reject = True
        error = self.raises_code("STUDIO_RENDER_PLAN_REJECTED", {"sceneJson": fixture()})
        self.assertNotIn("PRIVATE_LOCAL", error.message)
        self.assertIn("sourceManifest", error.fields)

    def test_unpinned_image_rejected_before_binding(self):
        with self.assertRaises(StudioContractError) as context:
            normalize_submission({"sceneJson": fixture()}, image_digest="latest", backend=self.backend)
        self.assertEqual(context.exception.code, "STUDIO_IMAGE_DIGEST_REQUIRED")
        self.assertEqual(self.backend.calls, [])

    def test_wrong_output_format_is_rejected(self):
        plan = fixture()
        plan["resolution"]["width"] = 720
        self.raises_code("STUDIO_OUTPUT_SPEC_CONFLICT", {"sceneJson": plan})

    def test_unknown_cue_cannot_invent_an_event(self):
        self.raises_code("STUDIO_SFX_INVALID", {"sceneJson": fixture(), "sfx": {"cues": [
            {"eventId": "INVENTED_OCCUPATION", "frame": 0, "type": "OCCUPATION_COMPLETE"}]}})

    def test_title_control_characters_are_rejected(self):
        plan = fixture()
        plan["titleCandidates"] = ["title\nunsafe"]
        self.raises_code("STUDIO_TITLE_INVALID", {"sceneJson": plan})

    def test_missing_backend_does_not_admit_plan(self):
        with self.assertRaises(StudioContractError) as context:
            normalize_submission({"sceneJson": fixture()}, image_digest=DIGEST, backend=object())
        self.assertEqual(context.exception.code, "STUDIO_BACKEND_UNAVAILABLE")


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.parent = normalize_submission({"sceneJson": fixture(), "profile": "UNIVERSAL_V3", "sfx": {
            "enabled": True, "gain": .65, "cues": [{"eventId": "SUPPLIED_EVENT", "frame": frame,
                "type": "CLICK", "gain": .8} for frame in (0, 750, 1049, 1050, 1600)]}},
            image_digest=DIGEST, backend=FakeBackend())

    def error(self, code, start=25, end=35, prompt="", sfx=None):
        with self.assertRaises(StudioContractError) as context:
            plan_revision(self.parent, start, end, prompt, sfx)
        self.assertEqual(context.exception.code, code)
        return context.exception

    def test_sfx_revision_reuses_all_video_and_keeps_parent_immutable(self):
        before = deepcopy(self.parent)
        result = plan_revision(self.parent, 25, 35, "효과음 꺼줘")
        self.assertEqual(self.parent, before)
        self.assertEqual(result["submission"]["videoPlan"], before["videoPlan"])
        impact = result["impact"]
        self.assertEqual(impact["requestedFrames"], [750, 1050])
        self.assertEqual(impact["affectedSceneIds"], ["scene-1"])
        self.assertEqual(impact["invalidatedSceneIds"], [])
        self.assertEqual(len(impact["reusedSceneIds"]), 4)
        self.assertFalse(impact["requiresGpu"])
        self.assertFalse(impact["gpuPartialRevisionVerified"])

    def test_half_open_interval_preserves_boundary_and_outside_gain(self):
        result = plan_revision(self.parent, 25, 35, "SFX OFF")["submission"]["sfx"]
        self.assertEqual(result["gain"], 1.)
        self.assertEqual([c["gain"] for c in result["cues"]], [.52, 0., 0., .52, .52])

    def test_volume_revision_changes_only_requested_cue_onsets(self):
        result = plan_revision(self.parent, 25, 35, "효과음 음량 40%")["submission"]["sfx"]
        self.assertEqual([c["gain"] for c in result["cues"]], [.52, .4, .4, .52, .52])

    def test_structured_revision_with_existing_event(self):
        command = {"schema": "WORLD_ENGINE_STUDIO_REVISION_V1", "sfx": {"cues": [
            {"eventId": "SUPPLIED_EVENT", "frame": 800, "type": "MECHANICAL_TICK"}]}}
        result = plan_revision(self.parent, 25, 35, json.dumps(command))["submission"]["sfx"]
        self.assertEqual([c["frame"] for c in result["cues"]], [0, 800, 1050, 1600])

    def test_new_cue_outside_selected_range_is_rejected(self):
        self.error("STUDIO_REVISION_CUE_OUTSIDE_RANGE", sfx={"cues": [
            {"eventId": "SUPPLIED_EVENT", "frame": 1050, "type": "CLICK"}]})

    def test_camera_language_is_not_falsely_applied(self):
        error = self.error("STUDIO_VISUAL_REVISION_UNSUPPORTED", prompt="카메라를 조금 더 확대하고 이동을 느리게 해줘")
        self.assertEqual(error.status, 422)
        self.assertIn("sfx.gain", error.fields)

    def test_exact_frame_times_are_required(self):
        self.error("STUDIO_REVISION_TIME_INVALID", start="0.333")
        self.error("STUDIO_REVISION_TIME_INVALID", start=-1)
        self.error("STUDIO_REVISION_TIME_INVALID", end=81)
        self.error("STUDIO_REVISION_TIME_INVALID", start=True)

    def test_empty_and_reversed_ranges_are_rejected(self):
        self.error("STUDIO_REVISION_RANGE_EMPTY", start=35, end=35, prompt="SFX OFF")
        self.error("STUDIO_REVISION_RANGE_EMPTY", start=36, end=35, prompt="SFX OFF")

    def test_mixed_free_text_and_structured_sfx_is_rejected(self):
        self.error("STUDIO_REVISION_REQUEST_CONFLICT", prompt="카메라 확대", sfx={"enabled": False})

    def test_null_gain_and_nontext_prompt_are_safe_errors(self):
        self.error("STUDIO_REVISION_SFX_INVALID", sfx={"gain": None})
        self.error("STUDIO_REVISION_PROMPT_REQUIRED", prompt=1, sfx={"enabled": False})

    def test_consecutive_revisions_preserve_outside_effective_audio(self):
        first = plan_revision(self.parent, 25, 35, "SFX OFF")["submission"]
        second = plan_revision(first, 25, 35, "효과음 음량 30%")["submission"]
        self.assertEqual([c["gain"] for c in second["sfx"]["cues"]], [.52, .3, .3, .52, .52])


class AudioIntervalImpactTests(unittest.TestCase):
    """Focused actual audio support at a requested interval/scene boundary."""

    def setUp(self):
        RevisionTests.setUp(self)
        self.parent["videoPlan"]["scenes"] = [
            {"sceneId": "before", "startFrame": 0, "endFrame": 750},
            {"sceneId": "requested", "startFrame": 750, "endFrame": 1050},
            {"sceneId": "after", "startFrame": 1050, "endFrame": 2400}]

    # The original four-scene behavior remains covered by RevisionTests. These
    # cases bind an actual scene boundary to the requested audio interval end.
    def test_sfx_revision_reuses_all_video_and_keeps_parent_immutable(self):
        self.assert_audio_tail_is_reported()

    def assert_audio_tail_is_reported(self):
        before = deepcopy(self.parent)
        result = plan_revision(self.parent, 25, 35, "SFX OFF")
        self.assertEqual(self.parent, before)
        impact = result["impact"]
        self.assertEqual(impact["affectedSceneIds"], ["requested"])
        self.assertEqual(impact["adjacentSceneIds"], ["after"])
        self.assertEqual(impact["audioAffectedSceneIds"], ["requested", "after"])
        self.assertEqual(impact["invalidatedSceneIds"], [])
        self.assertEqual(impact["reusedSceneIds"], ["before", "requested", "after"])
        self.assertFalse(impact["requiresGpu"])
        self.assertEqual(impact["audioRequestedSamples"], [25 * 48000, 35 * 48000])
        self.assertEqual(impact["audioImpact"]["comparison"], "CONSERVATIVE_AUTHORED_CUE_SUPPORT")
        self.assertFalse(impact["audioImpact"]["actualPcmCompared"])
        self.assertTrue(impact["audioImpact"]["outsideReportedIntervalsUnchangedByConstruction"])
        intervals = impact["audioChangedSampleIntervals"]
        self.assertTrue(any(a < 35 * 48000 < b for a, b in intervals))
        self.assertLess(max(b for _, b in intervals), 36 * 48000)
        return result

    def test_removed_cues_report_bounded_neighbor_admission(self):
        result = plan_revision(self.parent, 25, 35, "", {"cues": []})
        impact = result["impact"]
        self.assertEqual(impact["adjacentSceneIds"], ["after"])
        self.assertLess(max(b for _, b in impact["audioChangedSampleIntervals"]), 36 * 48000)
        self.assertEqual(result["submission"]["videoPlan"], self.parent["videoPlan"])

    def test_actual_pcm_outside_reported_audio_support_is_unchanged(self):
        import numpy as np
        from studio_audio import render_sfx
        result = self.assert_audio_tail_is_reported()
        intervals = result["impact"]["audioChangedSampleIntervals"]
        with tempfile.TemporaryDirectory(prefix="studio-contract-audio-interval-") as name:
            root = Path(name)
            render_sfx(self.parent["sfx"], self.parent["videoPlan"], root / "old.wav")
            render_sfx(result["submission"]["sfx"], self.parent["videoPlan"], root / "new.wav")
            changed = 0
            with wave.open(str(root / "old.wav"), "rb") as old, wave.open(str(root / "new.wav"), "rb") as new:
                self.assertEqual(old.getnframes(), 80 * 48000)
                self.assertEqual(new.getnframes(), old.getnframes())
                start = 0
                while True:
                    a, b = old.readframes(48000), new.readframes(48000)
                    if not a:
                        self.assertEqual(b, b"")
                        break
                    previous = np.frombuffer(a, dtype="<i2").reshape(-1, 2)
                    following = np.frombuffer(b, dtype="<i2").reshape(-1, 2)
                    diff = np.any(previous != following, axis=1)
                    allowed = np.zeros(len(diff), dtype=bool)
                    for left, right in intervals:
                        lo, hi = max(left, start), min(right, start + len(diff))
                        if hi > lo:
                            allowed[lo - start:hi - start] = True
                    self.assertFalse(np.any(diff & ~allowed), f"unreported audio changed at block {start}")
                    if start >= 36 * 48000:
                        self.assertEqual(a, b)
                    changed += int(np.count_nonzero(diff))
                    start += len(diff)
            self.assertGreater(changed, 0)


class OriginalBackendIntegrationTests(unittest.TestCase):
    def test_preset_actual_source_binding_and_audio_revision_cache_keys(self):
        # This exercises the real frozen V3/V4 validators and source bindings.
        # It performs no GPU admission, process start, rendering, or claim writes.
        import studio_runtime as backend
        prompt = json.loads((HERE / "examples/STUDIO_PROMPT_V4_80S.json").read_text())
        result = normalize_submission({"prompt": json.dumps(prompt)}, image_digest=DIGEST, backend=backend)
        plan = result["videoPlan"]
        self.assertEqual(plan["totalFrames"], 2400)
        self.assertEqual(len(plan["scenes"]), 12)
        self.assertEqual(plan["sourceManifest"]["archivalFrontV4"]["profileId"], "VERIFIED_ARCHIVAL_FRONT_V4")
        self.assertEqual(len(result["sfx"]["cues"]), 12)
        revised = plan_revision(result, 25, 35, "효과음 음량 40%")
        cache = backend._cache()
        def keys(value):
            scenes = value["scenes"]
            return [cache.scene_cache_key(value, scene, scenes[index - 1] if index else None,
                    scenes[index + 1] if index + 1 < len(scenes) else None)
                    for index, scene in enumerate(scenes)]
        self.assertEqual(keys(plan), keys(revised["submission"]["videoPlan"]))
        self.assertEqual(len(revised["impact"]["reusedSceneIds"]), 12)


if __name__ == "__main__":
    unittest.main()
