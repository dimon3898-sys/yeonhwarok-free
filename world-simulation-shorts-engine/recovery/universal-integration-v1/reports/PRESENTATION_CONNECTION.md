# Presentation connection: additive Area and camera aliases

Status: **CPU contract and source-selection verified; NVIDIA draw, 5-second visual comparison and 80-second output are NOT_VERIFIED.** Existing renderer, geometry, shaders, masks, FINALs and Candidate source files were not edited.

## Exact connection

The preserved V4 `front_adapter.mjs` already imports `createProductionAreaPass` from `/production-v3/production_area_pass.mjs` and `createProductionNativeCamera` from `/production-v3/production_native_camera.mjs`. The new `extendIntegrationServerPlan` changes only those two exact source bindings in a cloned, already verified server configuration. Original source bytes remain reachable through separate `/integration-v1/parent_*` aliases. The preserved V4 adapter, compositor, source material, V5 camera, original Area engines and native masks are reused.

| Browser URL selected by preserved V4 adapter | New thin entry | Actual unchanged owner |
|---|---|---|
| `/production-v3/production_area_pass.mjs` | `production_area_bridge.mjs` | original `createProductionAreaPass` |
| `/production-v3/production_native_camera.mjs` | `production_camera_bridge.mjs` | original `createProductionNativeCamera` |
| `/integration-v1/presentation.mjs` | strict normalization and forwarding | original profile colors, marker policy and ownership policy retained |

The wrapper fetches `/runtime-config.json` through the existing loopback server and requires `integrationV1.schema = WORLD_ENGINE_UNIVERSAL_INTEGRATION_V1`, `profile = VISUAL_UNIFIED_V1`, a profile SHA-256, a source-manifest SHA-256 and a browser-source signature. The normalized five-field profile must match its SHA before either original factory is called. Missing metadata is an error; selecting this profile never silently returns the old path.

`runtime_binding.mjs` is a pure composition helper. Its caller must verify source records and seal the complete composed configuration before hardware launch. It does not grant GPU admission, fabricate an approval or itself render a video. User input cannot supply trustworthy source signatures; the integration controller derives them from verified local files.

## Supported knobs actually consumed

| Field | Default | Range | Actual consumer |
|---|---:|---:|---|
| `territoryOpacity` | 0.62 | 0.24–0.8 | original `productionAreaStyle` → original Area fill alpha |
| `frontCoreWidthPixels` | 4.8 | 2.5–7 | original `productionAreaStyle` → original front core width |
| `frontGlowRadiusPixels` | 10 | 3–16 | original `productionAreaStyle` → original front glow radius |
| `frontGlowGain` | 0.42 | 0.1–0.65 | original `productionAreaStyle` → original front glow gain |
| `cameraApproachFrames` | 48 | integer 12–120 | original native camera → original `compileProductionFocusPlan.approachFrames` |

Every extra field, including unsupported unit scale, color replacement, new geometry or new camera requests, fails strict normalization. Parent white/gold colors and all ownership and marker policies survive the merge. The camera knob adjusts the duration of the existing admitted conservative focus approach; it does not add rotation, a closer zoom floor or a new camera path. A CPU test uses the actual preserved focus compiler/evaluator and unchanged Detail smootherstep to verify different durations on a synthetic southern/western region while preserving start, target and minimum bounds.

These five settings make existing consumers accessible; they do not resolve missing historical ownership or national-unit positions. The original Area factory only fills explicitly bound supplied polygons. During source-active archival-front holds it receives zero occupation areas. No enemy complement or route is inferred.

## Actual 80-second source selection

`integrationFrameSelections` calls the existing `evaluateProductionGeometryClock` and `selectFrontSnapshot` for each requested global frame. No local wall clock, invented motion, new coordinate interpolation or ownership generation is used.

CPU evaluation of the preserved `verified-front-data-v4-recovery/VIDEO_PLAN_80S.json` and `FRONT_PROFILE.json` covered exactly **2,400 frames at 30 fps**:

| Source selection | Frames | Meaning |
|---|---:|---|
| `NO_EVENT_GEOMETRY` | 60 | preserved initial arrival; no event geometry |
| `PRESERVED_QUALIFIED_SCHEMATIC_AREAS` | 1,490 | existing qualified schematic snapshot clock |
| `NO_INFERRED_OCCUPATION_FILL` | 850 | reviewed partial archival front; no occupation polygons inferred |

Preserved plan SHA-256: `2632f9106962bb126bf333422bce2be5094d4af7b25c5701acdf4455a2829dc6`.

This proves the selection contract and explicit historical limitations. It does **not** prove that 2,400 GPU frames were rendered, that every historical date has a verified bilateral occupation boundary, or that the output meets reference quality. The current source data intentionally holds some front snapshots without inventing movement between unobserved dates.

## Focused CPU tests

Command, from repository root:

```text
node world-simulation-shorts-engine/recovery/universal-integration-v1/tests/test_presentation.mjs
```

Result: **13 PASS, 0 FAIL, 0 SKIP**. Tests cover strict fields and bounds, unchanged profile policies, actual original Area-style consumption, runtime-profile SHA validation, source aliases and collisions, immutable parent configuration, 2,400-frame selection and a synthetic southern/western source fixture. Forwarding tests inject clearly labeled CPU owners to verify factory calls and unchanged geometry/mask references; those tests are not GPU or WebGL evidence. The separate actual camera-focus test runs only preserved CPU math.

The new files are not present in the previously published `8ef393…` operating image. Source connection and old-image inclusion are distinct. A source manifest, independent launch path and later reviewed candidate build are required before GPU use. The user’s 5-second reference comparison and quality approval remain prerequisites for any 80-second render or FINAL promotion.

## Added files

- `presentation.mjs`: strict five-field runtime profile, browser integrity check, original-factory forwarding.
- `production_area_bridge.mjs`: explicit alias into original Area compositor.
- `production_camera_bridge.mjs`: explicit alias into original safe native camera.
- `runtime_binding.mjs`: source-bound cloned server configuration and existing per-frame source-selection trace.
- `tests/test_presentation.mjs`: focused CPU tests.

No original source or runtime data was copied into a new renderer. No shader, full renderer, geography, camera engine, GPU admission, claim or storage adapter was replaced.
