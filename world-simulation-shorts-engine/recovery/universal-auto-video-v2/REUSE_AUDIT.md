# Universal Auto Video V2: persisted planner and history reuse

This audit reads existing source and completed records at protected parent
`c1e9c099b22a8db1c5f21e7b029422e82f8efd33`. It performs no new historical-data
collection, old full-suite rerun, GPU execution, media rendering or modification
of an existing file. Exact input bytes, SHA-256 values and findings are recorded
in `HISTORY_AUDIT.json`; `HISTORY_CATALOG.json` provides the bounded external
catalog used by the new planner.

## Historical admission

The persisted Korean War fixture can support an **illustrative, fact-based
five-stage infographic** lasting 80 seconds. Its spatial keyframes must remain
the supplied schematic states. It cannot certify daily territorial control,
an archival front reconstruction, exact military unit positions or observed
movement timing. Increasing presentation duration does not create more history.

| Supplied state | Date | Existing geographic meaning |
| --- | --- | --- |
| START | 1950-06-25 | Broad southern held core at outbreak |
| BUSAN | 1950-09-01 | Schematic Republic of Korea / UN Busan perimeter |
| NORTH_ADVANCE | 1950-11-24 | Simplified northern mainland held core |
| SEOUL_WITHDRAWAL | 1951-01-04 | Broad southern withdrawal state |
| ARMISTICE | 1953-07-27 | Approximate final stalemate using simplified present border |

Canonical facts are
`recovery/planner-scene-json-v1/data/FACT_DATA.json`, SHA-256
`753f629a22f8bc2e5676ebdf4d7c9e64edd6a7314188f55cd3ca3237355a9e65`.
The 12 geometry records contain two source countries and five authored held-core
areas with their five matching fronts. The authored inland edges were clipped
against the existing Natural Earth mainland; they are not archival battlefield
lines. The final front is explicitly an approximation using the simplified
present inter-Korean boundary, not the surveyed 1953 Military Demarcation Line.

`SOURCE_REFERENCES.json` names the U.S. Department of State, U.S. Army Center of
Military History and Britannica. Their stored verification basis is curated
review of established chronology. **All three article-body retrievals were
blocked with HTTP 403; original body SHA values are null.** The previous fixture
does not claim it downloaded or reconstructed those historical maps. This task
reuses that honest status and does not repeat the blocked source collection.
The Natural Earth coastline provenance and existing source bytes remain separate
from the historical chronology evidence.

Interpolation between the five keyframes is a visual transition between known
schematic illustrations. An intermediate animation frame must not be labeled as
newly verified exact territorial control on an interpolated historical date.
No additional battle, territorial event or dated state is admitted by this audit.

## Existing implementation to reuse

| Existing component | Actual capability | New integration boundary |
| --- | --- | --- |
| `web/map_infographic_v1/planner_scene_v1.mjs` | `topicIntent`, `validateFactDataset`, `selectFeatures`, `compileScenePlan`, `validateScenePlan`; supplied-data alias and event-family planning | Wrap unchanged functions in the new duration/scene contract |
| Optional `facts.scene_timing` | Exact integer FPS, total frames, context/action/transition/hold timing already supported | Allocate generic duration in an outer adapter; retain legacy defaults |
| Planner engine adapter | Existing Event, Flow, Area and Camera requests from the declarative scene | Reuse existing feature engines rather than create duplicate solvers |
| `planner-night-run-v1` | Optional causal tracks with explicitly schematic direction cues | Do not relabel arrows as historical units or reuse them as historical battle paths |
| `reference-visual-master-v2` | Independent ASTRA/source material, territory style, frontier expression, marker scale and camera profile | Reuse expression components with an independently bound historical scene; its frozen runtime currently derives the modern F scene |
| ASTRA CPU/upload and GPU package | Existing parsing, metadata, masking, caching, upload and hardware guards | Reuse unchanged through the new run profile |
| Detached manager, encoder and storage | Existing one-shot detached lifecycle, common GPU admission/lock, FFmpeg and export verification | Add duration-aware orchestration only; preserve existing job claims/results |

The V2 result record says focused CPU and actual SwiftShader comparisons passed,
including old-F pixel equality at selected frames. Its new NVIDIA run, final
video quality and Dropbox download remain unexecuted. Existing hardware success
in earlier execution paths does not prove the new long-video path or V2 image.

## Natural-language scope

The JavaScript planner is already a deterministic natural-language planner for
supplied facts: it normalizes text, matches externally supplied subject aliases,
recognizes an event family, and rejects an unknown subject with `DATA_REQUIRED`.
It does not call an AI API or invent facts. This is a usable bounded offline
capability and must not be reported as open-ended research or unrestricted AI
topic planning.

The separate `engine/planner.py` is an older offline aviation/shipping/geographic
planner. Its `WAR_VFX` input rule explicitly rejects war requests; an optional
external planner is mentioned only as a contract, without an implemented AI
binding in the audited planners. It is unsuitable for the new Korean War path.
No credential values were inspected by this read-only audit.

## Unit and current-scene evidence

`map-engine-unit-bundle-v1/fixtures/HISTORICAL_UNIT_POLICY.json` supplies historical
era and participation-role gates, including the 48-star U.S. flag and Soviet air
or support roles. It requires location evidence but supplies no actual historical
military unit coordinates. Eligibility alone must not create a new marker or
ground-control claim.

The current 65422 / Reference F scene is explicitly a **modern counterfactual
visual study**, retained by a previous user choice. Its eight modern actors,
modern U.S. flag and Russian tricolor are not Korean War history. Preserve this
old candidate and reuse its visual components, not its fictional occupation
data, dates, actors or positions. The first historical fixture should omit
unverified unit claims; new verified unit data can be admitted later through the
same general source contract.

## Focused actual reuse check

One actual Node call executed the original fact validator, planner and scene
validator with the unchanged persisted five-state facts and an 80-second timing
override: 30 FPS, 2,400 frames, lock 60, initial reveal 36, each transition 567,
final hold 36. The result validated and every supplied geometry remained exactly
equal to the source geometry JSON. This is a **planner-contract capability
probe**, not the selected production rhythm, an 80-second render, an encoding
test, a performance result or a GPU test. No old complete suite was rerun.

## Gaps and safe actions

1. Exact archival/daily fronts: no such data is persisted. Keep schematic
   semantics; exact reconstruction requires a separately verified dated dataset.
2. Historical unit positions: no source evidence is persisted. Keep such markers
   absent; preserve existing actor designs and historical eligibility policy for
   later data-backed use.
3. Arbitrary unknown topics: the current offline catalog cannot research them.
   Return an explicit data-required result, without a fabricated plan. An
   optional AI binding would still require an available authorized service and
   factual source admission.
4. The old source-record normalizer omits `retrieval_http_status` and null
   `original_body_sha256`. Preserve the exact source-reference file path/hash and
   explicit reference-only/no-body status in the **new outer source manifest**.
   Do not modify the old validator or pretend schema validation certifies facts.
5. Long-video production, hardware throughput, provider execution API, billing
   limits and real Dropbox external delivery need separate actual evidence.
   None is established by this read-only history audit.

Required temporary-only source files: **0**. Old files changed by this audit:
**0**. The three audit/catalog files are all in the new recovery namespace.
