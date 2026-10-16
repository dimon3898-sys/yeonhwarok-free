"""Actual short CPU FFmpeg fixtures, not NVIDIA or historical footage."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location("universal_test_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compose = load("compose")
delivery = load("delivery")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable")
class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The preserved production storage adapter rejects untrusted ancestors.
        # This managed host maps /tmp's owner to nobody; use the owned checkout.
        production_private = Path("/var/lib/world-engine-private/engine")
        private_base = production_private if production_private.is_dir() and os.access(production_private, os.W_OK) else HERE.parents[2]
        cls.temporary = tempfile.TemporaryDirectory(prefix=".world-universal-media-", dir=private_base)
        cls.root = Path(cls.temporary.name)
        cls.originals = []
        for index in range(2):
            target = cls.root / f"fixture-{index}.mp4"
            command = ["ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i", "testsrc2=size=64x96:rate=10",
                       "-frames:v", "10", "-vf", f"hue=h={index * 90}", "-c:v", "libx264", "-threads", "1", "-preset", "ultrafast",
                       "-crf", "18", "-g", "10", "-bf", "0", "-pix_fmt", "yuv420p", str(target)]
            subprocess.run(command, check=True, capture_output=True)
            cls.originals.append(target)
        cls.plan = {"durationSeconds": 2, "fps": 10, "resolution": {"width": 64, "height": 96},
                    "scenes": [{"sceneId": "scene-a", "startFrame": 0, "endFrame": 10},
                               {"sceneId": "scene-b", "startFrame": 10, "endFrame": 20}]}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="case-", dir=self.root))
        self.segments = [{**scene, "path": str(path), "sha256": compose.digest_file(path)}
                         for scene, path in zip(self.plan["scenes"], self.originals)]

    def complete(self, name="composition", plan=None, segments=None):
        return compose.compose_segments(plan or self.plan, segments or self.segments, self.work / name)

    def test_actual_full_decode_stream_copy_and_exact_sequence(self):
        result = self.complete()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["mode"], "VERIFIED_STREAM_COPY")
        self.assertEqual(result["decoded"]["frames"], 20)
        self.assertEqual(result["summary"]["visualContinuity"], "UNREVIEWED")
        self.assertEqual(set(Path(result["publicDir"]).iterdir()), {Path(result["publicDir"]) / name for name in delivery.PUBLIC})
        self.assertFalse(result["summary"]["finalPromotion"])

    def test_cache_segment_verification_uses_actual_decode_and_edge_hashes(self):
        facts = compose.verify_segment(self.originals[0], self.plan["scenes"][0], self.plan)
        self.assertTrue(facts["frameCountVerified"])
        self.assertTrue(facts["fullDecodeVerified"])
        self.assertFalse(facts["gpuVerified"])
        self.assertEqual(facts["frames"], 10)
        self.segments[0]["boundaryFrames"] = facts["boundaryFrames"]
        self.assertEqual(self.complete()["technical"], "PASS")

    def test_actual_nonzero_pts_normalized_without_changed_pixels(self):
        offset = self.work / "offset.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", "-i", str(self.originals[1]), "-c", "copy",
                        "-output_ts_offset", "3", str(offset)], check=True, capture_output=True)
        self.segments[1].update(path=str(offset), sha256=compose.digest_file(offset))
        result = self.complete()
        self.assertEqual(result["mode"], "LOSSLESS_NORMALIZE_THEN_COPY")
        self.assertEqual(result["decoded"]["frames"], 20)

    def test_wrong_sha_quarantines_and_preserves_originals(self):
        self.segments[0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(compose.ComposeError, "SEGMENT_SHA256_MISMATCH"):
            self.complete()
        self.assertTrue((self.work / "composition/COMPOSE_FAILED.json").is_file())
        self.assertFalse((self.work / "composition/public-review").exists())
        self.assertTrue(all(path.is_file() for path in self.originals))

    def test_scene_order_gap_duplicate_and_length_are_rejected(self):
        for mutate in (lambda rows: rows.reverse(), lambda rows: rows[1].update(startFrame=11),
                       lambda rows: rows[1].update(sceneId="scene-a"), lambda rows: rows[1].update(endFrame=19)):
            rows = copy.deepcopy(self.segments)
            mutate(rows)
            with self.assertRaises(compose.ComposeError):
                compose.compose_segments(self.plan, rows, self.work / "never-created")
            self.assertFalse((self.work / "never-created").exists())

    def test_actual_rendered_edge_receipt_mismatch_is_rejected(self):
        self.segments[0]["boundaryFrames"] = {"algorithm": "DECODED_RGB24_SHA256", "first": "0" * 64, "last": "0" * 64}
        with self.assertRaisesRegex(compose.ComposeError, "SEGMENT_RENDERED_EDGE_HASH_MISMATCH"):
            self.complete()

    def test_requested_boundary_state_hashes_are_separate_from_pixels(self):
        plan = copy.deepcopy(self.plan)
        plan["scenes"][0]["boundaryEndSHA256"] = "a" * 64
        plan["scenes"][1]["boundaryStartSHA256"] = "a" * 64
        result = self.complete(plan=plan)
        self.assertEqual(result["summary"]["boundaryStateContract"], "PASS")
        self.assertNotEqual(result["segments"][0]["decoded"]["last"], result["segments"][1]["decoded"]["first"])
        self.assertEqual(result["summary"]["visualContinuity"], "UNREVIEWED")

    def test_changed_requested_boundary_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["scenes"][0]["boundaryEndSHA256"] = "a" * 64
        plan["scenes"][1]["boundaryStartSHA256"] = "b" * 64
        with self.assertRaisesRegex(compose.ComposeError, "REQUESTED_SCENE_BOUNDARY_STATE_MISMATCH"):
            self.complete(plan=plan)

    def test_nested_requested_boundary_contract_canonical_order(self):
        plan = copy.deepcopy(self.plan)
        plan["scenes"][0]["boundaryEnd"] = {"globalFrame": 10, "camera": {"x": 1, "y": 2}}
        plan["scenes"][1]["boundaryStart"] = {"camera": {"y": 2, "x": 1}, "globalFrame": 10}
        self.assertEqual(self.complete(plan=plan)["summary"]["boundaryStateContract"], "PASS")
        plan["scenes"][1]["boundaryStart"]["globalFrame"] = 11
        with self.assertRaisesRegex(compose.ComposeError, "REQUESTED_SCENE_BOUNDARY_STATE_MISMATCH"):
            self.complete(name="different-boundary", plan=plan)

    def test_all_black_real_clip_is_quarantined(self):
        black = self.work / "black.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i", "color=black:size=64x96:rate=10",
                        "-frames:v", "10", "-c:v", "libx264", "-threads", "1", "-preset", "ultrafast", "-g", "10", "-bf", "0",
                        "-pix_fmt", "yuv420p", str(black)], check=True, capture_output=True)
        self.segments[1].update(path=str(black), sha256=compose.digest_file(black))
        with self.assertRaisesRegex(compose.ComposeError, "NEAR_BLACK_MAP_FRAME_DETECTED"):
            self.complete()
        self.assertTrue((self.work / "composition/COMPOSE_FAILED.json").is_file())
        self.assertFalse((self.work / "composition/public-review").exists())

    def test_existing_output_is_never_overwritten(self):
        result = self.complete()
        original = Path(result["path"]).read_bytes()
        with self.assertRaisesRegex(compose.ComposeError, "FRESH_COMPOSITION_DIRECTORY_REQUIRED"):
            self.complete()
        self.assertEqual(Path(result["path"]).read_bytes(), original)

    def test_corrupt_bitstream_not_admitted(self):
        corrupt = self.work / "corrupt.mp4"
        corrupt.write_bytes(self.originals[0].read_bytes()[:100])
        self.segments[0].update(path=str(corrupt), sha256=compose.digest_file(corrupt))
        with self.assertRaises(compose.ComposeError):
            self.complete()
        self.assertTrue((self.work / "composition/COMPOSE_FAILED.json").is_file())

    @unittest.skipUnless(os.geteuid() == 1000 and os.getegid() == 1000, "Production storage adapter requires UID/GID 1000")
    def test_actual_export_reuses_storage_checks_and_readback(self):
        result = self.complete()
        mount = self.work / "mounted-dropbox-view"
        mount.mkdir(mode=0o700)
        exported = delivery.export_video(self.plan, result, mount)
        self.assertTrue(exported["mountedViewReadbackVerified"])
        self.assertFalse(exported["externalDownloadVerified"])
        self.assertFalse(exported["remotePersistenceVerified"])
        target = mount / exported["exportDirectory"]
        self.assertEqual(set(item.name for item in target.iterdir()), delivery.PUBLIC)
        self.assertEqual(compose.digest_file(target / compose.MOVIE), result["sha256"])
        second = delivery.export_video(self.plan, result, mount)
        self.assertNotEqual(second["exportDirectory"], exported["exportDirectory"])
        self.assertTrue(target.is_dir())

    def test_public_internal_file_is_blocked(self):
        result = self.complete()
        (Path(result["publicDir"]) / "INTERNAL.json").write_text("{}")
        mount = self.work / "mounted"
        mount.mkdir()
        with self.assertRaisesRegex(delivery.DeliveryError, "EXACT_PUBLIC_ALLOWLIST_REQUIRED"):
            delivery.export_video(self.plan, result, mount)

    def test_public_safe_summary_rejects_freeform_string_even_with_new_hash(self):
        result = self.complete()
        root = Path(result["publicDir"])
        summary = json.loads((root / compose.SUMMARY).read_text())
        summary["compositionMode"] = "private diagnostic text"
        (root / compose.SUMMARY).write_text(json.dumps(summary))
        (root / "SHA256SUMS").write_text("".join(f"{compose.digest_file(root / name)}  {name}\n" for name in (compose.MOVIE, compose.SUMMARY)))
        anchor = compose.digest_file(root / "SHA256SUMS")
        with self.assertRaisesRegex(delivery.DeliveryError, "PUBLIC_SAFE_QA_SUMMARY_INVALID"):
            delivery._public_manifest(root, anchor)

    def _fake_download(self, result, *, corrupt=False, status=200):
        source = Path(result["publicDir"])
        urls = {name: "https://www.dropbox.com/s/mock/" + name + "?dl=1" for name in delivery.PUBLIC}
        class Response(io.BytesIO):
            def __init__(self, url, body):
                super().__init__(body)
                self.status = status
                self.headers = {"Content-Length": str(len(body))}
                self.url = url
            def geturl(self):
                return self.url
        class Client:
            def open(self, request, timeout):
                filename = request.full_url.split("/")[-1].split("?")[0]
                body = (source / filename).read_bytes()
                return Response(request.full_url, body + b"bad" if corrupt else body)
        return urls, Client()

    def test_mock_download_hash_checked_but_never_claims_external_delivery(self):
        result = self.complete()
        urls, client = self._fake_download(result)
        verified = delivery.verify_external(result["publicDir"], urls, self.work / "download", result["sha256SumsSHA256"], opener=client)
        self.assertEqual(verified["status"], "SYNTHETIC_ONLY")
        self.assertFalse(verified["externalDownloadVerified"])
        self.assertTrue(all(row["httpStatus"] == 200 for row in verified["files"]))

    def test_mock_download_bad_sha_or_non200_rejected(self):
        result = self.complete()
        for index, arguments in enumerate(({"corrupt": True}, {"status": 403})):
            urls, client = self._fake_download(result, **arguments)
            with self.assertRaises(delivery.DeliveryError):
                delivery.verify_external(result["publicDir"], urls, self.work / f"download-{index}", result["sha256SumsSHA256"], opener=client)

    def test_non_dropbox_url_is_rejected_without_network(self):
        result = self.complete()
        urls = {name: "http://localhost/private" for name in delivery.PUBLIC}
        with self.assertRaises(Exception):
            delivery.verify_external(result["publicDir"], urls, self.work / "download", result["sha256SumsSHA256"])


class DurationContractTests(unittest.TestCase):
    def test_all_requested_lengths_use_identical_contract_and_half_open_ranges(self):
        for seconds, frames in ((80, 2400), (120, 3600), (180, 5400), (300, 9000), (600, 18000)):
            plan = {"durationSeconds": seconds, "fps": 30, "resolution": [1080, 1920]}
            contract = compose.video_contract(plan)
            self.assertEqual(contract["frames"], frames)
            segments = [{"sceneId": f"scene-{start}", "startFrame": start, "endFrame": min(start + 210, frames),
                         "sha256": "a" * 64} for start in range(0, frames, 210)]
            rows = compose._scene_rows(plan, segments, contract)
            self.assertEqual(sum(row["endFrame"] - row["startFrame"] for row in rows), frames)

    def test_fractional_total_frame_and_invalid_resolution_rejected(self):
        for plan in ({"durationSeconds": "0.15", "fps": 30, "resolution": [1080, 1920]},
                     {"durationSeconds": 80, "fps": 30, "resolution": [1081, 1920]},
                     {"durationSeconds": 80, "fps": True, "resolution": [1080, 1920]}):
            with self.assertRaises(compose.ComposeError):
                compose.video_contract(plan)


if __name__ == "__main__":
    unittest.main()
