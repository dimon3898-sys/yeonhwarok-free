"""Focused CPU tests of new storage/API composition; GPU outcomes are mocked."""
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import errno
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import launch


class FakeBootstrap:
    def __init__(self, operations):
        self.operations = operations

    def _directory(self, path):
        if self.operations.prepare_error:
            raise self.operations.prepare_error
        return path

    def prepare_environment(self, account, *, storage):
        self.operations.calls.append(("prepare", storage))
        self._directory(storage)
        self.operations.prepared = True


class FakeGPU:
    def __init__(self, operations):
        self.operations = operations

    def LauncherConfig(self, **options):
        self.operations.config = SimpleNamespace(**options)
        return self.operations.config

    def admit_gpu(self, config):
        self.operations.calls.append(("gpu", config.storage_root))
        if self.operations.gpu_error:
            raise self.operations.gpu_error
        return SimpleNamespace(test_only=False, safe_report={"status": "GPU_VERIFIED"})

    def render_65422(self, admission, config):
        self.operations.rendered = True
        return 0

    def serve_health(self, admission, config):
        self.operations.served = True

    @contextmanager
    def capture_guard(self, root):
        yield


class FakeOperations:
    def __init__(self, *, prepare_error=None, gpu_error=None, source_error=None):
        self.prepare_error, self.gpu_error, self.source_error = prepare_error, gpu_error, source_error
        self.calls = []
        self.config = None
        self.prepared = self.rendered = self.served = False
        self.device = FakeGPU(self)

    def account(self):
        return SimpleNamespace(pw_uid=1000, pw_gid=1000)

    def bootstrap(self):
        return FakeBootstrap(self)

    def source(self):
        self.calls.append(("source", None))
        if self.source_error:
            raise self.source_error
        return {"status": "PASS"}

    def dependencies(self):
        self.calls.append(("dependency", None))
        return {"status": "PASS"}

    def gpu(self):
        return self.device


class FakeSession:
    private_root = Path("/var/lib/world-engine-private/engine/session-test-only")
    export_name = "world-engine-export-test-only"

    def __init__(self, operations, *, preflight_error=None, export_error=None):
        self.operations, self.preflight_error, self.export_error = operations, preflight_error, export_error
        self.records, self.results = [], 0

    def preflight(self):
        if not self.operations.prepared:
            raise RuntimeError("preflight-before-original-bootstrap")
        self.operations.calls.append(("preflight", self.private_root))
        if self.preflight_error:
            raise self.preflight_error
        return {"private": {"uid": 1000, "gid": 1000, "mode": "0700", "filesystem": "overlay"},
                "export": {"mountedViewReadbackVerified": True, "remotePersistenceVerified": False,
                           "externalDownloadVerified": False, "privateDataAllowed": False},
                "password": "secret-canary-storage-value"}

    def export_safe_record(self, record):
        if self.export_error:
            raise self.export_error
        self.records.append(record)
        return {"status": "EXPORTED"}

    def export_results(self):
        self.results += 1
        if self.export_error:
            raise self.export_error
        return {"status": "EXPORTED"}


class GPUFailure(RuntimeError):
    code = "GPU_HARDWARE_UNAVAILABLE"
    diagnostics = {}


@contextmanager
def captured():
    events, saved, output = [], [], io.StringIO()
    with patch.object(launch.records, "emit_record", side_effect=lambda value: events.append(value)), \
         patch.object(launch.records, "persist_record", side_effect=lambda record, roots=None: saved.append(roots) or {"persisted": True}), \
         redirect_stdout(output), redirect_stderr(output):
        yield events, saved, output


