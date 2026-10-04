# Reproducing MASTER v2

MASTER v1 is retained under all original names. The v2 entry is `index_v2.html`. `src/core_v1_preserved.js` is a mirror of v1's classes with only the automatic browser bootstrap removed; `src/engine_v2.js` inherits and extends them. No GIS coordinates, country data, v1 music or v1 documentation were replaced.

Use the already installed dependencies from the original README. Start the internal render server from this project:

```sh
python3 -m http.server 8020 --bind 127.0.0.1
```

From a second terminal in the same directory:

```sh
.venv/bin/python tools/sound_v2.py
.venv/bin/python tools/master_audio_v2.py
node tools/preflight_v2.mjs
node tools/render_v2.mjs --seconds=20 --name=master_cinematic_20s_v2_picture_untagged
.venv/bin/python tools/tag_video_v2.py outputs/master_cinematic_20s_v2_picture_untagged.mp4 outputs/master_cinematic_20s_v2_muted.mp4
.venv/bin/python tools/mux_v2.py --name=master_cinematic_20s_v2 --seconds=20
.venv/bin/python tools/validate_v2.py outputs/master_cinematic_20s_v2.mp4 --scene outputs/master_cinematic_20s_v2_muted_scene_audit.json
node tools/playback_v2.mjs master_cinematic_20s_v2.mp4 --no-capture --mobile
```

The render command refuses an existing video filename. Use a different review name for iterations, preserving the approved v1/v2. `--start=5 --seconds=5 --name=your_review_name` renders a deterministic timeline slice. Compatible approved slices can be concatenated with the preserved `tools/concat.py`; pass their corresponding per-frame scene audit JSONs in timeline order to `validate_v2.py`.

The 600-pose preflight checks projected aircraft bounds against real font bounds before rendering. It does not replace final GPU-frame, encoded-video or playback checks. NRT/SIN labels move smoothly below the aircraft silhouette when nearby. In this delivery, the reviewed 0–5s slice is retained because only the later NRT/SIN label placement and nonvisual geometry auditing changed; the 5–10s slice was rerendered under an r2 filename. `outputs/v2_source_r2.json` records the source hashes and interval equivalence.

2160×3840 internal resolution, 2 temporal samples for restrained movement and 3 for the opening, network pull-out and final expansion; 180-degree shutter span. Crisp 2D type is added after scene blur. JPEG quality .99 transfer, Lanczos reduction, H.264 CRF16 slow, 1080×1920 / 30fps / faststart. `tag_video_v2.py` explicitly sets full-range BT.709 VUI and container tags without recompressing picture slices; final checks proved all 600 decoded RGB frames identical before/after tagging. Original stereo music/effects are mastered toward −18.5 LUFS / −2 dBTP; `mux_v2.py` applies a final −0.6dB gain before AAC 320 kbps to leave codec peak headroom. Final AAC measures −18.54 LUFS / −2.41 dBTP / 7.50 LU LRA. Final codec/color/loudness measurements are recorded in QUALITY_REPORT_V2.md rather than assumed from the target settings.

## Reusable direction modules

- `CameraController.values/update` and configurable key arrays: continuous push, settle, banking, orbital approach and pull-out. `follow_entity(routes)` activates smooth tracking.
- `MapRenderer.focus_city`: geographical focus lighting; globe shaders provide terrain shade, deep blue water, warm urban light and atmospheric depth.
- `RouteAnimator.animate_route`: arbitrary geographic endpoint geodesics, progressive thin core/glow/head and fading short tail.
- `EntityAnimator.spawn_entity/update`: inherited dimensional aircraft, tangent orientation, perspective and bank; it clears the frame for network expansion.
- `NetworkAnimator.activate_network`: restrained temporary neighboring relationships and final overview.
- `EffectsEngine.destination_pulse`: sequential destination halos and surface rings.
- `SceneManager.story`: timed information beats. `insert_cinematic_clip` and the inherited cover compositor keep the future map → prepared cinematic clip → moving map interface.

The example scene still specifies three hubs and authored shots. The geometry and projection routines accept arbitrary longitude/latitude; full automatic camera planning and global scene configuration remain later work, not completed capabilities.

The GIS/license sources from `assets/SOURCES.json` and the original README apply unchanged. `assets/v2/cloud-haze.png` is original procedural graphic noise for translucent atmospheric wisps, not a generated map or observed weather dataset. Both v2 generated audio waveforms and the original haze graphic may be reused under CC0-1.0. No external music, I2V model or reference design/audio is incorporated.
