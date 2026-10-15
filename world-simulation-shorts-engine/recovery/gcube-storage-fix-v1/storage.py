"""Private local POSIX workspace and explicitly untrusted public-only exports.

Shared-storage readback proves only the current mounted view. It is neither a
remote durability acknowledgement nor an external-download verification.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

PRIVATE_BASE = Path("/var/lib/world-engine-private/engine")
EXPORT_ROOT = Path("/world-storage")
LOCAL_FILESYSTEMS = frozenset({"overlay", "ext2", "ext3", "ext4", "xfs", "btrfs", "tmpfs"})
KNOWN_EXPORT_FILESYSTEMS = LOCAL_FILESYSTEMS | {"fuse", "fuse.rclone", "fuse.s3fs", "fuse.drivefs", "nfs", "nfs4",
    "cifs", "smb3", "9p", "virtiofs", "fuse.gcsfuse", "fuse.blobfuse2", "other", "unknown", "untrusted-shared"}
_IDENTITY = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,179}\Z")
_REASONS = frozenset({"IDENTITY_INVALID", "PATH_UNSAFE", "OWNER_OR_MODE_INVALID", "FILESYSTEM_NOT_LOCAL",
    "FILESYSTEM_UNKNOWN", "PRIVATE_IDENTITY_CHANGED", "PRIVATE_PROBE_FAILED", "EXPORT_PROBE_FAILED",
    "EXPORT_IDENTITY_CHANGED", "RECEIPT_INVALID", "PREFLIGHT_REQUIRED", "PUBLIC_ALLOWLIST_REQUIRED",
    "PUBLIC_SOURCE_INVALID", "SOURCE_MANIFEST_INVALID", "SOURCE_HASH_MISMATCH", "DESTINATION_READBACK_MISMATCH",
    "IO_UNAVAILABLE"})
_FLAGS = {"mountedViewReadbackVerified": True, "remotePersistenceVerified": False,
          "externalDownloadVerified": False, "privateDataAllowed": False}


def safe_facts(value, *, _depth=0):
    """Console-safe facts; no paths, environment values, free-form text or URLs."""
    if _depth > 3:
        return {}
    source = value if isinstance(value, dict) else {}
    result = {}
    for key, allowed in (("stage", {"PRIVATE", "EXPORT"}), ("reason", _REASONS),
                         ("filesystem", KNOWN_EXPORT_FILESYSTEMS),
                         ("mode", {"0700"}), ("storageRole", {"PRIVATE_POSIX_LOCAL", "UNTRUSTED_SHARED_EXPORT_ONLY"})):
        item = source.get(key)
        if isinstance(item, str) and item in allowed:
            result[key] = item
    if isinstance(source.get("inspectionStatus"), str) and source["inspectionStatus"] in {"AVAILABLE", "MISSING", "BLOCKED"}:
        result["inspectionStatus"] = source["inspectionStatus"]
    name = source.get("errnoName")
    if isinstance(name, str) and name in set(errno.errorcode.values()):
        result["errnoName"] = name
    for key in ("uid", "gid", "files", "bytes", "captures"):
        item = source.get(key)
        if isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 2**50:
            result[key] = item
    mode = source.get("modeBits")
    if isinstance(mode, int) and not isinstance(mode, bool) and 0 <= mode <= 0o7777:
        result["modeBits"] = mode
    for key in (*_FLAGS, "writeReadRenameFsyncFlockVerified", "preflightVerified", "present", "isDirectory", "isSymlink", "privateContractMatched"):
        if isinstance(source.get(key), bool):
            result[key] = source[key]
    for key in ("private", "export", "root", "legacyCandidate"):
        if isinstance(source.get(key), dict):
            result[key] = safe_facts(source[key], _depth=_depth + 1)
    return result


class StorageError(RuntimeError):
    def __init__(self, code="STORAGE_VALIDATION_FAILED", facts=None):
        self.code = code if isinstance(code, str) and code in {"STORAGE_VALIDATION_FAILED", "STORAGE_UNAVAILABLE"} else "STORAGE_VALIDATION_FAILED"
        self.facts = safe_facts(facts)
        super().__init__(self.code)


def _error(stage, reason, error=None, *, unavailable=False):
    facts = {"stage": stage, "reason": reason}
    if isinstance(getattr(error, "errno", None), int) and error.errno in errno.errorcode:
        facts["errnoName"] = errno.errorcode[error.errno]
    return StorageError("STORAGE_UNAVAILABLE" if unavailable else "STORAGE_VALIDATION_FAILED", facts)


def _identity(info):
    return {"device": info.st_dev, "inode": info.st_ino}


def _open_directory(path, *, safe_parents=False, account_uid=1000):
    """Walk every component with openat/O_NOFOLLOW; never repair metadata."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path == Path("/"):
        raise _error("PRIVATE" if safe_parents else "EXPORT", "PATH_UNSAFE")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            if safe_parents:
                info = os.fstat(descriptor)
                mode = stat.S_IMODE(info.st_mode)
                trusted_sticky = info.st_uid == 0 and bool(mode & stat.S_ISVTX)
                if info.st_uid not in {0, account_uid} or (mode & 0o022 and not trusted_sticky):
                    raise _error("PRIVATE", "PATH_UNSAFE")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _filesystem(path):
    # mountinfo is kernel-generated; decode only the defined octal escapes.
    target = str(Path(path))
    selected = None
    with open("/proc/self/mountinfo", encoding="utf-8") as stream:
        for line in stream:
            parts = line.rstrip("\n").split(" ")
            if "-" not in parts or len(parts) < 10:
                continue
            separator = parts.index("-")
            if separator + 1 >= len(parts):
                continue
            mount = re.sub(r"\\([0-7]{3})", lambda item: chr(int(item[1], 8)), parts[4])
            if target == mount or target.startswith(mount.rstrip("/") + "/"):
                if selected is None or len(mount) >= selected[0]:
                    selected = (len(mount), parts[separator + 1])
    return selected[1] if selected is not None else "unknown"


