# Camera Director V1

`camera_director.mjs` owns a pure camera timeline and a separate visual reveal
timeline. It does not render, generate a story, mutate GIS, change material or
layout design, or admit LOCAL detail. Its input is the three approved compiled
WORLD, CONTINENT and REGIONAL Scale plans and their source/admission evidence.
The final stop is the exact approved REGIONAL geographic bounds.

## API and input contract

`compileCameraPlan({ world, continent, regional, localAdmission, target,
measuredLayout, seed, profile })` returns a deeply frozen, deterministic plan.
All three plans must use the same verified Scene anchor and canonical
1080×1920 output. WORLD must be the approved orthographic globe; CONTINENT and
REGIONAL must use the approved regional equirectangular projection.

`target.intent` accepts `REGION_SHAPE`, `RELATION`, `EVENT_LOCATION` and
`SAFE_CLOSEST`. Region/relation/event bounds come from actual GIS records selected
by `geometryIds`; optional `eventGeometry` supplies verified event records. A
Point event anchor remains a Point: no made-up geographic area is substituted.
The compiler assesses geometry, marker size, canonical safe area and, when
provided, measured final label ink boxes. It records the geometric closest-fit
candidate and whether the target fits the approved stop. It does not claim a
shape or relation fit when the actual target exceeds that safe area.

`measuredLayout` accepts the real Renderer evidence `layout` array, or an object
with `items`/`layout`. If no measured glyph bounds are supplied, the diagnostic
records that gap; the actual measured Universal Layout remains authoritative.

`localAdmission` accepts the existing `localDetail` object or the admission
result. A requested LOCAL target is explicitly stopped at REGIONAL. This V1 has
no LOCAL stage even if some other Scene has adequate local data. A supplied safe
closest extent must match the approved REGIONAL stop; inconsistent inputs fail
rather than quietly reframing the approved output. The current denied LOCAL
result is preserved as a data-admission diagnostic, not a Renderer failure.

## State and motion profile

The integer-frame states are `CONTEXT`, `APPROACH`, `DECELERATE`, `SETTLE`,
`LOCK`, `REVEAL`, `HOLD` and `NEXT`. At the default 30 fps profile:

| Frames, inclusive | State | Action |
| --- | --- | --- |
| 0–53 | CONTEXT | Fixed approved WORLD context |
| 54–89 | APPROACH | Explicit WORLD→CONTINENT projection dissolve |
| 90–107 | CONTEXT | Fixed approved CONTINENT recognition |
| 108–179 | APPROACH | Geographic center and log-extent approach |
| 180–218 | DECELERATE | Remaining portion of the same smooth curve |
| 219–236 | SETTLE | Exact REGIONAL stop, information still hidden |
| 237–242 | LOCK | Camera locked, information still hidden |
| 243–302 | REVEAL | Sequential information reveal, camera fixed |
| 303–392 | HOLD | Camera and final measured layout fixed |
| 393–398 | NEXT | Fixed view; readiness only, no automatic next event |

The initial proof is 399 frames / 13.3 seconds. Hold duration derives from the
actual title, location and country grapheme count and a profile reading speed,
with a three-second minimum. It is not stretched to meet an arbitrary duration.
The `profile` owns recognition, travel, settle, lock, reveal and reading timing;
timing/easing adjustments do not alter approved visual tokens.

The camera profile uses the explicitly defined quintic curve
`6t⁵ − 15t⁴ + 10t³`. Its velocity and acceleration are zero at both endpoints.
CONTINENT→REGIONAL interpolates geographic center and logarithmic geographic
width/height using that single curve; DECELERATE is a state within that motion,
not a separate curve that causes a speed discontinuity. Both endpoint frames are
exact. Intermediate extents cannot be smaller than the final approved extent.
Hold drift is disabled. Camera evaluations never accumulate deltas.

## Projection transition

WORLD→CONTINENT is an explicit 36-frame GPU cross dissolve of the two fixed
approved projection views with the same quintic progress. Both views are
available throughout the transition; the contract forbids an intervening black
frame and a hard cut. This is a visual transition, not a globe-to-flat geometric
morph. Its diagnostic records that distinction. Marker and labels are hidden,
so no geographic marker is interpolated between incompatible projections.

## Separate reveal contract

The camera is at its final stop for SETTLE and LOCK before reveal begins.
Reveal stages, inclusive, are:

| Frames | Role |
| --- | --- |
| 243–254 | Primary region |
| 255–266 | Geographic marker |
| 267–281 | Location and country labels |
| 282–302 | Event title and its contrast panel |

Each stage evaluates its own smooth opacity. A later stage does not start before
the previous stage completes. Secondary geography remains context. Only an
actually present verified Scene disclaimer is visible throughout. No event
state, route, TTS, audio or story content is created or changed.

The Renderer measures the final REGIONAL Universal Layout once and reuses those
placements as information appears. Hidden text is not continuously relaid out
during camera movement. Marker drawing always uses the actual geographic
anchor, never a camera-relative guessed position.

## Evaluation and evidence

`evaluateCameraFrame(plan, frame)` only accepts an integer in
`[0, plan.totalFrames)`. It returns:

- Frame, time, state, state key, state progress and effective Scale/projection.
- Target intent/geometry IDs, geographic center/extent and the unchanged anchor.
- Geographic center velocity and logarithmic extent velocity, in units/second.
- Motion easing progress, explicit transition mix and settle/lock status.
- Separate primary/marker/location/country/title/disclaimer reveal values.
- Fixed world and current flat camera inputs, admission result and layout lock.

The default checkpoints are WORLD 0, CONTINENT 99, REGIONAL_SETTLE 236, REVEAL
302 and HOLD 348. All frame decisions depend only on the compiled Scene/data,
seed, profile and integer frame; wall-clock rendering speed does not affect them.
Plan source bindings record existing Scale, Renderer, GIS and asset identities;
the proof driver records cryptographic source/plan hashes and GPU diagnostics.

## Scope boundary

This V1 is one silent Software WebGL2 camera proof. It preserves the existing
Renderer Pixel Pipeline and visual design, does not implement Camera Director
story planning, Event Simulation, LOCAL detail, animation production, TTS,
containers or paid GPU execution. A successful technical run is still subject
to user video review before any next development stage.
