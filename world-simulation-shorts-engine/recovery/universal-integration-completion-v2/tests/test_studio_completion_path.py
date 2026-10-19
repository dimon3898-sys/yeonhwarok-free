"""CPU Studio/HTTP/capture wiring; no worker, GPU or external operation.

Real frozen V4 normalization is tested separately from explicit fake policy,
manifest facts, completed-parent state and no-worker routing spies. All private
records are created only in auto-cleaned, test-owned temporary directories.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import re
import secrets
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


controller = load("_completion_path_controller", HERE / "studio_controller.py")
entry = load("_completion_path_entry", HERE / "studio_entry.py")
legacy_http = load("_completion_reused_http_helpers", HERE.parent / "universal-integration-v1/tests/test_studio_entry.py")
DIGEST = "sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da"


def value(**completion_fields):
    return {"prompt": json.dumps({"schema": "WORLD_ENGINE_STUDIO_PROMPT_V2",
        "preset": "VERIFIED_FRONT_V4_80S", "durationSeconds": 80,
        "completion": {"schema": "WORLD_ENGINE_UNIVERSAL_COMPLETION_V2",
                       "profile": "VISUAL_UNIFIED_COMPLETION_V2", **completion_fields}}),
        "durationSeconds": 80, "profile": "V4_ARCHIVAL_80S", "sfx": {"enabled": False}}


def policy_fixture(instance):
    # A test fixture, never an approval for real hardware or external work.
    policy = {"schema": "WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1",
        "validUntil": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "maxWallSeconds": 60, "maxRetries": 0, "maxCostAmount": "1",
        "currency": "USD", "gpuHourlyRate": "1"}
    with instance._cache.PrivateTree(instance.control_root) as root:
        root.write_json("operator_policy.json", policy)


def manifest_facts(bridge):
    actual = bridge._manifest()
    return SimpleNamespace(canonical=actual.canonical, sha=actual.sha, read_regular=actual.read_regular,
        parent_path=actual.parent_path,
        verify_sources=lambda: {"status": "PASS", "manifestSHA256": "1" * 64,
            "previousManifestSHA256": "2" * 64, "registeredCandidateImageDigest": None})


class RealFrozenStudioCompletionTests(unittest.TestCase):
    """Real backend/normalizer; source proof is explicitly isolated test facts."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="world-completion-studio-", dir=HERE.parents[2])
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.controller = controller.StudioController(control_root=root / "studio",
            export_root=root / "exports", image_digest=DIGEST)
        policy_fixture(self.controller)
        self.bridge = self.controller.backend.bridge
        self.source_facts = patch.object(self.bridge, "_manifest", return_value=manifest_facts(self.bridge))
        self.source_facts.start()
        self.addCleanup(self.source_facts.stop)

    def saved(self, identifier):
        with self.controller._cache.PrivateTree(self.controller.control_root) as root:
            return self.controller._read_submission(root, identifier)["submission"]

    def test_real_normalizer_private_submit_and_blocked_preflight_preserve_metadata(self):
        with patch.object(self.controller.backend.parent_backend, "_health",
                side_effect=AssertionError("No hardware inspection is allowed")) as hardware:
            record = self.controller.submit(value())
            hardware.assert_not_called()
        submission = self.saved(record["submissionId"])
        self.assertEqual(submission["videoPlan"]["totalFrames"], 2400)
        self.assertEqual(len(submission["videoPlan"]["scenes"]), 12)
        self.assertEqual(submission["integration"]["profile"], "VISUAL_UNIFIED_V1")
        self.assertEqual(submission["completionV2"]["profile"], "VISUAL_UNIFIED_COMPLETION_V2")
        self.assertEqual(json.loads(submission["promptText"])["completion"]["profile"],
                         "VISUAL_UNIFIED_COMPLETION_V2")
        self.assertFalse(record["preflight"]["ready"])
        codes = {row.get("code") for row in record["preflight"]["checks"]}
        self.assertIn("INTEGRATION_CANDIDATE_NOT_INCLUDED_IN_IMAGE", codes)
        self.assertIn("INTEGRATION_REQUIRED_MODULE_BLOCKED", codes)
        self.assertTrue(any("QUALITY" in str(code) for code in codes))

    def test_completion_changes_submission_and_capture_identity_without_changing_scene(self):
        first = self.controller.submit(value())
        second = self.controller.submit(value(camera={"mode": "PRESERVE_PARENT"}))
        a, b = self.saved(first["submissionId"]), self.saved(second["submissionId"])
        self.assertNotEqual(first["submissionId"], second["submissionId"])
        self.assertEqual(a["videoPlan"], b["videoPlan"])
        self.assertEqual(a["integration"], b["integration"])
        ar = self.bridge.prepare_runtime_request(a, image_digest=DIGEST)
        br = self.bridge.prepare_runtime_request(b, image_digest=DIGEST)
        self.assertNotEqual(ar["captureSignature"], br["captureSignature"])
        self.assertEqual(ar["completionV2"], a["completionV2"])

    def test_direct_start_cannot_bypass_gate_or_create_worker_claim(self):
        stored = self.controller.submit(value())
        with patch.object(self.bridge, "start_studio_job", side_effect=AssertionError("No worker may start")) as worker:
            with self.assertRaises(controller.StudioError) as caught:
                self.controller.start(stored["submissionId"], "completion-test-negative-start", consent=True)
            worker.assert_not_called()
        self.assertEqual(caught.exception.code, "STUDIO_PREFLIGHT_BLOCKED")
        for directory in ("requests", "runs", "jobs"):
            self.assertEqual(list((self.controller.control_root / directory).iterdir()), [])

    def test_bad_completion_fields_are_reported_before_private_submission(self):
        result = self.controller.preflight(value(approved=True))
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"]["code"], "STUDIO_COMPLETION_FIELD_UNSUPPORTED")
        self.assertEqual(list((self.controller.control_root / "submissions").iterdir()), [])

    def test_sfx_child_preserves_metadata_with_explicit_fake_completed_parent(self):
        stored = self.controller.submit(value())
        parent_job = "studio-" + "a" * 32
        with self.controller._cache.PrivateTree(self.controller.control_root) as root:
            with root.child("jobs") as jobs:
                jobs.write_json(parent_job + ".json", {"jobId": parent_job,
                    "submissionId": stored["submissionId"], "requestId": "CPU_TEST_ONLY"})
        completed = {"jobId": parent_job, "state": "COMPLETED"}
        with patch.object(self.controller, "_raw_status", return_value=completed), \
             patch.object(self.controller, "_integration_gate", return_value={"allowed": True}):
            result = self.controller.revise(parent_job, {"startSeconds": 25, "endSeconds": 35,
                                                       "prompt": "효과음 음량 40%"})
        child, parent = self.saved(result["submissionId"]), self.saved(stored["submissionId"])
        for field in ("videoPlan", "integration", "completionV2"):
            self.assertEqual(child[field], parent[field])
        self.assertFalse(result["impact"]["requiresGpu"])
        self.assertEqual(len(result["impact"]["reusedSceneIds"]), 12)
        self.assertEqual(result["preflight"]["scope"], "SFX_ONLY_RECOMPOSE")


