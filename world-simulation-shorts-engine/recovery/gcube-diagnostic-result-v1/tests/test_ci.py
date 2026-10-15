"""Diagnostic-result packaging only; all external execution is mocked."""
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
spec = importlib.util.spec_from_file_location("diagnostic_result_ci_test", HERE / "ci.py")
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
TAG = "rtx4080s-2f9158b-12345-1"
DIGEST = "sha256:" + "a" * 64
CONFIG = "sha256:" + "b" * 64


class ResultCISafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="result-ci-test-"); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {"RESULT_CI_STATE": str(self.root / "state.json"), "RUNNER_TEMP": str(self.root),
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REPOSITORY": "dimon3898-sys/yeonhwarok-free",
            "RESULT_REPOSITORY_PRIVATE": "false", "RESULT_RUNNER_LABEL": "ubuntu-24.04",
            "GITHUB_REF": "refs/heads/" + ci.BRANCH, "GITHUB_SHA": "c" * 40,
            "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1", "RESULT_PHASE": "build",
            "RESULT_PUBLISHED_TAG": TAG, "RESULT_PUBLISHED_DIGEST": DIGEST, "GITHUB_OUTPUT": str(self.root / "outputs")}
        self.addCleanup(patch.stopall); patch.dict(os.environ, self.env, clear=True).start()
        self.run = patch.object(ci, "run", side_effect=AssertionError("unexpected command")).start()
        self.process = patch.object(ci.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")).start()
        self.network = patch.object(ci.urllib.request, "urlopen", side_effect=AssertionError("network forbidden")).start()
        self.old = SimpleNamespace(require_space=Mock(return_value={"freeBytes": 22 * 1024**3}), check_image=Mock(return_value={"status": "PASS"}), login=Mock())
        patch.object(ci, "helpers", return_value=self.old).start()
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
        labels = {"org.opencontainers.image.revision": "2f9158ba2df2a9f58362fb0b17118b8dc19f705a", "world-engine.result.parent-digest": ci.PARENT_DIGEST}
        labels.update({"world-engine." + part + ".source-revision": self.env["GITHUB_SHA"] for part in ("diagnostics", "storage", "result")})
        return {"Id": CONFIG, "Size": 100, "Os": "linux", "Architecture": "amd64", "RootFS": {"Layers": []},
            "Config": {"Env": ["PATH=/usr/bin"], "Entrypoint": ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", ci.STORAGE + "/launch.py"], "Labels": labels}}

    def test_free_public_standard_branch_and_run_identity_required(self):
        for key, value in [("RUNNER_ENVIRONMENT", "self-hosted"), ("RESULT_REPOSITORY_PRIVATE", "true"),
            ("RESULT_RUNNER_LABEL", "larger-runner"), ("GITHUB_REF", "refs/heads/main"), ("GITHUB_RUN_ID", "../1")]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(RuntimeError): ci.preflight()
        self.old.require_space.assert_not_called(); self.run.assert_not_called()

    def test_only_two_old_runtime_files_are_allowlisted(self):
        def git(args, **kwargs):
            if args[1] == "rev-parse": return self.env["GITHUB_SHA"]
            if args[1] == "diff": return changed
            return ""
        self.run.side_effect = git
        for changed in (ci.DIAG_SOURCE + "/records.py", ci.STORAGE_SOURCE + "/storage.py", "renderer.py"):
            with self.subTest(path=changed), self.assertRaises(RuntimeError): ci.preflight()
        changed = "\n".join(ci.PATCHES)
        ci.preflight(); self.assertEqual(ci.state()["tag"], TAG)

    def test_combined_manifests_preserve_unchanged_hashes_and_parent_chain(self):
        values = ci.manifests()
        self.assertEqual(values["DIAGNOSTIC_FILES.json"]["previousManifestSha256"], ci.OLD_DIAG_SHA)
        self.assertEqual(values["STORAGE_FILES.json"]["previousManifestSha256"], ci.OLD_STORAGE_SHA)
        self.assertEqual(values["RESULT_FILES.json"]["unchangedSources"], ci.UNCHANGED)
        self.assertEqual(len(values["RESULT_FILES.json"]["patchedSources"]), 2)
        self.assertTrue(all(item["sourceCommit"] == self.env["GITHUB_SHA"] and item["parentDigest"] == ci.PARENT_DIGEST for item in values.values()))
        original_sha = ci.sha
        with patch.object(ci, "sha", side_effect=lambda p: "0" * 64 if Path(p).name == "records.py" else original_sha(p)):
            with self.assertRaisesRegex(RuntimeError, "UNCHANGED_HELPER_HASH_MISMATCH"): ci.manifests()

    def test_explicit_context_contains_only_patches_helper_and_manifests(self):
        self.seed(); ci.stage(); context = Path(ci.state()["context"])
        self.assertFalse(context.is_relative_to(ci.REPO))
        self.assertEqual(set(p.name for p in context.iterdir()), {"startup.py", "launch.py", "recover_existing.py", "Dockerfile", "DIAGNOSTIC_FILES.json", "STORAGE_FILES.json", "RESULT_FILES.json"})
        (context / ".env").write_text("not a credential")
        with self.assertRaisesRegex(RuntimeError, "WHITELIST"): ci.build()
        self.process.assert_not_called()

    def test_failed_unit_tests_prevent_staging(self):
        self.seed(focusedTests={"exitCode": 1})
        with self.assertRaisesRegex(RuntimeError, "FOCUSED_TESTS_REQUIRED"): ci.stage()
        self.process.assert_not_called()

    def test_source_labels_platform_and_original_entrypoint_fail_closed(self):
        self.run.side_effect = None; self.run.return_value = json.dumps([self.facts()])
        self.assertEqual(ci.inspect_image("synthetic")["Id"], CONFIG)
        for part in ("diagnostics", "storage", "result"):
            facts = self.facts(); facts["Config"]["Labels"]["world-engine." + part + ".source-revision"] = "wrong"
            self.run.return_value = json.dumps([facts])
            with self.subTest(part=part), self.assertRaises(RuntimeError): ci.inspect_image("synthetic")
        facts = self.facts(); facts["Config"]["Entrypoint"] = ["/bin/true"]
        self.run.return_value = json.dumps([facts])
        with self.assertRaises(RuntimeError): ci.inspect_image("synthetic")

    def test_actual_image_contract_mismatch_is_rejected(self):
        self.run.side_effect = None; report = ci.manifests(); report["RESULT_FILES.json"]["helperSha256"] = "0" * 64
        self.run.return_value = json.dumps(report)
        with self.assertRaisesRegex(RuntimeError, "SOURCE_HASH_MISMATCH"): ci.image_hashes("synthetic")

    def test_publish_requires_verification_zero_secrets_and_double_unused_tag_guard(self):
        for value in [{"verification": "FAIL"}, {"secretScan": {"status": "PASS", "findings": 1}}]:
            self.seed(**value)
            with self.assertRaises(RuntimeError): ci.publish()
        self.old.login.assert_not_called(); self.registry.check_tag.assert_not_called()
        self.seed(); auth = self.root / "own-auth"; auth.mkdir(); (auth / "config.json").write_text("synthetic")
        self.old.login.return_value = (auth, {})
        self.registry.check_tag.side_effect = [{"status": "TAG_UNUSED"}, RuntimeError("TAG_ALREADY_EXISTS")]
        with self.assertRaisesRegex(RuntimeError, "TAG_ALREADY_EXISTS"): ci.publish()
        self.assertFalse(auth.exists()); self.run.assert_not_called()

    def test_publish_never_claims_independent_pull_success(self):
        self.seed(); auth = self.root / "own-auth"; auth.mkdir(); self.old.login.return_value = (auth, {})
        self.run.side_effect = None; self.run.return_value = TAG + ": digest: " + DIGEST + " size: 123\n"
        ci.publish(); result = ci.state(); self.assertIs(result["imagePushed"], True); self.assertIs(result["pullVerified"], False)
        self.assertEqual(result["status"], "PUBLISHED_INDEPENDENT_PULL_PENDING")

    def test_independent_pull_requires_original_and_all_patch_hashes(self):
        self.seed(); auth = self.root / "own-auth"; auth.mkdir(); self.old.login.return_value = (auth, {})
        self.run.side_effect = None
        with patch.object(ci, "inspect_image", return_value=self.facts()), patch.object(ci, "image_hashes", side_effect=RuntimeError("HASH_MISMATCH")):
            with self.assertRaises(RuntimeError): ci.pull()
        self.assertIs(ci.state()["pullVerified"], False)
        self.old.check_image.assert_called_once_with(ci.IMAGE + "@" + DIGEST, hashes_only=True)

    def test_dockerfile_inherits_entrypoint_and_does_not_install_or_copy_renderer(self):
        content = (HERE / "Dockerfile").read_text()
        self.assertIn("FROM " + ci.BASE, content)
        self.assertNotIn("ENTRYPOINT [", content); self.assertNotIn("HEALTHCHECK --", content)
        self.assertEqual(content.count("COPY "), 3)
        for forbidden in ("apt-get", "pip ", "npm ", "COPY repo", "ARG GH_TOKEN", "chmod /world-storage"):
            self.assertNotIn(forbidden, content)

    def test_console_records_parser_is_bounded_to_valid_objects(self):
        self.assertEqual(ci.json_lines('invalid\n[]\n{"errorCode":"GPU_HARDWARE_UNAVAILABLE"}\n'), [{"errorCode": "GPU_HARDWARE_UNAVAILABLE"}])
        self.assertNotIn("synthetic-value", ci.safe_log("token=synthetic-value https://example.test/?signed=synthetic-value"))
        self.assertLessEqual(len(ci.safe_log("x" * 100000)), 65536)


if __name__ == "__main__": unittest.main()
