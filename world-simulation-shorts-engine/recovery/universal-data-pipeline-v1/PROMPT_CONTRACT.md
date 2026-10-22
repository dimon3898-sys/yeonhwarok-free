# Structured production prompt contract V1

This additive adapter accepts JSON or a single fenced JSON block. It does not use an AI API, conduct research, infer geography, or implement unrestricted natural-language understanding. A short heading outside the JSON fence is permitted. Unsupported fields return `UNSUPPORTED` with a path and correction; they are never silently removed.

The existing `PLANNER_FACTS_V1` data model is reused, rather than inventing another renderer schema. The outer envelope separates simulation provenance, scene ranges, and renderer profile selection. The five complete input files are in `examples/`.

```json
{
  "schema": "WORLD_ENGINE_DATA_PROMPT_V1",
  "topic": "Supplied aviation transport routes",
  "simulationType": "GENERAL",
  "durationSeconds": 3,
  "fps": 30,
  "resolution": {"width": 1080, "height": 1920},
  "scenes": [{
    "sceneId": "route_scene",
    "startFrame": 0,
    "endFrame": 90,
    "facts": "Replace this string with the complete PLANNER_FACTS_V1 object from examples/AVIATION_GERMANY.json",
    "renderSettings": {"sourceRegionId": "europe_germany"},
    "dependsOn": [],
    "historicalEvidence": []
  }]
}
```

The example above illustrates the envelope; its `facts` placeholder is intentionally not executable. Use the complete example file for an executable prompt.

`simulationType` is `HISTORICAL`, `FICTIONAL`, or `GENERAL`. Fiction is explicitly `SYNTHETIC_TEST` inside the preserved Planner. General illustrative networks are also explicitly synthetic inside the engine; they do not claim observed traffic or trade. Historical or observed general datasets must use `PRODUCTION` and pass the additional server-owned evidence gate. A client `VERIFIED` label or a document SHA alone never proves a historical claim.

Each scene preserves its original half-open `[startFrame,endFrame)` range. The ranges must be contiguous and end exactly at `durationSeconds × fps`. A blocked scene does not renumber or silently delete other scenes. The response contains per-scene `status`, `issues`, `renderableSceneIds`, and `blockedSceneIds`; the overall status stays non-PASS when any scene is blocked. Partial rendering requires explicit selection and preserves those original ranges. Declared dependencies propagate a block; unrelated scenes remain available. Cyclic dependencies are rejected.

## Existing data fields

`facts` uses the protected `web/map_infographic_v1/planner_scene_v1.mjs` contract:

- `version`, `data_mode`, `subject`: identity, supplied aliases, and selected event family.
- `locations`, `geometries`, `camera`, `native_context`: explicit EPSG:4326 positions and references. Coordinate order is `[longitude,latitude]`.
- `time_range`, `stages`: complete Gregorian dates and supplied chronological area/front states. Stage order is sorted by supplied dates; no date or geometry is invented.
- `source_notes`: source identity, reference, verification class, license, original SHA and uncertainty notes.
- `routes`: supplied LineString, direction, object role and vector graphic. No actual airway, vessel navigation route, physical km/h, count, or military path is inferred.
- `markers`: explicitly supplied marker identities and geographic anchors. Marker/location labels and moving-object profile identifiers are semantic metadata; they do not request visible text or automatically select a graphic design. Supplied vector geometry selects the actual moving-object pixels.
- `scene_timing`: optional existing integer-frame timing. If omitted, a deterministic frame allocation is derived from the requested scene range. That allocation changes only playback timing, never facts.

WAR requires at least two complete supplied area/front states. Ordinary routes do not require territory, military factions or historical fronts. Exact core geometry, source, Flow and timing validators still run after the new gate. The generated Scene is standard `PLANNER_SCENE_JSON_V1`, validated unchanged, then bound through unchanged `compileExistingEnginePlan`.

## Connected scope and explicit limits

This candidate's free pixel consumer connects WAR (existing Area V3) and TRANSPORT (existing Flow V2). Existing LINE_METRIC and DISASTER Planner functionality is preserved, but those families return `UNSUPPORTED` in this new consumer until their own real pixel adapter is admitted. Current tests therefore do not advertise all Planner families as rendered.

WAR routes and causal tracks currently return `UNSUPPORTED`: their combined pixel/timing behavior has not been admitted by this bounded preview. This does not remove those existing engine features.

The server-owned regional source profiles are `namibia_desert_coast`, `europe_germany`, `south_america_chile`, `korean_peninsula`, and `nepal_himalaya`. These reuse existing licensed source-native texture assets. Arbitrary uncovered regions, arbitrary file paths and remote texture URLs are not accepted. The current camera profile is an existing Camera V5 regional locked view built from the supplied scene anchor and target/context geometries; arbitrary camera keyframes or effects are not implemented by this adapter. Unsupported camera/color/speed fields return explicit errors.

This is a bounded free preview path: 1080×1920, 30fps, 16..240 frames per scene. The envelope has a structural 600-second upper bound, but this preview has at most 64 scenes ×240 frames at30fps (512seconds theoretical maximum) and a much smaller Studio execution policy. It does not claim actual long production rendering or full600-second execution. The existing long-form pipeline remains unchanged. Studio policy independently bounds actual free demo jobs. No NVIDIA, paid GPU, 80-second completed film or final quality approval is claimed.

Dates before year 0001, BCE dates, dates with only year/month precision, and unknown calendars are `UNSUPPORTED` or `NEEDS_INPUT`; they are never replaced with invented precise modern dates. Current Rome extent data is missing. Existing Korean War partial lines do not establish full bilateral occupation polygons.

## Historical evidence gate

The registry is supplied only by the server, not by the prompt. A binding is:

```json
{"recordId":"reviewed_record", "sourceId":"source_id", "claimId":"reviewed_claim", "geometryIds":["geo_id"], "stageIds":["stage_id"]}
```

The server record must bind the exact original source reference/SHA, exact canonical facts digest, exact geometry digest, applicable dates, and reviewed claim scope. `PARTIAL_FRONT` or `EVENT_DATE` cannot qualify a `FULL_TERRITORY` polygon. Event date, map date, native pixel coordinates and georeferenced coordinates are distinct evidence dimensions. The current retained source ledger does not certify missing original PDFs or unknown source projections.

## Results, trace and invocation

Statuses are `PASS`, `NEEDS_INPUT`, `CONFLICT`, `UNSUPPORTED`, `INVALID`. Every issue includes `field`, `reason`, `code`, and `example`. `renderRequests` carry standard Scene JSON, engine plan, source manifest, original frame range, source-region choice, per-geometry/stage/route/camera trace, and deterministic digests. `originalBytesVerified:false` in the source manifest explicitly separates prompt metadata from an actual external source-byte fetch; server source asset/evidence checks are independent.

```sh
node prompt_pipeline.mjs --input examples/AVIATION_GERMANY.json --output /tmp/result.json --evidence-registry evidence/TRUSTED_EVIDENCE.json
```

`analyzePrompt(input, {evidenceRegistry})` is the in-process API. CLI exits 0 when it successfully returns an analysis, including a blocked result; consumer code must check `status` and scene selection. CLI argument/file errors exit 2. It prints only compact status counts to stderr. `validateLegacyScene(scene)` validates an existing standard Scene and binds its old engine plan without reinterpretation.
