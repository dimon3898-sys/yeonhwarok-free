"""Estimator contracts with synthetic temporary records, never real benchmarks.

Fixture MP4 bytes are not encoded footage; no renderer, ffprobe or paid job runs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from engine.backends import quality_settings
from engine.estimation import estimate_cpu_render
from engine.storage import plan_hash

RENDERER = "1" * 64
HASHES = {"adapter": "2" * 64, "render_html": "3" * 64, "render_tool": "4" * 64,
          "korean_font": "5" * 64, "assets/unit-only-earth.jpg": "6" * 64}
PROVENANCE = {"renderer_version": RENDERER, "native_hashes": HASHES,
              "native_assets": {"assets/unit-only-earth.jpg": "6" * 64},
              "asset_hashes": {"assets/unit-only-earth.jpg": "6" * 64}}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def requested(quality="HIGH", lighting="CINEMATIC_NIGHT", duration=4):
    return {"options": {"quality": quality}, "scenes": [
        {"scene_id": "S001", "scene_type": "ROUTE_CHASE", "render_quality": quality,
         "lighting_preset": lighting, "duration": duration}]}


class RenderEstimationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="world-estimate-unit-fixture-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "projects"
        self.provenance = copy.deepcopy(PROVENANCE)
        self.patcher = patch("engine.estimation._current_provenance", side_effect=lambda: self.provenance)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.serial = 0

    def reference(self, quality="HIGH", lighting="CINEMATIC_NIGHT", elapsed=10.,
                  duration=2., reused=False, same_bytes=None):
        self.serial += 1
        pid = f"project_unit{self.serial:06}"
        version = self.root / pid / "versions/v001"
        plan = requested(quality, lighting, duration)
        plan.update(project_id=pid, version="v001", duration=duration)
        plan["plan_hash"] = plan_hash(plan)
        write(version / "scene_plan.json", plan)
        write(version / "scene_json/S001.json", plan["scenes"][0])
        write(version / "approval.json", {"plan_hash": plan["plan_hash"], "user_approval": True})
        movie = version / "renders/S001/scene_S001_v001.mp4"
        movie.parent.mkdir(parents=True, exist_ok=True)
        movie.write_bytes(same_bytes or f"UNIT_ONLY_NOT_VIDEO_{self.serial}".encode())
        audit = movie.with_suffix(".audit.json")
        write(audit, {"unit_only": True})
        settings = quality_settings(quality, plan["scenes"][0])
        native = {"complete": True, "scene_id": "S001", "renderer": "MASTER_V3_SCENE_ADAPTER",
                  "duration": duration, "elapsedSeconds": elapsed, "fps": settings["fps"],
                  "frames": round(duration * settings["fps"]), "quality": quality,
                  "temporalSceneSamples": settings.get("temporal_samples", 1),
                  "internalResolution": [settings["internal_width"], round(settings["internal_width"] * 16 / 9)],
                  "outputResolution": [settings["output_width"], settings["output_height"]],
                  "sourceHashes": {**HASHES, "scene_json": hashlib.sha256((version / "scene_json/S001.json").read_bytes()).hexdigest()},
                  "sourceAssets": [{"path": name, "sha256": digest} for name, digest in PROVENANCE["native_assets"].items()],
                  "output": str(movie), "audit": str(audit),
                  "numericPreflight": {"finite": True, "cameraWithinEarth": False,
                                       "routeWithinEarth": False, "entityWithinEarth": False}}
        write(movie.with_suffix(".manifest.json"), native)
        finals = {}
        hashes = {}
        for name in ("final", "muted"):
            file = version / "final" / (name + ".mp4")
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"UNIT_ONLY_FINAL_BYTES")
            finals[name] = str(file)
            hashes[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        qc = {"passed": True, "file": finals["final"]}
        write(version / "qc/qc_report.json", qc)
        (version / "qc/qc_report.md").write_text("UNIT_ONLY_QC_CONTRACT")
        entry = {"complete": True, "scene_id": "S001", "renderer_version": RENDERER,
                 "quality": settings, "movie": str(movie), "audit": str(audit),
                 "video_sha256": hashlib.sha256(movie.read_bytes()).hexdigest(),
                 "audit_sha256": hashlib.sha256(audit.read_bytes()).hexdigest(),
                 "reused": reused, "current_render_seconds": 0. if reused else 99999.,
                 "elapsed_seconds": 88888., "native_manifest": native}
        result = {"plan_hash": plan["plan_hash"], "renderer_version": RENDERER,
                  "outputs": {**finals, "qc_report": str(version / "qc/qc_report.md")},
                  "final_sha256": hashes, "qc": qc, "scenes": [entry],
                  "metrics": {"measured": True, "backend": "CPU_LOCAL"},
                  "assets": {"passed": True, "errors": [], "renderer_version": RENDERER,
                             "assets": [{"file": name, "sha256": digest, "actual_sha256": digest,
                                         "license": "Unit-test provenance fixture only"}
                                        for name, digest in PROVENANCE["asset_hashes"].items()]}}
        write(version / "renders/scene_results.json", {"plan_hash": plan["plan_hash"], "scenes": [entry]})
        write(version / "renders/checkpoint.json", {"complete": True, "qc_passed": True,
                                                   "plan_hash": plan["plan_hash"], "completed_scenes": 1, "total_scenes": 1})
        write(version / "renders/project_result.json", result)
        return version, plan, result

    def save_result(self, version, result):
        write(version / "renders/scene_results.json", {"plan_hash": result["plan_hash"], "scenes": result["scenes"]})
        for entry in result["scenes"]:
            write(Path(entry["native_manifest"]["output"]).with_suffix(".manifest.json"), entry["native_manifest"])
        write(version / "renders/project_result.json", result)

    def estimate(self, plan=None, **kwargs):
        return estimate_cpu_render(plan or requested(), self.root, **kwargs)

    def test_empty_or_failed_final_qc_cannot_supply_a_prediction(self):
        self.assertIsNone(self.estimate()["seconds"])
        version, _, result = self.reference()
        result["qc"]["passed"] = False
        self.save_result(version, result)
        prediction = self.estimate()
        self.assertIsNone(prediction["seconds"])
        self.assertEqual(prediction["eligible_reference_count"], 0)
        self.assertIn("SUCCESSFUL_FINAL_QC_REQUIRED", prediction["rejected_reference_counts"])

    def test_native_elapsed_not_zero_reuse_or_pipeline_elapsed_drives_prediction(self):
        self.reference(elapsed=10, duration=2, reused=True)
        prediction = self.estimate()
        self.assertEqual(prediction["seconds"], 20)
        self.assertFalse(prediction["measured"])
        self.assertIsNone(prediction["cost_usd"])
        self.assertEqual(prediction["scope"], "uncached_scene_render_only")
        self.assertEqual(prediction["sources"][0]["native_elapsed_seconds"], 10)
        self.assertTrue(prediction["sources"][0]["reused_in_this_completed_version"])

    def test_exact_lighting_and_hero_buckets_take_priority(self):
        self.reference(lighting="CINEMATIC_NIGHT", elapsed=2)
        self.reference(lighting="HERO", elapsed=20)
        prediction = self.estimate(requested(lighting="HERO"))
        self.assertEqual(prediction["seconds"], 40)
        self.assertFalse(prediction["scenes"][0]["lighting_bucket_fallback"])
        self.assertEqual(len(prediction["sources"]), 1)

    def test_same_quality_fallback_is_median_and_explicit_about_unknown_lighting(self):
        self.reference(lighting="CINEMATIC_NIGHT", elapsed=8)
        self.reference(lighting="GEOGRAPHY_READABILITY", elapsed=12)
        prediction = self.estimate(requested(lighting="HERO"))
        self.assertEqual(prediction["seconds"], 20)
        self.assertTrue(prediction["scenes"][0]["lighting_bucket_fallback"])
        self.assertIn("unmeasured", prediction["scenes"][0]["fallback_note"])

    def test_reused_identical_source_video_is_counted_once_in_median(self):
        self.reference(elapsed=10, same_bytes=b"UNIT_ONLY_DUPLICATED_SOURCE")
        self.reference(elapsed=10, same_bytes=b"UNIT_ONLY_DUPLICATED_SOURCE", reused=True)
        self.reference(elapsed=30)
        prediction = self.estimate()
        self.assertEqual(prediction["eligible_reference_count"], 2)
        self.assertEqual(prediction["seconds"], 40)

    def test_high_does_not_invent_cinema_or_fast_times(self):
        self.reference()
        for quality in ("CINEMA", "FAST"):
            with self.subTest(quality=quality):
                prediction = self.estimate(requested(quality))
                self.assertIsNone(prediction["seconds"])
                self.assertEqual(prediction["scenes"][0]["reason"], "NO_SAME_QUALITY_AND_TEMPORAL_SAMPLE_REFERENCE")

    def test_cinema_uses_only_actual_two_sample_native_evidence(self):
        self.reference(quality="HIGH", elapsed=2)
        self.reference(quality="CINEMA", elapsed=24)
        prediction = self.estimate(requested("CINEMA"))
        self.assertEqual(prediction["seconds"], 48)
        self.assertEqual(prediction["scenes"][0]["temporal_samples"], 2)
        self.assertEqual(prediction["sources"][0]["quality"], "CINEMA")

    def test_unknown_quality_renderer_clip_or_scene_is_unknown_without_cost(self):
        for plan in (requested("ULTRA"), requested({"preset": "HIGH"}),
                     {"options": {"quality": "HIGH"}, "scenes": ["invalid"]}):
            with self.subTest(plan=plan):
                prediction = self.estimate(plan)
                self.assertIsNone(prediction["seconds"])
                self.assertIsNone(prediction["cost_usd"])
                self.assertFalse(prediction["measured"])
        clip = requested()
        clip["scenes"][0]["scene_type"] = "CINEMATIC_CLIP"
        self.assertEqual(self.estimate(clip)["reason"], "CINEMATIC_CLIP_TIMING_NOT_MODELLED")
        self.assertEqual(self.estimate(current_renderer_version="0" * 64)["reason"], "REQUESTED_RENDERER_IS_NOT_CURRENT")

    def test_native_frames_sample_count_elapsed_and_provenance_are_required(self):
        mutations = [lambda n: n.update(frames=1), lambda n: n.update(temporalSceneSamples=2),
                     lambda n: n.update(temporalSceneSamples=True), lambda n: n.update(elapsedSeconds=0),
                     lambda n: n.update(elapsedSeconds=float("nan")),
                     lambda n: n["sourceHashes"].update(adapter="0" * 64),
                     lambda n: n.update(sourceAssets=[]),
                     lambda n: n["numericPreflight"].update(routeWithinEarth=True)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                version, _, result = self.reference()
                mutate(result["scenes"][0]["native_manifest"])
                self.save_result(version, result)
        self.assertIsNone(self.estimate()["seconds"])
        self.assertEqual(self.estimate()["eligible_reference_count"], 0)

    def test_stale_approval_incomplete_checkpoint_and_old_renderer_are_excluded(self):
        v1, _, _ = self.reference()
        write(v1 / "approval.json", {"user_approval": True, "plan_hash": "0" * 64})
        v2, plan2, _ = self.reference()
        write(v2 / "renders/checkpoint.json", {"complete": False, "qc_passed": True,
                                              "plan_hash": plan2["plan_hash"]})
        v3, _, result3 = self.reference()
        result3["renderer_version"] = "0" * 64
        self.save_result(v3, result3)
        self.assertIsNone(self.estimate()["seconds"])

    def test_missing_or_modified_media_and_mismatched_scene_source_are_excluded(self):
        v1, _, result1 = self.reference()
        Path(result1["outputs"]["final"]).unlink()
        v2, _, result2 = self.reference()
        changed = Path(result2["scenes"][0]["movie"])
        later = (v2 / "renders/project_result.json").stat().st_mtime_ns + 1
        os.utime(changed, ns=(later, later))
        v3, _, _ = self.reference()
        write(v3 / "scene_json/S001.json", {"altered": True})
        self.assertIsNone(self.estimate()["seconds"])

    def test_declared_synthetic_records_are_not_production_reference_data(self):
        version, _, result = self.reference()
        result["synthetic"] = True
        self.save_result(version, result)
        prediction = self.estimate()
        self.assertIsNone(prediction["seconds"])
        self.assertIn("SYNTHETIC_REFERENCE_FORBIDDEN", prediction["rejected_reference_counts"])

    def test_path_only_korean_font_provenance_matches_the_actual_registry_contract(self):
        version, _, result = self.reference()
        name = "web/fonts/NotoSansCJKkr-Regular.otf"
        self.provenance["asset_hashes"][name] = "5" * 64
        result["assets"]["assets"].append({"path": str(APP_ROOT / name), "id": "noto-sans-cjk-kr",
                                            "sha256": "5" * 64, "actual_sha256": "5" * 64,
                                            "license": "Unit-test font provenance fixture only"})
        self.save_result(version, result)
        prediction = self.estimate()
        self.assertEqual(prediction["seconds"], 20)
        self.assertEqual(prediction["eligible_reference_count"], 1)

    def test_mixed_plan_with_unobserved_cinema_returns_no_total_prediction(self):
        self.reference()
        plan = requested()
        cinema = copy.deepcopy(plan["scenes"][0])
        cinema.update(scene_id="S002", render_quality="CINEMA")
        plan["scenes"].append(cinema)
        prediction = self.estimate(plan)
        self.assertIsNone(prediction["seconds"])
        self.assertEqual(prediction["scenes"][0]["seconds"], 20)
        self.assertIsNone(prediction["scenes"][1]["seconds"])

    def test_prediction_is_deterministic_and_leaves_all_fixture_records_unchanged(self):
        self.reference()
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.root.rglob("*") if path.is_file()}
        first = self.estimate()
        self.assertEqual(first, self.estimate())
        after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
