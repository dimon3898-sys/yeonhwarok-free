# WORLD ENGINE — isolated startup diagnostic image V1

This layer addresses the next startup's observability. It does not claim the
historical cause of gCube Workload #5373 is known or fixed.

Parent image (unchanged):
`ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:82a4d9086edc2345cd3f00430ff4c354ee3fbaedcef5f0b927a0d5f9c5e16a37`.
Source/reproduction baseline: `a28487dc8c901eb0ca38e0c162fe70dd39294430`.
Original RTX package `2f9158b`, ASTRA CPU `a002d894`, frontier `45af879` and all
approved FINAL/renderer/camera/visual files are preserved byte-for-byte.

## Layer boundary and reuse

Four standard-library modules are copied to a new directory outside the
original source contract: `/opt/world-engine-startup-diagnostics/`. A generated
manifest records their SHA-256 and source commit. The old application/dependencies
are inherited by immutable digest, with no apt/pip/npm installation or full
package rebuild. No original file is overwritten.

`startup.py` reuses the original preparation, source verifier, dependency verifier,
native `admit_gpu`, admitted health server and renderer functions. A nonmutating
call observer identifies preparation failures without replacing a check.
Normal mode preserves failure exits 1/2 and native admission before render.

Only the explicit `WORLD_ENGINE_STARTUP_MODE=diagnostic` enables an isolated,
bounded startup worker. The worker executes the same native checks and sends a
bounded sanitized record to its parent. The parent verifies it, drops to UID/GID
1000 with no supplementary groups, and starts a read-only diagnostic service.
No admission object or rendering capability is transferred. Failed privilege
transition prevents the service from opening.

## Record contract

Records contain schema, mode, stage, fixed error code/reason, UTC time, exit code,
and an allowlisted diagnostic object. Stages distinguish runtime/storage,
UID/GID, source integrity, dependencies, NVIDIA, graphics, Chromium, WebGL2,
GPU/shared memory and unexpected failures. Original GPU A–F stage diagnostics
and EGL/Vulkan attempt evidence are reused and further filtered.

Raw exception text, traceback, environment values, tokens, passwords, URLs,
GPU UUIDs and arbitrary graphics identity strings are omitted. Structured
stdout/stderr precede best-effort private-file persistence. Storage refusal
cannot suppress the console record. File creation never repairs ownership or
permissions on existing mount contents; a private nonpersistent `/tmp` fallback
is explicit. This is not a new result-file downloader.

## Mode and health contract

- Normal mode delegates original native execution; failed admission exits 2.
- Diagnostic `/healthz` HTTP 200 describes only diagnostic liveness. Its body
  preserves `BLOCKED`, the startup failure, `gpuRenderingVerified:false` and
  `renderAllowed:false`.
- Diagnostic `/readyz` is always 503; render and command paths are absent.
- Docker HEALTHCHECK validates the selected mode and response fields. It never
  returns success merely because the Python process exists.
- Worker timeout, signal cancellation and diagnostic TTL preserve nonzero
  failure semantics. Worker processes are stopped/reaped on interruption.
- Actual gCube probe/restart settings and hardware remain unverified. TTL expiry
  may cause a platform restart; no promise of indefinite platform keepalive is made.

## Validation and build

`.github/workflows/gcube-diagnostic-image.yml` permits only the public repository,
its isolated branch and the free standard `ubuntu-24.04` runner. It checks 20 GiB
of disk-backed Docker space and protected source paths. It runs only new focused
tests on the approved CPU base, then builds the small diagnostic layer.

The resulting image is checked for four new source hashes, all 160 original
file hashes, real CPU normal/diagnostic failure behavior, read-only storage,
sanitized record persistence, HTTP/render denial and Docker health consistency.
Gitleaks scans the actual new application layer and new source/workflow. The
original image audit and 104 package tests, plus the prior eight-case reproduction,
are reused rather than repeated. Mocks remain explicitly separate from actual
CPU container observations and unexecuted GPU validation.

Publication uses an unused run-ID tag and verifies its remote manifest/config.
A separate fresh runner pulls by immutable digest and rechecks original/new
sources. The tag retains the original-package prefix
`rtx4080s-2f9158b-<run-id>-<attempt>`; labels and the diagnostic manifest identify
this layer's source commit. No existing tag/digest is overwritten.

Final decision is `GPU_DIAGNOSTIC_IMAGE_READY` only after successful build,
zero secret findings, publication and independent pull. Otherwise it remains
`GPU_DIAGNOSTIC_BLOCKED`. Neither decision is an actual gCube recovery/GPU PASS.

See `GCUBE_DIAGNOSTIC_SETTINGS.md` for the future, separately authorized settings.
