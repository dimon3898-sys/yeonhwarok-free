# Universal long-video planning contract

`planner.py` is an additive offline adapter around the existing
`web/map_infographic_v1/planner_scene_v1.mjs::compileScenePlan`. It does not replace
the planner, geometry engine, camera, renderer or Scene V1 validator. The new
wrapper schema is `WORLD_ENGINE_UNIVERSAL_VIDEO_V2`.

## Actual supported planning

A constrained Korean/English parser reads a topic with duration, optional FPS,
resolution and aspect ratio. Explicit Python/CLI settings take the same contract;
conflicting textual settings fail. Seconds and minutes, including `1분 20초`, are
supported. The parser is not an external language model and reports
`externalAIConnected: false`. Free arbitrary factual planning is not claimed.

Subjects are selected only through the hash-bound supplied fact catalog. The
initial catalog contains the existing five illustrative Korean War states. Unknown
subjects, unavailable sources, source hash changes and requests for archival,
daily-control or precise historical unit tracks fail. Extending the catalog is a
data review task, not a new renderer. The long-duration allocation currently
supports the existing multi-state WAR family; other legacy event families remain
explicitly unsupported by this allocation adapter rather than silently converted.

The original facts and source records remain unchanged. The new source manifest
retains the raw HTTP403 retrieval evidence and null article-body hashes omitted
by the older normalized source record. Curated chronology is not live article
retrieval or archival boundary certification. The authored five front/held-core
snapshots and their dates are reused exactly; animation between them means an
infographic transition, not observed control on interpolated calendar dates.
No unit coordinates, battles, arrows or additional states are invented.

## Exact time and scene ranges

`durationSeconds * fps` must be an exact positive integer; it is never rounded.
The old planner receives its existing optional `scene_timing` field. Global frame
ranges use `[startFrame, endFrame)`. Split boundaries respect source beats and cap
work units at `maxSceneFrames`. Every interval is nonempty and the scene sum must
match total duration exactly. Scene metadata scales with scene count, without an
array of all frames or any decoded frame buffers.

The tested 80-second schedule at 30FPS contains 2,400 frames: 60 arrival frames,
60 initial frames, four 555-frame state transitions and 60 final-hold frames. It
splits into 12 work units capped at 300 frames. This timing is presentation data,
not a claim that the historical stages occupied equal real calendar durations.
The same code was checked at 80/120/180/300/600 seconds and at 24FPS; a successful
contract check does not mean these videos were rendered.

## Wrapper and renderer binding

Top-level output contains `durationSeconds`, `fps`, `resolution`, `aspectRatio`,
`totalFrames`, `sourceManifest`, `encoder`, `legacyScenePlan`, `renderProfile`,
`cameraProfile`, `materialProfile`, `audioSettings` and `scenes`. Each scene has
`sceneId`, `startFrame`, `endFrame`, `globalFrameOffset`, `eventTimeline`,
`territoryState`, `frontierState`, `cameraProfile`, `materialProfile`,
`unitMarkers`, `audioSettings`, `sourceManifest`, `renderProfile`, `boundaryStart`
and `boundaryEnd`.

`globalFrameOffset` always equals `startFrame`. Clipped event records retain both
their absolute source interval and scene interval. Renderers must evaluate the
original absolute timeline; no per-scene event or camera reset is permitted.
Boundary signatures cover source timeline/state, camera intent and effect profile
at the same absolute frame. They prove semantic contract continuity only. Actual
camera matrices, geometry and decoded boundary pixels still require the runtime
and GPU checks; the manifest labels that limitation explicitly.

Plans initially use `UNIVERSAL_AREA_ASTRA_V2` with capability
`POLYGON_STATE_TIMELINE` and `BLOCKED_RENDERER_BINDING_REQUIRED`. `bind_renderer`
accepts a separately validated runtime profile whose `nativePayload` contains
`path`, `sha256`, `validationStatus: VERIFIED`. Only `status: READY` permits
`validate_plan(..., require_renderable=True)`. Runtime validation must still
open/hash that payload and enforce its native GIS/camera/source bindings.
Neither a descriptor nor a CPU mock proves hardware rendering or video quality.

## APIs

```python
plan = plan_topic("한국전쟁의 전선 변화를 80초 영상으로 만들어줘.")
plan = bind_renderer(plan, validated_runtime_profile)
validate_plan(plan, require_renderable=True)
```

`split_plan(plan, max_scene_frames)` rebuilds dependent scene bindings;
`canonical_sha256(value)` is the stable JSON hash used by downstream caching.
CLI output uses exclusive file creation and never overwrites prior plans or jobs.

## Visual capability truthfulness

`REFERENCE_VISUAL_V2` remains the requested input style. The actual historical
profile is `REFERENCE_V2_SOURCE_WITH_AREA_V3`: the existing ASTRA material, support
edge blend and V2 source grade feed the unchanged Area V3 polygon transitions and
front-line overlay. Original native boundary pixels and native foreground remain
protected. The camera profile is `PRESERVED_V5_NATIVE_ARRIVAL_LOCK`. The one-winner
scalar V2 gain/white-gold frontier, V2 unit scale and V2 focus-hold camera are not
applied to reversing historical state timelines. No verified national-unit
positions exist, so none are generated. `visualReuse` records each applied and
non-applied component explicitly; this is not a full V2 visual-quality approval.
The inherited `REFERENCE_VISUAL_MASTER_V2_F` identifier appears only as the frozen
asset/data-closure profile, never as a claim that all its scene effects run.
