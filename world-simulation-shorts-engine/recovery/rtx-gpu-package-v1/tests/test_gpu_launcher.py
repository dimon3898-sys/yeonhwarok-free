"""Injected CPU control-flow checks; none of these certify physical GPU PASS."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import stat
from subprocess import CompletedProcess
import tempfile
import unittest
from unittest import mock

import gpu_launcher as launcher
from deployment.gcube.gpu import GPUError


DEVICE_UUID = "GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
MODEL = "NVIDIA GeForce RTX 4080 SUPER"
DRIVER = "580.95.05"


def source_report(_):
    return {"status": "PASS", "files": 200, "sourceContractSha256": "a" * 64}


def probe_report(model=MODEL, total=16376, *, profile="egl"):
    identity = "ANGLE (NVIDIA, " + model + ", OpenGL)"
    return {"render_mode": "gpu-required", "gpu_profile": profile,
            "gpu_rendering_verified": True, "hardware_status": "visible",
            "browser_started": True, "browser_version": "154.0.8037.57",
            "profile_fingerprint": "b" * 64,
            "nvidia_devices": [{"name": model, "uuid": DEVICE_UUID,
                                "driver_version": DRIVER, "memory_total_mib": total}],
            "webgl": {"context_available": True, "context_version": 2,
                      "debug_renderer_available": True, "draw_passed": True,
                      "renderer": identity, "unmasked_renderer": identity,
                      "vendor": "NVIDIA", "unmasked_vendor": "NVIDIA",
                      "pixel": [255, 0, 0, 255], "webgl_error": 0},
            "diagnostics": {}, "adapter_source_hashes": {"gpu.py": "c" * 64}}


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="rtx-launcher-unit-", dir="/tmp")
        self.addCleanup(self.directory.cleanup)
        self.config = launcher.LauncherConfig(storage_root=Path(self.directory.name) / "storage")
        self.events = []
        self.model, self.total, self.free = MODEL, 16376, 14000
        self.report = probe_report()

    def runner(self, command, **kwargs):
        self.events.append(("smi", command))
        self.assertEqual(command[0], "nvidia-smi")
        self.assertEqual(kwargs["timeout"], 10)
        output = f"{self.model}, {DEVICE_UUID}, {DRIVER}, {self.total}, {self.free}\n"
        return CompletedProcess(command, 0, output, "")

    def prepare(self, env):
        self.events.append(("prepare", env["WORLD_ENGINE_RENDER_MODE"]))
        return {"VK_DRIVER_FILES": "/run/world-engine/unit-test-icd.json"}, {"status": "UNIT_TEST_ONLY"}

    def probe(self, *, environ, runner):
        self.events.append(("probe", environ["WORLD_ENGINE_GPU_PROFILE"]))
        report = deepcopy(self.report)
        report["gpu_profile"] = environ["WORLD_ENGINE_GPU_PROFILE"]
        return report

    def dependencies(self, **extra):
        options = dict(environ={"WORLD_ENGINE_GPU_PROFILE": "egl"}, source_validator=source_report,
                       runner=self.runner, runtime_prepare=self.prepare, probe=self.probe,
                       shm_reader=lambda: {"capacityBytes": 2 * launcher.GIB,
                                           "availableBytes": 2 * launcher.GIB})
        options.update(extra)
        return options

    def admit(self, **extra):
        return launcher.admit_gpu(self.config, **self.dependencies(**extra))

    def test_kernel_capture_guard_blocks_concurrent_jobs_then_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            with launcher.capture_guard(Path(directory)):
                with self.assertRaises(launcher.LauncherError) as blocked:
                    with launcher.capture_guard(Path(directory)):
                        self.fail("parallel capture acquired guard")
                self.assertEqual(blocked.exception.code, "GPU_CAPTURE_ALREADY_RUNNING")
            with launcher.capture_guard(Path(directory)):
                pass

    def test_parent_signal_handlers_restore_after_interruption(self):
        from types import SimpleNamespace
        admission = SimpleNamespace(test_only=False, output_root=Path(tempfile.gettempdir()))
        handlers = {}
        def install(number, callback):
            handlers[number] = callback
        def body(*args, **kwargs):
            handlers[launcher.signal.SIGTERM](launcher.signal.SIGTERM, None)
        with mock.patch.object(launcher, "capture_guard") as guard, \
             mock.patch.object(launcher.signal, "getsignal", return_value="previous"), \
             mock.patch.object(launcher.signal, "signal", side_effect=install), \
             mock.patch.object(launcher, "_render_65422", side_effect=body):
            with self.assertRaises(launcher.LauncherError) as blocked:
                launcher.render_65422(admission, launcher.LauncherConfig())
            self.assertEqual(blocked.exception.code, "GPU_RENDER_INTERRUPTED")
            self.assertEqual(set(handlers.values()), {"previous"})

    def test_allowed_models_and_physical_memory_threshold(self):
        for model, total in ((MODEL, 15360), ("NVIDIA GeForce RTX 4090", 24564),
                             ("NVIDIA GeForce RTX 5090", 32607)):
            with self.subTest(model=model):
                self.model, self.total, self.free = model, total, total
                self.report = probe_report(model, total)
                admitted = self.admit()
                self.assertEqual(admitted.safe_report["physicalMemoryMiB"], total)
                self.assertTrue(admitted.test_only)
                self.assertEqual(admitted.safe_report["status"], "TEST_ONLY")
                self.assertFalse(admitted.safe_report["gpuRenderingVerified"])

    def test_unsupported_or_not_super_models_fail_before_profile_or_node(self):
        for name in ("NVIDIA GeForce RTX 4080", "NVIDIA GeForce RTX 4090 Laptop GPU",
                     "NVIDIA RTX A6000", "NVIDIA Tesla T4", "AMD Radeon RX 7900", "RTX 5090 Ti"):
            with self.subTest(model=name):
                self.model = name
                self.events.clear()
                with self.assertRaisesRegex(launcher.LauncherError, "GPU_MODEL_UNSUPPORTED"):
                    self.admit()
                self.assertEqual([e[0] for e in self.events], ["smi"])

    def test_less_than_15_gib_physical_memory_fails_before_probe(self):
        self.total, self.free = 15359, 15359
        with self.assertRaisesRegex(launcher.LauncherError, "GPU_PHYSICAL_MEMORY_INSUFFICIENT"):
            self.admit()
        self.assertEqual([e[0] for e in self.events], ["smi"])

    def test_missing_nvidia_smi_and_nonzero_query_fail_without_profile_probe(self):
        def absent(*args, **kwargs):
            raise FileNotFoundError("PRIVATE_FAKE_DETAIL")
        with self.assertRaisesRegex(launcher.LauncherError, "GPU_HARDWARE_UNAVAILABLE"):
            self.admit(runner=absent)
        with self.assertRaisesRegex(launcher.LauncherError, "GPU_HARDWARE_UNAVAILABLE"):
            self.admit(runner=lambda *a, **k: CompletedProcess(a, 1, "", "PRIVATE_FAKE_DETAIL"))
        self.assertEqual(self.events, [])

    def test_ambiguous_multi_gpu_allocation_is_rejected(self):
        line = f"{MODEL}, {DEVICE_UUID}, {DRIVER}, 16376, 14000\n"
        with self.assertRaisesRegex(launcher.LauncherError, "GPU_ALLOCATION_AMBIGUOUS"):
            self.admit(runner=lambda *a, **k: CompletedProcess(a, 0, line + line, ""))
        self.assertEqual(self.events, [])

    def test_cpu_mode_invalid_profile_and_invalid_budget_never_query_hardware(self):
        for env in ({"WORLD_ENGINE_RENDER_MODE": "cpu"}, {"WORLD_ENGINE_GPU_PROFILE": "swiftshader"}):
            with self.subTest(env=env), self.assertRaises(launcher.LauncherError):
                self.admit(environ=env)
        for budget in (True, 0, -1, float("nan"), float("inf"), 10**400, 1e-100):
            with self.subTest(budget=budget), self.assertRaises(launcher.LauncherError):
                launcher.admit_gpu(launcher.LauncherConfig(budget_gib=budget), **self.dependencies())
        self.assertEqual(self.events, [])

    def test_default_budget_and_free_memory_reserve_enforced(self):
        self.free = 10 * 1024
        admitted = self.admit()
        self.assertEqual(admitted.safe_report["vramBudgetBytes"], 8 * launcher.GIB)
        self.assertEqual(admitted.safe_report["reservedMemoryBytes"], 2 * launcher.GIB)
        self.free -= 1
        self.events.clear()
        with self.assertRaisesRegex(launcher.LauncherError, "GPU_VRAM_BUDGET_EXCEEDS_AVAILABLE"):
            self.admit()
        self.assertEqual([e[0] for e in self.events], ["smi"])

    def test_shared_memory_floor_and_two_gib_recommendation(self):
        with self.assertRaisesRegex(launcher.LauncherError, "SHARED_MEMORY_INSUFFICIENT"):
            self.admit(shm_reader=lambda: {"capacityBytes": launcher.GIB, "availableBytes": launcher.GIB - 1})
        admitted = self.admit(shm_reader=lambda: {"capacityBytes": launcher.GIB, "availableBytes": launcher.GIB})
        self.assertEqual(admitted.safe_report["warnings"], ["SHARED_MEMORY_2_GIB_RECOMMENDED"])

    def test_bad_source_contract_prevents_all_hardware_activity(self):
        for report in ({"status": "FAIL"}, True, {"status": "PASS", "files": 0, "sourceContractSha256": "a" * 64}):
            with self.subTest(report=report), self.assertRaisesRegex(launcher.LauncherError, "SOURCE_CONTRACT_INVALID"):
                self.admit(source_validator=lambda _: report)
        self.assertEqual(self.events, [])

    def test_actual_pixel_probe_rejects_software_failed_draw_or_wrong_model(self):
        for mutation in ("software", "draw", "model", "missing_debug"):
            with self.subTest(mutation=mutation):
                self.report = probe_report()
                if mutation == "software":
                    self.report["webgl"]["unmasked_renderer"] = "ANGLE (Google, SwiftShader Device)"
                elif mutation == "draw":
                    self.report["webgl"]["pixel"] = [0, 0, 0, 255]
                elif mutation == "model":
                    self.report["webgl"]["unmasked_renderer"] = "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090, OpenGL)"
                else:
                    self.report["webgl"]["debug_renderer_available"] = False
                with self.assertRaises(launcher.LauncherError):
                    self.admit()

    def test_probe_identity_cannot_change_from_allocation(self):
        self.report["nvidia_devices"][0]["uuid"] = "GPU-ffffffff"
        with self.assertRaisesRegex(launcher.LauncherError, "GPU_ALLOCATION_CHANGED_DURING_PROBE"):
            self.admit()

    def test_unspecified_profile_uses_legacy_bounded_vulkan_then_egl_selection(self):
        def fallback(*, environ, runner):
            if environ["WORLD_ENGINE_GPU_PROFILE"] == "vulkan":
                raise GPUError("GPU_WEBGL_UNVERIFIED")
            return self.probe(environ=environ, runner=runner)
        admitted = self.admit(environ={}, probe=fallback)
        self.assertEqual(admitted.environ["WORLD_ENGINE_GPU_PROFILE"], "egl")
        self.assertEqual(admitted.private_report["probe"]["safe_profile_attempts"],
                         [{"profile": "vulkan", "status": "failed", "error_code": "GPU_WEBGL_UNVERIFIED"},
                          {"profile": "egl", "status": "verified"}])

    def test_admission_persists_private_uuid_and_safe_model_driver_without_environment_dump(self):
        admitted = self.admit(environ={"WORLD_ENGINE_GPU_PROFILE": "egl", "FAKE_SECRET": "NEVER_SAVE_THIS"})
        private = json.loads(admitted.admission_file.read_text())
        safe = json.loads(admitted.admission_file.with_name("admission_safe.json").read_text())
        self.assertEqual(private["allocation"]["uuid"], DEVICE_UUID)
        self.assertEqual(safe["model"], "RTX 4080 SUPER")
        self.assertEqual(safe["driverVersion"], DRIVER)
        self.assertNotIn("uuid", json.dumps(safe))
        self.assertNotIn("NEVER_SAVE_THIS", admitted.admission_file.read_text())
        self.assertEqual(stat.S_IMODE(admitted.admission_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(admitted.admission_file.parent.stat().st_mode), 0o700)
        self.assertEqual(admitted.environ["CHROMIUM_PATH"], str(launcher.ENGINE_ROOT / "deployment/gcube/chromium_wrapper.py"))
        self.assertEqual(admitted.environ["RTX_GPU_VRAM_BUDGET_BYTES"], str(8 * launcher.GIB))

    def test_unit_admission_cannot_start_production_process_or_server(self):
        admitted = self.admit()
        with mock.patch.object(launcher.subprocess, "run", side_effect=AssertionError("must not run Node")):
            with self.assertRaisesRegex(launcher.LauncherError, "TEST_ADMISSION_NOT_EXECUTABLE"):
                launcher.render_65422(admitted, self.config)
        with mock.patch.object(launcher, "ThreadingHTTPServer", side_effect=AssertionError("must not bind")):
            with self.assertRaisesRegex(launcher.LauncherError, "TEST_ADMISSION_NOT_EXECUTABLE"):
                launcher.serve_health(admitted, self.config)

    def test_render_delegation_arguments_and_nonzero_exit(self):
        admitted = self.admit()
        run = mock.Mock(return_value=CompletedProcess([], 0))
        launcher.render_65422(admitted, self.config, runner=run)
        command = run.call_args.args[0]
        self.assertEqual(command[0], "node")
        self.assertEqual(command[1], str(launcher.HERE / "hardware_render.mjs"))
        self.assertEqual(command[2:], ["--admission-file", str(admitted.admission_file),
                                       "--output-root", str(admitted.output_root)])
        self.assertEqual(run.call_args.kwargs["env"]["WORLD_ENGINE_GPU_PROFILE"], "egl")
        run.return_value = CompletedProcess([], 1)
        with self.assertRaisesRegex(launcher.LauncherError, "GPU_RENDER_PROCESS_FAILED"):
            launcher.render_65422(admitted, self.config, runner=run)

    def test_render_memory_monitor_terminates_budget_growth_or_reserve_violation(self):
        admitted = self.admit()
        for free in (5000, 2047):
            with self.subTest(free=free):
                process = mock.Mock(pid=987654, returncode=0)
                process.poll.side_effect = [None, None, None, None]
                process.wait.return_value = 0
                stop = mock.Mock()
                self.free = free
                with self.assertRaisesRegex(launcher.LauncherError, "GPU_RENDER_VRAM_BUDGET_EXCEEDED"):
                    launcher.render_65422(admitted, self.config, process_factory=lambda *a, **k: process,
                                         memory_runner=self.runner, stop_group=stop, sleep=lambda _: None)
                stop.assert_called_once_with(process.pid, launcher.signal.SIGTERM)

    def test_render_memory_monitor_fail_closed_on_query_failure(self):
        admitted = self.admit()
        process = mock.Mock(pid=987654, returncode=0)
        process.poll.side_effect = [None, None, None, None]
        def missing(*a, **k):
            raise FileNotFoundError()
        stop = mock.Mock()
        with self.assertRaisesRegex(launcher.LauncherError, "GPU_HARDWARE_UNAVAILABLE"):
            launcher.render_65422(admitted, self.config, process_factory=lambda *a, **k: process,
                                 memory_runner=missing, stop_group=stop, sleep=lambda _: None)
        stop.assert_called_once()

    def test_render_deadline_terminates_process_without_unbounded_polling(self):
        admitted = self.admit()
        process = mock.Mock(pid=987654, returncode=0)
        process.poll.side_effect = [None, None, None]
        stop = mock.Mock()
        clock = mock.Mock(side_effect=[0, self.config.render_timeout_seconds])
        with self.assertRaisesRegex(launcher.LauncherError, "GPU_RENDER_DEADLINE_EXCEEDED"):
            launcher.render_65422(admitted, self.config, process_factory=lambda *a, **k: process,
                                 memory_runner=mock.Mock(side_effect=AssertionError("deadline first")),
                                 clock=clock, sleep=lambda _: None, stop_group=stop)
        stop.assert_called_once()

    def test_health_only_handler_never_echoes_private_details_or_accepts_jobs(self):
        admitted = self.admit()
        handler = launcher.health_handler(admitted).__new__(launcher.health_handler(admitted))
        handler.send_response, handler.send_header, handler.end_headers = mock.Mock(), mock.Mock(), mock.Mock()
        handler.wfile = io.BytesIO()
        handler.path = "/healthz"
        handler.do_GET()
        body = json.loads(handler.wfile.getvalue())
        self.assertFalse(body["autoRender"])
        self.assertFalse(body["renderExecuted"])
        self.assertNotIn(DEVICE_UUID, handler.wfile.getvalue().decode())
        self.assertNotIn(str(admitted.admission_file), handler.wfile.getvalue().decode())
        handler.wfile = io.BytesIO()
        handler.path = "/arbitrary-command?secret=FAKE"
        handler.do_GET()
        self.assertEqual(handler.send_response.call_args.args, (404,))
        self.assertNotIn("FAKE", handler.wfile.getvalue().decode())
        handler.wfile = io.BytesIO()
        handler.do_POST()
        self.assertEqual(handler.send_response.call_args.args, (405,))

    def test_default_main_serves_only_after_gates_and_check_does_not_serve_or_render(self):
        server = mock.Mock()
        factory = mock.Mock(return_value=server)
        with redirect_stdout(io.StringIO()):
            result = launcher.main(["--check"], config=self.config, server_factory=factory,
                                   render_runner=mock.Mock(side_effect=AssertionError("no render")), **self.dependencies())
        self.assertEqual(result, 0)
        factory.assert_not_called()
        launcher.main([], config=self.config, server_factory=factory, **self.dependencies())
        factory.assert_called_once()
        self.assertEqual(factory.call_args.args[0], ("0.0.0.0", 8000))
        server.serve_forever.assert_called_once()
        server.server_close.assert_called_once()

    def test_failed_cli_admission_never_dispatches_and_persists_sanitized_failure(self):
        factory, render = mock.Mock(), mock.Mock()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = launcher.main(["--render-65422"], config=self.config, source_validator=lambda _: {"status": "FAIL"},
                                   server_factory=factory, render_runner=render, runner=self.runner)
        self.assertEqual(result, 2)
        factory.assert_not_called()
        render.assert_not_called()
        self.assertEqual(self.events, [])
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertFalse(payload["gpuRenderingVerified"])
        self.assertEqual(len(list(self.config.storage_root.glob("diagnostics/*/admission_private.json"))), 1)

    def test_missing_gpu_cli_check_is_blocked_before_browser_render_or_server(self):
        def no_hardware(*args, **kwargs):
            raise FileNotFoundError("FAKE_PRIVATE_QUERY_DETAIL")
        factory, render, probe = mock.Mock(), mock.Mock(), mock.Mock()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = launcher.main(["--check"], config=self.config, source_validator=source_report,
                                   runner=no_hardware, probe=probe, runtime_prepare=self.prepare,
                                   shm_reader=lambda: {}, server_factory=factory, render_runner=render)
        self.assertEqual(result, 2)
        factory.assert_not_called()
        render.assert_not_called()
        probe.assert_not_called()
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["reasonCode"], "GPU_HARDWARE_UNAVAILABLE")
        self.assertNotIn("FAKE_PRIVATE_QUERY_DETAIL", stderr.getvalue())

    def test_persistent_diagnostics_failure_prevents_dispatch_even_after_probe(self):
        root = Path(self.directory.name) / "not-a-directory"
        root.write_bytes(b"unit fixture")
        config = launcher.LauncherConfig(storage_root=root)
        server, render = mock.Mock(), mock.Mock()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = launcher.main(["--render-65422"], config=config, server_factory=server,
                                   render_runner=render, **self.dependencies())
        self.assertEqual(result, 2)
        server.assert_not_called()
        render.assert_not_called()
        self.assertFalse(json.loads(stderr.getvalue())["diagnosticsPersisted"])

    def test_cli_does_not_offer_mock_cpu_or_arbitrary_commands(self):
        for option in ("--mock-gpu", "--cpu", "--command", "--gpu-pass"):
            with self.subTest(option=option), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                launcher.main([option], config=self.config)
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
