# Camera Director V4 contract

This pure motion module consumes geographic Scene data. It does not render,
select terrain, color regions, place labels, reveal information, make stories or
modify Scale / local-detail admission.

## CameraIntent

`compileCameraIntent(scene)` validates and freezes:

- `primary_region_id`, real `primary_geometry`, and `event_anchor` as longitude /
  latitude; optional real `event_geometry` and `context_geometry`.
- `event_title`, `location_label`, optional `primary_label` as supplied text.
- `approved_final_extent`, `desired_detail_level`, and `scale_admission`.
- Optional `context_extent`, `start_extent`, `safe_area`, `canonical_output`.
- An admitted local request additionally needs `admitted_local_extent` or the
  admitted requested extent; missing or rejected admission retains the exact
  approved regional / safe-closest stop.

The initial extent fits actual primary bounds to the canonical safe area. Its
span cannot be smaller than the admitted stop. Required context is the geographic
union of actual primary, event and relation geometry. Expansion occurs only if
this union is not contained by the starting safe viewport. Context is fitted with
shared `fitGeographicExtent`; sea is never a prerequisite. No topic-specific
coordinates, zoom, labels, frame numbers or branches exist in the director.

## CameraPlan

`compileReferenceCameraPlan({scene, intent, profile, seed})` returns a deep-frozen
`CAMERA_DIRECTOR_V4` plan before a RevealPlan is created. `scene` is unnecessary
when an already-compiled `intent` is provided. Profile values are semantic motion
and perception policies rather than fixture times. Output duration follows
normalized geographic pan distance, log extent change and supplied-text reading
budgets; it is not stretched to a target number of seconds.

Motion states are primary recognition, optional context expansion, relation hold,
event approach, guided reveal, deceleration, event framing, settle, lock, event
title, perception hold and next. `GUIDED_REVEAL` reserves a legible motion window;
it does not control the presence of any rendered text or marker.

Each moving leg evaluates geographic center and logarithmic extent analytically.
The approach has one C2 trajectory across all its state phases; phases never reset
the curve. Distinct monotonic pan / zoom progress is derived from geographic
travel metrics so pan can lead zoom. Endpoints have exactly zero velocity and
acceleration. Context expansion and relation hold are explicit when needed.
The final extent is copied exactly from the approved / admitted input.

`evaluateReferenceCameraFrame(plan, integerFrame)` returns camera bounds, center,
velocity, acceleration, pan/zoom weights and progress, projected primary-region
size, projected event anchor, primary/event screen velocity, Scale admission and
settle/lock state. It has no RevealPlan or layout mutation. Frame zero and every
other frame report `primaryMaterial: 1`; this is a fixed material input, not an
animation stage. The evaluator is random-access, deterministic and clock-free.

## Separate responsibilities

CameraIntent describes spatial intent. CameraPlan owns movement and readability
budgets. A separate RevealPlan may read state, velocity, Scale and projected size,
but must not mutate the CameraPlan. Layout owns candidate choice and measured
text bounds; it may not modify camera coordinates. Renderer consumes these
independent results through the existing pixel pipeline.

No final-frame compositing, completed-frame substitution or projection switch
belongs in this plan. LOD remains geographic and source-density driven by the
unchanged existing pipeline. The exact approved final material, layout and pixels
must be verified in the actual renderer, separately from these pure motion tests.

## Guided information and measured moving layout

`compileGuidedRevealPlan({cameraPlan, scene, layoutContract, visualTokensForFrame})`
reads the completed immutable motion plan. It chooses entry frames from projected
region size, actual event screen speed, scale, safe-area/collision eligibility and
minimum perception windows. It never repositions or recompiles the camera.
`evaluateGuidedRevealFrame` is an integer-frame, random-access visibility latch.
The primary material is always on. The location follows its marker; the event
title requires the completed settle/lock phase.

`compileMovingLayoutContract` consumes the existing factory's measured glyph
atlases and approved Universal Layout result. Country and marker anchors follow
the same geographic camera; the location retains its selected relative candidate
through a beat. Final boxes and all visual metadata return the original approved
values exactly. No clock, string-specific coordinates, font replacement or camera
adjustment exists in this consumer.

## Explicit GPU frame graph and native source coverage

`createGuidedCameraGpuPipeline` uses the frozen map renderer factory for terrain,
DEM, material, GIS, boundary and glow. An explicitly owned GPU graphic pass then
draws measured glyph/marker quads into the same default framebuffer. Its four GLSL
sources are byte-identical to the approved graphic shaders. There is no wrapper,
finished-frame image substitution or Canvas final composition. A temporary Canvas
is used only to decode the existing glyph coverage atlas into a GPU texture.

The optional `contextTerrain` descriptor is a geographic resource view of the
same admitted native raster. Camera motion may require a wider native pixel
window than a previous static extent. Such a window preserves original source
identity, texel spacing and RGB bytes, has a separately recorded derivative hash,
and uses the unchanged geographic source-LOD formula. It must cover the whole
compiled trajectory with a real-source sampling halo. It cannot create, resample,
recolor or sharpen data, and must not overwrite earlier source windows.
