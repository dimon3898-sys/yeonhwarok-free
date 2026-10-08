# v014 Integer Frame Grid

## Confirmed defect

The v013 scheduler snapped time to `ceil(seconds * 30) / 30`, then rounded that result to six decimal seconds. Scene boundary accumulation and last-scene residual adjustment propagated that lost precision. Production `engine/gpu_preflight.py` correctly rejected durations more than `1e-7` frames off the grid. The validator tolerance was not weakened.

The preserved v013 shipping plan reproduces the reported pattern:

| Scene | Old duration | duration × 30 | Before | Integer frames | After |
|---|---:|---:|---|---:|---|
| S001 | 2.133333 | 63.99999 | DURATION_FRAME_GRID_INVALID | 64 | PASS |
| S002 | 2.933333 | 87.99999 | DURATION_FRAME_GRID_INVALID | 88 | PASS |
| S003 | 3.100000 | 93 | PASS | 93 | PASS |
| S004 | 3.833334 | 115.00002 | DURATION_FRAME_GRID_INVALID | 115 | PASS |

This is the committed v013 shipping fixture, not a newly acquired gcube Diagnostic ZIP. No gcube workload was accessed, started, changed or rendered.

## Fix

`engine/frame_grid.py` allocates integer frame budgets before accumulating boundaries. Rational FPS is supported by the allocator. Current production FPS comes from the existing render-quality configuration. Seconds are derived views of integer counts, without six-decimal serialization rounding. End frames are exclusive.

Scene JSON stores `scene_start_frame`, `scene_end_frame` and `frame_count`; metadata stores the FPS and complete frame-clock receipt. Production preflight checks this contract in addition to its original checks. Old loaded projects are not automatically migrated. Source fingerprints distinguish newly generated plans.

| Scene | Start frame | End frame | Count | Start seconds | End seconds | Perception hold frames |
|---|---:|---:|---:|---:|---:|---:|
| S001 | 0 | 64 | 64 | 0 | 2.1333333333333333 | 52 |
| S002 | 64 | 152 | 88 | 2.1333333333333333 | 5.066666666666666 | 43 |
| S003 | 152 | 245 | 93 | 5.066666666666666 | 8.166666666666666 | 48 |
| S004 | 245 | 360 | 115 | 8.166666666666666 | 12 | 61 |

Total: 360. Last end: 360. Gaps: 0. Overlaps: 0.

The generated plan has unchanged camera start/end, lighting preset and render quality relative to the preserved v013 fixture. GPU graphics profiles, renderer, proxy, audio, diagnostic packaging, checkpoint, retry and FFmpeg contracts are inherited from the immutable validated v013 image. The existing preflight gained only an integer timing-contract check; its GPU/geometry/duration predicates remain unchanged.

## Evidence

- `PREFLIGHT_BEFORE_AFTER.json`: summarized real production collect-all results, including assets, all-scene native geometry, paths, FFmpeg capabilities, concat policy and actual audio preparation.
- `PREFLIGHT_BEFORE_AFTER_FULL.json.gz`: complete native reports, including the newly generated plan admission.
- `NEW_PLAN.json`: actual newly generated renderer input with integer timing fields.
- `DURATION_CASES.json`: 12/15/20/75/80-second reference beat allocation; planning only.
- `FPS_VARIABLE_SCENES.json`: 150 allocator cases at 24/25/30/60/29.97/30000/1001 FPS and variable scene counts. This is not alternate-FPS GPU renderer certification.
- `PRESERVED_SOURCES.json`: preserved source hashes and the explicitly scoped timing-validator extension.

Actual NVIDIA scene draws are NOT_RUN in this task. GPU validation is not bypassed and CPU/software GPU fallback is not enabled.

## Release verification

- Final container CI: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37722783466
- Core: 576 PASS. Independent proxy/GPU logic: 206 PASS. Unchanged diagnostic tests: 31 PASS. Total: 813 PASS, 0 FAIL, 0 SKIP.
- Container dependencies/assets/native four-domain fixtures/synthetic JPEG→FFmpeg→concat→audio→QC/checkpoint-retry: PASS.
- Container actual production collect-all: old fixture [FAIL, FAIL, PASS, FAIL] → corrected fixture [PASS, PASS, PASS, PASS]; freshly generated plan also PASS.
- Owner login, health, production fail-closed without physical NVIDIA, and >=61-second server persistence: PASS.
- Anonymous Docker pull and independent anonymous manifest/config read: PASS.
- Image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v014-framegrid`
- Digest: `sha256:948a8cc6d9d8bebc221ef1d02fbc186fb036e89f3d6d995cc0e9e497a4608577`
- Source revision: `3335c5b1b8d35d18a3be7f4ac44f25b3e078e6ef`
- gcube production GPU run: NOT_RUN. Existing tags were not overwritten.

Create a new plan with this image; preserved old approved plans are not silently rewritten.
