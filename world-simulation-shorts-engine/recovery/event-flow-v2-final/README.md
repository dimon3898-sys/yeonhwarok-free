# Approved Flow V2 final freeze

The user approved `SUEZ_EVENT_FEATURE_BUNDLE_V2_FLOW_MOVEMENT_POLISH.mp4`, SHA-256 `5ff055643ded594198f3dc5e313d9acadb6b636d4f621294ad69456d4b6449fe`. This sibling folder contains final verification procedures and private receipts. It does not change the approved Event V1/Flow runtime, geometry, projection, camera, graphics, profile, timeline or Public Review.

Approved media commit: `a0add53bc5d9182bf24a17ac9dd13e69129c9fa0`. Approved Candidate/validation snapshot: `4a1f773dcf377ebca5e46d83b81204707a56b59d`. Original render source: `be428ab6dbe6723f8b3cc25a287c18a744a9c318`. Parent: `EVENT_SYSTEM_V1_FINAL_BASELINE`, commit `f79f3d55d945ef0e53b03ac2ed666f48f28b5881`, manifest SHA `52d4f5f5e034079a58a6227deff71d36bf4b775af0df600daf689eec4f7701a1`.

Explicit approval is saved separately in `USER_REVIEW_APPROVAL.json`. Historical Candidate `user_video_approved`, `event_final` and `permanent_gate_executed` flags remain unchanged. A successful `FINAL_MANIFEST.json` binds the new approval and seven final gates; preparation alone does not grant a final result.

Run the immutable approved Candidate inventory once from repository root, saving its JSON stdout as `evidence/CANDIDATE_PERSISTENCE_CHECK.json`:

```
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-feature-bundle-v2-polish/build_candidate_manifest.py --stage candidate --require-persisted
```

Clean reproduction uses a fresh remote Git clone pinned to the complete approved `4a1f773` snapshot. The original render-source commit remains `be428ab`; the later snapshot supplies the original media, comparison reports and manifests without changing runtime source. The sparse checkout selects the 415 approved required files and Git infrastructure. Its independent Git objects, remote LFS originals, fresh npm installation/cache and pinned system-tool versions are recorded by `bootstrap_clean_checkout.py` in `evidence/CLEAN_CHECKOUT_SETUP.json`. This is an independent remote checkout using existing pinned system tools, not a newly provisioned operating-system image. `CLEAN_REPRODUCTION_RECIPE.json` preserves the clone, revision-pin, LFS/npm and verification procedure.

After the fresh checkout is prepared, run the new verification driver:

```
node world-simulation-shorts-engine/recovery/event-flow-v2-final/reproduce_clean_flow.mjs --checkout <separate-checkout> --output-dir <repository>/world-simulation-shorts-engine/recovery/event-flow-v2-final/evidence/clean-reproduction
```

The output directory must be absent. Every runtime module and asset loads from the remote checkout. The driver compares all 240 native RGBA/PNG frame hashes, camera/timeline/Flow/presentation controls, six native checkpoints and the encoded MP4. An encoder-only byte difference can pass only if all 240 decoded frame pixel hashes match. The approved checkout and Public Review are preserved. Private verification media remain under `evidence/clean-reproduction`.

Once approval, persistence, remote setup and successful clean reproduction receipts exist, aggregate exactly the seven authorized gates:

```
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-flow-v2-final/finalize_baseline.py --write
```

The narrow wrapper reuses the frozen Event V1 final helper without changing it. It distinguishes the approved snapshot from original render source, checks all 415 remotely reproduced input bodies and emits `FINAL_MANIFEST.json` plus `evidence/PERMANENT_GATE.json` only after all checks pass. Missing or failed receipts produce a blocked gate receipt and no final manifest. No historical visual suite or data investigation is repeated.

Before saving the final commit, scan approved required text inputs and all new final-freeze text:

```
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-flow-v2-final/scan_final_freeze.py --repo <repository> --scanner <pinned-gitleaks-8.24.3>
```

The pinned default rules use an empty ignore list, full redaction and decode depth three. Binary assets are hash-verified rather than claimed as text secret scans. The scan receipt excludes itself to avoid recursive hashes. The containing final Git commit and exact manifest SHA are reported after persistence; a manifest does not embed its own hash or commit.

Final state requires explicit user approval, Permanent Gate 7/7 and successful clean reproduction. No new feature work is part of these procedures. Any separately authorized subsequent scope starts only after the final baseline is remotely persisted.

Sparse checkout preparation uses the 413 approved HASH rows plus HASH_MANIFEST.json, manifests/SHA256SUMS and the three infrastructure files recorded in CLEAN_REPRODUCTION_RECIPE.json. Send their sorted, slash-prefixed paths to `git sparse-checkout set --no-cone --stdin`, after `git sparse-checkout init --no-cone`, with GIT_LFS_SKIP_SMUDGE=1. Pin the approved validation revision before bootstrap. If branch HEAD advances, first fetch that exact revision with the recorded fetch argv. The selected list is metadata; all selected file bodies come from the remote clone.
