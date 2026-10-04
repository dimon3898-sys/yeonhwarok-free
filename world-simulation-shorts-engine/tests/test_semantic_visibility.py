"""Regression for the genuine 6.65 s invisible New York reveal, without GL."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))
from engine.planner import replace_geographic_event_with_milestone
from engine.visibility import certify_semantic_visibility, semantic_input_hash


class SemanticVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((APP_ROOT / "tests/fixtures/semantic_e006_regression.json").read_text())

    def test_actual_mid_atlantic_new_york_reveal_is_blocked(self):
        report = certify_semantic_visibility(self.fixture, scene_ids=["S002"])
        self.assertFalse(report["passed"])
        self.assertEqual([f["event_id"] for f in report["failures"]], ["E006"])
        failure = report["failures"][0]
        self.assertEqual(failure["code"], "GEOGRAPHIC_EVENT_NOT_VISIBLE")
        self.assertAlmostEqual(failure["projection_at_scheduled_time"]["x"], -1.5208564134, places=8)
        self.assertFalse(failure["projection_at_scheduled_time"]["inside_event_safe_area"])

    def test_sourced_remaining_distance_repairs_only_event(self):
        plan = copy.deepcopy(self.fixture)
        scene = plan["scenes"][0]
        before = copy.deepcopy(scene)
        event = next(e for e in scene["visual_events"] if e["id"] == "E006")
        repair = replace_geographic_event_with_milestone(scene, event)
        self.assertGreater(repair["remaining_km"], 0)
        for field in ("camera_start", "camera_end", "routes", "entities"):
            self.assertEqual(scene[field], before[field])
        self.assertEqual(event["time"], 2.65)
        self.assertEqual(event["caused_by"], "E005")
        report = certify_semantic_visibility(plan, scene_ids=["S002"])
        self.assertTrue(report["passed"], report["failures"])
        eligible = next(e for e in report["events"] if e["event_id"] == "E006")
        self.assertIn("information", eligible["eligible_primitives"])
        self.assertGreaterEqual(eligible["visible_seconds"], .1)

    def test_physical_route_event_cannot_pass_with_only_information_text(self):
        plan = copy.deepcopy(self.fixture)
        event = next(e for e in plan["scenes"][0]["visual_events"] if e["id"] == "E006")
        event.update(kind="route_start", target_id="NONEXISTENT_ROUTE", text="A route starts")
        report = certify_semantic_visibility(plan, scene_ids=["S002"])
        self.assertFalse(report["passed"])
        self.assertTrue(any(f["code"] == "MEANINGFUL_EVENT_NOT_ELIGIBLE" and f["event_id"] == "E006"
                            for f in report["failures"]))

    def test_cache_is_detached_and_ignores_recorded_certificate_metadata(self):
        plan = copy.deepcopy(self.fixture)
        original_hash = semantic_input_hash(plan)
        first = certify_semantic_visibility(plan, scene_ids=["S002"])
        first["failures"].clear()  # A caller cannot alter the cached certificate.
        plan["gate"] = {"passed": True}
        plan.setdefault("metadata", {})["semantic_visibility"] = first
        self.assertEqual(semantic_input_hash(plan), original_hash)
        repeated = certify_semantic_visibility(plan, scene_ids=["S002"])
        self.assertTrue(repeated["certificate_cache_hit"])
        self.assertFalse(repeated["passed"])
        self.assertEqual(repeated["failures"][0]["event_id"], "E006")

    def test_unknown_scene_and_missing_runtime_fail_closed(self):
        self.assertEqual(certify_semantic_visibility(self.fixture, scene_ids=["UNKNOWN"])["failures"][0]["code"],
                         "UNKNOWN_SCOPED_SCENE")
        with patch("engine.visibility.TOOL", APP_ROOT / "tools/does-not-exist.mjs"):
            report = certify_semantic_visibility(self.fixture)
        self.assertFalse(report["passed"])
        self.assertEqual(report["failures"][0]["code"], "SEMANTIC_CERTIFICATION_FAILED")

    def test_valid_clip_annotations_delegate_without_physical_map_claims(self):
        plan = json.loads((APP_ROOT / "tests/fixtures/semantic_clip_regression.json").read_text())
        report = certify_semantic_visibility(plan, scene_ids=["S004"])
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual({p for event in report["events"] for p in event["eligible_primitives"]},
                         {"clip_information"})
        self.assertTrue(all(event["source"]["sha256"] for event in report["events"]))
        self.assertFalse(report["certificate_cache_hit"])
        self.assertFalse(certify_semantic_visibility(plan, scene_ids=["S004"])["certificate_cache_hit"])

    def test_clip_physical_event_unlicensed_source_and_missing_media_are_blocked(self):
        plan = json.loads((APP_ROOT / "tests/fixtures/semantic_clip_regression.json").read_text())
        bad = copy.deepcopy(plan)
        bad["scenes"][0]["visual_events"][0]["kind"] = "route_start"
        report = certify_semantic_visibility(bad, scene_ids=["S004"])
        self.assertFalse(report["passed"])
        self.assertTrue(any(error["code"] == "UNSUPPORTED_CLIP_SEMANTIC_EVENT" for error in report["failures"]))
        for mutation in ({"license": "", "user_owned": False},
                         {"path": str(APP_ROOT / "library/uploads/nonexistent.mp4")}):
            bad = copy.deepcopy(plan)
            bad["scenes"][0]["cinematic_clip"].update(mutation)
            report = certify_semantic_visibility(bad, scene_ids=["S004"])
            self.assertFalse(report["passed"])
            self.assertTrue(any(error["code"] == "CLIP_SOURCE_PREFLIGHT_FAILED" for error in report["failures"]))

    def test_first_clip_has_actual_hook_overlay_eligibility(self):
        plan = json.loads((APP_ROOT / "tests/fixtures/semantic_clip_regression.json").read_text())
        plan["scenes"][0]["start_time"] = 0
        plan["scenes"][0]["hook"] = "다음 목적지는?"
        report = certify_semantic_visibility(plan)
        self.assertTrue(report["passed"], report["failures"])
        self.assertTrue(report["opening_hook_eligible"])


if __name__ == "__main__":
    unittest.main()
