# Production V3 scene contract

`scene_planner.py` adds a chapter/evidence layer to the frozen universal V2
planner, contracts and native data binding. It verifies the parent manifest
`982cf2c0a5f435afe936605c0aeb76cbf40b6990da41d27c0ea0bd5ef22eb756`
and imports the unchanged original Python and Node planners. No old file is
rewritten. `build_scene_plan()` and `validate_production_plan()` are the new APIs.
The input parser remains the bounded offline fact-catalog parser, not an external
language model or a claim of arbitrary automatic factual research.

## Native contract and additive fields

The root schema stays `WORLD_ENGINE_UNIVERSAL_VIDEO_V2`, as required by the frozen
runtime/data loader. `renderProfile.adapter` stays `UNIVERSAL_AREA_ASTRA_V2` only
for that inherited contract. The new runtime must separately enforce BOTH
`renderProfile.productionAdapter: UNIVERSAL_PRODUCTION_V3` and
`productionV3.runtimeProfile: UNIVERSAL_PRODUCTION_V3`. The V3 entrypoint is the
actual independent driver, not a claim that the old browser implements V3.

`productionV3.schema` is `WORLD_ENGINE_PRODUCTION_SCENE_V3`. It contains:

- `eventChapters`: dated editorial chapters with absolute half-open frame ranges,
  source IDs, title, `displayLabel`, raw event date/precision/evidence,
  `presentationPolicy`, geometry-state references and source-derived narration.
- `geometrySchedule`: absolute frame ranges mapping into the original five-state
  Scene timeline, with `sourceStartFrame`, `sourceEndFrame`, supplied state IDs,
  snapshot date, on-screen snapshot label and explicit geometry accuracy status.
- `visualBindings.areaStyles`: exact original area IDs and source-bound ownership
  evidence. Only the supplied held-core polygons are colored. An enemy complement
  cannot be inferred from the rest of a country.
- `visualProfile`: hash-bound Scene-data palette and scope policy; color-role names
  are data, not country-name branches in a renderer. No new unit positions exist.
- `sourceBindings`: SHA-256 of the reviewed chronology, ownership evidence, visual
  profile and frozen parent manifest. These are also bound in root sourceManifest.

Every source file is read and hashed again during validation. Derived metadata is
recomputed from those bytes; tampered chapters, geometry clocks, palette bindings,
source references and boundary contracts are rejected.

## Narrative and geometry are different clocks

Twelve historical chapters do not mean twelve certified front geometries. The
original five authored schematic snapshots remain byte-for-byte identical inside
`legacyScenePlan`: 1950-06-25, 1950-09-01, 1950-11-24, 1951-01-04, 1953-07-27.
Chronology and source precision remain independent from their spatial accuracy.
No original official article body was newly verified; existing HTTP403/null-body
records are preserved. New curated chapter dates are not upgraded into official
body evidence by this planner.

An exact event-date front that is unavailable retains a clearly dated supplied
map as context. The active schedule's `snapshotLabel` MUST be shown alongside the
event date/title. `chapter.onScreenGeometryLabel` is a phase summary; the active
schedule label overrides it, especially in the two-snapshot eighth chapter.
`onScreenSnapshotDateAlwaysRequired` is mandatory, not an optional diagnostic.

In particular, the October 25 Chinese first-combat chapter retains the earlier
September 1 map. The later November 24 northern snapshot is not shown as the
October 25 front. The editorial north-advance chapter uses September 29–October 24
while noting that the broader advance continued later. Chapter eight contains
the later November 24 snapshot followed by the supplied January 4 snapshot.
The 1953 geometry is a simplified present-border approximation, not surveyed MDL.

## Exact frames and source sampling

The same weighted-remainder allocator handles 80/120/180/300/600 seconds.
At 80 seconds and 30FPS, twelve equal-weight chapters contain 200 frames each,
covering `[0,2400)`. Work scenes use a bounded maximum (default 300 frames). Their cuts are independent
from editorial chapters: the first available boundary is shifted into the middle
of an actual supplied-snapshot transition when the cap permits, otherwise an
extra work cut is inserted. At 80 seconds the first ranges are `[0,200)`,
`[200,445)`, `[445,600)`; the 12 story chapters still retain their original ranges.
A work unit records all overlapping `chapterRefs`; the renderer must select the
chapter at the actual global frame, never from the work unit start.
Longer durations reuse the same code and do not allocate
an array of rendered frames. Data checks are not claims of full-length rendering.

`source_geometry_frame(plan, globalFrame)` returns an integer source Scene frame.
For a geometry segment, the new runtime must use:

```text
p = (frame - startFrame) / (endFrame - startFrame - 1)
sourceGeometryFrame = Math.round(sourceStartFrame + p * (sourceEndFrame-sourceStartFrame))
```

For a one-frame segment use `sourceEndFrame`; HOLD has equal source endpoints.
The Python function matches JavaScript Math.round for nonnegative values.
`visualProfile.geometryTransitionDurationSeconds` is a Scene-data presentation
parameter, currently 3 seconds, capped to half each snapshot slot so the target
can also be held. It is not a historical elapsed-time or velocity estimate.
At 80 seconds the first transition is `[400,490)`, and its actual work cut at 445
is strictly inside moving source-clock progress. Chapter eight has two 50-frame
transitions and two 50-frame holds. This allows the software proof to test an
active cut rather than accidentally certifying an inactive original timeline. The
first segment is `ARRIVAL_NO_EVENT`; the original camera lock still gates event
rendering. Source reveal starts only after that lock. All transitions reuse the
old Area state-alpha evaluation between supplied snapshots. They do not construct
new geographic vertices, observed daily fronts or fictitious capture events.

Root's inherited `boundaryStart/End` still certify the old legacy-clock contract.
New `scene.productionBoundaryStart/End` separately bind the actual V3 source clock,
global camera intent and effect profile at each cut. Neighboring scenes must agree
at the same absolute boundary. These signatures certify semantic/data continuity;
actual matrices, decoded pixels and NVIDIA visual quality require runtime proof.

## Runtime plan creation

```sh
python3 -B scene_planner.py '한국전쟁의 전선 변화를 80초 영상으로 만들어줘.' \
  --image-digest 'sha256:<actual newly published immutable image digest>' \
  --output /private-job/PLAN.json
```

Output is exclusive 0600 creation; no prior plan is overwritten. Without a digest,
the plan records `IMAGE_BINDING_REQUIRED`. A supplied digest is operator configuration,
not hardware self-attestation or cost authorization. The final plan hash must be
approved with a finite cost/time/retry budget before paid execution. No GPU run,
80-second MP4, performance result or visual-quality approval is asserted here.
