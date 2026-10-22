# Native projection implementation

Current status: **CANDIDATE05 APPLIED; NATIVE FLAT/ROTATION UNIT SCOPE PASS; OVERALL PHASE1 PARTIAL — ORIGINAL WORLD BASELINE NONDETERMINISTIC**. The native pixel agent's final receipt, rather than this report or a syntax check, determines the exact native-test scope.

## Authorized file and evidence

Only modified protected path: `world-simulation-shorts-engine/web/map_infographic_v1/renderer.mjs`.

- Base commit: `5cc9b98c628324814e1e63f9d0f8c6254ee84174`.
- Original SHA-256: `e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38`.
- Current applied candidate05 SHA-256: `9f60a7e4a6299b23b6c9070be4b830a3bbad25f5e1b321e5eff383ce35fb4995`. Earlier candidate04 SHA `c5aaf6b902d5f5374d93230e8979919dee398e47c41cf65a12e3bf2a35b55f9d` is preserved as a failed exact globe-comparison checkpoint; a patch-caused regression was not established.
- Original file:53,468bytes. Current candidate05 file:65,924bytes. Candidate04 was64,945bytes with94 additional lines. Candidate05 isolates default shader source bytes; the observed comparison failure cannot currently be attributed to the patch because original-only repeated draws also vary.
- Pre-change design/backup/diff were remotely saved at `136b54953e8411e955f3838d0dd59e2adc5f0926` before replacement. The original hash was asserted immediately before applying the exact candidate bytes.
- `node --check world-simulation-shorts-engine/web/map_infographic_v1/renderer.mjs` passed after application.

The original307 manifest and backup remain unchanged. Protection results must say which original hashes differ under explicit authorization, rather than claiming all307 original hashes still match.

## Actual public API

```js
const factory = await createMapInfographicRenderer({
  // Existing canvas, plan, source metadata, layoutPlan and shared renderer.
  ...existingInputs,
  projectionMode: 'REFERENCE_SIMILARITY_2D_V1',
});
const projection = factory.projectionDescriptor();
factory.updateSimilarity({centerQ, scale, angleDegrees});
const canonicalPixel = factory.screen([longitude, latitude]);
const geographicPoint = factory.inverseScreen([canonicalX, canonicalY]);
const fullSourceFootprint = factory.sourceEnvelope();
factory.renderFrame({graphics:false, ...existingMaterialOptions});
// The existing/current projected graphic consumer then draws through the shared
// Three renderer, using factory.screen. Native fixed-layout graphics are blocked.
```

The new selector starts inactive, preserving the original native camera until a successful explicit update. A normal factory with no selector retains the prior camera and source-loading behavior. `updateCamera(bounds)` returns an opted-in factory to that established nonrotated bounds path. Old globe construction/rendering is unchanged; selecting the new flat mode on a globe is explicitly unsupported.

`centerQ` uses the original map's fixed standard-parallel coordinates with y down, matching the prior director math contract: `[(lon−originLon)×cos(originLat), originLat−lat]`. Scale is canonical output pixels per projected degree. Supplied screen rotation maps to the actual native Three camera's Z rotation; `screen` uses that camera. The inverse terrain sampling computes the same geographic point. Current-view ID/coverage buffers remain in screen UVs. Native geographic boundaries use the same geographic camera. The result is not a completed-frame rotation or an overlay-only camera.

## Current source and geometry guards

- Snapshot initial projection origin/bounds, source descriptor and both plan/locked-layout minimum extents. Caller mutations cannot alter the numerical contract after asynchronous factory creation.
- Call original `assertLocalDetailAdmission` for the actual plan and, only on the new path, a separate supplied layout plan. Required LOCAL evidence is never replaced with a client boolean.
- Require both plan and layout minimum camera-axis spans. Rotation cannot make a small viewport's AABB appear broad enough to bypass minimum zoom.
- Verify actual regional terrain bytes against SHA-256 before decode on the opt-in path. Default TextureLoader remains unchanged.
- Derive source-native spacing with the unchanged metadata helper, conservatively bounded by actual decoded texture dimensions. Require geographic source metadata, explicit `NoData:null`, full rotated footprint coverage, one native texel gutter, and no more than one output pixel per native texel.
- Compute regional RGB UV from CPU-relative center UV plus a small inverse pixel delta, avoiding large geographic coordinate subtraction inside the fine RGB shader path.
- Refuse far-origin deep zoom when the current-view Float32 position arithmetic budget exceeds0.25canonicalpixels. This budget is not a geographic accuracy certificate and does not replace source/GIS quality or actual pixel inspection.
- Keep the established DEM sampling and lighting algorithms. Refuse active DEM data below the absolute geographic Float32 sampling precision rather than inventing higher precision.
- Refuse active fixed-layout `graphics:true`, an unqualified context LOD mix, and a draw after a commit-time camera update failure. Explicit projected graphic consumers remain a separate integration layer.

Updates are transactional. A failed pre-mutation admission check leaves the last admitted camera and evidence unchanged, including the initially inactive legacy state. It does not accept the rejected pose or fabricate activation. An unexpected failure after camera mutation marks the factory unsafe and blocks drawing until a successful camera update. A blanket ban on drawing after any rejected request is not this API's contract.

## Important remaining limits

**One qualified regional raster per active draw.** This primitive does not implement or certify an entire country-to-submeter source hierarchy. Full reference production still needs a coherent, license-cleared multi-resolution source pipeline and precision-qualified geographic data. An impossibly enlarged coarse raster cannot pass the source-density gate. The current source shortage cannot be solved by claiming this projection primitive alone completes reference reproduction.

