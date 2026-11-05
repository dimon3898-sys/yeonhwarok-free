"""Read bounded private evidence; publish fixed-schema, non-secret diagnostics.
Production callers MUST use capture_diagnostics_safe.export_after_cleanup, which
isolates filesystem I/O in a time-bounded child. No raw logs are read or exported.
"""
import argparse
import hashlib
import json
import os
import re
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
    "NATIVE_CONTEXT_PROOF", "DRAW", "READBACK", "PROOF_VALIDATION", "PNG", "ENCODER", "ENCODER_WRITE", "ENCODER_DRAIN", "PROGRESS", "PAGE_EVALUATION", "EXPORT", "CLEANUP"})
SOURCES = frozenset({"CAPTURE_ADAPTER", "PRESENTATION_RUNTIME", "NATIVE_GUARD"})
FAILURE_KINDS = frozenset({"DOMAIN_ERROR", "UNCLASSIFIED_EXCEPTION", "MODULE_IMPORT_FAILURE", "ASSET_HTTP_FAILURE",
    "PAGE_TIMEOUT", "PAGE_CRASH", "PAGE_CLOSED", "EVALUATION_TRANSPORT_FAILURE", "STORAGE_FAILURE"})
EXCEPTIONS = frozenset({"Error", "TypeError", "RangeError", "ReferenceError", "SyntaxError", "TimeoutError", "DOMException", "UNKNOWN"})

def frame_limit(value):
    # Diagnostic bounds never authorize a capture. Only the explicit supported
    # 10s/300 pair extends the default six-second diagnostic range.
    return 300 if (isinstance(value, dict) and type(value.get("durationSeconds")) is int
        and value["durationSeconds"] == 10 and type(value.get("totalFrames")) is int
        and value["totalFrames"] == 300) else 180


def safe_failure(value, *, total_frames=180):
    if (type(total_frames) is not int or total_frames not in (180, 300)
            or not isinstance(value, dict) or value.get("operationId") not in OPERATIONS
            or value.get("sourceId") not in SOURCES):
        return None
    code = safe_code(value.get("errorCode")) or "UNCLASSIFIED_EXCEPTION"
    index = value.get("frameIndex")
    return {"operationId": value["operationId"], "sourceId": value["sourceId"], "line": None, "column": None,
        "errorCode": code, "recognized": code != "UNCLASSIFIED_EXCEPTION",
        "exceptionType": value.get("exceptionType") if value.get("exceptionType") in EXCEPTIONS else "UNKNOWN",
        "failureKind": value.get("failureKind") if value.get("failureKind") in FAILURE_KINDS else "UNCLASSIFIED_EXCEPTION",
        "frameIndex": index if type(index) is int and 0 <= index < total_frames else None}

def safe_identifier(value, pattern):
    return value if type(value) is str and re.fullmatch(pattern, value) else None


def safe_operations(value):
    if not isinstance(value, dict) or value.get("schema") != "WORLD_ENGINE_CAPTURE_OPERATIONS_V1":
        return None
    total_frames = frame_limit(value)
    count, sequence = value.get("renderedFrames"), value.get("sequence")
    observed = value.get("observedAtUnixMs")
    index, phase = value.get("frameIndex"), value.get("operationPhase")
    result = {"schema": "WORLD_ENGINE_CAPTURE_OPERATIONS_V1",
        "runId": safe_identifier(value.get("runId"), r"studio-[a-f0-9]{32}"),
        "imageDigest": safe_identifier(value.get("imageDigest"), r"sha256:[a-f0-9]{64}"),
        "sceneSHA256": safe_identifier(value.get("sceneSHA256"), r"[a-f0-9]{64}"),
        "observedAtUnixMs": observed if type(observed) is int and 0 <= observed <= 9007199254740991 else None,
        "operationId": value.get("operationId") if value.get("operationId") in OPERATIONS else None,
        "operationPhase": phase if type(phase) is str and phase in {"START", "END", "FAIL", "CLEANUP_FAIL"} else None,
        "frameIndex": index if type(index) is int and 0 <= index < total_frames else None,
        "lastCompletedOperation": value.get("lastCompletedOperation") if value.get("lastCompletedOperation") in OPERATIONS else None,
        "firstFailure": safe_failure(value.get("firstFailure"), total_frames=total_frames),
        "cleanupFailure": safe_failure(value.get("cleanupFailure"), total_frames=total_frames),
        "nativeProofCompleted": value.get("nativeProofCompleted") is True,
        "renderedFrames": count if type(count) is int and 0 <= count <= total_frames else None,
        "sequence": sequence if type(sequence) is int and 0 <= sequence <= 1000000 else None,
        "evidenceStatus": value.get("evidenceStatus") if value.get("evidenceStatus") in {"LOCAL_ATOMIC_CHECKPOINT", "LOCAL_WRITE_FAILED", "NOT_WRITTEN"} else "UNKNOWN",
        "storageError": value.get("storageError") if value.get("storageError") in {"DIAGNOSTIC_STORAGE_PERMISSION", "DIAGNOSTIC_STORAGE_NO_SPACE", "DIAGNOSTIC_STORAGE_TOO_LARGE", "DIAGNOSTIC_STORAGE_IO"} else None}
    if total_frames == 300:
        result.update(durationSeconds=10, totalFrames=300)
    return result


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


