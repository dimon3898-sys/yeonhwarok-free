# WORLD ENGINE — EVENT FEATURE BUNDLE V3: AREA & PROPAGATION

## Frozen scope and parent

This document freezes the next implementation bundle: **Area Reveal / Grow / Contract / Move / Hold + Propagation Ring/Wave + Impact Zone + Front Line + State Transition + Time Step**. It is a scope document, not an implemented Area engine, an executable schema, or a generated proof. No Area source, tests, data acquisition, or rendering is authorized by this document-writing step.

The next bundle extends the following saved Final through a separate V3 layer:

| Binding | Frozen value |
|---|---|
| Parent baseline | `EVENT_FEATURE_BUNDLE_V2_FLOW_FINAL_BASELINE` |
| Parent Final commit | `fbc3be89d94040271c7f54a051162913ad134bac` |
| Parent Final Manifest | `recovery/event-flow-v2-final/FINAL_MANIFEST.json` |
| Parent Final Manifest SHA-256 | `43f83ff77895ef8f4749b328a49a3acd0bb6b13667198347bb606e187efbe1e3` |
| Parent Flow source commit | `be428ab6dbe6723f8b3cc25a287c18a744a9c318` |
| Approved Flow media commit | `a0add53bc5d9182bf24a17ac9dd13e69129c9fa0` |
| Approved Flow validation commit | `4a1f773dcf377ebca5e46d83b81204707a56b59d` |
| Approved Flow MP4 SHA-256 | `5ff055643ded594198f3dc5e313d9acadb6b636d4f621294ad69456d4b6449fe` |
| Ancestor Event V1 Final | `EVENT_SYSTEM_V1_FINAL_BASELINE` / `f79f3d55d945ef0e53b03ac2ed666f48f28b5881` |
| Camera V5 Final | `29b8ee294360812b55ef577b62411de58159003b` |

Parent Final source, manifests, assets, fixtures, approved media, and tags stay immutable. V3 does not retune the approved Flow object, route, timing, occlusion, or Detail approach. Its default production standard remains `FACT_BASED_VISUAL_GRADE`.

## Purpose and common ownership

The bundle communicates how a **geographical footprint, front, or affected zone changes over time**. Tsunami, war/front changes, typhoon, and disaster coverage are possible data-driven uses of the same primitive family. They are not separate engines or built-in simulations.

The caller supplies the subject, geographical source, state sequence, event time meaning, and visual intent. The renderer does not infer a story or calculate physical spread. A propagation ring is a visual representation of a supplied front/extent; an impact zone is a supplied affected footprint. Neither establishes wave speed, inundation, casualty count, territorial ownership, or storm severity by itself.

The frozen ownership chain is:

**Authored AreaIntent → AreaPlan → AreaTimeline → pure AreaFrameState → V3 Area overlay / existing annotation primitives**.

V5 owns arrival and camera state. An explicitly admitted V3 Area Detail extension may own a short post-arrival approach. The Area evaluator owns only the event display state. Existing Renderer, Projection, Scale, Glyph, Universal Layout, Marker, Boundary, native Glow, and Final Occlusion remain separate owners.

## Ten integrated features

All ten features belong to one implementation bundle and one common data/timeline model. A particular proof uses a coherent subset appropriate to its factual subject; it does not run ten unrelated effects as a showcase.

