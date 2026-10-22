# Native flat similarity extension — pre-change design

Base: `5cc9b98c628324814e1e63f9d0f8c6254ee84174`.
Only authorized protected target: `web/map_infographic_v1/renderer.mjs`.
Original source SHA-256: `e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38`.
Proposed candidate03 SHA-256: `f84ca6a29c55fb0316b47112ca673b63f530b9d492c661da1c9f5eb913e87496`.

The original renderer remains unchanged while this proposal is reviewed and remotely saved. The immutable backup, original307 manifest, baseline actual hashes and candidate unified diff are retained by the new protection tool. The original hash is not silently replaced with the candidate hash.

## Versioned public API

The existing factory adds one optional `projectionMode` selector. Missing/null retains the established path. The only new accepted selector is `REFERENCE_SIMILARITY_2D_V1`. The mode starts inactive, and no camera change occurs until `updateSimilarity` succeeds.

New methods:

- `projectionDescriptor()` returns the existing fixed standard-parallel world model as `NATIVE_FLAT_Q_MODEL_V1`. Its origin is the initial geographic framing center; `Q=[(longitude-originLongitude)*cos(originLatitude), originLatitude-latitude]` has screen-y-down convention. This matches the existing V1 director math contract without importing any reference data or timings into the renderer.
- `updateSimilarity({centerQ,scale,angleDegrees})` applies a uniform scale in canonical1080×1920 pixels, projected center and screen-y-down angle. Unknown fields, malformed pose, wrapped/polar/globe transitions, deficient source/native detail, insufficient gutter or a closer-than-admitted extent fail before camera mutation.
- `screen(point)` remains the actual native camera projection, not an overlay-only approximation.
- `inverseScreen(pixel)` uses the actual native camera inverse. It rejects globe use; no invented globe inverse is returned.
- `sourceEnvelope()` inverse-projects all four viewport corners through the actual camera and reports their geographic rectangle. The update compares these native inverses to its analytic forward/inverse contract.

Actual camera math: the private Three camera uses orthographic sides `±540/scale, ±960/scale`, position `[centerQ.x,-centerQ.y,5]`, and Z rotation equal to the supplied screen-y-down angle. Every GIS ID, coverage and native boundary ribbon uses this same camera. Existing screen graphics remain upright and must use a current projected external graphic consumer; an active transform rejects `graphics:true` rather than rendering stale fixed-layout anchors.

## Exact old/new ownership

| Original function/section | Change and preserved behavior |
| --- | --- |
| Factory declaration around345 | Add opt-in selector and metadata snapshots only. `assertLocalDetailAdmission` is still called before WebGL; default and globe selection remain intact. |
| Native camera/screen around374 | Existing project/camera/screen remain their actual owners. New update configures that camera; no second renderer or frame-copy pass is added. |
| Terrain `main` around132 | Preserve old `geo=mix(bounds.xy,bounds.zw,vUv)` and entire globe branch. Only active opt-in flat sampling obtains geo from the inverse similarity. GIS ID/coverage UV remains `vUv`, referring to current-view targets. |
| Regional source UV around145 | Active opt-in computes regional source UV in relative projected coordinates. This avoids subtracting large absolute latitudes at fine local RGB resolution. Default expression remains unchanged. |
| Terrain loading around415 | Default uses the existing TextureLoader path. Opt-in fetches actual terrain bytes, verifies SHA-256, decodes exactly those bytes via a temporary Blob URL, and revokes that URL after load. |
| `updateCamera(bounds)` around561 | Existing argument checks, admitted minimum extent, old bounds uniforms and redraw remain. On an opted-in factory only, it explicitly turns similarity off and returns to the old nonrotated camera. |
| `renderFrame` around596 | Default/globe graph remains unchanged. Active opt-in requires a successfully admitted transform, current projected graphics consumption, and the qualified regional source at full weight. It does not silently mix unqualified LOD sources. |
| Returned factory around677 | Add new public methods; all existing members remain. |

## Source and detail admission

The new path snapshots the actual terrain asset and admitted closest extent before asynchronous loading. It derives native spacing using the existing `terrainDetailDescriptor`, conservatively bounded by the actual decoded image spacing; a declared smaller spacing cannot make a low-resolution image appear finer. The source must have exact SHA, EPSG:4326, explicit `NoData:null`, valid native metadata and matching decoded dimensions.

