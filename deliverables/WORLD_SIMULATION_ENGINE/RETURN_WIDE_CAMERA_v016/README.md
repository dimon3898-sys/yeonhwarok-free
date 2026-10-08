# SINGLE_EVENT_RETURN_TO_WIDE_TEST v016

A separate 15-second camera QA preset. Existing production, Reference Master and saved v015 plans are retained. v015 camera JavaScript is byte-identical; the new preset imports it. All camera positions, quaternions and FOV values at frames 0–359 match v015 exactly. An explicitly computed close-to-wide transition occurs only at 12–14 seconds; no video reversal, orbit, world rotation or next destination is introduced.

## Timeline (end frame exclusive)

| State | Frames | Seconds |
|---|---:|---:|
| WIDE | 0–60 | 0–2 |
| EVENT_LOCATION | 60–90 | 2–3 |
| ZOOM_IN | 90–150 | 3–5 |
| SETTLE | 150–180 | 5–6 |
| EVENT_REVEAL | 180–240 | 6–8 |
| EVENT_HOLD | 240–330 | 8–11 |
| EVENT_RESOLVED | 330–360 | 11–12 |
| ZOOM_OUT | 360–420 | 12–14 |
| FINAL_WIDE | 420–450 | 14–15 |

Exactly 450 frames; gap 0, overlap 0, final end frame 450. Camera remains close and fixed during resolution; final wide is fixed for 30 frames. Suez target: latitude 30.318359°, longitude 32.382202°. Close center-distance 1.2 Earth radii / FOV 48°; wide center-distance 3.5 Earth radii / FOV 64°.

## Resolved state

At 11s, existing-label styling displays CANAL OPEN and the old blockade barrier is hidden. This is a QA resolved state, not an additional destination/story. Original location/closed labels remain at 2s/6s; no text design, lighting, route/entity design or audio code changes were made. No additional SFX is introduced.

## Scoped QA QC

The unchanged original technical QC still decodes video and checks frames, format, textures, clipping, WebGL, routes, camera continuity, brightness and audio. Only this explicit v016 QA preset treats intentional stillness and single-event narrative retention as nonapplicable production policy. The original production QC source is unchanged. Final QA admission instead requires all 450 observed camera frames, their recorded state, expected hold/move ranges, geographic target, fixed orientation, location/closed/resolved label evidence and final wide. Missing resolution, early zoom-out, missing final wide, wrong state, missing frame and invalid camera fail. Black-frame, decode and WebGL failures remain blocking.

The post-draw browser audit adds cameraState, cameraFrame and cameraPreset. Existing synchronous journal flush and ZIP packaging preserve these alongside timestamps, cameraPosition, cameraQuaternion and cameraFov. A failure-path ZIP round-trip test confirms that state and frame survive. Diagnostic infrastructure itself is unchanged.

## Validation scope

Native camera/projection checks cover all 450 frames and match the production collect-all preflight. Synthetic codec/audio/QC checks exercise a real 15-second 1080x1920 H264/BT709 video with 450 frames; its camera/label audits are explicit test fixtures. No physical NVIDIA scene draw, resolved-state pixels or human visual-quality PASS is claimed. The real RTX4080S test remains NOT_RUN. No gcube workload was started or modified.

This image automatically selects SINGLE_EVENT_RETURN_TO_WIDE_TEST for new 15-second QA requests. Its inherited 12-second single-event test and existing non-QA production behavior remain. Keep the existing port 8000, GPU-required mode, NVIDIA_DRIVER_CAPABILITIES=all and owner-code secret. No terminal commands or new secrets are required.

Image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v016-return-wide`

## Published validation

841 automated tests passed: 604 core (including 18 new return-wide tests), 206 independent proxy/GPU logic and 31 unchanged diagnostic tests. Failures 0, errors 0, skips 0. Actual container asset/package audit, legacy 12s media/concat/audio/QC/retry, v015 camera preflight, new 450-frame return-wide preflight, real 15s synthetic technical QC, owner login, health, 61s persistence, fail-closed GPU admission and anonymous public pull all passed. Physical NVIDIA scene pixels and human camera/resolve assessment remain NOT_RUN.

Source revision: `439c966baed771503959ff31277084914e77625d`.

Published digest: `sha256:35564d83c66257641612545d4355f09ced946ce72dfc84f6fe6404ddde0c59d4`.

[Verified build and public pull](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37744780698).
