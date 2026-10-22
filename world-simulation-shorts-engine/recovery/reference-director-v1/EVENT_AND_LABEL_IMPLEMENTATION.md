# Event, marker and label sidecar — implementation boundary

Status: **CONTRACT IMPLEMENTED / COMPONENT UNIT DRAW VERIFIED / NATIVE STUDIO CONSUMER BLOCKED**.
This is not a reference-reproduction PASS. No map movie, native map rotation, full
reference frame or actual Studio window is claimed by this component work.

## Existing modules reused and limits verified

| Existing owner | Evidence in 82854af | This implementation |
|---|---|---|
| `web/map_infographic_v1/event_contract_v1.mjs` | `compileEventIntent`, `validateEventAnchor`, `freezeEventData` validate source modes, geographic LineStrings and coordinates | Imported unchanged by `director_events.mjs`; true source SHA and input IDs are additionally required |
| `event_line_v1.mjs:27` | `measurementSpace: CURRENT_PROJECTED_SCREEN_PIXELS` | Cannot supply camera-independent geographic reveal. New data-only source arclength clips unchanged supplied edges before projection |
| `glyph_atlas.mjs:44` | `createMeasuredGlyph` measures real pinned-font ink, checks font loaded, atlas clipping and fit | Imported unchanged; new helper derives stable whole-word ink centering, prefix advance and bottom gap |
| `event_metric_v1.mjs` | Full measured atlas is reusable, but original fraction includes whitespace, has no individual per-grapheme pop scale | New sidecar separates whitespace layout from grapheme beats; no original metric module edited |
| `event_metric_pass_v1.mjs:20–36` | Axis-aligned orthographic plane position only; no along-line rotation or per-glyph scale interface | Native pixel-consumer extension still required; no unsupported draw claim |
| `presentation_runtime.mjs` | Location/country/title/disclosure disabled; native Event consumer absent | Old runtime preserved; new sidecar is not silently inserted into old Studio execution |

## Added, independent code

`director_events.mjs` implements a strict versioned event input, authoring-only
unbound-target compilation and deterministic evaluation of reference frames
29–574. The three window seams do not reset event time. Supplied labels and
metric text remain input data; no country/place/metric fact is hardcoded into the
module. Unknown actual-input fields, missing anchors, source SHA and inconsistent
source verification are rejected. The target's null geography remains null, with
`AUTHORING_ONLY_UNBOUND_NOT_EXECUTABLE`, `renderAllowed:false` and
`pixelConnected:false`.

Implemented state/asset contracts are: once-only context and hero pop curves;
screen-pixel bottom-tip pins; grapheme labels with full-word ink reservation;
four-frame label and eight-frame metric settling; geographic directed boundary
reveal from455 to485 and hold; static context-opacity reveal; separate required,
cull and area-clip roles; no count-up, fake territorial movement or repeated pulse.
The rendered text halo, per-glyph GPU pop and shared native-map projection are
**not implemented pixel consumers** in this sidecar.

`assets/reference-pin-hero.svg` and `assets/reference-pin-context.svg` are newly
authored profile assets from the user's specified path. They preserve a real
even-odd transparent hole, 116×151/49×64 logical pixels, 68/29px hole design,
1.5px outer stroke and bottom-tip anchor. They are not extracted original SVGs.

Source arclength uses an explicit mean-Earth sphere of radius6371008.8m and an
adaptive line integral **along unchanged linear-lon/lat source edges**. It does
not substitute endpoint great-circle length or projected screen length. Segment
integration tolerance is max(1e-6m,1e-11 relative); the cut is numerically inverted
on the original edge. This is a documented spherical model, not a claim of survey
or ellipsoidal measurement accuracy. Wrapped dateline edges fail explicitly.

The metric's geographic midpoint is fixed before projection. Its screen normal
belongs to the directed source; readable glyph rotation cannot move it to the
other side of the line. Full-track compilation selects the upward side once and
rejects a forced180° readable-text flip, rather than hiding it in a placement
fallback. Source geometry and source hashes are never altered.

## Actual verification performed

Command:

```
node recovery/reference-director-v1/tests/director_events.test.mjs
```

**24 PASS, 0 FAIL, 0 SKIP**. Tests include strict missing/unknown inputs,
reference-observation versus verified source truth, combining/emoji graphemes,
too-long fixed event windows, all546states and window seams, one-shot pin hold,
exact timed glyph beats,70-frame final metric hold, source-edge preservation,
geographic arclength versus latitude-dependent speed, stable metric normal across
89.9°→90.1°, explicit readable-flip refusal, role-specific safe/clip decisions and
transparent-hole SVG structure.

The long-edge regression `[[0,0],[120,60]]` integrates12942077.902159482m under the
documented spherical model. Its half-arclength point is approximately
`[53.58629553545704,26.79314776772852]`; no incorrect arithmetic midpoint is
substituted. An independent reviewer re-integrated the first half and obtained
0.49999999999999944 of the full source arc.

Actual free local Chromium component command:

```
node recovery/reference-director-v1/tools/check_event_components.mjs
```

**PASS**: two SVG rasterizations and three real pinned-font glyph rasterizations.
Native map rendered=false; Studio path executed=false; NVIDIA verified=false.
First sandbox attempt failed at Chromium process creation with EPERM, before
browser execution. The same local-only test then succeeded through the supported
`require_escalated` execution path; no external connection, paid service or GPU
was used. The component image is visibly labeled **COMPONENT UNIT DRAW ONLY**.

Actual pin alpha bboxes: hero[0,0,116,151], context[0,0,49,64]; both hole centers
alpha0. Hero clear integer pixel run66 versus nominal68 (antialiasing at the
circle edge), context29 versus nominal29. Both have actual outer-outline pixels.
`세우타`, `멜리야` and `85 m` have real nonzero glyph alpha coverage, no atlas edge
touch and exact full-word ink centering. Text is a component fixture from supplied
reference observations, not independently verified geography.

Font: existing `web/fonts/NotoSansCJKkr-Bold.otf`, SHA256
`da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0`.
Existing license: `web/fonts/LICENSE_Noto_CJK.txt` (SIL OFL1.1), SHA256
`849f4ea9c214fa4ac3593b770c699f387534b11ce671264c1b10d85bdcb5997b`.
The existing copy `cinematic-world-map/assets/NotoSansCJK-license.txt` has the same
14,712 bytes and SHA; neither file was modified.
The original video's font has not been recovered or asserted identical.

Artifacts: `reports/EVENT_UNIT_TEST_LOG.txt`,
`reports/EVENT_COMPONENT_DRAW.json`, `evidence/EVENT_COMPONENT_DRAW.png`.
These are component/unit evidence, not the requested reference-vs-render image
or substitute Studio MP4. Production remains gated by the protected native
projection hook and missing verified detail geometry/source described elsewhere.
