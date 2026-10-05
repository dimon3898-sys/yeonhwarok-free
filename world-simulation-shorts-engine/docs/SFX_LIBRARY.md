# Production event sound library v1

Production Default v1 uses original 48 kHz stereo procedural cues. No audio was
sampled from a reference video, stock site, film, game, or recording. The author
is the Cinematic World Map project. The composition and generated audio are
released under **CC0-1.0**, with no attribution requirement. The source is
`engine/sfx_library.py`; its SHA-256 identifies each preserved library revision.

This is a restrained cinematic map sound library. Aircraft and ship cues are
stylized pass sounds, not authenticated engine recordings. No paid API or audio
download is required.

## Categories and variants

Every category has three reproducible variants, named `CATEGORY_01`,
`CATEGORY_02`, and `CATEGORY_03`. Each changes duration, tonal center, noise
bandwidth, stereo reflection, and deterministic noise seed within its family.

| Category | Family | Intended role |
| --- | --- | --- |
| CAMERA_MOVE | low sweep | Optional quiet camera travel |
| FAST_ZOOM | short sweep | A fast approach |
| COUNTRY_REVEAL | warm pulse | Geographic region emphasis |
| CITY_REVEAL | soft pulse | City focus or arrival |
| ENTITY_SPAWN | short pulse | Entity appearance |
| AIRCRAFT_PASS | stereo pass | Aircraft departure or passage |
| SHIP_PASS | low stereo pass | Ship departure or passage |
| ROUTE_START | light sweep | Route head begins |
| ROUTE_PROGRESS | short light sweep | Useful progress/distance information |
| ROUTE_BLOCK | restrained impact | Route changes to blocked |
| REROUTE | directional sweep | An alternative path appears |
| RADAR | soft pulse | Radar information |
| WARNING | low impact | New constraint |
| IMPACT | low impact | Significant state change |
| SHOCKWAVE | deep impact | Shockwave visual |
| NETWORK_EXPAND | broad sweep | Connections expand |
| NEW_VARIABLE | tension sweep | A new causal variable |
| MID_PEAK | deep impact | Narrative midpoint payoff |
| FINAL_PEAK | deep impact | Final major payoff |
| FINAL_REVEAL | deep impact | Results or global reveal |
| TRANSITION | short sweep | Information-preserving transition |

Categories describe sound support, not the availability of a visual plugin.
For example, having a SHOCKWAVE sound does not implement WAR_VFX.

## Selection, timing, and history

Only plans with `production_defaults.version: "v1"` use this new mix. Unmarked
plans retain the original synthesizer, score, and mix law. An `options.sfx`
toggle suppresses effects independently of narration and music.

An event can set `sfx_category`, `sfx_variant`, and `sfx_intensity`. When a
`visual_event_id` is provided, the mixer uses that same Scene's actual visual
timestamp rather than an inconsistent separate sound time. The timestamp is
advanced to the first rendered frame at or after that time. At 30 fps the onset
is placed on the exact 1,600-sample frame boundary, with less than one frame of
rounding. No claim of pixel-detected onset or spoken-word alignment is made.

Variant selection is chronological and deterministic. It avoids the immediately
previous file and prefers variants not used in the preceding four seconds.
When all three variants of a category are used inside four seconds, it chooses
the least recently used valid variant and discloses the short-term reuse. A
user's explicitly selected variant takes priority and any repeat is reported.
The same plan therefore produces the same sound choice without unstable random
selection. Project history is preserved in `audio/sfx_history.json`.

The reusable WAV library is stored under
`assets/audio/production_sfx_v1/<source-hash>/<CATEGORY_NN>.wav`. Each WAV has an
adjacent metadata JSON with author, source, license, attribution, actual
generation date, SHA-256, byte count, sample rate, and channels. A source revision
creates a new directory. Existing WAVs are verified and never replaced. Used
files are recorded again in each project's `audio/sfx_sources.json`.

## Intensity and mix

| Intensity | Peak-normalized source gain | Typical use |
| --- | --- | --- |
| LOW | 0.048 | Country/city focus, progress, optional camera |
| MEDIUM | 0.090 | Route start, entity pass, reroute |
| HIGH | 0.145 | New variable, block, mid peak |
| PEAK | 0.235 | Final peak and reveal |

The gain law is applied before narration ducking and whole-program loudness
normalization. Explicit linear `gain` scales this law relative to 0.12. Legacy
`gain_db` remains the old mix law for unmarked plans; production uses documented
category intensity instead. Camera motion is never automatically counted as a
meaningful retention event, and optional camera cues default to LOW.

Measured narration cues have smooth 180 ms attack and 450 ms recovery. Actual
voice RMS also reserves space for supplied narration without timing cues. During
speech, SFX can fall to 0.25 and BGM to 0.16 of their original gains. No TTS speed
or waveform duration is changed. The low-mid BGM follows causal events, a faster
Hook rise, midpoint peaks, a post-peak breath, the final reveal, and a short
resolve. FAST/NORMAL/CINEMATIC adjusts this music pulse rate; it does not speed
the completed film or voice.

The completed mix uses the existing two-pass FFmpeg normalization target of
−18 LUFS and −2.5 dBTP. Peaks are controlled before normalization. The report
retains the actual measured normalization values rather than claiming the
target is always achieved by every short film.

## Verification and limits

`tests/test_production_sound.py` checks all 63 distinct licensed waveforms,
immutable cache bytes, chronological repeat behavior, explicit user override,
visual binding, exact sample placement, intensity ratios, ON/OFF, smooth
measured/untimed speech priority, music peak/breath rhythm, actual FFmpeg mix
outputs and source hashes. A representative old pulse/whoosh/deep-impact plan
retains the raw PCM SHA-256 recorded from the original audio implementation:
`6d99792c5f0ffa464188003c300b9e216cee6e474234849152e1d7cc35af1091`.

The cloud environment supports waveform, loudness, timing, and playback checks.
Direct human listening and empirical TTS intelligibility/subjective cinematic
quality are not established by these automatic checks. Audio reports therefore
retain `direct_listening: false`. The short integration video is the style
approval artifact; this module does not authorize a 75-second render.

The completed 12-second integration actually uses 13 cues, 12 distinct WAV
hashes and 11 categories, with no consecutive file repetition or file reuse
inside four seconds. Its encoded mix measures −18.0 LUFS / −2.5 dBTP and has
zero offset against the prepared PCM. All authored onsets are on the frame
sample grid. Smooth visual fades become positive on the next frame; semantic
visibility receipts can follow by two frames, so this is not a claim that every
visible primitive appears at full strength on its sound sample. Actual ducking
minima are BGM 0.16 and SFX 0.25. The SFX-OFF movie retains TTS/BGM and exactly
the same picture stream. See the delivered [QC report](../../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/QC_REPORT.md)
and [independent AV audit](../../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/INDEPENDENT_FINAL_AV.json).
