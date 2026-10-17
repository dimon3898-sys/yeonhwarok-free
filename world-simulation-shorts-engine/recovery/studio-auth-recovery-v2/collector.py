#!/usr/bin/env python3
"""Read-only official gcube CLI collection with no public raw log output.

Credentials are supplied only by the invoking approved Secret environment.
This tool neither installs credentials nor edits gcube configuration. In CI the
legacy Secret can be tested as an opaque bearer value, but compatibility is
reported only after an authenticated workload describe actually succeeds.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile

WORKLOAD = "5373"
ALLOWED_COMMANDS = (
    ("--version",),
    ("-o", "json", "workload", "describe", WORKLOAD),
    ("-o", "json", "workload", "pods", WORKLOAD),
    ("workload", "logs", WORKLOAD),
)
MAX_CAPTURE_BYTES = 8 * 1024 * 1024
# Deliberate closed vocabulary. Unknown free-form values are never published,
# including values placed in an otherwise legitimate errorCode/status field.
ERROR_CODES = frozenset("""
STUDIO_BOOTSTRAP_FAILED STUDIO_STARTUP_BLOCKED STUDIO_HTTPS_ORIGIN_REQUIRED
STUDIO_OWNER_CONFIGURATION_REQUIRED STUDIO_OWNER_CODE_LENGTH_REQUIRED
STUDIO_OPERATOR_POLICY_JSON_REQUIRED STUDIO_OPERATOR_POLICY_FIELDS_REQUIRED
STUDIO_DISTINCT_PORT_REQUIRED STUDIO_ROOT_BOOTSTRAP_REQUIRED
STUDIO_PRIVATE_DIRECTORY_REQUIRED STUDIO_PRIVATE_FILE_REQUIRED
STUDIO_PRIVATE_IDENTITY_REQUIRED STUDIO_PRIVATE_LOCAL_STATE_REQUIRED
STUDIO_PRIVATE_PATH_SYMLINK_FORBIDDEN STUDIO_EXISTING_PRIVATE_CONFIGURATION_PRESERVED
STUDIO_ENGINE_ACCOUNT_REQUIRED STUDIO_ENGINE_HOME_REQUIRED
STUDIO_FROZEN_DEVICE_GROUP_HELPER_REQUIRED STUDIO_DEVICE_GROUP_ALLOWLIST_REQUIRED
STUDIO_ORIGINAL_GPU_HEALTH_NOT_READY STUDIO_IMAGE_DIGEST_REQUIRED
STUDIO_EXPLICIT_ORIGIN_REQUIRED STUDIO_HTTPS_REQUIRED STUDIO_OWNER_FILE_REQUIRED
STUDIO_STATE_MUST_BE_PRIVATE STUDIO_STATE_UNSAFE STUDIO_FROZEN_SECURITY_CHANGED
STORAGE_VALIDATION_FAILED SOURCE_INTEGRITY_FAILED DEPENDENCY_VALIDATION_FAILED
NVIDIA_VALIDATION_FAILED NVIDIA_DEVICE_NOT_FOUND NVIDIA_DEVICE_UNAVAILABLE
NVIDIA_SMI_FAILED GPU_VALIDATION_FAILED GPU_REQUIRED WEBGL2_VALIDATION_FAILED
WEBGL2_UNAVAILABLE GRAPHICS_INITIALIZATION_FAILED GPU_MEMORY_INSUFFICIENT
SHARED_MEMORY_INSUFFICIENT STARTUP_EXCEPTION DIAGNOSTIC_ONLY
""".split())
STAGES = frozenset(("STORAGE", "SOURCE", "SOURCE_INTEGRITY", "DEPENDENCIES",
    "IDENTITY", "NVIDIA", "GPU", "EGL", "VULKAN", "WEBGL2", "MEMORY",
    "STARTUP", "STUDIO", "BOOTSTRAP", "HEALTH", "SERVICE"))
STATES = frozenset(("open", "deploy", "finish", "stop", "close", "ready", "wait", "error",
    "pending", "running", "failed", "stopped", "terminated", "unknown",
    "Pending", "Running", "Succeeded", "Failed", "Unknown", "Waiting",
    "CrashLoopBackOff", "ContainerCreating", "Error", "Completed"))
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$")


@dataclass(frozen=True)
class Capture:
    returncode: int | None
    timed_out: bool
    stdout: bytes
    stderr: bytes
    truncated: bool = False


def safe_time(value):
    if isinstance(value, str) and TIMESTAMP.fullmatch(value):
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value
        except ValueError:
            pass
    return None


def closed_value(value, vocabulary, default=None):
    return value if isinstance(value, str) and value in vocabulary else default


def json_documents(raw):
    """Accept one JSON output or newline-delimited JSON; never parse prose."""
    text = raw.decode("utf-8", errors="replace")
    try:
        document = json.loads(text)
    except (ValueError, TypeError):
        document = None
    if isinstance(document, (dict, list)):
        return [document]
    output = []
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(value, (dict, list)):
            output.append(value)
    return output


def cli_failure(capture):
    """Return an enum only; original errors may contain tokens or request URLs."""
    if capture.timed_out:
        return "TIMEOUT"
    if capture.returncode == 0:
        return None
    raw = (capture.stdout + b"\n" + capture.stderr).lower()
    if b"no token configured" in raw or b"not logged in" in raw:
        return "NO_TOKEN"
    if any(pattern in raw for pattern in (b"unauthorized", b"forbidden", b"401", b"403", b"authentication", b"invalid token")):
        return "AUTH_REJECTED"
    if any(pattern in raw for pattern in (b"connection", b"network", b"name resolution", b"proxy", b"ssl", b"certificate", b"timed out")):
        return "NETWORK"
    if b"not running" in raw:
        return "WORKLOAD_NOT_RUNNING"
    if b"no running pods" in raw:
        return "NO_RUNNING_PODS"
    return "OTHER_WITHHELD"


def capture_command(binary, arguments, environ, timeout_seconds=45):
    arguments = tuple(arguments)
    if arguments not in ALLOWED_COMMANDS:
        raise ValueError("COMMAND_NOT_ALLOWED")
    if not 1 <= timeout_seconds <= 60:
        raise ValueError("TIMEOUT_OUT_OF_RANGE")
    # The directory and both raw captures remain private, are never artifacts,
    # and are removed after each command. Nothing is echoed from the child.
    with tempfile.TemporaryDirectory(prefix="studio-gcube-private-") as directory:
        os.chmod(directory, 0o700)
        stdout_path, stderr_path = Path(directory) / "stdout", Path(directory) / "stderr"
        descriptors = [os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            for path in (stdout_path, stderr_path)]
        try:
            with os.fdopen(descriptors[0], "w+b") as out, os.fdopen(descriptors[1], "w+b") as err:
                try:
                    child = subprocess.Popen([binary, *arguments], env=environ,
                        stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                        start_new_session=True)
                except (OSError, ValueError):
                    return Capture(None, False, b"", b"", False)
                timed_out = False
                try:
                    child.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait()
                out.flush(); err.flush()
                too_large = any(os.fstat(handle.fileno()).st_size > MAX_CAPTURE_BYTES for handle in (out, err))
                out.seek(0); err.seek(0)
                return Capture(child.returncode, timed_out,
                    out.read(MAX_CAPTURE_BYTES), err.read(MAX_CAPTURE_BYTES), too_large)
        finally:
            # fdopen normally closes these; also cover partially opened paths.
            for descriptor in descriptors:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def safe_command_result(arguments, capture):
    return {"command": "gcube " + " ".join(arguments),
        "cli_exit_code": capture.returncode,
        "timed_out": capture.timed_out,
        "capture_truncated": capture.truncated,
        "stdout_captured_bytes": len(capture.stdout),
        "stderr_captured_bytes": len(capture.stderr),
        "error_category": cli_failure(capture)}


def matching_workload(documents):
    for document in documents:
        if isinstance(document, dict) and str(document.get("ser")) == WORKLOAD:
            return document
    return None


def safe_workload(document):
    """Never return names, addresses, owners, commands, images or containerEnvs."""
    state = document.get("state")
    pods = document.get("pods")
    containers = document.get("containers")
    return {"workload": int(WORKLOAD),
        "state": closed_value(state, STATES, "WITHHELD_UNKNOWN"),
        "pod_count": len(pods) if isinstance(pods, list) else None,
        "container_count": len(containers) if isinstance(containers, list) else None,
        "pod_statuses": [closed_value(pod.get("status"), STATES, "WITHHELD_UNKNOWN")
            for pod in pods if isinstance(pod, dict)] if isinstance(pods, list) else [],
        "raw_environment_published": False}


def terminated_states(document):
    """Only explicit Kubernetes terminated state fields count as exit evidence."""
    output = []
    traversable = ("pods", "containers", "containerStatuses", "initContainerStatuses",
        "statuses", "status", "data", "workload")
    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for state_key in ("state", "lastState"):
                state = value.get(state_key)
                if isinstance(state, dict) and isinstance(state.get("terminated"), dict):
                    term = state["terminated"]
                    code = term.get("exitCode")
                    if type(code) is int and 0 <= code <= 255:
                        output.append({"record_type": state_key + ".terminated",
                            "exit_code": code,
                            "started_at": safe_time(term.get("startedAt")),
                            "finished_at": safe_time(term.get("finishedAt"))})
            for key in traversable:
                if key in value:
                    visit(value[key])
    visit(document)
    return output


def first_error(documents):
    """Find the first structured record in received order, without fake prose parsing."""
    def records(value):
        if isinstance(value, list):
            for item in value:
                yield from records(item)
        elif isinstance(value, dict):
            yield value
            for key in ("logs", "records", "events", "diagnostics", "data"):
                if key in value:
                    yield from records(value[key])
    for document in documents:
        for record in records(document):
            code = record.get("errorCode", record.get("error_code", record.get("code")))
            # A generic HTTP/success `code` field is not an error record.
            if ("errorCode" not in record and "error_code" not in record
                    and (not isinstance(code, str) or code not in ERROR_CODES)):
                continue
            if isinstance(code, str) and code:
                stage = record.get("stage")
                timestamp = record.get("timestamp", record.get("utc", record.get("time")))
                return {"error_code": code if code in ERROR_CODES else "WITHHELD_UNKNOWN_CODE",
                    "stage": closed_value(stage, STAGES),
                    "timestamp": safe_time(timestamp),
                    "source": "structured_container_log",
                    "first_record_in_received_stream_only": True}
    return None


def collect(environ=None, *, binary="gcube", runner=capture_command):
    source_environment = dict(os.environ if environ is None else environ)
    official = source_environment.get("GCUBE_ACCESS_TOKEN") or ""
    legacy = source_environment.get("GCUBE_API_TOKEN") or ""
    credential_source = "GCUBE_ACCESS_TOKEN" if official else "GCUBE_API_TOKEN" if legacy else "NONE"
    result = {"schema": "WORLD_ENGINE_GCUBE_READONLY_COLLECTION_V2",
        "utc": datetime.now(timezone.utc).isoformat(), "workload": int(WORKLOAD),
        "status": "BLOCKED", "credential_source": credential_source,
        "credential_values_published": False, "raw_outputs_published": False,
        "legacy_bearer_compatibility": "NOT_TESTED" if not legacy or official else "UNVERIFIED",
        "authenticated_workload_read_succeeded": False,
        "actual_container_exit_code": None, "terminated_container_records": [],
        "first_actual_error": None, "logs_command_executed": False,
        "container_log_channel": "MERGED_OR_CHANNEL_UNSPECIFIED",
        "archived_previous_container_logs_supported_by_cli": False,
        "actual_cause_confirmed": False, "paid_operations": 0, "commands": []}
    if not official and not legacy:
        result["blocking_reason"] = "APPROVED_SECRET_CREDENTIAL_NOT_PROVIDED"
        return result
    child_environment = dict(source_environment)
    child_environment["GCUBE_ACCESS_TOKEN"] = official or legacy
    child_environment.pop("GCUBE_API_TOKEN", None)
    version = runner(binary, ALLOWED_COMMANDS[0], child_environment, 10)
    result["commands"].append(safe_command_result(ALLOWED_COMMANDS[0], version))
    # No request with an unexpected CLI implementation/version.
    if version.returncode != 0 or version.stdout.strip() != b"gcube 0.4.2":
        result["blocking_reason"] = "OFFICIAL_CLI_VERSION_NOT_VERIFIED"
        return result
    result["cli_version"] = "0.4.2"
    describe = runner(binary, ALLOWED_COMMANDS[1], child_environment, 45)
    result["commands"].append(safe_command_result(ALLOWED_COMMANDS[1], describe))
    workload = matching_workload(json_documents(describe.stdout))
    if describe.returncode != 0 or describe.timed_out or workload is None:
        result["blocking_reason"] = cli_failure(describe) or "WORKLOAD_RESPONSE_NOT_VERIFIED"
        return result
    result["authenticated_workload_read_succeeded"] = True
    if legacy and not official:
        result["legacy_bearer_compatibility"] = "CONFIRMED_FOR_THIS_READ_ONLY_REQUEST"
    result["deployment"] = safe_workload(workload)
    pod_capture = runner(binary, ALLOWED_COMMANDS[2], child_environment, 45)
    result["commands"].append(safe_command_result(ALLOWED_COMMANDS[2], pod_capture))
    documents = [workload]
    if pod_capture.returncode == 0 and not pod_capture.timed_out:
        documents.extend(json_documents(pod_capture.stdout))
    for document in documents:
        result["terminated_container_records"].extend(terminated_states(document))
    exit_values = {record["exit_code"] for record in result["terminated_container_records"]}
    if len(exit_values) == 1:
        result["actual_container_exit_code"] = next(iter(exit_values))
    logs = runner(binary, ALLOWED_COMMANDS[3], child_environment, 45)
    result["logs_command_executed"] = True
    result["commands"].append(safe_command_result(ALLOWED_COMMANDS[3], logs))
    result["first_actual_error"] = first_error(json_documents(logs.stdout))
    result["status"] = "READ_ONLY_EVIDENCE_COLLECTED"
    result["actual_cause_confirmed"] = False
    result["remaining_limits"] = ["FIRST_RECEIVED_ERROR_IS_NOT_PROOF_OF_FIRST_HISTORICAL_ERROR",
        "CLI_HAS_NO_PREVIOUS_CONTAINER_OR_ARCHIVED_LOG_SWITCH",
        "NO_GPU_EXECUTION_OR_CRASH_FIX_CONFIRMED_BY_THIS_COLLECTOR"]
    if cli_failure(logs):
        result["logs_limitation"] = cli_failure(logs)
    if result["actual_container_exit_code"] is None:
        result["exit_code_limitation"] = "NO_UNAMBIGUOUS_EXPLICIT_TERMINATED_EXIT_CODE_RETURNED"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path,
        help="Directory for the single public sanitized CLI_RESULT.json")
    parser.add_argument("--cli", default="gcube")
    arguments = parser.parse_args()
    result = collect(binary=arguments.cli)
    # This file is the only publishable artifact. No CLI output is printed.
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    arguments.output.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(arguments.output / "CLI_RESULT.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(raw)
    print(json.dumps({"status": result["status"], "credential_source": result["credential_source"],
        "authenticated_workload_read_succeeded": result["authenticated_workload_read_succeeded"]}))


if __name__ == "__main__":
    main()
