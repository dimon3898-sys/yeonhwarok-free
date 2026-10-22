# Baseline, immutable backup and authorized scope

Base commit: `5cc9b98c628324814e1e63f9d0f8c6254ee84174`.
New branch: `development/reference-director-v2-20261022`.
New additive namespace: `world-simulation-shorts-engine/recovery/reference-director-v2/`.

The uploaded `WORLD_ENGINE_NEXT_CODEX_INSTRUCTION.txt` was read in full, followed
by the four prior capability/data/source/restart reports it names. Its phase1
item4 expressly authorizes a limited change to one protected file. The saved
authorization SHA-256 is
`166b980f02c6ccf8fdecf51b79a8412560a565e8802ba81cb4bc8821268d6142`.
No other protected file, FINAL, approved media, cache, or previous worktree is
authorized to change. The original307 manifest remains immutable.

## Before-change evidence

`tools/protection.py --acquire` ran before any protected renderer modification:

- Original307 source-contract SHA and actual307 file hashes: **307/307 match**.
- All6,877 tracked files at5cc9b98: actual SHA-256, size and Git blob equal.
- Four previous worktrees: HEAD and clean porcelain state captured unchanged.
- Five existing private/cache roots:1,135 inode/size/mtime/mode metadata entries
  captured unchanged, including the previous reference-director-v1 private root.
  Cache contents were not rehashed, repaired or rewritten by this metadata check.
- Only the new namespace was written. Initial result: **PASS**.

The exact307 original source manifest is
`recovery/g2-renderer-recovery-v1/reports/PROTECTION_BASELINE.json`, with SHA-256
`cc09c9dca0262b800387df1d27e6ac91d0fd18d2c5c582862cc600baf843ce3e`.
It has not been updated to make a changed renderer appear unchanged.

## One explicitly authorized protected file

Path: `world-simulation-shorts-engine/web/map_infographic_v1/renderer.mjs`.

- Original SHA-256:
  `e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38`.
- Original size:53,468bytes.
- Immutable task backup: `backups/renderer.5cc9b98.original.mjs`, mode0444.
- Backup bytes equal the original SHA and the exact5cc9b98 Git blob.

The authorized semantic scope is opt-in shared geographic similarity/rotation,
paired forward/inverse projection, terrain inverse sampling, and all-four-corner
source-envelope validation. Existing flat defaults, `updateCamera(bounds)`,
globe behavior, source admission and minimum-detail constraints must remain.
No completed-frame postprocessing rotation is authorized.

Before applying the first protected-file edit, a candidate is written inside the
new namespace. `tools/protection.py --proposal /absolute/new-namespace/candidate`
requires the live renderer still to match the original SHA, then records the
original/candidate SHA, byte counts and exact unified diff. That receipt is a
pre-change evidence artifact; it does not assert a pixel or feature PASS.

After a real authorized edit, the protection result must be reported as
**306 original protected files unchanged +1 explicit authorized modification**,
with both hashes and its exact diff. It must not be described as307 unchanged.
Any other changed protected/tracked file, old worktree or cache entry causes a
FAIL. A missing live renderer is not treated as an authorized modification.

## Rollback and recovery boundary

No restoration is performed by the protection tool. If regression cannot be
resolved, the reviewer has the original Git blob and an independently hashed
0444 backup of this single file. A rollback can restore only that authorized
renderer in the new branch, verify its original SHA, and rerun affected gates;
it does not require a reset, deletion, cache removal, forced push, or edits to
any old worktree. The original307 manifest stays unchanged in either direction.

Per-function changes and the proposed implementation diff are supplied by the
projection owner. Protection verifies scope and file preservation, while actual
default/opt-in draw/readPixels regression is a separate mandatory gate.

Evidence: `reports/PROTECTION_BASELINE.json`, `reports/PROTECTION_INITIAL.json`,
the pre-change proposal receipt/patch, and the final protection receipt generated
after the renderer is applied and verified. Paid GPU/API/deployment is not run.
