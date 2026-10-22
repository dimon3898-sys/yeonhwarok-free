# Original protection gate and canonical source recovery

The immutable original 307-file manifest is retained without edits at
`recovery/g2-renderer-recovery-v1/reports/PROTECTION_BASELINE.json`.
Its SHA-256 is `cc09c9dca0262b800387df1d27e6ac91d0fd18d2c5c582862cc600baf843ce3e`.
The later G2 final manifest is also unchanged. Of the original 307 protected
files, 306 are Git files and one is a reproducible generated external Plan.

The new execution environment did not contain the old machine's private
canonical Plan or private capture caches. This is an environment restoration
condition, not evidence that this task deleted those files. Old inode/mtime
preservation is not claimed. All existing tracked G1/G2 evidence, media,
renderer, Scene, Asset and FINAL bytes are covered by the new complete pinned
Git snapshot in `reports/PROTECTION_BASELINE.json`.

## Exact canonical Plan

The existing durable recovery instructions are
`recovery/story-director-16frames-v1/EXACT_REPLAY_INPUTS.md`. They identify
`recovery/universal-overnight-v3/prepare_source_preview.py` as the original
source-bound canonical generator. That preserved program reuses
`PREVIEW_PROFILE.json`, the existing contract/Planner/backend and immutable
native payload. It does not start Chromium, a Studio job, a GPU or encoding.

The exact Plan was regenerated into a **new owner-only directory**, without
activation generation, ASTRA redownload, new geographic facts, source edits,
or an old file overwrite:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B \
  world-simulation-shorts-engine/recovery/universal-overnight-v3/prepare_source_preview.py \
  --destination /workspace/universal-data-pipeline-v1-private-20261022/original-source-replay \
  --image-digest sha256:a956c93e4b23bc1f73990d94948c85e4db0c2f18f0bdef301f61ad7882be4886
```

The image digest above is the original document's inert image binding. No
image was pulled, deployed or executed. Activation is optional in the
preserved preparer and affects only prepared runtime options, not Plan bytes.

The actual resulting `PLAN.json` is **179,907 bytes**, SHA-256
`33596c97b433887afb7ced6847d4ef63d099a9b6633546d541890a45c9c6289e`,
matching the original protected entry exactly. The returned `PREPARED.json`
also records source manifest SHA
`ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7`,
`renderStarted=false`, `gpuVerified=false`, and `full80sRenderAllowed=false`.
The original protected manifest's logical alias is resolved to this fresh
private Plan by the additive checker. The old report is not rewritten to
pretend its old absolute private paths are present.

## Checks and repeat verification

`tools/protection.py --acquire` runs only once before task commits. It hashes
every file tracked in pinned commit
`e39969cbc76a071d34a38440d9551425e6d5e545`, verifies its actual Git blob ID,
and stores SHA-256 and byte length in this task's own baseline. It also
captures the older checkout's HEAD and clean status. Later validation uses:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B \
  world-simulation-shorts-engine/recovery/universal-data-pipeline-v1/tools/protection.py
```

This verifies actual bytes for all 307 original protected entries and all
pinned Git files, checks that old recovery namespaces remain unchanged,
rejects task changes outside the new namespace, and confirms the older
checkout's HEAD/status are unchanged. It never resets, deletes, repairs,
re-renders or overwrites a protected source. Results are written only in the
new task's `reports/` directory.

Private generated aliases that were explicitly outside the original 307
count remain outside it. Their old path-dependent activation hashes and old
machine capture inode/mtime values are not claimed as newly verified.
