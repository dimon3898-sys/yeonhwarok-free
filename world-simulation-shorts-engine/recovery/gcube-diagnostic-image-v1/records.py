"""Small, fail-closed startup records. No exception messages or environment dumps."""
from __future__ import annotations

from datetime import datetime, timezone
import errno
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

SCHEMA = "WORLD_ENGINE_STARTUP_DIAGNOSTIC_V1"
STAGES = frozenset({"BOOTSTRAP", "CONFIGURATION", "RUNTIME_DIRECTORY", "STORAGE", "UID_GID", "SOURCE_INTEGRITY",
                    "DEPENDENCY", "NVIDIA", "GRAPHICS", "CHROMIUM", "WEBGL2", "GPU_MEMORY",
                    "UNEXPECTED", "DIAGNOSTIC_SERVICE"})
# Exact known codes only: never reflect an exception's arbitrary .code or text.
REASONS = {
    "STARTUP_UNEXPECTED_EXCEPTION": "Unexpected startup failure; raw exception withheld.",
    "STARTUP_MODE_INVALID": "Startup mode must be normal or diagnostic.",
    "BOOTSTRAP_FAILED": "Startup bootstrap failed.",
    "RUNTIME_DIRECTORY_UNAVAILABLE": "Private runtime directory could not be prepared.",
    "RUNTIME_DIRECTORY_UNSAFE": "Runtime directory ownership or permissions were unsafe.",
    "STORAGE_UNAVAILABLE": "Startup storage could not be accessed.",
    "STORAGE_PERMISSION_DENIED": "Storage access or permission operation was denied.",
    "STORAGE_OWNERSHIP_INVALID": "Storage ownership was incompatible with the engine account.",
    "STORAGE_READ_ONLY": "Storage was read-only.",
    "STORAGE_PATH_UNSAFE": "Storage path did not meet private-directory requirements.",
    "UID_GID_INVALID": "Engine user or group identity was invalid.",
    "UID_GID_TRANSITION_FAILED": "Transition to the engine account failed.",
    "ENGINE_ACCOUNT_UNAVAILABLE": "The engine account was unavailable.",
    "SOURCE_CONTRACT_INVALID": "Packaged source integrity verification failed.",
    "SOURCE_INTEGRITY_FAILED": "Packaged source integrity verification failed.",
    "CPU_DEPENDENCY_CHECK_FAILED": "Required CPU dependency verification failed.",
    "DEPENDENCY_CHECK_FAILED": "Required dependency verification failed.",
    "GPU_HARDWARE_UNAVAILABLE": "Required NVIDIA hardware could not be queried.",
    "GPU_ALLOCATION_AMBIGUOUS": "A single unambiguous NVIDIA allocation was not available.",
    "GPU_IDENTITY_INVALID": "The NVIDIA allocation identity was invalid.",
    "GPU_MODEL_UNSUPPORTED": "The detected GPU model was not admitted.",
    "GPU_PHYSICAL_MEMORY_INSUFFICIENT": "Physical GPU memory was insufficient.",
    "GPU_MEMORY_QUERY_INVALID": "GPU memory telemetry was invalid.",
    "GPU_VRAM_BUDGET_EXCEEDS_AVAILABLE": "The requested GPU memory budget was unavailable.",
    "GPU_ALLOCATION_CHANGED_DURING_PROBE": "GPU allocation changed during verification.",
    "SHARED_MEMORY_UNAVAILABLE": "Shared-memory capacity could not be read.",
    "SHARED_MEMORY_INSUFFICIENT": "Shared-memory capacity was below the required minimum.",
    "GPU_GRAPHICS_RUNTIME_PREPARATION_FAILED": "EGL or Vulkan runtime preparation failed.",
    "GPU_GRAPHICS_RUNTIME_PATH_UNSAFE": "Graphics runtime paths were unsafe.",
    "GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE": "Graphics runtime paths were not writable.",
    "GPU_GRAPHICS_DRIVER_API_UNAVAILABLE": "The NVIDIA graphics driver API was unavailable.",
    "GPU_PROFILE_INVALID": "The selected graphics profile was invalid.",
    "GPU_REQUIRED_CPU_MODE_REJECTED": "CPU rendering was rejected by GPU-required admission.",
    "GPU_BROWSER_UNAVAILABLE": "The required Chromium executable was unavailable.",
    "GPU_WRAPPER_NOT_EXECUTABLE": "The Chromium hardware wrapper was not executable.",
    "GPU_BROWSER_PROBE_FAILED": "The Chromium hardware probe failed.",
    "GPU_WEBGL_UNVERIFIED": "Physical NVIDIA WebGL2 draw verification did not pass.",
    "GPU_PROBE_FINGERPRINT_INVALID": "GPU probe fingerprint verification failed.",
    "GPU_LAUNCH_FAILED": "GPU startup did not complete.",
    "DIAGNOSTIC_STORAGE_UNSAFE": "Diagnostic storage was unsafe.",
    "DIAGNOSTIC_STORAGE_UNAVAILABLE": "Diagnostic storage was unavailable.",
    "DIAGNOSTICS_EXCEED_LIMIT": "Diagnostic record size exceeded its fixed limit.",
    "INVALID_VRAM_BUDGET": "The configured GPU memory budget was invalid.",
    "INVALID_HEALTH_PORT": "The health service port was invalid.",
    "INVALID_RENDER_TIMEOUT": "The rendering deadline was invalid.",
    "DIAGNOSTIC_SERVICE_REFUSED": "Diagnostic service identity or configuration was unsafe.",
    "DIAGNOSTIC_SERVICE_FAILED": "The bounded diagnostic service could not start.",
    "DIAGNOSTIC_ONLY_REQUESTED": "Diagnostic-only mode does not admit rendering.",
    "INVALID_STARTUP_MODE": "Startup mode must be normal or diagnostic.",
    "INVALID_DIAGNOSTIC_CONFIG": "Diagnostic configuration was invalid.",
    "DIAGNOSTIC_RENDER_FORBIDDEN": "Rendering is forbidden in diagnostic mode.",
    "ACCOUNT_UNAVAILABLE": "The engine account was unavailable.",
    "STORAGE_VALIDATION_FAILED": "Storage did not meet private-directory requirements.",
    "RUNTIME_DIRECTORY_FAILED": "The private runtime directory could not be prepared.",
    "UID_GID_FAILED": "Engine account permission validation or transition failed.",
    "UNEXPECTED_STARTUP_EXCEPTION": "Unexpected startup failure; raw exception withheld.",
    "TEST_SEAM_PRODUCTION_DISPATCH_BLOCKED": "Test-only startup evidence cannot dispatch production execution.",
    "DIAGNOSTIC_ONLY": "Diagnostic-only mode does not admit rendering.",
    "DIAGNOSTIC_WORKER_TIMEOUT": "The bounded diagnostic startup worker exceeded its deadline.",
    "DIAGNOSTIC_WORKER_FAILED": "The isolated diagnostic startup worker failed.",
    "DIAGNOSTIC_WORKER_INTERRUPTED": "The isolated diagnostic startup worker was interrupted and reaped.",
    "DIAGNOSTIC_RECORD_INVALID": "The isolated startup worker produced an invalid diagnostic record.",
    "GPU_ALLOCATION_CHANGED_DURING_RENDER": "GPU allocation changed during rendering.",
    "GPU_CAPTURE_ALREADY_RUNNING": "A capture was already running under the existing lock.",
    "GPU_RENDER_DEADLINE_EXCEEDED": "Rendering exceeded its existing deadline.",
    "GPU_RENDER_INTERRUPTED": "Rendering was interrupted.",
    "GPU_RENDER_PROCESS_FAILED": "The GPU render subprocess failed.",
    "GPU_RENDER_VRAM_BUDGET_EXCEEDED": "Rendering exceeded the observed GPU memory budget.",
    "TEST_ADMISSION_NOT_EXECUTABLE": "Test-only GPU admission cannot authorize rendering.",
}
_GPU_CODES = frozenset({
    "GPU_HARDWARE_UNAVAILABLE", "GPU_WEBGL_UNVERIFIED", "GPU_BROWSER_PROBE_FAILED",
    "GPU_WRAPPER_NOT_EXECUTABLE", "GPU_BROWSER_UNAVAILABLE", "GPU_PROFILE_INVALID",
    "CPU_FALLBACK_UNVERIFIED", "NOT_RUN", "DEVICE_NODES_VISIBLE", "NVIDIA_QUERY_VISIBLE",
    "GPU_GRAPHICS_RUNTIME_PATH_UNSAFE", "GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE",
    "GPU_GRAPHICS_DRIVER_API_UNAVAILABLE", "DEVICE_NODES_ABSENT", "NVIDIA_QUERY_FAILED",
    "NVIDIA_QUERY_TIMEOUT", "CHROMIUM_STARTED", "CHROMIUM_START_FAILED", "CHROMIUM_TIMEOUT",
    "CHROMIUM_EVALUATION_FAILED", "PROBE_OUTPUT_INVALID", "DRIVER_GRAPHICS_MISSING",
    "WEBGL2_CONTEXT_CREATED", "WEBGL2_CONTEXT_UNAVAILABLE", "DEBUG_RENDERER_UNAVAILABLE",
    "SOFTWARE_RENDERER_REJECTED", "NVIDIA_RENDERER_MISSING", "NVIDIA_DEVICE_MISMATCH",
    "NVIDIA_DEVICE_MATCHED", "SOFTWARE_RENDERER_CONFIRMED", "WEBGL_DRAW_VERIFIED",
    "WEBGL_DRAW_FAILED", "GPU_PROBE_SHADER_FAILED", "GPU_PROBE_PROGRAM_FAILED", "VERIFIED"})