def _private_check(descriptor, account):
    info = os.fstat(descriptor)
    if info.st_uid != account.pw_uid or info.st_gid != account.pw_gid or stat.S_IMODE(info.st_mode) != 0o700:
        raise _error("PRIVATE", "OWNER_OR_MODE_INVALID")
    return info


def _new_directory(parent_fd, prefix, *, uid=None, gid=None):
    for _ in range(8):
        name = prefix + os.urandom(12).hex()
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            # Only this newly-created local directory may be provisioned for UID1000.
            if uid is not None and os.geteuid() == 0:
                os.fchown(descriptor, uid, gid)
            if uid is not None:
                os.fchmod(descriptor, 0o700)
            return name, descriptor
        except BaseException:
            os.close(descriptor)
            raise
    raise FileExistsError(errno.EEXIST, "fresh directory unavailable")


def _file_info(descriptor, *, uid=None, private=False):
    info = os.fstat(descriptor)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            (uid is not None and info.st_uid != uid) or
            (private and stat.S_IMODE(info.st_mode) != 0o600)):
        raise _error("PRIVATE" if private else "EXPORT", "PUBLIC_SOURCE_INVALID")
    return info


def _read_fd(descriptor, *, limit=256 * 1024):
    result = bytearray()
    while len(result) <= limit:
        piece = os.read(descriptor, min(65536, limit + 1 - len(result)))
        if not piece:
            return bytes(result)
        result.extend(piece)
    raise ValueError("bounded record exceeded")


def _write_all(descriptor, data):
    remaining = memoryview(data)
    while remaining:
        count = os.write(descriptor, remaining)
        if count <= 0:
            raise OSError(errno.EIO, "short write")
        remaining = remaining[count:]


def _shared_fsync(descriptor):
    try:
        os.fsync(descriptor)
        return True
    except OSError as error:
        if error.errno in {errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS}:
            return False  # Never interpreted as remote durability.
        raise


def _new_file(directory, name, data, *, private=False):
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        written_identity = _identity(os.fstat(descriptor))
        if private:
            os.fchmod(descriptor, 0o600)  # Only this fresh local file.
        _write_all(descriptor, data)
        os.fsync(descriptor) if private else _shared_fsync(descriptor)
    finally:
        os.close(descriptor)
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        if _identity(_file_info(descriptor)) != written_identity:
            raise _error("EXPORT", "DESTINATION_READBACK_MISMATCH")
        readback = _read_fd(descriptor, limit=len(data))
    finally:
        os.close(descriptor)
    if hashlib.sha256(readback).digest() != hashlib.sha256(data).digest():
        raise _error("EXPORT", "DESTINATION_READBACK_MISMATCH")
    return {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "_identity": written_identity}