| Feature | Required behavior | Semantic and implementation boundary |
|---|---|---|
| `AREA_REVEAL` | Introduce an authored Polygon/MultiPolygon footprint with a short readable appearance. | Reveal changes coverage/opacity, not the stored source geometry or the factual location. |
| `AREA_GROW` | Progressively expose more of a supplied footprint or progress through supplied expanding states. | A presentation mask may grow inside its declared footprint. Actual expansion claims require corresponding source states; no invented physical spread. |
| `AREA_CONTRACT` | Reduce displayed coverage or progress through supplied shrinking states. | Contraction is explicit input. It does not infer recovery, retreat, or dissipation from a decreasing graphic. |
| `AREA_MOVE` | Translate an authored display footprint along an explicit trajectory or select supplied geographical states. | Reuse existing route arc-length sampling where the input is a valid trajectory. Keep source geometry immutable; do not add storm/vehicle physics. |
| `AREA_HOLD` | Keep the completed footprint/front and information stable for a short readable window. | Integer-frame hold; no repeated blinking, drift, or effect restart. |
| `PROPAGATION_RING_WAVE` | Advance one restrained ring or authored wave/front contour through an explicit progression. | Geographic propagation uses authored geographic states, not the existing screen-space endpoint pulse as a false geographic radius. No tsunami/weather solver. |
| `IMPACT_ZONE` | Distinguish a source-defined affected zone and its relation to the event. | New Event overlay only. No explosion, destruction simulation, inferred damage, or unsourced number. |
| `FRONT_LINE` | Show a supplied boundary/front and its direction or dated state change. | Reuse V1 Line reveal for a legitimate LineString representation within its admitted capacity; do not rewrite the Route engine or pretend a filled area is a line. |
| `STATE_TRANSITION` | Move between explicitly supplied, ordered area/front states. | Prefer deterministic masks/crossfades or discrete sourced states initially. Do not morph unmatched polygon vertex indices or erase holes to force interpolation. |
| `TIME_STEP` | Evaluate the authored state sequence at deterministic frames with an explicit display-time mapping. | Display duration and real event timestamps are separate input meanings. No guessed dates, inferred real speed, or runtime clock dependence. |

Grow/contract/transition may be explanatory display operations or factual state changes. The intent must distinguish those meanings. A synthetic fixture cannot be marked verified production data, and an illustrative transition cannot become a measured real evolution through its style or label.

## Contract scope to implement next

These are named ownership concepts, not executable schemas generated in this scope step:

- **AreaIntent:** provenance/data mode, immutable area geometry, geographic anchors, source-defined states/fronts, optional explicit trajectory, operation roles, display-time meaning, optional fixed sourced metric, and caller-selected visual profile.
- **AreaPlan:** validated representation and topology, deterministic operation schedule, state/time bindings, full swept footprint, camera/projection binding, optional admission binding, resource/complexity budget, and protected reservations.
- **AreaTimeline:** explicit integer-frame beats and operation windows. It coordinates existing arrival/lock with V3 event beats without changing the old Event/Flow plans.
- **AreaFrameState:** random-access pure evaluation of the authored state, mask/coverage, transform, front progression, opacity, annotation visibility, and hold. It does not mutate source geometry, camera, native graphics, or the next evaluation.
- **AreaFraming/Admission:** the full polygon/front and its complete evolution are evaluated against safe view, protected information, available visual data, and semantic integrity. A single initial polygon or center point is insufficient for a moving or expanding event.
- **AreaOverlay/Annotation adapters:** separate Event-owned resources and conservative reservations. Existing measured glyphs and supplied metric meaning remain unchanged.

Input geometry preserves source parts, ring closure, holes, CRS, and source identity. Initially support ordinary regional Polygon/MultiPolygon footprints and explicit LineString fronts/trajectories. Invalid topology, unbounded transformations, unsupported wrapping/polar cases, and source complexity beyond an admitted renderer budget require explicit affected-feature handling before proof generation. They are not silently repaired, simplified, or cropped.

## Actual reuse and required new adapters

The current APIs were read from the saved implementation, rather than inferred from their names. Detailed limits and split conditions are recorded in [RISK_AND_REUSE.md](RISK_AND_REUSE.md).

