# Event Area / Propagation V3

Parent: `EVENT_FEATURE_BUNDLE_V2_FLOW_FINAL_BASELINE` at `fbc3be89d94040271c7f54a051162913ad134bac`. All parent tracked files are protected. This extension owns event overlays and supplied visual states only.

## Input and ownership

`compileAreaIntent` accepts sourced GeoJSON Polygon/MultiPolygon areas, authored states, LineString fronts and trajectories, an origin, and explicitly illustrative angular propagation contours. Holes, parts, closure and source vertices are preserved. Invalid topology is rejected, never repaired or substituted. Production sources require an explicit verified source record; synthetic records cannot authorize production.

`compileAreaPlan` binds an immutable source intent to integer-frame operations: reveal, grow, contract, move, propagation, impact, front, state/time transition and final hold. Every evaluation is random-access and deterministic. State transitions crossfade supplied complete polygons instead of morphing unmatched topology. Grow/contract limit visible coverage inside the supplied footprint. Move uses the existing Line arc-length evaluator and Flow route sampler on a supplied trajectory.

Propagation is an infographic presentation of a supplied relationship. Angular radius and presentation frames do not represent measured wave speed, inundation extent, wave height or scientific arrival time. Authored state labels must distinguish presentation phases from observed dates/times.

## Polygon visual admission

`AREA_DATA_PROFILE` records actual available terrain/GIS and the unchanged survey status. `AREA_VISUAL_ADMISSION` projects the complete future sweep, including motion, all states, fronts and propagation contours through the existing native projector. It checks semantic integrity, safe area, visual evidence and full-object visibility.

An already readable view returns `USE_CURRENT_VIEW`. An insufficient view produces a separately typed `AREA_DETAIL_FRAMING_REQUEST`; it cannot inherit a Line certificate or silently bypass admission. Production requires actual native-render proof bound to the exact framing and geometry. Warnings do not automatically block FACT_BASED_VISUAL_GRADE; critical visual or semantic errors do.

## Native composition

The native bridge delegates Camera V5, projection, geographic scale tokens, moving layout and guided reveal to their frozen owners. It redraws the existing map factory on every frame before Area overlays; it never copies a completed frame. No Area primitive starts before native camera lock. Missing regional DEM coverage uses the existing baked-relief factory path and is disclosed in the fixture.

The Area GPU pass reuses native Polygon triangulation and V1 Line primitives. It masks all native Marker/Text/Panel reservations, safe-area edges, and geometry-generated support for existing country boundary/glow. An owned R8 coverage framebuffer contains only projected boundary geometry, not copied terrain pixels. Shared WebGL state is restored after every pass. Area/time annotations reuse the existing measured Metric glyph and GPU pass at 40px and select a safe candidate without moving existing graphics.

## Save and review gates

Core and Synthetic PASS are committed before long rendering. Actual fixture/camera integration is committed separately before proof rendering. Candidate media, source, fixture, data provenance, dependency/import and reproduction manifests are committed afterward. Public review contains only the original MP4, eight PNG checkpoints and SHA256SUMS. Final freeze and Permanent Gate are deferred until the user approves the actual video.
