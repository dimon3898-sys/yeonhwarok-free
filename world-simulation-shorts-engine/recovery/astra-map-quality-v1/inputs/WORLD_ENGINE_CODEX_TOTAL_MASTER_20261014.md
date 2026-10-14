# WORLD ENGINE — CODEX TOTAL IMPLEMENTATION MASTER
## ASTRA Global Map Data × Cinematic Terrain × Moving Frontier Glow
**Date:** 2026-10-14  
**State:** IMPLEMENTATION AUTHORIZED ON ISOLATED BRANCH / FINAL PROTECTED / USER_VIDEO_REVIEW_REQUIRED

## 0. Required attachments and authority
Read **all** of `ESSENTIAL_DATA_REPORT.md`, `CODEX_HANDOFF.md`, the `ESSENTIAL_MAP_SAMPLES.zip` package including `DATA_MANIFEST.json`, `SHA256SUMS.txt`, `licenses/*`, `provenance/*`, and `65422.mp4` before modifying code. The `.sha256` file verifies the ZIP. Treat the attached ASTRA handoff as the source of truth for the acquired datasets, metadata and known caveats. If it conflicts with live code, report the conflict and resolve conservatively without rewriting approved behavior. Do not claim repository/GPU validation from the data package alone.

ZIP SHA-256: `bd028be93f1813e0ac16628afcd218e95685cedb730b89a6584d196878ead66a`  
65422.mp4 SHA-256: `f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6`

Reference baseline: `65422.mp4` (5 seconds, 1080×1920, 30fps). Locate original `65416` and target REFERENCE in the repository if available. If unavailable, explicitly mark reference-equivalence evaluation as BLOCKED; do not invent comparisons.

## 1. Objective and non-negotiables
Make the actual 9:16 output as visually close to or better than the user's target reference **as can be demonstrated**, by integrating real terrain, bathymetry and surface textures, improving moving-frontier visibility, and preserving existing camera, timing, army design, land-control colors, audio and previously approved aesthetic. Quality is determined by rendered video, not tests or screenshots alone. Do not promise reference parity without side-by-side evaluation and explicit user approval.

WORLD ENGINE is a **global, reusable engine**, not a Korean War renderer. All sources and effects must work via generic bbox/CRS/LOD/Scene JSON and data-driven faction/time controls. Korean coordinates, flags and event details belong only in fixtures. No hardcoded Korea logic, no decorative arrows or unnecessary lines. Preserve approved FINAL/MASTER, main, and unrelated assets. Work on a **new isolated development branch**; never overwrite existing FINAL, original videos, data or cache without safeguards. No 14-second expansion or FINAL promotion before user approves the integrated 5-second sample.

## 2. Phase A — read-only baseline audit and go/no-go
1. Inspect repository, active branch, worktree, current approved outputs and their checksums; locate renderer entry points, Flat/Globe modes, Scene JSON schema, terrain/ocean masks, land-control layers, army symbols, glow shader, LOD, GPU/WebGL, FFmpeg, audio, caches and tests.
2. Verify all input SHA-256 hashes and ZIP internal `SHA256SUMS.txt`, inspect formats, CRS, geotransforms, nodata, dimensions, provenance and attribution. Preserve original bytes.
3. Capture current render baseline, known working tests, environment and performance if execution is possible. Record what could not be checked.
4. Write `BASELINE_AUDIT.md` including risks, compatibility plan and precise touched files. If critical dependencies are absent or the current code cannot be audited, stop and request missing inputs instead of fabricating success.

## 3. Phase B — generic data source adapters
Use the acquired **three** datasets only; do not redo ASTRA research or download global rasters. Acquire only bounded extra test tiles if explicitly necessary and permitted, with source/version/size logging.

### TerrainSource: Copernicus DEM GLO-30
Use the 2021 sample and pinned source. Preserve original Float32 meters, PixelIsPoint registration, transform, nodata, EGM2008 vertical datum metadata and source version. Preserve actual pixel placement (do not replace TIFF transform with requested bbox). Produce terrain mesh/height texture and geodetically correct normals; separate source elevation from visual exaggeration. Never gamma/sRGB-convert height data. Existing lighting remains baseline.

### BathymetrySource: GEBCO_2026
Read signed elevation from NetCDF with actual lat/lon axes and south-to-north ordering; ensure north-up conversion where needed. Use `max(0,-elevation)` only for depth shading, preserving raw sign. Keep mixed/mean-sea-level datum caveat explicit. Do not classify all negative land elevation as ocean; integrate existing land/ocean mask. Avoid coast seams, inland depression flooding, fake interpolated depth and unsupported claims of survey accuracy.

### SurfaceTextureSource: NASA Blue Marble Next Generation
Use pinned August 2004 static composite; read PNG with `.pgw` and `.prj`. Respect WMS 1.3 EPSG:4326 axis-order inversion relative to internal `[west,south,east,north]`; distinguish WMTS EPSG:4326 matrix geometry from standard XYZ/Web Mercator. Convert color texture in correct color space. Do not infer bathymetry from ocean pixels or present 2004 composite as current imagery. Do not invent high-resolution detail at close zoom.

