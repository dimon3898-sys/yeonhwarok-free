"""CPU-only storage/export tests. Real POSIX operations; no GPU or cloud claims."""
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "gcube-diagnostic-image-v1"))
import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        # Managed sandboxes can present /tmp as foreign-owned; do not weaken
        # production ancestor checks merely to accommodate that fixture path.
        temporary_root = "/tmp" if Path("/tmp").stat().st_uid in {0, 1000} else "/workspace"
        self.temporary = tempfile.TemporaryDirectory(prefix="world-storage-focused-", dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base = self.root / "private"
        self.base.mkdir(mode=0o700)
        self.export = self.root / "shared"
        self.export.mkdir(mode=0o755)
        self.account = SimpleNamespace(pw_uid=1000, pw_gid=1000)
        if os.geteuid() != 1000 or os.getegid() != 1000:
            self.skipTest("Actual private preflight tests require UID/GID1000; use container --user1000:1000")

    def session(self):
        return storage.StorageSession.create(self.account, base=self.base, export_root=self.export)

    def public_fixture(self, session, *, capture="a" * 64, report_status="CAPTURE_TECHNICAL_PASS"):
        capture_root = session.private_root / "captures" / capture
        public = capture_root / "public-review"
        public.mkdir(parents=True, mode=0o700)
        (session.private_root / "captures").chmod(0o700)
        capture_root.chmod(0o700)
        media = {"PROOF.mp4": b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom" + b"fixture" * 10,
                 "01_CHECKPOINT.png": b"\x89PNG\r\n\x1a\n" + b"fixture-pixels" * 10}
        for name, data in media.items():
            (public / name).write_bytes(data)
        sums = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in sorted(media.items()))
        (public / "SHA256SUMS").write_text(sums)
        (capture_root / "REPORT.json").write_text(json.dumps({"schema": "RTX_GPU_HARDWARE_CAPTURE_V1",
            "status": report_status, "signature": capture, "sourceVerification": {"status": "PASS"},
            "privateTokenCanary": "must-never-be-exported"}))
        return public

    def test_actual_preflight_private_posix_and_shared_readback(self):
        session = self.session()
        facts = session.preflight()
        self.assertEqual(facts["status"], "PASS")
        self.assertEqual(stat.S_IMODE(session.private_root.stat().st_mode), 0o700)
        self.assertEqual(session.private_root.stat().st_uid, 1000)
        self.assertTrue(facts["private"]["writeReadRenameFsyncFlockVerified"])
        self.assertTrue(facts["mountedViewReadbackVerified"])
        for key in ("remotePersistenceVerified", "externalDownloadVerified", "privateDataAllowed"):
            self.assertFalse(facts[key])
        self.assertFalse(list(session.private_root.glob("probe-*")))
        self.assertFalse(list((self.export / session.export_name).glob("probe-*")))
        self.assertEqual(stat.S_IMODE((session.private_root / "EXPORT_RECEIPT.json").stat().st_mode), 0o600)

    def test_existing_shared_data_and_metadata_unchanged(self):
        legacy = self.export / "rtx-gpu-package-v1"
        legacy.mkdir(mode=0o755)
        legacy.chmod(0o755)  # Deliberately incompatible fixture, independent of caller umask.
        sentinel = legacy / "KEEP.txt"
        sentinel.write_bytes(b"previous-storage-must-remain")
        before = (legacy.stat().st_uid, legacy.stat().st_gid, stat.S_IMODE(legacy.stat().st_mode), sentinel.read_bytes())
        session = self.session()
        with mock.patch.object(storage.os, "chown", side_effect=AssertionError("existing chown forbidden")), \
                mock.patch.object(storage.os, "chmod", side_effect=AssertionError("existing chmod forbidden")):
            facts = session.preflight()
        self.assertEqual(before, (legacy.stat().st_uid, legacy.stat().st_gid, stat.S_IMODE(legacy.stat().st_mode), sentinel.read_bytes()))
        observed = facts["export"]["legacyCandidate"]
        self.assertEqual(observed["uid"], 1000)
        self.assertEqual(observed["modeBits"], 0o755)
        self.assertFalse(observed["privateContractMatched"])
        preflight_json = next((self.export / session.export_name).glob("storage-preflight-*.json"))
        self.assertEqual(json.loads(preflight_json.read_text())["export"]["legacyCandidate"]["modeBits"], 0o755)

    def test_private_filesystem_remote_rejected_before_new_session(self):
        with mock.patch.object(storage, "_filesystem", return_value="fuse.rclone"):
            with self.assertRaises(storage.StorageError) as caught:
                self.session()
        self.assertEqual(caught.exception.facts["reason"], "FILESYSTEM_NOT_LOCAL")
        self.assertEqual(list(self.base.iterdir()), [])

    def test_private_base_symlink_and_unsafe_mode_rejected(self):
        link = self.root / "alias"
        link.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(storage.StorageError):
            storage.StorageSession.create(self.account, base=link, export_root=self.export)
        self.base.chmod(0o755)
        with self.assertRaises(storage.StorageError) as caught:
            self.session()
        self.assertEqual(caught.exception.facts["reason"], "OWNER_OR_MODE_INVALID")

    def test_preflight_requires_uid1000_after_drop(self):
        session = self.session()
        with mock.patch.object(storage.os, "geteuid", return_value=0):
            with self.assertRaises(storage.StorageError) as caught:
                session.preflight()
        self.assertEqual(caught.exception.facts["reason"], "IDENTITY_INVALID")

    def test_root_can_chown_only_new_private_session(self):
        actual = os.fchown
        changed = []
        def note(descriptor, uid, gid):
            changed.append((os.fstat(descriptor).st_ino, uid, gid))
            actual(descriptor, uid, gid)  # Same UID/GID on a fresh caller-owned test directory.
        with mock.patch.object(storage.os, "geteuid", return_value=0), \
                mock.patch.object(storage.os, "fchown", side_effect=note):
            session = self.session()
        self.assertEqual(changed, [(session.private_root.stat().st_ino, 1000, 1000)])

    def test_shared_permission_failure_is_explicit_and_safe(self):
        session = self.session()
        original = storage._open_directory
        def blocked(path, **kwargs):
            if Path(path) == self.export:
                raise PermissionError(errno.EACCES, "private-canary-password")
            return original(path, **kwargs)
        with mock.patch.object(storage, "_open_directory", side_effect=blocked):
            with self.assertRaises(storage.StorageError) as caught:
                session.preflight()
        self.assertEqual(caught.exception.code, "STORAGE_UNAVAILABLE")
        self.assertEqual(caught.exception.facts["stage"], "EXPORT")
        self.assertEqual(caught.exception.facts["errnoName"], "EACCES")
        self.assertNotIn("canary", json.dumps(caught.exception.facts))

    def test_actual_shared_directory_permission_denial(self):
        session = self.session()
        self.export.chmod(0o000)
        try:
            with self.assertRaises(storage.StorageError) as caught:
                session.preflight()
        finally:
            self.export.chmod(0o700)  # Restore this test's freshly-created fixture only.
        self.assertEqual(caught.exception.facts["stage"], "EXPORT")
        self.assertEqual(caught.exception.facts["errnoName"], "EACCES")
        self.assertEqual(list(self.export.iterdir()), [])

    def test_foreign_private_owner_rejected_without_repair(self):
        actual_fstat = storage.os.fstat
        base_inode = self.base.stat().st_ino
        def foreign(descriptor):
            actual = actual_fstat(descriptor)
            if actual.st_ino == base_inode:
                return SimpleNamespace(st_uid=0, st_gid=0, st_mode=actual.st_mode,
                                       st_ino=actual.st_ino, st_dev=actual.st_dev)
            return actual
        with mock.patch.object(storage.os, "fstat", side_effect=foreign), \
                mock.patch.object(storage.os, "fchown", side_effect=AssertionError("existing repair forbidden")):
            with self.assertRaises(storage.StorageError) as caught:
                self.session()
        self.assertEqual(caught.exception.facts["reason"], "OWNER_OR_MODE_INVALID")
        self.assertEqual(list(self.base.iterdir()), [])

    def test_private_write_enospc_not_replaced_by_cleanup_enotempty(self):
        session = self.session()
        with mock.patch.object(storage.os, "write", side_effect=OSError(errno.ENOSPC, "sensitive message")):
            with self.assertRaises(storage.StorageError) as caught:
                session.preflight()
        self.assertEqual(caught.exception.facts["errnoName"], "ENOSPC")
        self.assertNotIn("sensitive", str(caught.exception))

    def test_child_parent_receipt_reopen_and_repeat_preflight(self):
        session = self.session()
        session.preflight()
        reopened = storage.StorageSession(session.account, session.private_root, session.export_root,
                                           session.export_name, session._private_identity)
        self.assertEqual(reopened.preflight()["status"], "PASS")
        self.assertEqual(len(list(self.export.glob("world-engine-export-*"))), 1)

    def test_replaced_export_directory_rejected_without_touching_replacement(self):
        session = self.session()
        session.preflight()
        old = self.export / session.export_name
        old.rename(self.export / "preserved-original")
        old.mkdir()
        (old / "KEEP.txt").write_bytes(b"existing replacement")
        with self.assertRaises(storage.StorageError) as caught:
            session.preflight()
        self.assertEqual(caught.exception.facts["reason"], "EXPORT_IDENTITY_CHANGED")
        self.assertEqual((old / "KEEP.txt").read_bytes(), b"existing replacement")

    def test_preexisting_export_name_collision_never_reused_or_overwritten(self):
        session = self.session()
        collision = self.export / session.export_name
        collision.mkdir()
        (collision / "KEEP.txt").write_bytes(b"must-remain")
        with self.assertRaises(storage.StorageError):
            session.preflight()
        self.assertEqual((collision / "KEEP.txt").read_bytes(), b"must-remain")
        self.assertEqual(sorted(item.name for item in collision.iterdir()), ["KEEP.txt"])

    def test_safe_record_requires_preflight_and_strips_secrets(self):
        import records
        session = self.session()
        record = records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, mode="diagnostic")
        record["privateToken"] = "must-never-be-exported"
        with self.assertRaises(storage.StorageError):
            session.export_safe_record(record)
        session.preflight()
        exported = session.export_safe_record(record)
        data = (self.export / session.export_name / exported["file"]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), exported["sha256"])
        self.assertNotIn(b"must-never", data)
        self.assertFalse(json.loads(data)["renderAllowed"])
        self.assertFalse(exported["remotePersistenceVerified"])

    def test_complete_capture_export_media_only_and_receipt_last(self):
        session = self.session()
        session.preflight()
        public = self.public_fixture(session)
        calls = []
        original = storage._new_file
        def note(directory, name, data, **kwargs):
            calls.append(name)
            return original(directory, name, data, **kwargs)
        with mock.patch.object(storage, "_new_file", side_effect=note):
            result = session.export_results()
        self.assertEqual(result["status"], "EXPORTED")
        self.assertEqual(result["files"], 3)
        self.assertEqual(calls[-1], "EXPORT_COMPLETE.json")
        destination = self.export / session.export_name / result["results"][0]["directory"]
        self.assertEqual(sorted(item.name for item in (destination / "public-review").iterdir()),
                         ["01_CHECKPOINT.png", "PROOF.mp4", "SHA256SUMS"])
        for item in result["results"][0]["files"]:
            copied = (destination / "public-review" / item["file"]).read_bytes()
            self.assertEqual(copied, (public / item["file"]).read_bytes())
            self.assertEqual(hashlib.sha256(copied).hexdigest(), item["sha256"])
        self.assertNotIn("must-never", "".join(path.read_text(errors="ignore") for path in destination.rglob("*") if path.is_file()))
        self.assertFalse(result["externalDownloadVerified"])

    def test_incomplete_or_failed_capture_not_exported(self):
        session = self.session()
        session.preflight()
        self.public_fixture(session, report_status="BLOCKED")
        self.assertEqual(session.export_results()["status"], "NO_PUBLIC_RESULTS")
        self.assertFalse(list((self.export / session.export_name).glob("capture-*")))

    def test_internal_files_in_public_directory_are_rejected(self):
        session = self.session()
        session.preflight()
        public = self.public_fixture(session)
        (public / "admission_private.json").write_text("private-canary")
        with self.assertRaises(storage.StorageError) as caught:
            session.export_results()
        self.assertEqual(caught.exception.facts["reason"], "PUBLIC_ALLOWLIST_REQUIRED")

    def test_symlink_or_hardlink_source_rejected(self):
        for kind in ("symlink", "hardlink"):
            with self.subTest(kind=kind):
                session = self.session()
                session.preflight()
                public = self.public_fixture(session)
                source = public / "PROOF.mp4"
                original = session.private_root / "preserved.mp4"
                source.rename(original)
                original_bytes = original.read_bytes()
                source.symlink_to(original) if kind == "symlink" else os.link(original, source)
                with self.assertRaises(storage.StorageError):
                    session.export_results()
                self.assertEqual(original.read_bytes(), original_bytes)

    def test_source_hash_mismatch_creates_no_completion_receipt(self):
        session = self.session()
        session.preflight()
        public = self.public_fixture(session)
        with (public / "PROOF.mp4").open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaises(storage.StorageError) as caught:
            session.export_results()
        self.assertEqual(caught.exception.facts["reason"], "SOURCE_HASH_MISMATCH")
        self.assertFalse(list((self.export / session.export_name).rglob("EXPORT_COMPLETE.json")))

    def test_destination_readback_corruption_blocks_completion(self):
        session = self.session()
        session.preflight()
        self.public_fixture(session)
        original_sync = storage._shared_fsync
        def corrupt(descriptor):
            if os.readlink(f"/proc/self/fd/{descriptor}").endswith("/public-review/PROOF.mp4"):
                os.lseek(descriptor, 0, os.SEEK_SET)
                os.write(descriptor, b"corrupted")
            return original_sync(descriptor)
        with mock.patch.object(storage, "_shared_fsync", side_effect=corrupt):
            with self.assertRaises(storage.StorageError) as caught:
                session.export_results()
        self.assertEqual(caught.exception.facts["reason"], "DESTINATION_READBACK_MISMATCH")
        self.assertFalse(list((self.export / session.export_name).rglob("EXPORT_COMPLETE.json")))

    def test_manifest_traversal_rejected_before_export_copy(self):
        session = self.session()
        session.preflight()
        public = self.public_fixture(session)
        (public / "SHA256SUMS").write_text("0" * 64 + "  ../REPORT.json\n")
        with self.assertRaises(storage.StorageError) as caught:
            session.export_results()
        self.assertEqual(caught.exception.facts["reason"], "SOURCE_MANIFEST_INVALID")
        self.assertFalse(list((self.export / session.export_name).glob("capture-*")))

    def test_fifo_readback_substitution_rejected_without_blocking(self):
        directory = os.open(self.export, os.O_RDONLY | os.O_DIRECTORY)
        original = storage.os.open
        replaced = False
        def substitute(name, flags, *args, **kwargs):
            nonlocal replaced
            if name == "record.json" and not flags & os.O_CREAT and not replaced:
                replaced = True
                os.unlink(name, dir_fd=directory)
                os.mkfifo(name, dir_fd=directory)
            return original(name, flags, *args, **kwargs)
        try:
            with mock.patch.object(storage.os, "open", side_effect=substitute):
                with self.assertRaises(storage.StorageError):
                    storage._new_file(directory, "record.json", b"safe")
        finally:
            os.close(directory)

    def test_cleanup_does_not_delete_replaced_file(self):
        directory = os.open(self.export, os.O_RDONLY | os.O_DIRECTORY)
        original = self.export / "original"
        original.write_bytes(b"old")
        expected = storage._identity(original.stat())
        original.rename(self.export / "preserved")
        original.write_bytes(b"replacement")
        try:
            with self.assertRaises(storage.StorageError):
                storage._unlink_owned(directory, "original", expected)
            self.assertEqual(original.read_bytes(), b"replacement")
        finally:
            os.close(directory)

    def test_facts_allowlist_rejects_arbitrary_text_and_malformed_values(self):
        facts = storage.safe_facts({"stage": "EXPORT", "reason": "IO_UNAVAILABLE", "uid": 1000,
            "modeBits": 0o777, "filesystem": "fuse.rclone", "password": "must-never-be-exported",
            "inspectionStatus": [], "private": {"path": "/secret", "modeBits": True}})
        self.assertEqual(facts, {"stage": "EXPORT", "reason": "IO_UNAVAILABLE", "uid": 1000,
                                "modeBits": 0o777, "filesystem": "fuse.rclone", "private": {}})
        self.assertEqual(storage.StorageError(code=[]).code, "STORAGE_VALIDATION_FAILED")
        cyclic = {}
        cyclic["private"] = cyclic
        self.assertLess(len(json.dumps(storage.safe_facts(cyclic))), 100)


if __name__ == "__main__":
    unittest.main()
