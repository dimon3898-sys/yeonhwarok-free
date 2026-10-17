#!/usr/bin/env python3
"""Optional official HTTP log retrieval; no deployment or authentication changes.

Only closed-vocabulary summaries leave this process. The HTTP helper is shipped
by gcube-cli 0.4.2; its existence does not establish archived-log retention.
"""
from __future__ import annotations
import argparse
import ast
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

import collector

WORKLOAD = "5373"
MAX_LOG_BYTES = 512 * 1024
RAW_STATES = frozenset(("open", "deploy", "finish"))
POD_STATES = collector.STATES | frozenset(("Terminating", "ImagePullBackOff", "ErrImagePull", "NotFound", "Deleted"))
POD_NAME = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?\Z", re.ASCII)
PREFIX = "WORLD_ENGINE_STUDIO_"
POLICY_KEYS = {"validUntil", "maxWallSeconds", "maxRetries", "maxCostAmount", "currency", "gpuHourlyRate"}
APPROVED_TAG = "studio-v1-344dc2d-38883417252-1"
APPROVED_DIGEST = "sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94"


def official_api(token):
    from importlib.metadata import version
    if version("gcube-cli") != "0.4.2":
        raise RuntimeError("OFFICIAL_CLI_VERSION_REQUIRED")
    from gcube_cli.api.client import Client
    from gcube_cli.api.workload import WorkloadAPI
    # Never accept an arbitrary URL or enable request debugging.
    return WorkloadAPI(Client("https://api.gcube.ai", token, debug=False))


def numeric_code(value):
    if type(value) is int and 0 <= value <= 999:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,3}", value):
        return int(value)
    return None


def safe_exception(error):
    """Never stringify exceptions, which may contain tokens, URLs or API bodies."""
    kind = type(error).__name__
    return {"status": "FAILED", "error_category": {
        "APIError": "API_ERROR", "AuthError": "AUTH_REJECTED",
        "SystemExit": "OFFICIAL_CLIENT_EXIT"}.get(kind, "UNEXPECTED_ERROR"),
        "http_or_api_status": numeric_code(getattr(error, "status_code", None)),
        "api_numeric_code": numeric_code(getattr(error, "code", None))}


def environment_summary(container):
    rows = container.get("containerEnvs")
    values = {}
    shape_valid = isinstance(rows, list)
    duplicates = False
    if shape_valid:
        for row in rows:
            if not isinstance(row, dict) or len(row) != 1:
                shape_valid = False
                continue
            key, value = next(iter(row.items()))
            if not isinstance(key, str) or not isinstance(value, str):
                shape_valid = False
                continue
            if key in values:
                duplicates = True
            values[key] = value
    # Conflicting or unsupported input must not be treated as verified settings.
    if not shape_valid or duplicates:
        return {"environment_shape_verified": False,
            "duplicate_keys_present": duplicates, "configuration_checks": None}
    def present(key):
        return key in values
    origin = values.get(PREFIX + "PUBLIC_ORIGIN", "")
    try:
        parsed = urlsplit(origin)
        origin_valid = bool(parsed.scheme == "https" and parsed.hostname
            and not any((parsed.path, parsed.query, parsed.fragment, parsed.username, parsed.password)))
    except ValueError:
        origin_valid = False
    owner = values.get(PREFIX + "OWNER_CODE", "")
    policy_valid = None
    if present(PREFIX + "OPERATOR_POLICY_JSON"):
        try:
            policy = json.loads(values[PREFIX + "OPERATOR_POLICY_JSON"])
            policy_valid = (isinstance(policy, dict) and POLICY_KEYS <= policy.keys()
                and not set(policy) - POLICY_KEYS - {"schema"}
                and ("schema" not in policy or policy["schema"] == "WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1"))
        except (ValueError, TypeError, RecursionError):
            policy_valid = False
    digest = values.get("WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST", "")
    port = values.get(PREFIX + "PORT", "8080")
    port_valid = bool(re.fullmatch(r"[1-9][0-9]{3,4}", port) and 1024 <= int(port) <= 65535 and int(port) != 8000)
    image = container.get("containerImage")
    image_match = isinstance(image, str) and (image == APPROVED_TAG
        or image == "ghcr.io/dimon3898-sys/world-simulation-shorts-engine:" + APPROVED_TAG
        or image == "ghcr.io/dimon3898-sys/world-simulation-shorts-engine@" + APPROVED_DIGEST)
    return {"environment_shape_verified": True, "duplicate_keys_present": False,
        "configuration_checks": {
            "prefixed_origin_present": present(PREFIX + "PUBLIC_ORIGIN"), "origin_format_valid": origin_valid,
            "prefixed_owner_present": present(PREFIX + "OWNER_CODE"),
            "owner_format_valid": 16 <= len(owner) <= 256 and all(33 <= ord(char) <= 126 for char in owner),
            "owner_private_file_state": "NOT_INSPECTED",
            "prefixed_operator_policy_present": present(PREFIX + "OPERATOR_POLICY_JSON"),
            "policy_startup_structure_valid": policy_valid,
            "policy_missing_is_startup_failure": False,
            "universal_image_digest_present": present("WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST"),
            "image_digest_format_valid": bool(re.fullmatch(r"sha256:[a-f0-9]{64}", digest)),
            "image_digest_matches_approved": digest == APPROVED_DIGEST,
            "configured_image_matches_approved": image_match,
            "studio_port_format_valid": port_valid,
            "container_port_is_8080": container.get("port") in (8080, "8080"),
            "command_override_empty": container.get("containerCommand") in (None, ""),
            "startup_mode": collector.closed_value(values.get("WORLD_ENGINE_STARTUP_MODE"), {"normal", "diagnostic"}, "ABSENT_OR_WITHHELD"),
            "render_mode": collector.closed_value(values.get("WORLD_ENGINE_RENDER_MODE"), {"gpu-required"}, "ABSENT_OR_WITHHELD"),
            "unprefixed_origin_present": present("PUBLIC_ORIGIN"),
            "unprefixed_owner_present": present("OWNER_CODE"),
            "unprefixed_policy_present": present("OPERATOR_POLICY_JSON"),
            "unprefixed_image_digest_present": present("IMAGE_DIGEST")}}


