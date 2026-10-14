#!/usr/bin/env python3
"""Fail-closed RTX admission and a health-only container entry point.

Production always uses the unchanged native GPU/WebGL pixel probe. Injection
parameters are a unit-test seam, never command-line options or GPU evidence.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
ENGINE_ROOT = HERE.parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from deployment.gcube.chromium_wrapper import BrowserProfileError, browser_profile
from deployment.gcube.gpu import GPUError, classify_probe, sanitize_gpu_diagnostics
from deployment.gcube.graphics_runtime import GraphicsRuntimeError, prepare_graphics_runtime
from deployment.gcube.graphics_start import select_graphics_profile

GIB = 1024 ** 3
MIB = 1024 ** 2
MIN_MEMORY_MIB = 15 * 1024
RESERVED_MEMORY_BYTES = 2 * GIB
MIN_SHM_BYTES = GIB
RECOMMENDED_SHM_BYTES = 2 * GIB
DEFAULT_STORAGE_ROOT = Path("/world-storage/rtx-gpu-package-v1")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MODEL = re.compile(r"(?:NVIDIA\s+)?(?:GeForce\s+)?RTX\s+(4080\s+SUPER|4090|5090)\Z", re.I)


class LauncherError(RuntimeError):
    def __init__(self, code, *, diagnostics=None):
        self.code = code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{1,95}", code) else "ADMISSION_FAILED"
        self.diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
        super().__init__(self.code)


@dataclass(frozen=True)
class LauncherConfig:
    budget_gib: float = 8.0
    port: int = 8000
    package_root: Path = Path("/opt/rtx-package")
    storage_root: Path = DEFAULT_STORAGE_ROOT
    render_timeout_seconds: int = 3600

    def validate(self):
        try:
            budget = float(self.budget_gib)
        except (TypeError, ValueError, OverflowError):
            raise LauncherError("INVALID_VRAM_BUDGET") from None
        if isinstance(self.budget_gib, bool) or not math.isfinite(budget) or budget <= 0 or budget > 128:
            raise LauncherError("INVALID_VRAM_BUDGET")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1024 <= self.port <= 65535:
            raise LauncherError("INVALID_HEALTH_PORT")
        if (isinstance(self.render_timeout_seconds, bool) or not isinstance(self.render_timeout_seconds, int)
                or not 1 <= self.render_timeout_seconds <= 14400):
            raise LauncherError("INVALID_RENDER_TIMEOUT")
        budget_bytes = int(budget * GIB)
        if budget_bytes < 1:
            raise LauncherError("INVALID_VRAM_BUDGET")
        return budget_bytes


@dataclass(frozen=True)
class Admission:
    environ: dict
    private_report: dict
    safe_report: dict
    admission_file: Path
    output_root: Path
    test_only: bool


def verify_staged_sources(package_root):
    """Read-only verification of original bodies and explicit package overlays."""
    try:
        from stage_package import verify_staged_context
        return verify_staged_context(package_root)
    except Exception:
        # Verification errors may contain private paths; never reflect their text.
        raise LauncherError("SOURCE_CONTRACT_INVALID") from None


def _source_summary(report):
    if (not isinstance(report, dict) or report.get("status") != "PASS"
            or isinstance(report.get("files"), bool) or not isinstance(report.get("files"), int)
            or report["files"] <= 0 or not isinstance(report.get("sourceContractSha256"), str)
            or _HASH.fullmatch(report["sourceContractSha256"]) is None):
        raise LauncherError("SOURCE_CONTRACT_INVALID")
    return {"status": "PASS", "files": report["files"],
            "sourceContractSha256": report["sourceContractSha256"]}


def _model_name(name):
    if not isinstance(name, str):
        raise LauncherError("GPU_MODEL_UNSUPPORTED")
    match = _MODEL.fullmatch(name.strip())
    if match is None:
        raise LauncherError("GPU_MODEL_UNSUPPORTED")
    return "RTX " + re.sub(r"\s+", " ", match.group(1).upper())


def _memory_mib(value):
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        raise LauncherError("GPU_MEMORY_QUERY_INVALID") from None
    if isinstance(value, bool) or not math.isfinite(number) or not number.is_integer() or not 0 <= number <= 1024 * 1024:
        raise LauncherError("GPU_MEMORY_QUERY_INVALID")
    return int(number)


def query_allocation(environ, runner):
    """Query actual free memory; total VRAM alone cannot establish a free budget."""
    try:
        response = runner(["nvidia-smi", "--query-gpu=name,uuid,driver_version,memory.total,memory.free",
                           "--format=csv,noheader,nounits"], capture_output=True, text=True,
                          timeout=10, env=environ, check=False)
    except (OSError, subprocess.SubprocessError):
        raise LauncherError("GPU_HARDWARE_UNAVAILABLE") from None
    if (response.returncode != 0 or not isinstance(response.stdout, str)
            or len(response.stdout) > 65536):
        raise LauncherError("GPU_HARDWARE_UNAVAILABLE")
    rows = list(csv.reader(io.StringIO(response.stdout)))
    if len(rows) != 1 or len(rows[0]) != 5:
        raise LauncherError("GPU_ALLOCATION_AMBIGUOUS" if len(rows) > 1 else "GPU_HARDWARE_UNAVAILABLE")
    name, device_uuid, driver, total, free = (v.strip() for v in rows[0])
    model = _model_name(name)
    if (not re.fullmatch(r"GPU-[a-fA-F0-9-]+", device_uuid)
            or not re.fullmatch(r"\d+(?:\.\d+){1,4}", driver)):
        raise LauncherError("GPU_IDENTITY_INVALID")
    total, free = _memory_mib(total), _memory_mib(free)
    if total < MIN_MEMORY_MIB:
        raise LauncherError("GPU_PHYSICAL_MEMORY_INSUFFICIENT")
    if free > total:
        raise LauncherError("GPU_MEMORY_QUERY_INVALID")
    return {"name": name, "model": model, "uuid": device_uuid,
            "driver_version": driver, "memory_total_mib": total, "memory_free_mib": free}


def shared_memory_facts(path=Path("/dev/shm")):
    try:
        values = os.statvfs(path)
    except OSError:
        raise LauncherError("SHARED_MEMORY_UNAVAILABLE") from None
    return {"capacityBytes": values.f_blocks * values.f_frsize,
            "availableBytes": values.f_bavail * values.f_frsize}


def _check_limits(allocation, shm, budget_bytes):
    if budget_bytes > allocation["memory_free_mib"] * MIB - RESERVED_MEMORY_BYTES:
        raise LauncherError("GPU_VRAM_BUDGET_EXCEEDS_AVAILABLE")
    if (not isinstance(shm, dict) or any(isinstance(shm.get(k), bool) or not isinstance(shm.get(k), int)
                                       or shm[k] < MIN_SHM_BYTES for k in ("capacityBytes", "availableBytes"))):
        raise LauncherError("SHARED_MEMORY_INSUFFICIENT")
    return ([] if shm["capacityBytes"] >= RECOMMENDED_SHM_BYTES
            else ["SHARED_MEMORY_2_GIB_RECOMMENDED"])


def _private_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not stat.S_ISDIR(path.lstat().st_mode):
        raise LauncherError("DIAGNOSTIC_STORAGE_UNSAFE")
    path.chmod(0o700)
    return path


def _write_private_json(path, report):
    try:
        encoded = (json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if len(encoded) > 256 * 1024:
            raise LauncherError("DIAGNOSTICS_EXCEED_LIMIT")
        fd, temporary = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            path.chmod(0o600)
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    except (OSError, ValueError, TypeError):
        raise LauncherError("DIAGNOSTIC_STORAGE_UNAVAILABLE") from None


def persist_reports(storage_root, private_report, safe_report):
    try:
        root = _private_directory(storage_root)
        diagnostics = _private_directory(root / "diagnostics")
        token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex
        run = _private_directory(diagnostics / token)
        _write_private_json(run / "admission_private.json", private_report)
        _write_private_json(run / "admission_safe.json", safe_report)
        return run / "admission_private.json", root
    except OSError:
        raise LauncherError("DIAGNOSTIC_STORAGE_UNAVAILABLE") from None


def admit_gpu(config, *, environ=None, source_validator=None, runner=None,
              probe=None, runtime_prepare=None, shm_reader=None):
    """Return admitted environment after source, allocation and real draw gates.

    Supplying native-operation replacements marks every resulting report TEST_ONLY.
    Such an admission cannot start the production server or render subprocess.
    """
    budget = config.validate()
    env = dict(os.environ if environ is None else environ)
    test_only = any(v is not None for v in (runner, probe, runtime_prepare, shm_reader))
    try:
        mode, _ = browser_profile(env)
    except BrowserProfileError:
        raise LauncherError("GPU_PROFILE_INVALID") from None
    if mode != "gpu-required":
        raise LauncherError("GPU_REQUIRED_CPU_MODE_REJECTED")
    env["WORLD_ENGINE_RENDER_MODE"] = "gpu-required"
    validator = verify_staged_sources if source_validator is None else source_validator
    try:
        source = _source_summary(validator(config.package_root))
    except Exception:
        raise LauncherError("SOURCE_CONTRACT_INVALID") from None
    run = subprocess.run if runner is None else runner
    allocation = query_allocation(env, run)
    shm = (shared_memory_facts if shm_reader is None else shm_reader)()
    warnings = _check_limits(allocation, shm, budget)
    prepare = prepare_graphics_runtime if runtime_prepare is None else runtime_prepare
    try:
        updates, preparation = prepare(env)
        env.update(updates)
        report = select_graphics_profile(env, runner=runner, probe=probe)
    except GPUError as error:
        raise LauncherError(error.code, diagnostics=error.diagnostics) from None
    except (GraphicsRuntimeError, OSError, ValueError, TypeError):
        raise LauncherError("GPU_GRAPHICS_RUNTIME_PREPARATION_FAILED") from None
    if (report.get("gpu_rendering_verified") is not True or report.get("render_mode") != "gpu-required"
            or report.get("hardware_status") != "visible" or report.get("gpu_profile") not in {"egl", "vulkan"}):
        raise LauncherError("GPU_WEBGL_UNVERIFIED")
    hardware = report.get("nvidia_devices")
    if not isinstance(hardware, list) or len(hardware) != 1:
        raise LauncherError("GPU_ALLOCATION_AMBIGUOUS")
    device = hardware[0]
    if (not isinstance(device, dict) or device.get("uuid") != allocation["uuid"]
            or device.get("driver_version") != allocation["driver_version"]
            or _model_name(device.get("name")) != allocation["model"]
            or _memory_mib(device.get("memory_total_mib")) != allocation["memory_total_mib"]):
        raise LauncherError("GPU_ALLOCATION_CHANGED_DURING_PROBE")
    try:
        classify_probe(report, hardware, mode="gpu-required")
    except GPUError:
        raise LauncherError("GPU_WEBGL_UNVERIFIED") from None
    fingerprint = report.get("profile_fingerprint")
    if not isinstance(fingerprint, str) or _HASH.fullmatch(fingerprint) is None:
        raise LauncherError("GPU_PROBE_FINGERPRINT_INVALID")
    # The browser probe can change free memory. Refresh before publishing a
    # budget; only the same physical allocation may carry the admission forward.
    current = query_allocation(env, run)
    if any(current[k] != allocation[k] for k in ("uuid", "model", "driver_version", "memory_total_mib")):
        raise LauncherError("GPU_ALLOCATION_CHANGED_DURING_PROBE")
    allocation = current
    warnings = _check_limits(allocation, shm, budget)
    env.update(WORLD_ENGINE_GPU_PROFILE=report["gpu_profile"],
               CHROMIUM_PATH=str(ENGINE_ROOT / "deployment/gcube/chromium_wrapper.py"),
               RTX_GPU_VRAM_BUDGET_BYTES=str(budget), RTX_GPU_MODEL=allocation["model"],
               RTX_GPU_DRIVER_VERSION=allocation["driver_version"],
               RTX_GPU_PROBE_FINGERPRINT=fingerprint)
    safe = {"schema": "RTX_GPU_ADMISSION_V1", "status": "TEST_ONLY" if test_only else "GPU_VERIFIED",
            "testOnly": test_only, "gpuRenderingVerified": not test_only,
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "verificationScope": "STARTUP_NATIVE_GPU_PIXEL_DRAW",
            "renderMode": "gpu-required", "gpuProfile": report["gpu_profile"],
            "model": allocation["model"], "driverVersion": allocation["driver_version"],
            "physicalMemoryMiB": allocation["memory_total_mib"], "availableMemoryMiB": allocation["memory_free_mib"],
            "vramBudgetBytes": budget, "reservedMemoryBytes": RESERVED_MEMORY_BYTES,
            "vramBudgetScope": "OBSERVED_GPU_MEMORY_GROWTH_SINCE_ADMISSION",
            "driverMemoryReservation": False, "renderMemoryMonitoringIntervalSeconds": 1,
            "renderMemoryQueryTimeoutSeconds": 10,
            "sharedMemory": shm, "warnings": warnings, "sourceVerification": source,
            "autoRender": False, "renderExecuted": False, "visualQualityVerified": False}
    private = {**safe, "observedAt": datetime.now(timezone.utc).isoformat(),
               "allocation": allocation, "probe": report, "graphicsPreparation": preparation,
               "profileFingerprint": fingerprint}
    admission_file, output_root = persist_reports(config.storage_root, private, safe)
    env["RTX_GPU_ADMISSION_FILE"] = str(admission_file)
    return Admission(env, private, safe, admission_file, output_root, test_only)


def health_payload(admission):
    return {k: admission.safe_report[k] for k in
            ("status", "testOnly", "gpuRenderingVerified", "renderMode", "gpuProfile", "model",
             "driverVersion", "physicalMemoryMiB", "vramBudgetBytes", "autoRender", "renderExecuted",
             "visualQualityVerified", "observedAt", "verificationScope")}


def health_handler(admission):
    class HealthHandler(BaseHTTPRequestHandler):
        server_version = "RTXPackageHealth"
        sys_version = ""

        def _reply(self, status_code, payload):
            body = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._reply(200, health_payload(admission)) if self.path == "/healthz" else self._reply(404, {"error": "NOT_FOUND"})

        def _deny(self):
            self._reply(405, {"error": "GET_HEALTH_ONLY"})

        do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = do_CONNECT = do_TRACE = _deny

        def log_message(self, *args):
            pass  # Never echo request URLs, headers or query strings.

    return HealthHandler


def serve_health(admission, config, *, server_factory=None):
    if admission.test_only and server_factory is None:
        raise LauncherError("TEST_ADMISSION_NOT_EXECUTABLE")
    factory = ThreadingHTTPServer if server_factory is None else server_factory
    server = factory(("0.0.0.0", config.port), health_handler(admission))
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _stop_render(process, *, stop_group=None):
    if process.poll() is not None:
        return
    stop = os.killpg if stop_group is None else stop_group
    try:
        stop(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            stop(process.pid, signal.SIGKILL)
        except OSError:
            pass
        process.wait(timeout=5)


def render_65422(admission, config, *, runner=None, process_factory=None,
                 memory_runner=None, clock=time.monotonic, sleep=time.sleep, stop_group=None):
    if admission.test_only and runner is None and process_factory is None:
        raise LauncherError("TEST_ADMISSION_NOT_EXECUTABLE")
    command = ["node", str(HERE / "hardware_render.mjs"), "--admission-file", str(admission.admission_file),
               "--output-root", str(admission.output_root)]
    if runner is not None:
        # Complete subprocess replacement exists only for CPU control-flow tests.
        try:
            response = runner(command, cwd=ENGINE_ROOT, env=admission.environ,
                              timeout=config.render_timeout_seconds, check=False)
        except (OSError, subprocess.SubprocessError):
            raise LauncherError("GPU_RENDER_PROCESS_FAILED") from None
        if response.returncode != 0:
            raise LauncherError("GPU_RENDER_PROCESS_FAILED")
        return 0
    factory = subprocess.Popen if process_factory is None else process_factory
    run_memory = subprocess.run if memory_runner is None else memory_runner
    allocation = admission.private_report["allocation"]
    baseline_used = allocation["memory_total_mib"] - allocation["memory_free_mib"]
    budget = admission.safe_report["vramBudgetBytes"]
    process = None
    deadline = clock() + config.render_timeout_seconds
    try:
        process = factory(command, cwd=ENGINE_ROOT, env=admission.environ, start_new_session=True)
        while process.poll() is None:
            if clock() >= deadline:
                raise LauncherError("GPU_RENDER_DEADLINE_EXCEEDED")
            current = query_allocation(admission.environ, run_memory)
            if any(current[k] != allocation[k] for k in ("uuid", "model", "driver_version", "memory_total_mib")):
                raise LauncherError("GPU_ALLOCATION_CHANGED_DURING_RENDER")
            growth = max(0, current["memory_total_mib"] - current["memory_free_mib"] - baseline_used) * MIB
            if growth > budget or current["memory_free_mib"] * MIB < RESERVED_MEMORY_BYTES:
                raise LauncherError("GPU_RENDER_VRAM_BUDGET_EXCEEDED")
            sleep(min(1.0, max(0.0, deadline - clock())))
        if process.returncode != 0:
            raise LauncherError("GPU_RENDER_PROCESS_FAILED")
    except (OSError, subprocess.SubprocessError):
        raise LauncherError("GPU_RENDER_PROCESS_FAILED") from None
    finally:
        if process is not None and process.poll() is None:
            _stop_render(process, stop_group=stop_group)
    return 0


def main(argv=None, *, environ=None, source_validator=None, runner=None, probe=None,
         runtime_prepare=None, shm_reader=None, server_factory=None, render_runner=None,
         config=None):
    parser = argparse.ArgumentParser(description="Required physical RTX GPU admission; default is GET /healthz only.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="Verify source contract and physical WebGL pixel draw, then exit")
    actions.add_argument("--render-65422", action="store_true", help="After admission, run the isolated hardware renderer explicitly")
    parser.add_argument("--vram-budget-gib", type=float, default=8.0)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    config = LauncherConfig(budget_gib=args.vram_budget_gib, port=args.port) if config is None else config
    render_started = False
    try:
        admission = admit_gpu(config, environ=environ, source_validator=source_validator, runner=runner,
                              probe=probe, runtime_prepare=runtime_prepare, shm_reader=shm_reader)
        if args.check:
            print(json.dumps(admission.safe_report, sort_keys=True, allow_nan=False))
            return 0
        if args.render_65422:
            render_started = True
            return render_65422(admission, config, runner=render_runner)
        serve_health(admission, config, server_factory=server_factory)
        return 0
    except (LauncherError, GPUError, GraphicsRuntimeError, OSError, ValueError, TypeError) as error:
        code = error.code if isinstance(error, (LauncherError, GPUError)) else "GPU_LAUNCH_FAILED"
        safe = {"schema": "RTX_GPU_ADMISSION_V1", "status": "BLOCKED", "reasonCode": code,
                "gpuRenderingVerified": False, "autoRender": False, "renderExecuted": False,
                "renderAttempted": render_started,
                "visualQualityVerified": False}
        private = {**safe, "observedAt": datetime.now(timezone.utc).isoformat(),
                   "diagnostics": sanitize_gpu_diagnostics(getattr(error, "diagnostics", {}))}
        try:
            persist_reports(config.storage_root, private, safe)
        except LauncherError:
            safe["diagnosticsPersisted"] = False
        print(json.dumps(safe, sort_keys=True, allow_nan=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
