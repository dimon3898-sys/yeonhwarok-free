# v020 reference effect layer verified public release

All required CI stages passed. The public image was pulled anonymously, its source revision and digest were verified, and both legacy OFF and default-v020 gateway login/health persisted for 61 seconds. Actual NVIDIA rendering remains NOT_RUN.

- Source revision: `3d24147ac1a7ef26a39c0866a42ce8b15f5b4711`.
- Public image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v020-reference-effects`.
- Image digest: `sha256:9d759dc334516174d395429de927092d3d5552b6734336dcd400cf2c0dcc15d9`.
- Third CI attempt: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37879845265/job/113656768319.
- Immutable public v019 parent: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:6bccc9c2df52052da743719269316c8cd8839502b13e408efc349c4f998d7ae4`, source `32a0477f64ee3a3596ef3dbfce6a89ce40f459fb`.

The two uploaded videos were decoded in full. Confirmed sparse entrance timing from reference frames 0–574 was mapped to the existing v019 scene. Suez and Singapore receive one short marker entrance each; Canal Closed and Canal Open receive short character reveals. Original wording, geographic anchors, camera motion, material, regional detail, licensed sources and audio remain preserved. The reference outro is excluded.

The v020 image sets `WORLD_ENGINE_REFERENCE_EFFECTS_VERSION=v020` to enable effects for newly generated eligible v019 24-second plans. `WORLD_ENGINE_REFERENCE_EFFECTS_VERSION=legacy` selects OFF for new plans. `apply_effects(parent_plan, enabled=False)` returns an independent, exact copy of the original v019 plan, including its gate. Saved scenes retain their explicit selection and cache identity when the environment changes.

Reference SFX remains unconfirmed in the mixed AAC track. Added SFX count is zero. Existing soft_pulse at 2 seconds/frame 60 and low_impact at 6 seconds/frame 180 are preserved. The regression suite checks exact 24-second raw and mastered PCM equality with effects OFF and ON.

## Required release validation

The final result is **969 unique tests PASS, 0 FAIL, 0 errors, 0 SKIP**: 732 core tests (701 inherited plus 31 v020), 206 independent proxy/GPU-logic tests, and 31 diagnostic-server tests. The early isolated 31-case stage repeats the same v020 cases already included in the core suite; it is not counted again.

The 24-check native adapter contract exercises actual inherited initialization, camera/material/overlay methods and visible effect receipts across all 720 frames. It verifies the same resource URLs and fetch counts under reversed asynchronous texture completion, with no duplicate or missing requests. Final-container admission also checks every inherited required asset identity (77 original plus 2 new render resources, 79 total), actual static serving, contiguous OFF/ON effect timelines and source/backend selection.

Additional passed CI stages include JPEG/FFmpeg/concat/audio/QC and checkpoint retry, inherited camera/frame-grid contracts, health/login persistence, and actual default-v020 production startup that stays fail-closed without physical NVIDIA for 61 seconds. Both release-tag absence guards returned404 and the source-HEAD guard passed. Anonymous pull verified the OCI revision and both legacy and default-v020 login/health persistence for 61 seconds. The actual default production entrypoint remained fail-closed without NVIDIA; these login fixtures do not claim GPU admission.

These are native admission and synthetic media checks. Recording Canvas2D uses explicit fixture font metrics. Physical NVIDIA/RTX4080S AFTER frames, shader compilation, GPU memory/timing and perceived output quality are **NOT_RUN**. No gcube workload or GPU start was performed.

## Current publication evidence

The first two attempts failed the native overlay regression and published no image. The second attempt also failed v020 preflight and identified the request-order assertion. Their bounded records are `CI_FIRST_ATTEMPT.json` and `CI_SECOND_ATTEMPT.json`. The third attempt changes the native test harness to verify identical concurrent resource inventories while deliberately reversing completion order; the six v020 runtime source files remain byte-identical to the first attempt.

The third attempt completed successfully at 2026-10-09T03:57:26Z. See RELEASE_VALIDATION.json and PUBLIC_IMAGE.json for the exact successful steps, test counts, digest and anonymous verification. No gcube workload request was sent; its current status was not queried.
