# Reference Visual Master V2 — implementation record

Status: C–G are implemented and CPU-verified. Integration, software GL and image checks are pending. This is not a video-quality approval or a hardware result.

## Reference and comparison limits

The actual attachment is `WORLD_ENGINE_REFERENCE_65379_COMPRESSED.mp4`, SHA-256 `5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6`. The request calls it `65395.mp4`; no separate file under that alias has been verified. All 958 native frames were decoded successfully. Duration is 31.813189 seconds. The final approximately 3.8 seconds show a flag/outro presentation, not the same territorial-change phase as the first part.

`analysis/REFERENCE_STORYBOARD.md` records the full temporal review, UI exclusions and semantic alignment. The comparable existing event window is 5.181813–10.181813 seconds. Phone status/navigation, social controls, channel/footer and subtitle overlays are excluded. Masked pixels are unknown, not map failures. Reference screenshots, phone UI and the uploaded MP4 are excluded from the image package and public review.

An actual NVIDIA-rendered F MP4 has not been inspected in this task. Current-F comparisons use saved actual SwiftShader pixels and immutable source data from run 38821837659-1. They do not establish NVIDIA frame performance, MP4 quality or user video approval. Source/content comparisons must not be presented as a frame-registered video comparison.

## Confirmed findings and changes

1. **Territorial change.** The original classifier already distinguishes held, newly gained and losing territory. F selected the same held/gained material. The new opt-in decorator changes only the cumulative gained material through the existing shader's supported uniforms. Source hue, fixed initial boundary, moving boundary, ownership and event clock remain unchanged. This is cumulative gain, not an invented per-pixel acquisition-age effect.
2. **Source material.** Existing 32px support-distance blending is reused. There is no claim that all bathymetry sign/coast transitions are defects. A new source-stage contrast/exposure/teal grade uses actual per-role support and native GIS coverage. Unsupported and NoData pixels retain the old source. Contrast does not borrow sea or unsupported neighbours. Candidate values are clipped before the support mix, preserving even unsupported RGB 255 exactly. The source output texture is returned before territory and original frontier lighting.
3. **Frontier.** No ownership/motion synchronization defect was found in the original algorithm. It remains delegated unchanged. The new expression uses legal original white-core/halo profile values. A separate finite gold outer treatment uses only the opaque, geometry-verified, same-frame native G+B domain union. It excludes the shared internal boundary and unrelated R-only land. Projection/frame/domain checks, viewport edge clamping, protected reservations and original GL state restoration are explicit. SCREEN composition retains pure-white original front pixels.
4. **Units.** Existing 8-unit artwork, national profiles, roles, count, anchors, headings and visibility arrays remain unchanged. A static requested scale is checked with the existing national-unit SAT/layout evaluator at every frame. Current F selects 1.14: 118.56px texture square, measured artwork bounds 105.59–108.08px wide and flag width 75.8784px. These are CPU geometry measurements, not yet rendered-pixel measurements. All 150 frames have zero overlaps, critical collisions and Safe Area violations; minimum Safe Area margin is 196.57px. Request 1.25 is limited to 1.14. No size pumping or new layout engine is introduced.
5. **Camera.** A Scene-owned C1 cadence selects a measured 10-frame position/extent/roll plateau at frames 96–105. Event and object frames continue. Entry/exit ramps are 18 frames. All 150 frames respect the existing native floor/envelope, active-front safety and 118.56px units; additional cropped source vertices are zero. The original F already crops some inactive domain vertices (whole-domain-visible frames 0/150), so full-country visibility is not claimed. Maximum center step changes 4.9933→5.3003px/frame and sampled acceleration .16879→.84002px/frame². Original camera code remains unchanged; C2 acceleration continuity is not claimed.

## Focused verification and persistence

| Stage | Evidence | CPU result | Remote checkpoint |
| --- | --- | --- | --- |
| A | Full native decode, PTS/RGB cross-check, UI/content alignment | 958 decoded, zero decode errors | 88e5cca |
| B | Actual source/interface findings | Recorded, no protected edits | 68ef078 |
| C | `tests/test_gain_style.mjs` | 9 PASS | 57c5b9e |
| D | `tests/test_source_grade.mjs` | 11 PASS | 1471ea0 |
| E | `tests/test_frontier_ref2.mjs` | 9 PASS; GL calls explicitly mocked | 5e6be75 |
| F | `tests/test_unit_size_profile.mjs`, `STAGE_F_UNIT_AUDIT.json` | 9 PASS; all150 layout samples | 077d1ee |
| G | `tests/test_camera_profile.mjs`, `STAGE_G_CAMERA_AUDIT.json` | 9 PASS; all150 pose/layout samples | This checkpoint |
| H–J | Integrated runtime, actual SwiftShader, image/pull | Pending | Pending |

Branch: `development/reference-visual-master-v2-20261016`. Each checkpoint above was pushed and the remote head confirmed. All changed files so far are additions inside this new namespace. Existing FINAL, V4, parent Quality F, source samples, geometry, artwork, approved videos and images have not been changed. `STAGE_LEDGER.json` is the current ordered record. `PROTECTED_BASELINE.json` records parent image/manifests and exact old F raw-RGBA regression hashes.

No paid job, gCube deployment, NVIDIA render, longer video expansion, Permanent Gate or FINAL promotion has been executed. Event retiming and nonzero story hold are not implemented by the new visual material controls. The later profile contract must reject unsupported controls explicitly.

## Pending completion evidence

- H independently bound execution profile, source manifest, job namespace and capture signature.
- I actual SwiftShader A–F `draw/readPixels`, old-F regression, source/coast/NoData/domain composition probes, job/storage tests and Secret Scan.
- J unique image build/push and independent immutable digest pull/source verification.
- Concrete hardware execution and Dropbox download instructions; no hardware or final visual PASS before actual user-approved GPU results.
