"""Focused CPU control-flow tests; all fake GPU outcomes are TEST_ONLY."""
from __future__ import annotations

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import startup


class GPUFailure(RuntimeError):
    def __init__(self, code, diagnostics=None):
        self.code, self.diagnostics = code, diagnostics or {}
        super().__init__("secret-canary-never-reflect-this-message")


class FakeBootstrap:
    def __init__(self, error=None, storage=False, delay=0):
        self.error, self.storage, self.delay = error, storage, delay

    def _directory(self, path):
        if self.error:
            raise self.error

    def prepare_environment(self, account):
        if self.delay:
            time.sleep(self.delay)
        if self.storage:
            self._directory("/world-storage/rtx-gpu-package-v1")
        elif self.error:
            raise self.error
        return {"uid": 1000}


class FakeGPU:
    LauncherConfig = SimpleNamespace

    def __init__(self, error=None):
        self.error = error
        self.admitted = self.rendered = self.served = 0

    def admit_gpu(self, config):
        self.admitted += 1
        if self.error:
            raise self.error
        return SimpleNamespace(test_only=False, safe_report={"status": "GPU_VERIFIED"})

    def render_65422(self, admission, config):
        self.rendered += 1
        return 0

    def serve_health(self, admission, config):
        self.served += 1


class FakeOperations:
    def __init__(self, *, prepare_error=None, storage=False, source_error=None,
                 dependency_status="PASS", dependency_error=None, gpu_error=None, delay=0):
        self.boot = FakeBootstrap(prepare_error, storage, delay)
        self.device = FakeGPU(gpu_error)
        self.source_error, self.dependency_error = source_error, dependency_error
        self.dependency_status = dependency_status
        self.order = []

    def account(self):
        return SimpleNamespace(pw_uid=1000, pw_gid=1000)

    def bootstrap(self):
        self.order.append("prepare")
        return self.boot

    def source(self):
        self.order.append("source")
        if self.source_error:
            raise self.source_error
        return {"status": "PASS"}

    def dependencies(self):
        self.order.append("dependency")
        if self.dependency_error:
            raise self.dependency_error
        return {"status": self.dependency_status}

    def gpu(self):
        self.order.append("gpu")
        return self.device


@contextmanager
def captured_records():
    observed = []
    with patch.object(startup.records, "emit_record", side_effect=lambda record: observed.append(record)), \
         patch.object(startup.records, "persist_record", return_value={"persisted": True, "tier": "TEST_ONLY"}):
        yield observed


