# Production Default v1

Approved PREMIUM FLAT v004 is the normal geographic presentation. MASTER V3 Earth remains available for scale reveals, peaks and regions where a registered native-resolution terrain tile is unavailable. Existing saved plans, versions, render caches, checkpoints and master outputs are preserved; they are not automatically rewritten.

The policy is **INFORMATION FIRST. CINEMATIC WHEN IT MATTERS.** Flat scenes retain real GIS outlines, native terrain texture, translucent country tint, v004 aircraft/route styling, auto focus and next-event anticipation. Three restrained country hues are combined with borders, labels and focus; color alone does not convey meaning. A new production adapter adds modest adaptive route emphasis and direction cues while leaving the approved renderer source unchanged.

## Default and activation

`PRODUCTION_DEFAULT` uses:

| Setting | Default |
|---|---|
| Visual | `PREMIUM_FLAT_v004` when registered terrain covers required geography |
| Pace | `FAST` |
| Text | Short geographic labels and measured information |
| SFX | Timestamped categories with deterministic variants |
| Earth | Peaks/global reveals; readable global fallback where needed |
| Retention / diversity / dead-time gates | Enabled |

The default is promoted only after a real 10–15 second integration MP4 passes full-frame QC, mobile browser playback, semantic event/retention/dead-time checks and sound synchronization/repetition/ducking checks. `data/production_default_promotion.json` stores relative report/video paths, their hashes and a manifest of the critical production source files. A missing, modified or failed certificate deactivates the promoted default. Promotion checks actual H.264 1080×1920 / ≥30fps media metadata, rather than trusting a UI completion label.

New natural-language requests select the promoted policy automatically. Before promotion, the candidate must be explicitly requested with `production_preset: PRODUCTION_DEFAULT_CANDIDATE`. `production_preset: LEGACY` retains the prior planning grammar. A saved unmarked Scene JSON remains a legacy plan regardless of the current default.

## Scene contract

Optional fields preserve backwards compatibility: `production_defaults.version: v1`, `visual_mode`, `pace`, `text_density`, `sfx_intensity`, `motion_timing`, `focus_target` and `text_events`. An approved Flat scene explicitly has `render_mode: FLAT_MAP_PREMIUM` and `visual_polish: {version: v004, entity_separation: v1}`. Earth continues to use `MASTER_V3_EARTH` with the existing v004 readability adapter.

Text events are attached to verified geographic coordinates. Distance/route events can reference a real route for a moving spatial anchor. Country labels stay near the country, city labels near their city and numbers near the route. A short map-attached question is actually drawn at the opening even with TTS off. Arrival/status text avoids duplicating active city labels. Large generated explanation banners are disabled. A title requires explicit `large_title_requested: true`; it is never inferred from a generic style request.

Sound events retain their existing `visual_event_id` and gain optional `sfx_category`, `sfx_variant` and `sfx_intensity`. Production visual onsets are authored on the 30fps frame grid before sound binding. Narration playback remains 1.0×. SFX and BGM are mixed around narration, not the reverse.

## Geographic coverage and global compatibility

Registered native Natural Earth terrain currently covers the validated East Asia region. The planner checks geographic bounds against required locations instead of assigning the same Asia raster to arbitrary topics. A region without a matching native tile uses the existing global V3 Earth renderer with `GEOGRAPHY_READABILITY`; metadata records that fallback. The time ratios are a guide, never an excuse to substitute incorrect geography. Wider global native terrain coverage and pixel-level validation of those regions remain future work.

The existing natural-language aviation, shipping and hypothetical-geography contracts, sourced GIS coordinates and FACT / ASSUMPTION / SIMULATION distinctions remain. The short integration example extends the same East Asia civil network to a catalogued Shanghai context node at the final reveal. Shanghai's coordinates are FACT; the new link is explicitly SIMULATION under existing assumptions. It does not claim observed flight traffic.

## Partial rendering and approval

Production edits create new Scene JSON and versions. Changed camera/route/text/style timing invalidates only affected Scene cache keys. Unchanged legacy master and Scene files are retained; a requested visual change does not falsely claim a cache hit. `entry_state` and `exit_state` remain continuous. The normal planning/approval/rendering workflow, independent Scene rendering, audio/subtitle switches, QC and mobile downloads continue to apply.

This integration task is bounded to one short test. It does not start a 75-second render, approve a new topic or regenerate MASTER V3.

## Delivered and promoted evidence

The actual 12-second HIGH test passed full 360-frame decode/native-render audits, retention/diversity/dead-time gates and 375px mobile browser playback with zero dropped or corrupted frames. The main MP4, muted MP4 and SFX-OFF comparison retain the same H.264 picture stream. The quality certificate now activates this default; it does not bypass approval of future Scene Plans.

- [Download integration MP4](../../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/production_default_integration_12s.mp4)
- [QC report](../../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/QC_REPORT.md)
- [Immutable activation certificate](../../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/INTEGRATION_QC.json)
- [Benchmark](../../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/BENCHMARK.md)

The test contains normal-speed offline Korean TTS, BGM and SFX; subtitles are OFF. Actual browser playback/download and encoded sound measurements are verified. Physical handset playback, human listening and paid/cloud hosting are not claimed. Native Flat coverage remains the registered East Asia tile; other regions use readable preserved V3 Earth.

전체 회귀 검사 **255개 PASS**(293.622초), 핵심 소스·승격 인증서·MP4 전후 해시 동일. [실제 검사 결과](../../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/REGRESSION_REPORT.json).
