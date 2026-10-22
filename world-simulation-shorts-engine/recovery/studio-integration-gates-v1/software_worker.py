"""Detached software-only exact-source worker; never invokes a GPU launcher."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from process_guard import DescendantGuard

HERE = Path(__file__).resolve().parent


def atomic(path, value):
    temporary = path.with_name(path.name + ".new")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(value, output, ensure_ascii=False, allow_nan=False, indent=2)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def run(args):
    job = args.job_root
    if job.is_symlink() or job.stat().st_uid != os.getuid() or job.stat().st_mode & 0o077:
        raise RuntimeError("STUDIO_REFERENCE_PRIVATE_STATE_REQUIRED")
    for _ in range(100):
        if (job / "launch.json").is_file():
            break
        time.sleep(.05)
    else:
        raise RuntimeError("STUDIO_REFERENCE_LAUNCH_RECEIPT_MISSING")
    state = json.loads((job / "state.json").read_bytes())
    started = time.monotonic()
    try:
        raw = (job / "receipt.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != args.receipt_sha256:
            raise RuntimeError("STUDIO_REFERENCE_RECEIPT_CHANGED")
        receipt = json.loads(raw)
        if receipt["softwareOnly"] is not True or receipt["approvedFrameRange"] != [0, 150] or receipt["maxWallSeconds"] != 900:
            raise RuntimeError("STUDIO_REFERENCE_SCOPE_INVALID")
        remaining = (datetime.fromisoformat(receipt["expiresAt"]) - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 5:
            raise RuntimeError("STUDIO_REFERENCE_APPROVAL_EXPIRED")
        output = args.export_root / receipt["jobId"]
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        cache = job / "fresh-capture"
        state.update(state="RUNNING", phase="FRESH_DRAW_READPIXELS")
        atomic(job / "state.json", state)
        command = ["node", str(HERE / "reference_capture.mjs"),
            "--receipt=" + str(job / "receipt.json"), "--receipt-sha256=" + args.receipt_sha256,
            "--output-root=" + str(output), "--cache-root=" + str(cache),
            "--capsule=" + str(args.capsule_root), "--original-report=" + str(args.original_report)]
        # Session belongs to this detached worker, not the browser or terminal.
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=True)
        with DescendantGuard(child.pid) as guard:
            try:
                returncode = child.wait(timeout=min(895, remaining - 5))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                raise
            finally:
                # Playwright detaches Chromium into its own session. Bound
                # pidfds additionally clean up observed owned descendants.
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                cleanup = guard.cleanup()
                atomic(job / "cleanup.json", cleanup)
            if cleanup["remaining"] or cleanup["errors"] or cleanup["observationError"]:
                raise RuntimeError("STUDIO_REFERENCE_CLEANUP_UNVERIFIED")
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)
        videos = list((output / "public-review").glob("*.mp4"))
        if len(videos) != 1:
            raise RuntimeError("STUDIO_REFERENCE_OUTPUT_MISSING")
        video = videos[0]
        # Driver already performed actual full decode. Bind completion to that
        # report and exact bytes, without spending a second decode budget.
        report = json.loads((output / "proof/CAPTURE_REPORT.json").read_bytes())
        video_sha = hashlib.sha256(video.read_bytes()).hexdigest()
        if (report["fullDecode"] != "PASS" or report["newlyRenderedFrames"] != 150
                or report["rawRgbaEqualFrames"] != 150 or report["pngEqualFrames"] != 150
                or report["video"]["sha256"] != video_sha):
            raise RuntimeError("STUDIO_REFERENCE_CAPTURE_NOT_EQUAL")
        result = {"jobId": receipt["jobId"], "state": "COMPLETED", "softwareOnly": True,
            "gpuRenderingVerified": False, "userApproved": False,
            "downloads": [{"name": video.name, "sha256": video_sha,
                           "bytes": video.stat().st_size, "path": str(video)}]}
        atomic(job / "result.json", result)
        state.update(state="COMPLETED", phase="SOFTWARE_REFERENCE_COMPLETE", processedFrames=150,
                     completedScenes=1, elapsedSeconds=round(time.monotonic() - started, 3))
    except Exception as error:
        # Child stderr remains private. No arbitrary exception text is exported.
        state.update(state="FAILED", phase="SOFTWARE_REFERENCE_FAILED", errorCode="STUDIO_REFERENCE_WORKER_FAILED",
                     elapsedSeconds=round(time.monotonic() - started, 3))
        atomic(job / "failure.json", {"kind": type(error).__name__, "childExitCode": getattr(error, "returncode", None)})
        raise
    finally:
        atomic(job / "state.json", state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("job-root", "export-root", "capsule-root", "original-report"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--receipt-sha256", required=True)
    run(parser.parse_args())
