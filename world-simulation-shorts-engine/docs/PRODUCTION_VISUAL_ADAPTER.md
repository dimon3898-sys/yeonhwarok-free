# Production Default visual adapter v1

Production scenes explicitly select `production_defaults.version: "v1"`. The new adapter subclasses the approved `SceneFlatEntitySeparationPolishRenderer` and `SceneEarthPolishRenderer`; it does not edit either renderer, their GIS assets, or MASTER V3.

## Selected render pages

- FLAT: `web/render_production_flat.html`
- EARTH/HERO: `web/render_production_earth.html`
- Native runner: `tools/render_production_scene.mjs`
- Shared presentation policy: `web/production_visual_adapter.js`

The existing renderer dispatch remains unchanged for old Scene JSON. Production scenes receive an additive source/version digest; renderer cache records include the exact source hashes. All files are rendered to new output/version paths with the original exclusive-write and recovery checkpoint policy.

## Timing contract

`motion_timing.camera_travel_duration` and `zoom_duration` are independent real-time travel intervals. Camera travel eases to the authored destination and then settles. Entity/route interpolation consumes authored start/end times rather than camera time. Anticipatory `next_event_lead_time`, focus transition timing, geometric handoff timing and the shader clock use real scene time. Earth camera travel and FOV/height zoom use the same policy while orbit/follow envelopes retain the scene clock.

The planner, rather than a global playback multiplier, writes changed route/entity timing. `tts_playback_rate` remains 1.0. FAST never accelerates the completed MP4 or narration waveform.

New plans record `motion_timing.camera_speed_reference` at timing authoring. A later natural-language camera-speed edit changes the effective travel/zoom intervals by `reference / current_camera_speed`, while preserving scene time, route/entity poses and narration. Old production JSON without this optional reference retains its authored intervals.

## Geographic labels

`text_events` are short, explicitly authored statements with verified source coordinates and a bound event ID. They become map-attached labels. A distance or route-status label may declare `route_id`; its display anchor is computed from that verified great-circle route's current head. Its original coordinates and geographic provenance stay unchanged in stored JSON.

Only `role: "distance"` or `role: "route"` follows the moving head. A route ID on a city/arrival/new-variable/block-status label supplies context and does not override its explicit city coordinates. A future explicit `display_anchor: "route_head"` is the only opt-in exception; unsupported input fields still require schema authorization. Both Flat and Earth use the same rule.

Default generated title and story-information banners are suppressed. An explanatory title needs `production_defaults.large_titles: true` and explicit `large_title_approved: true` for the text event. NONE removes labels; MINIMAL keeps relevant country/city/distance/status text. The old narration/script still remain in project records.

The opening question can be a short, explicitly authored `role: "question"` text event bound to a non-meaningful hook event and a verified geographic anchor. It is drawn at the regular map-label scale and marked `kind: "hook_reveal"` only for that actual drawn label. This preserves first-three-second hook QC when TTS is OFF, without adding a large generated title or counting decorative text as a meaningful event.

The post-draw audit stores actual label boxes, geographic screen anchors, opacity, route display parameters and the production source marker. The canvas-free semantic preflight consumes this same production text and camera policy; it forecasts eligibility and is not a rendered-pixel or listening claim.

## Terrain, countries, routes and entities

The approved Natural Earth terrain material, coastlines, selected-country texture-preserving tint, 54-pixel minimum city typography, 88/82-pixel aircraft presentation floors and v1 cartographic separation remain the foundation. Country border colors follow the planner's restrained distinct palette instead of all converging to the same amber highlight. Labels and focus accompany color, so color is not the sole signal.

A primary route has a nominal 6.25-pixel mobile core, increasing to 6.75 over brighter sampled source terrain, a stronger moving head and a small direction chevron aligned to the verified route tangent. Secondary route opacity is 0.30 and glow opacity 0.028. Sampled background luminance comes from the existing geographic raster UV; no new map or coordinates are invented. Main and secondary routes use different visual priority.

The v004 plane-to-sphere geometry, geographic registration, no-veil handoff, Earth day/night lighting, physical atmosphere, separate cloud layer, city lights and readable surface fill remain in use. HERO is a planned peak/global-reveal treatment rather than a substitute for geographic readability.

## Fresh event and final-reveal evidence

A production final-network receipt requires a bound new route that starts at the final event timestamp, makes positive progress and is visible alongside at least one other route. A stored old path or camera pullback alone is not accepted by that binding. Native frame review must additionally check that this new path is visually distinguishable; this prevents duplicate geometry from masquerading as a new situation.

The approved v004 final Earth scene cannot be reused byte-for-byte for a minimal-text production sample because it contains `THREE CITIES · ONE NETWORK`. Removing or covering a caption cannot be claimed as unchanged cache reuse. A new short Earth scene receives its own renderer/scene cache key and measured render time; the old approved scene stays preserved.

## Cache boundary

Only production visual cache keys exclude `sound_events`, `music_energy` and SFX category/variant/intensity choices, including those attached to visual-event metadata. Audio-source library entries are excluded from pixel asset identity. Full Scene JSON, including audio choices, stays preserved in input/manifests and the audio pipeline has its own records. Actual visual timing, labels, country tint, route/entity state and renderer source changes invalidate the corresponding pixel cache. Legacy cache-key behavior is unchanged.

## Geographic scope and limits

The preserved high-detail native regional terrain atlas covers East Asia (104–152 degrees east, -8–65 degrees north). Outside it, the renderer uses the already licensed and georeferenced global 8K Earth surface image; it never silently substitutes Asian coordinates or fabricated geography. Texture detail outside the atlas is lower and is reported as such. The 2K material bump remains visual relief, not surveyed DEM or physical terrain simulation.

Dateline geometry and polar/extreme Mercator framing still require normal preflight and native readability checks. A unsupported projection/route/asset requirement must fail explicitly rather than use a mislabeled graphic. Production default is enabled only for supported planner scenes; existing immutable projects remain untouched.

## Verification

- `node tools/production_visual_contract_tests.mjs`: authored travel/zoom/settle, anticipation, geographic text, explicit title approval, route priority and frozen approved-source checks.
- `.venv/bin/python -m unittest tests.test_visual_polish_contracts tests.test_production_visual_cache`: legacy Earth/flat hashes, additive production source identity, and SFX-only pixel-cache reuse versus actual visual changes.
- The root integration test additionally performs actual native WebGL capture/render, final-frame QC, mobile playback/download and event/SFX onset checks. No 75-second or MASTER rerender is part of this update.
