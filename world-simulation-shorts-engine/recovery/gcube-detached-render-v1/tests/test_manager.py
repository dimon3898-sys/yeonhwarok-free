"""Focused CPU lifecycle checks for the detached one-shot supervisor.

Native callbacks and seven-file metadata below are synthetic. No test invokes a
GPU admission, renderer, service endpoint or external storage account. The PTY
check closes a real controlling terminal while its detached CPU job is active.
"""
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import job_manager as manager
import job_store


def clear_inspection():
    return {"status": "CLEAR", "reason": "NO_EXISTING_CAPTURE_EVIDENCE",
            "gpuExecuted": False, "renderAllowed": False, "testOnly": True,
            "processes": [], "evidenceCounts": {}}


def result_fixture():
    files = [{"file": "fixture.mp4", "sha256": "0" * 64, "bytes": 1}]
    files += [{"file": "checkpoint-" + str(number) + ".png", "sha256": "1" * 64, "bytes": 1}
              for number in range(5)]
    files += [{"file": "SHA256SUMS", "sha256": "2" * 64, "bytes": 1}]
    return {"schema": "WORLD_ENGINE_EXPORT_LOCATION_V1", "testOnly": True,
            "exportDirectory": "world-engine-export-" + "a" * 24,
            "mountedViewReadbackVerified": True, "remotePersistenceVerified": False,
            "externalDownloadVerified": False, "captures": [{
                "directory": "capture-" + "b" * 12 + "-" + "c" * 24,
                "publicDirectory": "public-review", "completionReceipt": "EXPORT_COMPLETE.json",
                "files": files}]}


def verify_synthetic(result, export_root):
    if result != result_fixture() or not Path(export_root).is_dir():
        raise ValueError("synthetic result rejected")
    return result


def wait_until(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.025)
    raise AssertionError("CPU lifecycle condition timed out")


@unittest.skipUnless(os.geteuid() == 1000 and os.getegid() == 1000,
                     "run focused manager tests as engine UID/GID 1000")
