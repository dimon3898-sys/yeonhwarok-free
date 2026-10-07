"""Fail-closed storage preparation outside the approved renderer and app source.

Only a marked ``world-engine`` subdirectory is owned. Existing project, cache,
checkpoint, authentication and owner-code bytes are never replaced or chowned.
Local POSIX probes cannot establish cloud crash or cross-machine durability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import fcntl
import hmac
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid


MARKER_NAME = ".world-engine-storage.json"
FORMAT = "world-native-personal-storage-v1"
VOLATILE_FILESYSTEMS = frozenset({
    "tmpfs", "ramfs", "proc", "sysfs", "devtmpfs", "overlay", "devpts", "cgroup", "cgroup2",
})
LOCK_CHILD = """import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0))
try:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(23)
    fcntl.flock(fd, fcntl.LOCK_UN)
finally:
    os.close(fd)
"""


class StorageError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StorageReport:
    root: str
    runtime_root: str
    cache_root: str
    audio_root: str
    mode: str
    persistent_mount_detected: bool
    filesystem_probe_passed: bool
    probe_checks: dict
    owner_code_status: str
    uid: int
    gid: int
    filesystem: str | None = None
    cloud_crash_durability_verified: bool = False
    cross_machine_locking_verified: bool = False

    def as_dict(self):
        return asdict(self)


def _mount_info(base):
    """Recognize an exact mount target, including Linux bind/FUSE mountpoints."""
    path = Path("/proc/self/mountinfo")
    if path.is_file():
        for line in path.read_text().splitlines():
            before, separator, after = line.partition(" - ")
            fields = before.split()
            if not separator or len(fields) < 5:
                continue
            target = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), fields[4])
            if target == str(base):
                return {"mounted": True, "filesystem": after.split()[0] if after.split() else None}
        return {"mounted": False, "filesystem": None}
    return {"mounted": os.path.ismount(base), "filesystem": None}


class NativePersonalStorage:
    def __init__(self, base=None, *, mode="required", mount_checker=None, uid=1000, gid=1000):
        if mode not in {"required", "ephemeral"}:
            raise StorageError("STORAGE_MODE", "스토리지 모드는 required 또는 명시적 ephemeral이어야 합니다.")
        candidate = Path(base if base is not None else ("/world-storage" if mode == "required" else "/data"))
        if (not candidate.is_absolute() or candidate == Path("/") or ".." in candidate.parts or
                isinstance(uid, bool) or isinstance(gid, bool) or not isinstance(uid, int) or
                not isinstance(gid, int) or uid < 0 or gid < 0):
            raise StorageError("STORAGE_UNSAFE_PATH", "안전한 전용 스토리지 경로와 소유자를 지정하세요.")
        self.base, self.mode = candidate, mode
        self.root = candidate / "world-engine"
        self.uid, self.gid = uid, gid
        self.mount_checker = mount_checker or _mount_info

    @staticmethod
    def _safe_chain(path):
        for candidate in [*reversed(path.parents), path]:
            try:
                value = candidate.lstat()
            except FileNotFoundError:
                raise StorageError("STORAGE_UNSAFE_PATH", "스토리지 상위 경로가 존재해야 합니다.") from None
            if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
                raise StorageError("STORAGE_UNSAFE_PATH", "심볼릭 링크나 파일 경로를 스토리지로 사용할 수 없습니다.")

    def _owned_dir(self, path, *, allow_create=True):
        created = False
        if not path.exists() and not path.is_symlink():
            if not allow_create:
                raise StorageError("STORAGE_UNSAFE_PATH", "필수 스토리지 경로가 없습니다.")
            try:
                path.mkdir(mode=0o700)
                created = True
            except FileExistsError:
                pass
        value = path.lstat()
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
            raise StorageError("STORAGE_UNSAFE_PATH", "소유 스토리지 폴더가 안전하지 않습니다.")
        if created:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
            try:
                os.fchmod(fd, 0o700)
                self._new_ownership(fd)
            finally:
                os.close(fd)
        value = path.lstat()
        if (stat.S_IMODE(value.st_mode) != 0o700 or value.st_uid != self.uid or value.st_gid != self.gid):
            raise StorageError("STORAGE_OWNERSHIP", "기존 폴더의 소유자·0700 권한을 확인하세요. 자동 변경하지 않았습니다.")
        return created

    def _new_ownership(self, fd):
        value = os.fstat(fd)
        if value.st_uid != self.uid or value.st_gid != self.gid:
            os.fchown(fd, self.uid, self.gid)

    @staticmethod
    def _fsync_directory(path):
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _create_file(self, path, value):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            os.fchmod(fd, 0o600)
            self._new_ownership(fd)
            data = value if isinstance(value, bytes) else value.encode("utf-8")
            offset = 0
            while offset < len(data):
                written = os.write(fd, data[offset:])
                if written <= 0:
                    raise OSError("incomplete storage probe write")
                offset += written
            os.fsync(fd)
        finally:
            os.close(fd)
        self._owned_file(path)

    def _owned_file(self, path):
        value = path.lstat()
        if (not stat.S_ISREG(value.st_mode) or stat.S_IMODE(value.st_mode) != 0o600 or
                value.st_uid != self.uid or value.st_gid != self.gid):
            raise StorageError("STORAGE_UNSAFE_FILE", "소유 파일의 일반 파일·0600 권한·소유자를 확인하세요. 자동 변경하지 않았습니다.")
        return value

    def _prepare_root(self):
        new_root = not self.root.exists() and not self.root.is_symlink()
        if not new_root:
            self._owned_dir(self.root, allow_create=False)
            marker = self.root / MARKER_NAME
            if not marker.exists() or marker.is_symlink():
                raise StorageError("STORAGE_FOREIGN_ROOT", "소유 표시가 없는 기존 world-engine 폴더는 인수하지 않습니다.")
            self._owned_file(marker)
            if marker.stat().st_size > 1024:
                raise StorageError("STORAGE_FOREIGN_ROOT", "기존 스토리지 소유 표시가 너무 큽니다.")
            try:
                value = json.loads(marker.read_bytes())
            except (ValueError, UnicodeError):
                raise StorageError("STORAGE_FOREIGN_ROOT", "기존 스토리지 소유 표시를 검증할 수 없습니다.") from None
            if value != {"format": FORMAT, "uid": self.uid, "gid": self.gid}:
                raise StorageError("STORAGE_FOREIGN_ROOT", "기존 스토리지 소유 표시가 일치하지 않습니다.")
        else:
            if not self._owned_dir(self.root):
                raise StorageError("STORAGE_INITIALIZATION_RACE", "다른 스토리지 초기화가 진행 중입니다.")
            self._create_file(self.root / MARKER_NAME,
                              json.dumps({"format": FORMAT, "uid": self.uid, "gid": self.gid}) + "\n")
            self._fsync_directory(self.root)
            self._fsync_directory(self.base)
        for name in ("runtime", "cache", "audio"):
            self._owned_dir(self.root / name)
        self._fsync_directory(self.root)

    @staticmethod
    def _identity(path):
        value = path.lstat()
        return value.st_dev, value.st_ino

    def _probe(self):
        folder = self.root / (".storage-probe-" + uuid.uuid4().hex)
        self._owned_dir(folder)
        # Keep the owned objects alive until cleanup. Inode numbers may be
        # reused immediately after unlink on overlay/ext4, so dev+ino alone
        # cannot identify a replaced, already-closed probe file safely.
        pins = []
        def pin_identity(path):
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                value = os.fstat(fd)
                identity = (value.st_dev, value.st_ino)
                if self._identity(path) != identity:
                    raise StorageError("STORAGE_PROBE_CHANGED", "검수 대상이 변경되어 검사를 중단했습니다.")
            except BaseException:
                os.close(fd)
                raise
            pins.append(fd)
            return identity
        folder_identity = pin_identity(folder)
        files = {}
        checks = {"posix_mode_0600": False, "local_cross_process_flock_exclusion": False,
                  "atomic_replace": False, "directory_fsync": False}
        try:
            lock = folder / "lock"
            self._create_file(lock, b"owned-lock-probe\n")
            files[lock] = pin_identity(lock)
            checks["posix_mode_0600"] = stat.S_IMODE(lock.lstat().st_mode) == 0o600
            fd = os.open(lock, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                child = subprocess.run([sys.executable, "-I", "-c", LOCK_CHILD, str(lock)],
                                       stdin=subprocess.DEVNULL, capture_output=True, timeout=5,
                                       env={"PATH": os.defpath})
                if child.returncode != 23:
                    raise StorageError("STORAGE_UNSUPPORTED", "스토리지가 독립 프로세스 파일 잠금 배제를 보장하지 않습니다.")
                fcntl.flock(fd, fcntl.LOCK_UN)
                child = subprocess.run([sys.executable, "-I", "-c", LOCK_CHILD, str(lock)],
                                       stdin=subprocess.DEVNULL, capture_output=True, timeout=5,
                                       env={"PATH": os.defpath})
                if child.returncode != 0:
                    raise StorageError("STORAGE_UNSUPPORTED", "스토리지 파일 잠금 복구를 확인할 수 없습니다.")
                checks["local_cross_process_flock_exclusion"] = True
            finally:
                os.close(fd)
            current, pending = folder / "current", folder / "pending"
            self._create_file(current, b"before-atomic-replace\n")
            files[current] = pin_identity(current)
            self._create_file(pending, b"after-atomic-replace\n")
            files[pending] = pin_identity(pending)
            if self._identity(current) != files[current] or self._identity(pending) != files[pending]:
                raise StorageError("STORAGE_PROBE_CHANGED", "검수 대상이 변경되어 atomic replace를 중단했습니다.")
            os.replace(pending, current)  # Both paths were exclusively created by this probe.
            files[current] = files.pop(pending)
            self._owned_file(current)
            if current.read_bytes() != b"after-atomic-replace\n":
                raise StorageError("STORAGE_UNSUPPORTED", "스토리지 atomic replace 결과를 확인할 수 없습니다.")
            checks["atomic_replace"] = True
            self._fsync_directory(folder)
            checks["directory_fsync"] = True
            return checks
        finally:
            try:
                # Remove only exact objects created in this unique, private probe.
                if self._identity(folder) != folder_identity or folder.is_symlink():
                    raise StorageError("STORAGE_PROBE_CHANGED", "검수 폴더가 변경되어 자동 정리를 중단했습니다.")
                present = set(folder.iterdir())
                if present - set(files):
                    raise StorageError("STORAGE_PROBE_CHANGED", "검수 폴더에 다른 파일이 있어 자동 정리를 중단했습니다.")
                for path, identity in files.items():
                    if path.exists() or path.is_symlink():
                        if self._identity(path) != identity:
                            raise StorageError("STORAGE_PROBE_CHANGED", "검수 파일이 변경되어 자동 정리를 중단했습니다.")
                        path.unlink()
                folder.rmdir()
                self._fsync_directory(self.root)

            finally:
                for fd in reversed(pins):
                    os.close(fd)

    @staticmethod
    def _valid_code(value):
        return (isinstance(value, str) and 16 <= len(value) <= 512 and value == value.strip() and
                not any(ord(c) < 32 or ord(c) == 127 for c in value))

    def _owner_code(self, explicit):
        path = self.root / "runtime/owner-code.txt"
        if explicit is not None and not self._valid_code(explicit):
            raise StorageError("STORAGE_OWNER_CODE_INVALID", "소유자 코드 길이·형식을 확인하세요. 코드는 출력하지 않습니다.")
        if path.exists() or path.is_symlink():
            self._owned_file(path)
            if explicit is None:
                return "preserved"
            if path.stat().st_size > 4096:
                raise StorageError("STORAGE_OWNER_CODE_MISMATCH", "기존 소유자 코드는 교체하지 않습니다.")
            try:
                existing = path.read_text().strip()
                if existing.startswith("{"):
                    existing = json.loads(existing)["password"]
                equal = isinstance(existing, str) and hmac.compare_digest(existing.encode(), explicit.encode())
            except (ValueError, KeyError, TypeError, UnicodeError):
                equal = False
            if not equal:
                raise StorageError("STORAGE_OWNER_CODE_MISMATCH", "환경 코드가 기존 소유자 코드와 다릅니다. 기존 인증 정보를 보존했습니다.")
            return "matched_preserved"
        if explicit is None:
            return "not_supplied"
        self._create_file(path, explicit + "\n")
        self._fsync_directory(path.parent)
        return "created_from_explicit"

    def prepare(self, *, explicit_owner_code=None):
        try:
            self._safe_chain(self.base)
            info = self.mount_checker(self.base)
            mounted = info.get("mounted") is True if isinstance(info, dict) else info is True
            filesystem = info.get("filesystem") if isinstance(info, dict) else None
            if not isinstance(filesystem, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", filesystem):
                filesystem = None
            if self.mode == "required" and (not mounted or filesystem in VOLATILE_FILESYSTEMS):
                raise StorageError("STORAGE_MOUNT_REQUIRED", "검증 가능한 지속 스토리지 실제 mount가 필요합니다. ephemeral은 첫 테스트에만 명시적으로 선택하세요.")
            self._prepare_root()
            checks = self._probe()
            owner_status = self._owner_code(explicit_owner_code)
            return StorageReport(
                root=str(self.root), runtime_root=str(self.root / "runtime"),
                cache_root=str(self.root / "cache"), audio_root=str(self.root / "audio"),
                mode=self.mode, persistent_mount_detected=self.mode == "required" and mounted,
                filesystem_probe_passed=all(checks.values()), probe_checks=checks,
                owner_code_status=owner_status, uid=self.uid, gid=self.gid, filesystem=filesystem)
        except StorageError:
            raise
        except Exception:
            raise StorageError("STORAGE_UNSUPPORTED", "스토리지 POSIX 검수·안전한 초기화에 실패했습니다. 기존 데이터는 변경하지 않았습니다.") from None
