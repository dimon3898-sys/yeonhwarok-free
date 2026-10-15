"""CPU pipeline safety tests: all Git, Docker, registry and network calls mocked."""
import contextlib
import copy
import importlib.util
import io
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
spec = importlib.util.spec_from_file_location("rtx_pipeline_under_test", HERE / "pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
TAG = "rtx4080s-2f9158b-12345-1"
DIGEST = "sha256:" + "a" * 64
CONFIG = "sha256:" + "b" * 64
CONTRACT = "5938d0f33168daae415d9573701cafe290bcdd9850a14f4cb61c966560640180"


def helper_report(*, hashes_only=False):
    return {
        "schema": "RTX_BUILT_IMAGE_CPU_CHECK_V1", "status": "PASS", "uid": 1000,
        "gpuExecuted": False, "browserPageOpened": False, "networkIsolation": "LOOPBACK_ONLY",
        "mode": "hashes-only" if hashes_only else "full-cpu",
        "source": {"sourceContractSha256": CONTRACT, "stagingReceiptSha256": "c" * 64,
                   "files": 160, "originalFiles": 140,
                   "sourceCommits": {"cpu": "a002d89492734bfa9d17b98145ee6cb9a3b366a2",
                                     "glow": "45af879d7417abba58e9ebd59d8e6630a785ac28"}},
    }


class PipelineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rtx-pipeline-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = {
            "RTX_CI_STATE": str(self.root / "state.json"), "RUNNER_TEMP": str(self.root),
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REPOSITORY": "dimon3898-sys/yeonhwarok-free",
            "RTX_REPOSITORY_PRIVATE": "false", "RTX_RUNNER_LABEL": "ubuntu-24.04",
            "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "d" * 40,
            "RTX_PHASE": "build", "GITHUB_ACTOR": "example-owner", "GH_TOKEN": "SYNTHETIC_TOKEN_NOT_LOGGED",
            "GITHUB_OUTPUT": str(self.root / "outputs"), "RTX_PUBLISHED_TAG": TAG,
            "RTX_PUBLISHED_DIGEST": DIGEST,
        }
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()
        self.command = patch.object(pipeline, "run", side_effect=AssertionError("unexpected external command")).start()
        self.process = patch.object(pipeline.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")).start()
        self.network = patch.object(pipeline.urllib.request, "urlopen", side_effect=AssertionError("network prohibited")).start()
        self.registry = Mock()
        self.registry.check_tag.return_value = {"status": "TAG_UNUSED", "tag": TAG}
        self.registry.inspect_digest.return_value = {"digest": DIGEST, "configDigest": CONFIG}
        registry_module = ModuleType("registry_guard")
        registry_module.RegistryGuard = lambda: self.registry
        registry_module.validate_tag = lambda value: value
        registry_module.validate_digest = lambda value: value
        patch.dict(sys.modules, {"registry_guard": registry_module}).start()
        self.builder = {"root": "/disk/docker", "freeBytes": 21 * 1024**3, "filesystem": "ext2/ext3", "driver": "overlay2"}

    def seed(self, **changes):
        state = pipeline.read_state()
        state.update(tag=TAG, image=pipeline.IMAGE + ":" + TAG, configDigest=CONFIG,
                     context=str(self.root / "context"), imageBuilt=True,
                     imageChecks=helper_report(), secretScan={"status": "PASS", "findings": 0})
        state.update(changes)
        pipeline.save(state)
        return state

    def facts(self, **changes):
        result = {"Id": CONFIG, "Size": 123456, "Architecture": "amd64", "Os": "linux",
                  "Config": {"Env": ["PATH=/usr/bin"], "Labels": {"org.opencontainers.image.revision": pipeline.SOURCE,
                             "world-engine.ci-revision": self.env["GITHUB_SHA"]}}, "RootFS": {"Layers": ["sha256:" + "e" * 64]}}
        result.update(changes)
        return result

    def assert_not_ready(self):
        state = pipeline.read_state()
        self.assertIs(state["pullVerified"], False)
        self.assertNotEqual(state["status"], "GPU_IMAGE_READY_FOR_DEPLOYMENT")
        return state

    def test_free_public_standard_and_trusted_run_identity_gate(self):
        variants = [{"RUNNER_ENVIRONMENT": "self-hosted"}, {"GITHUB_REPOSITORY": "different/repository"},
                    {"RTX_REPOSITORY_PRIVATE": "true"}, {"RTX_RUNNER_LABEL": "larger-runner"},
                    {"GITHUB_RUN_ID": "0"}, {"GITHUB_RUN_ATTEMPT": "../1"}]
        with patch.object(pipeline, "require_space") as capacity:
            for changes in variants:
                with self.subTest(changes=changes), patch.dict(os.environ, {**self.env, **changes}, clear=True):
                    with self.assertRaises(RuntimeError):
                        pipeline.preflight()
            capacity.assert_not_called()
        self.command.assert_not_called()
        self.process.assert_not_called()

    def test_capacity_boundary_and_tmpfs_refusal(self):
        def output(arguments, **_kwargs):
            if arguments[:2] == ["docker", "info"]:
                return json.dumps("/disk/docker") if "DockerRootDir" in arguments[-1] else "overlay2\n"
            if arguments[0] == "stat":
                return filesystem
            self.fail("unapproved command")

        self.command.side_effect = output
        for free, filesystem, allowed in [(20 * 1024**3 - 1, "ext2/ext3", False),
                                          (20 * 1024**3, "tmpfs", False),
                                          (20 * 1024**3, "ext2/ext3", True)]:
            with self.subTest(free=free, filesystem=filesystem), patch.object(pipeline.shutil, "disk_usage", return_value=SimpleNamespace(free=free)):
                if allowed:
                    self.assertEqual(pipeline.require_space()["freeBytes"], free)
                else:
                    with self.assertRaises(RuntimeError):
                        pipeline.require_space()
        self.process.assert_not_called()

    def test_preflight_records_unique_fully_qualified_reference_and_fallback_state(self):
        with patch.dict(os.environ, {k: v for k, v in self.env.items() if k != "RTX_CI_STATE"}, clear=True), \
                patch.object(pipeline, "require_space", return_value=self.builder), contextlib.redirect_stdout(io.StringIO()):
            pipeline.preflight()
            state = pipeline.read_state()
            self.assertEqual(state["image"], pipeline.IMAGE + ":" + TAG)
            self.assertEqual(state["tag"], TAG)
            self.assertEqual(pipeline.state_file().parent, self.root)
            self.assertIs(state["freeRunner"]["repositoryPublic"], True)
            self.assertIs(state["freeRunner"]["largerRunner"], False)
            self.assertIs(state["imagePushed"], False)
            self.assertIs(state["gpuExecuted"], False)
        self.process.assert_not_called()

    def test_existing_tag_and_failed_secret_scan_block_push(self):
        for conflict_call in (1, 2):
            with self.subTest(conflict_call=conflict_call):
                self.seed()
                self.registry.reset_mock()
                self.registry.check_tag.side_effect = ([RuntimeError("TAG_ALREADY_EXISTS")] if conflict_call == 1 else
                                                       [{"status": "TAG_UNUSED"}, RuntimeError("TAG_ALREADY_EXISTS")])
                self.process.reset_mock()
                self.command.reset_mock()
                with self.assertRaisesRegex(RuntimeError, "TAG_ALREADY_EXISTS"):
                    pipeline.publish()
                self.command.assert_not_called()
                self.assertFalse((self.root / ("rtx-auth-" + TAG)).exists())
                self.assertIs(pipeline.read_state()["imagePushed"], False)
                self.assertEqual(self.process.call_count, conflict_call - 1)
        self.registry.check_tag.side_effect = None
        self.registry.reset_mock()
        self.seed(secretScan={"status": "FAIL", "findings": 0})
        self.process.reset_mock()
        with self.assertRaises(RuntimeError):
            pipeline.publish()
        self.registry.check_tag.assert_not_called()
        self.process.assert_not_called()

    def test_login_failure_cleans_only_its_new_auth_directory(self):
        unrelated = self.root / "unrelated-docker-auth"
        unrelated.mkdir()
        sentinel = unrelated / "config.json"
        sentinel.write_text("unrelated synthetic configuration")
        state = self.seed()
        auth = self.root / ("rtx-auth-" + TAG)

        def fail_login(_arguments, **_kwargs):
            (auth / "config.json").write_text("synthetic rejected credential")
            raise subprocess.CalledProcessError(1, "docker", stderr="SYNTHETIC_TOKEN_NOT_LOGGED")

        self.process.side_effect = fail_login
        with self.assertRaises(RuntimeError) as caught:
            pipeline.login(state)
        self.assertNotIn("SYNTHETIC_TOKEN_NOT_LOGGED", str(caught.exception))
        self.assertFalse(auth.exists())
        self.assertEqual(sentinel.read_text(), "unrelated synthetic configuration")
        self.process.side_effect = None
        self.process.reset_mock()
        with patch.dict(os.environ, {k: v for k, v in self.env.items() if k != "GH_TOKEN"}, clear=True):
            with self.assertRaises((RuntimeError, KeyError)):
                pipeline.login(state)
        self.assertFalse(auth.exists(), "missing login prerequisites must not leave a new auth directory")
        auth.mkdir()
        existing = auth / "config.json"
        existing.write_text("existing configuration must remain")
        self.process.reset_mock()
        with self.assertRaises((RuntimeError, FileExistsError)):
            pipeline.login(state)
        self.assertEqual(existing.read_text(), "existing configuration must remain")
        self.process.assert_not_called()

    def test_build_inspection_rejects_wrong_source_platform_or_credentials(self):
        variants = [self.facts(Config={"Env": [], "Labels": {"org.opencontainers.image.revision": "f" * 40}}),
                    self.facts(Architecture="arm64"), self.facts(Os="windows"),
                    self.facts(Config={"Env": ["GH_TOKEN=SYNTHETIC_TOKEN_NOT_LOGGED"],
                                       "Labels": {"org.opencontainers.image.revision": pipeline.SOURCE}})]
        with patch.object(pipeline, "require_space", return_value=self.builder):
            for facts in variants:
                with self.subTest(facts=facts):
                    self.seed(imageBuilt=False)
                    self.command.side_effect = None
                    self.command.return_value = json.dumps([facts])
                    with self.assertRaises(RuntimeError):
                        pipeline.build()
                    self.assertIs(pipeline.read_state()["imageBuilt"], False)
            self.seed(imageBuilt=False)
            self.command.return_value = json.dumps([self.facts()])
            pipeline.build()
            self.assertEqual(pipeline.read_state()["configDigest"], CONFIG)
            self.assertIs(pipeline.read_state()["imageBuilt"], True)

    def test_failed_or_contradictory_image_checks_cannot_leave_pull_ready(self):
        bad_reports = ["not JSON", json.dumps({"status": "FAIL"}), json.dumps({"status": "PASS"})]
        for field, value in [("schema", "WRONG"), ("uid", 0), ("gpuExecuted", True), ("mode", "full-cpu")]:
            report = helper_report(hashes_only=True)
            report[field] = value
            bad_reports.append(json.dumps(report))
        wrong_source = helper_report(hashes_only=True)
        wrong_source["source"]["sourceContractSha256"] = "f" * 64
        bad_reports.append(json.dumps(wrong_source))
        for output in bad_reports:
            with self.subTest(output=output):
                self.seed()
                self.process.return_value = SimpleNamespace(returncode=0, stdout=output, stderr="")
                with self.assertRaises(RuntimeError):
                    pipeline.check_image(pipeline.IMAGE + "@" + DIGEST, hashes_only=True)
                self.assert_not_ready()
        self.process.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
        for prior_ready in (False, True):
            with self.subTest(prior_ready=prior_ready):
                self.seed(pullVerified=prior_ready, imageDigest="sha256:" + "f" * 64,
                          status="GPU_IMAGE_READY_FOR_DEPLOYMENT" if prior_ready else "IN_PROGRESS")
                self.command.side_effect = None
                self.command.return_value = json.dumps([self.facts()])
                with patch.object(pipeline, "require_space", return_value=self.builder), \
                        patch.object(pipeline, "check_image", side_effect=RuntimeError("IMAGE_SOURCE_HASH_MISMATCH")):
                    with self.assertRaisesRegex(RuntimeError, "IMAGE_SOURCE_HASH_MISMATCH"):
                        pipeline.pull()
                self.assert_not_ready()
                self.assertFalse((self.root / ("rtx-auth-" + TAG)).exists())

    def test_pull_requires_remote_config_and_source_label_identity(self):
        for facts, reason in [(self.facts(Id="sha256:" + "f" * 64), "PULLED_CONFIG_HASH_MISMATCH"),
                              (self.facts(Config={"Labels": {"org.opencontainers.image.revision": "f" * 40}}), "PULLED_SOURCE_COMMIT_MISMATCH")]:
            with self.subTest(reason=reason):
                self.seed()
                self.command.side_effect = None
                self.command.return_value = json.dumps([facts])
                with patch.object(pipeline, "require_space", return_value=self.builder), patch.object(pipeline, "check_image") as checks:
                    with self.assertRaisesRegex(RuntimeError, reason):
                        pipeline.pull()
                    checks.assert_not_called()
                self.assert_not_ready()

    def test_successful_push_is_retained_if_remote_verification_fails(self):
        for remote_result in (RuntimeError("REMOTE_VERIFY_FAILED"), {"digest": DIGEST, "configDigest": "sha256:" + "f" * 64}):
            with self.subTest(remote_result=remote_result):
                self.seed()
                self.registry.check_tag.side_effect = None
                self.registry.inspect_digest.side_effect = remote_result if isinstance(remote_result, Exception) else None
                self.registry.inspect_digest.return_value = remote_result
                self.command.side_effect = None
                self.command.return_value = TAG + ": digest: " + DIGEST + " size: 512\n"
                with self.assertRaises(RuntimeError):
                    pipeline.publish()
                state = self.assert_not_ready()
                self.assertIs(state["imagePushed"], True)
                self.assertEqual(state["imageDigest"], DIGEST)
                self.assertFalse((self.root / ("rtx-auth-" + TAG)).exists())
                self.assertFalse((self.root / "outputs").exists())

    def test_exact_push_digest_parser_and_successful_publication_state(self):
        valid = TAG + ": digest: " + DIGEST + " size: 512\n"
        invalid = [valid + valid, valid.replace(TAG, "wrong-tag"), valid.replace("a" * 64, "A" * 64),
                   valid.replace(" size: 512", " size: 512 trailing-junk")]
        for output in invalid:
            with self.subTest(output=output):
                self.seed(imagePushed=False, imageDigest=None)
                self.registry.check_tag.side_effect = None
                self.registry.inspect_digest.side_effect = None
                self.registry.inspect_digest.reset_mock()
                self.command.side_effect = None
                self.command.return_value = output
                with self.assertRaisesRegex(RuntimeError, "UNIQUE_PUSH_DIGEST_REQUIRED"):
                    pipeline.publish()
                self.registry.inspect_digest.assert_not_called()
                state = self.assert_not_ready()
                self.assertIs(state["imagePushed"], True, "the completed registry write must not be erased by parsing failure")
                self.assertIsNone(state["imageDigest"])
        self.seed(imagePushed=False, imageDigest=None)
        self.registry.inspect_digest.return_value = {"digest": DIGEST, "configDigest": CONFIG}
        self.command.return_value = "layer: pushed\n" + valid
        pipeline.publish()
        state = self.assert_not_ready()
        self.assertEqual(state["status"], "BUILD_AND_PUSH_PASS_PULL_PENDING")
        self.assertEqual(state["imageReference"], pipeline.IMAGE + "@" + DIGEST)
        self.assertEqual((self.root / "outputs").read_text(), "tag=" + TAG + "\ndigest=" + DIGEST + "\n")
        self.registry.inspect_digest.assert_called_once_with(DIGEST)
        self.assertFalse((self.root / ("rtx-auth-" + TAG)).exists())


if __name__ == "__main__":
    unittest.main()
