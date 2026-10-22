"""Minimize NEW public receipt copies, retaining originals privately unchanged."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def write(file, data):
    with file.open("x") as target:
        json.dump(data, target, indent=2, ensure_ascii=False)
        target.write("\n")


def prepare(name, capture, archive):
    if not name or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in name):
        raise ValueError("SAFE_PUBLIC_NAME_REQUIRED")
    public = HERE / "public-review"
    original_file = capture / "CAPTURE_RECEIPT.json"
    original = json.loads(original_file.read_bytes())
    if original["status"] != "TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED":
        raise ValueError("COMPLETED_ACTUAL_CAPTURE_REQUIRED")
    video = public / (name + ".mp4")
    if sha(video) != original["video"]["sha256"] or sha(capture / "VIDEO.mp4") != sha(video):
        raise ValueError("PUBLIC_VIDEO_SHA_MISMATCH")
    frame = public / (name + "_FRAME_EVIDENCE.json")
    if sha(frame) != original["frameEvidence"]["sha256"]:
        raise ValueError("PUBLIC_FRAME_EVIDENCE_SHA_MISMATCH")
    copied = public / (name + "_CAPTURE_RECEIPT.json")
    if sha(copied) != sha(original_file):
        raise ValueError("EXPECTED_UNPUBLISHED_RAW_COPY_REQUIRED")
    destination = archive / copied.name
    if destination.exists():
        raise ValueError("ARCHIVE_ALREADY_EXISTS")
    # Preserve the new raw copy; never remove or alter the original job receipt,
    # MP4, Scene, cache, source or an earlier published artifact.
    copied.rename(destination)
    destination.chmod(0o600)
    keys = ["status", "packageSHA256", "sourceInputSHA256", "sourceQualificationSHA256", "totalFrames",
            "renderedFrames", "softwareOnly", "nvidiaVerified", "visualQualityApproved", "paidExecuted",
            "startedAt", "transitions", "sourceCredits", "dependencies", "embeddedSourceCredits",
            "video", "elapsedSeconds", "finishedAt", "browserErrors"]
    safe = {key: original[key] for key in keys}
    safe.update({"schema": "WORLD_ENGINE_PUBLIC_CAPTURE_RECEIPT_V2", "originalCaptureReceiptSHA256": sha(original_file),
        "originalCaptureReceiptPreservedPrivately": True,
        "omittedFromPublicCopy": ["nativeFactory/internal-layout diagnostics", "private absolute source/cache paths"],
        "frameEvidence": {"file": frame.name, "sha256": sha(frame)},
        "runtime": {"backend": original["runtime"]["backend"], "segments": [
            {key: segment[key] for key in ["segmentIndex", "schema", "backend", "softwareOnly", "nvidiaVerified",
                "actualGPUVerified", "visualQualityApproved", "existingEngines", "movingComposition",
                "trackHydration", "countrySpecificBranches", "finishedFrameBlit"]}
            for segment in original["runtime"]["segments"]]}})
    safe["video"] = {**safe["video"], "file": video.name,
                     "originalPrivateFileBasename": "VIDEO.mp4"}
    raw = json.dumps(safe, ensure_ascii=False).encode()
    if b"/workspace/" in raw or b"/tmp/" in raw:
        raise ValueError("PRIVATE_PATH_IN_SAFE_RECEIPT")
    write(copied, safe)
    request = public / (name + "_RENDER_REQUEST.json")
    raw_request = (capture / "REQUEST.json").read_bytes()
    if b"/workspace/" in raw_request or b"/tmp/" in raw_request:
        raise ValueError("PRIVATE_PATH_IN_RENDER_REQUEST")
    with request.open("xb") as target:
        target.write(raw_request)
    return {"name": name, "videoSHA256": sha(video), "frameEvidenceSHA256": sha(frame),
        "renderRequestSHA256": sha(request), "publicReceiptSHA256": sha(copied),
        "originalReceiptSHA256": sha(original_file), "rawCopyArchivedUnchanged": sha(destination) == sha(original_file),
        "videoAndFrameEvidenceModified": False, "publicPrivatePathCount": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="append", required=True)
    parser.add_argument("--private-archive", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not args.private_archive.is_absolute() or args.private_archive.is_relative_to(HERE.parents[2]):
        raise ValueError("PRIVATE_ARCHIVE_OUTSIDE_REPOSITORY_REQUIRED")
    args.private_archive.mkdir(mode=0o700, parents=True, exist_ok=False)
    rows = [prepare(name, Path(directory), args.private_archive)
            for name, directory in (x.split("=", 1) for x in args.capture)]
    result = {"schema": "WORLD_ENGINE_UP2_PUBLIC_MEDIA_MINIMIZATION_V1", "status": "PASS", "artifacts": rows,
        "existingProtectedFilesChanged": 0, "rawReceiptsPublished": False}
    write(args.report, result)
    print(json.dumps(result, indent=2))
