# Source-bound director camera

The new camera is an explicit `SOFTWARE_PREVIEW` profile. The original 80-second Scene and its 12 global chapter ranges stay unchanged. It does not certify NVIDIA output, LOCAL admission, historical troop coordinates or visual quality.

`DIRECTOR_CAMERA_PROFILE.json` refers to existing Scene geometry IDs, existing location IDs and the already admitted partial-front IDs. A location is geographic context; it does not establish a landing site, unit position or occupation event. The initial view fits the original country geometries. The first approach fits the first supplied schematic source. Subsequent views fit the supplied geometry used by the current chapter and its declared location context.

The implementation reuses these existing consumers:

| Purpose | Existing consumer |
| --- | --- |
| Original V5 base and admission metadata | `native.cameraPlan`, originally consumed by `evaluateMinimumContextCameraFrame` |
| Geographic pan, zoom and shared C1 interpolation | `compileReferenceCameraTrack` and `evaluateReferenceCameraTrackFrame` in `reference_camera_adapter_v1.mjs` |
| Geographic aspect fitting | `fitGeographicExtent` in `scale_contract.mjs` |
| Native marker and label positions | `evaluateMovingLayout` and `validateVisibleMovingLayout` |
| Pixel projection and camera upload | `native.factory.updateCamera`, `native.project` |
| Scale and source LOD | `geographicScaleVisualTokens`, `geographicTerrainLod` |
| Base redraw | `native.factory.renderFrame` with the original frozen material parameters |
| Protected overlays' current native frame | `publishNativeFrame` |

The original reference adapter requires its final endpoint to be closest. A wider director endpoint therefore compiles the same original adapter in the opposite direction and samples that **camera-only** segment in reverse. This does not change, reset or reverse the Scene's global frame, front geometry, territory state or event clock. Duplicate endpoint bounds use the original adapter's shared slopes to create zero-motion endpoint holds. No replacement spline is implemented.

Original completion-V2 camera guards are preserved in their old profile. They require the full 80-second geometry to remain visible and disallow a closer view than the parent floor; that combination produced the previously measured subpixel motion. The independent director profile checks the current chapter's source and the original native foreground instead, while preserving the actual native factory's closest admitted Regional extent. It cannot be selected by a production or unauthenticated rendering request: its runtime requires `testOnlySoftwareProbe=true`, `mode=SOFTWARE_PREVIEW` and `productionEligible=false`.

The second actual attempt rendered frame 0 but rejected frame 150 with `LOCAL_NOT_ADMITTED / Camera extent exceeds the admitted locked endpoint` from the unchanged `renderer.mjs:updateCamera`. The earlier CPU mock did not exercise this native guard. The director now receives the real `plans.REGIONAL.framing.bounds` and proportionally widens any smaller target or initial context around its source-derived center. The original factory, floor, admission and validator are unchanged. An exact-source CPU test executes the real original `updateCamera` function with only draw/uniform spies: it reproduces the failed narrow target and accepts all 2,400 corrected camera bounds. This is guard verification, not GPU pixel evidence. Closer zoom is explicitly `BLOCKED_NATIVE_LOCAL_NOT_ADMITTED`; the preview permits pan and a wider view approaching the approved Regional endpoint only.

Before rendering, native visible-role layout is checked at all 2,400 global frames. A target is widened when the existing native layout rejects it. Existing geographic labels and markers are neither moved nor hidden. Failure to obtain a safe native target stops the director.

An actual software boot found that the duplicate fixed native headline `한국전쟁의 전선` failed `EVENT_TITLE / BOUNDARY_CLEARANCE` against `COUNTRY_KOR` for every tested view; wider alternatives also collided with the Seoul location label. The production composition already has an independent current-chapter date/title and a source-date qualifier. The explicit director-only `hideDuplicateNativeHeadline=true` policy therefore sets only the existing `reveal.title` channel to zero. The original reveal object, source Scene, headline text, layout core and validator are unchanged. All other reveal roles are retained; the chapter title and source qualifier remain their existing owners. Validation, the native redraw, returned reveal and foreground draw all consume the same visibility. The redundant title and its panel no longer reserve invisible space. An unconditional native redraw when this policy is active prevents stale headline pixels. The focused test proves that no other reveal channel changes.

Each sampled frame reports the actual native camera, geographic-to-pixel matrix, pixel scale, native-projected context targets, camera-only sample frame, global frame and active source geometry. Source safe-area cropping during an approach is recorded separately; the presence of a valid target does not establish that every intermediate source view is safe. A crop or weak camera beat requires review rather than an invented visual PASS.

The first actual native preflight found 79 source-cropped frames at global frames 1400–1478: chapter 8 supplied a larger northern schematic state before its camera approach had reached the wider view. The director profile now explicitly frames that existing next-state geometry as chapter 7's **geographic context only**. Its `preTransitionContext` records the next chapter, original geometry IDs and reason. The territory/frontline is not drawn before its original source clock. This is a camera look-ahead, not a new historical observation or occupation event. The updated CPU camera contract checks all 2,400 frames and records zero source safe-area crops with its mock native predicate; the final actual native preflight is a separate requirement.

Rotation remains `BLOCKED_CURRENT_HISTORICAL_COMPOSITOR_HAS_NO_ROLL_CONSUMER`. The preserved 65422 scalar/presentation renderer can rotate, but copying its fictional scalar fields or counterfactual units into this historical Scene is prohibited. This director therefore reports zero roll rather than adding a different compositing effect.

The CPU contract test uses an explicitly injected always-valid native predicate. It verifies source resolution, the original adapter, all global frames, chapter continuity and unsupported-field failure. Only the browser runtime can establish actual native-layout and rendered-pixel results. `CAMERA_CPU_CONTRACT.json` must retain that distinction.
