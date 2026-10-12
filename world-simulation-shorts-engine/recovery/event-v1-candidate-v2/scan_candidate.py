#!/usr/bin/env python3
"""Pinned, redacted candidate scans. No credentials or raw matches are reported."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

SCANNER_SHA256 = "e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad"
SCANNER_VERSION = "8.24.3"


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def command_output(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd).decode().strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--candidate", required=True, help="Repository-relative candidate path")
    parser.add_argument("--base", default="1d5182f")
    parser.add_argument("--tip", default="HEAD")
    parser.add_argument("--scanner", default=shutil.which("gitleaks"),
                        help="Optional explicit path to the pinned Gitleaks 8.24.3 binary")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    candidate = repo / args.candidate
    candidate.resolve().relative_to(repo)
    if not candidate.is_dir():
        raise SystemExit("Candidate directory is missing")
    if not args.scanner:
        raise SystemExit("Gitleaks is missing; supply --scanner with the verified 8.24.3 binary")
    scanner = Path(args.scanner).resolve()
    if digest(scanner) != SCANNER_SHA256:
        raise SystemExit("Pinned scanner integrity check failed")
    if command_output([str(scanner), "version"]) != SCANNER_VERSION:
        raise SystemExit("Pinned scanner version check failed")
    base = command_output(["git", "rev-parse", "--verify", args.base + "^{commit}"], repo)
    tip = command_output(["git", "rev-parse", "--verify", args.tip + "^{commit}"], repo)
    changed = subprocess.check_output([
        "git", "diff", "--name-only", "-z", "--diff-filter=ACMRTUXB", base, tip
    ], cwd=repo).decode().split("\0")
    event_sources = subprocess.check_output([
        "git", "ls-files", "-z", "world-simulation-shorts-engine/web/map_infographic_v1/event_*",
        "world-simulation-shorts-engine/tests/event_*"
    ], cwd=repo).decode().split("\0")
    paths = set(path for path in changed + event_sources if path)
    for directory in [candidate, repo / "world-simulation-shorts-engine/recovery/event-data"]:
        for path in directory.rglob("*"):
            if path.is_file():
                paths.add(str(path.relative_to(repo)))
    output_relative = str((candidate / "evidence/SECRET_SCAN.json").relative_to(repo))
    paths.discard(output_relative)
    # Post-scan records cannot be in their own input set. Other manifests are included.
    for name in ["POST_SCAN_SOURCE_CHECK.json", "SOURCE_AFTER_SECRET_SCAN.json"]:
        paths.discard(str((candidate / "evidence" / name).relative_to(repo)))
    env = os.environ.copy()
    env.pop("GITLEAKS_CONFIG", None)
    env.pop("GITLEAKS_CONFIG_TOML", None)
    input_files = []
    skipped = []
    summaries = []
    with tempfile.TemporaryDirectory(prefix="event-v1-candidate-v2-secret-scan-") as temporary:
        temp = Path(temporary)
        config = temp / "trusted-default.toml"
        config.write_text("[extend]\nuseDefault = true\n")
        ignore = temp / "empty.gitleaksignore"
        ignore.write_text("")
        common = ["--redact=100", "--max-decode-depth=3", "--ignore-gitleaks-allow",
                  "--no-banner", "--no-color", "--config", str(config),
                  "--gitleaks-ignore-path", str(ignore), "--report-format=json"]
        stage = temp / "scope"
        stage.mkdir()
        for relative in sorted(paths):
            source = repo / relative
            source.resolve().relative_to(repo)
            if source.is_symlink() or not source.is_file():
                skipped.append({"file": relative, "reason": "symlink_or_missing"})
                continue
            with source.open("rb") as stream:
                prefix = stream.read(8192)
            if b"\0" in prefix or source.suffix.lower() in {".png", ".jpg", ".jpeg", ".mp4", ".webm"}:
                skipped.append({"file": relative, "reason": "binary_media_or_data_content",
                                "git_pointer_or_diff_scanned": relative in changed})
                continue
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source, target)
            except OSError:
                shutil.copyfile(source, target)
            input_files.append({"file": relative, "sha256": digest(source), "bytes": source.stat().st_size})
        for label, mode, target, extra in [
            ("worktree", "dir", str(stage), []),
            ("development_git_range", "git", str(repo), ["--log-opts=" + base + ".." + tip]),
        ]:
            report = temp / (label + ".json")
            result = subprocess.run([str(scanner), mode, target, *extra, *common,
                                     "--report-path", str(report)], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Never print or save scanner stdout/stderr, even when redaction is requested.
            findings = []
            if report.exists():
                raw = json.loads(report.read_text())
                for row in raw or []:
                    filename = row.get("File", "")
                    if label == "worktree":
                        filename = filename.removeprefix(str(stage) + "/")
                    findings.append({"file": filename, "rule": row.get("RuleID"),
                                     "start_line": row.get("StartLine"), "end_line": row.get("EndLine")})
            summaries.append({"scope": label, "exit_code": result.returncode,
                              "findings_count": len(findings), "findings": findings,
                              "report_created": report.exists()})
    complete = all(scan["exit_code"] == 0 and scan["findings_count"] == 0 and scan["report_created"]
                   for scan in summaries)
    after_changed = [row["file"] for row in input_files if digest(repo / row["file"]) != row["sha256"]]
    payload = {
        "status": "PASS" if complete and not after_changed else "FAILED",
        "scanner": {"name": "Gitleaks", "version": SCANNER_VERSION, "binary_sha256": SCANNER_SHA256,
                    "official_release_provenance": "Binary pinned to the official v8.24.3 release verified during tool preparation",
                    "release": "https://github.com/gitleaks/gitleaks/releases/tag/v8.24.3"},
        "git_version": command_output(["git", "--version"]),
        "development_range": {"base": base, "tip": tip},
        "redaction_percent": 100, "max_decode_depth": 3, "ignore_allow_comments": True,
        "rules": "Gitleaks embedded default, no custom allowlists or ignore entries",
        "excluded_paths": ["Git metadata/hooks/config", "credential files", "process environment",
                           output_relative, "post-scan self-referential records"],
        "binary_limitation": "Binary media and binary data bodies are not scanned as text; native Git scan includes any associated added LFS pointers and textual diffs.",
        "worktree_input_files": input_files, "worktree_skipped": skipped,
        "input_mutations_during_scan": after_changed, "scans": summaries,
    }
    output = candidate / "evidence/SECRET_SCAN.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"status": payload["status"], "worktree_input_files": len(input_files),
                      "worktree_skipped": len(skipped), "scans": [
                          {key: row[key] for key in ["scope", "exit_code", "findings_count"]}
                          for row in summaries], "report": str(output)}))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
