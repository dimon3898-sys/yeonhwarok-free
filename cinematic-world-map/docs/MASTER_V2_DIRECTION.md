# MASTER v2 — direction before implementation

Preserve the complete v1, its GIS, source, sound, documents and delivered files. The verified archive is `/workspace/preserved-originals/cinematic-world-map-before-v2-20261004T014301.tar.gz`; the adjacent JSON records all 83 original hashes. All v2 work uses new filenames.

The existing film actually runs SIN → ICN → NRT. The new brief explicitly requests ICN → NRT → SIN, so v2 adopts that sequence rather than describing the old film inaccurately. Airports, borders, coastline, land and projection stay geographic. Flight time and altitude remain cinematic, not real scheduling data.

## Diagnosis after viewing v1 and the reference

The reference reveals changing consequences roughly every 0.97 seconds, including new territory, arrival responses and changes of scale. Its strength is successive situations; do not reuse its military content, script, audio or design. v1 has a much cleaner globe and civil aircraft, but the large opening title remains for too long and a single plane dominates most of the middle. Smooth motion alone does not create narrative events. The warm urban layer is too restrained and the camera's rhythm too similar across legs.

## Focal sequence

| Time | Dominant event / viewer expectation |
|---|---|
| 0.00 | Already-moving East Asian globe, rapid orbital push; no black or logo introduction |
| 0.40 | Seoul pulse, warm surrounding lights wake; origin becomes clear |
| 1.15 | First curved route begins to draw |
| 1.80 | Dimensional aircraft appears and tracking starts |
| 2.75 | Eastern destination hinted by a distant beacon |
| 4.40 | Faster flight and first distance reveal |
| 5.90 | Tokyo's name and glow emerge |
| 7.10 | Arrival ripple and deliberate camera settle |
| 8.40 | Pull back; three subdued neighboring routes briefly activate |
| 10.15 | New southern leg, Singapore revealed as the next destination |
| 12.20 | Direction and scale shift; longer curved trajectory unfolds |
| 14.25 | Low orbital view, haze pass, curved horizon: visual climax |
| 16.30 | Singapore lights wake and destination becomes the focal point |
| 17.20 | Arrival response, resolve the journey |
| 18.35 | Accelerating overview pull-out |
| 19.30 | Full route/network resolves, final low impact |

Authored event intervals: mean 1.287 s, maximum 2.05 s. Continuous motion exists between these events; secondary network lines remain markedly dimmer than the hero route. Distance, place and narrative text reveal in stages, never all together. Aesthetic lighting/cloud haze is a cinematic overlay, not a claim about present weather or city power use.

## Implementation and verification order

1. Reuse the v1 classes as a preserved base, with separate v2 subclasses and scene entry.
2. Verify still compositions at opening, tracking, network expansion, low orbital shot and finale.
3. Compose and master original procedural sound against the authored cue timeline.
4. Render 5 s, inspect actual encoded frames and mobile-scale compositions, fix problems.
5. Render/inspect 10 s; reuse approved frames only when the source affecting that exact interval is unchanged. Record any later-interval-only modification explicitly.
6. Render the remaining sequence and inspect all 600 frames, actual browser playback, every half-second contact frame and representative native/mobile frames.
7. Compare reference/v1/v2. Aesthetic judgment and anticipated retention are not empirical viewer-test results. Sound waveform/mastering verification is distinguishable from direct listening, which this environment may not provide.

Internal render stays 2160×3840. 30 fps, adaptive temporal samples for fast camera passages, crisp typography after motion blur, Lanczos to 1080×1920, H.264 MP4 and synchronized AAC stereo. Check asset loads, camera/route continuity, black/frozen/duplicate frames, text bounds and icon screen position. Keep the existing cinematic insertion hook, without building I2V/TTS/60-second/UI automation.
