# User-authorized hardware validation of Reference Visual V2

This procedure is prepared for the next user-approved run. This task does not deploy gCube, start a paid GPU, or approve video quality. Build, registration and independent digest pull passed in run38831714161. Preserve all old images, jobs, claims and videos.

Image tag (use if the gCube image form requires a tag):

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:reference-v2-233bca7-38831714161-1
```

Immutable image for environments accepting digest references:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5
```

`IMAGE.json` records source commit `e9feafc785fbd138cbac3ca4db090380968dc37e`, platform linux/amd64 and the actual source-manifest hash. Later report-only commits do not imply another built image.

Required settings retain the existing working package:

- RTX4080SUPER16GB; shared memory2GiB.
- Existing Dropbox mount at `/world-storage`; retain the original port8000 normal health service.
- Leave container Command override empty. Keep `WORLD_ENGINE_STARTUP_MODE=normal` and `WORLD_ENGINE_RENDER_MODE=gpu-required`.
- Keep `NVIDIA_DRIVER_CAPABILITIES=graphics,utility`, provider-assigned `NVIDIA_VISIBLE_DEVICES`, and the previously validated driver/graphics settings. No new token or public render endpoint is needed.
- Keep the inherited bootstrap/UID1000 transition and hardware Chromium wrapper. Diagnostic mode cannot render; SwiftShader is rejected by production admission.

After the user approves deployment, inspect the new lane:

```sh
/usr/bin/python3 -B /opt/world-engine-reference-v2/job_ref2.py inspect
/usr/bin/python3 -B /opt/world-engine-reference-v2/job_ref2.py status
```

Only after inspection and authorization for this new operation:

```sh
/usr/bin/python3 -B /opt/world-engine-reference-v2/job_ref2.py start --confirm-new-job
```

If retained baseline history is reported and this distinct operation is intended, explicitly acknowledge that history:

```sh
/usr/bin/python3 -B /opt/world-engine-reference-v2/job_ref2.py start --confirm-new-job --acknowledge-baseline-history
```

This acknowledgement cannot override an active original65422, ASTRA, Quality or V2 supervisor/capture; the original common GPU lease; unsafe paths; malformed state; or hardware admission failure. Do not delete/reset old claims to retry. The new job ID starts `reference-v2-65422-`; private state is `/var/lib/world-engine-private/engine/job-reference-v2-v1`, and the shared control namespace is `/world-storage/world-engine-reference-v2-job-v1`.

Wait for the actual job ID and supervisor identity. If the mobile terminal disconnects before the response, reconnect and query `status` rather than starting blindly. The inherited detached supervisor survives terminal hangup. Container stop/restart can kill it; no automatic rerender, resume of frames, shutdown or billing-stop guarantee is introduced.

## Verify the actual GPU result

Production accepts only `REFERENCE_VISUAL_MASTER_V2_F`. The inherited controller verifies source/dependency contracts, available GPU/shared memory and a fresh NVIDIA WebGL2 admission before capture. Original encoding and export verification remain in place. A–E and the software tools are test-only variants.

Use completed status `.result` to locate its unique export and capture directory. Do not assume a fixed media folder or reuse an old success receipt. The existing seven-file verifier intentionally retains these names inside the **new, distinct** `public-review` directory:

```text
WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4
01_START.png
02_ADVANCE.png
03_TRACKING.png
04_CONTINUOUS_CONTROL.png
05_END.png
SHA256SUMS
```

Keep `ASTRA_COMPLETE.json`, native completion receipts, source/manifest data and diagnostic logs outside Public Review. Confirm the receipt's new profile ID and capture/source signature. Verify150frames,1080×1920,30fps,5seconds and no audio; fully decode/play the MP4; check each original file against SHA256SUMS. File existence alone is not completion or visual approval.

Mounted Dropbox write/readback is distinct from remote synchronization. Before stopping the container, confirm the remote Dropbox folder, create approved direct links to only MP4/PNG/SHA256SUMS, download through those external URLs, require actual HTTP200 and compare downloaded SHA-256 to the original source. Never re-encode the MP4 to provide it. Review on a phone. This task has not claimed a new GPU output, Dropbox synchronization or external MP4 download.

Hardware review must confirm supported-data seams and NoData, actual land/ocean alignment, visible cumulative territorial gain, white moving front on its true ownership boundary, distinct gold outer boundary, unit/flag readability, camera cadence, GPU memory/performance and the reference comparison. Existing F already crops inactive domain vertices; V2 adds none and protects the active front and all units. It does not claim whole-country visibility on every frame.

Compare the same event phase from the actual reference (approximately5.181813–10.181813s), excluding phone UI. The actual GPU F video is not available in this task; saved F software pixels provide engineering regression only. Do not call software PNGs NVIDIA footage or promote FINAL before the actual new video is inspected and approved.