def safe_capture_failure(value, *, total_frames=180):
    """Export fixed codes/templates only; the original message stays private.

    Playwright prefixes engine exceptions with an API and an exception class.
    Removing only those exact prefixes recovers reviewed domain codes without
    accepting arbitrary uppercase text as a public error code.
    """
    if not isinstance(value, dict) or not isinstance(value.get("code"), str):
        return None
    original = value["code"][:4000]
    first_line = original.splitlines()[0] if original else ""
    category = message_category(original)
    remainder = first_line
    api = ""
    for prefix in ("page.evaluate:", "browserType.launch:", "page.goto:", "browser.newPage:"):
        if remainder.startswith(prefix):
            api = prefix
            remainder = remainder[len(prefix):].lstrip()
            break
    exception_type = "UNKNOWN"
    for name in sorted(EXCEPTIONS - {"UNKNOWN"}, key=len, reverse=True):
        prefix = name + ":"
        if remainder.startswith(prefix):
            exception_type = name
            remainder = remainder[len(prefix):].lstrip()
            break
    code = safe_code(remainder) or "UNCLASSIFIED_EXCEPTION"
    reason = "DOMAIN_ERROR" if code != "UNCLASSIFIED_EXCEPTION" else "UNCLASSIFIED"
    # Only fixed prefixes are recognized; no caller-controlled suffix survives.
    if reason == "UNCLASSIFIED":
        for prefix, candidate in (
                ("Cannot read properties of undefined", "UNDEFINED_PROPERTY_READ"),
                ("Cannot read properties of null", "NULL_PROPERTY_READ"),
                ("Failed to fetch dynamically imported module", "MODULE_IMPORT_FAILED"),
                ("Failed to resolve module specifier", "MODULE_SPECIFIER_UNRESOLVED"),
                ("Target page, context or browser has been closed", "PAGE_OR_BROWSER_CLOSED")):
            if remainder.startswith(prefix):
                reason = candidate
                break
        if reason == "UNCLASSIFIED" and exception_type == "TypeError" and remainder.endswith(" is not a function"):
            reason = "NOT_A_FUNCTION"
        if reason == "UNCLASSIFIED" and exception_type == "ReferenceError":
            reason = "REFERENCE_ERROR"
        if reason == "UNCLASSIFIED" and exception_type == "SyntaxError":
            reason = "SYNTAX_ERROR"
    stage = value.get("diagnosticStage")
    index = value.get("frameIndex")
    return {"code": code, "diagnosticStage": stage if type(stage) is str and stage in DIAGNOSTIC_STAGES else None,
        "frameIndex": index if type(index) is int and 0 <= index < total_frames else None,
        "exceptionType": exception_type, "reason": reason,
        "message": ((api + " ") if api else "") + exception_type + ": " + (code if code != "UNCLASSIFIED_EXCEPTION" else "[REDACTED]"),
        "messageSHA256": hashlib.sha256(original.encode("utf-8", errors="replace")).hexdigest()}



