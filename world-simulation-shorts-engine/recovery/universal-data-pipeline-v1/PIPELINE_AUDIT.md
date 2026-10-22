# Existing data pipeline audit — PHASE A

Baseline: `e39969cbc76a071d34a38440d9551425e6d5e545`. This audit reads actual local code and saved source artifacts. It does not render, deploy, call a paid API, change a protected source, or declare visual quality PASS. The parent process owns the required 307-file integrity gate; this report is not a substitute for it.

## Actual execution paths

1. **Legacy Studio production**: `production-studio-mvp-v1/server.py:326-353` → injected controller `preflight/submit/start` → `studio_contracts.normalize_submission` → `studio_runtime.bind_render_image/validate_render_plan` → original profile-specific orchestrator → cached segments → FFmpeg → Studio SFX/finalization/export. The HTTP server keeps owner authentication, CSRF and effective-Origin checks (`server.py:224-239, 293-318`). Construction, GET, validation or reconnect do not start rendering.
2. **V2 / completion**: `universal-integration-completion-v2/studio_controller.py:34-36` → completion contract → preserved V2 contract → V1. The original Scene remains unchanged and presentation sidecars select an independent runtime. V2 is explicitly bound to one V4 archival80s preset, not arbitrary topic support.
3. **Generic core planning**: supplied `PLANNER_FACTS_V1` → `validateFactDataset/topicIntent/selectFeatures/compileScenePlan` in `web/map_infographic_v1/planner_scene_v1.mjs` → `PLANNER_SCENE_JSON_V1` → `compileExistingEnginePlan` in `planner_engine_adapter_v1.mjs`. The generic core already understands TRANSPORT, LINE_METRIC, DISASTER and WAR. A contract compilation alone does not prove every family has a Studio pixel consumer.
4. **Old offline natural-language wrapper**: `universal-auto-video-v2/planner.py` parses output intent, then selects a server catalog. The actual default catalog has only KOREAN_WAR and `_timing` requires WAR. Thus the bounded natural-language wrapper is narrower than the existing generic JS core.
5. **Source/G2 review**: authenticated Studio source controller → server-pinned source bundle → `SourceRegistry` → original AreaV3 validation/GEOS control compilation → explicit frame package → detached software worker → actual native map factory/Area/CameraV5 capture → FFmpeg/full decode/SHA → private result. G2 final recovery adds generic bounded label placement but intentionally still accepts only the frozen nonhistorical180f DEMO.

## Stage classifications and concrete evidence

