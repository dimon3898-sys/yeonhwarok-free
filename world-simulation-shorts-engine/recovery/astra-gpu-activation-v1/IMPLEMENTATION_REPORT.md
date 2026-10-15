# ASTRA selected material runtime — implementation and handoff

This is an independent, opt-in execution package for actual ASTRA source material selection before territory/frontier compositing. It preserves the original V4 and old65422 execution lane. Physical NVIDIA execution, paid deployment, actual Dropbox remote synchronization/download and video quality are not verified by this task. See IMAGE.json and the final successful run records for the exact published image and verification status; earlier failed run records are intentionally retained.

## Existing state and completed connection

| Component | Prior state | Work performed |
| --- | --- | --- |
| ASTRA source catalog, original samples, parsing/cache/Scene helpers | Implemented in a002d894 | Reused; no supplier research or downloads, no repeated24-member archive audit |
| Verified raw-value GPU upload contract | Implemented in711b232; inactive in original render lane | Reused unchanged; selected by the new source material |
| Original V4 pipeline | Complete, frozen; source factory private | Reused through a standard browser import map and a per-canvas material decorator; no V4 copy or file modification |
| Actual height/surface/depth material | Missing | New supported-source compositing pass with native same-frame GIS coverage and baseline fallback |
| Native admission, controls, encoder and storage | Complete | Reused unchanged; new orchestration selects the separate runtime |
| Detached manager | Complete for original one-shot65422 | Reused as isolated pinned module instances with a separate ASTRA job identity and common GPU lock |
| NVIDIA texture/draw and visible result | Only original lane previously verified | New lane remains pending an explicitly authorized real hardware run |

Protected source baseline:711b232265aefb1f0f4e368673f7943d86cf03b0. CPU:a002d89492734bfa9d17b98145ee6cb9a3b366a2. Original GPU package:2f9158ba2df2a9f58362fb0b17118b8dc19f705a. Detached manager:5269521131059cacdd18de5110ee3aaae302b8b5. The previous upload activation contract is preserved; this new namespace implements its remaining selection chain.

## Actual selected path

```text
explicit new job_astra CLI + immutable profile authorization
→ reused detached supervisor/one-shot state
→ launch_astra, ORIGINAL common GPU capture guard
→ original source/dependency/NVIDIA/WebGL2 admission and memory controls
→ existing CPU providers/cache/Scene + unchanged upload exporter
→ capture_astra + fresh NVIDIA-bound astra_runtime
→ original V4 adapter with a standard exact import-map material selection
→ original encoder, ffprobe, export/readback verification
→ original7-file completion plus ASTRA_COMPLETE attestation
```

The browser import map selects `astra_material.mjs` only for the original terrain-factory module's exact URL. Its decorator imports the original module through a query-qualified URL and calls the unchanged original factory. The original adapter, camera, control-plan compiler, area evaluator, territory pass, frontier pass, presentation and national-unit artwork remain the original source modules. No source-response rewriting or complete V4 duplication is used.

Composition order is enforced at the source texture boundary:

```text
native camera/GIS/coverage
→ original baseline material
→ supported ASTRA surface + height-based relief light + signed bathymetry color
→ original territory ownership
→ original terrain lighting/frontier, sampling the ASTRA-combined RGB8 outputTexture
→ original presentation
→ original flags/units
```

ASTRA is not a finished-frame overlay. The actual material output is the texture consumed by the original subsequent stages. Neither the old native CLI nor the normal-mode service automatically selects ASTRA; the explicit new profile does.

## Numerical and geographic handling

Original Float32 DEM, signed Int16 bathymetry and surface RGBA bytes are passed through the existing upload contract without quantizing/replacing NoData. Separate validity masks control application. DEM relief requires the center and all four finite-difference neighbors to be valid; metre spacing incorporates latitude, transform and row direction. Negative elevation does not establish ocean: bathymetry is gated by the original current-frame fractional GIS ocean coverage. Every source is mapped from the same current camera bounds and its actual source transform/pixel centers. Source-edge and unsupported locations use the original material.

The sample bundle contains32,115,808 artifact bytes. Its deterministic manifest SHA256 is `02495857b20e92b75c5e4f9d60090e2e959b82c677053ef068024a7d5c63261f`. Regional samples do not cover the whole saved camera envelope. This is partial supported-source activation, not full-frame/global detailed data coverage. Provider replacement remains generic and data/profile based; the saved numeric scene extent belongs to a fixture rather than country/era branches.

Height currently affects finite-difference normal illumination and bounded altitude tone; it does not displace a terrain mesh. Original source vertical metadata is retained; no unsupported common vertical-datum correction is invented. BlueMarble encoded colors are retained; this is a visual material combination, not a radiometric calibration. The selected native view is flat EPSG4326/non-wrapping. Other projections or antimeridian-crossing camera bounds require a separately verified adapter, not silent interpolation or camera changes.

## New files and reasons

All implementation is additive under `recovery/astra-gpu-activation-v1`, plus one new workflow.