# Runtime evidence is additive: legacy failure classification and cleanup gates
# keep their original meaning. Metadata never attests a remote image or GPU PASS.
SAFE_PROFILE_ARGS = frozenset({"--disable-dev-shm-usage", "--headless", "--headless=new",
    "--enable-gpu", "--enable-webgl", "--use-gl=angle", "--use-angle=vulkan",
    "--use-vulkan=native", "--enable-features=Vulkan", "--disable-vulkan-surface",
    "--disable-software-rasterizer", "--no-sandbox", "--disable-setuid-sandbox",
    "--enable-unsafe-swiftshader", "--disable-gpu", "--disable-webgl", "--disable-webgl2"})
SAFE_GPU_MODELS = frozenset({"NVIDIA GeForce RTX 4080 SUPER", "NVIDIA GeForce RTX 4080",
    "NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 5090", "NVIDIA RTX A6000",
    "NVIDIA A100-SXM4-40GB", "NVIDIA A100-SXM4-80GB", "NVIDIA H100 80GB HBM3"})


def bounded_int(value, minimum=0, maximum=1000000):
    return value if type(value) is int and minimum <= value <= maximum else None


def safe_dependencies(value):
    if not isinstance(value, dict):
        return None
    return {key: safe_identifier(value.get(key), r"v?[0-9]{1,4}(?:\.[0-9]{1,4}){2,3}(?:-[0-9]{1,4})?")
            for key in ("node", "playwright", "chromium")}


def safe_browser_profile(value):
    if not isinstance(value, dict):
        return None
    args = value.get("selectedArgs")
    source = args if type(args) is list else []
    selected = [arg for arg in source[:64] if type(arg) is str and arg in SAFE_PROFILE_ARGS]
    return {"backend": value.get("backend") if value.get("backend") in ("vulkan",) else None,
        "rootTestOnly": value.get("rootTestOnly") if type(value.get("rootTestOnly")) is bool else None,
        "sandbox": value.get("sandbox") if value.get("sandbox") in ("CHROMIUM_SANDBOX", "EXPLICIT_ROOT_TEST_ONLY") else None,
        "selectedArgs": selected, "omittedArgumentCount": len(source) - len(selected),
        "selectedArgsFullyRetained": type(args) is list and len(selected) == len(args),
        "scope": "PROFILE_SELECTED_ARGS_NOT_FINAL_ARGV"}


def safe_gpu_allocation(value):
    if not isinstance(value, dict):
        return None
    model = value.get("model")
    return {"model": model if type(model) is str and model in SAFE_GPU_MODELS else None,
        "modelRecognized": type(model) is str and model in SAFE_GPU_MODELS,
        "driverVersion": safe_identifier(value.get("driverVersion"), r"[0-9]{1,4}(?:\.[0-9]{1,4}){1,3}"),
        "memoryTotalMiB": bounded_int(value.get("memoryTotalMiB"), 1, 1048576),
        "uuidSHA256": safe_identifier(value.get("uuidSHA256"), r"[a-f0-9]{64}"),
        "scope": "ALLOCATION_METADATA_NOT_GRAPHICS_INITIALIZATION_PROOF"}



# Revalidate private collector fields before crossing the public export boundary.
DIAGNOSTIC_EXECUTABLES = frozenset(['/opt/google/chrome/chrome',
 '/opt/google/chrome/google-chrome',
 '/usr/bin/chromium',
 '/usr/bin/chromium-browser',
 '/usr/bin/google-chrome',
 '/usr/bin/google-chrome-stable'])
