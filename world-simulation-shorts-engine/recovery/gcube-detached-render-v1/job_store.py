"""One-shot detached render ledger; shared claims veto, never authorize execution.

The caller owns the lifetime of the returned flock descriptor. Nothing in this
module starts a process, provisions a mount, repairs permissions, or claims
remote Dropbox durability. Existing storage no-follow/readback helpers are used.
"""
from __future__ import annotations

import fcntl
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
STORAGE_HELPERS = Path("/opt/world-engine-storage-fix")
if not (STORAGE_HELPERS / "storage.py").is_file():
    STORAGE_HELPERS = HERE.parent / "gcube-storage-fix-v1"
DIAGNOSTIC_HELPERS = Path("/opt/world-engine-startup-diagnostics")
if not (DIAGNOSTIC_HELPERS / "records.py").is_file():
    DIAGNOSTIC_HELPERS = HERE.parent / "gcube-diagnostic-image-v1"
sys.path.insert(0, str(STORAGE_HELPERS))
sys.path.insert(0, str(DIAGNOSTIC_HELPERS))
import storage
import records

for _module, _expected in ((storage, STORAGE_HELPERS), (records, DIAGNOSTIC_HELPERS)):
    if Path(_module.__file__).resolve().parent != _expected.resolve():
        raise ImportError("JOB_HELPER_ORIGIN_INVALID")

CONTROL_ROOT = Path("/var/lib/world-engine-private/engine/job-control-v1")
EXPORT_ROOT = Path("/world-storage")
SHARED_NAME = "world-engine-65422-job-v1"
SCHEMA = "WORLD_ENGINE_DETACHED_JOB_V1"
MAX_RECORD = 128 * 1024
MAX_EVENTS = 256
_ACCOUNT = SimpleNamespace(pw_uid=1000, pw_gid=1000)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00\Z")
_JOB_ID = re.compile(r"65422-[0-9a-f]{24}\Z")
_BOOT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
STATES = frozenset({"QUEUED", "RUNNING", "COMPLETED", "FAILED"})
PHASES = frozenset({"QUEUED", "DETACHED", "NATIVE_STARTUP", "CAPTURE", "EXPORT", "VERIFY", "COMPLETE", "FAILED"})
REASONS = frozenset({"NEW_JOB", "STARTING", "NATIVE_RUNNING", "SUCCEEDED", "NATIVE_FAILED", "STORAGE_FAILED",
    "RESULT_VERIFICATION_FAILED", "WORKER_INTERRUPTED", "WORKER_LOST", "NATIVE_STILL_RUNNING", "SPAWN_FAILED",
    "ACK_TIMEOUT", "LOG_LIMIT_EXCEEDED", "DEADLINE_EXCEEDED", "UNEXPECTED_FAILURE"})
ERROR_CODES = frozenset({"JOB_IDENTITY_INVALID", "JOB_PATH_UNSAFE", "JOB_STORAGE_UNAVAILABLE",
    "JOB_LOCK_BUSY", "JOB_LOCK_REQUIRED", "JOB_RECORD_INVALID", "JOB_ALREADY_EXISTS", "JOB_CLAIM_INVALID",
    "JOB_READBACK_FAILED", "JOB_TRANSITION_INVALID", "JOB_EVENT_LIMIT", "JOB_PRIVATE_CHANGED"})
_FIELDS = frozenset({"schema", "jobId", "state", "reason", "phase", "createdAt", "updatedAt",
    "supervisorIdentity", "rendererIdentity", "exitCode", "firstFailure", "result", "testOnly", "sequence",
    "gpuRenderingVerified", "remotePersistenceVerified", "externalDownloadVerified"})


class JobError(RuntimeError):
    def __init__(self, code):
        self.code = code if isinstance(code, str) and code in ERROR_CODES else "JOB_STORAGE_UNAVAILABLE"
        super().__init__(self.code)


def _integer(value, maximum=2**63 - 1):
    return type(value) is int and 0 <= value <= maximum


