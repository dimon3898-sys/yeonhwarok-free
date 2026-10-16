"""Authenticated server's private, explicit production coordinator.

No render is started by construction, validation, reconnect or process restart.
The HTTP layer authenticates the owner; this layer additionally requires an
explicit consent and a private, real operator budget for every new GPU job.
Original managers remain responsible for hardware admission, leases and retries.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import math
from pathlib import Path
import re

import studio_contracts
from studio_common import canonical_sha256, load_original

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_JOB = re.compile(r"studio-[0-9a-f]{32}\Z")
_KEY = re.compile(r"[A-Za-z0-9_-]{8,128}\Z")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,95}\Z")
_ACTIVE = {"QUEUED", "RUNNING"}
_FINAL = {"COMPLETED", "FAILED", "INTERRUPTED"}
_POLICY_KEYS = {"validUntil", "maxWallSeconds", "maxRetries", "maxCostAmount",
                "currency", "gpuHourlyRate"}


class StudioError(RuntimeError):
    def __init__(self, code, message=None, status=409, fields=None):
        self.code = code
        self.message = message or code
        self.status = status
        self.fields = list(fields or [])
        super().__init__(self.message)


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _safe_error(error):
    code = getattr(error, "code", None) or str(error)
    return code if isinstance(code, str) and _CODE.fullmatch(code) else "STUDIO_RUNTIME_FAILED"


def _name(value, pattern, code):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise StudioError(code, "요청 식별자를 확인하세요.", 400)
    return value


def _budget_decimal(value):
    if (not isinstance(value, (str, int)) or isinstance(value, bool)
            or not re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,8})?", str(value))):
        raise StudioError("STUDIO_OPERATOR_POLICY_INVALID", "실제 요금과 비용 상한을 확인하세요.")
    try:
        number = Decimal(value)
        if not number.is_finite() or number <= 0:
            raise InvalidOperation
        return number
    except (InvalidOperation, ValueError):
        raise StudioError("STUDIO_OPERATOR_POLICY_INVALID", "실제 요금과 비용 상한을 확인하세요.") from None


class StudioController:
    def __init__(self, *, control_root, export_root, image_digest, backend=None):
        if not isinstance(image_digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest):
            raise StudioError("STUDIO_IMAGE_DIGEST_REQUIRED", "고정된 실행 이미지 digest가 필요합니다.")
        self.control_root, self.export_root = Path(control_root), Path(export_root)
        if (not self.control_root.is_absolute() or not self.export_root.is_absolute()
                or ".." in self.control_root.parts or ".." in self.export_root.parts):
            raise StudioError("STUDIO_ABSOLUTE_STORAGE_REQUIRED")
        self.image_digest = image_digest
        self._cache = load_original("cache")
        if backend is None:
            import studio_runtime
            backend = studio_runtime
        self.backend = backend
        # This validates an owned local POSIX directory. It never repairs a
        # shared Dropbox mount's mode or treats shared storage as private state.
        with self._cache.PrivateTree(self.control_root, create=True) as root:
            with root.lock(wait_seconds=8):
                for name in ("submissions", "requests", "runs", "jobs", "approvals", "recoveries"):
                    with root.child(name, create=True):
                        pass

    def _backend(self, name, *args, **kwargs):
        method = getattr(self.backend, name, None)
        if not callable(method):
            raise StudioError("STUDIO_BACKEND_UNAVAILABLE", "기존 제작 실행 경로를 사용할 수 없습니다.", 503)
        try:
            return method(*args, **kwargs)
        except StudioError:
            raise
        except Exception as error:
            raise StudioError(_safe_error(error), "제작 검증 또는 실행에 실패했습니다. 안전한 오류 코드를 확인하세요.") from None

    def _policy(self, root):
        value = root.json("operator_policy.json", optional=True)
        if value is None:
            raise StudioError("STUDIO_OPERATOR_POLICY_REQUIRED",
                "운영자가 실제 GPU 요금·최대 비용·실행시간·만료시각을 설정해야 제작을 시작할 수 있습니다.")
        if (not isinstance(value, dict) or set(value) - {"schema"} != _POLICY_KEYS
                or value.get("schema", "WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1") != "WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1"):
            raise StudioError("STUDIO_OPERATOR_POLICY_INVALID", "운영 비용 정책 필드를 확인하세요.")
        if (type(value["maxWallSeconds"]) is not int or not 1 <= value["maxWallSeconds"] <= 86400
                or type(value["maxRetries"]) is not int or not 0 <= value["maxRetries"] <= 2
                or not isinstance(value["currency"], str) or not re.fullmatch(r"[A-Z]{3}", value["currency"])):
            raise StudioError("STUDIO_OPERATOR_POLICY_INVALID", "실행시간·재시도·통화 설정을 확인하세요.")
        try:
            expiry = datetime.fromisoformat(value["validUntil"])
            if expiry.tzinfo is None or expiry.utcoffset() is None:
                raise ValueError()
            if expiry <= datetime.now(timezone.utc):
                raise StudioError("STUDIO_OPERATOR_POLICY_EXPIRED", "운영 비용 정책이 만료됐습니다.")
        except (TypeError, ValueError):
            raise StudioError("STUDIO_OPERATOR_POLICY_INVALID", "정책 만료시각에 시간대가 필요합니다.") from None
        cost, rate = _budget_decimal(value["maxCostAmount"]), _budget_decimal(value["gpuHourlyRate"])
        if Decimal(value["maxWallSeconds"]) * rate / Decimal(3600) > cost:
            raise StudioError("STUDIO_COST_LIMIT_EXCEEDED", "실행시간 상한이 승인된 비용 상한을 초과합니다.")
        return {key: value[key] for key in _POLICY_KEYS}

    def _normal(self, value):
        return studio_contracts.normalize_submission(value, image_digest=self.image_digest, backend=self.backend)

    def _read_submission(self, root, submission_id):
        _name(submission_id, _HEX, "STUDIO_SUBMISSION_ID_INVALID")
        with root.child("submissions") as directory:
            record = directory.json(submission_id + ".json", optional=True)
        if record is None:
            raise StudioError("STUDIO_SUBMISSION_NOT_FOUND", "저장된 제작 입력이 없습니다.", 404)
        signed = {"submission": record.get("submission"), "lineage": record.get("lineage")}
        if record.get("submissionId") != submission_id or canonical_sha256(signed) != submission_id:
            raise StudioError("STUDIO_SUBMISSION_CORRUPT", "저장된 제작 입력의 무결성 확인에 실패했습니다.")
        return record

    def _save_submission(self, root, submission, lineage=None):
        submission_id = canonical_sha256({"submission": submission, "lineage": lineage})
        record = {"schema": "WORLD_ENGINE_STUDIO_PRIVATE_SUBMISSION_V1", "submissionId": submission_id,
                  "submission": deepcopy(submission), "lineage": deepcopy(lineage), "createdAt": _stamp()}
        with root.child("submissions") as directory:
            if directory.json(submission_id + ".json", optional=True) is None:
                directory.write_json(submission_id + ".json", record)
        return submission_id

    def _job_record(self, root, job_id):
        _name(job_id, _JOB, "STUDIO_JOB_ID_INVALID")
        with root.child("jobs") as directory:
            record = directory.json(job_id + ".json", optional=True)
        if record is None or record.get("jobId") != job_id:
            raise StudioError("STUDIO_JOB_NOT_FOUND", "저장된 작업이 없습니다.", 404)
        return record

    def _raw_status(self, job_id):
        result = self._backend("studio_status", job_id, control_root=self.control_root, export_root=self.export_root)
        if not isinstance(result, dict) or result.get("jobId") != job_id or result.get("state") not in _ACTIVE | _FINAL:
            raise StudioError("STUDIO_JOB_STATE_INVALID")
        return result

    def _safe_status(self, state):
        result = {"jobId": state["jobId"], "state": state["state"]}
        phase = state.get("phase")
        result["phase"] = phase if isinstance(phase, str) and _CODE.fullmatch(phase) else "UNKNOWN"
        for key in ("totalScenes", "completedScenes", "processedFrames", "totalFrames", "elapsedSeconds"):
            value = state.get(key)
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                result[key] = value
        for key in ("gpuRenderingVerified", "requiresGpu"):
            if type(state.get(key)) is bool:
                result[key] = state[key]
        for key in ("createdAt", "updatedAt"):
            value = state.get(key)
            if isinstance(value, str) and re.fullmatch(r"[0-9T:+.Z-]{10,48}", value):
                result[key] = value
        error = state.get("errorCode")
        result["errorCode"] = error if isinstance(error, str) and _CODE.fullmatch(error) else None
        result["resultAvailable"] = state.get("state") == "COMPLETED"
        return result

    def _audio_gate(self, submission):
        if submission["sfx"]["enabled"] is not True:
            return True, {"name": "SFX_LICENSE_AND_FILES", "status": "SKIP", "code": "SFX_DISABLED"}
        try:
            from studio_audio import verify_assets
            facts = verify_assets()
            if facts.get("status") != "PASS":
                raise StudioError("STUDIO_SFX_ASSET_VALIDATION_FAILED")
            return True, {"name": "SFX_LICENSE_AND_FILES", "status": "PASS",
                          "facts": {"license": facts["license"], "assetCount": facts["assetCount"]}}
        except Exception as error:
            return False, {"name": "SFX_LICENSE_AND_FILES", "status": "BLOCKED", "code": _safe_error(error)}

    def _public_checks(self, checks):
        permitted = {"frames", "scenes", "localPosixOnly", "mountedReadWriteVerified", "externalDownloadVerified",
                     "availableBytes", "minimumEstimatedBytes", "estimateOnly", "model", "physicalMemoryMiB",
                     "verificationScope", "assetCount", "license"}
        result = []
        for row in checks:
            if (not isinstance(row, dict) or not isinstance(row.get("name"), str)
                    or not _CODE.fullmatch(row["name"]) or row.get("status") not in {"PASS", "FAIL", "SKIP", "BLOCKED", "WARNING"}):
                raise StudioError("STUDIO_PREFLIGHT_RESULT_INVALID")
            safe = {"name": row["name"], "status": row["status"]}
            if isinstance(row.get("code"), str) and _CODE.fullmatch(row["code"]):
                safe["code"] = row["code"]
            if isinstance(row.get("facts"), dict):
                safe["facts"] = {key: value for key, value in row["facts"].items() if key in permitted
                    and (type(value) in (int, bool) or type(value) is float and math.isfinite(value)
                         or isinstance(value, str) and len(value) <= 96 and not any(c in value for c in "\\/\r\n"))}
            result.append(safe)
        return result

    def _preflight_record(self, root, record):
        submission, lineage = record["submission"], record.get("lineage")
        audio_ready, audio_check = self._audio_gate(submission)
        if lineage is not None:
            parent = self._job_record(root, lineage["parentJobId"])
            status = self._raw_status(parent["jobId"])
            ready = status["state"] == "COMPLETED"
            return {"valid": True, "ready": ready and audio_ready, "requiresGpu": False,
                    "checks": [{"name": "VERIFIED_COMPLETED_PARENT", "status": "PASS" if ready else "BLOCKED",
                                "code": None if ready else "STUDIO_REVISION_PARENT_NOT_COMPLETED"}, audio_check],
                    "scope": "SFX_ONLY_RECOMPOSE", "gpuRenderingVerified": False}
        runtime = self._backend("preflight", submission["videoPlan"], submission["profile"],
                                control_root=self.control_root, export_root=self.export_root)
        if not isinstance(runtime, dict) or not isinstance(runtime.get("checks"), list):
            raise StudioError("STUDIO_PREFLIGHT_RESULT_INVALID")
        checks, budget = self._public_checks(runtime["checks"]), None
        checks.append(audio_check)
        try:
            budget = self._policy(root)
            checks.append({"name": "OWNER_BUDGET_POLICY", "status": "PASS"})
        except StudioError as error:
            checks.append({"name": "OWNER_BUDGET_POLICY", "status": "BLOCKED", "code": error.code})
        except Exception as error:
            checks.append({"name": "OWNER_BUDGET_POLICY", "status": "BLOCKED", "code": _safe_error(error)})
        return {"valid": True, "ready": runtime.get("renderAllowed") is True and budget is not None and audio_ready,
                "requiresGpu": True, "checks": checks, "budget": budget,
                "gpuRenderingVerified": runtime.get("gpuRenderingVerified") is True,
                "providerBillingStopControlled": False}

    def preflight(self, value):
        try:
            submission = self._normal(value)
        except studio_contracts.StudioContractError as error:
            return {"valid": False, "ready": False, "requiresGpu": True,
                    "checks": [{"name": "PRODUCTION_INPUT", "status": "FAIL", "code": error.code}],
                    "error": {"code": error.code, "message": error.message, "fields": error.fields}}
        with self._cache.PrivateTree(self.control_root) as root:
            return self._preflight_record(root, {"submission": submission, "lineage": None})

    def submit(self, value):
        submission = self._normal(value)
        with self._cache.PrivateTree(self.control_root) as root:
            with root.lock(wait_seconds=8):
                submission_id = self._save_submission(root, submission)
                record = self._read_submission(root, submission_id)
            preflight = self._preflight_record(root, record)
        return {"submissionId": submission_id, "preflight": preflight, "title": submission["title"]}

    def _check_active(self, root):
        active = root.json("active.json", optional=True)
        if active is None:
            return
        if not isinstance(active, dict) or not _JOB.fullmatch(str(active.get("jobId", ""))):
            raise StudioError("STUDIO_UNRESOLVED_START_CLAIM", "이전 시작 기록의 확인이 필요합니다. 자동 재실행하지 않습니다.")
        if self._raw_status(active["jobId"])["state"] in _ACTIVE:
            raise StudioError("STUDIO_JOB_ALREADY_ACTIVE", "현재 작업이 끝난 뒤 새 제작을 시작하세요.")

    def start(self, submission_id, idempotency_key, *, consent=False):
        if consent is not True:
            raise StudioError("STUDIO_OWNER_CONSENT_REQUIRED", "제작 시작과 설정된 실행 한도에 명시적으로 동의하세요.", 403)
        _name(idempotency_key, _KEY, "STUDIO_IDEMPOTENCY_KEY_INVALID")
        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        with self._cache.PrivateTree(self.control_root) as root:
            with root.lock(wait_seconds=8):
                record = self._read_submission(root, submission_id)
                with root.child("requests") as requests:
                    previous = requests.json(key_hash + ".json", optional=True)
                    if previous is not None:
                        if (previous.get("submissionId") != submission_id
                                or previous.get("operation", "PRODUCTION_START") != "PRODUCTION_START"):
                            raise StudioError("STUDIO_IDEMPOTENCY_CONFLICT", "같은 요청 키를 다른 제작 입력에 사용할 수 없습니다.")
                        if previous.get("jobId"):
                            return self._safe_status(self._raw_status(previous["jobId"]))
                        raise StudioError("STUDIO_UNRESOLVED_START_CLAIM", "이전 시작 시도의 상태를 확인해야 합니다. 자동으로 다시 시작하지 않습니다.")
                # A new browser key never silently reruns the same submission.
                with root.child("runs") as runs:
                    previous_run = runs.json(submission_id + ".json", optional=True)
                if previous_run is not None:
                    if previous_run.get("jobId"):
                        with root.child("requests") as requests:
                            requests.write_json(key_hash + ".json", {**previous_run, "idempotentAlias": True})
                        return self._safe_status(self._raw_status(previous_run["jobId"]))
                    raise StudioError("STUDIO_UNRESOLVED_START_CLAIM")
                self._check_active(root)
                gate = self._preflight_record(root, record)
                if not gate["ready"]:
                    raise StudioError("STUDIO_PREFLIGHT_BLOCKED", "사전검사를 통과해야 제작을 시작할 수 있습니다.")
                request_id = "owner-" + key_hash[:32]
                claim = {"schema": "WORLD_ENGINE_STUDIO_START_CLAIM_V1", "operation": "PRODUCTION_START", "submissionId": submission_id,
                         "requestId": request_id, "createdAt": _stamp(), "jobId": None, "state": "CLAIMED"}
                with root.child("requests") as requests:
                    requests.write_json(key_hash + ".json", claim)
                with root.child("runs") as runs:
                    runs.write_json(submission_id + ".json", claim)
                root.write_json("active.json", {"requestId": request_id, "jobId": None}, replace=True)
                submission, lineage = record["submission"], record.get("lineage")
                try:
                    if lineage is None:
                        policy = self._policy(root)
                        approval = {"schema": "WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1", "approved": True,
                                    "planSHA256": canonical_sha256(submission["videoPlan"]),
                                    "imageDigest": self.image_digest, **policy}
                        with root.child("approvals") as approvals:
                            with approvals.child(request_id, create=True) as directory:
                                directory.write_json("authorization.json", approval)
                        approval_path = self.control_root / "approvals" / request_id / "authorization.json"
                        state = self._backend("start_studio_job", submission["videoPlan"], submission["profile"],
                            approval_path, submission["sfx"], request_id,
                            control_root=self.control_root, export_root=self.export_root)
                    else:
                        state = self._backend("start_studio_revision", lineage["parentJobId"],
                            submission["sfx"], request_id, control_root=self.control_root, export_root=self.export_root)
                    if (not isinstance(state, dict) or not isinstance(state.get("jobId"), str)
                            or not _JOB.fullmatch(state["jobId"]) or state.get("state") not in _ACTIVE | _FINAL):
                        raise StudioError("STUDIO_START_RESULT_INVALID")
                except Exception as error:
                    failed = {**claim, "state": "UNRESOLVED", "errorCode": _safe_error(error)}
                    with root.child("requests") as requests:
                        requests.write_json(key_hash + ".json", failed, replace=True)
                    # Preserve the claim even when a launch receipt is missing;
                    # the detached child might already exist. Never retry blind.
                    raise StudioError(_safe_error(error), "시작 결과를 확인하지 못했습니다. 기존 시작 기록을 보존하며 중복 실행을 차단합니다.") from None
                completed_claim = {**claim, "jobId": state["jobId"], "state": "LAUNCHED"}
                with root.child("requests") as requests:
                    requests.write_json(key_hash + ".json", completed_claim, replace=True)
                with root.child("runs") as runs:
                    runs.write_json(submission_id + ".json", completed_claim, replace=True)
                with root.child("jobs") as jobs:
                    jobs.write_json(state["jobId"] + ".json", {"jobId": state["jobId"],
                        "submissionId": submission_id, "requestId": request_id,
                        "authorizationRequestId": request_id if lineage is None else None, "createdAt": _stamp()})
                root.write_json("active.json", {"requestId": request_id, "jobId": state["jobId"]}, replace=True)
                return self._safe_status(state)

    def status(self, job_id):
        with self._cache.PrivateTree(self.control_root) as root:
            self._job_record(root, job_id)
        return self._safe_status(self._raw_status(job_id))

    def resume(self, job_id, idempotency_key, *, consent=False):
        """An explicit new supervisor; native retry/deadline ledgers stay intact."""
        if consent is not True:
            raise StudioError("STUDIO_OWNER_CONSENT_REQUIRED", "기존 실행 한도 안의 복구 시작에 명시적으로 동의하세요.", 403)
        _name(idempotency_key, _KEY, "STUDIO_IDEMPOTENCY_KEY_INVALID")
        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        with self._cache.PrivateTree(self.control_root) as root:
            with root.lock(wait_seconds=8):
                parent = self._job_record(root, job_id)
                with root.child("requests") as requests:
                    previous = requests.json(key_hash + ".json", optional=True)
                if previous is not None:
                    if previous.get("operation") != "RECOVERY" or previous.get("parentJobId") != job_id:
                        raise StudioError("STUDIO_IDEMPOTENCY_CONFLICT")
                    if previous.get("jobId"):
                        return self._safe_status(self._raw_status(previous["jobId"]))
                    raise StudioError("STUDIO_UNRESOLVED_START_CLAIM")
                with root.child("recoveries") as recoveries:
                    previous_recovery = recoveries.json(job_id + ".json", optional=True)
                if previous_recovery is not None:
                    if previous_recovery.get("jobId"):
                        with root.child("requests") as requests:
                            requests.write_json(key_hash + ".json", {**previous_recovery, "idempotentAlias": True})
                        return self._safe_status(self._raw_status(previous_recovery["jobId"]))
                    raise StudioError("STUDIO_UNRESOLVED_START_CLAIM")
                current = self._raw_status(job_id)
                if current["state"] not in {"FAILED", "INTERRUPTED"}:
                    raise StudioError("STUDIO_RECOVERY_REQUIRES_FAILED_OR_INTERRUPTED_JOB",
                                      "실패·중단된 작업만 명시적으로 복구할 수 있습니다.")
                self._check_active(root)
                authorization_id = parent.get("authorizationRequestId")
                approval_path = None
                if authorization_id is not None:
                    _name(authorization_id, _KEY, "STUDIO_APPROVAL_RECORD_INVALID")
                    # Reuse exactly the first consent's approval. A policy
                    # update cannot extend this job's old retry/time/cost cap.
                    with root.child("approvals") as approvals:
                        with approvals.child(authorization_id) as directory:
                            directory.json("authorization.json")
                    approval_path = self.control_root / "approvals" / authorization_id / "authorization.json"
                request_id = "recovery-" + key_hash[:32]
                claim = {"schema": "WORLD_ENGINE_STUDIO_START_CLAIM_V1", "operation": "RECOVERY",
                         "parentJobId": job_id, "submissionId": parent["submissionId"],
                         "requestId": request_id, "createdAt": _stamp(), "jobId": None, "state": "CLAIMED"}
                with root.child("requests") as requests:
                    requests.write_json(key_hash + ".json", claim)
                with root.child("recoveries") as recoveries:
                    recoveries.write_json(job_id + ".json", claim)
                root.write_json("active.json", {"requestId": request_id, "jobId": None}, replace=True)
                try:
                    state = self._backend("start_studio_recovery", job_id, approval_path, request_id,
                                          control_root=self.control_root, export_root=self.export_root)
                    if (not isinstance(state, dict) or not _JOB.fullmatch(str(state.get("jobId", "")))
                            or state.get("state") not in _ACTIVE | _FINAL):
                        raise StudioError("STUDIO_START_RESULT_INVALID")
                except Exception as error:
                    with root.child("requests") as requests:
                        requests.write_json(key_hash + ".json", {**claim, "state": "UNRESOLVED", "errorCode": _safe_error(error)}, replace=True)
                    raise StudioError(_safe_error(error), "복구 시작 결과를 확인해야 합니다. 중복 실행을 자동 차단합니다.") from None
                launched = {**claim, "jobId": state["jobId"], "state": "LAUNCHED"}
                with root.child("requests") as requests:
                    requests.write_json(key_hash + ".json", launched, replace=True)
                with root.child("recoveries") as recoveries:
                    recoveries.write_json(job_id + ".json", launched, replace=True)
                with root.child("runs") as runs:
                    runs.write_json(parent["submissionId"] + ".json", launched, replace=True)
                with root.child("jobs") as jobs:
                    jobs.write_json(state["jobId"] + ".json", {"jobId": state["jobId"], "submissionId": parent["submissionId"],
                        "requestId": request_id, "authorizationRequestId": authorization_id,
                        "recoveryOfJobId": job_id, "createdAt": _stamp()})
                root.write_json("active.json", {"requestId": request_id, "jobId": state["jobId"]}, replace=True)
                return self._safe_status(state)

    def revise(self, job_id, value):
        if (not isinstance(value, dict) or set(value) - {"startSeconds", "endSeconds", "prompt", "sfx"}
                or not {"startSeconds", "endSeconds"} <= set(value)):
            raise StudioError("STUDIO_REVISION_REQUEST_INVALID", "수정 시작·종료 시간과 프롬프트를 확인하세요.", 400)
        with self._cache.PrivateTree(self.control_root) as root:
            with root.lock(wait_seconds=8):
                job = self._job_record(root, job_id)
                if self._raw_status(job_id)["state"] != "COMPLETED":
                    raise StudioError("STUDIO_REVISION_PARENT_NOT_COMPLETED", "완성된 영상만 수정할 수 있습니다.")
                parent = self._read_submission(root, job["submissionId"])
                revision = studio_contracts.plan_revision(parent["submission"], value["startSeconds"],
                    value["endSeconds"], value.get("prompt", ""), value.get("sfx"))
                impact = revision["impact"]
                if impact.get("requiresGpu") is not False or revision["submission"]["videoPlan"] != parent["submission"]["videoPlan"]:
                    raise StudioError("STUDIO_VISUAL_REVISION_UNSUPPORTED", "보호된 영상 계획은 이 수정 경로에서 변경할 수 없습니다.", 422)
                lineage = {"parentJobId": job_id, "parentSubmissionId": job["submissionId"], "impact": impact}
                submission_id = self._save_submission(root, revision["submission"], lineage)
                record = self._read_submission(root, submission_id)
                return {"submissionId": submission_id, "impact": impact,
                        "affectedSceneIds": impact.get("affectedSceneIds", []),
                        "preflight": self._preflight_record(root, record)}

    def result(self, job_id):
        with self._cache.PrivateTree(self.control_root) as root:
            self._job_record(root, job_id)
        state = self._raw_status(job_id)
        if state["state"] != "COMPLETED" or not isinstance(state.get("result"), dict):
            raise StudioError("STUDIO_RESULT_NOT_AVAILABLE", "아직 검증된 완성 영상이 없습니다.")
        # Reuse the audio-aware adapter's pinned openat traversal, exact public
        # allowlist, file bounds and streaming SHA checks rather than duplicating
        # or weakening storage validation here.
        from studio_delivery import verify_export
        try:
            receipt = verify_export(state["result"], self.export_root)
        except Exception as error:
            raise StudioError(_safe_error(error), "결과물 무결성 검사에 실패했습니다.") from None
        downloads = [{**item, "path": str(self.export_root / receipt["exportDirectory"] / item["name"])}
                     for item in receipt["files"]]
        return {"jobId": job_id, "state": "COMPLETED", "downloads": downloads,
                "dropbox": {"mountReadbackVerified": receipt.get("mountedViewReadbackVerified") is True,
                            "relativeDirectory": receipt["exportDirectory"],
                            "externalDownloadVerified": False},
                "remotePersistenceVerified": False, "userVideoReviewRequired": True}
