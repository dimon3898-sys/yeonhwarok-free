# Independent visual observations

Status: **USER_REVIEW_REQUIRED**. This is a human-visible review of six actual renderer probe PNGs, not a full video review, NVIDIA validation or reference-quality approval. The files were opened individually with the image-view tool. Exact dimensions and SHA-256 values are recorded in `evidence/FICTION_PROBE_VISUAL_REVIEW.json`.

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

## Remaining visual review

Full MP4s for the three demonstration types have not been reviewed in this document yet. Complete frame audits, decoded playback, route-follow motion, event-highlight visibility and comparison against the reference remain separate evidence. No final image-quality PASS is declared.
