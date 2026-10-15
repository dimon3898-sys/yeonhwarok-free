# Stage A — reference storyboard and semantic alignment

The authoritative target is the uploaded `WORLD_ENGINE_REFERENCE_65379_COMPRESSED.mp4`, SHA-256 `5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6`. The latest user calls the reference `65395`; no separately verified file with that alias is available. This analysis uses the actual attachment, not a guessed replacement. Its duration is 31.813189 seconds, dimensions 1080×2520, and decoded frame count 958. Timing varies; frame numbers must use their actual PTS.

The entire timeline was visually reviewed through 64 decoded half-second samples from 0.0 through 31.5 seconds. Full-resolution details at the opening and approximately 5.18, 7.68 and 10.18 seconds were also inspected. The separate [dense audit](FULL_REFERENCE_METRICS.json) and [independent native decode cross-check](NATIVE_DECODE_CROSSCHECK.json) decoded all 958 frames: no exact adjacent duplicates, no qualifying low-motion run of at least 0.15 seconds, and no equal opening/end loop were found. Those measurements do not mean that every map feature moves continuously. Slow camera intervals, individual unit holds and caption changes remain distinct visual actions.

No actual NVIDIA-rendered F MP4 was supplied. Current-F comparisons below use the saved CPU SwiftShader images `F_000.png`, `F_075.png` and `F_149.png` from run `38821837659-1`, plus the immutable saved control and camera inputs. They cannot establish real GPU motion, frame performance, encoding quality or user video approval.

## Whole-clip storyboard

Intervals are approximate visual boundaries with half-second sampling precision. They are not new event timings to copy into the existing five-second fixture.

| Recorder time | Visible phase | Consequence for the five-second comparison |
| --- | --- | --- |
| 0–1.5s | The whole peninsula is established. Orange northern territory and textured purple southern territory are already present. Southern support badges enter/reposition while framing eases outward. Gold outer-country/coast light is visible before substantial new gain. | Establishes that the gold silhouette is a persistent map treatment, rather than a front-triggered effect. |
| 1.5–5s | Marker groups arrange on opposing sides. The camera changes position and scale gradually. Existing southern purple still carries terrain detail. | This is positioning context, not the best window for measuring a large gain band. |
| About 5–10.5s | A saturated violet gained band advances north. A thin bright white interface follows its leading edge. Gold light remains around the outer country/coast silhouette. Camera tracking and scale change continue. | This is the relevant phase already represented by the saved F geometry and event clock. |
| 10.5–13.5s | The gained band broadens while the original southern territory retains a different, textured purple appearance. The remaining orange region retreats. | Later progress of the same event; do not replace the saved five-second geometry merely to imitate this larger outcome. |
| About 13.5–16.5s | A yellow/black warning or radiation-style glyph appears near the front. | A separate story symbol. It is not evidence of a physical simulation and is outside the saved five-second scene. |
| About 16.5–20.5s | Several aircraft silhouettes cross the view. A brief localized orange/white impact effect and a grey remnant appear near one location. | These later effects must not be added to the current five-second fixture by inference. |
| About 20.5–23.5s | Aircraft leave; marker groups and northward control change remain. | No reset to the opening state was observed. |
| About 23.5–28s | Remaining orange territory shrinks; some northern markers fade individually. Purple gains fill most of the north while the camera continues gentle tracking. | Closing takeover, not a replay of the selected early-advance segment. |
| About 28–31.813s | A large red/blue/white national-flag-shaped fill replaces the territorial presentation. | An outro transition. Its colors must not enter territorial ownership, saturation or terrain statistics. |

The full recorder contains approximately 31.8 seconds of changing presentation. Ordinary territorial development occupies roughly the first 28 seconds; the final roughly 3.8 seconds is a flag-fill outro. There is no basis for calling all 31.8 seconds one repeated five-second loop or trimming it to an invented short “effective” animation duration.

## Phone UI and text exclusion

Coordinates below use the original 1080×2520 recorder frame, in half-open `[left, top, right, bottom]` form. The dense audit supports map texture beginning at row 211: row 210 is almost entirely black. Row 212 is a conservative clean-start guard. A nominal 1080×1920 map embedding is `[0,211,1080,2131]`; the bottom is inferred from aspect ratio and is partly obscured, so it is not a measured clean-content edge.

| Exclude from map-quality scoring and reproduction | Conservative recorder-space region |
| --- | --- |
| Phone status and upper navigation | `[0,0,1080,211]` |
| Bottom app/phone navigation outside nominal map | `[0,2131,1080,2520]` |
| Right social controls and counts | `[920,870,1080,2131]` |
| Right-edge floating handle | `[1060,820,1080,1300]` |
| Channel, join button, title and comment overlay | `[0,1835,1080,2131]` |
| Changing in-video subtitle band | `[120,1450,930,1620]` |

