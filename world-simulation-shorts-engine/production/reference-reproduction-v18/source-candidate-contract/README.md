# Isolated derived-source candidate validator

This directory is an isolated candidate implementation. Its scope excludes production runtime files: existing source contracts, renderer, Studio, generated Vulkan variants and deployment image are unchanged. Publishing these candidate files does not enable runtime behavior. It performs no network access, rendering or production admission.

## Files and checks

- `derived_source_manifest.mjs`: structural and local-byte verification.
- `derived_source_manifest.test.mjs`: 45 focused synthetic tests, separate from old project PASS suites. All 45 current tests passed with zero failures, skips or cancellations after the final partition/provenance changes because those changes affect shared fixtures and validation.
- `focused-tests.tap`: historical pre-revision receipt, 29 passed. Intermediate changed-test receipts are `changed-focused-tests.tap`, `changed-focused-extra-tests.tap`, and `changed-report-field-test.tap`. The final current receipt is `final-candidate-tests.txt`: 45 total, 45 passed, 0 failed. Its module SHA-256 is `273223357ac39273419e67100b9072e7ae7bcbc835e42b9279bd136958547e5b`. No unrelated project suites ran.
- `implementation.patch`: standalone new-file patch for review; not applied to repository.

Run `node --test --test-reporter=tap derived_source_manifest.test.mjs`. Import `validateCandidateManifest` for structural checking, or await `verifyCandidateFiles(manifest, {root})` for file/hash/composition checks. The verifier never writes source assets. It limits candidate assets plus receipts to 512 MiB by default and supports a smaller `maxTotalBytes`.

A successful result is always `QUALIFICATION_REQUIRED`. It reports structural/byte checks separately and sets `productionAdmitted`, `renderAllowed`, and `imageBuildAllowed` to false. No acceptance field can be supplied to change that. Existing schemas are rejected rather than reinterpreted.

## Candidate contract

Top-level fields are strictly: schema `WORLD_ENGINE_DERIVED_SOURCE_CANDIDATE_V1`, purpose `QUALIFICATION_ONLY`, assets, receipts, products, layers, qualification. Qualification must remain `PENDING` with nonempty missingChecks.

Assets are raw, independently hashed rasters with id, relative file, sha256, bytes, encoding, dimensions `[width,height]`, pixel-edge bounds `[west,south,east,north]`, and crs `EPSG:4326`. Supported encodings are RGB8, MASK8 (binary 0/1), and F32LE. Dimensions must not exceed 4096. No PNG/NPZ decoding is hidden in this module; the acquisition/preparation worker must explicitly export raw bytes and preserve decoding/resampling receipts. Pixel edges, not sample-center bounds, are required. Parent derivative inputs and masks must have identical grids.

Receipts are local JSON files referenced by file, sha256 and bytes. Each product now binds both an acquisition/derivation receipt hash and a separate upstreamManifestSha256. The derivation receipt binds schema `WORLD_ENGINE_LOCAL_DERIVATION_RECEIPT_V1`, productKind, derivedArtifactSha256, upstreamManifestSha256, resampling and colorMapping. Missing, unbound, tampered or mismatched upstream-manifest hashes are rejected.

The upstream JSON schema is `WORLD_ENGINE_DERIVED_SOURCE_INPUT_MANIFEST_V1`, with completeness `ALL_DECLARED_UPSTREAM_INPUTS` and a nonempty sources array. List every actual input to the mosaic or mask, not a single representative tile. Each source records a unique id, HTTPS sourceUrl, license, attribution, sourceHashScope, sourceWholeFileSha256, CRS/grid, and processingMethod. Raster grids require dimensions and AREA/POINT pixel interpretation; vector sources have null dimensions/pixel interpretation rather than invented pixels. BYTE_RANGES inputs additionally require rangeReceipts `{offset,bytes,sha256}` and a null whole-file hash. Processing methods are EXACT_SOURCE_DECODE, COG_WINDOW_RESAMPLE, MASK_DERIVATION or GEOGRAPHIC_MASKED_COMPOSITION. The 82-tile case can therefore bind all tile URLs and their individual evidence.

Products bind id, kind, classification, assetId and provenance. Provenance contains acquisitionReceiptSha256, upstreamManifestSha256, resampling and colorMapping. The verifier checks the actual local hashes and consistency of those bindings. It cannot prove an author did not omit an upstream source, verify remote acquisition authenticity, or reproduce upstream resampling; source-list completeness and authenticity explicitly remain qualification work. Never invent a whole-file digest from partial COG access.

Supported product kinds/classifications:

- OPTICAL_RGB / OPTICAL_RGB_NOT_BAKED
- BAKED_BASEMAP_RGB / BAKED_BASEMAP_NOT_OPTICAL
- DSM / REAL_DSM_METRES
- VALIDITY_MASK / SOURCE_VALIDITY
- KNOWN_LAND_MASK / KNOWN_LAND
- KNOWN_WATER_MASK / KNOWN_WATER
- UNKNOWN_MASK / UNKNOWN_CLASSIFICATION
- SELECTION_MASK / SOURCE_SELECTION
- DSM_USE_MASK / COMPLETE_DSM_NEIGHBORHOOD

Resampling metadata is limited to NONE, NEAREST, BILINEAR or AREA_MEAN_VALID_ONLY. Color mapping must be explicitly described. These are recorded operations, not assertions that the verifier independently reproduced them. The final composite, however, is checked pixel-for-pixel against its supplied real-source derivatives.

## RGB composition and water handling

