355-source label packaging — source-only preparation

Base: 5e4ed42496c45333126c08166571598d9fcf0495.
No image was built, pulled, published, started, or dispatched by this work.
The existing G2 image and all prior PASS evidence are reused unchanged.

Confirmed new connection defects
1. capture_nvidia.validateVariantManifest still required the pre-label runtime
   original SHA. The actual baseline validator rejects the label manifest with
   HANDOFF_EXACT_VARIANT_SET_REQUIRED. Only that original SHA is refreshed.
2. build_variants.derive_runtime omitted the existing diagnostic instrumentation.
   It now reproduces the committed instrumented label runtime exactly. The new
   --verify-existing mode checks committed variants without writing/regenerating.
   The historical no-argument generator and old patches are not a packaging path
   for this snapshot, and were not executed or claimed to pass.
3. The 355-row manifest carried an older, uninstrumented native_guard hash/size.
   Its row now matches the unchanged repository AND successful G2 image source.
   No native guard, Chromium options, renderer, Scene, camera or lease code edits.

Supported source preparation route
- Read CHECKPOINT and RESULT.json first; do not repeat completed tests.
- On a newly changed snapshot only, run the read-only variant linkage gate:
  python3 -B recovery/codex-to-gcube-handoff-v1/backend/build_variants.py --verify-existing
  (paths above are relative to world-simulation-shorts-engine).
- package_labels.py plan/prepare/verify uses fixed candidate and historical G2
  manifest pins. Its --repo must be an absolute repository root; --context must
  be a fresh, separate absolute directory with an existing parent.
- This stage already ran prepare/readback once. The committed CONTEXT_PLAN.json
  and Dockerfile.preview preserve that result. Do not repeat it without changes.
- The new tool has no Docker, registry, network, subprocess or dispatch facility.

Parent and closure
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da
Image source root remains /opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo.
353 historical rows + exactly two new label module rows = 355 current rows.
333 identical G2 rows are inherited by metadata; their source files are not
rehashed by the packager. Twenty changed and two new sources are copied with
the runtime manifest, bootstrap and startup manifest: 25 overlay files total.
COPY pins all file bytes and ownership/mode; existing directories/config remain
inherited. Declared ENTRYPOINT changes only startup/source manifest SHA indices
10 and 14. Runtime, bootstrap SOURCE_SHA and startup hashes agree.

Input sample
../visible-labels-v1/GENERIC_LABELS_10S.json remains the authored 10s/300-frame
input. It is a separate controller input, not executable source or an automatic
render request. Its existing 29-case label and 28-case duration proofs are reused.
No sample compilation, pixel preview, 6s/GPU or old suite was repeated here.

New verification only
5 runtime/import/admission cases + 6 read-only variant cases + 10 context cases
= 21 distinct PASS, each suite executed once, all exit codes zero.
New context tests verify fixed snapshot admission, minimal copy scope, inherited
source read prevention, declared entrypoint, readback, modes, limits and rejection
of substitution, traversal/cycles, source/context tamper, symlinks and reuse.

Remaining gates
This is SOURCE_CONTEXT_AND_DECLARED_OCI_ENTRYPOINT PASS, not installed-image or
GPU PASS. A separately authorized candidate build still needs fresh free-runner
cost/capacity/permission checks and installed 355-file/bootstrap/OCI verification.
GHCR publication needs its existing separate access/approval gates. Actual NVIDIA
10s label framebuffer/video/readability and reference quality require separate
GPU approval. No existing image/tag/digest or main branch changes are authorized.