| Files | Purpose |
| --- | --- |
| astra_material_core.mjs, astra_material.mjs | Bounded profile, coordinates/validity, actual WebGL2 material draw and original-factory decorator |
| astra_adapter.mjs, astra_runtime.mjs, serve_astra.py | Select and bind the new material before pipeline construction; exact loopback-only static runtime, source hashes, canonical original Scene transport |
| SCENE_MAP_DATA.json, prepare_activation.py | Optional data profile, original CPU/upload pipeline preparation, strict separate extension manifest |
| capture_astra.mjs, launch_astra.py | New NVIDIA-required native capture, common guard, original encoder/export with strict ASTRA attestation |
| job_astra.py | Separate persistent ASTRA identity, history authorization and reused detached/one-shot mechanics |
| tests/ | Focused source/material/projection/manager/launch/export/CI regressions |
| software_probe.mjs | Explicit test-only real Chromium SwiftShader compile/draw/readback and pixel A/B; cannot satisfy production admission |
| Dockerfile, ci.py, .github/workflows/astra-gpu-activation.yml | Exact additive image layer, free public standard CPU CI, unique GHCR tag and independent digest pull |
| Manifests, reports, run records and SHA256SUMS | Permanent source/image/validation and recovery evidence |

No original FINAL, renderer, shader, camera, territory speed, frontier, flag/unit, old manager, public API, source contract, encoder or storage-adapter file is modified. No old job claim/result/image is deleted or overwritten. The original normal-mode ENTRYPOINT and health behavior are inherited unchanged.

## Focused validation and recovery

The new tests cover raw source/mask/row/half-pixel preservation; true native coverage; fallback and failed-draw cleanup; immutable profile/source bindings; loopback/CSP/Host isolation; production rejection of TEST_ONLY admission; actual common flock; allocation/deadline/native-failure handling; original export+SHA/receipt verification; detached PTY disconnect; concurrent/repeated starts; preserved old claims; lost worker with no auto-rerun; unsafe records; and explicit history authorization bound to the new job.

The actual software probe launches Chromium, compiles the actual shader, uploads the real prepared sample bundle, executes the original pipeline at frames0/75/149 and reads pixels. Its ASTRA versus zero-mix A/B requires different raw pixels with equal camera and geometry. It requires SwiftShader and labels every result test-only, physicalNvidiaExecuted=false, productionRenderAllowed=false. This establishes executable material selection/composition, not NVIDIA or visual-quality approval. It is not an encoded public video proof.

Confirmed new-path failures were corrected without editing protected engines:

1. CPU Chromium inherited `/root` HOME after UID1000 transition. The CPU probe now uses the actual engine account home and private Chromium config/cache. No production GPU flags were changed.
2. The new server recursively sorted runtime JSON keys, conflicting with the original control-intent compiler's canonical order. It now preserves the saved Scene object's key order; a real HTTP-to-original-compiler regression verifies150frames/30fps.
3. The original exact image inventory rejected legitimate additive ASTRA files. The new CI now verifies a strict union of the original protected inventory and explicit hash-pinned additions; original inventory/code/source contracts remain unchanged. Final run evidence records the implemented correction and rejects unknown extra files.

Each failure stopped image publication. Source and failed-run evidence were remotely checkpointed before continuing. The prior8/104/233-test suites and supplier audits were not unnecessarily repeated. Final run records distinguish focused tests, software draw, actual image checks, secret scan and independent pull. Unexecuted real-GPU/Dropbox/visual checks remain pending.

## Hardware handoff

Use [GCUBE_EXECUTION.md](GCUBE_EXECUTION.md) only after the user separately authorizes paid execution. The image defaults to the existing normal-mode health service, with no automatic render and no public render API. Run `job_astra.py inspect` and `status`, then explicitly start the new ASTRA job. Existing history requires a deliberate acknowledgement; it cannot bypass live/unsafe evidence or the common capture guard. Keep the persisted job ID before closing the terminal. No restart automatically rerenders.

The new output is150frames,1080×1920,30fps,5seconds,silent, with five original checkpoint names and SHA256SUMS. The original MP4 basename is retained inside a distinct capture/export to reuse the original exact verifier. The ASTRA profile/capture receipts distinguish it from the old video; they stay outside PublicReview. Actual Dropbox synchronization, directHTTP200 and downloadedSHA equality must be checked after the authorized real run.

Required hardware checks: NVIDIA upload/draw and same backend; visible supported-region height/surface/depth effect; coastline/NoData edges; territory/frontier/flags/units preservation; identical camera/timeline; VRAM/shared-memory/frame performance; full MP4 decode; Dropbox remote download/SHA; reference/mobile visual review. No FINAL or video-quality PASS is granted here.

The original archive/data, provider code, native assets and build/reproduction recipes are persisted in the pinned parent and repository. Derived private bundles are regenerated by the tested recipe. Required temp-only source/asset/recipe files:0. The task does not delete existing caches, images, volumes, jobs or saved videos.