| Stage | Classification | Code | Evidence / failure |
|---|---|---|---|
| studio_input | PARTIAL | `world-simulation-shorts-engine/recovery/production-studio-mvp-v1/studio_contracts.py:77` | Structured JSON/fenced JSON parser, duplicate-key and finite-number checks; free prose is explicitly rejected. `STUDIO_STRUCTURED_PROMPT_REQUIRED` |
| studio_direct_scene | IMPLEMENTED | `world-simulation-shorts-engine/recovery/production-studio-mvp-v1/studio_contracts.py:151` | Direct sceneJson bypasses reinterpretation; preserved backend binding and validation remain required. `STUDIO_RENDER_PLAN_REJECTED` |
| studio_v2_prompt | TOPIC_PRESET_BOUND | `world-simulation-shorts-engine/recovery/universal-integration-v1/contract_v2.py:72` | V2 prompt lowers to V1, admits only VERIFIED_FRONT_V4_80S, V4_ARCHIVAL_80S, duration80; sceneJson+V2 forbidden. `STUDIO_V2_PRESET_REQUIRED` |
| completion_sidecar | IMPLEMENTED_BOUNDED | `world-simulation-shorts-engine/recovery/universal-integration-completion-v2/contract_v2.py:119` | Optional camera/frontier/eventFlow sidecar, no new source trust; delegates V1 unchanged. `STUDIO_COMPLETION_FIELD_UNSUPPORTED` |
| offline_nl_request | PARTIAL | `world-simulation-shorts-engine/recovery/universal-auto-video-v2/planner.py:40` | Parses bounded topic/duration/fps/resolution; no external AI and no arbitrary fact extraction. `INVALID_TOPIC` |
| offline_catalog | TOPIC_DATA_BOUND | `world-simulation-shorts-engine/recovery/universal-auto-video-v2/planner.py:114` | Catalog contains only KOREAN_WAR. Other subjects rejected before rendering; WAR-only long timing allocator. `FACT_CATALOG_TOPIC_REQUIRED` |
| fact_validator | IMPLEMENTED | `world-simulation-shorts-engine/web/map_infographic_v1/planner_scene_v1.mjs:194` | Existing source/mode/geometry validator, four event families, calls protected Event/Flow/Area validators. `DATA_REQUIRED` |
| scene_compiler | IMPLEMENTED | `world-simulation-shorts-engine/web/map_infographic_v1/planner_scene_v1.mjs:417` | compileScenePlan supplied facts -> deterministic PLANNER_SCENE_JSON_V1; validateScenePlan is authoritative compatible API. `PLANNER_FACTS_VERSION_REQUIRED` |
| engine_plan_compiler | IMPLEMENTED_BOUNDED | `world-simulation-shorts-engine/web/map_infographic_v1/planner_engine_adapter_v1.mjs:75` | compileExistingEnginePlan emits Flow/Event/Area/Wave plans for all four families; contract success is not actual pixel proof. `PLANNER_EXISTING_ENGINE_BINDING_REQUIRED` |
| area_only_runtime | DISCONNECTED_FOR_OTHER_FAMILIES | `world-simulation-shorts-engine/recovery/planner-scene-json-v1/planner_runtime.mjs:12` | Existing fixture-backed capture uses compileSceneEngineRequest and createAreaGpuAdapter, not general route runtime. `PLANNER_EXISTING_AREA_SCENE_CONTRACT_REQUIRED` |
| long_timeline | IMPLEMENTED | `world-simulation-shorts-engine/recovery/universal-auto-video-v2/contracts.py:157` | split_plan/validate_plan enforce exact half-open ranges, frame sums and boundary identity; not generic source admission. `SCENE_GAP_OVERLAP_OR_RESET` |
| studio_production_backend | TOPIC_PROFILE_BOUND | `world-simulation-shorts-engine/recovery/production-studio-mvp-v1/studio_runtime.py:83` | V4 exact source-parent equality; V3 frozen chronology/source validation. Existing durations80/120/180/300/600. `STUDIO_V4_SOURCE_PLAN_CHANGED` |
| source_scene_normalizer | IMPLEMENTED_SERVER_BOUND | `world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/source_contract.py:71` | Exact server-index/bundle bindings, source rights/SHA, actor palette, up to240 frames; new prompt cannot register sources. `SOURCE_SCENE_BINDING_MISMATCH_*` |
| control_source_registry | IMPLEMENTED | `world-simulation-shorts-engine/recovery/studio-integration-gates-v1/control_provider.py:110` | Server-pinned SourceRegistry and compile_control_state reuse protected Area V3 and GEOS; no complement ownership inference. `CONTROL_SOURCE_ROLE_NOT_QUALIFIED` |
| source_pixel_consumer | PARTIAL_SYNTHETIC_ONLY | `world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/native_runtime.mjs:25` | Actual factory, Area passes and CameraV5 reusable; current runtime requires bounded owner/front frames, synthetic caption, local frame indices. `UNIVERSAL_SOURCE_FIELD_CLOCK_MISMATCH` |
| g2_final_contract | INTENTIONALLY_FIXED_DEMO | `world-simulation-shorts-engine/recovery/g2-final-recovery-v1/source_contract.py:69` | Delegates exact original180f nonhistorical DEMO then adds only trusted generic label placement; must remain immutable. `G2_RECOVERY_UNCHANGED_DEMO_SCENE_REQUIRED` |
| g2_layout_extension | IMPLEMENTED_REUSABLE | `world-simulation-shorts-engine/recovery/g2-final-recovery-v1/source_contract.py:48` | apply_layout_profile(runtime_payload) independently adds bounded generic placement policy without replacing geometry/camera. `G2_FINAL_SERVER_LAYOUT_PROFILE_REQUIRED` |
| studio_auth_http | IMPLEMENTED_REUSABLE | `world-simulation-shorts-engine/recovery/production-studio-mvp-v1/server.py:224` | Owner authentication, CSRF and effective-Origin policy; injected controller handles preflight/submit/start/status/results. `STUDIO_PREFLIGHT_BLOCKED` |
| studio_source_worker | IMPLEMENTED_REUSABLE | `world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/studio_controller.py:165` | Explicit owner consent, idempotent private claim, active lock, detached software worker; admission900sec max0 retries. `STUDIO_OWNER_CONSENT_REQUIRED` |
| video_and_result_validation | IMPLEMENTED | `world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/software_worker.py:66` | Full capture frame count, fullDecode and video SHA checked before COMPLETED; no NVIDIA or user approval claimed. `STUDIO_SOURCE_CAPTURE_INCOMPLETE_OR_CHANGED` |
| generic_validation_outcomes | MISSING_AT_BASELINE | `world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/source_contract.py:157` | Existing per-module fail codes and ready/blockers lack one shared PASS/NEEDS_INPUT/CONFLICT/UNSUPPORTED/INVALID response contract. `NOT_IMPLEMENTED` |
| generic_prompt_data_compiler | MISSING_AT_BASELINE | `world-simulation-shorts-engine/recovery/production-studio-mvp-v1/studio_contracts.py:173` | No one topic+supplied-data prompt lowering all requested history/fiction/general topic inputs to an actually selected Studio runtime. `STUDIO_PROMPT_FIELD_UNSUPPORTED` |