_EXCEPTIONS = frozenset({"OSError", "PermissionError", "FileNotFoundError", "NotADirectoryError",
    "IsADirectoryError", "FileExistsError", "ValueError", "TypeError", "ImportError",
    "ModuleNotFoundError", "RuntimeError", "BootstrapError", "LauncherError", "GPUError",
    "GraphicsRuntimeError", "TimeoutError", "SubprocessError", "CalledProcessError",
    "TimeoutExpired", "MemoryError", "KeyError", "JSONDecodeError"})


def _integer(value, maximum=2**40):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= maximum else None


def _enum(value, values):
    return value if isinstance(value, str) and value in values else None


def _safe_gpu(value, *, attempts=True):
    """Second allowlist after the unchanged engine sanitizer; no raw identities."""
    if not isinstance(value, dict) or not value:
        return {}
    result = {"schema_version": 1}
    for key, allowed in (("render_mode", {"gpu-required", "cpu"}), ("gpu_profile", {"egl", "vulkan"}),
                         ("failed_stage", set("ABCDEF")), ("reason_code", _GPU_CODES)):
        result[key] = _enum(value.get(key), allowed)
    version = value.get("browser_version")
    if isinstance(version, str) and re.fullmatch(r"\d+(?:\.\d+){1,4}", version):
        result["browser_version"] = version
    raw = value.get("webgl") if isinstance(value.get("webgl"), dict) else {}
    result["webgl"] = {key: raw.get(key) is True for key in
                        ("context_available", "webgl2", "draw_passed", "debug_renderer_available", "software_renderer")}
    for key in ("context_version", "webgl_error", "max_texture_size", "max_renderbuffer_size"):
        result["webgl"][key] = _integer(raw.get(key), 65536)
    result["webgl"]["reason_code"] = _enum(raw.get("reason_code"), _GPU_CODES)
    pixel = raw.get("pixel")
    if isinstance(pixel, list) and len(pixel) == 4 and all(_integer(n, 255) is not None for n in pixel):
        result["webgl"]["pixel"] = pixel[:]
    stages = value.get("stages") if isinstance(value.get("stages"), list) else []
    result["stages"] = [{"id": item["id"], "status": _enum(item.get("status"), {"PASS", "FAIL", "NOT_RUN"}),
                          "reason_code": _enum(item.get("reason_code"), _GPU_CODES)}
                         for item in stages[:6] if isinstance(item, dict) and _enum(item.get("id"), set("ABCDEF"))]
    result["nvidia_devices"] = []
    devices = value.get("nvidia_devices") if isinstance(value.get("nvidia_devices"), list) else []
    for item in devices[:16]:
        if not isinstance(item, dict):
            continue
        clean = {}
        driver = item.get("driver_version")
        if isinstance(driver, str) and re.fullmatch(r"\d+(?:\.\d+){1,4}", driver):
            clean["driver_version"] = driver
        memory = item.get("memory_total_mib")
        if isinstance(memory, (int, float)) and not isinstance(memory, bool) and math.isfinite(memory) and 0 < memory < 2**30:
            clean["memory_total_mib"] = memory
        # Model names are omitted rather than reflecting arbitrary vendor strings.
        result["nvidia_devices"].append(clean)
    runtime = value.get("runtime") if isinstance(value.get("runtime"), dict) else {}
    result["runtime"] = {"environment": {}, "devices": {}, "libraries": {}, "driver_delivery": {}}
    env = runtime.get("environment") if isinstance(runtime.get("environment"), dict) else {}
    for name in ("NVIDIA_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES"):
        item = env.get(name) if isinstance(env.get(name), dict) else {}
        result["runtime"]["environment"][name] = {"present": item.get("present") is True,
            "selection": _enum(item.get("selection"), {"unset", "all", "none", "index-list", "configured"})}
    for group, names in (("devices", ("nvidia", "dri")),
                         ("libraries", ("egl", "gles", "opengl", "vulkan", "nvidia_egl", "nvidia_vulkan")),
                         ("driver_delivery", ("egl_vendor_manifest", "vulkan_nvidia_icd"))):
        items = runtime.get(group) if isinstance(runtime.get(group), dict) else {}
        for name in names:
            result["runtime"][group][name] = (_integer(items.get(name), 256) or 0) if group == "devices" else items.get(name) is True
    info = value.get("system_info") if isinstance(value.get("system_info"), dict) else {}
    features = info.get("feature_status") if isinstance(info.get("feature_status"), dict) else {}
    feature_values = {"enabled", "enabled_on", "enabled_force", "disabled", "disabled_off", "disabled_software",
                      "unavailable_off", "unavailable_software", "unavailable_off_ok", "enabled_readback"}
    result["system_info"] = {"feature_status": {key: _enum(features.get(key), feature_values)
        for key in ("webgl", "webgl2", "gpu_compositing", "vulkan", "rasterization")}}
    if attempts:
        entries = value.get("profile_attempts") if isinstance(value.get("profile_attempts"), list) else []
        result["profile_attempts"] = [{"backend": item["backend"],
            "status": _enum(item.get("status"), {"failed", "verified"}),
            "error_code": _enum(item.get("error_code"), _GPU_CODES),
            "diagnostics": _safe_gpu(item.get("diagnostics"), attempts=False)}
            for item in entries[:2] if isinstance(item, dict) and _enum(item.get("backend"), {"egl", "vulkan"})]
    return result


