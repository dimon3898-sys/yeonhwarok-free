# RTX GPU execution package

This is a separate packaging layer over saved WORLD ENGINE code. It does not change a FINAL, renderer, shader, camera, territory/frontier evaluator, icon, timing, data source or public renderer API. It does not activate new ASTRA GPU materials. Physical hardware and video quality remain unverified until a later authorized run.

Parent source: CPU `a002d89492734bfa9d17b98145ee6cb9a3b366a2`, glow `45af879d7417abba58e9ebd59d8e6630a785ac28`, Phase A `21036824888dffbe232934d0332420c5910b98a4`. CPU already contains the unchanged glow and Phase A sources. No branch merge is required.

## Build preparation

From the repository root, using the recorded package commit:

```sh
python3 -B world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/prepare_context.py --destination /tmp/world-engine-rtx-context
docker build --platform linux/amd64 \
  -f /tmp/world-engine-rtx-context/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/Dockerfile \
  -t world-engine-rtx-package:review-unique-tag /tmp/world-engine-rtx-context
```

Use a new unused tag. Neither preparation nor this package pushes an image, changes the old GHCR image, deploys gCube or runs a paid job. Before a future push, inspect the built dependency report and source receipt and record the new registry digest. **No new image digest is claimed in this submission.**

The context includes only the 140 explicitly pinned original files and the explicit new overlay in `package_overlay.json`. Sources retain their canonical paths under `/opt/rtx-package/repo`; the image does not fetch or merge source branches at startup. Original-file commit/blob, SHA and size verification runs before staging. Runtime startup checks the staged source and overlay bytes again without Git or networking.

## Hardware admission

`bootstrap.py` preserves provider device groups and drops to the engine account. `gpu_launcher.py` requires one supported physical NVIDIA allocation: RTX 4080 SUPER with at least 15 GiB reported memory, or RTX 4090/5090. It records actual model, UUID, driver and VRAM, checks free-memory/shared-memory limits, reuses the existing graphics-profile preparation and native WebGL2 draw/readPixels probe, and rejects software rendering. Default startup exposes sanitized `GET /healthz` only; it does not render automatically.

The separate Node bootstrap uses the original renderer factories and the same saved scene, camera, geometry, diagnostics and encoder arguments. It requires a fresh private admission and the same actual NVIDIA backend/browser profile. The old SwiftShader launcher is preserved and inactive here.

An explicit later `--render-65422` command captures the existing 150-frame scene into a **new** persistent directory. It cannot overwrite the original Candidate. It binds resumable PNG/row caches to staged source bytes, browser, driver, model and GPU fingerprint, performs a fresh hardware draw even on a complete cache hit, and preserves a verified completed new MP4 instead of encoding it again. Public review holds MP4/PNG/SHA256SUMS only; private diagnostics stay outside it.

The 8 GiB default budget is a monitored increase from admission usage, with a 2 GiB free reserve. NVIDIA consumer drivers do not provide a per-process VRAM reservation through this launcher. Polling can stop an observed over-budget run; it is not a hard allocation cap.

See `GCUBE_EXECUTION.md`, `DEPENDENCY_VALIDATION.md`, `GPU_HARDWARE_VALIDATION_TODO.md`, `RTX_PACKAGE_REPORT.md` and the persisted evidence for exact checks and remaining limitations.
