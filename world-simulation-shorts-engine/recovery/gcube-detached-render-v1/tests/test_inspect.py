"""Focused synthetic and real-proc inspection tests; never a GPU probe."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("existing_inspection_under_test", HERE / "inspect_existing.py")
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)
BOOT = "01234567-89ab-cdef-0123-456789abcdef"
LAUNCHER = "/opt/world-engine-storage-fix/launch.py"
RENDERER = "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/hardware_render.mjs"


class InspectionTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.private, self.export, self.proc = [self.root / name for name in ("private", "export", "proc")]
        for directory in (self.private, self.export, self.proc):
            directory.mkdir()
        kernel = self.proc / "sys/kernel/random"
        kernel.mkdir(parents=True)
        (kernel / "boot_id").write_text(BOOT + "\n")
        self.control = self.private / "job-control-v1"

    def tearDown(self):
        self.temporary.cleanup()

    def inspect(self, **kwargs):
        return inspector.inspect(self.control, self.private, self.export, _proc_root=self.proc, **kwargs)

    def process(self, pid, command, *, ticks="9000", state="S"):
        directory = self.proc / str(pid)
        directory.mkdir(exist_ok=True)
        # /proc/PID/stat field22 is index19 after the comm's closing parenthesis.
        fields = [state] + ["0"] * 18 + [ticks, "0", "0"]
        (directory / "stat").write_text(str(pid) + " (name with ) parens) " + " ".join(fields))
        (directory / "cmdline").write_bytes(b"\0".join(item.encode() for item in command) + b"\0")

    def capture(self):
        capture = self.private / ("session-" + "a" * 24) / "captures" / ("b" * 64)
        capture.mkdir(parents=True)
        return capture

    def test_clear_is_read_only_and_test_only(self):
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        result = self.inspect()
        self.assertEqual(result["status"], "CLEAR")
        self.assertTrue(result["testOnly"])
        self.assertFalse(result["gpuExecuted"])
        self.assertFalse(result["renderAllowed"])
        self.assertEqual(before, sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")))

    def test_real_proc_is_readable_without_gpu_or_native_process(self):
        result = inspector.inspect(self.control, self.private, self.export, exclude_pids=(os.getpid(),))
        self.assertEqual(result["status"], "CLEAR", result)
        self.assertTrue(result["testOnly"])

    def test_native_role_processes_only_and_no_arguments_leaked(self):
        self.process(41, ["/usr/bin/python3", LAUNCHER, "--render-65422", "secret-value"])
        self.process(42, ["/usr/bin/node", RENDERER, "--admission-file", "private-value"])
        self.process(43, ["/usr/bin/python3", LAUNCHER])  # Existing health-only parent.
        self.process(44, ["/usr/bin/python3", "/tmp/launch.py", "--render-65422"])
        result = self.inspect()
        self.assertEqual(result["status"], "RUNNING")
        self.assertEqual([item["pid"] for item in result["processes"]], [41, 42])
        self.assertEqual(result["processes"][0]["startTime"], "9000")
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("private-value", json.dumps(result))

    def test_current_manager_exclusion_and_zombies(self):
        self.process(41, ["python3", LAUNCHER, "--render-65422"])
        self.process(42, ["node", RENDERER], state="Z")
        self.assertEqual(self.inspect(exclude_pids=(41,))["status"], "CLEAR")
        self.assertEqual(self.inspect(exclude_pids=(True,))["reason"], "INVALID_EXCLUSIONS")

    def test_guard_held_and_stale_file_have_different_results(self):
        guard = self.private / "CAPTURE.guard"
        guard.write_bytes(b"original")
        with guard.open("rb") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.inspect()
            self.assertEqual(result["status"], "RUNNING")
            self.assertEqual(result["evidenceCounts"]["heldCaptureGuards"], 1)
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        self.assertEqual(self.inspect()["status"], "CLEAR")
        self.assertEqual(guard.read_bytes(), b"original")

    def test_existing_capture_never_authorizes_rerender(self):
        capture = self.capture()
        report = capture / "REPORT.json"
        with report.open("wb") as stream:
            stream.truncate(25 * 1024 ** 2)  # Presence is sufficient: no large JSON read.
        (capture / "CAPTURE_STATUS.json").write_text('{"status":"IN_PROGRESS"}')
        result = self.inspect()
        self.assertEqual(result["status"], "EXISTING_RECORDS")
        self.assertEqual(result["evidenceCounts"]["captureReports"], 1)
        self.assertEqual(result["evidenceCounts"]["captureStatusFiles"], 1)

    def test_empty_capture_directory_is_prior_work_too(self):
        self.capture()
        self.assertEqual(self.inspect()["status"], "EXISTING_RECORDS")

    def test_live_lock_requires_matching_pid_boot_and_start(self):
        capture = self.capture()
        self.process(51, ["unrelated-program"], ticks="10")
        lock = {"pid": 51, "bootId": BOOT, "startTime": "10"}
        file = capture / "ACTIVE_CAPTURE_LOCK.json"
        file.write_text(json.dumps(lock))
        result = self.inspect()
        self.assertEqual(result["status"], "RUNNING")
        self.assertEqual(result["processes"][0]["role"], "NATIVE_CAPTURE_LOCK")
        for changed in ({"startTime": "11"}, {"bootId": "11111111-2222-3333-4444-555555555555"}, {"pid": 52}):
            with self.subTest(changed=changed):
                file.write_text(json.dumps({**lock, **changed}))
                self.assertEqual(self.inspect()["status"], "EXISTING_RECORDS")

    def test_invalid_lock_and_symlink_cannot_clear(self):
        capture = self.capture()
        file = capture / "ACTIVE_CAPTURE_LOCK.json"
        file.write_text('{"pid":true}')
        self.assertEqual(self.inspect()["reason"], "CAPTURE_LOCK_INVALID")
        file.unlink()
        file.symlink_to(self.proc / "sys/kernel/random/boot_id")
        self.assertEqual(self.inspect()["status"], "BLOCKED")

    def test_admission_only_session_and_manager_ledger_are_ignored(self):
        diagnostic = self.private / ("session-" + "a" * 24) / "diagnostics"
        diagnostic.mkdir(parents=True)
        (diagnostic / "admission_safe.json").write_text('{"status":"GPU_VERIFIED"}')
        self.control.mkdir()
        (self.control / "JOB.json").write_text('{"status":"WAITING"}')
        self.assertEqual(self.inspect()["status"], "CLEAR")

    def test_shared_capture_blocks_but_startup_exports_do_not(self):
        directory = self.export / ("world-engine-export-" + "c" * 24)
        directory.mkdir()
        (directory / ("startup-safe-" + "d" * 24 + ".json")).write_text("{}")
        self.assertEqual(self.inspect()["status"], "CLEAR")
        capture = directory / ("capture-" + "e" * 12 + "-" + "f" * 24)
        capture.mkdir()
        self.assertEqual(self.inspect()["status"], "EXISTING_RECORDS")
        self.assertEqual(self.inspect()["evidenceCounts"]["sharedCaptureDirectories"], 1)

    def test_original_bootstrap_legacy_captures_block_but_admission_does_not(self):
        legacy = self.export / "rtx-gpu-package-v1"
        (legacy / "diagnostics").mkdir(parents=True)
        self.assertEqual(self.inspect()["status"], "CLEAR")
        captures = legacy / "captures"
        captures.mkdir()
        self.assertEqual(self.inspect()["status"], "CLEAR")
        (captures / ("a" * 64)).mkdir()
        result = self.inspect()
        self.assertEqual(result["status"], "EXISTING_RECORDS")
        self.assertEqual(result["evidenceCounts"]["legacyCaptureDirectories"], 1)

    def test_original_bootstrap_legacy_malformed_or_symlink_capture_is_rejected(self):
        legacy = self.export / "rtx-gpu-package-v1"
        captures = legacy / "captures"
        captures.mkdir(parents=True)
        bad = captures / "not-a-signature"
        bad.mkdir()
        self.assertEqual(self.inspect()["reason"], "LEGACY_CAPTURE_RECORD_INVALID")
        bad.rmdir()
        (captures / ("b" * 64)).symlink_to(self.private, target_is_directory=True)
        self.assertEqual(self.inspect()["status"], "BLOCKED")

    def test_missing_path_bad_proc_and_path_symlinks_block(self):
        self.export.rmdir()
        self.assertEqual(self.inspect()["status"], "BLOCKED")
        self.export.symlink_to(self.private)
        self.assertEqual(self.inspect()["status"], "BLOCKED")
        self.export.unlink()
        self.export.mkdir()
        self.process(80, ["python3", LAUNCHER, "--render-65422"])
        (self.proc / "80/stat").write_text("malformed secret-message")
        result = self.inspect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn("secret-message", json.dumps(result))

    @unittest.skipIf(os.geteuid() == 0, "Requires real unprivileged permissions; no root bypass simulation")
    def test_unreadable_proc_and_mount_block(self):
        self.process(90, ["other"])
        file = self.proc / "90/cmdline"
        file.chmod(0)
        try:
            self.assertEqual(self.inspect()["status"], "BLOCKED")
        finally:
            file.chmod(0o600)
        self.export.chmod(0)
        try:
            self.assertEqual(self.inspect()["status"], "BLOCKED")
        finally:
            self.export.chmod(0o700)

    def test_cli_has_no_override_or_render_arguments(self):
        completed = subprocess.run([sys.executable, str(HERE / "inspect_existing.py"), "--render-65422"],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 2)
        result = json.loads(completed.stdout)
        self.assertEqual(result["reason"], "ARGUMENTS_FORBIDDEN")
        self.assertFalse(result["renderAllowed"])

    def test_one_global_entry_budget_prevents_unbounded_walks(self):
        self.process(41, ["other"])
        self.process(42, ["other"])
        self.capture()
        with mock.patch.object(inspector, "_MAX_ENTRIES", 4):
            self.assertEqual(self.inspect()["reason"], "INSPECTION_LIMIT_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
