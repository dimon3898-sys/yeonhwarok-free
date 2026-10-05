# B75 v003 publication delta and operator checklist

This is a **new v003-targeted preparation**, following the preserved [v002 preparation](../shipping75_publication_preparation_r01/README.md). It does not repeat or replace that evidence. No export, ZIP, split, network check, render, test, approval or Git action was executed here. v001/v002 and all original MASTER files remain preserved. At the initial observation v003 had not yet been created; root owns the forthcoming exact v003 approval/resume. Never reuse v002's plan hash/approval as v003 approval.

## Changes to check before publication

- Wait for the actual approved `project_594442ec2df9/v003`, all ten Scene results, final assembly and successful final QC. Verify S004/S005 repaired place/status readability in the actual rendered frames and 375px video. A source/plan test does not certify rendered contrast.
- `export_project.py`, `aggregate_benchmarks.py` and `deliverable_evidence.py` have **unchanged SHA** from the v002 preparation. Strict export still requires exact approval/plan/result/checkpoint hash; full ordered complete Scene MP4/audit hashes; final/muted hashes; and actual QC JSON identical to result. Existing files fail exclusive output checks. Shared 8K/assets/runtime/cache are excluded from export.
- Current v002 five completed Scene movies total **32,604,682 bytes/37.5 seconds**. Their complete registered MP4s are measured files, but v002 was paused for label contrast; these are not approved final v003 measurements. S001/S003 were reused with recorded current_render_seconds=0. See `PREPARATION.json` for the per-Scene byte/time records. **measured_final=false**: v003 final/ZIP size and split count remain unknown. No new linear size or render-time estimate is presented.
- Do not attach v002 UI evidence to a v003 benchmark: project/version/plan hash must match. Add a `--ui-evidence` path only when the real v003 report exists and has explicit measured timing. Approval/enqueue evidence without planning_seconds must not manufacture planning time.

## Exact commands, only after final v003 completion/QC

The fresh run folder and ZIP must not exist. If a preserved name already exists, choose a new artifact suffix; never delete or overwrite it. These commands are not a Git publication action:

```bash
set -euo pipefail
cd /workspace/yeonhwarok-free/world-simulation-shorts-engine
world_version='projects/project_594442ec2df9/versions/v003'
world_zip='../deliverables/WORLD_SIMULATION_ENGINE/SUEZ_CLOSURE_75S_TTS_v003.zip'
world_run='/workspace/deliverables/shipping75-publication-v003-r01'
mkdir "$world_run"
set -o noclobber
.venv/bin/python tools/export_project.py inspect "$world_version" > "$world_run/INSPECT.json"
.venv/bin/python tools/export_project.py export "$world_version" --output "$world_zip" > "$world_run/EXPORT_REPORT.json"
.venv/bin/python tools/aggregate_benchmarks.py "$world_version" --output "$world_run/BENCHMARK_REPORT.json"
if [ "$(stat -c %s "$world_zip")" -gt 104857600 ]; then
  .venv/bin/python tools/export_project.py split "$world_zip" --max-part-mib 90 > "$world_run/SPLIT_REPORT.json"
  .venv/bin/python tools/export_project.py verify "$world_zip.parts.json" > "$world_run/PARTS_VERIFIED.json"
fi

```

`inspect` blocks missing/incomplete/failed v003; do not bypass it. If the run directory exists, a fresh `r02` folder is needed. If ZIP creation fails, preserve the incomplete new ZIP and use a new `_export_r02.zip`. Split only the actual oversized ZIP. `--max-part-mib 90` creates `.zip.part001`, `.part002`, … and `.zip.parts.json`, preserving the original ZIP. Verify streams each chunk and the complete concatenated SHA; it does not reconstruct or replace the archive.

## Actual versus reused benchmark fields

Require a completed-version report in `completed_versions`, not an incomplete Scene observation. `metrics.measured=true` and actual finite scene_render/audio/assembly/QC/total values are required. Cached Scenes have **zero current render time**; their original native elapsed time is labeled separately. A v003 cache-assisted run is not a cold 75-second benchmark, and the costs/wall time of paused v001/v002 attempts are not secretly added to or discarded from the v003 successful-run measurement. Report prior attempts separately with their scope. Full-video playback, subtitle/sound sync, geography and aesthetic review remain separate completion requirements.

## Selective public v003 artifacts