DIAGNOSTIC_ARGS = frozenset(['--disable-dev-shm-usage',
 '--disable-gpu',
 '--disable-gpu-sandbox',
 '--disable-setuid-sandbox',
 '--disable-software-rasterizer',
 '--disable-vulkan-surface',
 '--disable-webgl',
 '--enable-automation',
 '--enable-features=CDPScreenshotNewSurface',
 '--enable-features=Vulkan',
 '--enable-gpu',
 '--enable-unsafe-swiftshader',
 '--enable-webgl',
 '--headless',
 '--headless=new',
 '--headless=old',
 '--ignore-gpu-blocklist',
 '--no-sandbox',
 '--remote-debugging-pipe',
 '--use-angle=default',
 '--use-angle=gl',
 '--use-angle=gl-egl',
 '--use-angle=gles',
 '--use-angle=swiftshader',
 '--use-angle=vulkan',
 '--use-gl=angle',
 '--use-gl=desktop',
 '--use-gl=egl',
 '--use-vulkan=native',
 '--use-vulkan=swiftshader'])
DIAGNOSTIC_NATIVE_CODES = frozenset(['EGL_BAD_ACCESS',
 'EGL_BAD_ALLOC',
 'EGL_BAD_ATTRIBUTE',
 'EGL_BAD_CONFIG',
 'EGL_BAD_CONTEXT',
 'EGL_BAD_CURRENT_SURFACE',
 'EGL_BAD_DISPLAY',
 'EGL_BAD_MATCH',
 'EGL_BAD_NATIVE_PIXMAP',
 'EGL_BAD_NATIVE_WINDOW',
 'EGL_BAD_PARAMETER',
 'EGL_BAD_SURFACE',
 'EGL_CONTEXT_LOST',
 'EGL_NOT_INITIALIZED',
 'GL_CONTEXT_LOST',
 'GL_INVALID_ENUM',
 'GL_INVALID_FRAMEBUFFER_OPERATION',
 'GL_INVALID_OPERATION',
 'GL_INVALID_VALUE',
 'GL_OUT_OF_MEMORY',
 'VK_ERROR_DEVICE_LOST',
 'VK_ERROR_EXTENSION_NOT_PRESENT',
 'VK_ERROR_FEATURE_NOT_PRESENT',
 'VK_ERROR_FORMAT_NOT_SUPPORTED',
 'VK_ERROR_INCOMPATIBLE_DRIVER',
 'VK_ERROR_INITIALIZATION_FAILED',
 'VK_ERROR_LAYER_NOT_PRESENT',
 'VK_ERROR_MEMORY_MAP_FAILED',
 'VK_ERROR_NATIVE_WINDOW_IN_USE_KHR',
 'VK_ERROR_OUT_OF_DEVICE_MEMORY',
 'VK_ERROR_OUT_OF_HOST_MEMORY',
 'VK_ERROR_SURFACE_LOST_KHR',
 'VK_ERROR_UNKNOWN'])
DIAGNOSTIC_NATIVE_FUNCTIONS = frozenset(['CreateVulkanDevice',
 'CreateVulkanInstance',
 'GetPlatformDisplay',
 'InitializeGLOneOff',
 'InitializeSandbox',
 'InitializeVulkan',
 'eglCreateContext',
 'eglGetDisplay',
 'eglInitialize',
 'eglMakeCurrent',
 'vkCreateDevice',
 'vkCreateInstance',
 'vkEnumeratePhysicalDevices',
 'vkGetDeviceProcAddr',
 'vkGetInstanceProcAddr'])
DIAGNOSTIC_SIGNALS = frozenset(['SIGABRT',
 'SIGBUS',
 'SIGFPE',
 'SIGILL',
 'SIGINT',
 'SIGKILL',
 'SIGPIPE',
 'SIGQUIT',
 'SIGSEGV',
 'SIGTERM',
 'SIGTRAP',
 'SIGXCPU',
 'SIGXFSZ'])
DIAGNOSTIC_DRIVER_CAPABILITIES = frozenset(['all', 'compat32', 'compute', 'display', 'graphics', 'utility', 'video'])


def safe_string_list(value, allowed, maximum):
    return [item for item in value[:maximum] if type(item) is str and item in allowed] if type(value) is list else []


