# ASTRA map quality — Phase A baseline audit

Decision: **NO_GO / PHASE_A_BLOCKED**. Accessible physical graphics GPU is absent. No Phase B adapter, Phase C material, Phase D glow change or new movie has been implemented.

## Authority and checkpoint

The complete supplied `inputs/WORLD_ENGINE_CODEX_TOTAL_MASTER_20261014.md` is frozen with SHA-256 `0a7630edd77290fa09804af957a366f6388027787ffa41ec80dc2792f719d453`. Phase A.4 says: **“If critical dependencies are absent or the current code cannot be audited, stop and request missing inputs instead of fabricating success.”** Phase E requires verifying actual hardware acceleration; completion requires a real GPU integrated five-second video. This stop follows that instruction, rather than substituting software output for hardware proof.

Preserved parent branch: `development/moving-frontier-glow-fix-20261014`; local and actual remote HEAD both `45af879d7417abba58e9ebd59d8e6630a785ac28`. Isolated audit branch: `development/astra-map-quality-20261014`. Existing untracked `tools/__pycache__/` is preserved and excluded from the new checkpoint.

No existing FINAL, engine source, old Candidate, source data, fixture, style, camera, timeline, unit, control geometry or cache is overwritten. Public scene remains the user's selected modern counterfactual; historical participation tests remain private. Main and all previous branches remain unchanged.

## Inputs and available comparisons

| Role | Persisted source | SHA-256 |
|---|---|---|
| 65422 baseline | `../moving-frontier-glow-fix-v1/public-review/WORLD_ENGINE_MOVING_FRONTIER_GLOW_FIX_5S.mp4` | `f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6` |
| 65416 earlier Candidate | `../map-engine-unit-bundle-v1/public-review/WORLD_ENGINE_MAP_ENGINE_UNIT_BUNDLE_5S.mp4` | `4f1b676baef6a4ba6fefbfd58a5d6b2e235fb57ada7d11cfd2baf827ec79f12e` |
| 65379 target reference | `../reference-reproduction-v1/data/REFERENCE_65379_COMPRESSED.mp4` | `5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6` |
| Original ASTRA package | `inputs/ESSENTIAL_MAP_SAMPLES.zip` | `bd028be93f1813e0ac16628afcd218e95685cedb730b89a6584d196878ead66a` |

All three movie files match their parent Git blobs. The uploaded 65422 and 65379 match these stored originals. Reference comparison is therefore available; the unrelated 14-second Korean War Candidate is not used as a reference. Existing whole-reference analysis remains preserved; this audit does not repeat that analysis or data research.

65422 was actually decoded in full: 150 RGB frames, 1080×1920, H.264, 30 fps, 5.000 seconds, one video stream and no audio. Decode exited zero without errors. Every frame hash is recorded in `evidence/BASELINE_FULL_DECODE.json`; a ten-frame chronological contact sheet was inspected. It shows the existing smooth camera/control evolution, red/purple ownership and eight national badges. This is observation of the old movie, not approval of new integrated quality. No new video was rendered or reencoded.

The ZIP has 25 safe regular members with no duplicate or unsafe paths. All 24 internal checksum entries match; the checksum file itself is the remaining member. All members, handoff/report, manifest, licenses and provenance were read by the read-only data audit. Original ZIP and supplied documents are copied byte-for-byte; notices and original licensing PDF remain inside the archive.

| Sample | Actual parsing result | Important contract |
|---|---|---|
| Copernicus GLO-30 2021 | Float32, 1800² finite cells; 204–1574.278564 m | EPSG:4326; PixelIsPoint; exact first-sample/transform; EGM2008 metadata; no height gamma conversion |
| GEBCO_2026 | Signed Int16, 480²; −2124–1613 m; 142575 negative cells | Ascending actual lat/lon axes; exact agreement with bundled OPeNDAP ASCII; north-up conversion and mixed sea-level datum caveat |
| NASA BMNG | RGBA 1600×2000, alpha 255 | `.pgw`/`.prj`; August 2004 composite; 0.005° output spacing; neither current imagery nor measured depth |

