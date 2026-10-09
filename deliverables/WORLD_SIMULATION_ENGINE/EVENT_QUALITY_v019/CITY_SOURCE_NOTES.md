# v019 City Source Audit

Read-only existing repository assets; no downloads or GPU execution.

- Only three night/light sources: selected 8192×4096 JPEG, trial 4096×2048 JPEG, legacy 2048×1024 PNG. No higher-resolution night source exists in named assets, image header inventory, original MASTER ZIP or preserved source manifests.
- Selected 8K source SHA256 `9894e83a585a22c1c425e7ca4f987a9ba625bf08ecee45d3c9dcacae3c2ad5f7` matches the pinned Solar System Scope mirror registry. No build/runtime resize was found; v018 validates source dimensions against MAX_TEXTURE_SIZE and protects the exact source SHA.
- The native 8K asset already contains isolated warm square clusters. Singapore-area 159×251 source crop, shader-equivalent linear city > 0.05: 125 components, median 2×2 texels, 103 ≤ 4×4. 123 of 125 do not have 8×8 dimensions. A normal bilinear preview still shows the clusters. The primary cause is source pattern plus close magnification; the evidence does not identify a new FFmpeg/JPEG DCT tile grid.
- Source JPEG is 4:4:4, with Photoshop 2014 processed-file metadata and an sRGB ICC profile. Repository evidence cannot establish the exact satellite mosaic or subpixel generation history; do not call the source synthetic, AI or random.
- Existing 21600×10800 TIFF is daytime land-cover/shaded relief, not night-light data. v018 regional daytime native density is 2.637× the global night source. Terrain improvement does not create city-light detail.
- Existing city gain, focus, exposure and bloom can amplify the existing pattern. Mipmap, linear filtering and unchanged geographic UV have not been identified as the primary cause. Actual 64476 frame-to-source comparison comes from the frame-analysis agent.
- The available fix without new data is to retain real daytime/relief LOD and WIDE night appearance, while bounding close emissive city contribution to a subordinate level. No blur, fake lights or downloads. Actual NVIDIA AFTER frame quality remains NOT_RUN.
