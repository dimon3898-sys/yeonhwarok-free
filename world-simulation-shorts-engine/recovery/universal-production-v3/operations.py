"""Authenticated, fixed-route gCube control plane; no paid launch is executable.

Routes and response fields come from the saved official gcube-cli 0.4.2 wheel.
An approval record is supplied by a trusted operator, never by Scene JSON or an
HTTP request. It records authorization; it is not an authentication mechanism.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
import time
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_ORIGIN = "https://api.gcube.ai"
CLI_VERSION = "0.4.2"
HARD_COST_CAP_SUPPORTED = False
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_LOCAL_JWT_PAYLOAD_BYTES = 4096
_SER = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_ENV = re.compile(r"GCUBE_[A-Z0-9_]{1,94}\Z")
_FAILURES = {"START_FAILED", "STOP_FAILED", "FORCE_STOP_REQUIRED", "VM_FAILED",
             "VM_ACTIVATE_FAILED", "NODE_JOIN_FAILED"}


class OperationsError(RuntimeError):
    """Only stable codes are emitted; provider bodies/exceptions are private."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise OperationsError(code)


def _utc(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _require(result.tzinfo is not None, "TIMEZONE_REQUIRED")
        return result.astimezone(timezone.utc)
    except (AttributeError, ValueError, TypeError):
        raise OperationsError("INVALID_TIMESTAMP") from None


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _local_token_accounts(token: str) -> tuple[str, ...]:
    """Bounded consistency check only; this does NOT verify a JWT signature."""
    parts = token.split(".")
    if len(parts) != 3 or not 1 <= len(parts[1]) <= 5462 or not re.fullmatch(
            r"[A-Za-z0-9_-]+", parts[1]):
        return ()
    try:
        raw = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        if len(raw) > MAX_LOCAL_JWT_PAYLOAD_BYTES:
            return ()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return ()
        email = payload.get("email")
        sub = payload.get("sub")
        # Official CLI uses email first, then an email-like sub. If both carry
        # email identities, detect disagreement rather than silently choosing one.
        accounts = []
        if isinstance(email, str) and email:
            accounts.append(email)
        if isinstance(sub, str) and "@" in sub:
            accounts.append(sub)
        return tuple(accounts)
    except (ValueError, UnicodeError, binascii.Error, RecursionError):
        return ()


@dataclass(frozen=True)
class SecretSelectors:
    token_env: str = "GCUBE_API_TOKEN"
    email_env: str = "GCUBE_EMAIL"

    def __post_init__(self):
        _require(bool(_ENV.fullmatch(self.token_env)) and
                 bool(_ENV.fullmatch(self.email_env)), "INVALID_SECRET_SELECTOR")
        _require(self.token_env != self.email_env, "INVALID_SECRET_SELECTOR")

    def presence(self, environment: Mapping[str, str] | None = None) -> dict:
        env = os.environ if environment is None else environment
        return {self.token_env: bool(env.get(self.token_env)),
                self.email_env: bool(env.get(self.email_env))}


@dataclass(frozen=True)
class Approval:
    approval_id: str
    account: str
    workload_ser: str
    operations: frozenset[str]
    expires_at: str
    max_cost: float
    currency: str
    max_wall_seconds: int
    max_retries: int

    def validate(self, account: str, ser: str, operation: str, now: datetime) -> None:
        _require(isinstance(self.approval_id, str) and bool(re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", self.approval_id)),
                 "EXPLICIT_APPROVAL_REQUIRED")
        _require(isinstance(self.operations, frozenset) and bool(self.operations) and
                 self.operations <= {"stop", "start", "schedule", "schedule_rollback"},
                 "INVALID_APPROVAL_OPERATIONS")
        _require(self.account == account and self.workload_ser == ser and
                 operation in self.operations, "APPROVAL_SCOPE_MISMATCH")
        _require(_utc(self.expires_at) > now, "APPROVAL_EXPIRED")
        _require(_finite(self.max_cost) and self.max_cost > 0 and
                 self.currency in ("USD", "KRW"), "FINITE_COST_LIMIT_REQUIRED")
        _require(type(self.max_wall_seconds) is int and 1 <= self.max_wall_seconds <= 86400,
                 "FINITE_WALL_LIMIT_REQUIRED")
        _require(type(self.max_retries) is int and 0 <= self.max_retries <= 2,
                 "BOUNDED_RETRIES_REQUIRED")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OperationsError("API_REDIRECT_REJECTED")


class HttpsJSONTransport:
    """Verified TLS, inherited platform proxy, no redirects or automatic retry."""

    def __call__(self, method, url, headers, body, timeout):
        _require(url.startswith(API_ORIGIN + "/api/"), "API_ORIGIN_REJECTED")
        request = Request(url, data=None if body is None else json.dumps(
            body, allow_nan=False).encode(), headers=headers, method=method)
        try:
            with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
                _require(response.status == 200, "API_HTTP_REJECTED")
                payload = response.read(MAX_RESPONSE_BYTES + 1)
            _require(len(payload) <= MAX_RESPONSE_BYTES, "API_RESPONSE_TOO_LARGE")
            return json.loads(payload)
        except OperationsError:
            raise
        except HTTPError as error:
            raise OperationsError("API_AUTH_REJECTED" if error.code in (401, 403)
                                  else "API_HTTP_REJECTED") from None
        except (URLError, OSError, ValueError):
            raise OperationsError("API_TRANSPORT_FAILED") from None


class GcubeOperations:
    def __init__(self, token: str, account: str, *, transport=None,
                 request_timeout: float = 15, clock: Callable | None = None):
        _require(isinstance(token, str) and bool(token) and len(token) <= 65536 and
                 not any(c.isspace() for c in token), "AUTH_SECRET_REQUIRED")
        _require(isinstance(account, str) and bool(re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+_=?^`{|}~-]+@[A-Za-z0-9.-]+", account)) and
            len(account) <= 254, "ACCOUNT_BINDING_REQUIRED")
        _require(_finite(request_timeout) and 0 < request_timeout <= 30,
                 "BOUNDED_REQUEST_TIMEOUT_REQUIRED")
        self.__token = token
        self.__account = account
        self.__transport = transport or HttpsJSONTransport()
        self.__timeout = request_timeout
        self.__clock = clock or (lambda: datetime.now(timezone.utc))
        self.__token_account_binding_verified = False

    @classmethod
    def from_environment(cls, selectors: SecretSelectors | None = None, *,
                         environment: Mapping[str, str] | None = None, **kwargs):
        selectors = selectors or SecretSelectors()
        env = os.environ if environment is None else environment
        return cls(env.get(selectors.token_env, ""), env.get(selectors.email_env, ""), **kwargs)

    def _request(self, operation: str, ser: str | None = None, *, timeout=None, approval=None):
        if ser is not None:
            _require(isinstance(ser, str) and bool(_SER.fullmatch(ser)), "INVALID_WORKLOAD_SER")
        base = f"/api/workloads/gai/{ser}"
        # Exact action allowlist: GET deploy/finish must never be mistaken for reads.
        routes = {
            "identity": ("GET", "/api/users/" + quote(self.__account, safe="")),
            "describe": ("GET", base),
            "schedules": ("GET", base + "/schedule"),
            "schedule_history": ("GET", base + "/schedule/logs?startNum=0&scaleNum=20"),
            "pricing": ("GET", "/api/gpu/available/pricing/list"),
            "points": ("GET", "/api/point/status?" + urlencode({"owner": self.__account})),
            "stop": ("GET", base + "/state/finish"),
        }
        _require(operation in routes, "OPERATION_NOT_ALLOWLISTED")
        _require(operation in ("identity", "pricing", "points") or ser is not None,
                 "INVALID_WORKLOAD_SER")
        if operation == "stop":
            self._approved(ser, "stop", approval)
            _require(self.__token_account_binding_verified, "AUTH_ACCOUNT_BINDING_UNVERIFIED")
        method, route = routes[operation]
        try:
            result = self.__transport(method, API_ORIGIN + route,
                                      {"Authorization": "Bearer " + self.__token,
                                       "Content-Type": "application/json"}, None,
                                      self.__timeout if timeout is None else timeout)
            _require(isinstance(result, dict) and type(result.get("status")) is int and
                     result["status"] == 200, "API_ENVELOPE_REJECTED")
            return result
        except OperationsError:
            raise
        except Exception:
            raise OperationsError("API_TRANSPORT_FAILED") from None

    def _identity(self, *, timeout=None):
        self.__token_account_binding_verified = False
        accounts = _local_token_accounts(self.__token)
        _require(not accounts or all(account == self.__account for account in accounts),
                 "AUTH_TOKEN_ACCOUNT_MISMATCH")
        user = self._request("identity", timeout=timeout).get("user")
        _require(isinstance(user, dict) and user.get("email") == self.__account and
                 isinstance(user.get("namespace"), str) and bool(user["namespace"]),
                 "AUTHENTICATED_ACCOUNT_MISMATCH")
        self.__token_account_binding_verified = bool(accounts)
        return {"authenticatedRequestSucceeded": True,
                "tokenAccountBindingVerified": bool(accounts),
                "tokenClaimsCryptographicallyVerified": False,
                "identityBindingEvidence": (
                    "LOCAL_UNSIGNED_CLAIM_MATCH_PLUS_AUTHENTICATED_USER_LOOKUP" if accounts else
                    "UNVERIFIED_OPAQUE_OR_UNDECODABLE_TOKEN")}

    def _describe(self, ser: str, *, timeout=None):
        envelope = self._request("describe", ser, timeout=timeout)
        workload = envelope.get("workload", envelope.get("data", envelope))
        _require(isinstance(workload, dict) and str(workload.get("ser")) == ser and
                 workload.get("owner") == self.__account and
                 not workload.get("teamId"), "WORKLOAD_ACCOUNT_MISMATCH")
        return workload

    @staticmethod
    def _phase(workload):
        ops = workload.get("operations")
        if isinstance(ops, list) and ops and isinstance(ops[0], dict):
            latest = ops[0]
            if latest.get("status") in _FAILURES:
                return "failed", False
            if latest.get("status") == "COMPLETED":
                if latest.get("type") == "STOP":
                    return "finished", True
                if latest.get("type") == "START":
                    return "running", False
            return ("stopping" if latest.get("type") == "STOP" else "starting"), False
        return {"finish": "finished", "open": "idle", "deploy": "running"}.get(
            workload.get("state"), "unknown"), False

    def _schedules(self, ser: str):
        data = self._request("schedules", ser)
        items = data.get("schedules")
        _require(isinstance(items, list) and len(items) <= 500, "INVALID_SCHEDULE_RESPONSE")
        normalized = []
        zones = set()
        for item in items:
            _require(isinstance(item, dict) and type(item.get("enabled")) is bool and
                     item.get("action") in ("START", "STOP") and
                     type(item.get("daysOfWeek")) is int and 0 <= item["daysOfWeek"] <= 127 and
                     isinstance(item.get("time"), str) and bool(re.fullmatch(
                         r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", item["time"])),
                     "INVALID_SCHEDULE_RESPONSE")
            zone = item.get("timeZone")
            if zone:
                _require(zone == "Asia/Seoul", "UNSUPPORTED_SCHEDULE_TIMEZONE")
                zones.add(zone)
            entry = {"enabled": item["enabled"], "action": item["action"],
                     "daysOfWeek": item["daysOfWeek"], "time": item["time"],
                     "date": item.get("scheduleDate"), "endDate": item.get("endDate")}
            for field in ("date", "endDate"):
                if entry[field] is not None:
                    try:
                        _require(datetime.strptime(entry[field], "%Y-%m-%d").strftime(
                            "%Y-%m-%d") == entry[field], "INVALID_SCHEDULE_RESPONSE")
                    except (ValueError, TypeError):
                        raise OperationsError("INVALID_SCHEDULE_RESPONSE") from None
            _require((entry["date"] is not None and entry["daysOfWeek"] == 0 and
                      entry["endDate"] is None) or
                     (entry["date"] is None and entry["daysOfWeek"] > 0),
                     "INVALID_SCHEDULE_RESPONSE")
            normalized.append(entry)
        zone = data.get("timeZone")
        _require(zone is None or zone == "Asia/Seoul", "UNSUPPORTED_SCHEDULE_TIMEZONE")
        # Missing timezone for existing entries cannot establish a safe replacement.
        return {"timeZone": zone or ("Asia/Seoul" if zones else None), "schedules": normalized}

    def preflight(self, workload_ser: str) -> dict:
        """Authenticated reads only. No claim of GPU, billing cap or SSH readiness."""
        identity = self._identity()
        workload = self._describe(workload_ser)
        schedules = self._schedules(workload_ser)
        cost = self.cost_snapshot()
        phase, stopped = self._phase(workload)
        return {"schema": "GCUBE_PREFLIGHT_V3", **identity,
                "workloadSer": workload_ser, "phase": phase,
                "providerStopOperationVerified": stopped,
                "scheduleCount": len(schedules["schedules"]),
                "scheduleSnapshotSha256": _digest(schedules), "cost": cost,
                "hardCostCapSupported": False, "launchExecutable": False,
                "sshVerified": False, "hardwareGpuVerified": False}

    def cost_snapshot(self) -> dict:
        """Official account points/pricing reads; rates are observations, not caps."""
        identity = self._identity()
        raw = self._request("points")
        points = raw.get("data", raw)
        _require(isinstance(points, dict), "INVALID_POINTS_RESPONSE")
        points = points.get("points", points)
        _require(isinstance(points, dict), "INVALID_POINTS_RESPONSE")
        point_fields = {}
        for key in ("availablePoint", "chargePoint", "spendPoint", "netPoint"):
            _require(_finite(points.get(key)), "INVALID_POINTS_RESPONSE")
            point_fields[key] = points[key]
        for key in ("isBlocked", "isAlarm"):
            _require(type(points.get(key)) is bool, "INVALID_POINTS_RESPONSE")
            point_fields[key] = points[key]
        raw = self._request("pricing")
        rows = raw.get("pricings", raw.get("data"))
        _require(isinstance(rows, list) and len(rows) <= 10000, "INVALID_PRICING_RESPONSE")
        prices = []
        for row in rows:
            _require(isinstance(row, dict) and _finite(row.get("price")) and
                     _finite(row.get("usagePrice")) and row["price"] >= 0 and
                     row["usagePrice"] >= 0 and row.get("currencyUnit") in ("USD", "KRW"),
                     "INVALID_PRICING_RESPONSE")
            gpu_identity = {}
            for field in ("gpuName", "productName", "gpuExt", "productCode"):
                value = row.get(field)
                if isinstance(value, str) and bool(re.fullmatch(
                        r"[A-Za-z0-9 ._()/+-]{1,96}", value)) and self.__token not in value:
                    gpu_identity[field] = value
            for field in ("gpu", "vram", "cpu", "memory", "disk", "ppIndex"):
                value = row.get(field)
                if type(value) is int and 0 <= value <= 1000000000:
                    gpu_identity[field] = value
            complete = {"gpuName", "productName", "gpu", "vram", "cpu", "memory", "disk"} <= gpu_identity.keys()
            prices.append({"price": row["price"], "usagePrice": row["usagePrice"],
                           "currencyUnit": row["currencyUnit"], **gpu_identity,
                           "gpuIdentityComplete": complete, "rateBindingVerified": False,
                           "rateBindingReason": "WORKLOAD_GPU_SPEC_MATCH_NOT_PERFORMED" if complete else
                           "GPU_IDENTITY_INCOMPLETE_OR_UNSAFE"})
        return {**identity, "points": point_fields, "pricingRows": prices,
                "rateBindingVerified": False,
                "interpretation": "OFFICIAL_OBSERVED_RATE_FIELDS_ONLY_NO_TOTAL_COST_GUARANTEE",
                "hardCostCapSupported": False}

    def _approved(self, ser, operation, approval):
        _require(isinstance(ser, str) and bool(_SER.fullmatch(ser)), "INVALID_WORKLOAD_SER")
        _require(isinstance(approval, Approval), "EXPLICIT_APPROVAL_REQUIRED")
        approval.validate(self.__account, ser, operation, self.__clock())

    def plan_start(self, workload_ser: str, *, approval=None, stop_at=None) -> dict:
        """Local plan only, including when approval and STOP evidence are supplied."""
        _require(isinstance(workload_ser, str) and bool(_SER.fullmatch(workload_ser)),
                 "INVALID_WORKLOAD_SER")
        if approval is not None:
            self._approved(workload_ser, "start", approval)
        if stop_at is not None:
            _require(_utc(stop_at) > self.__clock(), "STOP_DEADLINE_MUST_BE_FUTURE")
        return {"operation": "start", "workloadSer": workload_ser, "executable": False,
                "status": "BLOCKED", "reason": "STRICT_PROVIDER_COST_CAP_UNSUPPORTED",
                "stopScheduleMustBeVerifiedBeforeStart": True,
                "processTimeoutStopsBilling": False, "accountCallExecuted": False}

    def start(self, workload_ser: str, *, approval=None, stop_at=None):
        self._approved(workload_ser, "start", approval)
        self.plan_start(workload_ser, approval=approval, stop_at=stop_at)
        raise OperationsError("STRICT_PROVIDER_COST_CAP_UNSUPPORTED")

    def deploy(self, workload_ser: str, *, approval=None, stop_at=None):
        return self.start(workload_ser, approval=approval, stop_at=stop_at)

    def register(self, *, approval=None):
        raise OperationsError("STRICT_PROVIDER_COST_CAP_UNSUPPORTED")

    def plan_stop_schedule(self, workload_ser: str, *, stop_at: str, approval: Approval) -> dict:
        self._approved(workload_ser, "schedule", approval)
        self._identity()
        self._describe(workload_ser)
        deadline = _utc(stop_at)
        remaining = (deadline - self.__clock()).total_seconds()
        _require(60 <= remaining <= approval.max_wall_seconds, "STOP_OUTSIDE_APPROVED_WALL_LIMIT")
        _require(deadline.second == 0 and deadline.microsecond == 0,
                 "STOP_SCHEDULE_MINUTE_PRECISION_REQUIRED")
        from zoneinfo import ZoneInfo
        local = deadline.astimezone(ZoneInfo("Asia/Seoul"))
        prior = self._schedules(workload_ser)
        _require(prior["timeZone"] is not None or not prior["schedules"],
                 "EXISTING_SCHEDULE_TIMEZONE_UNKNOWN")
        prior["timeZone"] = "Asia/Seoul"
        new = {"enabled": True, "action": "STOP", "daysOfWeek": 0,
               "time": local.strftime("%H:%M"), "date": local.strftime("%Y-%m-%d"),
               "endDate": None}
        desired = {"timeZone": "Asia/Seoul", "schedules": prior["schedules"] + [new]}
        return {"operation": "schedule", "workloadSer": workload_ser,
                "executable": False, "status": "BLOCKED",
                "reason": "SCHEDULE_ATOMIC_UPDATE_UNSUPPORTED",
                "before": prior, "beforeSha256": _digest(prior), "desired": desired,
                "desiredSha256": _digest(desired), "stopAtUtc": deadline.isoformat(),
                "rollback": {"maxWrites": 1, "requiresExactCurrentDesiredHash": True,
                             "restore": prior}, "mutationExecuted": False}

    def install_stop_schedule(self, plan: dict, *, approval=None):
        self._approved(plan.get("workloadSer"), "schedule", approval)
        raise OperationsError("SCHEDULE_ATOMIC_UPDATE_UNSUPPORTED")

    def rollback_stop_schedule(self, receipt: dict, *, approval=None):
        self._approved(receipt.get("workloadSer"), "schedule_rollback", approval)
        raise OperationsError("SCHEDULE_ATOMIC_UPDATE_UNSUPPORTED")

    def verify_stop_schedule(self, workload_ser: str, *, stop_at: str) -> dict:
        self._identity()
        self._describe(workload_ser)
        from zoneinfo import ZoneInfo
        deadline = _utc(stop_at)
        _require(deadline > self.__clock() and deadline.second == 0 and deadline.microsecond == 0,
                 "INVALID_FUTURE_STOP_DEADLINE")
        local = deadline.astimezone(ZoneInfo("Asia/Seoul"))
        snapshot = self._schedules(workload_ser)
        _require(snapshot["timeZone"] == "Asia/Seoul", "STOP_TIMEZONE_NOT_VERIFIED")
        matches = [s for s in snapshot["schedules"] if s == {
            "enabled": True, "action": "STOP", "daysOfWeek": 0,
            "time": local.strftime("%H:%M"), "date": local.strftime("%Y-%m-%d"), "endDate": None}]
        _require(bool(matches), "STOP_SCHEDULE_NOT_VERIFIED")
        return {"stopScheduleVerified": True, "stopAtUtc": deadline.isoformat(),
                "snapshotSha256": _digest(snapshot), "scheduleExecutionVerified": False,
                "billingTerminationGuaranteed": False}

    def verify_stopped(self, workload_ser: str) -> dict:
        self._identity()
        phase, verified = self._phase(self._describe(workload_ser))
        return {"phase": phase, "providerStopOperationVerified": verified,
                "billingTerminationGuaranteed": False}

    def schedule_history(self, workload_ser: str) -> dict:
        self._identity()
        self._describe(workload_ser)
        rows = self._request("schedule_history", workload_ser).get("logs")
        _require(isinstance(rows, list) and len(rows) <= 20, "INVALID_SCHEDULE_HISTORY")
        # Provider logs may contain private data. Only return counts, never bodies.
        return {"historyRead": True, "entryCount": len(rows), "executionInferred": False}

    def stop(self, workload_ser: str, *, approval: Approval) -> dict:
        """One approved stop request; no retry. Timeout is never billing proof."""
        self._approved(workload_ser, "stop", approval)
        begun = time.monotonic()
        def remaining_timeout():
            remaining = approval.max_wall_seconds - (time.monotonic() - begun)
            _require(remaining > 0, "APPROVED_WALL_LIMIT_EXPIRED")
            return min(self.__timeout, remaining)
        identity = self._identity(timeout=remaining_timeout())
        _require(identity["tokenAccountBindingVerified"], "AUTH_ACCOUNT_BINDING_UNVERIFIED")
        self._describe(workload_ser, timeout=remaining_timeout())
        self._approved(workload_ser, "stop", approval)
        timeout = remaining_timeout()
        try:
            self._request("stop", workload_ser, timeout=timeout, approval=approval)
        except OperationsError:
            raise OperationsError("STOP_OUTCOME_UNKNOWN_VERIFY_SEPARATELY_NO_RETRY") from None
        remaining = approval.max_wall_seconds - (time.monotonic() - begun)
        _require(remaining > 0, "STOP_REQUESTED_VERIFICATION_TIME_EXPIRED")
        # One immediate readback; caller may make separately bounded read-only polls.
        try:
            phase, verified = self._phase(self._describe(workload_ser, timeout=remaining_timeout()))
        except OperationsError:
            raise OperationsError("STOP_REQUESTED_VERIFICATION_FAILED_VERIFY_SEPARATELY") from None
        return {"operation": "stop", "requestAccepted": True, "mutationAttempts": 1,
                "automaticRetries": 0, "phase": phase,
                "providerStopOperationVerified": verified,
                "billingTerminationGuaranteed": False}

    def ssh(self, *args, **kwargs):
        raise OperationsError("APPROVED_SSH_KEY_KNOWN_HOSTS_AND_TCP_GRANT_REQUIRED")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("capabilities", "preflight"))
    parser.add_argument("--workload-ser")
    parser.add_argument("--allow-account-read", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.operation == "capabilities":
            from pathlib import Path
            result = json.loads(Path(__file__).with_name("OPERATIONS_CAPABILITIES.json").read_text())
        else:
            _require(args.allow_account_read, "EXPLICIT_ACCOUNT_READ_REQUIRED")
            _require(bool(args.workload_ser), "INVALID_WORKLOAD_SER")
            result = GcubeOperations.from_environment().preflight(args.workload_ser)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except OperationsError as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
