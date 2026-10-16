"""Focused new mounted-final and NONPUBLIC scene checkpoint regression."""
import copy
import os
from pathlib import Path
import shutil
import unittest

import test_compose_delivery as base_tests

compose, delivery = base_tests.compose, base_tests.delivery


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and os.geteuid() == 1000 and os.getegid() == 1000,
                     "Actual inherited storage contract requires FFmpeg and UID/GID 1000")
class SceneCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_tests.MediaTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base_tests.MediaTests.tearDownClass.__func__(cls)

    def setUp(self):
        base_tests.MediaTests.setUp(self)
        self.mount = self.work / "mounted-dropbox-view"
        self.mount.mkdir(mode=0o700)

    def checkpoint(self):
        source = self.work / "segment.mp4"
        shutil.copyfile(self.originals[0], source)
        source.chmod(0o600)
        scene = self.plan["scenes"][0]
        facts = compose.verify_segment(source, scene, self.plan)
        segment = {**scene, **facts, "path": str(source), "testOnly": True, "hardwareVerified": False}
        return delivery.export_scene_checkpoint(self.plan, scene, segment, self.mount, private_base=self.work)

    def completed(self):
        composed = compose.compose_segments(self.plan, self.segments, self.work / "composition")
        return delivery.export_video(self.plan, composed, self.mount)

    def test_mounted_completed_result_actual_rehash_pass(self):
        exported = self.completed()
        verified = delivery.verify_mounted_export(exported, self.mount)
        self.assertEqual(verified["reverification"], "MOUNTED_BYTES_REHASHED")
        self.assertTrue(verified["mountedViewReadbackVerified"])
        self.assertFalse(verified["externalDownloadVerified"])

    def test_completed_missing_or_mutated_movie_rejected_without_repair(self):
        exported = self.completed()
        movie = self.mount / exported["exportDirectory"] / compose.MOVIE
        before = movie.read_bytes()
        movie.write_bytes(before[:-1] + bytes([before[-1] ^ 1]))
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_mounted_export(exported, self.mount)
        self.assertNotEqual(movie.read_bytes(), before)
        movie.unlink()  # Only this test's newly generated fixture.
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_mounted_export(exported, self.mount)

    def test_completed_symlink_and_directory_traversal_rejected(self):
        exported = self.completed()
        actual = self.mount / exported["exportDirectory"]
        movie = actual / compose.MOVIE
        renamed = self.work / "copy.mp4"
        movie.rename(renamed)
        movie.symlink_to(renamed)
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_mounted_export(exported, self.mount)
        forged = {**exported, "exportDirectory": "../outside"}
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_mounted_export(forged, self.mount)

    def test_scene_checkpoint_roundtrip_private_anchor_nonpublic_files_only(self):
        checkpoint = self.checkpoint()
        target = self.mount / checkpoint["exportDirectory"]
        self.assertEqual(set(item.name for item in target.iterdir()), {"segment.mp4", "SHA256SUMS"})
        self.assertFalse(checkpoint["publicReview"])
        self.assertFalse(checkpoint["externalDownloadVerified"])
        self.assertFalse(checkpoint["remotePersistenceVerified"])
        self.assertFalse(checkpoint["hardwareVerified"])
        self.assertTrue(Path(checkpoint["privateAnchor"]).is_file())
        verified = delivery.verify_scene_checkpoint(checkpoint, self.mount)
        self.assertEqual(verified["reverification"], "PRIVATE_ANCHOR_AND_MOUNTED_BYTES_REHASHED")

    def test_shared_scene_corruption_and_missing_private_anchor_cannot_self_authenticate(self):
        checkpoint = self.checkpoint()
        target = self.mount / checkpoint["exportDirectory"] / "segment.mp4"
        body = target.read_bytes()
        target.write_bytes(body + b"corrupt")
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_scene_checkpoint(checkpoint, self.mount)
        target.write_bytes(body)
        Path(checkpoint["privateAnchor"]).unlink()
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_scene_checkpoint(checkpoint, self.mount)

    def test_forged_private_anchor_or_job_plan_identity_is_rejected(self):
        checkpoint = self.checkpoint()
        for key, value in (("planSHA256", "0" * 64), ("privateAnchorSHA256", "1" * 64), ("hardwareVerified", True)):
            forged = {**checkpoint, key: value}
            with self.assertRaises(delivery.DeliveryError):
                delivery.verify_scene_checkpoint(forged, self.mount)


if __name__ == "__main__":
    unittest.main()
