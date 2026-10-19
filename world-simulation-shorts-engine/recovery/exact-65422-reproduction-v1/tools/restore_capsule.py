#!/usr/bin/env python3
"""Restore the unchanged 65422 source in a separate, non-overwriting capsule.

The original rendering report supplies the 73 bound files. Operational files
that report did not bind are resolved from the same immutable source commit.
No Git worktree, old output directory, source, renderer, or cache is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

SOURCE_COMMIT = "2c097df2d02432a3f9ae4dae5d714dbc9eacd434"
REPORT_COMMIT = "45af879d7417abba58e9ebd59d8e6630a785ac28"
REPORT_PATH = "world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/evidence/proof/REPORT.json"
REPORT_SHA256 = "550c1d7db502b91dc94548284ddfb10ff27f8e52cdf7efac7e7df68bfa768656"
ENGINE = "world-simulation-shorts-engine/"
IMPORT = re.compile(r"(?:from\s*|import\s*(?:\(\s*)?)[\"']([^\"']+)[\"']")
EXTRA = [
    ENGINE + "recovery/planner-scene-json-v1/planner_runtime.mjs",
    ENGINE + "recovery/v5/serve.py",
    ENGINE + "recovery/v5/index.html",
    ENGINE + "recovery/v5/harness.mjs",
    "cinematic-world-map/package.json",
    "cinematic-world-map/assets/v3/earth/earth-day-8k.jpg",
    "cinematic-world-map/assets/gis/earth-topology.png",
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.PIPE)


def safe_relative(value: str) -> str:
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in ("", ".", "..") for x in p.parts):
        raise ValueError("UNSAFE_CAPSULE_PATH " + value)
    return p.as_posix()


def exact_bytes(repo: Path, relative: str) -> tuple[bytes, str, str]:
    """Use a matching existing file before asking Git for a missing blob."""
    expected = git(repo, "rev-parse", SOURCE_COMMIT + ":" + relative).decode().strip()
    source = repo / relative
    if source.is_file() and not source.is_symlink():
        data = source.read_bytes()
        if blob_sha(data) == expected:
            return data, expected, "EXISTING_CHECKOUT_EQUALS_IMMUTABLE_GIT_BLOB"
    data = git(repo, "show", SOURCE_COMMIT + ":" + relative)
    if blob_sha(data) != expected:
        raise ValueError("IMMUTABLE_SOURCE_BLOB_MISMATCH " + relative)
    return data, expected, "IMMUTABLE_GIT_BLOB"


def put_nonoverwriting(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise ValueError("CAPSULE_FILE_SYMLINK_FORBIDDEN " + str(path))
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError("CAPSULE_EXISTING_FILE_DIFFERS " + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(data)


def imports(relative: str, data: bytes) -> list[str]:
    if not relative.endswith((".mjs", ".js")):
        return []
    result = []
    for spec in IMPORT.findall(data.decode("utf-8")):
        if spec.startswith("."):
            normalized = os.path.normpath(str(PurePosixPath(relative).parent / spec))
            result.append(safe_relative(normalized))
        elif spec.startswith("/modules/"):
            result.append(ENGINE + "web/map_infographic_v1/" + spec[len("/modules/"):])
        elif spec == "/three.js":
            result.append(ENGINE + "web/vendor/three/0.170.0/three.module.js")
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    p.add_argument("--capsule", type=Path, default=Path("/workspace/exact-65422-capsule-20261020"))
    p.add_argument("--report", type=Path, default=Path("/workspace/exact-65422-original-report-20261020.json"))
    p.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "reports/SOURCE_CAPSULE_MANIFEST.json")
    p.add_argument("--defer-unavailable-probes", action="store_true", help="Record only missing static admission PNGs as pending; runtime never reads them")
    args = p.parse_args()
    repo, capsule = args.repo.resolve(), args.capsule.resolve()
    if capsule == repo or repo in capsule.parents or (capsule / ".git").exists():
        raise ValueError("INDEPENDENT_NON_GIT_CAPSULE_REQUIRED")
    if not args.report.exists():
        put_nonoverwriting(args.report, git(repo, "show", REPORT_COMMIT + ":" + REPORT_PATH))
    report_data = args.report.read_bytes()
    if sha(report_data) != REPORT_SHA256:
        raise ValueError("ORIGINAL_REPORT_HASH_MISMATCH")
    report = json.loads(report_data)
    expected = {safe_relative(row["path"]): row for row in report["sourceBindings"]}
    queue, done, missing = list(expected) + EXTRA, {}, []
    while queue:
        relative = safe_relative(queue.pop(0))
        if relative in done or relative in missing:
            continue
        try:
            data, blob, origin = exact_bytes(repo, relative)
        except subprocess.CalledProcessError:
            if args.defer_unavailable_probes and "/evidence/native_probe/" in relative:
                missing.append(relative)
                continue
            raise
        if relative in expected:
            old = expected[relative]
            if sha(data) != old["sha256"] or len(data) != old["bytes"]:
                raise ValueError("ORIGINAL_REPORT_SOURCE_BINDING_MISMATCH " + relative)
        put_nonoverwriting(capsule / relative, data)
        done[relative] = {
            "path": relative, "bytes": len(data), "sha256": sha(data),
            "sourceCommit": SOURCE_COMMIT, "gitBlob": blob, "restoredFrom": origin,
            "originalReportBound": relative in expected,
        }
        queue.extend(imports(relative, data))
    dependency_root = subprocess.check_output(
        ["node", "-p", "require.resolve('playwright/package.json')"], cwd=repo, text=True
    ).strip()
    dependency_root = Path(dependency_root).parent.parent.resolve()
    link = capsule / "cinematic-world-map/node_modules"
    if link.is_symlink():
        if link.resolve() != dependency_root:
            raise ValueError("CAPSULE_DEPENDENCY_LINK_CONFLICT")
    elif link.exists():
        raise ValueError("CAPSULE_DEPENDENCY_PATH_CONFLICT")
    else:
        link.symlink_to(dependency_root, target_is_directory=True)
    manifest = {
        "schema": "EXACT_65422_SOURCE_CAPSULE_V1",
        "status": "READY" if not missing else "RUNTIME_READY_STATIC_ADMISSION_PROBES_PENDING",
        "sourceCommit": SOURCE_COMMIT,
        "originalReportCommit": REPORT_COMMIT,
        "originalReportSHA256": REPORT_SHA256,
        "originalReportBindingCount": len(expected),
        "originalReportBindingsRestored": sum(x["originalReportBound"] for x in done.values()),
        "additionalOperationalClosureCount": sum(not x["originalReportBound"] for x in done.values()),
        "totalFiles": len(done), "totalBytes": sum(x["bytes"] for x in done.values()),
        "capsuleRoot": str(capsule), "gitWorktreeCreated": False,
        "existingSourceChanged": False, "existingOutputOrCacheReused": False,
        "runtimeModule": ENGINE + "recovery/moving-frontier-glow-fix-v1/reference_runtime.mjs",
        "runtimeExport": "openQualityRuntime",
        "runtimeOptions": {"mode": "VISUAL_REFERENCE_STUDY"},
        "dependencyLink": {"path": "cinematic-world-map/node_modules", "target": str(dependency_root), "kind": "LOCAL_EXISTING_DEPENDENCIES_NOT_SERVED_BY_LOOPBACK_SERVER"},
        "pendingStaticProbeFiles": missing,
        "files": list(done.values()),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: manifest[k] for k in ("status", "capsuleRoot", "totalFiles", "originalReportBindingsRestored", "additionalOperationalClosureCount")}))


if __name__ == "__main__":
    main()
