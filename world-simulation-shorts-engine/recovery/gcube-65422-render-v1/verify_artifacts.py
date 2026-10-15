#!/usr/bin/env python3
"""Verify existing 65422 media and optional Dropbox GETs; never render or use GPU.

Reuses the seven-file SHA/actual-GET pattern in moving-frontier-glow-fix-v1/
verify_public_downloads.py. URLs remain private input and are never in receipts.
The SHA256SUMS anchor must come separately from the source export log/receipt.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

MOVIE = "WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4"
PNGS = ("01_START.png", "02_ADVANCE.png", "03_TRACKING.png",
        "04_CONTINUOUS_CONTROL.png", "05_END.png")
EXPECTED = frozenset((MOVIE, *PNGS, "SHA256SUMS"))
LIMITS = {MOVIE: 512 * 1024**2, **{name: 32 * 1024**2 for name in PNGS}, "SHA256SUMS": 8192}
HASH = re.compile(r"[0-9a-f]{64}\Z")


class ArtifactError(RuntimeError):
    """Fixed safe codes, with no remote URL or raw subprocess error text."""


def _fail(code):
    raise ArtifactError(code)


def _anchor(value):
    if not isinstance(value, str) or HASH.fullmatch(value) is None:
        _fail("SOURCE_SHA256SUMS_ANCHOR_REQUIRED")
    return value


def _read_regular(path, limit):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= limit:
                _fail("REGULAR_BOUNDED_SINGLE_LINK_FILE_REQUIRED")
            value = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        if (len(value) > limit or before.st_size != len(value)
                or (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)):
            _fail("FILE_CHANGED_OR_EXCEEDED_LIMIT")
        return value
    except OSError:
        _fail("FILE_ACCESS_FAILED")


def parse_sums(body, anchor):
    if hashlib.sha256(body).hexdigest() != _anchor(anchor):
        _fail("SOURCE_SHA256SUMS_ANCHOR_MISMATCH")
    try:
        lines = body.decode("ascii").splitlines()
    except UnicodeError:
        _fail("SHA256SUMS_INVALID")
    declared = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if not match or match[2] in declared or match[2] not in EXPECTED - {"SHA256SUMS"}:
            _fail("SHA256SUMS_INVALID")
        declared[match[2]] = match[1]
    if set(declared) != EXPECTED - {"SHA256SUMS"}:
        _fail("SHA256SUMS_EXACT_SIX_REQUIRED")
    return declared


def _probe(movie, *, decode):
    if shutil.which("ffprobe") is None or (decode and shutil.which("ffmpeg") is None):
        _fail("MEDIA_VERIFIER_DEPENDENCY_UNAVAILABLE")
    command = ["ffprobe", "-v", "error", "-count_frames", "-show_entries",
               "stream=codec_name,codec_type,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration:format=duration",
               "-of", "json", str(movie)]
    try:
        result = subprocess.run(command, capture_output=True, timeout=120, check=False)
        if result.returncode != 0 or len(result.stdout) > 1024 * 1024 or result.stderr.strip():
            _fail("FFPROBE_FAILED")
        probe = json.loads(result.stdout)
        streams = probe["streams"]
        if len(streams) != 1:
            _fail("SINGLE_SILENT_VIDEO_STREAM_REQUIRED")
        video = streams[0]
        if (video.get("codec_name") != "h264" or video.get("codec_type") != "video"
                or video.get("width") != 1080 or video.get("height") != 1920
                or Fraction(video.get("avg_frame_rate", "0")) != 30
                or Fraction(video.get("r_frame_rate", "0")) != 30
                or int(video.get("nb_frames", "0")) != 150 or int(video.get("nb_read_frames", "0")) != 150
                or Fraction(video.get("duration", "0")) != 5
                or Fraction(probe.get("format", {}).get("duration", "0")) != 5):
            _fail("VIDEO_65422_CONTRACT_MISMATCH")
        if decode:
            result = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-hwaccel", "none",
                                     "-threads", "2", "-i", str(movie), "-map", "0:v:0", "-an", "-sn", "-dn",
                                     "-f", "null", "-"], capture_output=True, timeout=120, check=False)
            if result.returncode != 0 or result.stderr.strip():
                _fail("CPU_FULL_DECODE_FAILED")
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError, ZeroDivisionError):
        _fail("MEDIA_VALIDATION_FAILED")
    return {"width": 1080, "height": 1920, "fps": 30, "decodedFrames": 150,
            "durationSeconds": 5, "videoCodec": "h264", "audioStreams": 0,
            "ffprobeCountFrames": "PASS", "ffmpegFullDecode": "PASS" if decode else "NOT_EXECUTED",
            "decodeHardwareAcceleration": "none"}


def verify_public(public_dir, anchor, *, decode=False):
    root = Path(public_dir)
    try:
        if root.is_symlink() or not root.is_dir() or set(item.name for item in root.iterdir()) != EXPECTED:
            _fail("EXACT_SEVEN_PUBLIC_FILES_REQUIRED")
    except OSError:
        _fail("PUBLIC_DIRECTORY_UNAVAILABLE")
    sums = _read_regular(root / "SHA256SUMS", LIMITS["SHA256SUMS"])
    expected = parse_sums(sums, anchor)
    rows = []
    for name in sorted(EXPECTED):
        body = _read_regular(root / name, LIMITS[name])
        digest = hashlib.sha256(body).hexdigest()
        if digest != (anchor if name == "SHA256SUMS" else expected[name]):
            _fail("ARTIFACT_SHA256_MISMATCH")
        if name in PNGS and (len(body) < 33 or body[:8] != b"\x89PNG\r\n\x1a\n"
                             or body[12:16] != b"IHDR" or struct.unpack(">II", body[16:24]) != (1080, 1920)):
            _fail("CHECKPOINT_PNG_DIMENSIONS_INVALID")
        rows.append({"file": name, "sha256": digest, "bytes": len(body)})
    media = _probe(root / MOVIE, decode=decode)
    # Reject an input modified while ffprobe/ffmpeg was reading it.
    if any(hashlib.sha256(_read_regular(root / row["file"], LIMITS[row["file"]])).hexdigest() != row["sha256"] for row in rows):
        _fail("ARTIFACT_CHANGED_DURING_MEDIA_CHECK")
    return {"schema": "WORLD_ENGINE_65422_ARTIFACT_VERIFICATION_V1", "status": "ARTIFACT_TECHNICAL_PASS",
            "sourceSha256SumsAnchor": anchor, "files": rows, "media": media,
            "externalDownloadVerified": False, "hardwareVerified": False,
            "visualQuality": "UNREVIEWED", "actualRenderPerformed": False, "finalPromotion": False}


def validate_dropbox_url(value):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 33 for c in value):
        _fail("DROPBOX_HTTPS_URL_REQUIRED")
    try:
        parsed = urllib.parse.urlsplit(value)
        host = parsed.hostname
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment
                or parsed.port not in {None, 443} or not host):
            _fail("DROPBOX_HTTPS_URL_REQUIRED")
        if host in {"dropbox.com", "www.dropbox.com"}:
            query = urllib.parse.parse_qs(parsed.query)
            if (not parsed.path.startswith(("/s/", "/scl/fi/"))
                    or not (query.get("dl") == ["1"] or query.get("raw") == ["1"])):
                _fail("DROPBOX_DIRECT_DOWNLOAD_REQUIRED")
        elif not (host == "dropboxusercontent.com" or host.endswith(".dropboxusercontent.com")):
            _fail("DROPBOX_HTTPS_URL_REQUIRED")
    except ValueError:
        _fail("DROPBOX_HTTPS_URL_REQUIRED")
    return value


class DropboxRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 5
    max_repeats = 2

    def redirect_request(self, request, fp, code, message, headers, newurl):
        validate_dropbox_url(newurl)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def read_urls(path):
    try:
        def pairs(items):
            result = {}
            for name, value in items:
                if name in result:
                    _fail("URL_MAP_DUPLICATE_KEY")
                result[name] = value
            return result
        mapping = json.loads(_read_regular(Path(path), 32768), object_pairs_hook=pairs)
    except (ValueError, TypeError):
        _fail("URL_MAP_INVALID")
    if not isinstance(mapping, dict) or set(mapping) != EXPECTED:
        _fail("URL_MAP_EXACT_SEVEN_REQUIRED")
    for value in mapping.values():
        validate_dropbox_url(value)
    return mapping


def download_public(mapping, destination, anchor, *, opener=None):
    """Actual bounded HTTPS GET with TLS defaults; injected opener is SYNTHETIC."""
    _anchor(anchor)
    if not isinstance(mapping, dict) or set(mapping) != EXPECTED:
        _fail("URL_MAP_EXACT_SEVEN_REQUIRED")
    for value in mapping.values():
        validate_dropbox_url(value)
    root = Path(destination)
    try:
        root.mkdir(mode=0o700)  # Existing paths are never reused or overwritten.
    except OSError:
        _fail("FRESH_DOWNLOAD_DIRECTORY_REQUIRED")
    synthetic = opener is not None
    client = opener or urllib.request.build_opener(DropboxRedirect())
    rows, expected = [], None
    for name in ["SHA256SUMS", *sorted(EXPECTED - {"SHA256SUMS"})]:
        digest, size, started = hashlib.sha256(), 0, time.monotonic()
        try:
            request = urllib.request.Request(mapping[name], headers={"User-Agent": "WorldEngineArtifactVerifier/1"})
            with client.open(request, timeout=30) as response:
                validate_dropbox_url(response.geturl())
                if response.status != 200:
                    _fail("DOWNLOAD_HTTP_200_REQUIRED")
                declared = response.headers.get("Content-Length")
                if declared is not None and (not declared.isdecimal() or not 0 < int(declared) <= LIMITS[name]):
                    _fail("DOWNLOAD_SIZE_LIMIT_EXCEEDED")
                read_chunk = getattr(response, "read1", None)
                if not callable(read_chunk):
                    _fail("DOWNLOAD_BOUNDED_STREAM_REQUIRED")
                fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    while True:
                        if time.monotonic() - started > 90:
                            _fail("DOWNLOAD_SIZE_OR_DEADLINE_EXCEEDED")
                        # HTTPResponse.read(n) can wait to fill n bytes despite
                        # continuous slow input. read1 performs at most one raw
                        # read, allowing the total deadline to be checked again.
                        chunk = read_chunk(min(1024 * 1024, LIMITS[name] + 1 - size))
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > LIMITS[name] or time.monotonic() - started > 90:
                            _fail("DOWNLOAD_SIZE_OR_DEADLINE_EXCEEDED")
                        digest.update(chunk)
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
            if size == 0 or (declared is not None and int(declared) != size):
                _fail("DOWNLOAD_LENGTH_MISMATCH")
            if name == "SHA256SUMS":
                expected = parse_sums(_read_regular(root / name, LIMITS[name]), anchor)
            elif digest.hexdigest() != expected[name]:
                _fail("DOWNLOAD_SHA256_MISMATCH")
            rows.append({"file": name, "httpStatus": 200, "bytes": size, "sha256": digest.hexdigest()})
        except (OSError, ValueError, urllib.error.URLError):
            _fail("DOWNLOAD_FAILED")
    return {"method": "SYNTHETIC_HTTP" if synthetic else "ACTUAL_HTTPS_GET_WITH_TLS_VERIFICATION",
            "testOnly": synthetic, "files": rows, "externalDownloadVerified": not synthetic}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-dir", type=Path)
    parser.add_argument("--sha256sums-sha256", required=True)
    parser.add_argument("--urls-file", type=Path, help="Private exact filename-to-Dropbox-direct-URL JSON; never put in public-review")
    parser.add_argument("--download-dir", type=Path, help="Must not already exist")
    parser.add_argument("--receipt", required=True, type=Path, help="New private JSON file outside public-review")
    parser.add_argument("--decode", action="store_true", help="Also fully decode with CPU FFmpeg and fail on decoding errors")
    args = parser.parse_args(argv)
    receipt = {"schema": "WORLD_ENGINE_65422_ARTIFACT_VERIFICATION_V1", "status": "BLOCKED",
               "hardwareVerified": False, "visualQuality": "UNREVIEWED", "actualRenderPerformed": False,
               "externalDownloadVerified": False, "finalPromotion": False}
    code, receipt_allowed = 2, False
    try:
        _anchor(args.sha256sums_sha256)
        if bool(args.urls_file) != bool(args.download_dir) or bool(args.public_dir) == bool(args.urls_file):
            _fail("SELECT_LOCAL_DIRECTORY_OR_DROPBOX_DOWNLOAD")
        public = args.download_dir if args.urls_file else args.public_dir
        if args.receipt.resolve().is_relative_to(public.resolve()) or args.receipt.exists():
            _fail("NEW_PRIVATE_RECEIPT_OUTSIDE_PUBLIC_REQUIRED")
        receipt_allowed = True
        downloaded = None
        if args.urls_file:
            downloaded = download_public(read_urls(args.urls_file), public, args.sha256sums_sha256)
        receipt = verify_public(public, args.sha256sums_sha256, decode=args.decode)
        if downloaded:
            receipt["download"] = downloaded
            receipt["externalDownloadVerified"] = downloaded["externalDownloadVerified"]
        code = 0
    except ArtifactError as error:
        receipt["errorCode"] = str(error)
    except (OSError, ValueError, TypeError):
        receipt["errorCode"] = "VERIFICATION_UNAVAILABLE"
    if not receipt_allowed:
        print(json.dumps(receipt, sort_keys=True, allow_nan=False))
        return 2
    try:
        fd = os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    except OSError:
        print(json.dumps({"status": "BLOCKED", "errorCode": "PRIVATE_RECEIPT_WRITE_FAILED", "hardwareVerified": False}))
        return 2
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
