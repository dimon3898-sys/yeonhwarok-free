"""Mock control-plane safety tests. These make zero account/network calls."""
from dataclasses import replace
import base64
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v3_operations", HERE / "operations.py")
ops = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ops
spec.loader.exec_module(ops)
NOW = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)
ACCOUNT = "operator@example.invalid"


def synthetic_token(payload):
    """Unsigned mock claim container; never an actual authentication fixture."""
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return "mock-header." + encoded + ".mock-signature"


TOKEN = synthetic_token({"email": ACCOUNT})


def approval(*actions):
    return ops.Approval("test-approval", ACCOUNT, "123", frozenset(actions),
                        "2026-10-16T01:00:00Z", 10, "USD", 3600, 0)


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.owner = ACCOUNT
        self.identity = ACCOUNT
        self.state = "deploy"
        self.operations = [{"type": "START", "status": "COMPLETED"}]
        self.schedules = [{"enabled": False, "action": "START", "daysOfWeek": 1,
                           "time": "10:00", "scheduleDate": None, "endDate": None,
                           "timeZone": "Asia/Seoul"}]
        self.points = {"availablePoint": 100, "chargePoint": 100, "spendPoint": 0,
                       "netPoint": 100, "isBlocked": False, "isAlarm": False}
        self.prices = [{"price": 100, "usagePrice": 1, "currencyUnit": "KRW"}]
        self.stop_error = None
        self.expected_token = TOKEN

    def __call__(self, method, url, headers, body, timeout):
        # Keep only method/URL/timeout, never the authenticated headers.
        self.calls.append((method, url, timeout))
        assert headers["Authorization"] == "Bearer " + self.expected_token
        assert 0 < timeout <= 30
        assert method == "GET" and body is None
        if "/api/users/" in url:
            return {"status": 200, "user": {"email": self.identity, "namespace": "test"}}
        if url.endswith("/state/finish"):
            if self.stop_error:
                raise self.stop_error
            self.operations = [{"type": "STOP", "status": "COMPLETED"}]
            return {"status": 200}
        if url.endswith("/schedule/logs?startNum=0&scaleNum=20"):
            return {"status": 200, "logs": [{"private": TOKEN}]}
        if url.endswith("/schedule"):
            return {"status": 200, "schedules": self.schedules, "timeZone": "Asia/Seoul"}
        if "/api/point/status?" in url:
            return {"status": 200, "points": self.points}
        if url.endswith("/api/gpu/available/pricing/list"):
            return {"status": 200, "pricings": self.prices}
        if url.endswith("/api/workloads/gai/123"):
            return {"status": 200, "workload": {"ser": 123, "owner": self.owner,
                    "state": self.state, "operations": self.operations,
                    "containerArray": [{"containerEnvs": [{"SECRET": TOKEN}]}]}}
        raise AssertionError("Unexpected route")


class OperationsSafetyTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.client = ops.GcubeOperations(TOKEN, ACCOUNT, transport=self.api, clock=lambda: NOW)

    def assert_blocked(self, code, function, *args, **kwargs):
        with self.assertRaises(ops.OperationsError) as caught:
            function(*args, **kwargs)
        self.assertEqual(code, str(caught.exception))

    def test_missing_secret_fails_before_transport(self):
        self.assert_blocked("AUTH_SECRET_REQUIRED", ops.GcubeOperations.from_environment,
                            environment={}, transport=self.api)
        self.assertEqual([], self.api.calls)
        self.assertEqual({"GCUBE_API_TOKEN": False, "GCUBE_EMAIL": False},
                         ops.SecretSelectors().presence({}))

    def test_preflight_is_real_route_allowlist_and_sanitized(self):
        result = self.client.preflight("123")
        self.assertTrue(result["authenticatedRequestSucceeded"])
        self.assertTrue(result["tokenAccountBindingVerified"])
        self.assertFalse(result["tokenClaimsCryptographicallyVerified"])
        self.assertFalse(result["launchExecutable"])
        self.assertFalse(result["hardwareGpuVerified"])
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertNotIn("containerEnvs", json.dumps(result))
        self.assertTrue(all("/state/" not in row[1] for row in self.api.calls))

    def test_jwt_email_and_email_sub_mismatch_reject_before_account_call(self):
        for payload in ({"email": "other@example.invalid"},
                        {"sub": "other@example.invalid"},
                        {"email": ACCOUNT, "sub": "other@example.invalid"}):
            client = ops.GcubeOperations(synthetic_token(payload), ACCOUNT,
                                         transport=self.api, clock=lambda: NOW)
            self.assert_blocked("AUTH_TOKEN_ACCOUNT_MISMATCH", client.preflight, "123")
        self.assertEqual([], self.api.calls)

    def test_opaque_or_oversized_claim_allows_reads_but_never_stop(self):
        for token in ("opaque-proxy-placeholder", synthetic_token({"email": ACCOUNT, "padding": "x" * 5000})):
            with self.subTest(kind="opaque_or_oversized"):
                self.api.expected_token = token
                client = ops.GcubeOperations(token, ACCOUNT, transport=self.api, clock=lambda: NOW)
                result = client.preflight("123")
                self.assertTrue(result["authenticatedRequestSucceeded"])
                self.assertFalse(result["tokenAccountBindingVerified"])
                self.assertFalse(result["tokenClaimsCryptographicallyVerified"])
                self.assertNotIn(token, json.dumps(result))
                self.assert_blocked("AUTH_ACCOUNT_BINDING_UNVERIFIED", client.stop,
                                    "123", approval=approval("stop"))
        self.assertTrue(all("/state/" not in row[1] for row in self.api.calls))

    def test_email_like_sub_fallback_is_locally_matched_not_signature_verified(self):
        token = synthetic_token({"sub": ACCOUNT})
        self.api.expected_token = token
        client = ops.GcubeOperations(token, ACCOUNT, transport=self.api, clock=lambda: NOW)
        result = client.preflight("123")
        self.assertTrue(result["tokenAccountBindingVerified"])
        self.assertFalse(result["tokenClaimsCryptographicallyVerified"])

    def test_gpu_identity_retained_without_claiming_workload_rate_binding(self):
        expected = {"gpuName": "RTX4080", "productName": "RTX 4080 SUPER", "gpu": 1,
                    "vram": 16, "cpu": 12, "memory": 32, "disk": 100}
        self.api.prices[0].update(expected)
        row = self.client.cost_snapshot()["pricingRows"][0]
        self.assertEqual(expected, {key: row[key] for key in expected})
        self.assertTrue(row["gpuIdentityComplete"])
        self.assertFalse(row["rateBindingVerified"])
        self.assertEqual("WORKLOAD_GPU_SPEC_MATCH_NOT_PERFORMED", row["rateBindingReason"])
        self.api.prices[0]["gpuName"] = TOKEN
        row = self.client.cost_snapshot()["pricingRows"][0]
        self.assertNotIn(TOKEN, json.dumps(row))
        self.assertFalse(row["gpuIdentityComplete"])
        self.assertFalse(row["rateBindingVerified"])

    def test_invalid_account_or_owner_cannot_progress(self):
        self.api.identity = "someone@example.invalid"
        self.assert_blocked("AUTHENTICATED_ACCOUNT_MISMATCH", self.client.preflight, "123")
        self.assertEqual(1, len(self.api.calls))
        self.api.identity = ACCOUNT
        self.api.owner = "someone@example.invalid"
        self.assert_blocked("WORKLOAD_ACCOUNT_MISMATCH", self.client.preflight, "123")
        self.assertTrue(all("/schedule" not in row[1] for row in self.api.calls))

    def test_no_paid_launch_even_with_approval_and_stop_deadline(self):
        self.assert_blocked("STRICT_PROVIDER_COST_CAP_UNSUPPORTED", self.client.start,
                            "123", approval=approval("start"), stop_at="2026-10-16T00:30:00Z")
        self.assertEqual([], self.api.calls)
        self.assertFalse(self.client.plan_start("123")["executable"])
        self.assert_blocked("EXPLICIT_APPROVAL_REQUIRED", self.client.start, "123")

    def test_full_operation_allowlist_blocks_injected_paths_and_mutating_get(self):
        self.assert_blocked("INVALID_WORKLOAD_SER", self.client.preflight, "123/state/deploy")
        self.assert_blocked("OPERATION_NOT_ALLOWLISTED", self.client._request, "deploy", "123")
        self.assert_blocked("EXPLICIT_APPROVAL_REQUIRED", self.client._request, "stop", "123")
        self.assertTrue(all("/state/" not in row[1] for row in self.api.calls))

    def test_stop_requires_all_finite_scoped_controls_before_account_reads(self):
        cases = [(None, "EXPLICIT_APPROVAL_REQUIRED"),
                 (replace(approval("stop"), account="wrong"), "APPROVAL_SCOPE_MISMATCH"),
                 (replace(approval("stop"), expires_at="2026-10-15T00:00:00Z"), "APPROVAL_EXPIRED"),
                 (replace(approval("stop"), max_cost=float("nan")), "FINITE_COST_LIMIT_REQUIRED"),
                 (replace(approval("stop"), max_wall_seconds=0), "FINITE_WALL_LIMIT_REQUIRED"),
                 (replace(approval("stop"), max_retries=3), "BOUNDED_RETRIES_REQUIRED")]
        for item, code in cases:
            with self.subTest(code=code):
                self.assert_blocked(code, self.client.stop, "123", approval=item)
        self.assertEqual([], self.api.calls)

    def test_approved_stop_single_mutation_and_independent_operation_readback(self):
        result = self.client.stop("123", approval=approval("stop"))
        self.assertTrue(result["providerStopOperationVerified"])
        self.assertFalse(result["billingTerminationGuaranteed"])
        self.assertEqual(1, sum("/state/finish" in c[1] for c in self.api.calls))
        self.assertEqual(0, result["automaticRetries"])

    def test_stop_timeout_is_ambiguous_never_retried_or_logged(self):
        self.api.stop_error = RuntimeError("provider echoed " + TOKEN)
        self.assert_blocked("STOP_OUTCOME_UNKNOWN_VERIFY_SEPARATELY_NO_RETRY",
                            self.client.stop, "123", approval=approval("stop"))
        self.assertEqual(1, sum("/state/finish" in c[1] for c in self.api.calls))

    def test_stop_requests_use_remaining_wall_budget(self):
        with patch.object(ops.time, "monotonic", side_effect=[0, .2, .4, .6, .8, .9]):
            result = self.client.stop("123", approval=replace(approval("stop"), max_wall_seconds=1))
        self.assertTrue(result["requestAccepted"])
        self.assertEqual(4, len(self.api.calls))
        for actual, expected in zip([c[2] for c in self.api.calls], [.8, .6, .4, .1]):
            self.assertAlmostEqual(expected, actual)

    def test_expired_wall_budget_prevents_stop_request(self):
        with patch.object(ops.time, "monotonic", side_effect=[0, .2, .4, 1.1]):
            self.assert_blocked("APPROVED_WALL_LIMIT_EXPIRED", self.client.stop,
                                "123", approval=replace(approval("stop"), max_wall_seconds=1))
        self.assertTrue(all("/state/" not in row[1] for row in self.api.calls))

    def test_latest_operation_beats_stale_finished_state(self):
        self.api.state = "finish"
        self.api.operations = [{"type": "STOP", "status": "STOP_FAILED"}]
        result = self.client.verify_stopped("123")
        self.assertEqual("failed", result["phase"])
        self.assertFalse(result["providerStopOperationVerified"])
        self.api.operations = []
        self.assertFalse(self.client.verify_stopped("123")["providerStopOperationVerified"])

    def test_schedule_plan_preserves_disabled_entries_and_never_writes(self):
        plan = self.client.plan_stop_schedule("123", stop_at="2026-10-16T00:30:00Z",
                                              approval=approval("schedule"))
        self.assertFalse(plan["executable"])
        self.assertFalse(plan["before"]["schedules"][0]["enabled"])
        self.assertEqual(plan["before"]["schedules"], plan["desired"]["schedules"][:-1])
        self.assertEqual("09:30", plan["desired"]["schedules"][-1]["time"])
        self.assertEqual(plan["before"], plan["rollback"]["restore"])
        self.assertEqual(1, plan["rollback"]["maxWrites"])
        before = len(self.api.calls)
        self.assert_blocked("SCHEDULE_ATOMIC_UPDATE_UNSUPPORTED", self.client.install_stop_schedule,
                            plan, approval=approval("schedule"))
        self.assert_blocked("SCHEDULE_ATOMIC_UPDATE_UNSUPPORTED", self.client.rollback_stop_schedule,
                            plan, approval=approval("schedule_rollback"))
        self.assertEqual(before, len(self.api.calls))

    def test_stop_schedule_requires_exact_enabled_future_entry(self):
        self.api.schedules = [{"enabled": True, "action": "STOP", "daysOfWeek": 0,
                               "time": "09:30", "scheduleDate": "2026-10-16", "endDate": None,
                               "timeZone": "Asia/Seoul"}]
        self.assertTrue(self.client.verify_stop_schedule(
            "123", stop_at="2026-10-16T00:30:00Z")["stopScheduleVerified"])
        self.api.schedules[0]["enabled"] = False
        self.assert_blocked("STOP_SCHEDULE_NOT_VERIFIED", self.client.verify_stop_schedule,
                            "123", stop_at="2026-10-16T00:30:00Z")
        self.assert_blocked("INVALID_FUTURE_STOP_DEADLINE", self.client.verify_stop_schedule,
                            "123", stop_at="2026-10-15T00:30:00Z")

    def test_unknown_missing_nonfinite_cost_is_not_free(self):
        del self.api.points["availablePoint"]
        self.assert_blocked("INVALID_POINTS_RESPONSE", self.client.cost_snapshot)
        self.api.points["availablePoint"] = 1
        self.api.prices[0]["price"] = float("inf")
        self.assert_blocked("INVALID_PRICING_RESPONSE", self.client.cost_snapshot)

    def test_no_ssh_provisioning_or_raw_history(self):
        self.assert_blocked("APPROVED_SSH_KEY_KNOWN_HOSTS_AND_TCP_GRANT_REQUIRED", self.client.ssh)
        self.assertNotIn(TOKEN, json.dumps(self.client.schedule_history("123")))
        self.assertTrue(all("/api/pods/ssh/" not in c[1] for c in self.api.calls))

    def test_http_redirect_refuses_token_forwarding(self):
        self.assert_blocked("API_REDIRECT_REJECTED", ops._NoRedirect().redirect_request,
                            None, None, 302, "redirect", {}, "https://attacker.invalid")
        self.assert_blocked("API_ORIGIN_REJECTED", ops.HttpsJSONTransport(),
                            "GET", "https://api.gcube.ai.attacker.invalid/api/users/x", {}, None, 1)

    def test_cli_account_read_requires_explicit_flag(self):
        with io.StringIO() as capture, patch("sys.stdout", capture):
            status = ops.main(["preflight", "--workload-ser", "123"])
            result = json.loads(capture.getvalue())
        self.assertEqual(2, status)
        self.assertEqual("EXPLICIT_ACCOUNT_READ_REQUIRED", result["reason"])


if __name__ == "__main__":
    unittest.main()
