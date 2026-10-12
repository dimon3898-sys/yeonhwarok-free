# Camera Director V5 candidate

State: `V5_CANDIDATE` / `USER_VIDEO_REVIEW_REQUIRED`. This is not `V5_FINAL` or
`V5_GATE_COMPLETE`. The user must review the actual video; final Permanent Gate
validation follows user approval.

## Immutable baseline and scope

Reference: `V4_RECOVERED_EQUIVALENT_BASELINE`, source
`786521b87b5edd65dfd7ff507d2f0fbaa08f0152`, baseline manifest commit
`1bcd9d0b5ecc5385a61317ce70fa6927565c3d24`, manifest SHA256
`24bf44dc623991cc8c8fabf00a3f8df6f1f66af083b13b1c2953d00a058693b0`.
The old lost temporary V4 files are not the development target.

All 98 baseline payload/inventory/policy paths remain unchanged. The Renderer,
terrain/DEM/GIS/font bytes, palette, lighting, boundary/glow, glyph, layout,
scale, LOCAL admission, geographic marker anchor and V4 Reveal source are frozen.
V5 adds camera mathematics, a GPU binding adapter and capture/serving procedures.
The GPU adapter preserves the V4 GPU body and changes only its camera import,
evaluation entry, exported factory/version and initialization labels.

## Camera contract

`compileMinimumContextIntent` derives required space from actual Primary geometry,
event anchor/optional event geometry and explicitly selected direct relation
geometry. Optional country scenery is clipped against the primary/event corridor
for evidence; showing entire unrelated countries is not mandatory. Safe-area and
geographic-aspect fitting uses the smallest feasible extent. A sufficient starting
view skips expansion. Invalid Primary recognition fails instead of altering an
approved starting view.

`compileMinimumContextPlan` and `evaluateMinimumContextCameraFrame` use actual
seconds and C2 quintic center/log-extent curves. With a real geographic pan,
Context-to-approach keeps a shared nonzero pan tangent at the zoom maximum. For a
real zoom approach, center travel finishes earlier at the data-timed deceleration
boundary while zoom continues to the protected endpoint. The zoom curve's value,
velocity and acceleration are preserved at the additional pan-completion knot.
Coincident centers are explicitly `PURE_ZOOM_REVERSAL`; no fabricated pan is added.
With equal start/target spans, camera movement is pan only.

The plan explicitly reports `directorVersion=CAMERA_DIRECTOR_V5` while retaining
the V4 public Plan shape/version required by the unchanged Reveal compiler.
The GPU adapter passes the V5 evaluator to `compileGuidedRevealPlan`. Reveal
algorithm, profile, semantic order and geographic/layout eligibility stay intact;
frames are recomputed from the new motion, never assigned to a Suez timestamp.

## Verified fixture scope

- A, near: sufficient current view skips unnecessary expansion.
- B, far: actual far anchor requires minimum Context; Primary polygon is visible
  and anchor safe during the moving Context beat; C2 and actual pan/zoom phasing
  are checked. The supplied distant final excludes Primary, which is explicitly
  recorded as final-view feasibility and does not change that final. These are
  Camera tests, not a claim of a rendered synthetic scene with a new layout.
- C, sufficient context: unrelated scenery does not add zoom.
- Asymmetric safe areas, invalid recognition, polygon visibility, exact endpoints,
  alternate fps and coincident-center zoom are also covered by the pure tests.

Suez's preserved start already contains Egypt and the event in its safe viewport.
V4's 50.850836341463434 by 84.3740527725027 degree context is replaced by the
unchanged 14.9 by 23.355663772671775 degree starting view. Context expansion and
the zoom reversal are skipped; a continuous northward pan reaches the unchanged
REGIONAL framing. No closer LOCAL view is admitted. The compiled candidate has
250 frames at 30 fps (8.333333333333334 seconds), including the unchanged 2.6-second
minimum title perception budget. This shorter duration removes unused camera
travel and does not speed up a pre-existing video.

## Reproduce from development storage

Run from the repository root using the baseline's pinned toolchain:

```sh
bash tools/setup_v4_recovery.sh
node --test world-simulation-shorts-engine/tests/camera_director_v5.test.mjs
```

Saved `inputs/scene.json`, `inputs/camera-plan.json` and `INPUT_PROVENANCE.json`
are persistent runtime inputs. To verify a deterministic recompilation, write to
a NEW directory and compare JSON against these saved inputs:

```sh
node world-simulation-shorts-engine/recovery/v5/compile_inputs.mjs \
  --output-dir NEW_INPUT_DIRECTORY
```

The CPU capture CLI creates a new private output directory and runs a read-only
loopback server and Chromium 154.0.8037.57 with SwiftShader. All assets resolve to
the committed baseline paths; setup hydrates the two original LFS assets. The
approved endpoint PNG is used only by the comparator and is never a render input.

```sh
node world-simulation-shorts-engine/recovery/v5/render_candidate.mjs \
  --phase checkpoints --output-dir NEW_PRIVATE_CHECKPOINT_DIRECTORY
node world-simulation-shorts-engine/recovery/v5/render_candidate.mjs \
  --phase video --output-dir NEW_PRIVATE_VIDEO_DIRECTORY
```

Capture rejects changed input hashes, noninteger/out-of-range frames, a hardware
backend, GL errors, visible layout failures, changed geographic anchor, changed
LOCAL admission or a different final/initial decoded PNG. Video frames stream to
FFmpeg without resize or intermediate full-frame storage. Output is silent H.264,
1080x1920, 30 fps; ffprobe checks actual decoded count, dimensions and duration.

Checkpoint frames are derived from the plan/schedule. When expansion is skipped,
`02_MINIMUM_CONTEXT` is the last recognition frame and `03_DIRECTIONAL_TURN` is
the first event-travel frame; these images do not claim an expansion or turn
occurred. `04_EVENT_APPROACH` samples the actual approach state; `05_MARKER_GUIDE`
is derived from condition-based location readiness and follows that checkpoint.

## Candidate persistence and next Gate

Store development Source + runtime/build asset references + Camera inputs +
source/hash/dependency/import manifests and procedures in the candidate branch.
The shared assets remain in their permanent baseline paths, not copied to public
Proof. `public-review/` contains only the MP4, seven PNGs and SHA256SUMS. Internal
frame diagnostics and reports remain under `evidence/` in development storage.

Run the candidate validator before committing/publishing the candidate. Its
candidate preflight does not grant user approval or complete the final Permanent
Gate. After user video approval, all seven conditions must PASS with current-commit
clean checkout/reproduction and remote asset retrieval evidence:
SOURCE_PERSISTED, ASSETS_PERSISTED, HASH_MANIFEST_PASS, DEPENDENCY_MANIFEST_PASS,
IMPORT_MANIFEST_PASS, NO_REQUIRED_TEMP_FILES, CLEAN_ENV_REPRODUCIBLE.
Any failure means `V5_GATE_INCOMPLETE` and blocks the next development Gate.
No Event System, route animation, TTS, subtitle, audio, Planner or hardware work is
part of this candidate.

The provided eight 64306 direction/readability principles guide evaluation. The
identity of a preserved 64306 reference video was not verified, so direct video-to-
video matching with that reference is not claimed.
