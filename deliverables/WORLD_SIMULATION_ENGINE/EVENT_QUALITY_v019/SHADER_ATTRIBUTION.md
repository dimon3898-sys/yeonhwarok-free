# v019 source → material → output attribution

Scope: read-only inspection of the existing v018 path plus scalar arithmetic
over existing sources. No source/preset/camera code changed, no external data
download, no GPU/Chromium/frame renderer/gcube execution. Scalar predictions
below are **not AFTER GPU frames** and exclude atmospheric/cloud-shell raster,
post vignette, mesh interpolation, MSAA and actual GPU precision.

## Suez source and material

The path is SceneVisualQualityRenderer → SceneSecondEventRenderer →
SceneReturnWideRenderer → SceneSingleEventRenderer → SceneProductionEarthRenderer
→ SceneEarthPolishRenderer → SceneEarthRenderer → frozen MASTER V3 Renderer.

- Frozen day image and native regional crop are sRGB sources; they decode to
  linear RGB for material sampling. There is no identified duplicate color-space
  conversion or tone mapping by Three.js. Renderer uses LinearSRGB output and
  NoToneMapping; the frozen post shader performs the explicit film curve and
  gamma conversion.
- `visualQualityRegional()` only replaces geographically matched land albedo
  and land mask at close weight; max RGB blend .65. It preserves original ocean
  RGB and does not manufacture height/normal data.
- The actual regional Suez desert source is bright. At 31E28N it is linear
  [.9280,.9153,.8090]; combined original/dayLOD is [.8925,.8445,.7203].
- Frozen surface diffuse includes hardcoded solar multiplier **1.55**, lunar
  contribution .055 and base .018; it is independent of the scene's Three
  DirectionalLight/Hemisphere intensities. These scene lights illuminate 3D
  entities, not this custom Earth ShaderMaterial (no light chunks/uniforms).
- v004 geography fill is .15, bounded coast addition ≤.0084×day. Preset exposure
  is 1.30. v018 close-day multiplier is .82, effective 1.066 before the post pass.
- At the desert sample sun-dot-normal=.92745 and cloud shadow=0; land=1,
  specular=0, city=0. Diffuse is [1.1115,1.1530,1.0916] and fill
  [.1261,.1295,.1007]. Post film inputs after ×1.23 are
  [1.6227,1.6815,1.5633], producing ~242 luma code before atmospheric/vignette
  effects. This is highlight-shoulder contrast compression, not evidence of
  hard RGB clipping. Exact film hard clamp starts at input ~7.24166.
- Additional daylight-only pre-film scale .60 analytically produces ~230.8 luma
  code for this sample and improves response to ±3% source detail from 1.02 to
  1.67 luma code (~64%). .55 gives ~228.3 and ~78% improvement. These remain
  bright geographic displays, not a global-darkening recommendation. Preserve
  night/readability fill with a sunlit gate, not an unconditional scale.
- Glare is separate: exact frozen projection of F210 pixel(125,570) is
  29.75448E32.37774N. Reflection alignment=.999806, nd=.94963;
  scalar specular after v018 .45 multiplier≈.18879, actual MP4 RGB165/173/201.
  Two desert pixels have effectively zero reflection. The ocean peak follows
  the hardcoded shininess95 lobe; an additional close-only spec multiplier can
  reduce it without changing ocean source/albedo or WIDE.

## Cloud, atmosphere, tone mapping

- Both licensed 8K cloud shells, opacity .34, shadow expression and original
  advection stay unchanged. The audited clear desert source sample has cloud
  shadow zero; clouds are therefore not needed to explain its shoulder washout.
- RGB Rayleigh post contribution attenuates Earth and adds scatter **after**
  surface exposure. v018 did not lower it. It can contribute haze but no per-pass
  actual GPU buffers were supplied; its absolute fraction cannot honestly be
  declared measured. No evidence requires changing the architecture or shells.
- Film×1.23 then gamma1/2.2 is the same validated frozen output transform.
  Its high-input shoulder compresses authentic regional detail. Additional
  highlight compression after/before this shoulder would flatten detail again;
  first lower the daylight material input to leave the shoulder.
- Native bloom threshold1.6 and 8×3.5px sampling amount .015 are unchanged.

## Singapore city-light attribution

- Current city source is the pinned Solar System Scope processed 8K JPEG;
  source agent confirmed visible warm square clusters in the native crop,
  no higher-resolution source, and 4:4:4 JPEG (not chroma subsampling).
  They are mostly 2×2 or ≤4×4 native source clusters, not new 8×8 DCT block tiles.
- Geographic UVs, trilinear/linear filters, mip generation are unchanged and
  verified; close magnification samples native level rather than missing mips.
  A filtering/UV/bloom change cannot create absent geographic night detail.
- The native night score is sampled globally while the day/terrain material
  now has 21600-wide source LOD: the mismatch exposes night-map footprints.
- v018 power .82→1 removes dark-radiance boosting but does not change footprint;
  cityGain *.72 reduces intensity, not pattern.
- `SceneEarthPolishRenderer.lightingAt()` raises geography cityGain .88 to 1.03.
  Actual v018 coefficient before exposure is .8×1.03×.72=.59328.
- Frozen first-event preservation binds all first three focus coordinates to
  Suez-labelled information, not Singapore. At Singapore all focus kernels
  underflow to zero, focus=1; city_focus_limit2 is irrelevant here.
- At exact Singapore anchor nd=-.0297, day exposure≈1.29326. City red=.41975
  versus combined diffuse/readability red=.03207: emission dominates by13.09×.
  Pre-post red=.5843 (<bloom1.6), proving bloom is not required for this pattern.
- Proposal: multiply existing city emissive only by a close weight-dependent
  .12 factor and existing native GIS land mask; do not blur/resample/night-source
  fabricate. At the coastal Singapore anchor mask=.413, predicted city/geography
  ratio drops to .649×. Keep genuine day/regional geography and night fill.
  This prevents coarse offshore footprints from being mistaken for city data.
  It suppresses old source radiance where inadequate, **does not produce finer
  urban geometry** or imply a new high-resolution city asset.

## WIDE and frozen camera requirements

All new factors must equal1 when v018 material weight=0 (height≥.75); original
v018 qualitySampler/albedo/land, sun clock, focus, postpass and all camera values
must remain unchanged. Only explicit v019 plans use new shader/profile hashes.
No added texture/upload/VRAM is necessary for the proposal (existing masks reused).

## Reproducible receipts

- `shader_scalar_attribution.py` and `shader-scalar-attribution.json`
- `shader-candidate-math.json`
- `suez-selected-pixel-geography.json`, `suez-glare-scalar.json`
- Actual BEFORE source frames live in `actual-analysis/before/`.

Every actual appearance/contrast improvement remains unverified until NVIDIA
AFTER frames are generated. Analytic arithmetic is not a local CPU fallback.
