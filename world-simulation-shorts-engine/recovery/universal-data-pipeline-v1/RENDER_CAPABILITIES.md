# Renderer reuse audit

Baseline: `e39969cbc76a071d34a38440d9551425e6d5e545`. The existing-code and persisted-asset findings below were established by read-only inspection. No existing source was changed and no NVIDIA or visual-quality result is claimed. The new opt-in `generic_runtime.mjs` and `capture_generic.mjs` now implement the bounded WAR/TRANSPORT composition described here; actual draw/video evidence is recorded separately from this API audit.

## Existing APIs and exact connection points

Paths below are relative to `world-simulation-shorts-engine/`.

| Input or capability | Existing entry point | Actual contract and limitation |
|---|---|---|
| Map GIS, base material, geographic projection | `web/map_infographic_v1/renderer.mjs:345`, `createMapInfographicRenderer({canvas,plan,width,height,terrainTreatment,heightSource,outputRenderer,outputTarget,layoutPlan,contextTerrain,contextGeometries})` | Uses a real WebGL2 context. Canonical aspect is 1080:1920. Optional shared Three renderer is supported. No fake preview fallback. Source geometry records and source asset descriptors must already exist. |
| Same projected position for map and all overlays | `renderer.mjs:677`, factory `screen([longitude,latitude])` | Reuse this function for every Area, Flow, marker and audit coordinate. A second hand-coded screen transform would risk misalignment. |
| Per-frame map and safe camera updates | `renderer.mjs:560`, `updateCamera(bounds)`; `renderer.mjs:595`, `renderFrame(options)` | Flat camera bounds only; cannot zoom closer than the admitted regional endpoint. `dem:true` fails without a qualified height source. Base `renderFrame({mode:1,graphics:false,boundaries:false,glow:false,primaryMaterial:1,...})` is already used by G2's overlay composition. |
| Camera planning | `camera_director_v5.mjs:146`, `compileMinimumContextIntent(scene,{relationGeometry})`; `:296`, `compileMinimumContextPlan({scene,intent,profile,seed,relationGeometry})` | Data includes primary geometry, event anchor, final/start extents, output and safe area. Camera V5 decides actual admission. Required relationship geometry is explicit; country names do not imply it. |
| Camera frame state | `camera_director_v5.mjs:304`, `evaluateMinimumContextCameraFrame(plan,frame)` | Returns real flatBounds, projection, admission, `cameraLocked` and `settle.locked`. Event/Flow require **both** lock flags. Natural motion arrival alone need not mean settled lock. Freeze an actual admitted final source frame during route travel; do not invent readiness flags. |
| Polygon validation and provenance | `area_core_v3.mjs:85`, `validateAreaGeometry`; `:137`, `compileAreaIntent` | Polygon/MultiPolygon with original rings and holes; rejects crossings, invalid holes and overlapping parts. Maximum 4096 vertices per geometry. Actual observed states and illustrative visual progression are distinct semantic modes. |
| Area animation | `area_core_v3.mjs:256`, `compileAreaPlan(intent,{fps,start_frame,total_frames,operations})`; `:354`, `evaluateAreaFrame(plan,frame,{project})` | Existing reveal/grow/contract/move, supplied state changes, fronts and hold. Exactly one final `AREA_HOLD`; total frame count must equal the complete operation endpoint; maximum 1200 frames per plan. Observed historical polygons must not be invented or radially revealed as if those intermediate extents were observed. |
| Area/front GPU pixels | `area_overlay_pass_v3.mjs:114`, `createAreaOverlayPass({canvas,width,height,style})`; returned `draw({controls,project,safeArea,protectedGraphics,...})` | Uses the same WebGL2 canvas and restores native state. Caller supplies explicit colors and authentic controls. Supports polygon fill and original frontier line primitives, not inferred shared borders. |
| Frontier supplied geometry | `area_core_v3.mjs:182`, `compileAreaLinePrimitive({geometry,source,direction,style_role,data_mode},{project})` | Uses existing geographic line engine. New projected primitive is needed if camera projection changes; stale front projection is rejected by the pass. |
| Event line/metric data | `event_contract_v1.mjs:68`, `compileEventIntent` | Requires a line and/or metric. `PRODUCTION` requires supplied verified provenance; `SYNTHETIC_TEST` requires explicit synthetic provenance. A source string alone does not independently verify historical truth. Wrapped antimeridian line segments are rejected. |
| Event timing/readiness | `event_timeline_v1.mjs:27`, `compileEventPlan(intent,{fps,profile,seed})`; `:64`, `evaluateEventReadiness`; `:101`, `evaluateEventFrame` | Integer-frame controls and immutable source data. Requires actual admitted locked camera, unchanged projection, safe area and protected boxes every frame. Optional primitives omit their own beats. |
| Authored route and object | `flow_core_v2.mjs:58`, `compileFlowIntent({data_mode,route_geometry,route_source,start_anchor,end_anchor,direction,object_role,object_graphic})` | Endpoint anchors must equal the directed original LineString endpoints. Object is a caller-supplied vector graphic. Flow does not invent aviation or navigable shipping paths. |
| Route timing | `flow_core_v2.mjs:106`, `compileFlowPlan(intent,options)` | Options: fps, start_frame, reveal_frames, direction_start_frame, object_start_frame, travel_frames, departure_pulse_frames, arrival_pulse_frames, hold_frames. Total local frames = object_start_frame + travel_frames + arrival_pulse_frames + hold_frames. Route reveal must finish before hold and must not be overtaken by the moving object. |
| Arc-length motion and heading | `flow_core_v2.mjs:145`, `compileFlowRoute(intent,{project})`; `:169`, `sampleFlowRoute(primitive,fraction,{lookAheadPixels})`; `:191`, `evaluateFlowFrame(plan,frame,{primitive,eventContext})` | Position follows original projected-route arc length; heading uses secant/tangent lookahead and unwrapping. Motion uses smootherstep display timing. This is **not** physical km/h or historical movement interpolation. Real-world speed needs an explicit validated time-to-display mapping. |
| Route line, direction, object and endpoint pulses | `flow_graphic_pass_v2.mjs:233`, `createFlowGraphicPass({canvas,style,width,height})`; `draw({primitive,controls,safeArea,protectedGraphics,flowIntent})` | Shares native WebGL2 canvas; full native GL state captured/restored. Object width24..80px and height12..80px; 1..8 polygons; 3..12 points/polygon; up to 64 protected reservations. Full route/object/pulse footprint must fit admitted safe area. |
| Route contrast | `event_style_v1.mjs:95`, `selectEventLineStyle({role,theme,primaryMaterialColor,backgroundSamples})` | Reuses existing native width/glow tokens and optional real framebuffer samples. Does not change geographic geometry. Missing actual samples are explicitly reported as material-color fallback. |
| G2 layout recovery | `recovery/g2-final-recovery-v1/layout_extension.mjs:13`, `validateLocationPlacementPolicy`; `:51`, `buildMeasuredGraphicLayout` | Explicit policy `WORLD_ENGINE_LOCATION_PLACEMENT_POLICY_V1 / BOUNDED_GAP_SEARCH`, maxGap<=20% of minimum output dimension, step4..32. Reuses original glyph measurement and original 8px primary-boundary clearance. No label deletion or collision-check bypass. Policy absent gives exact old behavior. |
| Dynamic layout audit | `layout_extension.mjs:84`, `auditRuntimeLayout({plan,screen})` | Reuses the same factory glyph callback and current native projection; diagnostic only. It does not prove a hidden label was drawn. G2 native runtime hides location/country/title labels during its supplied-zone demo. |
| Existing native glyph/marker drawing | `graphic_motion_pass_v4.mjs`, `createMovingGraphicPass({renderer,factory,width,height})` | Existing native glyph artwork can be drawn from approved layout data. Arbitrary military units or flags are not inferred from a place or route. A new common adapter should draw only explicitly supplied marker data it actually supports. |

