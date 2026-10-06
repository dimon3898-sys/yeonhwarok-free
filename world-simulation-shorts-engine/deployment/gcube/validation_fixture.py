"""Idempotent, unapproved first-boot QA fixture; call after dropping privileges.

The marker refers to the immutable initial version. Owner approvals, completed
videos, and later revisions are retained across starts. Corrupt/incomplete
initialization fails closed and never silently creates a replacement project.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys

APP = Path(__file__).resolve().parents[2]
if str(APP) in sys.path:
    sys.path.remove(str(APP))
sys.path.insert(0, str(APP))

from deployment.gcube.validate_container import SOURCE, seed, sha
from deployment.mobile_server import checked_state_root
from engine.storage import ProjectStore, plan_hash


class FixtureError(Exception):
    pass


def _require(value, code):
    if not value:
        raise FixtureError(code)


def _record(path):
    _require(not path.is_symlink() and path.is_file(), "INVALID_VALIDATION_MARKER")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "r", encoding="utf-8") as source:
        info = os.fstat(source.fileno())
        _require(stat.S_ISREG(info.st_mode) and not stat.S_IMODE(info.st_mode) & 0o077
                 and info.st_size <= 8192, "INVALID_VALIDATION_MARKER")
        try:
            value = json.load(source)
        except (ValueError, UnicodeError):
            raise FixtureError("INVALID_VALIDATION_MARKER") from None
    _require(isinstance(value, dict), "INVALID_VALIDATION_MARKER")
    return value


def _exclusive_record(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _verify(marker, runtime, template_sha):
    pid, version, digest = marker.get("project_id"), marker.get("version"), marker.get("plan_hash")
    _require(marker.get("schema_version") == 1 and marker.get("template_sha256") == template_sha
             and isinstance(pid, str) and re.fullmatch(r"project_[a-z0-9_]{6,64}", pid)
             and version == "v001" and isinstance(digest, str)
             and re.fullmatch(r"[a-f0-9]{64}", digest), "INVALID_VALIDATION_MARKER")
    _require(marker.get("approved_at_initialization") is False and marker.get("render_started_at_initialization") is False
             and marker.get("gpu_speedup_claimed") is False, "INVALID_VALIDATION_MARKER")
    try:
        store = ProjectStore(runtime / "projects")
        pid, version = marker["project_id"], marker["version"]
        _require(not (runtime / "projects" / pid).is_symlink(), "VALIDATION_PROJECT_MISSING_OR_CHANGED")
        folder = store.version_path(pid, version)
        _require(not folder.is_symlink() and not (folder / "scene_plan.json").is_symlink(), "VALIDATION_PROJECT_MISSING_OR_CHANGED")
        plan = store.get(pid, version)["plan"]
        _require(plan.get("plan_hash") == marker["plan_hash"] == plan_hash(plan)
                 and float(plan.get("duration", 0)) == 12
                 and len(plan.get("scenes", [])) == 5, "VALIDATION_PROJECT_MISSING_OR_CHANGED")
    except FixtureError:
        raise
    except Exception:
        raise FixtureError("VALIDATION_PROJECT_MISSING_OR_CHANGED") from None
    return marker


def _sync_project(runtime, pid):
    project = runtime / "projects" / pid
    for path in project.rglob("*"):
        _require(not path.is_symlink(), "VALIDATION_PROJECT_MISSING_OR_CHANGED")
        if path.is_file():
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    directories = [path for path in project.rglob("*") if path.is_dir()]
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        _sync_directory(path)
    _sync_directory(project)
    _sync_directory(runtime / "projects")


def seed_once(state_root, *, template=SOURCE):
    """Seed once after UID drop, before app startup; never approves or renders."""
    runtime = checked_state_root(state_root)
    template = Path(template)
    _require(template.is_file() and not template.is_symlink(), "VALIDATION_TEMPLATE_REQUIRED")
    template_sha = sha(template)
    marker_path = runtime / "gcube-validation-project.json"
    pending_path = runtime / "gcube-validation-project.pending.json"
    lock_path = runtime / "gcube-validation-project.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "a+") as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if marker_path.exists() or marker_path.is_symlink():
            return _verify(_record(marker_path), runtime, template_sha)
        # If a prior process died after writing project files but before the
        # durable marker, retain those files and require explicit recovery.
        _require(not pending_path.exists() and not pending_path.is_symlink(), "VALIDATION_INITIALIZATION_INCOMPLETE")
        transaction = secrets.token_hex(16)
        _exclusive_record(pending_path, {"schema_version": 1, "template_sha256": template_sha,
                                       "transaction_id": transaction,
                                       "state": "initializing", "approved": False, "render_started": False})
        _sync_directory(runtime)
        try:
            result = seed(template, runtime)
            marker = {"schema_version": 1, "template_sha256": template_sha,
                      "transaction_id": transaction,
                      "project_id": result["project_id"], "version": result["version"],
                      "duration": result["duration"], "scene_ids": result["scene_ids"],
                      "plan_hash": result["plan_hash"], "gate_passed_at_initialization": result["gate_passed"],
                      "approved_at_initialization": False, "render_started_at_initialization": False,
                      "gpu_speedup_claimed": False}
            _verify(marker, runtime, template_sha)
            _sync_project(runtime, result["project_id"])
            temporary = runtime / f".gcube-validation-project.{transaction}.tmp"
            _exclusive_record(temporary, marker)
            # link publishes a complete marker atomically and refuses to
            # replace any existing file, including a corrupt marker.
            os.link(temporary, marker_path, follow_symlinks=False)
            _sync_directory(runtime)
            temporary.unlink()
            pending_path.unlink()
            _sync_directory(runtime)
            return marker
        except FixtureError:
            raise
        except Exception:
            raise FixtureError("VALIDATION_INITIALIZATION_FAILED") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--template", type=Path, default=SOURCE)
    args = parser.parse_args(argv)
    try:
        record = seed_once(args.state_root, template=args.template)
    except Exception:
        print(json.dumps({"passed": False, "failure": "VALIDATION_FIXTURE_BLOCKED", "render_started": False}))
        return 1
    print(json.dumps(record, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