Before each similarity change:

1. Inverse-project every rotated viewport corner; reject domain/dateline/polar limitations explicitly.
2. Compare the unrotated camera-axis spans to the unchanged original admitted minimum. A larger rotated AABB cannot hide an impermissibly closer zoom.
3. Enforce at most one canonical output pixel per native source texel in each source direction.
4. Require at least one native pixel of source gutter around the complete rotated geographic envelope.
5. Bind actual source bytes/hash, spacing, dimensions, density and gutter into current-camera evidence. No `approved:true` or similar client flag can bypass these checks.

An update commits to camera/terrain uniforms and redraws GIS targets only after these checks. An unexpected commit-time inverse failure marks the factory unsafe to draw until a successful explicit camera update. No settled/locked state is fabricated; evidence says false. A field named `REFERENCE_*` is a generic version identifier, not country/scene-specific behavior.

This extension supports one qualified regional source in an active draw. A future coherent multi-resolution source hierarchy needs separate source/registration/license admission; it is not silently claimed here. Source shortages remain data gates. Fine RGB relative UV is improved, but existing DEM/material/light algorithms and their source contracts are not replaced.

## Protection and rollback

The original307 manifest and full5cc9b98 baseline remain immutable. Final protection will report the actual authorized renderer change with both original and modified SHA, and every other protected file as unchanged. The original file is available from both the immutable backup and `git show 5cc9b98:world-simulation-shorts-engine/web/map_infographic_v1/renderer.mjs`. No automatic restore, cache delete or original overwrite is used to obtain a test PASS.

Before actual replacement, retain `reports/RENDERER_PRE_CHANGE_PROPOSAL.json` and `.patch` with their hashes. The parent will save that checkpoint remotely first. After replacement, actual free SwiftShader draw/readPixels must establish default pixel identity and real opt-in map/GIS/source alignment. If that fails, downstream production remains blocked; mathematical tests alone cannot declare the native capability gate PASS.

## Pre-change review revision04 (supersedes candidate03)

Latest candidate04 SHA-256: `c5aaf6b902d5f5374d93230e8979919dee398e47c41cf65a12e3bf2a35b55f9d` (64,945bytes,94 additional source lines). `reports/RENDERER_PRE_CHANGE_PROPOSAL04.json/.patch` is the final pre-change receipt; candidate03 and its first receipt remain as earlier un-applied design evidence.

The root/baseline independent review added these bounded safeguards before any protected-file replacement:

- On the opt-in path only, `assertLocalDetailAdmission(layoutPlan,heightSource)` is also applied to a separate provided layout plan. A LOCAL closest layout cannot be accepted merely as unvalidated metadata.
- Minimum camera spans must satisfy both original plan framing and the optional locked layout framing. Selecting a GLOBAL/CONTINENT label or a tiny layout cannot relax the original plan minimum.
- The opt-in projection snapshots the original framing bounds as well as source/minimum metadata. Mutation of a caller-owned array cannot make `projectionDescriptor()` inconsistent with its fixed geographic origin.
- Fine regional RGB UV uses a CPU-computed relative center UV plus a small inverse-projected pixel delta. It does not first add a potentially large Float32 projected center and subtract the same large tile origin in the shader.
- A conservative Float32 native-position budget is checked before camera mutation. Deep zoom far from a projection origin fails explicitly with `SIMILARITY_FLOAT32_POSITION_PRECISION_EXCEEDED` above0.25canonicalpixels, rather than claiming untested submeter geometry precision. Recreating a legitimately admitted plan with a nearby geographic projection origin is the supported remedy; geographic source vertices are not altered.
- The original DEM sampling/material algorithm is unchanged. An active opt-in draw refuses DEM data finer than the representable absolute geographic Float32 sampling precision with `SIMILARITY_DEM_GEOGRAPHIC_PRECISION_INSUFFICIENT`. This is a bounded new-path admission guard, not synthesized height or a shader-lighting rewrite.

These are generic numerical/source contracts. No country, event, reference frame number, label or85m fact is embedded in the native renderer. Actual draw/readPixels remains a mandatory subsequent gate, not awarded by this proposal.
