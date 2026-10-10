# Gate 1 RTX4080S Static Proof release

This service packages the original iteration-05 compiled plan and renderer bytes.
It does not tune the visual pipeline. `createProofFinal` is the original factory;
all shader, material, coverage, relief, boundary, glow, marker and glyph passes
remain in the frozen module. Runtime hardware admission lives outside it.

The UI is served by this container, and Chromium runs on the gCube server. A phone
downloads the server-generated PNG; its local browser GPU is not substituted for
RTX4080S. `CHECK GPU / WEBGL2` checks identity, capabilities and an actual pixel
clear/readback. `GENERATE STATIC PROOF` rechecks admission, then draws exactly one
proof frame. Vulkan admission may fall back to the preserved GL-EGL hardware
profile. SwiftShader, software adapters, wrong GPU and insufficient capabilities
fail explicitly. There is no CPU-success fallback in public UI/API.

## Deployment

- Image: use the verified immutable tag/digest from release evidence.
- GPU: RTX4080 SUPER; provider graphics/utility NVIDIA userspace injection.
- Container port: 8000. Command override: empty.
- Required secret environment: `WORLD_ENGINE_OWNER_CODE` (at least 12 characters).
- `WORLD_ENGINE_GPU_PROFILE=vulkan` defaults to Vulkan with hardware GL-EGL fallback.
- `WORLD_ENGINE_RENDER_MODE=gpu-required`; CPU mode is refused at boot.
- Use the provider HTTPS URL. Open it and log in with the owner code.
- Click `CHECK GPU / WEBGL2`, confirm the server renderer is NVIDIA RTX4080 SUPER.
- Click `GENERATE STATIC PROOF`. Download `SUEZ_STATIC_PROOF_RTX4080S.png`
  and `SUEZ_STATIC_PROOF_RTX4080S.diagnostic.json` before stopping the workload.
- User visual approval is still required. No next Gate is invoked.

## Paths

`/healthz` is public, contains no secrets and never starts the GPU.
`/auth/login` establishes an HttpOnly SameSite session.
`/api/check-gpu` and `/api/generate` require authentication and CSRF header.
`/api/jobs/{id}` exposes progress and bounded stage timings.
`/download/{id}/png` returns an authenticated HTTP PNG attachment with the exact
required filename, only after GPU admission and one-frame success.
`/download/{id}/diagnostic` also works after a failed GPU check.

No public request can change scene, renderer, dimensions, seed, theme or mode.
No FFmpeg/video/TTS/audio/Production modules are imported.

Each Chromium worker has launch/navigation deadlines, a 150-second hard deadline,
10-second progress heartbeat and a server watchdog at 180 seconds that reaps only
its child process group. Jobs are serialized. No automatic startup rendering.
PNG and diagnostic are ephemeral container output; download them before stopping.
Peak VRAM/RAM is `UNKNOWN` because this release does not measure it.

## Focused validation

The release checks frozen sources/assets, API/login/health/download security,
browser/mobile download, capability rejection, one-frame mode, source provenance
and same factory. Local `validate-software` CLI is validation only: its diagnostic
and filename say `SOFTWARE_TEST_ONLY`; the public server cannot select that mode.
NVIDIA quality/performance is NOT RUN until the user runs gCube.

The original software PNG, iteration montage and report are never overwritten.
Legacy regression is not invoked by this release.