def safe_browser_diagnostics(value):
    if (not isinstance(value, dict) or value.get("schema") != "WORLD_ENGINE_BROWSER_DIAGNOSTIC_V1"
            or value.get("source") != "PLAYWRIGHT_BROWSER_STDIO"):
        return None
    executable = value.get("executable")
    executable = executable if isinstance(executable, dict) else {}
    known_path = executable.get("knownPath")
    known_path = known_path if type(known_path) is str and known_path in DIAGNOSTIC_EXECUTABLES else None
    browser_exit = value.get("browserExit")
    browser_exit = browser_exit if isinstance(browser_exit, dict) else {}
    args = value.get("safeActualArgs")
    args = args if type(args) is list else []
    safe_args = safe_string_list(args, DIAGNOSTIC_ARGS, 64)
    source_errors = value.get("nativeErrors")
    source_errors = source_errors if type(source_errors) is list else []
    errors = []
    for event in source_errors[:32]:
        if not isinstance(event, dict) or event.get("category") not in (
                "VULKAN", "EGL", "OPENGL", "DEVICE_ACCESS", "SANDBOX", "ANGLE", "GPU_PROCESS"):
            continue
        errors.append({"category": event["category"],
            "codes": safe_string_list(event.get("codes"), DIAGNOSTIC_NATIVE_CODES, 32),
            "functions": safe_string_list(event.get("functions"), DIAGNOSTIC_NATIVE_FUNCTIONS, 16),
            "lineSHA256": safe_identifier(event.get("lineSHA256"), r"[a-f0-9]{64}")})
    env = value.get("graphicsEnvironment")
    env = env if isinstance(env, dict) else {}
    environment = {
        "gpuBackend": env.get("gpuBackend") if env.get("gpuBackend") in ("vulkan", "egl") else None,
        "renderMode": env.get("renderMode") if env.get("renderMode") in ("gpu-required", "cpu") else None,
        "driverCapabilities": safe_string_list(env.get("driverCapabilities"), DIAGNOSTIC_DRIVER_CAPABILITIES, 7),
        "deviceSelectionClass": env.get("deviceSelectionClass") if env.get("deviceSelectionClass") in ("NOT_SET", "ALL", "NONE", "EXPLICIT") else None,
        "deviceSelectionSHA256": safe_identifier(env.get("deviceSelectionSHA256"), r"[a-f0-9]{64}"),
        "vulkanICDOverrideSHA256": safe_identifier(env.get("vulkanICDOverrideSHA256"), r"[a-f0-9]{64}"),
        "uid": bounded_int(env.get("uid"), 0, 4294967295),
        "gid": bounded_int(env.get("gid"), 0, 4294967295),
        "nativeGraphicsInitializationVerified": False}
    for key in ("vulkanICDOverrideSet", "libraryPathSet", "runtimeDirSet", "displaySet"):
        environment[key] = env.get(key) if type(env.get(key)) is bool else None
    signal_value = browser_exit.get("signal")
    omitted = bounded_int(value.get("omittedArgumentCount"))
    return {"schema": "WORLD_ENGINE_BROWSER_DIAGNOSTIC_V1", "source": "PLAYWRIGHT_BROWSER_STDIO",
        "launchObserved": value.get("launchObserved") is True,
        "executable": {"knownPath": known_path,
            "basename": Path(known_path).name if known_path else None,
            "pathSHA256": safe_identifier(executable.get("pathSHA256"), r"[a-f0-9]{64}")},
        "safeActualArgs": safe_args,
        "omittedArgumentCount": min(1000000, (omitted or 0) + len(args) - len(safe_args)),
        "argumentLineSHA256": safe_identifier(value.get("argumentLineSHA256"), r"[a-f0-9]{64}"),
        "fullArgvCaptured": False,
        "browserExit": {"exitCode": bounded_int(browser_exit.get("exitCode"), -255, 255),
            "signal": signal_value if type(signal_value) is str and signal_value in DIAGNOSTIC_SIGNALS else None,
            "observed": browser_exit.get("observed") is True},
        "nativeErrors": errors,
        "observedLines": bounded_int(value.get("observedLines")),
        "droppedLines": bounded_int(value.get("droppedLines")),
        "truncated": value.get("truncated") is True or len(args) > 64 or len(source_errors) > 32,
        "expectedImageDigest": safe_identifier(value.get("expectedImageDigest"), r"sha256:[a-f0-9]{64}"),
        "graphicsEnvironment": environment}


