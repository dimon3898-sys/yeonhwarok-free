"""CPU-only regression: polling must not overwrite a newly committed result.

Creates only owned temporary private records. No browser, renderer or child
process is started; /proc observation is simulated at the precise race point.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gates_race_review_service", HERE / "studio_service.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)
IMAGE = "sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5"
JOB_ID = "studio-" + "a" * 32
FAKE_PID = 987654321


class StatusRaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="g1-status-race-", dir="/workspace")
        root = Path(self.temporary.name)
        self.controller = service.StudioController(control_root=root / "state", export_root=root / "exports",
            image_digest=IMAGE, allow_software_reference=True)
        with self.controller._cache.PrivateTree(self.controller.control_root) as tree:
            with tree.child("jobs") as jobs:
                jobs.write_json(JOB_ID + ".json", {"jobId": JOB_ID, "referenceOnly": True})
            with tree.child("reference-jobs") as jobs, jobs.child(JOB_ID, create=True):
                pass
        self.running = {"jobId": JOB_ID, "state": "RUNNING", "phase": "FRESH_DRAW_READPIXELS",
                        "pid": FAKE_PID, "processStart": "original-start", "processedFrames": 120}
        self.write_state(self.running)

    def tearDown(self):
        self.temporary.cleanup()

    def write_state(self, value):
        with self.controller._cache.PrivateTree(self.controller.control_root) as tree:
            with tree.child("reference-jobs") as jobs, jobs.child(JOB_ID) as job:
                job.write_json("state.json", value, replace=True)

    def read_state(self):
        with self.controller._cache.PrivateTree(self.controller.control_root) as tree:
            with tree.child("reference-jobs") as jobs, jobs.child(JOB_ID) as job:
                return job.json("state.json")

    def test_worker_terminal_commit_between_initial_read_and_dead_pid_is_preserved(self):
        original_read_text = Path.read_text
        for terminal in ("COMPLETED", "FAILED", "INTERRUPTED"):
            with self.subTest(state=terminal):
                self.write_state(self.running)
                completed = {**self.running, "state": terminal, "phase": "TERMINAL_COMMIT",
                             "processedFrames": 150, "commitMarker": terminal}
                observations = []

                def process_exits_after_commit(path, *args, **kwargs):
                    if path == Path(f"/proc/{FAKE_PID}/stat"):
                        observations.append(str(path))
                        self.write_state(completed)
                        raise FileNotFoundError("simulated worker exited after terminal commit")
                    return original_read_text(path, *args, **kwargs)

                with patch.object(Path, "read_text", process_exits_after_commit), \
                        patch.object(service.controller_module.subprocess, "Popen") as child:
                    actual = self.controller._raw_status(JOB_ID)
                    child.assert_not_called()
                self.assertEqual(len(observations), 1)
                self.assertEqual(actual, completed)
                self.assertEqual(self.read_state(), completed)

    def test_dead_worker_without_terminal_commit_is_recorded_interrupted(self):
        original_read_text = Path.read_text

        def process_missing(path, *args, **kwargs):
            if path == Path(f"/proc/{FAKE_PID}/stat"):
                raise FileNotFoundError("simulated absent worker")
            return original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", process_missing), \
                patch.object(service.controller_module.subprocess, "Popen") as child:
            actual = self.controller._raw_status(JOB_ID)
            child.assert_not_called()
        self.assertEqual(actual["state"], "INTERRUPTED")
        self.assertEqual(actual["errorCode"], "STUDIO_REFERENCE_WORKER_INTERRUPTED")
        self.assertEqual(actual["processedFrames"], 120)
        self.assertEqual(self.read_state(), actual)


if __name__ == "__main__":
    unittest.main()
