"""Additive source-Scene review family over the preserved authenticated Studio.

Only a server-enabled, bounded source-qualified software job is admitted here.
Existing G1 and production families delegate to their existing controller. No
GPU budget, historical source approval, or hardware evidence is manufactured.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SCHEMA = "WORLD_ENGINE_UNIVERSAL_SOURCE_SCENE_V2"
PROFILE = "FREE_SOURCE_SCENE_REVIEW"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


parent = load("_source_preserved_g1_controller", HERE.parent / "studio-integration-gates-v1/studio_controller.py")
StudioError = parent.StudioError


def _base_module():
    module = parent
    while not hasattr(module, "load_original"):
        module = module.parent
    return module


def _sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def selected(value):
    return isinstance(value, dict) and (value.get("schema") == SCHEMA or value.get("profile") == PROFILE)


class StudioController(parent.StudioController):
    def __init__(self, *, source_root, expected_index_sha256, allow_software_source_review=False, **kwargs):
        self.source_root = Path(source_root)
        if (not self.source_root.is_absolute() or self.source_root.is_symlink()
                or not re.fullmatch(r"[a-f0-9]{64}", str(expected_index_sha256))):
            raise StudioError("STUDIO_SOURCE_SERVER_CATALOG_REQUIRED")
        self.expected_index_sha256 = expected_index_sha256
        self.allow_software_source_review = allow_software_source_review is True
        cache = _base_module().load_original("cache")
        with cache.PrivateTree(Path(kwargs["control_root"]), create=True):
            pass
        kwargs["control_root"] = Path(kwargs["control_root"]) / "universal-source-pipeline-v2"
        super().__init__(**kwargs)
        with self._cache.PrivateTree(self.control_root) as root:
            with root.child("source-jobs", create=True):
                pass

    def _normal(self, value):
        if not selected(value):
            return super()._normal(value)
        contract = load("_source_scene_normalizer", HERE / "source_contract.py")
        try:
            result = contract.normalize_submission(value, source_root=self.source_root,
                expected_index_sha256=self.expected_index_sha256)
            if not isinstance(result, dict) or not isinstance(result.get("sourcePipeline"), dict):
                raise StudioError("STUDIO_SOURCE_PIPELINE_REQUIRED")
            result["sourcePipeline"]["originalRequest"] = deepcopy(value)
            return result
        except StudioError:
            raise
        except Exception as error:
            code = getattr(error, "code", None) or str(error)
            if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,99}", code):
                code = "STUDIO_SOURCE_SCENE_INVALID"
            raise StudioError(code, status=400) from None

    def _preflight_record(self, root, record):
        submission = record["submission"]
        if submission.get("schema") != SCHEMA:
            return super()._preflight_record(root, record)
        pipeline = submission.get("sourcePipeline")
        if not isinstance(pipeline, dict):
            raise StudioError("STUDIO_SOURCE_PIPELINE_REQUIRED")
        total = pipeline.get("totalFrames")
        bounded = type(total) is int and 2 <= total <= 240
        scope_allowed = pipeline.get("mode") == "SYNTHETIC_TEST" or (
            pipeline.get("mode") == "PRODUCTION" and pipeline.get("scope") == "G3_SOURCE_QUALIFIED_HISTORICAL")
        checks = [{"name": "STRICT_SOURCE_SCENE", "status": "PASS"},
            {"name": "SERVER_SOFTWARE_REVIEW_OPT_IN", "status": "PASS" if self.allow_software_source_review else "BLOCKED"},
            {"name": "QUALIFIED_SOFTWARE_REVIEW_SCOPE", "status": "PASS" if scope_allowed else "BLOCKED"},
            {"name": "BOUNDED_FRAME_COUNT", "status": "PASS" if bounded else "BLOCKED"},
            {"name": "SOURCE_FRAME_PACKAGE", "status": "PASS" if pipeline.get("ready") is True else "BLOCKED"},
            {"name": "SOFTWARE_DEPENDENCIES", "status": "PASS" if shutil.which("node") and shutil.which("ffmpeg") else "BLOCKED"},
            {"name": "PRIVATE_DISK_RESERVE", "status": "PASS" if shutil.disk_usage(self.control_root).free >= 2 * 1024**3 else "BLOCKED"}]
        for blocker in pipeline.get("blockers", []):
            code = blocker.get("code") if isinstance(blocker, dict) else blocker
            if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,99}", code):
                code = "STUDIO_SOURCE_EVIDENCE_NOT_ADMITTED"
            checks.append({"name": "SOURCE_EVIDENCE", "status": "BLOCKED", "code": code})
        ready = all(row["status"] == "PASS" for row in checks)
        return {"valid": True, "ready": ready,
            "requiresGpu": False, "gpuRenderingVerified": False, "paidRenderAllowed": False,
            "historicalRenderAllowed": bool(ready and pipeline.get("mode") == "PRODUCTION"), "scope": PROFILE, "checks": checks,
            "totalFrames": total if bounded else 0, "maxWallSeconds": 900, "maxRetries": 0}

    def preflight(self, value):
        if not selected(value):
            return super().preflight(value)
        try:
            normalized = self._normal(value)
            with self._cache.PrivateTree(self.control_root) as root:
                return self._preflight_record(root, {"submission": normalized})
        except StudioError as error:
            return {"valid": False, "ready": False, "requiresGpu": False, "gpuRenderingVerified": False,
                "error": {"code": error.code}, "historicalRenderAllowed": False}

    def _source_job(self, root, job_id):
        record = self._job_record(root, job_id)
        return record if record.get("sourcePipelineOnly") is True else None

    def _raw_status(self, job_id):
        with self._cache.PrivateTree(self.control_root) as root:
            record = self._source_job(root, job_id)
            if not record:
                return super()._raw_status(job_id)
            with root.child("source-jobs") as jobs, jobs.child(job_id) as job:
                state = job.json("state.json")
                progress_file = self.export_root / job_id / "proof/CAPTURE_STATUS.json"
                if progress_file.is_file() and not progress_file.is_symlink():
                    try:
                        progress = json.loads(progress_file.read_bytes())
                        count = progress.get("capturedFrames")
                        if (progress.get("jobId") == job_id and type(count) is int
                                and 0 <= count <= state["totalFrames"]):
                            state["processedFrames"] = count
                    except (OSError, ValueError):
                        pass  # Atomic worker state remains authoritative.
                if state["state"] in {"QUEUED", "RUNNING"} and state.get("pid"):
                    try:
                        fields = Path(f"/proc/{state['pid']}/stat").read_text().rsplit(") ", 1)[1].split()
                        alive = fields[0] != "Z" and fields[19] == state.get("processStart")
                    except (OSError, IndexError):
                        alive = False
                    if not alive:
                        with job.lock(wait_seconds=8):
                            latest = job.json("state.json")
                            if latest["state"] in {"COMPLETED", "FAILED", "INTERRUPTED"}:
                                return latest
                            state = {**latest, "state": "INTERRUPTED", "phase": "INTERRUPTED",
                                "errorCode": "STUDIO_SOURCE_WORKER_INTERRUPTED"}
                            job.write_json("state.json", state, replace=True)
                return state

    def start(self, submission_id, idempotency_key, *, consent=False):
        with self._cache.PrivateTree(self.control_root) as root:
            record = self._read_submission(root, submission_id)
        if record["submission"].get("schema") != SCHEMA:
            return super().start(submission_id, idempotency_key, consent=consent)
        if consent is not True:
            raise StudioError("STUDIO_OWNER_CONSENT_REQUIRED", status=403)
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", idempotency_key):
            raise StudioError("STUDIO_IDEMPOTENCY_KEY_INVALID", status=400)
        key = hashlib.sha256(idempotency_key.encode()).hexdigest()
        with self._cache.PrivateTree(self.control_root) as root, root.lock(wait_seconds=8):
            with root.child("requests") as requests, root.child("runs") as runs:
                previous = requests.json(key + ".json", optional=True)
                if previous and (previous.get("submissionId") != submission_id or previous.get("operation") != PROFILE):
                    raise StudioError("STUDIO_IDEMPOTENCY_CONFLICT")
                previous = previous or runs.json(submission_id + ".json", optional=True)
                if previous:
                    if not previous.get("jobId"):
                        raise StudioError("STUDIO_UNRESOLVED_START_CLAIM")
                    requests.write_json(key + ".json", previous, replace=True)
                    return self._safe_status(self._raw_status(previous["jobId"]))
                self._check_active(root)
                # Bind the persisted canonical Scene again to the current pinned
                # source index before claim/launch; no stale or modified source.
                submission = record["submission"]
                original = submission.get("sourcePipeline", {}).get("originalRequest")
                if original is None or _sha(self._normal(original)) != _sha(submission):
                    raise StudioError("STUDIO_SOURCE_SCENE_BINDING_CHANGED")
                if not self._preflight_record(root, record)["ready"]:
                    raise StudioError("STUDIO_PREFLIGHT_BLOCKED")
                job_id = "studio-" + hashlib.sha256((submission_id + key).encode()).hexdigest()[:32]
                now = datetime.now(timezone.utc)
                total = submission["sourcePipeline"]["totalFrames"]
                start_frame = submission["sourcePipeline"]["startFrame"]
                receipt = {"schema": "WORLD_ENGINE_STUDIO_SOURCE_EXECUTION_V2", "jobId": job_id,
                    "softwareOnly": True,
                    "historicalRenderAllowed": submission["sourcePipeline"].get("mode") == "PRODUCTION",
                    "sourceScope": submission["sourcePipeline"].get("scope"), "sourceIndexSHA256": self.expected_index_sha256,
                    "frameRange": [start_frame, start_frame + total],
                    "maxWallSeconds": 900, "expiresAt": (now + timedelta(seconds=900)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    "requestSHA256": submission["sourcePipeline"].get("requestSHA256"),
                    "traceStages": ["AUTHENTICATED_STUDIO_HTTP", "SOURCE_SCENE_NORMALIZER", "SOURCE_REGISTRY",
                        "PRIVATE_SUBMISSION", "EXPLICIT_OWNER_CONSENT", "PRIVATE_START_CLAIM", "SOURCE_RUNTIME_SELECTOR", "DETACHED_SOFTWARE_WORKER"]}
                claim = {"operation": PROFILE, "submissionId": submission_id, "jobId": job_id, "state": "CLAIMED"}
                requests.write_json(key + ".json", claim)
                runs.write_json(submission_id + ".json", claim)
                root.write_json("active.json", {"jobId": job_id}, replace=True)
                with root.child("jobs") as jobs:
                    jobs.write_json(job_id + ".json", {**claim, "sourcePipelineOnly": True})
                with root.child("source-jobs") as jobs, jobs.child(job_id, create=True) as job:
                    package = {**deepcopy(submission), "executionReceipt": receipt}
                    job.write_json("compiledpackage.json", package)
                    state = {"jobId": job_id, "state": "QUEUED", "phase": "SOURCE_VERIFY", "totalFrames": total,
                        "processedFrames": 0, "totalScenes": 1, "completedScenes": 0, "requiresGpu": False,
                        "gpuRenderingVerified": False, "createdAt": now.isoformat()}
                    job.write_json("state.json", state)
                    job_path = self.control_root / "source-jobs" / job_id
                    plan_sha = hashlib.sha256((job_path / "compiledpackage.json").read_bytes()).hexdigest()
                    log = os.open(job_path / "worker.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    try:
                        child = subprocess.Popen([sys.executable, str(HERE / "software_worker.py"),
                            "--job-root", str(job_path), "--export-root", str(self.export_root), "--plan-sha256", plan_sha],
                            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, close_fds=True)
                        fields = Path(f"/proc/{child.pid}/stat").read_text().rsplit(") ", 1)[1].split()
                        state.update(pid=child.pid, processStart=fields[19])
                        job.write_json("state.json", state, replace=True)
                        job.write_json("launch.json", {"pid": child.pid})
                    finally:
                        os.close(log)
                return self._safe_status(state)

    def result(self, job_id):
        with self._cache.PrivateTree(self.control_root) as root:
            record = self._source_job(root, job_id)
            if record:
                if self._raw_status(job_id)["state"] != "COMPLETED":
                    raise StudioError("STUDIO_RESULT_NOT_READY")
                with root.child("source-jobs") as jobs, jobs.child(job_id) as job:
                    return job.json("result.json")
        return super().result(job_id)

    def resume(self, job_id, idempotency_key, *, consent=False):
        with self._cache.PrivateTree(self.control_root) as root:
            if self._source_job(root, job_id):
                raise StudioError("STUDIO_SOURCE_AUTORETRY_FORBIDDEN")
        return super().resume(job_id, idempotency_key, consent=consent)

    def revise(self, job_id, value):
        with self._cache.PrivateTree(self.control_root) as root:
            if self._source_job(root, job_id):
                raise StudioError("STUDIO_SOURCE_REVIEW_IMMUTABLE")
        return super().revise(job_id, value)
