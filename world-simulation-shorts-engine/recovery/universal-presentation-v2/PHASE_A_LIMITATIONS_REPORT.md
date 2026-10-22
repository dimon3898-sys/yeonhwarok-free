# PHASE A — current limits and actual connection points

Baseline: `b0d013832ee38571f9d3dfe685ce63f7083ba90f`.
Branch: `development/universal-presentation-v2-20261022`.

The original307 protected hashes and all6,439 baseline tracked file hashes match. The two preceding worktrees and565 existing private cache metadata entries were also captured and remained unchanged after the actual298 baseline tests. No existing implementation is edited by this audit.

## Confirmed causes

| Limit | Existing code / evidence | Required separate extension |
|---|---|---|
| Free prose is rejected | `universal-data-pipeline-v1/prompt_pipeline.mjs`, `parsePrompt`: `FREE_NATURAL_LANGUAGE_NOT_SUPPORTED` | A bounded, honest natural-language intent/entity adapter over supplied data; not a claim of an existing unrestricted AI. |
| Earlier natural-language planner is catalog/subject limited | `universal-auto-video-v2/planner.py`, `parse_request`, `_entry`, `_timing` | Reuse useful parsing behavior and the native generic Planner. Do not route arbitrary supplied topics through a WAR-only catalog. |
| Five region IDs are hard admission limits in the old preview | `universal-data-pipeline-v1/prompt_pipeline.mjs` `REGIONS`; `capture_generic.mjs` `SOURCE_REGIONS`; `studio_adapter.py` `REGIONS` | A new opt-in source catalog and independent coverage gate. The old profile must continue rejecting unsupported old inputs; no fake registered-region fallback. |
| Camera stays fixed despite native motion support | `universal-data-pipeline-v1/generic_runtime.mjs` evaluates the final V5 frame and reuses its bounds | Connect the existing reference camera keyframe adapter and current native projection through a versioned presentation sidecar. |
| Existing Flow's camera admission is locked | Native Flow/Event readiness requires a genuine locked/settled camera | Keep original behavior intact. A moving-camera composition requires its own explicit current-projection safety checks and must not forge old camera lock flags. |
| Area and route pixels already exist | The old generic runtime calls existing Area V3 and Flow V2 plans/passes | Reuse those engines, rather than adding a second territory or route renderer. |
| Other Planner families are not automatically pixel-connected | Existing Planner supports LINE_METRIC/DISASTER, but the bounded data preview does not consume them | Keep unsupported capabilities explicit until actually connected; distinguish historical source gaps from this engine connection limit. |
| A named full terrain file is not materialized | `library/flat/terrain/NE1_HR_LC_SR_W_DR.tif` is an actual134-byte LFS pointer, not the referenced699,969,932-byte raster | Reuse verified existing native raster crops and separately qualified actual global imagery. Do not report pointer metadata as available high-resolution terrain. |
| Studio persistence has a serialization constraint | Original strict Scene validator compares canonical geometry member order; prior wire-string fix already exists | Preserve Scene wire strings and semantic/wire hashes across private canonical storage, including multi-scene requests. |

The new natural-language input must distinguish extracted intent from authoritative attached facts. It may derive presentation parameters from supplied geometry under declared defaults; it may not invent coordinates, history, ownership or evidence. Ambiguous/missing input must produce concrete clarification fields.

The regional extension must select a single qualified source covering the whole camera envelope. Different source styles and resolutions must be reported honestly. A global RGB image is not an elevation model, bathymetry, or a materialized NE1 hills raster. Out-of-coverage, unsupported projection and resource-limit requests must be explicit errors.

Real scene transitions must switch actual supplied Scenes at exact half-open timeline boundaries. Area state changes inside one Scene are not a substitute for that capability. Original authentication, CSRF, Origin, private claims and paid-execution restrictions remain in force.

## Reused evidence and limits

The retained31.8-second reference file is available as actual MP4 bytes. Its current SHA, full decoding and factual scope are recorded separately in `reports/REFERENCE_ACCESS.json`; the prior detailed chronological analysis is reused without claiming a second full manual review. It is a modern hypothetical scenario, not a historical Korean War source.

The audit establishes causes and integration targets, not implementation or video-quality PASS. See `NL_LIMITATIONS_AUDIT.md`, `STUDIO_CONNECTION_AUDIT.md` and the forthcoming source/presentation reports for component detail. No paid API, GPU run, deployment,80second film or FINAL promotion is part of this work.
