# 65422 hardware render execution — current storage adapter

This runbook supersedes only the old bootstrap/output-path examples in `rtx-gpu-package-v1/GCUBE_EXECUTION.md`. It preserves that file and all original source. It prepares a future separately authorized GPU operation; executing the paid workload is not part of this preparation.

User reports the existing GPU/WebGL2 inspection passed. Do not rerun the old diagnostics or full package suites. The original renderer still performs its mandatory native admission on each actual capture; this guard cannot be skipped based on a previous pass.

## Settings to copy after separate execution authorization

| Setting | Value |
| --- | --- |
| Image | `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:rtx4080s-2f9158b-38722819744-1` (digest below; no image rebuild on gCube) |
| GPU | One assigned RTX 4080 SUPER 16GB |
| Command override | Empty for normal health service plus authorized terminal method below |
| User | Preserve image root entrypoint and its original UID/GID1000 transition |
| CPU / RAM | Existing package recommendation: at least4 cores /8GiB;16GiB RAM gives unmeasured headroom |
| Shared memory | Configure2GiB; verify actual `/dev/shm` capacity and available bytes |
| Dropbox | Approved writable mount at `/world-storage`; never change existing mount ownership/mode |
| Port | 8000, existing normal GPU health service |
| `WORLD_ENGINE_STARTUP_MODE` | `normal` |
| `WORLD_ENGINE_RENDER_MODE` | `gpu-required` |
| `NVIDIA_DRIVER_CAPABILITIES` | `graphics,utility` |
| `NVIDIA_VISIBLE_DEVICES` | Preserve provider-assigned allocation; do not substitute all devices |
| `WORLD_ENGINE_GPU_PROFILE` | Leave unset for existing native profile selection |

Verified immutable reference:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:1a0a953d36ed0269a0c99267dd2d2d9e92ac6c50ffb7808e78bfbde24e7e2842
```

Build and independent CPU pull both passed in Actions38722819744. This is not a hardware or video-quality result.

Do not set diagnostic mode and do not use `--check` or `--check-storage` as a long-running workload. No new HTTP render endpoint or remote command API exists.

## Preferred existing execution method

Required platform conditions: an already-authorized **normal-mode** health service remains running, and an authorized terminal/exec/SSH method for that same workload is available. This environment has not verified #5373 shell access. Do not start or restart a workload simply to test the command below.

Open that existing normal-mode container terminal and run the **active storage entrypoint**, once:

```sh
WORLD_ENGINE_STARTUP_MODE=normal WORLD_ENGINE_RENDER_MODE=gpu-required \
/usr/bin/python3 /opt/world-engine-storage-fix/launch.py --render-65422 --vram-budget-gib 8
```

Run this in the foreground of a stable terminal. Preserve the command exit status and its structured stdout/stderr in a private operator log; do not publish full diagnostic archives or environment dumps. An SSH connection that dies may interrupt the child. Do not blindly repeat the command after losing a connection: first inspect `WORLD_ENGINE_EXPORT_LOCATION_V1`, the recorded capture status and completion receipt.

The existing PID1 normal health service remains available while the separate child performs native capture, encoding and export. The child exits0 only after verified mounted-view export; a child failure returns nonzero and emits the existing sanitized startup error. This is process composition already supported by the existing launcher, not a new renderer mode. Do not invoke this command in a diagnostic-mode workload and pretend its diagnostic readiness authorizes rendering.

The older direct `/opt/rtx-package/.../bootstrap.py --render-65422` example bypasses the active shared-storage export adapter. Do not use it for this task.

## Command override alternative — conditional, not platform-verified

Docker appends an argument list to the image ENTRYPOINT. For a platform that explicitly exposes image arguments, the argument list is:

```json
["--render-65422", "--vram-budget-gib", "8"]
```

A platform that **replaces** the executable instead requires:

```text
/usr/bin/tini -g -- /usr/bin/python3 /opt/world-engine-storage-fix/launch.py --render-65422 --vram-budget-gib 8
```

Saved official gCube documentation defines a `containerCommand` string and blank=image default, but does not establish which override semantics apply. Do not paste either alternative until the actual field contract is confirmed.

Direct PID1 capture is a one-shot job: it serves no `/healthz` during rendering and exits after export. It is safe only with a verified one-shot policy, no liveness probe that kills an active capture, and no automatic successful restart. `Never` is preferable to avoid automatic retries of a partially completed paid job. Inherited Docker healthcheck has a300-second start period and can report unhealthy afterward; Docker health status itself is not a verified gCube restart policy. An Always restart policy can create a fresh session and render again. The original locks prevent concurrency, not sequential repeated executions.

If neither a verified existing terminal nor a verified one-shot override/policy exists, **GPU execution is blocked by platform configuration**. Do not guess command parsing or add an untested keepalive service. A separate startup package can be considered only after the actual missing platform capability is established.

## Resource checks before authorizing a run

Original admission requires a supported physical GPU reporting at least15360MiB, default VRAM growth budget8GiB, and2GiB free reserve; admission therefore needs at least10GiB free for this budget. Memory is polled during capture, not reserved by a hardware partition. Shared-memory capacity **and available bytes** must each be at least1GiB; configure2GiB.

The launcher has no quantitative free-disk admission gate; its storage probe verifies actual small I/O. Read available capacity without changing storage:

```sh
python3 - <<'PY'
import json, os, shutil
for label, path in [('private', '/var/lib/world-engine-private/engine'), ('export', '/world-storage')]:
    value = shutil.disk_usage(path)
    print(json.dumps({'storageRole':label, 'freeBytes':value.free, 'totalBytes':value.total}))
