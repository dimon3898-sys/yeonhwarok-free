# B75 v002 publication preparation (read-only)

This preparation was recorded while `project_594442ec2df9/v002` was still rendering. No 75-second version was exported, ZIP-created, split, uploaded, rendered, tested, or marked complete by this preparation. The commands below are **future commands**, for the exact completed/QC-passed immutable version. They must not be executed on the current incomplete version. The current plan hash is `6e0508972293e329b54498051cfec87887b167bab1bff60e57ec6ed10c22cc91`.

## Completion gate and unchanged tool contracts

`tools/export_project.py inspect` calls the same `load_completed_version` validation used by `export`: exact user approval and plan digest; completed result/checkpoint with automatic QC PASS; final and muted bytes/SHA; resolved QC JSON identical to result; all ten ordered complete Scene results; each Scene movie/audit SHA; matching Scene result manifest/checkpoint counts. Missing/incomplete/old/mutated results fail closed. `inspect` does not render or write output.

`export` creates an exclusive new ZIP outside the source project. It selects final/muted MP4; script and story/Scene plans; each Scene JSON, MP4, audit and native/reuse manifests; source/QC/contact-sheet reports; actual audio/subtitle files; and optional benchmark. It excludes shared Earth textures, fonts, runtime, cache and unrelated failed/partial outputs. Completed source checkpoint/manifests inside the archive describe this immutable version, whereas **live project/status/job/checkpoint trees must never be staged wholesale**. ZIP streaming also verifies each selected source did not change during copying. `EXPORT_MANIFEST.json` records the selected members and SHA. A failed or existing export is preserved; use a new artifact suffix instead of overwriting it.

These automatic checks do not assert aesthetic approval, human listening, an actual phone, public application hosting or browser playback. Before publication, review the actual complete 75-second video, mobile contact sheet, final QC, geography, subtitles and sound limits separately. Retain `aesthetic_review_required`/`publication_quality` exactly as reported rather than making them true in a copy step.

## Exact future inspect → export → size branch → verify

Run from the app folder after all ten Scenes, assembly and final QC are complete. The run folder and ZIP below must be new. `noclobber` protects the capture reports; the Python tools independently reject existing archives/reports/parts.

```bash
cd /workspace/yeonhwarok-free/world-simulation-shorts-engine
world_version='projects/project_594442ec2df9/versions/v002'
world_export='../deliverables/WORLD_SIMULATION_ENGINE/SUEZ_CLOSURE_75S_TTS_v002.zip'
world_publication_run='/workspace/deliverables/shipping75-publication-v002-r01'
mkdir "$world_publication_run"
set -o noclobber
.venv/bin/python tools/export_project.py inspect "$world_version" > "$world_publication_run/INSPECTION.json"
.venv/bin/python tools/export_project.py export "$world_version" --output "$world_export" > "$world_publication_run/EXPORT_REPORT.json"
.venv/bin/python tools/aggregate_benchmarks.py "$world_version" --ui-evidence validation/final_B75_shipping_revision_v002_r02/UI_END_TO_END_REPORT.json --output "$world_publication_run/BENCHMARK_REPORT.json"
world_zip_bytes="$(stat -c %s "$world_export")"
if [ "$world_zip_bytes" -gt 104857600 ]; then
  .venv/bin/python tools/export_project.py split "$world_export" --max-part-mib 90 > "$world_publication_run/SPLIT_REPORT.json"
  .venv/bin/python tools/export_project.py verify "$world_export.parts.json" > "$world_publication_run/PARTS_VERIFIED.json"
fi
```

Use `set -e` in a script, or stop immediately if any command fails. This sequence is not a Git command and does not publish anything. If the run folder already exists, pick a fresh `r02` folder. If the ZIP already exists, inspect/verify the preserved output or use an exclusive `_export_r02.zip`; do not overwrite or delete it. Do not use `export --split-mib 90` unconditionally: that always creates parts, even for a small archive. The size branch above splits only an actual ZIP over the normal Git limit.

The exact part names are `SUEZ_CLOSURE_75S_TTS_v002.zip.part001`, `.part002`, … and `SUEZ_CLOSURE_75S_TTS_v002.zip.parts.json`. Parts are binary chunks, not independent ZIP files. `verify` streams all parts in manifest order, verifies each part's bytes/SHA and the complete reconstructed ZIP SHA, and does not write a reconstructed archive. The original ZIP remains preserved locally. All pre-existing part names/manifests cause an error rather than replacement.

