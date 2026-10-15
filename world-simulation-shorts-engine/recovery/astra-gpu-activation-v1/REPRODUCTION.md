# Reproduce the additive ASTRA package

Use the source commit and immutable image recorded in IMAGE.json. Preserve the original protected baseline711b232 and parent-image digest. No data re-acquisition or parent rebuild is needed. CI uses a public standard ubuntu24.04 CPU runner, a20GiB free-Docker-space gate and the existing pinned parent image; it never selects a GPU or larger paid runner and never prunes old images/caches/volumes.

## Exact files and image layer

The new Dockerfile layers the10explicit runtime files, ACTIVATION_FILES.json, the test-only software probe and the two unchanged prior upload files onto the immutable parent. It introduces no new system/npm/pip dependencies, API change or alternate default ENTRYPOINT. GDAL/NetCDF/Pillow/NumPy, Playwright/Chromium, FFmpeg and native graphics libraries are inherited. Runtime files are read-only. The separate private job directory is owned by UID/GID1000.

ACTIVATION_FILES.json is copied verbatim from the successful run's activationManifest JSON serialization. It binds sourceCommit, original baseline, parent image, new runtime SHA256, the unchanged prior upload files and11inherited runtime helpers. The original staged160-file source contract remains intact. SHA256SUMS binds this namespace and its new workflow; it excludes only itself and transient Python bytecode.

The workflow in `.github/workflows/astra-gpu-activation.yml` executes the new ci.py phases:

```text
preflight → unique-tag absence guard → focused tests and actual software draw
→ explicit context stage → additive Docker build
→ exact protected/additive inventory and source verification
→ actual-image software draw and read-only new CLI
→ secret scan → unique-tag recheck/publish
→ separate runner immutable digest pull and source verification
→ bounded remote evidence persistence
```

A failed required phase blocks publication. Every retry follows a recorded confirmed correction. Old failed run records are retained, with source IDs and reason codes. Branch/unique-tag protection prevents overwriting original images. Credentials remain in the ephemeral CI authorization/configuration; they are neither image files nor repository records.

## CPU tests

On a machine with the inherited Python/Node dependencies, from the repository root:

```sh
/usr/bin/python3 -B -m unittest discover -s world-simulation-shorts-engine/recovery/astra-gpu-activation-v1/tests -p 'test_*.py' -v
node --test --test-isolation=none world-simulation-shorts-engine/recovery/astra-gpu-activation-v1/tests/test_capture.mjs world-simulation-shorts-engine/recovery/astra-gpu-activation-v1/tests/test_material.mjs world-simulation-shorts-engine/recovery/astra-gpu-activation-v1/tests/test_runtime_plan.mjs
```

The ci.py test phase performs these new suites inside the immutable parent with only the new namespace and the pinned upload dependencies mounted read-only. It runs as UID/GID1000, with network disabled and bounded memory/process/shared-memory resources. This avoids dependence on this development machine's browser or default Python. Test fixtures that encode150synthetic frames are CPU lifecycle/storage checks, not a public video or GPU evidence.

The actual software probe uses real Chromium GLSL/WebGL2 compile, draw and pixel readback at frames0/75/149, and a frame0ASTRA/zero-mix comparison. It explicitly requires SwiftShader and marks the results test-only. It checks source immutability, selection, raw pixel difference, equal camera/geometry, same-frame native coverage and the combined texture. Its safe Chromium home/config/cache are scoped to the CPU probe. Production code cannot accept its TEST_ONLY admission or renderer.

## Source preparation

The original persisted sample archive/catalog, license/provenance evidence, existing CPU providers/cache/Scene handling and original upload exporter produce the activation bundle. No supplier network request is required. The full saved camera envelope requests actual overlap only; unsupported coverage remains explicit. Runtime preparation derives raw source artifacts and validity masks rather than baking GPU-specific approximations into the repository.

The deterministic bundle manifest SHA256 is `02495857b20e92b75c5e4f9d60090e2e959b82c677053ef068024a7d5c63261f`; artifact bytes32,115,808. Activation-file SHA includes private absolute paths and can differ between runs; the manifest/data values remain bound. Runtime asserts the original saved Scene byte SHA and source closure before and after capture. It does not edit original Scene JSON, camera or control-intent key order.

## Real GPU execution is separate

Follow GCUBE_EXECUTION.md after separate user authorization. It supplies exact settings and explicit manager commands, state/claim handling, output locators and Dropbox verification. Normal-mode startup never automatically runs ASTRA. Do not replace the container command with the CPU test probe or use software WebGL as NVIDIA admission.

The real capture reuses native GPU admission, budget/allocation checks, source guard and the original encoder/export verifier. All150production frames must record actual ASTRA material selection and intact original protected diagnostics. Strict ASTRA completion and original SHA/ffprobe receipts are both required. A partial file or mere process exit cannot become a completed ASTRA result.

No actual NVIDIA render, new MP4, paid run, gCube configuration change, external Dropbox sync/download or visual-quality approval is performed by this preparation task. These remain explicit next-run checks, rather than implied by image construction or software tests.
