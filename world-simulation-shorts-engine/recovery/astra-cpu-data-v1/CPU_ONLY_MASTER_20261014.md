# WORLD ENGINE — CODEX CPU-ONLY SAFE IMPLEMENTATION MASTER

User instruction received 2026-10-14 (Asia/Seoul). This CPU-only scope takes precedence over the earlier GPU-dependent stop for independent CPU work. The original TOTAL MASTER and Phase A records remain immutable.

## Authorized ordered scope

1. Reuse branch `development/astra-map-quality-20261014` at Phase A `2103682` if local/remote and worktree are safe. Create a child branch only for concurrent/conflicting work. Reuse completed research, 24-member integrity audit and sample inspection without unnecessary repetition; test the new implementation.
2. B: Copernicus 2021 GeoTIFF parsing, original Float32 meters/nodata/CRS/transform/PixelIsPoint/crop/hash; GEBCO 2026 NetCDF signed values/actual axes/cell centers/masks/crop; NASA PNG/PGW/PRJ/georegistration/WMS axes/color metadata/source-vs-output resolution. Produce neutral CPU data contracts, no meshes or GPU upload.
3. C: independent TerrainSource/BathymetrySource/SurfaceTextureSource interfaces. Required results: status, sourceId, sourceVersion, sourceURL, bbox, CRS, nativeResolution, outputResolution, verticalDatum, nodata, attribution, SHA-256, error. Statuses distinguish available/unavailable/auth_required/version_changed/license_unverified/invalid_data. Bbox order west/south/east/north; no country/scene hardcodes.
4. D: bounded regional Copernicus tile-index/COG Range requests, pinned GEBCO metadata/axis/index subsets, NASA WMS/WMTS metadata/matrix requests. No global raster downloads/research/server-limit bypass. If network unavailable, implement request generation and mock response tests; never claim live downloads.
5. E: raw/derived caches keyed by provider/version/bbox/CRS/resolution/raw hash/transform; reuse/deduplication; reject failed/corrupt success entries; restart/resume; version isolation; limited concurrency/timeout/retry caps. Share this contract with future GPU integration.
6. F: optional Scene JSON map-data preparation settings, existing scene behavior preserved; no old parser/API edits. Config includes bbox/crs/targetGroundResolution/three source IDs+versions/cache policy. GPU activation remains inactive. Defer any change requiring an existing parser/renderer edit.
7. G: CPU real-data and synthetic geography/nodata/sign/half-pixel/WMS/version/cache/recovery/Scene/protection regressions. Distinguish PASS/FAIL/SKIP/BLOCKED. No unexecuted PASS or global real-data certification from synthetic tests.

## Absolute protections and stop rules

Do not modify existing FINAL or approved MASTER/movie, GPU renderer, WebGL/frontier shaders, terrain/ocean materials, gold lighting, camera, control colors/speed, army/flag/marker designs, audio or postprocessing. Do not break public APIs, convert missing source values to zero, manufacture ocean masks or claim SwiftShader/NVIDIA validation. CPU outputs preserve neutral original values/metadata without fixing GPU-specific memory layout.

Stop only the affected work if it requires protected changes, destructive API edits, source-value damage, unclear license, unresolved existing regression, branch conflict or irreconcilable data contract conflict. Continue independent authorized CPU work. Record GPU integration prerequisites in `GPU_INTEGRATION_TODO.md`.

## Required delivery and stop

Write CPU_ONLY_IMPLEMENTATION_REPORT.md, DATA_PROVIDER_CONTRACT.md, DATA_ACQUISITION_REPORT.md, CACHE_AND_RECOVERY_TEST.md, SCENE_JSON_COMPATIBILITY.md, GPU_INTEGRATION_TODO.md, REGRESSION_TEST_RESULTS.md and SHA256SUMS. Report implemented/reused features, changed files, actual/unrun tests, unresolved items, GPU work, branch/commits/remote save, protected-file changes, secret scan and temporary files.

Save safely to remote GitHub. If CPU implementation, provider interface, possible acquisition scope, cache/recovery, backward Scene compatibility, existing regressions, zero protected changes and documented GPU TODO all pass, state CPU_ONLY_READY_FOR_GPU_INTEGRATION; otherwise CPU_ONLY_PARTIAL_BLOCKED. Do not declare video-quality PASS. Stop after final report and wait for user review. GPU follow-up resumes the original TOTAL MASTER integration; no video/14-second/FINAL work here.