def _unlink_owned(directory, name, expected):
    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or _identity(info) != expected:
        raise _error("EXPORT", "EXPORT_IDENTITY_CHANGED")
    os.unlink(name, dir_fd=directory)


def _probe(directory, *, private):
    name, probe = _new_directory(directory, "probe-")
    first = "probe.bin"
    renamed = "renamed.bin"
    data = os.urandom(1024)
    owned_file = None
    owned_directory = _identity(os.fstat(probe))
    failed = False
    try:
        owned_file = _new_file(probe, first, data, private=private)["_identity"]
        if private:
            descriptor = os.open(first, os.O_RDWR | os.O_NOFOLLOW, dir_fd=probe)
            competitor = os.open(first, os.O_RDWR | os.O_NOFOLLOW, dir_fd=probe)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    fcntl.flock(competitor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise OSError(errno.ENOLCK, "lock semantics unavailable")
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(competitor)
                os.close(descriptor)
            os.rename(first, renamed, src_dir_fd=probe, dst_dir_fd=probe)
            first = renamed
            os.fsync(probe)
        _unlink_owned(probe, first, owned_file)
        first = None
        os.fsync(probe) if private else _shared_fsync(probe)
    except BaseException:
        failed = True
        raise
    finally:
        try:
            try:
                if first is not None and owned_file is not None:
                    try:
                        _unlink_owned(probe, first, owned_file)
                    except FileNotFoundError:
                        pass
            finally:
                os.close(probe)
            current = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or _identity(current) != owned_directory:
                raise _error("EXPORT", "EXPORT_IDENTITY_CHANGED")
            os.rmdir(name, dir_fd=directory)  # Only our own fresh probe directory.
        except Exception:
            if not failed:
                raise  # A secondary cleanup error must never replace the original failure.


class StorageSession:
    def __init__(self, account, private_root, export_root, export_name, private_identity):
        self.account = account
        self.private_root = Path(private_root)
        self.export_root = Path(export_root)
        self.export_name = export_name
        self._private_identity = private_identity

    @classmethod
    def create(cls, account, *, base=PRIVATE_BASE, export_root=EXPORT_ROOT):
        if (getattr(account, "pw_uid", None) != 1000 or getattr(account, "pw_gid", None) != 1000
                or os.geteuid() not in {0, 1000}):
            raise _error("PRIVATE", "IDENTITY_INVALID")
        base_fd = None
        try:
            base_fd = _open_directory(base, safe_parents=True, account_uid=account.pw_uid)
            _private_check(base_fd, account)
            filesystem = _filesystem(base)
            if filesystem not in LOCAL_FILESYSTEMS:
                raise _error("PRIVATE", "FILESYSTEM_NOT_LOCAL")
            name, descriptor = _new_directory(base_fd, "session-", uid=account.pw_uid, gid=account.pw_gid)
            try:
                info = _private_check(descriptor, account)
                identity = _identity(info)
                os.fsync(base_fd)
            finally:
                os.close(descriptor)
            return cls(account, Path(base) / name, export_root,
                       "world-engine-export-" + os.urandom(12).hex(), identity)
        except StorageError:
            raise
        except (OSError, ValueError, TypeError) as error:
            raise _error("PRIVATE", "IO_UNAVAILABLE", error, unavailable=True) from None
        finally:
            if base_fd is not None:
                os.close(base_fd)

    def _private_fd(self):
        if os.geteuid() != 1000 or os.getegid() != 1000:
            raise _error("PRIVATE", "IDENTITY_INVALID")
        descriptor = _open_directory(self.private_root, safe_parents=True, account_uid=self.account.pw_uid)
        try:
            info = _private_check(descriptor, self.account)
            if _identity(info) != self._private_identity:
                raise _error("PRIVATE", "PRIVATE_IDENTITY_CHANGED")
            if _filesystem(self.private_root) not in LOCAL_FILESYSTEMS:
                raise _error("PRIVATE", "FILESYSTEM_NOT_LOCAL")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def _load_receipt(self, private):
        if not re.fullmatch(r"world-engine-export-[0-9a-f]{24}", self.export_name):
            raise _error("EXPORT", "RECEIPT_INVALID")
        descriptor = os.open("EXPORT_RECEIPT.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=private)
        try:
            _file_info(descriptor, uid=1000, private=True)
            value = json.loads(_read_fd(descriptor))
        finally:
            os.close(descriptor)
        if (not isinstance(value, dict) or value.get("schema") != "WORLD_ENGINE_EXPORT_SESSION_V1"
                or value.get("preflightVerified") is not True or value.get("exportName") != self.export_name
                or not isinstance(value.get("rootIdentity"), dict)
                or not isinstance(value.get("directoryIdentity"), dict)
                or any(value.get(key) is not expected for key, expected in _FLAGS.items())):
            raise _error("EXPORT", "RECEIPT_INVALID")
        return value

    def _export_fd(self, private):
        receipt = self._load_receipt(private)
        root = _open_directory(self.export_root)
        try:
            if _identity(os.fstat(root)) != receipt["rootIdentity"]:
                raise _error("EXPORT", "EXPORT_IDENTITY_CHANGED")
            descriptor = os.open(self.export_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
            if _identity(os.fstat(descriptor)) != receipt["directoryIdentity"]:
                os.close(descriptor)
                raise _error("EXPORT", "EXPORT_IDENTITY_CHANGED")
            return descriptor
        finally:
            os.close(root)

    def preflight(self):
        private = root = export = None
        stage = "PRIVATE"
        try:
            private = self._private_fd()
            _probe(private, private=True)
            stage = "EXPORT"
            try:
                self._load_receipt(private)
            except FileNotFoundError:
                root = _open_directory(self.export_root)
                os.mkdir(self.export_name, 0o700, dir_fd=root)  # Collision is a hard failure; never reuse unknown data.
                export = os.open(self.export_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
                _probe(export, private=False)
                receipt = {"schema": "WORLD_ENGINE_EXPORT_SESSION_V1", "preflightVerified": True,
                    "exportName": self.export_name, "rootIdentity": _identity(os.fstat(root)),
                    "directoryIdentity": _identity(os.fstat(export)), **_FLAGS}
                _new_file(private, "EXPORT_RECEIPT.json", (json.dumps(receipt, sort_keys=True) + "\n").encode(), private=True)
                os.fsync(private)
            else:
                export = self._export_fd(private)
                _probe(export, private=False)
            if root is None:
                root = _open_directory(self.export_root)
            root_info = os.fstat(root)
            export_filesystem = _filesystem(self.export_root)
            root_facts = {"inspectionStatus": "AVAILABLE", "present": True,
                          "uid": root_info.st_uid, "gid": root_info.st_gid,
                          "modeBits": stat.S_IMODE(root_info.st_mode),
                          "filesystem": export_filesystem if export_filesystem in KNOWN_EXPORT_FILESYSTEMS else "other"}
            try:
                legacy = os.stat("rtx-gpu-package-v1", dir_fd=root, follow_symlinks=False)
                legacy_facts = {"inspectionStatus": "AVAILABLE", "present": True,
                    "uid": legacy.st_uid, "gid": legacy.st_gid, "modeBits": stat.S_IMODE(legacy.st_mode),
                    "isDirectory": stat.S_ISDIR(legacy.st_mode), "isSymlink": stat.S_ISLNK(legacy.st_mode),
                    "privateContractMatched": stat.S_ISDIR(legacy.st_mode) and legacy.st_uid == 1000 and stat.S_IMODE(legacy.st_mode) == 0o700}
                legacy_filesystem = _filesystem(self.export_root / "rtx-gpu-package-v1")
                legacy_facts["filesystem"] = legacy_filesystem if legacy_filesystem in KNOWN_EXPORT_FILESYSTEMS else "other"
            except FileNotFoundError:
                legacy_facts = {"inspectionStatus": "MISSING", "present": False, "privateContractMatched": False}
            except OSError:
                legacy_facts = {"inspectionStatus": "BLOCKED", "privateContractMatched": False}
            facts = {"schema": "WORLD_ENGINE_STORAGE_PREFLIGHT_V1", "status": "PASS",
                     "private": {"uid": 1000, "gid": 1000, "mode": "0700",
                         "filesystem": _filesystem(self.private_root), "storageRole": "PRIVATE_POSIX_LOCAL",
                         "writeReadRenameFsyncFlockVerified": True},
                     "export": {"storageRole": "UNTRUSTED_SHARED_EXPORT_ONLY", "root": root_facts,
                                "legacyCandidate": legacy_facts, **_FLAGS}, **_FLAGS}
            safe_preflight = {"schema": "WORLD_ENGINE_STORAGE_PREFLIGHT_V1", "status": "PASS", **safe_facts(facts)}
            _new_file(export, "storage-preflight-" + os.urandom(12).hex() + ".json",
                      (json.dumps(safe_preflight, sort_keys=True) + "\n").encode())
            _shared_fsync(export)
            return facts
        except StorageError:
            raise
        except (OSError, ValueError, TypeError) as error:
            reason = "PRIVATE_PROBE_FAILED" if stage == "PRIVATE" else "EXPORT_PROBE_FAILED"
            raise _error(stage, reason, error, unavailable=True) from None
        finally:
            for descriptor in (export, root, private):
                if descriptor is not None:
                    os.close(descriptor)

    def export_safe_record(self, record):
        private = export = None
        try:
            private = self._private_fd()
            export = self._export_fd(private)
            from records import safe_record
            safe = safe_record(record)
            name = "startup-safe-" + os.urandom(12).hex() + ".json"
            written = _new_file(export, name, (json.dumps(safe, sort_keys=True, allow_nan=False) + "\n").encode())
            written.pop("_identity")
            _shared_fsync(export)
            return {"schema": "WORLD_ENGINE_SAFE_RECORD_EXPORT_V1", "status": "EXPORTED",
                    "exportName": self.export_name, **written, **_FLAGS}
        except StorageError:
            raise
        except FileNotFoundError as error:
            raise _error("EXPORT", "PREFLIGHT_REQUIRED", error) from None
        except (OSError, ValueError, TypeError, ImportError) as error:
            raise _error("EXPORT", "IO_UNAVAILABLE", error, unavailable=True) from None
        finally:
            for descriptor in (export, private):
                if descriptor is not None:
                    os.close(descriptor)

    def export_results(self):
        private = export = captures = None
        try:
            private = self._private_fd()
            export = self._export_fd(private)
            try:
                captures = os.open("captures", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=private)
            except FileNotFoundError:
                return {"schema": "WORLD_ENGINE_PUBLIC_EXPORT_V1", "status": "NO_PUBLIC_RESULTS",
                        "captures": 0, "files": 0, **_FLAGS}
            _private_check(captures, self.account)
            outputs = []
            for capture in sorted(os.listdir(captures)):
                if not _IDENTITY.fullmatch(capture):
                    raise _error("EXPORT", "PUBLIC_SOURCE_INVALID")
                capture_fd = os.open(capture, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=captures)
                public = None
                try:
                    _private_check(capture_fd, self.account)
                    try:
                        report_fd = os.open("REPORT.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=capture_fd)
                    except FileNotFoundError:
                        continue  # In-progress captures are never a complete public export.
                    try:
                        _file_info(report_fd, uid=1000)
                        report = json.loads(_read_fd(report_fd, limit=1024 * 1024))
                    finally:
                        os.close(report_fd)
                    if (not isinstance(report, dict) or report.get("schema") != "RTX_GPU_HARDWARE_CAPTURE_V1"
                            or report.get("status") != "CAPTURE_TECHNICAL_PASS" or report.get("signature") != capture
                            or not isinstance(report.get("sourceVerification"), dict)
                            or report["sourceVerification"].get("status") != "PASS"):
                        continue
                    try:
                        public = os.open("public-review", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=capture_fd)
                    except FileNotFoundError:
                        continue
                    _private_check(public, self.account)
                    outputs.append(self._export_capture(export, public, capture))
                finally:
                    if public is not None:
                        os.close(public)
                    os.close(capture_fd)
            return {"schema": "WORLD_ENGINE_PUBLIC_EXPORT_V1", "status": "EXPORTED" if outputs else "NO_PUBLIC_RESULTS",
                    "captures": len(outputs), "files": sum(len(item["files"]) for item in outputs),
                    "results": outputs, **_FLAGS}
        except StorageError:
            raise
        except (OSError, ValueError, TypeError) as error:
            raise _error("EXPORT", "IO_UNAVAILABLE", error, unavailable=True) from None
        finally:
            for descriptor in (captures, export, private):
                if descriptor is not None:
                    os.close(descriptor)

    def _export_capture(self, export, public, capture):
        names = sorted(os.listdir(public))
        if (not 2 <= len(names) <= 64 or "SHA256SUMS" not in names
                or any(not _NAME.fullmatch(name) or (name != "SHA256SUMS" and not name.endswith((".mp4", ".png"))) for name in names)
                or not any(name.endswith(".mp4") for name in names)):
            raise _error("EXPORT", "PUBLIC_ALLOWLIST_REQUIRED")
        manifest = os.open("SHA256SUMS", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=public)
        try:
            _file_info(manifest, uid=1000)
            manifest_bytes = _read_fd(manifest)
        finally:
            os.close(manifest)
        expected = {}
        for line in manifest_bytes.decode("ascii").splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9_.-]{0,179})", line)
            if match is None or match[2] in expected or match[2] == "SHA256SUMS":
                raise _error("EXPORT", "SOURCE_MANIFEST_INVALID")
            expected[match[2]] = match[1]
        if set(expected) != set(names) - {"SHA256SUMS"}:
            raise _error("EXPORT", "SOURCE_MANIFEST_INVALID")
        # Validate the entire source before creating an export completion unit.
        for name, digest in expected.items():
            self._source_digest(public, name, digest)
        directory_name, directory = _new_directory(export, "capture-" + capture[:12] + "-")
        public_output = None
        try:
            os.mkdir("public-review", 0o700, dir_fd=directory)
            public_output = os.open("public-review", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            files = []
            for name in names:
                digest = hashlib.sha256(manifest_bytes).hexdigest() if name == "SHA256SUMS" else expected[name]
                files.append(self._copy_public_file(public, public_output, name, digest))
            _shared_fsync(public_output)
            receipt = {"schema": "WORLD_ENGINE_PUBLIC_EXPORT_RECEIPT_V1", "status": "COMPLETE",
                       "captureId": capture, "files": files, "sourceSha256SumsVerified": True, **_FLAGS}
            _new_file(directory, "EXPORT_COMPLETE.json", (json.dumps(receipt, sort_keys=True) + "\n").encode())
            _shared_fsync(directory)
            return {"directory": directory_name, "files": files, "completionReceipt": "EXPORT_COMPLETE.json"}
        finally:
            if public_output is not None:
                os.close(public_output)
            os.close(directory)

    def _source_digest(self, public, name, expected):
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=public)
        try:
            info = _file_info(descriptor, uid=1000)
            if not 1 <= info.st_size <= 4 * 1024**3:
                raise _error("EXPORT", "PUBLIC_SOURCE_INVALID")
            first = os.read(descriptor, 32)
            if ((name.endswith(".png") and not first.startswith(b"\x89PNG\r\n\x1a\n"))
                    or (name.endswith(".mp4") and (len(first) < 12 or first[4:8] != b"ftyp"))):
                raise _error("EXPORT", "PUBLIC_SOURCE_INVALID")
            digest = hashlib.sha256(first)
            size = len(first)
            for chunk in iter(lambda: os.read(descriptor, 1024 * 1024), b""):
                size += len(chunk)
                if size > 4 * 1024**3:
                    raise _error("EXPORT", "PUBLIC_SOURCE_INVALID")
                digest.update(chunk)
            after = os.fstat(descriptor)
            if (digest.hexdigest() != expected or info.st_size != after.st_size or info.st_mtime_ns != after.st_mtime_ns):
                raise _error("EXPORT", "SOURCE_HASH_MISMATCH")
            return info.st_size
        finally:
            os.close(descriptor)

    def _copy_public_file(self, source, destination, name, expected):
        source_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=source)
        destination_fd = None
        try:
            before = _file_info(source_fd, uid=1000)
            destination_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=destination)
            digest = hashlib.sha256()
            size = 0
            for chunk in iter(lambda: os.read(source_fd, 1024 * 1024), b""):
                size += len(chunk)
                if size > 4 * 1024**3:
                    raise _error("EXPORT", "PUBLIC_SOURCE_INVALID")
                _write_all(destination_fd, chunk)
                digest.update(chunk)
            after = os.fstat(source_fd)
            if digest.hexdigest() != expected or before.st_size != size or before.st_mtime_ns != after.st_mtime_ns:
                raise _error("EXPORT", "SOURCE_HASH_MISMATCH")
            _shared_fsync(destination_fd)
        finally:
            if destination_fd is not None:
                os.close(destination_fd)
            os.close(source_fd)
        readback = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=destination)
        try:
            _file_info(readback)
            verified = hashlib.sha256()
            for chunk in iter(lambda: os.read(readback, 1024 * 1024), b""):
                verified.update(chunk)
            if verified.hexdigest() != expected:
                raise _error("EXPORT", "DESTINATION_READBACK_MISMATCH")
        finally:
            os.close(readback)
        return {"file": name, "sha256": expected, "bytes": size}
