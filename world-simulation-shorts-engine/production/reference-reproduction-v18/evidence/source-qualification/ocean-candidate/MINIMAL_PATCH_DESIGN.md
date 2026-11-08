# Minimal ocean appearance proposal at 6e4c95f3

## Findings

Reference contact-sheet close shots visibly contain ocean surface texture and highlight contrast. Latest sample contact sheet instead has nearly flat dark blue. A contact sheet does not establish measured bathymetry, exact water normals or temporal water behavior, and its small-island close shots are not scale-equivalent to the present Korea-wide camera.

The active presentation path imports `web/map_infographic_v1/renderer.mjs` from `recovery/universal-presentation-v2/presentation_runtime.mjs:3`, instantiates it at line47 and forces terrain LOD1 at line62. Renderer lines230–241 derive sea from registered raster luminance, mix using unchanged GIS coverage, then apply the existing transfer. It has no bathymetric water-normal path. Its `topo` normal is explicitly a coarse relief proxy and is not ocean depth data. Do not repurpose it as bathymetry.

Existing reusable modules were found:
- `web/map_infographic_v1/reference_ocean_material_v3.mjs`: authored derivative-filtered analytical ripple and sparse glint; explicitly not measured water or simulation.
- `reference_ocean_material_v4.mjs`: source-tone/chroma response, explicitly removes the V3 ripple/glint/drift and rejects attempts to enable them. This is the better minimal reuse. Do not reintroduce V3 as an accidental regression.
- `wave_visual_v3.mjs` describes event-owned illustrative wave fronts over supplied coast geometry, not a reusable ocean surface normal/material.
- Legacy `web/flat_renderer.js:54–60` has a simple varied dark ocean and dithering, explicitly no surface-image lookup or relief. It is not the active renderer here.

Neither inspected ocean module is imported by the current `presentation_runtime.mjs` or `renderer.mjs`. This is a bounded active-path inspection, not proof that no other repository branch or isolated study uses them.

## Source calibration issue

V4 defaults were designed for NE1: source luminance range0.56–0.77, anchor0.68. CPU inspection of the five actual BMNG baseline derivatives, restricted to class80 known water, gives encoded-sRGB median Y0.010–0.055 and 99th percentile0.265–0.298. At least99.9996% fall below V4's lower anchor. Blind reuse would collapse almost all source-tone separation. Linear luminance is lower still. Evidence: `BASELINE_WATER_LUMA_AUDIT.json`.

The isolated candidate reuses V4 with one fixed, source-specific profile: range0.005–0.30, anchor0.05, contrast0.75, source chroma retention0.35, nearshoreMix0. It does not adapt per frame or per atlas, invent depth or generate waves. These are provisional display parameters informed by real-source distribution, not a visual acceptance result. The nearshore band is disabled to avoid inventing coastal depth/color implications from generalized GIS.

## Smallest runtime patch after review, not applied

1. Add explicit `waterAppearance:null` default to the map factory; null must select the exact current shader bytes. Follow the existing opt-in source-variant pattern at renderer lines244–270 and material selection near line493. Preserve default and globe programs unchanged. New profile name must not reuse an accepted old schema.
2. In the opt-in shader variant only, insert the existing V4 GLSL generated from the fixed BMNG profile. Sample the hash-bound baseline RGB derivative separately from optical/composite RGB; water appearance must never use a land optical sample to derive ocean tone. The baseline source is already required by the86-source manifest, but passing it separately costs a sampler if it cannot be reused safely. Do not claim zero reads for the full new integration merely because the V4 helper itself has no sampler reads.
3. Require explicit source/mask binding under the candidate admission path. Shade only when the full runtime texture footprint is valid known water, no unknown/land samples occur, and existing GIS land coverage is exactly zero. Every other pixel retains the exact prior sea expression. Class80 is permanent water, including inland water; it is not an ocean-membership or tidal proof. Accurate broad ocean coverage therefore remains blocked by unknown classification. Never infer sea solely from color or convert unknown to ocean.
4. Resolve color space explicitly: V4 profile and proposed CPU helper take encoded sRGB and return encoded sRGB. Current renderer variable `source` is linearized. Supply baseline encoded RGB to V4, then linearize its result before the unchanged renderer output transfer. Do not feed linear RGB into the encoded-source thresholds. GPU/CPU parity and final tone calibration require later authorized visual review.
5. Insert the gated replacement only at the existing `vec3 sea=...` material point; do not touch land, GIS IDs, coverage, boundaries, camera, DEM, source RGB assets or area overlays. Preserve mixed-coast antialiasing via the unchanged final blend. Keep raw-source and diagnostic modes unchanged.
6. Bind profile hash, baseline asset hash, mask/footprint evidence and color-space declaration through `presentation_plan`, `presentation_runtime`, `capture_presentation` and Studio source admission. Default preset remains disabled; qualification remains false. Do not only edit a generated Vulkan variant; deliberate source-generation/reconciliation belongs to later integration.

## Isolated implementation and checks

`bmng_ocean_candidate.mjs` is a CPU-testable V4 profile adapter, response evaluator and conservative sample-footprint gate. It imports only the saved V4 helper, not a renderer. The original helper is copied unmodified in semantics. It does not write the source atlases or runtime, compile a shader, create a GPU context or render anything.

Ten new focused tests pass: disabled exact return, eligible footprint, unknown/mixed/invalid fallback, any nonzero land coverage fallback, partition rejection, BMNG tonal separation, zero procedural/nearshore energy, no-admission/color-space evidence, input validation/nonmutation and deterministic bounded response.

No claim of reference parity, realistic waves, bathymetry, mask admission, shader compatibility or visually approved palette is made. The minimal source-tone reuse should be reviewed first. Matching the reference's close-shot surface texture would be a distinct visual-material task, not something source-tone calibration alone can guarantee, and must not silently reverse V4's deliberate pattern removal.
