# Actual 12s FAST plan vs 15s NORMAL authored timing

UTC evidence capture: 2026-10-05T21:38:57.053909+00:00

Read-only comparison of the actual approved v002 input and r03 NORMAL plan. No film was rendered, retimed or decoded by this task. This is not a render performance benchmark.

| Scene | NORMAL start / duration | FAST start / duration | Camera travel NORMAL→FAST | Zoom NORMAL→FAST | Focus transition NORMAL→FAST |
| --- | --- | --- | --- | --- | --- |
| S001 | 0s / 3s | 0s / 2.5s | 2.7→1.8s | 2.6→1.66667s | 0.3→0.18s |
| S002 | 3s / 3s | 2.5s / 2.5s | 2.7→1.8s | 2.6→1.66667s | 0.3→0.18s |
| S003 | 6s / 3s | 5s / 2.5s | 2.7→1.8s | 2.6→1.66667s | 0.3→0.18s |
| S004 | 9s / 3s | 7.5s / 2.5s | 2.7→2.13333s | 2.6→2.13333s | 0.3→0.18s |
| S005 | 12s / 3s | 10s / 2s | 2.7→1.7s | 2.6→1.7s | 0.3→0.18s |

The five Scene windows change from 3+3+3+3+3 to 2.5+2.5+2.5+2.5+2 seconds: 15→12 seconds, a 20% structural duration reduction. Camera path intervals total 13.5→9.233333 seconds; these authored travel intervals are not render wall-time measurements. Peak/result shots retain slower travel and reserve at least 0.8 seconds in their authored reward windows.

Configured transition timing changes 0.65→0.38 seconds and next-event lead changes 0.65→0.35 seconds. Actual mixed-mode transitions and focus windows are listed in the JSON; a configured interval alone does not mean every cut uses that effect. Persistent entity display windows remain independent of the earlier-completed route.

| Moving route / Scene | NORMAL travel window | FAST travel window | Progress span |
| --- | --- | --- | --- |
| R_SEOUL_TOKYO / S001 | 0.8–3s (2.2s) | 0.666667–2.2s (1.53333s) | 0→0.32 |
| R_SEOUL_TOKYO / S002 | 0–3s (3s) | 0–2.1s (2.1s) | 0.32→1 |
| R_TOKYO_TAIPEI / S004 | 1.7–3s (1.3s) | 1.43333–2.43333s (1s) | 0→0.9 |
| R_SEOUL_TAIPEI / S004 | 0.8–3s (2.2s) | 0.666667–2.4s (1.73333s) | 0→0.9 |
| R_TOKYO_TAIPEI / S005 | 0–0.866667s (0.866667s) | 0–0.533333s (0.533333s) | 0.9→1 |
| R_SEOUL_TAIPEI / S005 | 0–0.966667s (0.966667s) | 0–0.6s (0.6s) | 0.9→1 |
| P_FINAL_SHANGHAI / S005 | 1.66667–2.9s (1.23333s) | 1.2–1.9s (0.7s) | 0→1 |

Held/preview-only paths are excluded from this travel table. All corresponding GIS route points and progress endpoints are identical between the two inputs.

| Scene | Preserved v004 source script | Shared NORMAL / FAST shortened script |
| --- | --- | --- |
| S001 | 다음 목적지가 바뀐다면? | 목적지가 바뀐다면? |
| S002 | 첫 연결이 도쿄로 향합니다. | 도쿄로 향합니다. |
| S003 | 다음 목적지가 바뀐다고 가정합니다. | 다음은 타이베이. |
| S004 | 새 민간 항로가 연결됩니다. | 새 항로가 열립니다. |
| S005 | 세 도시의 연결망이 보입니다. | 연결. |

Narration is shortened before synthesis. NORMAL and FAST already use the same short script, and every Scene keeps authored TTS playback 1.0×; no whole-video acceleration is requested.

Current 12s plan validation: **PASS**. Semantic/native preflight, Retention, Event Diversity and Dead Time checks pass.

Meaningful events: 12; distinct types: 11; average interval: 1.0091s; maximum gap: 2.2667s; first 3s: 4 events; longest same-kind run: 1; peaks: 1. The final payoff is counted separately from the mid-peak. Camera motion is not counted as a meaningful event.

The saved-file SHA is `fe5acff84191dd6956556508677f6efcfbca8c769c92e6909a9b601b52bedd58`. The canonical approval plan hash is `786a31dc9cb2686b904a358aa1e3dc49868d772f96cea89d31f256810cbf455c`; the different values are expected because they hash different representations. All three input files and the 17 critical sources match their original hashes after validation.

Final MP4 decoding, mobile playback, sound QC and wall-clock rendering measurements belong to the separate live job. The NORMAL 15s plan is not a newly rendered comparison film. The actual v002 also contains later label-window polish, so no controlled pixel-equivalence or viewer-retention improvement is claimed here.
