# SINGLE_EVENT_CAMERA_TEST v015

This isolated QA preset uses one Suez scene and one major camera movement. It is not a replacement for saved Reference Master or FAST_PLUS plans. New 12-second QA requests in this test image select this preset automatically; old saved plans keep their authored preset.

## Fixed timeline (30 fps, end exclusive)

| State | Frames | Seconds |
|---|---:|---:|
| WIDE | 0–60 | 0–2 |
| EVENT_LOCATION | 60–90 | 2–3 |
| ZOOM_IN | 90–150 | 3–5 |
| SETTLE | 150–180 | 5–6 |
| EVENT_REVEAL | 180–240 | 6–8 |
| EVENT_HOLD | 240–360 | 8–12 |

360 frames, gap 0, overlap 0. No next destination, orbit, route chase, pullback, or automatic multi-event director. Camera position, quaternion and FOV are fixed from frame 150 to the end.

## Actual camera equations

Geographic target: Suez Canal, longitude 32.382202°, latitude 30.318359°. Earth radius is 1 render unit. Wide center-distance 3.5R / surface altitude 2.5R / vertical FOV 64°. Close center-distance 1.2R / surface altitude 0.2R / vertical FOV 48°. Only 3–5 seconds interpolate position and FOV using a smooth acceleration/deceleration curve. Target and orientation remain fixed.

Native Three.js ray projection estimates Earth viewport coverage at 31.7% wide and 100% close. This is geometric coverage, not a GPU pixel or visual-quality measurement. The production collect-all preflight uses the same camera installer and checks all 360 actual frame poses. Real NVIDIA image rendering was not executed.

## Scope and preservation

The existing production Earth renderer supplies textures, lighting, labels, blockade effect and audio. No visual design, GPU/proxy/runtime, frame-audit predicate, encoding, diagnostic, or secret policy is relaxed. The ordinary multi-event narrative retention policy is inapplicable to an explicitly isolated single-event test; only that test uses its strict six-state camera admission contract. Original schema, GIS, asset, projection, frame, GPU and security checks remain. Invalid extra states and foreign camera targets are rejected.

Existing renderer assets, MASTER versions and saved projects are preserved. No gcube workload was started.

## Deployment

Image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v015-single-event-camera`

Keep the existing RTX4080 SUPER runtime, port 8000, owner-code secret, NVIDIA_DRIVER_CAPABILITIES=all and GPU-required setting. Do not render 75/80 seconds with this QA test. This image is for one 12-second Suez camera test. Real visual confirmation remains necessary before declaring its camera framing successful.

## Final verified release

823 automated regressions passed: 586 core (including 10 new camera tests), 206 independent proxy/GPU-logic tests and 31 diagnostic tests. Failures 0, errors 0, skips 0. Container asset audit, synthetic JPEG/encoder/concat/audio/QC, old frame-grid before/after parity, all-frame single-camera preflight, owner login, health and 61-second persistence passed. Anonymous registry pull and pulled-container login/persistence passed. Physical NVIDIA rendering and real visual framing remain NOT_RUN.

Source revision: `14ff518ef474dc92c393594138ec828290324d68`.

Published digest: `sha256:c8365f4784bee20d82009607e77eb5871abe1dce7cb3698b8fb4fe0c86333f15`.

[Verified workflow](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37738538033).
