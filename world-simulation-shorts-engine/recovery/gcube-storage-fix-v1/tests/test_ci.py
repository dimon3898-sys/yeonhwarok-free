"""New storage packaging safety only; Docker, network and registry are mocked."""
import importlib.util
import ast
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("storage_ci_test", HERE / "ci.py")
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
TAG = "rtx4080s-2f9158b-12345-1"
DIGEST = "sha256:" + "a" * 64
CONFIG = "sha256:" + "b" * 64


class StorageCISafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="storage-ci-test-"); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {"STORAGE_CI_STATE": str(self.root / "state.json"), "RUNNER_TEMP": str(self.root),
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REPOSITORY": "dimon3898-sys/yeonhwarok-free",
            "STORAGE_REPOSITORY_PRIVATE": "false", "STORAGE_RUNNER_LABEL": "ubuntu-24.04",
            "GITHUB_REF": "refs/heads/" + ci.BRANCH, "GITHUB_SHA": "c" * 40,
            "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1", "STORAGE_PHASE": "build",
            "STORAGE_PUBLISHED_TAG": TAG, "STORAGE_PUBLISHED_DIGEST": DIGEST,
            "GITHUB_OUTPUT": str(self.root / "outputs")}
        self.addCleanup(patch.stopall); patch.dict(os.environ, self.env, clear=True).start()
        self.run = patch.object(ci, "run", side_effect=AssertionError("unexpected command")).start()
        self.process = patch.object(ci.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")).start()
        self.network = patch.object(ci.urllib.request, "urlopen", side_effect=AssertionError("network forbidden")).start()
        self.old = SimpleNamespace(require_space=Mock(return_value={"freeBytes": 22 * 1024**3}),
                                  check_image=Mock(return_value={"status": "PASS"}), login=Mock())
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
        return {"Id": CONFIG, "Size": 100, "Os": "linux", "Architecture": "amd64", "RootFS": {"Layers": []},
            "Config": {"Env": ["PATH=/usr/bin"], "Entrypoint": ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", ci.DEST + "/launch.py"],
                "Labels": {"org.opencontainers.image.revision": "2f9158ba2df2a9f58362fb0b17118b8dc19f705a",
                    "world-engine.diagnostics.source-revision": ci.DIAGNOSTIC_SOURCE,
                    "world-engine.storage.source-revision": self.env["GITHUB_SHA"], "world-engine.storage.parent-digest": ci.PARENT_DIGEST}}}

    def test_only_free_public_exact_branch_with_trusted_run_identity(self):
        for key, value in [("RUNNER_ENVIRONMENT", "self-hosted"), ("STORAGE_REPOSITORY_PRIVATE", "true"),
            ("STORAGE_RUNNER_LABEL", "larger-runner"), ("GITHUB_REF", "refs/heads/main"),
            ("GITHUB_RUN_ID", "../1"), ("GITHUB_RUN_ATTEMPT", "0")]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(RuntimeError): ci.preflight()
        self.old.require_space.assert_not_called(); self.run.assert_not_called()

    def test_protected_changes_and_dirty_checkout_fail_closed(self):
        def outputs(args, **kwargs):
            if args[1] == "rev-parse": return self.env["GITHUB_SHA"]
            if args[1] == "diff": return changed
            return dirty
        self.run.side_effect = outputs
        for changed, dirty in [("approved-renderer.py", ""), (ci.NAMESPACE + "/storage.py", " M protected.py")]:
            with self.subTest(changed=changed), self.assertRaises(RuntimeError): ci.preflight()
        self.old.require_space.assert_not_called()

    def test_minimal_context_and_failed_tests_stop_build(self):
        self.seed(focusedTests={"exitCode": 1})
        with self.assertRaises(RuntimeError): ci.stage()
        self.seed(); ci.stage(); value = ci.state(); context = Path(value["context"])
        self.assertFalse(context.is_relative_to(ci.REPO))
        self.assertEqual(set(path.name for path in context.iterdir()), {"storage.py", "launch.py", "Dockerfile", "STORAGE_FILES.json"})
        self.assertEqual(set(json.loads((context / "STORAGE_FILES.json").read_text())["files"]), {"storage.py", "launch.py"})
        (context / ".env").write_text("not a credential")
        with self.assertRaisesRegex(RuntimeError, "WHITELIST"): ci.build()
        self.process.assert_not_called()

    def test_old_and_new_source_labels_and_platform_are_independent(self):
        self.run.side_effect = None; self.run.return_value = json.dumps([self.facts()])
        self.assertEqual(ci.inspect_image("synthetic")["Id"], CONFIG)
        for key in ("world-engine.diagnostics.source-revision", "world-engine.storage.source-revision", "world-engine.storage.parent-digest"):
            facts = self.facts(); facts["Config"]["Labels"][key] = "incorrect"
            self.run.return_value = json.dumps([facts])
            with self.subTest(key=key), self.assertRaises(RuntimeError): ci.inspect_image("synthetic")
        facts = self.facts(); facts["Config"]["Env"] = ["GH_TOKEN=synthetic"]
        self.run.return_value = json.dumps([facts])
        with self.assertRaises(RuntimeError): ci.inspect_image("synthetic")

    def test_old_manifest_and_new_module_hash_mismatch_rejected(self):
        self.run.side_effect = None
        value = ci.manifest(); value["files"]["storage.py"] = "0" * 64
        self.run.return_value = json.dumps({"new": value})
        with self.assertRaisesRegex(RuntimeError, "HASH_MISMATCH"): ci.image_hashes("synthetic")
        command = self.run.call_args[0][0]
        self.assertIn(ci.DIAGNOSTIC_MANIFEST_SHA, command[-1])
        self.assertIn(ci.DIAGNOSTIC_SOURCE, command[-1])

    def test_failed_verification_or_scan_never_authenticates(self):
        for overrides in [{"verification": "FAIL"}, {"secretScan": {"status": "FAIL", "findings": 0}},
                          {"secretScan": {"status": "PASS", "findings": 1}}]:
            self.seed(**overrides)
            with self.assertRaises(RuntimeError): ci.publish()
        self.old.login.assert_not_called(); self.registry.check_tag.assert_not_called()

    def test_two_tag_guards_and_isolated_auth_cleanup(self):
        self.seed(); auth = self.root / "own-auth"; auth.mkdir(); (auth / "config.json").write_text("synthetic")
        self.old.login.return_value = (auth, {})
        self.registry.check_tag.side_effect = [{"status": "TAG_UNUSED"}, RuntimeError("TAG_ALREADY_EXISTS")]
        with self.assertRaisesRegex(RuntimeError, "TAG_ALREADY_EXISTS"): ci.publish()
        self.assertFalse(auth.exists()); self.run.assert_not_called()
        self.assertEqual(self.registry.check_tag.call_count, 2)

    def test_publish_never_claims_ready_before_independent_pull(self):
        self.seed(); auth = self.root / "own-auth"; auth.mkdir(); self.old.login.return_value = (auth, {})
        self.run.side_effect = None; self.run.return_value = TAG + ": digest: " + DIGEST + " size: 100\n"
        ci.publish(); value = ci.state()
        self.assertIs(value["imagePushed"], True); self.assertIs(value["pullVerified"], False)
        self.assertEqual(value["imageDigest"], DIGEST); self.assertNotEqual(value["status"], "STORAGE_FIX_IMAGE_CPU_VERIFIED")

    def test_independent_pull_requires_both_hash_layers(self):
        self.seed(); auth = self.root / "own-auth"; auth.mkdir(); self.old.login.return_value = (auth, {})
        self.run.side_effect = None
        with patch.object(ci, "inspect_image", return_value=self.facts()), \
             patch.object(ci, "image_hashes", side_effect=RuntimeError("STORAGE_MODULE_HASH_MISMATCH")):
            with self.assertRaises(RuntimeError): ci.pull()
        self.assertIs(ci.state()["pullVerified"], False)
        self.old.check_image.assert_called_once_with(ci.IMAGE + "@" + DIGEST, hashes_only=True)

    def test_logs_are_bounded_and_secret_values_removed(self):
        result = ci.safe_log("token=synthetic password: synthetic https://example.test/?key=synthetic")
        self.assertNotIn("synthetic", result); self.assertNotIn("https://", result)
        self.assertLessEqual(len(ci.safe_log("x" * 100000)), 65536)

    def test_dockerfile_inherits_approved_images_and_changes_only_new_directory(self):
        content = (HERE / "Dockerfile").read_text()
        self.assertIn("FROM " + ci.BASE, content); self.assertEqual(content.count("COPY "), 1)
        self.assertIn("/var/lib/world-engine-private/engine", content)
        for forbidden in ("apt-get", "pip ", "npm ", "chmod /world-storage", "chown /world-storage", "COPY repo", "ARG GH_TOKEN"):
            self.assertNotIn(forbidden, content)

    def test_generated_actual_export_probe_compiles_without_durability_claim(self):
        self.run.side_effect = None; self.run.return_value = json.dumps({"status": "PASS"})
        ci.verify_safe_export("synthetic-container", "GPU_HARDWARE_UNAVAILABLE", 2)
        arguments = self.run.call_args[0][0]
        self.assertEqual(arguments[:4], ["docker", "exec", "--user=1000:1000", "synthetic-container"])
        code = arguments[-1]; ast.parse(code)
        self.assertIn("'remotePersistenceVerified':False", code)
        self.assertIn("'externalDownloadVerified':False", code)

    def reuse_git(self, arguments, **kwargs):
        self.assertEqual(arguments[:2], ["git", "show"])
        name = arguments[2].rsplit("/", 1)[-1]
        return (HERE / "tests" / name).read_text()

    def test_pinned_reuse_requires_original_production_tests_and_counts(self):
        self.run.side_effect = self.reuse_git
        evidence, origin = ci.verified_reuse()
        self.assertEqual(origin["run"], "38680285245-1")
        self.assertIs(origin["testSourceHashesMatch"], True)
        self.assertEqual(origin["reusedCPUUnitTests"], 40)
        self.assertEqual(len(evidence["integrationCases"]), 4)
        self.assertEqual(self.run.call_count, 2)
        self.run.side_effect = lambda arguments, **kwargs: "changed test source"
        with self.assertRaisesRegex(RuntimeError, "REUSE_TEST_SOURCE_CHANGED"): ci.verified_reuse()

    def test_corrupt_evidence_and_changed_production_hashes_are_not_reused(self):
        original_sha = ci.sha
        self.run.side_effect = self.reuse_git
        for changed in ("build.json", "storage.py", "launch.py", "Dockerfile"):
            def modified(path):
                return "0" * 64 if Path(path).name == changed else original_sha(path)
            with self.subTest(changed=changed), patch.object(ci, "sha", side_effect=modified), self.assertRaises(RuntimeError):
                ci.verified_reuse()

    def test_actual_diagnostic_uses_default_root_and_nonroot_guard_stays_explicit(self):
        self.seed(); self.run.side_effect = None
        for groups in ([1000], []):
            self.run.return_value = json.dumps({"uid": 1000, "gid": 1000, "groups": groups})
            with patch.object(ci, "image_hashes", return_value={}), patch.object(ci, "fixture_root", return_value=self.root), \
                 patch.object(ci, "fixture_snapshot", return_value={"unchanged": True}), \
                 patch.object(ci, "verified_reuse", return_value=({}, {"observation": "REUSED_NOT_REEXECUTED"})), \
                 patch.object(ci, "secret_scan"), patch.object(ci, "execute_case", return_value={"status": "PASS"}) as execute:
                ci.verify()
                self.assertEqual(execute.call_args_list[0].kwargs["as_root"], True)
                self.assertEqual(execute.call_args_list[0].kwargs["service_expected"], True)
                self.assertEqual(execute.call_args_list[0].kwargs["expected_code"], "GPU_HARDWARE_UNAVAILABLE")
                if groups:
                    self.assertEqual(execute.call_count, 2)
                    guard = execute.call_args_list[1].kwargs
                    self.assertIs(guard["as_root"], False)
                    self.assertIs(guard["diagnostic"], True)
                    self.assertIs(guard["service_expected"], False)
                    self.assertEqual((guard["expected_code"], guard["expected_exit"]), ("UID_GID_FAILED", 1))
                else:
                    self.assertEqual(execute.call_count, 1)
                    self.assertEqual(ci.state()["unprivilegedDiagnosticGroupGuard"]["status"], "SKIP")


if __name__ == "__main__": unittest.main()