| Owner/API | Reuse in V3 | Existing limit that V3 must respect |
|---|---|---|
| `event_contract_v1.mjs`: `freezeEventData`, `validateEventAnchor`, `compileEventIntent` | Immutable data and geographic-point validation; metric-only intent where appropriate. | EventIntent V1 supports line and/or metric. It does **not** accept a Polygon/MultiPolygon or a standalone Point event. |
| `event_timeline_v1.mjs`: `compileEventPlan`, `evaluateEventFrame` | Existing event primitives retain their own integer-frame timing. | Its named Line/Metric beats are not a generic Area timeline. V3 needs a separate coordinating timeline. |
| `event_line_v1.mjs`: `compileGeographicLinePrimitive`, `evaluateGeographicLineReveal` | Front Line and valid route/contour line operations reuse the existing arc-length evaluator. | Source LineString, direction, and geometry stay unchanged. No second Route reveal engine. |
| `flow_core_v2.mjs`: `compileFlowRoute`, `sampleFlowRoute` | Exact arc-length position/tangent for an explicit area trajectory, where compatible. | FlowPlan itself is a single-route/single-object contract, not a changing-area contract. |
| `renderer.mjs`: `polygons`, `triangulateRegion` | Reuse polygon decomposition/triangulation, including holes, in the new browser-side Area overlay. | Existing native Region material/coverage is not a mutable Event area API. New overlay resources do not enter or retune the frozen native scenes. |
| Renderer factory `screen` + V5 evaluated camera state | Use the actual factory transform, camera bounds, projection and lock state. | The V5 GPU wrapper holds its factory privately. A new small V3 integration bridge must obtain the unchanged factory's projection through a supported factory lifecycle; it cannot assume a private handle is exported. |
| `scale_contract.mjs`: `geometryBounds`, `fitGeographicExtent` | Bounds and aspect-safe extent fit for complete authored footprints. | Bounds calculation is not visual admission, topology validation, or a new Scale policy. |
| `scale_projection.mjs`: `geographicAtlasRecord`, `createGlobeProjection` | Existing source-preserving polygon projection machinery where its representation is admitted. | Polygon-capable projection does not make the existing Event Detail API polygon-capable. First proof does not add a new globe/polar/wrapped Area pipeline. |
| `visual_detail_admission_v1.mjs`, `detail_data_profile_v1.mjs` | Preserve Fact-based visual-grade decisions and old survey records. | Event Detail geometry validation is LineString-specific. Area request/admission must be separately typed; no proxy line or transferred certificate. |
| `camera_detail_approach_adapter_v1.mjs`: `detailSmootherstep`; existing V5 arrival/state | Reuse motion easing and the established arrival → approach → settle → lock ownership. | Existing compilation/evaluation binds a LineString EventPlan. Area approach requires a separate V3 extension, not a Polygon forced into the Final Line contract. |
| `glyph_atlas.mjs`: `createMeasuredGlyph`; `event_metric_v1.mjs` | Existing font, full measured glyph bounds, fixed sourced values and reveal. | No numeric facts or metric units are invented by the Area renderer. |
| `graphic_layout.mjs`, moving Layout/Graphic pass | Native measured labels, Marker, Title, safe-area and reservation ownership remain intact. | New Area information gets a separate candidate adapter. Existing graphics do not move to make room. |
| `event_layout_adapter_v1.mjs`: `chooseMetricPlacement`, `chooseRelatedMetricPlacement` | Peripheral annotation placement using measured bounds; related placement may consume explicit projected boundary paths. | Path support is not polygon-interior semantics. V3 must validate area/front relation and placement separately. |
| `event_style_v1.mjs` contrast helpers; frozen theme tokens | Read existing colors/material samples to choose a legible Event-only profile. | Native Region Color, Boundary, Glow and approved Line style do not change. |
| `flow_graphic_pass_v2.mjs`: native GL state capture/restore | Reuse established GPU state isolation for the new overlay when its context is compatible. | Existing Flow object/pulse shader is not an Area fill/propagation shader. |
| `event_occlusion_policy_v1.mjs` + native protected graphics | Preserve native reservations and strict text protection. | Its sole exception is Event Line ↔ Protected Marker. It grants **no Area ↔ Marker/Text exemption**. |

The V3 overlay must mask/protect every native Marker, Label, Title/Panel and existing Metric reservation conservatively. Its internal time/coverage continues behind protected graphics. It must retain native Boundary/Glow readability with an explicit composition or preservation strategy; painting over them and changing their style to compensate is excluded. Whole-frame blits, copied finished video frames, or replacing native terrain are excluded.

## Framing and visual rules

If the complete event evolution is already readable, use the current admitted view. All Area animation starts only after the required camera lock. The first integrated proof separates approach from event change; no metric or Area transition appears during an unsettled camera move.

