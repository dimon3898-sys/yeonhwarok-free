#!/usr/bin/env python3
"""Read existing native SAFE admission only; never initialize GPU or render.

Run inside the already-running storage-fix diagnostic container. The only HTTP
request is the fixed loopback /diagnostics endpoint, without proxies/redirects.
The raw admission_private.json and environment values are never read; exception
strings are never printed. This reader neither repairs storage nor creates files.
"""
from __future__ import annotations

from datetime import datetime
import errno
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import urllib.request

HERE = Path(__file__).resolve().parent
LIMIT = 128 * 1024
ACCOUNT = SimpleNamespace(pw_uid=1000, pw_gid=1000)
SCHEMA = "WORLD_ENGINE_EXISTING_ADMISSION_RECOVERY_V1"
RECOVERY_CODES = frozenset({
    "LOOPBACK_REDIRECT_REJECTED", "CURRENT_RECORD_UNAVAILABLE", "RECORD_TOO_LARGE",
    "DUPLICATE_JSON_KEY", "NONFINITE_JSON", "RECORD_INVALID", "PRIVATE_OWNER_INVALID",
    "RECORD_CHANGED_DURING_READ", "DIRECTORY_LIMIT_EXCEEDED", "TIMESTAMP_INVALID",
    "CURRENT_RECORD_NOT_RECOVERABLE", "CURRENT_RECORD_INVALID", "NATIVE_SAFE_ADMISSION_INVALID",
    "NATIVE_ADMISSION_STALE", "NATIVE_MEMORY_FACTS_INVALID", "NATIVE_SOURCE_OR_SHM_INVALID",
    "PRIVATE_FILESYSTEM_INVALID", "RECEIPT_INVALID", "CURRENT_RECORD_AMBIGUOUS",
    "NATIVE_ADMISSION_AMBIGUOUS_OR_MISSING"})
sys.dont_write_bytecode = True


