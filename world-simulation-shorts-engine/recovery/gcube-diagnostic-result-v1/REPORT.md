# GPU diagnostic result recovery — final report

## Result

**Diagnostic patch image built, published and independently pulled. Actual #5373 hardware evidence remains UNVERIFIED.** No GPU was deployed, started or probed by this task. No paid operation or rendering was performed.

Baseline: `d1f6041d4fdb97c5ac1c8245d3b8ce66821b3343`.
Branch: `development/gcube-diagnostic-result-20261015`.
Implementation checkpoint: `b5b83c4ed93151ee31c94bff09b7668e1789043a`.
Image source: `eb937ec312cd60af147b7333677c5e5f10bd687e`.

## Confirmed cause and existing evidence

`DIAGNOSTIC_ONLY` is the normal diagnostic-mode response after the old worker's checks succeed. The worker called original native `admit_gpu` but discarded its returned Admission, replacing the details with a generic successful diagnostic record. This is a confirmed observability defect. It is not a native GPU failure code. Outer `gpuRenderingVerified: false`, `renderAllowed: false`, readiness503 and render denial intentionally remain.

The native launcher writes safe/private admissions before returning success. Its existing safe result is at `/var/lib/world-engine-private/engine/session-*/diagnostics/<UTC>-<random>/admission_safe.json`. The actual #5373 full JSON, current image identity and surviving files were not accessible here; file existence and GPU outcome on that workload cannot be asserted. A restart may have destroyed the private files. No newest-file inference is permitted.

A second confirmed code defect allowed a subsequent UID/GID transition failure to replace the first worker error. That path is fixed separately; it is not claimed to have caused the reported #5373 status.

## Minimal implementation

- `gcube-diagnostic-image-v1/startup.py`: validate the native success envelope and forward native probe diagnostics through the existing `make_record` sanitizer, bounded worker pipe and `safeDiagnostics.gpu`. Missing/contradictory evidence returns `DIAGNOSTIC_RECORD_INVALID`. Existing failures retain stage, code and timestamp. Preserve primary failure before any secondary UID failure.
- `gcube-storage-fix-v1/launch.py`: preserve and publish the original failed record before publishing a later UID/GID error; no unsafe service is started.
- New `gcube-diagnostic-result-v1/recover_existing.py`: read-only existing-evidence reader. It correlates the exact current loopback response, private export receipt, exported safe startup JSON and unique current safe admission within the bounded startup window. It never reads private admission, initializes GPU, renders, changes permissions or creates a new service. Ambiguity or missing/stale evidence is UNVERIFIED.
- New isolated Docker/CI configuration inherits the previous immutable image and replaces only two startup modules, their manifests and the reader. No dependency reinstall, API change or new GPU check.

`records.py`, `service.py`, `healthcheck.py`, `storage.py`, original GPU launcher, ASTRA, FINAL, renderer, frontier, camera and approved visual code are unchanged. The existing `/diagnostics` route is reused. The historical old manifests remain immutable provenance; current combined manifests are saved under `image-manifests/` and inside the new image.

## Focused verification

40 new tests PASS: success forwarding6, first-error preservation4, read-only recovery18, CI safeguards12. Native-success test evidence is synthetic and explicitly TEST_ONLY. The old `d1f6041` worker was actually loaded to compare the omitted-success behavior. Fork/pipe and existing HTTP routes were exercised. Old8/55/56/104 suites were not repeated.

Actual CPU containers using the resulting image:

| Case | Result | Exit | Stored evidence |
| --- | --- | --- | --- |
| Canonical root entrypoint, no GPU | First error `GPU_HARDWARE_UNAVAILABLE`; same console and HTTP response; health200, ready503, renderGET404/POST405; healthy and restart0 during observation | 2 after controlled stop | Exact first record in private and shared export |
| UID1000 with supplementary group guard | First `GPU_HARDWARE_UNAVAILABLE`, followed by separate `UID_GID_FAILED`; unsafe service refused | 1 | Both records in private and shared export |

