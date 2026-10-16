"""Bounded, frame-verified composition using the existing FFmpeg toolchain.

This is a new orchestration layer, not a renderer. Actual decoded frame hashes
prove segment order and identity; adjacent different images are not, by
themselves, proof of a visually continuous camera or historical state.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import threading
import time

HASH = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,179}\Z")
MOVIE = "WORLD_ENGINE_AUTO_VIDEO.mp4"
SUMMARY = "QUALITY_SUMMARY.json"
CHUNK = 1024 * 1024


class ComposeError(RuntimeError):
    """Safe, fixed error codes; raw paths and subprocess errors remain private."""


def _fail(code):
    raise ComposeError(code)


def _json(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def digest_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size <= 0:
            _fail("REGULAR_SINGLE_LINK_FILE_REQUIRED")
        digest = hashlib.sha256()
        for chunk in iter(lambda: os.read(fd, CHUNK), b""):
            digest.update(chunk)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            _fail("INPUT_CHANGED_DURING_READ")
        return digest.hexdigest()
    finally:
        os.close(fd)


def video_contract(plan):
    """Accept the generator's neutral plan; all ranges are half open."""
    try:
        fps = Fraction(str(plan["fps"]))
        duration = Fraction(str(plan["durationSeconds"]))
        resolution = plan["resolution"]
        width, height = ((resolution["width"], resolution["height"]) if isinstance(resolution, dict) else resolution)
        frames = duration * fps
        if (isinstance(plan["fps"], bool) or fps.denominator != 1 or not 1 <= fps <= 120
                or duration <= 0 or duration > 86400 or frames.denominator != 1
                or any(isinstance(v, bool) or not isinstance(v, int) or v < 16 or v > 8192 or v % 2 for v in (width, height))):
            _fail("VIDEO_PLAN_CONTRACT_INVALID")
        return {"fps": int(fps), "durationSeconds": float(duration), "frames": int(frames), "width": width, "height": height}
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        _fail("VIDEO_PLAN_CONTRACT_INVALID")


def _run(command, log, *, timeout=1800):
    with open(log, "xb") as error:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=error, timeout=timeout, check=False)
    if result.returncode != 0:
        _fail("MEDIA_COMMAND_FAILED")
    if len(result.stdout) > 4 * 1024**2:
        _fail("MEDIA_METADATA_TOO_LARGE")
    return result.stdout


def _watchdog(process, seconds=1800):
    expired = threading.Event()
    def stop():
        expired.set()
        try:
            process.kill()
        except ProcessLookupError:
            pass
    timer = threading.Timer(seconds, stop)
    timer.daemon = True
    timer.start()
    return timer, expired


def _probe(path, contract, frames, diagnostics, name):
    raw = _run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-show_data_hash", "sha256",
                "-of", "json", str(path)], diagnostics / (name + "-probe.stderr"))
    try:
        data = json.loads(raw)
        streams = data["streams"]
        if len(streams) != 1:
            _fail("SINGLE_SILENT_VIDEO_STREAM_REQUIRED")
        stream = streams[0]
        if (stream.get("codec_name") != "h264" or stream.get("codec_type") != "video"
                or stream.get("pix_fmt") != "yuv420p" or stream.get("width") != contract["width"]
                or stream.get("height") != contract["height"]
                or Fraction(stream.get("avg_frame_rate", "0")) != contract["fps"]
                or Fraction(stream.get("r_frame_rate", "0")) != contract["fps"]
                or int(stream.get("nb_read_frames", "0")) != frames):
            _fail("SEGMENT_MEDIA_CONTRACT_MISMATCH")
        duration = Fraction(stream.get("duration", "0"))
        if abs(duration - Fraction(frames, contract["fps"])) > Fraction(1, 100000):
            _fail("SEGMENT_DURATION_MISMATCH")
        signature = {key: stream.get(key) for key in ("codec_name", "codec_tag_string", "profile", "level", "width", "height", "pix_fmt",
                                                     "time_base", "field_order", "color_range", "color_space", "color_transfer", "color_primaries", "extradata_hash")}
        return {"signature": signature, "codec": "h264", "frames": frames, "duration": float(duration)}
    except (ValueError, TypeError, KeyError, ZeroDivisionError):
        _fail("MEDIA_METADATA_INVALID")


