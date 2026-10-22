"""Latest Studio extension: authenticated, explicit, bounded software regression.

Existing production calls delegate unchanged. This branch authorizes only the
original software capture, never NVIDIA, a historical preview or full production.
"""
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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


parent = load("_gates_preserved_director_controller", HERE.parent / "astra-event-director-v2/studio_controller.py")
contract = load("_gates_reference_contract", HERE / "reference_contract.py")
StudioError = parent.StudioError


class StudioController(parent.StudioController):
    def __init__(self, *, allow_software_reference=False, capsule_root=None, original_report=None, history_source_gate=None, **kwargs):
        self.allow_software_reference = allow_software_reference is True
        # A source-owner callback, never a Scene/body approval flag. Different
        # source packages may supply their own qualified control-state provider.
        self.history_source_gate = history_source_gate
        self.capsule_root = Path(capsule_root or "/workspace/exact-65422-capsule-20261020")
        self.original_report = Path(original_report or "/workspace/exact-65422-original-report-20261020.json")
        # Own namespace keeps existing submissions, completed claims and caches.
        cache = parent.parent.parent.parent.load_original("cache")
        with cache.PrivateTree(Path(kwargs["control_root"]), create=True):
            pass
        kwargs["control_root"] = Path(kwargs["control_root"]) / "studio-integration-gates-v1"
        super().__init__(**kwargs)
        with self._cache.PrivateTree(self.control_root) as root:
            with root.child("reference-jobs", create=True):
                pass

    def _normal(self, value):
        if contract.selected(value):
            return contract.normalize(value, capsule_root=self.capsule_root, error=StudioError)
        return super()._normal(value)

    def _preflight_record(self, root, record):
        submission = record["submission"]
        if submission.get("schema") != contract.SCHEMA:
            result = super()._preflight_record(root, record)
            if isinstance(submission.get("eventDirector"), dict) and self.history_source_gate is not None:
                evidence = self.history_source_gate(request=submission)
                result["sourceControlGate"] = evidence
                if evidence.get("renderAllowed") is not True:
                    result["ready"] = False
                    result["reviewReady"] = False
                    result["checks"].append({"name": "SOURCE_QUALIFIED_CONTROL_STATE", "status": "BLOCKED", "code": "G2_SOURCE_CONTROL_NOT_ADMITTED"})
            return result
        # Revalidate persisted input and source, rather than trust a client flag.
        normalized = self._normal(submission["request"])
        if contract.sha(normalized) != contract.sha(submission):
            raise StudioError("STUDIO_EXACT_REFERENCE_SOURCE_CHANGED")
        checks = [{"name": "EXACT_SOURCE_SCENE", "status": "PASS"},
                  {"name": "SOFTWARE_REFERENCE_OPT_IN", "status": "PASS" if self.allow_software_reference else "BLOCKED"},
                  {"name": "SOFTWARE_DEPENDENCIES", "status": "PASS" if shutil.which("node") and shutil.which("ffmpeg") else "BLOCKED"},
                  {"name": "PRIVATE_DISK_RESERVE", "status": "PASS" if shutil.disk_usage(self.control_root).free >= 2 * 1024**3 else "BLOCKED"}]
        return {"valid": True, "ready": all(r["status"] == "PASS" for r in checks),
                "requiresGpu": False, "gpuRenderingVerified": False, "checks": checks,
                "scope": contract.PROFILE, "paidRenderAllowed": False,
                "maxWallSeconds": 900, "maxRetries": 0, "totalFrames": 150}

    def preflight(self, value):
        if not contract.selected(value):
            return super().preflight(value)
        try:
            submission = self._normal(value)
            with self._cache.PrivateTree(self.control_root) as root:
                return self._preflight_record(root, {"submission": submission})
        except StudioError as error:
            return {"valid": False, "ready": False, "requiresGpu": False,
                    "error": {"code": error.code}, "gpuRenderingVerified": False}

    def _reference_job(self, root, job_id):
        record = self._job_record(root, job_id)
        return record if record.get("referenceOnly") is True else None

    def _raw_status(self, job_id):
        with self._cache.PrivateTree(self.control_root) as root:
            record = self._reference_job(root, job_id)
            if not record:
                return super()._raw_status(job_id)
            with root.child("reference-jobs") as jobs, jobs.child(job_id) as job:
                state = job.json("state.json")
                progress_path = self.export_root / job_id / "proof/CAPTURE_STATUS.json"
                if progress_path.is_file() and not progress_path.is_symlink():
                    progress = json.loads(progress_path.read_bytes())
                    if type(progress.get("capturedFrames")) is int:
                        state["processedFrames"] = progress["capturedFrames"]
                if state["state"] in {"QUEUED", "RUNNING"} and state.get("pid"):
                    try:
                        proc = Path("/proc") / str(state["pid"]) / "stat"
                        stat_fields = proc.read_text().rsplit(") ", 1)[1].split()
                        alive = stat_fields[0] != "Z" and stat_fields[19] == state.get("processStart")
                    except (OSError, IndexError):
                        alive = False
                    if not alive:
                        # The worker may have committed COMPLETED between our
                        # first read and its exit. Never overwrite that record.
                        with job.lock(wait_seconds=8):
                            latest = job.json("state.json")
                            if latest["state"] in {"COMPLETED", "FAILED", "INTERRUPTED"}:
                                return latest
                            state = {**latest, "state": "INTERRUPTED", "phase": "INTERRUPTED",
                                     "errorCode": "STUDIO_REFERENCE_WORKER_INTERRUPTED"}
                            job.write_json("state.json", state, replace=True)
                return state

    def start(self, submission_id, idempotency_key, *, consent=False):
        with self._cache.PrivateTree(self.control_root) as root:
            record = self._read_submission(root, submission_id)
        if record["submission"].get("schema") != contract.SCHEMA:
            return super().start(submission_id, idempotency_key, consent=consent)
        if consent is not True:
            raise StudioError("STUDIO_OWNER_CONSENT_REQUIRED", status=403)
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", idempotency_key):
            raise StudioError("STUDIO_IDEMPOTENCY_KEY_INVALID", status=400)
        key = hashlib.sha256(idempotency_key.encode()).hexdigest()
        with self._cache.PrivateTree(self.control_root) as root, root.lock(wait_seconds=8):
            with root.child("requests") as requests, root.child("runs") as runs:
                previous = requests.json(key + ".json", optional=True)
                if previous and (previous.get("submissionId") != submission_id or previous.get("operation") != contract.PROFILE):
                    raise StudioError("STUDIO_IDEMPOTENCY_CONFLICT")
                previous = previous or runs.json(submission_id + ".json", optional=True)
                if previous:
                    if not previous.get("jobId"):
                        raise StudioError("STUDIO_UNRESOLVED_START_CLAIM")
                    requests.write_json(key + ".json", previous, replace=True)
                    return self._safe_status(self._raw_status(previous["jobId"]))
                self._check_active(root)
                if not self._preflight_record(root, record)["ready"]:
                    raise StudioError("STUDIO_PREFLIGHT_BLOCKED")
                job_id = "studio-" + hashlib.sha256((submission_id + key).encode()).hexdigest()[:32]
                now = datetime.now(timezone.utc)
                submission = record["submission"]
                receipt = {"schema": "WORLD_ENGINE_STUDIO_REFERENCE_EXECUTION_V1", "jobId": job_id,
                    **{k: submission[k] for k in ("requestSHA256", "normalizerSHA256", "sourceSceneSHA256", "sourceCommit", "runtimeSourceSignature")},
                    "softwareOnly": True, "approvedFrameRange": [0, 150], "maxWallSeconds": 900,
                    "expiresAt": (now + timedelta(seconds=900)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    "traceStages": ["AUTHENTICATED_STUDIO_HTTP", "STRICT_REFERENCE_NORMALIZER", "PRIVATE_SUBMISSION",
                                    "EXPLICIT_OWNER_CONSENT", "PRIVATE_START_CLAIM", "EXACT_RUNTIME_SELECTOR", "DETACHED_SOFTWARE_WORKER"]}
                claim = {"operation": contract.PROFILE, "submissionId": submission_id, "jobId": job_id, "state": "CLAIMED"}
                # Persist before launch, including an active claim. A failed or
                # interrupted launch is never silently reset or retried.
                requests.write_json(key + ".json", claim)
                runs.write_json(submission_id + ".json", claim)
                root.write_json("active.json", {"jobId": job_id}, replace=True)
                with root.child("jobs") as jobs:
                    jobs.write_json(job_id + ".json", {**claim, "referenceOnly": True})
                with root.child("reference-jobs") as jobs, jobs.child(job_id, create=True) as job:
                    job.write_json("receipt.json", receipt)
                    state = {"jobId": job_id, "state": "QUEUED", "phase": "SOURCE_VERIFY",
                             "totalFrames": 150, "processedFrames": 0, "totalScenes": 1, "completedScenes": 0,
                             "requiresGpu": False, "gpuRenderingVerified": False, "createdAt": now.isoformat()}
                    job.write_json("state.json", state)
                    job_path = self.control_root / "reference-jobs" / job_id
                    receipt_sha = hashlib.sha256((job_path / "receipt.json").read_bytes()).hexdigest()
                    log = os.open(job_path / "worker.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    try:
                        process = subprocess.Popen([sys.executable, str(HERE / "software_worker.py"),
                            "--job-root", str(job_path), "--export-root", str(self.export_root),
                            "--receipt-sha256", receipt_sha, "--capsule-root", str(self.capsule_root),
                            "--original-report", str(self.original_report)], stdin=subprocess.DEVNULL,
                            stdout=log, stderr=log, start_new_session=True, close_fds=True)
                        proc_fields = Path(f"/proc/{process.pid}/stat").read_text().rsplit(") ", 1)[1].split()
                        state.update(pid=process.pid, processStart=proc_fields[19])
                        # Worker waits for launch.json, so state cannot be overwritten by a race.
                        job.write_json("state.json", state, replace=True)
                        job.write_json("launch.json", {"pid": process.pid})
                    finally:
                        os.close(log)
                return self._safe_status(state)

    def result(self, job_id):
        with self._cache.PrivateTree(self.control_root) as root:
            record = self._reference_job(root, job_id)
            if record:
                state = self._raw_status(job_id)
                if state["state"] != "COMPLETED":
                    raise StudioError("STUDIO_RESULT_NOT_READY")
                with root.child("reference-jobs") as jobs, jobs.child(job_id) as job:
                    return job.json("result.json")
        return super().result(job_id)

    def resume(self, job_id, idempotency_key, *, consent=False):
        with self._cache.PrivateTree(self.control_root) as root:
            if self._reference_job(root, job_id):
                raise StudioError("STUDIO_REFERENCE_AUTORETRY_FORBIDDEN")
        return super().resume(job_id, idempotency_key, consent=consent)

    def revise(self, job_id, value):
        with self._cache.PrivateTree(self.control_root) as root:
            if self._reference_job(root, job_id):
                raise StudioError("STUDIO_REFERENCE_INPUT_IMMUTABLE")
        return super().revise(job_id, value)
