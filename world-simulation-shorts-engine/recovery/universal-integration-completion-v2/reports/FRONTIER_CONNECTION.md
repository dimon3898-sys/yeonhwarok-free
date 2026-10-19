# Supplied-front light connection

## What is actually connected

`production_area_bridge.mjs` is a browser import alias. It reuses the existing
V1 five-parameter binding and the unchanged
`universal-production-v3/production_area_pass.mjs` factory. That factory remains
the owner of the Area V3 GPU pass, white core and gold halo. The actual consumer
is `web/map_infographic_v1/area_overlay_pass_v3.mjs`: `drawLine()` calls the
original geographic arc-length evaluator and `contour()` sends the existing
core/radius/halo/gain uniforms to the existing contour program.

The additive `frontier_extension.mjs` provides:

- `normalizeFrontierProfile(value)` for the strict
  `AUTHORED_FRONT_MOTION_V2` profile.
- `compileSuppliedFrontMotion({observations, totalFrames, profile})` for dense,
  explicitly supplied frame geometries. Missing observations are rejected.
- `evaluateSuppliedFrontMotion(plan, frame, front)` for deterministic,
  scene-independent motion/settle strength on the exact supplied front.
- `bindFrontierProductionFactory(originalFactory, {profile,
  readFrameContext, motionPlan})` for the actual factory/draw connection.

The wrapper changes only an existing front's alpha before the original owner
draws it. The parent still receives its original polygon list, front geometry,
line primitive, projection, safe area, protected marker/label reservations and
native-boundary mask. It does not add a line, arrow, route, opposite ownership
fill, terrain sample or geometry vertex. Stop response uses a smooth finite
envelope after actual comparable geographic coordinate changes. Camera motion
does not count as frontier motion. Topology changes without corresponding
vertices are reported as unmeasured and retain normal parent visibility.

Dense observations are compressed into exact coordinate runs. There is no
historical interpolation or assumption that an absent observation was held.
The evaluator is stateless; it gives the same result after a seek or at a scene
split. A completely static supplied front retains normal parent visibility;
the adapter does not invent advancing motion or periodic blinking.

## Runtime binding

Required aliases:

| URL | Owner |
| --- | --- |
| `/production-v3/production_area_pass.mjs` | New `production_area_bridge.mjs` |
| `/completion-v2/frontier_extension.mjs` | New pure adapter |
| `/completion-v2/frame_context.mjs` | Root-owned global-frame context |
| `/integration-v1/parent_production_area_pass.mjs` | Preserved production factory |
| `/integration-v1/presentation.mjs` | Preserved five-knob binding |

The bridge reads the explicit `runtimeConfig.completionV2.frontier` profile and
the source-bound `runtimeConfig.completionFrontierMotion` plan. The global-frame
context must be published by the root-owned capture wrapper before the parent
draw. No parent file is edited.

If motion metadata is absent, the exact parent alpha is preserved and the
diagnostic reports `COMPLETION_FRONTIER_MOTION_SOURCE_NOT_CONNECTED`.
`motionConnected: false` must remain a feature/readiness blocker; preserving a
safe parent image is not a claim that motion integration passed.

The actual current historical fixture contains held/partial fronts and qualified
schematic states. A compiler can connect whatever changes the preserved
evaluators actually supply. A lack of comparable moving geographic fronts
cannot be repaired by inventing daily front coordinates. The root's source/data
admission remains authoritative.

## Exact advanced-light incompatibility

The prior high-grade implementation is
`web/map_infographic_v1/reference_control_frontier_light_v3.mjs`, optionally
decorated by `reference-visual-master-v2/frontier_ref2.mjs`.

`createControlFrontierLightPassV3()` requires an asserted complementary scalar
`TerritoryControlPlan`, its exact land-domain polygons and trusted evaluated
longitudinal boundary knots. Its draw requires the actual current source
`actualTerrainTexture`, matching projection and protected graphics. It applies
terrain-derived destination lighting and then its scalar material boundary.
The reference outer-gold decorator additionally requires same-frame native
domain-coverage data and exact geometry/source hashes.

Current V4/Area production instead supplies arbitrary partial geographic
polylines and explicitly qualified held-core polygons. The Area overlay's
public draw API has no actual-terrain texture sampler. Converting those partial
lines to a complementary scalar ownership field would invent unsupported
ownership. Treating the complement of a held core as enemy territory is also
forbidden. Therefore that whole high-grade shader is **not** invoked here.

The safe connection is the existing white/gold Area consumer plus the supplied
geometry motion envelope. Per-fragment terrain-aware frontier lighting remains
**BLOCKED** on a missing compatible contract. The exact minimum next work is:

1. Expose a source-bound current-frame terrain texture/projection/mask handle
   from the existing source owner to a polyline-capable light consumer.
2. Reuse an existing compatible consumer if one is added; otherwise implement a
   separately versioned, narrow polyline-light pass rather than changing the
   protected scalar owner or copying an entire renderer.
3. Preserve the Area reservation and native-boundary masks, admit only supplied
   front geometry, and obtain actual GPU A/B evidence before declaring quality.

No unsupported `terrainLighting` prompt flag is exposed. The diagnostic records
`terrainLightingConnected: false`; the source-grade/ASTRA path remains preserved
as a separate existing owner. Existing style and data/source selection are not
reported as proof of this missing terrain sampler.

## Focused CPU evidence

`node --test --test-isolation=none tests/test_frontier_extension.mjs`:
**13 tests PASS**. They verify strict fields/bounds, dense source coverage,
moving/stop response, seek/split equivalence, static front behavior, topology
uncertainty, geometry binding, protected-input forwarding, disabled behavior,
alternate hemispheres/date-line values and prototype-safe IDs.

One test executes the unchanged real production factory with only its deepest
GPU allocator replaced by an explicit CPU observation fixture. It verifies
that the existing production style and no-complement policy actually consume
the wrapper output. This is factory/consumer instrumentation, not a WebGL draw,
pixel comparison, GPU test or visual-quality approval.

No shader or renderer was copied or edited. No GPU, SwiftShader, MP4 or paid
operation ran. Actual NVIDIA output and visual quality remain `NOT_VERIFIED`.