def runtime_evidence(job, receipt, supervisor, plan, allocation, process=None, browser_snapshot=None):
    profile = plan.get("renderProfile") if isinstance(plan, dict) else None
    expected = safe_identifier(profile.get("imageDigest"), r"sha256:[a-f0-9]{64}") if isinstance(profile, dict) else None
    browser = safe_browser_diagnostics(supervisor.get("browserDiagnostics")) or safe_browser_diagnostics(browser_snapshot)
    environment_digest = browser.get("expectedImageDigest") if browser else None
    expected_source = "PLAN" if expected else "CAPTURE_ENVIRONMENT" if environment_digest else "MISSING"
    expected_agree = expected == environment_digest if expected and environment_digest else None
    expected = expected or environment_digest
    exit_code = bounded_int(supervisor.get("captureProcessExitCode"), -255, 255)
    exit_source = "SUPERVISOR" if exit_code is not None else "MISSING"
    if exit_code is None and isinstance(process, dict):
        exit_code = bounded_int(process.get("exitCode"), -255, 255)
        if exit_code is not None:
            exit_source = "CAPTURE_PROCESS_RESULT"
    return {"schema": "WORLD_ENGINE_CAPTURE_RUNTIME_EVIDENCE_V1",
        "jobId": safe_identifier(job.name, r"studio-[a-f0-9]{32}"),
        "dependencies": safe_dependencies((receipt or {}).get("dependencies")),
        "browserProfile": safe_browser_profile((receipt or {}).get("browserProfile")),
        "gpuAllocation": safe_gpu_allocation(allocation),
        "imageIdentity": {"expectedImageDigest": expected,
            "expectedSource": expected_source, "captureEnvironmentExpectedImageDigest": environment_digest,
            "expectedDigestsAgree": expected_agree,
            "actualImageDigest": None, "actualImageStatus": "NOT_OBSERVED_FROM_APPLICATION_PROCESS"},
        "captureProcess": {"exitCode": exit_code, "source": exit_source,
            "status": "OBSERVED" if exit_code is not None else "NOT_RECORDED",
            "scope": "CAPTURE_NODE_PROCESS_NOT_BROWSER_PROCESS"},
        "browserDiagnostics": browser,
        "missingEvidence": {"plan": plan is None, "gpuAllocation": allocation is None,
            "browserDiagnostics": browser is None},
        "persistenceScope": "SHARED_EXPORT_WRITE_NOT_REMOTE_BACKUP_ATTESTATION"}


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
    plan = read_json_safe(job / "PLAN.json")
    allocation = read_json_safe(job / "GPU_ALLOCATION.json")
    process = read_json_safe(job / "CAPTURE_PROCESS_RESULT.json")
    browser_snapshot = read_json_safe(job / "BROWSER_DIAGNOSTIC.json")
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
            "failure": safe_capture_failure(failure, total_frames=frame_limit(receipt)),
            "renderedFrames": frames if type(frames) is int and 0 <= frames <= frame_limit(receipt) else (operations or {}).get("renderedFrames"),
            "nvidiaVerified": (receipt or {}).get("nvidiaVerified") is True},
        "missingEvidence": {"first": first is None, "capture": receipt is None, "checkpoint": checkpoint is None},
        "runtimeEvidence": runtime_evidence(job, receipt, supervisor, plan, allocation, process, browser_snapshot)}
    content = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(content) > LIMIT:
        raise OSError(27, "DIAGNOSTIC_STORAGE_TOO_LARGE")
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


