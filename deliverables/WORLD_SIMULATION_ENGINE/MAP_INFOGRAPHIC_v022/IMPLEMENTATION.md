# World Engine map infographic v022

The new, opt-in map infographic layer draws verified country and event geometry,
keeps location markers and semantic state visible after their intros, and assigns
one shared layout to map text. It does not change the approved 24-second camera
loop or the v018/v019 Earth materials. Technical admission and final video quality
are separate results. NVIDIA production frames and human quality approval are
NOT_RUN in this development session.

## Source and input identity

- Protected source baseline: `b88ec3e26d45c1709bf7496cbaed4e220a14628c`.
- Immutable public runtime baseline: `gcube-v021-story-progression`, digest
  `sha256:2f68a880afdc56a5d3b9dc5ab52c2a87100316048d5d863e712654fee789a9dc`.
  Its public registry manifest and OCI revision were rechecked before use.
- REFERENCE SHA256:
  `853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc`.
- CURRENT SHA256:
  `1fc3e4bdc8f393e0363dde259649337633bfad752e15a41660f65eae2581d7c4`.
  CURRENT's generating image and commit remain UNCONFIRMED. It is not labelled
  as an executed v021 output.
- Both inputs were fully decoded. Reference phone chrome and frames 575–634
  are excluded from normalized map comparisons. See BASELINE_VIDEO_ANALYSIS.md,
  INPUT_CAPTURE_RECEIPTS.json and PIXEL_MEASUREMENTS.json.

## CODE changes

| Module | Implemented behavior |
|---|---|
| `engine/infographic_contract.py` | Versioned, source-pinned geometry/event/font/schema contract; native feature identity, claims, hypothetical watermark, selected-plan admission and diagnostic provenance |
| `engine/infographic_planner.py` | Explicit new 24-second QA family and separate measured Production builder; legacy OFF and explicitly selected old profile retain the original plan |
| `web/infographic_adapter.js` | Polygon/MultiPolygon fill with holes, screen-width boundaries, native multipart lines, seam/horizon/near-plane clipping, state transitions, persistent marker and shared four-role layout |
| `web/render_infographic_earth.html` | Original v021 QA renderer beneath the new overlay; explicit Production regional consumer reuses v018/v019 installers; one text owner |
| `engine/infographic_backend.py` | Validates the selected actual Scene and changes only the render page; existing Chromium wrapper, GPU-required transport, JPEG and FFmpeg lifecycle remain in use |
| `engine/infographic_framing.py` | Optional, explicitly selected native-geometry Local-Close over the existing spherical solver; Point geometry cannot manufacture an extent; subtitle/text safe areas are reserved |
| `engine/semantic_timeline.py` | Authored Script → actual sentence synthesis → decoded PCM measurement → integer-frame visual allocation; original mixer/subtitles reuse that measured voice without resynthesis |
| `engine/infographic_qc.py` | Requires actual source-bound frame receipts, visible geometry/state/text/watermark; retains original GPU/video/assets/clipping/audio failures; missing audits return QC failure |
| `engine/qa_planner.py`, `engine/pipeline_stability.py` | Additive selection and pipeline hooks; selected source records flow into existing Diagnostic ZIP; existing saved plans are not migrated |
| `deployment/gcube/infographic_preflight.py` | Frozen-source/asset/license/HTTP admission, legacy/native/CPU-pixel/measured-audio checks and full new container preflight |

`WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION=v022` is the new image's default. Its
24-second HIGH request selects `MAP_INFOGRAPHIC_QA_V022`. An explicit
`SECOND_EVENT_ADAPTIVE_WIDE_TEST` still selects the protected old camera fixture.
The separate `MAP_INFOGRAPHIC_PRODUCTION_V022` family is constructed from an
authored, source-bound script through `generate_production_infographic`; it does
not overwrite the fixed QA or legacy Production presets.

## DATA and license changes

The registry contains 542 verified records from six source families. Existing
Natural Earth countries, location catalog, OurAirports and maritime source
records are reused. EPSG:4326 longitude/latitude and native topology are preserved.
Every registry record carries feature identity, source/version/hash, license and
geometry role. Server data and browser data are identical, audited mirrors.
For catalog Point records, the feature hash identifies the preserved catalog
entry named by `provenance.selector`; the separate source-file hash identifies
the original upstream file. All 291 catalog coordinates were also compared
directly with those raw sources. Native country and canal feature hashes
identify the actual extracted source features.

Only two new geographic features were extracted: Natural Earth's native Suez
river and lake-centerline features. They contain 26 source vertices in three
native parts. The source gap is preserved; no interpolated canal bank, traffic,
obstruction, joining line or inferred event area is generated. Natural Earth
`10m` here means **1:10,000,000 cartographic scale**, not 10-metre survey accuracy.
The full world rivers dataset is not included. The representative
`LOCATION_SUEZ_CANAL` remains a Point and is never treated as a canal line.

Licenses packaged with source receipts:

- Natural Earth: public domain, including reused countries and new canal subset.
- Existing OurAirports records: PDDL 1.0 notice.
- Existing searoute 1.6.0: Apache-2.0 with existing attribution and license.
- Actual Noto Sans CJK Korean Bold 700, extracted from the installed source TTC:
  SIL OFL 1.1. Existing Regular 400 is unchanged. No synthetic font weight.
- Existing MASTER/LOD texture provenance and CC BY notices are retained.

No reference graphics, country colors, wording or icons were extracted. No AI,
OSM, invented geometry, random city data or replacement global texture was added.

## QA event and lifetime mapping

The original 720 camera samples, target/FOV and timeline remain unchanged.
New geometry consumes only authored Scene facts and states:

