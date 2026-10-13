#!/usr/bin/env python3
"""Focused pinned default-rule secret scan; emit only redacted finding coordinates."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from build_manifest import (REPO, BASE, ENGINE, SOURCE_PARENT, OPTIONAL_OVERRIDES,
                            POSTSAVE, H, encode, require, discover)

PINNED_SHA256 = "e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad"
DEFAULT_SCANNER = "/workspace/.onboarding/event-v1-tools/gitleaks"
TEXT_SUFFIXES = {".mjs", ".py", ".md", ".txt", ".json", ".toml", ".lock", ".sh", ".html", ".css"}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scanner", type=Path, default=Path(DEFAULT_SCANNER))
    parser.add_argument("--output", type=Path, default=REPO / BASE / "evidence/SECRET_SCAN.json")
    args = parser.parse_args()
    scanner = args.scanner.resolve()
    require(scanner.is_file() and digest(scanner) == PINNED_SHA256, "PINNED_SCANNER_INTEGRITY")
    version = subprocess.check_output([str(scanner), "version"], stderr=subprocess.PIPE).decode().strip()
    require(version == "8.24.3", "PINNED_SCANNER_VERSION")
    output = args.output.resolve()
    relative_output = output.relative_to(REPO).as_posix()
    require(relative_output in POSTSAVE and output.name.startswith("SECRET_SCAN"), "SECRET_RECEIPT_OUTPUT_SCOPE")
    paths = set(OPTIONAL_OVERRIDES)
    paths.update(discover(ENGINE + "/web/map_infographic_v1", "planner_causal*.mjs"))
    paths.update(discover(ENGINE + "/tests", "planner_causal*.test.mjs"))
    skipped_media = []
    for source in (REPO / BASE).rglob("*"):
        if not source.is_file() or any(p in {"__pycache__", ".pytest_cache"} for p in source.parts):
            continue
        relative = source.relative_to(REPO).as_posix()
        if relative in POSTSAVE:
            continue
        H.HELPER.safe_file(relative)
        if source.suffix.lower() in {".mp4", ".png"}:
            skipped_media.append(relative)
        else:
            require(source.suffix.lower() in TEXT_SUFFIXES or source.name == "SHA256SUMS", "UNCLASSIFIED_UNSCANNED_CANDIDATE_BODY: " + relative)
            paths.add(relative)
    paths = sorted(paths)
    rows = [{"file": relative, "sha256": digest(H.HELPER.safe_file(relative)),
             "bytes": (REPO / relative).stat().st_size} for relative in paths]
    env = os.environ.copy()
    env.pop("GITLEAKS_CONFIG", None)
    env.pop("GITLEAKS_CONFIG_TOML", None)
    stage_parent = Path("/workspace/.onboarding/planner-night-secret-scan")
    stage_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scope-", dir=stage_parent) as temporary:
        temporary = Path(temporary)
        stage = temporary / "scope"
        stage.mkdir()
        config = temporary / "trusted-default.toml"
        config.write_text("[extend]\nuseDefault = true\n")
        ignore = temporary / "empty.gitleaksignore"
        ignore.write_text("")
        for relative in paths:
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / relative, target)
        report = temporary / "redacted-findings.json"
        command = [str(scanner), "dir", str(stage), "--redact=100", "--max-decode-depth=3",
                   "--ignore-gitleaks-allow", "--no-banner", "--no-color", "--config", str(config),
                   "--gitleaks-ignore-path", str(ignore), "--report-format=json", "--report-path", str(report)]
        scan = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        created = report.is_file()
        findings = []
        if created:
            for row in json.loads(report.read_text()) or []:
                findings.append({"file": row.get("File", "").removeprefix(str(stage) + "/"),
                                 "rule": row.get("RuleID"), "start_line": row.get("StartLine"), "end_line": row.get("EndLine")})
    mutations = [row["file"] for row in rows if digest(REPO / row["file"]) != row["sha256"]]
    passed = scan.returncode == 0 and created and not findings and not mutations
    result = {"schema": "PLANNER_NIGHT_RUN_SECRET_SCAN_V1", "status": "PASS" if passed else "FAIL",
              "scanner": {"name": "gitleaks", "version": version, "sha256": PINNED_SHA256,
                          "source": "https://github.com/gitleaks/gitleaks/releases/tag/v8.24.3", "required_for_runtime": False},
              "scope": "NEW_NIGHT_TEXT_MANIFESTS_AND_GENERIC_MODULES_TESTS_PLUS_TWO_OPTIONAL_NONFINAL_OVERRIDES",
              "sourceParent": SOURCE_PARENT, "input_files": rows, "input_mutations": mutations,
              "rules": "Embedded default rules; trusted explicit config; empty ignore list; allow comments ignored",
              "redaction_percent": 100, "max_decode_depth": 3, "exit_code": scan.returncode,
              "report_created": created, "findings_count": len(findings), "findings": findings,
              "postsave_report_exclusions": sorted(POSTSAVE), "media_excluded_from_text_scan": sorted(skipped_media),
              "protected_original_binaries_rescanned": False, "raw_findings_or_secret_values_emitted": False,
              "requiredTempOnlyFiles": 0, "permanentGateExecuted": False,
              "eventFinal": False, "plannerFinal": False, "userVideoApproved": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encode(result))
    print(json.dumps({"status": result["status"], "scannedTextFiles": len(rows), "findings": len(findings), "inputMutations": len(mutations)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