Original160 packaged source hashes PASS; unchanged diagnostic/storage helper hashes PASS; patched module/reader and manifest hashes PASS. Existing shared directory metadata and sentinel content remain unchanged. Mounted-view readback does not establish Dropbox remote durability or external download.

Secret Scan: pinned Gitleaks8.24.3, findings0; changed runtime modules, actual image copies, reader, new namespace and workflow scanned. Parent source/dependency audits reused. Required temp-only files:0; reproducible source, tests, workflow, source/asset contracts and build/pull evidence are in Git. Original images and data were not deleted or overwritten.

## Published image

Tag:
`ghcr.io/dimon3898-sys/world-simulation-shorts-engine:rtx4080s-2f9158b-38713103848-1`

Immutable reference:
`ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:e7245bdd73c99eff806effdfd1f5ba6765fcffdc2d64fbdb52c360e79148dff3`

Config:
`sha256:456fbf96fc22d8e2ad702de1de8a54a359e449cf9557c6f9ddbe14e5872f24dd`

Parent preserved:
`sha256:119873aa8515622c3508e934247bd4a18e85d080e3f33696e66acc1bae874825`

Free public standard `ubuntu-24.04` Actions had ~85GiB available. Build/publish and fresh independent digest pull both PASS. Full evidence: [Actions run38713103848](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38713103848), `runs/38713103848-1/build.json`, `pull.json`. Platform linux/amd64; no NVIDIA hardware available or simulated as real success.

## User's exact next action — no redeploy

1. If #5373 is still running, open its existing terminal/exec facility. Access to that gCube facility has not been verified here. Do not restart or deploy merely to obtain a shell.
2. Run the SHA-checked fixed-commit reader block in [README.md](README.md). The public helper URL was checked HTTP200 and SHA matches `7a12a58f130a9cdc7c50646a14f5a92cf06030dd0a3f4912f7480988ea8ba039`. It uses the existing loopback port8000 and reads current evidence without rerunning native GPU admission.
3. Return only its allowlisted JSON and the existing safe `/diagnostics` JSON. A `RECOVERED_SAFE_ADMISSION` result establishes recovered prior native evidence, not new GPU execution or render permission. An UNVERIFIED code must be retained; do not choose older files or change ownership to force recovery.
4. If terminal/current service is unavailable or files were lost, report that limitation. Do not redeploy under this task. A future deployment of the new image needs separate authorization; it will expose native details through the existing endpoint.

## Subsequent errors and hardware-only verification

No additional unresolved CPU implementation error was observed. GPU absence and unsafe supplementary identity are expected refusal paths, not an actual gCube diagnosis.

On a separately approved hardware run, preserve the FIRST `stage/errorCode/timestamp` and `safeDiagnostics.gpu` stagesA–F. That existing allowlist carries driver/memory, runtime library delivery, profile attempts, WebGL2 context/draw/pixel and reason codes. Do not dump environment variables, UUIDs, tokens or `admission_private.json`.

- NVIDIA/allocation error: check actual assigned device/model/driver and a single admitted allocation without changing GPU guards.
- GRAPHICS error: inspect allowlisted NVIDIA graphics capabilities and EGL/vendor/Vulkan ICD delivery before selecting an existing supported profile.
- WEBGL2 error: preserve native stages, software-renderer status and draw/readPixels reason; do not accept SwiftShader.
- GPU_MEMORY/shared-memory error: compare recorded capacity and configured existing budget; never lower admission requirements to force PASS.
- Source/dependency error: compare pinned manifests first; do not modify the renderer or reinstall arbitrary packages.

Actual RTX4080SUPER delivery, EGL/Vulkan, physical WebGL2 draw/readPixels, memory, gCube health/restart policy, remote export durability/download and 65422 rendering remain hardware/platform validation items. This task stops for user review.
