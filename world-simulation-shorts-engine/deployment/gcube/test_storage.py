"""Native storage policy with new temporary fixtures and local POSIX probes.

The mount checker is injected for success fixtures. These tests do not claim
that an actual GCube/FUSE mount or cloud-crash durability was established.
No old app files, servers, movies, projects or credentials are accessed.
"""
import errno
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from deployment.gcube import storage as module
from deployment.gcube.storage import NativePersonalStorage, StorageError


CODE = "SYNTHETIC_OWNER_CODE_NOT_REAL_0123456789"


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wss-native-storage-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / "mount"
        self.base.mkdir(mode=0o700)
        self.uid, self.gid = os.getuid(), os.getgid()

    def storage(self, *, mode="required", checker=None, base=None):
        return NativePersonalStorage(base or self.base, mode=mode,
                                     mount_checker=checker if checker is not None else lambda _: True,
                                     uid=self.uid, gid=self.gid)

    @staticmethod
    def snapshot(root):
        result = {}
        for path in root.rglob("*"):
            s = path.lstat()
            if path.is_symlink():
                value = ("symlink", os.readlink(path))
            elif path.is_file():
                value = ("file", path.read_bytes())
            else:
                value = ("directory", None)
            result[str(path.relative_to(root))] = (value, stat.S_IMODE(s.st_mode), s.st_uid, s.st_gid)
        return result

    @staticmethod
    def write(root, relative, content, mode=0o600):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        path.chmod(mode)
        return path

    def test_required_is_default_and_requires_actual_mount_before_writes(self):
        value = NativePersonalStorage(self.base, uid=self.uid, gid=self.gid)
        self.assertEqual(value.mode, "required")
        with self.assertRaises(StorageError) as error:
            value.prepare()
        self.assertEqual(error.exception.code, "STORAGE_MOUNT_REQUIRED")
        self.assertEqual(list(self.base.iterdir()), [])
        self.assertEqual(NativePersonalStorage().base, Path("/world-storage"))

    def test_explicit_ephemeral_uses_data_world_engine_without_mount_claim(self):
        value = self.storage(mode="ephemeral", checker=lambda _: False)
        report = value.prepare().as_dict()
        self.assertEqual(report["root"], str(self.base / "world-engine"))
        self.assertEqual(report["mode"], "ephemeral")
        self.assertFalse(report["persistent_mount_detected"])
        self.assertTrue(report["filesystem_probe_passed"])
        self.assertEqual(NativePersonalStorage(mode="ephemeral").base, Path("/data"))

    def test_required_report_records_local_posix_probes_not_cloud_durability(self):
        report = self.storage().prepare()
        data = report.as_dict()
        self.assertTrue(data["persistent_mount_detected"])
        self.assertTrue(data["filesystem_probe_passed"])
        self.assertTrue(all(data["probe_checks"].values()))
        self.assertFalse(data["cloud_crash_durability_verified"])
        self.assertFalse(data["cross_machine_locking_verified"])
        for name in ("root", "runtime_root", "cache_root", "audio_root"):
            path = Path(data[name])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
            self.assertEqual(path.stat().st_uid, self.uid)
            self.assertEqual(path.stat().st_gid, self.gid)
        marker = Path(data["root"]) / module.MARKER_NAME
        self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o600)
        self.assertEqual(list(Path(data["root"]).glob(".storage-probe-*")), [])
        json.dumps(data)

    def test_temporary_and_overlay_filesystems_fail_closed_even_if_mounted(self):
        for fs in ("tmpfs", "ramfs", "overlay", "proc"):
            with self.subTest(filesystem=fs):
                value = self.storage(checker=lambda _, fs=fs: {"mounted": True, "filesystem": fs})
                with self.assertRaises(StorageError) as error:
                    value.prepare()
                self.assertEqual(error.exception.code, "STORAGE_MOUNT_REQUIRED")
                self.assertEqual(list(self.base.iterdir()), [])

    def test_injected_fuse_metadata_still_requires_posix_checks_and_makes_no_provider_claim(self):
        value = self.storage(checker=lambda _: {"mounted": True, "filesystem": "fuse.fixture"})
        report = value.prepare().as_dict()
        self.assertEqual(report["filesystem"], "fuse.fixture")
        self.assertTrue(report["filesystem_probe_passed"])
        self.assertFalse(report["cloud_crash_durability_verified"])

    def test_foreign_mount_root_files_permissions_ownership_are_untouched(self):
        foreign = self.write(self.base, "foreign.txt", b"FOREIGN_DATA", mode=0o644)
        before_file = foreign.stat()
        before_base = self.base.stat()
        self.storage().prepare()
        after_file, after_base = foreign.stat(), self.base.stat()
        self.assertEqual(foreign.read_bytes(), b"FOREIGN_DATA")
        for before, after in ((before_file, after_file), (before_base, after_base)):
            self.assertEqual(stat.S_IMODE(before.st_mode), stat.S_IMODE(after.st_mode))
            self.assertEqual((before.st_uid, before.st_gid), (after.st_uid, after.st_gid))

    def test_foreign_world_engine_without_marker_is_not_taken_over(self):
        root = self.base / "world-engine"
        root.mkdir(mode=0o700)
        self.write(root, "foreign-project.json", b"PRESERVED_FOREIGN_PROJECT")
        before = self.snapshot(self.base)
        with self.assertRaises(StorageError) as error:
            self.storage().prepare()
        self.assertEqual(error.exception.code, "STORAGE_FOREIGN_ROOT")
        self.assertEqual(self.snapshot(self.base), before)

    def test_missing_base_root_relative_parent_traversal_and_mode_are_rejected(self):
        for base in ("relative", "/", str(self.base / ".." / "unsafe")):
            with self.subTest(base=base), self.assertRaises(StorageError):
                NativePersonalStorage(base)
        with self.assertRaises(StorageError):
            NativePersonalStorage(self.base, mode="auto")
        with self.assertRaises(StorageError):
            self.storage(base=self.base / "missing").prepare()
        self.assertFalse((self.base / "missing").exists())

    def test_symlink_base_and_ancestor_are_rejected_without_touching_target(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        foreign = self.write(outside, "foreign.txt", b"OUTSIDE_DATA")
        link = Path(self.temp.name) / "link"
        link.symlink_to(outside, target_is_directory=True)
        for base in (link, link / "subdir"):
            with self.subTest(base=base), self.assertRaises(StorageError):
                self.storage(base=base).prepare()
        self.assertEqual(foreign.read_bytes(), b"OUTSIDE_DATA")
        self.assertFalse((outside / "world-engine").exists())

    def test_symlink_runtime_cache_audio_and_marker_are_not_followed(self):
        report = self.storage().prepare()
        root = Path(report.root)
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        sentinel = self.write(outside, "sentinel.bin", b"OUTSIDE_SENTINEL")
        for name in ("runtime", "cache", "audio"):
            path = root / name
            path.rmdir()
            path.symlink_to(outside, target_is_directory=True)
            with self.subTest(name=name), self.assertRaises(StorageError):
                self.storage().prepare()
            path.unlink()
            path.mkdir(mode=0o700)
        marker = root / module.MARKER_NAME
        before = marker.read_bytes()
        marker.unlink()
        marker.symlink_to(sentinel)
        with self.assertRaises(StorageError):
            self.storage().prepare()
        self.assertEqual(sentinel.read_bytes(), b"OUTSIDE_SENTINEL")
        self.assertFalse((outside / "owner-code.txt").exists())
        self.assertTrue(before)

    def test_existing_projects_cache_audio_checkpoints_auth_and_owner_code_are_byte_identical(self):
        report = self.storage().prepare(explicit_owner_code=CODE)
        root = Path(report.root)
        for relative in ("runtime/projects/p1/renders/checkpoint.json", "runtime/auth-state.json",
                         "runtime/jobs/job_fixture.json", "cache/scene-fixture.mp4", "audio/narration.wav"):
            self.write(root, relative, ("PRESERVED_SYNTHETIC_" + relative).encode())
        before = self.snapshot(root)
        second = self.storage().prepare(explicit_owner_code=CODE)
        self.assertEqual(second.owner_code_status, "matched_preserved")
        self.assertEqual(self.snapshot(root), before)
        self.assertNotIn(CODE, json.dumps(second.as_dict()))

    def test_new_explicit_owner_code_is_0600_and_never_logged_in_report(self):
        report = self.storage().prepare(explicit_owner_code=CODE)
        path = Path(report.runtime_root) / "owner-code.txt"
        self.assertEqual(path.read_bytes(), (CODE + "\n").encode())
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(path.stat().st_uid, self.uid)
        self.assertEqual(report.owner_code_status, "created_from_explicit")
        self.assertNotIn(CODE, json.dumps(report.as_dict()))

    def test_existing_owner_code_without_explicit_env_is_preserved(self):
        report = self.storage().prepare(explicit_owner_code=CODE)
        owner = Path(report.runtime_root) / "owner-code.txt"
        before = owner.read_bytes()
        second = self.storage().prepare()
        self.assertEqual(second.owner_code_status, "preserved")
        self.assertEqual(owner.read_bytes(), before)

    def test_existing_owner_code_mismatch_does_not_rotate_any_persisted_bytes(self):
        report = self.storage().prepare(explicit_owner_code=CODE)
        root = Path(report.root)
        self.write(root, "runtime/auth-state.json", b"EXISTING_AUTH_STATE")
        before = self.snapshot(root)
        with self.assertRaises(StorageError) as error:
            self.storage().prepare(explicit_owner_code=CODE + "_CHANGED")
        self.assertEqual(error.exception.code, "STORAGE_OWNER_CODE_MISMATCH")
        self.assertNotIn(CODE, str(error.exception))
        self.assertEqual(self.snapshot(root), before)

    def test_owner_code_constant_time_comparison_and_json_fixture_preserve_bytes(self):
        report = self.storage().prepare()
        owner = self.write(Path(report.runtime_root), "owner-code.txt",
                           json.dumps({"password": CODE, "synthetic": True}) + "\n")
        before = owner.read_bytes()
        original = module.hmac.compare_digest
        with patch.object(module.hmac, "compare_digest", wraps=original) as compare:
            matched = self.storage().prepare(explicit_owner_code=CODE)
        compare.assert_called_once_with(CODE.encode(), CODE.encode())
        self.assertEqual(matched.owner_code_status, "matched_preserved")
        self.assertEqual(owner.read_bytes(), before)

    def test_invalid_code_and_unsafe_existing_owner_file_fail_closed(self):
        for code in ("short", "x" * 513, CODE + "\n", " " + CODE, CODE + "\x00"):
            with self.subTest(code_length=len(code)), self.assertRaises(StorageError):
                self.storage().prepare(explicit_owner_code=code)
        report = self.storage().prepare()
        owner = self.write(Path(report.runtime_root), "owner-code.txt", CODE + "\n", mode=0o644)
        with self.assertRaises(StorageError):
            self.storage().prepare(explicit_owner_code=CODE)
        self.assertEqual(stat.S_IMODE(owner.stat().st_mode), 0o644)
        owner.unlink()
        outside = self.write(Path(self.temp.name), "outside-code.txt", CODE + "\n")
        owner.symlink_to(outside)
        with self.assertRaises(StorageError):
            self.storage().prepare(explicit_owner_code=CODE)
        self.assertEqual(outside.read_text(), CODE + "\n")

    def test_crossprocess_lock_support_failure_stops_storage_preparation(self):
        fake = subprocess.CompletedProcess(["synthetic-child"], 0, b"", b"")
        with patch.object(module.subprocess, "run", return_value=fake):
            with self.assertRaises(StorageError) as error:
                self.storage().prepare()
        self.assertEqual(error.exception.code, "STORAGE_UNSUPPORTED")
        self.assertEqual(list((self.base / "world-engine").glob(".storage-probe-*")), [])

    def test_atomic_replace_failure_is_closed_without_changing_existing_files(self):
        report = self.storage().prepare(explicit_owner_code=CODE)
        root = Path(report.root)
        self.write(root, "cache/preserved.mp4", b"EXISTING_CACHE")
        before = self.snapshot(root)
        with patch.object(module.os, "replace", side_effect=OSError(errno.ENOTSUP, "synthetic-unsupported")):
            with self.assertRaises(StorageError) as error:
                self.storage().prepare()
        self.assertEqual(error.exception.code, "STORAGE_UNSUPPORTED")
        self.assertEqual(self.snapshot(root), before)

    def test_directory_fsync_failure_rejects_storage_and_preserves_existing_state(self):
        report = self.storage().prepare(explicit_owner_code=CODE)
        root = Path(report.root)
        before = self.snapshot(root)
        original = NativePersonalStorage._fsync_directory
        def unsupported_probe(path):
            if path.name.startswith(".storage-probe-"):
                raise OSError(errno.EINVAL, "synthetic-fuse-directory-fsync-unsupported")
            return original(path)
        with patch.object(NativePersonalStorage, "_fsync_directory", side_effect=unsupported_probe):
            with self.assertRaises(StorageError) as error:
                self.storage().prepare()
        self.assertEqual(error.exception.code, "STORAGE_UNSUPPORTED")
        self.assertEqual(self.snapshot(root), before)

    def test_probe_cleanup_never_deletes_foreign_file_inserted_into_own_probe(self):
        original, foreign_paths = module.os.replace, []
        def insert_foreign(source, destination):
            result = original(source, destination)
            path = Path(destination).parent / "foreign-do-not-delete.bin"
            path.write_bytes(b"FOREIGN_PROBE_SENTINEL")
            foreign_paths.append(path)
            return result
        with patch.object(module.os, "replace", side_effect=insert_foreign):
            with self.assertRaises(StorageError) as error:
                self.storage().prepare()
        self.assertEqual(error.exception.code, "STORAGE_PROBE_CHANGED")
        self.assertEqual(len(foreign_paths), 1)
        self.assertEqual(foreign_paths[0].read_bytes(), b"FOREIGN_PROBE_SENTINEL")

    def test_replaced_probe_target_is_not_overwritten_or_deleted(self):
        original, foreign_paths = NativePersonalStorage._create_file, []
        def replace_target(instance, path, value):
            result = original(instance, path, value)
            if path.name == "pending":
                current = path.parent / "current"
                current.unlink()
                current.write_bytes(b"FOREIGN_REPLACED_TARGET")
                foreign_paths.append(current)
            return result
        with patch.object(NativePersonalStorage, "_create_file", new=replace_target):
            with self.assertRaises(StorageError) as error:
                self.storage().prepare()
        self.assertEqual(error.exception.code, "STORAGE_PROBE_CHANGED")
        self.assertEqual(len(foreign_paths), 1)
        self.assertEqual(foreign_paths[0].read_bytes(), b"FOREIGN_REPLACED_TARGET")

    def test_unlinked_probe_inode_stays_pinned_and_foreign_replacement_survives(self):
        original, observations, foreign_paths = NativePersonalStorage._create_file, [], []
        def replace_target(instance, path, value):
            result = original(instance, path, value)
            if path.name == "pending":
                current = path.parent / "current"
                before = current.stat()
                current.unlink()
                held = False
                for entry in Path("/proc/self/fd").iterdir():
                    try:
                        info = os.fstat(int(entry.name))
                    except OSError:
                        continue
                    held |= (info.st_dev, info.st_ino) == (before.st_dev, before.st_ino)
                observations.append(held)
                current.write_bytes(b"FOREIGN_PINNED_REPLACEMENT")
                foreign_paths.append(current)
            return result
        with patch.object(NativePersonalStorage, "_create_file", new=replace_target):
            with self.assertRaises(StorageError) as error:
                self.storage().prepare()
        self.assertEqual(error.exception.code, "STORAGE_PROBE_CHANGED")
        self.assertEqual(observations, [True])
        self.assertEqual(foreign_paths[0].read_bytes(), b"FOREIGN_PINNED_REPLACEMENT")

    def test_new_only_ownership_targets_uid1000_without_recursive_chown(self):
        value = NativePersonalStorage(self.base)
        with patch.object(module.os, "fstat", return_value=SimpleNamespace(st_uid=0, st_gid=0)), \
                patch.object(module.os, "fchown") as chown:
            value._new_ownership(99)
        chown.assert_called_once_with(99, 1000, 1000)
        with patch.object(module.os, "fstat", return_value=SimpleNamespace(st_uid=1000, st_gid=1000)), \
                patch.object(module.os, "fchown") as chown:
            value._new_ownership(99)
        chown.assert_not_called()

    def test_existing_root_mode_is_not_corrected_or_chowned_implicitly(self):
        report = self.storage().prepare()
        root = Path(report.root)
        root.chmod(0o755)
        before = self.snapshot(self.base)
        with patch.object(module.os, "fchown") as chown:
            with self.assertRaises(StorageError) as error:
                self.storage().prepare()
        self.assertEqual(error.exception.code, "STORAGE_OWNERSHIP")
        chown.assert_not_called()
        self.assertEqual(self.snapshot(self.base), before)
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o755)

    def test_mount_checker_failure_is_sanitized_and_does_not_create_storage(self):
        checker = Mock(side_effect=RuntimeError(CODE))
        with self.assertRaises(StorageError) as error:
            self.storage(checker=checker).prepare()
        self.assertNotIn(CODE, str(error.exception))
        self.assertEqual(list(self.base.iterdir()), [])

    def test_mountinfo_exact_mountpoint_recognizes_bind_or_fuse_not_parent(self):
        text = "36 25 0:35 / /world-storage rw - fuse.fixture PersonalStorage rw\n"
        with patch.object(module.Path, "is_file", return_value=True), \
                patch.object(module.Path, "read_text", return_value=text):
            self.assertEqual(module._mount_info(Path("/world-storage")),
                             {"mounted": True, "filesystem": "fuse.fixture"})
            self.assertEqual(module._mount_info(Path("/world-storage/subdir")),
                             {"mounted": False, "filesystem": None})


if __name__ == "__main__":
    unittest.main()
