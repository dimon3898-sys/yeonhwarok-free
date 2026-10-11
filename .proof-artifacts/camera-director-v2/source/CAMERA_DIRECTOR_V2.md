# Camera Director V2 — Continuous Continent Zoom

V2 begins on the approved flat Continent map. A single camera trajectory moves
the geographic center while interpolating the logarithm of geographic width and
height. All motion phases sample the same C2 quintic curve; crossing a state
boundary does not restart an easing curve or replace the displayed map.

`camera_director_v2.mjs` is a pure frame-plan module. Rendering, raster source LOD
and GPU resource management remain outside it. It does not own a final-image
dissolve or a Globe/Flat projection transition.

## Inputs and stop contract

`compileContinuousCameraPlan` accepts approved `continent` and `regional` Scale
plans, optional geographic `contextExtent`, actual target geometry references,
event anchor, measured text bounds and Local Detail Admission evidence. No region
name, scene-specific coordinates, zoom distance or label position is embedded in
the compiler.

The default starting extent comes from the compiled Continent plan. If a context
extent is supplied, the shared geographic extent fitter preserves its coverage
and canonical output aspect. The start must contain the approved Regional stop.
The final camera bounds equal that approved stop exactly. LOCAL is never used,
including when it is requested by a target intent.

## Default timeline (30 fps)

| State | Frames (start inclusive, end exclusive) |
| --- | --- |
| CONTEXT | 0–45 |
| ACCELERATE | 45–93 |
| TRAVEL | 93–148 |
| DECELERATE | 148–204 |
| SETTLE | 204–222 |
| LOCK | 222–228 |
| REVEAL | 228–288 |
| HOLD | 288–378 |
| NEXT | 378–384 |

The moving camera reaches the approved Regional extent exactly at frame 203;
frame 204 begins the fixed Settle state. Velocity and acceleration approach zero
at both endpoints. No motion or camera drift occurs in the reveal/read tail.

The V1 reveal order and relative timings are preserved: Primary 12 frames, Marker
12, Location plus Country 15, Title 21. V1 Lock, Hold reading policy and Next
timings are protected. Only wide hold, motion duration, phase fractions and
Settle duration can be overridden. The scenario disclaimer retains V1 behavior.

## Renderer integration

`evaluateContinuousCameraFrame` provides actual geographic bounds, center,
velocity, state and reveal fractions for an integer frame. A renderer must use
one continuously updated flat camera and geographic GIS geometry. LOD must
select geographically registered source data within that material path rather
than switching or dissolving complete rendered output frames. The Regional
arrival must preserve the previously approved final image and measured layout.

V1 files and proof assets remain intact. V2 does not add a World stage, LOCAL
stage, animation story, Event State simulation, audio or Production pipeline.

The motion proof is Software WebGL2 only. Final approval remains user video
review; this module does not authorize a following development gate.
