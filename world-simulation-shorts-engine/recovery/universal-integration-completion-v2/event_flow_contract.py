"""Bounded CPU bridge to the preserved JavaScript Event/Flow/Area compilers.

Validation is structural/canonical only. Source authority is checked later by
compileCompletionEventFlow against a server-owned immutable source catalog.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
SCHEMA = "WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1"
_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,127}\Z")


class EventFlowContractError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _compiler(value, mode):
    try:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        encoded = raw.encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise EventFlowContractError("COMPLETION_EVENT_FLOW_INVALID_JSON") from None
    if len(encoded) > 4 * 1024 * 1024:
        raise EventFlowContractError("COMPLETION_EVENT_FLOW_INPUT_TOO_LARGE")
    script = HERE / "event_flow_binding.mjs"
    if any(component.is_symlink() for component in (script, *script.parents)) or not script.is_file():
        raise EventFlowContractError("COMPLETION_EVENT_FLOW_LOCAL_COMPILER_REQUIRED")
    try:
        result = subprocess.run(["node", "--no-warnings", str(script), mode], input=encoded,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False, cwd=HERE)
    except (OSError, subprocess.TimeoutExpired):
        raise EventFlowContractError("COMPLETION_EVENT_FLOW_CPU_COMPILER_UNAVAILABLE") from None
    if len(result.stdout) > 8 * 1024 * 1024:
        raise EventFlowContractError("COMPLETION_EVENT_FLOW_OUTPUT_TOO_LARGE")
    try:
        response = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise EventFlowContractError("COMPLETION_EVENT_FLOW_CPU_COMPILER_FAILED") from None
    if result.returncode != 0 or response.get("ok") is not True:
        code = response.get("code")
        raise EventFlowContractError(code if isinstance(code, str) and _CODE.fullmatch(code)
                                     else "COMPLETION_EVENT_FLOW_INVALID")
    normalized = response.get("value")
    if not isinstance(normalized, dict):
        raise EventFlowContractError("COMPLETION_EVENT_FLOW_CPU_COMPILER_FAILED")
    return normalized


def normalize_event_flow(value):
    """Return a canonical request, never a source verification or render grant."""
    normalized = _compiler(value, "--normalize")
    if normalized.get("schema") != SCHEMA:
        raise EventFlowContractError("COMPLETION_EVENT_FLOW_CPU_COMPILER_FAILED")
    return normalized


def validate_event_flow(value, *, fps, total_frames, trusted_sources):
    """Admit supplied data against a server-loaded catalog; no GPU side effects.

    The caller must load and SHA-verify ``trusted_sources`` from the immutable
    server source manifest. It must never take that catalog from a prompt.
    """
    receipt = _compiler({"request": value, "fps": fps, "totalFrames": total_frames,
                         "trustedSources": trusted_sources}, "--admit")
    if (receipt.get("schema") != "WORLD_ENGINE_COMPLETION_EVENT_FLOW_CPU_ADMISSION_V1"
            or receipt.get("status") != "CPU_SOURCE_BOUND" or receipt.get("gpuOutputVerified") is not False):
        raise EventFlowContractError("COMPLETION_EVENT_FLOW_CPU_COMPILER_FAILED")
    return receipt
