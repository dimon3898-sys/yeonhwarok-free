"""Boundary tests with explicitly synthetic temporary evidence, never real exports.

Fixture MP4 bytes are not encoded footage or a production QC/quality claim.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aggregate_benchmarks import aggregate
from deliverable_evidence import (EvidenceError, MIB, create_export, github_size_report,
                                 load_completed_version, plan_digest, sha256, split_zip, verify_parts)


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, dict):
        path.write_text(json.dumps(value), encoding="utf-8")
    elif isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_bytes(value)


def fixture(root: Path):
    version = root / "project_abcdef123456/versions/v001"
    plan = {"project_id": "project_abcdef123456", "version": "v001", "duration": 20,
            "options": {"quality": "HIGH"}, "synthetic_test_fixture": True,
            "scenes": [{"scene_id": "S001", "duration": 10}, {"scene_id": "S002", "duration": 10}]}
    plan["plan_hash"] = plan_digest(plan)
    write(version / "scene_plan.json", plan)
    write(version / "approval.json", {"plan_hash": plan["plan_hash"], "user_approval": True})
    for name in ("scene_plan_readable.md", "script.txt", "assets/source_report.md"):
        write(version / name, "Synthetic boundary fixture only")
    write(version / "assets/source_report.json", {"synthetic_test_fixture": True})
    write(version / "story/story_plan.json", {"synthetic_test_fixture": True})
    final = version / "final/attempt002/final.mp4"
    muted = version / "final/attempt002/final_muted.mp4"
    # Incorrect preserved first attempts must never be chosen by guessing paths.
    write(version / "final/final.mp4", b"FAILED_PRESERVED_FIRST_ATTEMPT")
    write(final, b"SYNTHETIC_FINAL_FIXTURE_NOT_ACTUAL_VIDEO")
    write(muted, b"SYNTHETIC_MUTED_FIXTURE_NOT_ACTUAL_VIDEO")
    qc_dir = version / "qc/attempt002"
    qc = {"passed": True, "file": str(final), "synthetic_test_fixture": True}
    write(qc_dir / "qc_report.json", qc)
    write(qc_dir / "qc_report.md", "SYNTHETIC AUTOMATIC QC CONTRACT")
    write(qc_dir / "contact_sheet.png", b"SYNTHETIC_IMAGE_FIXTURE")
    write(version / "audio/audio_report.json", {"synthetic_test_fixture": True})
    write(version / "audio/subtitles.ass", "SYNTHETIC_ASS")
    write(version / "assets/DO_NOT_EXPORT_TEXTURE.jpg", b"EXCLUDED_LARGE_TEXTURE")
    write(version / "renders/S003/DO_NOT_EXPORT_PARTIAL.mp4", b"PARTIAL")
    entries = []
    for index, scene in enumerate(plan["scenes"]):
        sid = scene["scene_id"]
        movie = version / f"renders/{sid}/scene_{sid}_v001_attempt002.mp4"
        audit = movie.with_suffix(".audit.json")
        write(movie, b"SYNTHETIC_SCENE_BYTES" + sid.encode())
        write(audit, {"synthetic_test_fixture": True, "scene_id": sid})
        native = {"complete": True, "quality": "HIGH", "elapsedSeconds": 999 if index else 2.5}
        write(movie.with_suffix(".manifest.json"), native)
        write(movie.with_suffix(".checkpoint.json"), {"status": "complete"})
        write(version / f"scene_json/{sid}.json", scene)
        entries.append({"scene_id": sid, "complete": True, "movie": str(movie), "audit": str(audit),
                        "video_sha256": sha256(movie), "audit_sha256": sha256(audit),
                        "quality": {"quality": "HIGH", "internal_width": 2160},
                        "reused": bool(index), "current_render_seconds": 999 if index else 2.6,
                        "elapsed_seconds": 999 if index else 2.6, "native_manifest": native})
    result = {"plan_hash": plan["plan_hash"], "qc": qc, "scenes": entries,
              "outputs": {"final": str(final), "muted": str(muted),
                          "qc_report": str(qc_dir / "qc_report.md"),
                          "contact_sheet": str(qc_dir / "contact_sheet.png"),
                          "source_report": str(version / "assets/source_report.md")},
              "final_sha256": {"final": sha256(final), "muted": sha256(muted)},
              "publication_quality": True, "aesthetic_review_required": True,
              "metrics": {"measured": True, "backend": "CPU_LOCAL", "scene_count": 2,
                          "rendered_scene_count": 1, "cached_scene_count": 1,
                          "scene_render_seconds": 2.6, "audio_preparation_seconds": .5,
                          "assembly_audio_mux_subtitles_seconds": .8, "qc_seconds": .4,
                          "total_seconds": 4.3}}
    write(version / "renders/project_result.json", result)
    write(version / "renders/scene_results.json", {"plan_hash": plan["plan_hash"], "scenes": entries})
    write(version / "renders/checkpoint.json", {"complete": True, "qc_passed": True,
                                               "plan_hash": plan["plan_hash"],
                                               "completed_scenes": 2, "total_scenes": 2})
    return version, plan, result


class DeliverableToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="world-deliverable-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.version, self.plan, self.result = fixture(self.root / "projects")

    def test_export_resolves_recovery_outputs_preserves_sources_and_excludes_partials(self):
        before = {str(path): sha256(path) for path in self.version.rglob("*") if path.is_file()}
        output = self.root / "new deliverables/fixture archive.zip"
        report = create_export(load_completed_version(self.version), output)
        self.assertTrue(report["automatic_qc_passed"])
        self.assertTrue(report["aesthetic_review_required"])
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            self.assertEqual(archive.read("final/final.mp4"), Path(self.result["outputs"]["final"]).read_bytes())
            self.assertIn("qc/qc_report.json", names)
            self.assertIn("scene_json/S001.json", names)
            self.assertIn("renders/S001/scene_S001_v001_attempt002.manifest.json", names)
            self.assertNotIn("assets/DO_NOT_EXPORT_TEXTURE.jpg", names)
            self.assertNotIn("renders/S003/DO_NOT_EXPORT_PARTIAL.mp4", names)
            manifest = json.loads(archive.read("EXPORT_MANIFEST.json"))
            self.assertEqual(manifest["version"], "v001")
            for item in manifest["files"]:
                self.assertEqual(hashlib.sha256(archive.read(item["archive_member"])).hexdigest(), item["sha256"])
            recovered = next(item for item in manifest["files"] if item["archive_member"] == "final/final.mp4")
            self.assertEqual(recovered["source_relative"], "final/attempt002/final.mp4")
        self.assertEqual(before, {str(path): sha256(path) for path in self.version.rglob("*") if path.is_file()})

    def test_existing_archive_and_source_project_output_are_blocked_without_overwrite(self):
        output = self.root / "preserved.zip"
        output.write_bytes(b"preserve me")
        completed = load_completed_version(self.version)
        with self.assertRaisesRegex(EvidenceError, "OUTPUT_EXISTS_PRESERVED"):
            create_export(completed, output)
        self.assertEqual(output.read_bytes(), b"preserve me")
        with self.assertRaisesRegex(EvidenceError, "EXPORT_MUST_NOT_WRITE"):
            create_export(completed, self.version / "new.zip")

    def test_failed_qc_stale_approval_changed_final_and_missing_scene_refuse_export(self):
        mutations = [
            ("qc", lambda v, p, r: r["qc"].update(passed=False)),
            ("stale approval", lambda v, p, r: write(v / "approval.json", {"user_approval": True, "plan_hash": "0" * 64})),
            ("changed final", lambda v, p, r: write(Path(r["outputs"]["final"]), b"modified preserved output")),
            ("missing scene", lambda v, p, r: r["scenes"].pop()),
        ]
        for index, (name, mutate) in enumerate(mutations):
            with self.subTest(case=name):
                version, plan, result = fixture(self.root / f"case{index}")
                mutate(version, plan, result)
                write(version / "renders/project_result.json", result)
                with self.assertRaises(EvidenceError):
                    load_completed_version(version)

    def test_final_path_cannot_escape_immutable_version_via_symlink(self):
        outsider = self.root / "outside.mp4"
        outsider.write_bytes(b"outside bytes")
        alias = self.version / "final/attempt002/alias.mp4"
        alias.symlink_to(outsider)
        self.result["outputs"]["final"] = str(alias)
        self.result["final_sha256"]["final"] = sha256(outsider)
        write(self.version / "renders/project_result.json", self.result)
        with self.assertRaisesRegex(EvidenceError, "OUTSIDE_IMMUTABLE"):
            load_completed_version(self.version)

    def test_measured_benchmark_distinguishes_reuse_and_matching_ui_timing(self):
        ui = self.root / "ui.json"
        write(ui, {"project_id": self.plan["project_id"], "version": "v001", "plan_hash": self.plan["plan_hash"],
                   "real_browser": True, "planning_seconds": .9, "failures": []})
        report = aggregate([self.version], [ui])
        self.assertFalse(report["invalid_or_rejected_versions"])
        completed = report["completed_versions"][0]
        self.assertEqual(completed["rendered_scene_count"], 1)
        self.assertEqual(completed["reused_scene_count"], 1)
        self.assertEqual(completed["scenes"][1]["current_render_seconds"], 0)
        self.assertEqual(completed["scenes"][1]["original_native_render_seconds"], 999)
        self.assertEqual(completed["measured_render_seconds"]["total_seconds"], 4.3)
        self.assertEqual(completed["external_timing"][0]["measured_seconds"], {"planning_seconds": .9})
        self.assertFalse(completed["external_timing"][0]["added_to_render_total"])
        self.assertFalse(report["extrapolated_or_estimated_times_included"])

    def test_mismatched_ui_and_unmeasured_benchmark_never_supply_measured_times(self):
        ui = self.root / "other_plan_ui.json"
        write(ui, {"project_id": self.plan["project_id"], "version": "v001", "plan_hash": "f" * 64,
                   "real_browser": True, "planning_seconds": 888})
        write(self.version / "benchmark.json", {"project_id": self.plan["project_id"], "version": "v001",
                                               "plan_hash": self.plan["plan_hash"], "measured": False,
                                               "planning_seconds": 777, "estimated_75s_seconds": 1234})
        completed = aggregate([self.version], [ui])["completed_versions"][0]
        self.assertFalse(completed["external_timing"])
        self.assertIn("UNMEASURED", completed["external_timing_rejected"][0]["reason"])

    def test_incomplete_final_has_only_completed_scene_observations(self):
        (self.version / "renders/project_result.json").unlink()
        report = aggregate([self.version])
        self.assertFalse(report["completed_versions"])
        self.assertEqual(len(report["incomplete_versions"]), 1)
        observations = report["completed_scene_observations_for_incomplete_videos"][0]
        self.assertFalse(observations["video_completed"])
        self.assertEqual(len(observations["scenes"]), 2)

    def test_split_and_hash_verification_preserve_original_and_refuse_existing_parts(self):
        output = self.root / "export.zip"
        create_export(load_completed_version(self.version), output)
        original = sha256(output)
        split = split_zip(output, part_bytes=1024)
        verified = verify_parts(split["manifest"])
        self.assertTrue(verified["verified"])
        self.assertGreater(verified["parts"], 1)
        self.assertEqual(sha256(output), original)
        with self.assertRaisesRegex(EvidenceError, "OUTPUT_EXISTS_PRESERVED"):
            split_zip(output, part_bytes=1024)
        self.assertEqual(sha256(output), original)

    def test_corrupt_part_and_path_traversal_fail_without_touching_original(self):
        output = self.root / "export.zip"
        create_export(load_completed_version(self.version), output)
        original = sha256(output)
        report = split_zip(output, part_bytes=1024)
        manifest = Path(report["manifest"])
        first = manifest.parent / report["parts"][0]["name"]
        data = bytearray(first.read_bytes())
        data[0] ^= 1
        first.write_bytes(data)
        with self.assertRaisesRegex(EvidenceError, "PART_HASH_MISMATCH"):
            verify_parts(manifest)
        self.assertEqual(sha256(output), original)
        document = json.loads(manifest.read_text())
        document["parts"][0]["name"] = "../export.zip"
        write(manifest, document)
        with self.assertRaisesRegex(EvidenceError, "INVALID_OR_DUPLICATE_PART_NAME"):
            verify_parts(manifest)

    def test_github_file_size_boundaries_and_split_cap_are_exact(self):
        self.assertTrue(github_size_report(100 * MIB)["github_normal_git_size_eligible"])
        self.assertFalse(github_size_report(100 * MIB + 1)["github_normal_git_size_eligible"])
        self.assertTrue(github_size_report(25 * MIB)["github_browser_upload_size_eligible"])
        self.assertFalse(github_size_report(25 * MIB + 1)["github_browser_upload_size_eligible"])
        output = self.root / "export.zip"
        create_export(load_completed_version(self.version), output)
        for size in (0, 90 * MIB + 1, True):
            with self.subTest(size=size), self.assertRaises(EvidenceError):
                split_zip(output, size)


if __name__ == "__main__":
    unittest.main()
