# Exact remaining activation work — no protected patch applied

The new upload extension is INACTIVE. Existing GPU/WebGL2 and prior65422 video remain valid for the old renderer; they do not validate ASTRA textures/materials.

## Missing selection chain

1. `gcube-detached-render-v1/job_manager.py` pins the old storage launch and one-shot65422 job identity.
2. `rtx-gpu-package-v1/gpu_launcher.py` pins the old hardware capture.
3. `hardware_render.mjs` lexically imports `openHardwareRuntime` with no runtime-factory parameter.
4. `hardware_runtime.mjs` imports/creates the V4 adapter immediately, without a pre-pipeline material hook.
5. V4's terrain factory is private and unconditionally drawn; native DEM is disabled. A finished-frame overlay is unsafe.

Exact source/line references are permanently recorded in evidence/CONNECTION_AUDIT.json. No existing API is silently changed, TEST_ONLY runner substituted, module response rewritten or immutable source contract relaxed.

## Concrete non-destructive route

Implement a separately versioned opt-in ASTRA runtime/adapter lane under a new namespace, preserving all existing files and the original lane. Reuse the existing native GPU admission, projection/GIS factory, camera/timeline evaluators, territory/frontier/presentation/national-unit passes, encoder and Dropbox export/verifier. Add an explicit source-material factory contract before pipeline construction, rather than duplicating those engines or changing frozen V4.

The new lane needs a distinct source/material profile binding and capture signature. Its job selector must preserve the already completed65422 claim/result and prevent concurrent GPU jobs; no removal/reset of the old claim can authorize a rerun. The existing manager has no configurable production lane and cannot currently choose ASTRA. An explicit new selector/job profile is therefore required, including its integrity, once-only execution, storage and restart regressions.

Proposed new factory interface, for implementation review only (not an existing callable API):

```js
createAstraSourceMaterial({
  gl, defaultTerrain, verifiedUploadBundle,
  nativeCoverageBinding, projectionBinding, sourceProfile
}) // -> {draw({bounds,frame,fps,coverage}), outputTexture, dispose()}
```

Required unchanged composition order:

```text
native camera/GIS/coverage
→ unchanged baseline source material
→ supported ASTRA source material + explicit baseline fallback
→ territory ownership
→ existing destination terrain lighting/frontier using actual ASTRA-combined terrain texture
→ presentation
→ national-unit/flag artwork
```

The ASTRA pass must provide the combined RGB8 terrain snapshot as `outputTexture` to the existing frontier-light pass. A stale baseline texture there would sever terrain-light/territory relation. Keep global current-frame native coverage for land/ocean gating; derive fragment geographic coordinates from the same current camera bounds/projection. A same-sized unrelated Boolean array or elevation sign is insufficient. The existing coverage buffer is not itself a coindexed geographic raster.

## Data extent policy

The saved samples do not cover the whole unchanged150-frame native envelope. Partial material activation may use actual source support and unchanged baseline outside it; missing full coverage alone does not block this limited mode. It must remain visibly/evidentially partial, never labelled full-scene ASTRA. Full coverage needs bounded permitted acquisition through the existing providers/cache, including derivative guard support; no new research or acquisition was executed here.

## Gates before a new image or paid run

First validate the new lane's source/material selection and fallback, compositing order, source/profile signature, old-lane byte protection and once-only job routing on CPU. Only then build a unique free-CI image, register GHCR and independently pull/verify its closure. Preserve original images and source contract as a parent contract plus a distinct extension contract.

A separately authorized real hardware run must then verify NVIDIA uploads, actual draws, coast seams, relief/color, territory and frontier visibility, unchanged camera/time, frame cost/VRAM and full decode/reference comparison. Keep physical GPU and visual quality PENDING until actual evidence exists; user approval is still required for FINAL.

Next user action: review this prepared handoff and the explicit new runtime/adapter/job-selector scope. Keep the successful existing job/image unchanged; do not incur GPU cost merely to test files that are not selected by its runtime. Resume with that separately versioned activation lane; no supplier redownload or CPU/manager/GPU-admission redevelopment is needed.
