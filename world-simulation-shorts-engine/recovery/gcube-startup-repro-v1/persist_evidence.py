"""Persist only bounded synthetic CPU reproduction evidence on its own branch."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = "9034e18062ebcb8fd1f1fcc6dcee8898764650c7"
BRANCH = "development/gcube-startup-repro-20261015"
PREFIX = "world-simulation-shorts-engine/recovery/gcube-startup-repro-v1/"
WORKFLOW = ".github/workflows/gcube-startup-repro.yml"


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                          check=True, timeout=180).stdout.strip()


def protection():
    git("merge-base", "--is-ancestor", BASE, "HEAD")
    changed = git("diff", "--name-only", BASE, "HEAD").splitlines()
    if any(not (p.startswith(PREFIX) or p == WORKFLOW) for p in changed):
        raise RuntimeError("PROTECTED_BASELINE_CHANGE_FORBIDDEN")
    result = {"baseline": BASE, "protectedSourceChanges": 0,
              "diagnosticSourceCommit": git("rev-parse", "HEAD"),
              "changedPaths": changed, "gpuDeployed": False, "newImageBuilt": False}
    output = Path(os.environ["STARTUP_EVIDENCE_DIR"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "PROTECTION.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"protection": "PASS", "protectedSourceChanges": 0}))


def persist():
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("DIAGNOSTIC_BRANCH_REQUIRED")
    run_id, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    if not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[1-9][0-9]*", attempt):
        raise RuntimeError("TRUSTED_RUN_ID_REQUIRED")
    source = Path(os.environ["STARTUP_EVIDENCE_DIR"])
    target = HERE / "runs" / (run_id + "-" + attempt)
    if target.exists():
        raise RuntimeError("EXISTING_EVIDENCE_MUST_NOT_BE_OVERWRITTEN")
    if not source.is_dir():
        raise RuntimeError("EVIDENCE_DIRECTORY_MISSING")
    files = sorted(source.rglob("*"))
    entries = []
    total = 0
    for path in files:
        if path.is_symlink():
            raise RuntimeError("EVIDENCE_SYMLINK_FORBIDDEN")
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        if not re.fullmatch(r"[A-Za-z0-9_./-]+\.(json|stdout|stderr)", relative):
            raise RuntimeError("EVIDENCE_PATH_NOT_ALLOWED")
        size = path.stat().st_size
        total += size
        if size > 1024 * 1024 or total > 16 * 1024 * 1024:
            raise RuntimeError("EVIDENCE_SIZE_LIMIT")
        body = path.read_bytes()
        # No credentials are injected into any case. Reject familiar credential
        # encodings as an additional safeguard before publishing synthetic logs.
        if re.search(rb"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", body):
            raise RuntimeError("POSSIBLE_CREDENTIAL_IN_EVIDENCE")
        entries.append((relative, path, hashlib.sha256(body).hexdigest()))
    if not entries:
        raise RuntimeError("NO_EVIDENCE_FILES")
    git("fetch", "--filter=blob:none", "origin", BRANCH)
    if git("rev-parse", "HEAD") != git("rev-parse", "FETCH_HEAD"):
        raise RuntimeError("REMOTE_BRANCH_CHANGED_NO_AUTOMATIC_MERGE")
    target.mkdir(parents=True)
    for relative, original, _ in entries:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
    (target / "STEP_OUTCOMES.json").write_text(os.environ.get("STARTUP_STEP_OUTCOMES", "{}") + "\n")
    sums = [(p.relative_to(target).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(target.rglob("*")) if p.is_file()]
    (target / "SHA256SUMS").write_text("".join(digest + "  " + name + "\n" for name, digest in sums))
    relative_target = target.relative_to(REPO).as_posix()
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "--", relative_target)
    staged = git("diff", "--cached", "--name-only").splitlines()
    if not staged or any(not p.startswith(relative_target + "/") for p in staged):
        raise RuntimeError("EVIDENCE_ONLY_COMMIT_REQUIRED")
    git("commit", "-m", "docs: save immutable startup CPU reproduction evidence [skip ci]")
    git("push", "origin", "HEAD:refs/heads/" + BRANCH)
    print(json.dumps({"persisted": relative_target, "commit": git("rev-parse", "HEAD")}))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"protection", "persist"}:
        raise SystemExit("explicit protection or persist operation required")
    protection() if sys.argv[1] == "protection" else persist()
