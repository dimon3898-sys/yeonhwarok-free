# Camera Director V3: Primary material from frame 0

V3 consumes the exact approved V2 compiled camera plan. V2 remains the sole evaluator of camera centers/extents, velocity, easing, scale, admission, settle/lock and Hold. The shared single-map GPU pipeline and geographic source LOD are reused.

Primary country material is permanently enabled with the explicit `primaryMaterial=1` input. Secondary/Neutral palette rules stay unchanged. No country material animation stage exists.

The legacy `reveal.primary` factor is retained exclusively for the V2 Boundary/Glow timing. It does not control V3 country material. The renderer accepts an optional material factor; null preserves legacy behavior. Shader code, colors, terrain, DEM and all ribbon/glow style parameters are unchanged.

The existing 60-frame post-lock window becomes Marker (12 frames), Location (15), Country (12), Event Title (21). Camera/Settle/Lock/Hold/total384 frames are unchanged. The graphics renderer uses existing factor>0 appearance semantics; no text redesign or layout reflow.

Proof output: Software WebGL2, 1080×1920,30fps,12.8seconds,silent. One iteration only. Final Hold must exactly match the V2/approved PNG. No Container, gCube, NVIDIA, Event/TTS or next stage.