If a closer view is needed, the future V3 Area admission contract assesses the complete swept footprint, all required states/fronts, safe area, protected information, data coverage and visible integrity. It retains `FACT_BASED_VISUAL_GRADE` and keeps the old `LOCAL_NOT_ADMITTED`/survey evidence intact. It does not reduce thresholds, force LOCAL, transfer a Line certificate, or use country/topic/coordinate exceptions.

The new Area Detail extension reuses V5 state and established short approach/settle/lock motion principles. It does not create a new Camera Director. If safely connecting the actual polygon footprint requires editing a frozen Camera/Renderer owner, split or defer **Area Detail approach** while keeping an admitted current-view Area proof available where possible.

Use one dominant Area footprint and one supporting front/ring or impact emphasis in the first real proof. Multipart components of one sourced footprint are permitted; crowd, traffic and multi-object simulations are excluded. Color, opacity, contour and finite halo belong to an explicit Event role/profile, chosen for mobile contrast without obscuring the geographic subject. No excessive neon, repeated pulses, arbitrary blink, test watermark, or explanatory development UI appears in the real Public Proof.

An extent must retain the whole geographical meaning across the complete state sequence. Presentation masking is not geographic crop. Protected-graphic masks must not make the event's remaining visible shape materially misleading; otherwise choose a different safe V3 layout/framing or block the affected event. Existing graphics stay fixed.

## Implementation order — frozen next work bundle

1. Verify the Flow V2 Final parent/source hashes and establish a new V3 development layer; do not rerun its completed data research or retune Final.
2. Record the actual reuse boundary above and perform the representation/projection/admission/overlay preflight. Separate unsupported parts explicitly before attempting a Core change.
3. Implement the V3 AreaIntent and AreaPlan contracts with source-preserving topology, authored state/time meaning, whole swept bounds and explicit operation roles.
4. Implement the coordinating AreaTimeline and pure random-access AreaFrameState evaluator. Reuse existing Line arc-length and trajectory sampling where applicable.
5. Connect current admitted camera state and actual native projection through the separate V3 bridge. Add typed Area Detail admission/approach only when it can be isolated without modifying Final owners.
6. Implement Event-owned Area fill/reveal/grow/contract/move/hold and state/time-step presentation, reusing existing triangulation. Keep native Region material/terrain unchanged.
7. Add restrained geographic propagation ring/wave, impact zone, and Front Line presentation. Reuse the existing V1 Line primitive where the representation/capacity permits it; do not add physical solvers.
8. Connect conservative native reservation masking, safe-area containment and optional sourced Metric/Glyph layout. Verify native GPU state restoration and no existing graphic relocation.
9. Run Synthetic A/B/C below plus focused negative cases. Check all ten feature behaviors across these fixtures before selecting a real subject.
10. Save passing implementation and required fixtures/profile assets to the development branch **before the long proof render**.
11. Select one factual real fixture with already available or quickly verifiable public geometry/state evidence. Preserve source/license/version/date/hash/CRS and distinguish actual states from illustrative presentation. Avoid a long data-investigation phase.
12. Generate one coherent integrated proof and native Checkpoints, inspect the actual decoded video, run focused protection checks, and correct only observed V3 issues.
13. Persist Candidate source/fixtures/data/profile/manifests/reproduction instructions and media; verify required temp-only files are zero and run Secret Scan.
14. Provide immutable MP4/PNG/SHA256SUMS mobile download URLs; verify HTTP 200 and downloaded SHA equality. Stop at `USER_VIDEO_REVIEW_REQUIRED`.

The implementation should advance through consecutive passing steps without asking for routine confirmations. Permanent Gate and Final promotion remain after user video approval. This scope-writing step does not execute any of the implementation/render steps.

## Synthetic and real proof strategy

| Fixture | Required focus | Expected evidence |
|---|---|---|
| Synthetic A — simple footprint | Reveal → grow → contract → impact emphasis → hold in an already readable view. | Explicit synthetic provenance; deterministic coverage; correct footprint/anchor; current-view decision; stable hold; readable contrast. |
| Synthetic B — irregular area | Irregular/multipart footprint with a hole where applicable; authored propagation states; Area state transition and time-step sequence. | Parts/holes preserved; no invalid topology or invented edges; entire state union visible; meaningful ring/front relationship; no mistaken physical claim. |
| Synthetic C — moving front | Area move along an authored path plus changing front near existing Marker/Label/Title/Metric reservations. | Arc-length/tangent continuity when reused; complete swept extent inside safe view; conservative graphic protection; uninterrupted internal evolution; no critical collision. |

