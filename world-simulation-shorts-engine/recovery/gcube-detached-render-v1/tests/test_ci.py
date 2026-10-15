"""New detached CLI packaging controls; every external operation is mocked."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("detached_ci_test", HERE / "ci.py")
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
TAG = "rtx4080s-2f9158b-12345-1"
DIGEST = "sha256:" + "a" * 64
CONFIG = "sha256:" + "b" * 64


class DetachedCISafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="detached-ci-test-"); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {"RESULT_CI_STATE": str(self.root / "state.json"), "RUNNER_TEMP": str(self.root),
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REPOSITORY": "dimon3898-sys/yeonhwarok-free", "RESULT_REPOSITORY_PRIVATE": "false",
            "RESULT_RUNNER_LABEL": "ubuntu-24.04", "RESULT_PHASE": "build", "GITHUB_REF": "refs/heads/" + ci.BRANCH,
            "GITHUB_SHA": "c" * 40, "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1", "RESULT_PUBLISHED_TAG": TAG,
            "RESULT_PUBLISHED_DIGEST": DIGEST, "GITHUB_OUTPUT": str(self.root / "outputs")}
        self.addCleanup(patch.stopall); patch.dict(os.environ, self.env, clear=True).start()
        self.command = Mock(side_effect=AssertionError("unexpected command"))
        patch.object(ci, "run", self.command).start(); patch.object(ci.controls, "run", self.command).start()
        self.process = patch.object(ci.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")).start()
        self.network = patch.object(ci.urllib.request, "urlopen", side_effect=AssertionError("network forbidden")).start()
        self.old = SimpleNamespace(require_space=Mock(return_value={"freeBytes": 22 * 1024**3}), check_image=Mock(return_value={"status": "PASS"}), login=Mock())
        patch.object(ci, "helpers", return_value=self.old).start(); patch.object(ci.controls, "helpers", return_value=self.old).start()
        self.registry = Mock(); self.registry.check_tag.return_value = {"status": "TAG_UNUSED"}
        self.registry.inspect_digest.return_value = {"digest": DIGEST, "configDigest": CONFIG}
        module = ModuleType("registry_guard"); module.RegistryGuard = lambda: self.registry
        module.validate_tag = lambda x: x; module.validate_digest = lambda x: x
        patch.dict(sys.modules, {"registry_guard": module}).start()

    def seed(self, **overrides):
        value = ci.state(); value.update(tag=TAG, image=ci.IMAGE + ":" + TAG, configDigest=CONFIG,
            focusedTests={"exitCode": 0}, verification="PASS", secretScan={"status": "PASS", "findings": 0})
        value.update(overrides); ci.save(value); return value

    def facts(self):
        labels = {"org.opencontainers.image.revision": "2f9158ba2df2a9f58362fb0b17118b8dc19f705a",
            "world-engine.diagnostics.source-revision": ci.DIAGNOSTIC_SOURCE,
            "world-engine.detached-render.source-revision": self.env["GITHUB_SHA"], "world-engine.detached-render.parent-digest": ci.PARENT_DIGEST}
        labels.update({"world-engine." + part + ".source-revision": ci.PARENT_SOURCE for part in ("storage", "result", "render-export")})
        return {"Id": CONFIG, "Size": 100, "Os": "linux", "Architecture": "amd64", "Config": {"Labels": labels, "Env": ["PATH=/usr/bin"],
            "Entrypoint": ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "/opt/world-engine-storage-fix/launch.py"]}}

    def test_free_public_standard_exact_branch_required(self):
        self.assertEqual(ci.controls.PATCHES, {})
        for key, value in [("RUNNER_ENVIRONMENT", "self-hosted"), ("RESULT_REPOSITORY_PRIVATE", "true"),
                ("RESULT_RUNNER_LABEL", "larger-runner"), ("GITHUB_REF", "refs/heads/main")]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(RuntimeError): ci.preflight()
        self.old.require_space.assert_not_called(); self.command.assert_not_called()

    def test_no_existing_runtime_file_changes_are_allowlisted(self):
        def git(args, **kwargs):
            if args[1] == "rev-parse": return self.env["GITHUB_SHA"]
            if args[1] == "diff": return changed
            return ""
        self.command.side_effect = git
        for changed in ("renderer.py", "world-simulation-shorts-engine/recovery/gcube-storage-fix-v1/storage.py"):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError): ci.preflight()
        changed = ci.NAMESPACE + "/job_manager.py"
        ci.preflight(); self.assertEqual(ci.state()["tag"], TAG)

    def test_manifest_pins_three_new_modules_verifier_and_parent_contracts(self):
        result = ci.manifest()
        self.assertEqual(set(result["files"]), {*ci.MODULES, "verify_artifacts.py"})
        self.assertEqual(result["files"]["verify_artifacts.py"], ci.VERIFIER_SHA)
        self.assertEqual(len(result["inheritedSources"]), 7)
        self.assertEqual(len(result["inheritedManifests"]), 4)
        self.assertEqual(result["sourceCommit"], self.env["GITHUB_SHA"])
        self.assertEqual(result["parentDigest"], ci.PARENT_DIGEST)
        original = ci.sha
        with patch.object(ci, "sha", side_effect=lambda p: "0" * 64 if Path(p).name == "verify_artifacts.py" else original(p)):
            with self.assertRaisesRegex(RuntimeError, "PINNED_VERIFIER_REQUIRED"): ci.manifest()

    def test_only_explicit_cli_files_and_manifest_enter_context(self):
        self.seed(); ci.stage(); context = Path(ci.state()["context"])
        self.assertFalse(context.is_relative_to(ci.REPO))
        self.assertEqual(set(p.name for p in context.iterdir()), {*ci.MODULES, "verify_artifacts.py", "Dockerfile", "JOB_FILES.json"})
        (context / ".env").write_text("not a credential")
        with self.assertRaisesRegex(RuntimeError, "WHITELIST"): ci.build()
        self.process.assert_not_called()

    def test_bad_unit_result_prevents_staging(self):
        self.seed(focusedTests={"exitCode": 1})
        with self.assertRaisesRegex(RuntimeError, "FOCUSED_TESTS_REQUIRED"): ci.stage()
        self.process.assert_not_called()

    def test_image_labels_preserve_all_parent_source_revisions(self):
        self.command.side_effect = None; self.command.return_value = json.dumps([self.facts()]); ci.inspect_image("synthetic")
        for key in self.facts()["Config"]["Labels"]:
            value = self.facts(); value["Config"]["Labels"][key] = "wrong"
            self.command.return_value = json.dumps([value])
            with self.subTest(key=key), self.assertRaises(RuntimeError): ci.inspect_image("synthetic")

    def test_actual_manifest_difference_rejects_image(self):
        self.command.side_effect = None; value = ci.manifest(); value["files"]["job_manager.py"] = "0" * 64
        self.command.return_value = json.dumps(value)
        with self.assertRaisesRegex(RuntimeError, "SOURCE_HASH_MISMATCH"): ci.image_hashes("synthetic")

    def test_secret_or_verification_failure_prevents_publish(self):
        for overrides in [{"verification": "FAIL"}, {"secretScan": {"status": "PASS", "findings": 1}}]:
            self.seed(**overrides)
            with self.assertRaises(RuntimeError): ci.publish()
        self.old.login.assert_not_called(); self.registry.check_tag.assert_not_called()

    def test_two_no_overwrite_guards_and_isolated_auth_cleanup(self):
        self.seed(); own = self.root / "own-auth"; own.mkdir(); (own / "config.json").write_text("synthetic")
        unrelated = self.root / "old-auth"; unrelated.mkdir(); (unrelated / "config.json").write_text("preserved")
        self.old.login.return_value = (own, {})
        self.registry.check_tag.side_effect = [{"status": "TAG_UNUSED"}, RuntimeError("TAG_ALREADY_EXISTS")]
        with self.assertRaisesRegex(RuntimeError, "TAG_ALREADY_EXISTS"): ci.publish()
        self.assertFalse(own.exists()); self.assertEqual((unrelated / "config.json").read_text(), "preserved")
        self.command.assert_not_called()

    def test_independent_pull_is_not_ready_on_parent_or_job_hash_mismatch(self):
        self.seed(); own = self.root / "own-auth"; own.mkdir(); self.old.login.return_value = (own, {})
        self.command.side_effect = None
        with patch.object(ci.controls, "inspect_image", return_value=self.facts()), patch.object(ci.controls, "image_hashes", side_effect=RuntimeError("HASH_MISMATCH")):
            with self.assertRaises(RuntimeError): ci.pull()
        self.assertIs(ci.state()["pullVerified"], False)
        self.old.check_image.assert_called_once_with(ci.IMAGE + "@" + DIGEST, hashes_only=True)

    def test_docker_adds_no_automatic_entrypoint_service_or_dependencies(self):
        text = (HERE / "Dockerfile").read_text(); self.assertIn("FROM " + ci.BASE, text)
        for forbidden in ("ENTRYPOINT [", "HEALTHCHECK --", "EXPOSE ", "apt-get", "pip ", "npm ", "COPY repo", "ARG GH_TOKEN"):
            self.assertNotIn(forbidden, text)
        self.assertIn("test ! -e /var/lib/world-engine-private/engine/job-control-v1", text)

    def test_real_cli_smoke_requires_empty_clear_and_not_started_states(self):
        inspect = {"schema": "WORLD_ENGINE_EXISTING_CAPTURE_INSPECTION_V1", "status": "CLEAR", "gpuExecuted": False, "renderAllowed": False}
        status = {"schema": "WORLD_ENGINE_DETACHED_STATUS_V1", "state": "NOT_STARTED", "gpuRenderingVerified": False, "renderAllowed": False}
        ci.validate_read_only_result("inspect", 0, inspect)
        ci.validate_read_only_result("status", 0, status)
        for action, code, body in [("inspect", 0, {}), ("inspect", 2, {**inspect, "status": "BLOCKED"}),
            ("inspect", 0, {**inspect, "gpuExecuted": True}), ("status", 0, {**status, "state": "QUEUED"}),
            ("status", 0, {**status, "gpuRenderingVerified": True}), ("start", 0, status)]:
            with self.subTest(action=action, body=body), self.assertRaises(RuntimeError): ci.validate_read_only_result(action, code, body)

    def test_png_builder_fixture_is_pinned_and_staged_outside_checkout(self):
        self.seed(); destination = ci.prepare_unit_context()
        self.assertFalse(destination.is_relative_to(ci.REPO))
        self.assertEqual(ci.sha(destination / "cpu-artifact-fixture/tests/test_artifacts.py"), ci.CPU_FIXTURE_SHA)
        self.assertEqual(ci.sha(destination / "cpu-artifact-fixture/verify_artifacts.py"), ci.VERIFIER_SHA)
        self.assertEqual(ci.sha(destination / "verify_artifacts.py"), ci.VERIFIER_SHA)
        self.assertEqual(ci.state()["unitFixture"]["scope"], "REUSED_PNG_BUILDER_ONLY_OLD_SUITE_NOT_EXECUTED")
        original = ci.sha
        with patch.object(ci, "sha", side_effect=lambda p: "0" * 64 if Path(p).name == "test_artifacts.py" else original(p)):
            with self.assertRaisesRegex(RuntimeError, "PINNED_CPU_FIXTURE_REQUIRED"): ci.prepare_unit_context()


if __name__ == "__main__": unittest.main()
