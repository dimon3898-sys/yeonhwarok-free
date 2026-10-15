# gCube STORAGE recovery — final result

**STORAGE_FIX_READY_FOR_GPU_VALIDATION** — the isolated storage adapter and its published image are CPU verified. Actual #5373 startup, actual Dropbox permission semantics, NVIDIA execution and remote result recovery are not claimed as PASS. No GPU deployment or paid task was run.

## 1. Storage fix and confirmed cause boundary

The actual user-reported #5373 diagnostic is STORAGE_VALIDATION_FAILED at STORAGE with GPU/render disabled. Exact Dropbox UID, mode, chown/chmod behavior, symlink or I/O cause has not been independently measured. The existing bootstrap requires an engine-owned 0700 private directory; several low-level failures map to the reported code. The report does not infer one undocumented Dropbox behavior.

The verified fix removes the inappropriate dependency on treating a shared mounted export as a private POSIX working directory. It supplies a fresh container-local private path through **both existing APIs**, original `bootstrap.prepare_environment(account, storage=...)` and original `LauncherConfig(storage_root=...)`. The original directory, source, dependency, native GPU admission and render checks are retained. Environment-variable-only redirection is not used.

`/var/lib/world-engine-private/engine` is UID/GID 1000 and 0700 under a root-owned 0755 parent. Fresh sessions must be on an admitted local filesystem and pass real write/read/SHA/delete/rename/fsync/flock checks. Shared `/world-storage` is explicitly UNTRUSTED_SHARED_EXPORT_ONLY. It must pass UID1000 write/readback/delete before GPU admission. Existing mount files, permissions and ownership are never repaired, deleted or treated as private.

## 2. Changed files and reuse

Changes are restricted to new `recovery/gcube-storage-fix-v1/` and `.github/workflows/gcube-storage-fix.yml`:

- `storage.py`: strict private workspace, no-follow fd paths, fresh exclusive probes, read-only mount/legacy metadata, private receipt, safe log export, public capture allowlist and destination SHA verification.
- `launch.py`: storage keyword/config composition around the existing checks and diagnostic worker; local diagnostic persistence; original render plus verified export; original common capture guard and original per-session lock retained.
- `Dockerfile`: inherit immutable diagnostic base and add only two modules plus their manifest; provision new local private directory; preserve original package/dependencies/healthcheck.
- `ci.py`, three focused test files and workflow: free CPU verification, safe reuse, minimal build, unique tag, GHCR verification and fresh independent pull.
- README, settings, contracts, observed-error/checkpoint/retry records, run evidence, RESULT and SHA256SUMS: permanent reproduction material.

No original bootstrap, GPU launcher, diagnostic module, renderer, camera, ASTRA data or FINAL file was overwritten. The normal entrypoint still uses native admission, and Python test seams cannot dispatch production render. After a native capture, export requires a nonempty completed native report, source SHA validity, allowlisted media, copied-byte readback and completion receipt last. Private admission, source, frames/rows and internal reports are excluded from shared export. Failed copies leave private local output and a failure; they do not become a successful render/export result.

## 3. Reproduction and before/after validation

All following are real **CPU containers with synthetic filesystem fixtures**, not an actual Dropbox mount or GPU run:

| Case | Outcome | Evidence |
|---|---|---|
| Original diagnostic image, UID1000, shared root 0777 and existing legacy leaf root-owned 0755 | STORAGE_VALIDATION_FAILED, exit 1 | First run |
| New image, identical UID1000 and untouched shared mount | Private/export + SOURCE_INTEGRITY + DEPENDENCY pass, then GPU_HARDWARE_UNAVAILABLE, exit 2 | First run |
| New image, default root then original UID1000 transition | Same phase completion and NVIDIA absence, exit 2 | First run |
| New image, read-only export | STORAGE_UNAVAILABLE/EROFS, exit 1 before GPU | First run |
| New image, default-root diagnostic | Same completed CPU phases, NVIDIA absence, read-only service alive, exit 2 on stop | Latest run |
| New image, forced UID1000 diagnostic with actual groups [1000] | Existing UID_GID_FAILED refusal, exit 1; no service/renderer | Latest run |

The legacy directory UID/mode and sentinel bytes/metadata matched before and after. These numeric filesystem values describe the CPU fixture only; actual Dropbox values remain unmeasured.

Focused functional tests **40/40 PASS** (storage 24, launcher 16) in run 38680285245. The latest run reused them and the first four passing actual cases only after the fixed evidence SHA, original source commit, parent digest, runtime module hashes, Dockerfile SHA, test source bytes and execution counts matched. They are explicitly REUSED_NOT_REEXECUTED. Latest changed CI tests **15/15 PASS** in run 38680872082. Tests include real POSIX operations, path/symlink/hardlink/identity substitution rejection, actual denied access, ENOSPC/error preservation, failure/permission mocks, source/destination hash corruption, allowlist, incomplete report rejection, original flock concurrency and safe log redaction. Synthetic media bytes are not a rendered video.

Old eight-case reproduction, 56-diagnostic suite and 104-package suite were not rerun. Existing audits were reused. New image source/hash checks were performed before publication and again by the independent pull runner.

## 4. Follow-up error handling

The first new-image run passed all 52 then-current new tests and the four storage/normal container cases, but the forced nonroot diagnostic service condition failed. No image was pushed. Its actual failure was preserved as UID_GID_FAILED; the unchanged diagnostic security function requires no supplementary groups. A new read-only identity probe measured UID1000/GID1000/groups[1000]. The canonical image default root path can clear groups and then serve as UID/GID1000 with no supplementary groups. That path passed in the latest run, and the forced nonroot refusal also passed as an expected protection. No security check was weakened and neither runtime module changed for this CI correction.

