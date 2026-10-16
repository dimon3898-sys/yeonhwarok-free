"""Focused new contract tests; no original core suite and no GPU execution."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from contracts import ContractError, boundary_at, canonical_sha256, split_plan, total_frames, validate_plan
from planner import PlanningError, bind_renderer, parse_request, plan_topic


@unittest.skipUnless(shutil.which("node"), "BLOCKED: Node required for unchanged original planner")
class PlannerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = plan_topic("한국전쟁의 전선 변화를 80초 영상으로 만들어줘.")

    def test_real_existing_planner_is_reused(self):
        self.assertEqual(self.plan["legacyScenePlan"]["metadata"]["schema"], "PLANNER_SCENE_JSON_V1")
        self.assertEqual(self.plan["totalFrames"], 2400)
        facts_path = ROOT.parent.parent / self.plan["sourceManifest"]["factsPath"]
        facts = json.loads(facts_path.read_bytes())
        self.assertEqual(self.plan["legacyScenePlan"]["geometries"], facts["geometries"])
        self.assertEqual([step["date"] for step in self.plan["legacyScenePlan"]["time_steps"]], [step["date"] for step in facts["stages"]])
        self.assertEqual(len(self.plan["legacyScenePlan"]["time_steps"]), 5)
        self.assertNotIn("moving_objects", self.plan["legacyScenePlan"])

    def test_duration_matrix_80_to_600(self):
        for seconds in (80, 120, 180, 300, 600):
            with self.subTest(seconds=seconds):
                plan = plan_topic("한국전쟁 전선 변화", duration_seconds=seconds)
                self.assertIs(validate_plan(plan), plan)
                self.assertEqual(sum(s["endFrame"] - s["startFrame"] for s in plan["scenes"]), seconds * 30)
                self.assertEqual(plan["scenes"][0]["startFrame"], 0)
                self.assertEqual(plan["scenes"][-1]["endFrame"], seconds * 30)
                self.assertLessEqual(len(plan["scenes"]), seconds // 10 + 10)
                self.assertNotIn("frames", plan)
                self.assertNotIn("frameBuffers", plan)

    def test_non30_fps_and_exact_fractional_duration(self):
        plan = plan_topic("Korean War", duration_seconds=80.5, fps=24)
        self.assertEqual(plan["totalFrames"], 1932)
        self.assertEqual(plan["legacyScenePlan"]["timing"]["fps"], 24)

    def test_half_open_boundaries_match_and_do_not_reset(self):
        for left, right in zip(self.plan["scenes"], self.plan["scenes"][1:]):
            self.assertEqual(left["endFrame"], right["startFrame"])
            self.assertEqual(left["boundaryEnd"], right["boundaryStart"])
            self.assertFalse(right["territoryState"]["resetAtSceneStart"])
            self.assertEqual(right["globalFrameOffset"], right["startFrame"])

    def test_boundary_inside_state_transition_uses_global_time(self):
        cut = self.plan["legacyScenePlan"]["time_steps"][1]["start_frame"] + 17
        a = boundary_at(self.plan, cut)
        b = boundary_at(split_plan(self.plan, 37), cut)
        self.assertEqual(a, b)
        self.assertIn("SEMANTIC_CONTRACT_ONLY", a["validationBasis"])

    def test_original_events_exactly_cover_each_scene(self):
        for scene in self.plan["scenes"]:
            cursor = scene["startFrame"]
            for event in scene["eventTimeline"]:
                self.assertEqual(event["startFrame"], cursor)
                self.assertLess(event["startFrame"], event["endFrame"])
                self.assertLessEqual(event["sourceStartFrame"], event["startFrame"])
                self.assertGreaterEqual(event["sourceEndFrame"], event["endFrame"])
                cursor = event["endFrame"]
            self.assertEqual(cursor, scene["endFrame"])

    def test_missing_native_binding_is_blocked_honestly(self):
        self.assertEqual(self.plan["renderProfile"]["status"], "BLOCKED_RENDERER_BINDING_REQUIRED")
        with self.assertRaisesRegex(ContractError, "NATIVE_PAYLOAD_REQUIRED"):
            validate_plan(self.plan, require_renderable=True)
        self.assertEqual(self.plan["gpuValidation"], "NOT_EXECUTED")

    def test_separately_verified_adapter_binding(self):
        profile = {"adapter": "UNIVERSAL_AREA_ASTRA_V2", "gpuMode": "gpu-required", "status": "READY",
                   "rendererCapability": "POLYGON_STATE_TIMELINE", "nativePayload": {"path": "synthetic-fixture.json", "sha256": "1" * 64, "validationStatus": "VERIFIED"}}
        bound = bind_renderer(self.plan, profile)
        self.assertIs(validate_plan(bound, require_renderable=True), bound)
        self.assertNotEqual(bound["renderProfile"], self.plan["renderProfile"])
        self.assertEqual(bound["legacyScenePlan"], self.plan["legacyScenePlan"])

    def test_unverified_native_binding_rejected(self):
        profile = deepcopy(self.plan["renderProfile"])
        profile["status"] = "READY"
        with self.assertRaisesRegex(ContractError, "VERIFIED_NATIVE_PAYLOAD_REQUIRED"):
            bind_renderer(self.plan, profile)

    def test_source_http403_and_null_body_hash_preserved(self):
        records = self.plan["sourceManifest"]["records"]
        historical = [r for r in records if r["id"].startswith("HISTORY_")]
        self.assertEqual(len(historical), 3)
        for source in historical:
            self.assertEqual(source["retrieval_http_status"], 403)
            self.assertIsNone(source["original_body_sha256"])
        self.assertFalse(self.plan["sourceManifest"]["semanticPolicy"]["sourceArticleBodiesVerified"])
        self.assertFalse(self.plan["sourceManifest"]["semanticPolicy"]["inventMissingHistory"])

    def test_unknown_topic_fails_without_history_generation(self):
        with self.assertRaisesRegex(PlanningError, "FACT_CATALOG_TOPIC_REQUIRED"):
            plan_topic("Atlantis empire territorial chronology", duration_seconds=80)

    def test_archival_and_daily_accuracy_requests_block(self):
        for topic in ("Korean War day-by-day fronts", "한국전쟁 실제 부대 이동", "Korean War archival reconstruction"):
            with self.subTest(topic=topic), self.assertRaisesRegex(PlanningError, "HISTORICAL_PRECISION_NOT_SUPPORTED"):
                plan_topic(topic, duration_seconds=80)

    def test_source_tamper_fails_before_compile(self):
        catalog = json.loads((ROOT / "HISTORY_CATALOG.json").read_bytes())
        catalog["entries"][0]["factsSHA256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "catalog.json"
            target.write_text(json.dumps(catalog))
            with self.assertRaisesRegex(PlanningError, "CATALOG_SOURCE_HASH_MISMATCH"):
                plan_topic("한국전쟁", duration_seconds=80, catalog_path=target)

    def test_source_unavailable_fails(self):
        catalog = json.loads((ROOT / "HISTORY_CATALOG.json").read_bytes())
        catalog["entries"][0]["status"] = "UNAVAILABLE"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "catalog.json"
            target.write_text(json.dumps(catalog))
            with self.assertRaisesRegex(PlanningError, "SOURCE_UNAVAILABLE"):
                plan_topic("한국전쟁", duration_seconds=80, catalog_path=target)

    def test_missing_node_explicitly_blocked(self):
        with self.assertRaisesRegex(PlanningError, "LEGACY_PLANNER_UNAVAILABLE"):
            plan_topic("한국전쟁", duration_seconds=80, node="/path/that/does/not/exist")

    def test_applied_visual_capabilities_are_source_only_not_full_scalar_v2(self):
        reuse = self.plan["visualReuse"]
        self.assertEqual(self.plan["visualStyle"], "REFERENCE_VISUAL_V2")
        self.assertEqual(self.plan["materialProfile"]["profileId"], "REFERENCE_V2_SOURCE_WITH_AREA_V3")
        self.assertEqual(self.plan["cameraProfile"]["candidateProfile"], "PRESERVED_V5_NATIVE_ARRIVAL_LOCK")
        self.assertEqual(reuse["frontier"], "UNCHANGED_AREA_V3_FRONT_LINE")
        self.assertEqual(reuse["nationalUnitMarkers"], "NOT_AVAILABLE_NOT_GENERATED")
        for field in ("referenceV2ScalarGainApplied", "referenceV2ScalarWhiteGoldFrontierApplied", "referenceV2UnitScaleApplied", "referenceV2FocusHoldCameraApplied"):
            self.assertIs(reuse[field], False)
        self.assertFalse(reuse["visualQualityApproved"])

    def test_replanning_is_deterministic(self):
        other = plan_topic("한국전쟁의 전선 변화를 80초 영상으로 만들어줘.")
        self.assertEqual(canonical_sha256(self.plan), canonical_sha256(other))

    def test_mutated_gap_overlap_and_total_reject(self):
        for mutate in (lambda p: p["scenes"][1].__setitem__("startFrame", 0),
                       lambda p: p.__setitem__("totalFrames", 2399),
                       lambda p: p["scenes"].pop()):
            plan = deepcopy(self.plan)
            mutate(plan)
            with self.assertRaises(ContractError):
                validate_plan(plan)

    def test_mutated_effect_camera_source_and_state_reject(self):
        for key in ("cameraProfile", "materialProfile", "territoryState", "sourceManifest", "boundaryStart"):
            plan = deepcopy(self.plan)
            plan["scenes"][1][key]["tamper"] = True
            with self.subTest(key=key), self.assertRaisesRegex(ContractError, "SCENE_BINDING_MISMATCH"):
                validate_plan(plan)

    def test_mutating_adjacent_timeline_changes_binding(self):
        plan = deepcopy(self.plan)
        before = canonical_sha256(plan["scenes"][2])
        plan["legacyScenePlan"]["time_steps"][1]["transition_frames"] += 1
        after = split_plan(plan, 300)
        self.assertNotEqual(canonical_sha256(after["scenes"][2]), before)
        with self.assertRaises(ContractError):
            validate_plan(plan)

    def test_zero_scene_budget_does_not_silently_fallback(self):
        with self.assertRaisesRegex(ContractError, "INVALID_SCENE_BUDGET"):
            plan_topic("한국전쟁", duration_seconds=80, max_scene_frames=0)

    def test_cli_output_exclusive_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "plan.json"
            target.write_bytes(b"prior preserved")
            result = subprocess.run([sys.executable, "-B", str(ROOT / "planner.py"), "한국전쟁 80초", "--output", str(target)], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_bytes(), b"prior preserved")


class NaturalLanguageTests(unittest.TestCase):
    def test_korean_english_compound_and_particles(self):
        for text, seconds in (("한국전쟁 80초로 만들어줘", 80), ("Korean War 120 seconds", 120),
                              ("한국전쟁 1분 20초 영상", 80), ("Korean War 10 minutes", 600)):
            with self.subTest(text=text):
                request = parse_request(text)
                self.assertEqual(request["durationSeconds"], seconds)
                self.assertFalse(request["externalAIConnected"])
                self.assertEqual(request["plannerMode"], "OFFLINE_CONSTRAINED_FACT_CATALOG")

    def test_duration_conflict_and_ambiguity(self):
        with self.assertRaisesRegex(PlanningError, "DURATION_CONFLICT"):
            parse_request("한국전쟁 80초", duration_seconds=120)
        with self.assertRaisesRegex(PlanningError, "AMBIGUOUS_DURATION"):
            parse_request("한국전쟁 80초 또는 120초")
        with self.assertRaisesRegex(PlanningError, "DURATION_REQUIRED"):
            parse_request("한국전쟁")

    def test_natural_resolution_fps_and_ratio(self):
        request = parse_request("한국전쟁 80초 30fps 1080×1920 9:16")
        self.assertEqual(request["resolution"], {"width": 1080, "height": 1920})
        self.assertEqual(request["aspectRatio"], "9:16")
        landscape = parse_request("한국전쟁 80초 가로 영상")
        self.assertEqual(landscape["aspectRatio"], "16:9")

    def test_configuration_conflicts_reject(self):
        for kwargs in ({"fps": 24}, {"resolution": {"width": 1920, "height": 1080}}, {"aspect_ratio": "16:9"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(PlanningError):
                parse_request("한국전쟁 80초 30fps 1080x1920 9:16", **kwargs)

    def test_invalid_resolution_and_style_reject(self):
        for resolution in ([], {"width": True, "height": 1920}, {"width": 1081, "height": 1920}):
            with self.subTest(resolution=resolution), self.assertRaises(PlanningError):
                parse_request("한국전쟁 80초", resolution=resolution)
        with self.assertRaisesRegex(PlanningError, "UNSUPPORTED_VISUAL_STYLE"):
            parse_request("한국전쟁 80초", visual_style="INVENTED")

    def test_exact_frame_math_never_rounds(self):
        self.assertEqual(total_frames(0.1, 30), 3)
        for duration, fps in ((80.01, 30), (0, 30), (float("nan"), 30), (80, True), (80, 0)):
            with self.subTest(duration=duration, fps=fps), self.assertRaises(ContractError):
                total_frames(duration, fps)


if __name__ == "__main__":
    unittest.main()
