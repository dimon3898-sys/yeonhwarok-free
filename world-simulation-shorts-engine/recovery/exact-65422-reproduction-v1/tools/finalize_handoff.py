#!/usr/bin/env python3
"""Package explicitly allowlisted public evidence after the 150-frame comparison.

Never packages original private Scene/fixtures, complete capture diagnostics,
caches, logs, credentials, or arbitrary files discovered by directory walking.
The root checksum inventory hashes persisted evidence without publishing it.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import os
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ZIP_NAME = "WORLD_ENGINE_EXACT_65422_REPRODUCTION_HANDOFF.zip"
REQUIRED = (
    "ORIGINAL_EXECUTION_PROFILE.json",
    "reports/ROOT_CAUSE_LEDGER.json",
    "reports/ROOT_CAUSE_LEDGER.csv",
    "reports/ROOT_CAUSE_LEDGER.md",
    "reports/SOURCE_CAPSULE_MANIFEST.json",
    "reports/comparison/ALL_150_FRAME_COMPARISON.json",
    "reports/comparison/ALL_150_FRAME_COMPARISON.csv",
    "proof/CAPTURE_RECEIPT.json",
    "REPRODUCTION_INSTRUCTIONS.md",
)
OPTIONAL = (
    "README.md", "RESULT.md", "VALIDATION.json", "RESULT.json",
    "reports/ORIGINAL_ENVIRONMENT.md",
    "reports/PRIMARY_EVIDENCE.json", "reports/CAPTURE_ADAPTER_REVIEW.json",
    "reports/ENCODING_DIFFERENCE_AND_TRIALS.json", "reports/DUPLICATE_RENDER_GUARD.json",
    "reports/VALIDATION.json",
    "reports/REGRESSION_TEST_RESULTS.json", "reports/TEST_RESULTS.json",
    "reports/PROTECTION_CHECK.json", "reports/PROTECTION_RESULTS.json",
    "reports/PROTECTION.json",
    "reports/SECRET_SCAN.json", "reports/SECURITY_AND_PROTECTION.json",
    "tools/restore_capsule.py", "tools/capture_original.mjs",
    "tools/compare_150_frames.py", "tools/test_compare_150_frames.py",
    "tools/build_cause_ledger.py", "tools/finalize_handoff.py",
    "tools/verify_downloads.py", "tools/verify_protection.py",
)
PERSISTED_ONLY = (
    ".gitignore", "proof/CAPTURE_STATUS.json",
    "reports/DOWNLOAD_VERIFICATION.json", "reports/PERSISTENCE_RECEIPT.json",
)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def regular(path: Path) -> None:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        raise ValueError("HANDOFF_PATH_OUTSIDE_CANDIDATE") from None
    current = ROOT
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("HANDOFF_SYMLINK_FORBIDDEN " + str(relative))
    if not path.is_file():
        raise ValueError("HANDOFF_REGULAR_FILE_REQUIRED " + str(relative))


def atomic_generated(path: Path, data: bytes) -> None:
    """Only new-namespace generated reports/checksums may be refreshed."""
    if path.exists():
        regular(path)
        if path.read_bytes() == data:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".writing")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("GENERATED_TEMPORARY_ALREADY_EXISTS " + str(temporary))
    with temporary.open("xb") as target:
        target.write(data)
    os.replace(temporary, path)


def validate_capture_receipt() -> None:
    source = ROOT / "proof/CAPTURE_RECEIPT.json"
    regular(source)
    report = json.loads(source.read_text())
    if report.get("status") not in ("CAPTURE_AND_ENCODE_PASS_COMPARISON_REQUIRED", "PASS") or report.get("totalFrames") != 150:
        raise ValueError("COMPLETE_FRESH_CAPTURE_REQUIRED")
    if "frames" in report or "runtime" in report or "sourceBindings" in report:
        raise ValueError("ONLY_SANITIZED_CAPTURE_RECEIPT_MAY_BE_PUBLIC")


def make_handoff() -> None:
    comparison = ROOT / "reports/comparison/ALL_150_FRAME_COMPARISON.json"
    regular(comparison)
    parsed = json.loads(comparison.read_text())
    # Require actual per-frame evidence; leave PASS/NEEDS_REWORK to its author.
    if not isinstance(parsed, dict) or len(parsed.get("frames", [])) != 150 or parsed.get("decodedMovie", {}).get("frameCount") != 150:
        raise ValueError("ACTUAL_COMPARISON_REPORT_REQUIRED")
    validate_capture_receipt()
    payload = {}
    for name in REQUIRED + OPTIONAL:
        source = ROOT / name
        if not source.exists():
            if name in REQUIRED:
                raise ValueError("REQUIRED_HANDOFF_FILE_MISSING " + name)
            continue
        regular(source)
        payload[name] = source.read_bytes()
    manifest = {
        "schema": "EXACT_65422_SAFE_PUBLIC_HANDOFF_V1",
        "packagingPolicy": "EXPLICIT_FILE_ALLOWLIST_ONLY",
        "privateSceneOrFixturesIncluded": False,
        "fullCaptureDiagnosticsIncluded": False,
        "originalCaptureReportIncluded": False,
        "cacheOrLogsIncluded": False,
        "files": [{"path": name, "bytes": len(data), "sha256": digest_bytes(data)}
                  for name, data in sorted(payload.items())],
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    payload["HANDOFF_MANIFEST.json"] = manifest_bytes
    payload["SHA256SUMS"] = ("".join(digest_bytes(data) + "  " + name + "\n"
                                      for name, data in sorted(payload.items()))).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payload.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    target = ROOT / "handoff" / ZIP_NAME
    if target.parent.is_symlink():
        raise ValueError("HANDOFF_DIRECTORY_SYMLINK_FORBIDDEN")
    if target.exists():
        regular(target)
        if target.read_bytes() != buffer.getvalue():
            raise ValueError("REFUSE_EXISTING_HANDOFF_ZIP_OVERWRITE_USE_NEW_VERSION")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(buffer.getvalue())
    atomic_generated(ROOT / "handoff/HANDOFF_MANIFEST.json", manifest_bytes)


def checksums() -> dict:
    directories = {}
    for folder in ("public-review", "handoff"):
        directory = ROOT / folder
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError("PUBLIC_DIRECTORY_REQUIRED " + folder)
        files = []
        for source in sorted(directory.iterdir()):
            if source.name == "SHA256SUMS":
                regular(source)
                continue
            regular(source)
            if folder == "public-review" and source.suffix.lower() not in (".mp4", ".png"):
                raise ValueError("PUBLIC_REVIEW_ONLY_MP4_PNG_SHA256SUMS " + source.name)
            if folder == "handoff" and source.name not in (ZIP_NAME, "HANDOFF_MANIFEST.json"):
                raise ValueError("UNEXPECTED_PUBLIC_HANDOFF_ARTIFACT " + source.name)
            files.append(source)
        if not files:
            raise ValueError("PUBLIC_ARTIFACTS_REQUIRED " + folder)
        if folder == "public-review":
            names = {f.name for f in files}
            if "WORLD_ENGINE_65422_EXACT_REPRODUCTION_5S.mp4" not in names or "COMPARISON_CAMERA_FRONTIER_TERRITORY_LIGHTING.png" not in names:
                raise ValueError("MOVIE_AND_ACTUAL_COMPARISON_PNG_REQUIRED")
        atomic_generated(directory / "SHA256SUMS", ("".join(digest_file(f) + "  " + f.name + "\n" for f in files)).encode())
        directories[folder] = len(files)
    # Enumerate persisted allowlisted files; never depend on full private report.
    inventory = {ROOT / name for name in REQUIRED + OPTIONAL + PERSISTED_ONLY if (ROOT / name).exists()}
    for folder in ("public-review", "handoff"):
        inventory.update((ROOT / folder).iterdir())
    inventory = sorted(inventory)
    for source in inventory:
        regular(source)
    atomic_generated(ROOT / "SHA256SUMS", ("".join(digest_file(f) + "  " + f.relative_to(ROOT).as_posix() + "\n" for f in inventory)).encode())
    return {"publicArtifacts": directories, "persistedInventoryFiles": len(inventory)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checksums-only", action="store_true", help="Refresh checksum inventories after a later persisted receipt; preserve existing ZIP")
    args = parser.parse_args()
    if not args.checksums_only:
        make_handoff()
    elif not (ROOT / "handoff" / ZIP_NAME).is_file():
        raise ValueError("EXISTING_FINALIZED_HANDOFF_REQUIRED")
    result = checksums()
    result["status"] = "SAFE_PUBLIC_HANDOFF_PREPARED"
    result["zip"] = ZIP_NAME
    result["zipBytes"] = (ROOT / "handoff" / ZIP_NAME).stat().st_size
    result["zipSHA256"] = digest_file(ROOT / "handoff" / ZIP_NAME)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
