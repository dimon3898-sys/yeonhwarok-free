"""Best-effort post-cleanup export; isolate I/O from the GPU worker deadline.
No credentials or raw logs are passed to the child or returned to the caller.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import re
import subprocess
import sys

_JOB = re.compile(r"studio-[a-f0-9]{32}\Z")


def export_after_cleanup(job_root, export_root, execution_deadline):
    job, export = Path(job_root), Path(export_root)
    if not _JOB.fullmatch(job.name):
        raise ValueError("DIAGNOSTIC_JOB_ID_INVALID")
    if not export.is_absolute() or not export.is_dir() or export.is_symlink():
        raise ValueError("DIAGNOSTIC_EXPORT_ROOT_INVALID")
    deadline = datetime.fromisoformat(execution_deadline)
    if deadline.tzinfo is None:
        raise ValueError("DIAGNOSTIC_DEADLINE_INVALID")
    remaining = min(5.0, (deadline - datetime.now(timezone.utc)).total_seconds())
    if remaining <= 0:
        raise TimeoutError("DIAGNOSTIC_DEADLINE_EXPIRED")
    helper = Path(__file__).with_name("safe_capture_export.py")
    # Empty environment: owner/token values must never be inherited by exporter.
    process = subprocess.Popen([sys.executable, "-I", "-S", str(helper),
        "--job-root", str(job), "--destination", str(export / ("capture-diagnostic-" + job.name)),
        "--seconds", str(remaining)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, env={}, close_fds=True)
    try:
        code = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            return {"status": "TIMEOUT_CLEANUP_UNCONFIRMED"}
        return {"status": "TIMEOUT"}
    failures = {21: "STORAGE_PERMISSION", 22: "STORAGE_NO_SPACE", 23: "STORAGE_TOO_LARGE", 24: "EXPORT_FAILED", 25: "TIMEOUT"}
    return {"status": "EXPORTED" if code == 0 else failures.get(code, "EXPORT_FAILED")}
