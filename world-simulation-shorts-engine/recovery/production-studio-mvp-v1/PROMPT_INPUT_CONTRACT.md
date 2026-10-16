# Production Studio structured input V1

The mobile form accepts an existing verified Scene JSON or one JSON production
prompt. This adapter performs no historical research, free-language planning,
new geographic inference, or paid API requests. Missing data returns a named
field error. A pasted Scene JSON is not reinterpreted through the prompt text.

The Studio form request is:

```json
{
  "prompt": "JSON or a single complete fenced JSON block",
  "sceneJson": null,
  "durationSeconds": 80,
  "profile": "V4_ARCHIVAL_80S",
  "sfx": {"enabled": true, "gain": 0.65, "exportWav": false}
}
```

Omit `sceneJson` when pasting a prompt. Omit `prompt` when supplying Scene JSON.
When both are supplied, the Scene JSON defines the video; prompt text is retained
as a private note and is not applied as an unverified visual instruction.

Use [examples/STUDIO_PROMPT_V4_80S.json](examples/STUDIO_PROMPT_V4_80S.json) for the
preserved 80-second, 2,400-frame, 12-chapter profile. Its source-derived V4 fronts
are **partial approximations**, not survey-certified front lines. The preset is
80 seconds only; selecting a longer duration produces an explicit conflict.

For other supplied events and lengths, select `UNIVERSAL_V3` and provide a
validated existing V3 production plan. The same adapter accepts 80, 120, 180,
300, and 600 seconds. It never fabricates or stretches historical data. Video
output is 1080×1920, 9:16, 30 fps; the existing backend owns source, projection,
GPU admission, renderer, camera, frame coverage, and cache validation.

An external structured prompt may contain `schema`, `title`, `durationSeconds`,
`profile`, `sceneJson`, and `sfx`; its schema is
`WORLD_ENGINE_STUDIO_PROMPT_V1`. It must supply either the one known `preset`
or an actual `sceneJson`. The latter includes the existing event timeline,
territory/frontier state, camera/material profiles, unit markers, source
manifest and hashes. Only the protected explicit image/source binding may be
changed by the backend. New records or coordinates are not generated.

Input is bounded to 4 MiB, nesting to 64 levels, and finite JSON values. Duplicate
keys, unknown fields, unpinned image tags, contradictory duration/profile
selections, and missing source admission fail before a render may start.
`StudioContractError` exposes only `code`, safe `message`, named `fields` and
HTTP `status`; internal backend paths or arbitrary exceptions are not returned.

## Event-bound sound

`sfx` accepts `enabled`, `gain` (0–1), `exportWav`, and optional `cues`.
Each cue names an existing `eventId`, its global integer `frame`, a supported
`type`, and optional `gain` (0–1). Event IDs and frame ranges must exist in the
supplied plan. Missing `cues` adds only one transition sound at each supplied
event-chapter start; explicit `[]` requests no cues. It does not infer occupation
completion, troop spawns, or unseen events.

Supported sound types are `CLICK`, `MECHANICAL_TICK`, `OCCUPATION_COMPLETE`,
`MARKER_POP`, `CAMERA_WHOOSH`, and `EVENT_TRANSITION`. A sound name is not evidence
that a historical event happened. The original licensed assets, frame-to-sample
mapping, overlap controls and mux validation belong to `studio_audio.py`.

## Implemented interval revision scope

`plan_revision(parent, startSeconds, endSeconds, prompt, sfx=None)` supports SFX
ON/OFF, volume, or replacement event-bound cues. Seconds must resolve to exact
frame boundaries and define a nonempty half-open interval `[start, end)`.

For example, `25` to `35` with `효과음 꺼줘`, or:

```json
{
  "schema": "WORLD_ENGINE_STUDIO_REVISION_V1",
  "sfx": {"gain": 0.4}
}
```

The revision applies to cue onsets inside the interval. A short sound that
started before the interval retains its tail. It does not claim sample-window
cutting at both boundaries. A changed cue near the end can extend into the next
scene. Removing/replacing a cue can also change admission of a nearby authored
cue because of the fixed cooldown and overlap limit. Replacement cues must
remain inside the selected event/time ranges.

Cue variants are chosen from stable cue identity. Admission examines the local
authored cue schedule rather than a chain of previously accepted cues. This
prevents changing a cue at 25 seconds from cascading through unrelated later
sounds. `audio_revision_impact` compares the two actual schedules and reports
merged half-open `changedSampleIntervals`, including changed cue tails and any
bounded neighboring admission effects. This is a conservative source-support
bound, **not a claim of an exact changed-sample measurement**. Tests separately
render real PCM and check that all samples outside the reported support remain
identical. Cues outside the request preserve their requested gains, while any
local audible effect crossing the boundary is explicitly reported.

Every revision returns a new submission and an impact report containing exact
requested frames, touched scenes, invalidated scenes, reusable scenes, and GPU
requirement. `audioAffectedSceneIds` identifies scenes intersecting the reported
audio support; `adjacentSceneIds` lists affected scenes outside the requested
frame interval. `audioRequestedSamples` distinguishes the requested range from
the conservative `audioChangedSampleIntervals`. A sound-only edit preserves the
complete video plan, invalidates zero GPU scenes, and requires audio
regeneration/remux only. Existing media, claims, and completed source/cache
records are not changed by this function.

Camera zoom/speed, territory, frontier, and other free-text visual edits are
explicitly **unsupported in this MVP adapter**. They return
`STUDIO_VISUAL_REVISION_UNSUPPORTED` (HTTP 422) and preserve the parent. A new
externally verified Scene JSON may be submitted as a new production. This
module does not claim that partial visual GPU rerendering was implemented or
tested on NVIDIA hardware.

Input unit tests use an explicitly fake validator. A separate integration test
exercises the actual frozen V4 source/image validators and existing scene cache
keys. Audio interval tests render actual CPU PCM. None is NVIDIA execution;
real GPU/runtime admission remains independently required by the backend.