Dateline-wrapped and polar/globe transitions remain unsupported in this bounded flat contract. Geographic identity,85m measured fact, source license and native coastline precision are not inferred from the image or from a projection test.

No old camera, Area, Flow, Event, Planner, fixed glyph atlas, cache, FINAL or previous video was rewritten. No renderer core was copied into a new fake runtime. No paid GPU/API/deployment or80second production was executed by this implementation work.

## Observed default globe comparison failure and shader-source isolation05

The actual pixel audit of applied candidate04 found a failed exact comparison:12 of2,073,600 default globe pixels changed versus the original source under the same input and software backend; maximum RGB delta5. Flat Namibia/Nepal12-frame comparison remained bit-exact. This is a failed default-path gate, not an acceptable threshold difference. The private audit preserves raw readPixels hashes, difference metrics and both PNGs. Downstream active/reference production was stopped.

Candidate05 preserves the original `terrainFragment` declaration byte-for-byte (declaration SHA-256 `66575443eaa3f61fa72a2764fcf9db80eb76e0c2eb4773e2f3397872b3bd7545`). A bounded four-anchor helper constructs the explicit opt-in source variant only when the new mode is selected. The default/globe material receives the exact old GLSL string, removing the unused opt-in GLSL branch from the normal/globe compiled source. Whether that branch caused the earlier difference was not established. Camera/source/precision admission and the no-blit composition are unchanged.

Candidate05 source SHA-256: `9f60a7e4a6299b23b6c9070be4b830a3bbad25f5e1b321e5eff383ce35fb4995`. Separate diffs versus original and candidate04 are preserved. At proposal time the live protected renderer was candidate04. Root saved failure/proposal evidence remotely before allowing replacement. The following apply receipt records the authorized replacement; it does not claim exact pixel PASS.


### Candidate05 applied after saved failure/proposal checkpoint

Root remotely saved failed04 and original/current→05 evidence at `bb0d8ec781949e2c765f178019ff44cc588c2154`, then explicitly authorized applying the exact candidate05. The live renderer was checked against failed04 SHA immediately before replacement. Only the approved renderer path was changed. `reports/RENDERER05_APPLY_RECEIPT.json` records original/failed/applied hashes; syntax validation passed. The actual default/globe and active pixel rechecks are still required. This apply receipt deliberately says `actualPixelFixVerified:false`; it cannot replace the pixel agent's final test report.


### Corrected attribution after original-only determinism control

The candidate05 same-input WORLD original/patched pair still failed exact equality (14 pixels, maximum RGB delta6). The pixel agent then repeated draws using the **unchanged original renderer in the same factory** and observed different raw readPixels hashes. Thus the earlier candidate04 comparison remains a real failed exact-equality test, but it is **not evidence that candidate04 caused a default rendering regression**. Candidate05 is retained as a bounded source-preservation improvement; it is not a demonstrated pixel-restoration fix. Original-only determinism and render-pass isolation evidence is owned by the native pixel audit. No threshold was relaxed and no protected code was further changed on this hypothesis.

Read-only inspection found no Date/random rendering input. `performance.now()` is used only for measurements. Original `setReveal` is idempotent on repeated default arguments, and original GLSL performs inverse-globe trigonometry, implicit texture filtering and source anisotropy. Font-face registration, MSAA/state and sampler/backend behavior are investigation candidates only; none is an established cause. In particular, a repeated-factory font registration cannot alone explain variation within the same unchanged factory.

## Final native-test scope

Candidate05 independent native unit validation passed with 53 actual factory frames and 12 admitted rotated poses. The executed receipts are `reports/NATIVE_UNIT_SUMMARY.json` and `reports/NATIVE_UNIT_PIXEL_RESULTS.json`, which retains all raw frame hashes. Six independent checks pass within this unit scope. The actual draws/readPixels include 3,082 informative real source samples and 25,068 GIS probes with zero coverage mismatches. CPU forward/inverse residuals are approximately 2.54e-13/1.61e-13 canonical pixels; these mathematical residuals do not themselves measure raster accuracy. Actual source readback mean channel error is 0.15–0.66, versus 49–76 for the deliberately wrong inverse control.

These actual free SwiftShader draws/readPixels cover flat default and opt-in-inactive equivalence, shared camera/source/GIS rotation and inverse behavior, and negative admission conditions. The contact sheet is `evidence/native-common-projection-unit/NATIVE_PROJECTION_UNIT_CONTACT_SHEET.png`. This is unit capability evidence only, not Studio reference production, NVIDIA validation, geographic accuracy or visual-quality approval. The final pixel receipts above are authoritative for exact assertion/frame counts and metrics.

The unchanged original WORLD baseline is nondeterministic even in native source diagnostic mode 5 with graphics, boundaries and glow disabled: the original-first same-factory pair differs by 24 pixels, maximum channel delta 2. This narrows the observed variation to the native globe/source-output path in this backend; it does not identify a driver, filter or trigonometric root cause. `reports/NATIVE_GLOBE_BASELINE_NONDETERMINISM.json` preserves actual original/patched stage metrics and evidence hashes. The exact default WORLD requirement remains UNVERIFIED, with thresholds unchanged. Overall PHASE1 is PARTIAL. No downstream Studio reference MP4, source-detail gate, NVIDIA or quality PASS follows from the independent unit result.
