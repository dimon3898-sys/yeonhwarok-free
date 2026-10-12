# Event System V1 common Core

Status: **CORE_IMPLEMENTED_DATA_BLOCKED**. This is not a complete production Candidate or Event Final.

Parent is `V5_CAMERA_DIRECTOR_FINAL_BASELINE`, commit `29b8ee294360812b55ef577b62411de58159003b`. The reference upload SHA is `853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc`. The prior full-video audit is retained: geographic line draw → brief hold → fixed metric glyph reveal → information hold. The common Timeline and the synthetic durations are generator rules, not copied reference frame numbers. No simulation, inferred measurements, count-up, audio, route, pulse, or result panel is implemented.

## Data gate and order

The implementation instruction's section 14 permits data-independent common Core work when its step 2 data gate fails. The preserved generalized maritime passage is not a verified complete canal line, and a matching verified metric is absent. `evidence/SUEZ_DATA_GATE.json` records the actual source/hash and limits. No production fixture was created. The reference metric is never substituted.

Steps 3–10 implement the immutable contract, pure integer-frame controls, projected arc-length line, native measured metric, collision adapter, and separate GPU composition. `fixtures/synthetic-a.json` and `synthetic-b.json` are explicitly synthetic focused test data. They do not establish production provenance or completion of the required three-fixture gate. Steps 11–14 (production fixture and 150-frame public review Proof) remain blocked. Independent common Core source is saved without claiming full Candidate PASS.

## Runtime API

Import `createEventGpuPipeline` from `web/map_infographic_v1/event_gpu_pipeline_v1.mjs`. Its existing V5 initialization inputs are unchanged; the optional `eventPlan` is produced by `compileEventIntent` and `compileEventPlan`. Call `drawFrame(cameraFrame, {eventEnabled, eventFrame})` with separate integer indices. Camera evaluation, projection, terrain/LOD, measured layout and Reveal are owned by the unchanged V5 public APIs.

Composition is fresh native map → separate Event line → unchanged Marker/Labels → separate Event metric. Event OFF never evaluates or draws Event controls. Rebuilding the native base also removes prior Event pixels; no finished-frame overlay or cached-map accumulation is used.

Line progress uses current projected segment arc-length. Supplied vertices, direction and provenance are immutable. Wrapped geographic lines and more than 128 projected segments are rejected rather than replaced or simplified. The compact halo and full line footprint must be safe and disjoint from protected graphics; a collision blocks the input. PRIMARY/SECONDARY styles consume existing approved material tokens without changing them.

Metric value/unit are supplied strings. Production requires VERIFIED provenance, but that declaration does not replace an external factual data gate. Metric uses the existing Noto/Glyph atlas and LOCATION_LABEL typography, one full measured reservation, sequential native coverage, and stable baselines. Layout considers four positions derived from the current geographic anchor, actual marker size, measured full text bounds and existing gap. It moves only the Event annotation. No wrapping, font resizing or historical label movement is used to make invalid data fit.

## Reproduction

Use the pinned V5 dependency setup and LFS assets; no data generation or dependency upgrade is required. From a clean checkout of this development branch:

```sh
git lfs pull
npm --prefix cinematic-world-map ci --ignore-scripts --no-audit --no-fund --strict-ssl=true
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-v1/validate_core.py --require-persisted
node --test world-simulation-shorts-engine/tests/event_contract_timeline_v1.test.mjs world-simulation-shorts-engine/tests/event_line_v1.test.mjs world-simulation-shorts-engine/tests/event_layout_adapter_v1.test.mjs world-simulation-shorts-engine/tests/event_metric_v1.test.mjs
node world-simulation-shorts-engine/tests/event_line_gpu_v1.test.mjs
node world-simulation-shorts-engine/tests/event_gpu_integration_v1.test.mjs
```

Pinned environment: Node 24.19.0, Three 0.170.0, Playwright 1.62.1, Chromium 154.0.8037.57, system Python 3.13.5. GPU tests start the existing loopback-only V5 server, use Software WebGL2 SwiftShader, and close their browser/server. They consume only repository runtime URLs. They produce no MP4 or public review PNG. The optional integration `--report` flag writes private diagnostics, never Public Proof.

The actual focused tests verify Event OFF frames 0/144/205/249 against approved raw RGBA and PNG hashes, Event ON pixels outside the Event ROI and inside protected boxes, deterministic holds, and removal when switched OFF. The expected final PNG remains `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673`.

Runtime assets and deterministic build inputs inherit the immutable V5 manifests and their hashes. No new required runtime asset or temporary-only runtime file was introduced. Manifest validation covers the new source, fixtures, test procedures, syntax-parsed import closure, inherited runtime assets, build inputs and pinned dependencies. Clean common Core verification is distinct from a complete Event production proof.

## Completion boundary

Required next input: a verified meaningful line for the production fixture and a metric value/unit/source that describes that same line. Then continue the blocked production fixture/generalization/5-second Silent Proof steps. User review is required before Event Final. Protected V5 files, main and Public Review remain unchanged.

Development stores Source + assets + manifests. Public Review may contain only MP4/PNG and required SHA. Never publish this directory, source, internal plans or diagnostics as Public Proof.
