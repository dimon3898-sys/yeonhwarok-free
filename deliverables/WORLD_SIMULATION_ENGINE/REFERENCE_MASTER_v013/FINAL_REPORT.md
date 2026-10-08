# WORLD ENGINE v013 — verified release

Verified 2026-10-08T11:31:07+09:00 (Asia/Seoul). Actual gcube workload/GPU was never operated. No75/80-second render. This release has planning/native geometry and container/media approval; it does not have a new GPU-output aesthetic approval.

- Image: ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v013-reference-master
- Immutable digest: sha256:102a77d567c2cd7306aa66d811b6aa8f334e0c6e656684a623d4cc9531b74ff7
- OCI source revision: 78385fbe721a0b55aa5ae18bedd7ebd12ee101e8
- Source branch: fix/v013-reference-master (main merge is not claimed).
- Actual image CI: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37716774481 — Success.
- Core569 +proxy206 +unchanged diagnostic suite31 =806 passing;0 failures;0 skips. New40 tests pass locally. The host-only root permission skip from an earlier local proxy run is resolved by the actual container root test gate.
- Required libegl1/libvulkan1/libx11-6/libxext6, Node, Chromium, FFmpeg,67 asset checks and UID1000 writable/data/runtime paths: PASS inside image.
- Four reference-master12-second domain fixtures: PASS; planning/native readability warnings0.
- 75-second production: complete geographic planning/native admission regression only, no video render.
-360 valid synthetic JPEG frames at HIGH2160×3840 internal→1080×1920 output: encoding, exact frame-clock concat, real audio, QC and controlled S002 retry PASS. Synthetic media46.663 seconds is a CPU test measurement, not a GPU render benchmark.
- Existing legacy synthetic5-scene media and retry: PASS.
- Subtitle optional: PASS; TTS optional over-budget policy rejected explicitly. Offline20-second provider budget check PASS. TTS/Subtitles remain OFF by default and available as options.
- Authenticated gateway health/login/secure session +61s foreground persistence: PASS.
- Actual production entrypoint with no physical NVIDIA: healthy web service, engine_ready=false, GPU_HARDWARE_UNAVAILABLE, no software GPU substitution or CPU fallback; persisted61s.
- Anonymous actual Docker pull from public GHCR, matching OCI revision and digest, plus owner-login and61s persistence on the pulled image: PASS.
-45 protected legacy/GPU/proxy/audio/diagnostic/graphics source files: byte-identical, hash proof attached.

## New direction and event-relative timing

Profile→event/information budget→perception timing→camera/text/route/entity/SFX→sourced geographic Scene IR. No5 equal scenes, no global hold constant, no Suez-only direction branch. REFERENCE_MASTER is the new QA preset; saved legacy plans and FAST_PLUS_LEGACY remain versioned.

Shipping QA uses four causal beats. Primary reveal→next major movement/end intervals: departure1.733 s; Suez closure1.433 s; alternative route1.600 s; Singapore result2.033 s. Subsequent location is introduced after camera lock, then primary event0.6s later. Scene exit/start camera continuity and hold pose/FOV are verified on every native frame. See SHIPPING_TIMELINE.json for each absolute start/end/deceleration/lock/reveal/SFX time, labels and priorities.

One primary and at most one subordinate location; support is removed before shortening recognition time. Labels have a local contrast treatment and safe/collision layout. Routes use zoom-based widths/priority. Display entity size is bounded independently of physical geometry, which retains original grounding/clipping checks. Lighting is beat-specific with surface fill/night readability; texture/cloud/atmosphere/city assets remain intact. Result has a locked camera and a39.34% ray-projected screen area; that is geometry, not measured GPU pixel occupancy.

The reference is not globally slower: its longest high2D-motion run is2.133s versus current1.233s; current p95 apparent rotation11.20°/s is lower than reference14.10°/s. The current's late Suez information has only≈0.72s to the next major motion; earlier1.533s camera settle was incorrectly treated as recognition time for information disclosed later. Final current metric is available≈1s. The reference's local detail intervals are1.433/2.167s and its final information2.533s but still zooming. All635/360 frames were decoded; optical flow is not a calibrated3D camera measure. Mixed reference audio cannot isolate precise SFX timestamps; unavailable fields stay null, with no copied reference sound/graphic assets. New authored SFX event/PCM alignment passes the existing one-frame gate.

## Additional real container defect repaired

Bookworm MP4 source format durations round64/88/93/115-frame scenes to2.134/2.934/3.100/3.834s. Legacy concat on those same movies creates360frames at276480/9217fps (29.996745), stream duration12.001302s. Reference-only explicit frame-count offsets yield360frames at30/1fps and12.000000s. All compressed packet payloads and H264 parameter sets are preserved. No re-encoding, frame drop/duplication or QC tolerance change. Completed assembly proof/file hash protects retry; legacy pipeline remains unchanged.

## Output evidence and next user test

Existing Diagnostic ZIP/FAILED_INVARIANT/redaction remains intact. It receives reference preflight timing/projection metrics and actual frame camera motion, label visibility, reveal timing and sampled pixel geography/route metrics. Plan prediction and actual observations are marked separately. Unrun GPU/pixel checks stay NOT_RUN. Technical WARNING policy does not claim perceptual approval.

Next user operation only: use the new image and same RTX4080S/port8000 settings, NVIDIA_DRIVER_CAPABILITIES=all and gpu-required. Replace any previously exposed owner code privately in gcube Secret settings before public login. Create a NEW12s HIGH REFERENCE_MASTER Suez plan once. Assess closure/route/result recognition, text priority, entity tracking, night map readability, route contrast, stable final frame and SFX. Download MP4+Diagnostic ZIP then stop the workload. No75/80s render yet.

PWA/standalone app/brighter web UI remains TODO; no implementation in this release.