One overview layer is required; one regional layer may be added. Each identifies rgbAssetId, opticalProductId, baselineProductId, baselineValidityProductId, opticalValidityProductId, knownLandMaskProductId, knownWaterMaskProductId, unknownMaskProductId and selectionProductId.

Policies must be:

- composition: EXACT_MASK_SELECT_REAL_RGB
- waterPolicy: PRESERVE_REAL_BASEMAP
- invalidOpticalLandPolicy: PRESERVE_BASEMAP_AND_BLOCK_ADMISSION

The three classification masks are required, binary, mutually exclusive and exhaustive: knownLand + knownWater + unknown must equal one at every pixel. A wetland or class0 pixel may remain unknown; it must not be inferred to be water. The selection mask must equal optical validity AND knownLand, for every pixel. The output must copy exactly the selected optical derivative pixel or the baseline derivative pixel. Every baseline pixel must be valid. No inpainting, silent recoloring, unknown alpha behavior or fabricated optical detail is accepted.

The audit separately counts knownLandPixels, knownWaterPixels, unknownPixels, invalidOpticalKnownLandPixels and opticalPixels. Known water and unknown both preserve the real BMNG derivative, but unknown is never reported as verified water. Invalid optical known-land remains an explicit unresolved count, even when the candidate display preserves baseline RGB. No silent source admission is possible. Even zero gaps do not grant admission. A generalized shoreline mask, including Natural Earth 1:10-million geometry, does not establish subpixel shoreline accuracy. This validator verifies how a provided mask is used, not its geographical truth.

## Height handling

An optional layer.height binds dsmProductId, validityProductId and useMaskProductId. It requires metre Float32 samples with scale 1, offset 0, invalidPayload NAN and outsidePolicy NO_DEM_KEEP_BASELINE_LIGHTING.

Missing samples must remain NaN under validity 0. Finite zero is accepted only under validity 1, as a declared measured zero. Validity1 with NaN or invalidity 0 with numeric zero is rejected.

The use mask may enable height only on knownLand, never knownWater or unknown, and only where the entire declared square neighborhood is inside the grid and valid. An integral invalid-sample map makes neighborhood checking linear in raster size. The contract deliberately says DECLARED_SQUARE_PENDING_RUNTIME_BINDING: the validator does not claim the current renderer's derivative kernel has been bound. Actual integration must derive a conservative sample radius from the renderer's bilinear height sampling, 3×3 footprint taps, central derivatives, per-frame sampling step and grid spacing. It must reject any frame whose required radius exceeds the admitted neighborhood. An arbitrary small radius is not production certification.

## Exact remaining integration changes

Repository paths below begin `world-simulation-shorts-engine/`.

1. Add a separate opt-in derived-source path beside `recovery/universal-presentation-v2/region_source.mjs`. Preserve the old exact-native-crop, single-source, no-resampling contract unchanged. New source qualification must verify actual imagery, mask semantics, full coverage, shoreline suitability, LOD sampling, color mapping and seams, not just this candidate schema.
2. Extend `capture_presentation.mjs` sourceRowsFor, prepareRuntimeRequest, verifyPreparedRuntimeRequest and loopback aliases to bind/hash all qualified RGB/mask/height/receipt assets. Preserve private-root and safe-file restrictions.
3. Extend `studio_adapter.py` source admission/material-file validation and cache identity for the new opt-in family. No client-provided PASS or arbitrary file URL may authorize it.
4. In `presentation_runtime.mjs`, pass qualified contextTerrain/height inputs, replace fixed LOD 1 only for the new path, and check active source coverage/gutters. Update source evidence; do not keep hardcoded demEnabled:false or fabricated full-source claims. `presentation_plan.mjs` currently disables DEM.
5. Current renderer RGB sampling ignores alpha. CPU-composed RGB products can use its existing regional+context sampler; raw masked RGBA cannot. A new accurate treatment/classification is needed; optical is not BAKED_RELIEF. CURRENT still uses existing relief proxy unless a real height path is enabled.
6. Current height contract requires complete finite R32F and its demWeight tests only rectangular boundaries. Add a separately qualified validity-mask path and full-neighborhood rejection before enabling sparse/coastal DSM. Do not feed these NaN-bearing candidate grids to the current renderer.
7. Reconcile pinned/generated Vulkan source derivation and manifests deliberately before packaging; do not overwrite historical generated variants or run the old builder blindly. No image build has been authorized by this validator.

## Two-layer sizing evidence

Using the preserved 600 viewport bounds and 1× output sampling plus two-pixel gutters, the first segment would need 2980×4229 as one atlas, above 4096. A 341-sample/degree overview plus 1389×1973 regional atlas for frames 55–149 avoids that limit. Other segment atlas minima are 2421×3116,1696×2336 and 1357×1924. These are numerical sizes, not a visual-quality pass or 2× sampling guarantee.

Safe schedule: overview-only until the regional atlas fully covers the current viewport and gutter; blend only where both layers cover; regional-only afterward. Existing renderer setTerrainLod supports two geographic RGB sources and correctly rejects regional-only rendering outside the regional extent. It still needs formal source admission and runtime wiring.

## Limits of this local deliverable

Tests use synthetic fixtures solely to exercise rejection and mask behavior. No actual acquired WorldCover mosaics or DSM atlases were qualified by these tests. Acquisition receipt authenticity, original-source range hashes, upstream resampling, cloud detection, historical accuracy, complete shoreline/water semantics, optical visual quality, renderer compatibility and runtime derivative radii remain unfinished. This directory does not claim deployment readiness.
