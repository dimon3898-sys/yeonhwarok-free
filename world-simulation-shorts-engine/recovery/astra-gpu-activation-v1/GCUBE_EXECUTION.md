# ASTRA opt-in GPU job — after separate paid-run authorization

Do not deploy or start a paid workload as part of this CPU/image preparation. The package never autostarts rendering. Preserve any live original job and its original claim/results. Use the final immutable image in IMAGE.json only after reviewing the result and authorizing the hardware run.

## Exact workload settings

| Setting | Value |
| --- | --- |
| GPU | One RTX4080SUPER16GB; existing4090/5090 compatibility remains inherited |
| Container Command override | Empty; keep inherited normal-mode startup/health service |
| User | Keep root bootstrap and inherited UID/GID1000 transition |
| Shared memory | 2GiB |
| Dropbox mount | Approved existing writable `/world-storage` |
| Port |8000, original health-only service |
| WORLD_ENGINE_STARTUP_MODE | normal |
| WORLD_ENGINE_RENDER_MODE | gpu-required |
| NVIDIA_DRIVER_CAPABILITIES | graphics,utility |
| NVIDIA_VISIBLE_DEVICES | Provider-assigned allocation; do not invent a device |

Keep the existing graphical driver/EGL/Vulkan settings and runtime setup. No extra API key or public render endpoint is introduced. The current image's API/ENTRYPOINT/health behavior and the old CLI remain unchanged; using the old CLI still selects the original material. ASTRA requires the explicit new CLI below.

## Inspect and submit one NEW ASTRA operation

In the authorized normal-mode container:

```sh
/usr/bin/python3 -B /opt/world-engine-astra-activation/job_astra.py inspect
/usr/bin/python3 -B /opt/world-engine-astra-activation/job_astra.py status
```

If a live old/new supervisor, native capture or common GPU guard exists, do not start another job. Resolve inaccessible/malformed records; historical acknowledgement cannot bypass active/unsafe evidence.

When no prior history is present, explicitly submit:

```sh
/usr/bin/python3 -B /opt/world-engine-astra-activation/job_astra.py start --confirm-new-job
```

If inspection reports retained original65422 history and the user deliberately intends this separate ASTRA operation, use:

```sh
/usr/bin/python3 -B /opt/world-engine-astra-activation/job_astra.py start --confirm-new-job --acknowledge-baseline-history
```

The history flag acknowledges a different NEW job; it never proves an old shared record is true, resumes/repeats65422, deletes a claim, or overrides live GPU work. It creates an immutable authorization bound to the ASTRA job ID. If it is interrupted before claim/fork, preserve the state for manual review; do not delete it to retry.

Wait for the persisted actual `jobId` (`astra-...`) and `supervisorIdentity` before disconnecting. If the terminal closes before acknowledgement, reconnect and use `status`; never blindly repeat a render. The manager uses the existing fork/setsid/SIGHUP-independent supervisor and one-shot state machine. Subsequent starts return retained state instead of another native invocation.

The underlying fixed native command is:

```text
/opt/world-engine-astra-activation/launch_astra.py --render-astra-65422 --vram-budget-gib 8
```

Use the manager for mobile operation. The native CLI is a foreground diagnostic/explicit execution entrypoint, not a replacement for detachment. Diagnostic startup mode never renders. No container command override is needed.

## What the selected path does

The child prepares the existing three source samples through the old CPU/cache/Scene/upload APIs into a fresh private bundle, then takes the ORIGINAL common private GPU capture lock before GPU admission. It uses unchanged source/dependency/GPU/WebGL2 tests and allocation/memory controls. The lock remains held through render/export/receipt. A fresh admission must identify the same NVIDIA backend/browser in the actual capture context. Software contexts and TEST_ONLY admissions cannot produce a successful production capture.

The ASTRA signature binds source closure, profile, bundle and activation hashes, parent staging receipt, browser/driver/allocation fingerprint. It cannot reuse the old baseline capture signature. There are150frames at1080×1920,30fps,5seconds,silent; FFmpeg flags are inherited. A source/profile changed mid-run, incomplete capture, nonzero exit, malformed receipt or bad SHA cannot become COMPLETED.

Only source support is applied. The supplied DEM and GEBCO are regional; outside them, source edges without valid neighbors and NoData use unchanged baseline. This is not full-world/full-frame high-resolution coverage. Other scenes use explicit data/source profiles and existing provider contracts, not country branches. Current pipeline remains flat EPSG4326/non-wrapping; an antimeridian-crossing camera or Globe view needs a separately validated adapter rather than silent coordinate changes.

## Exact result and Dropbox recovery

Private control: `/var/lib/world-engine-private/engine/job-astra-v1`. Shared safe ledger:

```text
/world-storage/world-engine-astra-job-v1/
  CLAIM.json
  PROFILE_AUTHORIZATION.json
  state-<sequence>-<random>.json
```

The completed `status` response's `.result` identifies the exact unique existing storage-adapter export/capture. Use that locator, not a guessed latest folder. Within its capture:

```text
EXPORT_COMPLETE.json
ASTRA_COMPLETE.json
public-review/
  WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4
  01_START.png
  02_ADVANCE.png
  03_TRACKING.png
  04_CONTINUOUS_CONTROL.png
  05_END.png
  SHA256SUMS
```

The existing MP4 basename is intentionally retained to reuse the unmodified7-file verifier and storage contract. The directory/signature and ASTRA_COMPLETE receipt identify the NEW ASTRA output; it is never an overwrite of the old video. Completion requires the original exact7-file SHA/FFprobe verification plus strict ASTRA receipt binding to this profile and capture.

Only MP4, five PNGs and SHA256SUMS may be placed in PublicReview. Keep claims/authorization, diagnostics/logs/source and both receipts outside it. Mounted export/readback is not Dropbox remote synchronization. Follow the unchanged previous Dropbox verification procedure: confirm exact remote paths, retain independent source SHA for SHA256SUMS, download all seven originals via approved direct URLs, check actualHTTP200+downloadedSHA, fully decode/play and compare on mobile. No external Dropbox sync or download has been executed by this preparation task.

## Hardware evidence still required

Verify actualNVIDIA upload/draw; visible height/surface/depth effect within supported regions; coastline/NoData seams; territory/frontier/unit preservation; unchanged camera/timeline; VRAM/frame cost; realMP4 andDropboxdownload; reference/mobile quality. Software tests do not pass any of these hardware/quality gates. Keep FINAL pending user video approval.

Detachment survives terminal loss, not container/host deletion or SIGKILL. A container restart never automatically rerenders; retained ASTRA claim vetoes replay. Missing/delayed shared history is not distributed exactly-once proof. Preserve all work and recover provider/job evidence before any retry. The3600-second native deadline does not stop provider billing; stop the authorized paid workload only after independently recovering required artifacts/logs. This task performs no paid deployment, automatic provider stop or FINAL promotion.
