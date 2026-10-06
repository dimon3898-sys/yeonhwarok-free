# Reference-driven rhythm extension v1

This extension changes timing and sound over the approved Premium Flat v004 / MASTER V3 graphics. Existing saved plans, materials, textures, renderer modules, outputs and the previous Production certificate remain preserved. A separate short-test certificate activates the new recommended default; changing a certified source deactivates that promotion.

`FAST_PLUS` is a Pace choice, independent of the FAST/HIGH/CINEMA render-quality choice. FAST, NORMAL and CINEMATIC remain available. TTS and subtitles remain optional; their recommended channel default is OFF. BGM and SFX remain independently selectable and external narration remains supported.

## Real clocks and small beats

`rhythm_micro_beats` describes real scene-local REVEAL, FOCUS, MOVE, RESPONSE, IMPACT, NEXT_CUE, BUILD, PEAK, RELEASE and MICRO_PAUSE intervals. These records drive the music curve and reporting. They never create extra meaningful story events or repair a failed Retention/Event Diversity Gate by themselves.

`rhythm_visual` separately defines camera, zoom and moving-route speed knots. The native adapter integrates smoothly interpolated nonnegative speeds and normalizes the result to exact 0/1 endpoints. Aircraft tangent, bank, trail and route head reuse the same route phase. Shader time, spawn, visibility, action, label, country highlight, focus, anticipation and geographic handoff use real scene time. The endpoint state and TTS playback rate remain unchanged. Camera translation can briefly pause while zoom/tracking/visual effects continue.

The sampled polish plan retains its 12-second duration. Travel intervals are edited locally; it does not use a whole-video `setpts` or an audio tempo filter. Important status/reveal shots may deliberately settle longer than ordinary explanatory travel. Source-backed remaining-distance labels are recomputed from the actual ramped route progress.

## Event sound and music

The additional original CC0 SFX catalog has 33 categories, three deterministic variants per category and five intensities: SUBTLE, LOW, MEDIUM, HIGH, PEAK. The v1 catalog is untouched. Category/intensity/history choose a compatible variant; recent and immediately repeated variants are avoided and explicit user overrides are disclosed. Every generated WAV has content/source hashes and author/license metadata.

Canonical Scene JSON sounds retain their visual-event timestamps. The mixer snaps to the authored frame, then uses the explicit first-positive-visual-frame offset, then applies pre/post offsets. Important events use at most three layers; ordinary cues use one. Generated layers, their actual sample insertion time, onset measurements and source hashes are recorded independently of the canonical plan.

Music follows real Micro Beats, builds, short breaths, peaks and releases. Important primary SFX gently reduce only the BGM, then it returns smoothly. Existing measured narration priority ducking remains independent. Mastering retains −18 LUFS / −2.5 dBTP targets. Actual post-ducking SFX, BGM and narration stems are saved before integrated mastering; they are measurable mix contributions rather than claims of direct listening.

## Cache and partial rendering

Sound settings, music energy and Micro Beat metadata do not shade pixels and are excluded from the production visual-cache key. Actual motion knots, text timing, route timing, assets and native visual-source versions stay in that key. An audio-only new version reuses all validated scene MP4s. The bounded polish sample authorizes only its changed Flat scenes; the existing Earth scene must hit its verified cache or the job fails rather than rendering a replacement.

Sample builder (does not render):

```bash
.venv/bin/python tools/build_rhythm_master_sample.py \
  --evidence docs/evidence/rhythm_sample_created_NEW_VERSION
```

This recovery/polish tool expects the preserved local 12-second Production project and its validated Earth cache. It explicitly refuses an absent cache. Normal new-topic generation is through the application's plan/approval workflow and does not require this test builder or a user-authored JSON.

## Verification boundaries

The two actual uploaded excerpts were analyzed before edits; platform UI and the two-second export cards were excluded. Existing opening movement is not called a fresh launch. Camera-only movement, subtitle swaps and effect growth do not inflate event counts. The common principles are uneven movement/reveal/reading rhythm, anticipation, concise timely information, subject hierarchy and measured dynamic contrast. Reference scripts, screenshots, design, colors, countries and audio are not production assets.

The runtime provides decoded-frame, native-geometry, PCM, onset, loudness, browser-playback and actual-download checks. It does not provide direct assistant audio listening or a physical smartphone. Perceptual sound superiority and audience retention are not certified by numerical tests. The versioned RHYTHM_REPORT and SFX_TIMELINE separate measured results from those remaining user-review judgments.
