"""Focused bounded-report packaging tests; external operations are mocked."""
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
spec = importlib.util.spec_from_file_location("report_export_ci_test", HERE / "ci.py")
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
TAG = "rtx4080s-2f9158b-12345-1"
DIGEST = "sha256:" + "a" * 64
CONFIG = "sha256:" + "b" * 64


class RenderCISafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="report-ci-test-"); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {"RESULT_CI_STATE": str(self.root / "state.json"), "RUNNER_TEMP": str(self.root),
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REPOSITORY": "dimon3898-sys/yeonhwarok-free",
            "RESULT_REPOSITORY_PRIVATE": "false", "RESULT_RUNNER_LABEL": "ubuntu-24.04", "RESULT_PHASE": "build",
            "GITHUB_REF": "refs/heads/" + ci.BRANCH, "GITHUB_SHA": "c" * 40, "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1",
            "RESULT_PUBLISHED_TAG": TAG, "RESULT_PUBLISHED_DIGEST": DIGEST, "GITHUB_OUTPUT": str(self.root / "outputs")}
        self.addCleanup(patch.stopall); patch.dict(os.environ, self.env, clear=True).start()
        self.command = Mock(side_effect=AssertionError("unexpected external command"))
        patch.object(ci, "run", self.command).start(); patch.object(ci.orchestration, "run", self.command).start()
        self.process = patch.object(ci.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")).start()
        self.network = patch.object(ci.urllib.request, "urlopen", side_effect=AssertionError("network forbidden")).start()
        self.old = SimpleNamespace(require_space=Mock(return_value={"freeBytes": 22 * 1024**3}), check_image=Mock(return_value={"status": "PASS"}), login=Mock())
        patch.object(ci, "helpers", return_value=self.old).start(); patch.object(ci.orchestration, "helpers", return_value=self.old).start()
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
            "world-engine.storage.source-revision": self.env["GITHUB_SHA"], "world-engine.result.source-revision": self.env["GITHUB_SHA"],
            "world-engine.render-export.source-revision": self.env["GITHUB_SHA"], "world-engine.render-export.parent-digest": ci.PARENT_DIGEST,
            "world-engine.diagnostics.source-revision": ci.PARENT_SOURCE, "world-engine.result.helper-source-revision": ci.PARENT_SOURCE}
        return {"Id": CONFIG, "Size": 100, "Os": "linux", "Architecture": "amd64", "Config": {"Labels": labels, "Env": ["PATH=/usr/bin"],
            "Entrypoint": ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", ci.STORAGE + "/launch.py"]}}

    def test_parent_controls_reconfigured_only_for_single_storage_patch(self):
        self.assertEqual(ci.orchestration.PATCHES, {ci.STORAGE_SOURCE: "storage.py"})
        self.assertEqual(ci.orchestration.NAMESPACE, ci.NAMESPACE)
        self.assertEqual(ci.orchestration.BASELINE, ci.BASELINE)
        for key, value in [("RUNNER_ENVIRONMENT", "self-hosted"), ("RESULT_REPOSITORY_PRIVATE", "true"),
                ("RESULT_RUNNER_LABEL", "larger-runner"), ("GITHUB_REF", "refs/heads/main")]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(RuntimeError): ci.preflight()
        self.old.require_space.assert_not_called(); self.command.assert_not_called()

    def test_existing_helper_changes_are_not_allowlisted(self):
        def git(args, **kwargs):
            if args[1] == "rev-parse": return self.env["GITHUB_SHA"]
            if args[1] == "diff": return changed
            return ""
        self.command.side_effect = git
        for changed in ("renderer.py", ci.STORAGE_SOURCE.replace("storage.py", "launch.py")):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError): ci.preflight()
        changed = ci.STORAGE_SOURCE
        ci.preflight(); self.assertEqual(ci.state()["tag"], TAG)

    def test_all_live_manifests_are_consistent_after_storage_update(self):
        values = ci.manifests(); storage = values["STORAGE_FILES.json"]; result = values["RESULT_FILES.json"]; render = values["RENDER_FILES.json"]
        self.assertEqual(storage["previousManifestSha256"], ci.OLD_STORAGE_SHA)
        self.assertEqual(result["previousManifestSha256"], ci.OLD_RESULT_SHA)
        self.assertEqual(result["helperSourceCommit"], ci.PARENT_SOURCE)
        self.assertEqual(result["patchedSources"][ci.STORAGE + "/storage.py"], storage["files"]["storage.py"])
        self.assertNotIn(ci.STORAGE + "/storage.py", result["unchangedSources"])
        self.assertEqual(len(render["unchangedSources"]), 6)
        self.assertEqual(render["inheritedDiagnosticManifestSha256"], ci.OLD_DIAG_SHA)
        self.assertTrue(all(x["sourceCommit"] == self.env["GITHUB_SHA"] and x["parentDigest"] == ci.PARENT_DIGEST for x in values.values()))

    def test_minimal_context_and_bad_test_result_fail_closed(self):
        self.seed(focusedTests={"exitCode": 1})
        with self.assertRaisesRegex(RuntimeError, "FOCUSED_TESTS_REQUIRED"): ci.stage()
        self.seed(); ci.stage(); context = Path(ci.state()["context"])
        self.assertEqual(set(p.name for p in context.iterdir()), {"storage.py", "Dockerfile", "STORAGE_FILES.json", "RESULT_FILES.json", "RENDER_FILES.json"})
        self.assertFalse(context.is_relative_to(ci.REPO))
        (context / ".env").write_text("not a credential")
        with self.assertRaisesRegex(RuntimeError, "WHITELIST"): ci.build()
        self.process.assert_not_called()

    def test_label_and_entrypoint_protection(self):
        self.command.side_effect = None; self.command.return_value = json.dumps([self.facts()]); ci.inspect_image("synthetic")
        for key in self.facts()["Config"]["Labels"]:
            facts = self.facts(); facts["Config"]["Labels"][key] = "wrong"
            self.command.return_value = json.dumps([facts])
            with self.subTest(key=key), self.assertRaises(RuntimeError): ci.inspect_image("synthetic")

    def test_image_contract_mismatch_is_rejected(self):
        self.command.side_effect = None; report = ci.manifests(); report["RENDER_FILES.json"]["storageSha256"] = "0" * 64
        self.command.return_value = json.dumps(report)
        with self.assertRaisesRegex(RuntimeError, "HASH_MISMATCH"): ci.image_hashes("synthetic")

    def test_secret_and_verification_failure_prevent_publish(self):
        for overrides in [{"verification": "FAIL"}, {"secretScan": {"status": "PASS", "findings": 1}}]:
            self.seed(**overrides)
            with self.assertRaises(RuntimeError): ci.publish()
        self.registry.check_tag.assert_not_called(); self.old.login.assert_not_called()

    def test_reused_publisher_checks_tag_twice_and_preserves_old_auth(self):
        self.seed(); own = self.root / "own-auth"; own.mkdir(); (own / "config.json").write_text("synthetic")
        unrelated = self.root / "existing-auth"; unrelated.mkdir(); (unrelated / "config.json").write_text("preserved")
        self.old.login.return_value = (own, {})
        self.registry.check_tag.side_effect = [{"status": "TAG_UNUSED"}, RuntimeError("TAG_ALREADY_EXISTS")]
        with self.assertRaisesRegex(RuntimeError, "TAG_ALREADY_EXISTS"): ci.publish()
        self.assertFalse(own.exists()); self.assertEqual((unrelated / "config.json").read_text(), "preserved")
        self.command.assert_not_called()

    def test_independent_pull_never_ready_on_hash_failure(self):
        self.seed(); auth = self.root / "own-auth"; auth.mkdir(); self.old.login.return_value = (auth, {})
        self.command.side_effect = None
        with patch.object(ci.orchestration, "inspect_image", return_value=self.facts()), patch.object(ci.orchestration, "image_hashes", side_effect=RuntimeError("HASH_MISMATCH")):
            with self.assertRaises(RuntimeError): ci.pull()
        self.assertIs(ci.state()["pullVerified"], False)
        self.old.check_image.assert_called_once_with(ci.IMAGE + "@" + DIGEST, hashes_only=True)

    def test_dockerfile_inherits_runtime_and_installs_no_dependencies(self):
        text = (HERE / "Dockerfile").read_text(); self.assertIn("FROM " + ci.BASE, text)
        self.assertNotIn("ENTRYPOINT [", text); self.assertNotIn("HEALTHCHECK --", text)
        for forbidden in ("apt-get", "pip ", "npm ", "COPY repo", "ARG GH_TOKEN", "chmod /world-storage"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__": unittest.main()
