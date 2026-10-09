# v019 comparison baseline: actual 64476

These BEFORE frames come from the user-confirmed RTX4080 SUPER output **64476.mp4**, uploaded as `final (7).mp4`: 24.000 seconds, 720 frames, 30 fps, 1080×1920.

Input SHA256: `68f74bf756d918fc7f22d7fbc31665f4322701699092fb2b35c4e87b7ec12ca1`.

| Fixed frame | Time | What the actual BEFORE shows |
|---|---:|---|
| [Suez F210](before/suez-event-view-F210.png) | 7.0s | Native regional relief exists, but the desert has a very narrow bright tonal range. Broad Mediterranean reflection remains. |
| [Suez F300](before/suez-event-view-F300.png) | 10.0s | The same appearance persists in the camera hold. |
| [CONTINENT_WIDE F435](before/continent-wide-F435.png) | 14.5s | Readable continental geography; protected WIDE baseline. |
| [Singapore F630](before/singapore-event-view-F630.png) | 21.0s | Regional terrain/coast detail is present, while coarse gold city-light clusters dominate locally. |
| [Singapore F690](before/singapore-event-view-F690.png) | 23.0s | The same stationary gold blocks remain during the hold. |

## Confirmed output findings

- Suez desert ROI `[20,1180,240,1510]`: mean display luma **235.29/255**, p10–p90 contrast **4.65 codes**, approximately **99.99% ≥230**. In the selected Suez surface ROIs, **all RGB ≥245, any RGB ≥250 and luma ≥250 are each 0%**. The confirmed issue is washed-out highlight-shoulder tonal compression, not proven hard white clipping.
- Pure Mediterranean glare ROI: mean **151.88**, compared with **107.80** in surrounding sea. This is a local reflection contribution.
- Large-scale Suez land/sea separation remains strong: median difference **123.48 codes** in the recorded color-split ROI. The finer land relief is the weak part; the coastline has not completely disappeared.
- Singapore F630: **54** measured gold components, median bbox **20×19 px**, largest bbox **100×101 px**. F690 preserves that largest bbox. The native 8K Night texture contains corresponding sparse, square clusters.
- Existing source audit found selected 8K, trial 4K and legacy 2K night images, with **no higher-resolution real city-light source**. The 21600×10800 TIFF is daytime land-cover/shaded relief, not nighttime light data.

## Comparison contract

AFTER NVIDIA frames are **NOT_RUN**. This folder contains no CPU-rendered or synthetic AFTER image. The actual next GPU output must be compared at the same five frame indices, with the unchanged 720-frame camera positions, quaternion, target, FOV and timing. WIDE must preserve its v018 appearance.

`before-after-comparison-manifest.json` records the BEFORE PNG hashes and exact AFTER capture requirements. Actual GPU contrast, final appearance, VRAM and rendering time must remain unverified until those frames exist.

## Evidence and limits

- `ACTUAL_BASELINE_ANALYSIS.md`: direct observations and attribution limits.
- `selected-roi-metrics.json`: full-resolution native-frame ROI values and explicit coordinates.
- `all-frame-metrics.json`: all 720 frames decoded; global metrics use a documented 270×480 area downsample.
- `city-source-audit.json`, `city-source-inventory.json`, `CITY_SOURCE_NOTES.md`: existing repository source inventory and integrity.
- `night-source-pattern-correlation.json`: analysis-only source projection; not a GPU AFTER frame or a recovered GPU camera log.

Values are Rec.709-weighted 8-bit **display RGB code**, not HDR nits. Thresholds cannot reveal pre-tone-mapping GPU values. Local contrast varies with geography, and numerical improvement alone is not a visual PASS.

No complete MP4, absolute workspace path, environment dump, authentication secret, gcube operation or new external data is included in these artifacts.