Use a new `deliverables/WORLD_SIMULATION_ENGINE/SUEZ_CLOSURE_75S_TTS_v003/` folder, matching the verified 20-second ON/OFF flat delivery pattern. Copy exact resolved final/muted MP4s without re-encoding under `SUEZ_CLOSURE_75S_TTS_v003.mp4` and `_muted.mp4`; include plan/script/QC/source reports, contact sheet and actual optional audio/subtitle reports. A new `DELIVERY_MANIFEST.json` must contain project_id/version/plan_hash, exact copied `files` entries (`name`, `bytes`, `sha256`) and automatic_qc_passed=true, while accurately retaining aesthetic/playback/audio limitations. Preserve all older directories.

Normal Git permits up to **104,857,600 bytes/file**; the warning starts at52,428,800 bytes and browser upload is limited to26,214,400 bytes. These are different limits. For a ZIP over100MiB, keep the full ZIP local and stage only verified90MiB parts (94,371,840 bytes maximum) and their manifest. Do not stage the oversized full ZIP. Each loose MP4 must separately meet100MiB; otherwise keep its exact bytes inside the split archive and arrange a separately verified one-click delivery method before claiming mobile direct MP4 download. Do not lower quality to meet Git size limits.

Stage explicit copied artifacts and small source/evidence paths only. Do not stage entire projects, mutable status/job/checkpoint trees, partial Scene MP4s, cache, venv, node_modules, runtime binaries, duplicate textures/fonts or diagnostics. Full Scene MP4s and native records belong inside the strictly validated export archive rather than redundant loose copies.

## Newly required source/test dependency

The new `tests/test_place_label_readability.py` directly reads **tests/fixtures/shipping75_v002_label_readability_original.json** using `Path(__file__).resolve().parents[1]`; it verifies exact SHA **12d997d125443af691267b88ef6743d4295438c108705f6af8bea154abaffab5**. The fixture is582,882 bytes and both paths were untracked at this observation. Include both with the frozen planner/revisions/schema changes in the later selective source checkpoint. Do not substitute a mutable project plan. The fixture's30 absolute paths are historical metadata.estimates provenance only; no Scene executable clip/asset/narration file pointer is present. Existing fonts/Three/helper/source dependencies remain the full-repository checkout contract. This read-only review does not claim the ongoing175-test run passed.

## After a later actual Git push: public HTTP/byte/SHA verification

The evidence-only helper below was statically parsed but **never executed here**. It requires the actual pushed main commit and a QC-passed v003 delivery manifest; checks every selected loose file and either the whole eligible ZIP or all parts; verifies public HTTP200 and exact local bytes/SHA; and also checks the remote reassembled ZIP SHA for split delivery. It is read-only except for an exclusive new external verification JSON. It contains no credentials and echoes no raw proxy/network exception contents. Run only after the root owner stages/pushes the actual final artifacts:

```bash
world_published_commit="$(git -C /workspace/yeonhwarok-free rev-parse HEAD)"
python3 /workspace/yeonhwarok-free/world-simulation-shorts-engine/docs/evidence/shipping75_publication_v003_preparation_r01/verify_public_downloads.py \
  --repo /workspace/yeonhwarok-free \
  --delivery-dir /workspace/yeonhwarok-free/deliverables/WORLD_SIMULATION_ENGINE/SUEZ_CLOSURE_75S_TTS_v003 \
  --commit "$world_published_commit" \
  --output /workspace/deliverables/shipping75-publication-v003-r01/GITHUB_VERIFICATION.json

```

The helper is an operator aid, not an engine/test dependency. A future failed verification must block a public-download completion claim. Public GitHub artifacts are distinct from public application hosting or a real mobile-device end-to-end test.

Existing evidence: [official GitHub limits](../github_file_limits_r01.json), [LFS auth readiness](../github_lfs_auth_readiness_r01.json), [actual ON ordinary-Git HTTP/SHA publication](../github_A20_ON_publish_20261004T192400Z/GITHUB_VERIFICATION.json), [actual OFF publication](../github_generator_first_publish_20261004T185000Z/GITHUB_VERIFICATION.json). LFS client3.6.1 is installed but authenticated_lfs_ready=false/quota_verified=false; exit0 was not accepted as authentication because stderr said Username could not be read. No LFS setup/probe/upload was performed here. Actual20ON/OFF ordinary-Git public downloads already worked; new75v003 public delivery has not been attempted.