No critical sample parse errors were found. GEBCO acquired timestamps differ: manifest/CSV `00:49:30.362139+00:00`, provenance/NetCDF `00:50:36.557312+00:00` on 2026-10-14. This noncritical provenance inconsistency is recorded without rewriting original bytes. Package checksums do not establish survey accuracy or supplier signatures. GEBCO/NASA license evidence is supplied; external terms were not reinvestigated. Retain bundled attribution and restrictions.

## Actual renderer compatibility audit

All code paths below refer to unchanged `web/map_infographic_v1/` unless stated otherwise.

- `renderer.mjs:345` exposes the native factory. Flat uses regional equirectangular projection with a framing-center standard parallel; Globe has separate orthographic sampling. The current V4 bundle is Flat-only in practice: context terrain and `updateCamera` reject Globe. Global source adapters must gate supported projection modes explicitly; no global real-data validation is claimed.
- `renderer.mjs:417–433` accepts SHA-verified raw Float32 meters in R32F, nearest sampling, with no color conversion/mipmaps. It validates EPSG:4326, scale/offset, finite values and GPU texture limits. TIFF/NetCDF ingestion is absent. `:52–82` uses actual first-sample spacing, geographic derivatives and WGS84 east/north distances; incomplete neighborhoods fade to prior lighting. This path provides normal lighting, not displaced terrain mesh.
- `map_engine_unit_gpu_adapter_v4.mjs:166–168` deliberately sets terrain LOD 0 and `dem:false`; its fixture has `heightSource:null`. The full-screen V4 material subsequently replaces native color. Passing a DEM into the old runner alone would not display real height shading.
- `reference_terrain_material_v4.mjs:55–86` derives appearance from the actual Natural Earth I baked-relief RGB source, rather than physical height/normals. Its source is 2880×3360, bbox `[104,7,152,63]`, SHA `49127186cb2076131e49e3787454c31474e48ef206c27c6c637749173aca143a`. RGB8 framebuffer snapshots are deliberate; preserve this format compatibility.
- `reference_ocean_material_v4.mjs:46–62` derives source-tone/coastal appearance, not measured bathymetry. Its approved sea style rejects added analytic ripples/glints/drift. GEBCO requires a new optional material path with A/B evidence; preserve the baseline.
- Native polygon triangulation preserves holes; nearest GIS IDs and MSAA coverage own the land silhouette. V4 land/sea mixing uses that coverage. Negative height/depth cannot substitute for a geographic mask.
- Actual displayed order is native GIS IDs/coverage → V4 terrain/ocean → terrain RGB snapshot → complementary ownership fill → destination terrain-light multiplication → actual boundary core/halo → whole-map roll/overscan → national badges. Depth is disabled; blend/order matters. A new data material belongs before ownership/frontier/presentation/badges, rather than over the finished output.
- Territory and glow reuse one actual evaluated scalar boundary. Core/finite halo use derivatives and overscan-corrected widths. No decorative stroke, arrow or route exists. Existing control topology is two factions with a longitudinal function and 2–64 knots; this is not arbitrary worldwide front topology. Do not redesign it during this task.
- Disabling `frontierEnabled` also removes terrain-light multiplication. Valid glow-only/off ablations must change center/halo alpha while retaining the lighting profile. Keep all camera, units, geometry, timing and encoder inputs identical.
- Native geographic source LOD exists; mesh screen-error LOD, generic tile acquisition and restartable source transforms do not. Existing render capture already has source-bound frame caches and resumable diagnostics. Reuse those mechanisms instead of overwriting caches or duplicating the line/control engine.
- Separate production Flat/Earth routes exist in `engine/rendering.py`; they are not the current recovery runner. The latter pins Node 24.19.0 / Playwright 1.62.1 / Chromium 154.0.8037.57 and mounts existing module routes from `recovery/v5/serve.py`.

## Hardware and performance

No `/dev/nvidia*`, `/dev/dri/*`, `/dev/kfd` or framebuffer devices exist. PCI display/accelerator and DRM inventories are empty; NVIDIA proc driver and Vulkan ICDs are absent. Managed capabilities and callable physical-GPU/remote-render tools are empty. A Mesa EGL manifest alone does not prove hardware availability.

