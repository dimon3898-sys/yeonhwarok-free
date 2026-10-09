# v022 RTX4080S verification after user approval

The Workload remains stopped during development. These are future checks, not
executed GPU results. Use the verified new immutable digest in RELEASE_VERIFICATION.json
and preserve the current gcube runbook, secure owner authentication and runtime:
`NVIDIA_DRIVER_CAPABILITIES=all`, `WORLD_ENGINE_RENDER_MODE=gpu-required`.

Run the MASTER sequence within one approved session:

1. Record NVIDIA model, nvidia-smi, actual WebGL renderer, Vulkan/GL-EGL selection,
   test draw and readiness in the existing Diagnostic ZIP. Stop quality admission
   if NVIDIA validation fails; software fallback stays prohibited.
2. Run the explicit `SECOND_EVENT_ADAPTIVE_WIDE_TEST`: 24 seconds, HIGH, 30 fps,
   the same Suez topic. It remains the original 720-frame camera-only contract.
3. Compare the separate `MAP_INFOGRAPHIC_QA_V022` OFF/ON plans at identical
   camera poses, audio, source/seed, LOD and materials. OFF is selected with
   `map_infographic=False`; ON is the new image's default 24-second HIGH request.
   Validate country outline/fill, persistent markers, native canal CLOSED/OPEN
   state and the visible hypothetical-scenario watermark. Check text hierarchy,
   steady halo, wrapping, source bounds, and intro-versus-lifetime behavior.
4. Run the packaged source-backed Production fixture separately. Its actual
   sentence TTS creates the timing; regenerate its PCM on the GPU host rather
   than copying development-host paths or assuming the local 253-frame clock.
   Suez canal, Singapore Port and Seoul contain only their authored geographic
   statements. Optional geometry Local-Close requires the explicit native-fit
   profile and a genuine area/line target. An uncovered local LOD is declared,
   without advertising new detail.
5. Download each MP4 and Diagnostic ZIP before stopping ephemeral storage.
   Inspect the source/image/font hashes, actual camera/frame audit, state timeline,
   duration/frame count, subtitle end, failure invariants and resume records.
   Review full-speed videos, normalized reference frames and continuous local
   frames; listen to the final AAC for narration, SFX and ducking.

Actual overlay/shader compilation, depth and LOD interactions, geography/text
readability, GPU memory/render time, and human visual/listening approval remain
NOT_RUN until these real outputs have been reviewed. The technical regression
and CPU Canvas evidence do not substitute for this review. No 75/80-second GPU
Production test is scheduled by this implementation task.

The existing public v021 digest in IMPLEMENTATION.md is the unchanged rollback
baseline. No existing release tag or `latest` is overwritten.
