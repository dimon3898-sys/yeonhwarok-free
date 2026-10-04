"""Read-only evidence validation and exclusive archive writing (stdlib only).

No renderer, codec, server, or paid service is started by this module.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import zipfile

MIB = 1024 * 1024
GITHUB_NORMAL_GIT_LIMIT = 100 * MIB
MAX_SPLIT_PART = 90 * MIB
CHUNK = MIB


class EvidenceError(RuntimeError):
    pass


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise EvidenceError(f"INVALID_OR_MISSING_JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise EvidenceError(f"JSON_OBJECT_REQUIRED: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode()


def plan_digest(plan: dict) -> str:
    ignored = {"plan_hash", "gate", "retention_gate", "approval", "validation", "created_at"}
    return hashlib.sha256(canonical({key: value for key, value in plan.items()
                                    if key not in ignored})).hexdigest()


def inside_file(version: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = version / path
    path = path.resolve()
    if not path.is_relative_to(version) or not path.is_file():
        raise EvidenceError(f"MISSING_OR_OUTSIDE_IMMUTABLE_VERSION: {value}")
    return path


def verified_file(version: Path, value: str | Path, expected: str) -> Path:
    path = inside_file(version, value)
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise EvidenceError(f"RECORDED_SHA256_REQUIRED: {path}")
    if sha256(path) != expected:
        raise EvidenceError(f"PRESERVED_FILE_HASH_MISMATCH: {path}")
    return path


def load_completed_version(value: str | Path) -> dict:
    """Require exact approval, completed automatic QC, and recorded output hashes."""
    version = Path(value).resolve()
    if not re.fullmatch(r"v\d{3,}", version.name) or version.parent.name != "versions":
        raise EvidenceError("IMMUTABLE_VERSION_PATH_REQUIRED: projects/PROJECT/versions/vNNN")
    plan_path = inside_file(version, "scene_plan.json")
    plan = read_json(plan_path)
    digest = plan_digest(plan)
    if plan.get("version") != version.name or plan.get("project_id") != version.parent.parent.name:
        raise EvidenceError("PLAN_PROJECT_VERSION_MISMATCH")
    if plan.get("plan_hash") != digest:
        raise EvidenceError("PLAN_CONTENT_HASH_MISMATCH")
    approval = read_json(inside_file(version, "approval.json"))
    result_path = inside_file(version, "renders/project_result.json")
    result = read_json(result_path)
    checkpoint = read_json(inside_file(version, "renders/checkpoint.json"))
    if approval.get("user_approval") is not True or approval.get("plan_hash") != digest:
        raise EvidenceError("EXACT_PLAN_APPROVAL_REQUIRED")
    if result.get("plan_hash") != digest or checkpoint.get("plan_hash") != digest:
        raise EvidenceError("COMPLETED_RESULT_PLAN_HASH_MISMATCH")
    if (result.get("qc", {}).get("passed") is not True or
            checkpoint.get("complete") is not True or checkpoint.get("qc_passed") is not True):
        raise EvidenceError("SUCCESSFUL_FINAL_AUTOMATIC_QC_REQUIRED")
    outputs = result.get("outputs", {})
    final_paths = {key: verified_file(version, outputs.get(key, ""),
                                     result.get("final_sha256", {}).get(key))
                   for key in ("final", "muted")}
    qc_md = inside_file(version, outputs.get("qc_report", ""))
    qc_json = inside_file(version, qc_md.with_suffix(".json"))
    actual_qc = read_json(qc_json)
    if actual_qc.get("passed") is not True or actual_qc != result["qc"]:
        raise EvidenceError("QC_RESULT_AND_RESOLVED_REPORT_DISAGREE")
    if inside_file(version, actual_qc.get("file", "")) != final_paths["final"]:
        raise EvidenceError("QC_FINAL_PATH_MISMATCH")
    scenes = result.get("scenes", [])
    plan_ids = [scene["scene_id"] for scene in plan.get("scenes", [])]
    if not plan_ids or [entry.get("scene_id") for entry in scenes] != plan_ids:
        raise EvidenceError("COMPLETE_ORDERED_SCENE_RESULTS_REQUIRED")
    scene_results = read_json(inside_file(version, "renders/scene_results.json"))
    if scene_results.get("plan_hash") != digest or scene_results.get("scenes") != scenes:
        raise EvidenceError("SCENE_RESULT_MANIFEST_MISMATCH")
    if checkpoint.get("completed_scenes") != len(scenes) or checkpoint.get("total_scenes") != len(scenes):
        raise EvidenceError("COMPLETED_CHECKPOINT_COUNT_MISMATCH")
    for entry in scenes:
        if entry.get("complete") is not True:
            raise EvidenceError("INCOMPLETE_SCENE: " + str(entry.get("scene_id")))
        verified_file(version, entry.get("movie", ""), entry.get("video_sha256"))
        verified_file(version, entry.get("audit", ""), entry.get("audit_sha256"))
    return {"version_dir": version, "plan": plan, "result": result,
            "plan_hash": digest, "final_paths": final_paths,
            "qc_md": qc_md, "qc_json": qc_json, "result_path": result_path}


def finite_seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def export_inventory(completed: dict) -> list[dict]:
    """Select current successful paths; never traverse cache/partial/runtime/assets."""
    version = completed["version_dir"]
    result = completed["result"]
    selected: dict[str, Path] = {}

    def add(value, archive=None, required=True):
        try:
            source = inside_file(version, value)
        except EvidenceError:
            if required:
                raise
            return
        name = archive or source.relative_to(version).as_posix()
        if name in selected and selected[name] != source:
            raise EvidenceError(f"ARCHIVE_MEMBER_CONFLICT: {name}")
        selected[name] = source

    for name in ("scene_plan.json", "scene_plan_readable.md", "script.txt", "approval.json",
                 "story/story_plan.json", "assets/source_report.json",
                 "renders/project_result.json", "renders/scene_results.json", "renders/checkpoint.json"):
        add(name)
    add(result["outputs"]["source_report"], "assets/source_report.md")
    add(completed["final_paths"]["final"], "final/final.mp4")
    add(completed["final_paths"]["muted"], "final/final_muted.mp4")
    add(completed["qc_md"], "qc/qc_report.md")
    add(completed["qc_json"], "qc/qc_report.json")
    add(result["outputs"]["contact_sheet"], "qc/contact_sheet.png")
    for scene in completed["plan"]["scenes"]:
        add("scene_json/" + scene["scene_id"] + ".json")
    for entry in result["scenes"]:
        movie = inside_file(version, entry["movie"])
        add(movie)
        add(entry["audit"])
        for suffix in (".manifest.json", ".checkpoint.json", ".reuse.json",
                       ".clip_annotations.ass", ".clip_annotation_proof.json", ".clip_ffmpeg.log"):
            add(movie.with_suffix(suffix), required=False)
        if not movie.with_suffix(".manifest.json").is_file() and not entry.get("native_manifest"):
            raise EvidenceError("SCENE_NATIVE_OR_REUSE_MANIFEST_REQUIRED: " + entry["scene_id"])
    for source in sorted((version / "audio").glob("*")):
        if source.is_file() and source.suffix.lower() in {".wav", ".mp3", ".json", ".ass", ".srt"}:
            add(source)
    add("benchmark.json", required=False)
    return [{"archive_member": name, "source": str(source),
             "source_relative": source.relative_to(version).as_posix(),
             "bytes": source.stat().st_size, "sha256": sha256(source)}
            for name, source in sorted(selected.items())]


def exclusive_json(path: Path, value) -> None:
    if path.exists():
        raise EvidenceError(f"OUTPUT_EXISTS_PRESERVED: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def create_export(completed: dict, output: str | Path) -> dict:
    output = Path(output).absolute()
    version = completed["version_dir"]
    if output.resolve().is_relative_to(version.parent.parent):
        raise EvidenceError("EXPORT_MUST_NOT_WRITE_IN_SOURCE_PROJECT")
    if output.exists():
        raise EvidenceError(f"OUTPUT_EXISTS_PRESERVED: {output}")
    inventory = export_inventory(completed)
    document = {"schema_version": 1, "project_id": completed["plan"]["project_id"],
                "version": completed["plan"]["version"], "plan_hash": completed["plan_hash"],
                "source_version_directory": str(version), "automatic_qc_passed": True,
                "aesthetic_review_required": completed["result"].get("aesthetic_review_required", True),
                "publication_quality": completed["result"].get("publication_quality", False),
                "external_shared_assets_included": False,
                "asset_reproduction": "Use source_report and native source hashes with the preserved V3 shared asset library; large fonts, textures, runtime, cache, failed/partial outputs are excluded.",
                "files": inventory}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Failure leaves the newly created incomplete archive available for diagnosis.
    # Never delete or overwrite either an existing source file or archive.
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for item in inventory:
            digest = hashlib.sha256()
            size = 0
            with Path(item["source"]).open("rb") as source, archive.open(item["archive_member"], "w", force_zip64=True) as target:
                for block in iter(lambda: source.read(CHUNK), b""):
                    target.write(block)
                    digest.update(block)
                    size += len(block)
            if digest.hexdigest() != item["sha256"] or size != item["bytes"]:
                raise EvidenceError("SOURCE_CHANGED_DURING_EXPORT: " + item["source"])
        archive.writestr("EXPORT_MANIFEST.json", json.dumps(document, ensure_ascii=False, indent=2))
    return {"zip": str(output), "bytes": output.stat().st_size, "sha256": sha256(output),
            "file_count": len(inventory), "plan_hash": completed["plan_hash"],
            "project_id": completed["plan"]["project_id"], "version": completed["plan"]["version"],
            **github_size_report(output.stat().st_size),
            "original_zip_preserved": True, "automatic_qc_passed": True,
            "aesthetic_review_required": document["aesthetic_review_required"]}


def github_size_report(size: int) -> dict:
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise EvidenceError("NONNEGATIVE_INTEGER_FILE_SIZE_REQUIRED")
    return {"github_normal_git_warning_bytes": 50 * MIB,
            "github_normal_git_limit_bytes": GITHUB_NORMAL_GIT_LIMIT,
            "github_browser_upload_limit_bytes": 25 * MIB,
            "github_normal_git_size_eligible": size <= GITHUB_NORMAL_GIT_LIMIT,
            "github_browser_upload_size_eligible": size <= 25 * MIB,
            "github_limit_source": "docs/evidence/github_file_limits_r01.json",
            "git_lfs_account_quota_verified": False}


def split_zip(source: str | Path, part_bytes: int = MAX_SPLIT_PART) -> dict:
    source = Path(source).resolve()
    if not source.is_file() or not zipfile.is_zipfile(source):
        raise EvidenceError("EXISTING_ZIP_REQUIRED")
    if isinstance(part_bytes, bool) or not isinstance(part_bytes, int) or not 1 <= part_bytes <= MAX_SPLIT_PART:
        raise EvidenceError("PART_SIZE_MUST_BE_POSITIVE_AND_AT_MOST_90_MIB")
    count = max(1, math.ceil(source.stat().st_size / part_bytes))
    paths = [source.with_name(source.name + f".part{index:03}") for index in range(1, count + 1)]
    manifest = source.with_name(source.name + ".parts.json")
    for path in [*paths, manifest]:
        if path.exists():
            raise EvidenceError(f"OUTPUT_EXISTS_PRESERVED: {path}")
    original_hash = sha256(source)
    complete_hash = hashlib.sha256()
    entries = []
    with source.open("rb") as stream:
        for path in paths:
            size, digest = 0, hashlib.sha256()
            with path.open("xb") as target:
                while size < part_bytes:
                    block = stream.read(min(CHUNK, part_bytes - size))
                    if not block:
                        break
                    target.write(block)
                    size += len(block)
                    digest.update(block)
                    complete_hash.update(block)
            entries.append({"name": path.name, "bytes": size, "sha256": digest.hexdigest()})
        if stream.read(1) or complete_hash.hexdigest() != original_hash:
            raise EvidenceError("ZIP_CHANGED_DURING_SPLIT: original and newly written parts preserved")
    result = {"schema_version": 1, "original_name": source.name, "original_bytes": source.stat().st_size,
              "original_sha256": original_hash, "max_part_bytes": part_bytes,
              "parts": entries, "original_zip_preserved": True}
    exclusive_json(manifest, result)
    verify_parts(manifest)
    return {"manifest": str(manifest), **result}


def verify_parts(manifest: str | Path) -> dict:
    manifest = Path(manifest).resolve()
    document = read_json(manifest)
    digest = hashlib.sha256()
    total, names = 0, set()
    parts = document.get("parts", [])
    if not parts or not 1 <= document.get("max_part_bytes", 0) <= MAX_SPLIT_PART:
        raise EvidenceError("INVALID_PARTS_MANIFEST")
    for index, item in enumerate(parts):
        name = item.get("name", "")
        if not name or Path(name).name != name or name in names:
            raise EvidenceError("INVALID_OR_DUPLICATE_PART_NAME")
        names.add(name)
        path = (manifest.parent / name).resolve()
        if not path.is_relative_to(manifest.parent) or not path.is_file():
            raise EvidenceError("PART_MISSING_OR_OUTSIDE_MANIFEST_DIRECTORY")
        size = path.stat().st_size
        if (size != item.get("bytes") or size > document["max_part_bytes"] or
                size <= 0 or (index < len(parts) - 1 and size != document["max_part_bytes"])):
            raise EvidenceError("PART_SIZE_MISMATCH: " + name)
        part_hash = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(CHUNK), b""):
                digest.update(block)
                part_hash.update(block)
        if part_hash.hexdigest() != item.get("sha256"):
            raise EvidenceError("PART_HASH_MISMATCH: " + name)
        total += size
    if total != document.get("original_bytes") or digest.hexdigest() != document.get("original_sha256"):
        raise EvidenceError("REASSEMBLED_ZIP_HASH_MISMATCH")
    return {"verified": True, "parts": len(parts), "bytes": total,
            "reassembled_sha256": digest.hexdigest(), "original_zip_modified": False}
