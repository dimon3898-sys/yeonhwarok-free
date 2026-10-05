# Pacing addendum — current v003 recovery

The previous v002 comparison is preserved. This addendum describes the actual v003 plan and checks its retained inputs; it does not render or certify a final MP4.

Only S005 changed: camera travel and zoom each 1.7→1.4 seconds, with authored settle reserve (`dead_time_removed`) 0.3→0.6 seconds. Entry/exit state and all other S005 fields are identical. The Scene still lasts 2 seconds; the full plan still lasts 12 seconds.

| Scene | NORMAL start / duration | v003 start / duration | Camera NORMAL→v003 | Zoom NORMAL→v003 | Focus NORMAL→v003 |
| --- | --- | --- | --- | --- | --- |
| S001 | 0s / 3s | 0s / 2.5s | 2.7→1.8s | 2.6→1.66667s | 0.3→0.18s |
| S002 | 3s / 3s | 2.5s / 2.5s | 2.7→1.8s | 2.6→1.66667s | 0.3→0.18s |
| S003 | 6s / 3s | 5s / 2.5s | 2.7→1.8s | 2.6→1.66667s | 0.3→0.18s |
| S004 | 9s / 3s | 7.5s / 2.5s | 2.7→2.13333s | 2.6→2.13333s | 0.3→0.18s |
| S005 | 12s / 3s | 10s / 2s | 2.7→1.4s | 2.6→1.4s | 0.3→0.18s |

The structural 15→12 second change remains 3+3+3+3+3→2.5+2.5+2.5+2.5+2. Authored camera intervals now total 13.5→8.933333 seconds. These are animation intervals, not wall-clock rendering speed measurements. The same shortened script and TTS playback 1.0× are retained; no whole-video acceleration is requested.

S001–S004 individual Scene JSON files are byte-identical to v002. Their four actual reused MP4 byte hashes match the completed v002 films and their cache receipts. S005 alone is the changed render input. All 17 critical sources match the r03 recovery lock and the previous r02 source set.

The retained native recovery record reports 2.572802→2.485022 degrees per frame against the unchanged 2.5 gate. The addendum attributes those measurements to that record; it does not independently rerender or declare the live final MP4 passed.

Current v003 numeric plan, semantic visibility, Retention, Event Diversity and Dead Time gates: **PASS**. Event definitions and timings are unchanged from v002.

Meaningful events: 12; types: 11; average gap: 1.0091s; maximum gap: 2.2667s; first 3s: 4 events; maximum same-kind run: 1. Camera movement is not counted as an event.

File SHA: `e6ac8af4cc0c82f3afefe33c7e3ac06380c3c56ed91bb9e5fa02268119698c73`. Canonical approval plan hash: `b6d60e38bf3370e3e38f6ce3e748d09da962186a8a08dece0cdec577336cc734`. Both recompute correctly and intentionally cover different representations.

No program source, older evidence, input plan, render, cache or existing output was edited by this task. No test suite or 75-second render was started. Final media playback/QC and actual render times remain the responsibility of the separate live job.
