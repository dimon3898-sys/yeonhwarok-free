# v019 close-view surface and city-light treatment

## Confirmed causes

The provided `64476.mp4` is 24 seconds, 720 frames, 1080×1920 at 30 fps. Five decoded BEFORE PNGs are preserved at frames 210, 300, 435, 630 and 690. See `ACTUAL_BASELINE_ANALYSIS.md` for exact output ROIs and source correlation.

Suez: native regional reflectance detail is present. Bright desert RGB enters the custom Earth surface's strong sun/fill radiance and the unchanged film transform's shoulder. The measured desert ROI has 99.986% luminance ≥230/255 but zero hard-clipped pixels at the recorded thresholds. This is compressed fine contrast, not proven hard RGB clipping. Ocean reflection is a separate contribution. Ordinary Three.js directional/hemisphere controls do not illuminate this custom Earth material. Clouds and atmosphere were not identified as necessary to explain the audited clear desert pixels, and are preserved.

Singapore: coarse warm clusters already exist in the actual 8192×4096 night JPEG. Projected source correlation is 0.608. The native crop contains predominantly 2×2 or ≤4×4 clusters; the evidence does not establish ordinary 8×8 JPEG DCT blocking, bad UVs, nearest sampling, or bloom as the primary cause. The native regional day LOD now resolves finer geography than the global night source. At the audited anchor, existing city red radiance is 13.09 times geographic red radiance. Existing 4K and 2K night sources are lower resolution; no higher-resolution real night data was found in the repository. The 21600×10800 TIFF is day geography, not city-light or height data.

## Minimal versioned correction

`v019` explicitly layers over the immutable `v018` material. Existing v018 files, native cropped PNGs, mask bounds, blending, filtering, textures and the full camera implementation are unchanged.

- Close sunlit surface inputs: multiply diffuse/readability by 0.60, using a bounded sun-dot-normal gate. Do not change post tone mapping or global/WIDE exposure.
- Close sunlit specular: an additional 0.50 reflection factor. Preserve ocean color, original shape/shininess, clouds and atmosphere.
- Close city emission: 0.12 of the existing contribution, geographically restricted with the **existing** native regional land mask. No new city texture, blur, sharpening, inferred or invented urban geometry. True night-side geographic fill is retained.
- At original regional LOD weight zero, all added surface arithmetic is bypassed. Both WIDE states retain the original calculation.
- Only explicit new v019 plans use the new shader and cache identity. Previously approved v018 projects retain their original source hashes and cache identity.

## Evidence and limits

The same actual inherited renderer initialization and camera evaluator execute for v018 and v019 in the Node contract fixture. Texture loading is explicitly a CPU-side source/header fixture, not WebGL rendering. All 720 positions, quaternions, FOV values and camera states are compared; the 14–16.5 second Continental Wide range has exactly zero new material weight. All original PNG fetches, samplers, filtering, color spaces and dimensions are retained. Renderer transport changes only the served page, retaining the production GPU-required Chromium path.

Analytical radiance at the sampled desert predicts a reduction from approximately 242 to 231 display luma, with approximately 64% better response to ±3% authentic source variation. At the Singapore coastal anchor, modeled city/geography red contribution drops from 13.09 to 0.649. These are **scalar predictions**, exclude actual raster/post contributions, and are not measured NVIDIA AFTER pixels or a visual-quality pass.

The assembled fragment also undergoes a CPU GLSL syntax check. Actual NVIDIA shader compilation, pixel output, before/after coastal contrast and block salience, GPU memory and timing remain NOT_RUN until a real GPU comparison.

## Resource impact

Additional texture files: 0. Additional texture disk bytes: 0. Additional GPU texture uploads: 0. Existing regional day/mask textures are reused. Six scalar uniforms and one geographically selected existing-mask sample are added at nonzero close-view weight. No added texture RAM/VRAM is required; total shader/driver memory and timing overhead are unmeasured. HIGH internal 2160×3840 and final 1080×1920/30 fps remain unchanged.

## Same-camera comparison

`PLAN_v019.json`, `camera-trajectory-720.json` and `before-after-comparison-manifest.json` identify the frozen frames and new opt-in. AFTER slots are deliberately NOT_RUN. A fresh 24-second HIGH plan on v019 is required to test the new version; rendering a saved v018 plan intentionally retains v018 behavior. MP4 and Diagnostic ZIP remain the existing download artifacts. No gcube workload was started, changed or deleted during development.
