"""Fail-closed quality prerequisite gate; this module never starts a GPU job.

Only a server-side adapter may construct ``context`` or select a receipt path.
Neither is a Scene/prompt field. A true result is ONE prerequisite: the frozen
Studio authorization, GPU admission, lease and operator cost checks still run.
CPU planning evidence is explicitly not rendered-output evidence.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,95}\Z")
_FEATURE = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_POLICY_KEYS = {"validUntil", "maxWallSeconds", "maxRetries", "maxCostAmount", "currency", "gpuHourlyRate"}
_CONTEXT_KEYS = {"sourceCommit", "sourceManifestSHA256", "sourceClosureManifestSHA256",
    "sceneSHA256", "imageDigest", "durationSeconds", "fps", "sourceClosureVerified",
    "imagePackageIncluded", "requiredModules", "dataBlockers", "referenceSHA256", "candidateSHA256"}
_RECEIPT_BINDINGS = ("sourceCommit", "sourceManifestSHA256", "sourceClosureManifestSHA256",
    "sceneSHA256", "imageDigest", "referenceSHA256", "candidateSHA256")
_RECEIPT_KEYS = {"schema", "userReview", "reviewedAt", "validUntil", "candidate",
    "targetDurationSeconds", "targetFps",
    "referenceComparison", *_RECEIPT_BINDINGS}
_FULL_DURATIONS = {80, 120, 180, 300, 600}


class QualityGateError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _sha(value):
    return isinstance(value, str) and bool(_HEX.fullmatch(value))


def _time(value):
    if not isinstance(value, str):
        raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_TIME_INVALID")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except ValueError:
        raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_TIME_INVALID") from None


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_INVALID") from None


def _private_receipt(path, root, uid):
    """Read operator-owned POSIX state without following any symlink component.

    Never create directories, repair modes, rewrite a receipt, or trust a shared
    Dropbox mount as the private operator authority. O_NOFOLLOW + directory FDs
    prevent swapping an already checked path to a symlink before the read.
    """
    if path is None or root is None:
        raise QualityGateError("INTEGRATION_5S_USER_QUALITY_APPROVAL_REQUIRED")
    try:
        path, root = Path(path), Path(root)
        if (not path.is_absolute() or not root.is_absolute() or ".." in path.parts
                or ".." in root.parts or not path.is_relative_to(root) or path == root):
            raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_PATH_UNSAFE")
        relative = path.relative_to(root)
        descriptors = []
        try:
            descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
            descriptors.append(descriptor)
            for component in root.parts[1:]:
                descriptor = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                     dir_fd=descriptor)
                descriptors.append(descriptor)
            info = os.fstat(descriptor)
            if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
                raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_ROOT_NOT_PRIVATE")
            for component in relative.parts[:-1]:
                descriptor = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                     dir_fd=descriptor)
                descriptors.append(descriptor)
                info = os.fstat(descriptor)
                if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
                    raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_ROOT_NOT_PRIVATE")
            descriptor = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 dir_fd=descriptor)
            descriptors.append(descriptor)
            before = os.fstat(descriptor)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != uid
                    or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                    or not 0 < before.st_size <= 65536):
                raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_FILE_NOT_PRIVATE")
            raw = os.read(descriptor, 65537)
            after = os.fstat(descriptor)
            if (len(raw) != before.st_size or len(raw) > 65536
                    or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_CHANGED")
            return _json(raw)
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
    except QualityGateError:
        raise
    except (OSError, TypeError, ValueError):
        raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_PATH_UNSAFE") from None


def _validate_receipt(receipt, context, now):
    if (not isinstance(receipt, dict) or set(receipt) != _RECEIPT_KEYS
            or receipt.get("schema") != "WORLD_ENGINE_5S_USER_QUALITY_APPROVAL_V1"
            or receipt.get("userReview") != "PASS"):
        raise QualityGateError("INTEGRATION_5S_USER_QUALITY_APPROVAL_REQUIRED")
    for key in _RECEIPT_BINDINGS:
        if receipt.get(key) != context.get(key):
            raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_BINDING_MISMATCH")
    if (type(receipt["targetDurationSeconds"]) is not int
            or receipt["targetDurationSeconds"] != context.get("durationSeconds")
            or type(receipt["targetFps"]) is not int or receipt["targetFps"] != context.get("fps")):
        raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_BINDING_MISMATCH")
    reviewed, expiry = _time(receipt["reviewedAt"]), _time(receipt["validUntil"])
    if reviewed > now or expiry <= now or expiry <= reviewed:
        raise QualityGateError("INTEGRATION_QUALITY_RECEIPT_EXPIRED_OR_FUTURE")
    candidate = receipt.get("candidate")
    if (not isinstance(candidate, dict)
            or set(candidate) != {"durationSeconds", "fps", "width", "height", "frames",
                "gpuVendor", "gpuRenderingVerified", "mp4FullyDecoded", "gpuEvidenceSHA256"}
            or any(type(candidate.get(key)) is not int or candidate[key] != value
                   for key, value in {"durationSeconds": 5, "fps": 30, "width": 1080,
                       "height": 1920, "frames": 150}.items())
            or candidate.get("gpuVendor") != "NVIDIA"
            or candidate.get("gpuRenderingVerified") is not True
            or candidate.get("mp4FullyDecoded") is not True
            or not _sha(candidate.get("gpuEvidenceSHA256"))):
        raise QualityGateError("INTEGRATION_5S_NVIDIA_OUTPUT_EVIDENCE_REQUIRED")
    comparison = receipt.get("referenceComparison")
    if (not isinstance(comparison, dict)
            or set(comparison) != {"status", "referenceSHA256", "candidateSHA256", "evidenceSHA256"}
            or comparison.get("status") != "COMPLETED"
            or comparison.get("referenceSHA256") != context["referenceSHA256"]
            or comparison.get("candidateSHA256") != context["candidateSHA256"]
            or not _sha(comparison.get("evidenceSHA256"))):
        raise QualityGateError("INTEGRATION_5S_REFERENCE_COMPARISON_REQUIRED")


def evaluate_render_gate(context, *, phase, operator_policy=None, policy_validator=None,
                         receipt_path=None, trusted_receipt_root=None, trusted_uid=None, now=None):
    """Evaluate server-supplied prerequisites without I/O other than receipt read.

    ``policy_validator`` must call the unchanged Studio ``_policy`` validator on
    private operator state; it must not be a client callback. ``context`` comes
    from the candidate's source/data closure, never from a prompt. This API does
    not grant billing approval, perform NVIDIA admission, or validate an image
    by downloading it. Missing proof is a blocker, never a synthesized PASS.
    """
    now = now or datetime.now(timezone.utc)
    blockers = []

    def block(code, **detail):
        blockers.append({"code": code, **detail})

    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if not isinstance(phase, str) or phase not in {"REFERENCE_5S", "FULL_VIDEO"}:
        block("INTEGRATION_RENDER_PHASE_INVALID")
    if not isinstance(context, dict) or set(context) - _CONTEXT_KEYS:
        block("INTEGRATION_TRUSTED_GATE_CONTEXT_INVALID")
        context = {}
    if (not isinstance(context.get("sourceCommit"), str)
            or not _COMMIT.fullmatch(context["sourceCommit"])
            or any(not _sha(context.get(key)) for key in ("sourceManifestSHA256",
                "sourceClosureManifestSHA256", "sceneSHA256", "referenceSHA256"))):
        block("INTEGRATION_SOURCE_SCENE_REFERENCE_BINDING_REQUIRED")
    if not isinstance(context.get("imageDigest"), str) or not _DIGEST.fullmatch(context["imageDigest"]):
        block("INTEGRATION_IMMUTABLE_IMAGE_REQUIRED")
    if context.get("sourceClosureVerified") is not True:
        block("INTEGRATION_SOURCE_CLOSURE_NOT_VERIFIED")
    if context.get("imagePackageIncluded") is not True:
        block("INTEGRATION_CANDIDATE_NOT_INCLUDED_IN_IMAGE")
    duration = context.get("durationSeconds")
    if (type(duration) is not int or type(context.get("fps")) is not int or context.get("fps") != 30
            or (phase == "REFERENCE_5S" and duration != 5)
            or (phase == "FULL_VIDEO" and duration not in _FULL_DURATIONS)):
        block("INTEGRATION_RENDER_DURATION_INVALID")
    modules = context.get("requiredModules")
    if not isinstance(modules, dict) or not modules:
        block("INTEGRATION_REQUIRED_MODULE_EVIDENCE_MISSING")
    else:
        for name, state in sorted(modules.items(), key=lambda pair: str(pair[0])):
            if not isinstance(name, str) or not _FEATURE.fullmatch(name):
                block("INTEGRATION_REQUIRED_MODULE_EVIDENCE_INVALID")
            elif not isinstance(state, str) or state not in {"READY", "NOT_REQUIRED"}:
                block("INTEGRATION_REQUIRED_MODULE_BLOCKED", featureId=name)
        if all(value == "NOT_REQUIRED" for value in modules.values()):
            block("INTEGRATION_REQUIRED_MODULE_EVIDENCE_MISSING")
    data = context.get("dataBlockers")
    if not isinstance(data, list) or any(not isinstance(code, str) or not _CODE.fullmatch(code) for code in data):
        block("INTEGRATION_DATA_EVIDENCE_INVALID")
    else:
        for code in sorted(set(data)):
            block("INTEGRATION_REQUIRED_DATA_BLOCKED", dataCode=code)
    if operator_policy is None or not callable(policy_validator):
        block("INTEGRATION_SEPARATE_PAID_GPU_APPROVAL_REQUIRED")
    else:
        try:
            validated = policy_validator(deepcopy(operator_policy))
            if (not isinstance(validated, dict) or set(validated) != _POLICY_KEYS
                    or not isinstance(operator_policy, dict)
                    or any(validated[key] != operator_policy.get(key) for key in _POLICY_KEYS)):
                raise QualityGateError("INTEGRATION_OPERATOR_POLICY_NOT_VALIDATED")
        except Exception as error:
            code = getattr(error, "code", None)
            block(code if isinstance(code, str) and _CODE.fullmatch(code)
                  else "INTEGRATION_OPERATOR_POLICY_NOT_VALIDATED")
    receipt_verified = False
    if phase == "FULL_VIDEO":
        if not _sha(context.get("candidateSHA256")):
            block("INTEGRATION_5S_CANDIDATE_SHA_REQUIRED")
        try:
            receipt = _private_receipt(receipt_path, trusted_receipt_root,
                os.geteuid() if trusted_uid is None else trusted_uid)
            _validate_receipt(receipt, context, now)
            receipt_verified = True
        except QualityGateError as error:
            block(error.code)
    return {"schema": "WORLD_ENGINE_INTEGRATION_RENDER_GATE_V1", "phase": phase,
        "allowed": not blockers, "blockers": blockers,
        "verification": {"cpuContractOnly": True, "gpuExecuted": False,
            "gpuRenderingVerified": False, "renderStarted": False,
            "userQualityReceiptVerified": receipt_verified,
            "existingStudioAuthorizationStillRequired": True,
            "existingNVIDIAAdmissionStillRequired": True,
            "noPaidGPUApprovalIssuedByThisGate": True}}