Optional additional ZIP-member verification, performed only on that new completed export:

```bash
.venv/bin/python - <<'PYZIP'
from pathlib import Path
import hashlib,json,zipfile
p=Path('../deliverables/WORLD_SIMULATION_ENGINE/SUEZ_CLOSURE_75S_TTS_v002.zip')
with zipfile.ZipFile(p) as z:
    manifest=json.loads(z.read('EXPORT_MANIFEST.json'))
    for item in manifest['files']:
        h=hashlib.sha256();size=0
        with z.open(item['archive_member']) as f:
            for block in iter(lambda:f.read(1024*1024),b''):
                h.update(block);size+=len(block)
        assert size==item['bytes'] and h.hexdigest()==item['sha256'],item['archive_member']
print('All selected archived members match recorded bytes/SHA')
PYZIP
```

## Selective ordinary-Git/public files

After successful inspection and actual complete-video review, create a new flat directory `deliverables/WORLD_SIMULATION_ENGINE/SUEZ_CLOSURE_75S_TTS_v002/` matching the existing ON/OFF publication pattern. Copy the exact resolved final/muted files without re-encoding, under `SUEZ_CLOSURE_75S_TTS_v002.mp4` and `_muted.mp4`. Add the small plan/script/QC/source reports, contact sheet, and actual optional audio/subtitle reports listed in `PREPARATION.json`. A fresh `DELIVERY_MANIFEST.json` should record exact project/version/plan hash; source-relative paths; copied bytes and SHA; QC and real playback evidence and their scope. Include an actual `BENCHMARK_REPORT.json` only after its completed-version metrics validate. Do not claim missing measurements or infer times from duration/mtime.

Select **only exact final copied paths** for Git. Individual normal-Git files must be at most 104,857,600 bytes (prefer margin); a 52,428,800-byte warning is expected above 50 MiB. GitHub browser upload's 25 MiB limit is a different limit and does not prevent normal-Git downloads of already committed 27 MB MP4s. For a ZIP under the normal limit, add that single ZIP. For a ZIP over the limit, preserve it locally and add only `.zip.partNNN` plus `.zip.parts.json`, verified by the tool. Never add the oversized full ZIP, entire `projects/`, partial MP4s, live status/job/checkpoints, render cache, logs, venv, node_modules or duplicate 8K/font assets. Individual Scene MP4s remain in the complete ZIP and app downloads, not as many redundant loose public copies.

If an individual final MP4 exceeds 100 MiB, do not stage it or re-encode at lower quality to meet the limit. The exact MP4 is still inside the split ZIP. A one-click mobile MP4 URL would then require a separately authenticated/verified release-asset or storage/app-host delivery; no such endpoint is established by this preparation. Do not label multipart reconstruction as direct mobile MP4 playback.

## Measured sizes versus preliminary capacity estimate

At this observation, old v001's completed S001/S002/S003 total **20,639,784 movie bytes over 22.5 seconds**; these are actual file sizes, not full-final measurements. v001 S002 is the preserved duplicate-label counterexample, not the corrected v002 output. v002 currently has only cached S001 registered complete. The final 75-second MP4/ZIP sizes and required part count remain unknown: `measured_final=false`.

An illustrative linear size-only projection from those three old completed Scene files is about **68,799,280 bytes per 75-second movie**, or **206,397,840 bytes for two final variants plus the Scene movie set**, before reports/audio/ZIP compression. This is not a measured final size, a codec bound, a completed benchmark or a prediction that later HERO/network shots have equal bitrate. It only justifies preparing the split path; the actual ZIP decides whether/how many parts are needed. No ZIP was generated to obtain this estimate.

## Benchmark scope

`aggregate_benchmarks.py` reads exact completed/QC-passed immutable versions, recorded metrics with `measured=true`, matching scene counts and native SHA, and finite timing fields. Cached scenes contribute **zero current render time**; their original native time is separately labeled. It can report completed Scene observations of an incomplete video, but those are never completed-video benchmarks. It does not extrapolate a 20-second render time to 75 seconds. Current revision r02 UI evidence has approval/enqueue timing, not an explicit planning_seconds measurement; the tool may record `NO_MEASURED_PLANNING_OR_UI_TIMING` rather than fabricate planning time. Keep UI/plan timing separate from rendering totals.

