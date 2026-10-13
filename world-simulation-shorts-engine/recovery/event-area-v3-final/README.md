# Area / Propagation V3 final freeze

This folder verifies and freezes the user-approved Area V3 and Tsunami Wave
Polish without changing the approved engines, data, timing, pixels, or public
proof. The attached instruction explicitly approves the SHA-bound eight-second
Candidate. Historical Candidate manifests keep their original review flags.

Approved remote branch: `development/event-tsunami-wave-polish-v3-20261013`.
Approved validation revision: `a6ef67fa16143dc2bd53b334d583c05cf1476bed`.
Approved media revision: `263a5250671a36297892ebe4b11380fdfb927a9b`.
Original render source: `1e52b58deaf0fa1a48d6966c0d0e19f55e8b8cd0`.
Approved MP4 SHA-256:
`d41891620cf08aa953eed78e5b0d443b51843b173912fa1f887fb7e163d9ead7`.

## Verification recipe

1. Create a fresh HTTPS clone from the recorded remote branch at the approved
   validation revision. Do not use a local clone, worktree, object alternates,
   source copies, asset copies, or existing `node_modules`. Select the frozen
   `HASH_MANIFEST.json` inventory plus its manifest/checksum files through Git
   sparse checkout if desired. Fetch the original render and media commit
   objects from the same remote. These commits bind the source to the actual
   approved render.
2. Run the bootstrap script with `--checkout <fresh-checkout>`. It hydrates
   required Git LFS bodies from the remote, performs the frozen `npm ci` with a
   fresh cache, and verifies pinned tools. It uses the existing pinned system
   Node, Chromium, Python, and FFmpeg; it does not claim a fresh operating system.
3. Run the reproduction script with `--checkout <fresh-checkout>` and
   `--output-dir <this-folder>/evidence/clean-reproduction`. The output directory
   must be new and outside the approved checkout. It imports the approved
   `openWaveRuntime` from that remote checkout, evaluates all 240 native frames,
   compares raw RGBA and native PNG hashes, preserves camera/timeline/wave
   controls, emits eight exact checkpoints, and uses the original encoder
   arguments. The approved public files remain unchanged.
4. Run the final gate once after the actual reproduction receipt is PASS:
   `/usr/bin/python3 -B recovery/event-area-v3-final/verify_final_gate.py --write`
   from `world-simulation-shorts-engine`. It reads the frozen inventories and
   receipts; it does not rebuild them or rerun historical synthetic tests.
5. Run the same script with `--scan <pinned-gitleaks>` to scan new final text
   files using Gitleaks 8.24.3 and embedded default rules, then commit and push
   all new final source, provenance, receipts, and the final manifest.

The seven gate names are `SOURCE_PERSISTED`, `ASSETS_PERSISTED`,
`HASH_MANIFEST_PASS`, `DEPENDENCY_MANIFEST_PASS`, `IMPORT_MANIFEST_PASS`,
`NO_REQUIRED_TEMP_FILES`, and `CLEAN_ENV_REPRODUCIBLE`. Only an actual successful
remote clean reproduction can produce a final manifest. MP4 byte equality is
preferred; if encoder bytes differ, all 240 decoded RGB frame hashes must match.

The canonical production source, assets, data, fixtures, manifests, and approved
proof are already in remote Git or Git LFS. Clone/build/cache directories are
rebuildable verification outputs, not required temporary production inputs.
Required temp-only files: **0**.

No new media is required for Part A. Its public proof keeps only the original
MP4, eight PNGs, and SHA256SUMS. Private source, setup, diagnostics, final gate,
and internal instruction files remain outside the public-review directory.

The final manifest's containing commit and exact SHA are reported externally
after write; it does not embed its own hash or commit. Part B may start only
after seven gates PASS, clean reproduction PASS, and this final baseline has
been committed and pushed. This final verification tool implements no Planner.
