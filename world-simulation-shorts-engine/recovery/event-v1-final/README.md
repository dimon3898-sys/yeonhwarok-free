# Event System V1 final freeze

The user explicitly approved the existing V3 candidate. This sibling directory contains final verification procedures and private evidence. It does not alter the approved runtime, camera, source manifests, fixtures, profile, graphics, timeline, or Public Review delivery.

Approved source/inventory revision: `a7241a1e69d901fdd7ef5212ea5faf34d0ea6baf`.
Approved media revision: `d1cc0488688e2611e3f449cbdf97007b5147085f`.
Original render source revision: `ef95c08da99ab3aebcafd3b7c8fc6d7861fd4438`.
Parent V5 baseline: `29b8ee294360812b55ef577b62411de58159003b`.

The immutable candidate inventory validator is executed once with `--stage candidate --require-persisted`. Its result binds 326 saved source, asset, fixture, dependency and import files. Historical candidate approval/final flags are retained as historical records; the explicit user approval is separately bound by `USER_REVIEW_APPROVAL.json`.

Clean reproduction uses an actual HTTPS remote clone at the approved source revision, independent Git objects, remote Git LFS asset retrieval and fresh `npm ci` dependencies. The system browser, encoder, Node and Python are the existing pinned toolchain, rather than a newly provisioned operating system. The bootstrap receipt records this limitation explicitly.

`CLEAN_REPRODUCTION_RECIPE.json` saves the remote clone, explicit approved-revision pin, selected LFS pull, frozen npm install and invocation recipe. Future branch HEAD may contain final metadata, so fetch/check out the approved `a7241a1` revision explicitly. The one-time bootstrap helper is not a runtime dependency.

From repository root, run the following verification-only procedure after the clean checkout has been prepared:

```
node world-simulation-shorts-engine/recovery/event-v1-final/reproduce_clean_candidate.mjs --checkout /workspace/event-v1-final-clean-20261013 --output-dir /workspace/yeonhwarok-free/world-simulation-shorts-engine/recovery/event-v1-final/evidence/clean-reproduction
```

The output directory must be absent. Every runtime module and asset is loaded from the clean checkout. Every one of the 210 native raw frame hashes and PNG hashes, all camera/timeline/event controls, seven original checkpoint PNGs and the final encoded MP4 are compared with the approved artifacts. Encoder-only differences may pass solely when all 210 decoded frame pixel hashes match. The clean checkout remains unchanged.

Reproduction media under `evidence/clean-reproduction` are private verification artifacts. The existing Public Review folder continues to contain only the approved MP4, PNGs and SHA256SUMS, without additions or replacements.

`finalize_baseline.py` aggregates exactly the seven authorized permanent gates and fails closed on absent or failed evidence. Existing generic V4 gate tools require a different manifest/import schema; the approved candidate validator and narrow final receipt validator are used without changing either baseline or its schema. A final manifest does not contain its own Git commit or hash; those are recorded externally after the immutable manifest is committed.

After the final receipts and manifest exist, `scan_final_freeze.py` checks approved required text inputs and final verification text using pinned Gitleaks defaults, an empty ignore list, full redaction and decode depth three. Binary assets are hash-verified, not claimed as text secret scans. The scan receipt excludes itself to avoid circular hashes. The final commit persists all required files; no required runtime input depends on `/tmp` or the clean checkout location.

Final promotion requires explicit user approval, Permanent Gate 7/7 and successful clean reproduction. Stop after reporting the freeze; no subsequent plugin, planner or feature bundle starts automatically.
