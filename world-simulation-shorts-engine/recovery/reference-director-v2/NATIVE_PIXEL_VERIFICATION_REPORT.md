# Native projection pixel verification

Status: **independent flat/similarity unit checks PASS; overall PHASE 1 PARTIAL**. The unmodified native WORLD path is not pixel deterministic on the tested SwiftShader backend. PHASE 3 reference/Studio production remains unexecuted. These diagnostic frames are not the requested reference frames or proof of NVIDIA quality.

## Actual renderer and environment

- Original immutable module: `backups/renderer.5cc9b98.original.mjs`, SHA-256 `e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38`.
- Authorized native module candidate05: SHA-256 `9f60a7e4a6299b23b6c9070be4b830a3bbad25f5e1b321e5eff383ce35fb4995`.
- Actual Chromium 154.0.8037.57 / Playwright 1.62.1 / WebGL2. Renderer string: `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)`.
- No NVIDIA device verification, paid API, GPU deployment, or MP4 production was performed.
- The localhost HTTP server serves the original backup at the original module directory URL, preserving relative imports. Both module variants use the same Three.js renderer, GL context, source bytes and inputs. External browser network requests are blocked. The current G2 layout adapter is reused.
- The official sandbox permission path was required because restricted execution denied localhost listening with EPERM. No external network policy was bypassed.

## Default and inactive regression

The existing G2 region provider prepared real Namibia and Nepal source windows. The original module produced four immutable raw-pixel golden hashes: each region at original bounds and a 2% wider bounds update. Candidate05 default and opt-in-inactive modes reproduced all four exactly: **8 real comparison frames, zero differing pixels**. Original golden inputs, source hashes and actual backend are verified before reuse. See `reports/NATIVE_ORIGINAL_GOLDENS.json` and `reports/NATIVE_UNIT_PIXEL_RESULTS.json`.

The earlier raw Nepal seed initially failed its existing layout admission. That harness input did not use the current G2 provider's bounded-gap layout adaptation. Selecting the existing public provider fixed the test input; no label, collision check, layout engine or protected source was changed.

## Actual common-projection unit draw

Two explicitly synthetic, nonrectangular polygons exercise native GIS triangles, coverage, core/edge/glow and territory material. They are not geographic or historical claims. Their background is an exact native-pixel window of the licensed real Earthday raster, not a generated background. The crop is checked against source SHA, dimensions and original pixel window, with no resampling.

- Real source: `GLOBAL_EARTH_DAY_RGB_V1`, original 8192×4096 raster, SHA-256 `88ab060b6e7d241cfc590c69f528fab2b3247b738d40124cb590999a6fe44abc`.
- Attribution: Solar System Scope / NASA; CC BY 4.0, https://www.solarsystemscope.com/textures/ . Native spacing 0.0439453125°.
- Initial standard parallels: 0°, +20°, −20°.
- Each uses four actual rotated poses: +25°, +50°, +82°, −37°, with multiple centers and scales.
- **53 actual native draw/readPixels frames**: 8 flat regression frames plus 45 active/source/coverage/material/restoration frames.
- **3,082 informative real terrain source samples** compare actual rotated readPixels to independent inverse-geographic points in the baseline actual native source draw. Mean RGB error per pose is 0.1523–0.6541/255. An intentionally incorrect unrotated/AABB sampler has error 49.36–75.76/255 on those same samples. CPU bilinear sampling is used only for numerical audit, never to produce output frames.
- **25,068 native GIS coverage pixel probes; 0 mismatches** against independent inverse projection and polygon inclusion, excluding 4-pixel edge ambiguity.
- Maximum forward residual: 2.5421e−13 pixels. Maximum inverse round-trip residual: 1.6078e−13 pixels. Maximum four-corner source-envelope deviation: 2.0097e−14°.
- Original minimum-extent zoom, native texel density, source gutter, unsupported geographic domain, invalid pose fields and stale fixed-graphic use are explicitly rejected. Native bounds updates restore exact legacy source pixels.
- Actual draw has no GL errors; material output has no black rotation corners. All thresholds were defined before the active run and were not weakened.

Selected source/coverage/material frames and the labeled unit contact sheet are under `evidence/native-common-projection-unit/`. All 53 raw frame hashes, individual pose admissions and sample metrics are in `reports/NATIVE_UNIT_PIXEL_RESULTS.json`. This is a unit test of shared GIS/terrain projection, not a substitute for the two full PHASE 3 director fixture profiles.

