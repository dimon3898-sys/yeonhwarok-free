# Event Feature Bundle V2 — Flow & Movement Candidate

Parent: `EVENT_SYSTEM_V1_FINAL_BASELINE`, commit `f79f3d55d945ef0e53b03ac2ed666f48f28b5881`, Final Manifest SHA-256 `52d4f5f5e034079a58a6227deff71d36bf4b775af0df600daf689eec4f7701a1`.

This is an additive Flow layer. All previously tracked V1/Camera/Renderer/Visual/Geometry/Metric files remain unchanged. Production uses FACT_BASED_VISUAL_GRADE. No Permanent Gate or V2 FINAL is authorized before user video approval.

FlowIntent → FlowPlan → FlowTimeline → Route → Moving Object → Endpoint State. Route input and provenance use the V1 Event contract. Route reveal, screen arc length, random-access readiness and the Route GPU pass reuse V1. The Camera and Detail Decision/Approach/Settle/Lock remain existing V5/V1 APIs. Production screen points come from the actual native factory projection, exposed by its EVENT_READY diagnostics; there is no second projection engine.

The new GPU vector pass shares the native WebGL2 canvas and restores the complete native GL state. No finished frame is blitted, mixed, resized or replaced. Native graphics stay at their existing anchors and design. Route-over-Marker uses the V1 raster occlusion; Route/Text collisions remain strict. Object, direction cue and one-shot Pulse rasterize below every protected reservation without interrupting internal progress. Full graphic footprints remain inside Safe Area.

Object shape, role and colors are fixture data. Motion is deterministic projected arc length with smootherstep acceleration/deceleration. Heading uses an arc-length secant sized from the object graphic; this smooths corners without changing the route or sampled position. No aircraft/ship physics, traffic, area propagation, sound, subtitles or Planner are included.

The real fixture is an illustrative southbound passage over the already verified Suez main navigation axis: Port Said → Bitter Lakes → Suez Gulf. It names no particular vessel, incident, departure, arrival, speed or actual travel duration. The new data title is `수에즈 운하 항로`, with the existing disclosure role reading `이동 예시`. Original V1 title data remain unchanged. The original 92 coordinates/91 segments, OSM Relation 7719838 v17 and saved SCA route evidence are reused, with source hashes and ODbL attribution in the fixture. No new data research was performed.

The eight-second proof uses 60 existing Camera frames followed by 180 Flow frames. Route introduction overlaps the direction cue and travel; arrival gets one short Pulse, then a 34-frame Hold. There are no repeating endpoint flashes.

Focused checks: Core18, Synthetic A/B/C, native constructor/draw/dispose state restoration, native redraw BIT_EXACT, actual fixture integration and all proof-frame protected pixel checks. Only affected heading tests were repeated after a Synthetic B failure; the old complete V1 suites were not repeated.

Saved procedures, run from repository root with pinned Node24.19.0, Chromium154.0.8037.57, Playwright1.62.1, Three0.170.0, Python3.13.5 and FFmpeg7.1.5:

```
node world-simulation-shorts-engine/recovery/event-feature-bundle-v2/build_flow_fixture.mjs --verify
node --test world-simulation-shorts-engine/tests/flow_core_v2.test.mjs
node world-simulation-shorts-engine/recovery/event-feature-bundle-v2/verify_synthetic_gpu.mjs
node world-simulation-shorts-engine/recovery/event-feature-bundle-v2/verify_native_state.mjs
node world-simulation-shorts-engine/recovery/event-feature-bundle-v2/verify_integration.mjs
node world-simulation-shorts-engine/recovery/event-feature-bundle-v2/render_proof.mjs
```

Evidence and media output directories are exclusive to protect saved results. For original reproduction, fetch/check out the recorded pre-media proof source commit from the remote repository, hydrate the inherited original Git LFS assets, and use frozen `npm ci` dependencies. That source commit already contains the prerequisite evidence and runtime fixture. The manifests record the original render source revision; it predates delivery media, so the exclusive `public-review`/`evidence/proof` directories are absent. Do not overwrite committed Candidate media to rerun it.

The final Candidate inventory binds Source, Fixture/Data, inherited runtime assets, dependencies, AST import closure, evidence, original MP4/checkpoint hashes and reproduction recipe. Historical CONTINENT `/tmp` descriptors are explicitly inactive provenance (`runtime_required:false`, `runtime_loaded:false`); actual runtime assets come from committed repository/Git LFS files. Required temp-only inputs are zero.

Public Review contains only the original MP4, eight native PNG checkpoints and SHA256SUMS. HTTP200 and downloaded SHA-256 equality are checked after the media commit is pushed. Source, diagnostics and plans remain outside Public Review. Submission stops at USER_VIDEO_REVIEW_REQUIRED.