@contextmanager
def original_launcher_for_lock_test():
    package = launch.startup.PACKAGE
    if not (package / "gpu_launcher.py").is_file():
        package = HERE.parent / "rtx-gpu-package-v1"
    name = "world_engine_original_launcher_lock_test_only"
    with patch.object(sys, "path", [str(package), str(package.parents[1]), *sys.path]), patch.dict(sys.modules):
        spec = importlib.util.spec_from_file_location(name, package / "gpu_launcher.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        yield module


class LaunchTests(unittest.TestCase):
    def invoke(self, operations, session, argv=None, **options):
        with captured() as captures:
            result = launch.main(argv or [], operations=operations, session_factory=lambda account: session, **options)
        return result, captures

    def test_same_selected_private_path_reaches_original_bootstrap_and_gpu_config(self):
        operations = FakeOperations(gpu_error=GPUFailure("mock-no-nvidia"))
        session = FakeSession(operations)
        result, (events, saved, output) = self.invoke(operations, session, ["--check"])
        self.assertEqual(result, 2)
        self.assertEqual([item[0] for item in operations.calls], ["prepare", "preflight", "source", "dependency", "gpu"])
        self.assertEqual(operations.calls[0][1], session.private_root)
        self.assertEqual(operations.config.storage_root, session.private_root)
        self.assertEqual(events[-1]["errorCode"], "GPU_HARDWARE_UNAVAILABLE")
        self.assertEqual(saved, [[session.private_root / "startup-diagnostics"]])
        self.assertEqual(session.records[-1]["errorCode"], "GPU_HARDWARE_UNAVAILABLE")
        self.assertNotIn("secret-canary", output.getvalue())
        self.assertFalse(events[-1]["gpuRenderingVerified"])

    def test_gpu_facade_delegates_actual_methods_without_substitution(self):
        operations = FakeOperations()
        session = FakeSession(operations)
        selected = launch.StorageOperations(operations, session, mode="normal", test_only=True)
        facade = selected.gpu()
        self.assertEqual(facade.admit_gpu, operations.device.admit_gpu)
        self.assertEqual(facade.render_65422, operations.device.render_65422)
        self.assertEqual(facade.serve_health, operations.device.serve_health)
        self.assertEqual(facade.capture_guard, operations.device.capture_guard)
        config = facade.LauncherConfig(budget_gib=8.0, port=8000)
        self.assertEqual(config.storage_root, session.private_root)

    def test_private_bootstrap_failure_remains_storage_stage_without_mount_prefix(self):
        operations = FakeOperations(prepare_error=PermissionError(errno.EPERM, "private-secret-path"))
        session = FakeSession(operations)
        result, (events, _, output) = self.invoke(operations, session)
        self.assertEqual((result, events[0]["stage"], events[0]["errorCode"]), (1, "STORAGE", "STORAGE_PERMISSION_DENIED"))
        self.assertEqual([item[0] for item in operations.calls], ["prepare"])
        self.assertNotIn("private-secret-path", output.getvalue())

    def test_shared_preflight_failure_blocks_before_source_or_gpu(self):
        operations = FakeOperations()
        error = launch.storage.StorageError("STORAGE_UNAVAILABLE", {"stage": "EXPORT", "reason": "EXPORT_PROBE_FAILED", "errnoName": "EROFS"})
        session = FakeSession(operations, preflight_error=error, export_error=error)
        result, (events, _, output) = self.invoke(operations, session)
        self.assertEqual(result, 1)
        self.assertEqual(events[0]["stage"], "STORAGE")
        self.assertEqual(events[0]["errorCode"], "STORAGE_UNAVAILABLE")
        self.assertEqual([item[0] for item in operations.calls], ["prepare", "preflight"])
        self.assertIn('"errnoName": "EROFS"', output.getvalue())

    def test_source_failure_stops_native_gpu(self):
        operations = FakeOperations(source_error=ValueError("source-secret"))
        result, (events, _, output) = self.invoke(operations, FakeSession(operations))
        self.assertEqual((result, events[0]["stage"]), (1, "SOURCE_INTEGRITY"))
        self.assertEqual([item[0] for item in operations.calls], ["prepare", "preflight", "source"])
        self.assertNotIn("source-secret", output.getvalue())

    def test_all_python_injected_successes_are_blocked_from_production_dispatch(self):
        for argv in ([], ["--check"], ["--render-65422"]):
            with self.subTest(argv=argv):
                operations = FakeOperations()
                session = FakeSession(operations)
                result, (events, _, _) = self.invoke(operations, session, argv)
                self.assertEqual((result, events[-1]["errorCode"]), (2, "TEST_SEAM_PRODUCTION_DISPATCH_BLOCKED"))
                self.assertFalse(operations.rendered)
                self.assertFalse(operations.served)
                self.assertEqual(session.results, 0)

    def test_explicit_storage_check_never_admits_gpu_or_serves(self):
        operations = FakeOperations()
        result, (events, _, output) = self.invoke(operations, FakeSession(operations), ["--check-storage"])
        self.assertEqual(result, 0)
        self.assertEqual([item[0] for item in operations.calls], ["prepare", "preflight", "source", "dependency"])
        record = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(record["status"], "STORAGE_ONLY_VERIFIED")
        self.assertFalse(record["gpuRenderingVerified"])
        self.assertFalse(record["renderAllowed"])
        self.assertTrue(record["testOnly"])
        self.assertEqual(events, [])

    def test_storage_only_check_preserves_source_and_dependency_failure_stages(self):
        for stage in ("SOURCE_INTEGRITY", "DEPENDENCY"):
            with self.subTest(stage=stage):
                operations = FakeOperations(source_error=ValueError("secret-source") if stage == "SOURCE_INTEGRITY" else None)
                if stage == "DEPENDENCY":
                    operations.dependencies = Mock(side_effect=ImportError("secret-dependency"))
                result, (events, _, output) = self.invoke(operations, FakeSession(operations), ["--check-storage"])
                self.assertEqual((result, events[0]["stage"]), (1, stage))
                self.assertNotIn("secret-source", output.getvalue())
                self.assertNotIn("secret-dependency", output.getvalue())
                self.assertFalse(operations.rendered)
                self.assertFalse(operations.served)

    def test_render_export_requires_verified_nonempty_public_results(self):
        valid = {"status": "EXPORTED", "captures": 1, "files": 3,
                 "mountedViewReadbackVerified": True, "privateDataAllowed": False,
                 "remotePersistenceVerified": False, "externalDownloadVerified": False}
        session = SimpleNamespace(export_results=Mock(return_value=valid))
        with captured():
            self.assertEqual(launch._export_render_results(session, test_only=True), valid)
        for report in ({"status": "NO_PUBLIC_RESULTS", "captures": 0, "files": 0},
                       {**valid, "captures": 0}, {**valid, "files": 0},
                       {**valid, "mountedViewReadbackVerified": False},
                       {**valid, "remotePersistenceVerified": True},
                       {**valid, "externalDownloadVerified": True}):
            with self.subTest(report=report):
                session.export_results.return_value = report
                with self.assertRaises(launch.storage.StorageError):
                    launch._export_render_results(session, test_only=True)

    def test_two_fresh_sessions_share_original_guard_during_render_and_export(self):
        # Actual original kernel/flock guard; fake render/export perform no GPU work.
        with original_launcher_for_lock_test() as native, tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first, second = base / "session-a", base / "session-b"
            first.mkdir(mode=0o700)
            second.mkdir(mode=0o700)
            valid = {"status": "EXPORTED", "captures": 1, "files": 3,
                     "mountedViewReadbackVerified": True, "privateDataAllowed": False,
                     "remotePersistenceVerified": False, "externalDownloadVerified": False}
            other = SimpleNamespace(private_root=second, export_results=Mock(return_value=valid))
            other_gpu = SimpleNamespace(capture_guard=native.capture_guard, render_65422=Mock(return_value=0))
            order = []

            def assert_second_cannot_start():
                with self.assertRaises(native.LauncherError) as failed:
                    launch._render_and_export(other_gpu, None, None, other)
                self.assertEqual(failed.exception.code, "GPU_CAPTURE_ALREADY_RUNNING")

            def render(admission, config):
                order.append("render")
                # The original inner per-session lock is retained and compatible.
                with native.capture_guard(first):
                    assert_second_cannot_start()
                return 0

            def export():
                order.append("export")
                assert_second_cannot_start()
                return valid

            session = SimpleNamespace(private_root=first, export_results=export)
            gpu = SimpleNamespace(capture_guard=native.capture_guard, render_65422=render)
            with patch.object(launch.storage, "PRIVATE_BASE", base), captured():
                self.assertEqual(launch._render_and_export(gpu, None, None, session), 0)
                with native.capture_guard(base):
                    pass  # Successful completion released the common guard.
            self.assertEqual(order, ["render", "export"])
            other_gpu.render_65422.assert_not_called()
            other.export_results.assert_not_called()

    def test_export_failure_releases_original_common_guard_without_success(self):
        with original_launcher_for_lock_test() as native, tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            session = SimpleNamespace(export_results=lambda: {"status": "NO_PUBLIC_RESULTS", "captures": 0, "files": 0})
            gpu = SimpleNamespace(capture_guard=native.capture_guard, render_65422=Mock(return_value=0))
            with patch.object(launch.storage, "PRIVATE_BASE", base):
                with self.assertRaises(launch.storage.StorageError):
                    launch._render_and_export(gpu, None, None, session)
                with native.capture_guard(base):
                    pass

    def test_export_location_prints_only_generated_basenames_and_checked_hashes(self):
        session = SimpleNamespace(export_name="world-engine-export-" + "a" * 24)
        flags = {"status": "EXPORTED", "mountedViewReadbackVerified": True,
                 "remotePersistenceVerified": False, "externalDownloadVerified": False}
        report = {"schema": "WORLD_ENGINE_SAFE_RECORD_EXPORT_V1", "exportName": session.export_name,
                  "file": "startup-safe-" + "b" * 24 + ".json", "sha256": "c" * 64, "bytes": 100,
                  "password": "secret-location-canary", **flags}
        with captured() as (_, _, output):
            self.assertTrue(launch._emit_export_location(session, report, test_only=True))
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["files"][0]["sha256"], "c" * 64)
        self.assertEqual(payload["exportDirectory"], session.export_name)
        self.assertNotIn("secret-location-canary", output.getvalue())
        self.assertFalse(payload["externalDownloadVerified"])
        report["file"] = "/private/location/secret.json"
        with captured() as (_, _, output):
            self.assertFalse(launch._emit_export_location(session, report, test_only=True))
        self.assertEqual(output.getvalue(), "")

    def test_diagnostic_parent_drops_before_export_or_server_and_keeps_blocked_record(self):
        operations = FakeOperations()
        session = FakeSession(operations)
        order = []
        native_export = session.export_safe_record
        session.export_safe_record = lambda record: order.append("export") or native_export(record)
        record = launch.records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, mode="diagnostic", test_only=True)
        def serve(value, **options):
            order.append("serve")
            self.assertFalse(value["renderAllowed"])
            return 2
        result, _ = self.invoke(operations, session, environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic"},
            worker=lambda *args, **options: record, privilege_drop=lambda account: order.append("drop"), diagnostic_service=serve)
        self.assertEqual(result, 2)
        self.assertEqual(order, ["drop", "export", "serve"])

    def test_diagnostic_privilege_failure_never_opens_server(self):
        operations = FakeOperations()
        session = FakeSession(operations)
        serve = Mock()
        def denied(account):
            raise PermissionError(errno.EPERM, "hidden-groups")
        record = launch.records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, mode="diagnostic", test_only=True)
        result, (events, _, _) = self.invoke(operations, session, environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic"},
            worker=lambda *args, **options: record, privilege_drop=denied, diagnostic_service=serve)
        self.assertEqual((result, events[0]["stage"]), (1, "UID_GID"))
        serve.assert_not_called()

    def test_diagnostic_never_accepts_render_or_storage_check_actions(self):
        for argv in (["--render-65422"], ["--check-storage"]):
            operations = FakeOperations()
            session = FakeSession(operations)
            result, (events, _, _) = self.invoke(operations, session, argv, environ={"WORLD_ENGINE_STARTUP_MODE": "diagnostic"})
            self.assertEqual((result, events[0]["errorCode"]), (2, "DIAGNOSTIC_RENDER_FORBIDDEN"))
            self.assertEqual(operations.calls, [])

    def test_safe_export_failure_is_explicit_and_original_gpu_failure_is_preserved(self):
        operations = FakeOperations(gpu_error=GPUFailure("private-error"))
        error = launch.storage.StorageError("STORAGE_UNAVAILABLE", {"stage": "EXPORT", "reason": "IO_UNAVAILABLE"})
        session = FakeSession(operations, export_error=error)
        result, (events, _, output) = self.invoke(operations, session)
        self.assertEqual(result, 2)
        self.assertEqual([value["errorCode"] for value in events], ["GPU_HARDWARE_UNAVAILABLE", "STORAGE_UNAVAILABLE"])
        self.assertIn('"status": "BLOCKED"', output.getvalue())
        self.assertNotIn("private-error", output.getvalue())


if __name__ == "__main__":
    unittest.main()