## Public download verification after a later push

The following is a future read-only verification command, to run from the repository root **after** another owner has staged/pushed the selected artifacts and created the flat `DELIVERY_MANIFEST.json`. It uses the actual current commit as an immutable raw URL, compares public bytes/SHA to the selected local files, and captures HTTP results in a new external report. It does not push, change Git or log credentials. The ZIP is checked only if it fits normal Git; otherwise the parts and manifest are checked. All public files must actually be in that pushed commit. A local Git HEAD alone is not remote confirmation.

```bash
cd /workspace/yeonhwarok-free
python3 - <<'PYHTTP'
from pathlib import Path
import datetime,hashlib,json,subprocess,urllib.request
root=Path.cwd();folder=root/'deliverables/WORLD_SIMULATION_ENGINE/SUEZ_CLOSURE_75S_TTS_v002'
manifest=folder/'DELIVERY_MANIFEST.json';delivery=json.loads(manifest.read_text())
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/main'],text=True).split()[0]
assert commit==remote,'Local commit is not confirmed at remote main'
files=[folder/item['name'] for item in delivery['files']]+[manifest]
archive=folder.parent/'SUEZ_CLOSURE_75S_TTS_v002.zip'
if archive.stat().st_size<=104857600:
    files.append(archive)
else:
    parts=archive.with_name(archive.name+'.parts.json');doc=json.loads(parts.read_text())
    files += [parts]+[parts.parent/item['name'] for item in doc['parts']]
rows=[]
for f in files:
    assert f.is_file() and f.stat().st_size<=104857600,f
    rel=f.relative_to(root).as_posix();url=f'https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/{commit}/{rel}'
    expected=hashlib.sha256(f.read_bytes()).hexdigest();h=hashlib.sha256();size=0
    with urllib.request.urlopen(url,timeout=120) as response:
        assert response.status==200,(rel,response.status)
        for block in iter(lambda:response.read(1024*1024),b''):
            h.update(block);size+=len(block)
    assert size==f.stat().st_size and h.hexdigest()==expected,rel
    rows.append({'path':rel,'url':url,'http_status':200,'bytes':size,'sha256':h.hexdigest(),'matches_local':True})
out=Path('/workspace/deliverables/shipping75-publication-v002-r01/GITHUB_VERIFICATION.json')
with out.open('x') as stream:
    json.dump({'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':commit,'remote_main':remote,'files':rows,'scope':'Public GitHub files only; not public application or real-phone E2E'},stream,indent=2)
print(out)
PYHTTP
```

No network verification command above was executed in this preparation. A final user message should link exact immutable GitHub URLs only after actual HTTP/SHA verification. ZIP-part delivery also needs concise manifest-ordered reconstruction instructions and the full original SHA. Preserve the large original ZIP and all old ON/OFF/v001 files. Public GitHub file delivery does not deploy the mobile generator application.

## Existing verified evidence

- [Official limits](../github_file_limits_r01.json): GitHub official docs-source HTTP 200, normal Git 100 MiB / warning 50 MiB / browser upload 25 MiB.
- [LFS readiness](../github_lfs_auth_readiness_r01.json): installed client3.6.1 but username authentication failed in stderr despite exit0; authenticated_lfs_ready=false, quota_verified=false, no uploads/filter activation. Do not retry credentials or activate LFS during this read-only preparation.
- [OFF ordinary-Git publication](../github_generator_first_publish_20261004T185000Z/GITHUB_VERIFICATION.json): actual commit a6f3fc0, public file HTTP200/bytes/SHA.
- [ON ordinary-Git publication](../github_A20_ON_publish_20261004T192400Z/GITHUB_VERIFICATION.json): actual commit632826e7, public MP4 27,118,124B, muted26,487,658B, ZIP94,927,749B, all HTTP200/bytes/SHA. The ZIP was under100MiB, so no LFS/split was needed.
- [Public application scope](../public_mobile_runtime_status_r02.json): no configured/verified public app URL or physical-phone E2E. Internal localhost/375px Chromium evidence is distinct from public mobile hosting.

This ownership is frozen after writing only `README.md` and `PREPARATION.json` in this new exclusive folder. Source/render/test tools and current project artifacts were read only.