def _identity(value):
    return (isinstance(value, dict) and set(value) == {"pid", "bootId", "startTime"}
            and _integer(value["pid"], 2**31 - 1) and value["pid"] > 0
            and isinstance(value["bootId"], str) and bool(_BOOT_ID.fullmatch(value["bootId"]))
            and isinstance(value["startTime"], str) and bool(re.fullmatch(r"[1-9][0-9]{0,18}", value["startTime"])))


def _result(value):
    if not isinstance(value, dict) or set(value) != {"schema", "exportDirectory", "testOnly",
            "mountedViewReadbackVerified", "remotePersistenceVerified", "externalDownloadVerified", "captures"}:
        return False
    if (value["schema"] != "WORLD_ENGINE_EXPORT_LOCATION_V1" or type(value["testOnly"]) is not bool
            or value["mountedViewReadbackVerified"] is not True or value["remotePersistenceVerified"] is not False
            or value["externalDownloadVerified"] is not False or not isinstance(value["exportDirectory"], str)
            or not re.fullmatch(r"world-engine-export-[0-9a-f]{24}", value["exportDirectory"])
            or not isinstance(value["captures"], list) or len(value["captures"]) != 1):
        return False
    capture = value["captures"][0]
    if (not isinstance(capture, dict) or set(capture) != {"directory", "publicDirectory", "completionReceipt", "files"}
            or not isinstance(capture["directory"], str)
            or not re.fullmatch(r"capture-[0-9a-f]{12}-[0-9a-f]{24}", capture["directory"])
            or capture["publicDirectory"] != "public-review" or capture["completionReceipt"] != "EXPORT_COMPLETE.json"
            or not isinstance(capture["files"], list) or len(capture["files"]) != 7):
        return False
    names = []
    for entry in capture["files"]:
        if (not isinstance(entry, dict) or set(entry) != {"file", "sha256", "bytes"}
                or not isinstance(entry["file"], str)
                or not re.fullmatch(r"(?:SHA256SUMS|[A-Za-z0-9][A-Za-z0-9_.-]{0,174}\.(?:mp4|png))", entry["file"])
                or not isinstance(entry["sha256"], str) or not _HEX64.fullmatch(entry["sha256"])
                or not _integer(entry["bytes"], 4 * 1024**3) or entry["bytes"] == 0):
            return False
        names.append(entry["file"])
    return (len(set(names)) == 7 and "SHA256SUMS" in names
            and sum(name.endswith(".mp4") for name in names) == 1
            and sum(name.endswith(".png") for name in names) == 5)


def validate_state(value):
    """Reject unsafe fields rather than silently making a partial job record."""
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise JobError("JOB_RECORD_INVALID")
    if (value["schema"] != SCHEMA or not isinstance(value["jobId"], str) or not _JOB_ID.fullmatch(value["jobId"])
            or not isinstance(value["state"], str) or value["state"] not in STATES
            or not isinstance(value["reason"], str) or value["reason"] not in REASONS
            or not isinstance(value["phase"], str) or value["phase"] not in PHASES
            or any(not isinstance(value[key], str) or not _STAMP.fullmatch(value[key]) for key in ("createdAt", "updatedAt"))
            or type(value["testOnly"]) is not bool or not _integer(value["sequence"], 1000000)
            or any(value[key] is not False for key in ("gpuRenderingVerified", "remotePersistenceVerified", "externalDownloadVerified"))
            or any(value[key] is not None and not _identity(value[key]) for key in ("supervisorIdentity", "rendererIdentity"))
            or (value["exitCode"] is not None and not _integer(value["exitCode"], 255))):
        raise JobError("JOB_RECORD_INVALID")
    try:
        if datetime.fromisoformat(value["updatedAt"]) < datetime.fromisoformat(value["createdAt"]):
            raise ValueError
    except ValueError:
        raise JobError("JOB_RECORD_INVALID") from None
    failure = value["firstFailure"]
    if failure is not None and (not isinstance(failure, dict) or records.safe_record(failure) != failure
            or failure.get("exitCode", 0) == 0 or failure.get("status") != "BLOCKED"):
        raise JobError("JOB_RECORD_INVALID")
    if value["state"] == "COMPLETED":
        if value["exitCode"] != 0 or failure is not None or not _result(value["result"]) or value["result"]["testOnly"] != value["testOnly"]:
            raise JobError("JOB_RECORD_INVALID")
    elif value["result"] is not None:
        raise JobError("JOB_RECORD_INVALID")
    if value["state"] in {"QUEUED", "RUNNING"} and value["exitCode"] is not None:
        raise JobError("JOB_RECORD_INVALID")
    if value["state"] == "FAILED" and (not _integer(value["exitCode"], 255) or value["exitCode"] == 0):
        raise JobError("JOB_RECORD_INVALID")
    # A bounded roundtrip also rejects non-JSON objects and excessive nested data.
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if len(data) > MAX_RECORD:
            raise ValueError
        return json.loads(data)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise JobError("JOB_RECORD_INVALID") from None


