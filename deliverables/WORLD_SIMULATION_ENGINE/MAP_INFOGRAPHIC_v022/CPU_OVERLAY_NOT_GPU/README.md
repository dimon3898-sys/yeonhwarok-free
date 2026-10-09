# Actual CPU overlay snapshots — NOT GPU output

These 10 PNGs were captured from actual Chromium Canvas2D pixels with GPU and GPU compositing disabled. They exercise the versioned v022 geometry projection and shared text layout helpers. They are **not NVIDIA/RTX4080S scene renders**, do not contain the production Earth shader, and do not establish final video quality or GPU performance.

`COUNTRY_EGY.png` and `COUNTRY_SGP.png` use the actual pinned registry country geometry. Files starting with `TEST_` use explicitly named artificial topology or typography test inputs; those inputs are never added to the authored Story/Scene. The font snapshots load the real licensed Noto Korean 400 and 700 faces. Holes, separated islands, antimeridian/horizon clipping and four-pixel line width are checked using actual pixel data.

Reproduce from `world-simulation-shorts-engine`:

```sh
node tools/test_infographic_v022.mjs --canvas-snapshots /tmp/v022-cpu-overlay
```

`metrics.json` contains 16 passed checks, Chromium flags/version, source hashes, real font ink/layout measurements, and every PNG SHA256. GPU status is `NOT_RUN`. The recording/native renderer checks and the actual CPU Canvas2D pixel checks are separate evidence.