s = os.statvfs('/dev/shm')
print(json.dumps({'storageRole':'shared-memory', 'capacityBytes':s.f_blocks*s.f_frsize, 'availableBytes':s.f_bavail*s.f_frsize}))
PY
```

150 raw RGBA frames equal1,244,160,000bytes (~1.159GiB) before PNG encoding. Five checkpoints add ~39.6MiB raw-equivalent, plus ~17MiB frame diagnostics, browser scratch, MP4/partial encoding, receipts and an export copy. Compression and peak space are not measured hardware results. Conservative planning recommendation: at least8GiB free private local workspace and2GiB export headroom; count both if the mount caches onto the same disk. Provider quota may differ from reported filesystem free space. Do not delete existing files or assume this recommendation is a renderer hard limit.

The original render deadline is3600seconds. It does not bound image pull, startup, Dropbox synchronization, external recovery or idle billing. On failure inspect the first sanitized stage/code before retrying.

## Output and completion

Expected output:1080×1920,30fps,150frames,5.000seconds, one H.264 video stream, no audio. The existing FFmpeg pipeline uses libx264, preset fast, CRF16, yuv420p and faststart; no encoder change is made here.

The existing capture creates:

```text
WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4
01_START.png                 frame0
02_ADVANCE.png               frame38
03_TRACKING.png              frame75
04_CONTINUOUS_CONTROL.png    frame112
05_END.png                   frame149
SHA256SUMS
```

Private work: `/var/lib/world-engine-private/engine/session-<random>/captures/<signature>/`.
Approved shared export:

```text
/world-storage/world-engine-export-<random>/capture-<signature12>-<random>/
  EXPORT_COMPLETE.json
  public-review/             only MP4, five PNG and SHA256SUMS
```

Read the exact generated names and per-file hashes from `WORLD_ENGINE_EXPORT_LOCATION_V1`. Do not select a latest glob, replace an older Candidate, or treat a partially copied directory as success. The source capture report must be `CAPTURE_TECHNICAL_PASS`; all public SHA checks and mounted destination readback must pass; `EXPORT_COMPLETE.json` is written last outside public-review.

`CAPTURE_TECHNICAL_PASS` is not visual-quality approval. Follow `DROPBOX_VERIFICATION.md` before stopping the workload.

## Cost and stop boundary

No current account tariff or render throughput was measured. Do not use an old RTX4080 demonstration price as a RTX4080SUPER quote. Obtain the selected live node rate and minimum billing increment before approving execution:

```text
cost = hourly rate × (pull/startup + native admission + capture/encode
       + Dropbox sync + external download verification + idle/retry seconds) /3600
       + actual storage/network/VAT/rounding charges
```

Provider billing continues while idle until the provider stops the workload. Neither a render exit0 nor its3600-second watchdog is an automatic provider stop. Agree on a cost/time limit before the separately authorized run. Stop only after required outputs/logs have been externally recovered and their SHA verified; this preparation does not execute that stop.
