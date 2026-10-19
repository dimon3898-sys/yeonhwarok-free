#!/usr/bin/env python3
"""Read-only decoded diagnostic comparison; never renders or changes a source.

The historical preview and hypothetical reference are different events. No
temporal registration, pixel parity, ownership accuracy or quality PASS follows
from this figure. Platform UI is masked using the saved source analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

REFERENCE_SHA = "5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6"
REFERENCE_FRAMES = [160, 235, 310]
REFERENCE_PTS = [5.181813, 7.694207, 10.175196]
PREVIEW_FRAMES = [0, 75, 149]
MAP_CROP = [0, 211, 1080, 2131]
EXCLUDE = [
    [920, 870, 1080, 2131],
    [1060, 820, 1080, 1300],
    [0, 1835, 1080, 2131],
    [120, 1450, 930, 1620],
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    return json.loads(subprocess.run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout)


def exact_read(stream, size: int) -> bytes:
    parts = []; remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        parts.append(chunk); remaining -= len(chunk)
    return b"".join(parts)


def selected_reference(path: Path, frames: list[int]) -> list[np.ndarray]:
    expression = "+".join(f"eq(n\\,{frame})" for frame in frames)
    process = subprocess.Popen([
        "ffmpeg", "-v", "error", "-threads", "2", "-i", str(path), "-an", "-sn",
        "-vf", f"select={expression}", "-fps_mode", "passthrough", "-frames:v", str(len(frames)),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = []
    assert process.stdout is not None
    for _ in frames:
        raw = exact_read(process.stdout, 1080 * 2520 * 3)
        if len(raw) != 1080 * 2520 * 3:
            raise RuntimeError("REFERENCE_SELECTED_FRAME_DECODE_INCOMPLETE")
        result.append(np.frombuffer(raw, dtype=np.uint8).reshape(2520, 1080, 3).copy())
    process.stdout.close()
    error = process.stderr.read() if process.stderr else b""
    if process.wait() or error:
        raise RuntimeError("REFERENCE_SELECTED_FRAME_DECODE_FAILED")
    return result


def masked_content(frame: np.ndarray) -> np.ndarray:
    left, top, right, bottom = MAP_CROP
    result = frame[top:bottom, left:right].copy()
    for x0, y0, x1, y1 in EXCLUDE:
        result[max(0, y0 - top):min(bottom - top, y1 - top), max(0, x0 - left):min(right - left, x1 - left)] = [32, 38, 45]
    return result


def decode_preview(path: Path) -> tuple[dict, list[np.ndarray]]:
    metadata = probe(path)
    video = [row for row in metadata["streams"] if row["codec_type"] == "video"]
    if len(video) != 1 or (video[0]["width"], video[0]["height"]) != (1080, 1920):
        raise RuntimeError("PREVIEW_CANONICAL_DIMENSIONS_REQUIRED")
    process = subprocess.Popen([
        "ffmpeg", "-v", "error", "-threads", "2", "-i", str(path), "-an", "-sn",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-fps_mode", "passthrough", "pipe:1"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    selected = []; prior = None; count = 0; frame_hashes = []; temporal = []
    assert process.stdout is not None
    while True:
        raw = exact_read(process.stdout, 1080 * 1920 * 3)
        if not raw:
            break
        if len(raw) != 1080 * 1920 * 3:
            raise RuntimeError("PREVIEW_PARTIAL_RGB_FRAME")
        image = np.frombuffer(raw, dtype=np.uint8).reshape(1920, 1080, 3)
        frame_hashes.append(hashlib.sha256(raw).hexdigest())
        if count in PREVIEW_FRAMES:
            selected.append(image.copy())
        small = np.asarray(Image.fromarray(image).resize((120, 213), Image.Resampling.BILINEAR), dtype=np.int16)
        if prior is not None:
            temporal.append(float(np.abs(small - prior).mean()))
        prior = small; count += 1
    process.stdout.close()
    error = process.stderr.read() if process.stderr else b""
    if process.wait() or error or count != 150 or len(selected) != 3:
        raise RuntimeError("PREVIEW_FULL_150_DECODE_FAILED")
    return {
        "decodedFrames": count,
        "nativeRGBSHA256": frame_hashes,
        "adjacentExactDuplicatePairs": sum(a == b for a, b in zip(frame_hashes, frame_hashes[1:])),
        "downsampledRGBTemporalDelta": {
            "kind": "MEASURED_PIXEL_CHANGE_NOT_SEMANTIC_MOTION",
            "analysisDimensions": [120, 213],
            "mean": float(np.mean(temporal)),
            "minimum": float(min(temporal)),
            "maximum": float(max(temporal)),
            "all149Transitions": temporal,
        },
        "audioStreams": [{key: row.get(key) for key in ["codec_name", "sample_rate", "channels", "duration"]}
                         for row in metadata["streams"] if row["codec_type"] == "audio"],
        "fullDecodeExitCode": 0,
        "ffmpegErrorBytes": len(error),
    }, selected


def figure(reference: list[np.ndarray], preview: list[np.ndarray], output: Path) -> None:
    # Matplotlib's default cache may target a read-only home directory. This
    # analysis-only cache is disposable and is never a required result file.
    cache = tempfile.TemporaryDirectory(prefix="world-engine-comparison-plot-")
    previous_cache = os.environ.get("MPLCONFIGDIR")
    os.environ["MPLCONFIGDIR"] = cache.name
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 2, figsize=(10, 27), facecolor="#111922")
    for index in range(3):
        axes[index, 0].imshow(masked_content(reference[index]))
        axes[index, 1].imshow(preview[index])
        axes[index, 0].set_title(f"65379 reference — {REFERENCE_PTS[index]:.3f}s\nPhone UI/caption excluded", color="white", fontsize=11)
        axes[index, 1].set_title(f"New software preview — {PREVIEW_FRAMES[index] / 30:.3f}s\nOriginal global frame {1400 + PREVIEW_FRAMES[index]}", color="white", fontsize=11)
        for axis in axes[index]:
            axis.axis("off")
    fig.suptitle("STYLE / READABILITY COMPARISON\nDifferent source events and framing; no frame alignment\nSwiftShader CPU preview — NVIDIA quality NOT verified", color="white", fontsize=14, y=.994)
    fig.subplots_adjust(top=.935, bottom=.012, left=.01, right=.99, wspace=.025, hspace=.12)
    fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    if previous_cache is None:
        os.environ.pop("MPLCONFIGDIR", None)
    else:
        os.environ["MPLCONFIGDIR"] = previous_cache
    cache.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.reference) != REFERENCE_SHA:
        raise RuntimeError("REFERENCE_SOURCE_SHA_MISMATCH")
    args.output.mkdir(parents=True, exist_ok=True)
    references = selected_reference(args.reference, REFERENCE_FRAMES)
    report = {
        "schema": "WORLD_ENGINE_OVERNIGHT_REFERENCE_COMPARISON_V1",
        "referenceSHA256": REFERENCE_SHA,
        "referenceFramesActuallyDecoded": REFERENCE_FRAMES,
        "referencePTSSeconds": REFERENCE_PTS,
        "referencePriorFullDecode": "REUSED_958_FRAME_REFERENCE_VISUAL_MASTER_V2_ANALYSIS",
        "fullReferenceDecodeRepeated": False,
        "mapCropRecorderPixels": MAP_CROP,
        "excludedRecorderRectangles": EXCLUDE,
        "maskPolicy": "CONSERVATIVE_FIXED_PHONE_UI_EXCLUSION_NOT_INPAINTING",
        "comparisonKind": "DIFFERENT_EVENT_STYLE_AND_READABILITY_ONLY",
        "temporalAlignmentClaimed": False,
        "nvidiaRenderingVerified": False,
        "visualQualityPass": False,
        "actual66430VideoAvailable": False,
        "notes": [
            "Reference is a modern hypothetical scenario; the candidate uses qualified historical archival data.",
            "Camera/framing, events, fronts and ownership sources differ; no pixel-parity metric is meaningful.",
            "Reference UI/caption masks intentionally also discard some valid map pixels.",
            "Reference original source video and full extracted frames are not published by this tool.",
        ],
    }
    if args.candidate is None:
        Image.fromarray(masked_content(references[1])).save(args.output / "REFERENCE_CONTENT_PRIVATE_SAMPLE.png")
        report["candidateState"] = "WAITING_FOR_ACTUAL_150_FRAME_MP4"
    else:
        decoded, preview = decode_preview(args.candidate)
        image = args.output / "REFERENCE_VS_SOFTWARE_PREVIEW.png"
        figure(references, preview, image)
        report.update(candidateState="ACTUAL_SOFTWARE_MP4_DECODED", candidateSHA256=sha256(args.candidate),
                      candidateOriginalFrameRange=[1400, 1550], candidatePreviewFrames=PREVIEW_FRAMES,
                      candidateDecode=decoded, comparisonPNG={"filename": image.name, "sha256": sha256(image)})
    report_file = args.output / "REFERENCE_COMPARISON.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"report": str(report_file), "candidateState": report["candidateState"]}))


if __name__ == "__main__":
    main()
