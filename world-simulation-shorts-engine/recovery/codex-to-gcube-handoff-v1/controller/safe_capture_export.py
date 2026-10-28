"""Read only three private receipts; publish fixed-schema, non-secret diagnostics.
Production callers MUST use capture_diagnostics_safe.export_after_cleanup, which
isolates filesystem I/O in a time-bounded child. No raw logs are read or exported.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time

STAGES = frozenset({"RENDER_RUNTIME", "APPROVAL_OR_INPUT", "SOURCE_OR_SCENE",
    "RUNTIME_PERMISSIONS", "GPU_NATIVE_DRAW", "ENCODING_OR_DECODE", "DEADLINE",
    "PRE_CAPTURE_VALIDATION", "DESCENDANT_CLEANUP"})
# An uppercase regex is NOT a secret filter. Only fixed public enum values leave.
CODES = frozenset({"GCUBE_CAPTURE_RUNTIME_FAILED", "HANDOFF_CAPTURE_PROCESS_FAILED",
    "HANDOFF_CAPTURE_SUPERVISOR_FAILED", "HANDOFF_CAPTURE_STOP_REQUESTED",
    "HANDOFF_APPROVED_CAPTURE_DEADLINE_EXCEEDED", "HANDOFF_PARENT_EXITED_CAPTURE_ABORTED",
    "HANDOFF_GPU_DESCENDANT_CLEANUP_UNRESOLVED", "HANDOFF_UNRESOLVED_CAPTURE_CLEANUP",
    "HANDOFF_PARENT_EXITED_BEFORE_CAPTURE", "HANDOFF_CAPTURE_PARENT_IDENTITY_REQUIRED",
    "GCUBE_REVIEW_DEADLINE_EXCEEDED", "GCUBE_NVIDIA_RENDERER_REQUIRED",
    "GCUBE_NVIDIA_VULKAN_REQUIRED", "GCUBE_NATIVE_CONTEXT_REQUIRED",
    "GCUBE_NATIVE_DRAW_FAILED", "GCUBE_NATIVE_READBACK_INVALID",
    "GCUBE_NATIVE_REPEATED_PIXEL_MISMATCH", "UP2_BLACK_FRAME", "UP2_FRAME_GL_ERROR",
    "UP2_ENCODER_EARLY_EXIT", "UP2_ENCODER_CLOSED", "UP2_PRIVATE_PLAYWRIGHT_REQUIRED"})
DIAGNOSTIC_STAGES = frozenset({"PAGE_EVALUATE_RUNTIME_IMPORT", "PAGE_EVALUATE_FIRST_NATIVE_DRAW", "PAGE_EVALUATE_FRAME_CAPTURE"})
LIMIT = 65536


def safe_code(value):
    return value if isinstance(value, str) and value in CODES else None


def directory_fd(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("DIAGNOSTIC_ABSOLUTE_PATH_REQUIRED")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_json_safe(path):
    parent = fd = None
    try:
        parent = directory_fd(Path(path).parent)
        fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.getuid() or info.st_mode & 0o077
                or info.st_size > LIMIT):
            return None
        raw = bytearray()
        while len(raw) <= LIMIT:
            block = os.read(fd, min(8192, LIMIT + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        if len(raw) > LIMIT:
            return None
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None
    finally:
        if fd is not None:
            os.close(fd)
        if parent is not None:
            os.close(parent)


def message_category(value):
    # Category is evidence of an error API, NOT a proven GPU root cause.
    if not isinstance(value, str):
        return None
    for prefix, category in (("browserType.launch:", "BROWSER_LAUNCH"),
            ("page.goto:", "PAGE_NAVIGATION"), ("page.evaluate:", "PAGE_EVALUATION"),
            ("browser.newPage:", "PAGE_CREATION")):
        if value.startswith(prefix):
            return category
    return "UNCLASSIFIED"


def export_failure(job_root, destination, *, deadline_seconds=5):
    if (isinstance(deadline_seconds, bool) or not isinstance(deadline_seconds, (float, int))
            or not 0 < deadline_seconds <= 5):
        raise ValueError("DIAGNOSTIC_DEADLINE_INVALID")
    limit = time.monotonic() + deadline_seconds
    def check_time():
        if time.monotonic() >= limit:
            raise TimeoutError("DIAGNOSTIC_DEADLINE_EXCEEDED")
    job, dest = Path(job_root), Path(destination)
    check_time()
    supervisor = read_json_safe(job / "LEASE_SUPERVISOR_RESULT.json")
    if not supervisor or supervisor.get("cleanupVerified") is not True:
        raise ValueError("DIAGNOSTIC_VERIFIED_CLEANUP_REQUIRED")
    check_time()
    # supervisor run() passes output=job; neither of these files is in capture/.
    first = read_json_safe(job / "FIRST_CAPTURE_FAILURE.json")
    if first is None and isinstance(supervisor.get("firstFailure"), dict):
        first = supervisor["firstFailure"]
    receipt = read_json_safe(job / "capture" / "CAPTURE_RECEIPT.json")
    failure = (receipt or {}).get("failure")
    text = failure.get("code") if isinstance(failure, dict) else None
    code = (first or {}).get("code")
    stage = (first or {}).get("stage")
    frames = (receipt or {}).get("renderedFrames")
    raw_stage = failure.get("diagnosticStage") if isinstance(failure, dict) else None
    safe_stage = raw_stage if type(raw_stage) is str and raw_stage in DIAGNOSTIC_STAGES else None
    payload = {"schema": "WORLD_ENGINE_CAPTURE_DIAGNOSTIC_SAFE_V2",
        "firstFailure": {"code": safe_code(code), "stage": stage if isinstance(stage, str) and stage in STAGES else None,
            "unrecognizedCode": code is not None and safe_code(code) is None},
        "supervisor": {"reason": safe_code(supervisor.get("reason")), "cleanupVerified": True},
        "capture": {"code": safe_code(text), "messageCategory": message_category(text),
            "diagnosticStage": safe_stage,
            "renderedFrames": frames if type(frames) is int and 0 <= frames <= 180 else None,
            "nvidiaVerified": (receipt or {}).get("nvidiaVerified") is True},
        "missingEvidence": {"first": first is None, "capture": receipt is None}}
    content = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(content).hexdigest()
    parent = directory_fd(dest.parent)
    target = None
    try:
        check_time()
        os.mkdir(dest.name, mode=0o700, dir_fd=parent)
        target = os.open(dest.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        for name, body in (("CAPTURE_DIAGNOSTIC.json", content),
                ("SHA256SUMS", (digest + "  CAPTURE_DIAGNOSTIC.json\n").encode())):
            check_time()
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=target)
            with os.fdopen(fd, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
        check_time()
    finally:
        if target is not None:
            os.close(target)
        os.close(parent)
    return {"sha256": digest, "diagnostic": payload}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-root", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--seconds", type=float, required=True)
    args = parser.parse_args()
    try:
        export_failure(args.job_root, args.destination, deadline_seconds=args.seconds)
    except Exception:
        raise SystemExit(1) from None
