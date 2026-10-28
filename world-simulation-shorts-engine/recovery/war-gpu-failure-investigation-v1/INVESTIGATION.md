# WAR GPU failure investigation — BLOCKED
Date: 2026-10-29 (Asia/Seoul)
Job: `studio-86e62700b98ac8d70089b3fe8534a693`

## Conclusion
The first capture failure is **UNKNOWN**. The observed UI shows RUNNING, UNRESOLVED_CAPTURE_CLEANUP and HANDOFF_UNRESOLVED_WORKER_OR_DESCENDANTS with 87/180 reported frames. No actual first exception, operation checkpoint, original state.json or supervisor cleanup receipt for this job was recovered.

This investigation makes no code change and no GPU/CPU engine execution. G0, G1, G2, WAR Scene contract and WAR map/camera CPU PASS remain unchanged.

## What the error actually establishes
At immutable G2 source commit `27f9fa5c133a65ed08824cf047116128bd9dfe5e`, [NvidiaPresentationBackend.studio_status(), nvidia_backend.py lines 259–271](https://github.com/dimon3898-sys/yeonhwarok-free/blob/27f9fa5c133a65ed08824cf047116128bd9dfe5e/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/nvidia_backend.py#L259) returns the displayed error when a saved QUEUED/RUNNING worker cannot be matched to a non-zombie process with the same start identity. Missing PID fields, process-read errors and mismatched identity can take the same path. It overwrites the response phase and errorCode; it does not establish the original capture exception or actual descendant survival.

The displayed 87 is propagated only after completed frame output. It is not proof that frameIndex 87 failed. Reference source and installed-image source mapping, exact excerpts, Git blob identities and line numbers are preserved in SOURCE_TRACE.json. The gCube configured tag matches the retained G2 tag, but actual failed runtime digest and Scene hash were not exposed, so all source-to-incident attribution remains conditional.

## Observed timeline and limits
| Source | Observed time | Fact |
|---|---|---|
| gCube workload #5373 Events | 2026-10-29 07:26:31 | Downloading container image |
| gCube Events | 07:26:32 | Image downloaded, container created and started |
| gCube workload header | 07:26:38 | Last Deployed display; separate UI field |
| User screenshot file metadata | 07:34:08.599181 KST | File created/uploaded; contains target job, 87/180 and error |
| gCube Events | 07:34:59 | “Forcibly terminating container”; detail Normal / kubelet / Stopping container dep5373-0 |
| Current UI | Investigation time | Finished; Terminal and SSH disabled |

Pod shown: `dep5373-7498c68478-dq8m7`; event identifier: `wn7e9b3dce`.
The screenshot metadata is not the image capture or runtime failure timestamp. The job-to-pod link, raw provider timestamp, process signals, exit code and termination requester are missing. Therefore these observations cannot establish a complete process-level sequence or prove that platform termination caused the first failure.

The [gCube workload](https://gcube.ai/demand/ns74a360e2/workload/5373) and [monitoring](https://gcube.ai/demand/ns74a360e2/workload/5373/monitoring) were read through the existing authenticated session. Monitoring returned GPU, GPU memory, CPU, RAM and network charts for the requested 07:25–07:36 window at one-minute sampling. Charts do not establish OOM or any per-process exit cause. The existing Studio URL failed to open with ERR_HTTP_RESPONSE_CODE_FAILURE; no HTTP status/body was inferred.

## Dropbox evidence
The exact job-ID search returned zero matches. A complete direct listing of /WORLD_ENGINE had 97 children. Seven recent export folders, modified 22:26–22:31 UTC, each contained a single 897-byte storage-preflight JSON; metadata and extracted contents were read. None included this job's exception, process state or cleanup record.

The preflight files record mountedViewReadbackVerified=true, privateDataAllowed=false and remotePersistenceVerified=false. These are historical storage preflight records, not a new validation and not proof of capture or remote diagnostic outcome. Earlier studio-ebd5… and studio-56ad… diagnostic files were excluded. Dropbox NOT_FOUND for /world-storage does not show a mount failure: /world-storage is the container mount name, not necessarily its cloud path. Search completeness is limited to the connected account and examined locations.

## Why absent diagnostics do not resolve the cause
[nvidia_worker.py lines 246–251](https://github.com/dimon3898-sys/yeonhwarok-free/blob/27f9fa5c133a65ed08824cf047116128bd9dfe5e/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/nvidia_worker.py#L246) exports only when cleanup is verified and unresolved=false. The wrapper also requires time before the deadline; the safe exporter requires cleanupVerified=true. This explains a conditional preservation gap, not the actual reason for missing diagnostics in this job.

Node stdout/stderr is combined into the supervisor pipe, whose parser keeps allowed progress/failure records; arbitrary raw stderr is not automatically persisted by that code. worker.log and lease-supervisor.stderr.log have different producers and are not interchangeable with Node stderr. Neither was recovered for this job.

## Minimum correction and next action
No code correction target is established. First recover existing target state.json, capture/CAPTURE_OPERATION_CHECKPOINT.json, capture/CAPTURE_RECEIPT.json, FIRST_CAPTURE_FAILURE.json, LEASE_SUPERVISOR_RESULT.json, worker.log and lease-supervisor.stderr.log, plus retained platform exit/signal/OOM records. RESULT.json lists exact paths and fields.

Compare firstFailure and cleanupFailure separately using operationId, sequence, observedAtUnixMs, PID/start identity and executionDeadline. Until these exist, do not change timeouts, process cleanup, Scene or renderer. No next execution is authorized.

Current UI cannot recover stopped private storage, and examined Dropbox backups lack the target diagnostics. User/provider intervention is needed only to provide already retained records. LOG_RECOVERY_REQUEST.txt is a ready request; it has not been sent. No restart, deployment, build, rendering or repeat validation is requested.
