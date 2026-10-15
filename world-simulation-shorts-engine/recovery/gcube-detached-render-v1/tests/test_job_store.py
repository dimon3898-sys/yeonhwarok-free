"""Real CPU filesystem/lock tests; no native GPU admission or rendering."""
from __future__ import annotations

from copy import deepcopy
import json
import multiprocessing
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import job_store


def initial():
    return {"schema": job_store.SCHEMA, "jobId": "65422-" + "a" * 24, "state": "QUEUED",
        "reason": "NEW_JOB", "phase": "QUEUED", "sequence": 0,
        "createdAt": "2026-10-15T00:00:00+00:00", "updatedAt": "2026-10-15T00:00:00+00:00",
        "supervisorIdentity": None, "rendererIdentity": None, "exitCode": None,
        "firstFailure": None, "result": None, "testOnly": True,
        "gpuRenderingVerified": False, "remotePersistenceVerified": False, "externalDownloadVerified": False}


def running(previous):
    value = deepcopy(previous)
    value.update(state="RUNNING", phase="NATIVE_STARTUP", reason="NATIVE_RUNNING",
        updatedAt="2026-10-15T00:00:01+00:00",
        supervisorIdentity={"pid": os.getpid(), "bootId": "a" * 8 + "-" + "b" * 4 + "-" + "c" * 4 + "-" + "d" * 4 + "-" + "e" * 12,
            "startTime": "12345"})
    return value


def completed(previous):
    value = deepcopy(previous)
    names = ["OUTPUT.mp4", *[f"FRAME_{index}.png" for index in range(5)], "SHA256SUMS"]
    value.update(state="COMPLETED", phase="COMPLETE", reason="SUCCEEDED", exitCode=0,
        result={"schema": "WORLD_ENGINE_EXPORT_LOCATION_V1", "exportDirectory": "world-engine-export-" + "b" * 24,
            "testOnly": True, "mountedViewReadbackVerified": True, "remotePersistenceVerified": False,
            "externalDownloadVerified": False, "captures": [{"directory": "capture-" + "c" * 12 + "-" + "d" * 24,
                "publicDirectory": "public-review", "completionReceipt": "EXPORT_COMPLETE.json",
                "files": [{"file": name, "sha256": "e" * 64, "bytes": 42} for name in names]}]})
    return value


