# Additive reference 65379 quality rework

Resume the verified `8e274729bb8df78e0deac08eeac756e9815e4678` saved point on
`development/reference-quality-rework-20261014`. Every previously tracked body,
including all FINAL cores and the old five-second Candidate, remains immutable.
This directory and new versioned adapters contain the rework. The uploaded
compressed target is SHA-identical to the retained original reference; the old
five-second comparison is also SHA-identical to its retained MP4. The historical
14-second Korean War Candidate is never the target.

Read `USER_INSTRUCTION.txt`, `CHECKPOINT_STATUS.json`, and the saved actual input
audit before resuming. Skip completed stages. Check live capture processes and
saved source signatures before starting another capture. On supported capacity
errors use bounded 1, 3, and 5 minute retry with Retry-After respected. Save the
checkpoint first; unavailable service never authorizes guessed footage or a
FINAL change. This workflow ends at `USER_VIDEO_REVIEW_REQUIRED`.

The pinned runtime requires Node 24.19.0, system `/usr/bin/python3` 3.13.5,
Chromium 154.0.8037.57, FFmpeg 7.1.5, Three 0.170.0, Playwright 1.62.1, NumPy
2.2.4, and Pillow 11.1.0. Preserve session proxy, CA trust, and TLS checks. If
the locked JavaScript packages are absent, install the retained lock from the
repository root:

```sh
npm --prefix cinematic-world-map ci --ignore-scripts --no-audit --no-fund --strict-ssl=true
```

The read-only original V5 loopback server loads the original native plans and
assets. The new pipeline uses actual native rendering, geographically registered
licensed map material, complementary territory control, measured camera
presentation, and source-supported unit overlays. The reference video is never
used as a finished-frame map background. The new shot explicitly omits optional
native foreground labels through the renderer's public settings; it does not
edit the original labels, marker, glyph, layout, or FINAL source. Do not claim
old foreground pixel equality for this intentionally different shot.

All required source, scene, fixtures, asset bodies, manifest, and review outputs
must be persisted according to the existing Git/Git-LFS policy. Browser/package
caches, recoverable PNG capture caches, scanner binaries, and downloaded proof
verification copies are disposable. Required temp-only runtime inputs are zero.
The new fixture explicitly lists actual runtime module and asset inputs, and the
runtime hashes them before and after capture. The manifest records the complete
protected source and dependency closure.

Commands below run from the repository root. Actual three-frame probe captures
must be visually inspected before root writes the saved admission receipt:

```sh
node world-simulation-shorts-engine/recovery/reference-quality-rework-v2/probe_native.mjs
```

Probe frames 0, 74, and 149 are genuine native captures. Scripts report technical
status separately from visual admission and cannot self-certify parity. Existing
probe PNGs are preserved; a focused iteration can use an explicit new contained
output directory through `--output=evidence/native_probe_iteration_2`.

After implementation passes the focused checks, commit and push the source,
fixtures, actual static probe evidence, and render admission. Verify the remote
checkpoint before the longer 150-frame capture. Then run:

```sh
node world-simulation-shorts-engine/recovery/reference-quality-rework-v2/render_proof.mjs
```

Recovery after a later media/report commit must use the saved render source
commit from `evidence/proof/REPORT.json`, rather than the newer checkout HEAD:

```sh
node world-simulation-shorts-engine/recovery/reference-quality-rework-v2/render_proof.mjs --source-commit=FULL_SAVED_RENDER_SOURCE_COMMIT
```

Capture signatures bind that source commit, every actual input body, and the
saved static admission. Saved frame PNGs and their diagnostic rows are reused
only if their hashes and signature match. A live process lock prevents duplicate
captures. The original MP4 is encoded once from those native PNGs as 150 frames,
1080×1920, fixed 30 fps, H.264, silent, 5.000 seconds. If a verified complete
original MP4 already exists, preserve it without reencoding.

Actually decode all original output frames, record their hashes and timestamps,
and create the five source-left/output-right comparisons:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/reference-quality-rework-v2/audit_candidate.py
```

The comparison uses the nearest actual target PTS within 5.181813–10.181813
seconds and the recorded [0, 211, 1080, 2131] source map crop. Retained reference
frame PNGs are checked against the complete original decoded RGB audit before
use. The full original MP4 and native checkpoint PNGs remain unchanged. The
five chronological contact sheets cover all 150 decoded output frames exactly
once; inspect those sheets and all five comparisons. Decoder success, source
hashes, and complementary-mask assertions cannot grant visual-quality PASS.
Record remaining territory, camera, map, combat, or color gaps honestly.

Before Candidate publication, run the focused hash/dependency/import inventory,
confirm every old tracked body is unchanged, ensure required temp-only inputs are
zero, and perform the pinned redacted secret scan. Commit and push the coherent
new source, fixtures, manifest, reproduction instructions, and verified review
artifacts, then verify the immutable remote revision and persisted body hashes.
Do not run the user-approval-only Permanent Gate or promote FINAL.

Public review exposes only the new original MP4, the five reference-comparison
PNG files, necessary executed `SCENE_PLAN.json`, and `SHA256SUMS`. Native raw
checkpoints, source code, source assets, diagnostics, internal plans, and the
entire reference video are not public-review bodies. The public Scene must be
byte-identical to the executed fixture and contain no private URLs or secrets.

Every public URL must be an immutable pushed media-commit URL with a real HTTPS
GET returning HTTP 200. Downloaded SHA-256 must match both original local bytes
and the Git commit body; preserve the approved MP4 without reencoding. Keep
download/persistence receipts private. If mobile verification is blocked, report
that fact without claiming a usable URL. Stop after delivery without 14-second
expansion, unrelated development, or FINAL promotion.
