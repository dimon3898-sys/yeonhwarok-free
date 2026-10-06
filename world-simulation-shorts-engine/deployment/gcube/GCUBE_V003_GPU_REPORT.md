# GCUBE v003 — NVIDIA WebGL admission and diagnostics

This release changes only the gcube GPU/browser/container deployment adapter. The approved engine, scene planner, mobile generation UI, owner authentication, renderers, GIS/assets, scenes, cache/checkpoint semantics, and existing videos remain intact. No 75/80-second render or new video render is part of this release.

## Actual evidence and limits

The user reports that gcube-v002 pulls and starts successfully on RTX 3070 ×1 / 8 GB, CPU 12 cores, RAM 16 GB, port 8000, Istio ON, 1 GB shared memory and explicit ephemeral `/data` storage. The status page returns `GPU_WEBGL_UNVERIFIED`. In the shipped v002 code, `GPU_WEBGL_UNVERIFIED` is reached after a valid NVIDIA query and browser-probe response, at the WebGL admission check. It therefore narrows the failure to context/renderer/draw verification; it does not identify the actual EGL/Vulkan backend or prove which provider library is missing. This is not a deployment-schema failure or a successful GPU draw.

The original v002 error did not retain individual browser attempts and raw renderer identity in its safe user-facing status. The exact provider-side failed graphics stage cannot be inferred from that error alone. v003 must show actual, bounded diagnostics so the next gcube test identifies hardware visibility, nvidia-smi, browser launch, WebGL context, NVIDIA identity and test-draw outcomes separately.

The Codex and GitHub Actions runners used here have no NVIDIA GPU. Their actual Chromium/CPU test draw verifies browser availability, software renderer rejection and fail-closed behavior only. It does not certify an RTX 3070 draw, render acceleration, gcube cost or actual provider driver/library injection.

## Admission rules retained

- Default gcube render mode is GPU-required; no automatic CPU fallback.
- `nvidia-smi` and GPU visibility alone cannot make the engine READY.
- Real WebGL2 context, unmasked renderer identity, successful shader draw/readback and no GL error are required.
- SwiftShader, llvmpipe, softpipe, lavapipe and other software rasterizers cannot pass NVIDIA admission.
- Host NVIDIA kernel drivers are not installed in the application image.
- Diagnostic liveness on port 8000 is not engine readiness; `/readyz` stays 503 while admission fails.
- Failed admission starts no render, and the status page tells the user to stop the gcube workload to avoid idle billing.
- Owner-code, arbitrary environment values and private project paths are not included in public diagnostics.

## Graphics changes in v003

The hardware EGL profile is retained as the first bounded attempt. If it cannot prove a NVIDIA draw, the second bounded attempt uses Chromium's documented native Vulkan headless flags: `--enable-features=Vulkan`, `--use-vulkan=native`, and `--disable-vulkan-surface`, alongside the existing ANGLE/Vulkan selection. The v002 fallback did not include this complete native Vulkan recipe. Unrelated Chromium feature lists are merged and retained.

The wrapper removes caller-supplied GPU/WebGL disabling flags in GPU-required mode as defensive handling. The pinned Playwright defaults did not contain `--disable-gpu` or `--disable-gpu-compositing`, so these flags are not asserted as the actual gcube root cause. No Xvfb, kernel-driver installation, guessed driver version or forced-PASS override is added.

The image adds neutral GLES/OpenGL loader packages (`libgles2`, `libopengl0`). If a provider-mounted NVIDIA driver is actually loadable with the required EGL/Vulkan entrypoint but its loader descriptor is missing, startup can create a private descriptor for that existing driver. Valid provider descriptors are retained. Vulkan API version is read from the loaded ICD rather than guessed. No driver is downloaded/installed and no GPU identity or successful draw is inferred from this repair.

The startup probe retains masked/unmasked vendor and renderer, actual red-pixel readback, WebGL2 and GL error, selected backend and the individual A–F outcomes. NVIDIA identity must match a visible physical GPU model; successful context creation or a synthetic `draw_passed` flag alone is insufficient. Runtime inventory records only fixed known library/driver-manifest booleans, device counts and environment selection classifications; no GPU UUID, raw environment, owner-code, private path or stderr is exposed.

The owner-authenticated diagnostic routes are `/api/gcube/gpu`, `/gcube/gpu.json` and `/gcube/gpu`. When GPU startup is blocked before login, the root status page shows the safe failed stage/renderer/backend/reason and Stop-workload guidance; readiness remains false and mutations remain blocked.

The same verified backend is carried into later browser launches. CPU validation is selected explicitly only by the test harness. No generated video or old renderer is altered by startup validation.

## gcube inputs

Only the image changes to `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v003`. Keep Registry GitHub, port 8000, blank command, RTX 3070, current CPU/RAM/disk, Istio ON, 1 GB shared memory, no minimum CUDA version and the existing test settings:

| Environment name | Value |
| --- | --- |
| `WORLD_ENGINE_OWNER_CODE` | Existing private owner-code, never stored in the image/report |
| `WORLD_ENGINE_STORAGE_MODE` | `ephemeral` |
| `WORLD_ENGINE_STORAGE_PATH` | `/data` |

Ephemeral storage is for this short test; removing the workload can lose its files. It is not persistent production storage.

## Immutable previous releases

Before publication, anonymous GHCR metadata requests returned HTTP 200 and confirmed:

| Tag | Unchanged digest |
| --- | --- |
| `gcube-v001` | `sha256:207a3058986f7ef0e46a7eaa95422833438b23ff3123c5daea1140a80031a3f2` |
| `gcube-v002` | `sha256:92b72a9e87625502d16a300b4831c8a206d8b58e44c414f74e28f0fa46574a8c` |

The v003 workflow publishes only the v003 stable tag and its source-SHA tag. It never pushes either old release tag.

## Official implementation references

- [Chromium: hardware GPU in headless Chrome](https://github.com/chromium/chromium/blob/main/docs/gpu/using-gpu-hardware-in-headless-chrome.md)
- [Chromium: server-side headless Linux Chrome with GPUs](https://github.com/chromium/chromium/blob/main/docs/gpu/server-side-headless-linux-chrome-with-gpus.md)
- [NVIDIA Container Runtime driver capabilities](https://github.com/NVIDIA/nvidia-container-runtime#nvidia_driver_capabilities): `graphics` supplies OpenGL/Vulkan; `utility` supplies NVML/nvidia-smi. A working query alone does not prove graphics injection.
- [GLVND EGL vendor enumeration](https://github.com/NVIDIA/libglvnd/blob/master/src/EGL/icd_enumeration.md)
- [Vulkan loader/driver interface](https://github.com/KhronosGroup/Vulkan-Loader/blob/main/docs/LoaderDriverInterface.md)

The deployment retains `NVIDIA_DRIVER_CAPABILITIES=graphics,utility`. Neutral Debian GL/EGL/GLES/OpenGL/Vulkan loader packages are image dependencies; NVIDIA vendor drivers/manifests are host-runtime delivery, not packaged kernel drivers.
