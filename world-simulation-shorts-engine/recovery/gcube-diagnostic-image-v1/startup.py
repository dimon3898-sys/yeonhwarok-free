#!/usr/bin/env python3
"""Add bounded, fail-closed startup diagnostics around the unchanged RTX package.

Normal mode delegates the original native checks and admitted execution. Only
the explicitly selected diagnostic mode uses a supervisor: an isolated child
runs those same checks, then an unprivileged parent serves a blocked report.
There are no command-line or environment switches for replacing GPU checks.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import importlib
import json
import os
from pathlib import Path
import pwd
import select
import signal
import sys
import time

import records
from service import serve_diagnostic

PACKAGE = Path("/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1")
REPO = PACKAGE.parents[2]
MAX_WORKER_BYTES = 65536
WORKER_TIMEOUT_SECONDS = 240


class StartupFailure(Exception):
    def __init__(self, stage, code, exit_code=1):
        self.stage, self.code, self.exit_code = stage, code, exit_code
        super().__init__(code)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unrecognised arguments, which may be secrets.
        raise StartupFailure("CONFIGURATION", "INVALID_DIAGNOSTIC_CONFIG", 2)


@dataclass
class Stage:
    name: str = "UID_GID"


class NativeOperations:
    """Thin original-function calls; unit-test substitutes are Python-only."""

    @staticmethod
    def _module(name):
        # The new image adds this directory but never alters its original bytes.
        if str(PACKAGE) not in sys.path:
            sys.path.insert(0, str(PACKAGE))
        module = importlib.import_module(name)
        if Path(module.__file__).resolve().parent != PACKAGE:
            raise StartupFailure("SOURCE_INTEGRITY", "SOURCE_CONTRACT_INVALID")
        return module

    @staticmethod
    def account():
        return pwd.getpwnam("engine")

    def bootstrap(self):
        return self._module("bootstrap")

    def source(self):
        return self._module("stage_package").verify_staged_context(PACKAGE.parents[3])

    def dependencies(self):
        contract = json.loads((PACKAGE / "dependency_contract.json").read_text())
        return self._module("verify_dependencies").verify_dependencies(REPO, contract)

    def gpu(self):
        return self._module("gpu_launcher")


@contextmanager
def observe_prepare(bootstrap, stage):
    """Observe original calls without replacing functions or changing checks."""
    previous = sys.getprofile()
    directory = getattr(bootstrap, "_directory", None)
    directory_code = getattr(directory, "__code__", None)

    def observe(frame, event, argument):
        # An observer must never turn a valid original operation into a failure.
        try:
            if event == "call" and directory_code is not None and frame.f_code is directory_code:
                path = str(frame.f_locals.get("path", ""))
                stage.name = "STORAGE" if path == "/world-storage" or path.startswith("/world-storage/") else "RUNTIME_DIRECTORY"
            elif event == "return" and directory_code is not None and frame.f_code is directory_code and argument is not None:
                stage.name = "BOOTSTRAP"
            elif event == "c_call" and getattr(argument, "__name__", "") in {"setuid", "setgid", "setgroups"}:
                stage.name = "UID_GID"
        except Exception:
            pass

    try:
        sys.setprofile(observe)
        yield
    finally:
        sys.setprofile(previous)


def _failure(stage, error, *, mode, test_only=False):
    code, exit_code, diagnostics = "UNEXPECTED_STARTUP_EXCEPTION", 1, None
    if isinstance(error, StartupFailure):
        stage, code, exit_code = error.stage, error.code, error.exit_code
    elif stage in {"NVIDIA", "GRAPHICS", "CHROMIUM", "WEBGL2", "GPU_MEMORY"}:
        exit_code = 2
        candidate = getattr(error, "code", "GPU_LAUNCH_FAILED")
        code = candidate if isinstance(candidate, str) and candidate in records.REASONS else "GPU_LAUNCH_FAILED"
        diagnostics = getattr(error, "diagnostics", None)
        failed_stage = diagnostics.get("failed_stage") if isinstance(diagnostics, dict) else None
        if code.startswith("INVALID_"):
            stage = "CONFIGURATION"
        elif "MEMORY" in code or "VRAM" in code:
            stage = "GPU_MEMORY"
        elif code.startswith("GPU_GRAPHICS") or code == "GPU_PROFILE_INVALID":
            stage = "GRAPHICS"
        elif failed_stage in {"A", "B"}:
            stage = "NVIDIA"
        elif failed_stage == "C" or "BROWSER" in code or "CHROMIUM" in code:
            stage = "CHROMIUM"
        elif failed_stage in {"D", "E", "F"} or "WEBGL" in code or "FINGERPRINT" in code:
            stage = "WEBGL2"
        elif code == "SOURCE_CONTRACT_INVALID":
            stage = "SOURCE_INTEGRITY"
        elif code.startswith("DIAGNOSTIC_STORAGE"):
            stage = "STORAGE"
        elif not hasattr(error, "code"):
            stage = "UNEXPECTED"
    elif stage == "STORAGE":
        code = ("STORAGE_READ_ONLY" if getattr(error, "errno", None) == errno.EROFS else
                "STORAGE_PERMISSION_DENIED" if getattr(error, "errno", None) in {errno.EACCES, errno.EPERM} else
                "STORAGE_VALIDATION_FAILED")
    elif stage == "RUNTIME_DIRECTORY":
        code = "RUNTIME_DIRECTORY_FAILED"
    elif stage == "UID_GID":
        code = "ACCOUNT_UNAVAILABLE" if isinstance(error, KeyError) else "UID_GID_FAILED"
    elif stage == "BOOTSTRAP":
        code = "BOOTSTRAP_FAILED"
    elif stage == "SOURCE_INTEGRITY":
        code = "SOURCE_CONTRACT_INVALID"
    elif stage == "DEPENDENCY":
        code = "CPU_DEPENDENCY_CHECK_FAILED"
    else:
        stage = "UNEXPECTED"
    # Sanitization, code allowlists, and fixed termination reasons live in records.
    return records.make_record(stage, code, exit_code, mode=mode,
                               errno_value=getattr(error, "errno", None),
                               exception_type=type(error).__name__,
                               gpu_diagnostics=diagnostics, test_only=test_only)


def _checks(operations, args, *, mode, test_only):
    stage = Stage()
    try:
        account = operations.account()
        bootstrap = operations.bootstrap()
        with observe_prepare(bootstrap, stage):
            bootstrap.prepare_environment(account)
        stage.name = "SOURCE_INTEGRITY"
        operations.source()
        stage.name = "DEPENDENCY"
        if operations.dependencies().get("status") != "PASS":
            raise StartupFailure("DEPENDENCY", "CPU_DEPENDENCY_CHECK_FAILED")
        stage.name = "NVIDIA"
        gpu = operations.gpu()
        config = gpu.LauncherConfig(budget_gib=args.vram_budget_gib, port=args.port)
        admission = gpu.admit_gpu(config)  # Native only in production; no runner/probe replacements.
        return (gpu, config, admission), None
    except Exception as error:
        return None, _failure(stage.name, error, mode=mode, test_only=test_only)


def _admission_diagnostics(checked, *, test_only):
    """Validate the native result envelope, then forward only existing safe GPU data."""
    if type(test_only) is not bool or not isinstance(checked, tuple) or len(checked) != 3:
        raise ValueError()
    admission = checked[2]
    safe = getattr(admission, "safe_report", None)
    private = getattr(admission, "private_report", None)
    admitted_test = getattr(admission, "test_only", None)
    if (type(admitted_test) is not bool or admitted_test and not test_only
            or not isinstance(safe, dict) or not isinstance(private, dict)
            or safe.get("schema") != "RTX_GPU_ADMISSION_V1"
            or safe.get("testOnly") is not admitted_test
            or safe.get("status") != ("TEST_ONLY" if admitted_test else "GPU_VERIFIED")
            or safe.get("gpuRenderingVerified") is not (not admitted_test)
            or safe.get("verificationScope") != "STARTUP_NATIVE_GPU_PIXEL_DRAW"
            or safe.get("renderMode") != "gpu-required" or safe.get("gpuProfile") not in {"egl", "vulkan"}
            or safe.get("autoRender") is not False or safe.get("renderExecuted") is not False
            or safe.get("visualQualityVerified") is not False
            or not isinstance(safe.get("sourceVerification"), dict)
            or safe["sourceVerification"].get("status") != "PASS"):
        raise ValueError()
    probe = private.get("probe")
    if (not isinstance(probe, dict) or probe.get("gpu_rendering_verified") is not True
            or probe.get("render_mode") != "gpu-required" or probe.get("hardware_status") != "visible"
            or probe.get("gpu_profile") != safe["gpuProfile"]):
        raise ValueError()
    diagnostics = probe.get("diagnostics")
    if (not isinstance(diagnostics, dict) or type(diagnostics.get("schema_version")) is not int
            or diagnostics.get("schema_version") != 1
            or diagnostics.get("render_mode") != "gpu-required"
            or diagnostics.get("gpu_profile") != safe["gpuProfile"]
            or diagnostics.get("reason_code") != "VERIFIED" or diagnostics.get("failed_stage") is not None):
        raise ValueError()
    stages = diagnostics.get("stages")
    if (not isinstance(stages, list) or len(stages) != 6
            or any(not isinstance(item, dict) or item.get("status") != "PASS" for item in stages)
            or {item.get("id") for item in stages} != set("ABCDEF")):
        raise ValueError()
    webgl = diagnostics.get("webgl")
    if (not isinstance(webgl, dict) or webgl.get("context_available") is not True
            or webgl.get("webgl2") is not True or webgl.get("draw_passed") is not True
            or webgl.get("software_renderer") is not False or type(webgl.get("webgl_error")) is not int
            or webgl.get("webgl_error") != 0):
        raise ValueError()
    pixel = webgl.get("pixel")
    if (not isinstance(pixel, list) or len(pixel) != 4
            or any(type(value) is not int or not 0 <= value <= 255 for value in pixel)
            or pixel[0] < 250 or pixel[1] > 5 or pixel[2] > 5 or pixel[3] < 250):
        raise ValueError()
    # make_record applies the unchanged engine sanitizer and strict secondary
    # allowlist. No admission object, environment, allocation UUID or render
    # capability is transferred through the diagnostic worker pipe.
    return diagnostics


def _worker_record(operations, args, test_only):
    checked, failure = _checks(operations, args, mode="diagnostic", test_only=test_only)
    if failure is not None:
        return failure
    try:
        diagnostics = _admission_diagnostics(checked, test_only=test_only)
        return records.make_record("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_ONLY", 0, mode="diagnostic",
                                   gpu_diagnostics=diagnostics, test_only=test_only)
    except Exception:
        return records.make_record("DIAGNOSTIC_SERVICE", "DIAGNOSTIC_RECORD_INVALID", 1,
                                   mode="diagnostic", test_only=test_only)


def _diagnostic_worker(operations, args, *, test_only, timeout=WORKER_TIMEOUT_SECONDS):
    """Bounded private pipe carries only a re-normalized safe record, never admission."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(read_fd)
            os.setpgid(0, 0)
            record = _worker_record(operations, args, test_only)
            body = json.dumps(record, separators=(",", ":"), allow_nan=False).encode()
            if len(body) > MAX_WORKER_BYTES:
                os._exit(1)
            # A bounded record can exceed PIPE_BUF; preserve all bytes.
            view = memoryview(body)
            while view:
                written = os.write(write_fd, view)
                view = view[written:]
            os.close(write_fd)
            os._exit(0 if record["exitCode"] == 0 else record["exitCode"])
        except BaseException:
            os._exit(1)
    os.close(write_fd)
    reaped = False
    previous_signals = {}
    try:
        def interrupted(number, frame):
            raise StartupFailure("UNEXPECTED", "DIAGNOSTIC_WORKER_INTERRUPTED", 128 + number)

        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            previous_signals[number] = signal.signal(number, interrupted)
        try:
            os.setpgid(pid, pid)
        except (PermissionError, ProcessLookupError):
            pass
        deadline, body, timed_out = time.monotonic() + timeout, bytearray(), False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            readable, _, _ = select.select([read_fd], [], [], min(remaining, 1.0))
            if readable:
                chunk = os.read(read_fd, MAX_WORKER_BYTES + 1 - len(body))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > MAX_WORKER_BYTES:
                    break
        status = None
        if not timed_out and len(body) <= MAX_WORKER_BYTES:
            # EOF alone does not prove that a child exited. Preserve the same
            # deadline even if an unexpected child closes its pipe early.
            while time.monotonic() < deadline:
                waited, status = os.waitpid(pid, os.WNOHANG)
                if waited == pid:
                    reaped = True
                    break
                time.sleep(min(.01, max(0, deadline - time.monotonic())))
            if not reaped:
                timed_out = True
        if timed_out or len(body) > MAX_WORKER_BYTES:
            code = "DIAGNOSTIC_WORKER_TIMEOUT" if timed_out else "DIAGNOSTIC_RECORD_INVALID"
            return records.make_record("UNEXPECTED", code, 1, mode="diagnostic", test_only=test_only)
        try:
            value = json.loads(body)
            safe = value.get("safeDiagnostics", {}) if isinstance(value, dict) else {}
            if (not isinstance(value, dict) or value.get("schema") != "WORLD_ENGINE_STARTUP_DIAGNOSTIC_V1"
                    or value.get("startupMode") != "diagnostic" or (safe.get("testOnly") is True) is not test_only
                    or value.get("gpuRenderingVerified") is not False or value.get("renderAllowed") is not False
                    or not os.WIFEXITED(status) or os.WEXITSTATUS(status) != value.get("exitCode")):
                raise ValueError()
            # The child has already applied the engine sanitizer and removed
            # identities. Re-apply the strict record allowlist without sending
            # redacted device data through the original identity-based parser.
            return records.safe_record(value)
        except (ValueError, TypeError, AttributeError):
            return records.make_record("UNEXPECTED", "DIAGNOSTIC_WORKER_FAILED", 1,
                                       mode="diagnostic", test_only=test_only)
    finally:
        os.close(read_fd)
        if not reaped:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
        for number, handler in previous_signals.items():
            signal.signal(number, handler)


