# Generic director composition — implementation and verification boundary

**Implemented: generic data program and shared-frame GPU consumer code. Verified: 25 CPU contract tests and five actual SwiftShader graphics component draws on a solid, non-map unit background. Native-map composition, Studio integration and reference production are not verified.**

All code is additive under `recovery/reference-director-v2/`. No existing Event,
Area, glyph, camera, renderer, Studio, asset or cache file was changed by this work.
The renderer's separately authorized opt-in extension belongs to the projection
implementation and has its own protection/pixel receipts.

## Configurable input and evaluation

`director_program.mjs` exports:

- `compileDirectorProgram(input)` — validates `WORLD_ENGINE_DIRECTOR_PROGRAM_V1`.
- `evaluateDirectorProgram(program, globalFrame)` — deterministic event state.
- `programWindowFrame(program, windowId, localFrame)` — maps honest bounded windows
  to that one global state; it never restarts event time.

Input fields: `dataMode`, `frameRange`, `fps`, `output`, `safeArea`, `locations`,
`areas`, `lines`, `metrics`, `events` and contiguous `windows`. Every job window is
at most 240 frames. All event start/end/pop/reveal/grapheme/settle/reading-hold
times come from the input. The implementation contains no country names,
geographic locations, historical dates or source-reference frame timings.

Records have unique IDs and explicit sources (`id`, SHA-256 and verification mode).
Optional source URL, license, date, CRS, native-resolution and uncertainty metadata
are preserved. These fields are traceability, **not independent factual/license
verification**. The caller's source registry/admission must verify real bytes,
coverage, precision and legal use before allowing production.

Events support `PIN`, `LABEL`, `AREA`, `LINE`, `METRIC`. Typed event/style fields
are strict: unknown or irrelevant fields are rejected rather than ignored.
Missing locations, source lines, metric values, malformed geometry, wrapped
dateline edges, zero-length lines, reversed times and too-short reading windows
fail explicitly. Geographic line consumer capacity is128 segments; source
geometry is never simplified to fit that limit. AREA and LINE reject `requiredRange`: AREA supports viewport clipping only; LINE supports required-safe only. LINE events currently require
`REQUIRED_VISIBLE_SAFE`; `CONTEXT_CULL` is rejected as unsupported at compilation
because the unchanged native Event line consumer requires its full halo ROI
inside the safe area. This is distinct from supported context pin/text culling.
Required intervals must fit inside their own active event, and each LABEL's PIN
must remain active throughout its entire LABEL interval.

Style descriptors select existing authored `HERO`/`CONTEXT` teardrop artwork with
screen-pixel dimensions with uniform artwork aspect ratio; anisotropic pin stretching is rejected. These are visual importance variants, not country or
reference identities. The original authored design is reused unchanged from V1;
all locations/labels/timing/styles are program data. Static region reveal changes
opacity only; source geometry remains unchanged.

## Existing modules reused

| Owner | Actual use |
| --- | --- |
| `event_contract_v1` | Coordinate/source-mode and geographic event validation |
| V1 `director_events` | Graphemes, one-shot pop curve, source arclength clipping, metric track, measured word reservation and visibility policy |
| `glyph_atlas.createMeasuredGlyph` | Existing pinned-font alpha coverage and real ink metrics; no final map Canvas |
| `area_overlay_pass_v3` | Polygon triangulation and area contour over the actual shared native framebuffer; large areas use viewport clipping |
| `event_line_v1` + `event_line_pass_v1` | Supplied geographic path is cut **before projection**; the existing GPU consumer draws100% of that cut path. Its projected-length timer is not used as the source clock |
| Native map factory | Public `screen`, `updateSimilarity`, `renderFrame(graphics:false)`, `inverseScreen`, `sourceEnvelope` |

`director_graphic_pass.mjs` defines:

- `createDirectorGraphicPass({renderer,canvas,factory,program})`: real WebGL quad,
  line and polygon consumers over the shared native framebuffer. Pin atlas has
  a true transparent hole; glyph alpha and finite halo are prepared separately
  and composited by GPU. Glyph quads support individual scale/opacity and line
  orientation. A linear-time exact Euclidean glyph distance transform computes the finite halo; a glyph is capped at 1024×1024, total atlas pixels at 8,388,608 and program glyphs at 256. No completed frame is copied, resampled or rotated.
