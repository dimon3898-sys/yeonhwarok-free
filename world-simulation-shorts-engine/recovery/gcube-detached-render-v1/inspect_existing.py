"""Bounded, read-only legacy capture inspection. No GPU or rendering imports."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import stat


PRIVATE_BASE = Path("/var/lib/world-engine-private/engine")
EXPORT_ROOT = Path("/world-storage")
CONTROL_ROOT = PRIVATE_BASE / "job-control-v1"
PROC_ROOT = Path("/proc")
_SESSION = re.compile(r"session-[0-9a-f]{24}\Z")
_SIGNATURE = re.compile(r"[0-9a-f]{64}\Z")
_EXPORT = re.compile(r"world-engine-export-[0-9a-f]{24}\Z")
_CAPTURE = re.compile(r"capture-[0-9a-f]{12}-[0-9a-f]{24}\Z")
_BOOT = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
_MAX_ENTRIES = 4096
_LAUNCHERS = frozenset({
    "/opt/world-engine-storage-fix/launch.py",
    "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/bootstrap.py",
    "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/gpu_launcher.py",
})
_RENDER = "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/hardware_render.mjs"


class InspectionBlocked(Exception):
    pass


def _directory(path, *, optional=False):
    """Open every path component without following a symlink."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise InspectionBlocked("UNSAFE_PATH")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=descriptor)
            except FileNotFoundError:
                if optional:
                    return None
                raise
            os.close(descriptor)
            descriptor = child
        result, descriptor = descriptor, None
        return result
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _entries(descriptor, budget):
    names = []
    with os.scandir(descriptor) as entries:
        for index, entry in enumerate(entries):
            if index >= _MAX_ENTRIES:
                raise InspectionBlocked("INSPECTION_LIMIT_EXCEEDED")
            budget[0] += 1
            if budget[0] > _MAX_ENTRIES:
                raise InspectionBlocked("INSPECTION_LIMIT_EXCEEDED")
            names.append(entry.name)
    return names


def _child_directory(descriptor, name):
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                   dir_fd=descriptor)


def _read(descriptor, name, limit):
    file = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
    try:
        info = os.fstat(file)
        if not stat.S_ISREG(info.st_mode):
            raise InspectionBlocked("UNSAFE_FILE")
        data = os.read(file, limit + 1)
        if len(data) > limit:
            raise InspectionBlocked("INSPECTION_LIMIT_EXCEEDED")
        return data
    finally:
        os.close(file)


def _present_regular(descriptor, name):
    try:
        info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode):
        raise InspectionBlocked("UNSAFE_FILE")
    return True


def _identity(proc, pid, boot):
    descriptor = _child_directory(proc, str(pid))
    try:
        raw = _read(descriptor, "stat", 8192).decode("utf-8")
        right = raw.rfind(")")
        if right < 1 or raw[:raw.find("(")].strip() != str(pid):
            raise InspectionBlocked("PROCESS_IDENTITY_UNVERIFIED")
        fields = raw[right + 1:].split()
        if len(fields) < 20 or not fields[19].isdigit():
            raise InspectionBlocked("PROCESS_IDENTITY_UNVERIFIED")
        return {"pid": pid, "bootId": boot, "startTime": fields[19]}, fields[0]
    finally:
        os.close(descriptor)


def _role(command):
    if not command:
        return None
    executable = Path(command[0]).name
    if (re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)?)?", executable)
            and "--render-65422" in command and any(path in command for path in _LAUNCHERS)):
        return "NATIVE_LAUNCHER"
    if executable in {"node", "nodejs"} and _RENDER in command:
        return "NATIVE_CAPTURE"
    return None