def _timestamps(path, contract, frames, diagnostics, name):
    """Inspect every presentation timestamp with constant memory."""
    count, first, first_key = 0, None, False
    log = diagnostics / (name + "-timestamps.stderr")
    with open(log, "xb") as error:
        process = subprocess.Popen(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                    "frame=best_effort_timestamp_time,key_frame", "-of", "compact=p=0:nk=0", str(path)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=error, text=True)
        timer, expired = _watchdog(process)
        try:
            for line in process.stdout:
                fields = dict(part.split("=", 1) for part in line.strip().split("|") if "=" in part)
                if "best_effort_timestamp_time" not in fields:
                    continue
                pts = Fraction(fields["best_effort_timestamp_time"])
                if first is None:
                    first, first_key = pts, fields.get("key_frame") == "1"
                if abs(pts - first - Fraction(count, contract["fps"])) > Fraction(2, 1000000):
                    _fail("FRAME_TIMESTAMP_GAP_OR_DUPLICATE")
                count += 1
                if count > frames:
                    _fail("SEGMENT_FRAME_COUNT_MISMATCH")
            code = process.wait(timeout=30)
            if expired.is_set():
                _fail("MEDIA_OPERATION_TIMEOUT")
            if code != 0 or count != frames:
                _fail("SEGMENT_TIMESTAMPS_INVALID")
        except BaseException:
            process.kill()
            process.wait()
            raise
        finally:
            timer.cancel()
            process.stdout.close()
    return {"frames": count, "startZero": first == 0, "firstKeyframe": first_key, "constantRate": True}


def _framehashes(path, destination, diagnostics, name, *, expected_paths=(), inspect_black=False):
    """Full software decode; hashes are streamed to disk, never frame buffers."""
    expected = iter(_iter_hashes(expected_paths)) if expected_paths else None
    count, first, last, aggregate = 0, None, None, hashlib.sha256()
    with open(diagnostics / (name + "-decode.stderr"), "xb") as error, open(destination, "x", encoding="ascii") as output:
        # Metadata output is private, streamed and contains no user text.
        black_path = diagnostics / (name + "-blackframes.txt")
        if any(value in str(black_path) for value in ("'", ":", "\\", "\n", "\r")):
            _fail("MEDIA_DIAGNOSTIC_PATH_UNSAFE")
        filters = (f"blackframe=amount=99:threshold=26,metadata=mode=print:key=lavfi.blackframe.pblack:file='{black_path}'," if inspect_black else "") + "format=rgb24"
        process = subprocess.Popen(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-hwaccel", "none", "-threads", "2", "-i", str(path),
                                    "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", filters, "-fps_mode", "passthrough",
                                    "-f", "framehash", "-hash", "sha256", "-"], stdout=subprocess.PIPE, stderr=error, text=True)
        timer, expired = _watchdog(process)
        try:
            for line in process.stdout:
                if line.startswith("#") or not line.strip():
                    continue
                value = line.rsplit(",", 1)[-1].strip()
                if not HASH.fullmatch(value):
                    _fail("DECODED_FRAME_HASH_INVALID")
                if expected is not None and next(expected, None) != value:
                    _fail("COMPOSED_DECODED_FRAME_CHANGED_OR_REORDERED")
                output.write(value + "\n")
                aggregate.update((value + "\n").encode())
                first, last, count = first or value, value, count + 1
            code = process.wait(timeout=30)
            if expired.is_set():
                _fail("MEDIA_OPERATION_TIMEOUT")
            if code != 0 or not count:
                _fail("FULL_DECODE_FAILED")
            if expected is not None and next(expected, None) is not None:
                _fail("COMPOSED_DECODED_FRAME_MISSING")
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            process.kill()
            process.wait()
            raise
        finally:
            timer.cancel()
            process.stdout.close()
    if inspect_black:
        # Whole-frame near-black is corruption for this map-only profile.
        # This is a detector, not semantic or aesthetic quality approval.
        with open(black_path, encoding="ascii") as stream:
            if any(line.startswith("lavfi.blackframe.pblack=") for line in stream):
                _fail("NEAR_BLACK_MAP_FRAME_DETECTED")
    return {"frames": count, "first": first, "last": last, "decodedRGB24SequenceSHA256": aggregate.hexdigest()}


