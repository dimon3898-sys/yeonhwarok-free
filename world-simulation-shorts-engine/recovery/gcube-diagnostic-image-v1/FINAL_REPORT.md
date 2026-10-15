# gCube startup diagnostic image — final CPU result

Decision: **GPU_DIAGNOSTIC_IMAGE_READY**. This certifies the new diagnostic image's build, registry presence and focused CPU behavior. Workload #5373's historical root cause remains **UNCONFIRMED**; no gCube deployment, paid work or NVIDIA hardware execution occurred.

## 1. Modified files

All changes are new files under `world-simulation-shorts-engine/recovery/gcube-diagnostic-image-v1/`, plus `.github/workflows/gcube-diagnostic-image.yml`. The original package and approved FINAL/renderer/camera/frontier/ASTRA sources were not edited.

- `startup.py`: wrapper around original bootstrap, source/dependency verification, native GPU admission and admitted normal dispatch; explicit isolated diagnostic worker.
- `records.py`: strict stage/code/time/reason diagnostics and safe private persistence.
- `service.py`: unprivileged, bounded read-only diagnostic HTTP service.
- `healthcheck.py`: mode-aware liveness validation, preserving failed GPU readiness.
- `Dockerfile`: four modules and a generated hash manifest in a separate image directory, inherited immutable base; no dependency installation or old-file replacement.
- `ci.py`, `tests/test_startup.py`, `tests/test_records_service.py`, `tests/test_ci_safety.py`: focused CPU/build/publish/pull checks.
- README, settings, local/retry/run evidence, result and SHA256SUMS: reproduction and verification records.

## 2. Error recording and diagnostic behavior

Records distinguish storage/mount/ownership, UID/GID, source integrity, dependency, NVIDIA, EGL/Vulkan graphics, Chromium/WebGL2, GPU/shared memory, and unexpected failures. They contain a UTC timestamp, fixed code/reason, exit status and allowlisted facts. Original native GPU checks and sanitization are reused. Arbitrary exceptions, environment values, secrets, UUIDs and identity strings are not echoed.

Structured stdout **and** stderr are emitted before best-effort private JSON persistence. Files use 0600, new diagnostic directories 0700. Existing mount ownership/mode is not repaired. Primary path: `/world-storage/rtx-gpu-package-v1/startup-diagnostics/`; fallback: an exclusively created `/tmp/world-engine-startup-diagnostics-*` directory. The fallback is not durable. Console logging remains when storage is unusable.

Only `WORLD_ENGINE_STARTUP_MODE=diagnostic` enables the new service. The original checks run in a bounded worker; the parent validates its record and drops to UID/GID 1000 with no supplementary groups before listening. Worker timeout is 240 seconds; signal cancellation terminates and reaps it. Diagnostic mode cannot dispatch render, including after a successful diagnostic-only admission.

## 3. CPU validation and actual observations

Free public standard `ubuntu-24.04` Actions run: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38676932882

New focused tests: **56/56 PASS** (24 startup, 16 records/service/health, 16 CI safety). Tests include explicit NVIDIA/WebGL failure mocks, permission and UID failures, source/dependency early stops, canary redaction, record persistence, render blocking, timeout/signals and health consistency. Mocks are not hardware evidence. The previous eight-case reproduction and 104 package tests were reused, not rerun.

Actual new CPU image cases, no GPU:

| Case | Exit | Result |
|---|---:|---|
| Normal, no GPU | 2 | `GPU_HARDWARE_UNAVAILABLE`; no diagnostic keepalive |
| Normal, read-only storage | 1 | `STORAGE_READ_ONLY`; normal failure preserved |
| Diagnostic, no GPU | 2 on stop | Failure visible, private primary record, service alive, render denied |
| Diagnostic, read-only storage | 1 on stop | Failure visible, private local fallback record, service alive, render denied |

Both diagnostic cases returned `/healthz` 200 with `status=BLOCKED`, `gpuRenderingVerified=false`, `renderAllowed=false`; `/readyz` 503, GET `/render` 404 and POST `/render` 405. Each was running with Docker health `healthy` and RestartCount 0 during the observation; stop preserved the original nonzero failure.

The initial run 38676332924 stopped before build because a test incorrectly assumed the original sanitizer retained a malformed device name. The fixture was corrected without weakening the original filter. A verified worker normalization issue was also fixed using the existing strict `safe_record`; three directly related new checks passed. Full evidence and the retry rationale are retained.

