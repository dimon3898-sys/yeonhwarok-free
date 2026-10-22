# Reference 64306: capability gap and minimal patch map

Audited source: `82854af429d09aebb4b31c2f168e2f0ddc9560c9`. All line references below are to this commit. Inspection was read only; none of these protected files was changed.

**Decision: CAPABILITY_EXTENSION_REQUIRED.** The new `director_camera.mjs` supplies independent mathematical contracts and tests. It is **NOT_CONNECTED** to native pixels. No rotation-capable native runtime or successful reference render is claimed.

## Confirmed native factory barrier

| Source and function | Observed implementation | Consequence |
| --- | --- | --- |
| `web/map_infographic_v1/renderer.mjs:345`, `createMapInfographicRenderer` | Options expose canvas, plan, source assets, shared renderer/target, frozen layout and context source. | There is no transform, inverse projection or custom material factory argument. |
| Same file:355,374–379 | Initial standard-parallel cosine, geographic `project`, Three orthographic `camera` and `screen` are local variables inside the factory closure. | An external adapter cannot rotate the camera or replace the canonical geographic projection through a returned public object. |
| Same file:132–143, terrain fragment | Flat terrain geography is `mix(bounds.xy,bounds.zw,vUv)`. Only the existing globe branch changes its inverse sampling. | Rotating GIS alone would leave the full-screen terrain geographically unrotated. All geographic layers must share the new inverse sampling. |
| Same file:561–577, `updateCamera` | Accepts a four-number geographic bounds array. Updates orthographic sides/position, bounds uniform and GIS targets. Contains source-admission limits. | Pan/extent are supported. Rotation, arbitrary similarity and rotated source-envelope checks are absent. These admission limits must remain. |
| Same file:677–683, returned public API | `render`, `renderFrame`, `updateCamera`, width/LOD settings, readbacks, probes, `screen`, `dispose`. No returned camera, material, scene, inverse, callback or camera setter beyond bounds. | There is no public hook that can implement the required native planar similarity. |
| Same file:610–618, `renderFrame` | Full-screen terrain, glow, composite, geographic boundary and screen graphics are separate passes. | A correct extension must change geographic sampling and geographic camera together, before screen-space pin/text rendering. |

These are code-confirmed capability findings, not a GPU execution result. A generic WebGL extension does not expose JavaScript closure variables and does not supply the missing geographic inverse.

The public `outputRenderer` argument at345/348/351 allows sharing a Three renderer and output targets. It is a supported composition hook, but it does not declare a geographic forward/inverse transform or a terrain shader transform hook. Intercepting `renderer.render` to inspect/mutate the factory's private scene, camera or material uniforms would be a monkey patch of protected rendering behavior, not a supported coordinate adapter. Arbitrary JavaScript interception is not claimed to be technically impossible; it is outside the authorized public-hook approach and the renderer/shader protection rule.

## Existing rotation implementation cannot satisfy this MASTER

`web/map_infographic_v1/reference_presentation_adapter_v2.mjs` has pure projection helpers at lines94–114. Its pixel path is different: `createReferencePresentationPass` at140 copies the already rendered native framebuffer at173 and samples it with a rotated/cropped full-screen shader at129–137. Its evidence explicitly names `GENUINE_NATIVE_MAP_GPU_COPY_UNIFORM_ROTATE_CROP` at194.

The current MASTER expressly forbids completed-frame rotation/blit. Reusing that pixel pass would violate the task even though it uses a real GPU texture. It has therefore **not** been invoked. A new full map renderer or Canvas replacement has not been added.

## Other existing contracts and reusable consumers