def _processes(proc, boot, exclude, budget):
    result = []
    for name in _entries(proc, budget):
        if not name.isdigit() or int(name) <= 0 or int(name) in exclude:
            continue
        pid = int(name)
        descriptor = None
        try:
            before, state = _identity(proc, pid, boot)
            if state == "Z":
                continue
            descriptor = _child_directory(proc, name)
            data = _read(descriptor, "cmdline", 16384)
            command = [part.decode("utf-8", errors="strict") for part in data.rstrip(b"\0").split(b"\0")]
            role = _role(command)
            after, state = _identity(proc, pid, boot)
            if before != after or state == "Z":
                continue
            if role:
                result.append({**after, "role": role})
        except (FileNotFoundError, ProcessLookupError):
            continue  # Normal process exit during a read-only snapshot.
        finally:
            if descriptor is not None:
                os.close(descriptor)
    return result


def _guard(private):
    try:
        descriptor = os.open("CAPTURE.guard", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=private)
    except FileNotFoundError:
        return False
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise InspectionBlocked("UNSAFE_CAPTURE_GUARD")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return False
    finally:
        os.close(descriptor)


def _capture_records(private, proc, boot, exclude, budget):
    counts = {"captureDirectories": 0, "captureReports": 0, "captureStatusFiles": 0,
              "captureLockFiles": 0, "sharedCaptureDirectories": 0,
              "legacyCaptureDirectories": 0, "heldCaptureGuards": 0}
    active = []
    if _guard(private):
        counts["heldCaptureGuards"] += 1
    for name in _entries(private, budget):
        if not _SESSION.fullmatch(name):
            continue
        session = _child_directory(private, name)
        captures = None
        try:
            if _guard(session):
                counts["heldCaptureGuards"] += 1
            try:
                captures = _child_directory(session, "captures")
            except FileNotFoundError:
                continue  # Admission-only diagnostic sessions are not captures.
            for signature in _entries(captures, budget):
                if not _SIGNATURE.fullmatch(signature):
                    raise InspectionBlocked("CAPTURE_RECORD_INVALID")
                capture = _child_directory(captures, signature)
                counts["captureDirectories"] += 1
                try:
                    for filename, key in (("REPORT.json", "captureReports"),
                                          ("CAPTURE_STATUS.json", "captureStatusFiles")):
                        if _present_regular(capture, filename):
                            counts[key] += 1
                    if _present_regular(capture, "ACTIVE_CAPTURE_LOCK.json"):
                        counts["captureLockFiles"] += 1
                        lock = json.loads(_read(capture, "ACTIVE_CAPTURE_LOCK.json", 8192))
                        if (not isinstance(lock, dict) or type(lock.get("pid")) is not int
                                or lock["pid"] <= 0 or not isinstance(lock.get("bootId"), str)
                                or not _BOOT.fullmatch(lock["bootId"])
                                or not isinstance(lock.get("startTime"), str)
                                or not lock["startTime"].isdigit()):
                            raise InspectionBlocked("CAPTURE_LOCK_INVALID")
                        if lock["pid"] not in exclude and lock["bootId"] == boot:
                            try:
                                identity, state = _identity(proc, lock["pid"], boot)
                            except (FileNotFoundError, ProcessLookupError):
                                identity, state = None, None
                            if identity == {key: lock[key] for key in ("pid", "bootId", "startTime")} and state != "Z":
                                active.append({**identity, "role": "NATIVE_CAPTURE_LOCK"})
                finally:
                    os.close(capture)
        finally:
            if captures is not None:
                os.close(captures)
            os.close(session)
    return counts, active


def _shared_records(export, counts, budget):
    for name in _entries(export, budget):
        if name == "rtx-gpu-package-v1":
            legacy = _child_directory(export, name)
            captures = None
            try:
                try:
                    captures = _child_directory(legacy, "captures")
                except FileNotFoundError:
                    continue  # Original admission-only root is not capture evidence.
                for signature in _entries(captures, budget):
                    if not _SIGNATURE.fullmatch(signature):
                        raise InspectionBlocked("LEGACY_CAPTURE_RECORD_INVALID")
                    capture = _child_directory(captures, signature)
                    os.close(capture)
                    counts["legacyCaptureDirectories"] += 1
            finally:
                if captures is not None:
                    os.close(captures)
                os.close(legacy)
            continue
        if not _EXPORT.fullmatch(name):
            continue
        directory = _child_directory(export, name)
        try:
            for child in _entries(directory, budget):
                if child.startswith("capture-"):
                    if not _CAPTURE.fullmatch(child):
                        raise InspectionBlocked("SHARED_CAPTURE_RECORD_INVALID")
                    capture = _child_directory(directory, child)
                    os.close(capture)
                    counts["sharedCaptureDirectories"] += 1
        finally:
            os.close(directory)


