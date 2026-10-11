# Camera Director V1 — Suez Software WebGL2 Proof

1080×1920 · 30fps · 399 frames · 13.3 seconds · silent MP4.

Decision: CAMERA_DIRECTOR_PASS for this Suez motion proof. USER VIDEO REVIEW REQUIRED. No next Gate was started.

WORLD → CONTINENT uses an explicit 1.2-second GPU dissolve between the approved globe and map projections. This is not a globe/flat morph. CONTINENT → REGIONAL uses geographic-center and logarithmic-extent interpolation with C2 quintic easing. The camera stops at the approved Regional extent and never enters denied LOCAL.

| Time (seconds) | Camera state / information |
| --- | --- |
| 0–1.8 | WORLD CONTEXT |
| 1.8–3.0 | WORLD→CONTINENT projection APPROACH / dissolve |
| 3.0–3.6 | CONTINENT CONTEXT |
| 3.6–6.0 | APPROACH |
| 6.0–7.3 | DECELERATE |
| 7.3–7.9 | SETTLE; fixed camera, native Regional LOD settles |
| 7.9–8.1 | LOCK |
| 8.1–10.1 | Primary → Marker → Location/Country → Event Title |
| 10.1–13.1 | HOLD; no camera drift |
| 13.1–13.3 | NEXT-ready state; remains fixed, no new event |

Camera state and reveal state are separate and evaluated from integer frames. Primary fades through the existing GIS coverage input; Marker/Text have ordered full-opacity appearance steps. The verified scenario disclaimer stays visible. Event data does not change.

## Visual protection

All 14 existing map GLSL templates and all 8 protected Scale/Layout/Color/Boundary/Glyph/Admission modules are byte-identical to the pre-task snapshot. Camera methods only change framing, approved Scale widths/sizes and role visibility. No Terrain/DEM/Lighting/Material/palette tuning was performed.

The full Reveal and Hold PNGs are byte-identical to the approved REGIONAL PNG: `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673`. Changed pixels: **0**. The measured Layout has zero text/Boundary collisions and zero safe-area violations. No premature Marker/major labels, GL errors or LOCAL frames occurred in the 399-frame diagnostic.

All encoded frames were decoded and inspected through phase frames and pixel continuity evidence. There are no black transition frames. Hold has identical source pixels; small decoded differences are H.264 compression noise.

## Reference and scope

The existing actual 64306 reference was audited (reference MP4 SHA-256 `853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc`). This proof implements the user's specified broad-context→approach→settle→reveal→hold grammar; it does not claim literal reference-keyframe reproduction.

The input fixture uses real Suez GIS and its existing anchor. Core camera/pipeline code has no Suez coordinate branches. REGION_SHAPE, RELATION, EVENT_LOCATION and SAFE_CLOSEST intents resolve actual geometry and calculate candidate framing. V1 execution stops at the approved REGIONAL extent; a target that does not fit is explicitly diagnosed rather than claimed to be fully framed. Other-region motion and arbitrary wider target endpoints are not validated by this proof.

Frame telemetry records pure Camera center/extent, velocity, easing, reveal and admission. During dissolves, `gpu.actualCamera` describes the FROM factory; the blend-to camera is described by the pure camera/transition plan, not separately measured. `gpu.boundaryPixels` contains motion-size intent, not measured WORLD ribbon widths. Approved per-factory widths remain available in the evidence.

## Focused validation

Final checks: **PASS 153 / FAIL 0 / ERROR 0 / SKIP 1** (RTX4080S prohibited).

An initial new transition-pass GLSL attribute-name conflict produced no frames and was corrected. Two initially exact cross-runtime floating comparisons differed by at most 1.42e-14 degrees and 2.27e-13 pixels. Their original failures are preserved; only those numeric comparisons use an explicit 1e-10 tolerance. Pixel equality remains exact.

No full legacy regression, Container, gCube/RTX, Event Simulation, route animation, audio/TTS, planner or production was executed. Release CI only checks and publishes the existing file bytes; it performs no rendering or build.