The latest diagnostic response has /healthz 200 meaning service liveness only, status BLOCKED, gpuRenderingVerified=false and renderAllowed=false. /readyz is 503; GET /render is 404 and POST /render 405. The safe diagnostic JSON and private receipt were read back and hashed. Docker was running/healthy with RestartCount 0 during the CPU observation. This is not gCube restart-policy verification. Worker limit 240 seconds, startup grace 300 seconds and diagnostic TTL up to 900 seconds remain; a provider Always policy can restart after expiry.

SOURCE_INTEGRITY and CPU DEPENDENCY passed in actual CPU startup. NVIDIA absence is the expected hardware boundary. Actual card identity/driver, EGL/Vulkan, physical Chromium WebGL2 draw/readPixels, VRAM/shared memory and renderer output remain unexecuted hardware checks, not mocked PASS.

## 5. New image and reproducibility

Tag:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:rtx4080s-2f9158b-38680872082-1
```

Immutable reference:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:119873aa8515622c3508e934247bd4a18e85d080e3f33696e66acc1bae874825
```

- Manifest digest: `sha256:119873aa8515622c3508e934247bd4a18e85d080e3f33696e66acc1bae874825`.
- Config digest: `sha256:a5431019e55d0590c5bd6ceb4551ba5e2f71fc416e5a5ce9be2d72196485b97c`.
- Platform: linux/amd64. Local image size 1,570,425,119 bytes.
- Storage files manifest SHA-256: `ecee5f20c68bb55ae9d63964befa30fd6209b21d7615bde52847de033ee62b30`.
- Runtime source bytes: commit `97872d4949ad9a0d0c96b96fc418a68f24e67f67`, unchanged in the retry.
- Build/CI source commit: `d07e9469182548b9dee0a4858f85ac850f99b252`.
- Implementation checkpoint: `9e8c1bb`.
- Build evidence commit: `6e90fc9091823357b0dd122a0e7e38fe59f328a7`.
- Independent pull evidence commit: `bec44fe580c219404cf9d667fe40be7cb66160e0`.
- Branch: development/gcube-storage-fix-20261015.
- First CPU run: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38680285245
- Successful build/pull run: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38680872082

Build and push succeeded; a fresh independent runner pulled the exact digest and verified config, all original 160 files, all inherited diagnostic four files and both new module hashes. Anonymous manifest GET returned HTTP 200 with matching bytes/digest. Actual gCube registry UI/pull was not accessed. The first unpublished build was not reused after its ephemeral runner ended; only the small same-runtime diagnostic layer was rebuilt on the approved immutable parent, with a new unique tag. No original image/tag/digest was overwritten.

## 6. Protection, secrets and persistence

Existing FINAL, renderer, camera, frontier, geometry, data and original diagnostics changed: **0**. No old project files, images, caches or volumes were deleted. Only created CPU test containers/probes were cleaned. All required runtime source, Docker/build configuration, original dependency/base provenance, test fixtures, instructions and run evidence are remote-versioned. Required temp-only files: **0**.

Pinned Gitleaks scanned the actual new image application layer, new namespace and workflow: **0 findings**, exit 0. Parent audit was reused. The original source verifier's root-home field remains SEPARATE_PRIVILEGED_CI_CHECK_REQUIRED and is not mislabeled as a new complete parent credential audit. Ephemeral registry auth is outside the image/context and cleaned by the pipeline. Console and exports use strict allowlists; existing security refusal and GPU-required checks remain enabled.

## 7. Remaining real GPU and storage checks

Actual Dropbox UID/mode/metadata and writable export remain to be measured by the next real execution. If /world-storage is unwritable to UID1000 or read-only, the image must block; configure a verified approved writable export through gCube rather than forcing chmod/chown or ignoring admission. Private local work is ephemeral and capacity must be sufficient for capture.

Mounted-view readback is verified only in CPU fixtures. Remote Dropbox upload/durability, an external downloaded SHA match and survival after stop remain **UNVERIFIED**. Private admission/raw capture evidence stays local and requires a separately verified private retrieval channel if needed. Do not stop the real workload before external recovery and SHA verification.

Actual RTX4080SUPER device/driver injection, EGL/Vulkan, native WebGL2 pixel draw, memory limits, gCube liveness/restart policy and 65422 rendering must be checked on separately authorized hardware. No actual GPU success or automatic deployment approval is issued here.

## 8. Exact next user settings

Use the new tag above, preserve the image default root entry and leave command override empty; the bootstrap and diagnostic parent then drop safely to UID1000. Keep Dropbox mounted at /world-storage, writable for creation of a new UID1000 export namespace. Do not alter existing Dropbox files or the old legacy directory.

```text
WORLD_ENGINE_STARTUP_MODE=diagnostic
WORLD_ENGINE_DIAGNOSTIC_PORT=8000
WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS=900
NVIDIA_DRIVER_CAPABILITIES=graphics,utility
WORLD_ENGINE_RENDER_MODE=gpu-required
```

If configurable, use /healthz for liveness with at least 300 seconds startup grace; diagnostic /readyz remains 503. Keep the original recommended 2 GiB shared memory and verify actual capacity. If gCube mandates conflicting nonroot/supplementary-group settings, resolve that platform policy before expecting diagnostic keepalive; preserve the guard and inspect safe exported logs.

Collect the next actual error or GPU result from stdout/stderr, /diagnostics and /world-storage/world-engine-export-*/. Safe storage facts and WORLD_ENGINE_EXPORT_LOCATION_V1 identify generated export directories and checked file hashes. After successful native capture, only the new capture-*/public-review/ MP4/PNG/SHA256SUMS is suitable for public review. Verify externally downloaded bytes before termination. No paid redeployment was executed; await user review and separate GPU authorization.