- `prepareMetricPlacements(program,{projectAt})`: fixes the source geographic
  midpoint, chooses normal side once over the whole visible interval, rejects
  unreadable flips and applies the input's metric offset.
- `createDirectorRuntime(...)`: invokes the actual factory similarity update,
  verifies current projected anchors against the supplied global camera driver,
  draws the native map with stale fixed graphics disabled, then calls the new
  GPU consumers. Source/factual/Studio admission is explicitly external.

Required labels reserve full measured-word ink before individual glyph reveal.
The current hero/metric use required-safe admission; prior context can cull;
large areas clip at the viewport without changing geographic vertices. Prepared
metric placement is checked against the actual current factory projection.

## Actual verification

Command:

```sh
node --test --test-isolation=none --test-reporter=tap world-simulation-shorts-engine/recovery/reference-director-v2/tests/director_program.test.mjs world-simulation-shorts-engine/recovery/reference-director-v2/tests/glyph_distance.test.mjs
```

**25 PASS / 0 FAIL / 0 SKIP** in the final focused run (21 program +4 glyph-distance
tests). Persisted evidence is
`reports/DIRECTOR_PROGRAM_TEST.tap`. The same grammar was exercised with a
different time origin, hemisphere, geometry and label length. Other tests cover
window continuity, source-truth separation, whitespace/grapheme timing, reading
hold, source bindings and explicit unsupported input failures.

The first run exposed a new validator control-flow error: a dangling `else`
incorrectly applied line-style validation to labels. It was fixed without
weakening assertions. A shared mutable test source fixture also contaminated
later tests and was replaced with fresh cloned fixture inputs. Final tests
pass; the original renderer or historical facts were not changed to get PASS.

`FONT_COVERAGE.json` records the unchanged actual pinned Noto font's cmap:
44,810 mapped codepoints in 2,032 ranges. The compiler rejects unmapped
codepoints before creating glyphs. A test checks the actual font bytes against
that manifest. This is neither a promise of all-Unicode coverage nor independent
validation of every sequence's shaping. The real GPU unit covers CJK `항구` and
Latin/digits `12 km`; emoji grapheme segmentation is not font draw support.

## Actual free software-GPU component draw

Command (requires the existing Playwright/Chromium environment and localhost
browser permission):

```sh
node world-simulation-shorts-engine/recovery/reference-director-v2/tools/check_graphic_components.mjs attempt-02
```

The actual backend was ANGLE Vulkan SwiftShader. Five consumers compiled shaders,
drew and read back real pixels: PIN 8,738 changed pixels, LABEL 9,016, AREA 10,827,
LINE 5,671 and METRIC 3,715. All five had GL error 0. The pin hole matched the
underlying clear background exactly. Label core/blue halo counts were 1,337/3,664;
its full-word white ink center was x=540. The metric unit's coarse principal-axis
pixel estimate differed from its requested angle by 0.405°. Its unit assertion is
10°, **not** a replacement for the tighter production/reference layout gate.

Evidence: `reports/GPU_GRAPHIC_COMPONENT_RESULT.json` records draw diagnostics,
actual loaded-module hashes and explicit `nativeMapRendered:false`,
`actualStudioRender:false`, `referenceProduction:false` and
`nvidiaVerified:false`. `evidence/GRAPHIC_COMPONENT_UNIT_CONTACT_SHEET.png` is
visibly captioned as a synthetic graphics unit, not a map or Studio output.

The first actual GPU component attempt failed when reaching the unchanged raw
Area consumer with `AREA_GPU_GL_ERROR_1282` after other graphics resources had
been disposed. Resetting the shared Three bindings **before** raw-GL pass
construction resolved the same lifecycle condition; the new consumer now also
rejects preexisting and resource-creation GL errors explicitly. The old Area,
Event and renderer modules were not edited to make this pass. The failed
observation is preserved in `reports/GPU_GRAPHIC_COMPONENT_ATTEMPTS.json`; full
pre-fix stderr was not persisted, and that limitation is explicit.

## Remaining production gates

The component draw uses a clearly declared projection stub on a solid clear
background. It proves the five graphics consumers' GPU execution for those
fixtures only. It does not prove common native-map projection, source accuracy,
full global layout, reference continuity, Studio admission or final video quality.
Those require their separate native-map, data and actual-production gates.

No MP4 or fake reference map frame was produced by this composition subtask.
A data gate failure cannot be overridden by this program or by choosing
`SYNTHETIC_TEST` for the real scene. No paid GPU/API was used.
