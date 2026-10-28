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
CODES = CODES | frozenset(['UNCLASSIFIED_EXCEPTION', 'CAPTURE_ASSET_HTTP_FAILED', 'CAPTURE_PAGE_TIMEOUT', 'CAPTURE_PAGE_CRASH', 'CAPTURE_PAGE_CLOSED', 'CAPTURE_EVALUATION_TRANSPORT_FAILED', 'CAPTURE_DIAGNOSTIC_SCHEMA_INVALID', 'DIAGNOSTIC_STORAGE_PERMISSION', 'DIAGNOSTIC_STORAGE_NO_SPACE', 'DIAGNOSTIC_STORAGE_TOO_LARGE', 'DIAGNOSTIC_STORAGE_IO', 'GCUBE_ACTUAL_NATIVE_RUNTIME_REQUIRED', 'GCUBE_ACTUAL_RENDERER_INFO_REQUIRED', 'GCUBE_INITIAL_SEGMENT_REQUIRED', 'GCUBE_NATIVE_CONTEXT_REQUIRED', 'GCUBE_NATIVE_DRAW_FAILED', 'GCUBE_NATIVE_READBACK_INVALID', 'GCUBE_NATIVE_REPEATED_PIXEL_MISMATCH', 'GCUBE_NATIVE_STABILITY_DRAWS_INVALID', 'GCUBE_NATIVE_STABILITY_PROOF_REQUIRED', 'GCUBE_NVIDIA_RENDERER_REQUIRED', 'GCUBE_NVIDIA_VULKAN_REQUIRED', 'GCUBE_STABILITY_INITIAL_FRAME_REQUIRED', 'GCUBE_REVIEW_DEADLINE_EXCEEDED', 'UP2_WEBGL2_REQUIRED', 'UP2_BLACK_FRAME', 'UP2_FRAME_GL_ERROR', 'UP2_ENCODER_EARLY_EXIT', 'UP2_ENCODER_CLOSED', 'UP2_PRIVATE_PLAYWRIGHT_REQUIRED', 'UP2_ACTUAL_DRAW_GL_ERROR', 'UP2_ACTUAL_FEATURE_PIXELS_MISSING', 'UP2_ACTUAL_NATIVE_SOURCE_REQUIRED', 'UP2_ANALYSIS_PROJECTION_MISMATCH', 'UP2_AREA_NOT_DRAWN', 'UP2_AREA_SOURCE_FOOTPRINT_OUTSIDE_SAFE', 'UP2_BROWSER_CAMERA_TRANSPORT_DRIFT', 'UP2_CAMERA_KEYFRAME_TRANSPORT_CHANGED', 'UP2_CAMERA_OWNER_REQUIRED', 'UP2_CANONICAL_CANVAS_REQUIRED', 'UP2_CPU_CAMERA_SAMPLES_REQUIRED', 'UP2_CPU_CAMERA_SAMPLE_INVALID', 'UP2_CURRENT_COORDINATE_MISMATCH', 'UP2_CURRENT_LAYOUT_FAILED', 'UP2_CURRENT_SOURCE_COVERAGE_FAILED', 'UP2_ENGINE_FRAME_BINDING_REQUIRED', 'UP2_ENGINE_UNSUPPORTED', 'UP2_FLOW_OBJECT_NOT_DRAWN', 'UP2_FLOW_ROUTE_NOT_DRAWN', 'UP2_FRAME_NOT_DRAWN', 'UP2_FRAME_RANGE', 'UP2_FREE_FRAME_SCOPE', 'UP2_MARKER_RESERVATION_CAPACITY', 'UP2_ORIGINAL_MARKER_DESIGN_REQUIRED', 'UP2_SOURCE_BINDING_REQUIRED', 'UP2_SOURCE_MUTATION', 'UP2_SUPPLIED_MARKER_FULL_ROI_OUTSIDE_SAFE'])
LIMIT = 65536


def safe_code(value):
    return value if isinstance(value, str) and value in CODES else None


OPERATIONS = frozenset({"INPUT_CANVAS", "RUNTIME_IMPORT", "RUNTIME_CREATE", "WEBGL_CONTEXT",
    "RENDERER_IDENTIFICATION", "MAP_TEXTURE_PREPARATION", "GRAPHICS_PREPARATION", "NATIVE_GUARD_IMPORT",
    "NATIVE_CONTEXT_PROOF", "DRAW", "READBACK", "PROOF_VALIDATION", "PNG", "ENCODER", "EXPORT", "CLEANUP"})
SOURCES = frozenset({"CAPTURE_ADAPTER", "PRESENTATION_RUNTIME", "NATIVE_GUARD"})
FAILURE_KINDS = frozenset({"DOMAIN_ERROR", "UNCLASSIFIED_EXCEPTION", "MODULE_IMPORT_FAILURE", "ASSET_HTTP_FAILURE",
    "PAGE_TIMEOUT", "PAGE_CRASH", "PAGE_CLOSED", "EVALUATION_TRANSPORT_FAILURE", "STORAGE_FAILURE"})
