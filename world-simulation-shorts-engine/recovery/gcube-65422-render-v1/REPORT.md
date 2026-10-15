# 65422 hardware-render and Dropbox preparation result

**Execution package CPU verified; actual gCube platform configuration and paid GPU authorization remain required.** Existing GPU/WebGL2 PASS is reused as user-reported prior evidence, not rerun. This task produced no hardware-rendered65422 video, no actual Dropbox download and no visual-quality PASS.

## Existing 5-second support

Confirmed in the existing `gpu_launcher.py`, active `launch.py`, `hardware_render.mjs` and fixture. The unchanged pipeline produces1080×1920,30fps,150frames,5.000seconds, H.264 and no audio. It creates `WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4`, five PNG checkpoints at0/38/75/112/149 and SHA256SUMS. Original FFmpeg settings remain libx264/fast/CRF16/yuv420p/faststart.

Current entrypoint is tini→Python `/opt/world-engine-storage-fix/launch.py`, which accepts `--render-65422` in **normal** mode. Diagnostic+render is explicitly refused. The older bootstrap-only example in original GCUBE_EXECUTION predates the shared-storage adapter and is not the command for this run; that historical document remains protected.

## Confirmed defect and minimal fix

A valid completed report could not be exported: `storage.py` limited REPORT.json to1MiB although the unchanged capture stores all150 frame diagnostics.

- Existing saved original report:25,747,252bytes, SHA550c1d7db502b91dc94548284ddfb10ff27f8e52cdf7efac7e7df68bfa768656.
- Reconstructing the native row shape from all150 distinct existing diagnostic rows and original frame hashes:17,790,153bytes, SHAb6ab411496bb32d160ce29ba87a8eee18fb64a032a678d3f83cab0e77ffb0c34. This is a CPU reconstruction, not a new GPU report.
- Separate permanent test fixture repeats one approved diagnostic:17,754,693bytes; it tests capacity using synthetic media, not GPU success or playable scene output. Provenance and the distinction are saved in SIZE_EVIDENCE.json and tests/fixtures/PROVENANCE.json.
- Immutable51fba45 source reproduces `STORAGE_UNAVAILABLE / EXPORT / IO_UNAVAILABLE` and no completion receipt. The patched adapter exports identical synthetic media hashes and writes the receipt last.

Only runtime change: `storage.py` now admits a report size of1..64MiB by fstat before a bounded read. All previous nofollow, file type/link/UID, private directory, capture signature, completed status, source status, manifest/media SHA, destination readback and final completion-receipt requirements remain. Small safe-record limits do not change. Oversize, empty, invalid, incomplete or corrupt data does not become a successful export.

## Validation and new image

33 unique new focused tests PASS: export8, artifact verification15, CI10. The built image independently ran the8 export tests with its actual patched module; no bind-mounted production replacement. CPU synthetic video was really encoded/count-probed/full-decoded for verifier testing, explicitly not the65422 scene. HTTP tests use synthetic mocks only. No old8/40/55/56/104/233 suites were repeated.

Free public standard ubuntu24.04 Actions [38722819744](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38722819744) completed build, Secret Scan0, unique-tag publication and fresh independent digest pull. Original160 packaged source hashes, six unchanged helpers and all updated live manifests PASS. Existing renderer, camera, ASTRA, frontier, FINAL and original images are preserved. Dependency/base-image audits were reused; no dependency rebuild or GPU deployment.

Image:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:rtx4080s-2f9158b-38722819744-1
```

Immutable:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:1a0a953d36ed0269a0c99267dd2d2d9e92ac6c50ffb7808e78bfbde24e7e2842
```

Config digest: `sha256:768e8c76f9364750241fd50315deb9bfb24acc766796211baff82713e0a0c0a6`.
Parent e7245bdd…48dff3 retained. Image size1,570,595,735bytes. Source checkpoint282e8edcd987f31d6425740dd52372a1ed89a8d4; build source da01dfa1d19695adbcee7ecb0be6c8ac426a1bba. Full generated manifests and build/pull evidence are saved here.

