# Additive change manifest

Baseline: `b0d013832ee38571f9d3dfe685ce63f7083ba90f`. All additions are inside `world-simulation-shorts-engine/recovery/universal-presentation-v2/`. At the documentation checkpoint, `git diff --name-only b0d0138` excluding this namespace was empty. Existing G1/G2/data-pipeline code, renderers, shaders, Camera/Area/Flow/Event owners, FINAL, prior scenes/assets/videos, claims and caches were not edited or deleted. The original 307 protected SHA identities, all 6,439 baseline tracked-file hashes and 565 existing cache metadata entries have separate protection evidence in `reports/PROTECTION_*.json`; the final delivery report records the last check.

## Added execution files and exact dispatch

| New file | Responsibility and actual dispatch |
|---|---|
| [presentation_prompt.mjs](presentation_prompt.mjs#L257) | `analyzePresentationPrompt` accepts the versioned text-plus-data envelope, extracts bounded intent, retains unchanged data-validator failures, qualifies the real source, then calls unchanged `validateFactDataset`, `compileScenePlan`, `validateScenePlan` and `compileExistingEnginePlan`. It emits native Scenes plus explicit presentation/region sidecars and input/source hashes. |
| [region_source.mjs](region_source.mjs#L128) | `qualifyRegion` checks actual source bytes/license/SHA, GIS identities, coordinates and requested coverage. `resolveRegionPlan` reuses existing Scale/native GIS/V5 camera owners. `prepareRegionTerrain` chooses one actual source for the whole camera envelope and produces a verified native-pixel crop. `verifyRegionQualification` rejects changed receipts/crops. |
| [REGION_SOURCE_CATALOG.json](REGION_SOURCE_CATALOG.json), [REGION_REQUEST_SCHEMA.json](REGION_REQUEST_SCHEMA.json) | Versioned source/coverage/license receipts and coordinate-region shape. No renderer edit is needed for a new supported coordinate extent. |
| [presentation_plan.mjs](presentation_plan.mjs#L23) | Validates consumed sidecar fields; compiles existing reference-camera tracks; preserves public Area operation semantics; verifies explicit scene continuity; bridges existing Flow timing to the actual current projection with safety checks. |
| [presentation_runtime.mjs](presentation_runtime.mjs#L25) | `createPresentationRuntime` calls the unchanged native map factory and existing Area/Flow/marker passes. Each frame updates the actual factory camera, checks source/layout/coordinate safety, evaluates original geographic events and checks real draw/readPixels results. |
| [capture_presentation.mjs](capture_presentation.mjs#L48) | Prepares all source/camera segments before execution, verifies immutable wire/qualification hashes, opens loopback-only Chromium/SwiftShader, switches actual runtime at exact CUT frames, streams frames to existing FFmpeg and records frame/media receipts. |
| [studio_adapter.py](studio_adapter.py#L153) | New `StudioController` subclasses the existing manager in an isolated imported instance. `_normal` dispatches `WORLD_ENGINE_PRESENTATION_STUDIO_REQUEST_V2` through the new compiler; `__timeline__` requires every contiguous segment. Existing owner authentication, CSRF/Origin protection, consent, claim and detached launch are reused. |
| [software_worker.py](software_worker.py) | Verifies the accepted package, original/runtime wire hashes, source seals and execution scope; dispatches `capture_presentation.mjs`; retains bounded failure/cleanup handling; independently ffprobes and fully decodes the result before completion. |
| [run_studio_demos.py](run_studio_demos.py) | Checks A–E gates and protection first, then reuses the preserved mobile HTTP runner for authenticated validation/consent/start/status, disconnect/reconnect and exclusive result export. This exercises the Studio service path. |
| [PRESENTATION_PROMPT.schema.json](PRESENTATION_PROMPT.schema.json) | New self-contained structural envelope schema; existing facts definitions are reused with their original schema hash. Semantic/source/render gates remain separate. |

## Feature-to-pixel consumers

| Requested feature | Connected consumer and retained owner |
|---|---|
| Camera move / zoom / route follow | `compilePresentationCameraPlan` → unchanged `reference_camera_adapter_v1.mjs` / Camera V5 → runtime `factory.updateCamera`. Follow positions come from the supplied route and unchanged Flow fractions. The moving camera is never falsely reported locked. |
| Territory color / expansion / contraction | Supplied native Scene states → unchanged Area V3 evaluation → existing `createAreaOverlayPass`; palette changes fill RGBA only. No territory geometry or historical ownership is invented. |
| Already-visible provided state at a cut | Explicit `initialStateVisibility:PRESERVE_PROVIDED` → public `compileAreaPlan` reveal/front operation endpoints `[1,1]`, after matching-boundary validation. Source state order, geometry and world clock are unchanged. |
| Route / object / arrival animation | Existing Flow V2 event timing and fractions → current-projection primitive → unchanged Flow graphic pass, with full route/object/pulse footprint admission. Old fixed-model readiness is not misrepresented as moving-camera Event admission. |
| Location / event emphasis | Explicit supplied location ID and local frame window → pulse of the existing native marker design at that geographic anchor. Labels and event facts are not synthesized. |
| Time and scene transitions | Original half-open frame intervals and native state timing → actual per-frame segment selection. Only exact hard CUT boundaries are implemented. |

## Supporting additions

`examples/`, `evidence/` and their preparation/audit tools contain authored nonhistorical inputs, two previously unregistered regions, negative inputs and the retained limited historical cases. Corrections to authored wrapper/context fields have before-byte archives and provenance. Historical facts/geometry are retained without an expanded accuracy claim. Tests and `reports/` record the actual previous 298-test rerun, new focused checks, source/frame evidence and attempted failures. `tools/protection.py` verifies the original baseline without rewriting it. Public review/export tools copy only approved result artifacts. Documentation defines the actual contract, source credits and explicit limitations; it does not replace missing execution evidence.

## Scope and remaining limits

- This is bounded Korean/English grammar plus authoritative attached facts, not unrestricted natural-language understanding, a geocoder or an historical research AI. Unsupported structured fields and recognized unsupported intents fail explicitly.
- The existing production mobile textarea, Docker/GPU image and deployment entrypoint are unchanged. These additions are selected through the new authenticated **source-checkout free review profile**; no claim is made that an old gCube image contains or exposes them. No new image or workload is deployed by this change.
- The free profile is nonhistorical GENERAL/FICTIONAL, 1080×1920, 30fps, at most 240 total frames, with no audio. Existing long-form/SFX/Dropbox implementations remain preserved; local export alone does not certify external Dropbox synchronization.
- The preserved reference camera requires the final keyframe to be the closest view. Out-and-in zoom is supported; a final wider overview and constant-follow dynamic zoom are not silently substituted.
- Native visible labels are intentionally hidden because protected glyph metrics cannot be replaced with arbitrary names. Explicit show-label/name/caption requests are unsupported; supplied names remain entity references and metadata.
- Actual regional Natural Earth crops and the available global RGB asset are used honestly. The full global NE1 TIFF remains an LFS pointer. No new DEM, bathymetry or fake elevation is created, and global RGB is not claimed to be real DEM relief.
- Whole-trajectory source coverage, native resolution, crop budget, GIS identity, projection limits and complete feature footprints remain mandatory. Dateline wrapping, unsupported polar extents, excessive windows and pure-ocean extents without a valid native country context remain blocked.
- Current pixel families remain the connected WAR/TRANSPORT contracts. Insufficient historical ownership stays `NEEDS_INPUT`; qualified partial line/metric data without a pixel consumer stays `UNSUPPORTED`. Historical G3, paid execution, 80-second production and FINAL promotion remain blocked.
- CPU/SwiftShader tests and rendered frames are technical evidence. They do not establish NVIDIA validation, reference-level visual quality or user approval.
