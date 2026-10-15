# Separate authorized GPU validation of visual quality F

This document prepares the next run. It does not authorize or perform paid deployment. Preserve the original ASTRA image/jobs/videos and use only the new immutable image in IMAGE.json after the user approves the hardware run.

Settings: RTX4080SUPER16GB, shared memory2GiB, existing Dropbox mount `/world-storage`, original port8000 health service, original root bootstrap/UID1000 transition. Leave container Command override empty. Keep `WORLD_ENGINE_STARTUP_MODE=normal`, `WORLD_ENGINE_RENDER_MODE=gpu-required`, `NVIDIA_DRIVER_CAPABILITIES=graphics,utility` and provider-assigned `NVIDIA_VISIBLE_DEVICES`/existing graphics driver settings. No new token or public render API is required.

The old CLI still selects old behavior. To select the new lane, inspect through the terminal:

```sh
/usr/bin/python3 -B /opt/world-engine-visual-quality/job_quality.py inspect
/usr/bin/python3 -B /opt/world-engine-visual-quality/job_quality.py status
```

Start only after inspection and explicit approval for this NEW operation:

```sh
/usr/bin/python3 -B /opt/world-engine-visual-quality/job_quality.py start --confirm-new-job
```

If retained original65422 or ASTRA history is reported and this distinct operation is intended, use the existing explicit history acknowledgement:

```sh
/usr/bin/python3 -B /opt/world-engine-visual-quality/job_quality.py start --confirm-new-job --acknowledge-baseline-history
```

The flag cannot override active old/new supervisors, native capture, the common GPU lock, unsafe paths or malformed records. Do not delete claims to retry. Wait for the persisted `quality-...` job ID and actual supervisor identity. If connection drops before acknowledgement, reconnect and query status rather than blindly starting again. The inherited detached supervisor survives terminal hangup; container stop/restart can still kill it, and no automatic rerender or billing-stop guarantee is made.

The new private/shared profile locations are `/var/lib/world-engine-private/engine/job-quality-v1` and `/world-storage/world-engine-quality-job-v1`. Original65422/ASTRA locations are unchanged. Production accepts only integrated profile F; A–E are explicit software comparison variants. Native GPU admission and the original common guard remain mandatory. Diagnostic startup mode cannot render.

Use completed status `.result` to locate the unique export. Keep both receipts and diagnostic logs outside `public-review`. Inside public-review retain only the original MP4 basename `WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4`, five existing checkpoint PNG names and SHA256SUMS. The basename is intentionally reused within a DISTINCT capture directory to retain the original seven-file verifier. The profile ID `VISUAL_QUALITY_UPGRADE_V1_F` and signature identify the new result; do not overwrite or confuse the old video.

Verify150frames,1080×1920,30fps,5seconds,silent; decode/play the whole output; verify source/PNG hashes and the F receipt. Mounted Dropbox readback is not remote synchronization. Confirm remote paths, download original MP4/PNGs/SHA256SUMS by approved direct URLs, check actual HTTP200 and downloaded/source SHA equality, and review on a mobile screen. No remote synchronization/download is claimed by the current CPU/image task.

Hardware review must assess natural source boundaries, no coast blur, territory change comprehension, true frontier alignment, camera priority/rhythm, units/flags, NoData/fallback, performance/VRAM, and comparison with the reference. Software A/B PNGs are supporting engineering evidence, not NVIDIA footage or final user approval. Do not promote FINAL before the user approves the actual GPU video.

Verified candidate image tag for the gCube image field:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:visual-v1-a7df81f-38821837659-1
```

Immutable reference for digest-aware tools:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:92698c51b718a051c9ccf48fc31c2755962038854119f5b572d5ce11e72086ae
```

Build and independent digest pull succeeded. No live gCube account pull/deployment was performed in this task.
