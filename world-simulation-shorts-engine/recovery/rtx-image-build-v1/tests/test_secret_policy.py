"""Exercise the narrow public-fingerprint exception with pinned local Gitleaks."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rtx_secret_policy_under_test", PACKAGE / "secret_policy.py")
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)

BINARY = Path(os.environ.get("RTX_GITLEAKS_BINARY", "/workspace/.onboarding/event-v1-tools/gitleaks"))
BINARY_SHA256 = "e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad"
SOURCE = PACKAGE.parents[1] / "assets/flat/SOURCES.json"
SOURCE_SHA256 = "20e51ab95c7d524d8a8f2f34769deb3d59e5b446eafa633068381b99a04e6b17"
PUBLIC_CONTENT_DIGEST = "99a6ebfafb2f78a29cea244d9a20cf732c619c4c97db868bf98255f34ec26624"
RELATIVE_METADATA = "repo/world-simulation-shorts-engine/assets/flat/SOURCES.json"


class SecretPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BINARY.is_file():
            raise unittest.SkipTest("PINNED_SCANNER_UNAVAILABLE_SET_RTX_GITLEAKS_BINARY")
        if hashlib.sha256(BINARY.read_bytes()).hexdigest() != BINARY_SHA256:
            raise RuntimeError("PINNED_SCANNER_BINARY_MISMATCH")
        cls.original = SOURCE.read_bytes()
        if hashlib.sha256(cls.original).hexdigest() != SOURCE_SHA256:
            raise RuntimeError("PINNED_PUBLIC_METADATA_MISMATCH")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rtx-secret-policy-test-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.scanroot = self.base / "application"
        self.metadata = self.scanroot / RELATIVE_METADATA
        self.metadata.parent.mkdir(parents=True)
        self.metadata.write_bytes(self.original)
        self.config = self.base / "policy.toml"
        self.default_config = self.base / "defaults.toml"
        self.default_config.write_text("[extend]\nuseDefault = true\n")
        self.ignore = self.base / "empty-ignore"
        self.ignore.write_text("")
        self.scan_number = 0

    def scan(self, config):
        self.scan_number += 1
        report = self.base / ("report-%d.json" % self.scan_number)
        command = [str(BINARY), "dir", str(self.scanroot), "--config", str(config),
                   "--gitleaks-ignore-path", str(self.ignore), "--ignore-gitleaks-allow",
                   "--redact=100", "--report-format=json", "--report-path", str(report), "--no-banner"]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=30, check=False)
        self.assertIn(result.returncode, (0, 1), "Unexpected scanner exit code")
        self.assertTrue(report.is_file(), "Scanner must write its structured report")
        findings = json.loads(report.read_text())
        if not isinstance(findings, list):
            raise AssertionError("Scanner report must be a list")
        # Never include raw findings or process streams in assertions or output.
        rules = [finding.get("RuleID") for finding in findings]
        self.assertTrue(all(isinstance(rule, str) for rule in rules), "Rule IDs must be strings")
        return result.returncode, len(findings), sorted(rules)

    def test_original_default_finding_is_suppressed_by_the_exact_policy(self):
        self.assertEqual(self.scan(self.default_config), (1, 1, ["generic-api-key"]))
        evidence = policy.write_config(self.scanroot, self.config)
        self.assertIsInstance(evidence, dict)
        self.assertTrue(isinstance(evidence.get("schema"), str) and bool(evidence["schema"]))
        self.assertEqual(evidence["metadataFile"], RELATIVE_METADATA)
        self.assertEqual(evidence["metadataSha256"], SOURCE_SHA256)
        self.assertEqual(evidence["publicContentDigest"], PUBLIC_CONTENT_DIGEST)
        self.assertEqual(evidence["field"], "JSON[1].cache_key")
        self.assertEqual(evidence["gitleaksVersion"], "8.24.3")
        self.assertEqual(evidence["condition"], "AND")
        self.assertEqual(evidence["configSha256"], hashlib.sha256(self.config.read_bytes()).hexdigest())
        config = tomllib.loads(self.config.read_text())
        self.assertIs(config["extend"]["useDefault"], True)
        self.assertNotIn("allowlist", config)
        self.assertEqual(len(config["rules"]), 1)
        self.assertEqual(config["rules"][0]["id"], "generic-api-key")
        self.assertEqual(config["rules"][0]["allowlist"]["condition"], "AND")
        self.assertEqual(config["rules"][0]["allowlist"]["regexTarget"], "line")
        self.assertEqual(self.scan(self.config), (0, 0, []))

    def test_new_synthetic_api_value_after_policy_generation_is_still_detected(self):
        policy.write_config(self.scanroot, self.config)
        document = json.loads(self.original)
        document[0]["api_key"] = hashlib.sha256(b"synthetic policy regression fixture").hexdigest()
        self.metadata.write_text(json.dumps(document, indent=2) + "\n")
        self.assertEqual(self.scan(self.default_config), (1, 2, ["generic-api-key", "generic-api-key"]))
        self.assertEqual(self.scan(self.config), (1, 1, ["generic-api-key"]))

    def test_public_fingerprint_in_another_filename_is_not_allowlisted(self):
        policy.write_config(self.scanroot, self.config)
        (self.scanroot / "another-file.json").write_text(
            json.dumps({"cache_key": PUBLIC_CONTENT_DIGEST}, indent=2) + "\n")
        self.assertEqual(self.scan(self.config), (1, 1, ["generic-api-key"]))

    def test_public_fingerprint_in_another_field_is_not_allowlisted(self):
        policy.write_config(self.scanroot, self.config)
        document = json.loads(self.original)
        document[0]["api_key"] = PUBLIC_CONTENT_DIGEST
        self.metadata.write_text(json.dumps(document, indent=2) + "\n")
        self.assertEqual(self.scan(self.default_config), (1, 2, ["generic-api-key", "generic-api-key"]))
        self.assertEqual(self.scan(self.config), (1, 1, ["generic-api-key"]))

    def test_altered_metadata_blocks_policy_creation_before_scanning(self):
        self.metadata.write_bytes(self.original + b"\n")
        with self.assertRaises(RuntimeError):
            policy.write_config(self.scanroot, self.config)
        self.assertFalse(self.config.exists())
        self.assertEqual(self.metadata.read_bytes(), self.original + b"\n")


if __name__ == "__main__":
    unittest.main()