class CompletionHTTPTests(unittest.TestCase):
    """Inherited real HTTP authentication/CSRF; controller backend is a fixture."""
    request = legacy_http.HTTPTests.request
    login = legacy_http.HTTPTests.login
    tearDown = legacy_http.HTTPTests.tearDown

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="completion-http-", dir=HERE.parents[2])
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "private"
        root.mkdir(mode=0o700)
        self.owner = root / "owner-code"
        self.password = secrets.token_urlsafe(32)
        self.owner.write_text(self.password)
        self.owner.chmod(0o600)
        self.backend, self.bridge = legacy_http.FakeParentBackend(), legacy_http.FakeBridge()
        test = self
        def factory(**kwargs):
            test.controller = controller.StudioController(**kwargs, backend=test.backend, bridge_module=test.bridge)
            policy_fixture(test.controller)
            return test.controller
        self.app = entry.Application(root, self.owner, Path(self.tmp.name) / "exports", DIGEST,
            controller_factory=factory, gpu_check=lambda: False, initial_origin=legacy_http.ORIGIN)
        self.server = entry.prior.proxy.original.StudioHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def test_authenticated_profile_and_csrf_for_completion_input(self):
        self.assertEqual(self.request("/api/integration/profile")[0], 401)
        cookie, csrf = self.login()
        status, profile, _ = self.request("/api/integration/profile", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(profile["profile"], "VISUAL_UNIFIED_COMPLETION_V2")
        self.assertFalse(profile["renderAllowed"])
        self.assertEqual(self.request("/api/submissions", "POST", value(), cookie)[0], 403)
        status, stored, _ = self.request("/api/submissions", "POST", value(), cookie, csrf)
        self.assertEqual(status, 201, str(stored))
        with self.controller._cache.PrivateTree(self.controller.control_root) as root:
            submission = self.controller._read_submission(root, stored["submissionId"])["submission"]
        self.assertEqual(submission["completionV2"]["profile"], "VISUAL_UNIFIED_COMPLETION_V2")
        self.assertEqual(self.backend.calls, [])
        self.assertEqual(self.bridge.calls, [])

    def test_host_origin_and_browser_job_namespace_remain_separate(self):
        cookie, _ = self.login()
        self.assertGreaterEqual(self.request("/api/integration/profile", cookie=cookie, host="bad.invalid")[0], 400)
        self.assertEqual(self.request("/api/integration/profile", cookie=cookie, origin="https://bad.invalid")[0], 403)
        status, script, _ = self.request("/app.js", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(b"world-studio-completion-v2-job", script)
        self.assertNotIn(b"'world-studio-job'", script)


class CompletionRevisionCaptureTests(unittest.TestCase):
    """Real private capture/index helpers and an explicit no-worker runtime spy."""
    def test_sfx_revision_uses_parent_capture_scope_and_preserves_metadata(self):
        manager = load("_completion_revision_capture_manager", HERE / "execution_manager.py")
        bridge = controller.bridge
        import studio_runtime as frozen
        normalized = controller.contract.normalize_submission(value(), image_digest=DIGEST,
            backend=frozen, parent_normalize=controller.parent.parent.studio_contracts.normalize_submission)
        facts = manifest_facts(bridge)
        with patch.object(bridge, "_manifest", return_value=facts):
            request = bridge.prepare_runtime_request(normalized, image_digest=DIGEST)
        child_job = "studio-" + "b" * 32
        fake = SimpleNamespace(_cache=frozen._cache, JOB=re.compile(r"studio-[a-f0-9]{32}\Z"),
            start_studio_revision=Mock(return_value={"jobId": child_job, "state": "QUEUED", "testOnly": True}))
        auth = SimpleNamespace(_authorize_start=Mock(return_value=None))
        with tempfile.TemporaryDirectory(prefix="completion-revision-scope-", dir=HERE.parents[2]) as tmp:
            root = Path(tmp) / "private"
            with frozen._cache().PrivateTree(root, create=True) as tree:
                with tree.child("runtime_inputs", create=True) as inputs:
                    with inputs.child(request["captureSignature"], create=True) as scope:
                        scope.write_json("INTEGRATION_REQUEST.json", request)
                        scope_path = scope.path
            parent_job = "studio-" + "a" * 32
            with patch.object(manager, "runtime", return_value=fake), \
                 patch.object(manager.parent, "runtime", return_value=fake), \
                 patch.object(manager, "job_scope", return_value=scope_path), \
                 patch.object(manager, "_load", return_value=auth):
                result = manager.revise(parent_job, normalized, "CPU_REVISION_ONLY",
                    control_root=root, export_root=Path(tmp) / "exports", image_digest=DIGEST)
            self.assertTrue(result["testOnly"])
            self.assertEqual(fake.start_studio_revision.call_args.args[:2], (parent_job, normalized["sfx"]))
            self.assertEqual(fake.start_studio_revision.call_args.kwargs["control_root"], scope_path)
            with frozen._cache().PrivateTree(root) as tree:
                with tree.child("runtime_jobs") as jobs:
                    record = jobs.json(child_job + ".json")
            self.assertEqual(record["captureSignature"], request["captureSignature"])
            self.assertEqual(json.loads((scope_path / "INTEGRATION_REQUEST.json").read_bytes())["completionV2"],
                             normalized["completionV2"])


if __name__ == "__main__":
    unittest.main()
