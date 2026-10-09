# v020 actual mixed-track analysis

Both uploaded MP4s contain one 48 kHz stereo AAC audio stream. PCM was decoded
directly from those streams into memory for analysis; no WAV, reference audio
sample, or new sound asset was retained. This analysis includes waveform-envelope
and spectral measurements plus independent frame inspection. Direct listening
and source separation were not performed, so audible SFX identification remains
unconfirmed.

The reference audio stream ends at 19.050667 s although its video is 21.166666 s.
Its stereo RMS is -25.871 dBFS and sample peak is -0.903 dBFS. The current audio
runs 24.000000 s, with stereo RMS -17.688 dBFS and sample peak -2.425 dBFS. These
are sample/RMS measurements, not integrated loudness or true-peak measurements.

The reference spectrogram shows repeated harmonic/formant-like structures and
irregular broadband consonant-like rises throughout the recording. Its 65
spectral novelty candidates are not 65 SFX. Maximum envelope autocorrelation
between 0.2 and 2 s is only 0.064, which does not establish a regular effect/beat
cadence. The current has a steady low-frequency harmonic bed with two distinct
transient components at approximately 2 and 6 s. Its many lesser envelope rises
are chiefly the recurring amplitude pattern of that bed.

## Reference temporal associations

Onset, peak and end below are proxies measured in the **mixed track**. End means
three consecutive 10 ms windows returned to within 2 dB of the median envelope
0.08–0.35 s before the novelty. A blank end means no such return within 0.9 s.
For these mixed signals, that threshold is not the duration or decay of a
separable SFX. Relative level is RMS peak above that local envelope baseline.

| Visible event | First positive / visual peak | Mixed onset / peak / end | Relative peak | Interpretation |
| --- | --- | --- | --- | --- |
| Map cut | 0.9667 / 0.9667 s | 1.045 / 1.105 / 1.965 s | +27.38 dB | New phrase-like mixed sound follows cut; isolated transition SFX unconfirmed. |
| Two yellow pins pop | 5.900 / 6.0333 s | 6.055 / 6.065 / unavailable | +43.58 dB | Strong mixed rise near scale peak, but sustained harmonic activity follows. |
| Left violet label begins | 9.6333 / not uniquely defined | 9.835 / 9.835 / 9.855 s | +16.61 dB | Brief broadband high-frequency component after first letter; source unconfirmed. |
| Right violet label begins | 10.3667 / not uniquely defined | 10.405 / 10.555 / 10.805 s | +18.79 dB | Mixed rise during lettering; lower-frequency and later broadband components overlap. |
| Central yellow pin pops | 11.100 / 11.2667 s | 11.255 / 11.285 / unavailable | +36.62 dB | Mixed rise near scale peak, followed by sustained harmonic phrase-like activity. |
| Glowing boundary line begins drawing | 15.1667 / not uniquely defined | 15.345 / 15.435 / 15.915 s | +20.74 dB | Mixed rise after line begins; source unconfirmed. |
| Measurement starts typing | 16.2667 / not uniquely defined | 16.265 / 16.435 / 16.445 s | +3.34 dB | Modest rise near first character, with several further unrelated novelty candidates. |

The two main pin-pop mixed peaks fall approximately 32 and 18 ms after their
visual scale peaks. That is evidence of temporal association. Narration can
also be timed to the exact same visual events, so it does not establish that
the associated sound is an independent pop, hit, or whoosh. Their mixed onset
interval is 5.200 s. The interval between the strongest left-label component
and the central-pin component is 1.420 s; intermediate right-label components
make a simple repeated SFX cadence inappropriate.

There is no confirmed isolated reference SFX onset, peak, end, gain, or decay
to reproduce. `reference_event_audio_correlations.json` therefore retains null
isolated-SFX fields and `event_linked_sfx_confirmed: false` for every event.
The sound recommendation is to preserve existing current audio; do not add a
new whoosh/hit merely because a visual accent is being introduced.

## Current audio and existing engine interfaces

The current distinct components have novelty centers 1.991333 and 6.001333 s.
Their mixed onset/peak/end proxies are respectively 2.005/2.015/2.085 s and
6.005/6.005/6.615 s. Local RMS rises are +8.781 and +15.754 dB; their interval
is 4.000 s. Current thumbnails show the first sound precedes the readable
SUEZ CANAL label, while the second overlaps CANAL CLOSED appearing after 6 s.
They are already authored in `EVENT_QUALITY_v019/PLAN_v019.json` as
`soft_pulse` at 2 s and `low_impact` at 6 s, both with `gain_db: -12`.

That plan has no top-level `production_defaults` or `rhythm_policy`.
Read-only renderer/profile inspection by the architecture agent confirms
compilation does not inject those audio policies. Consequently `engine/audio.py`
uses its preserved legacy branch: kind/gain/gain_db determine those sounds;
the authored `sfx_category` and `sfx_variant` are not selection inputs there.
Adding a visual v020 layer should retain this branch and these authored cues.

Existing authorized alternatives, for a future confirmed need:

- `engine/sfx_library.py` enables its existing CC0 catalog when
  `production_defaults.version == 'v1'`. It accepts existing category-compatible
  variants and `visual_event_id`, aligns insertion to the authored frame, and
  reports event history, sources, gain and sync error. Categories include
  `CITY_REVEAL`, `ENTITY_SPAWN`, `IMPACT`, and `TRANSITION`.
- `engine/rhythm_sound.py` is enabled by `rhythm_policy.version == 'v1'`.
  `select_rhythm_sound_events()` binds semantic visual timestamps, applies
  a configurable 0–1 frame first-positive offset, then existing pre/post
  recipes. It offers existing `CITY_REVEAL`, `IMPACT_LIGHT`, `IMPACT_MEDIUM`,
  `IMPACT_HEAVY`, and `TRANSITION_LIGHT` variants. Authored category/gain choices
  are overridden for bound visuals unless `preserve_authored_sfx_choices` is
  true. Enabling the policy also alters the BGM energy/sidechain path, so it is
  broader than a visual-effect change.
- Both paths retain their existing source/license metadata and can report
  onset samples, rendered PCM hash, peak/RMS, variant history and bindings.
  Their functions can materialize existing procedural-library assets; this
  analysis did not call them or synthesize any sound.

## Reproduction and artifacts

Run `python3 analyze_mixed_audio.py`, `python3 make_acoustic_windows.py`, and
`python3 correlate_event_windows.py` from this directory. The first script
decodes source PCM in memory and saves only numerical envelopes, candidate
measurements and diagnostic plots. The second saves transient-centered visual
thumbnail evidence. The third adds the independently audited native visual
frames without asserting acoustic-source certainty. No repository edits,
external downloads, GPU work, or source-audio reuse occurred.
