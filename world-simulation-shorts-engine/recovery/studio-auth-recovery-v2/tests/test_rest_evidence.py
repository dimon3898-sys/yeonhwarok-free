"""Offline read-only HTTP wrapper contracts; not actual gCube evidence."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("studio_rest_evidence", ROOT / "rest_evidence.py")
rest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rest)


class RestTests(unittest.TestCase):
    def test_public_origin_must_be_an_actual_safe_gcube_root_url(self):
        self.assertEqual(rest.approved_public_origin('https://service.gcube.ai/'),
                         'https://service.gcube.ai')
        for value in ('service.gcube.ai', 'http://service.gcube.ai',
                      'https://private.invalid', 'https://service.gcube.ai/path',
                      'https://token@service.gcube.ai', 'https://service.gcube.ai/?token=secret'):
            self.assertIsNone(rest.approved_public_origin(value))

    def test_configuration_only_never_repeats_unavailable_log_request(self):
        api, calls = self.api()
        result = rest.collect({'GCUBE_ACCESS_TOKEN': 'OFFLINE_TEST_ONLY'},
                              factory=lambda _: api, configuration_only=True)
        self.assertEqual(calls, [('describe', '5373')])
        self.assertFalse(result['logs_request_repeated'])

    def test_registry_selector_image_path_is_not_misreported_as_wrong_image(self):
        row = {'containerEnvs': [], 'containerImage':
               'dimon3898-sys/world-simulation-shorts-engine:' + rest.APPROVED_TAG}
        self.assertTrue(rest.environment_summary(row)['configuration_checks']['configured_image_matches_approved'])

    def api(self, *, pod="authorized-pod", state="finish", logs="", env=None):
        calls = []
        class API:
            def describe(self, ser):
                calls.append(("describe", ser))
                return SimpleNamespace(raw={"ser": 5373, "state": state, "containerArray": [{
                    "containerEnvs": env or [], "containerImage": rest.APPROVED_TAG,
                    "containerCommand": "", "port": 8080}]})
            def pods(self, ser):
                calls.append(("pods", ser))
                return [{"name": pod, "status": "Failed"}]
            def logs(self, ser, name):
                calls.append(("logs", ser, name))
                return logs
        return API(), calls

    def test_no_token_cannot_contact_server(self):
        def fail(_):
            self.fail("No token must not invoke API")
        result = rest.collect({}, factory=fail)
        self.assertEqual(result["operations"], [])

    def test_stopped_state_uses_only_official_existing_pod_read(self):
        api, calls = self.api(logs=json.dumps({"errorCode": "STUDIO_HTTPS_ORIGIN_REQUIRED", "stage": "STUDIO"}))
        result = rest.collect({"GCUBE_ACCESS_TOKEN": "TEST_ONLY_SECRET"}, factory=lambda _: api)
        self.assertEqual(calls, [("describe", "5373"), ("pods", "5373"), ("logs", "5373", "authorized-pod")])
        self.assertEqual(result["raw_workload_state"], "finish")
        self.assertIsNone(result["actual_container_exit_code"])
        self.assertFalse(result["actual_cause_confirmed"])
        self.assertEqual(result["first_actual_error"]["error_code"], "STUDIO_HTTPS_ORIGIN_REQUIRED")

    def test_path_or_arbitrary_pod_is_rejected_before_log_read(self):
        for name in ("../escape", "pod?token=secret", "", "Bad Pod"):
            api, calls = self.api(pod=name)
            result = rest.collect({"GCUBE_ACCESS_TOKEN": "TEST_ONLY"}, factory=lambda _: api)
            self.assertEqual(len(calls), 2)
            self.assertEqual(result["blocking_reason"], "AUTHORIZED_POD_NAME_NOT_VALIDATED")

    def test_freeform_environment_and_logs_never_leave_summary(self):
        secret = "PRIVATE_OFFLINE_TEST_VALUE"
        env = [{"WORLD_ENGINE_STUDIO_OWNER_CODE": secret}, {"WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN": "https://private.invalid"}]
        api, _ = self.api(env=env, logs=json.dumps({"errorCode": secret, "reason": secret, "stage": secret}))
        result = rest.collect({"GCUBE_ACCESS_TOKEN": secret}, factory=lambda _: api)
        serialized = json.dumps(result)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("private.invalid", serialized)
        self.assertEqual(result["first_actual_error"]["error_code"], "WITHHELD_UNKNOWN_CODE")
        self.assertTrue(result["configuration"]["configuration_checks"]["owner_format_valid"])

    def test_exception_details_and_stdout_are_not_published(self):
        class APIError(Exception):
            status_code = 403
            code = "SENSITIVE_TEST_CODE"
        api, _ = self.api()
        def fail(*_):
            print("PRIVATE_TEST_STDOUT")
            raise APIError("PRIVATE_TEST_EXCEPTION_TOKEN")
        api.logs = fail
        result = rest.collect({"GCUBE_ACCESS_TOKEN": "TEST_ONLY"}, factory=lambda _: api)
        self.assertNotIn("PRIVATE_TEST", json.dumps(result))
        self.assertNotIn("SENSITIVE_TEST", json.dumps(result))
        self.assertEqual(result["operations"][-1]["http_or_api_status"], 403)
        self.assertEqual(result["blocking_reason"], "API_ERROR")

    def test_duplicate_or_unknown_environment_shape_not_assumed_valid(self):
        self.assertFalse(rest.environment_summary({"containerEnvs": [{"KEY": "a"}, {"KEY": "b"}]})["environment_shape_verified"])
        self.assertFalse(rest.environment_summary({"containerEnvs": [{"key": "KEY", "value": "a"}]})["environment_shape_verified"])

    def test_configuration_formats_are_separate_from_runtime_success(self):
        env = [{"WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN": "https://test.invalid/"},
            {"WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST": "registry/image@" + rest.APPROVED_DIGEST},
            {"WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON": "{}"}]
        checks = rest.environment_summary({"containerEnvs": env})["configuration_checks"]
        self.assertFalse(checks["origin_format_valid"])
        self.assertFalse(checks["image_digest_format_valid"])
        self.assertFalse(checks["policy_startup_structure_valid"])
        self.assertFalse(checks["policy_missing_is_startup_failure"])

    def test_official_str_dict_return_and_size_limit(self):
        docs, oversized = rest.log_documents(str({"errorCode": "STORAGE_VALIDATION_FAILED"}))
        self.assertEqual(docs[0]["errorCode"], "STORAGE_VALIDATION_FAILED")
        self.assertFalse(oversized)
        self.assertEqual(rest.log_documents("x" * (rest.MAX_LOG_BYTES + 1)), ([], True))
        self.assertEqual(rest.log_documents("__import__('os').system('false')"), ([], False))


if __name__ == "__main__":
    unittest.main()