def competing_lock(control, export, pipe):
    store = job_store.Store(control_root=control, export_root=export)
    try:
        descriptor = store.lock()
    except job_store.JobError as error:
        pipe.send(error.code)
    else:
        os.close(descriptor)
        pipe.send("UNEXPECTED_SUCCESS")
    pipe.close()


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual((os.geteuid(), os.getegid()), (1000, 1000), "Tests require actual engine UID/GID1000")
        self.temporary = tempfile.TemporaryDirectory(prefix="world-engine-job-store-test-", dir="/workspace")
        self.base = Path(self.temporary.name)
        self.control = self.base / "control"
        self.export = self.base / "export"
        self.control.mkdir(mode=0o700)
        self.export.mkdir(mode=0o700)
        self.store = job_store.Store(control_root=self.control, export_root=self.export)
        self.fd = self.store.lock()

    def tearDown(self):
        os.close(self.fd)
        self.temporary.cleanup()

    def assertCode(self, code, function, *args):
        with self.assertRaises(job_store.JobError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)

    def test_create_claim_private_and_safe_append_readback(self):
        value = self.store.create(initial())
        self.assertEqual(self.store.read(), value)
        self.assertEqual(stat.S_IMODE((self.control / "JOB.json").stat().st_mode), 0o600)
        claim = self.export / job_store.SHARED_NAME / "CLAIM.json"
        self.assertEqual(json.loads(claim.read_bytes())["jobId"], value["jobId"])
        self.assertEqual(len(list(claim.parent.glob("state-000000-*.json"))), 1)
        self.assertFalse(json.loads(claim.read_bytes())["renderAllowed"])

    def test_shared_claim_prevents_second_job_even_when_private_lost(self):
        self.store.create(initial())
        fresh = self.base / "fresh-private"
        fresh.mkdir(mode=0o700)
        restarted = job_store.Store(control_root=fresh, export_root=self.export)
        fd = restarted.lock()
        try:
            self.assertCode("JOB_ALREADY_EXISTS", restarted.create, initial())
            self.assertIsNone(restarted.read())
        finally:
            os.close(fd)

    def test_existing_shared_directory_is_veto_never_repaired(self):
        shared = self.export / job_store.SHARED_NAME
        shared.mkdir(mode=0o755)
        sentinel = shared / "existing.txt"
        sentinel.write_bytes(b"old-data")
        before = shared.stat()
        self.assertCode("JOB_ALREADY_EXISTS", self.store.create, initial())
        self.assertEqual(sentinel.read_bytes(), b"old-data")
        self.assertEqual(stat.S_IMODE(shared.stat().st_mode), stat.S_IMODE(before.st_mode))
        self.assertIsNone(self.store.read())

    def test_existing_private_record_veto_even_if_malformed(self):
        (self.control / "JOB.json").write_bytes(b"malformed")
        self.assertCode("JOB_ALREADY_EXISTS", self.store.create, initial())
        self.assertFalse((self.export / job_store.SHARED_NAME).exists())

    def test_lock_excludes_real_other_process(self):
        parent, child = multiprocessing.Pipe(duplex=False)
        process = multiprocessing.Process(target=competing_lock, args=(self.control, self.export, child))
        process.start()
        child.close()
        self.assertTrue(parent.poll(5))
        self.assertEqual(parent.recv(), "JOB_LOCK_BUSY")
        process.join(5)
        self.assertEqual(process.exitcode, 0)
        parent.close()

    def test_unlocked_descriptor_cannot_mutate(self):
        import fcntl
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        self.assertCode("JOB_LOCK_REQUIRED", self.store.create, initial())

    def test_foreign_lock_does_not_authorize_old_descriptor(self):
        import fcntl
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        other = job_store.Store(control_root=self.control, export_root=self.export)
        descriptor = other.lock()
        try:
            self.assertCode("JOB_LOCK_REQUIRED", self.store.create, initial())
            other.create(initial())
        finally:
            os.close(descriptor)

    def test_inherited_descriptor_can_attach_but_no_new_execution_authority(self):
        second = job_store.Store(control_root=self.control, export_root=self.export)
        second.attach_lock(self.fd)
        second.create(initial())
        self.assertCode("JOB_ALREADY_EXISTS", self.store.create, initial())

    def test_transitions_sequence_and_terminal_immutable(self):
        queued = self.store.create(initial())
        active = self.store.save(running(queued))
        self.assertEqual(active["sequence"], 1)
        done = self.store.save(completed(active))
        self.assertEqual(done["sequence"], 2)
        self.assertEqual(self.store.read(), done)
        self.assertCode("JOB_TRANSITION_INVALID", self.store.save, done)
        self.assertEqual(len(list((self.export / job_store.SHARED_NAME).glob("state-*.json"))), 3)

    def test_stale_sequence_and_changed_job_rejected(self):
        queued = self.store.create(initial())
        self.store.save(running(queued))
        self.assertCode("JOB_TRANSITION_INVALID", self.store.save, running(queued))
        changed = self.store.read()
        changed["jobId"] = "65422-" + "f" * 24
        self.assertCode("JOB_TRANSITION_INVALID", self.store.save, changed)

    def test_strict_safe_schema_and_native_failure_preserved(self):
        for key, value in (("reason", "token=secret"), ("phase", []), ("gpuRenderingVerified", True),
                ("externalDownloadVerified", True), ("createdAt", "2026-99-99T00:00:00+00:00"),
                ("supervisorIdentity", {"pid": 1, "bootId": "a" * 36, "startTime": "1"})):
            with self.subTest(key=key):
                malformed = initial()
                malformed[key] = value
                self.assertCode("JOB_RECORD_INVALID", job_store.validate_state, malformed)
        queued = self.store.create(initial())
        failed = deepcopy(queued)
        failure = job_store.records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, test_only=True)
        failed.update(state="FAILED", phase="FAILED", reason="NATIVE_FAILED", exitCode=2, firstFailure=failure)
        saved = self.store.save(failed)
        self.assertEqual(self.store.read()["firstFailure"], failure)
        self.assertEqual(saved["exitCode"], 2)

    def test_private_symlink_and_hardlink_rejected(self):
        value = initial()
        target = self.base / "target.json"
        target.write_text(json.dumps(value))
        target.chmod(0o600)
        link = self.control / "JOB.json"
        link.symlink_to(target)
        self.assertCode("JOB_RECORD_INVALID", self.store.read)
        link.unlink()
        os.link(target, link)
        self.assertCode("JOB_RECORD_INVALID", self.store.read)

    def test_private_root_replacement_rejected(self):
        self.store.create(initial())
        self.control.rename(self.base / "preserved-old-control")
        self.control.mkdir(mode=0o700)
        self.assertCode("JOB_PRIVATE_CHANGED", self.store.read)

    def test_corrupt_and_duplicate_json_rejected(self):
        self.store.create(initial())
        path = self.control / "JOB.json"
        path.write_bytes(b'{"schema":"a","schema":"b"}')
        self.assertCode("JOB_RECORD_INVALID", self.store.read)
        path.write_bytes(b"{" + b"x" * (job_store.MAX_RECORD + 1))
        self.assertCode("JOB_RECORD_INVALID", self.store.read)

    def test_read_retries_valid_atomic_job_replacement_only(self):
        self.store.create(initial())
        for method in ("_file_info", "_read_fd"):
            with self.subTest(window=method):
                previous = self.store.read()
                next_state = running(previous)
                original = getattr(job_store.storage, method)
                fired = False
                def replace_open_record(descriptor, **options):
                    nonlocal fired
                    # _file_info injects after open/before metadata. _read_fd
                    # injects after metadata/read but before pathname identity.
                    result = None
                    if method == "_read_fd":
                        result = original(descriptor, **options)
                    if not fired:
                        fired = True
                        self.store.save(next_state)
                    return original(descriptor, **options) if method == "_file_info" else result
                with patch.object(job_store.storage, method, side_effect=replace_open_record):
                    observed = self.store.read()
                self.assertTrue(fired)
                self.assertEqual(observed["state"], "RUNNING")
                self.assertEqual(observed["sequence"], previous["sequence"] + 1)

    def test_atomic_overlap_does_not_retry_invalid_replacement(self):
        queued = self.store.create(initial())
        job = self.control / "JOB.json"
        for kind in ("corrupt_json", "hardlink", "symlink"):
            with self.subTest(kind=kind):
                job.unlink()
                job.write_bytes(job_store._encode(queued))
                job.chmod(0o600)
                replacement = self.control / (kind + "-replacement")
                source = self.control / (kind + "-source")
                valid_new_state = running(queued)
                valid_new_state["sequence"] = 1
                source.write_bytes(job_store._encode(valid_new_state))
                source.chmod(0o600)
                if kind == "corrupt_json":
                    replacement.write_bytes(b'{"not":"a-valid-job"}')
                    replacement.chmod(0o600)
                elif kind == "hardlink":
                    os.link(source, replacement)
                else:
                    replacement.symlink_to(source)
                original = job_store.storage._file_info
                fired = False
                def replace_open_record(descriptor, **options):
                    nonlocal fired
                    if not fired:
                        fired = True
                        os.replace(replacement, job)
                    return original(descriptor, **options)
                with patch.object(job_store.storage, "_file_info", side_effect=replace_open_record), \
                        patch.object(job_store.time, "sleep", side_effect=AssertionError("unsafe retry")):
                    self.assertCode("JOB_RECORD_INVALID", self.store.read)
                self.assertTrue(fired)

    def test_shared_claim_tamper_fails_but_private_failure_is_preserved(self):
        queued = self.store.create(initial())
        shared = self.export / job_store.SHARED_NAME
        (shared / "CLAIM.json").write_bytes(b"{}")
        failed = deepcopy(queued)
        failed.update(state="FAILED", phase="FAILED", reason="STORAGE_FAILED", exitCode=1)
        self.assertCode("JOB_CLAIM_INVALID", self.store.save, failed)
        self.assertEqual(self.store.read()["state"], "FAILED")
        self.assertEqual((shared / "CLAIM.json").read_bytes(), b"{}")

    def test_shared_directory_swap_refused(self):
        queued = self.store.create(initial())
        shared = self.export / job_store.SHARED_NAME
        shared.rename(self.export / "preserved-shared")
        shared.mkdir(mode=0o700)
        self.assertCode("JOB_CLAIM_INVALID", self.store.save, running(queued))
        self.assertEqual(list(shared.iterdir()), [])

    def test_shared_write_failure_does_not_finalize_completed(self):
        queued = self.store.create(initial())
        active = self.store.save(running(queued))
        with patch.object(self.store, "_append", side_effect=job_store.JobError("JOB_READBACK_FAILED")):
            self.assertCode("JOB_READBACK_FAILED", self.store.save, completed(active))
        self.assertEqual(self.store.read()["state"], "RUNNING")

    def test_shared_write_failure_keeps_local_failed_state(self):
        queued = self.store.create(initial())
        failed = deepcopy(queued)
        failed.update(state="FAILED", phase="FAILED", reason="STORAGE_FAILED", exitCode=1)
        with patch.object(self.store, "_append", side_effect=job_store.JobError("JOB_READBACK_FAILED")):
            self.assertCode("JOB_READBACK_FAILED", self.store.save, failed)
        self.assertEqual(self.store.read()["state"], "FAILED")
        self.assertEqual(self.store.read()["sequence"], 1)

    def test_result_requires_complete_allowlist_and_no_remote_success(self):
        queued = self.store.create(initial())
        active = self.store.save(running(queued))
        for mutation in ("missing_png", "outside_path", "remote_claim", "duplicate"):
            value = completed(active)
            if mutation == "missing_png":
                value["result"]["captures"][0]["files"].pop()
            elif mutation == "outside_path":
                value["result"]["exportDirectory"] = "../../private"
            elif mutation == "remote_claim":
                value["result"]["externalDownloadVerified"] = True
            else:
                value["result"]["captures"][0]["files"][1] = value["result"]["captures"][0]["files"][0]
            with self.subTest(mutation=mutation):
                self.assertCode("JOB_RECORD_INVALID", self.store.save, value)

    def test_root_can_only_read_not_write(self):
        self.store.create(initial())
        with patch.object(os, "geteuid", return_value=0):
            self.assertEqual(self.store.read()["state"], "QUEUED")
            self.assertCode("JOB_IDENTITY_INVALID", self.store.lock)

    def test_readback_fault_stops_before_private_job_creation(self):
        original = job_store.storage._new_file
        def fail_claim(directory, name, data, **options):
            if name == "CLAIM.json":
                raise job_store.storage.StorageError("STORAGE_VALIDATION_FAILED", {"reason": "DESTINATION_READBACK_MISMATCH"})
            return original(directory, name, data, **options)
        with patch.object(job_store.storage, "_new_file", side_effect=fail_claim):
            self.assertCode("JOB_STORAGE_UNAVAILABLE", self.store.create, initial())
        self.assertIsNone(self.store.read())
        self.assertCode("JOB_ALREADY_EXISTS", self.store.create, initial())


if __name__ == "__main__":
    unittest.main()