## Confirmed G3 blockers are different kinds of gates

- **EXPLICIT_POLICY — CONFIRMED**: `g2-final-recovery-v1/studio_controller.py:30-46`. historicalG3 must remain BLOCKED and paidGpuExecuted false; source synthetic recovery cannot authorize history.
- **FIXED_DEMO_CONTRACT — CONFIRMED**: `g2-renderer-recovery-v1/source_contract.py:59-72`. Exact DEMO equality and180f restrictions reject arbitrary replacement prompts before scene compile. This is intentional recovery scope, not a parser defect.
- **SOURCE_EVIDENCE_GAPS — CONFIRMED_PARTIAL**: `studio-integration-gates-v1/fixtures/INCHEON_SOURCE_GATE.json`. Dates and8 official PDF page-position paths exist; full dated bilateral owner masks, georegistrationGCP/heldout residuals, eventROI, transition correspondence not source-qualified.
- **PIXEL_CONSUMER_ADMISSION — CONFIRMED**: `universal-source-pipeline-v2/source_contract.py:152-155`. Historical branch unconditionally appends SOURCE_HISTORICAL_PIXEL_CONSUMER_NOT_ADMITTED even if data become available.
- **INTEGRATION_IMAGE_QUALITY_GATES — CONFIRMED_CODE_PATH**: `universal-integration-v1/runtime_bridge.py:92-133`. Data blockers, registered image equality, real operator budget and full-video quality approval are separate gates; no current image inspection in this audit.
- **ALL_DATA_LOST — RULED_OUT_AS_GENERAL_CLAIM**: `universal-source-pipeline-v2/source-review/CMH_UN_OFFENSIVE_PDF008_POSITION_PATHS.json`. Actual preserved source-position artifact contains8 paths; June28 partial front and3 official-source catalog rows exist. Incomplete ownership evidence must not be mislabeled total data loss.
- **NEPAL_LAYOUT — RULED_OUT_AS_HISTORY_BLOCKER**: `g2-final-recovery-v1/layout_adapter.py`. Layout recovery is separate from historic source qualification. Current task starts from finalG2 recovery, preserves placement adapter.

The existing historical source preflight records `framesAvailable: 0` for the admitted **complete bilateral control-frame** package. It does not mean that all historical material is absent. The preserved Incheon page artifact has eight dated open source-position paths; the official-source gate lists three source publications; a June28 partial front has three parts/19vertices with approximately3.66km maximum held-out generalized-locality fit error. It explicitly lacks a full owner mask and is ineligible as an Incheon fallback. Date labels, source hashes, modern GIS locality and observed unit-position lines must not be promoted to complete historical control polygons.

`control_provider.validate_g2_history` (`:489-522`) deliberately binds frozen source evidence and calls endpoint preflight with missing admitted endpoints; a client-supplied ready flag cannot fix that. A new data workflow may truthfully validate usable small inputs while keeping unproved historical scenes blocked. It must not relabel the existing G3 gate PASS.

## Read-only probes actually executed

The following Python invocation imported only the existing planner and inspected its default catalog. It called `parse_request` then `_entry`; no Scene was saved, no controller was instantiated, no renderer was started:

```text
python -B (import planner; load HISTORY_CATALOG; parse_request(text); _entry(topic,catalog))
```

| Input family | Actual result |
|---|---|
| World airline network | FACT_CATALOG_TOPIC_REQUIRED |
| World trade | FACT_CATALOG_TOPIC_REQUIRED |
| Roman Empire | FACT_CATALOG_TOPIC_REQUIRED |
| User fiction war | FACT_CATALOG_TOPIC_REQUIRED |
| Korean War | Recognized KOREAN_WAR; AVAILABLE_SCHEMATIC_ONLY |

This proves the default wrapper's catalog limit. It does not prove that the generic core cannot process supplied facts for those families.

## Reusable extension points

- Reuse `studio_contracts._parse_json` for duplicate-key, finite JSON and4MiB checks. Keep old `normalize_submission` delegated unchanged for old inputs.
- Add a new opt-in data schema/profile and a new controller subclass in the new namespace. Never widen `G2_RECOVERY_UNCHANGED_DEMO_SCENE_REQUIRED` or change old StudioV2's exact preset policy.
- Lower validated supplied inputs to existing `PLANNER_FACTS_V1`; call `compileScenePlan({topic,facts,output})` and `validateScenePlan`. Call `compileExistingEnginePlan` to choose existing Flow/Event/Area plans. Do not call Area-only `compileSceneEngineRequest` on a route-only Scene.
- Reuse G2 final `apply_layout_profile(runtime_payload)` / trusted layout module alias, G2 source-native NE1 coverage policy and unchanged map factory. Keep original raster coordinates, source licensing and hashes.
- Reuse actual authenticated HTTP routes and source Studio consent/idempotency/private-claim/detached-worker pattern. A new profile must remain explicit free software review, bounded frames, zero paid authority, unique job/capture identity.
- Existing `createFlowGpuAdapter` / `createFlowGraphicPass`, `event_gpu_pipeline_v1` / `visual_event_gpu_adapter_v1`, Area overlay and CameraV5 may be selected by a small independent composition adapter. Do not copy the full renderer. The source runtime's synthetic-only caption and bilateral field assumption cannot represent a general airline/trade topic without an honest separate adapter.
- A unified validation outcome object with PASS/NEEDS_INPUT/CONFLICT/UNSUPPORTED/INVALID, per-scene blockers, field examples and source-to-Scene trace is missing at baseline. Validation success must remain separate from source authority, hardware admission and user visual approval.

## Scene compatibility and unsupported scope

- Old Scene schema is `PLANNER_SCENE_JSON_V1`, validated by the unchanged exported `validateScenePlan`. Geometry/source references, semantic mode, camera ownership, exact integer timing and engine feature arrays are enforced there. It is not the same schema as `WORLD_ENGINE_UNIVERSAL_SOURCE_SCENE_V2`.
- Long-video wrapper schema is owned by `universal-auto-video-v2/contracts.py`; it preserves `legacyScenePlan`, exact half-open segment ranges, hashes and boundary continuity. Existing StudioV1 chooses80/120/180/300/600s; V4 preset specifically remains80s.
- Source review schema's JSONSchema is structural only (`SOURCE_SCENE_V2.schema.json:4`); actual normalizer additionally pins exact sources and requested values. It is capped at240frames/8s, fps30 and1080×1920.
- G2 final normalizer is a deliberately narrower180f nonhistorical recovery profile. Its scope remains unchanged.
- Existing V1 time-interval revisions are SFX-only (`studio_contracts.py:233-258, 261-343`). Do not advertise arbitrary visual revision from prose as implemented.
- Unsupported natural language, unknown prompt fields, missing source evidence, missing object graphics, invalid coordinates and time-order errors must stay explicit errors. A source citation or user-provided VERIFIED string is not historical ground-truth verification.
- No image was pulled or inspected in this audit. Runtime source inclusion and active gCube settings are UNVERIFIED here; parent must use actual manifests/CI evidence for any image claim.

## Audit limits

No protected implementation source was changed by this audit. No new video, GPU verification, image build or visual-quality decision is claimed. The full143test suite and protection hash result belong to the parent task and are not fabricated here. Missing historical facts remain missing; no invented coordinates, owners, fronts or routes were added.