An actual 2×2 WebGL2 identity probe launched Chromium 154.0.8037.57 with software rasterization disabled and ANGLE GL; it could not create a context. This bounded probe is combined with device inventory, not treated as universal renderer certification. See `GPU_CAPABILITY_AUDIT.json` and `HARDWARE_ONLY_WEBGL_PROBE.json`.

The old runner explicitly forces `--use-angle=swiftshader` at `reference_runtime.mjs:118` and requires SwiftShader at `:154`. Even on a future hardware worker it must be preserved and accompanied by a new hardware-aware runner. Existing proof reports `ANGLE … SwiftShader Device (Subzero) … SwiftShader driver`: software, not physical GPU.

The old recorded 251.184-second proof run is historical software performance, not a new measurement. Physical GPU frame times, VRAM, integrated rendering cost and realtime performance are **NOT_AVAILABLE**. No source/image-generated CPU result is substituted for hardware evidence.

## Coverage and conservative plan

All 150 current camera/presentation frames were evaluated with the existing APIs, without rendering or changing input. Unrotated tracked framing envelope (before presentation roll) is `[123.6214717970718,33.46816920440891,130.38461926846924,43.62545236855281]`; native overscan 1.36 expands support to `[122.30838605591185,31.8417974782448,131.5778453458887,44.99324396294251]` before derivative guard bands.

Supplied terrain covers only `[128.2498611111111,37.25013888888889,128.7498611111111,37.75013888888889]`, bathymetry `[128,37,130,39]`, surface `[124,33,132,43]`. None covers the full current shot, especially the expanded native view. This is a coverage limitation, not a parse failure. Later integration must expose explicit source support/fallback masks, preserve the old source outside valid data and/or follow permitted bounded same-source acquisition. Never stretch edges, interpolate nonexistent terrain, silently zero-fill, alter the protected camera to hide missing data or claim full-scene high detail.

Proposed only after GPU readiness: generic source contract/three sample parsers/cache metadata under this recovery namespace; optional `web/astra_map_data_v1/` source/LOD/material orchestration; new hardware-aware runtime/server; new fixture/variants/tests. Keep existing renderer, V4 materials, V3 glow, camera/projection, ownership, badges, production routes and FINAL files immutable. The generic contract carries bbox/CRS/resolution/source/version/status, separate raw/derivative caches and explicit missing/version/license states. Date-line/polar synthetic checks cannot certify global real-data support.

Actual touched paths at this checkpoint are **only** `recovery/astra-map-quality-v1/`: original input copies, input manifest, baseline audit, resume instructions, integrity/parse/hardware/media/camera/test evidence and checkpoint records. No runtime integration files have been created. The final checksum inventory lists each new persisted file precisely.

## Focused regression and incomplete gates

Actual command `node recovery/moving-frontier-glow-fix-v1/test_control_frontier_glow.mjs`: **4/4 PASS**. It checks all 150 unchanged camera/control inputs, separate generic stopping-state monotone decay, profile protections and deterministic evaluation. Pure stopping logic is rechecked; RAW rendered core width/brightness metrics are not revalidated. The prior 2.62–2.70px and 1.42–1.44× claims remain labeled historical.

| Check | Result |
|---|---|
| Original/input byte integrity and sample parsing | PASS |
| Existing focused baseline regressions | PASS (4/4) |
| Full 65422 decode and stored original hashes | PASS |
| Existing source/FINAL protection | PASS, no tracked parent modification |
| Physical GPU availability | BLOCKED |
| Three runtime data adapters | NOT_STARTED |
| Integrated GPU A/B/proof/visual parity | NOT_STARTED |
| New candidate HTTP/SHA downloads | NOT_APPLICABLE; no new movie |
| USER_VIDEO_REVIEW_REQUIRED / FINAL | NOT_REACHED / NOT_EXECUTED |

Minimum external fix: attach an accessible graphics-enabled physical GPU worker with compatible driver/device nodes, or an authorized remote GPU runner through secure environment configuration. Do not install drivers as a substitute for absent hardware or save credentials in files/chat. Recheck hardware identity and complete the deferred Phase A hardware baseline composition/performance capture using unchanged V4 APIs on a new hardware-aware runner. Then resume **Phase B** from this checkpoint. No previous completed development or data investigation needs to restart.
