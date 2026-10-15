"""Verification evidence tests; Docker, network, tar and scanner are mocked."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rtx_verify_evidence_pipeline", HERE / "pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
TAG = "rtx4080s-2f9158b-12345-1"
SCANNER = b"inert synthetic scanner bytes; never executed"
HELPER = {"schema": "RTX_BUILT_IMAGE_CPU_CHECK_V1", "status": "PASS", "uid": 1000,
          "gpuExecuted": False, "source": {"files": 160, "derivedBytecodeCount": 8}}
POLICY = {"schema": "rtx-public-metadata-secret-policy-v1", "metadataFile": "repo/public-fixture.json",
          "metadataSha256": hashlib.sha256(b"synthetic public policy fixture").hexdigest(),
          "field": "JSON[1].cache_key", "gitleaksVersion": "8.24.3", "condition": "AND",
          "ruleId": "generic-api-key", "allowlistScope": "rules.allowlist"}


class VerifyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rtx-verify-evidence-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"RTX_CI_STATE": str(self.base / "state.json"), "RUNNER_TEMP": str(self.base),
                               "GITHUB_SHA": "a" * 40}, clear=True).start()
        self.cpu = patch.object(pipeline, "check_image", return_value=HELPER).start()
        self.commands = patch.object(pipeline, "run", side_effect=self.command).start()
        self.scanner_process = patch.object(pipeline.subprocess, "run", side_effect=self.scan).start()
        self.download = patch.object(pipeline.urllib.request, "urlopen").start()
        self.download.return_value.__enter__.return_value.read.return_value = b"inert archive fixture"
        patch.object(pipeline, "SCANNER_SHA", hashlib.sha256(SCANNER).hexdigest()).start()
        self.policy_writer = Mock(side_effect=self.write_policy)
        patch.dict(sys.modules, {"secret_policy": SimpleNamespace(write_config=self.policy_writer)}).start()
        self.failure = None
        self.credential_absent = True
        self.exit_code = 0
        self.findings = []
        self.write_report = True
        self.seed()

    @property
    def scanroot(self):
        return Path(os.environ["RUNNER_TEMP"]) / ("rtx-image-source-" + TAG)

    def seed(self, *, previous_pass=False):
        state = {"schema": "RTX_IMAGE_BUILD_V1", "sourceCommit": pipeline.SOURCE,
                 "image": pipeline.IMAGE + ":" + TAG, "tag": TAG, "status": "IN_PROGRESS",
                 "imageBuilt": True, "imagePushed": False, "pullVerified": False,
                 "gpuExecuted": False, "gCubeDeployed": False, "videoRendered": False}
        if previous_pass:
            state.update(imageChecks={"status": "PASS", "old": True},
                         credentialPathCheck={"knownCredentialPathsAbsent": True},
                         secretScan={"status": "PASS", "findings": 0})
        pipeline.save(state)

    def command(self, arguments, **_kwargs):
        if arguments[:2] == ["docker", "run"]:
            if self.failure == "credential":
                raise subprocess.CalledProcessError(1, arguments, output="RAW_STDOUT_SENTINEL", stderr="RAW_STDERR_SENTINEL")
            return json.dumps({"knownCredentialPathsAbsent": self.credential_absent,
                               "presentPaths": [] if self.credential_absent else ["/root/.docker/config.json"]})
        if arguments[:2] == ["docker", "create"]:
            return "only-new-inspection-container\n"
        if arguments[:2] == ["docker", "cp"]:
            if self.failure == "copy":
                raise subprocess.CalledProcessError(1, arguments, stderr="RAW_STDERR_SENTINEL")
            target = Path(arguments[-1])
            (target / "repo").mkdir(parents=True)
            (target / "repo/good.txt").write_bytes(b"synthetic public fixture bytes")
            outside = self.base / "outside.txt"
            outside.write_bytes(b"outside content must never be hashed")
            (target / "repo/escape").symlink_to(self.base, target_is_directory=True)
            return ""
        if arguments[:2] == ["docker", "rm"]:
            self.assertEqual(arguments[-1], "only-new-inspection-container")
            return ""
        if arguments[0] == "tar":
            if self.failure == "scanner-setup":
                raise subprocess.CalledProcessError(1, arguments, stderr="RAW_STDERR_SENTINEL")
            directory = Path(arguments[arguments.index("-C") + 1])
            (directory / "gitleaks").write_bytes(SCANNER)
            return ""
        self.fail("unexpected command path")

    def scan(self, arguments, **kwargs):
        self.assertEqual(Path(arguments[0]).name, "gitleaks")
        self.assertIs(kwargs["check"], False)
        self.assertIs(kwargs["capture_output"], True)
        self.assertIn("--redact=100", arguments)
        if self.failure == "scanner":
            raise subprocess.TimeoutExpired(arguments, 180, output="RAW_STDOUT_SENTINEL", stderr="RAW_STDERR_SENTINEL")
        if self.write_report:
            report = Path(arguments[arguments.index("--report-path") + 1])
            report.write_text(json.dumps(self.findings))
        return SimpleNamespace(returncode=self.exit_code, stdout="RAW_STDOUT_SENTINEL", stderr="RAW_STDERR_SENTINEL")

    def write_policy(self, scanroot, destination):
        self.assertEqual(scanroot, self.scanroot)
        self.assertFalse(destination.exists())
        destination.write_text("[extend]\nuseDefault = true\n")
        return POLICY

    def assert_false_publication_and_no_raw_secrets(self):
        state = pipeline.read_state()
        self.assertEqual(state["imageChecks"], HELPER)
        self.assertIs(state["imagePushed"], False)
        self.assertIs(state["pullVerified"], False)
        self.assertNotEqual(state["status"], "GPU_IMAGE_READY_FOR_DEPLOYMENT")
        if self.policy_writer.called:
            self.assertEqual(state["secretPolicy"], POLICY)
        encoded = json.dumps(state)
        for sentinel in ("RAW_STDOUT_SENTINEL", "RAW_STDERR_SENTINEL", "RAW_MATCH_SENTINEL", "RAW_SECRET_SENTINEL", "RAW_DESCRIPTION_SENTINEL"):
            self.assertNotIn(sentinel, encoded)
        return state

    def test_completed_image_check_survives_each_later_failure_without_stale_pass(self):
        failures = [("credential", "KNOWN_CREDENTIAL_PATHS"), ("copy", "COPY_ACTUAL_APPLICATION"),
                    ("scanner-setup", "PINNED_SCANNER_SETUP"), ("scanner", "ACTUAL_APPLICATION_SECRET_SCAN")]
        for index, (failure, stage) in enumerate(failures):
            with self.subTest(failure=failure):
                location = self.base / ("case-" + str(index)); location.mkdir()
                os.environ["RUNNER_TEMP"] = str(location)
                self.seed(previous_pass=True)
                self.failure = failure
                with self.assertRaises((subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                    pipeline.verify()
                state = self.assert_false_publication_and_no_raw_secrets()
                self.assertEqual(state["verificationStage"], stage)
                self.assertNotEqual(state.get("secretScan", {}).get("status"), "PASS")

    def test_known_credential_presence_is_saved_and_stops_before_copy_or_scanner(self):
        self.credential_absent = False
        self.seed(previous_pass=True)
        with self.assertRaisesRegex(RuntimeError, "IMAGE_KNOWN_CREDENTIAL_PATH_PRESENT"):
            pipeline.verify()
        state = self.assert_false_publication_and_no_raw_secrets()
        self.assertIs(state["credentialPathCheck"]["knownCredentialPathsAbsent"], False)
        self.assertEqual(state["credentialPathCheck"]["presentPaths"], ["/root/.docker/config.json"])
        self.assertEqual(state["verificationStage"], "KNOWN_CREDENTIAL_PATHS")
        self.assertFalse(any(call.args[0][:2] == ["docker", "create"] for call in self.commands.call_args_list))
        self.scanner_process.assert_not_called()
        self.download.assert_not_called()
        self.policy_writer.assert_not_called()
        self.assertNotEqual(state.get("secretScan", {}).get("status"), "PASS")

    def test_reported_findings_keep_only_bounded_nonsecret_location_evidence(self):
        self.exit_code = 1
        common = {"RuleID": "generic-api-key", "StartLine": 12, "Match": "RAW_MATCH_SENTINEL",
                  "Secret": "RAW_SECRET_SENTINEL", "Description": "RAW_DESCRIPTION_SENTINEL"}
        self.findings = [{**common, "File": "repo/good.txt"}, {**common, "File": "../outside.txt"},
                         {**common, "File": "repo/escape/outside.txt"},
                         {**common, "File": "/outside/path?RAW_SECRET_SENTINEL", "RuleID": "RAW_DESCRIPTION_SENTINEL", "StartLine": True}]
        with self.assertRaisesRegex(RuntimeError, "SECRET_SCAN_FINDINGS"):
            pipeline.verify()
        state = self.assert_false_publication_and_no_raw_secrets()
        scan = state["secretScan"]
        self.assertEqual((scan["status"], scan["findings"], scan["scannerExitCode"]), ("FAIL", 4, 1))
        descriptors = scan["descriptors"]
        self.assertEqual(descriptors[0], {"rule": "generic-api-key", "path": "repo/good.txt", "line": 12,
                                         "fileSha256": hashlib.sha256(b"synthetic public fixture bytes").hexdigest()})
        self.assertEqual(descriptors[1]["path"], "UNREPORTED_PATH")
        self.assertNotIn("fileSha256", descriptors[1])
        self.assertNotIn("fileSha256", descriptors[2])
        self.assertEqual(descriptors[3], {"rule": "unknown", "path": "UNREPORTED_PATH", "line": None})
        self.assertTrue(all(set(row) <= {"rule", "path", "line", "fileSha256"} for row in descriptors))
        self.assertEqual(state["verificationStage"], "ACTUAL_APPLICATION_SECRET_SCAN")

    def test_empty_success_report_completes_verification_without_publication(self):
        pipeline.verify()
        state = self.assert_false_publication_and_no_raw_secrets()
        self.assertEqual(state["verificationStage"], "COMPLETE")
        self.assertEqual((state["secretScan"]["status"], state["secretScan"]["findings"], state["secretScan"]["scannerExitCode"]), ("PASS", 0, 0))
        self.assertEqual(state["secretScan"]["descriptors"], [])
        self.assertEqual(state["secretScan"]["scannerBinarySha256"], hashlib.sha256(SCANNER).hexdigest())

    def test_failed_exit_and_malformed_findings_cannot_record_scan_success(self):
        for index, findings in enumerate(([], [None])):
            with self.subTest(findings=findings):
                location = self.base / ("exit-case-" + str(index)); location.mkdir()
                os.environ["RUNNER_TEMP"] = str(location)
                self.seed(previous_pass=True)
                self.exit_code = 1
                self.findings = findings
                with self.assertRaises(RuntimeError):
                    pipeline.verify()
                state = self.assert_false_publication_and_no_raw_secrets()
                self.assertEqual(state["secretScan"]["status"], "FAIL")
                self.assertEqual(state["secretScan"]["scannerExitCode"], 1)
                self.assertEqual(state["verificationStage"], "ACTUAL_APPLICATION_SECRET_SCAN")


if __name__ == "__main__":
    unittest.main()