These masks intentionally discard some valid map pixels. An occluded or masked pixel is unknown; it is never evidence of a terrain, coastline or color failure. Cropping away the phone header alone does not remove the social rail, captions or footer. No UI, subtitles, channel artwork or reference badge portraits are to be copied into a new proof. Original uploaded video bytes and extracted reference frames remain outside the public repository.

## Same-event alignment to the saved F scene

The immutable scene metadata already names `[5.181813,10.181813]` as its five-second reference segment. Actual inspection confirms that this window depicts the corresponding phase: a small initial gain grows into a broad northern band, with the same opposing marker groups and continuing camera motion. This is an appropriate semantic comparison window. It is not proof of exact pixel registration or equal wall-clock interpolation.

The preserved F control intent advances north and continues beyond the chosen window. Frame 149 is the end of the excerpt, not the end of the event; no artificial stop, arrival or camera lock should be inferred there. Current F uses its separate bounded camera adjustment, so reference and F framing must be registered or compared by semantic feature regions before numerical color comparison.

| F frame / time | Closest decoded reference frame / PTS | Saved mean boundary advance from base | Normalized advance within the existing excerpt | Comparison phase |
| --- | --- | --- | --- | --- |
| 0 / 0.000s | 160 / 5.181813s | 0.06034° | 0.000 | Initial gained sliver |
| 38 / 1.267s | 197 / 6.438010s | 0.60704° | 0.286 | Early northward expansion |
| 75 / 2.500s | 235 / 7.694207s | 1.21554° | 0.605 | Middle gain band |
| 112 / 3.733s | 272 / 8.918999s | 1.60116° | 0.807 | Late expansion |
| 149 / 4.967s | 310 / 10.175196s | 1.97022° | 1.000 | Excerpt end; event continues |

The degree values are an oracle over the existing saved boundary latitudes. They are not surveyed distances or new geometry. Reference indices come from actual frame PTS rather than an assumed constant 30fps. The normalized advance is intentionally not replaced with a linear frame fraction.

## Observed visual roles and differences

**Gold outer silhouette and white moving front are separate roles.** The reference has warm gold illumination around the outer country/coast geometry, including boundaries that are not currently advancing. The bright white internal leading edge follows actual territory change. Current F has the moving white/gold front but mostly dark outer coastline edges. Treating the missing outer halo as a failed moving-front shader would solve the wrong problem.

**New gain is visibly distinct from held territory.** In the reference’s selected window, newly gained territory is a very saturated, relatively flat violet band. The original southern purple retains much more visible land texture. The gained band accumulates across the selected interval; no return to the older textured material is demonstrated there. A timed fade must therefore not be presented as an observed reference fact. Current F intentionally assigns the same RGBA to existing and gained winning territory, so this distinction is absent even when ownership and motion are correct.

**The reference contains more local irregularity than the saved scalar knots show.** Its bright interface appears finely irregular, with small bright details close to the edge. Current F exposes some straighter connections between preserved control knots. This is an observation about appearance, not authorization to alter the saved geometry, invent another decorative line, or copy reference pixels. The existing boundary’s synchronization is already source-backed.

**The map is brighter and warmer around the silhouette, while relief remains legible.** Reference land outside the event area has readable ridge/valley structure. Its original territorial colors retain terrain detail; the gained band suppresses more of it. F’s supported ASTRA/NE materials are darker and more muted. A comparison must use the same semantic land regions and UI masks before recommending a global contrast or lighting increase.

**Water is teal-blue with broad darker relief features.** The gold silhouette contributes substantially to the apparent bright nearshore zone. It must not be misclassified as a measured shallow-water color. F’s darker blue ocean and partial source support should be evaluated separately from the static outer halo and the ownership fill.

**Reference markers have a larger, more conspicuous silhouette.** They use multilateral flag badges and a cartoon human center. Current F uses original rounded flag tablets with a dark housing. Their readability can be compared, but the reference portraits, badge artwork and exact container design must not be reproduced. This stage does not approve any marker redesign.

**Motion remains unverified for the current F video.** Source camera and event plans are deterministic, and F stills show different states. Without the actual NVIDIA F MP4, those facts do not establish real hardware continuity, performance, video compression or reference-level quality.

## Stage boundary

This deliverable is Stage A analysis only. It changes no renderer, camera, control intent, data, GPU launcher or existing output. No paid GPU work, rendering-quality PASS or FINAL promotion occurred. The next step is the parent’s Stage A review and the explicitly ordered source audit; implementation is not started by these observations.
