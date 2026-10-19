# Planner and Scene contract audit

Source snapshot: `c0f2868e9cab8a269c2bd8552dc09920e5e53863`. Current image: Studio proxy `8ef393d3…`, not the later mandatory-Dropbox image. This audit reads sources, bound public fixtures and image manifests. It does not start a renderer, access private jobs, change a Scene, or verify the current 80-second visual output.

## What ChatGPT can safely request today

The current Studio takes a structured JSON prompt or an explicit long-video Scene JSON. It does **not** pass a free-form production request to the offline topic planner. The working preset is `VERIFIED_FRONT_V4_80S`, selected with profile `V4_ARCHIVAL_80S`. Title and Studio SFX settings are submission controls; arbitrary camera, material, territory or marker instructions are not preset controls.

There are two separate Scene contracts:

1. `PLANNER_SCENE_JSON_V1` is the existing portable legacy plan produced by `compileScenePlan({topic,facts,output})`. It contains `metadata`, `beats`, `geometries`, family-specific records, `camera_intent`, `scale_intent`, `timing` and `source_notes`. It is not directly accepted as a Studio long Scene.
2. `WORLD_ENGINE_UNIVERSAL_VIDEO_V2` wraps that plan as `legacyScenePlan`. It adds `durationSeconds`, `fps`, `totalFrames`, output format, source/native/render identity, global work scenes, and production metadata. Studio accepts the wrapper through `sceneJson` and independently binds the image and validates the production profile.

The real Studio profile discriminator is the **sibling `profile` field**, since both V3 and V4 raw plans use `WORLD_ENGINE_UNIVERSAL_VIDEO_V2`. `SCENE_JSON_CONTRACT.schema.json` models the existing direct submission object and exposes `$defs/rawScenePlan`, `$defs/productionPlan`, `$defs/v4FrozenPlan` and `$defs/legacyScenePlan`. The `x-runtime` rules are mandatory: JSON Schema alone cannot reproduce file-hash checks, complete frozen-plan equality, native binding, authorization or GPU admission.

## Current V4 is frozen, not freely editable Scene control

`studio_runtime.py:101–118` first verifies that a supplied V4 Scene is the exact expected execution plan at its supplied image identity, then safely rebinds the current image. `scene_binding.py:67–115` requires the immutable parent file hash and whole-plan equality after adding the installed archival profile/manifest hashes and regenerated work-scene identities.

Consequences:

- V4 is exactly 80 seconds, 2,400 frames, 1080×1920 and 30 fps.
- Editing a camera profile, visual profile, territory, marker, timeline, source identity, or an unrelated extra field is rejected. A field present in a JSON file is not necessarily a supported user control.
- Pasting standalone FlowIntent, AreaIntent, a `PLANNER_FACTS_V1` dataset, or `PLANNER_SCENE_JSON_V1` instead of the long-video wrapper fails admission.
- A title change or SFX revision does not alter the frozen video Scene.
- Changing only `durationSeconds` does not extend history or regenerate a valid plan.

`UNIVERSAL_V3` can take a separately generated long Scene at 80, 120, 180, 300 or 600 seconds, within Studio's fixed format. It is still bound to chronology/ownership/visual source files and native inputs. `validate_production_plan` verifies file SHA values, regenerates all `productionV3` metadata and all work scenes, and requires exact equality. It is not an unrestricted long-video authoring interface.

## Why the 5-second F scene is not the historical 80-second scene

The offline planner explicitly declares a different historical route:

- Applied profile: `REFERENCE_V2_SOURCE_WITH_AREA_V3`.
- Territory engine: supplied Area V3 polygon snapshots, including reversals.
- F scalar territory gain, F scalar white/gold frontier, F unit scale and F focus/hold camera flags: `false`.
- National unit positions: `NOT_AVAILABLE_NOT_GENERATED`.
- Reason: the separate F lane represents one winner's scalar gain and is not substituted for reversing supplied polygon-state history.

These declarations are source evidence, not a substitute for checking the later selected compositor. **V3 does add its own source-bound territory style, white front core, gold glow and conservative native-camera extension.** `production_adapter.mjs:31–68,90–128` calls them. The V3 defaults are 0.62 territory opacity, 4.8 px front core, 10 px gold glow radius, 0.42 glow gain and a 48-frame camera approach. The scalar F classifier remains unused. Therefore it would be incorrect to report that the entire 80-second route has no white/gold front or no camera extension merely because parent compatibility flags are false.

V3's supplied ownership palette is blue/cyan held-core data, not a complete red/purple partition. It explicitly disallows an invented opponent complement. Existing military/flag assets in an image do not provide historical position evidence. The historical plan keeps the native geographic marker and labels; it does not fabricate national unit movement.