def _encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _load(directory, name, *, private):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        before = storage._file_info(descriptor, uid=1000 if private else None, private=private)
        if private and before.st_gid != 1000:
            raise JobError("JOB_RECORD_INVALID")
        data = storage._read_fd(descriptor, limit=MAX_RECORD)
        after = os.fstat(descriptor)
        if (storage._identity(before) != storage._identity(after) or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns):
            raise JobError("JOB_READBACK_FAILED")
        if storage._identity(os.stat(name, dir_fd=directory, follow_symlinks=False)) != storage._identity(after):
            raise JobError("JOB_READBACK_FAILED")
        value = json.loads(data, object_pairs_hook=_unique_object)
        return value, storage._identity(after), hashlib.sha256(data).hexdigest()
    finally:
        os.close(descriptor)


class Store:
    def __init__(self, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT):
        self.control_root = Path(control_root)
        self.export_root = Path(export_root)
        self._root_identity = None
        self._lock_fd = None

    @staticmethod
    def _writer():
        if os.geteuid() != 1000 or os.getegid() != 1000:
            raise JobError("JOB_IDENTITY_INVALID")

    def _private(self):
        if os.geteuid() not in {0, 1000}:
            raise JobError("JOB_IDENTITY_INVALID")
        descriptor = storage._open_directory(self.control_root, safe_parents=True)
        try:
            info = storage._private_check(descriptor, _ACCOUNT)
            if storage._filesystem(self.control_root) not in storage.LOCAL_FILESYSTEMS:
                raise JobError("JOB_PATH_UNSAFE")
            current = storage._identity(info)
            if self._root_identity is None:
                self._root_identity = current
            elif self._root_identity != current:
                raise JobError("JOB_PRIVATE_CHANGED")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def _locked(self, private):
        self._writer()
        if self._lock_fd is None:
            raise JobError("JOB_LOCK_REQUIRED")
        current = os.stat("LOCK", dir_fd=private, follow_symlinks=False)
        held = storage._file_info(self._lock_fd, uid=1000, private=True)
        if held.st_gid != 1000 or storage._identity(current) != storage._identity(held):
            raise JobError("JOB_LOCK_REQUIRED")
        # A second open must be excluded; this also catches an accidentally
        # unlocked inherited fd. The caller retains the original flock.
        competitor = os.open("LOCK", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=private)
        try:
            try:
                fcntl.flock(competitor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # A different process must not be mistaken for this caller's
                # held lock after an accidental unlock of its descriptor.
                try:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise JobError("JOB_LOCK_REQUIRED") from None
                return
            fcntl.flock(competitor, fcntl.LOCK_UN)
            raise JobError("JOB_LOCK_REQUIRED")
        finally:
            os.close(competitor)

    def attach_lock(self, descriptor):
        """Validate a caller-owned inherited flock after fork/exec."""
        self._writer()
        self._lock_fd = descriptor
        private = None
        try:
            private = self._private()
            self._locked(private)
        except BaseException:
            self._lock_fd = None
            raise
        finally:
            if private is not None:
                os.close(private)

    def lock(self, create=True):
        self._writer()
        private = descriptor = None
        try:
            private = self._private()
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
            if create:
                try:
                    descriptor = os.open("LOCK", flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=private)
                    os.fchmod(descriptor, 0o600)  # Only this freshly-created private file.
                    os.fsync(private)
                except FileExistsError:
                    descriptor = os.open("LOCK", flags, dir_fd=private)
            else:
                descriptor = os.open("LOCK", flags, dir_fd=private)
            info = storage._file_info(descriptor, uid=1000, private=True)
            if info.st_gid != 1000:
                raise JobError("JOB_LOCK_REQUIRED")
            if storage._identity(info) != storage._identity(os.stat("LOCK", dir_fd=private, follow_symlinks=False)):
                raise JobError("JOB_LOCK_REQUIRED")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise JobError("JOB_LOCK_BUSY") from None
            self._lock_fd = descriptor
            result, descriptor = descriptor, None
            return result
        except JobError:
            raise
        except (OSError, ValueError, TypeError, storage.StorageError):
            raise JobError("JOB_STORAGE_UNAVAILABLE") from None
        finally:
            for item in (descriptor, private):
                if item is not None:
                    os.close(item)

    def read(self):
        private = None
        try:
            private = self._private()
            try:
                value, _, _ = _load(private, "JOB.json", private=True)
            except FileNotFoundError:
                return None
            return validate_state(value)
        except JobError:
            raise
        except (OSError, ValueError, TypeError, storage.StorageError):
            raise JobError("JOB_RECORD_INVALID") from None
        finally:
            if private is not None:
                os.close(private)

    def _shared(self, private, state):
        receipt, _, _ = _load(private, "CLAIM_RECEIPT.json", private=True)
        if (not isinstance(receipt, dict) or set(receipt) != {"schema", "jobId", "rootIdentity", "directoryIdentity", "claimIdentity", "claimSha256"}
                or receipt["schema"] != "WORLD_ENGINE_JOB_CLAIM_RECEIPT_V1" or receipt["jobId"] != state["jobId"]
                or not isinstance(receipt["claimSha256"], str) or not _HEX64.fullmatch(receipt["claimSha256"])):
            raise JobError("JOB_CLAIM_INVALID")
        root = storage._open_directory(self.export_root)
        shared = None
        try:
            if storage._identity(os.fstat(root)) != receipt["rootIdentity"]:
                raise JobError("JOB_CLAIM_INVALID")
            shared = os.open(SHARED_NAME, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
            if storage._identity(os.fstat(shared)) != receipt["directoryIdentity"]:
                raise JobError("JOB_CLAIM_INVALID")
            claim, identity, digest = _load(shared, "CLAIM.json", private=False)
            if (identity != receipt["claimIdentity"] or digest != receipt["claimSha256"]
                    or claim != self._claim(state)):
                raise JobError("JOB_CLAIM_INVALID")
            result, shared = shared, None
            return result
        finally:
            os.close(root)
            if shared is not None:
                os.close(shared)

    @staticmethod
    def _claim(state):
        return {"schema": "WORLD_ENGINE_DETACHED_CLAIM_V1", "jobId": state["jobId"],
            "createdAt": state["createdAt"], "testOnly": state["testOnly"],
            "renderAllowed": False, "gpuRenderingVerified": False,
            "remotePersistenceVerified": False, "externalDownloadVerified": False}

    def _append(self, shared, state):
        # Bounded iteration, with no shared directory listing used to authorize execution.
        count = 0
        with os.scandir(shared) as entries:
            for _entry in entries:
                count += 1
                if count > MAX_EVENTS:
                    raise JobError("JOB_EVENT_LIMIT")
        name = "state-" + str(state["sequence"]).zfill(6) + "-" + os.urandom(12).hex() + ".json"
        storage._new_file(shared, name, _encode(state))
        storage._shared_fsync(shared)

    def _write_state(self, private, state, *, initial):
        body = _encode(state)
        if initial:
            storage._new_file(private, "JOB.json", body, private=True)
        else:
            _, previous_identity, _ = _load(private, "JOB.json", private=True)
            name = "state-pending-" + os.urandom(12).hex() + ".json"
            written = storage._new_file(private, name, body, private=True)
            if storage._identity(os.stat("JOB.json", dir_fd=private, follow_symlinks=False)) != previous_identity:
                raise JobError("JOB_PRIVATE_CHANGED")
            os.replace(name, "JOB.json", src_dir_fd=private, dst_dir_fd=private)
            value, identity, digest = _load(private, "JOB.json", private=True)
            if identity != written["_identity"] or digest != written["sha256"] or value != state:
                raise JobError("JOB_READBACK_FAILED")
        os.fsync(private)

    def create(self, initial):
        state = validate_state(initial)
        if state["state"] != "QUEUED" or state["sequence"] != 0:
            raise JobError("JOB_TRANSITION_INVALID")
        private = root = shared = None
        try:
            private = self._private()
            self._locked(private)
            for name in ("JOB.json", "CLAIM_RECEIPT.json"):
                try:
                    os.stat(name, dir_fd=private, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise JobError("JOB_ALREADY_EXISTS")
            root = storage._open_directory(self.export_root)
            try:
                os.mkdir(SHARED_NAME, 0o700, dir_fd=root)
            except FileExistsError:
                raise JobError("JOB_ALREADY_EXISTS") from None
            shared = os.open(SHARED_NAME, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
            claim = storage._new_file(shared, "CLAIM.json", _encode(self._claim(state)))
            storage._shared_fsync(shared)
            receipt = {"schema": "WORLD_ENGINE_JOB_CLAIM_RECEIPT_V1", "jobId": state["jobId"],
                "rootIdentity": storage._identity(os.fstat(root)),
                "directoryIdentity": storage._identity(os.fstat(shared)),
                "claimIdentity": claim["_identity"], "claimSha256": claim["sha256"]}
            storage._new_file(private, "CLAIM_RECEIPT.json", _encode(receipt), private=True)
            self._write_state(private, state, initial=True)
            self._append(shared, state)
            return state
        except JobError:
            raise
        except (OSError, ValueError, TypeError, storage.StorageError):
            raise JobError("JOB_STORAGE_UNAVAILABLE") from None
        finally:
            for descriptor in (shared, root, private):
                if descriptor is not None:
                    os.close(descriptor)

    def save(self, state):
        state = validate_state(state)
        private = shared = None
        try:
            private = self._private()
            self._locked(private)
            previous, _, _ = _load(private, "JOB.json", private=True)
            previous = validate_state(previous)
            if (any(state[key] != previous[key] for key in ("jobId", "createdAt", "testOnly"))
                    or datetime.fromisoformat(state["updatedAt"]) < datetime.fromisoformat(previous["updatedAt"])
                    or state["sequence"] != previous["sequence"]
                    or previous["state"] in {"COMPLETED", "FAILED"}
                    or state["state"] not in ({"RUNNING", "FAILED"} if previous["state"] == "QUEUED" else {"RUNNING", "COMPLETED", "FAILED"})
                    or (previous["firstFailure"] is not None and state["firstFailure"] != previous["firstFailure"])):
                raise JobError("JOB_TRANSITION_INVALID")
            state["sequence"] = previous["sequence"] + 1
            if state["state"] == "COMPLETED":
                # Never finalize completion if its shared status readback failed.
                shared = self._shared(private, state)
                self._append(shared, state)
                self._write_state(private, state, initial=False)
            else:
                # Failed exports retain the newest private failure/status. The
                # exception still prevents dispatch from an unexported state.
                self._write_state(private, state, initial=False)
                shared = self._shared(private, state)
                self._append(shared, state)
            return state
        except JobError:
            raise
        except (OSError, ValueError, TypeError, storage.StorageError):
            raise JobError("JOB_STORAGE_UNAVAILABLE") from None
        finally:
            for descriptor in (shared, private):
                if descriptor is not None:
                    os.close(descriptor)
