# Actual 64476 baseline: v019 event quality evidence

The input is the user-confirmed RTX4080 SUPER **64476.mp4**, uploaded as `final (7).mp4`. It is not the reference video and not the previous 64458 output.

- SHA256: `68f74bf756d918fc7f22d7fbc31665f4322701699092fb2b35c4e87b7ec12ca1`
- 24.000 seconds, 30/1 fps, 720 frames, 1080×1920, H.264 video and AAC audio.
- All 720 frames were decoded. Per-frame global metrics use an explicitly recorded 270×480 area downsample. The five required BEFORE frames and their ROI metrics use the full 1080×1920 decoded pixels.
- No GPU, gcube Workload or external source download was used.

## Direct frame observations

| Interval / frame | Actual observation | Quantitative evidence | What this establishes |
|---|---|---|---|
| Suez 5–12s; F210 / 7s and F300 / 10s | The v018 regional terrain and Nile/coast detail exist, but broad desert surfaces remain pale and the Mediterranean has a broad circular reflection. Both held frames show the same problem. | Western-desert ROI `[20,1180,240,1510]`: mean luma 235.29/255; p10 233.14, p90 237.78, contrast 4.65 codes. About 99.99% of that ROI is ≥230 luma. Sinai interior `[780,1120,900,1260]`: mean 230.33, contrast 13.29. | A compressed bright tonal range and prominent ocean reflection are directly observed. Regional texture detail was not lost by camera motion. |
| Suez sea at F210 | The glare is locally much brighter than surrounding sea. | Glare ROI `[0,300,350,700]` mean luma 151.88 versus unaffected sea `[440,250,700,550]` mean 107.80. | Reflection is a local contribution, not proof that the whole output needs darkening. |
| Suez F210/F300 white thresholds | Measured land, coast and sea ROIs have no decoded white saturation at the selected thresholds. | `all RGB ≥245 = 0%`; `luma ≥250 = 0%`; `any RGB ≥250 = 0%` in measured Suez ROIs. | Do **not** report proven hard highlight clipping. These pixels are washed out / tonally compressed below white. Shader trace is needed to apportion exposure, tone mapping, texture and other lighting contributions. |
| Suez F210 coast | Large-scale land/sea separation remains strong while finer land relief is weak. | Observed color split in `[430,1130,710,1500]`: land median 234.14, sea median 110.65, difference 123.48 codes. This is an RGB proxy, not GIS coastline segmentation. | A global coast-contrast failure is not established. The fix should improve surface detail without claiming the coast vanished or adding a coastline effect. |
| CONTINENT_WIDE 14–16.5s; F435 / 14.5s | Continental geography, terrain, cloud and day/night relationship remain readable. | Continental ROI `[300,520,850,1050]`: mean 171.20, p90−p10 126.19. | This interval is the protected WIDE baseline. Event-view fixes must have zero weight here. |
| Singapore 19.5–24s; F630 / 21s and F690 / 23s | Regional terrain and the coast are visibly sharper than the prior 64458 output, but rectangular gold city-light blobs remain and attract attention. A small set of isolated dots also appears offshore. | F630 gold-mask components: 54, median bbox 20×19 pixels. Largest gold cluster bbox `[480,881,580,982]`, 100×101 pixels. At F690 the same bbox remains; 55 components, median 20×18. | The pattern is stationary in the held map, not caused by camera motion. It must be checked against the native Night texture before changing filtering or inventing city detail. |
| Singapore source correspondence | Gold-cluster positions correspond to the existing 8K night image's sparse rectangular clusters, including the major Singapore cluster and the offshore dots. | Reused CPU analysis-only inverse projection from the unchanged v017 code camera. Gold-excess correlation with F630, label strip excluded: 0.608. Native source inspection independently shows the sparse few-texel blocks. | The low-resolution source pattern is a confirmed contributor. Correlation alone does not isolate cityGain, shader blend or each light contribution. The CPU projection is not an AFTER render. |

The frame-to-frame mean pixel deltas are small during held views (Suez approximately 0.031 code, Singapore approximately 0.036 code after downsampling), consistent with static views plus noise/cloud/text/compression. This is not a substitute for camera position/quaternion/FOV validation.

## Fixed comparison frames

The comparison contract is in `before-after-comparison-manifest.json`:

- Suez: F210 at 7.0s and F300 at 10.0s.
- CONTINENT_WIDE: F435 at 14.5s.
- Singapore: F630 at 21.0s and F690 at 23.0s.

BEFORE PNGs are actual decoded GPU output. AFTER NVIDIA frames are **NOT_RUN**. Compare those same frame indices, timestamps and unchanged camera values after the user authorizes the next GPU test. Do not label analytic source crops or CPU shader samples as AFTER images.

## Metric limits

- Luma is Rec.709-weighted **8-bit display RGB code**, not HDR nits or linear shader irradiance.
- Threshold fractions are decoded-white proxies. They do not expose pre-tone-mapping HDR values.
- ROI local contrast is geography-dependent and is not a universal visual quality score.
- Gold component thresholds describe observed screen footprint. They do not count buildings or estimate new city data.
- No renderer intermediate buffer, actual GPU texture telemetry or captured camera JSON was supplied with this MP4.
- A later AFTER video must be measured with the same ROI definitions; numerical improvement alone is not a visual PASS.
