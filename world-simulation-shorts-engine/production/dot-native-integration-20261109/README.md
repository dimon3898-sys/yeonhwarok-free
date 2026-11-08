# NVIDIA candidate connection — staging overlay

This overlay carries the existing official candidate source family through the existing NVIDIA controller, worker and single 300-frame capture loop. It does not start jobs or grant GPU approval. The frozen universal-presentation sources, existing images, main and recovery commits remain unchanged.

Apply `engine-overlay/` only to an isolated copy of the pinned repository. Keep the original source family: the NVIDIA generated-source verifier still requires its exact pins. The new `official-candidate-v1` namespace preserves that separation. The 300-frame candidate route is enabled only by the server registry pair; the previous six-second route retains its original normalizer.

Actual authored inputs are compiled by the controller. Registered source qualification, activation, exact wire bytes and per-scene identities enter the sealed plan. The existing worker still owns consent, image/source pins, budget, lease and capture supervision. Candidate scenes use separate local origins and release their prior session. The existing encoder receives all 300 frames. The native guard still requires three real NVIDIA/Vulkan draws before any GPU claim.

The changed source dependency entry uses the preserved source controller. The Dot version only changed its free-worker start hooks; this NVIDIA path calls its normalizer and never its submit/start methods.

Public exclusions: `CANDIDATE_SOURCE_CREDITS_REFERENCE.json` contains private provenance paths and is not included. The original is preserved privately. Runtime attribution text is retained in `candidate_source_credits.mjs`; source pixels and raw archives are not included here. Private registry paths, generated browser records and submissions belong in the private continuation package.

Validation outputs describe their exact CPU scope. A normalization-only source manifest is not an image manifest. No render, visual-quality approval, GPU approval or deployment readiness follows from these checks. Do not rebuild/deploy until CHECKPOINT's visual and image/source-closure gates are completed.

The test helpers accept an isolated prepared repository and an existing output directory. The binding test also needs a privately produced native submission. They never fetch original ZIPs or run a renderer. Existing PASS suites are not invoked.