def _engine_sanitize(value):
    try:
        from deployment.gcube.gpu import sanitize_gpu_diagnostics
    except ImportError:
        # Standalone diagnostic tests have no engine sys.path; second allowlist is independent.
        return _safe_gpu(value)
    return _safe_gpu(sanitize_gpu_diagnostics(value))


def make_record(stage, code, exit_code, *, mode="normal", errno_value=None,
                exception_type=None, gpu_diagnostics=None, test_only=False):
    code = code if isinstance(code, str) and code in REASONS else "STARTUP_UNEXPECTED_EXCEPTION"
    stage = stage if isinstance(stage, str) and stage in STAGES else "UNEXPECTED"
    exit_code = exit_code if _integer(exit_code, 255) is not None else 1
    safe = {}
    if _integer(errno_value, 4095) is not None and errno_value in errno.errorcode:
        safe["errno"] = errno_value
        safe["errnoName"] = errno.errorcode[errno_value]
    if isinstance(exception_type, str) and exception_type in _EXCEPTIONS:
        safe["exceptionType"] = exception_type
    if gpu_diagnostics:
        safe["gpu"] = _engine_sanitize(gpu_diagnostics)
    if test_only is True:
        safe["testOnly"] = True
    return {"schema": SCHEMA, "startupMode": "diagnostic" if mode == "diagnostic" else "normal",
        "status": "BLOCKED" if exit_code else "DIAGNOSTIC_ONLY", "stage": stage, "errorCode": code,
        "terminationReason": REASONS[code], "timestamp": datetime.now(timezone.utc).isoformat(),
        "exitCode": exit_code, "gpuRenderingVerified": False, "renderAllowed": False,
        "safeDiagnostics": safe}


