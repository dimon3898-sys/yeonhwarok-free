# gCube STORAGE recovery adapter V1

This is an isolated startup/storage layer on the immutable diagnostic image. It preserves the approved RTX package, ASTRA CPU, frontier effect, FINAL, renderer, camera and original diagnostic module bytes.

The actual #5373 error reported by the user is STORAGE_VALIDATION_FAILED at STORAGE. Exact Dropbox owner/mode/metadata behavior has not been measured. The fix addresses the confirmed contract conflict: a mounted shared destination must not be treated as a verified private POSIX work directory. It does not claim the historical low-level Dropbox failure is known.

## Reuse and behavior

The original bootstrap already supports `prepare_environment(account, storage=...)`; the original GPU LauncherConfig already accepts `storage_root`. The new launcher supplies the same fresh private local session path to both APIs. Original source/dependency/native GPU checks, renderer, normal health server, diagnostic worker, redaction and read-only diagnostic service are reused. No test injection authorizes production render.

The new local base is `/var/lib/world-engine-private/engine` (UID/GID 1000, 0700), beneath a root-owned 0755 parent. Known local filesystems and safe no-follow ancestors are required. Actual private write/read/SHA/delete/rename/fsync/flock capabilities are verified. The original private-directory check remains in force.

The mounted `/world-storage` is an **UNTRUSTED_SHARED_EXPORT_ONLY** destination. Existing files, modes and owners are untouched. New random namespaces use fd-relative no-follow operations and exclusive file creation. Actual shared write/readback/delete is required before GPU admission. Read-only or inaccessible exports fail closed and remain observable in stdout/stderr and diagnostic mode.

The adapter exports strict sanitized startup/preflight diagnostics and, after a successful native capture, allowlisted `public-review` MP4/PNG/SHA256SUMS only. Private admission, source, full frames/rows and internal capture reports remain in private local storage. It checks the completed native capture report and source hashes, copies without overwrite, verifies destination hashes, and writes completion receipt last. Source output survives an export failure locally; that local copy is ephemeral.

`mountedViewReadbackVerified=true` does not imply remote Dropbox persistence, external download or stop safety. These flags remain false until separately verified outside the container. See DATA_AND_SECURITY_CONTRACT.md.

## Modes and reproduction

Default normal mode retains native GPU-required admission, failure exits and explicit `--check` / `--render-65422`. The normal server never offers a render HTTP endpoint. Diagnostic mode remains explicit via `WORLD_ENGINE_STARTUP_MODE=diagnostic`, is bounded, keeps GPU readiness false and rendering disabled, and exposes liveness separately from readiness. No GPU deployment or renderer feature development occurs in CI.

`--check-storage` is a one-shot **CPU-only** check of private/shared storage, source and dependencies. Its STORAGE_ONLY_VERIFIED response explicitly has gpuRenderingVerified=false/renderAllowed=false. It is not a rendering bypass, a GPU health check or a persistent container command. Leave the deployment command override empty for the diagnostic service.

The new GitHub Actions workflow on `development/gcube-storage-fix-20261015` uses the free public standard ubuntu-24.04 runner with a 20 GiB disk gate. It runs only new focused tests, reproduces representative original STORAGE_VALIDATION_FAILED on a shared mount, compares the new layer on the identical untouched mount, verifies subsequent source/dependency phases and expected no-GPU failure, and checks diagnostic export. Explicit permission/GPU mocks are labeled separately from actual CPU containers. The old eight-case, 56-diagnostic and 104-package suites are not rerun.

The Dockerfile inherits the pinned diagnostic digest, adds only storage.py/launch.py plus their manifest, and uses the existing mode-aware healthcheck. No apt/pip/npm installation or old package rebuild is needed. All 160 original files, four inherited diagnostic modules and two new source files are verified before publication and by a fresh independent digest pull. Tags are unique; old images are preserved. New source/image-layer/workflow Gitleaks must report zero findings.

`ci.py` phases are run by `.github/workflows/gcube-storage-fix.yml`; the workflow supplies ephemeral scoped GitHub credentials without recording them. No private tokens belong in this repository. See the final run evidence for exact source/image digests and actual outcomes.
