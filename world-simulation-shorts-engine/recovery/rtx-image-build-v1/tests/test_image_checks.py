"""CPU image-check boundaries; external tools are always mocked."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "image_checks.py"
SPEC = importlib.util.spec_from_file_location("rtx_image_checks_under_test", MODULE_PATH)
checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checks)
SECRET = "SYNTHETIC_SECRET_MUST_NEVER_APPEAR"


def native_report():
    return {
        "status": "PASS", "gpuExecuted": False, "errors": [],
        "versions": {key: "1.2.3" for key in checks.VERSION_KEYS},
        "encoders": {"libx264": True},
        "gdalApis": {key: True for key in checks.GDAL_KEYS},
        "netcdfApis": {key: True for key in checks.NETCDF_KEYS},
        "probes": {key: "PASS" for key in checks.PROBE_KEYS},
    }


class RunChecksTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("/synthetic/image/package")
        self.source = {"status": "PASS", "gpuExecuted": False,
                       "sourceContractSha256": checks.SOURCE_CONTRACT_SHA256,
                       "sourceCommits": dict(checks.SOURCE_COMMITS), "files": 160}
        self.report = native_report()
        self.stage_module = SimpleNamespace(verify_staged_context=mock.Mock(side_effect=lambda root: self.source))
        self.native_module = SimpleNamespace(verify_dependencies=mock.Mock(
            side_effect=lambda repo, contract: self.report))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.uid = self.stack.enter_context(mock.patch.object(checks.os, "getuid", return_value=1000))
        self.euid = self.stack.enter_context(mock.patch.object(checks.os, "geteuid", return_value=1000))
        self.network = self.stack.enter_context(mock.patch.object(checks, "_check_network"))
        self.tree = self.stack.enter_context(mock.patch.object(checks, "_check_source_tree", return_value={
            "files": 160, "sourceContractSha256": checks.SOURCE_CONTRACT_SHA256,
            "stagingReceiptSha256": "b" * 64}))
        self.credentials = self.stack.enter_context(mock.patch.object(checks, "_check_credentials", return_value={
            "processEnvironment": "PASS", "stagedSources": "PASS", "engineHome": "PASS",
            "rootHome": "SEPARATE_PRIVILEGED_CI_CHECK_REQUIRED"}))
        self.modules = self.stack.enter_context(mock.patch.object(checks, "_module", side_effect=[
            self.stage_module, self.native_module]))
        self.metadata = self.stack.enter_context(mock.patch.object(checks, "_read_json", return_value=({}, "c" * 64)))
        self.playwright = self.stack.enter_context(mock.patch.object(checks, "_playwright", return_value={
            "node": "24.19.0", "playwright": "1.62.1", "moduleLoaded": True, "browserPageOpened": False}))
        self.codec = self.stack.enter_context(mock.patch.object(checks, "_codec", return_value={
            "encoder": "libx264", "frames": 2, "width": 16, "height": 16}))
        # No missed mock may start a real subprocess.
        self.subprocess = self.stack.enter_context(mock.patch.object(
            checks.subprocess, "run", side_effect=AssertionError("Real subprocess forbidden")))

    def run_checks(self, **kwargs):
        return checks.run_checks(package_root=self.root, environ={}, **kwargs)

    def test_full_cpu_success_calls_strict_gates_and_reports_no_gpu_or_browser(self):
        result = self.run_checks()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["mode"], "full-cpu")
        self.assertEqual(result["uid"], 1000)
        self.assertFalse(result["gpuExecuted"])
        self.assertFalse(result["browserPageOpened"])
        self.assertEqual(result["networkIsolation"], "LOOPBACK_ONLY")
        self.assertEqual(set(result["versions"]), checks.VERSION_KEYS)
        self.assertEqual(set(result["nativeAPIs"]["gdal"]), checks.GDAL_KEYS)
        self.assertEqual(set(result["nativeAPIs"]["netcdf"]), checks.NETCDF_KEYS)
        self.assertEqual(set(result["nativeProbes"]), checks.PROBE_KEYS)
        self.stage_module.verify_staged_context.assert_called_once_with(self.root)
        self.native_module.verify_dependencies.assert_called_once_with(self.root / "repo", {})
        self.playwright.assert_called_once_with(self.root / "repo")
        self.codec.assert_called_once_with()
        self.subprocess.assert_not_called()

    def test_hashes_only_keeps_source_security_gates_and_skips_native_node_codec(self):
        result = self.run_checks(hashes_only=True)
        self.assertEqual(result["mode"], "hashes-only")
        self.network.assert_called_once_with()
        self.tree.assert_called_once_with(self.root)
        self.credentials.assert_called_once_with({})
        self.stage_module.verify_staged_context.assert_called_once_with(self.root)
        self.assertEqual(self.modules.call_count, 1)
        self.metadata.assert_not_called()
        self.native_module.verify_dependencies.assert_not_called()
        self.playwright.assert_not_called()
        self.codec.assert_not_called()

    def test_real_and_effective_uid_must_both_be_1000(self):
        for uid, euid in ((0, 1000), (1000, 0), (1001, 1001)):
            with self.subTest(uid=uid, euid=euid):
                self.uid.return_value, self.euid.return_value = uid, euid
                with self.assertRaisesRegex(checks.ImageCheckError, "UID_1000_REQUIRED"):
                    self.run_checks(hashes_only=True)
        self.network.assert_not_called()
        self.tree.assert_not_called()

    def test_credential_environment_presence_rejects_empty_values_without_leaking(self):
        for name in checks.CREDENTIAL_ENV:
            for value in ("", SECRET):
                with self.subTest(name=name, empty=value == ""):
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        with self.assertRaises(checks.ImageCheckError) as caught:
                            checks.run_checks(package_root=self.root, environ={name: value})
                    self.assertEqual(str(caught.exception), "CREDENTIAL_ENV_PRESENT")
                    self.assertNotIn(SECRET, stdout.getvalue() + stderr.getvalue() + str(caught.exception))
        self.network.assert_not_called()

    def test_default_environment_is_checked_when_no_injected_environment_is_given(self):
        with mock.patch.dict(checks.os.environ, {"GITHUB_TOKEN": SECRET}, clear=True):
            with self.assertRaisesRegex(checks.ImageCheckError, "CREDENTIAL_ENV_PRESENT"):
                checks.run_checks(package_root=self.root)
        self.network.assert_not_called()

    def test_network_guard_failure_prevents_source_and_native_checks(self):
        self.network.side_effect = checks.ImageCheckError("NETWORK_NONE_REQUIRED")
        with self.assertRaisesRegex(checks.ImageCheckError, "NETWORK_NONE_REQUIRED"):
            self.run_checks()
        self.tree.assert_not_called()
        self.modules.assert_not_called()
        self.codec.assert_not_called()

    def test_source_verifier_contradictions_are_rejected(self):
        original = copy.deepcopy(self.source)
        invalid = (("status", "FAIL"), ("gpuExecuted", True), ("gpuExecuted", 0),
                   ("sourceContractSha256", "f" * 64), ("sourceCommits", {}),
                   ("files", 159), ("files", True))
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                self.source = dict(original, **{field: value})
                self.modules.side_effect = [self.stage_module, self.native_module]
                with self.assertRaisesRegex(checks.ImageCheckError, "PACKAGED_SOURCE_VERIFICATION_FAILED"):
                    self.run_checks()
        self.native_module.verify_dependencies.assert_not_called()
        self.playwright.assert_not_called()

    def test_non_dictionary_source_verifier_result_is_rejected(self):
        for result in (None, [], "PASS"):
            with self.subTest(result=result):
                self.source = result
                self.modules.side_effect = [self.stage_module]
                with self.assertRaisesRegex(checks.ImageCheckError, "PACKAGED_SOURCE_VERIFICATION_FAILED"):
                    self.run_checks(hashes_only=True)

    def test_native_failure_gpu_execution_or_error_list_prevents_tool_probes(self):
        original = native_report()
        for change in ({"status": "FAIL"}, {"gpuExecuted": True}, {"gpuExecuted": 0},
                       {"errors": [SECRET]}, {"errors": None}):
            with self.subTest(change=change):
                self.report = dict(original, **change)
                self.modules.side_effect = [self.stage_module, self.native_module]
                with self.assertRaisesRegex(checks.ImageCheckError, "STRICT_NATIVE_DEPENDENCY_CHECK_FAILED"):
                    self.run_checks()
        self.playwright.assert_not_called()
        self.codec.assert_not_called()

    def test_native_version_inventory_requires_exact_keys_and_numeric_strings(self):
        original = native_report()
        versions = original["versions"]
        missing = dict(versions)
        missing.pop("gdal")
        invalid = (None, missing, dict(versions, unexpected="1.2.3"),
                   dict(versions, gdal=3), dict(versions, gdal=SECRET),
                   dict(versions, gdal="1.2.3\n"))
        for candidate in invalid:
            with self.subTest(versions=candidate):
                self.report = dict(original, versions=candidate)
                self.modules.side_effect = [self.stage_module, self.native_module]
                with self.assertRaisesRegex(checks.ImageCheckError, "NATIVE_REPORT_INVALID"):
                    self.run_checks()

    def test_native_gdal_netcdf_and_probe_reports_require_exact_keys(self):
        for field in ("gdalApis", "netcdfApis", "probes"):
            original = native_report()
            valid = original[field]
            missing = dict(valid)
            missing.pop(next(iter(missing)))
            for candidate in (None, {}, missing, dict(valid, unexpected=True)):
                with self.subTest(field=field, candidate=candidate):
                    self.report = dict(original, **{field: candidate})
                    self.modules.side_effect = [self.stage_module, self.native_module]
                    with self.assertRaisesRegex(checks.ImageCheckError, "NATIVE_API_OR_PROBE_FAILED"):
                        self.run_checks()

    def test_native_api_values_must_be_true_and_probe_values_pass(self):
        for field, bad in (("gdalApis", False), ("gdalApis", 1), ("netcdfApis", False),
                           ("netcdfApis", 1), ("probes", "FAIL"), ("probes", True)):
            with self.subTest(field=field, value=bad):
                self.report = native_report()
                self.report[field][next(iter(self.report[field]))] = bad
                self.modules.side_effect = [self.stage_module, self.native_module]
                with self.assertRaisesRegex(checks.ImageCheckError, "NATIVE_API_OR_PROBE_FAILED"):
                    self.run_checks()

    def test_native_encoder_admission_requires_actual_true(self):
        for encoders in ({}, {"libx264": False}, {"libx264": 1}):
            with self.subTest(encoders=encoders):
                self.report = native_report()
                self.report["encoders"] = encoders
                self.modules.side_effect = [self.stage_module, self.native_module]
                with self.assertRaisesRegex(checks.ImageCheckError, "NATIVE_REPORT_INVALID"):
                    self.run_checks()

    def test_malformed_encoder_inventory_is_a_classified_native_failure(self):
        for encoders in (None, []):
            with self.subTest(encoders=encoders):
                self.report = native_report()
                self.report["encoders"] = encoders
                self.modules.side_effect = [self.stage_module, self.native_module]
                with self.assertRaisesRegex(checks.ImageCheckError, "NATIVE_REPORT_INVALID"):
                    self.run_checks()

    def test_success_reports_do_not_copy_unexpected_secret_fields_to_summary(self):
        self.source["privateDiagnostics"] = SECRET
        self.report["privateDiagnostics"] = SECRET
        self.report["encoders"]["privateDiagnostics"] = SECRET
        result = self.run_checks()
        self.assertNotIn(SECRET, json.dumps(result))


class ToolProbeTests(unittest.TestCase):
    def test_network_guard_accepts_only_loopback(self):
        with mock.patch.object(Path, "iterdir", return_value=iter([Path("/sys/class/net/lo")])):
            checks._check_network()
        for interfaces in ([], [Path("lo"), Path("eth0")], [Path("eth0")]):
            with self.subTest(interfaces=interfaces):
                with mock.patch.object(Path, "iterdir", return_value=iter(interfaces)):
                    with self.assertRaisesRegex(checks.ImageCheckError, "NETWORK_NONE_REQUIRED"):
                        checks._check_network()

    def test_network_inspection_failure_is_sanitized(self):
        with mock.patch.object(Path, "iterdir", side_effect=OSError(SECRET)):
            with self.assertRaisesRegex(checks.ImageCheckError, "NETWORK_ISOLATION_UNVERIFIED") as caught:
                checks._check_network()
        self.assertNotIn(SECRET, str(caught.exception))

    def test_command_uses_bounded_timeout_and_captured_output_without_shell(self):
        result = SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr="")
        with mock.patch.object(checks.subprocess, "run", return_value=result) as command:
            self.assertEqual(checks._command(["node", "-e", "public probe"], timeout=7), result.stdout)
        command.assert_called_once_with(["node", "-e", "public probe"], stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                        timeout=7, check=False)

    def test_command_failures_and_timeouts_never_include_subprocess_text(self):
        errors = (OSError(SECRET), subprocess.TimeoutExpired([SECRET], 30, output=SECRET, stderr=SECRET))
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(checks.subprocess, "run", side_effect=error):
                    with self.assertRaises(checks.ImageCheckError) as caught:
                        checks._command(["synthetic-command"])
                self.assertEqual(str(caught.exception), "CPU_COMMAND_UNAVAILABLE_OR_TIMEOUT")
                self.assertNotIn(SECRET, str(caught.exception))
        with mock.patch.object(checks.subprocess, "run", return_value=SimpleNamespace(
                returncode=1, stdout=SECRET, stderr=SECRET)):
            with self.assertRaisesRegex(checks.ImageCheckError, "CPU_COMMAND_FAILED") as caught:
                checks._command(["synthetic-command"])
        self.assertNotIn(SECRET, str(caught.exception))

    def test_command_rejects_oversized_stdout_and_stderr(self):
        for stdout, stderr in (("x" * 17, ""), ("", "x" * 17)):
            with self.subTest(stdout=bool(stdout)):
                with mock.patch.object(checks, "MAX_JSON_BYTES", 16), mock.patch.object(
                        checks.subprocess, "run", return_value=SimpleNamespace(
                            returncode=0, stdout=stdout, stderr=stderr)):
                    with self.assertRaisesRegex(checks.ImageCheckError, "CPU_COMMAND_FAILED"):
                        checks._command(["synthetic-command"])

    def test_playwright_loads_actual_node_module_without_launching_browser_or_gpu(self):
        repo = Path("/synthetic/repo")
        response = {"node": "24.19.0", "playwright": "1.62.1", "chromiumLaunchAPI": True}
        with mock.patch.object(checks, "_command", return_value=json.dumps(response)) as command:
            result = checks._playwright(repo)
        arguments = command.call_args.args[0]
        self.assertEqual(arguments[:2], ["node", "-e"])
        self.assertEqual(arguments[-1], str(repo))
        script = arguments[2]
        self.assertIn("createRequire", script)
        self.assertIn("process.argv[1]", script)
        self.assertIn("cinematic-world-map/package.json", script)
        self.assertIn("playwright/package.json", script)
        self.assertNotRegex(script, r"\.\s*(?:launch|newPage|newContext)\s*\(")
        for forbidden in ("gpu_launcher", "gpu_probe", "nvidia-smi", "gpu-required"):
            self.assertNotIn(forbidden, script)
        self.assertTrue(result["moduleLoaded"])
        self.assertFalse(result["browserPageOpened"])

    def test_playwright_json_version_api_and_inventory_failures_are_rejected(self):
        valid = {"node": "24.19.0", "playwright": "1.62.1", "chromiumLaunchAPI": True}
        candidates = (SECRET, "[]", "null", json.dumps(dict(valid, node="24.18.0")),
                      json.dumps(dict(valid, playwright="1.61.0")),
                      json.dumps(dict(valid, chromiumLaunchAPI=1)),
                      json.dumps(dict(valid, extra=True)))
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                with mock.patch.object(checks, "_command", return_value=candidate):
                    with self.assertRaises(checks.ImageCheckError) as caught:
                        checks._playwright(Path("/synthetic/repo"))
                self.assertNotIn(SECRET, str(caught.exception))

    def test_codec_uses_only_two_synthetic_black_frames_and_exact_probe(self):
        probe = {"streams": [{"codec_name": "h264", "width": 16, "height": 16,
                               "pix_fmt": "yuv420p", "nb_read_frames": "2"}]}
        with mock.patch.object(checks, "_command", side_effect=["", json.dumps(probe)]) as command:
            result = checks._codec()
        encode, inspect = [call.args[0] for call in command.call_args_list]
        self.assertEqual(encode[0], "ffmpeg")
        self.assertIn("-nostdin", encode)
        self.assertEqual(encode[encode.index("-f") + 1], "lavfi")
        self.assertEqual(encode[encode.index("-i") + 1], "color=c=black:s=16x16:r=1")
        self.assertEqual(encode[encode.index("-frames:v") + 1], "2")
        self.assertEqual(encode[encode.index("-c:v") + 1], "libx264")
        self.assertEqual(encode[encode.index("-pix_fmt") + 1], "yuv420p")
        self.assertEqual(inspect[0], "ffprobe")
        self.assertIn("-count_frames", inspect)
        self.assertEqual(inspect[inspect.index("-show_entries") + 1],
                         "stream=codec_name,width,height,pix_fmt,nb_read_frames")
        self.assertEqual(inspect[-1], encode[-1])
        self.assertEqual(Path(encode[-1]).name, "synthetic.mp4")
        self.assertEqual(result["frames"], 2)
        self.assertEqual((result["width"], result["height"]), (16, 16))
        self.assertTrue(result["syntheticBlackFramesOnly"])
        self.assertFalse(Path(encode[-1]).parent.exists())

    def test_codec_invalid_json_stream_count_and_exact_dimensions_are_rejected(self):
        valid = {"codec_name": "h264", "width": 16, "height": 16,
                 "pix_fmt": "yuv420p", "nb_read_frames": "2"}
        candidates = [SECRET, "[]", json.dumps({}), json.dumps({"streams": []}),
                      json.dumps({"streams": [valid, valid]})]
        candidates.extend(json.dumps({"streams": [dict(valid, **{field: value})]})
                          for field, value in (("codec_name", "hevc"), ("width", "16"),
                                               ("width", True), ("width", 17), ("height", 15),
                                               ("pix_fmt", "rgb24"), ("nb_read_frames", 2),
                                               ("nb_read_frames", "3")))
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                with mock.patch.object(checks, "_command", side_effect=["", candidate]):
                    with self.assertRaises(checks.ImageCheckError) as caught:
                        checks._codec()
                self.assertNotIn(SECRET, str(caught.exception))

    def test_codec_command_failure_stops_before_ffprobe(self):
        with mock.patch.object(checks, "_command", side_effect=checks.ImageCheckError(
                "CPU_COMMAND_UNAVAILABLE_OR_TIMEOUT")) as command:
            with self.assertRaises(checks.ImageCheckError):
                checks._codec()
        self.assertEqual(command.call_count, 1)


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rtx-image-fs-test-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "package"
        self.root.mkdir()
        self.home = self.base / "engine-home"
        self.home.mkdir()
        self.records = []
        for index in range(140):
            relative = "sources/%03d.txt" % index
            body = ("public fixture %d\n" % index).encode()
            self.write("repo/" + relative, body)
            self.records.append({"repoPath": relative, "bytes": len(body),
                                 "sha256": hashlib.sha256(body).hexdigest(),
                                 "sourceCommits": [checks.SOURCE_COMMITS["cpu"]]})
        contract = {"schema": "RTX_GPU_SOURCE_CONTRACT_V1", "files": self.records,
                    "sourceCommits": checks.SOURCE_COMMITS}
        body = (json.dumps(contract) + "\n").encode()
        self.write("source_contract.json", body)
        self.receipt = {"files": self.records}
        self.write("STAGING_RECEIPT.json", json.dumps(self.receipt).encode())
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(checks, "SOURCE_CONTRACT_SHA256", hashlib.sha256(body).hexdigest()))
        self.stack.enter_context(mock.patch.object(checks.os, "access", side_effect=lambda path, mode: not (mode & os.W_OK)))
        self.real_lstat = Path.lstat
        self.owner_overrides = {}

        def root_stat(path):
            values = list(self.real_lstat(path))
            values[4] = self.owner_overrides.get(path, 0)
            # Synthetic /tmp ancestors are not the production /opt tree.
            if path != self.root and self.root not in path.parents:
                values[0] &= ~0o022
            return os.stat_result(values)

        self.stack.enter_context(mock.patch.object(Path, "lstat", autospec=True, side_effect=root_stat))
        self.stack.enter_context(mock.patch.object(checks.pwd, "getpwuid", return_value=SimpleNamespace(pw_dir=str(self.home))))

    def write(self, relative, body):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        path.chmod(0o644)
        return path

    def test_exact_source_inventory_is_readable_and_root_owned(self):
        result = checks._check_source_tree(self.root)
        self.assertEqual(result["files"], 140)
        self.assertEqual(result["sourceContractSha256"], checks.SOURCE_CONTRACT_SHA256)
        self.assertEqual(len(result["stagingReceiptSha256"]), 64)

    def test_original_file_and_ancestor_ownership_are_enforced(self):
        for target in (self.root / "repo/sources/000.txt", self.root / "repo/sources"):
            with self.subTest(target=target):
                self.owner_overrides[target] = 1000
                with self.assertRaisesRegex(checks.ImageCheckError, "OWNERSHIP_OR_PERMISSIONS"):
                    checks._check_source_tree(self.root)
                self.owner_overrides.clear()

    def test_group_or_world_writable_source_is_rejected(self):
        target = self.root / "repo/sources/000.txt"
        for mode in (0o664, 0o646):
            with self.subTest(mode=mode):
                target.chmod(mode)
                with self.assertRaisesRegex(checks.ImageCheckError, "OWNERSHIP_OR_PERMISSIONS"):
                    checks._check_source_tree(self.root)
        target.chmod(0o644)

    def test_real_uid_readability_and_write_access_are_checked(self):
        target = self.root / "repo/sources/000.txt"
        for access in (lambda path, mode: False, lambda path, mode: True):
            with self.subTest(access=access):
                with mock.patch.object(checks.os, "access", side_effect=access):
                    with self.assertRaisesRegex(checks.ImageCheckError, "OWNERSHIP_OR_PERMISSIONS"):
                        checks._root_owned_readonly(target)

    def test_source_symlinks_and_directory_symlink_aliases_are_rejected(self):
        target = self.root / "repo/sources/000.txt"
        target.unlink()
        target.symlink_to(self.root / "repo/sources/001.txt")
        with self.assertRaisesRegex(checks.ImageCheckError, "OWNERSHIP_OR_PERMISSIONS"):
            checks._check_source_tree(self.root)
        target.unlink()
        self.write("repo/sources/000.txt", b"public fixture 0\n")
        (self.root / "alias").symlink_to(self.root / "repo", target_is_directory=True)
        with self.assertRaisesRegex(checks.ImageCheckError, "OWNERSHIP_OR_PERMISSIONS"):
            checks._check_source_tree(self.root)

    def test_unexpected_or_missing_staged_files_are_rejected(self):
        unexpected = self.write("repo/unselected.txt", b"public extra fixture")
        with self.assertRaisesRegex(checks.ImageCheckError, "UNEXPECTED_STAGED_FILE"):
            checks._check_source_tree(self.root)
        unexpected.unlink()
        (self.root / "repo/sources/000.txt").unlink()
        with self.assertRaisesRegex(checks.ImageCheckError, "STAGED_FILE_MISSING"):
            checks._check_source_tree(self.root)

    def test_staged_credential_paths_are_rejected_without_content_scanning(self):
        for relative in ("repo/.env", "repo/.env.local", "repo/.git-credentials", "repo/.netrc",
                         "repo/.docker/config.json", "repo/.aws/credentials", "repo/.config/gh/hosts.yml"):
            with self.subTest(relative=relative):
                target = self.write(relative, SECRET.encode())
                with self.assertRaises(checks.ImageCheckError) as caught:
                    checks._check_source_tree(self.root)
                self.assertNotIn(SECRET, str(caught.exception))
                target.unlink()

    def test_installed_npm_docs_env_examples_and_bin_symlinks_are_pruned(self):
        prefix = "repo/cinematic-world-map/node_modules"
        target = self.write(prefix + "/public-package/dotenv.md", b"public docs only")
        self.write(prefix + "/public-package/.env.example", b"public example")
        self.write(prefix + "/public-package/.env", b"public fixture")
        link = self.root / prefix / ".bin/public-command"
        link.parent.mkdir()
        link.symlink_to(target)
        result = checks._check_source_tree(self.root)
        self.assertEqual(result["files"], 140)

    def test_installed_npm_root_cannot_be_a_symlink(self):
        parent = self.root / "repo/cinematic-world-map"
        parent.mkdir()
        (parent / "node_modules").symlink_to(self.home, target_is_directory=True)
        with self.assertRaisesRegex(checks.ImageCheckError, "OWNERSHIP_OR_PERMISSIONS"):
            checks._check_source_tree(self.root)

    def test_duplicate_and_traversal_receipt_records_are_rejected(self):
        candidates = [self.records + [self.records[0]],
                      [dict(self.records[0], repoPath="../escape")],
                      [dict(self.records[0], repoPath="secret/.env")]]
        for records in candidates:
            with self.subTest(records=records[:1]):
                self.write("STAGING_RECEIPT.json", json.dumps({"files": records}).encode())
                with self.assertRaises(checks.ImageCheckError):
                    checks._check_source_tree(self.root)

    def test_engine_home_scope_uses_passwd_home_and_records_root_scope_limit(self):
        (self.home / "dotenv-public-docs.md").write_text("public examples mention credentials")
        result = checks._check_credentials({"HOME": "/unrelated/home"})
        self.assertEqual(result["engineHome"], "PASS")
        self.assertEqual(result["rootHome"], "SEPARATE_PRIVILEGED_CI_CHECK_REQUIRED")

    def test_engine_home_credentials_and_symlinks_are_rejected(self):
        for name in (".env", ".env.production", ".git-credentials", ".netrc", ".npmrc"):
            with self.subTest(name=name):
                path = self.home / name
                path.write_text(SECRET)
                with self.assertRaisesRegex(checks.ImageCheckError, "ENGINE_HOME_CREDENTIAL") as caught:
                    checks._check_credentials({})
                self.assertNotIn(SECRET, str(caught.exception))
                path.unlink()
        (self.home / "alias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(checks.ImageCheckError, "ENGINE_HOME_CREDENTIAL_OR_SYMLINK"):
            checks._check_credentials({})

    def test_engine_home_private_keys_and_gcube_auth_config_are_rejected(self):
        for relative in (".ssh/id_rsa", ".ssh/id_ed25519", ".gcube/config.yaml"):
            with self.subTest(relative=relative):
                path = self.home / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(SECRET)
                with self.assertRaisesRegex(checks.ImageCheckError, "ENGINE_HOME_CREDENTIAL") as caught:
                    checks._check_credentials({})
                self.assertNotIn(SECRET, str(caught.exception))
                path.unlink()

    def test_engine_home_public_ssh_material_is_not_a_private_credential(self):
        ssh = self.home / ".ssh"
        ssh.mkdir()
        (ssh / "known_hosts").write_text("public host-key fixture")
        (ssh / "id_ed25519.pub").write_text("public key fixture")
        self.assertEqual(checks._check_credentials({})["engineHome"], "PASS")

    def test_inaccessible_credential_scope_is_not_reported_absent(self):
        with mock.patch.object(checks.pwd, "getpwuid", side_effect=PermissionError(SECRET)):
            with self.assertRaisesRegex(checks.ImageCheckError, "SCOPE_UNREADABLE") as caught:
                checks._check_credentials({})
        self.assertNotIn(SECRET, str(caught.exception))


class MainOutputTests(unittest.TestCase):
    def invoke(self, side_effect=None, result=None, argv=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(checks, "run_checks", side_effect=side_effect, return_value=result) as run:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = checks.main(argv or [])
        lines = stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 1, stdout.getvalue())
        return code, json.loads(lines[0]), stdout.getvalue(), stderr.getvalue(), run

    def test_main_emits_one_json_report_and_forwards_hashes_only(self):
        def success(**kwargs):
            print("synthetic verifier noise")
            return {"schema": "RTX_BUILT_IMAGE_CPU_CHECK_V1", "status": "PASS", "gpuExecuted": False}

        code, report, stdout, stderr, run = self.invoke(side_effect=success, argv=["--hashes-only"])
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "PASS")
        self.assertNotIn("synthetic verifier noise", stdout)
        self.assertEqual(stderr, "")
        run.assert_called_once_with(hashes_only=True)

    def test_main_known_safe_errors_are_json_only_and_fail(self):
        code, report, stdout, stderr, _ = self.invoke(side_effect=checks.ImageCheckError("UID_1000_REQUIRED"))
        self.assertEqual(code, 1)
        self.assertEqual(report["errorCode"], "UID_1000_REQUIRED")
        self.assertFalse(report["gpuExecuted"])
        self.assertEqual(stderr, "")

    def test_main_unexpected_exceptions_never_leak_their_message(self):
        def failure(**kwargs):
            print(SECRET)
            raise RuntimeError(SECRET)

        code, report, stdout, stderr, _ = self.invoke(side_effect=failure)
        self.assertEqual(code, 1)
        self.assertEqual(report["errorCode"], "UNEXPECTED_CHECK_FAILURE")
        self.assertNotIn(SECRET, stdout + stderr)

    def test_main_unknown_image_check_error_text_is_sanitized(self):
        code, report, stdout, stderr, _ = self.invoke(side_effect=checks.ImageCheckError(SECRET))
        self.assertEqual(code, 1)
        self.assertNotIn(SECRET, stdout + stderr)
        self.assertEqual(report["status"], "FAIL")

    def test_main_verifier_stderr_does_not_leak_secret_text(self):
        def failure(**kwargs):
            print(SECRET, file=sys.stderr)
            raise RuntimeError(SECRET)

        code, report, stdout, stderr, _ = self.invoke(side_effect=failure)
        self.assertEqual(code, 1)
        self.assertNotIn(SECRET, stdout + stderr)
        self.assertEqual(report["errorCode"], "UNEXPECTED_CHECK_FAILURE")


if __name__ == "__main__":
    unittest.main()
