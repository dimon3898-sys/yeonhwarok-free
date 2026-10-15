"""Focused verifier tests. All media and HTTP are explicitly SYNTHETIC CPU fixtures."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import urllib.request
import zlib

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("artifact_verifier", HERE / "verify_artifacts.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def png(color=0, width=1080):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    raw = (b"\0" + bytes((color, 20, 30)) * width) * 1920
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, 1920, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Response(io.BytesIO):
    status = 200

    def __init__(self, body, url):
        super().__init__(body)
        self.url = url
        self.headers = {"Content-Length": str(len(body))}

    def geturl(self):
        return self.url


class SyntheticHTTP:
    def __init__(self, bodies, urls):
        self.bodies, self.urls, self.calls = bodies, urls, []

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        name = next(name for name, url in self.urls.items() if url == request.full_url)
        return Response(self.bodies[name], request.full_url)


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.area = tempfile.TemporaryDirectory(prefix="world-engine-synthetic-artifacts-")
        cls.root = Path(cls.area.name)
        cls.have_ffmpeg = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
        cls.movie = b"SYNTHETIC_NOT_VIDEO"
        if cls.have_ffmpeg:
            target = cls.root / "synthetic-cpu.mp4"
            result = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i",
                                     "color=c=0x193652:s=1080x1920:r=30", "-frames:v", "150", "-an",
                                     "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35", "-threads", "2",
                                     "-pix_fmt", "yuv420p", str(target)], capture_output=True, timeout=120)
            if result.returncode:
                raise RuntimeError("SYNTHETIC_CPU_FIXTURE_ENCODING_FAILED")
            cls.movie = target.read_bytes()
        cls.bodies = {v.MOVIE: cls.movie, **{name: png(index) for index, name in enumerate(v.PNGS)}}
        cls.bodies["SHA256SUMS"] = "".join(hashlib.sha256(body).hexdigest() + "  " + name + "\n"
                                           for name, body in sorted(cls.bodies.items())).encode()
        cls.anchor = hashlib.sha256(cls.bodies["SHA256SUMS"]).hexdigest()
        cls.urls = {name: "https://www.dropbox.com/scl/fi/SYNTHETIC/" + name + "?rlkey=SYNTHETIC_PRIVATE&dl=1"
                    for name in cls.bodies}

    @classmethod
    def tearDownClass(cls):
        cls.area.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.public = self.base / "public-review"
        self.public.mkdir()
        for name, body in self.bodies.items():
            (self.public / name).write_bytes(body)

    def check_error(self, code, function, *args, **kwargs):
        with self.assertRaisesRegex(v.ArtifactError, "^" + code + "$"):
            function(*args, **kwargs)

    def test_source_anchor_required_before_self_declared_hashes(self):
        self.check_error("SOURCE_SHA256SUMS_ANCHOR_REQUIRED", v.parse_sums, self.bodies["SHA256SUMS"], "")
        self.check_error("SOURCE_SHA256SUMS_ANCHOR_MISMATCH", v.parse_sums, self.bodies["SHA256SUMS"], "0" * 64)

    def test_exact_manifest_names_and_duplicate_rejected(self):
        for body in [self.bodies["SHA256SUMS"] + self.bodies["SHA256SUMS"].splitlines(True)[0],
                     b"0" * 64 + b"  ../private.json\n", b""]:
            self.check_error("SHA256SUMS_INVALID" if body else "SHA256SUMS_EXACT_SIX_REQUIRED",
                             v.parse_sums, body, hashlib.sha256(body).hexdigest())

    def test_public_directory_excludes_receipts_sources_and_diagnostics(self):
        (self.public / "REPORT.json").write_text("PRIVATE SYNTHETIC")
        self.check_error("EXACT_SEVEN_PUBLIC_FILES_REQUIRED", v.verify_public, self.public, self.anchor)

    def test_symlink_and_hardlink_artifacts_rejected(self):
        target = self.public / v.PNGS[0]
        target.unlink()
        target.symlink_to(self.public / v.PNGS[1])
        self.check_error("FILE_ACCESS_FAILED", v.verify_public, self.public, self.anchor)
        target.unlink()
        os.link(self.public / v.PNGS[1], target)
        self.check_error("REGULAR_BOUNDED_SINGLE_LINK_FILE_REQUIRED", v.verify_public, self.public, self.anchor)

    def test_corrupted_download_cannot_pass_own_manifest(self):
        (self.public / v.PNGS[0]).write_bytes(b"SYNTHETIC_CORRUPTION")
        self.check_error("ARTIFACT_SHA256_MISMATCH", v.verify_public, self.public, self.anchor)

    def test_wrong_png_dimensions_rejected_even_with_consistent_anchor(self):
        name = v.PNGS[0]
        (self.public / name).write_bytes(png(width=540))
        body = "".join(hashlib.sha256((self.public / item).read_bytes()).hexdigest() + "  " + item + "\n"
                       for item in sorted(v.EXPECTED - {"SHA256SUMS"})).encode()
        (self.public / "SHA256SUMS").write_bytes(body)
        self.check_error("CHECKPOINT_PNG_DIMENSIONS_INVALID", v.verify_public, self.public, hashlib.sha256(body).hexdigest())

    def test_dropbox_https_and_direct_download_and_redirect_limits(self):
        for url in ["http://www.dropbox.com/s/a?dl=1", "https://evil.example/a", "https://www.dropbox.com/s/a?dl=0",
                    "https://user:secret@www.dropbox.com/s/a?dl=1", "https://www.dropbox.com:444/s/a?dl=1",
                    "https://dropboxusercontent.com.evil.example/a", "https://www.dropbox.com/s/a?dl=1#fragment"]:
            with self.assertRaises(v.ArtifactError):
                v.validate_dropbox_url(url)
        self.assertEqual(v.validate_dropbox_url("https://dl.dropboxusercontent.com/s/SYNTHETIC/movie.mp4"),
                         "https://dl.dropboxusercontent.com/s/SYNTHETIC/movie.mp4")
        handler = v.DropboxRedirect()
        self.assertEqual(handler.max_redirections, 5)
        with self.assertRaises(v.ArtifactError):
            handler.redirect_request(urllib.request.Request(next(iter(self.urls.values()))), None, 302, "Found", {},
                                     "http://127.0.0.1/private")

    def test_synthetic_http_download_is_fresh_private_anchored_and_never_real_claim(self):
        destination = self.base / "download"
        client = SyntheticHTTP(self.bodies, self.urls)
        result = v.download_public(self.urls, destination, self.anchor, opener=client)
        self.assertEqual(result["method"], "SYNTHETIC_HTTP")
        self.assertTrue(result["testOnly"])
        self.assertFalse(result["externalDownloadVerified"])
        self.assertEqual(len(client.calls), 7)
        self.assertEqual(client.calls[0], self.urls["SHA256SUMS"])
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))
        self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(item.stat().st_mode & 0o777 == 0o600 for item in destination.iterdir()))
        self.check_error("FRESH_DOWNLOAD_DIRECTORY_REQUIRED", v.download_public, self.urls, destination, self.anchor, opener=client)

    def test_synthetic_http_anchor_mismatch_stops_before_movie(self):
        client = SyntheticHTTP(self.bodies, self.urls)
        self.check_error("SOURCE_SHA256SUMS_ANCHOR_MISMATCH", v.download_public,
                         self.urls, self.base / "download", "0" * 64, opener=client)
        self.assertEqual(len(client.calls), 1)

    def test_synthetic_http_sha_corruption_does_not_create_success(self):
        bodies = {**self.bodies, v.PNGS[0]: b"SYNTHETIC_BAD_BODY"}
        self.check_error("DOWNLOAD_SHA256_MISMATCH", v.download_public, self.urls, self.base / "download",
                         self.anchor, opener=SyntheticHTTP(bodies, self.urls))

    def test_synthetic_slow_stream_uses_read1_and_enforces_total_deadline(self):
        class Read1OnlyResponse(Response):
            reads = 0

            def read(self, *args):
                raise AssertionError("UNBOUNDED_FILL_READ_FORBIDDEN")

            def read1(self, size):
                self.reads += 1
                return super().read1(size)

        response = Read1OnlyResponse(self.bodies["SHA256SUMS"], self.urls["SHA256SUMS"])
        client = mock.Mock()
        client.open.return_value = response
        with mock.patch.object(v.time, "monotonic", side_effect=[0, 0, 91]):
            self.check_error("DOWNLOAD_SIZE_OR_DEADLINE_EXCEEDED", v.download_public, self.urls,
                             self.base / "slow-download", self.anchor, opener=client)
        self.assertEqual(response.reads, 1)
        self.assertEqual(client.open.call_count, 1)
        self.assertEqual((self.base / "slow-download" / "SHA256SUMS").stat().st_size, 0)

    def test_url_map_duplicate_keys_and_missing_names_rejected(self):
        target = self.base / "urls.json"
        target.write_text('{"SHA256SUMS":"first","SHA256SUMS":"second"}')
        self.check_error("URL_MAP_DUPLICATE_KEY", v.read_urls, target)
        target.write_text("{}")
        self.check_error("URL_MAP_EXACT_SEVEN_REQUIRED", v.read_urls, target)

    def test_private_receipt_never_added_to_public_or_overwritten(self):
        receipt = self.public / "receipt.json"
        with contextlib.redirect_stdout(io.StringIO()):
            code = v.main(["--public-dir", str(self.public), "--sha256sums-sha256", self.anchor,
                           "--receipt", str(receipt)])
        self.assertEqual(code, 2)
        self.assertFalse(receipt.exists())
        receipt = self.base / "receipt.json"
        receipt.write_text("EXISTING_SYNTHETIC")
        with contextlib.redirect_stdout(io.StringIO()):
            code = v.main(["--public-dir", str(self.public), "--sha256sums-sha256", self.anchor,
                           "--receipt", str(receipt)])
        self.assertEqual(code, 2)
        self.assertEqual(receipt.read_text(), "EXISTING_SYNTHETIC")

    def test_real_cpu_synthetic_ffprobe_count_and_full_decode(self):
        if not self.have_ffmpeg:
            self.skipTest("FFmpeg/FFprobe unavailable; no media PASS claimed")
        result = v.verify_public(self.public, self.anchor, decode=True)
        self.assertEqual(result["status"], "ARTIFACT_TECHNICAL_PASS")
        self.assertEqual(result["media"]["decodedFrames"], 150)
        self.assertEqual(result["media"]["ffmpegFullDecode"], "PASS")
        self.assertFalse(result["hardwareVerified"])
        self.assertEqual(result["visualQuality"], "UNREVIEWED")
        self.assertFalse(result["externalDownloadVerified"])

    def test_wrong_ffprobe_contract_cannot_pass_on_hash_alone(self):
        bad = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 540, "height": 960}],
               "format": {"duration": "5"}}
        process = subprocess.CompletedProcess([], 0, json.dumps(bad).encode(), b"")
        with mock.patch.object(v.shutil, "which", return_value="SYNTHETIC_VERIFIER"), mock.patch.object(v.subprocess, "run", return_value=process):
            self.check_error("VIDEO_65422_CONTRACT_MISMATCH", v.verify_public, self.public, self.anchor)


if __name__ == "__main__":
    unittest.main()