def log_documents(value):
    if not isinstance(value, str):
        return [], False
    raw = value.encode("utf-8", errors="replace")
    if len(raw) > MAX_LOG_BYTES:
        return [], True
    documents = collector.json_documents(raw)
    if not documents and value.lstrip().startswith(("{", "[")):
        # The official API helper converts nested data with str(dict/list).
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, (dict, list)):
                documents = [parsed]
        except (ValueError, SyntaxError, TypeError, RecursionError, MemoryError):
            pass
    return documents, False


def collect(environ=None, *, factory=official_api):
    environ = os.environ if environ is None else environ
    token = environ.get("GCUBE_ACCESS_TOKEN")
    result = {"schema": "WORLD_ENGINE_OFFICIAL_HTTP_LOG_EVIDENCE_V1", "workload": 5373,
        "utc": datetime.now(timezone.utc).isoformat(), "status": "BLOCKED",
        "credential_values_published": False, "raw_outputs_published": False,
        "paid_operations": 0, "state_changes": 0, "actual_cause_confirmed": False,
        "actual_container_exit_code": None, "first_actual_error": None, "operations": []}
    if not isinstance(token, str) or not token:
        result["blocking_reason"] = "APPROVED_SECRET_CREDENTIAL_NOT_PROVIDED"
        return result
    operation = "OFFICIAL_CLIENT_INITIALIZATION"
    # API libraries may echo free-form messages; discard them in a private file.
    with tempfile.TemporaryFile(mode="w+") as private_output:
        os.fchmod(private_output.fileno(), 0o600)
        with redirect_stdout(private_output), redirect_stderr(private_output):
            try:
                api = factory(token)
                operation = "WORKLOAD_DESCRIBE"
                workload = api.describe(WORKLOAD)
                raw = getattr(workload, "raw", {})
                if not isinstance(raw, dict) or str(raw.get("ser")) != WORKLOAD:
                    result["blocking_reason"] = "WORKLOAD_ID_NOT_VERIFIED"
                    return result
                result["operations"].append({"operation": operation, "status": "SUCCEEDED"})
                result["raw_workload_state"] = collector.closed_value(raw.get("state"), RAW_STATES, "WITHHELD_UNKNOWN")
                containers = raw.get("containerArray")
                if isinstance(containers, list) and len(containers) == 1 and isinstance(containers[0], dict):
                    result["configuration"] = environment_summary(containers[0])
                operation = "WORKLOAD_PODS"
                pods = api.pods(WORKLOAD)
                result["operations"].append({"operation": operation, "status": "SUCCEEDED"})
                result["pod_count"] = len(pods) if isinstance(pods, list) else None
                result["pod_statuses"] = [collector.closed_value(pod.get("status"), POD_STATES, "WITHHELD_UNKNOWN")
                    for pod in pods if isinstance(pod, dict)] if isinstance(pods, list) else []
                records = collector.terminated_states({"pods": pods})
                result["terminated_container_records"] = records
                codes = {record["exit_code"] for record in records}
                if len(codes) == 1:
                    result["actual_container_exit_code"] = next(iter(codes))
                if not isinstance(pods, list) or len(pods) != 1 or not isinstance(pods[0], dict):
                    result["blocking_reason"] = "UNAMBIGUOUS_EXISTING_POD_REQUIRED"
                    return result
                pod = pods[0].get("name")
                if not isinstance(pod, str) or not POD_NAME.fullmatch(pod) or ".." in pod:
                    result["blocking_reason"] = "AUTHORIZED_POD_NAME_NOT_VALIDATED"
                    return result
                operation = "OFFICIAL_HTTP_POD_LOGS"
                logs = api.logs(WORKLOAD, pod)
                documents, oversized = log_documents(logs)
                result["operations"].append({"operation": operation, "status": "SUCCEEDED"})
                result["log_size_limit_exceeded"] = oversized
                result["structured_log_document_count"] = len(documents)
                result["first_actual_error"] = collector.first_error(documents)
                result["status"] = "READ_ONLY_HTTP_EVIDENCE_COLLECTED"
                result["remaining_limits"] = ["ARCHIVED_LOG_RETENTION_NOT_ESTABLISHED",
                    "FIRST_RECEIVED_ERROR_NOT_PROOF_OF_FIRST_HISTORICAL_ERROR",
                    "NO_GPU_EXECUTION_OR_CRASH_FIX_CONFIRMED"]
            except (Exception, SystemExit) as error:
                summary = safe_exception(error)
                result["operations"].append({"operation": operation, **summary})
                result["blocking_reason"] = summary["error_category"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect()
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / "REST_RESULT.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(result, target, sort_keys=True, indent=2)
        target.write("\n")


if __name__ == "__main__":
    main()
