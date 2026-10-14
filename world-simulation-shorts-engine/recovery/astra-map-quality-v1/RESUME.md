# ASTRA integration resume point

State: PHASE_A_BLOCKED — accessible physical graphics GPU is missing.

Preserved parent: `development/moving-frontier-glow-fix-20261014`, `45af879d7417abba58e9ebd59d8e6630a785ac28`.
New branch: `development/astra-map-quality-20261014`.
Read the complete frozen `inputs/WORLD_ENGINE_CODEX_TOTAL_MASTER_20261014.md` before resuming.

Completed: input checksums and sample parsing; 65422 full 150-frame decoding and sequence inspection; current renderer read-only audit; existing four focused regressions; actual camera/source envelope over 150 frames; device inventory and hardware-only WebGL probe. All original inputs are preserved. No adapter, shader, camera, timeline, unit, ownership, FINAL or candidate media changed.

Resume prerequisite: graphics-enabled physical GPU worker or an authorized remote GPU runner. The current environment has no graphics device and hardware-only WebGL cannot create a context. Installing packages does not create a GPU.

Once the prerequisite is supplied, recheck device and hardware renderer identity. Preserve the old SwiftShader runner unchanged and create a new isolated hardware-aware runner. Complete the deferred Phase A 1080×1920 hardware baseline composition/performance capture with the unchanged V4 adapter before proceeding. Then continue Phase B from the supplied archive and known contracts. Do not repeat data research, prior development, full reference analysis, or already completed baseline tests without new concerns.

Respect partial sample coverage and the larger native overscan envelope. An explicit masked combination with the unchanged existing source may be tested; never stretch edge values, fake absent data, silently zero-fill, or claim full-scene high-detail coverage. Additional bounded same-source acquisition must follow the Master limits and recorded source/version/size rules.

Before any long render: implementation PASS → commit → push → confirm remote SHA. After proof: candidate commit → push → verify HTTP 200 and byte-identical downloads. No FINAL or 14-second expansion without user approval. No new movie exists at this checkpoint; USER_VIDEO_REVIEW_REQUIRED is not claimed prematurely.