def safe_record(record):
    """Rebuild before every output so callers cannot append unsanitized fields."""
    raw = record if isinstance(record, dict) else {}
    safe = raw.get("safeDiagnostics") if isinstance(raw.get("safeDiagnostics"), dict) else {}
    result = make_record(raw.get("stage"), raw.get("errorCode"), raw.get("exitCode"),
        mode=raw.get("startupMode"), errno_value=safe.get("errno"), exception_type=safe.get("exceptionType"),
        gpu_diagnostics=None, test_only=safe.get("testOnly") is True)
    if isinstance(safe.get("gpu"), dict):
        result["safeDiagnostics"]["gpu"] = _safe_gpu(safe["gpu"])
    stamp = raw.get("timestamp")
    if isinstance(stamp, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00", stamp):
        result["timestamp"] = stamp
    return result


def emit_record(record):
    body = json.dumps(safe_record(record), sort_keys=True, separators=(",", ":"), allow_nan=False)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.write(body + "\n")
            stream.flush()
        except (OSError, ValueError, AttributeError):
            pass


def _private_dir(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise OSError(errno.EINVAL, "unsafe diagnostic directory")
    current = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            except FileNotFoundError:
                os.mkdir(component, 0o700, dir_fd=current)
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                os.fchmod(child, 0o700)  # This component was just created by this process.
            os.close(current)
            current = child
        info = os.fstat(current)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise OSError(errno.EACCES, "unsafe diagnostic directory")
        return current
    except BaseException:
        os.close(current)
        raise


def _persist(path, record):
    directory = _private_dir(path)
    # All reads/writes/rename use the verified directory descriptor, preventing symlink substitution.
    name = ".startup-" + os.urandom(12).hex()
    final = "startup-" + os.urandom(12).hex() + ".json"
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            os.fchmod(fd, 0o600)  # Only the new, exclusively-created file; never existing storage.
            with os.fdopen(fd, "wb") as stream:
                stream.write((json.dumps(safe_record(record), sort_keys=True, allow_nan=False) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.rename(name, final, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(name, dir_fd=directory)
            except FileNotFoundError:
                pass
    finally:
        os.close(directory)


def persist_record(record, roots=None):
    roots = [Path("/world-storage/rtx-gpu-package-v1/startup-diagnostics")] if roots is None else roots
    for root in roots:
        try:
            _persist(root, record)
            return {"persisted": True, "tier": "primary"}
        except (OSError, ValueError, TypeError):
            continue
    try:
        fallback = tempfile.mkdtemp(prefix="world-engine-startup-diagnostics-", dir="/tmp")
        _persist(fallback, record)
        return {"persisted": True, "tier": "local_fallback"}
    except (OSError, ValueError, TypeError):
        return {"persisted": False, "tier": "stderr_only"}
