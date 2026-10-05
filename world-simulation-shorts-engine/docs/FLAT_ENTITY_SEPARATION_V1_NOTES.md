# Optional aircraft separation for S004

The new adapter is `web/flat_entity_separation_polish.js`. It exports
`SceneFlatEntitySeparationPolishRenderer` and requires both
`visual_polish.version = "v004"` and `visual_polish.entity_separation = "v1"`.
Unflagged scenes keep their frozen renderer and cache identity. The adapter does
not edit any previous renderer, shader, scene plan, texture, audio or video.

The display calculation uses the actual posed aircraft meshes: all eight
corners of each world-space `Box3` pass through the current registered map/globe
camera. Pair lanes come from verified route arrival directions and origin order.
The model size floors remain 88/82 pixels at the configured 1080-width map scale.
Actual perspective footprints vary with the camera; those configured floors
are not a claim that every orientation occupies an identical pixel rectangle.

For moving aircraft, the target lane gap is 12 pixels at a 375-pixel-wide mobile
viewport. At a shared departure airport a 3-pixel target and a 0.6-second
reservation let the stationary proxy yield before the departing model appears.
The reservation is an undrawn model clone: the aircraft and its visual event do
not appear early. This new subclass replaces the previous stopped-only display
offset with one absolute policy, restores the unshrunk model floor, and never
adds further model shrinking.

The offset is solved through a local inverse of the actual projection. Model,
shadow and short past-pose ghosts receive the same delta before the existing
geographic vertex warp. A smooth positive-part envelope and fixed lane direction
avoid slot flips. Each frame starts with inherited absolute entity poses; the
layout uses no previous-frame state. The verified geographic anchor, route head,
route progress, entity orientation and event timestamp remain unchanged. A faint
connector distinguishes a displaced display proxy from its geographic anchor.
Native audit records expose the distinction and conservative projected bounds.

`tools/flat_entity_separation_contract_tests.mjs` prepares all 90 S004 frames on
CPU using the real aircraft geometry and unchanged registered camera/warp code.
It creates no WebGL context, draws no movie and downloads no asset. The labels
use the previously recorded native Noto font boxes and the unchanged fixed
airport reservations. The complete report is
`docs/evidence/flat_entity_separation_v1_cpu_20261005T131100Z/CPU_REPORT.json`.

Measured CPU checks passed: no visible aircraft bounding-box overlap, no model
safe-area violation, no reserved-label overlap or position change, unchanged GIS
anchors and route progress, and identical results after reverse-time sampling.
The moving pair's smallest lane gap was 12.0877 pixels at mobile width 375; its
final gap was 12.1361. Across all visible pairs, the smallest rectangle gap was
6.2067 mobile pixels. The additional layout's largest 30 fps frame step was
3.6994 mobile pixels and largest change in that step was 1.5058 mobile pixels.
These are measured layout differences, not a claim about audience retention.
The report also verifies unchanged hashes of eight existing modules/pages/tools.

This is cartographic decluttering, not a physical air-traffic separation model.
The conservative boxes include empty silhouette corners, so the required proxy
spacing can exceed the spacing strictly necessary between visible pixels.
CPU checks do not establish raster visibility, final encoded motion quality or
the appearance of the following unchanged Earth scene. Native frame/movie review
must judge those separately. S005 and all completed v004 scenes are preserved;
this adapter is intended only for a separately versioned partial S004 render.
No 75-second render or MASTER render is performed by this change.