V4 then activates eight approximate, partial archival front windows starting at frame 1550. During an active archival window, the runtime requires `controls.areas=[]`, exact supplied line geometry and a visible approximate/partial source-date qualifier (`front_runtime.mjs:94–115`). It intentionally suppresses unverified schematic occupation fill. This is an important reason that the latter part of the 80-second output cannot be assumed to match a five-second occupation-gain demonstration.

The earlier 14-second night-run is a separate standalone causal demonstration. Its directional actors are explicitly schematic, not historical unit tracks, and `night_runtime.mjs` is absent from the current image's recursive source closure. It does not silently become part of the current 80-second profile.

## Planner breadth versus executable Studio breadth

The legacy planner recognizes four supplied-data families:

| Family | Data required | Compiled engines | Current Studio long preset |
|---|---|---|---|
| `TRANSPORT` | Sourced route, object role and an actual supplied graphic | Existing Flow V2 | None |
| `LINE_METRIC` | Sourced geographic line and metric | Existing Event V1 | None |
| `DISASTER` | Sourced propagation/coast and impact geometry | Existing Area/Wave V3 | None |
| `WAR` | At least two chronological supplied areas/fronts | Existing Area V3 | Frozen V4 80s; source-bound V3 long plan |

The bounded Python topic parser extracts durations, basic output format and a catalog match. It sets `externalAIConnected=false`. The shipped history catalog has one schematic Korean War entry. Other family compiler functions do not prove an arbitrary new topic is available in Studio. The long timing allocator currently accepts the `WAR` state-timeline family only.

No general historical research AI, arbitrary topic-to-history generator, archival unit simulator, or physics simulator is connected. The parser rejects missing facts and unsupported precision requests instead of inventing them.

## Coordinate, timing, source and cache semantics

- Geographic anchors use `[longitude, latitude]`, EPSG:4326 degrees. Original Event and Area geometry validators own geometry admission. No repair or interpolation is introduced by this audit.
- All long work-scene intervals are global half-open `[startFrame,endFrame)`. `globalFrameOffset=startFrame`; adjacent intervals exactly meet and cover `durationSeconds × fps` frames.
- Duration-to-frame conversion uses exact rational arithmetic. Fractional incomplete frames are rejected rather than rounded.
- Work-scene cuts are not narrative chapters. V3 may place a work cut inside a state transition while preserving one global geometry clock. The current 80-second fixture has 12 chapters and 12 work scenes; the cuts are not identical.
- `productionV3.geometrySchedule` maps narrative time to supplied snapshot source frames. Snapshot crossfade does not assert observed daily control. Event dates, geometry dates and qualifiers are separate.
- `sourceManifest.records[].verification_status` accepts `VERIFIED`/`SYNTHETIC_TEST` structurally. Original article-body availability, review basis, archival source accuracy and file-byte hash verification are separate evidence. Do not treat the status string as a survey certificate.
- Current native admission binds exactly five inputs: regional plan, continent plan, Scene, camera plan and input manifest. It checks all SHA values, output, FPS, event anchor, primary geometry, final framing and actual camera lock timing.
- `scene_cache_key` includes complete scene metadata, shared source/render/encoder/timeline/camera/material context and neighboring boundary states. Reuse requires a private successful receipt and rechecked artifact hashes. Failed attempts remain evidence, not reusable success entries.
- `/world-storage` is not a trusted private cache. Shared MP4 plus SHA alone cannot replace private native-provenance receipts after private state loss.

## Unknown fields and verification limits

Unknown-key behavior is deliberately documented per layer:

| Layer | Actual behavior |
|---|---|
| Studio submission/prompt root | Explicit whitelist; unknown fields rejected |
| Legacy `validateFactDataset` | Most objects normalize selected fields; unknown keys are not a global extension API |
| `native_context`, supplied `scene_timing`, causal track | Explicit whitelist; unknown fields rejected |
| Legacy `validateScenePlan` root | Unknown fields rejected |
| Universal Python long-plan root/source records | No global unknown-key rejection; accepted extra metadata is not proof of renderer use |
| V3 `productionV3` and generated work scenes | Exact equality with source-derived objects |
| V4 entire long plan | Exact equality with immutable expected execution plan |

The audit schema is checked against the persisted V4 example without GPU work. The separate prompt audit runs the actual frozen Studio backend normalization. These checks establish contract behavior only; the current RTX 5090's output quality and the complete current 80-second MP4 are not independently verified here.

## Image inclusion evidence

`IMAGE_AND_BASELINE_LINEAGE.json` records the current immutable image's recursive declared source membership. Universal contracts/planner/cache are in `UNIVERSAL_FILES.json`; V3 planner is in `PRODUCTION_FILES.json`; V4 binding is in `FRONT_FILES.json`; the legacy planner/engine adapter is in the original package source contract. Existing independent image-pull verification and Studio's parent inventory bind those closures. Source existence, image inclusion, selected renderer calls and actual output evidence remain separate columns in the feature records.