## Why the old G2 DEMO is not a general prompt renderer

`recovery/universal-source-pipeline-v2/native_runtime.mjs:24` validates a supplied owner-mask/shared-front frame sequence, 1..8 actor colors, a single event location equal to the native anchor, no custom annotations, and only four numeric style fields. It always builds a `SYNTHETIC DEMO` caption and a native event-point marker. It does **not** consume arbitrary routes, airport/port records, user-authored Event intents or topic-specific optional fields.

`recovery/g2-final-recovery-v1/source_contract.py:69` delegates to the preceding recovery normalizer. `recovery/g2-renderer-recovery-v1/source_contract.py` deliberately restricts the submitted semantic source to the registered six-second fixture. These are appropriate reproducibility gates for that fixed G2 test, not a universal topic contract. Do not weaken them. Add a new versioned contract and a small new composition consumer while preserving these paths.

The higher `createFlowGpuAdapter` in `flow_gpu_adapter_v2.mjs:15` additionally binds Flow to the existing detail-camera adapter and exact route/event geometry. It is reusable for that established scenario. A smaller general consumer should compose the unchanged `createMapInfographicRenderer` + Area/Flow core/pass functions directly. The Flow pass already shares the native canvas, so the new consumer does not need to expose or modify a protected renderer's internals.

## Persisted seed and source-native styles

