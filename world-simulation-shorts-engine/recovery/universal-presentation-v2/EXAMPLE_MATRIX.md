# Supplied-data and natural-language example matrix

Baseline: `b0d013832ee38571f9d3dfe685ce63f7083ba90f`. All files in this matrix are new opt-in inputs. Existing examples, source bytes, historical evidence, renderers and caches are read only.

These examples use a bounded Korean/English intent extractor and attached `WORLD_ENGINE_DATA_PROMPT_V1` facts. They do not demonstrate unrestricted natural-language understanding, geocoding, historical research, real flight schedules or observed trade. The envelope is `WORLD_ENGINE_PRESENTATION_PROMPT_V2`; supplied facts remain authoritative. Explicit camera controls provide reproducible movement instead of asking a language model to invent positions.

## Positive and safely blocked cases

| Input | Attached data and duration | Requested presentation | Expected compiler decision |
|---|---|---|---|
| `examples/AVIATION_EUROPE_NL.json` | Hamburg, Berlin and Munich modern localities; two opposite-direction illustrative connection scenes; 6 seconds / 180 frames | First scene has pan and zoom keyframes; second follows the supplied reverse route; city pulses; cut at frame 90 | PASS |
| `examples/TRADE_SOUTH_AMERICA_NL.json` | Valparaíso, Santiago and Concepción modern localities; two opposite-direction illustrative connection scenes; 6 seconds / 180 frames | First scene has pan and zoom keyframes; second follows the supplied reverse route; city pulses; cut at frame 90 | PASS |
| `examples/FICTIONAL_AFRICA_NL.json` | Original declared fictional small/large polygons, followed by explicitly authored contraction; Windhoek locality; 6 seconds / 180 frames | Camera keyframes, state-bound red/blue palettes, locality pulses and cut at frame 90 | PASS |
| `examples/NEW_REGION_JAPAN_NL.json` | Frozen Natural Earth Tokyo/Kyoto coordinates and existing Japan country context; illustrative connection; 3 seconds / 90 frames | Camera keyframes and Tokyo pulse | PASS |
| `examples/NEW_REGION_AUSTRALIA_NL.json` | Frozen Natural Earth Alice Springs/Canberra/Melbourne coordinates and existing Australia context; illustrative connection; 3 seconds / 90 frames | Camera keyframes and Canberra pulse | PASS |
| `examples/HISTORICAL_PARTIAL_SOURCE_NL.json` | Unchanged qualified 1951-01-24 approximate partial line and retained trusted-evidence registry | Partial-line display only; no complete territorial ownership claim | UNSUPPORTED: existing `LINE_METRIC` renderer consumer remains unconnected |
| `examples/HISTORICAL_MISSING_CONTROL_NL.json` | Unchanged historical example lacking adequate bilateral ownership and reviewed evidence | Request reports missing information rather than fabricating a front | NEEDS_INPUT |

The two transport demonstrations show declared technical connections between modern city coordinates. A line passing through those coordinates is not evidence of an actual airline service, navigable shipping route, trade volume or historical movement. Fictional rectangles are intentional supplied geometry; their edges must not be mistaken for texture-tile artifacts.

Japan and Australia are additional coordinate-selected regions, not new hardcoded renderer cases. The same compiler and actual source provider evaluate their center/bbox and country context. The provider independently verifies existing regional raster coverage or its explicitly identified global RGB fallback. RGB fallback is not DEM, bathymetry or equivalent native-detail coverage. The five legacy aliases are retained in `examples/LEGACY_FIVE_REGION_MATRIX.json`; that file is an input descriptor and does not itself establish a draw PASS.

## Negative cases

| Input under `examples/negative/` | Expected decision | Reason |
|---|---|---|
| `UNKNOWN_LOCATION.json` | NEEDS_INPUT | An unprovided endpoint must not acquire invented coordinates |
| `DATE_CONFLICT.json` | CONFLICT | Requested event date is outside the attached facts |
| `DURATION_CONFLICT.json` | CONFLICT | Text duration disagrees with exact supplied scene intervals |
| `INVALID_COORDINATE.json` | INVALID | Supplied longitude is 200 degrees |
| `MISSING_ATTACHED_DATA.json` | NEEDS_INPUT | Text alone does not contain authoritative source facts |
| `SCENE_GAP.json` | CONFLICT | Scene boundary leaves an uncovered frame |
| `UNSUPPORTED_ORBIT.json` | UNSUPPORTED | This extension has no connected orbit consumer |
| `UNSUPPORTED_DISSOLVE.json` | UNSUPPORTED | Only actual cut transitions are connected |
| `POLAR_PROJECTION_LIMIT.json` | UNSUPPORTED | The current flat renderer does not admit the polar range |
| `COUNTRY_COORDINATE_CONFLICT.json` | CONFLICT | Supplied country conflicts with the region coordinates |

## Executed evidence and scope

