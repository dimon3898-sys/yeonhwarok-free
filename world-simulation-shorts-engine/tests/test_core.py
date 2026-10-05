"""Behavioral regression tests for planning, provenance, approval and scoped edits.

This suite never renders the existing MASTER videos or starts a paid service.
Actual browser/video integration evidence belongs in projects/*/versions/*/qc.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from engine.assets import asset_registry, validate_assets
from engine.gis import RouteEngine, UnknownLocation, coordinate_source_report, resolve_location, verified_coordinate
from engine.plugins import UnsupportedVisualRequirement, require_plugins
from engine.retention import analyze_retention
from engine.revisions import approve_revision, preview_revision
from engine.schema import validate_plan
from engine.storage import EngineError, ProjectStore, atomic_json


def request(topic: str, duration: float = 20) -> dict:
    return {'production_preset': 'LEGACY', "topic": topic, "duration": duration, "style": "긴장감 있는 세계 시뮬레이션",
            "quality": "HIGH", "tts": False, "subtitles": False, "bgm": True}


def generate(topic: str, duration: float = 20) -> dict:
    from engine.planner import generate_plan
    return generate_plan(request(topic, duration))


def error_codes(report: dict) -> set[str]:
    return {error["code"] for error in report["errors"]}


def all_events(plan: dict) -> list[dict]:
    return [event for scene in plan["scenes"] for event in scene["visual_events"]]


class PlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aviation = generate("런던에서 파리, 로마로 이어지는 민간 항공 여행", 20)
        cls.shipping = generate("만약 수에즈 운하가 7일 동안 막힌다면?", 75)
        cls.hypothetical = generate("만약 서울과 싱가포르를 직접 연결한다면? 가상 도시 연결", 40)

    def test_three_distinct_topics_produce_valid_causal_plans(self):
        for name, plan in [("aviation", self.aviation), ("shipping", self.shipping),
                           ("hypothetical", self.hypothetical)]:
            with self.subTest(topic=name):
                report = validate_plan(plan)
                self.assertTrue(report["passed"], report["errors"])
                self.assertTrue(report["retention"]["passed"])
                self.assertFalse(report["retention"]["metrics"]["camera_events_counted"])
                self.assertEqual(sum(scene["duration"] for scene in plan["scenes"]), plan["duration"])
                for previous, following in zip(plan["scenes"], plan["scenes"][1:]):
                    self.assertEqual(previous["exit_state"], following["entry_state"])

    def test_different_routes_are_not_the_fixed_master_v3_story(self):
        targets = {target for scene in self.aviation["scenes"] for target in scene["geographic_targets"]}
        self.assertTrue({"london", "paris", "rome"}.issubset(targets), targets)
        self.assertFalse({"seoul", "tokyo", "singapore"}.issubset(targets))
        self.assertNotEqual(self.aviation["story"]["domain"], self.shipping["story"]["domain"])

    def test_shipping_uses_sourced_maritime_routes_and_two_peaks(self):
        routes = [route for scene in self.shipping["scenes"] for route in scene["routes"]]
        self.assertTrue(routes)
        self.assertTrue(all(route["kind"] == "sea" for route in routes))
        self.assertTrue(all(len(route["points"]) > 3 for route in routes))
        self.assertGreaterEqual(analyze_retention(self.shipping)["metrics"]["peak_count"], 2)
        claims = self.shipping["story"]["claims"]
        self.assertTrue(any(c["status"] == "ASSUMPTION" for c in claims))
        self.assertTrue(any(c["status"] == "SIMULATION" and c.get("assumption_ids") for c in claims))

    def test_hypothetical_connection_is_never_reported_as_fact(self):
        claims = self.hypothetical["story"]["claims"]
        self.assertTrue(any(c["status"] == "ASSUMPTION" for c in claims))
        self.assertTrue(any(c["status"] == "SIMULATION" for c in claims))
        for claim in claims:
            if claim["status"] == "FACT":
                self.assertTrue(claim["source_ids"])
        self.assertTrue(any(scene["fact_status"] != "FACT" for scene in self.hypothetical["scenes"]))

    def test_unknown_or_unimplemented_visuals_fail_closed(self):
        for topic, expected in [("판게아가 분리되는 모습을 보여줘", "TIME_MORPH"),
                                ("미사일과 전투기가 이동하는 전쟁 시뮬레이션", "WAR_VFX")]:
            with self.subTest(topic=topic):
                with self.assertRaises(UnsupportedVisualRequirement) as error:
                    generate(topic, 40)
                self.assertIn(expected, error.exception.modules)

    def test_camera_motion_and_decorative_pulses_cannot_satisfy_retention(self):
        plan = copy.deepcopy(self.aviation)
        for event in all_events(plan):
            event["kind"] = "camera_move"
            event["meaningful"] = True
        report = analyze_retention(plan)
        self.assertFalse(report["passed"])
        self.assertEqual(report["metrics"]["meaningful_event_count"], 0)
        self.assertIn("EVENT_DENSITY", error_codes(report))
        self.assertIn("WEAK_FIRST_3_SECONDS", error_codes(report))

    def test_over_three_second_semantic_gap_fails_gate(self):
        plan = copy.deepcopy(self.aviation)
        for scene in plan["scenes"]:
            scene["visual_events"] = [event for event in scene["visual_events"]
                                      if not 5 < scene["start_time"] + event["time"] < 10]
        self.assertIn("STAGNATION", error_codes(analyze_retention(plan)))

    def test_repeated_entity_departures_fail_event_diversity(self):
        plan = copy.deepcopy(self.aviation)
        for event in all_events(plan):
            event["kind"] = "entity_departure"
        self.assertIn("EVENT_DIVERSITY", error_codes(analyze_retention(plan)))

    def test_missing_peak_and_broken_causal_link_fail_gate(self):
        plan = copy.deepcopy(self.shipping)
        for event in all_events(plan):
            if event["kind"] == "peak_reveal" or event["role"] == "peak":
                event["kind"] = "connection_reveal"
                event["role"] = "progression"
        report = analyze_retention(plan)
        self.assertIn("MISSING_PEAK", error_codes(report))
        plan = copy.deepcopy(self.aviation)
        all_events(plan)[-1]["caused_by"] = "event_that_does_not_exist"
        self.assertIn("BROKEN_CAUSALITY", error_codes(analyze_retention(plan)))

    def test_coordinates_cannot_be_changed_even_with_a_real_source_name(self):
        plan = copy.deepcopy(self.aviation)
        plan["scenes"][0]["coordinates"]["lon"] += .5
        self.assertIn("UNVERIFIED_GIS_COORDINATE", error_codes(validate_plan(plan)))

    def test_unsourced_fact_and_unbound_simulation_are_rejected(self):
        plan = copy.deepcopy(self.shipping)
        fact = next(c for c in plan["story"]["claims"] if c["status"] == "FACT")
        fact["source_ids"] = []
        simulation = next(c for c in plan["story"]["claims"] if c["status"] == "SIMULATION")
        simulation["assumption_ids"] = []
        codes = error_codes(validate_plan(plan))
        self.assertIn("UNSOURCED_FACT", codes)
        self.assertIn("UNBOUND_SIMULATION", codes)

    def test_invalid_camera_height_and_unreadable_geography_are_rejected(self):
        plan = copy.deepcopy(self.aviation)
        plan["scenes"][0]["camera_start"]["height"] = -.1
        self.assertIn("SCHEMA_ERROR", error_codes(validate_plan(plan)))
        plan = copy.deepcopy(self.aviation)
        scene = plan["scenes"][1]
        scene["scene_type"] = "COUNTRY_FOCUS"
        scene["lighting_preset"] = "CINEMATIC_NIGHT"
        self.assertIn("GEOGRAPHY_LIGHTING_UNREADABLE", error_codes(validate_plan(plan)))

    def test_long_narration_blocks_render_instead_of_silently_speeding_tts(self):
        plan = copy.deepcopy(self.aviation)
        plan["scenes"][0]["narration"] = "설명해야 하는 내용이 너무 많습니다. " * 80
        self.assertIn("NARRATION_TOO_LONG", error_codes(validate_plan(plan)))

    def test_event_coordinates_and_sound_timestamps_are_validated(self):
        plan = copy.deepcopy(self.aviation)
        event = all_events(plan)[0]
        event["coordinates"]["lat"] += 1
        self.assertIn("UNVERIFIED_GIS_COORDINATE", error_codes(validate_plan(plan)))
        plan = copy.deepcopy(self.aviation)
        scene = next(s for s in plan["scenes"] if any(e.get("visual_event_id") for e in s["sound_events"]))
        cue = next(e for e in scene["sound_events"] if e.get("visual_event_id"))
        cue["time"] += .15
        self.assertIn("SOUND_EVENT_DESYNC", error_codes(validate_plan(plan)))
        cue["visual_event_id"] = "missing_visual_event"
        self.assertIn("UNKNOWN_SOUND_EVENT_TARGET", error_codes(validate_plan(plan)))

    def test_discontinuous_scene_boundaries_block_render(self):
        plan = copy.deepcopy(self.aviation)
        plan["scenes"][1]["entry_state"]["earth_rotation"] += .1
        self.assertIn("SCENE_DEPENDENCY_MISMATCH", error_codes(validate_plan(plan)))

    def test_longer_duration_is_not_forced_to_eight_scenes(self):
        plan = generate("뉴욕에서 런던을 거쳐 파리로 연결하는 항공 여행", 180)
        report = validate_plan(plan)
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(plan["duration"], 180)
        self.assertGreater(len(plan["scenes"]), 8)


class GeographicProvenanceTests(unittest.TestCase):
    def test_catalog_coordinates_round_trip_but_made_up_place_does_not(self):
        for identifier in ["london", "rome", "airport_icn", "SUEZ_CANAL", "CAPE_OF_GOOD_HOPE"]:
            with self.subTest(identifier=identifier):
                coordinate = resolve_location(identifier)["coordinates"]
                self.assertTrue(verified_coordinate(coordinate), coordinate)
                changed = dict(coordinate, source_id="fabricated_source")
                self.assertFalse(verified_coordinate(changed))
        with self.assertRaises(UnknownLocation):
            resolve_location("Atlantis International Airport")

    def test_sea_waypoints_require_correct_provenance(self):
        points = RouteEngine.sea("ROTTERDAM_SINGAPORE_CAPE")
        self.assertGreater(len(points), 3)
        self.assertTrue(all(verified_coordinate(point) for point in points))
        self.assertFalse(verified_coordinate(dict(points[len(points)//2], source_id="ourairports")))

    def test_land_routes_and_missing_plugins_are_not_fabricated(self):
        with self.assertRaises(UnsupportedVisualRequirement) as error:
            RouteEngine.land("london", "paris")
        self.assertIn("LAND_ROUTING", error.exception.modules)
        with self.assertRaises(UnsupportedVisualRequirement):
            require_plugins(["TIME_MORPH"])

    def test_geographic_source_files_match_recorded_hashes(self):
        for source in coordinate_source_report():
            with self.subTest(source=source["id"]):
                source_path = Path(source["local_path"])
                if not source_path.parts or source_path.parts[0] != "data":
                    source_path = APP_ROOT / "data" / source_path
                else:
                    source_path = APP_ROOT / source_path
                self.assertTrue(source_path.is_file(), source_path)
                self.assertEqual(hashlib.sha256(source_path.read_bytes()).hexdigest(), source["sha256"])
                self.assertTrue(source["license"])
                self.assertTrue(source["author"])

    def test_shared_v3_assets_have_real_licenses_and_matching_hashes(self):
        result = validate_assets()
        self.assertTrue(result["passed"], result["errors"])
        assets = asset_registry()
        self.assertGreaterEqual(len(assets), 4)
        for asset in assets:
            self.assertTrue(asset["license"])
            self.assertTrue(asset["author"])
            self.assertTrue(asset["sha256"])
        earth = [asset for asset in assets if asset["file"].startswith("assets/v3/earth/")]
        self.assertEqual(len(earth), 3)
        self.assertTrue(all("CC BY" in asset["license"] or "CC-BY" in asset["license"] for asset in earth))


class ApprovalAndRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="world_engine_test_")
        self.addCleanup(self.temp.cleanup)
        self.store = ProjectStore(self.temp.name)
        self.original = generate("런던에서 파리, 로마로 이어지는 민간 항공 여행", 20)
        self.created = self.store.create(request(self.original["request"]["topic"]), self.original)
        self.pid = self.created["project"]["id"]

    def assertEngineCode(self, code: str, action):
        with self.assertRaises(EngineError) as error:
            action()
        self.assertEqual(error.exception.code, code)

    def test_render_requires_approval_of_the_exact_current_plan(self):
        self.assertEngineCode("APPROVAL_REQUIRED", lambda: self.store.require_approved(self.pid, "v001"))
        plan = self.store.get(self.pid)["plan"]
        self.assertEngineCode("PLAN_CHANGED", lambda: self.store.approve(self.pid, "v001", "0"*64))
        self.store.approve(self.pid, "v001", plan["plan_hash"])
        self.assertEqual(self.store.require_approved(self.pid, "v001")["plan_hash"], plan["plan_hash"])

    def test_plan_changed_after_approval_is_rejected(self):
        plan = self.store.get(self.pid)["plan"]
        self.store.approve(self.pid, "v001", plan["plan_hash"])
        plan["scenes"][0]["camera_speed"] *= 1.1
        atomic_json(self.store.version_path(self.pid, "v001")/"scene_plan.json", plan)
        self.assertEngineCode("PLAN_CHANGED", lambda: self.store.require_approved(self.pid, "v001"))

    def test_natural_language_edit_preserves_other_scenes_and_boundary_states(self):
        before = self.store.get(self.pid)["plan"]
        source_file = self.store.version_path(self.pid, "v001")/"scene_plan.json"
        original_bytes = source_file.read_bytes()
        revision = preview_revision(self.store, self.pid, "v001", "첫 3초를 주간으로 더 빠르게")
        self.assertEqual(revision["affected_scenes"], [before["scenes"][0]["scene_id"]])
        self.assertFalse(revision["approved"])
        self.assertEqual(source_file.read_bytes(), original_bytes)
        after = revision["plan"]
        self.assertEqual(after["scenes"][0]["lighting_preset"], "DAY_DOCUMENTARY")
        self.assertGreater(after["scenes"][0]["camera_speed"], before["scenes"][0]["camera_speed"])
        self.assertEqual(after["scenes"][1:], before["scenes"][1:])
        for key in ["entry_state", "exit_state", "camera_start", "camera_end"]:
            self.assertEqual(after["scenes"][0][key], before["scenes"][0][key])
        approved = approve_revision(self.store, self.pid, revision["revision_id"])
        self.assertEqual(approved["version"], "v002")
        self.store.require_approved(self.pid, "v002")
        self.assertEqual(source_file.read_bytes(), original_bytes)

    def test_stale_revision_does_not_overwrite_a_new_version(self):
        first = preview_revision(self.store, self.pid, "v001", "첫 장면 낮으로")
        second = preview_revision(self.store, self.pid, "v001", "마지막 장면 더 빠르게")
        approve_revision(self.store, self.pid, first["revision_id"])
        self.assertEngineCode("STALE_REVISION", lambda: approve_revision(self.store, self.pid, second["revision_id"]))
        self.assertEqual(self.store.get(self.pid)["version"], "v002")

    def test_interrupted_job_is_resumable_without_changing_the_plan(self):
        before = self.store.get(self.pid)["plan"]["plan_hash"]
        self.store.set_status(self.pid, "v001", status="rendering")
        self.store.recover()
        self.assertEqual(self.store.status(self.pid)["status"], "interrupted")
        self.assertEqual(self.store.get(self.pid)["plan"]["plan_hash"], before)

    def test_unrecognized_edits_do_not_create_a_new_version(self):
        self.assertEngineCode("UNSUPPORTED_EDIT", lambda: preview_revision(self.store, self.pid, "v001", "첫 장면 유니콘으로 바꿔"))
        self.assertEqual(self.store.get(self.pid)["project"]["versions"], ["v001"])

    def test_scene_cache_only_changes_for_the_edited_scene(self):
        from engine.rendering import scene_cache_key
        from engine.backends import quality_settings
        before = self.store.get(self.pid)["plan"]
        revision = preview_revision(self.store, self.pid, "v001", "첫 장면을 주간으로")
        after = revision["plan"]
        assets = validate_assets(before)
        unchanged = before["scenes"][1]
        settings = quality_settings("HIGH", unchanged)
        key = scene_cache_key(unchanged, assets, settings, "renderer-version-1")
        self.assertEqual(key, scene_cache_key(after["scenes"][1], assets, settings, "renderer-version-1"))
        changed_before = before["scenes"][0]
        changed_after = after["scenes"][0]
        self.assertNotEqual(scene_cache_key(changed_before, assets, settings, "renderer-version-1"),
                            scene_cache_key(changed_after, assets, settings, "renderer-version-1"))
        self.assertNotEqual(key, scene_cache_key(unchanged, assets, settings, "renderer-version-2"))
        self.assertNotEqual(key, scene_cache_key(unchanged, assets, quality_settings("FAST", unchanged), "renderer-version-1"))


class GPUCostProtectionTests(unittest.TestCase):
    def test_no_worker_is_created_without_cost_approval_or_beyond_limit(self):
        from engine.backends import GPUCloudBackend, RenderEstimate
        class Adapter:
            calls = []
            def start_worker(self, **kwargs):
                self.calls.append("start")
                return "test-worker"
        adapter = Adapter()
        backend = GPUCloudBackend(adapter, maximum_cost_usd=1)
        with self.assertRaisesRegex(RuntimeError, "GPU_COST_APPROVAL_REQUIRED"):
            backend.run([], APP_ROOT, lambda _: None)
        backend = GPUCloudBackend(adapter, maximum_cost_usd=1,
                                  approved_estimate=RenderEstimate("GPU_CLOUD", False, 10, 2, "unit-test estimate"))
        with self.assertRaisesRegex(RuntimeError, "GPU_COST_LIMIT_EXCEEDED"):
            backend.run([], APP_ROOT, lambda _: None)
        self.assertEqual(adapter.calls, [])

    def test_provider_worker_is_stopped_after_execution_failure(self):
        from engine.backends import GPUCloudBackend, RenderEstimate
        class Adapter:
            def __init__(self):
                self.calls = []
            def start_worker(self, **kwargs):
                self.calls.append("start")
                return "test-worker"
            def run(self, worker, **kwargs):
                self.calls.append("run")
                raise RuntimeError("provider-test-failure")
            def stop_worker(self, worker):
                self.calls.append("stop")
        adapter = Adapter()
        backend = GPUCloudBackend(adapter, maximum_cost_usd=1,
                                  approved_estimate=RenderEstimate("GPU_CLOUD", False, 10, .2, "unit-test estimate"))
        with self.assertRaisesRegex(RuntimeError, "provider-test-failure"):
            backend.run([], APP_ROOT, lambda _: None)
        self.assertEqual(adapter.calls, ["start", "run", "stop"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