## Exact settings and execution boundary

Use the new image, RTX4080SUPER16GB, shared-memory2GiB, approved Dropbox `/world-storage`, `NVIDIA_DRIVER_CAPABILITIES=graphics,utility`, `WORLD_ENGINE_RENDER_MODE=gpu-required`, `WORLD_ENGINE_STARTUP_MODE=normal`; preserve provider device assignment and image UID bootstrap. Full settings/resource checks: [GCUBE_RENDER_EXECUTION.md](GCUBE_RENDER_EXECUTION.md).

Preferred existing route **if an authorized normal-mode terminal is available**: leave command override empty to retain the normal health service, then invoke the child once from that container terminal:

```sh
WORLD_ENGINE_STARTUP_MODE=normal WORLD_ENGINE_RENDER_MODE=gpu-required \
/usr/bin/python3 /opt/world-engine-storage-fix/launch.py --render-65422 --vram-budget-gib 8
```

This is an execution command for a separately approved run, not a command executed by this preparation. Actual #5373 shell/exec access is unverified. No new render API was added.

Direct PID1 capture is one-shot: no HTTP health service during render, exit0 after export. gCube command override precedence, liveness and automatic restart policies are not established by saved official docs. An Always policy may repeat a completed job in a fresh session; native locks prevent concurrency but not sequential retries. Therefore direct command override is not approved without verified one-shot policy/argument semantics. If neither supported route is available, platform execution remains blocked; no speculative wrapper or keepalive was built.

## Dropbox result preservation and actual retrieval

The exact export log identifies `/world-storage/world-engine-export-<random>/capture-<signature12>-<random>/public-review/`. Public review contains MP4, five PNG and SHA256SUMS only; sibling EXPORT_COMPLETE.json and safe logs remain private. The adapter verifies mounted-view source/destination SHA and writes completion last. It explicitly leaves remote persistence/external download false.

[DROPBOX_VERIFICATION.md](DROPBOX_VERIFICATION.md) provides source-anchor capture, actual remote-sync observation, authorized seven-file HTTPS download, SHA comparison, FFprobe/full-decode and phone playback instructions. `verify_artifacts.py` requires a source-side SHA256SUMS hash independently of the downloaded manifest; checks exact files, all SHA, PNG dimensions and150 decoded frames; only actual HTTP200 GETs can set external download verified. URL credentials/share keys never appear in output or receipts. GPU and visual approval remain false/UNREVIEWED even when artifact integrity passes.

No actual output URL exists from this task because the paid GPU render was not run. Existing safe logs and all required media must be externally recovered and matched before an authorized operator stops the GPU. A local mount or receipt alone is not proof of Dropbox durability. Never publicize source/private admission/report archives.

## Costs and next user action

Current account rate, billing increment, terminal capability and provider policies are unavailable. Cost cannot be quoted honestly as a fixed amount. Estimate live hourly rate × total billed seconds/3600, including startup, admission, render/encode, sync, verification and idle/retries, plus actual storage/network/tax/rounding. Ten minutes would be one-sixth of the hourly rate only as an arithmetic example, not a measured runtime. The existing3600-second renderer deadline does not stop provider billing.

Before paid execution: confirm the authorized terminal method or one-shot platform contract, check the current selected-node tariff and authorize a budget/run. After execution: preserve exact safe failure/completion logs, confirm remote Dropbox files, verify real HTTP200 and downloaded/source SHA, play the original MP4 and compare65422/reference. Hardware execution, external downloads and visual quality are NOT_EXECUTED/UNVERIFIED here. Await user review; no FINAL promotion or further development.

Branch: `development/gcube-65422-render-prep-20261015`. Required temp-only files0: source, fixture, verifier, contracts, workflow and evidence persist remotely. See RESULT.json, IMAGE.json, FINAL_CHECKS.json and SHA256SUMS.