There is no need to depend on `/workspace/exact-65422-capsule-*` or redownload the global TIFF to prepare the audited regional demos.

`recovery/g2-final-recovery-v1/fixtures/GENERIC_REGION_INPUTS.zip` is persisted in the repository. SHA-256: `29806402e97db3a97cb4f3b95d6851d9bca62810ccbfb29199592ad49b9dd22b`. Each `<case>/RECOVERY_RUNTIME.json` contains a full nativePlan with **242 country GIS records**, sourceStyle, sourceBindings and actual Camera V5 plan. These saved inputs are seeds, not a substitute for the user's supplied topic data.

| Seed member | Source-native asset bounds `[west,south,east,north]` | Persisted PNG |
|---|---|---|
| `europe_germany/RECOVERY_RUNTIME.json` | `[-6.133333333333326,27.866666666666667,26.133333333333326,74.13333333333333]` | `g2-final-recovery-v1/assets/terrain/europe_germany_ne1_native.png` |
| `korean_peninsula/RECOVERY_RUNTIME.json` | `[109.86666666666667,12.86666666666666,142.13333333333333,59.13333333333333]` | `g2-final-recovery-v1/assets/terrain/korean_peninsula_ne1_native.png` |
| `namibia_desert_coast/RECOVERY_RUNTIME.json` | `[-1.1333333333333258,-45.133333333333326,31.133333333333326,1.13333333333334]` | `g2-renderer-recovery-v1/assets/terrain/namibia_desert_coast_ne1_native.png` |
| `nepal_himalaya/RECOVERY_RUNTIME.json` | `[69.86666666666667,5.86666666666666,100.13333333333333,52.13333333333333]` | `g2-renderer-recovery-v1/assets/terrain/nepal_himalaya_ne1_native.png` |
| `south_america_chile/RECOVERY_RUNTIME.json` | `[-114.13333333333334,-59.133333333333326,-61.86666666666666,-13.86666666666666]` | `g2-final-recovery-v1/assets/terrain/south_america_chile_ne1_native.png` |

Natural Earth I source and derived crops are marked Public Domain; the native pixel spacing is 1/60 degree. Read the matching saved receipt, not a guessed extent. Every actual camera viewport must remain within the selected source with at least one native pixel of gutter; the original crop preparer uses eight. The preparation's current max texture dimension is4096, while actual capture validator permits saved asset dimensions up to8192. Do not reinterpret those as arbitrary source-resolution guarantees.

The four native asset bindings for the Germany saved seed were read and hashed during this audit: terrain, global RGB (`88ab060b...`), topo proxy (`839b12da...`) and font (`da1f4484...`) all match their saved exact hashes. This verifies persisted bytes, not GPU upload or visible output. The topo asset remains a relief proxy, not a newly qualified DEM.

Core scale code includes WORLD globe and CONTINENT paths (`scale_contract.mjs:166`), but an approved regional NE1 crop cannot support an arbitrary worldwide route. The global RGB source is a different visual source; silently falling back across a regional crop would reintroduce the G2 seam. Either stay within a qualified style extent, implement and independently validate an explicit single-source world style, or return `UNSUPPORTED` for that requested render extent. Antimeridian-wrapped flat routes are explicitly unsupported by the preserved Event contract.

## Minimal proposed common connection

1. A new validated, versioned submission separates `data` from `renderSettings`. Legacy submissions still dispatch to their old consumer unchanged.
2. Resolve a saved source-style seed and verify all actual bytes before use. Clone only in memory; preserve old archives and receipts.
3. Compile an actual Camera V5 plan from explicit supplied geometry, anchor, extent and profile. Compute every camera frame with V5.
4. Create the unchanged native map factory. Use `factory.screen` for every feature.
5. For explicit supplied polygon observations, compile Area V3 intent/plan and render original polygon controls. For routes, compile Flow V2 intent/plan and render only during a genuine admitted locked camera interval.
6. Render native base, then exact supplied feature layers, then protected native markers/glyphs. Do not paste another finished image over the map.
7. Expose frame diagnostics including source input IDs, geometry hash, source time, display frame, camera state, projected points and actual draw owner. A different topic must change inputs and evidence, not dispatch to another fixed fixture.
8. Invoke this consumer from the real authenticated Studio job path with claims, bounded subprocess, existing FFmpeg and verified output storage. A direct browser probe alone does not satisfy actual Studio integration.

Example canonical Flow payload accepted by the **existing core** (not a proposed freeform prompt grammar):

