# Event System V1 review candidate

State: `EVENT_SYSTEM_V1_CANDIDATE` / `USER_VIDEO_REVIEW_REQUIRED`.
`event_final=false`. Technical checks and a saved video do not grant video
approval or promote this candidate to `EVENT_SYSTEM_V1_FINAL`.

Permanent inputs are Event Core `00ad07e4`, production data `69e6ed83`, and
Camera V5 `29b8ee294360812b55ef577b62411de58159003b`. The original Core and V5
manifests remain immutable historical records. Current Event source belongs to
the separate `manifests/` in this directory. The production fixture, geometry,
metric, data provenance, and all original runtime/build inputs remain at their
existing committed locations. No data acquisition or geometry regeneration is
part of candidate reproduction.

Use the existing isolated checkout supplied for the cloud task. Do not create
a Git worktree unless the user explicitly requests one. Commit source and
procedures to the development branch before long capture or verification jobs.
Keep private reports under development `evidence/`; public review contains only
the candidate MP4, checkpoint PNGs and their required SHA256SUMS.

## Recorded environment

Exact versions: Node 24.19.0, Chromium 154.0.8037.57, system Python 3.13.5,
FFmpeg 7.1.5, Three 0.170.0, Playwright and Playwright Core 1.62.1. The inherited
Python lock pins NumPy 2.2.4, Pillow 11.1.0, and GDAL 3.10.3. Runtime is native
1080×1920 at 30 fps with software WebGL2 SwiftShader. Candidate rendering uses
the unchanged V5 read-only loopback server and existing native renderer APIs.

From the repository root, hydrate only the two original LFS inputs and install
the unchanged npm lock. These commands retain signature, artifact integrity and
TLS checks; do not replace locked assets or relax verification when access fails.

```sh
git lfs pull --include="world-simulation-shorts-engine/library/flat/terrain/NE1_HR_LC_SR_W_DR.tif,world-simulation-shorts-engine/web/dem/glo30/height.f32" --exclude=""
npm --prefix cinematic-world-map ci --ignore-scripts --no-audit --no-fund --strict-ssl=true
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-v1-candidate/validate_manifests.py --require-persisted
```

The validator checks exact interpreter/package versions, the pinned Babel AST
parser, named import bindings, locked npm imports, inherited source/assets/build
inputs, frozen data, source hash inventory, and persistence in both HEAD and the
index. Original LFS pointers are checked against the actual hydrated SHA256 and
byte count; a pointer file cannot satisfy an asset requirement. Hash manifests
include every required route body, new Event source/test/procedure, original
fixture and provenance, candidate fixture, private report and public proof body.
No required runtime source or asset resolves to temporary or machine-specific
paths. Installed packages are reproducibly obtained from the preserved npm lock
and its artifact integrity hashes; no `node_modules` copy is a retained input.

## Ordered technical reproduction

Existing saved evidence is immutable. Each driver phase requires a new,
nonexistent output directory. Replace the `NEW_...` directory names below with
new private paths when reproducing; do not overwrite previously saved reports.
Complete Event OFF before Event ON, then synthetic/collision/grammar checks,
then capture video and checkpoints.

```sh
node world-simulation-shorts-engine/recovery/event-v1-candidate/validate_candidate.mjs --phase off --output-dir NEW_OFF250_DIRECTORY
node world-simulation-shorts-engine/recovery/event-v1-candidate/validate_candidate.mjs --phase on --output-dir NEW_ON150_DIRECTORY
node --test world-simulation-shorts-engine/tests/event_contract_timeline_v1.test.mjs world-simulation-shorts-engine/tests/event_line_v1.test.mjs world-simulation-shorts-engine/tests/event_layout_adapter_v1.test.mjs world-simulation-shorts-engine/tests/event_metric_v1.test.mjs world-simulation-shorts-engine/tests/event_occlusion_policy_v1.test.mjs
node world-simulation-shorts-engine/tests/event_gpu_integration_v1.test.mjs
node world-simulation-shorts-engine/tests/event_collision_fixture_v1.test.mjs
node world-simulation-shorts-engine/recovery/event-v1-candidate/validate_candidate.mjs --phase grammar --on-report NEW_ON150_DIRECTORY/REPORT.json --output-dir NEW_GRAMMAR_DIRECTORY
node world-simulation-shorts-engine/recovery/event-v1-candidate/validate_candidate.mjs --phase video --output-dir NEW_SILENT_VIDEO_DIRECTORY
node world-simulation-shorts-engine/recovery/event-v1-candidate/validate_candidate.mjs --phase checkpoints --output-dir NEW_CHECKPOINT_DIRECTORY
```

OFF checks all 250 frames against an independent unchanged V5 pipeline and both
saved full-frame inventories, comparing raw RGBA and encoded PNG hashes. ON
checks all 150 frames, protected native pixels and pixels outside Event ROIs,
native diagnostics, fixed metric data, monotonic uninterrupted reveal, stable
holds and restoration when Event is switched OFF. Marker reservations remain
pixel-identical; line geometry continues behind them. Only the explicit
geographic Event line/Marker pair can overlap. Text, Title, Safe Area and Metric
constraints remain strict. Static protection source/tests and collision
fixtures are retained separately with their results.

Grammar validates the preserved 64306 semantic audit: geographic line reveal,
complete-line hold, fixed measured glyph reveal and information hold. It does
not claim that the original reference video has been recovered or a new direct
video-to-video comparison performed. Candidate timing is the saved generator
profile. Silent proof is a native 150-frame, five-second H.264 video with no
audio stream. Checkpoints are saved as original native PNGs, with no crop,
resize or overlay applied after capture.

## Save separate candidate manifests

After all candidate files and reports have settled, the following command
writes only this directory's `manifests/`. Do not run it concurrently with file
changes. A later evidence or procedure change requires regeneration followed
by another development commit. Historical Core and V5 manifests remain intact.

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-v1-candidate/validate_manifests.py --write-manifests
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-v1-candidate/validate_manifests.py --require-persisted
```

Run the second command after committing the new source, fixtures, reports,
proofs and manifests. `--inspect-only` performs source/dependency/asset checks
without writing or requiring manifests, useful while capture evidence is being
assembled. `HASH_MANIFEST.json` and `SHA256SUMS` exclude their own hashes to avoid
recursive self-hashing; their saved bytes and Git persistence are still checked.

For an independently provided clean checkout of the same development HEAD with
LFS bodies hydrated, add `--clean-checkout ABSOLUTE_CLEAN_CHECKOUT_PATH` to
`--require-persisted`. This read-only check compares every required persisted
body, including original build inputs and proofs. It does not itself render or
assert fresh execution. To establish fresh rendering, install the same pinned
dependencies in that clean checkout and run the ordered driver commands above
into new output directories, retaining their actual reports and output hashes.

Run the verified Gitleaks 8.24.3 scanner over the saved candidate files and relevant
development commits; save only the redacted/empty result and scanner version,
never credentials or scanner match values. Any retained scan evidence added
after generation requires another manifest regeneration and commit. User video
review remains required after all technical checks pass.

The verified scanner binary SHA256 is
`e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad`, obtained
from the official Gitleaks 8.24.3 release after archive-checksum verification.
Use an installed `gitleaks` command or provide its verified location to the
scan procedure. It is delivery verification tooling, with no temporary binary
path included among required rendering or build inputs. The manifest validator
records this metadata without claiming to execute the secret scan.
