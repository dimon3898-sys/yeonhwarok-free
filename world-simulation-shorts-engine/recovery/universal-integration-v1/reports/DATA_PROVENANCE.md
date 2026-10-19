# Supplied data coverage and provenance

This report reuses preserved source evidence. It creates no geographic coordinates, unit positions, dates or historical events, and performs no rendering. `TIMELINE_80S_COVERAGE.json` and `.csv` provide the per-chapter intersections. The source base is `c0f2868e9cab8a269c2bd8552dc09920e5e53863`; the prior handoff containing that audit is `c05ec96933d6e9e28cb96fd27602d82989a3a3e7`.

## What the supplied 80-second plan can show

The V4 plan contains 2,400 frames at 30 fps, 12 narrative chapters and 12 render work segments. Chapters and work segments are different partitions. Both cover `[0,2400)` without gaps or overlap. A separate production geometry clock selects only the five preserved schematic states. Eight dated, approximate, partial UN-front snapshots override that schematic clock during `[1550,2400)`. A source snapshot's scheduled display time does not certify every point along the historical front or every intermediate historical day.

| Chapter | Event | Frames | Partial archival-front hold | Schematic context | Effective schematic crossfade |
|---|---|---:|---:|---:|---:|
| 01 | 전쟁 발발 | `[0,200)` | 0 | 200 | 0 |
| 02 | 북한군 남하 | `[200,400)` | 0 | 200 | 0 |
| 03 | 낙동강 방어선 | `[400,600)` | 0 | 200 | 90 |
| 04 | 인천상륙작전 | `[600,800)` | 0 | 200 | 0 |
| 05 | 서울 수복 | `[800,1000)` | 0 | 200 | 0 |
| 06 | 국군·유엔군 북진 | `[1000,1200)` | 0 | 200 | 0 |
| 07 | 중국군 참전 | `[1200,1400)` | 0 | 200 | 0 |
| 08 | 전선 남하 | `[1400,1600)` | 50 | 150 | 100 |
| 09 | 국군·유엔군 재반격 | `[1600,1800)` | 200 | 0 | 0 |
| 10 | 38선 부근 교착 | `[1800,2000)` | 200 | 0 | 0 |
| 11 | 1951–1953 전선 변화 | `[2000,2200)` | 200 | 0 | 0 |
| 12 | 1953 정전협정 | `[2200,2400)` | 200 | 0 | 0 |

The total is **850 archival scheduled frames (35.4167%) and 1,550 schematic-context frames**. The first 60 context frames are arrival without event-area fill. A chapter title is not proof of a corresponding front. For example, the northward-advance and Chinese-intervention chapters retain the supplied September 1 schematic context until a later explicitly dated snapshot is selected. The January 24 source map is displayed in a chapter with a January 25 event anchor; both dates remain distinct. May 19 is labeled dated pre-stalemate context, not the start of stalemate.

During archival slots, `front_adapter.mjs` supplies `areas: []`. This prevents the nearby schematic polygon from being presented as an observed occupation area. Therefore the final chapter's original schematic transition is suppressed by the archival override. Counting the unused parent geometry schedule as visible occupation movement would be incorrect.

## Existing original sources and limits

| Data | Preserved source | What is admitted | What remains unavailable |
|---|---|---|---|
| Five held-core states | `recovery/planner-scene-json-v1/data/FACT_DATA.json`; source-qualified ownership in `universal-production-v3/history/AREA_OWNERSHIP.json` | Explicitly dated schematic ROK/allied-held mainland core; original geometry retained | Complete bilateral ownership, isolated pockets/islands, exact daily control, opposing complement |
| Eight partial fronts | Army CMH PUB 21–2, *Korea 1951–1953*, GovInfo original SHA `347135bd77e764484251c131db15d733063264a68907752e552cdca9597bcd8d`; preserved `verified-front-data-v4-recovery/FRONT_PROFILE.json` | Reviewed source ink, date, original raster/pixel trace and approximate reference-control registration, limited to supported trace edges | Original source projection/datum, surveyed accuracy, full coast-to-coast line, observed intermediate positions |
| Chronology | Preserved `SCENE_EVIDENCE_CONNECTION.json` and its original chronology review | Event-specific verification status and qualified date/range as already reviewed | Exact Seoul-recapture day and Chinese first-combat day remain unverified from the current retrieved document set; no new claim is made here |
| Native geography | Existing Natural Earth 5.1.1 1:50m country coverage and native city markers | Unchanged geography, projection and land/sea coverage | Military-unit positions are not implied by city markers |

The archival dates are 1950-12-31, 1951-01-24, 1951-02-28, 1951-04-21, 1951-05-19, 1951-06-24, 1951-11-12 and 1953-07-27. The Army map pages are respectively PDF zero-based indices 12, 22, 22, 30, 112, 118, 124 and 286. The source explicitly distinguishes actual UN fronts from attack arrows and operation/withdrawal phase lines. Those excluded markings must not become territorial boundaries.