`reports/EXAMPLE_EVIDENCE_AUDIT.json`: **18 PASS / 0 FAIL** against actual retained bytes. It verifies locality source/file and feature hashes, the retained public-domain license hash, the existing country GIS archive, Japan/Australia country geometries, connections built only from supplied coordinates, original first-scene facts, unchanged historical inputs and the unchanged trusted-evidence registry.

`reports/EXAMPLE_NATIVE_COMPILE.json`: **8 PASS / 0 FAIL** through the unchanged native fact validator, Scene compiler/validator and engine-plan adapter. This covers the six main-demo scene inputs plus Japan and Australia. It establishes native compatibility only; it does not establish natural-language interpretation, source-envelope admission, actual draw or image quality.

`reports/EXAMPLE_MATRIX_ATTEMPT_1.json`: actual initial compiler/source-provider execution, **13 / 17 expected decisions matched**. Four inputs were blocked by the same confirmed scoped-camera-intent conflict: the global text described two distinct scene modes, while initial compiler handling applied the route-follow intent to every scene. These failures are retained, not relabelled PASS. The natural-language owner corrected scene-scoped intent handling; subsequent receipts preserve the retests.

`reports/EXAMPLE_MATRIX_ATTEMPT_2.json`: actual intermediate retest, **16 / 17 expected decisions matched**. Invalid longitude was still masked by an earlier ambiguity clarification. The compiler was corrected to retain unchanged validator errors instead of returning before structural validation.

`reports/EXAMPLE_MATRIX_ATTEMPT_3.json`: completed intermediate compiler/provider retest, **17 / 17 expected decisions matched**, **0 input hash mismatches**. Five valid inputs were accepted; twelve unsupported, conflicting, incomplete or invalid inputs were correctly blocked. The versioned CSV/trace retain this checkpoint's actual decisions.

Attempt 3 was the completed checkpoint before independent inspection found stale Germany-only `native_context` metadata in the newly authored Japan/Australia/Korea/Nepal fixture copies. That metadata was corrected to reference each fixture's own supplied country/location IDs; no coordinates or original baseline fixtures were changed. A separately approved presentation sidecar preserves the supplied matching initial state in fictional scene two. Two historical wrappers now explicitly bind their pre-existing legacy source selection. Before inputs and manifest are retained under `examples/archive/`, with individual provenance JSONs under `evidence/`.

`reports/EXAMPLE_MATRIX_ATTEMPT_4.json` is the **final frozen-compiler/source-provider matrix** after those corrections: **17 / 17 expected decisions matched**, **0 input hash mismatches**, **5 accepted / 12 correctly blocked**. The final CSV and `INPUT_TO_SCENE_TRACE.json` now reference attempt 4; their previous attempt-3 versions are retained separately. Historical partial-line rendering remains `UNSUPPORTED / FAMILY_NOT_CONNECTED`, while the historical missing-control example remains `NEEDS_INPUT`. `reports/EXAMPLE_EVIDENCE_AFTER_CONTEXT_FIX.json` adds locality/context coherence checks for **27 PASS / 0 FAIL**.

`reports/LEGACY_PROBE_COMPILER_ATTEMPT_1.json`: **5 / 5 PASS** for additional full explicit-region inputs under `examples/legacy-probes/`. These reuse the preserved Germany/Chile/Namibia facts and source-backed modern Seoul/Daejeon/Kathmandu/Pokhara coordinates. `examples/LEGACY_NATIVE_PROBE_REQUESTS.json` separately describes a direct provider-regression override to `{legacyProfileId: ...}` for exact old source/framing tests. The alias-only override is not advertised as accepted natural-language envelope syntax. No probe draw is claimed by this compiler receipt.

No test in this document is a video-quality or NVIDIA hardware PASS. Actual Studio drawing, complete MP4/frame inspection and user visual approval remain separate gates. No paid service is invoked by the fixture builder, evidence audit or example compiler matrix.

## Reproduction commands

Run from repository root with `PYTHONDONTWRITEBYTECODE=1`:

```text
python -B world-simulation-shorts-engine/recovery/universal-presentation-v2/tools/prepare_presentation_examples.py
python -B world-simulation-shorts-engine/recovery/universal-presentation-v2/tools/verify_example_evidence.py
node world-simulation-shorts-engine/recovery/universal-presentation-v2/tools/run_example_matrix.mjs EXAMPLE_MATRIX_UNIQUE_ATTEMPT.json
```

The builder reuses identical existing example bytes and refuses to replace a different existing input. Audit/matrix tools write exclusive new receipts; use a new report name for a new execution. The evidence audit receipt is intentionally exclusive as well. Example execution status lives in the separate receipts; `CASE_MANIFEST.json` retains preparation status and the hashes of the current authored inputs. Earlier input versions/hashes are archived with provenance. Do not delete an earlier receipt or original cache to force a successful run.
