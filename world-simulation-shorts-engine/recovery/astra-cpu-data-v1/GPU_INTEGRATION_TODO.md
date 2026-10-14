# GPU integration boundary — CPU implementation does not activate rendering

CPU work prepares source values, geographic metadata, source identities/versioning, acquisition plans and portable cache artifacts. No GPU texture/mesh, shader, material, glow, camera, control color, unit/flag, audio or postprocessing is changed. No video-quality or GPU PASS is asserted.

## Already reusable after CPU completion

Use the three provider APIs, actual source sample axes/transform, nodata/support masks, pinned hashes/metadata, independent raw/derived caches, bounded request plans and optional Scene preparation contract. Do not redo ASTRA research or rebuild these layers in the GPU task. Original archive/licensing/provenance is permanently available in the unchanged Phase A namespace.

## Hardware and launch path

An accessible physical graphics GPU worker/authorized remote GPU runner is still required for the original TOTAL MASTER. Recheck hardware device and unmasked renderer identity. SwiftShader is software; the preserved old runner forces/requires it and cannot certify hardware. Use a new isolated hardware-aware runner, without changing that runner or V5 Core. First complete deferred Phase A baseline composition/performance capture, then perform the original controlled baseline/data-only/glow-only/combined comparisons with the same scene, time, camera and encoder.

## Neutral data to actual GPU resources

- Decide texture formats, numeric endian conversion, row upload orientation, alignment, texture size/VRAM limits and per-source tile/LOD upload only on the actual hardware/API. CPU NPZ is a neutral exchange artifact, not an assigned GPU memory layout. Preserve Float32 height meters, Int16 signed elevation and encoded uint8 channels until a documented conversion is needed.
- The existing native height API accepts SHA-bound Float32 EPSG:4326/scale1/offset0 with `NoData:null` and finite values. CPU data permits explicit nodata/support masks. Invalid cells cannot be zero-filled to satisfy the old API. Use an additive masked integration or valid supported subwindows, and stop the affected integration if it requires protected renderer/API changes.
- Existing V4 display composition disables native DEM and overwrites native color. Passing height alone will not display real terrain. Replace only the optional new source/material stage before ownership/frontier/presentation/units in a separate extension; do not paint over the finished frame or alter approved visual systems.
- A height mesh is not implemented here. Native normal lighting is present in the old engine; future geodetic derivatives must use WGS84 east/north distances, the original registration and a real neighborhood support mask. Visual exaggeration remains separate from raw elevation.
- The sample PNG has no embedded sRGB/ICC/gamma declaration. Preserve that uncertainty; choose/document color-space handling during GPU integration without double conversion. BMNG is an August 2004 composite, not current imagery or guaranteed physical albedo. Do not infer depth from its ocean colors or height from NE1 baked shading.

## Ocean/coast mask and datum

An actual existing land/ocean coverage mask must be supplied. CPU exposes a mask requirement and tests only explicit synthetic masks; no production coast mask is manufactured. Native MSAA coverage is screen-space, whereas the CPU signed-elevation grid is geographic. The future adapter must verify projection/grid/axes/support binding before using either mask; shape equality alone is not geographic alignment. `depth_with_ocean_mask` assumes the caller supplies a correctly coindexed boolean mask. Negative land depressions remain land.

Preserve Copernicus EGM2008 versus GEBCO heterogeneous mean-sea-level datum caveat. No survey-grade coastal reconciliation or datum correction is performed. Verify actual shoreline seams and source transition visually on the hardware proof; do not silently relabel them as certified.

## Coverage, modes and acquisition limits

The supplied three samples are regional and do not cover the full protected camera/native overscan envelope. Keep explicit source support and an unchanged-baseline fallback outside it, or follow the original Master's bounded same-source acquisition rules. Do not stretch edges, synthesize absent values or change camera framing to hide missing data. No live supplier request is executed by this CPU task because supplier domains are not configured; offline plans/mocks are not global-data validation.

The current V4 recovery composition is Flat-only; generic source metadata alone does not make it Globe-ready. Preserve projection APIs and gate unsupported modes. Geographic source adapters split date-line requests; projected/rotated grids and unsupported polar reprojection require explicit future handling. Metadata-only WMTS planning is not proof of JPEG tile decoding/upload or provider SLA.

## Frozen appearance and release gates

Reuse actual territory/control geometry, speed, screen-space glow, marker/unit artwork, camera and timing exactly. Valid glow-off A/B must retain destination terrain-light multiplication and only disable core/halo alpha; the old `frontierEnabled:false` removes both. Stopping-state decay remains a separate fixture, not a fabricated stop at frame149.

Real hardware rendering, seam/LOD flicker, ocean style, gold relief, color contrast, glow synchronization, units and mobile readability remain unexecuted. Resume the original TOTAL MASTER verification/delivery after hardware is supplied. No 14-second expansion, FINAL promotion or video-quality PASS is authorized by this CPU result.

## Concrete resume handoff

Use `prepare_scene` to obtain the unchanged renderer payload, explicit source/request bindings and cache policy. Use `CpuDataPipeline` for local data or the existing acquisition-plan/DownloadManager contracts for permitted live retrieval. Do not recreate source identity, original-byte validation, neutral serialization or raw/derived cache. The saved local CLI fixture is intentionally tiny and never substitutes for full protected-camera coverage. Live Copernicus index/header validation, complete GEBCO coordinate discovery and actual metadata-driven NASA availability remain input prerequisites for regional supplier acquisition; no configured hardware or endpoint access is implied by CPU readiness.
