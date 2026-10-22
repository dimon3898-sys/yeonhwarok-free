"""Verify frozen sources and G1 without rendering; inspect the pinned fixture ZIP.

Only this namespace's PROTECTION.json is written. Existing audit verifiers are
loaded in memory; their original writers, renderers and encoders are never run.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
BASE = "e6ff697348a8e63c9308d7b4546682cbc6620c96"
G1_ARTIFACT_COMMIT = "b97f9aaa6d58d01566c17555ae4abbfd032c6386"
ORIGINAL_REPORT_SHA256 = "550c1d7db502b91dc94548284ddfb10ff27f8e52cdf7efac7e7df68bfa768656"
TOKEN_PATTERNS = {
    "PRIVATE_KEY_BLOCK": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "GITHUB_TOKEN": rb"gh[pousr]_[A-Za-z0-9]{30,}",
    "GITHUB_FINE_GRAINED_TOKEN": rb"github_pat_[A-Za-z0-9_]{40,}",
    "AWS_ACCESS_KEY_ID": rb"\bAKIA[A-Z0-9]{16}\b",
}
SOURCE_ENTRY = re.compile(
    r"(?:INDEX\.json|demo/(?:BUNDLE\.json|DOMAIN\.geojson|NATIVE\.json|RECIPE\.json)"
    r"|demo/frames/[0-9]{3}_(?:DOMAIN\.geojson|RECEIPTS\.json|RECIPE\.json|STATE\.json|ZONE_A\.geojson|ZONE_B\.geojson)"
    r"|history/(?:BUNDLE\.json|PDF008_POSITION_PATHS\.json))\Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(file):
    if not file.is_file() or file.is_symlink():
        raise ValueError("PROTECTION_REGULAR_FILE_REQUIRED")
    return file.read_bytes()


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("PROTECTION_DUPLICATE_JSON_KEY")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("PROTECTION_NONFINITE_JSON")))


def source_fixture_check(findings):
    archive = HERE / "fixtures/SOURCE_BUNDLE.zip"
    pin = strict_json(regular(HERE / "fixtures/SOURCE_CATALOG_PIN.json"))
    data = regular(archive)
    if digest(data) != pin["archiveSHA256"] or len(data) != pin["bytes"]:
        raise ValueError("PROTECTION_SOURCE_ARCHIVE_PIN_MISMATCH")
    checked, total, seen = 0, 0, set()
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if len(entries) != pin["files"] + 1 or len({i.filename for i in entries}) != len(entries):
            raise ValueError("PROTECTION_SOURCE_ARCHIVE_ENTRIES_INVALID")
        if source.testzip() is not None:
            raise ValueError("PROTECTION_SOURCE_ARCHIVE_CRC_FAILURE")
        manifest = strict_json(source.read("SOURCE_MANIFEST.json"))
        if len(manifest) != pin["files"] or len(manifest) > 2000:
            raise ValueError("PROTECTION_SOURCE_MANIFEST_COUNT")
        if {i.filename for i in entries} != {r["path"] for r in manifest} | {"SOURCE_MANIFEST.json"}:
            raise ValueError("PROTECTION_SOURCE_ARCHIVE_UNLISTED_ENTRY")
        for row in manifest:
            name = row["path"]
            if name in seen or not SOURCE_ENTRY.fullmatch(name):
                raise ValueError("PROTECTION_SOURCE_ENTRY_NOT_ALLOWLISTED")
            seen.add(name)
            entry = source.getinfo(name)
            if stat.S_ISLNK(entry.external_attr >> 16) or entry.is_dir():
                raise ValueError("PROTECTION_SOURCE_ENTRY_NOT_REGULAR")
            if type(row["bytes"]) is not int or not 0 <= row["bytes"] <= 16 * 1024**2:
                raise ValueError("PROTECTION_SOURCE_ENTRY_CAPACITY")
            raw = source.read(name)
            total += len(raw)
            if total > 64 * 1024**2 or len(raw) != row["bytes"] or digest(raw) != row["sha256"]:
                raise ValueError("PROTECTION_SOURCE_ENTRY_HASH_MISMATCH")
            strict_json(raw)
            for code, pattern in TOKEN_PATTERNS.items():
                if re.search(pattern, raw):
                    findings.append({"path": "fixtures/SOURCE_BUNDLE.zip!" + name, "pattern": code})
            checked += 1
        if digest(source.read("INDEX.json")) != pin["indexSHA256"]:
            raise ValueError("PROTECTION_SOURCE_INDEX_PIN_MISMATCH")
    # Exercise the real bounded restore entrypoint in our own temporary private
    # directory. TemporaryDirectory removes only this audit's new scratch files.
    module_path = HERE / "tools/source_fixture_store.py"
    spec = importlib.util.spec_from_file_location("_protection_source_fixture_store", module_path)
    module = importlib.util.module_from_spec(spec)
    previous_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="world-engine-source-restore-check-", dir="/workspace") as temporary:
            destination = Path(temporary) / "payload"
            result, actual_pin = module.restore(destination)
            if result != destination or actual_pin != pin["indexSHA256"]:
                raise ValueError("PROTECTION_SOURCE_RESTORE_IDENTITY")
            for row in manifest:
                if digest(regular(destination / row["path"])) != row["sha256"]:
                    raise ValueError("PROTECTION_SOURCE_RESTORE_BYTES_MISMATCH")
    finally:
        sys.dont_write_bytecode = previous_bytecode
    return {"status": "PASS", "path": "fixtures/SOURCE_BUNDLE.zip", "archiveSHA256": pin["archiveSHA256"],
        "archiveBytes": len(data), "payloadFilesChecked": checked, "payloadUncompressedBytes": total,
        "allPayloadIsAllowlistedJsonOrGeoJson": True, "extraFiles": 0,
        "indexSHA256": pin["indexSHA256"], "actualSafeRestoreAndReadback": "PASS",
        "sourceFixtureStoreSHA256": digest(regular(module_path)), "requiredExternalTempFiles": 0}


def g1_check():
    old = HERE.parent / "studio-integration-gates-v1"
    altered = subprocess.check_output(["git", "diff", "--name-only", BASE, "--", str(old.relative_to(REPO))],
                                     cwd=REPO, text=True).splitlines()
    originals = []
    for name in ("reports/G1_CAPTURE_EVIDENCE.json", "reports/GATE_RESULTS.json", "reports/STUDIO_HTTP_EXECUTION.json",
                 "public-review/WORLD_ENGINE_STUDIO_G1_REFERENCE_5S.mp4"):
        file = old / name
        raw = regular(file)
        fixed = subprocess.check_output(["git", "show", G1_ARTIFACT_COMMIT + ":" + file.relative_to(REPO).as_posix()], cwd=REPO)
        if raw != fixed:
            raise ValueError("PROTECTION_G1_FIXED_COMMIT_BYTES_CHANGED")
        originals.append({"path": name, "bytes": len(raw), "sha256": digest(raw)})
    public_checks = []
    for line in regular(old / "public-review/SHA256SUMS").decode().splitlines():
        expected, name = line.split("  ", 1)
        file = old / "public-review" / name
        if not file.resolve().is_relative_to(old / "public-review") or digest(regular(file)) != expected:
            raise ValueError("PROTECTION_G1_PUBLIC_BYTES_CHANGED")
        public_checks.append({"path": name, "sha256": expected})
    original_file = Path("/workspace/exact-65422-original-report-20261020.json")
    if original_file.is_file() and not original_file.is_symlink():
        original_bytes = regular(original_file)
        original_location = "Verified existing immutable source-report cache"
    else:
        original_path = "world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/evidence/proof/REPORT.json"
        original_bytes = subprocess.check_output(["git", "show", "45af879d7417abba58e9ebd59d8e6630a785ac28:" + original_path], cwd=REPO)
        original_location = "Immutable Git proof commit45af879"
    if digest(original_bytes) != ORIGINAL_REPORT_SHA256:
        raise ValueError("PROTECTION_ORIGINAL_REPORT_IDENTITY_CHANGED")
    original = strict_json(original_bytes)
    capture = strict_json(regular(old / "reports/G1_CAPTURE_EVIDENCE.json"))
    frames, expected = capture["frames"], original["frames"]
    if len(frames) != 150 or len(expected) != 150:
        raise ValueError("PROTECTION_G1_FRAME_COUNT_CHANGED")
    raw_count = png_count = 0
    for frame, (left, right) in enumerate(zip(frames, expected)):
        if left["frame"] != right["frame"] or left["frame"] != frame:
            raise ValueError("PROTECTION_G1_FRAME_ORDER_CHANGED")
        raw_count += left["raw_rgba_sha256"] == right["raw_rgba_sha256"]
        png_count += left["png_sha256"] == right["png_sha256"]
    if raw_count != 150 or png_count != 150 or altered:
        raise ValueError("PROTECTION_G1_RENDER_EVIDENCE_CHANGED")
    return {"status": "PASS", "oldNamespaceTrackedDiff": altered, "artifactCommit": G1_ARTIFACT_COMMIT,
        "fixedCommitArtifacts": originals, "publicFilesChecked": len(public_checks), "publicChecks": public_checks,
        "originalReportSHA256": ORIGINAL_REPORT_SHA256, "originalReportLocation": original_location,
        "rawRGBAFramesEqual": raw_count, "pngFramesEqual": png_count,
        "newRenderPerformed": False, "newEncodePerformed": False,
        "strictEncodedComparison": "REPRODUCTION_NEEDS_REWORK_RETAINED", "userQualityApproval": False}


def check():
    prefix = HERE.relative_to(REPO).as_posix() + "/"
    changed = subprocess.check_output(["git", "diff", "--name-only", BASE], cwd=REPO, text=True).splitlines()
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=REPO, text=True).splitlines()
    outside = [name for name in changed + untracked if not name.startswith(prefix)]
    # Reuse the preserved 307-file /318-entry byte verifier without its writer.
    original = HERE.parent / "astra-event-director-v2/tools/check_preservation.py"
    source = regular(original).decode().replace("allowed = ROOT.relative_to(REPO).as_posix() + '/'", "allowed = " + repr(prefix))
    namespace = {"__file__": str(original), "__name__": "_universal_source_preserved_verifier"}
    exec(compile(source, str(original), "exec"), namespace)
    inherited = namespace["verify"]()
    errors = inherited["parentFileErrors"]
    findings, text_checked = [], 0
    for file in HERE.rglob("*"):
        if not file.is_file() or file.is_symlink() or any(part in {"captures", "__pycache__", ".git"} for part in file.parts):
            continue
        if file.suffix in {".py", ".mjs", ".json", ".geojson", ".md", ".csv", ".txt"}:
            text_checked += 1
            data = regular(file)
            for code, pattern in TOKEN_PATTERNS.items():
                if re.search(pattern, data):
                    findings.append({"path": file.relative_to(HERE).as_posix(), "pattern": code})
    fixture = source_fixture_check(findings)
    g1 = g1_check()
    public = HERE / "public-review"
    publication_errors = []
    if public.exists():
        for file in public.rglob("*"):
            if file.is_file() and (file.is_symlink() or file.name != "SHA256SUMS" and file.suffix.lower() not in {".png", ".mp4"}):
                publication_errors.append(file.relative_to(HERE).as_posix())
    result = {"schema": "UNIVERSAL_SOURCE_PIPELINE_PROTECTION_V2", "status": "PASS" if not outside and not errors and not findings and not publication_errors else "FAIL",
        "baselineCommit": BASE, "changesConfinedToNewNamespace": not outside, "outsideNamespaceChanges": outside,
        "protectedUniqueFilesVerified": inherited["verifiedUniqueParentFiles"],
        "protectedManifestEntriesVerified": inherited["verifiedParentManifestEntries"], "protectedFileErrors": errors,
        "g1Regression": g1, "sourceFixtureReproducibility": fixture,
        "secretScan": {"status": "PASS" if not findings else "FAIL", "textFilesChecked": text_checked,
            "archivePayloadFilesChecked": fixture["payloadFilesChecked"], "findings": findings,
            "scope": "Strong token/private-key byte patterns; source ZIP exact manifest and explicit JSON/GeoJSON entry allowlist; no credential values read or published."},
        "publicReviewAllowlist": {"accepted": "PNG/MP4/SHA256SUMS only", "unapprovedPaths": publication_errors},
        "existingFinalRendererCameraShaderSceneAssetModified": False,
        "existingClaimsCachesVideosDeletedOrOverwritten": False,
        "paidGpuExecuted": False, "deploymentPerformed": False, "full80SecondVideoRendered": False,
        "nvidiaVerified": False, "visualQualityApproved": False, "finalPromotion": False,
        "requiredTempOnlyFiles": 0,
        "tempExplanation": "The pinned SOURCE_BUNDLE contains all1087 source payload files, actual safe restore/readback passed. Runtime caches and temporary generated source directories can be recreated by tools/source_fixture_store.py. Original G1 inputs/reports remain pinned in immutable Git; no old video or claim was reset."}
    output = HERE / "reports/PROTECTION.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "protectedUniqueFilesVerified": result["protectedUniqueFilesVerified"],
        "g1RawRGBAEqual": g1["rawRGBAFramesEqual"], "g1PNGEqual": g1["pngFramesEqual"],
        "fixtureFilesVerified": fixture["payloadFilesChecked"], "secretFindings": len(findings),
        "outsideNamespaceChanges": outside, "reportSHA256": digest(regular(output))}))
    if result["status"] != "PASS":
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    check()