## 4. Restart-loop limits

The tests demonstrate bounded diagnostic liveness under Docker with `--restart=no`, not gCube's actual policy. Diagnostic readiness remains failed. Docker startup grace is 300 seconds, longer than the 240-second worker deadline. Diagnostic TTL is 1–900 seconds (default 900); expiry and signals preserve nonzero failure. A platform Always policy can restart after expiry. Actual #5373 probe path/startup grace/restart behavior is still unknown. Do not use `/readyz` as liveness or change readiness to 200 to satisfy a provider.

## 5. Published image and integrity

Tag:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:rtx4080s-2f9158b-38676932882-1
```

Immutable reference:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:3e8611e32860f4ae4f01febda8c4567f069552b111d7628cf0836101bdda9297
```

- Manifest digest: `sha256:3e8611e32860f4ae4f01febda8c4567f069552b111d7628cf0836101bdda9297`.
- Config digest: `sha256:f159e8bcbaa7746ad2ec5a4f69a6337a9917c7f8f37d362cf86061773288e1b8`.
- Platform: linux/amd64; local image size: 1,570,331,967 bytes.
- Diagnostic module manifest SHA-256: `de56af52ab0655045efed69fbc7a1f3cdf2b99ade96e700e89cf8a0e6dcba59a`.
- Build and GHCR push PASS; separate fresh runner digest pull PASS, matching config and sources.
- Anonymous GHCR manifest GET HTTP 200, exact digest match. No gCube pull/UI validation claimed.
- Source: `2799b949cab8c8954f2ac7f2a72f7f9b1a2f7a7d`.
- Build evidence: `f517e300eb61309e640d4c4cd422bba4c94d7ff7`.
- Independent pull evidence: `4ff96b0898ba7930df410bb739dfde3a0d726364`.
- Branch: `development/gcube-diagnostic-image-20261015`.

## 6. Protection, secrets and persistence

Original 160 packaged files and new four module hashes matched in both build verification and independent pull. Existing FINAL, renderer, camera, frontier and data changes: **0**. Original image/tag/digest preserved. No existing image/cache/volume/project-file deletion was performed. The image inherits the approved immutable base; only the small new diagnostic layer was built.

Pinned Gitleaks scanned the actual new image application layer, new namespace and workflow: **0 findings**, exit 0. Original parent audit is reused. The new records additionally pass canary/strict-allowlist tests. Existing parent credential audit fields marked `SEPARATE_PRIVILEGED_CI_CHECK_REQUIRED` remain unchanged and are not relabeled as a new complete parent audit.

All runtime-required new source, Docker configuration, test/reproduction instructions and evidence are stored on the remote branch. Required temp-only files: **0**. Temporary CI build contexts/fixtures/auth files are not runtime dependencies; generated private Docker auth is removed by the pipeline. Diagnostic `/tmp` output remains intentionally nonpersistent.

## 7. Actual gCube checks still required

Obtain #5373's real exit code, stdout/stderr and pod health/restart configuration. On a separately authorized diagnostic GPU execution, inspect the recorded first failed stage, Dropbox mount/UID semantics, NVIDIA device/driver injection, graphics capabilities, EGL/Vulkan, Chromium native WebGL2 draw/readPixels, VRAM/shared memory and external liveness behavior. No historical cause is inferred from the CPU cases.

## 8. User settings for the next separately authorized execution

Use the published unique tag, leave command override empty, expose diagnostic port 8000 and set:

```text
WORLD_ENGINE_STARTUP_MODE=diagnostic
WORLD_ENGINE_DIAGNOSTIC_PORT=8000
WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS=900
NVIDIA_DRIVER_CAPABILITIES=graphics,utility
WORLD_ENGINE_RENDER_MODE=gpu-required
```

If probes are configurable: liveness `/healthz`, startup grace at least 300 seconds; readiness `/readyz` remains 503. Confirm these are compatible with gCube before expecting keepalive. Preserve original GPU/mount settings when isolating their failure; do not alter permissions or bypass admission. Collect console and `/diagnostics` evidence before TTL/container termination. Review `GCUBE_DIAGNOSTIC_SETTINGS.md` for restrictions.

No deployment, render or next development stage was started. Await user review and separate GPU deployment authorization.
