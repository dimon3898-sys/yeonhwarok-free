# Exact global five-second preview

This adapter selects 150 frames from the original complete Scene JSON. It never
rebuilds the first scene, restarts a front, changes source coordinates, retimes
an event, or renders the complete eighty-second video.

`preview_contract.compile_preview(plan, bindings=..., start_frame=None)` returns
`WORLD_ENGINE_PREVIEW_REQUEST_V3`. Its trusted caller supplies six bindings:
`sourceCommit`, `sourceManifestSHA256`, `imageDigest`, `originalPlanSHA256`,
`completionProfileSHA256`, and `sourceCatalogSHA256`. A metadata binding alone
does not authorize rendering. Existing source-image, operator-cost, storage,
duplicate-job and actual GPU admission remain required at the Studio boundary.

The request includes an exact `[startFrame, endFrame)` range, immutable original
scene-slice hashes, the complete plan's semantic hash, local output PTS origin
zero, and the original global audio sample interval. `validate_preview` rejects
unknown fields, changed ranges, incomplete source timelines and unsupported
frame counts. `verify_preview_request_file` additionally verifies actual source
bytes using bounded, no-follow file reads.

For the preserved source plan, the final automatic selection is
**[1400,1550), 46.666666…–51.666666… seconds** within original scene-0007.
The package-owned camera cache contains exactly 200 observed global frames from
source-bound SwiftShader captures. It is checked against the semantic plan,
completion profile, and ten unchanged camera/layout module hashes; only the
thirteen image-digest slots already permitted by the original history authority
are neutralized in its cache identity. Unknown frames are not static poses.

The selector ranks genuinely observed camera activity jointly with the original
source transition schedule. The selected interval has 48 measured bounds
variants, 47 changing pairs and 100 authored active frames. It retains 50 frames
of source-qualified carry-in context and 50 frames of the chapter's schematic
transition. Those source qualifications remain visible and unchanged. No
coordinate, camera pose, event or interpolation is created by the cache.

The experimental coherence-only [1450,1600) selection was actually rendered and
found to be static. Its media and failure report are preserved in
`proof-coherent-static`; it is not the final review selection. Neither scoring
method grants historical accuracy, NVIDIA admission or visual-quality approval.

Production entry: `preview_capture.mjs` with `--request-file`, `--plan-file`,
`--plan-sha256`, `--admission-file`, and `--output-root`. It calls the separate
overnight runtime and retains its original NVIDIA hardware checks. The caller
must hold the original common GPU lease and complete Studio policy admission.
There is no full-eighty-second entry in this adapter.

The explicit `capturePreviewWithRuntime` harness requires a real, separately
marked SwiftShader runtime. Its result is `SOFTWARE_PREVIEW_TECHNICAL_PASS` with
`hardwareVerified: false` and `visualQualityApproved: false`. Production never
falls back to that harness after a hardware failure.

Original per-scene bounded capture is reused. Cross-work-unit ranges open each
original immutable scene and keep original global frame numbers. Newly created
PNG files are linked into local encoder sequence 0–149; existing scenes, cache
entries and results are neither renamed nor deleted. The original H.264 encoder
and full-decode checks produce `preview.mp4`, five checkpoint PNGs,
`SHA256SUMS`, `PREVIEW_RECEIPT.json`, and `PREVIEW_COMPLETE.json`.

SFX: `preview_audio.render_preview_sfx(settings, plan, request, output_wav)` reuses
the original licensed Studio mixer and complete authored cue schedule, then
copies exactly 240,000 PCM samples from the original global position. This
preserves cue tails, stable variants and cooldown decisions. Only CPU audio is
mixed in full; no full-length video is rendered. `mux_preview_sfx` reuses the
old AAC muxer and verifies unchanged video pixels and timestamps. SFX OFF is
supported without writing audio.

Focused preview validation: 17 Python tests and 7 Node source-contract tests.
The integrated overnight CPU receipt separately records all 143 focused tests. These test
actual source-clock selection, the 2,400-frame source-evaluator slice, raw-file
and scene immutability, exact PCM equality, failure guards, and the original
encoder contract. They do not assert NVIDIA execution or visual-quality PASS.

The production CLI now forwards actual cumulative output frames as bounded
`SCENE_CAPTURE` JSON; it does not invent progress or an estimated finish time.

Additional source authority: the new package-owned `EXTENSION_SOURCES.json` is
merged with the immutable parent catalog only after both manifests and canonical
payload SHA checks pass. The same effective catalog reaches Python admission,
preview binding, the original Event/Flow compiler, and optional visual consumers.
The shipped extension has **zero** new source records. Synthetic records remain
CPU-test-only and are refused in Studio production.

Trusted CPU caller: `camera_activity.load_bound_camera_evidence(plan, bindings)`
then `compile_preview(..., camera_evidence=evidence)`. Studio obtains this from
its manifested package; client-supplied camera traces are not a prompt field.
The consumer validates the same authority when reading an exact preview request.
