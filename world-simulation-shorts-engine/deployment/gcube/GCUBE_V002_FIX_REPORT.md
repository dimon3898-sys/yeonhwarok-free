# gcube-v002 startup correction

Verification date: 2026-10-07 KST. New image:
`ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v002`.
The existing `gcube-v001` tag must not be rebuilt or pushed by this workflow.
Publication, source revision and old/new digests are recorded in
[release evidence](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_BOOT_FIX_v002/GHCR_V002_PUBLICATION.json).

## What was reproduced

The user reports workload #5324 `world-engine-test`: RTX3070 8GB, CPU12/RAM16GB,
driver616.56, CUDA Toolkit13.4.0, shared-memory1GB, Istio enabled. Image pull and
container creation succeeded, followed by repeated exits. These are user-reported
provider facts, not measurements taken by this development environment.

The exact termination message from #5324 is unavailable. It would be incorrect
to claim a particular GPU, owner-code or storage failure was its proven cause.
The original startup adapter was reproduced in a CPU container with three real
exit-code2 paths: missing owner code, absent required storage path and unavailable
NVIDIA hardware in GPU-required mode. An actual `GET /api/health` with Kubernetes
Pod-IP authority returned HTTP400 `INVALID_HOST`. These failures happen before a
usable endpoint or can cause a provider liveness failure after startup.
[Reproduction evidence](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_BOOT_FIX_v002/v001_reproduced_failures.json).

## Changes confined to deployment

- Start a bounded read-only status listener on `0.0.0.0:8000` before preflight.
  Configuration/GPU rejection displays a fixed error code and keeps this service
  in the foreground. It never authenticates a user, accepts a render or silently
  falls back to CPU. Readiness explicitly remains false.
- Separate `/healthz` liveness from `/readyz` readiness. Kubernetes/IP/Istio health
  requests receive minimal read-only facts without binding an origin. All owner
  authentication and state-changing API origin checks remain in effect.
- Handoff port8000 to the original authenticated gateway only after admission.
  Keep the server as a foreground child; propagate termination to its process
  group with Tini and close the startup/termination race. Container CMD is empty.
- Prepare immutable cache/audio image links at build time through engine-owned
  `/run/world-engine`. The real cache and audio remain in isolated storage; UID1000
  need not modify root-owned app/source directories. `/data` is engine-owned for
  explicitly selected ephemeral QA. Required Personal Storage is never silently
  downgraded and existing data/ownership are not rewritten.
- Retain only non-root supplementary groups of actual NVIDIA/DRI character
  devices for the same unprivileged browser probe and server. No device mode,
  ownership, renderer shader or graphics asset is changed.
- Keep NVIDIA WebGL draw admission, bounded EGL/Vulkan attempts, owner-code
  validation, Chromium, FFmpeg and the certified 28-source preflight. RTX3070 and
  driver616.56 parse; CUDA Toolkit remains optional and unused. Chromium already
  uses `--disable-dev-shm-usage`. No unverified GPU flag change was introduced.

## Verification and limits

All **134 deployment tests pass** (31.182s). The current adapters on the existing
CPU dependency container passed owner login, unauthenticated401, authenticated
project access, Pod-IP/Istio health and a **61.545s** sustained foreground check.
All25 saved QA artifact hashes match; no render was requested.
[CPU evidence](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_BOOT_FIX_v002/cpu_gateway_sustained.json).

The publication workflow additionally builds the entire standalone image and
requires root and UID1000 CPU boot/login, a real bridge-IP port8000 request,
`0.0.0.0:8000` socket inspection, sustained processes, unapproved12s fixture and
owner-only diagnostic download. Three fresh failure-case containers must remain
alive with readiness503 and rejected mutation APIs. A status page alone cannot
pass the positive engine-readiness gate. Publication occurs only after these
checks succeed. See release evidence for their actual outcome.

The original core generator, MASTERs, renderers, graphics assets, projects,
checkpoints and cached outputs are preserved. No75s/80s or short video rerender
was performed. Actual gcube NVIDIA rendering, actual #5324 termination cause,
provider HTTPS/probe configuration and point consumption still require the
next provider deployment. A healthy status listener is not a GPU-success claim.

## Mobile redeploy settings

Stop #5324, replace only its image with `gcube-v002`, keep port8000 and leave the
container command blank. Keep the same owner code for existing storage (16–512
characters, no surrounding whitespace/control characters). Keep existing native
Personal Storage at `/world-storage`. If none was attached, the first QA can
explicitly select `WORLD_ENGINE_STORAGE_MODE=ephemeral` and
`WORLD_ENGINE_STORAGE_PATH=/data`; stopping may delete its files, so this is not
the persistent production configuration. GPU-required remains the default.

If a health-path option exists, use `/healthz`. `/readyz` is a separate readiness
check and returns503 until the actual engine is admitted. Istio and the currently
selected hardware can stay unchanged. Redeploy and open the issued service URL.
An initialization-error page supplies a safe code without terminal access and
does not mean the engine is ready. Stop the workload after checking/downloading;
keeping a blocked status service alive can still incur provider charges.