def _helper(name, deployed, fallback):
    path = Path(deployed)
    if not path.is_file():
        path = HERE.parent / fallback / (name + ".py")
    spec = importlib.util.spec_from_file_location("recovery_existing_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    storage = _helper("storage", "/opt/world-engine-storage-fix/storage.py", "gcube-storage-fix-v1")
    records = _helper("records", "/opt/world-engine-startup-diagnostics/records.py", "gcube-diagnostic-image-v1")
except Exception:
    storage = records = None  # Missing helpers yield a safe UNVERIFIED response, never a traceback.


class RecoveryError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RecoveryError("LOOPBACK_REDIRECT_REJECTED")


def fetch_current():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open("http://127.0.0.1:8000/diagnostics", timeout=3) as response:
        if response.status != 200:
            raise RecoveryError("CURRENT_RECORD_UNAVAILABLE")
        body = response.read(LIMIT + 1)
    if len(body) > LIMIT:
        raise RecoveryError("RECORD_TOO_LARGE")
    return _object(body)


def _object(body):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise RecoveryError("DUPLICATE_JSON_KEY")
            value[key] = item
        return value
    value = json.loads(body, object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(RecoveryError("NONFINITE_JSON")))
    if not isinstance(value, dict):
        raise RecoveryError("RECORD_INVALID")
    return value


def _read(directory, name, *, private=True):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        before = storage._file_info(descriptor, uid=1000 if private else None, private=private)
        if private and before.st_gid != 1000:
            raise RecoveryError("PRIVATE_OWNER_INVALID")
        if not 1 <= before.st_size <= LIMIT:
            raise RecoveryError("RECORD_TOO_LARGE")
        body = storage._read_fd(descriptor, limit=LIMIT)
        after = os.fstat(descriptor)
        if any(getattr(before, key) != getattr(after, key) for key in
               ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
            raise RecoveryError("RECORD_CHANGED_DURING_READ")
        return _object(body), hashlib.sha256(body).hexdigest()
    finally:
        os.close(descriptor)


def _names(directory, expression):
    matches = []
    with os.scandir(directory) as entries:
        for index, entry in enumerate(entries):
            if index >= 256:
                raise RecoveryError("DIRECTORY_LIMIT_EXCEEDED")
            if re.fullmatch(expression, entry.name):
                matches.append(entry.name)
    return sorted(matches)


def _directory(parent, name):
    descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        storage._private_check(descriptor, ACCOUNT)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _time(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00", value):
        raise RecoveryError("TIMESTAMP_INVALID")
    return datetime.fromisoformat(value)


def _current(value):
    if (value.get("schema") != records.SCHEMA or value.get("startupMode") != "diagnostic"
            or value.get("status") != "DIAGNOSTIC_ONLY" or type(value.get("exitCode")) is not int
            or value["exitCode"] != 0 or value.get("errorCode") != "DIAGNOSTIC_ONLY"
            or value.get("gpuRenderingVerified") is not False or value.get("renderAllowed") is not False
            or not isinstance(value.get("safeDiagnostics"), dict)
            or value["safeDiagnostics"].get("testOnly") is True):
        raise RecoveryError("CURRENT_RECORD_NOT_RECOVERABLE")
    _time(value.get("timestamp"))
    if records.safe_record(value) != value:
        raise RecoveryError("CURRENT_RECORD_INVALID")
    return value


def _admission(value, stamp, digest):
    if (value.get("schema") != "RTX_GPU_ADMISSION_V1" or value.get("status") != "GPU_VERIFIED"
            or value.get("testOnly") is not False or value.get("gpuRenderingVerified") is not True
            or value.get("verificationScope") != "STARTUP_NATIVE_GPU_PIXEL_DRAW"
            or value.get("renderMode") != "gpu-required" or value.get("gpuProfile") not in {"egl", "vulkan"}
            or value.get("model") not in {"RTX 4080 SUPER", "RTX 4090", "RTX 5090"}
            or not isinstance(value.get("driverVersion"), str)
            or not re.fullmatch(r"\d+(?:\.\d+){1,4}", value["driverVersion"])
            or any(value.get(key) is not False for key in ("autoRender", "renderExecuted", "visualQualityVerified"))):
        raise RecoveryError("NATIVE_SAFE_ADMISSION_INVALID")
    age = (_time(stamp) - _time(value.get("observedAt"))).total_seconds()
    if not 0 <= age <= 240:
        raise RecoveryError("NATIVE_ADMISSION_STALE")
    numeric = ("physicalMemoryMiB", "availableMemoryMiB", "vramBudgetBytes")
    if any(not isinstance(value.get(key), (int, float)) or isinstance(value[key], bool)
           or not math.isfinite(value[key]) or not 0 < value[key] <= 2**40 for key in numeric):
        raise RecoveryError("NATIVE_MEMORY_FACTS_INVALID")
    if (not 15 * 1024 <= value["physicalMemoryMiB"] <= 1024 * 1024
            or value["availableMemoryMiB"] > value["physicalMemoryMiB"]
            or value["vramBudgetBytes"] > value["availableMemoryMiB"] * 1024**2 - 2 * 1024**3):
        raise RecoveryError("NATIVE_MEMORY_FACTS_INVALID")
    shared, source = value.get("sharedMemory"), value.get("sourceVerification")
    if (not isinstance(shared, dict) or any(type(shared.get(key)) is not int or not 1024**3 <= shared[key] <= 2**50
            for key in ("capacityBytes", "availableBytes")) or shared["availableBytes"] > shared["capacityBytes"]
            or not isinstance(source, dict) or source.get("status") != "PASS"
            or type(source.get("files")) is not int or not 1 <= source["files"] <= 100000
            or not isinstance(source.get("sourceContractSha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", source["sourceContractSha256"])):
        raise RecoveryError("NATIVE_SOURCE_OR_SHM_INVALID")
    return {"recordTimestamp": stamp, "admissionObservedAt": value["observedAt"], "sourceFileSHA256": digest,
            **{key: value[key] for key in (*numeric, "model", "driverVersion", "gpuProfile", "verificationScope")},
            "sharedMemory": {key: shared[key] for key in ("capacityBytes", "availableBytes")},
            "sourceVerification": {"status": "PASS", "files": source["files"],
                                   "sourceContractSha256": source["sourceContractSha256"]}}


def _recover(current, base, export_root):
    current = _current(current)
    base_fd = storage._open_directory(base, safe_parents=True, account_uid=1000)
    matches = []
    sessions = 0
    try:
        storage._private_check(base_fd, ACCOUNT)
        if storage._filesystem(base) not in storage.LOCAL_FILESYSTEMS:
            raise RecoveryError("PRIVATE_FILESYSTEM_INVALID")
        for name in _names(base_fd, r"session-[0-9a-f]{24}"):
            private = _directory(base_fd, name)
            try:
                try:
                    receipt, _ = _read(private, "EXPORT_RECEIPT.json")
                except FileNotFoundError:
                    continue
                export_name = receipt.get("exportName")
                if not isinstance(export_name, str) or not re.fullmatch(r"world-engine-export-[0-9a-f]{24}", export_name):
                    raise RecoveryError("RECEIPT_INVALID")
                session = storage.StorageSession(ACCOUNT, Path(base) / name, export_root, export_name,
                                                 storage._identity(os.fstat(private)))
                shared = session._export_fd(private)  # Reuses receipt flags and root/directory inode checks.
                try:
                    records_here = [_read(shared, entry, private=False)[0] for entry in
                                    _names(shared, r"startup-safe-[0-9a-f]{24}\.json")]
                    count = sum(value == current for value in records_here)
                    if count == 0:
                        continue
                    if count != 1:
                        raise RecoveryError("CURRENT_RECORD_AMBIGUOUS")
                    sessions += 1
                finally:
                    os.close(shared)
                diagnostics = _directory(private, "diagnostics")
                try:
                    for run in _names(diagnostics, r"\d{8}T\d{6}-[0-9a-f]{32}"):
                        run_fd = _directory(diagnostics, run)
                        try:
                            admission, digest = _read(run_fd, "admission_safe.json")
                            # No latest-record fallback: every matched-session candidate must be valid.
                            matches.append(_admission(admission, current["timestamp"], digest))
                        finally:
                            os.close(run_fd)
                finally:
                    os.close(diagnostics)
            finally:
                os.close(private)
    finally:
        os.close(base_fd)
    if len(matches) != 1 or sessions != 1:
        raise RecoveryError("NATIVE_ADMISSION_AMBIGUOUS_OR_MISSING")
    return matches[0]


def recover(*, _current_record=None, _base=None, _export_root=None):
    """Python-only injection marks synthetic results TEST_ONLY, never hardware evidence."""
    test_only = any(item is not None for item in (_current_record, _base, _export_root))
    result = {"schema": SCHEMA, "status": "UNVERIFIED", "testOnly": test_only,
              "method": "READ_EXISTING_SAFE_RECORDS", "gpuRenderingVerified": False,
              "renderAllowed": False, "actualHardwareRerun": False}
    try:
        facts = _recover(fetch_current() if _current_record is None else _current_record,
                         storage.PRIVATE_BASE if _base is None else _base,
                         storage.EXPORT_ROOT if _export_root is None else _export_root)
        return {**result, **facts, "status": "TEST_ONLY" if test_only else "RECOVERED_SAFE_ADMISSION"}
    except Exception as error:
        # No exception text, raw path, private identity, endpoint or environment value is reflected.
        code = error.args[0] if isinstance(error, RecoveryError) and len(error.args) == 1 else None
        reason = code if isinstance(code, str) and code in RECOVERY_CODES else "EXISTING_EVIDENCE_UNVERIFIED"
        failure = {**result, "reasonCode": reason}
        if isinstance(error, OSError) and type(error.errno) is int and error.errno in errno.errorcode:
            failure["errnoName"] = errno.errorcode[error.errno]
        return failure


if __name__ == "__main__":
    result = recover()
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    raise SystemExit(0 if result["status"] == "RECOVERED_SAFE_ADMISSION" else 2)