def preserve_private_pending(job_root, *, deadline_seconds=1):
    """Write-once safe evidence INSIDE the private job, never an export permit.

    Cleanup remains unconfirmed. Existing post-cleanup export gates are unchanged.
    No raw stderr, state/approval file, token or caller-selected destination is read.
    """
    if type(deadline_seconds) not in (float, int) or not 0 < deadline_seconds <= 1:
        raise ValueError("DIAGNOSTIC_DEADLINE_INVALID")
    end = time.monotonic() + deadline_seconds
    def check():
        if time.monotonic() >= end:
            raise TimeoutError("DIAGNOSTIC_DEADLINE_EXCEEDED")
    job = Path(job_root)
    if not re.fullmatch(r"studio-[a-f0-9]{32}", job.name) or job.parent.name != "handoff-gpu-jobs":
        raise ValueError("DIAGNOSTIC_JOB_ID_INVALID")
    parent = directory_fd(job)
    temporary = None
    try:
        info = os.fstat(parent)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("DIAGNOSTIC_PRIVATE_JOB_REQUIRED")
        # An existing record wins, including under concurrent status readers.
        try:
            os.stat("CAPTURE_DIAGNOSTIC_PENDING.json", dir_fd=parent, follow_symlinks=False)
            return "ALREADY_PRESERVED"
        except FileNotFoundError:
            pass
        check()
        first = read_json_safe(job / "FIRST_CAPTURE_FAILURE.json")
        supervisor = read_json_safe(job / "LEASE_SUPERVISOR_RESULT.json") or {}
        if first is None and isinstance(supervisor.get("firstFailure"), dict):
            first = supervisor["firstFailure"]
        operations = safe_operations(read_json_safe(job / "capture" / "CAPTURE_OPERATION_CHECKPOINT.json"))
        inner = (operations or {}).get("firstFailure")
        if first is None and inner is None:
            return "NO_FIRST_FAILURE_EVIDENCE"
        code, stage = (first or {}).get("code"), (first or {}).get("stage")
        payload = {"schema": "WORLD_ENGINE_PRIVATE_PENDING_DIAGNOSTIC_V1",
            "cleanupStatus": "UNCONFIRMED_NOT_AN_EXPORT_AUTHORIZATION",
            "firstFailure": inner,
            "supervisorFirstFailure": {"code": safe_code(code),
                "stage": stage if type(stage) is str and stage in STAGES else None,
                "unrecognizedCode": code is not None and safe_code(code) is None},
            "operations": operations}
        body = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(body) > LIMIT:
            raise OSError(27, "DIAGNOSTIC_STORAGE_TOO_LARGE")
        check()
        # Unique temp + link provides complete, atomic, no-replace publication.
        temporary = ".pending-diagnostic-" + os.urandom(12).hex()
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
        check()
        try:
            os.link(temporary, "CAPTURE_DIAGNOSTIC_PENDING.json", src_dir_fd=parent,
                    dst_dir_fd=parent, follow_symlinks=False)
        except FileExistsError:
            return "ALREADY_PRESERVED"
        os.unlink(temporary, dir_fd=parent); temporary = None
        os.fsync(parent)
        return "PRIVATE_PENDING_PRESERVED"
    finally:
        try:
            if temporary is not None:
                os.unlink(temporary, dir_fd=parent)
        finally:
            os.close(parent)