class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="world-job-manager-", dir="/workspace")
        self.root = Path(self.temporary.name)
        self.control, self.export = self.root / "control", self.root / "export"
        self.control.mkdir(mode=0o700)
        self.export.mkdir(mode=0o700)
        self.store = job_store.Store(control_root=self.control, export_root=self.export)
        self.counter = self.root / "invocations"
        self.children = []
        self.identities = []

    def tearDown(self):
        try:
            current = self.store.read()
            if current:
                self.identities.extend(current.get(key) for key in
                                       ("supervisorIdentity", "rendererIdentity"))
        except (job_store.JobError, OSError):
            pass
        for identity in self.identities:
            if identity and manager.is_alive(identity):
                try:
                    os.kill(identity["pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
        for pid in self.children + [item["pid"] for item in self.identities if item]:
            try:
                wait_until(lambda: os.waitpid(pid, os.WNOHANG)[0] == pid, seconds=1)
            except (ChildProcessError, AssertionError):
                pass
        # An abrupt-child test may leave an adopted zombie but no live writer.
        time.sleep(0.02)
        self.temporary.cleanup()

    def increment(self):
        with open(self.counter, "a", encoding="ascii") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.write("invoked\n")
            stream.flush()
            os.fsync(stream.fileno())

    def success_native(self, delay=0.05):
        def run(state, update):
            self.increment()
            time.sleep(delay)
            return {"exitCode": 0, "result": result_fixture(), "firstFailure": None}
        return run

    def start(self, native=None, **kwargs):
        state = manager.start(self.store, native_override=native or self.success_native(),
                              verify_override=verify_synthetic,
                              inspect_override=clear_inspection, **kwargs)
        if isinstance(state, dict) and state.get("supervisorIdentity"):
            self.identities.append(state["supervisorIdentity"])
        return state

    def terminal(self):
        return wait_until(lambda: (lambda state: state if state and state["state"] in
                          {"COMPLETED", "FAILED"} else None)(manager.status(self.store)))

    def count(self):
        return len(self.counter.read_text().splitlines()) if self.counter.exists() else 0

    def assert_refused(self, operation):
        try:
            state = operation()
        except job_store.JobError:
            return
        self.assertIn(state["state"], {"QUEUED", "RUNNING", "COMPLETED", "FAILED"})

    def test_success_records_real_detached_identity_and_safe_completion(self):
        started = self.start(self.success_native(0.15))
        self.assertIn(started["state"], {"QUEUED", "RUNNING"})
        identity = started["supervisorIdentity"]
        self.assertNotEqual(identity["pid"], os.getpid())
        self.assertTrue(manager.is_alive(identity))
        self.assertEqual(os.getsid(identity["pid"]), identity["pid"])
        final = self.terminal()
        self.assertEqual(final["state"], "COMPLETED", final)
        self.assertEqual(final["exitCode"], 0)
        self.assertTrue(final["testOnly"])
        self.assertEqual(final["result"], result_fixture())
        self.assertFalse(final["gpuRenderingVerified"])
        self.assertFalse(final["remotePersistenceVerified"])
        self.assertFalse(final["externalDownloadVerified"])
        self.assertEqual(self.count(), 1)

    def test_shared_claim_exists_before_native_callback(self):
        observed = self.root / "claim-before-native.json"
        def run(state, update):
            claim = self.export / job_store.SHARED_NAME / "CLAIM.json"
            observed.write_text(json.dumps({"exists": claim.is_file(),
                                           "jobId": json.loads(claim.read_text())["jobId"]}))
            return {"exitCode": 0, "result": result_fixture(), "firstFailure": None}
        started = self.start(run)
        self.assertEqual(self.terminal()["state"], "COMPLETED")
        self.assertEqual(json.loads(observed.read_text()), {"exists": True, "jobId": started["jobId"]})

    def test_repeated_start_during_and_after_job_never_dispatches_twice(self):
        self.start(self.success_native(0.25))
        self.assert_refused(lambda: self.start(self.success_native()))
        final = self.terminal()
        self.assertEqual(final["state"], "COMPLETED")
        self.assert_refused(lambda: self.start(self.success_native()))
        self.assertEqual(self.count(), 1)
        self.assertEqual(manager.status(self.store)["jobId"], final["jobId"])

    def test_concurrent_starters_keep_one_native_invocation(self):
        starters = []
        for _ in range(2):
            pid = os.fork()
            if pid == 0:
                try:
                    self.start(self.success_native(0.25))
                except job_store.JobError:
                    pass
                except BaseException:
                    os._exit(91)
                os._exit(0)
            self.children.append(pid)
            starters.append(pid)
        for pid in starters:
            _, exit_status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(exit_status), 0)
        self.assertEqual(self.terminal()["state"], "COMPLETED")
        self.assertEqual(self.count(), 1)

    def test_real_pty_disconnect_does_not_kill_detached_job(self):
        pid, terminal = pty.fork()
        if pid == 0:
            try:
                state = self.start(self.success_native(0.65))
                os.write(1, ("DETACHED_ACK " + state["jobId"] + "\n").encode())
                # Keep the original terminal session alive until HUP is sent.
                signal.pause()
            except BaseException:
                os._exit(92)
            os._exit(0)
        self.children.append(pid)
        output = b""
        try:
            deadline = time.monotonic() + 4
            while b"DETACHED_ACK " not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([terminal], [], [], 0.1)
                if readable:
                    output += os.read(terminal, 8192)
            self.assertIn(b"DETACHED_ACK ", output)
            os.close(terminal)
            terminal = None
            try:
                os.kill(pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            _, exit_status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(exit_status), -signal.SIGHUP)
            final = self.terminal()
            self.assertEqual(final["state"], "COMPLETED", final)
            self.assertEqual(self.count(), 1)
        finally:
            if terminal is not None:
                os.close(terminal)

    def test_first_native_failure_is_preserved_and_no_completion_export(self):
        failure = job_store.records.make_record("WEBGL2", "GPU_WEBGL_UNVERIFIED", 7, test_only=True)
        def run(state, update):
            self.increment()
            return {"exitCode": 7, "result": None, "firstFailure": failure}
        self.start(run)
        final = self.terminal()
        self.assertEqual(final["state"], "FAILED")
        self.assertEqual(final["firstFailure"], failure)
        self.assertEqual(final["exitCode"], 7)
        self.assertIsNone(final["result"])
        self.assert_refused(lambda: self.start())
        self.assertEqual(self.count(), 1)

    def test_unexpected_native_exception_fails_closed_without_leaking_message(self):
        def run(state, update):
            raise RuntimeError("PRIVATE_SECRET_NOT_FOR_SHARED_STATE")
        self.start(run)
        final = self.terminal()
        self.assertEqual(final["state"], "FAILED")
        self.assertNotEqual(final["exitCode"], 0)
        self.assertNotIn("PRIVATE_SECRET", json.dumps(final))
        for path in (self.export / job_store.SHARED_NAME).glob("*.json"):
            self.assertNotIn("PRIVATE_SECRET", path.read_text())

    def test_verifier_rejection_cannot_be_completed(self):
        def reject(result, export_root):
            raise ValueError("SHA_MISMATCH_PRIVATE_PATH")
        state = manager.start(self.store, native_override=self.success_native(),
                              verify_override=reject, inspect_override=clear_inspection)
        self.identities.append(state["supervisorIdentity"])
        final = self.terminal()
        self.assertEqual(final["state"], "FAILED")
        self.assertEqual(final["reason"], "RESULT_VERIFICATION_FAILED")
        self.assertIsNone(final["result"])
        self.assertNotIn("PRIVATE_PATH", json.dumps(final))

    def test_shared_status_write_failure_preserves_private_failure(self):
        shared = self.export / job_store.SHARED_NAME
        def run(state, update):
            self.increment()
            shared.chmod(0o500)  # This freshly-created synthetic namespace only.
            update({"phase": "CAPTURE"})
            raise AssertionError("unreachable after real shared write denial")
        self.start(run)
        try:
            final = self.terminal()
            self.assertEqual(final["state"], "FAILED")
            self.assertEqual(final["reason"], "STORAGE_FAILED")
            self.assertIsNone(final["result"])
            self.assertEqual(self.count(), 1)
        finally:
            shared.chmod(0o700)

    def test_worker_loss_is_terminal_and_never_automatically_restarted(self):
        started = self.start(self.success_native(10))
        wait_until(lambda: self.count() == 1)
        os.kill(started["supervisorIdentity"]["pid"], signal.SIGKILL)
        wait_until(lambda: not manager.is_alive(started["supervisorIdentity"]))
        final = self.terminal()
        self.assertEqual(final["state"], "FAILED")
        self.assertEqual(final["reason"], "WORKER_LOST")
        self.assert_refused(lambda: self.start())
        self.assertEqual(self.count(), 1)

    def test_live_renderer_after_supervisor_loss_vetoes_duplicate_start(self):
        def run(state, update):
            self.increment()
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
            update({"rendererIdentity": manager.process_identity(child.pid)})
            child.wait()
            return {"exitCode": 0, "result": result_fixture(), "firstFailure": None}
        started = self.start(run)
        current = wait_until(lambda: (lambda state: state if state.get("rendererIdentity") else None)(self.store.read()))
        native = current["rendererIdentity"]
        self.identities.append(native)
        os.kill(started["supervisorIdentity"]["pid"], signal.SIGKILL)
        wait_until(lambda: not manager.is_alive(started["supervisorIdentity"]))
        still = manager.status(self.store)
        self.assertEqual(still["state"], "RUNNING")
        self.assertEqual(still["reason"], "NATIVE_STILL_RUNNING")
        self.assert_refused(lambda: self.start())
        self.assertEqual(self.count(), 1)
        os.kill(native["pid"], signal.SIGKILL)
        wait_until(lambda: not manager.is_alive(native))
        self.assertEqual(self.terminal()["reason"], "WORKER_LOST")

    def test_retained_shared_claim_blocks_replay_after_local_record_loss(self):
        self.start()
        self.assertEqual(self.terminal()["state"], "COMPLETED")
        # Simulate loss only inside this test's newly-created control directory.
        for name in ("JOB.json", "CLAIM_RECEIPT.json"):
            (self.control / name).unlink()
        fresh_store = job_store.Store(control_root=self.control, export_root=self.export)
        with self.assertRaises(job_store.JobError):
            manager.start(fresh_store, native_override=self.success_native(),
                          verify_override=verify_synthetic, inspect_override=clear_inspection)
        self.assertEqual(self.count(), 1)

    def test_existing_native_or_ambiguous_evidence_prevents_dispatch(self):
        for status in ("RUNNING", "EXISTING_RECORDS", "BLOCKED"):
            with self.subTest(status=status):
                def inspect_blocked():
                    return {**clear_inspection(), "status": status,
                            "reason": "EXISTING_CAPTURE_REQUIRES_REVIEW"}
                with self.assertRaises(manager.ManagerError):
                    manager.start(self.store, native_override=self.success_native(),
                                  verify_override=verify_synthetic, inspect_override=inspect_blocked)
                self.assertEqual(self.count(), 0)
        self.assertFalse((self.export / job_store.SHARED_NAME).exists())

    def test_process_identity_rejects_pid_reuse_and_dead_process(self):
        identity = manager.process_identity(os.getpid())
        self.assertEqual(set(identity), {"pid", "bootId", "startTime"})
        self.assertTrue(manager.is_alive(identity))
        wrong = {**identity, "startTime": str(int(identity["startTime"]) + 1)}
        self.assertFalse(manager.is_alive(wrong))
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        self.identities.append(manager.process_identity(process.pid))
        process.kill()
        process.wait()
        self.assertFalse(manager.is_alive(self.identities[-1]))


class ExportHandoffTests(unittest.TestCase):
    def test_nondumpable_cpu_subprocess_uses_own_inherited_descriptor(self):
        """Reproduce root-to-UID-drop procfs restrictions without relaxing them.

        Only this fresh CPU child is made non-dumpable. The production runtime
        must pass its pinned fd to FFprobe rather than enabling parent access.
        """
        code = """import ctypes, importlib.util, pathlib, sys, unittest
native = ctypes.CDLL(None, use_errno=True)
assert native.prctl(4, 0, 0, 0, 0) == 0
assert native.prctl(3, 0, 0, 0, 0) == 0
spec = importlib.util.spec_from_file_location('restricted_cpu_media_fixture', pathlib.Path(sys.argv[1]))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
case = fixture.ExportHandoffTests('test_actual_cpu_media_handoff_receipt_hash_and_pinned_descriptor')
result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([case]))
raise SystemExit(0 if result.wasSuccessful() else 1)
"""
        checked = subprocess.run([sys.executable, "-B", "-c", code, str(Path(__file__).resolve())],
                                 capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

    def test_actual_cpu_media_handoff_receipt_hash_and_pinned_descriptor(self):
        """FFprobe inherits its own pinned fd; no parent procfs access is needed.

        Reuses the existing PNG fixture builder only, without running old tests.
        The one solid-color 150-frame MP4 is explicitly synthetic CPU encoding.
        """
        old_fixture = HERE / "cpu-artifact-fixture/tests/test_artifacts.py"
        if not old_fixture.is_file():
            old_fixture = HERE.parent / "gcube-65422-render-v1/tests/test_artifacts.py"
        fixture_spec = importlib.util.spec_from_file_location("png_fixture_builder", old_fixture)
        fixture = importlib.util.module_from_spec(fixture_spec)
        fixture_spec.loader.exec_module(fixture)
        with tempfile.TemporaryDirectory(prefix="world-job-media-", dir="/workspace") as area:
            root = Path(area)
            movie = root / "SYNTHETIC_CPU_ONLY.mp4"
            encoded = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i",
                                      "color=c=0x193652:s=1080x1920:r=30", "-frames:v", "150", "-an",
                                      "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
                                      "-threads", "2", "-pix_fmt", "yuv420p", str(movie)],
                                     capture_output=True, timeout=120, check=False)
            self.assertEqual(encoded.returncode, 0, "SYNTHETIC_CPU_FIXTURE_ENCODING_FAILED")
            names = fixture.v
            bodies = {names.MOVIE: movie.read_bytes(),
                      **{name: fixture.png(index) for index, name in enumerate(names.PNGS)}}
            bodies["SHA256SUMS"] = "".join(hashlib.sha256(body).hexdigest() + "  " + name + "\n"
                                               for name, body in sorted(bodies.items())).encode()
            result = result_fixture()
            capture = result["captures"][0]
            capture["files"] = [{"file": name, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
                                for name, body in sorted(bodies.items())]
            unit = root / result["exportDirectory"] / capture["directory"]
            public = unit / "public-review"
            public.mkdir(parents=True)
            for name, body in bodies.items():
                (public / name).write_bytes(body)
            receipt = unit / "EXPORT_COMPLETE.json"
            receipt_body = json.dumps({"schema": "WORLD_ENGINE_PUBLIC_EXPORT_RECEIPT_V1", "status": "COMPLETE",
                "sourceSha256SumsVerified": True, "remotePersistenceVerified": False,
                "externalDownloadVerified": False, "privateDataAllowed": False,
                "captureId": "b" * 64, "files": capture["files"]})
            receipt.write_text(receipt_body)
            with self.subTest(case="real_cpu_ffprobe_inherited_fd"):
                def source_fingerprint():
                    values = {}
                    for path in public.iterdir():
                        info = path.stat()
                        values[path.name] = ((info.st_dev, info.st_ino, info.st_uid, info.st_gid,
                                             info.st_mode, info.st_nlink, info.st_size,
                                             info.st_mtime_ns, info.st_ctime_ns), path.read_bytes())
                    return values
                source_before = source_fingerprint()
                self.assertEqual(manager.verify_export(result, root), result)
                self.assertEqual(source_fingerprint(), source_before)
            with self.subTest(case="missing_receipt"):
                receipt.unlink()
                with self.assertRaises(FileNotFoundError):
                    manager.verify_export(result, root)
                receipt.write_text(receipt_body)
            with self.subTest(case="corrupted_artifact"):
                (public / names.PNGS[0]).write_bytes(b"SYNTHETIC_CORRUPTION")
                with self.assertRaisesRegex(RuntimeError, "^ARTIFACT_SHA256_MISMATCH$"):
                    manager.verify_export(result, root)


if __name__ == "__main__":
    unittest.main()