class StartupTests(unittest.TestCase):
    def invoke(self, ops, argv=None, **kwargs):
        with captured_records() as observed:
            result = startup.main(argv or [], operations=ops, **kwargs)
        self.assertTrue(observed)
        return result, observed[-1]

    def test_storage_permission_and_readonly_have_original_exit_one(self):
        for number, expected in ((errno.EPERM, "STORAGE_PERMISSION_DENIED"),
                                 (errno.EACCES, "STORAGE_PERMISSION_DENIED"),
                                 (errno.EROFS, "STORAGE_READ_ONLY")):
            with self.subTest(number=number):
                ops = FakeOperations(prepare_error=OSError(number, "private mount path"), storage=True)
                result, record = self.invoke(ops)
                self.assertEqual((result, record["stage"], record["errorCode"]), (1, "STORAGE", expected))
                self.assertEqual(record["safeDiagnostics"]["errno"], number)
                self.assertEqual(ops.order, ["prepare"])
                self.assertEqual(ops.device.admitted, 0)

    def test_uid_failure_does_not_start_native_gpu(self):
        result, record = self.invoke(FakeOperations(prepare_error=PermissionError(errno.EPERM, "private")))
        self.assertEqual((result, record["stage"], record["errorCode"]), (1, "UID_GID", "UID_GID_FAILED"))

    def test_source_failure_stops_dependency_and_gpu(self):
        ops = FakeOperations(source_error=ValueError("secret private source path"))
        result, record = self.invoke(ops)
        self.assertEqual((result, record["stage"]), (1, "SOURCE_INTEGRITY"))
        self.assertEqual(ops.order, ["prepare", "source"])

    def test_dependency_failure_stops_gpu(self):
        for values in ({"dependency_status": "FAIL"}, {"dependency_error": ImportError("secret module path")}):
            ops = FakeOperations(**values)
            result, record = self.invoke(ops)
            self.assertEqual((result, record["errorCode"]), (1, "CPU_DEPENDENCY_CHECK_FAILED"))
            self.assertEqual(ops.order, ["prepare", "source", "dependency"])

    def test_gpu_absence_preserves_exit_two(self):
        result, record = self.invoke(FakeOperations(gpu_error=GPUFailure("GPU_HARDWARE_UNAVAILABLE")))
        self.assertEqual((result, record["stage"], record["errorCode"]), (2, "NVIDIA", "GPU_HARDWARE_UNAVAILABLE"))
        self.assertFalse(record["gpuRenderingVerified"])
        self.assertTrue(record["safeDiagnostics"]["testOnly"])

    def test_gpu_phase_classification_is_explicit(self):
        cases = [("GPU_HARDWARE_UNAVAILABLE", {"failed_stage": "B"}, "NVIDIA"),
                 ("GPU_GRAPHICS_RUNTIME_PREPARATION_FAILED", {}, "GRAPHICS"),
                 ("GPU_BROWSER_PROBE_FAILED", {"failed_stage": "C"}, "CHROMIUM"),
                 ("GPU_WEBGL_UNVERIFIED", {"failed_stage": "F"}, "WEBGL2"),
                 ("SHARED_MEMORY_INSUFFICIENT", {}, "GPU_MEMORY"),
                 ("GPU_VRAM_BUDGET_EXCEEDS_AVAILABLE", {}, "GPU_MEMORY")]
        for code, diagnostics, expected in cases:
            with self.subTest(code=code):
                result, record = self.invoke(FakeOperations(gpu_error=GPUFailure(code, diagnostics)))
                self.assertEqual((result, record["stage"], record["errorCode"]), (2, expected, code))

    def test_unexpected_failure_and_secret_canary_never_appear(self):
        canary = "secret-canary-never-reflect-this-message"
        error = GPUFailure(canary, {"failed_stage": "D", "password": canary,
                                   "webgl": {"renderer": "NVIDIA " + canary}})
        with patch.object(startup.records, "persist_record", return_value={"persisted": False}):
            stream = io.StringIO()
            with redirect_stdout(stream), redirect_stderr(stream):
                result = startup.main([], operations=FakeOperations(gpu_error=error))
        self.assertEqual(result, 2)
        self.assertNotIn(canary, stream.getvalue())
        self.assertNotIn("private", stream.getvalue())
        self.assertEqual(len(stream.getvalue().splitlines()), 2)

    def test_unexpected_gpu_start_exception_has_its_own_stage(self):
        result, record = self.invoke(FakeOperations(gpu_error=RuntimeError("secret-canary-never-output")))
        self.assertEqual((result, record["stage"]), (2, "UNEXPECTED"))
        self.assertNotIn("secret-canary", json.dumps(record))

    def test_injected_success_never_dispatches_production(self):
        for argv in ([], ["--check"], ["--render-65422"]):
            ops = FakeOperations()
            result, record = self.invoke(ops, argv)
            self.assertEqual(result, 2)
            self.assertEqual(record["errorCode"], "TEST_SEAM_PRODUCTION_DISPATCH_BLOCKED")
            self.assertEqual((ops.device.rendered, ops.device.served), (0, 0))

    def test_diagnostic_render_is_rejected_before_checks(self):
        ops = FakeOperations()
        result, record = self.invoke(ops, ["--render-65422"], environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic"})
        self.assertEqual((result, record["errorCode"]), (2, "DIAGNOSTIC_RENDER_FORBIDDEN"))
        self.assertEqual(ops.order, [])

    def test_bad_mode_and_args_do_not_echo_values(self):
        for argv, env in (([], {"WORLD_ENGINE_STARTUP_MODE": "canary-invalid-mode"}),
                          (["--canary-secret-arg"], {}), (["--diagnostic"], {})):
            result, record = self.invoke(FakeOperations(), argv, environ=env)
            self.assertEqual(result, 2)
            self.assertNotIn("canary", json.dumps(record))

    def test_bad_diagnostic_options_stop_before_worker(self):
        for key, value in (("WORLD_ENGINE_DIAGNOSTIC_PORT", "80"),
                           ("WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS", "901")):
            worker = unittest.mock.Mock()
            result, record = self.invoke(FakeOperations(), environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic", key: value}, worker=worker)
            self.assertEqual((result, record["errorCode"]), (2, "INVALID_DIAGNOSTIC_CONFIG"))
            worker.assert_not_called()

    def test_diagnostic_port_matches_healthcheck_environment(self):
        args = SimpleNamespace(port=8000)
        self.assertEqual(startup._diagnostic_options(args, {}), (900, 8000))
        self.assertEqual(startup._diagnostic_options(args, {"WORLD_ENGINE_DIAGNOSTIC_PORT": "8111"}), (900, 8111))
        args.port = 8111
        with self.assertRaises(startup.StartupFailure):
            startup._diagnostic_options(args, {})
        self.assertEqual(startup._diagnostic_options(args, {"WORLD_ENGINE_DIAGNOSTIC_PORT": "8111"}), (900, 8111))

    def test_diagnostic_ttl_boundaries_match_service(self):
        args = SimpleNamespace(port=8000)
        for value in ("1", "900"):
            self.assertEqual(startup._diagnostic_options(args, {"WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS": value})[0], int(value))
        for value in ("0", "901", "3600"):
            with self.assertRaises(startup.StartupFailure):
                startup._diagnostic_options(args, {"WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS": value})

    def test_diagnostic_failure_record_keeps_service_blocked(self):
        record = startup.records.make_record("WEBGL2", "GPU_WEBGL_UNVERIFIED", 2,
                                             mode="diagnostic", test_only=True)
        events = []
        def service(received, **kwargs):
            events.append((received, kwargs))
            return 2
        result, published = self.invoke(FakeOperations(), environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic"},
            worker=lambda *args, **kwargs: record, privilege_drop=lambda account: events.append("dropped"),
            diagnostic_service=service)
        self.assertEqual(result, 2)
        self.assertEqual(events[0], "dropped")
        self.assertEqual(events[1][0]["status"], "BLOCKED")
        self.assertFalse(events[1][0]["renderAllowed"])
        self.assertEqual(published["errorCode"], "GPU_WEBGL_UNVERIFIED")

    def test_diagnostic_privilege_failure_prevents_listening(self):
        service = unittest.mock.Mock()
        def denied(account):
            raise PermissionError(errno.EPERM, "private identity")
        result, record = self.invoke(FakeOperations(), environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic"},
            worker=lambda *args, **kwargs: startup.records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, mode="diagnostic"),
            privilege_drop=denied, diagnostic_service=service)
        self.assertEqual((result, record["stage"], record["errorCode"]), (1, "UID_GID", "UID_GID_FAILED"))
        service.assert_not_called()

    def test_clear_groups_and_identity_are_verified(self):
        state = {"uid": 0, "gid": 0, "groups": [44, 109]}
        with patch.multiple(startup.os, getuid=lambda: state["uid"], geteuid=lambda: state["uid"],
            getgid=lambda: state["gid"], getegid=lambda: state["gid"], getgroups=lambda: state["groups"],
            setgroups=lambda v: state.update(groups=v), setgid=lambda v: state.update(gid=v),
            setuid=lambda v: state.update(uid=v)):
            startup._drop_diagnostic_privileges(SimpleNamespace(pw_uid=1000, pw_gid=1000))
        self.assertEqual(state, {"uid": 1000, "gid": 1000, "groups": []})

    def test_nonroot_inherited_device_groups_refuse_service(self):
        with patch.multiple(startup.os, getuid=lambda: 1000, geteuid=lambda: 1000,
            getgid=lambda: 1000, getegid=lambda: 1000, getgroups=lambda: [44]):
            with self.assertRaises(startup.StartupFailure):
                startup._drop_diagnostic_privileges(SimpleNamespace(pw_uid=1000, pw_gid=1000))

    @unittest.skipUnless(hasattr(os, "fork"), "Linux diagnostic supervisor uses fork")
    def test_actual_fork_reuses_native_shape_and_preserves_parent_identity(self):
        before = (os.getuid(), os.getgid(), os.getgroups())
        args = SimpleNamespace(vram_budget_gib=8.0, port=8000)
        record = startup._diagnostic_worker(FakeOperations(gpu_error=GPUFailure("GPU_HARDWARE_UNAVAILABLE")),
                                             args, test_only=True, timeout=2)
        self.assertEqual(record["errorCode"], "GPU_HARDWARE_UNAVAILABLE")
        self.assertTrue(record["safeDiagnostics"]["testOnly"])
        self.assertEqual((os.getuid(), os.getgid(), os.getgroups()), before)

    @unittest.skipUnless(hasattr(os, "fork"), "Linux diagnostic supervisor uses fork")
    def test_worker_timeout_is_bounded_and_nonzero(self):
        args = SimpleNamespace(vram_budget_gib=8.0, port=8000)
        before = time.monotonic()
        record = startup._diagnostic_worker(FakeOperations(delay=5), args, test_only=True, timeout=.1)
        self.assertEqual((record["errorCode"], record["exitCode"]), ("DIAGNOSTIC_WORKER_TIMEOUT", 1))
        self.assertLess(time.monotonic() - before, 2)

    @unittest.skipUnless(hasattr(os, "fork"), "Linux diagnostic supervisor uses fork")
    def test_worker_eof_does_not_bypass_exit_deadline(self):
        args = SimpleNamespace(vram_budget_gib=8.0, port=8000)
        with patch.object(startup.os, "_exit", side_effect=lambda code: time.sleep(5)):
            before = time.monotonic()
            record = startup._diagnostic_worker(FakeOperations(), args, test_only=True, timeout=.1)
        self.assertEqual((record["errorCode"], record["exitCode"]), ("DIAGNOSTIC_WORKER_TIMEOUT", 1))
        self.assertLess(time.monotonic() - before, 2)

    @unittest.skipUnless(hasattr(os, "fork"), "Linux diagnostic supervisor uses fork")
    def test_sigterm_cancels_worker_reaps_child_and_never_opens_service(self):
        # Isolate the real SIGTERM in a subprocess so the unittest runner is safe.
        script = r'''
import json, os, signal, sys, threading
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import startup
from test_startup import FakeOperations
native_fork = os.fork
worker_pids = []
served = []
def tracked_fork():
    pid = native_fork()
    if pid:
        worker_pids.append(pid)
    return pid
def serve(*args, **kwargs):
    served.append(True)
    return 2
timer = threading.Timer(.15, lambda: os.kill(os.getpid(), signal.SIGTERM))
before = signal.getsignal(signal.SIGTERM)
timer.start()
try:
    with patch.object(startup.os, "fork", tracked_fork), patch.object(startup.records, "persist_record", return_value={}):
        result = startup.main([], operations=FakeOperations(delay=5),
          environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic"},
          privilege_drop=lambda account: None, diagnostic_service=serve)
finally:
    timer.cancel()
    timer.join()
reaped = False
try:
    os.waitpid(worker_pids[0], os.WNOHANG)
except ChildProcessError:
    reaped = True
group_gone = False
try:
    os.killpg(worker_pids[0], 0)
except ProcessLookupError:
    group_gone = True
print(json.dumps({"result": result, "reaped": reaped, "groupGone": group_gone,
                  "served": bool(served), "handlerRestored": signal.getsignal(signal.SIGTERM) == before}))
'''
        process = subprocess.run([sys.executable, "-c", script, str(HERE), str(HERE / "tests")],
                                 capture_output=True, text=True, timeout=5, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        values = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(values[-1], {"result": 143, "reaped": True, "groupGone": True,
                                     "served": False, "handlerRestored": True})
        self.assertEqual(values[0]["errorCode"], "DIAGNOSTIC_WORKER_INTERRUPTED")
        self.assertNotIn("secret-canary", process.stdout + process.stderr)

    def test_profile_observer_is_restored_after_failure(self):
        previous = sys.getprofile()
        self.invoke(FakeOperations(prepare_error=PermissionError(errno.EPERM, "private"), storage=True))
        self.assertIs(sys.getprofile(), previous)


if __name__ == "__main__":
    unittest.main()