Negative cases target invalid topology, full-evolution crop, unsupported wrapped geometry, invalid state order, excessive renderer complexity, false/unbound metric, stale detail certificate and protected text intrusion. They reject or isolate the affected V3 part; they do not relax the Final policy.

After Synthetic PASS, use one real fixture with a clear sourced location, footprint/front and time relationship. Choose it for a readable visual sequence, not to demonstrate every primitive simultaneously. A subject does not become eligible merely because it is named tsunami, war, typhoon or disaster. If no suitable factual fixture is promptly available, produce an explicitly Synthetic proof during the future implementation phase and record the real-fixture gap. Do not manufacture production evidence or prolong data research.

The real proof target is **8–12 seconds, 1080×1920, 30 fps, 9:16, silent**. Choose duration for perception and motion; do not force a predetermined frame count. Its information order is geographical arrival → optional short detail → lock → Area introduction → authored evolution/front → impact/state emphasis → information hold. Use native checkpoints for arrival/lock, initial area, main evolution, propagation/front, final state/impact, and hold as relevant. Checkpoints are exact native encoded-frame inputs.

## Quality and focused protection gates

Technical success requires deterministic frame/state evaluation, source geometry preservation, valid topology, full event/swept visibility, safe Area/annotation bounds, zero changed native protected pixels, no critical collision, no Final source changes and no fixture-specific Engine branch. Off-path delegation must preserve the old Final behavior. Run the full Permanent Gate once after user approval, not throughout small V3 visual changes.

Actual video quality must also pass: legible footprint/front, obvious progression direction, purposeful camera rhythm, coherent state/time order, restrained impact emphasis, clear Metric relation when present, appropriate hold, mobile contrast and no severe geographic/terrain corruption. A technically valid mesh alone is insufficient.

Block the affected feature or fixture for wrong location/relationship, fabricated states, materially false metrics, whole-event crop, severe visual corruption, critical protected-information intrusion or any required Final Camera/Renderer damage. Absolute GIS certificates, unmeasured small coastal errors, modest simplification and inherited mild terrain softness are warnings when factual and visible meaning remain intact. They do not trigger survey-grade research or automatic failure.

## Exclusions and split policy

Excluded: Planner/story inference, TTS, subtitles, BGM/SFX, tsunami hydrodynamics, weather/typhoon simulation, combat/weapon/explosion simulation, casualties/damage inference, traffic density, multi-object crowds, collisions/physics, new Camera Director, new base Terrain, native Region/Boundary/Glow restyling, Glyph/Universal Layout redesign, replacement Route engine and edits to either Final baseline.

The ten features remain the frozen bundle. If one unsafe capability needs a separate extension—such as wrapped/polar area projection, unmatched-topology morphing, Area-specific detail admission, or a front exceeding current Line capacity—record that precise capability and keep the safe common portion separate. Do not silently claim unsupported behavior, truncate data, generalize a Line-only certificate, or widen the change into Final Core. Any later scope change needs an explicit updated scope record.

## Delivery and stop condition

Future technical Candidate state: `EVENT_FEATURE_BUNDLE_V3_AREA_PROPAGATION_CANDIDATE`. User video approval remains required before Permanent Gate/Final promotion.

Candidate storage includes source, fixture/data provenance, visual profile, asset/source/dependency/import/hash manifests and reproduction instructions. Required temp-only files: **0**. Public Review contains **MP4 / PNG / SHA256SUMS only**, with immutable direct downloads and verified HTTP 200 / original-download SHA equality. Source, diagnostics and internal scope plans are not added to Public Review.

Current scope result: **`EVENT_AREA_PROPAGATION_V3_SCOPE_FROZEN`**. The parent Flow Final is already saved separately; this document and its companion risk/reuse record are the only V3 deliverables at this stage. No executable Area work or proof begins automatically.
