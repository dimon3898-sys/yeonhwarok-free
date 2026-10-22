# Independent visual observations

Status: **QUALITY_REVIEW_REQUIRED / USER_REVIEW_REQUIRED**. This independent review covers the earlier actual probe PNGs and, subsequently, nine decoded contact pages containing all 540 actual movie-frame thumbnails plus 15 selected 1080×1920 frames. The exact inspected files and hashes are recorded in `reports/VISUAL_REVIEW.json`. It is not 540 full-resolution manual inspections, full-rate playback, NVIDIA validation or reference-quality approval. Images were opened with the image-view tool; no video was decoded or rerendered by this reviewer.

## Fictional-area probe, actual frame indices

Input at the time of this probe: now preserved as `examples/archive/FICTIONAL_AFRICA_PRE_CONTINUITY_NL.json`. Probe folder: `/workspace/up2-fiction-probe-20261022-03/`. Each image is 1080×1920. Global frame numbering is zero-based at 30 fps.

| Frame | Visible observation |
|---|---|
| 0 / 0.000 s | Namibia and surrounding terrain/coast are visible; no colored fictional area is visible yet. |
| 45 / 1.500 s | A narrow translucent red rectangle has a bright yellow outline. A wider, much fainter rectangle is also visible. Terrain detail remains visible through the area colors. |
| 89 / 2.967 s | The wider rectangle is clearly blue with a yellow outline. Its width and screen position differ from frame 45, while the coastline has also changed scale/position. |
| 90 / 3.000 s | The explicit second-scene cut changes the framing and the colored area is absent at the first frame of the new scene. The blue rectangle visible at frame 89 does not continue visibly across this cut. |
| 135 / 4.500 s | The wider blue area and a faint narrower inner boundary are visible as the second scene contracts toward the smaller supplied geometry. |
| 179 / 5.967 s | A narrow red area remains with the yellow outline. The map framing differs from the intermediate zoomed-out sample. |

The coastline, southern tip and inland terrain shift and change scale between samples. These images therefore provide direct evidence of camera framing variation instead of six copies of a fixed map. Sparse images do not establish that every intervening camera frame is smooth.

The fictional polygons were deliberately supplied as rectangles: `ZONE_SMALL` spans longitudes 14.8–16.8 and latitudes −26 to −20.5; `ZONE_LARGE` retains the same west/south/north values and extends east to 19.2. Their yellow rectangular outlines and colored fills correspond to those input geometries. They are **not evidence of a rectangular raster-tile seam**. The sampled map background shows no obvious unrelated full-height vertical seam or rectangular change of terrain material. This observation is limited to the inspected images and their visible map extent.

The intermediate images retain two visible outline/fill footprints at once. This reads as transition between supplied states rather than a single continuously deformed irregular front. The display remains schematic and is not an irregular historical frontier or evidence of actual territorial ownership.

## Confirmed continuity limitation

The first-frame disappearance at global frame 90 follows the unchanged Scene-to-Area adapter: `web/map_infographic_v1/planner_engine_adapter_v1.mjs` creates `AREA_REVEAL` operations at scene-local frame 0 using `initial_reveal_frames`. Each example scene has its own original Area timing. The runtime owner confirmed that the new renderer follows this timing and does not silently manufacture a carried-over state.

This is an explicit-cut demonstration with re-reveal, **not seamless cross-scene territorial continuity**. A production narrative requiring continuous ownership across scenes needs a separately specified continuation contract; this review does not authorize changing the protected Area engine or hiding the observed discontinuity. The frame-90 observation must remain visible in the final assessment.

After this observation, the parent approved a separate opt-in `initialStateVisibility: "PRESERVE_PROVIDED"` extension for matching adjacent supplied states. Only that new presentation sidecar was added to scene two of the current fictional input; its original facts and geometries remain unchanged. `evidence/FICTION_CONTINUATION_PROVENANCE.json` records the exact input hashes. The six pre-fix PNGs above do not establish that the extension fixes the output; post-fix draw and boundary inspection are still required.

The location highlight is scheduled outside these six reviewed samples. Its visual appearance is not established by this sample review. No labels, explanation text, troop positions or historical facts are inferred from the PNGs.

## Post-fix boundary review

The actual subsequent probe files `/workspace/universal-presentation-v2-private-20261022/E-probes-v2/fictional-continuity-draw/FRAME_089.png`, `FRAME_090.png` and `FRAME_091.png` were also opened individually. The wider translucent blue supplied area and its yellow outline are visible in **all three**. The frame-90 disappearance observed before the fix is resolved at this inspected boundary. Exact file hashes and review scope are preserved in `evidence/FICTION_CONTINUITY_VISUAL_AFTER.json`.

The authored cut still changes the map scale and position between frames 89 and 90. Preserving the supplied geographic state does not make that cut a smooth camera continuation. No complete-movie or final-quality approval follows from these three PNGs.