def _iter_hashes(paths):
    for path in paths:
        with open(path, encoding="ascii") as stream:
            for line in stream:
                yield line.strip()


def _concat_file(paths, destination):
    # Paths are generated numbered names inside our own fresh directory.
    with open(destination, "x", encoding="utf-8") as stream:
        stream.write("ffconcat version 1.0\n")
        for path in paths:
            if "'" in str(path) or "\n" in str(path) or "\r" in str(path):
                _fail("CONCAT_PATH_UNSAFE")
            stream.write("file '" + str(path.resolve()) + "'\n")


def _scene_rows(plan, segments, contract):
    if not isinstance(segments, list) or not segments or len(segments) > 10000:
        _fail("ORDERED_SEGMENTS_REQUIRED")
    cursor, seen, rows = 0, set(), []
    for segment in segments:
        try:
            scene_id, start, end = segment["sceneId"], segment["startFrame"], segment["endFrame"]
            if (not isinstance(scene_id, str) or not NAME.fullmatch(scene_id) or scene_id in seen
                    or isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int)
                    or not isinstance(end, int) or start != cursor or not start < end <= contract["frames"]
                    or not isinstance(segment.get("sha256"), str) or not HASH.fullmatch(segment["sha256"])):
                _fail("SEGMENT_ORDER_OR_HALF_OPEN_RANGE_INVALID")
            seen.add(scene_id)
            cursor = end
            rows.append(dict(segment))
        except (KeyError, TypeError):
            _fail("SEGMENT_RECEIPT_INVALID")
    if cursor != contract["frames"]:
        _fail("TOTAL_FRAME_COVERAGE_MISMATCH")
    scenes = plan.get("scenes")
    if scenes is not None:
        if (not isinstance(scenes, list) or len(scenes) != len(rows)
                or any(not isinstance(scene, dict) or any(scene.get(key) != row[key] for key in ("sceneId", "startFrame", "endFrame"))
                       for scene, row in zip(scenes, rows))):
            _fail("SEGMENT_PLAN_ORDER_MISMATCH")
    return rows


