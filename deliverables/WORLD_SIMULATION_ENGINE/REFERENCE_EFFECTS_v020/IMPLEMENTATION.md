# v020 implementation and comparison contract

v020 is a separate reference-effect profile layered over the unchanged v019 scene. The implementation transfers observed timing grammar into neutral artwork and the existing Noto Cinema font; it does not import reference pin artwork, colors, geography, wording, measurements, audio or social-player UI. Root implementation and release validation are recorded separately from the source-video evidence in this folder.

| Existing information cue | v020 added behavior | Frame range, end exclusive |
| --- | --- | --- |
| Suez location, 2 seconds | One neutral outlined circle grows, dips and settles; it uses the existing foreground. Local peak 64, settle 69; retained only through the readable location interval. | 60–90 |
| Canal closed, 6 seconds | Characters reveal with local glyph growth, then return to the original full text. Existing status cross and text opacity remain. | 180–197 |
| Canal open, 11 seconds | Characters reveal with local glyph growth, then return to the original full text. | 330–347 |
| Adaptive wide, 14 seconds | `NONE`; camera-only context has no invented accent. | 420–450 |
| Singapore location, 15 seconds | One neutral outlined circle follows the same entrance grammar. Local peak 454, settle 459; retained only through its readable location interval. | 450–495 |
| Singapore close, 19.5 seconds | `NONE`; camera arrival has no new factual callout. | 585 onward |

The pattern parameter choices are implementation interpretation, not a measured reconstruction of every reference pixel. The small rise/dip/settle curve does not claim an overshoot above final size. There is no recurring pulse, continuous glow, new exit fade, route, transition flash or added SFX. Existing text content, font, opacity, subtitles and authored audio remain unchanged; geography/material/lighting and camera timing are outside this layer.

The profile is [reference_effects_v020.json](../../../world-simulation-shorts-engine/data/reference_effects_v020.json), served as `/static/reference_effects_v020.json`. ON selects v020 through `apply_effects(parent_plan, enabled=True)` and its versioned renderer page. OFF selects the exact v019 parent plan/identity through `enabled=False`. The [complete ON/OFF timelines](effect-timelines.json) cover frames 0–719 without gaps or overlaps and include explicit `NONE`, camera state, text/visual effects and existing sound cues. `end_frame` is exclusive. New SFX are `NONE`; existing cues are identified separately as `EXISTING_soft_pulse` and `EXISTING_low_impact`.

To obtain a reviewable NVIDIA comparison, render ON and OFF using the same 24-second scene and all 720 frozen camera positions, quaternions and FOV values. Keep lighting, materials, geographic/city sources, foreground, font, existing fades, audio, resolution and encoder identical. Capture native images at frames 64, 190, 340, 454 and 630, using the exact `frame/30` timestamps in [the manifest](before-after-comparison-manifest.json). Frame 630 is a preservation check with no active added effect.

The five files under `before/` are real RGB frames decoded from the uploaded CURRENT MP4 by CPU ffmpeg and saved as lossless 1080×1920 PNGs. AFTER ON/OFF paths and hashes are deliberately null, with status `NOT_RUN_NVIDIA`. After an actual authorized NVIDIA run, record renderer/GPU identity, commands, profile/source/fixture hashes and captured image hashes before changing that status. Do not substitute simulated AFTER images or software pixels for that evidence.