def inspect(control_root=CONTROL_ROOT, private_base=PRIVATE_BASE, export_root=EXPORT_ROOT,
            exclude_pids=(), *, _proc_root=PROC_ROOT):
    """Return safe facts only; CLEAR is a snapshot, never permission to render.

    The manager owns its own journal. This function validates control-root
    access without interpreting the manager's current WAITING record. Any
    capture evidence or read uncertainty prevents a new unmanaged capture.
    Custom paths and proc roots are Python-only test seams, never CLI flags.
    """
    result = {"schema": "WORLD_ENGINE_EXISTING_CAPTURE_INSPECTION_V1", "status": "BLOCKED",
              "reason": "INSPECTION_UNAVAILABLE", "processes": [], "evidenceCounts": {},
              "testOnly": any(Path(value) != default for value, default in
                              ((control_root, CONTROL_ROOT), (private_base, PRIVATE_BASE),
                               (export_root, EXPORT_ROOT), (_proc_root, PROC_ROOT))),
              "gpuExecuted": False, "renderAllowed": False}
    descriptors = []
    budget = [0]
    try:
        if not isinstance(exclude_pids, (tuple, list)) or any(type(pid) is not int or pid <= 0 for pid in exclude_pids):
            raise InspectionBlocked("INVALID_EXCLUSIONS")
        for value in (private_base, export_root, _proc_root):
            descriptors.append(_directory(value))
        private, export, proc = descriptors
        control = _directory(control_root, optional=True)
        if control is not None:
            descriptors.append(control)
            _entries(control, budget)
        boot_path = _directory(Path(_proc_root) / "sys/kernel/random")
        try:
            boot = _read(boot_path, "boot_id", 128).decode("ascii").strip()
        finally:
            os.close(boot_path)
        if not _BOOT.fullmatch(boot):
            raise InspectionBlocked("PROCESS_IDENTITY_UNVERIFIED")
        processes = _processes(proc, boot, frozenset(exclude_pids), budget)
        counts, active = _capture_records(private, proc, boot, frozenset(exclude_pids), budget)
        _shared_records(export, counts, budget)
        for process in active:
            if not any((item["pid"], item["bootId"], item["startTime"]) ==
                       (process["pid"], process["bootId"], process["startTime"]) for item in processes):
                processes.append(process)
        result.update(processes=sorted(processes, key=lambda item: item["pid"]), evidenceCounts=counts)
        if processes or counts["heldCaptureGuards"]:
            result.update(status="RUNNING", reason="EXISTING_CAPTURE_ACTIVE")
        elif (counts["captureDirectories"] or counts["sharedCaptureDirectories"]
              or counts["legacyCaptureDirectories"]):
            result.update(status="EXISTING_RECORDS", reason="EXISTING_CAPTURE_REQUIRES_REVIEW")
        else:
            result.update(status="CLEAR", reason="NO_EXISTING_CAPTURE_EVIDENCE")
    except InspectionBlocked as error:
        result["reason"] = str(error)
    except (OSError, ValueError, TypeError, UnicodeError):
        pass  # Never echo OS paths, command arguments, JSON data or exception text.
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 1:
        print(json.dumps({"status": "BLOCKED", "reason": "ARGUMENTS_FORBIDDEN", "renderAllowed": False}))
        raise SystemExit(2)
    value = inspect()
    print(json.dumps(value, sort_keys=True))
    raise SystemExit(0 if value["status"] == "CLEAR" else 2)