def verify_segment(path, scene, plan, *, diagnostics=None):
    """Cache admission: actual ffprobe, every PTS and full decoded frame hashes.

    A disposable *new* private evidence directory is created when none is given.
    This never asserts that the images are geographic footage or GPU-rendered.
    """
    contract = video_contract(plan)
    try:
        start, end = scene["startFrame"], scene["endFrame"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= contract["frames"]:
            _fail("SEGMENT_FRAME_RANGE_INVALID")
        path = Path(path).absolute()
        root = Path(diagnostics) if diagnostics is not None else Path(tempfile.mkdtemp(prefix="verification-", dir=path.parent))
        if diagnostics is not None:
            root.mkdir(mode=0o700)
        before = digest_file(path)
        media = _probe(path, contract, end - start, root, "segment")
        pts = _timestamps(path, contract, end - start, root, "segment")
        decoded = _framehashes(path, root / "rgb24.sha256", root, "segment")
        if decoded["frames"] != end - start or digest_file(path) != before:
            _fail("SEGMENT_CHANGED_OR_DECODE_COUNT_MISMATCH")
        return {"technical": "PASS", "frameCountVerified": True, "sha256": before,
                "frames": decoded["frames"], "frameCount": decoded["frames"], "media": media, "timestamps": pts,
                "boundaryFrames": {"algorithm": "DECODED_RGB24_SHA256", "first": decoded["first"], "last": decoded["last"]},
                "decodedRGB24SequenceSHA256": decoded["decodedRGB24SequenceSHA256"],
                "verificationDirectory": str(root), "fullDecodeVerified": True, "gpuVerified": False}
    except (KeyError, TypeError, ValueError):
        _fail("SEGMENT_FRAME_RANGE_INVALID")


def compose_segments(plan, segments, destination):
    """Verify and compose a fresh output. Failure files are quarantined in place.

    The producer must supply ordered half-open global frame ranges and file SHA.
    Optional boundaryFrames contains actual encoded RGB24 first/last hashes.
    Optional plan scenes boundaryEndSHA256/boundaryStartSHA256 encode requested
    states at the same mathematical boundary (not adjacent frame equality).
    """
    contract = video_contract(plan)
    rows = _scene_rows(plan, segments, contract)
    root = Path(destination)
    try:
        root.mkdir(mode=0o700)
    except OSError:
        _fail("FRESH_COMPOSITION_DIRECTORY_REQUIRED")
    diagnostics = root / "diagnostics"
    diagnostics.mkdir(mode=0o700)
    started = time.monotonic()
    try:
        checked, hashes, paths = [], [], []
        for index, row in enumerate(rows):
            path = Path(row["path"]).absolute()
            actual = digest_file(path)
            if actual != row["sha256"]:
                _fail("SEGMENT_SHA256_MISMATCH")
            count, name = row["endFrame"] - row["startFrame"], f"segment-{index:05d}"
            media = _probe(path, contract, count, diagnostics, name)
            pts = _timestamps(path, contract, count, diagnostics, name)
            frame_path = diagnostics / (name + "-rgb24.sha256")
            decoded = _framehashes(path, frame_path, diagnostics, name)
            if decoded["frames"] != count:
                _fail("SEGMENT_DECODED_COUNT_MISMATCH")
            boundary = row.get("boundaryFrames")
            if boundary is not None and (boundary.get("algorithm") != "DECODED_RGB24_SHA256"
                    or boundary.get("first") != decoded["first"] or boundary.get("last") != decoded["last"]):
                _fail("SEGMENT_RENDERED_EDGE_HASH_MISMATCH")
            if digest_file(path) != actual:
                _fail("SEGMENT_CHANGED_DURING_VERIFICATION")
            checked.append({"sceneId": row["sceneId"], "startFrame": row["startFrame"], "endFrame": row["endFrame"],
                            "sha256": actual, "media": media, "timestamps": pts, "decoded": decoded})
            hashes.append(frame_path)
            paths.append(path)
        source_verified_at = time.monotonic()
        scene_states = plan.get("scenes", [])
        state_checks = []
        for previous, current in zip(scene_states, scene_states[1:]):
            left, right = previous.get("boundaryEndSHA256"), current.get("boundaryStartSHA256")
            if previous.get("boundaryEnd") is not None or current.get("boundaryStart") is not None:
                left_state, right_state = previous.get("boundaryEnd"), current.get("boundaryStart")
                if not isinstance(left_state, dict) or not isinstance(right_state, dict):
                    _fail("REQUESTED_SCENE_BOUNDARY_STATE_MISMATCH")
                left = hashlib.sha256(json.dumps(left_state, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                right = hashlib.sha256(json.dumps(right_state, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            if left is not None or right is not None:
                if not isinstance(left, str) or not HASH.fullmatch(left) or left != right:
                    _fail("REQUESTED_SCENE_BOUNDARY_STATE_MISMATCH")
                state_checks.append({"left": previous["sceneId"], "right": current["sceneId"], "stateSHA256": left})
        compatible = all(item["timestamps"]["startZero"] and item["timestamps"]["firstKeyframe"]
                         and item["media"]["signature"] == checked[0]["media"]["signature"] for item in checked)
        mode = "VERIFIED_STREAM_COPY" if compatible else "LOSSLESS_NORMALIZE_THEN_COPY"
        if not compatible:
            normalized = []
            for index, path in enumerate(paths):
                target = diagnostics / f"normalized-{index:05d}.mp4"
                _run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-n", "-threads", "2", "-i", str(path), "-map", "0:v:0", "-an",
                      "-vf", f"setpts=N/({contract['fps']}*TB)", "-r", str(contract["fps"]), "-fps_mode", "cfr", "-c:v", "libx264", "-threads", "2",
                      "-preset", "medium", "-crf", "0", "-pix_fmt", "yuv420p", "-video_track_timescale", str(contract["fps"] * 512),
                      str(target)], diagnostics / f"normalize-{index:05d}.stderr")
                normalized.append(target)
            paths = normalized
        normalized_at = time.monotonic()
        concat = diagnostics / "ordered.ffconcat"
        _concat_file(paths, concat)
        partial = diagnostics / "composed-unverified.mp4"
        _run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-n", "-f", "concat", "-safe", "0", "-i", str(concat),
              "-map", "0:v:0", "-an", "-c:v", "copy", "-movflags", "+faststart", str(partial)], diagnostics / "compose.stderr")
        muxed_at = time.monotonic()
        final_media = _probe(partial, contract, contract["frames"], diagnostics, "final")
        final_pts = _timestamps(partial, contract, contract["frames"], diagnostics, "final")
        if not final_pts["startZero"]:
            _fail("FINAL_ZERO_START_REQUIRED")
        final_decoded = _framehashes(partial, diagnostics / "final-rgb24.sha256", diagnostics, "final", expected_paths=hashes, inspect_black=True)
        if final_decoded["frames"] != contract["frames"]:
            _fail("FINAL_DECODED_COUNT_MISMATCH")
        decoded_at = time.monotonic()
        # No source is allowed to change while the composition process reads it.
        for row in rows:
            if digest_file(row["path"]) != row["sha256"]:
                _fail("SEGMENT_CHANGED_DURING_COMPOSITION")
        public = root / "public-review"
        public.mkdir(mode=0o700)
        final = public / MOVIE
        os.rename(partial, final)
        final_hash = digest_file(final)
        summary = {"schema": "WORLD_ENGINE_UNIVERSAL_SAFE_QA_V2", "technicalVerification": "PASS", **contract,
                   "videoCodec": "h264", "audioStreams": 0, "sceneCount": len(rows), "fullDecode": "PASS",
                   "decodedFrameSequenceMatchesSegments": True, "compositionMode": mode,
                   "boundaryStateContract": "PASS" if len(state_checks) == max(0, len(rows) - 1) else "NOT_PROVIDED",
                   "visualContinuity": "UNREVIEWED", "visualQuality": "USER_VIDEO_REVIEW_REQUIRED",
                   "hardwareVerification": "NOT_ASSERTED_BY_COMPOSER", "finalPromotion": False}
        _json(public / SUMMARY, summary)
        summary_hash = digest_file(public / SUMMARY)
        sums = f"{final_hash}  {MOVIE}\n{summary_hash}  {SUMMARY}\n"
        with open(public / "SHA256SUMS", "x", encoding="ascii") as output:
            output.write(sums)
            output.flush()
            os.fsync(output.fileno())
        receipt = {"schema": "WORLD_ENGINE_UNIVERSAL_COMPOSITION_V2", "status": "COMPLETE", "frames": contract["frames"],
                   "sha256": final_hash, "sha256SumsSHA256": digest_file(public / "SHA256SUMS"), "media": final_media,
                   "decoded": final_decoded, "segments": checked, "requestedBoundaryStates": state_checks,
                   "boundaryDecodedPixelTrace": "RECORDED_NOT_VISUAL_APPROVAL", "compositionSeconds": time.monotonic() - started,
                   "timings": {"sourceVerificationSeconds": source_verified_at - started,
                               "normalizationSeconds": normalized_at - source_verified_at,
                               "muxSeconds": muxed_at - normalized_at,
                               "finalFullValidationSeconds": decoded_at - muxed_at,
                               "finalSourceReadbackAndCommitSeconds": time.monotonic() - decoded_at},
                   "mode": mode, "peakFrameBuffering": "FFMPEG_BOUNDED_PIPELINE_NO_PYTHON_FRAMES", "summary": summary}
        _json(root / "COMPOSE_COMPLETE.json", receipt)
        return {**receipt, "path": str(final), "publicDir": str(public), "receiptPath": str(root / "COMPOSE_COMPLETE.json"),
                "completionReceipt": str(root / "COMPOSE_COMPLETE.json"), "technical": "PASS", "quality": "UNREVIEWED"}
    except BaseException as error:
        code = str(error) if isinstance(error, ComposeError) else "UNEXPECTED_COMPOSITION_FAILURE"
        _json(root / "COMPOSE_FAILED.json", {"schema": "WORLD_ENGINE_UNIVERSAL_COMPOSITION_FAILURE_V2", "status": "FAILED",
                                           "errorCode": code, "publicDeliveryAllowed": False, "existingSegmentsPreserved": True})
        if isinstance(error, ComposeError):
            raise
        raise ComposeError(code) from None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--segments", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args(argv)
    try:
        result = compose_segments(json.loads(Path(args.plan).read_text()), json.loads(Path(args.segments).read_text()), args.destination)
        print(json.dumps({key: result[key] for key in ("status", "sha256", "frames", "technical", "quality")}))
        return 0
    except ComposeError as error:
        print(json.dumps({"status": "FAILED", "errorCode": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
