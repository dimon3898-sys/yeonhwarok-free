"""Focused packaging safety tests. Every Docker/network/registry call is mocked."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("diagnostic_ci_under_test", HERE / "ci.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
TAG = "rtx4080s-2f9158b-12345-1"
DIGEST = "sha256:" + "a" * 64
CONFIG = "sha256:" + "b" * 64


class CISafety(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="diagnostic-ci-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = {"DIAG_CI_STATE": str(self.root / "state.json"), "RUNNER_TEMP": str(self.root),
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REPOSITORY": "dimon3898-sys/yeonhwarok-free",
            "DIAG_REPOSITORY_PRIVATE": "false", "DIAG_RUNNER_LABEL": "ubuntu-24.04",
            "GITHUB_REF": "refs/heads/" + ci.BRANCH, "GITHUB_SHA": "c" * 40,
            "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1", "DIAG_PHASE": "build",
            "DIAG_PUBLISHED_TAG": TAG, "DIAG_PUBLISHED_DIGEST": DIGEST,
            "GITHUB_OUTPUT": str(self.root / "outputs")}
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()
        self.run = patch.object(ci, "run", side_effect=AssertionError("unexpected command")).start()
        self.process = patch.object(ci.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")).start()
        self.network = patch.object(ci.urllib.request, "urlopen", side_effect=AssertionError("network forbidden")).start()
        self.old = SimpleNamespace(require_space=Mock(return_value={"freeBytes": 22 * 1024**3}),
                                   check_image=Mock(return_value={"status": "PASS"}), login=Mock())
        patch.object(ci, "previous", return_value=self.old).start()
        self.registry = Mock()
        self.registry.check_tag.return_value = {"status": "TAG_UNUSED"}
        self.registry.inspect_digest.return_value = {"digest": DIGEST, "configDigest": CONFIG}
        module = ModuleType("registry_guard")
        module.RegistryGuard = lambda: self.registry
        module.validate_tag = lambda value: value
        module.validate_digest = lambda value: value
        patch.dict(sys.modules, {"registry_guard": module}).start()

    def seed(self, **overrides):
        value = ci.read_state()
        value.update(tag=TAG, image=ci.IMAGE + ":" + TAG, configDigest=CONFIG,
                     focusedTests={"exitCode": 0}, verification="PASS",
                     secretScan={"status": "PASS", "findings": 0})
        value.update(overrides); ci.save(value); return value

    def facts(self):
        return {"Id": CONFIG, "Size": 100, "Os": "linux", "Architecture": "amd64",
            "RootFS": {"Layers": []}, "Config": {"Env": ["PATH=/usr/bin"],
                "Entrypoint": ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", ci.DEST + "/startup.py"],
                "Labels": {"org.opencontainers.image.revision": "2f9158ba2df2a9f58362fb0b17118b8dc19f705a",
                    "world-engine.diagnostics.source-revision": self.env["GITHUB_SHA"],
                    "world-engine.diagnostics.parent-digest": ci.PARENT_DIGEST}}}

    def git_preflight(self, arguments, **kwargs):
        if arguments == ["git", "rev-parse", "HEAD"]: return self.env["GITHUB_SHA"]
        if arguments[:3] == ["git", "diff", "--name-only"]: return ci.NAMESPACE + "/startup.py\n"
        if arguments == ["git", "status", "--porcelain"]: return ""
        self.fail("unexpected git call")

    def test_free_public_standard_exact_branch_required(self):
        self.run.side_effect = self.git_preflight
        for key, bad in [("RUNNER_ENVIRONMENT", "self-hosted"), ("DIAG_REPOSITORY_PRIVATE", "true"),
                ("DIAG_RUNNER_LABEL", "larger-runner"), ("GITHUB_REPOSITORY", "elsewhere/repo"),
                ("GITHUB_REF", "refs/heads/main"), ("GITHUB_RUN_ID", "../1"), ("GITHUB_RUN_ATTEMPT", "0")]:
            with self.subTest(key=key), patch.dict(os.environ, {key: bad}):
                with self.assertRaises(RuntimeError): ci.preflight()
        self.old.require_space.assert_not_called()
        ci.preflight()
        self.assertEqual(ci.read_state()["tag"], TAG)
        self.assertIs(ci.read_state()["gpuExecuted"], False)
        self.process.assert_not_called()

    def test_protected_source_and_dirty_checkout_block(self):
        for changed, dirty in [("world-simulation-shorts-engine/renderer.py", ""),
                               (ci.NAMESPACE + "/startup.py", " M existing.py")]:
            def outputs(args, **kwargs):
                if args[1] == "rev-parse": return self.env["GITHUB_SHA"]
                if args[1] == "diff": return changed
                return dirty
            self.run.side_effect = outputs
            with self.assertRaises(RuntimeError): ci.preflight()
        self.old.require_space.assert_not_called()

    def test_only_explicit_files_enter_external_context(self):
        self.seed()
        ci.stage()
        value = ci.read_state(); context = Path(value["context"])
        self.assertEqual(set(p.name for p in context.iterdir()), set((*ci.MODULES, "Dockerfile", "DIAGNOSTIC_FILES.json")))
        self.assertFalse(context.is_relative_to(ci.REPO))
        manifest = json.loads((context / "DIAGNOSTIC_FILES.json").read_text())
        self.assertEqual(set(manifest["files"]), set(ci.MODULES))
        self.assertEqual(manifest["parentDigest"], ci.PARENT_DIGEST)
        self.assertEqual(manifest["sourceCommit"], self.env["GITHUB_SHA"])
        self.assertNotIn("GH_TOKEN", (context / "DIAGNOSTIC_FILES.json").read_text())
        self.process.assert_not_called()

    def test_failed_tests_block_staging(self):
        self.seed(focusedTests={"exitCode": 1})
        with self.assertRaisesRegex(RuntimeError, "FOCUSED_TESTS_REQUIRED"): ci.stage()
        self.process.assert_not_called()

    def test_context_extras_block_build(self):
        self.seed(); ci.stage()
        (Path(ci.read_state()["context"]) / ".env").write_text("not a credential")
        with self.assertRaisesRegex(RuntimeError, "WHITELIST"): ci.build()
        self.process.assert_not_called()

    def test_image_provenance_and_entrypoint_fail_closed(self):
        for target, key, bad in [("root", "Os", "windows"), ("root", "Architecture", "arm64"),
                ("labels", "world-engine.diagnostics.source-revision", "d" * 40),
                ("labels", "world-engine.diagnostics.parent-digest", DIGEST),
                ("config", "Entrypoint", ["/bin/true"]),
                ("config", "Env", ["GH_TOKEN=synthetic"] )]:
            facts = self.facts()
            destination = facts if target == "root" else (facts["Config"]["Labels"] if target == "labels" else facts["Config"])
            destination[key] = bad
            self.run.side_effect = None; self.run.return_value = json.dumps([facts])
            with self.subTest(key=key), self.assertRaises(RuntimeError): ci.inspect_image("synthetic")
        self.run.return_value = json.dumps([self.facts()])
        self.assertEqual(ci.inspect_image("synthetic")["Id"], CONFIG)

    def test_source_hash_difference_is_rejected(self):
        self.run.side_effect = None
        report = ci.module_manifest(); report["files"]["startup.py"] = "0" * 64
        self.run.return_value = json.dumps(report)
        with self.assertRaisesRegex(RuntimeError, "HASH_MISMATCH"): ci.image_manifest("synthetic")

    def test_secret_or_verification_failure_prevents_auth_and_push(self):
        for overrides in [{"verification": "FAIL"}, {"secretScan": {"status": "FAIL", "findings": 0}},
                          {"secretScan": {"status": "PASS", "findings": 1}}]:
            self.seed(**overrides)
            with self.assertRaises(RuntimeError): ci.publish()
        self.registry.check_tag.assert_not_called(); self.old.login.assert_not_called()
        self.process.assert_not_called()

    def test_unique_tag_checked_twice_and_conflict_prevents_push(self):
        self.seed()
        auth = self.root / "own-auth"; auth.mkdir(); (auth / "config.json").write_text("synthetic")
        self.old.login.return_value = (auth, {})
        self.registry.check_tag.side_effect = [{"status": "TAG_UNUSED"}, RuntimeError("TAG_ALREADY_EXISTS")]
        with self.assertRaisesRegex(RuntimeError, "TAG_ALREADY_EXISTS"): ci.publish()
        self.assertEqual(self.registry.check_tag.call_count, 2)
        self.assertFalse(auth.exists()); self.run.assert_not_called()

    def test_publish_records_matching_digest_only(self):
        self.seed()
        auth = self.root / "own-auth"; auth.mkdir(); (auth / "config.json").write_text("synthetic")
        self.old.login.return_value = (auth, {})
        self.run.side_effect = None; self.run.return_value = TAG + ": digest: " + DIGEST + " size: 1234\n"
        ci.publish()
        state = ci.read_state()
        self.assertIs(state["imagePushed"], True)
        self.assertEqual(state["imageDigest"], DIGEST)
        self.assertIs(state["pullVerified"], False)
        self.assertNotEqual(state["status"], "GPU_DIAGNOSTIC_IMAGE_READY")
        self.assertFalse(auth.exists())

    def test_published_config_mismatch_never_ready(self):
        self.seed()
        auth = self.root / "own-auth"; auth.mkdir()
        self.old.login.return_value = (auth, {})
        self.run.side_effect = None; self.run.return_value = TAG + ": digest: " + DIGEST + " size: 1234\n"
        self.registry.inspect_digest.return_value = {"digest": DIGEST, "configDigest": "sha256:" + "e" * 64}
        with self.assertRaisesRegex(RuntimeError, "CONFIG_HASH_MISMATCH"): ci.publish()
        self.assertIs(ci.read_state()["pullVerified"], False)

    def test_independent_pull_requires_original_and_new_hashes(self):
        self.seed()
        auth = self.root / "own-auth"; auth.mkdir()
        self.old.login.return_value = (auth, {})
        self.run.side_effect = None
        with patch.object(ci, "inspect_image", return_value=self.facts()), \
                patch.object(ci, "image_manifest", side_effect=RuntimeError("NEW_MODULE_HASH_MISMATCH")):
            with self.assertRaises(RuntimeError): ci.pull()
        self.assertIs(ci.read_state()["pullVerified"], False)
        self.old.check_image.assert_called_once_with(ci.IMAGE + "@" + DIGEST, hashes_only=True)

    def test_scanner_archive_is_bounded_and_binary_pinned(self):
        source = (HERE / "ci.py").read_text()
        self.assertIn('SCANNER_SHA = "e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad"', source)
        self.assertIn('"SCANNER_BINARY_SHA_MISMATCH"', source)
        self.assertIn("32 * 1024**2 + 1", source)
        self.assertIn('config.write_text("[extend]\\nuseDefault = true\\n")', source)
        self.assertNotIn("gitleaks:allow", source)

    def test_logs_are_bounded_and_credential_values_removed(self):
        sample = "token=synthetic-value password: test-value https://host/path?signature=some-value\n"
        output = ci.safe_log(sample)
        self.assertNotIn("synthetic-value", output); self.assertNotIn("test-value", output)
        self.assertNotIn("signature=", output)
        self.assertLessEqual(len(ci.safe_log("x" * 100000)), 65536)

    def test_dockerfile_never_rebuilds_approved_sources(self):
        dockerfile = (HERE / "Dockerfile").read_text()
        self.assertIn("FROM " + ci.BASE, dockerfile)
        self.assertEqual(dockerfile.count("COPY "), 1)
        for forbidden in ("apt-get", "npm ", "pip ", "COPY repo", "ARG GH_TOKEN", "--gpus", "SwiftShader"):
            self.assertNotIn(forbidden, dockerfile)
        self.assertIn("WORLD_ENGINE_STARTUP_MODE=normal", dockerfile)
        self.assertIn("--start-period=300s", dockerfile)

    def test_private_persistence_primary_fallback_and_unsafe_record(self):
        primary = self.root / "primary"; primary.mkdir(mode=0o700)
        fallback = self.root / "fallback"; fallback.mkdir(mode=0o700)
        expected = {"errorCode": "GPU_HARDWARE_UNAVAILABLE", "exitCode": 2}
        path = primary / "record.json"; path.write_text(json.dumps(expected)); path.chmod(0o600)
        result = ci.check_persistence(primary, [], expected, readonly=False, expected_uid=os.getuid())
        self.assertEqual(result["tier"], "primary"); self.assertIs(result["durable"], False)
        self.assertNotIn(str(primary), json.dumps(result))
        path.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, "PRIVATE_DIAGNOSTIC_RECORD_REQUIRED"):
            ci.check_persistence(primary, [], expected, readonly=False, expected_uid=os.getuid())
        fallback_record = fallback / "record.json"
        fallback_record.write_text(json.dumps(expected)); fallback_record.chmod(0o600)
        result = ci.check_persistence(self.root / "absent", [fallback], expected,
                                      readonly=True, expected_uid=os.getuid())
        self.assertEqual(result["tier"], "local_fallback")
        self.assertEqual(result["counts"], {"primary": 0, "local_fallback": 1})
        fallback_record.write_text(json.dumps({**expected, "exitCode": 1}))
        with self.assertRaisesRegex(RuntimeError, "READONLY_FALLBACK_RECORD_REQUIRED"):
            ci.check_persistence(self.root / "absent", [fallback], expected,
                                 readonly=True, expected_uid=os.getuid())


if __name__ == "__main__":
    unittest.main()
