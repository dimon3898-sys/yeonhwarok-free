# Scene-local pace system

Pace and render quality are separate controls. `PACE_FAST`, `PACE_NORMAL` and `PACE_CINEMATIC` aliases map to `FAST`, `NORMAL` and `CINEMATIC`; render quality still selects `FAST`, `HIGH` or `CINEMA` resolution/cost settings independently.

| Motion property | FAST | NORMAL | CINEMATIC |
|---|---:|---:|---:|
| Camera travel fraction of Scene | .72 | .90 | 1.00 |
| Zoom travel fraction | .66 | .86 | 1.00 |
| Route travel factor | 1.20 | 1.00 | .90 |
| Focus transition | .18s | .30s | .42s |
| Map/Earth transition | .38s | .65s | .90s |
| Next-event lead | .35s | .65s | .85s |
| Minimum authored peak recognition reserve | .8s | 1.0s | 1.3s |

Peak/payoff shots use a smaller travel acceleration and at least an .85 camera/zoom fraction, so a result has time to register. Tracking, anticipation, geometry and shader clocks retain actual Scene time. FAST changes real camera interpolation intervals and route/entity end windows; it does not apply an FFmpeg `setpts` speed filter, globally resample the video or accelerate TTS. Endpoint progress and inter-Scene state remain continuous. Persistent entity display lifetime is preserved through the cut even when its route reaches the authored endpoint earlier.

`motion_timing.camera_speed_reference` records the speed at timing authoring. A later camera-speed edit scales the actual travel/zoom interval by reference/current speed while leaving route, entity, shader and narration clocks unchanged.

`apply_scene_pace()` preserves the user's requested Scene duration and script. A faster approach can settle while a country, route, number or result changes. That settle is not evidence of a new event by itself. A meaningless gap still blocks approval/rendering.

For the bounded integration comparison, `retime_scene_plan()` copies the approved five-Scene source and changes 3+3+3+3+3 seconds into 2.5+2.5+2.5+2.5+2 seconds. All local event/route/entity/effect/highlight/focus/label/audio clocks are scaled together and boundary timeline snapshots are rebuilt. The shorter narration must still fit: over-budget narration is rejected with `NARRATION_TOO_LONG`, never sped up. Shorter sample scripts are an explicit planning change. Normal natural-language requests retain their selected total length.

## Dead Time Gate

Only semantic events count. The gate checks:

- A meaningful-event gap greater than 3 seconds, including camera-only/unchanged periods.
- Long unbroken entity travel without a causal change.
- Excessive transitions relative to the selected pace.
- A peak/payoff with less than .8 seconds of recognition time.
- An excessive idle tail after a peak.
- Any pace-induced narration playback rate other than 1.0.

Scene-local motion trims are recorded in `metadata.production_pace_changes`. Story gaps need a genuine plan correction or shorter approved Scene; they are not concealed by adding more zooms. The existing Retention Gate independently enforces 1–3 second average event density, opening motion/hint, causal order, event diversity and delayed final payoff.

## Frame grid

Visual event onsets are snapped to the first 30fps frame at or after their authored time, with a rounding tolerance for six-decimal frame timestamps. Sounds then bind to those authored frames. `text_events` and next-event preview references are refreshed after timing edits; a changed route clock refreshes its actual distance metric. Final decoded frames and native renderer receipts remain required to confirm executed timing.

## Reuse

`engine/pace.py` contains `PACE_PROFILES`, `normalize_pace`, `apply_scene_pace`, `retime_scene_plan` and `analyze_dead_time`. `RetentionAnalyzer.analyze_dead_time()` exposes the optional production gate. Unmarked historical plans keep their prior gate and cache semantics. No old master or 75-second video is rewritten by selecting a new pace for a new project.

## Measured integration evidence

The delivered 12-second test uses four 2.5-second Flat Scenes and a 2-second V3 Earth reveal, compared with the source's five 3-second Scenes. The duration change is 15→12 seconds; no completed video or narration was sped up. The FINAL Earth handoff overrides only its camera/zoom travel interval from 1.7 to 1.4 seconds after actual rig measurement: the earlier settle lowers its maximum angular step from 2.572802° to 2.485022° per frame, below the unchanged 2.5° gate. Its camera endpoints, geographic coordinates and boundary states remain identical. The recognition reserve and new final connection remain visible. This fixed short-shot exception is not a global peak-timing rule.

Completed Flat Scenes were reused during that repair; only the failed Earth Scene was rendered. The SFX-OFF comparison then reused all five Scenes and retained an identical H.264 picture stream. See [integration QC](INTEGRATION_QC.json), [cache evidence](CACHE_COMPARISON.json) and [measured benchmark](BENCHMARK.md). This is a structural timing comparison, not a controlled NORMAL-versus-FAST rendering-speed benchmark.
