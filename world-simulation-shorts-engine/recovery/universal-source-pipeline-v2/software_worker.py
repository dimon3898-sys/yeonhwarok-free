"""Detached, source-bound software worker; never creates GPU authorization."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_source_preserved_process_guard", HERE.parent / "studio-integration-gates-v1/process_guard.py")
guard_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard_module
spec.loader.exec_module(guard_module)
DescendantGuard = guard_module.DescendantGuard


def atomic(path, value):
    temporary = path.with_name(path.name + ".new")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(value, output, ensure_ascii=False, allow_nan=False, indent=2)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def validate_package(raw, expected_sha):
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise RuntimeError("STUDIO_SOURCE_PACKAGE_HASH_MISMATCH")
    package = json.loads(raw)
    pipeline, receipt = package.get("sourcePipeline", {}), package.get("executionReceipt", {})
    total = pipeline.get("totalFrames")
    start_frame = pipeline.get("startFrame")
    frames = pipeline.get("runtimePayload", {}).get("frames")
    historical = pipeline.get("mode") == "PRODUCTION" and pipeline.get("scope") == "G3_SOURCE_QUALIFIED_HISTORICAL"
    allowed = pipeline.get("mode") == "SYNTHETIC_TEST" or historical
    if (package.get("schema") != "WORLD_ENGINE_UNIVERSAL_SOURCE_SCENE_V2"
            or not allowed or pipeline.get("ready") is not True
            or type(total) is not int or not 2 <= total <= 240
            or type(start_frame) is not int or start_frame < 0
            or receipt.get("schema") != "WORLD_ENGINE_STUDIO_SOURCE_EXECUTION_V2"
            or receipt.get("softwareOnly") is not True or receipt.get("historicalRenderAllowed") is not historical
            or receipt.get("sourceScope") != pipeline.get("scope")
            or receipt.get("requestSHA256") != pipeline.get("requestSHA256")
            or not re.fullmatch(r"[a-f0-9]{64}", str(receipt.get("requestSHA256")))
            or receipt.get("frameRange") != [start_frame, start_frame + total] or receipt.get("maxWallSeconds") != 900
            or not isinstance(receipt.get("jobId"), str)
            or not re.fullmatch(r"studio-[a-f0-9]{32}", receipt["jobId"])
            or not re.fullmatch(r"[a-f0-9]{64}", str(receipt.get("sourceIndexSHA256")))):
        raise RuntimeError("STUDIO_SOURCE_EXECUTION_SCOPE_INVALID")
    if (not isinstance(frames, list) or len(frames) != total
            or [frame.get("frame") if isinstance(frame, dict) else None for frame in frames] != list(range(start_frame, start_frame + total))):
        raise RuntimeError("STUDIO_SOURCE_FRAME_PACKAGE_INCOMPLETE")
    expiry = datetime.fromisoformat(receipt["expiresAt"].replace("Z", "+00:00"))
    if expiry.tzinfo is None or (expiry - datetime.now(timezone.utc)).total_seconds() <= 5:
        raise RuntimeError("STUDIO_SOURCE_APPROVAL_EXPIRED")
    return package


def validate_capture(report, video, total):
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    if (report.get("schema") != "WORLD_ENGINE_SOURCE_SCENE_CAPTURE_V2"
            or report.get("status") != "SOFTWARE_PREVIEW_COMPLETE"
            or report.get("totalFrames") != total or report.get("newlyRenderedFrames") != total
            or report.get("fullDecode") != "PASS" or report.get("video", {}).get("sha256") != digest
            or report.get("gpuRenderingVerified", False) is not False
            or report.get("userApproved", False) is not False):
        raise RuntimeError("STUDIO_SOURCE_CAPTURE_INCOMPLETE_OR_CHANGED")
    return digest


def run(args):
    job = args.job_root
    if (not job.is_dir() or job.is_symlink() or job.stat().st_uid != os.getuid()
            or job.stat().st_mode & 0o077):
        raise RuntimeError("STUDIO_SOURCE_PRIVATE_STATE_REQUIRED")
    for _ in range(100):
        if (job / "launch.json").is_file():
            break
        time.sleep(.05)
    else:
        raise RuntimeError("STUDIO_SOURCE_LAUNCH_RECEIPT_MISSING")
    state = json.loads((job / "state.json").read_bytes())
    started = time.monotonic()
    stage = "PRIVATE_SOURCE_PACKAGE_VERIFY"
    try:
        plan_file = job / "compiledpackage.json"
        package = validate_package(plan_file.read_bytes(), args.plan_sha256)
        receipt, total = package["executionReceipt"], package["sourcePipeline"]["totalFrames"]
        if receipt["jobId"] != job.name:
            raise RuntimeError("STUDIO_SOURCE_JOB_ID_MISMATCH")
        output, cache = args.export_root / job.name, job / "fresh-capture"
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        state.update(state="RUNNING", phase="SOURCE_NATIVE_DRAW_READPIXELS")
        atomic(job / "state.json", state)
        remaining = (datetime.fromisoformat(receipt["expiresAt"].replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds()
        command = ["node", str(HERE / "capture_source.mjs"), "--plan=" + str(plan_file),
            "--output-root=" + str(output), "--cache-root=" + str(cache), "--expected-sha256=" + args.plan_sha256]
        stage = "SOURCE_NATIVE_DRAW_READPIXELS"
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=True)
        with DescendantGuard(child.pid) as guard:
            try:
                returncode = child.wait(timeout=max(.1, min(895, remaining - 5)))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                raise
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                cleanup = guard.cleanup()
                atomic(job / "cleanup.json", cleanup)
            if cleanup["remaining"] or cleanup["errors"] or cleanup["observationError"]:
                raise RuntimeError("STUDIO_SOURCE_CLEANUP_UNVERIFIED")
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)
        stage = "SOURCE_OUTPUT_VERIFY"
        videos = list((output / "public-review").glob("*.mp4"))
        if len(videos) != 1:
            raise RuntimeError("STUDIO_SOURCE_OUTPUT_MISSING")
        video = videos[0]
        report = json.loads((output / "proof/CAPTURE_REPORT.json").read_bytes())
        digest = validate_capture(report, video, total)
        result = {"jobId": job.name, "state": "COMPLETED", "softwareOnly": True,
            "historicalRenderAllowed": receipt["historicalRenderAllowed"], "gpuRenderingVerified": False, "userApproved": False,
            "downloads": [{"name": video.name, "sha256": digest, "bytes": video.stat().st_size, "path": str(video)}]}
        atomic(job / "result.json", result)
        state.update(state="COMPLETED", phase="SOURCE_SOFTWARE_REVIEW_COMPLETE", processedFrames=total,
            completedScenes=1, elapsedSeconds=round(time.monotonic() - started, 3))
    except Exception as error:
        safe_code = str(error) if re.fullmatch(r"[A-Z][A-Z0-9_]{1,99}", str(error)) else "STUDIO_SOURCE_WORKER_FAILED"
        state.update(state="FAILED", phase=stage, errorCode=safe_code,
            elapsedSeconds=round(time.monotonic() - started, 3))
        atomic(job / "failure.json", {"stage": stage, "code": safe_code, "kind": type(error).__name__,
            "childExitCode": getattr(error, "returncode", None)})
        raise
    finally:
        atomic(job / "state.json", state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    run(parser.parse_args())
