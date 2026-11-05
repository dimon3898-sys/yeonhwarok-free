"""New CPU contract: active checkpoint survives private job loss; no GPU/render.

This does not rerun old recorder, browser, encoding, or storage test suites.
The external-looking directory is a LOCAL fixture, not a mounted/cloud PASS.
"""
import ast
from contextlib import contextmanager
import hashlib
import errno
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
CONTROLLER = HERE.parent.parent / "codex-to-gcube-handoff-v1" / "controller"
sys.path.insert(0, str(CONTROLLER))
import safe_capture_export as exporter
import capture_diagnostics_safe as diagnostics


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def write(path, value):
    with path.open("wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(canonical(value))


def make_job(base, letter):
    job = base / "private" / "handoff-gpu-jobs" / ("studio-" + letter * 32)
    capture = job / "capture"
    capture.mkdir(parents=True, mode=0o700)
    job.chmod(0o700)
    value = {"schema": "WORLD_ENGINE_CAPTURE_OPERATIONS_V1", "runId": job.name,
        "durationSeconds": 10, "totalFrames": 300, "operationId": "DRAW",
        "operationPhase": "START", "frameIndex": 1, "lastCompletedOperation": "PNG",
        "renderedFrames": 1, "sequence": 3, "observedAtUnixMs": 1793830000000,
        "firstFailure": None, "cleanupFailure": None, "nativeProofCompleted": True,
        "evidenceStatus": "LOCAL_ATOMIC_CHECKPOINT", "storageError": None,
        "token": "SYNTHETIC_SECRET_MUST_NOT_LEAVE", "privatePath": "/private/synthetic-only"}
    write(capture / "CAPTURE_OPERATION_CHECKPOINT.json", value)
    return job, value


def expect_error(callback, kind=Exception):
    try:
        callback()
    except kind:
        return
    raise AssertionError("Expected rejection")


def await_child(mirror):
    until = time.monotonic() + 2
    while mirror.process is not None and time.monotonic() < until:
        mirror.tick()
        time.sleep(.005)
    assert mirror.process is None, mirror.status


def inspect_envelope(file):
    wire = file.read_bytes()
    value = json.loads(wire)
    assert value["schema"] == "WORLD_ENGINE_ACTIVE_CAPTURE_CHECKPOINT_V1"
    assert digest(canonical(value["snapshot"])) == value["sha256"]
    assert value["snapshot"]["cleanupStatus"] == "UNCONFIRMED_NOT_COMPLETION_OR_EXPORT_AUTHORIZATION"
    assert value["snapshot"]["renderRecoveryPass"] is False
    assert b"SYNTHETIC_SECRET" not in wire and b"/private/synthetic-only" not in wire
    assert len(wire) < 16384
    return value, wire


def run(output):
    output.mkdir(mode=0o700)
    result = {"schema": "WORLD_ENGINE_ACTIVE_CHECKPOINT_FOCUS_V1", "status": "RUNNING",
        "startedAtUnix": time.time(), "gpuExecuted": False, "browserLaunched": False,
        "renderExecuted": False, "oldPassSuitesRerun": 0, "cases": [],
        "limits": ["Local filesystem fixture, not gCube mount or Dropbox recovery",
            "No actual capture stall reproduced; private-folder removal models container file loss",
            "Checkpoint mirror is sampled at one-second cadence, not every-operation durable acknowledgement",
            "Full diagnostics still require verified cleanup; active snapshot never asserts completion"],
        "sourceHashes": {name: digest((CONTROLLER / name).read_bytes()) for name in
            ("safe_capture_export.py", "capture_diagnostics_safe.py", "nvidia_worker.py")}}
    try:
        with tempfile.TemporaryDirectory(prefix="world-engine-active-checkpoint-") as temporary:
            base = Path(temporary)
            exports = base / "exports"
            exports.mkdir(mode=0o700)
            job, value = make_job(base, "a")
            mirror = diagnostics.ActiveCheckpointMirror(job, exports)
            calls = []
            real_popen = subprocess.Popen
            def actual_child(command, **options):
                assert options["env"] == {} and options["close_fds"] is True
                assert options["stdin"] == subprocess.DEVNULL
                assert options["stdout"] == subprocess.DEVNULL and options["stderr"] == subprocess.DEVNULL
                assert command[-3:] == ["--active-checkpoint", "--seconds", "1"]
                calls.append(1)
                return real_popen(command, **options)
            with patch.object(diagnostics.subprocess, "Popen", side_effect=actual_child):
                mirror.tick(); await_child(mirror)
                assert mirror.status == "ACTIVE_CHECKPOINT_MOUNTED_WRITE_CONFIRMED", mirror.status
                target = exports / ("capture-checkpoint-" + job.name) / "CAPTURE_CHECKPOINT.json"
                first, first_wire = inspect_envelope(target)
                assert first["snapshot"]["operations"]["frameIndex"] == 1
                assert first["snapshot"]["operations"]["operationPhase"] == "START"
                assert first["snapshot"]["operations"]["firstFailure"] is None
                # New operation, same completed frame count: independent of progress.
                value.update(operationId="READBACK", sequence=4)
                write(job / "capture" / "CAPTURE_OPERATION_CHECKPOINT.json", value)
                mirror.last_attempt -= 1.1  # Advance only the test's cadence gate.
                mirror.tick(); await_child(mirror)
                second, wire = inspect_envelope(target)
                assert second["snapshot"]["operations"]["sequence"] == 4
                assert second["snapshot"]["operations"]["operationId"] == "READBACK"
                assert second["snapshot"]["operations"]["renderedFrames"] == 1
                assert first_wire != wire
                mirror.last_attempt -= 1.1
                mirror.tick()
                assert len(calls) == 2 and mirror.process is None
            mirror.close()
            # This new active endpoint must not open the existing full export gate.
            expect_error(lambda: exporter.export_failure(job, exports / ("capture-diagnostic-" + job.name)), ValueError)
            shutil.rmtree(job)
            retained, retained_wire = inspect_envelope(target)
            assert retained == second and retained_wire == wire
            (output / "ACTIVE_CHECKPOINT.json").write_bytes(wire)
            result["cases"].append({"case": "NO_EXCEPTION_ACTIVE_FRAME_LOCAL_RETENTION", "status": "PASS",
                "freshSequenceWrites": 2, "sameSequenceExtraWrites": 0,
                "frameIndex": 1, "renderedFrames": 1, "operation": "READBACK/START",
                "firstFailure": None, "retainedAfterPrivateJobDeletion": True,
                "envelopeBytes": len(wire), "fileSHA256": digest(wire), "snapshotSHA256": retained["sha256"],
                "fullCleanupGate": "STILL_REJECTS_WITHOUT_CLEANUP_RECEIPT"})

            # New target handling rejects a symlink without touching its target.
            symlink_job, _ = make_job(base, "b")
            foreign = base / "untouched"
            foreign.mkdir(mode=0o700)
            (foreign / "sentinel").write_text("preserve")
            (exports / ("capture-checkpoint-" + symlink_job.name)).symlink_to(foreign, target_is_directory=True)
            expect_error(lambda: exporter.export_active_checkpoint(symlink_job,
                exports / ("capture-checkpoint-" + symlink_job.name)), OSError)
            assert sorted(p.name for p in foreign.iterdir()) == ["sentinel"]
            assert (foreign / "sentinel").read_text() == "preserve"
            result["cases"].append({"case": "ACTIVE_TARGET_SYMLINK", "status": "REJECTED_TARGET_UNCHANGED"})

            large_job, large_value = make_job(base, "c")
            large_value["unexpected"] = "x" * (exporter.LIMIT + 1)
            write(large_job / "capture" / "CAPTURE_OPERATION_CHECKPOINT.json", large_value)
            expect_error(lambda: exporter.export_active_checkpoint(large_job,
                exports / ("capture-checkpoint-" + large_job.name)), ValueError)
            assert not (exports / ("capture-checkpoint-" + large_job.name)).exists()
            result["cases"].append({"case": "OVERSIZE_PRIVATE_CHECKPOINT", "status": "REJECTED_NO_EXPORT"})

            # Real CPU child models blocked mounted I/O; no capture process exists.
            hang_job, _ = make_job(base, "d")
            hanging = diagnostics.ActiveCheckpointMirror(hang_job, exports)
            blocked_calls = []
            def blocked_child(command, **options):
                assert options["env"] == {} and options["close_fds"] is True
                process = real_popen([sys.executable, "-I", "-S", "-c", "import time;time.sleep(60)"], **options)
                blocked_calls.append(process)
                return process
            with patch.object(diagnostics.subprocess, "Popen", side_effect=blocked_child):
                hanging.tick()
                time.sleep(1.02)
                before = time.monotonic()
                hanging.tick()
                tick_seconds = time.monotonic() - before
                assert tick_seconds < .5 and hanging.status == "ACTIVE_CHECKPOINT_TIMEOUT"
                hanging.close()
                assert blocked_calls[0].poll() is not None
                hanging.last_attempt -= 2
                hanging.tick()
                assert len(blocked_calls) == 1 and hanging.disabled
            result["cases"].append({"case": "BLOCKED_STORAGE_CHILD", "status": "TIMEOUT_KILLED_AND_REAPED",
                "tickSeconds": tick_seconds, "newChildStarts": 1, "automaticRetries": 0,
                "renderErrorCodeTouched": False})

            # Existing export adapter explicitly permits non-POSIX shared modes
            # and unsupported fsync; private evidence rules must stay strict.
            shared_job, shared_value = make_job(base, "e")
            shared_target = exports / ("capture-checkpoint-" + shared_job.name)
            exporter.export_active_checkpoint(shared_job, shared_target)
            shared_target.chmod(0o755)
            shared_file = shared_target / "CAPTURE_CHECKPOINT.json"
            shared_file.chmod(0o644)
            shared_value.update(operationId="ENCODER_DRAIN", sequence=4)
            write(shared_job / "capture" / "CAPTURE_OPERATION_CHECKPOINT.json", shared_value)
            storage = exporter.active_shared_storage()
            with patch.object(storage.os, "fsync", side_effect=OSError(errno.EINVAL, "mock shared fsync unsupported")):
                saved = exporter.export_active_checkpoint(shared_job, shared_target)
            assert saved["status"] == "EXPORTED"
            shared_envelope, shared_wire = inspect_envelope(shared_file)
            assert shared_envelope["snapshot"]["operations"]["operationId"] == "ENCODER_DRAIN"
            # Actual I/O errors still fail, leaving the previous whole envelope.
            shared_value.update(sequence=5)
            write(shared_job / "capture" / "CAPTURE_OPERATION_CHECKPOINT.json", shared_value)
            with patch.object(storage.os, "fsync", side_effect=OSError(errno.EIO, "mock I/O failure")):
                expect_error(lambda: exporter.export_active_checkpoint(shared_job, shared_target), OSError)
            assert shared_file.read_bytes() == shared_wire
            shared_job.chmod(0o755)
            expect_error(lambda: exporter.export_active_checkpoint(shared_job, shared_target), ValueError)
            result["cases"].append({"case": "EXISTING_SHARED_ADAPTER_COMPATIBILITY", "status": "PASS",
                "public0755Directory0644Readback": True, "unsupportedFsyncToleratedWithoutRemoteDurabilityClaim": True,
                "realIOErrorPreservesLastWholeEnvelope": True, "private0700GateRetained": True,
                "actualFuseMount": False})

            tree = ast.parse((CONTROLLER / "nvidia_worker.py").read_text())
            loops = [node for node in ast.walk(tree) if isinstance(node, ast.While)
                     and ast.unparse(node.test) == "supervisor.poll() is None"]
            assert len(loops) == 1
            assert any(isinstance(node, ast.Assign) and ast.unparse(node.value) == "checkpoint_mirror.tick()"
                       for node in loops[0].body)
            result["cases"].append({"case": "WORKER_HOOK_PLACEMENT", "status": "IN_LOOP_OUTSIDE_PROGRESS_CHANGE_BRANCH"})
        result["status"] = "CPU_ACTIVE_CHECKPOINT_CONTRACT_PASS"
    except Exception as error:
        result["status"] = "FAIL"
        result["failure"] = {"type": type(error).__name__, "message": str(error)[:1000]}
        raise
    finally:
        result["finishedAtUnix"] = time.time()
        (output / "RESULT.json").write_bytes(canonical(result))
        files = sorted(p for p in output.iterdir() if p.is_file())
        (output / "SHA256SUMS").write_text("".join(digest(p.read_bytes()) + "  " + p.name + "\n" for p in files))
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -B active_checkpoint_focus.py fresh-output")
    run(Path(sys.argv[1]).resolve())
