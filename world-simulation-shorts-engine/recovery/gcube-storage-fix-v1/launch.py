#!/usr/bin/env python3
"""Use unchanged RTX APIs with private local work and verified shared exports."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
RUNTIME_HELPERS = Path("/opt/world-engine-startup-diagnostics")
HELPERS = RUNTIME_HELPERS if (RUNTIME_HELPERS / "startup.py").is_file() else HERE.parent / "gcube-diagnostic-image-v1"
sys.path.insert(0, str(HELPERS))
import startup
import records
from service import serve_diagnostic
import storage

for _module in (startup, records):
    if Path(_module.__file__).resolve().parent != HELPERS.resolve():
        raise ImportError("STARTUP_HELPER_ORIGIN_INVALID")


def _emit_facts(status, facts, *, test_only):
    event = {"schema": "WORLD_ENGINE_STORAGE_FACTS_V1", "status": status,
             "timestamp": datetime.now(timezone.utc).isoformat(),
             "safeFacts": storage.safe_facts(facts), "testOnly": test_only,
             "gpuRenderingVerified": False, "renderAllowed": False}
    body = json.dumps(event, sort_keys=True, allow_nan=False)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.write(body + "\n")
            stream.flush()
        except (OSError, ValueError, AttributeError):
            pass


def _emit_phase(stage, *, test_only):
    # A completed CPU phase is never evidence of GPU availability.
    event = {"schema": "WORLD_ENGINE_STARTUP_PHASE_V1", "stage": stage, "status": "PASS",
             "testOnly": test_only, "gpuRenderingVerified": False, "renderAllowed": False}
    print(json.dumps(event, sort_keys=True), flush=True)


def _emit_export_location(session, report, *, test_only):
    """Print generated basenames and checked hashes, never arbitrary report text."""
    name = getattr(session, "export_name", None)
    if (not isinstance(name, str) or not re.fullmatch(r"world-engine-export-[0-9a-f]{24}", name)
            or not isinstance(report, dict) or report.get("status") != "EXPORTED"
            or report.get("mountedViewReadbackVerified") is not True
            or report.get("remotePersistenceVerified") is not False
            or report.get("externalDownloadVerified") is not False):
        return False

    def file_record(value, *, safe_log=False):
        if not isinstance(value, dict):
            return None
        filename, digest, size = value.get("file"), value.get("sha256"), value.get("bytes")
        pattern = r"startup-safe-[0-9a-f]{24}\.json" if safe_log else r"(?:SHA256SUMS|[A-Za-z0-9][A-Za-z0-9_.-]{0,174}\.(?:mp4|png))"
        if (not isinstance(filename, str) or not re.fullmatch(pattern, filename)
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or type(size) is not int or not 1 <= size <= 4 * 1024 ** 3):
            return None
        return {"file": filename, "sha256": digest, "bytes": size}

    payload = {"schema": "WORLD_ENGINE_EXPORT_LOCATION_V1", "exportDirectory": name,
               "testOnly": test_only, "mountedViewReadbackVerified": True,
               "remotePersistenceVerified": False, "externalDownloadVerified": False}
    if report.get("schema") == "WORLD_ENGINE_SAFE_RECORD_EXPORT_V1":
        checked = file_record(report, safe_log=True)
        if checked is None or report.get("exportName") != name:
            return False
        payload["files"] = [checked]
    elif report.get("schema") == "WORLD_ENGINE_PUBLIC_EXPORT_V1":
        results = report.get("results")
        if not isinstance(results, list) or not 1 <= len(results) <= 16:
            return False
        captures = []
        for result in results:
            if (not isinstance(result, dict) or not isinstance(result.get("directory"), str)
                    or not re.fullmatch(r"capture-[0-9a-f]{12}-[0-9a-f]{24}", result["directory"])
                    or result.get("completionReceipt") != "EXPORT_COMPLETE.json"
                    or not isinstance(result.get("files"), list) or not 2 <= len(result["files"]) <= 64):
                return False
            files = [file_record(value) for value in result["files"]]
            if any(value is None for value in files):
                return False
            captures.append({"directory": result["directory"], "publicDirectory": "public-review",
                             "completionReceipt": "EXPORT_COMPLETE.json", "files": files})
        payload["captures"] = captures
    else:
        return False
    print(json.dumps(payload, sort_keys=True, allow_nan=False), flush=True)
    return True


def _storage_failure(error, *, mode, test_only):
    code = getattr(error, "code", "STORAGE_UNAVAILABLE")
    if code not in {"STORAGE_VALIDATION_FAILED", "STORAGE_UNAVAILABLE"}:
        code = "STORAGE_UNAVAILABLE"
    facts = storage.safe_facts(getattr(error, "facts", {}))
    _emit_facts("BLOCKED", facts, test_only=test_only)
    errno_name = facts.get("errnoName")
    number = getattr(errno, errno_name, None) if isinstance(errno_name, str) else None
    return records.make_record("STORAGE", code, 1, mode=mode, errno_value=number,
                               exception_type=type(error).__name__, test_only=test_only)


@contextmanager
def _observe_native_prepare(bootstrap, private_root, stage):
    """Only observe original calls; selected storage has no fixed mount prefix."""
    previous = sys.getprofile()
    directory_code = getattr(getattr(bootstrap, "_directory", None), "__code__", None)
    private_root = Path(private_root)

    def observe(frame, event, argument):
        try:
            if event == "call" and directory_code is not None and frame.f_code is directory_code:
                stage.name = "STORAGE" if Path(frame.f_locals.get("path", "")) == private_root else "RUNTIME_DIRECTORY"
            elif event == "return" and directory_code is not None and frame.f_code is directory_code and argument is not None:
                stage.name = "BOOTSTRAP"
            elif event == "c_call" and getattr(argument, "__name__", "") in {"setgroups", "setgid", "setuid"}:
                stage.name = "UID_GID"
        except Exception:
            pass

    try:
        sys.setprofile(observe)
        yield
    finally:
        sys.setprofile(previous)


class StorageOperations:
    """Composition through existing keyword APIs, with no original replacements."""
    def __init__(self, native, session, *, mode, test_only):
        self.native, self.session = native, session
        self.mode, self.test_only = mode, test_only

    def account(self):
        return self.native.account()

    def bootstrap(self):
        original = self.native.bootstrap()

        def prepare(account):
            stage = startup.Stage()
            try:
                with _observe_native_prepare(original, self.session.private_root, stage):
                    original.prepare_environment(account, storage=self.session.private_root)
            except Exception as error:
                # Preserve the original error's safe stage/errno; the outer
                # unchanged checker cannot know this new selected storage path.
                record = startup._failure(stage.name, error, mode=self.mode, test_only=self.test_only)
                failure = startup.StartupFailure(record["stage"], record["errorCode"], record["exitCode"])
                failure.errno = getattr(error, "errno", None)
                raise failure from None
            try:
                facts = self.session.preflight()
                _emit_facts("PASS", facts, test_only=self.test_only)
            except storage.StorageError as error:
                record = _storage_failure(error, mode=self.mode, test_only=self.test_only)
                failure = startup.StartupFailure("STORAGE", record["errorCode"], 1)
                failure.errno = record.get("safeDiagnostics", {}).get("errno")
                raise failure from None

        return SimpleNamespace(_directory=getattr(original, "_directory", None), prepare_environment=prepare)

    def source(self):
        result = self.native.source()
        _emit_phase("SOURCE_INTEGRITY", test_only=self.test_only)
        return result

    def dependencies(self):
        result = self.native.dependencies()
        if result.get("status") == "PASS":
            _emit_phase("DEPENDENCY", test_only=self.test_only)
        return result

    def gpu(self):
        original = self.native.gpu()

        def config(**options):
            return original.LauncherConfig(**options, storage_root=self.session.private_root)

        # These are the actual unchanged admission, health, and renderer methods.
        return SimpleNamespace(LauncherConfig=config, admit_gpu=original.admit_gpu,
                               render_65422=original.render_65422, serve_health=original.serve_health,
                               capture_guard=original.capture_guard)


def _publish(record, session, *, mode, test_only):
    safe = records.safe_record(record)
    records.emit_record(safe)
    roots = [] if session is None else [session.private_root / "startup-diagnostics"]
    saved = records.persist_record(safe, roots=roots)
    export_ok = False
    if session is not None:
        try:
            report = session.export_safe_record(safe)
            _emit_export_location(session, report, test_only=test_only)
            export_ok = True
        except storage.StorageError as error:
            failure = _storage_failure(error, mode=mode, test_only=test_only)
            records.emit_record(failure)
            records.persist_record(failure, roots=roots)
    return saved.get("persisted") is True and export_ok


def _check_storage(operations):
    # Explicit CPU storage inspection has no route to admit_gpu or a server.
    stage = "UID_GID"
    try:
        operations.bootstrap().prepare_environment(operations.account())
        stage = "SOURCE_INTEGRITY"
        operations.source()
        stage = "DEPENDENCY"
        result = operations.dependencies()
        if result.get("status") != "PASS":
            raise startup.StartupFailure("DEPENDENCY", "CPU_DEPENDENCY_CHECK_FAILED")
    except startup.StartupFailure:
        raise
    except Exception as error:
        record = startup._failure(stage, error, mode=operations.mode, test_only=operations.test_only)
        failure = startup.StartupFailure(record["stage"], record["errorCode"], record["exitCode"])
        failure.errno = getattr(error, "errno", None)
        raise failure from None
    return {"schema": "WORLD_ENGINE_STORAGE_ONLY_CHECK_V1", "status": "STORAGE_ONLY_VERIFIED",
            "testOnly": operations.test_only, "gpuRenderingVerified": False, "renderAllowed": False}


def _export_render_results(session, *, test_only=False):
    report = session.export_results()
    if (not isinstance(report, dict) or report.get("status") != "EXPORTED"
            or type(report.get("captures")) is not int or report["captures"] < 1
            or type(report.get("files")) is not int or report["files"] < 2
            or report.get("mountedViewReadbackVerified") is not True
            or report.get("privateDataAllowed") is not False
            or report.get("remotePersistenceVerified") is not False
            or report.get("externalDownloadVerified") is not False):
        raise storage.StorageError("STORAGE_VALIDATION_FAILED", {"stage": "EXPORT", "reason": "PUBLIC_SOURCE_INVALID"})
    _emit_facts("PASS", report, test_only=test_only)
    _emit_export_location(session, report, test_only=test_only)
    return report


def _render_and_export(gpu, admission, config, session):
    # Fresh per-start workspaces must not admit concurrent captures on one GPU.
    # Reuse the original lock implementation on their common private local base;
    # the renderer's original per-session lock remains in place inside it.
    with gpu.capture_guard(storage.PRIVATE_BASE):
        code = gpu.render_65422(admission, config)
        if code != 0:
            return code
        _export_render_results(session)
        return 0


def main(argv=None, *, operations=None, session_factory=None, environ=None,
         worker=None, privilege_drop=None, diagnostic_service=None):
    # Python test seams never grant production execution or hardware PASS.
    test_only = any(value is not None for value in
                    (operations, session_factory, environ, worker, privilege_drop, diagnostic_service))
    native = startup.NativeOperations() if operations is None else operations
    environment = os.environ if environ is None else environ
    session, mode = None, "normal"
    parser = startup.SafeArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--check-storage", action="store_true")
    actions.add_argument("--render-65422", action="store_true")
    parser.add_argument("--vram-budget-gib", type=float, default=8.0)
    parser.add_argument("--port", type=int, default=8000)
    try:
        args = parser.parse_args(argv)
        mode = environment.get("WORLD_ENGINE_STARTUP_MODE", "normal")
        if mode not in {"normal", "diagnostic"}:
            mode = "normal"
            raise startup.StartupFailure("CONFIGURATION", "INVALID_STARTUP_MODE", 2)
        if mode == "diagnostic" and (args.render_65422 or args.check_storage):
            raise startup.StartupFailure("CONFIGURATION", "DIAGNOSTIC_RENDER_FORBIDDEN", 2)
        if mode == "diagnostic":
            ttl, port = startup._diagnostic_options(args, environment)
        try:
            account = native.account()
            create = storage.StorageSession.create if session_factory is None else session_factory
            session = create(account)
            selected = StorageOperations(native, session, mode=mode, test_only=test_only)
            if mode == "diagnostic":
                run = startup._diagnostic_worker if worker is None else worker
                record = run(selected, args, test_only=test_only)
            elif args.check_storage:
                result = _check_storage(selected)
                print(json.dumps(result, sort_keys=True), flush=True)
                return 0
            else:
                checked, record = startup._checks(selected, args, mode=mode, test_only=test_only)
        except storage.StorageError as error:
            record = _storage_failure(error, mode=mode, test_only=test_only)
        if mode == "diagnostic":
            try:
                drop = startup._drop_diagnostic_privileges if privilege_drop is None else privilege_drop
                drop(native.account())
            except Exception as error:
                secondary = startup._failure("UID_GID", error, mode=mode, test_only=test_only)
                if (isinstance(record, dict) and type(record.get("exitCode")) is int
                        and record["exitCode"] != 0):
                    _publish(record, session, mode=mode, test_only=test_only)
                _publish(secondary, session, mode=mode, test_only=test_only)
                return secondary["exitCode"]
            _publish(record, session, mode=mode, test_only=test_only)
            serve = serve_diagnostic if diagnostic_service is None else diagnostic_service
            return serve(record, port=port, max_seconds=ttl)
        if record is not None:
            _publish(record, session, mode=mode, test_only=test_only)
            return record["exitCode"]
        gpu, config, admission = checked
        if test_only or admission.test_only:
            raise startup.StartupFailure("UNEXPECTED", "TEST_SEAM_PRODUCTION_DISPATCH_BLOCKED", 2)
        if args.check:
            print(json.dumps(admission.safe_report, sort_keys=True, allow_nan=False), flush=True)
            return 0
        try:
            if args.render_65422:
                return _render_and_export(gpu, admission, config, session)
            gpu.serve_health(admission, config)
            return 0
        except storage.StorageError as error:
            failure = _storage_failure(error, mode=mode, test_only=test_only)
            _publish(failure, session, mode=mode, test_only=test_only)
            return 1
        except Exception as error:
            failure = startup._failure("NVIDIA", error, mode=mode, test_only=test_only)
            _publish(failure, session, mode=mode, test_only=test_only)
            return failure["exitCode"]
    except Exception as error:
        failure = startup._failure("UNEXPECTED", error, mode=mode, test_only=test_only)
        _publish(failure, session, mode=mode, test_only=test_only)
        return failure["exitCode"]


if __name__ == "__main__":
    raise SystemExit(main())
