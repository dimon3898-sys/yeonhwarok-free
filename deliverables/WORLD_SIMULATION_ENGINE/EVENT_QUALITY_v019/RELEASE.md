# Verified public v019 release

Image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v019-event-quality`

Digest: `sha256:6bccc9c2df52052da743719269316c8cd8839502b13e408efc349c4f998d7ae4`

Source revision: `32a0477f64ee3a3596ef3dbfce6a89ce40f459fb`

[Completed container build, regression and public pull](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37868378257).

Final-container regression: **938 PASS / 0 FAIL / 0 SKIP** (701 core including 30 new v019 tests, 206 independent proxy/GPU-logic tests, 31 diagnostic-server tests). Actual container checks also passed 77 required assets, both v018/v019 720-frame camera/material contracts, served-source identity, frame-grid and synthetic JPEG/encoder/concat/audio/QC/retry pipelines. Owner login, health and 61-second persistence passed before and after anonymous public pull. The actual production entrypoint remained fail-closed without physical NVIDIA and persisted 61 seconds. No gcube workload was accessed or started.

Camera, 24-second/720-frame timing, WIDE surface calculation and original native v018 texture bytes are unchanged. Old approved v018 plans retain their original version/cache identity. To use v019, create a **new 24-second HIGH plan**; don't expect a saved v018 project to change automatically.

Five actual BEFORE PNGs and exact corresponding AFTER slots are recorded. **Actual NVIDIA AFTER pixels, appearance and GPU memory/time are NOT_RUN.** Scalar predictions and CPU GLSL syntax are not GPU quality passes. Only Suez close-day surface input/reflection and coarse close-city emission are changed; no new texture or urban detail is manufactured.