## Actual Studio movies: manual scope

For each movie, the three `FRAMES_000_059`, `FRAMES_060_119` and `FRAMES_120_179` contact pages were viewed. Thus every decoded frame is represented at thumbnail scale in the manual review. The following native frames were additionally opened:

| Movie and actual audit folder | Native frames viewed |
|---|---|
| Aviation Europe: `reports/MOVIE_AUDIT_1_TRACE_SCOPED` | 20, 89, 90, 110, 179 |
| Trade South America: `reports/MOVIE_AUDIT_2` | 20, 89, 90, 179 |
| Fictional Africa: `reports/MOVIE_AUDIT_3` | 20, 45, 89, 90, 135, 179 |

The parent separately performed decoding, frame counts and trace/geometry pixel audits. Their `ACTUAL_MOVIES_AUDIT.json` receipts are technical evidence and are not relabelled as visual-quality approval here. Tiny seams, aliasing or one-frame detail defects can be missed at thumbnail scale; absence of an obvious seam is not a guarantee of pixel-level perfection.

## Aviation Europe

Europe's coastlines and land extent visibly move and change scale through the first scene. The second scene uses a different framing and restrained pan associated with the supplied reverse route; the camera is not tightly locked to a vehicle at the screen center.

A bright yellow bent line follows the supplied Hamburg/Berlin/Munich connection. A yellow triangular moving glyph progresses toward the southern endpoint by frame 89 and points toward the northern endpoint by frame 179 after reversal. The red-centered, white/black-ring locality pulse is clearly visible near Hamburg in native frame 20 and Munich in frame 110. These marks are readable as a path and emphasis; the moving glyph does not visually establish an actual aircraft type or real scheduled flight.

The real cut at frame 90 visibly reframes the map and starts the second route reveal anew. The route is absent at that exact first frame, while the map remains present; this is distinct-scene reveal semantics, not continuous vehicle motion across a seamless edit.

The actual runtime selects `GLOBAL_EARTH_DAY_RGB_V1` for both segments after full camera-envelope admission. The map has green/brown photographic color and a dark, relatively flat sea, with visibly soft terrain detail at the larger framing. This is the explicitly disclosed global RGB fallback, not a claim that a full-resolution NE1 raster, original DEM or bathymetry was newly loaded. No obvious rectangular material patch or full-height vertical seam was noticed in the inspected pages/native samples.

## Trade South America

The Chile/Andes coastline and mountain features remain visible while the first scene changes scale and the second scene pans modestly with the reverse connection. Native frame 20 shows the contrasting locality pulse at the northern endpoint; frame 89 shows the moving triangular glyph at the southern endpoint, and frame 179 shows it returning north. The line follows the provided three-city geometry, including its inland bend. It is an illustrative city connection, not a verified navigable shipping lane or trade observation.

The cut at frame 90 changes framing and restarts the supplied reverse route reveal. No black output frame or unrelated rectangular material seam was apparent in the viewed material. The strong pale hillshade/Andes texture differs visibly from the global RGB used by the Europe case. Runtime metadata identifies the retained native NE1 crop and baked-hillshade treatment; the upstream full NE1 dimensions are a reference, not proof that its unavailable full TIFF was materialized.

## Fictional Africa

The actual 180-frame contacts show small red footprint → wider blue footprint → small red footprint, with intermediate overlapping faded rectangles. Frames 89 and 90 both retain the wider blue supplied state after `PRESERVE_PROVIDED`; the earlier scene-cut disappearance is not present in this final movie boundary. The authored camera cut remains visible.

The red/white/black Windhoek pulse is clear in native frame 20. Terrain remains visible beneath the translucent colored regions. The yellow rectangular outlines correspond to explicitly supplied synthetic polygons, not texture-tile edges. No separate unexplained map-material rectangle was noticed in the inspected samples.

The transition visually crossfades between supplied rectangular footprints. It does not demonstrate a continuously sweeping irregular historical front. No real ownership, military location or historical boundary is inferred from this synthetic example. The actual runtime uses a retained NE1 native crop with baked hillshade.

## Quality limits and remaining approval

These three movies show distinct supplied-data topics, camera changes, real scene cuts, path progress/reversal, location emphasis and Area state changes. They are technical demonstration candidates. The fairly wide framing, simple triangular moving object, schematic rectangular regions, restrained camera follow and source-dependent terrain style remain visible limitations. They do not establish reproduction of the advanced 65422 candidate or reference-level cinematic quality.

This reviewer did not directly compare the reference video or inspect all 540 frames at native resolution, listen to audio, watch full-rate playback or test an Android device. Mobile playback, final aesthetic judgement and any reference-level approval remain **USER_REVIEW_REQUIRED**. No image-quality PASS, NVIDIA PASS or FINAL promotion is declared.