def _drop_diagnostic_privileges(account):
    if account.pw_uid != 1000 or account.pw_gid != 1000:
        raise StartupFailure("UID_GID", "UID_GID_FAILED")
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    if (os.getuid() != 1000 or os.geteuid() != 1000 or os.getgid() != 1000
            or os.getegid() != 1000 or os.getgroups()):
        raise StartupFailure("UID_GID", "UID_GID_FAILED")


def _publish(record):
    # stderr/stdout always precede optional disk writes, including storage errors.
    records.emit_record(record)
    records.persist_record(record)


def _diagnostic_options(args, environ):
    try:
        ttl = int(environ.get("WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS", "900"))
        port = int(environ.get("WORLD_ENGINE_DIAGNOSTIC_PORT", "8000"))
        if not 1 <= ttl <= 900 or not 1024 <= port <= 65535 or args.port not in {8000, port}:
            raise ValueError()
        return ttl, port
    except (ValueError, TypeError):
        raise StartupFailure("CONFIGURATION", "INVALID_DIAGNOSTIC_CONFIG", 2) from None


def main(argv=None, *, operations=None, environ=None, worker=None,
         privilege_drop=None, diagnostic_service=None):
    # Seams are Python-callable only; an injected success cannot dispatch normal
    # production rendering or the admitted health server.
    test_only = any(value is not None for value in
                    (operations, environ, worker, privilege_drop, diagnostic_service))
    operations = NativeOperations() if operations is None else operations
    environment = os.environ if environ is None else environ
    mode = "normal"
    parser = SafeArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--render-65422", action="store_true")
    parser.add_argument("--vram-budget-gib", type=float, default=8.0)
    parser.add_argument("--port", type=int, default=8000)
    try:
        args = parser.parse_args(argv)
        mode = environment.get("WORLD_ENGINE_STARTUP_MODE", "normal")
        if mode not in {"normal", "diagnostic"}:
            mode = "normal"  # Never echo the invalid value.
            raise StartupFailure("CONFIGURATION", "INVALID_STARTUP_MODE", 2)
        if mode == "diagnostic":
            if args.render_65422:
                raise StartupFailure("CONFIGURATION", "DIAGNOSTIC_RENDER_FORBIDDEN", 2)
            ttl, port = _diagnostic_options(args, environment)
            run_worker = _diagnostic_worker if worker is None else worker
            record = run_worker(operations, args, test_only=test_only)
            # If checks dropped the child account, the parent can still clear
            # all groups before binding. There is never a root diagnostic server.
            try:
                account = operations.account()
                drop = _drop_diagnostic_privileges if privilege_drop is None else privilege_drop
                drop(account)
            except Exception as error:
                if record.get("exitCode", 0) > 0:
                    _publish(record)  # Preserve the first known startup failure.
                secondary = _failure("UID_GID", error, mode=mode, test_only=test_only)
                _publish(secondary)
                return secondary["exitCode"]
            _publish(record)
            serve = serve_diagnostic if diagnostic_service is None else diagnostic_service
            return serve(record, port=port, max_seconds=ttl)
        checked, failure = _checks(operations, args, mode=mode, test_only=test_only)
        if failure is not None:
            _publish(failure)
            return failure["exitCode"]
        gpu, config, admission = checked
        if args.check:
            if test_only or admission.test_only:
                raise StartupFailure("UNEXPECTED", "TEST_SEAM_PRODUCTION_DISPATCH_BLOCKED", 2)
            print(json.dumps(admission.safe_report, sort_keys=True, allow_nan=False))
            return 0
        if test_only or admission.test_only:
            raise StartupFailure("UNEXPECTED", "TEST_SEAM_PRODUCTION_DISPATCH_BLOCKED", 2)
        try:
            if args.render_65422:
                return gpu.render_65422(admission, config)
            gpu.serve_health(admission, config)
            return 0
        except Exception as error:
            record = _failure("NVIDIA", error, mode=mode)
            _publish(record)
            return record["exitCode"]
    except Exception as error:
        record = _failure("UNEXPECTED", error, mode=mode, test_only=test_only)
        _publish(record)
        return record["exitCode"]


if __name__ == "__main__":
    raise SystemExit(main())
