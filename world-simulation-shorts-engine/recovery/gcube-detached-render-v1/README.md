# 65422 render job independent of a mobile terminal

This package adds a local, explicitly started job supervisor. It reuses the original hardware launcher, renderer, GPU admission, storage export and artifact verifier. It adds no HTTP endpoint and leaves the image ENTRYPOINT, normal `/healthz` service and approved visuals unchanged.

The exact cause of the reported #5373 mobile disconnection and the current legacy job's state have **not** been observed here. A confirmed interruption path exists in the old foreground command: SIGHUP becomes `GPU_RENDER_INTERRUPTED` and stops its rendering child. That is not proof that this was the actual provider/browser failure.

## 1. Check the existing #5373 container first

Do not restart, redeploy, stop or submit another render to find out whether the old job is alive. If its existing authorized terminal is accessible, the following command downloads only the read-only inspector from immutable implementation commit `aaa9347bcb50eaa480dc83e135bc2ebca6f1f5f2`, verifies its SHA **before execution**, and runs it without a GPU probe. Downloading creates one fresh private temporary file; inspection does not modify job or result files.

```sh
/usr/bin/python3 -B - <<'PY'
import hashlib, os, pathlib, subprocess, tempfile, urllib.request
url = ('https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/'
       'aaa9347bcb50eaa480dc83e135bc2ebca6f1f5f2/'
       'world-simulation-shorts-engine/recovery/gcube-detached-render-v1/inspect_existing.py')
expected = '23a361ac0da95dad50ae7c2d5a57d2e527c904869b2d8bbf8e99146386cf7b38'
try:
    with urllib.request.urlopen(url, timeout=30) as response:
        if response.status != 200:
            raise ValueError()
        body = response.read(128 * 1024 + 1)
    if len(body) > 128 * 1024 or hashlib.sha256(body).hexdigest() != expected:
        raise ValueError()
except Exception:
    raise SystemExit('PINNED_INSPECTOR_DOWNLOAD_OR_SHA_FAILED; no inspector executed')
directory = pathlib.Path(tempfile.mkdtemp(prefix='world-engine-readonly-inspect-'))
script = directory / 'inspect_existing.py'
fd = os.open(script, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'wb') as output:
    output.write(body)
raise SystemExit(subprocess.run(['/usr/bin/python3', '-B', str(script)], check=False).returncode)
PY
```

Interpret the allowlisted JSON, not its exit code alone:

| Status | Action |
| --- | --- |
| `RUNNING` | A native render process, matching PID/boot/start identity or held capture lock exists. Leave it running; do not start another job. |
| `EXISTING_RECORDS` | Prior local capture or shared export evidence exists, including incomplete work. Preserve it and recover the exact existing result before considering any further execution. |
| `BLOCKED` | Access, path identity, evidence format or bounded inspection could not be established. Resolve that specific uncertainty; do not treat it as no job. |
| `CLEAR` | No native capture evidence was found in this snapshot. This is not GPU permission, a distributed no-job guarantee or approval for a paid run. Check the manager's own ledger and shared claim too. |

The inspector prints safe PID identities and counts, never command arguments, environment values or complete private reports. It also checks the original bootstrap's known `/world-storage/rtx-gpu-package-v1/captures/<signature>` path, so an older capture cannot be mistaken for no prior work. Admission-only diagnostics without captures do not count as rendering. A stale `CAPTURE_STATUS.json` saying `IN_PROGRESS`, a lock file's mere presence, a previous GPU PASS or an MP4's presence cannot establish current activity or successful completion. Missing or inaccessible terminal/files are not evidence that rendering never started. Do not modify permissions, remove locks or choose a “latest” result to force a clean state.

## 2. New image settings — after review and paid-run authorization

For gCube's image field use the new unique tag:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:rtx4080s-2f9158b-38737830116-1
```

The independently pulled immutable reference in `IMAGE.json` is:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5dc61e9ce0edfc175c4a38fa0a3f559e660761e604b65bb5edfb6704312610b7
```

If gCube accepts digest references, prefer the immutable reference; tag/digest input support still depends on the platform. Existing images remain preserved. Do not replace a live container merely to inspect its previous job; replacement can destroy private evidence.

| Setting | Value |
| --- | --- |
| GPU | One RTX 4080 SUPER 16GB |
| Command override | **Empty**; retain the existing normal health service |
| User | Preserve the image root entrypoint and original UID/GID1000 transition |
| Port | 8000 |
| Shared memory | 2GiB |
| Dropbox mount | Approved existing writable mount at `/world-storage` |
| `WORLD_ENGINE_STARTUP_MODE` | `normal` |
| `WORLD_ENGINE_RENDER_MODE` | `gpu-required` |
| `NVIDIA_DRIVER_CAPABILITIES` | `graphics,utility` |
| `NVIDIA_VISIBLE_DEVICES` | Preserve the provider-assigned allocation |

Do not use diagnostic mode or put the job manager/start command in the container command override. No public render API is provided. Actual gCube command-override precedence, liveness/restart policy, mobile/SSH lifecycle and account access remain platform verification items. Saved official documentation establishes blank command=image default; it does not certify those provider policies for #5373.

