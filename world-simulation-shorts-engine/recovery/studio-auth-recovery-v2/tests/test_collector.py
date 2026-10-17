"""Offline contract tests. None of these results are real gCube/GPU evidence."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "collector.py"
SPEC = importlib.util.spec_from_file_location("studio_readonly_collector", PATH)
collector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = collector
SPEC.loader.exec_module(collector)


class CollectorTests(unittest.TestCase):
    def fake_runner(self, captures, commands):
        def run(binary, arguments, environ, timeout):
            self.assertIn(tuple(arguments), collector.ALLOWED_COMMANDS)
            self.assertNotIn("GCUBE_API_TOKEN", environ)
            commands.append(tuple(arguments))
            return captures[len(commands) - 1]
        return run

    def cap(self, value=b"", rc=0, stderr=b"", timed_out=False):
        return collector.Capture(rc, timed_out,
            json.dumps(value).encode() if isinstance(value, (dict, list)) else value,
            stderr)

    def test_no_secret_never_runs_cli_or_network(self):
        def forbidden(*_):
            self.fail("CLI must not run without an approved supplied Secret")
        result = collector.collect({}, runner=forbidden)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["commands"], [])
        self.assertIsNone(result["actual_container_exit_code"])

    def test_allowlist_rejects_deploy_stop_update_and_shell_flags(self):
        for arguments in (("workload", "deploy", "5373"),
                ("workload", "stop", "5373"), ("workload", "update", "5373"),
                ("workload", "logs", "5373", ";", "env")):
            with self.assertRaisesRegex(ValueError, "COMMAND_NOT_ALLOWED"):
                collector.capture_command("gcube", arguments, {})

    def test_auth_error_does_not_publish_secret_or_freeform_reason(self):
        secret = "PRIVATE_TEST_ONLY_NEVER_A_REAL_TOKEN"
        commands = []
        result = collector.collect({"GCUBE_ACCESS_TOKEN": secret},
            runner=self.fake_runner([self.cap(b"gcube 0.4.2\n"),
                self.cap(rc=3, stderr=("Unauthorized token=" + secret + " email=private@example.invalid").encode())], commands))
        output = json.dumps(result)
        self.assertNotIn(secret, output)
        self.assertNotIn("private@example.invalid", output)
        self.assertEqual(result["blocking_reason"], "AUTH_REJECTED")
        self.assertIsNone(result["actual_container_exit_code"])

    def test_legacy_token_not_assumed_compatible_after_rejection(self):
        result = collector.collect({"GCUBE_API_TOKEN": "OFFLINE_TEST_VALUE"}, runner=self.fake_runner([
            self.cap(b"gcube 0.4.2\n"), self.cap(rc=3, stderr=b"401 unauthorized")], []))
        self.assertEqual(result["credential_source"], "GCUBE_API_TOKEN")
        self.assertEqual(result["legacy_bearer_compatibility"], "UNVERIFIED")

    def test_official_token_has_priority_and_legacy_is_not_tested(self):
        observed = []
        def run(binary, arguments, environ, timeout):
            observed.append(environ["GCUBE_ACCESS_TOKEN"])
            return self.cap(b"not the expected version")
        result = collector.collect({"GCUBE_ACCESS_TOKEN": "OFFICIAL_TEST", "GCUBE_API_TOKEN": "LEGACY_TEST"}, runner=run)
        self.assertEqual(observed, ["OFFICIAL_TEST"])
        self.assertEqual(result["credential_source"], "GCUBE_ACCESS_TOKEN")
        self.assertFalse(result["authenticated_workload_read_succeeded"])

    def test_success_only_public_whitelist_and_no_inferred_exit(self):
        marker = "HIDDEN_SECRET_TEST"
        commands = []
        workload = {"ser": 5373, "state": "deploy", "owner": marker,
            "containers": [{"containerEnvs": [{"key": "TOKEN", "value": marker}]}],
            "pods": [{"name": marker, "status": "CrashLoopBackOff", "ip": marker}]}
        logs = {"errorCode": "STUDIO_HTTPS_ORIGIN_REQUIRED", "stage": "STUDIO",
            "reason": marker, "timestamp": "2026-10-18T00:00:00Z", "env": marker}
        result = collector.collect({"GCUBE_API_TOKEN": marker}, runner=self.fake_runner([
            self.cap(b"gcube 0.4.2\n"), self.cap(workload), self.cap([]),
            self.cap(logs, rc=-9, timed_out=True)], commands))
        self.assertNotIn(marker, json.dumps(result))
        self.assertEqual(result["legacy_bearer_compatibility"], "CONFIRMED_FOR_THIS_READ_ONLY_REQUEST")
        self.assertIsNone(result["actual_container_exit_code"])
        self.assertEqual(result["logs_limitation"], "TIMEOUT")
        self.assertEqual(result["first_actual_error"]["error_code"], "STUDIO_HTTPS_ORIGIN_REQUIRED")
        self.assertEqual(len(commands), 4)

    def test_explicit_terminated_exit_code_only(self):
        value = {"status": {"containerStatuses": [{"lastState": {"terminated": {
            "exitCode": 1, "reason": "SECRET", "finishedAt": "2026-10-18T00:01:00Z"}}}]},
            "containerEnvs": {"state": {"terminated": {"exitCode": 99}}},
            "exitCode": 88}
        output = collector.terminated_states(value)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["exit_code"], 1)
        self.assertNotIn("SECRET", json.dumps(output))

    def test_unknown_status_code_stage_time_are_withheld(self):
        secret = "DO_NOT_PUBLISH"
        error = collector.first_error([{"errorCode": secret, "stage": secret, "timestamp": secret}])
        workload = collector.safe_workload({"ser": 5373, "state": secret, "pods": [{"status": secret}]})
        self.assertNotIn(secret, json.dumps([error, workload]))
        self.assertEqual(error["error_code"], "WITHHELD_UNKNOWN_CODE")

    def test_malformed_non_scalar_fields_are_not_published_or_crash(self):
        self.assertEqual(collector.safe_workload({"state": {"secret": "HIDDEN"},
            "pods": [{"status": ["HIDDEN"]}]})["state"], "WITHHELD_UNKNOWN")
        self.assertIsNone(collector.first_error([{"errorCode": "STUDIO_BOOTSTRAP_FAILED",
            "stage": {"secret": "HIDDEN"}}])["stage"])

    def test_text_log_is_never_published_or_fabricated_as_json_error(self):
        self.assertEqual(collector.json_documents(b"Bearer SOME_TEST_ONLY_VALUE\npassword=secret"), [])
        self.assertIsNone(collector.first_error(collector.json_documents(b"STUDIO_HTTPS_ORIGIN_REQUIRED")))

    def test_generic_success_code_does_not_replace_first_real_error(self):
        error = collector.first_error([{"code": {"untrusted": "non-scalar"}},
            {"code": "200", "status": "OK"},
            {"code": "STUDIO_HTTPS_ORIGIN_REQUIRED"}])
        self.assertEqual(error["error_code"], "STUDIO_HTTPS_ORIGIN_REQUIRED")

    def test_ambiguous_terminated_states_never_choose_exit_code(self):
        captures = [self.cap(b"gcube 0.4.2\n"), self.cap({"ser": 5373, "state": "deploy"}),
            self.cap([{"state": {"terminated": {"exitCode": 1}}},
                {"lastState": {"terminated": {"exitCode": 137}}}]), self.cap()]
        result = collector.collect({"GCUBE_ACCESS_TOKEN": "OFFLINE_TEST_ONLY"}, runner=self.fake_runner(captures, []))
        self.assertIsNone(result["actual_container_exit_code"])
        self.assertEqual(len(result["terminated_container_records"]), 2)

    def test_wrong_workload_does_not_confirm_auth_or_continue_logs(self):
        commands = []
        result = collector.collect({"GCUBE_API_TOKEN": "OFFLINE_TEST_ONLY"}, runner=self.fake_runner([
            self.cap(b"gcube 0.4.2\n"), self.cap({"ser": 9999, "state": "deploy"})], commands))
        self.assertEqual(len(commands), 2)
        self.assertFalse(result["authenticated_workload_read_succeeded"])
        self.assertFalse(result["logs_command_executed"])

    def test_actual_cpu_capture_is_private_and_temporary(self):
        # An offline fake binary tests host capture mechanics, not gcube auth.
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "offline_fake_cli"
            binary.write_text("#!" + sys.executable + "\nimport os, stat, sys\n"
                "assert stat.S_IMODE(os.fstat(sys.stdout.fileno()).st_mode) == 0o600\n"
                "assert stat.S_IMODE(os.fstat(sys.stderr.fileno()).st_mode) == 0o600\n"
                "print('OFFLINE_PRIVATE_CAPTURE_MARKER')\n")
            binary.chmod(0o700)
            capture = collector.capture_command(str(binary), ("--version",), dict(os.environ), 5)
        self.assertEqual(capture.returncode, 0)
        self.assertIn(b"OFFLINE_PRIVATE_CAPTURE_MARKER", capture.stdout)
        self.assertNotIn("OFFLINE_PRIVATE_CAPTURE_MARKER",
            json.dumps(collector.safe_command_result(("--version",), capture)))


if __name__ == "__main__":
    unittest.main()