| Frames (end exclusive) | Semantic state | Verified geometry and persistent information |
|---|---|---|
| 0–60 | Existing WIDE | Clean original map |
| 60–180 | Suez location | Egypt context polygon and Suez representative marker/location text |
| 180–330 | Hypothetical CANAL CLOSED | The two native canal features change to CLOSED; location marker and secondary Egypt context persist |
| 330–450 | Hypothetical CANAL OPEN | Same canal geometry changes to OPEN before the original zoom-out; persistent context remains |
| 450–720 | Singapore location/view | Verified Singapore country polygon and catalog location marker/text; no fabricated Singapore event |

Both canal states display `가정 시나리오`. Egypt's country polygon is context,
not a claimed country-wide closure. Introduction motion is separate from lifetime:
marker pop lasts nine frames at 30fps while markers persist through their source
event windows, then fade. Letter reveal uses the existing motion functions;
steady local halo and readable text remain afterwards. Primary moving effects
are limited to one; persistent state is counted separately. There is no repeated
pulse, whole-country stroke animation, count-up, particle effect or extra sound.

## Shared layout and measured Production

EVENT_TITLE, LOCATION_LABEL, SUPPORT_DATA and TTS_SUBTITLE have explicit sizes,
real font weights, roles, lifetimes and safe areas. Grapheme-safe reveal keeps
indices through wrapping. Layout prevents duplicate old overlays, marker/text
collisions and offscreen-anchor clamping. The existing FFmpeg subtitle renderer
remains the sole subtitle owner, with its reserved two-line region.

Production timing is measured per sentence from decoded PCM. It reports
`sentence_synthesis_measured_pcm` and `measured_utterance_window_only`; it never
claims word alignment. Claim/source/target/event links are validated against the
authored script. Variable Scene boundaries derive from the original frame-grid
allocator after measurement. Actual ESpeak → original audio mixer → ASS subtitle
checks are performed with the packaged provider, without substituting a silent
WAV or synthesizing the script a second time.

Final whole-pipeline admission found two additional defects in the new measured
path. The inherited loudnorm output `-t` could stop before its delayed EOF tail
flushed: the actual 253-frame fixture produced 401,600 samples instead of
404,800. Only the new wrapper removes that output-time stop and trims the flushed
output by its actual sample clock. The original overlapping PCM is bit-exact;
the missing tail is retained without added silence. The protected audio.py is
unchanged. Actual WAV duration/hash/sample count are persisted and validated.

The new helper also persists the original `audio_report.json` and
`subtitle_report.json` handoff before rendering. This prevents an already created
ASS file from being opened a second time. Cached reuse binds the exact plan,
script, voice, physical mastered WAV and ASS; changed or incomplete checkpoints
are rejected without overwrite. An integration test traverses real COLLECT_ALL
and the original renderer up to the admitted backend, then stops at an explicit
test-only no-GPU transport boundary. Its retry cannot remix, resynthesize or
rewrite subtitles. AAC presentation/decode padding is recorded separately from
the exact PCM source clock; a technical synthetic MP4 does not prove map quality.

Native geometry fit uses the existing Adaptive Wide/spherical projector and is
explicitly scoped to the new Production family. The existing Suez/Singapore LOD
textures and material code are reused. Uncovered locations explicitly report
`NO_LOCAL_LOD`; they do not acquire invented high-resolution detail. The inherited
four-texture upload budget is audited rather than advertised as a new atlas.

## Evidence and release admission

Protected v021 runtime bytes and original test IDs are pinned. All newly selected
runtime/data/font/license/test bytes are frozen in
`deployment/gcube/infographic_release_manifest.json`. The workflow builds from the
verified base digest, tests the complete container, and publishes only an absent,
commit-specific `gcube-v022-map-infographic-<12-character-source-SHA>` tag. Source
HEAD is checked again before publication. Existing release tags and latest are
not overwritten.

Native adapter checks compare all 720 QA poses/material/OFF draw operations;
CPU Chromium Canvas2D captures measure actual font ink and clipping/topology.
These captures are overlay test pixels, **not NVIDIA map BEFORE/AFTER renders**.
BEFORE_AFTER_FIXTURES.json keeps the actual GPU AFTER side explicitly NOT_RUN.
Measured Production fixtures also exercise native geometry, covered regional
LOD and an uncovered location. Synthetic encoder/A/V patterns, when present,
test the output pipeline and are never submitted as map-quality evidence.

Final RELEASE_VERIFICATION.json records the exact immutable source/tag/digest,
executed test inventory and container/public-pull checks after publication.

## Next actual GPU test

Do not start gcube during implementation. After the new image's release receipt
is complete and the user authorizes an RTX4080S session, use the MASTER's
sequence in that single session: the protected 24-second
`SECOND_EVENT_ADAPTIVE_WIDE_TEST`, the separate same-camera infographic OFF/ON
pair, then the packaged source-backed measured Production fixture. The new
default 24-second HIGH Suez request selects the infographic ON family; the
explicit old preset and `map_infographic=False` retain the old baseline. Keep
`NVIDIA_DRIVER_CAPABILITIES=all` and `WORLD_ENGINE_RENDER_MODE=gpu-required`.
Check persistent Egypt/Suez/Singapore context, canal CLOSED→OPEN state on the same
native geometry, event-first text hierarchy, steady halo and marker persistence.
Download the MP4 and Diagnostic ZIP before stopping the ephemeral Workload.

Actual NVIDIA overlay/shader quality, depth/LOD interaction, GPU memory/time,
human text/map readability, final voice quality and direct audio listening still
require real output review. No 75/80-second Production GPU render is authorized
by this development task. PWA, web brightness and web redesign remain deferred.
