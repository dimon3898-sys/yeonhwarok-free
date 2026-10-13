# Territory control extension V1

This is a data-owned, continuous control-field adapter above frozen Area V3. It does not own the camera, render a front line, construct routes, move objects, simulate combat, invent event facts, or change source coastlines. The selected reference is a modern hypothetical scenario. This fixture is a `REFERENCE_VISUAL_STUDY`; it must not be relabeled as an observed historical campaign.

## Input and compilation

`compileTerritoryControlIntent(input)` validates and deeply freezes the canonical intent. `compileTerritoryControlPlan(inputOrIntent)` returns the compiled, serializable plan. `assertTerritoryControlPlan(savedPlan)` revalidates a JSON-restored plan and rejects stale geometry or boundary bindings.

```js
{
  semantic_mode: 'REFERENCE_VISUAL_STUDY',
  source: {
    source_type: 'REFERENCE_VISUAL_STUDY',
    source_reference: 'logical-reference-id',
    verification_status: 'REFERENCE_INSPECTED'
  },
  domain: [{id: 'land-domain-id', geometry: suppliedPolygonOrMultiPolygon}],
  factions: {
    winner: {id: 'side-a'},
    loser: {id: 'side-b'}
  },
  longitudinal_knots: suppliedStrictlyIncreasingLongitudes,
  base_boundary_latitudes: suppliedOriginalBoundaryLatitudes,
  boundary_keyframes: [
    {frame: 0, latitudes: suppliedSegmentStartLatitudes},
    // Optional intermediate keyframes retain the same longitude knots.
    {frame: 149, latitudes: suppliedSegmentEndLatitudes}
  ],
  advance_direction: 'POSITIVE_LATITUDE',
  start_frame: 0,
  total_frames: 150,
  fps: 30,
  interpolation: 'LINEAR'
}
```

The engine has no subject names, fixed geographic coordinates, or faction color constants. Colors and opacities belong to fixture material inputs. A distinct `FACT_BASED_VISUAL_CONTROL` semantic mode is supported for supplied factual states, without any automatic provenance promotion.

The domain is an array of unchanged GeoJSON Polygon/MultiPolygon geometries. Original coordinate order, closure, part count, islands, holes, and geometry properties are retained. The Area V3 coordinate reader and Event V1 anchor validation are reused. Basic closed-ring/geographic validity is checked without repairing or simplifying native GIS. Topological correctness remains the responsibility of the already verified source dataset and the existing native polygon triangulator; the adapter is not a second GIS validator.

There must be 2–64 longitude knots covering the longitude range of every supplied domain part, including islands. Every latitude profile uses precisely those knots. Relative keyframe indices start at 0, end at `total_frames - 1`, and increase strictly. A positive-latitude advance requires every latitude at every keyframe to be at least its preceding latitude and at least the original base profile. A negative-latitude advance applies the opposite inequality. Thus interpolating between keys cannot reverse a gaining region.

`LINEAR` retains the measured progress between reference samples. Optional `SMOOTHERSTEP` delegates to the frozen Event Detail adapter's existing quintic `detailSmootherstep`; it does not introduce another easing implementation. The 150-frame/30fps/5-second requirements belong to this fixture, while the adapter permits other explicit integer durations for reuse.

## Evaluated frame

`evaluateTerritoryControlFrame(plan, absoluteIntegerFrame)` is stateless and deterministic under random access. Absolute frames lie in `[startFrame, startFrame + totalFrames)`. Its controls expose:

- `landDomain`, the frozen, unchanged source domain;
- `longitudinalKnots`, `baseBoundaryLatitudes`, and interpolated `boundaryLatitudes`;
- `advanceDirection` and `advanceSign` (`1` or `-1`);
- `factions`, `domainGeometryBinding`, and `boundaryKeyframeBinding`;
- relative `timeSeconds`, normalized `progress`, and current `keyframeInterval`;
- `geometryUnchanged: true`, `physicalSimulation: false`, `routeVisuals: false`, `standaloneFrontLine: false`.

No alpha crossfade controls or independently moving winner/loser polygons are emitted. This matters because the old Area `STATE_TRANSITION` correctly preserves supplied snapshot geometries but uses crossfades, and `AREA_GROW` uses radial coverage. Neither primitive represents the continuously advancing complementary boundary required by this reference. The new extension adds only the missing ownership field; all existing Area, Flow, Projection, Camera, and Renderer cores remain read-only.

## Complementary ownership and material regions

For a longitude, interpolate latitude linearly between its adjacent longitude knots. Let `b` be the moving latitude, `b0` the original base latitude, and `s` be `advanceSign`. A point in the source land domain belongs to the winner exactly when:

```text
s * (pointLatitude - b) <= 0
```

The loser is the logical complement. A point exactly on the boundary has one winner owner, avoiding an ambiguous gap. Existing winner land satisfies the same inequality against `b0`. Winner land beyond `b0` is `WINNER_GAINED`; it can receive the brighter reference-derived material while original southern winner land retains a terrain-readable material. The original base boundary may differ from frame 0 because the selected reference segment begins after some advance has occurred.

`sampleControlBoundary(planOrFrame, longitude, {kind: 'moving'|'base', frame})` exposes the numerical field. `classifyControlPoint(planOrFrame, geographicPoint, {frame})` is a verification oracle returning one of `WINNER_EXISTING`, `WINNER_GAINED`, `LOSER`, or `OUTSIDE_DOMAIN`, with owner, complementary winner/loser booleans, and source domain IDs. Plan queries require an explicit frame. Already evaluated frozen frame objects can be queried directly. Mutable copies are rejected rather than trusted as bound source controls.

The CPU point query respects holes and all MultiPolygon islands. It is not a rasterizer or clipping engine. The material extension should interpolate geographic longitude/latitude through triangles made by the existing native polygon triangulator, classify both sides in a single fragment invocation, and blend one selected material over the fresh native frame. This retains coastline clipping and avoids independently triangulating or swapping territorial meshes. Protected native graphics and existing boundary masks remain the responsibility of that GPU pass.

## Focused verification

Run:

```sh
node tests/territory_control_adapter_v1.test.mjs
```

Eight tests cover all 150 frames with a land-point grid; exact complementary ownership; monotonic winner gain; continuous keyframe interpolation; irregular western/eastern profile values; the original/new winner distinction; holes and islands; a decreasing-latitude generalization; source immutability; random access and JSON restoration; rejected stale bindings, invalid schedules, capacities, and reversal; existing easing reuse; and absence of subject-specific or rendering logic in this extension. These are control-contract tests, not visual acceptance or a Permanent Gate.

Implementation touches only the new adapter, its focused test file, and this contract. Camera movement, native GPU integration, candidate media, persistence, and full visual comparison are separate work owned by their respective adapters and Root.
