#!/usr/bin/env python3
"""Aggregate measured completed evidence without rendering or extrapolation.

Incomplete videos may contribute explicitly scoped completed-Scene observations,
never completed-video benchmarks. UI planning time remains separate from rendering.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from deliverable_evidence import (EvidenceError, exclusive_json, finite_seconds,
                                 inside_file, load_completed_version, read_json,
                                 sha256, verified_file)

TIMING_KEYS = ("scene_render_seconds", "audio_preparation_seconds",
               "assembly_audio_mux_subtitles_seconds", "qc_seconds", "total_seconds")
EXTERNAL_TIMING_KEYS = ("planning_seconds", "story_generation_seconds", "scene_plan_generation_seconds",
                        "ui_seconds", "ui_request_seconds")


def version_directories(paths: list[Path]) -> list[Path]:
    found = set()
    for path in paths:
        path = path.resolve()
        if path.name.startswith("v") and path.parent.name == "versions" and path.is_dir():
            found.add(path)
        for pattern in ("versions/v*/scene_plan.json", "project_*/versions/v*/scene_plan.json"):
            found.update(item.parent for item in path.glob(pattern))
    return sorted(found)


def scene_observations(version: Path, plan: dict, entries: list[dict]) -> list[dict]:
    observations = []
    durations = {scene["scene_id"]: scene.get("duration") for scene in plan.get("scenes", [])}
    for entry in entries:
        if entry.get("complete") is not True:
            continue
        sid = entry.get("scene_id")
        if sid not in durations:
            raise EvidenceError("UNKNOWN_SCENE_IN_BENCHMARK: " + str(sid))
        movie = verified_file(version, entry.get("movie", ""), entry.get("video_sha256"))
        verified_file(version, entry.get("audit", ""), entry.get("audit_sha256"))
        quality = entry.get("quality", {})
        reused = entry.get("reused", False) is True
        native = entry.get("native_manifest", {})
        observations.append({"scene_id": sid, "duration_seconds": durations[sid],
                             "quality": quality.get("quality") if isinstance(quality, dict) else quality,
                             "internal_width": quality.get("internal_width") if isinstance(quality, dict) else None,
                             "temporal_samples": quality.get("temporal_samples", 1) if isinstance(quality, dict) else None,
                             "reused": reused, "reuse_reason": entry.get("reuse_reason"),
                             "current_render_seconds": (0. if reused else finite_seconds(entry.get("current_render_seconds"))),
                             "original_native_render_seconds": finite_seconds(native.get("elapsedSeconds")),
                             "original_elapsed_seconds": finite_seconds(entry.get("elapsed_seconds")),
                             "original_timing_scope": "Original render only; cached historical time is never counted as current rendering",
                             "resolved_movie": str(movie), "video_sha256": entry["video_sha256"],
                             "renderer_version": entry.get("renderer_version")})
    return observations


def attach_external_timing(version: Path, plan: dict, evidence_paths: list[Path]) -> tuple[list, list]:
    timing, rejected = [], []
    for path in [*evidence_paths, *([version / "benchmark.json"] if (version / "benchmark.json").is_file() else [])]:
        try:
            document = read_json(path)
            if (document.get("project_id") != plan.get("project_id") or
                    document.get("version") != plan.get("version") or
                    document.get("plan_hash") != plan.get("plan_hash")):
                continue  # Other projects/versions cannot supply this plan's timing.
            is_ui = document.get("real_browser") is True
            if document.get("synthetic") is True or document.get("measured") is False:
                raise EvidenceError("UNMEASURED_OR_SYNTHETIC_TIMING")
            if not is_ui and document.get("measured") is not True:
                raise EvidenceError("EXPLICIT_MEASURED_FLAG_REQUIRED")
            if document.get("failures") or document.get("passed") is False:
                raise EvidenceError("FAILED_UI_OR_BENCHMARK_EVIDENCE")
            values = {key: finite_seconds(document.get(key)) for key in EXTERNAL_TIMING_KEYS}
            values = {key: value for key, value in values.items() if value is not None}
            if not values:
                raise EvidenceError("NO_MEASURED_PLANNING_OR_UI_TIMING")
            timing.append({"source": str(path.resolve()), "source_sha256": sha256(path),
                           "measured_seconds": values,
                           "scope": ("Browser plan request wall time, including HTTP/UI round trip; not isolated Story generation"
                                     if is_ui else document.get("scope", "Explicit measured timing supplied by benchmark.json")),
                           "added_to_render_total": False})
        except EvidenceError as error:
            rejected.append({"source": str(path), "reason": str(error)})
    return timing, rejected


def aggregate(paths: list[Path], ui_evidence: list[Path] | None = None) -> dict:
    completed, incomplete, invalid, partial_scenes = [], [], [], []
    for version in version_directories(paths):
        try:
            plan = read_json(version / "scene_plan.json")
            result_file = version / "renders/project_result.json"
            if not result_file.is_file():
                incomplete.append({"version_dir": str(version), "reason": "No completed final result; no video benchmark recorded"})
                scene_file = version / "renders/scene_results.json"
                if scene_file.is_file():
                    manifest = read_json(scene_file)
                    if manifest.get("plan_hash") != plan.get("plan_hash"):
                        raise EvidenceError("PARTIAL_MANIFEST_PLAN_HASH_MISMATCH")
                    observations = scene_observations(version, plan, manifest.get("scenes", []))
                    if observations:
                        partial_scenes.append({"project_id": plan.get("project_id"), "version": plan.get("version"),
                                               "plan_hash": plan.get("plan_hash"), "video_completed": False,
                                               "scope": "Completed Scene observations only; final video/QC has not completed",
                                               "scenes": observations})
                continue
            data = load_completed_version(version)
            result = data["result"]
            metrics = result.get("metrics", {})
            if metrics.get("measured") is not True:
                raise EvidenceError("RESULT_MEASURED_METRICS_REQUIRED")
            observations = scene_observations(version, plan, result["scenes"])
            rendered = sum(not entry["reused"] for entry in observations)
            reused = len(observations) - rendered
            if (metrics.get("scene_count") != len(observations) or
                    metrics.get("rendered_scene_count") != rendered or metrics.get("cached_scene_count") != reused):
                raise EvidenceError("MEASURED_SCENE_COUNTS_DISAGREE")
            timings = {key: finite_seconds(metrics.get(key)) for key in TIMING_KEYS}
            if any(value is None for value in timings.values()):
                raise EvidenceError("FINITE_MEASURED_RENDER_TIMES_REQUIRED")
            extra, rejected = attach_external_timing(version, plan, ui_evidence or [])
            completed.append({"project_id": plan["project_id"], "version": plan["version"],
                              "plan_hash": plan["plan_hash"], "duration_seconds": plan.get("duration"),
                              "requested_quality": plan.get("options", {}).get("quality", plan.get("request", {}).get("quality")),
                              "actual_scene_qualities": sorted({str(entry["quality"]) for entry in observations}),
                              "backend": metrics.get("backend"), "automatic_qc_passed": True,
                              "publication_quality": result.get("publication_quality", False),
                              "aesthetic_review_required": result.get("aesthetic_review_required", True),
                              "rendered_scene_count": rendered, "reused_scene_count": reused,
                              "audio_reused": metrics.get("audio_reused"), "measured_render_seconds": timings,
                              "timing_scope": metrics.get("benchmark_scope"), "external_timing": extra,
                              "external_timing_rejected": rejected, "scenes": observations,
                              "result_source": str(result_file), "result_source_sha256": sha256(result_file),
                              "final_sha256": result["final_sha256"]})
        except (EvidenceError, KeyError, OSError, TypeError) as error:
            invalid.append({"version_dir": str(version), "reason": str(error)})
    return {"schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "read_only": True, "extrapolated_or_estimated_times_included": False,
            "scope": "Observed completed execution metrics only; no projection from 20s to 75s, no cached historical render time added, UI/plan timing kept separate",
            "completed_versions": completed, "completed_scene_observations_for_incomplete_videos": partial_scenes,
            "incomplete_versions": incomplete, "invalid_or_rejected_versions": invalid}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Project root, project directory, or immutable version")
    parser.add_argument("--ui-evidence", action="append", default=[], type=Path)
    parser.add_argument("--output", type=Path, help="Optional new report; fails if it already exists")
    args = parser.parse_args()
    try:
        result = aggregate(args.paths, args.ui_evidence)
        if args.output:
            output = args.output.absolute()
            for version in version_directories(args.paths):
                if output.resolve().is_relative_to(version.parent.parent):
                    raise EvidenceError("BENCHMARK_REPORT_MUST_NOT_WRITE_IN_SOURCE_PROJECT")
            exclusive_json(output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (EvidenceError, OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