EXCEPTIONS = frozenset({"Error", "TypeError", "RangeError", "ReferenceError", "SyntaxError", "TimeoutError", "DOMException", "UNKNOWN"})

def safe_failure(value):
    if (not isinstance(value, dict) or value.get("operationId") not in OPERATIONS
            or value.get("sourceId") not in SOURCES):
        return None
    code = safe_code(value.get("errorCode")) or "UNCLASSIFIED_EXCEPTION"
    index = value.get("frameIndex")
    return {"operationId": value["operationId"], "sourceId": value["sourceId"], "line": None, "column": None,
        "errorCode": code, "recognized": code != "UNCLASSIFIED_EXCEPTION",
        "exceptionType": value.get("exceptionType") if value.get("exceptionType") in EXCEPTIONS else "UNKNOWN",
        "failureKind": value.get("failureKind") if value.get("failureKind") in FAILURE_KINDS else "UNCLASSIFIED_EXCEPTION",
        "frameIndex": index if type(index) is int and 0 <= index < 180 else None}

def safe_operations(value):
    if not isinstance(value, dict) or value.get("schema") != "WORLD_ENGINE_CAPTURE_OPERATIONS_V1":
        return None
    count, sequence = value.get("renderedFrames"), value.get("sequence")
    return {"schema": "WORLD_ENGINE_CAPTURE_OPERATIONS_V1",
        "operationId": value.get("operationId") if value.get("operationId") in OPERATIONS else None,
        "lastCompletedOperation": value.get("lastCompletedOperation") if value.get("lastCompletedOperation") in OPERATIONS else None,
        "firstFailure": safe_failure(value.get("firstFailure")), "cleanupFailure": safe_failure(value.get("cleanupFailure")),
        "nativeProofCompleted": value.get("nativeProofCompleted") is True,
        "renderedFrames": count if type(count) is int and 0 <= count <= 180 else None,
        "sequence": sequence if type(sequence) is int and 0 <= sequence <= 1000000 else None,
        "evidenceStatus": value.get("evidenceStatus") if value.get("evidenceStatus") in {"LOCAL_ATOMIC_CHECKPOINT", "LOCAL_WRITE_FAILED", "NOT_WRITTEN"} else "UNKNOWN",
        "storageError": value.get("storageError") if value.get("storageError") in {"DIAGNOSTIC_STORAGE_PERMISSION", "DIAGNOSTIC_STORAGE_NO_SPACE", "DIAGNOSTIC_STORAGE_TOO_LARGE", "DIAGNOSTIC_STORAGE_IO"} else None}


def storage_exit_code(error):
    import errno
    if isinstance(error, TimeoutError):
        return 25
    if isinstance(error, OSError):
        if error.errno in (errno.EACCES, errno.EPERM):
            return 21
        if error.errno in (errno.ENOSPC, errno.EDQUOT):
            return 22
        if error.errno == errno.EFBIG:
            return 23
    return 24


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
    checkpoint = read_json_safe(job / "capture" / "CAPTURE_OPERATION_CHECKPOINT.json")
    operations = safe_operations(checkpoint) or safe_operations((receipt or {}).get("captureOperations"))
    inner = (operations or {}).get("firstFailure")
    failure = (receipt or {}).get("failure")
    text = failure.get("code") if isinstance(failure, dict) else None
    code = (first or {}).get("code")
    stage = (first or {}).get("stage")
    frames = (receipt or {}).get("renderedFrames")
    raw_stage = failure.get("diagnosticStage") if isinstance(failure, dict) else None
    safe_stage = raw_stage if type(raw_stage) is str and raw_stage in DIAGNOSTIC_STAGES else None
    payload = {"schema": "WORLD_ENGINE_CAPTURE_DIAGNOSTIC_SAFE_V3",
        "firstFailure": {"code": safe_code(code), "stage": stage if isinstance(stage, str) and stage in STAGES else None,
            "unrecognizedCode": code is not None and safe_code(code) is None},
        "supervisor": {"reason": safe_code(supervisor.get("reason")), "cleanupVerified": True},
        "capture": {"code": inner["errorCode"] if inner else (safe_code(text) or "UNCLASSIFIED_EXCEPTION"), "messageCategory": message_category(text),
            "operations": operations,
            "diagnosticStage": safe_stage,
            "renderedFrames": frames if type(frames) is int and 0 <= frames <= 180 else (operations or {}).get("renderedFrames"),
            "nvidiaVerified": (receipt or {}).get("nvidiaVerified") is True},
        "missingEvidence": {"first": first is None, "capture": receipt is None, "checkpoint": checkpoint is None}}
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
            temporary = "." + name + ".tmp"
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=target)
            with os.fdopen(fd, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.rename(temporary, name, src_dir_fd=target, dst_dir_fd=target)
            os.fsync(target)
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
    except Exception as error:
        raise SystemExit(storage_exit_code(error)) from None