## WORLD baseline nondeterminism and attribution correction

Candidate04 old/new WORLD differed at 12 pixels; candidate05 old/new differed at 14 pixels. All differences were localized near the globe silhouette by New Zealand. The gate stopped before active production. Subsequent isolation showed the **unmodified original module itself changes pixels between consecutive identical draws in the same factory**.

The isolation tested native full material, material without labels/boundaries/glow, and raw-source mode5. Original raw-source repeat pairs differ at 20–24 pixels, at most 2/255 per RGB channel, in the same bounding region. Thus the difference persists before downstream labels, territory material, boundaries or glow. No particular GPU sampler/driver cause is established. A patch-caused WORLD regression is **UNVERIFIED**, not confirmed. The default original GLSL source is preserved exactly in candidate05, but source equality is not an actual pixel-PASS substitute.

Previous mismatch evidence is preserved unchanged. `reports/NATIVE_GLOBE_BASELINE_NONDETERMINISM.json` provides the attribution correction and per-layer measurements. Its evidence folder contains actual consecutive original-source frames and candidate05 old/new frames. The harness's first determinism experiment had an incorrect top-level success label; its detailed check was FAIL. The next experiment corrected the top-level label. This reporting defect and original receipts remain recorded in `reports/NATIVE_PIXEL_ATTEMPTS.json`.

No tolerance was substituted for the required exact WORLD comparison. Overall PHASE 1 remains PARTIAL; WORLD exact-default preservation remains unverified on this backend.

## Metadata admission and transaction contract

Pre-mutation admission rejection keeps the previous admitted camera, or initial legacy-inactive camera, unchanged. It does not install the rejected rotated pose. An unexpected failure after mutation starts blocks drawing until a successful update. This preserves opt-in-inactive backward compatibility without admitting missing metadata.

The first extra metadata microcheck incorrectly required every rejected update to disable even the untouched legacy state. That was a harness contract assumption, not an established renderer defect. It failed and is preserved. The corrected microcheck requires explicit metadata rejection and exact preservation of camera, envelope, evidence and raw legacy source pixels. It does not change source admission or accepted-input thresholds. The corrected native-factory microcheck PASSes all three cases (missing native pixel budget, wrong CRS, undeclared NoData), with six actual before/after source draws and exact prior-pixel equality. See `reports/NATIVE_METADATA_GUARDS.json`.

## Reproduction commands

Run from the worktree root. These commands use free local Chromium/SwiftShader and require official permission for localhost sockets in this environment:

```sh
node world-simulation-shorts-engine/recovery/reference-director-v2/tools/check_native_projection.mjs --attempt=<fresh-name> --only=baseline
node world-simulation-shorts-engine/recovery/reference-director-v2/tools/check_native_projection.mjs --attempt=<fresh-name> --only=verify05
node world-simulation-shorts-engine/recovery/reference-director-v2/tools/check_native_projection.mjs --attempt=<fresh-name> --only=determinism
node world-simulation-shorts-engine/recovery/reference-director-v2/tools/check_native_projection.mjs --attempt=<fresh-name> --only=unit05
node world-simulation-shorts-engine/recovery/reference-director-v2/tools/check_native_projection.mjs --attempt=<fresh-name> --only=guards
```

`verify05` enforces WORLD first and stops on mismatch. `unit05` is the separately authorized independent unit diagnostic; it explicitly does not clear the WORLD gate. Every attempt uses a fresh directory and preserves frames as they complete. No cached, original or protected artifact is overwritten.

## Remaining gate

1. Obtain deterministic actual WORLD baseline behavior or verify exact default parity on another officially available free backend; do not silently exclude/relax the mismatch.
2. Pass the independent real-detail identity/coverage/data gate.
3. Only after both gates, execute the requested real reference static frames and actual Studio A/B/C videos. No such production was run here.

Human inspection covered the native equator 50° material/source/coverage frames and the complete 12-pose diagnostic contact sheet. This confirms the diagnostic scene's visible rotation, common geography and synthetic polygon placement. It does not establish reference visual quality, historical accuracy, Studio integration quality or NVIDIA behavior.
