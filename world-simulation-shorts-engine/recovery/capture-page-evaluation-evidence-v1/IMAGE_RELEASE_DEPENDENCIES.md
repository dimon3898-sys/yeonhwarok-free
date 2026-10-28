# PAGE_EVALUATION image release dependency checkpoint

Status: **NOT_DEPLOY_READY**. No GPU deployment authorized.

## Confirmed
- Source candidate: `capture-page-evaluation-evidence-v1/candidate_capture_vulkan.mjs`, syntactic and exact-delta CI PASS: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/40644514234
- Exporter change: `codex-to-gcube-handoff-v1/controller/safe_capture_export.py`, stage allowlist CI PASS: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/40645252289
- Existing parent image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:eeb0e86441ca6b4cfcb62eedff1d41630c2c01178263363ea1ae48eb38cd993e`
- Parent runtime source root: `/opt/world-engine-handoffs/studio-diagnostics-v1/repo`
- Parent runtime manifest SHA256: `312d806393ab7776167a0977678df067b7b1f4ff3c8d25f9f119e549e0e74251`
- Parent startup manifest SHA256: `09d9f21f3fa58f5ec81e6753bb946def49d4f666ad58f88f104ad409e2f78ebc`
- Existing parent runtime manifest includes 352 source files. The original source manifest has 350; DO NOT reuse original 350-file image packaging contract.
- Current source manifest tracks `capture_vulkan.generated.mjs` by SHA256 and size. Copying the new candidate without regenerating this manifest will block startup.
- Startup manifest pins runtime manifest SHA256; the copied bootstrap's SOURCE_SHA constant and Docker ENTRYPOINT args must also use derived pins.
- The generated variant manifest `backend/GENERATED_SOURCE_MANIFEST.json` pins the three *other* variants, not this capture file; do not alter it without evidence.

## Minimal next execution
1. Derive a **new immutable image** from the above parent digest; never modify the parent.
2. Copy parent runtime tree to a separate new source root; replace **only** `capture_vulkan.generated.mjs` and `controller/safe_capture_export.py` from the current candidate branch.
3. Recompute those two manifest rows and regenerate the runtime manifest; update copied bootstrap's SOURCE_SHA pin and copied STARTUP_MANIFEST.json. Keep all other runtime files, supervisor, renderer, scene, auth unchanged.
4. Build a unique GHCR tag with no GPU access. Test default ENTRYPOINT, synthetic owner/origin/6-second plan (no render), installed stage allowlist, and original-parent immutability. Publish only after PASS; registry digest readback required.
5. Do not modify gCube #5373 or deploy until this derived image passes.

## Evidence limitation
The diagnostic marker identifies which `page.evaluate()` call failed. It does **not** fix the GPU root cause, and the private receipt's raw error text must not be exported. The prior capture failed 0/180 and had `PAGE_EVALUATION` category. No further GPU run should be authorized on a source-only candidate.

## Prohibited
Repeating previous 14/14 parent CPU tests, changing original renderer behavior, rebuilding the previous image unchanged, mutating main, changing Owner-code, unapproved paid GPU execution.
