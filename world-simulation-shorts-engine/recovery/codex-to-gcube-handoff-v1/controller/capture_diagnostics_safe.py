"""Best-effort post-cleanup export; isolate I/O from the GPU worker deadline.
No credentials or raw logs are passed to the child or returned to the caller.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import re
import subprocess
import sys
import time

_JOB = re.compile(r"studio-[a-f0-9]{32}\Z")


class ActiveCheckpointMirror:
    """One bounded storage child at a time; no retries after a storage failure.

    The worker polls this independently of frame progress. Only private local
    checkpoint metadata is read in the worker; mounted I/O stays in the child.
    The full post-cleanup export policy below is unchanged.
    """
    def __init__(self, job_root, export_root):
        self.job, self.export = Path(job_root), Path(export_root)
        self.process = None
        self.started = 0.0
        self.last_attempt = -1.0
        self.last_sequence = 0
        self.disabled = False
        self.status = "ACTIVE_CHECKPOINT_WAITING"
        if (not _JOB.fullmatch(self.job.name) or self.job.parent.name != "handoff-gpu-jobs"
                or not self.job.is_absolute() or not self.export.is_absolute()
                or ".." in self.export.parts):
            self.disabled = True
            self.status = "ACTIVE_CHECKPOINT_PATH_INVALID"

    def tick(self):
        try:
            now = time.monotonic()
            if self.process is not None:
                code = self.process.poll()
                if code is None:
                    if not self.disabled and now - self.started >= 1.0:
                        self.process.kill()
                        self.disabled = True
                        self.status = "ACTIVE_CHECKPOINT_TIMEOUT"
                    return self.status
                self.process = None
                if not self.disabled:
                    if code == 0:
                        self.status = "ACTIVE_CHECKPOINT_MOUNTED_WRITE_CONFIRMED"
                    else:
                        self.disabled = True
                        failures = {21: "ACTIVE_CHECKPOINT_PERMISSION", 22: "ACTIVE_CHECKPOINT_NO_SPACE",
                            23: "ACTIVE_CHECKPOINT_TOO_LARGE", 25: "ACTIVE_CHECKPOINT_TIMEOUT"}
                        self.status = failures.get(code, "ACTIVE_CHECKPOINT_STORAGE_FAILED")
            if self.disabled or now - self.last_attempt < 1.0:
                return self.status
            self.last_attempt = now
            source = self.job / "capture" / "CAPTURE_OPERATION_CHECKPOINT.json"
            if not os.path.lexists(source):
                return self.status
            from safe_capture_export import read_json_safe
            value = read_json_safe(source)
            sequence = value.get("sequence") if isinstance(value, dict) else None
            if (not isinstance(value, dict) or value.get("schema") != "WORLD_ENGINE_CAPTURE_OPERATIONS_V1"
                    or value.get("runId") != self.job.name or type(sequence) is not int
                    or not 1 <= sequence <= 1000000 or sequence < self.last_sequence):
                self.disabled = True
                self.status = "ACTIVE_CHECKPOINT_SOURCE_INVALID"
                return self.status
            if sequence == self.last_sequence:
                return self.status
            self.process = subprocess.Popen([sys.executable, "-I", "-S",
                str(Path(__file__).with_name("safe_capture_export.py")),
                "--job-root", str(self.job), "--destination", str(self.export / ("capture-checkpoint-" + self.job.name)),
                "--active-checkpoint", "--seconds", "1"], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={}, close_fds=True)
            self.started = time.monotonic()
            self.last_sequence = sequence
            if self.status == "ACTIVE_CHECKPOINT_WAITING":
                self.status = "ACTIVE_CHECKPOINT_STARTED"
            return self.status
        except Exception:
            self.disabled = True
            self.status = "ACTIVE_CHECKPOINT_STORAGE_FAILED"
            return self.status

    def close(self):
        """Stop only our storage child; never signal capture or touch its lease."""
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    self.process.kill()
                self.process.wait(timeout=0.5)
                self.process = None
            except Exception:
                self.status = "ACTIVE_CHECKPOINT_CHILD_CLEANUP_UNCONFIRMED"
        self.disabled = True
        return self.status


def preserve_before_cleanup(job_root):
    """Best-effort LOCAL safe receipt only; never unlock or access export_root.

    Called after cleanup attempts or on dead-worker status. Child I/O is bounded
    independently, including after the render deadline. This grants no render time.
    """
    process = None
    try:
        job = Path(job_root)
        if not _JOB.fullmatch(job.name) or job.parent.name != "handoff-gpu-jobs":
            return {"status": "PRIVATE_JOB_INVALID"}
        process = subprocess.Popen([sys.executable, "-I", "-S",
            str(Path(__file__).with_name("safe_capture_export.py")),
            "--job-root", str(job), "--private-pending", "--seconds", "1"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={}, close_fds=True)
        try:
            code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                return {"status": "TIMEOUT_CLEANUP_UNCONFIRMED"}
            return {"status": "TIMEOUT"}
        return {"status": "LOCAL_ATTEMPT_COMPLETE" if code == 0 else "LOCAL_STORAGE_FAILED"}
    except Exception:
        return {"status": "LOCAL_STORAGE_FAILED"}


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