def export_active_checkpoint(job_root, destination, *, deadline_seconds=1):
    """Publish only an allowlisted in-progress checkpoint, not a cleanup permit.

    A single atomic envelope keeps its canonical snapshot hash with its content
    even if the container stops between writes. No raw job/log data leaves.
    Production invokes this in the existing bounded, empty-environment helper.
    """
    if type(deadline_seconds) not in (float, int) or not 0 < deadline_seconds <= 1:
        raise ValueError("DIAGNOSTIC_DEADLINE_INVALID")
    until = time.monotonic() + deadline_seconds
    def check():
        if time.monotonic() >= until:
            raise TimeoutError("DIAGNOSTIC_DEADLINE_EXCEEDED")
    job, dest = Path(job_root), Path(destination)
    if (not re.fullmatch(r"studio-[a-f0-9]{32}", job.name)
            or job.parent.name != "handoff-gpu-jobs"
            or dest.name != "capture-checkpoint-" + job.name):
        raise ValueError("DIAGNOSTIC_JOB_ID_INVALID")
    private = directory_fd(job)
    try:
        info = os.fstat(private)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("DIAGNOSTIC_PRIVATE_JOB_REQUIRED")
    finally:
        os.close(private)
    check()
    operations = safe_operations(read_json_safe(job / "capture" / "CAPTURE_OPERATION_CHECKPOINT.json"))
    if (operations is None or operations.get("runId") != job.name
            or type(operations.get("sequence")) is not int or operations["sequence"] < 1
            or operations.get("operationId") not in OPERATIONS
            or operations.get("operationPhase") not in {"START", "END", "FAIL", "CLEANUP_FAIL"}):
        raise ValueError("CAPTURE_DIAGNOSTIC_SCHEMA_INVALID")
    snapshot = {"jobId": job.name, "operations": operations,
        "cleanupStatus": "UNCONFIRMED_NOT_COMPLETION_OR_EXPORT_AUTHORIZATION",
        "renderRecoveryPass": False,
        "persistenceScope": "MOUNTED_VIEW_READBACK_NOT_EXTERNAL_BACKUP_ATTESTATION"}
    canonical = lambda value: (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(canonical(snapshot)).hexdigest()
    envelope = {"schema": "WORLD_ENGINE_ACTIVE_CAPTURE_CHECKPOINT_V1",
        "snapshot": snapshot, "sha256": digest}
    body = canonical(envelope)
    if len(body) > 16384:
        raise OSError(27, "DIAGNOSTIC_STORAGE_TOO_LARGE")
    parent, target, temporary = directory_fd(dest.parent), None, None
    try:
        check()
        created = False
        try:
            os.mkdir(dest.name, mode=0o700, dir_fd=parent)
            created = True
        except FileExistsError:
            pass
        target = os.open(dest.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        info = os.fstat(target)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("DIAGNOSTIC_EXPORT_DIRECTORY_INVALID")
        if not created and os.path.lexists(dest / "CAPTURE_CHECKPOINT.json"):
            previous = read_json_safe(dest / "CAPTURE_CHECKPOINT.json")
            prior = previous.get("snapshot") if isinstance(previous, dict) else None
            if (not isinstance(prior, dict) or prior.get("jobId") != job.name
                    or previous.get("schema") != envelope["schema"]
                    or hashlib.sha256(canonical(prior)).hexdigest() != previous.get("sha256")):
                raise ValueError("DIAGNOSTIC_EXISTING_EXPORT_NOT_OWNED")
            old = (prior.get("operations") or {}).get("sequence")
            if type(old) is not int or old > operations["sequence"]:
                raise ValueError("DIAGNOSTIC_SEQUENCE_INVALID")
            if old == operations["sequence"]:
                if previous != envelope:
                    raise ValueError("DIAGNOSTIC_SEQUENCE_CHANGED")
                return {"status": "UNCHANGED", "sha256": digest}
        check()
        temporary = ".checkpoint-" + os.urandom(12).hex()
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=target)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
        check()
        os.rename(temporary, "CAPTURE_CHECKPOINT.json", src_dir_fd=target, dst_dir_fd=target)
        temporary = None
        os.fsync(target)
        check()
        if read_json_safe(dest / "CAPTURE_CHECKPOINT.json") != envelope:
            raise ValueError("DIAGNOSTIC_EXPORT_READBACK_FAILED")
        check()
        return {"status": "EXPORTED", "sha256": digest}
    finally:
        if target is not None:
            try:
                if temporary is not None:
                    os.unlink(temporary, dir_fd=target)
            finally:
                os.close(target)
        os.close(parent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-root", required=True)
    parser.add_argument("--destination")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--private-pending", action="store_true")
    mode.add_argument("--active-checkpoint", action="store_true")
    parser.add_argument("--seconds", type=float, required=True)
    args = parser.parse_args()
    try:
        if args.private_pending:
            if args.destination is not None:
                raise ValueError("DIAGNOSTIC_PRIVATE_DESTINATION_FORBIDDEN")
            preserve_private_pending(args.job_root, deadline_seconds=args.seconds)
        elif args.active_checkpoint:
            if args.destination is None:
                raise ValueError("DIAGNOSTIC_EXPORT_ROOT_INVALID")
            export_active_checkpoint(args.job_root, args.destination, deadline_seconds=args.seconds)
        else:
            export_failure(args.job_root, args.destination, deadline_seconds=args.seconds)
    except Exception as error:
        raise SystemExit(storage_exit_code(error)) from None