```json
{
  "data_mode": "SYNTHETIC_TEST",
  "route_geometry": {"type":"LineString","coordinates":[[8,49],[10,51],[12,52]]},
  "route_source": {"source_type":"SYNTHETIC_TEST","source_reference":"Explicit illustrative connection supplied by the test author; not an observed flight","verification_status":"SYNTHETIC_TEST"},
  "start_anchor": [8,49], "end_anchor": [12,52], "direction":"FORWARD",
  "object_role":"ILLUSTRATIVE_CONNECTION",
  "object_graphic": {"width_px":24,"height_px":24,"polygons":[{"points":[[-0.4,-0.3],[0.4,0],[-0.4,0.3]],"color":[0.1,0.9,1,1]}]}
}
```

It remains a synthetic display test even if the underlying place coordinates are real. A source/reference label does not turn a fabricated route into an observed airline service or sea-navigation path. Timing can use `{fps:30,start_frame:0,reveal_frames:12,direction_start_frame:6,object_start_frame:12,travel_frames:30,departure_pulse_frames:6,arrival_pulse_frames:6,hold_frames:12}` for a 60-frame local Flow plan, after safety/admission validation. This audit did not execute that example.

Three proposed short demonstration subjects can reuse the same consumer: (1) explicit fictional supplied polygon states, (2) supplied illustrative airport-node connection, (3) supplied illustrative port connection. The latter two must identify whether geometry is an abstract connection or an actual sourced path. They exercise three subjects but only two top-level validation classes (fictional/general), so do not falsely claim a historical render was verified. Korean War and Roman Empire examples may remain `NEEDS_INPUT` for unsupported historical territory claims while independently qualified event/location scenes are checked separately.

## Unsupported until independently connected and verified

- Free natural-language historical research or unbounded AI planning.
- Exact historical front/ownership inferred from event dates, country borders or modern GIS alone.
- Real speed, travel duration, airline frequency, trade tonnage or physical simulation inferred from display motion.
- Navigable sea paths inferred from port endpoints alone.
- Generic arbitrary annotations in the existing G2 native runtime.
- Global source continuity or antimeridian line wrapping inferred from regional tests.
- Arbitrary external textures, NoData/DEM qualification or unbounded zoom.
- NVIDIA validation, final visual quality, Dropbox external-delivery success or actual Studio rendering based solely on this read-only audit.

## Subsequent actual pixel proof

After PHASE A–E and protection gates passed, `tools/probe_input_pixels.mjs` drew frame45 twice with Chromium SwiftShader: the supplied Germany aviation example and one expressly modified synthetic middle route vertex. Both used the same qualified native source and exact camera. Native-map `readPixels` SHA-256 stayed `afe7ca3a8ca06b7a016adc414712a3b19aa6f43b1990c058b753c7d50d0fb217`; final pixel SHA changed from `9918252a7d22bfe61fcd9c41cd918dbed7b87148572350cfde7a410fb57c5f48` to `ef83de02967256511c329fd8cd8a7a69fdb0af69e691d86555531722cc8fcf88`. Actual feature-changed pixels were4537 and4665, and the existing Flow pass reported route and moving-object draws. The actual original PNG was visually inspected; this confirms this supplied route reached pixels, not final video quality.

Evidence: `reports/PAIRED_RENDER_PROBE_REPORT.json`, `reports/paired-input-probe/PAIRED_PIXEL_PROOF.json`, and the public actual-frame comparison. These two probes are not an authenticated Studio video claim. The separate Studio production-path tests and full demos must establish that connection.

The first default-sandbox attempt was blocked at local `127.0.0.1` HTTP listen with `EPERM`; no browser draw occurred. The supported `require_escalated` execution successfully ran the identical free local code. Both private attempt directories were preserved. No external GPU, paid service, or security-bypass code was used.

One subsequent real Studio attempt exposed a separate serialization defect before drawing: Python's sorted JSON changed geometry object member order while the preserved `validateScenePlan` checks canonical geometry with `JSON.stringify`. The new Studio adapter now preserves the compiler's immutable Scene wire JSON as a string, binds both semantic and raw-wire SHA-256, and verifies equality before the worker writes the exact wire. The strict original validator and all rendering modules remain unchanged. Real compiler → private persistence → wire → strict native payload tests cover all three new example subjects and wire tampering. Full Studio demo results are recorded by their own execution report.

The bounded profile keeps a real final admitted Camera V5 state locked. It supports source-native regional views, explicit supplied Area/Flow features, supplied point markers with the existing native design, and source/camera/frame evidence. Marker/locality labels and moving-object profile identifiers are semantic metadata; visible arbitrary text is explicitly unsupported. Pixel color comes from the supplied vector graphic and existing native feature styles, not an automatic named aircraft/ship preset. Physical travel speed, global source coverage, arbitrary camera movement, visible arbitrary labels, LINE_METRIC/DISASTER pixel consumers, and causal-contact tracks remain explicitly outside this new preview profile.