| Source | Status and bounded action |
| --- | --- |
| `reference_camera_adapter_v1.mjs:61–89` | Real V5 ownership and a useful C1 bounds track. Lines76–78 require the final endpoint to be closest; there is no angle. Do not submit A's wide endpoint through this contract or append a fake closest key. Leave this API intact. |
| `camera_director_v5.mjs` | Preserve as approved baseline. The new mathematical contract does not overwrite it or manufacture its settled/locked state. |
| `recovery/universal-presentation-v2/presentation_plan.mjs:25–41,75–106` | Keyframes support frame/center/zoom and compile into the old bounds track. New reference sidecar is independent; old accepted inputs keep their behavior. |
| `recovery/universal-presentation-v2/presentation_runtime.mjs:40–41,80–86` | Existing factory and measured graphic pass are reusable. Current draw applies bounds and disables native graphics/boundary/glow/DEM. No injected rotation contract. |
| Same runtime:65–68,90–105 | Actual engine consumer selection is Area V3 or Flow V2. General Event V1 line/metric cannot be selected here merely by adding metadata. |
| Same runtime:70–76,90–91,107 | All marker boxes and area vertices are forced inside the safe area; graphic draw exposes markers only. Sidecar needs role/time-specific visibility, real label/glyph consumption and Event binding. Those are independent from the blocked native map transform. |
| `event_line_pass_v1.mjs:57–85`, `event_metric_pass_v1.mjs:14–38`, `graphic_motion_pass_v4.mjs:59–103` | Existing real WebGL consumers exist. They can be reused through new bounded event/graphic adapters, once actual moving projection and current-frame admission are available. Their existence alone is not a reference pixel PASS. |

## Minimum protected capability change required, not applied

The smallest coherent native change is one opt-in versioned factory transform capability in **`web/map_infographic_v1/renderer.mjs`**. This task does not authorize changing that protected file, so the following is a reviewable request, not an applied patch:

1. Preserve the existing constructor/default path, `updateCamera(bounds)` and its admitted minimum extent. Add an explicit opt-in `REFERENCE_SIMILARITY_2D_V1` contract, plus a public application method and a public `inverseScreen(pixel)` paired with `screen(point)`.
2. Define the transform in the factory's existing flat projected coordinates. Apply the same scale, screen-y-down heading and projected center to the actual GIS coverage/ID camera and geographic boundary/ribbon camera. Do not replace existing polygon triangulation, terrain materials, lighting or final output transfer.
3. In the **flat terrain sampling branch**, add the inverse transform from canonical pixel to projected world to geographic longitude/latitude. Keep `gisUv=vUv`, because the GIS ID/coverage targets remain current-view screen targets. The globe branch and disabled/default flat path retain their exact previous expressions. No completed-frame copy/rotation is involved.
4. Derive source footprint from the inverse projection of all four rotated viewport corners for every frame. Retain geographic-domain, original-source, minimum-detail and one-pixel-gutter checks. Reject unsupported globe/planar transitions and incomplete coverage; do not fake detail outside the source.
5. Return transform evidence identifying current forward/inverse matrices, geographic corners, source admission and real camera state. Keep screen-space glyph and pin planes upright; sidecar graphic/event consumers project their geographic anchors through the same returned `screen`.
6. Verify the opt-in path with real draw/readPixels before granting any reference production gate. Verify default path output is unchanged, all307 protected hashes are updated only through a separately authorized protection workflow, and native old consumers still pass. This repository change has **not** been made under the current protection rule.

Merely returning the private Three camera would not be sufficient: terrain's full-screen geography inverse would still be wrong. Replacing only `screen` would produce floating overlays above an unrotated map. Adding a post-render image rotation would break the MASTER's composition rule.

## Completed independent math work

`director_camera.mjs` defines an opt-in, data-only coordinate and window contract, with no map renderer:

- Standard-parallel Q coordinates matching the flat factory model, canonical forward/inverse similarity, real anchor/pair/unmodified-polygon/verified-segment solvers.
- One whole-track C1 monotone cubic in projected center, log scale and unwrapped heading; no special final-closest endpoint or per-window resets.
- Honest `[29,575)` global frame mapping into180/180/186 windows, each at most240 frames.
- Inverse four-corner source envelope and every-frame coverage/resolution audit.
- Explicitly synthetic fixtures and missing-source guards. Mathematical results always carry `NOT_CONNECTED_CAPABILITY_EXTENSION_REQUIRED`, `actualPixelVerified:false`, and `referenceVisualMatch:UNVERIFIED`.

No source camera or Euler yaw was recovered from the optical-flow CSV. That CSV contains measured image motion estimates; the supplied target constraints remain estimates. Real geographic bindings and precise deep-zoom source coverage remain a separate gate.

## Production gate

The required native rotation/inverse capability and real detail geometry/source evidence are not available under current protections. Therefore phase C reference static draws and phase D reference MP4 windows remain **BLOCKED**. No old/fixed camera rendering is presented as the requested new reference output. Historical G3 remains BLOCKED.
