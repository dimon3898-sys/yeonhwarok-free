# Production Studio MVP package

The new image extends immutable V4 image
`ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:4f2daf520eed2331a1b6ea0d3644e6f7d65854e7d4f3368d43af5f96d1ff6ab4`.
It adds only `/opt/world-engine-production-studio`; the original strict 373-file
repository stays unchanged. No dependencies, browser, renderer or camera are
reinstalled. `STUDIO_FILES.json` binds every explicitly selected source, licensed
WAV, front-end file and focused test. Data/source hashes remain authoritative.

The **new image only** uses a small bootstrap ENTRYPOINT. It validates its own
payload, starts the original `/opt/world-engine-storage-fix/launch.py` unchanged,
waits for the original GPU/health service on port 8000, then starts the independent
Studio service on port 8080 as UID 1000 retaining only the frozen original graphics-device group allowlist. Either child
exiting stops both; no automatic service restart or video restart is added.
The original Docker HEALTHCHECK remains inherited and unchanged.

## Required deployment settings

The user manually deploys and stops gCube. This package does neither operation.

- Explicitly select **container port 8080** for the mobile HTTPS ingress. The
  inherited image still exposes port 8000; automatic port selection may choose
  its health-only service. Keep port 8000's inherited internal healthcheck.
- Set `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN` to the actual issued HTTPS origin,
  without path, query, trailing slash or credentials. Do not invent a URL.
- Supply an actual, user-chosen `WORLD_ENGINE_STUDIO_OWNER_CODE` through the
  workload's approved secret input. It must contain 16–256 visible ASCII
  characters. No credential is generated or included in the image.
- Supply `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST=sha256:<actual-new-image-digest>`.
- Keep the existing GPU-required configuration, NVIDIA graphics/utility device
  access, shared memory 2 GiB, and Dropbox mounted at `/world-storage`.
- Optional `WORLD_ENGINE_STUDIO_PORT` changes8080 but cannot select8000.

The owner code is consumed into a private0600 UID 1000 file under
`/var/lib/world-engine-private/engine/production-studio-mvp-v1/owner-code`.
Existing owner configuration is preserved; a different new code does not
silently overwrite it. Neither owner code nor raw operator-policy JSON is passed
into the health service, GPU renderer, Chromium, Studio child or FFmpeg.

A real operator policy is required before any authenticated Start. Configure it
with `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON`, containing exact fields
`validUntil`, `maxWallSeconds`, `maxRetries`, `maxCostAmount`, `currency`, and
`gpuHourlyRate`; optional schema is `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1`.
Use the actual rate, explicit expiry/timezone and user-approved limits. No
example number grants a budget. The controller enforces all values again.
The policy becomes private0600 `production/operator_policy.json`; absent policy
blocks Start, while existing policy is preserved. User login plus an explicit
Start consent is still required. Policy configuration alone starts no job.

Actual gCube HTTPS/proxy reachability, NVIDIA execution, partial GPU rerender,
80-second output, external Dropbox synchronization and final visual quality must
be verified in the separately approved hardware run. CPU/SwiftShader and mobile
fake-controller tests do not establish those results. Renderer timeout does not
stop gCube billing; the user must manually stop the workload.

## Free CI

The independent workflow runs on public standard `ubuntu-24.04` only. It guards
20 GiB free disk without deleting existing resources, validates a unique new tag,
runs focused CPU and real mobile-browser tests, builds from a strictly selected
payload, checks all 373 old files, performs one existing image-local V4 actual
SwiftShader draw/readPixels test, scans actual new image/source bytes with pinned
gitleaks/default rules, publishes, then pulls and verifies the immutable digest
on a separate runner. Existing tags/images/claims are never replaced.

No new image tag or digest is valid until actual CI build, publication and
independent pull evidence exist. `runs/<run-id>-<attempt>/` records actual results.