Retain the prior resource and billing limits in [the existing execution runbook](../gcube-65422-render-v1/GCUBE_RENDER_EXECUTION.md). This package does not authorize deployment, impose a provider spending cap or automatically stop billing.

## 3. Three commands in the authorized normal-mode container

First inspect existing native work:

```sh
/usr/bin/python3 -B /opt/world-engine-detached-render/job_manager.py inspect
```

Then check the manager's job state. This command may reconcile a lost worker into a recorded failure; it does not start rendering:

```sh
/usr/bin/python3 -B /opt/world-engine-detached-render/job_manager.py status
```

Only after prior-job uncertainty is resolved, no existing claim/job is blocking execution, and the paid GPU run has been approved, explicitly submit **one** job:

```sh
/usr/bin/python3 -B /opt/world-engine-detached-render/job_manager.py start --confirm-new-job
```

Wait for a JSON response containing the actual `jobId` and a non-null `supervisorIdentity` (`pid`, `bootId`, `startTime`), with state `RUNNING` or an already finished terminal state. That persisted supervisor record is the start acknowledgement. Record the job ID privately before closing the terminal. A `QUEUED` response, timeout, disconnected terminal or missing acknowledgement means **run `status` first**, never repeat the native render command or assume submission failed.

The supervisor creates its own session, ignores terminal SIGHUP, disconnects standard input/output from the PTY, and retains the job lock. It starts only the fixed original `launch.py --render-65422 --vram-budget-gib 8` command. Original GPU checks remain mandatory for that actual capture; old diagnostic suites are not rerun by these preparation commands.

`start` returns an existing job instead of dispatching again. Local terminal states `COMPLETED` and `FAILED` are retained; neither permits another launch. An existing or conflicting shared claim vetoes a new job. There is intentionally no reset/delete/retry endpoint or automatic render-on-container-start behavior.

## 4. Reconnect and recover the exact result

After reconnecting, use the same `status` command. States are `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`; phase, first safe native failure, process identities and exit code remain in the bounded record. A `FAILED` state alone does not prove every native process is idle: run `inspect` before any recovery decision. Never delete an existing job, claim or result to retry.

Private local control files are under `/var/lib/world-engine-private/engine/job-control-v1`. The safe Dropbox ledger is separate from public review:

```text
/world-storage/world-engine-65422-job-v1/
  CLAIM.json
  state-<sequence>-<random>.json
```

The append-only state records carry the same `jobId`. They are evidence and a retry veto, not trusted instructions or proof of external synchronization. Do not select an arbitrary “latest” shared JSON to authorize work. The private journal/claim identities govern the manager; shared state alone never resumes rendering.

Manager fields `gpuRenderingVerified:false`, `remotePersistenceVerified:false` and `externalDownloadVerified:false` mean the manager does not independently attest those outcomes. They are not substitutes for the unchanged native GPU-admission evidence or independent Dropbox/download checks. A successful native capture still must pass its original GPU checks.

A `COMPLETED` manager record has a non-null `.result` identifying the exact original storage adapter export:

```text
/world-storage/<result.exportDirectory>/<result.captures[0].directory>/
  EXPORT_COMPLETE.json
  public-review/
    WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4
    01_START.png
    02_ADVANCE.png
    03_TRACKING.png
    04_CONTINUOUS_CONTROL.png
    05_END.png
    SHA256SUMS
```

Use those exact generated names and source SHA values. Completion requires the original success receipt, all seven expected public files, source/destination hashes and original artifact/FFprobe verification. A zero child exit without a verified result never becomes `COMPLETED`. Mount readback does **not** prove Dropbox remote persistence or external download.

Follow the unchanged [Dropbox verification procedure](../gcube-65422-render-v1/DROPBOX_VERIFICATION.md): confirm the exact remote Dropbox files, preserve the independent source SHA of `SHA256SUMS`, download the original seven files through approved direct links, verify actual HTTP200 and downloaded SHA, decode and play the MP4, then review it against65422/reference. Keep `CLAIM.json`, job states, completion receipt, logs, diagnostics and source outside Public Review. Only MP4, five PNGs and SHA256SUMS may be public.

## Limits and recovery boundary

- Detachment protects against terminal/session loss. It cannot survive provider termination, SIGKILL, container deletion, host failure or exhausted storage by itself.
- A container restart never automatically renders. A preserved shared claim blocks an accidental fresh job even if local state was lost. Missing, stale or conflicting mounted evidence blocks recovery rather than authorizing a rerun.
- If both private state and shared claim are lost, delayed or inconsistently visible, this is not a globally distributed exactly-once guarantee. No paid rerun is authorized by absence alone; recover provider/job evidence and resolve it explicitly.
- Do not stop the paid workload until required logs and public artifacts have been independently recovered. Stopping may destroy private data; provider billing continues until an authorized provider stop, not merely until render completion.
- Actual #5373 process state, provider restart policy, physical GPU execution, Dropbox remote durability, independent downloads and video quality require their own real evidence. CPU tests do not mark them PASS.

Stop for user review after preparing and verifying this package. No FINAL promotion or14-second expansion is performed.
