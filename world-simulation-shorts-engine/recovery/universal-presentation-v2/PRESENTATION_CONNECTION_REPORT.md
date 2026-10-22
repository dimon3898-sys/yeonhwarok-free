# Connected presentation path V2

This opt-in extension consumes authoritative Scene JSON and a validated presentation sidecar. It does not replace or edit Camera V5, Flow V2, Area V3, Event V1, the native renderer, the G2 layout extension, shaders, or encoding code. Its software proof uses Chromium SwiftShader only.

| Control | Actual consumer and constraints |
|---|---|
| Camera KEYFRAMES | Unchanged `compileReferenceCameraTrack` and `evaluateReferenceCameraTrackFrame`; supplied integer-frame centers and zooms. Zoom 1 is the approved closest regional viewport; values below 1 widen it. The final endpoint must be the closest endpoint, as the existing adapter requires. |
| Camera ROUTE_FOLLOW | Existing Flow temporal fractions and arclength sampler provide display framing anchors from the supplied route. Existing reference camera interpolates those keyframes. This is bounded framing, not physical flight dynamics. Entire route and all current primitives must remain safe; unsafe requests fail. |
| Route/object animation | Existing Flow compile/evaluate timing runs at a genuine frozen, settled V5 analysis camera. Its fractions are composed with current factory projection and the unchanged Flow GPU pass. The current camera remains unlocked. New moving-projection admission is explicit; old Event admission is never claimed for the moving camera. |
| Territory colors | Existing Area GPU pass receives an explicit per-source-state palette. Authored polygon/front coordinates and transition frames remain exact. |
| Territory growth/contraction | Existing Area state timeline consumes the supplied successive polygon states. This is the existing state transition/crossfade representation, not newly generated occupation coordinates or a physical territory solver. |
| Event/location emphasis | Existing native marker design is positioned at supplied location IDs; a bounded size pulse follows the supplied frame interval. No new geography or text labels are invented. |
| Scene transitions | Exact CUT at every authored scene boundary, with one encoder stream and no duplicate or missing frame. Dissolves/orbits/unsupported effects are rejected. |
| Already visible initial state | Explicit `initialStateVisibility: "PRESERVE_PROVIDED"` recompiles the unchanged public Area plan with `AREA_REVEAL` and `FRONT_LINE` endpoints `from=1,to=1`. It preserves the original frame clock, state transitions and source geometry. A continuing cut requires exact previous-final/next-first geometry, front, source and explicit color agreement. The default `REVEAL` keeps old behavior. |

## Confirmed integration defects found before movie production

1. Arbitrary topic/location strings replaced the native seed strings without regenerating their measured glyph assets. The factory rejected `TEXT_EXCEEDS_MEASURED_BOUNDS`. The regional adapter now preserves the original text/glyph pair. Visible scene labels are explicitly unsupported in this profile; scene names remain metadata. No layout guard was disabled.
2. A reference-camera plan compiled in Node acquired a one-ULP derived coefficient difference when the unchanged canonical checker recompiled it in Chromium: `segments.1.to.3`, `3.053731205363982` versus `3.0537312053639822`. The consumer now recompiles the unchanged camera adapter from identical authored keyframes in the consuming browser realm. Every browser frame bound is compared with its original CPU-planned bound; drift above `1e-9` degrees fails. The strict owner canonical check is retained.
3. A fresh second Area scene restarted the existing reveal at opacity zero. Independent actual-frame inspection observed the supplied wide state disappear immediately after CUT. The new explicit already-visible mode uses the owner's existing operation API after source-state continuity checks. No preroll, negative frame, hidden time offset or new territory is used.

Actual source coverage, geographic projection, route/object/pulse footprint, marker reservation, GPU draw status, readPixels differences and GL errors are checked at draw time. A source-qualified preflight is not reported as a completed video. Actual probe and Studio movie outcomes are reported separately by their receipts.

## Limits

The profile is a free, 2–240-frame software preview at 1080×1920/30fps. It supports no paid GPU/API execution. Semantic labels are metadata, not visible text. Source coverage, native resolution, source attribution and licensing are recorded exactly; a global RGB fallback is not claimed to be DEM or baked relief. Final visual quality requires user review. Existing long-production and approved paths remain unchanged.

## Final pre-production evidence

- `reports/PRESENTATION_TESTS/RESULTS.json`: 40 focused tests PASS (23 contract/admission tests and 17 preparation/cache/continuity tests). Direct Node execution reports actual test counts.
- `reports/E_DRAW_REGRESSION_RESULTS.json`: all five preserved regional profiles plus Japan and Australia passed actual SwiftShader draw/readPixels at frames 0, 44 and 89. All 630 derived camera frame bounds were compared with CPU samples; only 21 frames were actually drawn in these seven probes. No full-video claim is made for those probes.
- `reports/AREA_CUT_CONTINUITY_PROOF.json`: five actual frames establish the continued supplied Area remains visible at frames 89→90→91; source geometry, front and explicit color match. Frame 90 now has alpha 1, coverage 1, front reveal 1 and 136,120 changed feature pixels. The authored camera CUT still changes the view.
- Original failed probe outputs were preserved privately. The initial exact-legacy Chile request legitimately exceeded its original source crop: its camera used an event anchor instead of the original framing center. The explicit regression descriptor now uses the actual original framing center and supported camera extents. No user framing semantics were silently changed.
- The source provider initially cropped only the moving envelope, while the unchanged factory also needs the approved initialization/analysis viewport. The provider now qualifies the union, and original safe-coverage checks remain active.
- Native label glyph binding, genuine V5 recognition start, source-union coverage, strict camera hydration, and explicit already-visible Area operations were all repaired in the new extension files. No original renderer, camera, shader, Scene, asset or cache was edited.
- The final compiler received a later validation-only change after the seven probes began. `compilerEquivalence` in the region report proves the current compiler emits exactly the same source input hash and actual Scene/region/presentation data for all seven recorded probe inputs. All rendering-code bindings remained unchanged.

Actual Studio movie production is a separate subsequent gate. The probe PNGs and safe source credits are under `reports/E_DRAW_PROBES/`; their SHA256SUMS binds the original captured bytes. No final video-quality approval is asserted.
