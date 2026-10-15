"""Focused real-filesystem export tests; no GPU, renderer or cloud execution.

The permanent capacity fixture repeats one existing approved diagnostic in the
native hardware report's exact 150-row shape. Media bytes are synthetic file
fixtures and cannot establish a successfully rendered or playable video.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
RECOVERY = HERE.parents[1]
STORAGE_ROOT = Path("/opt/world-engine-storage-fix")
if not (STORAGE_ROOT / "storage.py").is_file():
    STORAGE_ROOT = RECOVERY / "gcube-storage-fix-v1"
DIAGNOSTICS_ROOT = Path("/opt/world-engine-startup-diagnostics")
if not (DIAGNOSTICS_ROOT / "records.py").is_file():
    DIAGNOSTICS_ROOT = RECOVERY / "gcube-diagnostic-image-v1"
sys.path.insert(0, str(DIAGNOSTICS_ROOT))
sys.path.insert(0, str(STORAGE_ROOT))
import storage

BASELINE = "51fba453ce2b9a0fc8ed9e9062bd993fe0489ccc"
BASELINE_STORAGE_SHA256 = "ff8679bdbdf1f42f75b498ee9f68afa701346e4f535043bfdda9663005c130c1"
SOURCE_DIAGNOSTIC_SHA256 = "795e1894e08d9dbe7e6a979da89d97b257ba41a3043776a3e4690377c0d4f9c1"
FIXTURES = HERE / "fixtures"


def native_report(*, status="CAPTURE_TECHNICAL_PASS"):
    diagnostic = json.loads((FIXTURES / "approved_frame_diagnostic.json").read_bytes())
    return {"schema": "RTX_GPU_HARDWARE_CAPTURE_V1", "status": status,
            "signature": "a" * 64, "sourceVerification": {"status": "PASS"},
            "frames": [{"signature": "a" * 64, "frame": frame,
                        "raw_rgba_sha256": "b" * 64, "png_sha256": "c" * 64,
                        "diagnostic": diagnostic} for frame in range(150)]}


class ReportExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_bytes = json.dumps(native_report(), separators=(",", ":")).encode()

    def setUp(self):
        if os.geteuid() != 1000 or os.getegid() != 1000:
            self.skipTest("Real storage contract requires UID/GID 1000")
        root = "/tmp" if Path("/tmp").stat().st_uid in {0, 1000} else "/workspace"
        self.temporary = tempfile.TemporaryDirectory(prefix="report-export-focused-", dir=root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base = self.root / "private"
        self.base.mkdir(mode=0o700)
        self.export = self.root / "shared"
        self.export.mkdir(mode=0o700)
        self.account = SimpleNamespace(pw_uid=1000, pw_gid=1000)

    def session(self, module=storage):
        session = module.StorageSession.create(self.account, base=self.base, export_root=self.export)
        session.preflight()
        return session

    def capture(self, session, report_bytes=None):
        capture = session.private_root / "captures" / ("a" * 64)
        public = capture / "public-review"
        public.mkdir(parents=True, mode=0o700)
        (session.private_root / "captures").chmod(0o700)
        capture.chmod(0o700)
        media = {"PROOF.mp4": b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom" + b"synthetic" * 10,
                 "01_CHECKPOINT.png": b"\x89PNG\r\n\x1a\n" + b"synthetic" * 10}
        for name, body in media.items():
            (public / name).write_bytes(body)
        (public / "SHA256SUMS").write_text("".join(
            hashlib.sha256(body).hexdigest() + "  " + name + "\n" for name, body in sorted(media.items())))
        report = capture / "REPORT.json"
        report.write_bytes(self.report_bytes if report_bytes is None else report_bytes)
        return report, public, media

    def no_completion(self, session):
        self.assertEqual(list((self.export / session.export_name).glob("capture-*/EXPORT_COMPLETE.json")), [])

    def test_provenance_and_native_capacity_fixture(self):
        provenance = json.loads((FIXTURES / "PROVENANCE.json").read_bytes())
        body = (FIXTURES / provenance["fixture"]).read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(), SOURCE_DIAGNOSTIC_SHA256)
        self.assertEqual(provenance["selectedDiagnosticSHA256"], SOURCE_DIAGNOSTIC_SHA256)
        self.assertEqual(provenance["nativeReportFrames"], 150)
        self.assertFalse(provenance["gpuExecuted"])
        self.assertGreater(len(self.report_bytes), 16 * 1024 * 1024)
        self.assertLess(len(self.report_bytes), storage.CAPTURE_REPORT_MAX_BYTES)
        rows = json.loads(self.report_bytes)["frames"]
        self.assertEqual(len(rows), 150)
        self.assertEqual(set(rows[0]), set(provenance["hardwareFrameShape"]))

    def test_immutable_original_reproduces_one_mib_export_failure(self):
        original_path = os.environ.get("WORLD_ENGINE_TEST_BASELINE_STORAGE")
        if original_path:
            body = Path(original_path).read_bytes()
        else:
            repo = RECOVERY.parents[1]
            body = subprocess.run(["git", "show", BASELINE + ":world-simulation-shorts-engine/recovery/gcube-storage-fix-v1/storage.py"],
                                  cwd=repo, check=True, capture_output=True).stdout
        self.assertEqual(hashlib.sha256(body).hexdigest(), BASELINE_STORAGE_SHA256)
        original_path = self.root / "original_storage_51fba45.py"
        original_path.write_bytes(body)
        spec = importlib.util.spec_from_file_location("original_storage_51fba45", original_path)
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        session = self.session(original)
        self.capture(session)
        with self.assertRaises(original.StorageError) as failure:
            session.export_results()
        self.assertEqual(failure.exception.code, "STORAGE_UNAVAILABLE")
        self.assertEqual(failure.exception.facts, {"stage": "EXPORT", "reason": "IO_UNAVAILABLE"})
        self.no_completion(session)

    def test_native_size_report_exports_identical_public_bytes(self):
        session = self.session()
        report, public, media = self.capture(session)
        before = (report.stat().st_size, hashlib.sha256(report.read_bytes()).hexdigest())
        result = session.export_results()
        self.assertEqual(result["status"], "EXPORTED")
        self.assertEqual((result["captures"], result["files"]), (1, 3))
        output = self.export / session.export_name / result["results"][0]["directory"]
        receipt = json.loads((output / "EXPORT_COMPLETE.json").read_bytes())
        self.assertEqual(receipt["status"], "COMPLETE")
        self.assertTrue(receipt["sourceSha256SumsVerified"])
        for name, body in media.items():
            self.assertEqual((output / "public-review" / name).read_bytes(), body)
        self.assertEqual((output / "public-review" / "SHA256SUMS").read_bytes(), (public / "SHA256SUMS").read_bytes())
        self.assertEqual((report.stat().st_size, hashlib.sha256(report.read_bytes()).hexdigest()), before)
        self.assertEqual(sorted(p.name for p in (output / "public-review").iterdir()),
                         ["01_CHECKPOINT.png", "PROOF.mp4", "SHA256SUMS"])
        self.assertFalse(result["remotePersistenceVerified"])
        self.assertFalse(result["externalDownloadVerified"])
        self.assertFalse(result["privateDataAllowed"])

    def test_oversize_report_rejected_before_content_read(self):
        session = self.session()
        report, _, _ = self.capture(session, b"{}")
        with report.open("r+b") as stream:
            stream.truncate(storage.CAPTURE_REPORT_MAX_BYTES + 1)
        inode = report.stat().st_ino
        original_read = storage._read_fd

        def reject_report_read(descriptor, **kwargs):
            if os.fstat(descriptor).st_ino == inode:
                self.fail("Oversize report was read before size admission")
            return original_read(descriptor, **kwargs)

        with mock.patch.object(storage, "_read_fd", side_effect=reject_report_read):
            with self.assertRaises(storage.StorageError) as failure:
                session.export_results()
        self.assertEqual(failure.exception.code, "STORAGE_VALIDATION_FAILED")
        self.assertEqual(failure.exception.facts, {"stage": "EXPORT", "reason": "PUBLIC_SOURCE_INVALID"})
        self.no_completion(session)

    def test_bad_json_and_empty_report_have_no_completion(self):
        for body in (b'{"schema":', b""):
            with self.subTest(body=body):
                session = self.session()
                self.capture(session, body)
                with self.assertRaises(storage.StorageError):
                    session.export_results()
                self.no_completion(session)

    def test_incomplete_failed_or_missing_report_is_not_exported(self):
        for status in ("IN_PROGRESS", "BLOCKED", None):
            with self.subTest(status=status):
                session = self.session()
                report, _, _ = self.capture(session, json.dumps({
                    "schema": "RTX_GPU_HARDWARE_CAPTURE_V1", "status": status,
                    "signature": "a" * 64, "sourceVerification": {"status": "PASS"}}).encode())
                if status is None:
                    report.unlink()  # Only this newly-created synthetic fixture.
                result = session.export_results()
                self.assertEqual(result["status"], "NO_PUBLIC_RESULTS")
                self.no_completion(session)

    def test_native_size_report_does_not_bypass_media_hash_check(self):
        session = self.session()
        _, public, _ = self.capture(session)
        with (public / "PROOF.mp4").open("ab") as stream:
            stream.write(b"corrupted-synthetic-fixture")
        with self.assertRaises(storage.StorageError) as failure:
            session.export_results()
        self.assertEqual(failure.exception.facts["reason"], "SOURCE_HASH_MISMATCH")
        self.no_completion(session)

    def test_small_safe_records_keep_original_bound(self):
        import records
        session = self.session()
        record = records.make_record("NVIDIA", "GPU_HARDWARE_UNAVAILABLE", 2, mode="normal", test_only=True)
        seen = []
        original_read = storage._read_fd

        def note(descriptor, **kwargs):
            seen.append(kwargs.get("limit", 256 * 1024))
            return original_read(descriptor, **kwargs)

        with mock.patch.object(storage, "_read_fd", side_effect=note):
            result = session.export_safe_record(record)
        self.assertEqual(result["status"], "EXPORTED")
        self.assertNotIn(storage.CAPTURE_REPORT_MAX_BYTES, seen)
        self.assertLess((self.export / session.export_name / result["file"]).stat().st_size, 256 * 1024)


if __name__ == "__main__":
    unittest.main()
