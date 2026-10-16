"""Controller/claim tests with explicit fake hardware, never NVIDIA evidence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import studio_controller as controller
from studio_common import canonical_sha256, load_original, recovery_root

DIGEST = "sha256:" + "b" * 64


class FakeBackend:
    """In-memory CPU test double; reports no real hardware verification."""
    def __init__(self):
        self.jobs, self.calls = {}, []
        self.allowed = True
        self.fail_start = False

    def default_plan(self, profile):
        return json.loads((recovery_root() / "verified-front-data-v4-recovery/PARENT_PLAN_80S.json").read_text())

    def bind_render_image(self, plan, profile, image_digest):
        value = deepcopy(plan)
        value["renderProfile"]["imageDigest"] = image_digest
        return value

    def validate_render_plan(self, plan, profile, image_digest=None):
        return plan

    def preflight(self, plan, profile, **kwargs):
        return {"status": "PASS" if self.allowed else "BLOCKED", "renderAllowed": self.allowed,
                "checks": [{"name": "FAKE_HARDWARE", "status": "PASS" if self.allowed else "BLOCKED"}],
                "gpuRenderingVerified": False}

    def _new(self, request_id):
        job_id = "studio-" + hashlib.sha256(request_id.encode()).hexdigest()[:32]
        state = {"jobId": job_id, "state": "QUEUED", "phase": "QUEUED", "totalScenes": 12,
                 "completedScenes": 0, "processedFrames": 0, "totalFrames": 2400,
                 "elapsedSeconds": 0, "gpuRenderingVerified": False, "errorCode": None}
        self.jobs[job_id] = state
        return deepcopy(state)

    def start_studio_job(self, plan, profile, approval_path, audio, request_id, **kwargs):
        approval_path = Path(approval_path)
        approval = json.loads(approval_path.read_text())
        self.calls.append(("GPU", deepcopy(plan), approval, stat.S_IMODE(approval_path.stat().st_mode)))
        if self.fail_start:
            raise RuntimeError("private upstream exception that must never reach the client")
        return self._new(request_id)

    def studio_status(self, job_id, **kwargs):
        return deepcopy(self.jobs[job_id])

    def start_studio_revision(self, parent_job_id, audio, request_id, **kwargs):
        self.calls.append(("SFX", parent_job_id, deepcopy(audio)))
        return self._new(request_id)

    def start_studio_recovery(self, parent_job_id, approval_path, request_id, **kwargs):
        approval = json.loads(Path(approval_path).read_text()) if approval_path is not None else None
        self.calls.append(("RECOVERY", parent_job_id, approval))
        return self._new(request_id)


class StudioControllerTests(unittest.TestCase):
    def setUp(self):
        temporary_parent = "/tmp" if os.stat("/tmp").st_uid == 0 else "/workspace"
        self.tmp = tempfile.TemporaryDirectory(prefix="studio-controller-", dir=temporary_parent)
        self.base = Path(self.tmp.name)
        self.exports = self.base / "exports"
        self.exports.mkdir(mode=0o700)
        self.root = self.base / "production"
        self.backend = FakeBackend()
        self.instance = controller.StudioController(control_root=self.root, export_root=self.exports,
                                                   image_digest=DIGEST, backend=self.backend)
        self.prompt = {"schema": "WORLD_ENGINE_STUDIO_PROMPT_V1", "preset": "VERIFIED_FRONT_V4_80S",
                       "title": "Verified production test", "durationSeconds": 80, "profile": "V4_ARCHIVAL_80S"}
        self.value = {"prompt": json.dumps(self.prompt), "durationSeconds": 80, "profile": "V4_ARCHIVAL_80S",
                      "sfx": {"enabled": True, "gain": 0.5}}

    def tearDown(self):
        self.tmp.cleanup()

    def policy(self, **changes):
        policy = {"schema": "WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1",
                  "validUntil": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                  "maxWallSeconds": 600, "maxRetries": 1,
                  "maxCostAmount": "1", "currency": "USD", "gpuHourlyRate": "1"}
        policy.update(changes)
        with self.instance._cache.PrivateTree(self.root) as root:
            with root.lock():
                root.write_json("operator_policy.json", policy, replace=True)
        return policy

    def submitted(self):
        return self.instance.submit(self.value)["submissionId"]

    def running(self):
        self.policy()
        submission_id = self.submitted()
        job = self.instance.start(submission_id, "browser-request-0001", consent=True)
        return submission_id, job["jobId"]

    def completed(self):
        submission_id, job_id = self.running()
        self.backend.jobs[job_id].update(state="COMPLETED", phase="COMPLETED", completedScenes=12, processedFrames=2400)
        return submission_id, job_id

    def export_result(self, job_id):
        relative = "world-engine-export-" + "1" * 24 + "/studio-" + "2" * 24
        public = self.exports / relative
        public.mkdir(parents=True)
        rows = []
        for name in ("WORLD_ENGINE_STUDIO_VIDEO.mp4", "QUALITY_SUMMARY.json", "SHA256SUMS"):
            raw = ("CPU fixture " + name).encode()
            (public / name).write_bytes(raw)
            rows.append({"name": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        self.backend.jobs[job_id]["result"] = {"schema": "WORLD_ENGINE_STUDIO_EXPORT_V1",
            "exportDirectory": relative, "files": rows, "mountedViewReadbackVerified": True,
            "externalDownloadVerified": False, "remotePersistenceVerified": False}
        return public

    def test_pinned_originals_reused(self):
        self.assertTrue(hasattr(load_original("cache"), "PrivateTree"))
        self.assertTrue(hasattr(load_original("production_planner"), "_allocate"))
        with self.assertRaises(RuntimeError):
            load_original("arbitrary_path")

    def test_no_render_on_validation_or_submission(self):
        preflight = self.instance.preflight(self.value)
        self.assertTrue(preflight["valid"])
        self.assertFalse(preflight["ready"])
        self.assertIn("STUDIO_OPERATOR_POLICY_REQUIRED", str(preflight))
        submitted = self.instance.submit(self.value)
        self.assertRegex(submitted["submissionId"], r"^[a-f0-9]{64}$")
        self.assertEqual(self.backend.calls, [])
        self.assertFalse(preflight["gpuRenderingVerified"])

    def test_missing_input_is_explicit(self):
        preflight = self.instance.preflight({"prompt": ""})
        self.assertFalse(preflight["valid"])
        self.assertIn("sceneJson", preflight["error"]["fields"])
        self.assertEqual(self.backend.calls, [])

    def test_missing_hardware_remains_blocked_with_budget(self):
        self.policy()
        self.backend.allowed = False
        gate = self.instance.preflight(self.value)
        self.assertFalse(gate["ready"])
        self.assertFalse(gate["gpuRenderingVerified"])
        with self.assertRaises(controller.StudioError) as error:
            self.instance.start(self.submitted(), "browser-request-0001", consent=True)
        self.assertEqual(error.exception.code, "STUDIO_PREFLIGHT_BLOCKED")
        self.assertEqual(self.backend.calls, [])

    def test_sfx_licenses_and_actual_hashes_are_preflighted(self):
        self.policy()
        normal = self.instance.preflight(self.value)
        check = next(row for row in normal["checks"] if row["name"] == "SFX_LICENSE_AND_FILES")
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["facts"], {"license": "CC0-1.0", "assetCount": 18})
        with mock.patch("studio_audio.verify_assets", side_effect=RuntimeError("SFX_ASSET_HASH_MISMATCH")):
            self.assertFalse(self.instance.preflight(self.value)["ready"])
            with self.assertRaises(controller.StudioError):
                self.instance.start(self.submitted(), "browser-request-0001", consent=True)
        self.assertEqual(self.backend.calls, [])

    def test_public_preflight_and_status_drop_private_backend_fields(self):
        self.policy()
        original_preflight = self.backend.preflight
        def extra(*args, **kwargs):
            value = original_preflight(*args, **kwargs)
            value["checks"][0]["facts"] = {"privatePath": "/private/input.json", "approval": {"approved": True},
                                            "model": "RTX 4080 SUPER", "frames": 2400}
            return value
        self.backend.preflight = extra
        value = self.instance.preflight(self.value)
        self.assertNotIn("/private", json.dumps(value))
        self.assertNotIn("approval", json.dumps(value))
        _, job_id = self.running()
        self.backend.jobs[job_id].update(privatePath="/private/result", phase="/private/unsafe-phase", environment={"value": "private"})
        value = self.instance.status(job_id)
        self.assertEqual(value["phase"], "UNKNOWN")
        self.assertNotIn("/private", json.dumps(value))
        self.assertNotIn("environment", value)

    def test_policy_bounds_and_expiry(self):
        for changes in ({"maxCostAmount": "0.001"}, {"gpuHourlyRate": "0"},
                        {"maxRetries": 3}, {"validUntil": "2020-01-01T00:00:00+00:00"},
                        {"validUntil": "2099-01-01T00:00:00"}):
            with self.subTest(changes=changes):
                self.policy(**changes)
                self.assertFalse(self.instance.preflight(self.value)["ready"])
        self.assertEqual(self.backend.calls, [])

    def test_start_needs_consent_and_preserves_native_approval(self):
        self.policy()
        submission_id = self.submitted()
        with self.assertRaises(controller.StudioError) as error:
            self.instance.start(submission_id, "browser-request-0001")
        self.assertEqual(error.exception.code, "STUDIO_OWNER_CONSENT_REQUIRED")
        self.assertEqual(self.backend.calls, [])
        state = self.instance.start(submission_id, "browser-request-0001", consent=True)
        self.assertFalse(state["gpuRenderingVerified"])
        mode, plan, approval, permissions = self.backend.calls[0]
        self.assertEqual(mode, "GPU")
        self.assertEqual(approval["schema"], "WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1")
        self.assertEqual(approval["planSHA256"], canonical_sha256(plan))
        self.assertEqual(approval["imageDigest"], DIGEST)
        self.assertEqual(permissions, 0o600)
        self.assertEqual(approval["maxWallSeconds"], 600)
        self.assertFalse(self.instance.preflight(self.value)["providerBillingStopControlled"])

    def test_double_tap_and_new_browser_key_never_duplicate(self):
        submission_id, job_id = self.running()
        again = self.instance.start(submission_id, "browser-request-0001", consent=True)
        alias = self.instance.start(submission_id, "browser-request-0002", consent=True)
        self.assertEqual(again["jobId"], job_id)
        self.assertEqual(alias["jobId"], job_id)
        self.assertEqual(len(self.backend.calls), 1)

    def test_concurrent_double_touch_starts_one_job(self):
        self.policy()
        submission_id = self.submitted()
        states, errors = [], []
        barrier = threading.Barrier(2)
        def touch():
            try:
                barrier.wait(timeout=2)
                states.append(self.instance.start(submission_id, "browser-request-0001", consent=True))
            except Exception as error:
                errors.append(error)
        workers = [threading.Thread(target=touch) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(len(states), 2)
        self.assertEqual(states[0]["jobId"], states[1]["jobId"])
        self.assertEqual(len(self.backend.calls), 1)

    def test_idempotency_conflict_does_not_launch(self):
        self.running()
        changed = deepcopy(self.value)
        changed["sfx"]["gain"] = 0.4
        with self.assertRaises(controller.StudioError) as error:
            self.instance.start(self.instance.submit(changed)["submissionId"], "browser-request-0001", consent=True)
        self.assertEqual(error.exception.code, "STUDIO_IDEMPOTENCY_CONFLICT")
        self.assertEqual(len(self.backend.calls), 1)

    def test_active_job_blocks_new_submissions(self):
        self.running()
        changed = deepcopy(self.value)
        changed["sfx"]["gain"] = 0.4
        with self.assertRaises(controller.StudioError) as error:
            self.instance.start(self.instance.submit(changed)["submissionId"], "browser-request-0002", consent=True)
        self.assertEqual(error.exception.code, "STUDIO_JOB_ALREADY_ACTIVE")
        self.assertEqual(len(self.backend.calls), 1)

    def test_unknown_launch_outcome_keeps_claim_and_redacts_error(self):
        self.policy()
        submission_id = self.submitted()
        self.backend.fail_start = True
        with self.assertRaises(controller.StudioError) as error:
            self.instance.start(submission_id, "browser-request-0001", consent=True)
        self.assertEqual(error.exception.code, "STUDIO_RUNTIME_FAILED")
        self.assertNotIn("private upstream", str(error.exception))
        with self.assertRaises(controller.StudioError) as second:
            self.instance.start(submission_id, "browser-request-0001", consent=True)
        self.assertEqual(second.exception.code, "STUDIO_UNRESOLVED_START_CLAIM")
        self.assertEqual(len(self.backend.calls), 1)

    def test_restart_and_browser_disconnect_never_auto_start(self):
        _, job_id = self.running()
        restarted = controller.StudioController(control_root=self.root, export_root=self.exports,
                                                image_digest=DIGEST, backend=self.backend)
        self.assertEqual(restarted.status(job_id)["jobId"], job_id)
        self.assertEqual(len(self.backend.calls), 1)

    def test_revision_is_explicit_sfx_only_with_unchanged_plan(self):
        submission_id, job_id = self.completed()
        # No new paid GPU authorization is necessary for verified silent reuse.
        self.backend.allowed = False
        revised = self.instance.revise(job_id, {"startSeconds": 25, "endSeconds": 35, "prompt": "효과음 꺼줘"})
        self.assertTrue(revised["preflight"]["ready"])
        self.assertFalse(revised["preflight"]["requiresGpu"])
        self.assertEqual(revised["impact"]["invalidatedSceneIds"], [])
        self.assertEqual(len(revised["impact"]["reusedSceneIds"]), 12)
        self.assertEqual(len(self.backend.calls), 1)
        new = self.instance.start(revised["submissionId"], "browser-revision-0001", consent=True)
        self.assertNotEqual(new["jobId"], job_id)
        self.assertEqual([call[0] for call in self.backend.calls], ["GPU", "SFX"])
        with self.instance._cache.PrivateTree(self.root) as root:
            parent = self.instance._read_submission(root, submission_id)
            child = self.instance._read_submission(root, revised["submissionId"])
        self.assertEqual(parent["submission"]["videoPlan"], child["submission"]["videoPlan"])

    def test_visual_revision_is_rejected_precisely(self):
        _, job_id = self.completed()
        with self.assertRaises(Exception) as error:
            self.instance.revise(job_id, {"startSeconds": 25, "endSeconds": 35,
                                         "prompt": "카메라를 더 확대하고 이동을 느리게 해줘"})
        self.assertEqual(error.exception.code, "STUDIO_VISUAL_REVISION_UNSUPPORTED")
        self.assertEqual(len(self.backend.calls), 1)

    def test_resume_explicit_and_preserves_first_approval(self):
        _, job_id = self.running()
        original = deepcopy(self.backend.calls[0][2])
        self.backend.jobs[job_id].update(state="INTERRUPTED", phase="EXPLICIT_RECOVERY_REQUIRED")
        self.policy(maxWallSeconds=3600, maxCostAmount="10", maxRetries=2)
        with self.assertRaises(controller.StudioError) as error:
            self.instance.resume(job_id, "recovery-request-0001")
        self.assertEqual(error.exception.code, "STUDIO_OWNER_CONSENT_REQUIRED")
        resumed = self.instance.resume(job_id, "recovery-request-0001", consent=True)
        self.assertNotEqual(resumed["jobId"], job_id)
        self.assertEqual(self.backend.calls[1][0], "RECOVERY")
        self.assertEqual(self.backend.calls[1][2], original)
        duplicate = self.instance.resume(job_id, "recovery-request-0001", consent=True)
        other_key = self.instance.resume(job_id, "recovery-request-0002", consent=True)
        self.assertEqual(duplicate["jobId"], resumed["jobId"])
        self.assertEqual(other_key["jobId"], resumed["jobId"])
        self.assertEqual(len(self.backend.calls), 2)

    def test_resume_never_restarts_running_or_completed_job(self):
        _, job_id = self.running()
        with self.assertRaises(controller.StudioError):
            self.instance.resume(job_id, "recovery-request-0001", consent=True)
        self.backend.jobs[job_id]["state"] = "COMPLETED"
        with self.assertRaises(controller.StudioError):
            self.instance.resume(job_id, "recovery-request-0002", consent=True)
        self.assertEqual(len(self.backend.calls), 1)

    def test_result_downloads_rehash_but_never_claim_external_sync(self):
        _, job_id = self.completed()
        public = self.export_result(job_id)
        result = self.instance.result(job_id)
        self.assertEqual(len(result["downloads"]), 3)
        self.assertTrue(all(Path(row["path"]).parent == public for row in result["downloads"]))
        self.assertTrue(result["dropbox"]["mountReadbackVerified"])
        self.assertEqual(result["dropbox"]["relativeDirectory"], str(public.relative_to(self.exports)))
        self.assertFalse(result["dropbox"]["externalDownloadVerified"])
        self.assertTrue(result["userVideoReviewRequired"])

    def test_damaged_result_never_downloads(self):
        _, job_id = self.completed()
        public = self.export_result(job_id)
        (public / "WORLD_ENGINE_STUDIO_VIDEO.mp4").write_bytes(b"damaged")
        with self.assertRaises(controller.StudioError) as error:
            self.instance.result(job_id)
        self.assertEqual(error.exception.code, "STUDIO_EXPORT_HASH_MISMATCH")

    def test_unexpected_internal_result_file_is_rejected(self):
        _, job_id = self.completed()
        public = self.export_result(job_id)
        (public / "internal.log").write_text("private diagnostics")
        with self.assertRaises(controller.StudioError) as error:
            self.instance.result(job_id)
        self.assertEqual(error.exception.code, "STUDIO_EXACT_PUBLIC_ALLOWLIST_REQUIRED")

    def test_shared_private_state_is_rejected_without_chmod_repair(self):
        unsafe = self.base / "unsafe"
        unsafe.mkdir(mode=0o777)
        unsafe.chmod(0o777)
        with self.assertRaises(Exception):
            controller.StudioController(control_root=unsafe, export_root=self.exports, image_digest=DIGEST, backend=self.backend)
        self.assertEqual(stat.S_IMODE(unsafe.stat().st_mode), 0o777)


if __name__ == "__main__":
    unittest.main()
