"""Focused regressions for evidenced receipt path, filtering, I/O and imports."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

C = Path(__file__).resolve().parents[2] / "codex-to-gcube-handoff-v1/controller"
sys.path.insert(0, str(C))
from safe_capture_export import export_failure, safe_code, read_json_safe
from capture_diagnostics_safe import export_after_cleanup
from lease_supervisor import supervise_owned_capture, parent_identity

results = {}
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    job = root / ("studio-" + "b" * 32)
    job.mkdir(mode=0o700)
    exports = root / "exports"
    exports.mkdir(mode=0o700)
    lease = root / "CAPTURE.guard"
    fd = os.open(lease, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    pid = os.fork()
    if pid == 0:
        code = "import json,sys;print(json.dumps({'status':'FAILED','code':'GCUBE_CAPTURE_RUNTIME_FAILED','stage':'RENDER_RUNTIME'}),flush=True);sys.exit(23)"
        try:
            supervise_owned_capture([sys.executable, "-I", "-S", "-c", code],
                lease_fd=fd, lease_path=str(lease), parent=parent_identity(os.getppid()),
                seconds=3, environment={}, output=job)
        except RuntimeError as exc:
            os._exit(0 if str(exc) == "GCUBE_CAPTURE_RUNTIME_FAILED" else 7)
        os._exit(8)
    # Bounded wait avoids recreating the old test's unrecorded EOF problem.
    import time, signal
    end = time.monotonic() + 6
    status = None
    while time.monotonic() < end:
        got, value = os.waitpid(pid, os.WNOHANG)
        if got:
            status = value
            break
        time.sleep(.02)
    if status is None:
        os.kill(pid, signal.SIGKILL)
        _, status = os.waitpid(pid, 0)
    os.close(fd)
    assert os.waitstatus_to_exitcode(status) == 0
    assert (job / "FIRST_CAPTURE_FAILURE.json").is_file()
    assert not (job / "capture/FIRST_CAPTURE_FAILURE.json").exists()
    deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    assert export_after_cleanup(job, exports, deadline)["status"] == "EXPORTED"
    target = exports / ("capture-diagnostic-" + job.name) / "CAPTURE_DIAGNOSTIC.json"
    data = json.loads(target.read_bytes())
    assert data["firstFailure"] == {"code":"GCUBE_CAPTURE_RUNTIME_FAILED", "stage":"RENDER_RUNTIME", "unrecognizedCode":False}
    assert data["supervisor"]["cleanupVerified"] is True
    assert (target.parent/"SHA256SUMS").read_text().startswith(hashlib.sha256(target.read_bytes()).hexdigest())
    results["real_supervisor_job_root_and_bounded_export"] = "PASS"
    assert safe_code("TOP_SECRET_ASCII_TOKEN_123") is None
    results["uppercase_secret_rejected"] = "PASS"
    original = target.read_bytes()
    assert export_after_cleanup(job, exports, deadline)["status"] == "EXPORT_FAILED"
    assert target.read_bytes() == original
    results["exclusive_destination_preserved"] = "PASS"
    linked = root/"linked"
    linked.symlink_to(job, target_is_directory=True)
    assert read_json_safe(linked/"FIRST_CAPTURE_FAILURE.json") is None
    fifo = job/"pipe.json"
    os.mkfifo(fifo, mode=0o600)
    assert read_json_safe(fifo) is None
    results["symlink_ancestor_and_fifo_rejected"] = "PASS"
    receipt_dir = job/"capture"
    receipt_dir.mkdir(mode=0o700)
    receipt = receipt_dir/"CAPTURE_RECEIPT.json"
    receipt.write_text(json.dumps({"failure":{"code":"browserType.launch: SECRET_VALUE_NEVER_EXPORT"},"renderedFrames":0}))
    receipt.chmod(0o600)
    summary = export_failure(job, exports/"classification")
    body = (exports/"classification/CAPTURE_DIAGNOSTIC.json").read_bytes()
    assert b"SECRET_VALUE" not in body
    assert summary["diagnostic"]["capture"]["messageCategory"] == "BROWSER_LAUNCH"
    results["receipt_message_category_no_raw_message"] = "PASS"
print(json.dumps(results, sort_keys=True))
