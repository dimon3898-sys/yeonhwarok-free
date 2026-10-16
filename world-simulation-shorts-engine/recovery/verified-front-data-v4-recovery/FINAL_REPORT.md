# WORLD ENGINE V4 recovery — final execution report

Status: **V4_PARTIAL_ARCHIVAL_DATA_CANDIDATE_READY_FOR_GPU_VALIDATION**.
This is a source-grounded partial-data and software/image candidate. It is not a
complete historical reconstruction, an NVIDIA 80-second MP4 or video approval.

## Environment and authorization

Official `request_permissions(network.enabled=true)` was granted for this turn.
Normal HTTPS/proxy/TLS requests actually retrieved the two GovInfo originals and
Truman M99. The saved domain draft was not published. Recovery instructions were
saved at draft revision 10; Secret bindings, runtime requirements and domain
settings were preserved. Missing required GPU-token metadata exists, but no UI
validation trace establishes the exact reason Publish is disabled. No tool
available to this task can Publish or optionalize that requirement. No fake
credentials, bypass, paid GPU or secret modification was used.

## Source and scene result

Two original official Army books were actually decoded and their maps reviewed.
Seven native map rasters were independently re-extracted byte-exactly. Eight
dated **partial approximate UN fronts**, 1950-12-31 through 1953-07-27, are bound
to actual pixels, source pages, separate fit/check controls and review evidence.
Truman Possible MLR, arrows and ambiguous phase lines were excluded.

The original 80 seconds, 30 fps, 2,400 frames, 12 chapters and work segmentation remain.
The new fronts are selected in 850 frames; 1,550 frames retain explicitly dated
schematic context. No occupation polygons, unobserved daily front coordinates,
gap bridges, enemy complements or troop locations were invented. Source accuracy
and original CRS remain unknown. Independent checkpoint residuals are not total
historical accuracy. See `SOURCE_AND_SCENE_STATUS.md` for all 12 events and limits.

## Confirmed defect and recovery

Run 38867872905 correctly failed `FRONT_V4_GEOJSON_NOT_MANIFESTED` before any image
build. Six new GeoJSON dependencies were absent from the explicit inventory even
though they existed in the CPU test context. Commit 31426be adds those existing
files and a generic profile→inventory→actual-SHA closure guard. Three targeted
regressions verify omission and corruption cannot reach a draw/build. Historical
geometry, profile bytes and old visual sources were unchanged by this fix. The
earlier successful two-front image remains preserved as a checkpoint.

Root actual-PNG review then found the last source front was hidden by the static
country-boundary mask even though its draw call and coordinates passed. The
pre-fix eight-source image is also preserved. An additive source-only composition
policy now draws the actual partial front above a static country boundary while
keeping the existing native restore, fallback and marker/text/safe-area masks.
No protected source, coordinate or style changed. Every source snapshot and the
last frame must pass actual visible-pixel A/B constrained to the real source
stroke/halo corridor. See `FRONT_VISIBILITY_POLICY.md` and final CI evidence.

## Actual free verification

- Focused CPU/JS tests: 90 PASS (74 Python
  + 16 JavaScript); exact executed test records in
  `runs/38871556599-1/build.json`.
- 26 derived source outputs reproducible; source parts, dates and semantics exact.
- Actual SwiftShader draw/readPixels: PASS at 12 sample frames,
  including all 8 source snapshots and work-scene cut coverage.
- All 8 source fronts plus final frame: 9 actual suppression-versus-source A/B cases
  PASS. Each has visible changed center-stroke pixels, 0 protected-graphic changes,
  0 outside-safe-area changes and 0 changes outside actual source stroke/halo support.
- Pre-build versus actual-image raw RGBA and PNG hashes: BIT_EXACT for every
  sample. No claim of all 2,400 frames rendered or NVIDIA equality follows.
- Built-image strict inventory: 373 files. All 272 protected
  parent files unchanged; no old FINAL/renderer/camera/frontier source changed.
- Default-rule source/image Secret Scan: 0 findings, no exception allowlist.
- New tag push and fresh independent-runner immutable digest pull: PASS.
- Required temporary-only runtime files: 0; source maps, data, recipe, dependencies,
  manifests, profile, plan and evidence are permanent repository files.

## Image, plan and persistence

Branch: `development/korean-war-front-data-v4-recovery-20261016`.
Runtime/image source commit: `30ea53d85df39962822733f44872a303961aedde`.
CI: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38871556599

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:front-v4-4c4f39a-38871556599-1
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:4f2daf520eed2331a1b6ea0d3644e6f7d65854e7d4f3368d43af5f96d1ff6ab4
```

Source manifest SHA-256: `b9353fadf6c93484e3c6e2723991db98439678b87eff5360371039aa4beadb93`.
Profile SHA-256: `24dbac43ad45095d66dfa88edf00d33d1ed7162b1ddfaa9b32b4f2aff36d19e3`.
The separate `VIDEO_PLAN_80S.json` binds this actual image and both source hashes;
its canonical SHA-256 is `50428f062d2755be4a69de724e361820ca8a3e29dc38e4437781f43c5bae0a75`. The old parent plan is byte-preserved.
`OPERATOR_APPROVAL_TEMPLATE.json` deliberately has `approved:false`, unknown
pricing/cost/expiry fields, and does not authorize execution. The final result
commit is the repository commit containing this report and its SHA256SUMS.

## Remaining actions and limits

Actual RTX 4080 SUPER upload/draw, full 2,400-frame MP4, complete scene transitions,
mobile readability, 80-second rhythm, performance/60-minute target and Dropbox
external HTTP 200/SHA delivery remain unexecuted. Visible source-pixel A/B and
sampled pixel equality are not final video quality approval. Early actual front data and unobserved dates
remain incomplete. The exact September 28 Seoul recapture day and October 25
first Chinese combat day were not independently verified by these two books;
their existing curated dates retain their previous evidence status.

For a later production run, follow `OPERATOR_RUNBOOK.md`: confirm account access,
actual hourly price, maximum cost/time/retries and provider billing-stop policy;
obtain explicit paid GPU authorization; then invoke the existing detached
image-local coordinator once with the bound plan and genuine private approval.
Do not reset claims or request new intermediate 5-second reviews. No authenticated
gCube execution path or provider-enforced cost cap is claimed verified here.

No GPU was deployed, no 80-second MP4 is submitted by this task, and no FINAL
promotion occurred. Stop for user review of the prepared candidate and its
remaining hardware authorization requirements.
