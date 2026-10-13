# Planner Night causal visual Candidate

This continuation preserves Area/Flow/Event/Camera FINAL and the complete original
`planner-scene-json-v1` recovery directory. It composes existing moving-object,
route, endpoint pulse, front and Area APIs through new planner adapters. Only the
optional non-FINAL `planner_scene_v1.mjs` and its schema may change. The gate remains
`USER_VIDEO_REVIEW_REQUIRED`; this directory cannot grant user approval or promote
Planner to FINAL.

Read `USER_INSTRUCTION.txt`, `CONTRACT.md`, and `CHECKPOINT_STATUS.json` before
resuming. Stage receipts record their input revision, outputs and resume point.
Skip PASS stages. Check existing process/tool sessions before restarting an
incomplete render. Supported collaboration follow-up and tool-session resume are
the available recovery mechanisms; no external orchestrator is assumed. Capacity
retry guidance is 1, 3, 5, 10, 15 minutes with bounded retries and respect for
Retry-After. Do not duplicate completed work or render without a pushed source
checkpoint.

All required sources, fixtures, import closure, runtime asset bodies, locks and
outputs belong to durable repository storage. The inventory reuses the pinned
historical hash/Git-LFS helpers and Babel parser without invoking their original
test suites or Permanent Gate. It binds all inherited required runtime files,
including materialized LFS bodies. Non-required historical LFS files follow the
retained baseline policy. Package/browser caches and `/workspace/.onboarding`
tools and downloaded comparison copies are setup conveniences, not required
runtime inputs. Required temp-only files must remain zero.

Run from the repository root using the pinned `/usr/bin/python3` interpreter:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/planner-night-run-v1/build_manifest.py --stage implementation --write-manifests
```

After fixture creation and focused tests, use `--stage fixture --write-manifests`.
Commit and push coherent source/fixtures before rendering with the new
`render_proof.mjs`. A failed focused test blocks rendering. Existing approved
video bytes must never be overwritten or reencoded.

After the render has completed with a PASS report:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/planner-night-run-v1/verify_candidate.py
```

This focused audit probes H.264 metadata and actually decodes every one of the
420 frames, tests black/blank frames, measures half-second map changes, checks
motion/contact/control order, preserved historical facts/geometry, native pixel
protection and GPU diagnostics. It extracts selected encoded frames into private
`evidence/decoded-audit` and writes `evidence/CANDIDATE_AUDIT.json`. Technical PASS
does not claim a full visual review. A separate private visual receipt must state
the exact frames inspected and that full-video user review is still required.
Neither reference upload was mounted at the start; direct visual matching cannot
be claimed from the written requirements.

Public review contains exactly the new original MP4,
`KOREAN_WAR_PLANNER_SCENE_JSON_V1_CAUSAL_VISUAL_14S.mp4`, one `PREVIEW.png`, fixture
declared checkpoint PNGs, canonical `SCENE_PLAN.json`, and `SHA256SUMS`. PNG names
are declared by fixtures and bound to original encoder input frame hashes. The
canonical public Scene must be byte-identical to the executed fixture and pass
schema and internal-path/credential-key checks. Source, plans, diagnostics,
receipts and secrets stay private.

After technical checks and honest sample inspection:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/planner-night-run-v1/build_manifest.py --stage candidate --write-manifests
```

Use the existing pinned gitleaks 8.24.3 scanner at
`/workspace/.onboarding/event-v1-tools/gitleaks`, with verified binary SHA-256
`e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad`, for a focused
redacted candidate scan. Retain its receipt privately; no scanner is added to
runtime dependencies. Preserve dependency locks, checksum and TLS verification.

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/planner-night-run-v1/scan_candidate.py --output world-simulation-shorts-engine/recovery/planner-night-run-v1/evidence/SECRET_SCAN_IMPLEMENTATION.json
```

The scan binds current text input hashes, uses embedded defaults with a trusted
explicit configuration and empty ignore file, ignores allow comments, and
redacts findings by 100%. It scans new Night text/manifests, new generic modules
and tests, and the two optional non-FINAL overrides. Original protected binaries
are excluded. Reports contain only finding coordinates, never secret values.
Fixture and candidate inventories require the saved focused test and native
integration PASS receipts and bind their current source/protection evidence.

Commit and push candidate source/metadata/manifests/media using the established
artifact policy. Bind HTTP retrieval to the exact pushed media commit:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/planner-night-run-v1/build_manifest.py --stage candidate --require-persisted
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/planner-night-run-v1/verify_downloads.py --commit MEDIA_COMMIT_40_HEX
```

`verify_downloads.py` performs actual HTTPS GETs for every public body, requires
HTTP 200, and compares downloaded bytes/SHA with local original bytes and the
immutable Git commit. It never encodes media. Optional comparison copies are
durable under `/workspace/.onboarding/planner-night-http/<commit>` and are not
runtime inputs. The private receipt is `evidence/HTTP_DOWNLOAD_VERIFY.json`.
Do not fabricate URLs or claim this gate passed if hosting or GET is blocked.

`build_manifest.py` defaults to read-only comparison with saved manifests. Use
`--inspect-only` to calculate an inventory without writing or persistence checks.
`--require-persisted` checks required body hashes against both HEAD and index.
The explicit post-save exclusions cover mutable stage status and later
checkpoint/remote/persistence/HTTP/secret scan receipts; they never authorize
untracked runtime inputs. Hash-manifest self-reference is excluded and bound by
HEAD/index instead. Final clean reproduction/Permanent Gate is deferred until
the user reviews the actual complete video.