The reference-control registration residuals range from approximately 2.26 to 4.29 km. They assess the fitted reference model, **not total historical positional accuracy**. The original projection/datum and source map accuracy remain unknown. `PARTIAL_CONTROL_HULL` must not be relabeled full-map or precise survey coverage. The 1953 trace is not an exact Military Demarcation Line.

The prior original-source review establishes official Army map authorship as evidence for US Government work status under 17 USC 105. This is not a blanket public-domain claim for every image in the book; third-party photographs/cartoon material are not republished or needed by this integration.

## ASTRA sources actually supplied

These bounds come from the preserved CPU preparation receipt's `coverage.sourceBBox`, not its tiny CPU test crop. Bounds use `[west,south,east,north]` and EPSG:4326.

| Role | Source/version | Available original sample extent | Native/supplied detail | Existing source hash |
|---|---|---|---|---|
| Terrain | Copernicus GLO-30 AWS 2021; exact release suffix unverified | `[128.2498611111111,37.25013888888889,128.7498611111111,37.75013888888889]` | 1 arc-second Float32 DSM, not bare-earth DTM; PixelIsPoint half-pixel registration retained | `cb9ace49fbd4b5bd5f1cc1313eab728124fe6227eb742f8b0d73b20a2163ff84` |
| Signed elevation/bathymetry | GEBCO_2026 regional subset | `[128,37,130,39]` (floating-point representation in receipt differs by rounding only) | 15 arc-second Int16 cell-center values; mean-sea-level assumption and heterogeneous vertical datum caveat retained | `644fe9c1fbd2ef0284145443f645ddb3d08997b29b52cb1803f7a16d0dc38ea1` |
| Surface texture | NASA BMNG August 2004 via GIBS | `[124,33,132,43]` | Original WMS 1600×2000 image; 0.005° output spacing, nominal source 500 m; PGW/PRJ registration retained | `991c7bdfb8515a787c220b58b066241ac38411721124fbd8e6fae22131c793be` |

The source products are global; these supplied files are regional samples with different support. No claim of global asset coverage or full-scene DEM/depth detail is made. All support and NoData masks remain required. Signed negative elevation alone is not an ocean mask. Existing native GIS coverage separates land and sea, and unsupported pixels retain the existing base material. NoData cannot be converted into a zero-height or zero-depth observation.

The original attribution and license bundle remains in `astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip` (SHA `bd028be93f1813e0ac16628afcd218e95685cedb730b89a6584d196878ead66a`). The prior receipt verified 24 internal hashes; this task reuses that result and does not repeat all archive hashing or parsing. Copernicus attribution/modified-data notice, disclaimer and license propagation; GEBCO attribution/non-navigation disclaimer; and NASA Earth Observatory/GIBS credit and non-endorsement notices remain necessary. No new license assumption is introduced.

## Checks actually executed in this task

- Rehashed the preserved V4 plan, parent plan, front profile, front manifest and scene-evidence receipt; checked cross-referenced profile/manifest/parent hashes.
- Checked all eight profile GeoJSON hashes against the existing source manifest and confirmed their tracked paths. This is a manifest/path check, not a fresh byte rehash of every derived GeoJSON.
- Rehashed the preserved CPU preparation receipt and matched its existing source-asset manifest entry.
- Matched all three recorded original sample hashes to the prior archive integrity receipt. No full original archive reparse or repeat of its 24-member verification was performed.
- Ran nine focused CPU tests covering both timeline partitions, archival override, source/event date distinction, gaps, overlaps, future-source rejection, no-history-inference policy, regional coverage limits and no render permission.

All exact current input hashes and metadata-binding results are in `TIMELINE_80S_COVERAGE.json`. The generic `build_coverage` function reads supplied objects only; it does not contact a source, start a job or infer history. Omitting optional asset metadata or chronology evidence yields `NOT_VERIFIED` instead of inventing a successful check.

## Missing data and next safe action

`HISTORICAL_BLOCKERS.json` separates complete bilateral ownership, historical unit tracks and observed continuous front transitions. It identifies the minimum evidence needed and already-approved official source candidates. Those URLs are suggestions for a bounded follow-up, not a claim they were newly retrieved or contain ready-to-use coordinates. The present CPU integration must not silently substitute modern counterfactual flags/units, close partial lines into occupation polygons, or interpolate unobserved daily history.

Camera, ASTRA, SFX and front implementations can be selected as supporting modules while their rendered appearance remains `NOT_VERIFIED`. The supplied base plan is silent; its 12 chapter event IDs already supply a safe frame-bound SFX scheduling contract when SFX is explicitly enabled. No historical units, routes or battle effects can be meaningfully placed without additional source-backed event geometry.

The actual 80-second MP4 was not available among this audit's attached/source media inputs. Existing evidence establishes prior reference/65422 decoding, not the current 80-second picture. No new 5-second candidate, SwiftShader draw or NVIDIA output was generated. The 80-second render and FINAL promotion remain blocked until the separately controlled reference-comparison and user-quality approval gate succeeds.
