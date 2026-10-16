# Independent V2 visual profile contract

`ref2_profiles.mjs` normalizes `activation.referenceV2 = {"variant":"F","parameters":{}}`. It is a Node-side Scene/profile adapter, not a change to the original Scene JSON parser or renderer API. New browser factories validate their own material groups again. An absent V2 profile selects A: all new features are disabled and the inherited Quality F render path remains unchanged. A production job requires the explicitly bound `REFERENCE_VISUAL_MASTER_V2_F` identity.

The following defaults describe the **opt-in V2 candidate**, not changed global defaults. Original entrypoints and original videos remain unchanged.

| Requested control | Parameter / candidate default | Allowed range and actual meaning |
| --- | --- | --- |
| Territory Color Strength | `territoryColorStrength: 0.84` | 0.72–0.90; alpha of the original cumulative newly-gained ownership mask only. Held/losing colors retain F style. Original source alpha is never weakened. |
| Territory Transition Timing | `territoryTransitionTiming: "SCENE_OWNED"` | **Not a new adjustable feature.** Only this value is accepted. Original control keyframes and all150 event indices remain authoritative; other values fail. |
| Frontier Glow Intensity | `frontierGlowIntensity: 1` | 0–1 multiplier of existing white core/halo alpha; cannot exceed the original public caps. Gold outer intensity has a separate 0–1 control. |
| Frontier Glow Width | `frontierGlowWidth: 2.5` | 0.5–2.5 nominal output pixels through the unchanged frontier API. This is not a newly measured rendered width. |
| Terrain Contrast | `terrainContrast: 1.2` | 1–1.4, local encoded-RGB source contrast on supported interior land only; no mesh, source height or invented normals. Coast/NoData neighbours disable local contrast. |
| ASTRA Edge Blending | `astraEdgeBlending: 48` | 8–96 output pixels, using the existing support-distance algorithm. Disabled source-grade variants retain old F's 32px setting. No GIS/coast mask blur. |
| Unit Marker Scale | `unitMarkerScale: 1.14` | 1–1.25 requested uniform static scale. Existing72–140px limit and all-frame SAT/Safe Area checks can reduce it. No artwork/anchor changes or size pumping. |
| Camera Focus Priority | `cameraFocusPriority: 0.65` | 0–1 priority between observed control change and existing screen focus when selecting a safe camera reading opportunity. It does not invent events or own a new camera director. |
| Camera Motion Smoothing | `cameraMotionSmoothing: 0.8` | 0–1 controls the Scene-only entry/exit ramp length (8–20frames). Existing C1 interpolation remains; unsafe candidates fall back to old F without weakened guards. C2 continuity is not claimed. |
| Event Hold Duration | `eventHoldDurationFrames: 0` | **Not implemented for this advancing excerpt.** Nonzero values fail. Event and object timing remain unchanged. |

`cameraReadHoldFrames: 10` is a separate, supported camera-only control: 0 disables it; otherwise9–12 are accepted. It freezes position, extent and roll after measured admission. It does not pause territory, moving objects or the story clock. The default selected Scene holds frames96–105 and uses18-frame ramps. The original F's inactive domain crop remains disclosed; the new camera creates zero additional cropped source-vertex frames and keeps the active front and every unit safe.

Additional bounded material controls are `gainBrightness` (1.12, range1–1.25, source-hue multiplier with headroom cap), `landExposure` (1.04,1–1.2), `oceanExposure` (1.2,1–1.5), `oceanTealMix` (.12,0–.3), and `terrainLightingMinimum` (.76,.65–1). All operate through the declared source-stage or original-lighting APIs. Negative land elevation does not select ocean; native GIS coverage and valid negative bathymetry are independent requirements.

Gold outer controls are `outerGoldIntensity` (.75,0–1), `outerGoldWidth` (1,.5–1.5 nominal output px), `outerGoldSigma` (2.2,.5–3px) and `outerGoldSupport` (6,4–6px). Finite support must exceed sigma and core width. Integer neighbour sampling has a minimum of one native pixel; subpixel physical width is not claimed. The effect uses only verified actual domain-union coverage, not all-land coverage, source color inference, a traced contour or a decorative route. Setting intensity0 removes its coverage dependency.

The profile variants independently isolate A inherited F, B gained style, C source material, D frontier/outer glow plus unit scale, E camera only, and F integrated V2. A–D use the same old F camera. E/F use identical candidate camera keys admitted against the larger F units, even though E displays old104px units. Source geometry, scenario, event clock and rendering resolution remain fixed.

Unknown fields, nonfinite numbers, type mismatches and out-of-range values fail explicitly. There is no force-admission, survey exception, country name, coordinate, event date, arbitrary runtime-module path or public render API in this contract. CPU/profile PASS does not approve NVIDIA performance or final video quality.
