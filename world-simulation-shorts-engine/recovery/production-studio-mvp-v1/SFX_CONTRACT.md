# Studio SFX adapter

The Studio post-processing adapter reuses the original CC0 waveform library
without changing any existing video contract, renderer, camera, silent
composition, V4 source data, or reference video. It generates SFX only. There is
no narration, subtitle, music, historical-event inference, or external audio
download.

## Input and binding

`normalize_sfx(settings, video_plan)` returns a canonical object:

```json
{
  "enabled": true,
  "gain": 0.65,
  "exportWav": false,
  "cues": [
    {"eventId": "EXISTING_EVENT_ID", "frame": 30, "type": "CLICK", "gain": 1.0}
  ]
}
```

The event ID must exist in the supplied `productionV3.eventChapters` or
`legacyScenePlan.beats`. The cue frame must lie inside that event's actual
global, half-open frame range. Invalid references, duplicate cues, unknown
types, out-of-range frames, non-finite gains, and unknown settings are rejected.
All gains are bounded to `[0,1]`. A missing `cues` field creates one transition
cue at each supplied chapter start. An explicit empty list creates no cues.
The normalizer does not alter the underlying silent video plan.

| Public role | Existing original category |
| --- | --- |
| `CLICK` | `CITY_REVEAL` |
| `MECHANICAL_TICK` | `ROUTE_PROGRESS` |
| `OCCUPATION_COMPLETE` | `ROUTE_COMPLETE` |
| `MARKER_POP` | `ENTITY_SPAWN` |
| `CAMERA_WHOOSH` | `CAMERA_SOFT_MOVE` |
| `EVENT_TRANSITION` | `TRANSITION_LIGHT` |

These are configurable audio roles. Requesting a marker sound does not create
a geographic marker or assert that an unverified historical marker exists.
The producer supplies the structured events and cue bindings.

## Audio output

`render_sfx(settings, video_plan, output_wav)` writes a fresh 48,000 Hz stereo
PCM16 WAV and returns a private receipt. SFX OFF creates no WAV. At 30 fps each
video frame is exactly 1,600 samples. Other allowed frame rates use rational
round-half-up sample placement and exact declared frame-count duration.

The mixer never allocates a complete long-film PCM array. It streams blocks of
at most 48,000 stereo float32 samples and holds only the fixed short original
assets. Source reads verify the original source SHA, licensed catalog, WAV SHA,
PCM SHA, sample rate, channels, format, and frame count. No SciPy import is
required at playback: SciPy is used only by the recorded asset build recipe.

Three cues may overlap. Further concurrent cues are omitted with a private
receipt rather than shifted away from their visual event. Same-type cues
inside 120 ms are omitted similarly. A waveform variant is selected only from
the cue's stable event ID, frame, and role. It never depends on the preceding
accepted variant. Admission counts all authored predecessor cues, including
omitted cues, so removing one cue cannot cascade acceptance changes through
the rest of the film. Per-cue source gain is at most 0.18, limiting the sum of
three peak-normalized sources to 0.54 before PCM16 quantization. Clipping
causes failure rather than success. Cue endings use an 18 ms fade, including
truncation at the end of the video. Every omission, gain, asset hash, and sample
offset is recorded.

## Video composition and delivery

`mux_sfx(silent_mp4, wav_or_none, output_mp4, video_plan)` requires a verified
silent H.264 source matching the plan. It uses FFmpeg to copy the video stream
and add one 48 kHz stereo AAC track. The complete decoded video frame and
timestamp hash sequences must remain identical. The MP4 edit-list effective
audio duration must equal the WAV's exact sample count. Actual audio decoding
checks all effective samples; codec-frame padding below 1,024 samples is
reported separately. SFX OFF makes a byte-identical new silent MP4 copy.

Neither function overwrites an existing result. All WAVs, private receipts,
temporary files, and internal provenance stay in the private job directory.
The Studio delivery adapter may export the final MP4, SHA256SUMS, safe quality
summary, and optionally the SFX-only WAV. Mounted readback and external Dropbox
synchronization remain separate claims. Audio-only changes do not require new
GPU frames; the controller owns visual-cache invalidation.

## Partial audio revisions

`audio_revision_impact(old_settings, new_settings, video_plan)` uses the same
cue scheduler as the actual mixer. Its `changedSampleIntervals` are merged
half-open **conservative authored cue-support bounds**. They include changed
source tails and any immediately affected neighboring admission; they do not
claim every enclosed PCM sample differs. The contract reports affected and
adjacent scenes from these bounds. Outside the reported union, the set,
variant, gain, timing, and order of audible contributions remain identical.

The former unapproved Studio candidate used chronological accepted-variant
history and accepted-cue cooldown history. An actual PCM check demonstrated
that removing a cue at 25 seconds changed 9,059 sample frames at an unchanged
36-second cue. A dense authored burst also propagated 51 later acceptance
changes through 40 seconds. Both defects are corrected by stable cue identity
and local all-authored admission. Focused actual PCM regressions prove the
unchanged 36-second waveform and show that boundary tails/neighbor effects are
fully contained in the disclosed conservative intervals. The original frozen
CC0 library and all 18 WAV assets remain unchanged.

## Validation boundary

The focused tests execute actual FFmpeg on a synthetic 2-second test video and
verify an AAC mux with identical video pixels/timestamps, plus an actual
600-second WAV with 28,800,000 samples and a fixed 48,000-sample mix block.
They verify all six waveform roles, event bindings, sample placement, gain,
ON/OFF, repeat determinism, clipping/overlap limits, immutable output, damaged
asset rejection, duration, and failed publication handling.

The tests establish CPU waveform and FFmpeg behavior. Direct human listening,
reference-equivalent sound quality, actual NVIDIA output, and complete
80-second video delivery require their own evidence. No such success is
asserted by this adapter.