### Shared contract
Expose `bbox`, `crs`, `targetGroundResolution/zoom`, `sourceId`, `sourceVersion` in generic Scene JSON. Return `status, sourceURL, version, bbox, native/output resolution, CRS, vertical datum, nodata, attribution, SHA-256`. Distinguish `unavailable`, `auth_required`, `version_changed`, `license_unverified`; never silently replace missing data with zeros. Implement limited-concurrency bounded downloads, retries/timeouts, raw and transformed caches keyed by source/version/hash/CRS/resolution/transform, LOD by screen-space error, resumability, and date-line splitting. Account for polar limits and variable longitude spacing. No global full-resolution download.

## 4. Phase C — cinematic map quality integration
Treat the datasets as physical/geographic foundations, **not finished visual effects**. Separate layers: (a) actual height geometry and normals; (b) signed bathymetry and ocean coloration; (c) georegistered surface albedo; (d) directional golden terrain light and tone mapping; (e) legible land-control overlays; (f) moving-frontier core/halo; (g) army/flag labels; (h) existing postprocessing and camera. Implement ordering consistent with current depth/alpha architecture rather than blindly following this list.

Aim for readable mountain relief, coherent coastline, natural ocean depth transitions, geographically grounded land color, crisp territory ownership and no seams, aliasing, shimmer, LOD popping, overexposure, crushed blacks, artificial high-frequency texture or loss of symbols. Preserve current approved camera path, pacing, army appearance, sea style and golden light unless a separately isolated A/B test proves an improvement and user accepts it. Add quality parameters rather than destructive global changes.

Produce controlled A/B output with identical scene, time, camera and encoder: **baseline**, **data-only**, **glow-only**, **combined** where feasible. If a variant cannot be generated, state why. A change that reduces readability or aesthetics must be disabled or reverted without damaging approved layers.

## 5. Phase D — moving frontier glow
Use `65422.mp4` as the moving-frontier technical baseline. Reported earlier metrics (RAW white core 2.62–2.70px, boundary brightness +1.42–1.44×, separate stop fixture 12 frames to 8%) are **prior test claims**, not automatically revalidated facts. Independently test them if the fixture/code is available; do not turn those numbers into arbitrary universal targets.

Preserve territorial expansion geometry and speed. Attach luminous core and soft gold halo to the **actual evolving territory boundary**, not a floating decorative line. Maintain legibility over bright land, dark ocean, mountainous relief and different zoom levels with screen-space-aware width and constrained bloom. Keep ownership fill, direction of expansion, army icons and labels distinguishable; no unnecessary arrows, trajectories or graphics. Test moving-state frame synchronization and a **separate stopping-state fixture** for decay (the 5-second clip does not show stopping). Make color, width, intensity, falloff, zoom behavior and decay data-driven and usable with any factions/country/era. Ensure compositing does not wash out terrain or flags.

## 6. Phase E — verification gates
**Integrity:** ZIP/manifest/sample checksums, parsers, no NaN-to-zero coercion, attribution.  
**Geospatial:** CRS, WMS axes, half-pixel offsets, north-up orientation, signed depths, nodata, datum mismatch, coast mask, geodesic normal scaling.  
**Global architecture:** arbitrary bbox, western/southern hemispheres, date line, polar limitations, missing tiles, changing versions, cache reuse and restart. Synthetic tests are **not** evidence of global real-data validation.  
**Render:** 1080×1920/30fps 5-second actual GPU/WebGL output; frame counts, control-fill alignment, glow-follow behavior, symbol readability, coast seams, tile/LOD flicker, lighting and color. Verify actual hardware acceleration instead of merely assuming GPU availability.  
**Regression:** existing tests and previously approved scenes, camera, audio, animation speed, symbols, FINAL files and output checksums. Report performance/VRAM, frame times and rendering costs where measurable.  
**Visual:** full moving sequence plus matched start, advance, tracking, continuous control and end frames; compare to `65422`, `65416` if available, and target reference if available. Clearly separate technical PASS, visual observations, unresolved gaps and user approval.

## 7. Delivery and hard stop
Produce in the isolated branch:
- `BASELINE_AUDIT.md`
- `DATA_INTEGRATION_REPORT.md`
- `FRONTIER_GLOW_QA.md`
- `GLOBAL_COMPATIBILITY_TEST.md`
- `REGRESSION_TEST_RESULTS.md`
- `VISUAL_COMPARISON_REPORT.md`
- `IMPLEMENTATION_REPORT.md`
- 5-second 1080×1920 MP4 and five matched comparison PNGs
- `SHA256SUMS` for deliverables
- branch/commit identifiers, direct download URLs, test logs and explicit blocked/failed checks.

No misleading blanket PASS. Do not replace approved FINAL. Stop at **`USER_VIDEO_REVIEW_REQUIRED`** and ask the user to review the actual MP4. **Only after explicit user approval** may a separate follow-up implement 14-second expansion; FINAL promotion requires its own approval. If critical verification fails, stop with a concrete diagnosis and minimal proposed fix, not a success declaration.

## 8. Completion criteria
Implementation is technically complete only if all three adapters function with supplied real samples, generic Scene JSON is functional, geographic integrity and regressions pass, and a real GPU 5-second integrated video plus comparison artifacts are delivered. **Reference-grade visual quality is a separate user judgment.** Do not confuse an implemented feature with an approved cinematic result.
