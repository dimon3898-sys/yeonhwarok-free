# WORLD ENGINE presentation input V2

This opt-in profile combines Korean/English display instructions with an authoritative attached data package. It is bounded grammar and supplied-entity linking, without an external LLM, geocoder, historical researcher, or arbitrary natural-language understanding. The existing structured input and original renderer remain unchanged.

## Exact call

```js
import {analyzePresentationPrompt} from './presentation_prompt.mjs';
const result = await analyzePresentationPrompt({
  schema: 'WORLD_ENGINE_PRESENTATION_PROMPT_V2',
  prompt: '첨부한 도시와 경로를 사용해 6초 영상으로 만들어줘. 첫 장면은 카메라를 이동하고 줌아웃한 뒤 줌인해줘. 두 번째 장면은 제공한 경로를 따라 카메라가 이동해줘. 두 장면을 전환해줘.',
  data: suppliedWorldEngineDataPromptV1,
  region: {center: [10, 51], bbox: [0, 35, 20, 67], crs: 'EPSG:4326', sourceId: 'AUTO'},
  presentation: suppliedPresentation
}, {evidenceRegistry: serverOwnedEvidenceRegistry});
```

`data` is the existing `WORLD_ENGINE_DATA_PROMPT_V1` package, including its original `PLANNER_FACTS_V1` facts. The mobile/Studio integration assembles the envelope; users can paste text and attach a prepared JSON package rather than author this envelope by hand. The examples in `examples/` are complete runnable inputs, unlike the abbreviated call above.

The structural schema is `PRESENTATION_PROMPT.schema.json`. It embeds the unchanged prior facts schema as a separate JSON Schema resource and records the original file hash. Semantic, evidence, native-engine and actual-source validation remain mandatory after schema validation.

## Precedence and provenance

- Supplied facts, locations, geometries, route direction, dated states and source notes remain authoritative. Native context countries and location IDs are checked against supplied geometry/location bindings and the explicitly admitted region; stale inherited country/location context is rejected, as are contradictory duplicate contexts. Language does not overwrite them.
- Explicit video duration or fps in the text can fill a missing display scalar. A conflicting attached value returns `CONFLICT`. Missing fps defaults to 30; missing resolution defaults to 1080×1920. These are display defaults, not inferred world facts.
- If the attached topic is present, it is retained even when the prose uses another language. A missing topic may use an existing supplied subject alias. The first prose clause remains separate display metadata.
- All fact compilation invokes the unchanged native validators and `compileScenePlan` / `compileExistingEnginePlan`. Scene objects retain the existing `metadata.schema = PLANNER_SCENE_JSON_V1` structure and member order.
- Every request carries original input hashes, per-geometry hashes, source IDs, presentation hashes and mappings from input paths to Scene paths. Source-note metadata hashes do not prove original source bytes: `originalBytesVerified` stays false unless independently verified elsewhere.
- An old `data.renderSettings.sourceRegionId` or per-scene source selection is accepted only when `region.legacyProfileId` explicitly matches it. A contradiction returns `LEGACY_SOURCE_SELECTION_CONFLICT`; it is never silently ignored.
- The old profile's five-region rejection is recorded as old `UNSUPPORTED`, then replaced only by the new actual-source qualification gate. No registered-region sentinel or false old PASS is used. Other old failures remain failures.

## Supported bounded language

| Intent | Examples | Consumer / restriction |
|---|---|---|
| Duration | `6초`, `6 seconds`, `1분 20초` | Exact display frame budget. New free preview is limited to 240 total frames; long production paths are unchanged. |
| Frame rate | `30fps` | Existing preview requires 30fps. |
| Dates | `2026-10-22`, `2026년 10월 22일`, `2026년 10월`, `2026년` | Valid Gregorian calendar and interval overlap at stated precision. A verified event or source is not inferred from this text. |
| Place reference | Exact supplied location ID or label | Links to attached anchors; no place-name coordinate lookup. |
| Directed connection | `from HAMBURG to MUNICH`, `HAMBURG에서 MUNICH로` | Both locations and the directed endpoint geometry must already exist in the matching attached scene. No route invention. |
| Camera movement | `카메라를 이동`, `move the camera` | Existing reference camera adapter through the independent presentation profile. |
| Zoom | `확대`, `줌인`, `zoom in`, `줌아웃`, `zoom out` | Requires matching keyframe zoom changes. Final view must remain the closest approved endpoint. A final-only zoom-out is unsupported. |
| Route following | `경로를 따라`, `follow the route` | One exact supplied route; ambiguous routes require `routeId`. Current route-follow zoom is constant. |
| City emphasis | `도시를 강조`, `highlight cities` | Existing marker pulse at supplied locations; no visible name text is added. |
| Event emphasis | `사건을 강조`, `highlight the event` | Requires explicit supplied `locationId` and frame timing in `highlights`. |
| Territory change | `영토 변화`, `area expansion` | Requires existing dated WAR area/front states. No ownership or expansion is invented. |
| Scene transition | `장면 전환`, `cut scenes` | Actual hard cuts at every attached scene boundary; no fade implementation is claimed. |

Explicit sentence-level scope recognizes supplied scene IDs, `첫 장면` / `두 번째 장면` / `제3번째 장면`, `first scene` / `second scene` / `scene 3` / `3rd scene`. Unscoped instructions are shared. An out-of-range ordinal asks for input. A genuine shared follow request conflicting with attached keyframes is reported, not silently resolved.

The original prompt, exact character spans, scene scope, linked supplied entity IDs and any display-only derivations are returned. Text outside the supported grammar is retained as uninterpreted prose. This does not certify that arbitrary phrasing, negation, nuanced speed requests, every place name, or unsupported factual claims have been understood.

## Region contract

Optional `countryId` / `countryName` must match actual GIS identity and coordinates. A matched `legacyProfileId` can retain an explicitly selected preserved source profile.

`region.center` uses `[longitude, latitude]`. `region.bbox` uses `[west, south, east, north]`, EPSG:4326. Coordinates must be supplied; no country or city coordinate is guessed. An explicit prose center must match the attached region center, even if the different coordinate happens to be a supplied city. Other explicit coordinate pairs need a matching supplied location, geometry vertex, or approved center; otherwise the result asks for a named binding.

The new provider checks actual asset bytes, SHA-256, license, source coverage, GIS coordinates and bounds. AUTO may select a preserved regional Natural Earth crop or the actual global Earth Day RGB asset. The checkout's global NE1 TIFF is an LFS pointer, so this profile does not pretend that its full raster exists. Camera-wide coverage, projection limits, crop resolution and one source for the full movement envelope are checked again before execution. Unsupported wrap/polar/oversized requests remain blocked.

## Presentation sidecar

The original Scene is not rewritten to add new renderer fields. These settings form an independently validated runtime sidecar:

```json
{
  "camera": {
    "mode": "KEYFRAMES",
    "keyframes": [
      {"frame": 0, "center": [10, 51], "zoom": 0.8},
      {"frame": 44, "center": [10.2, 51.1], "zoom": 0.6},
      {"frame": 89, "center": [10, 51], "zoom": 1}
    ]
  },
  "highlights": [{"id": "focus", "locationId": "HAMBURG", "startFrame": 12, "endFrame": 28}],
  "sceneOverrides": {
    "scene_return": {"camera": {"mode": "ROUTE_FOLLOW", "routeId": "SUPPLIED_ROUTE", "zoom": 0.8, "followStrength": 0.2}}
  },
  "transitions": [{"type": "CUT", "frame": 90}]
}
```

- Keyframes start at local frame 0 and end at local frame N−1, with increasing integer frames. Zoom is `(0,1]`; bbox is the closest view at zoom 1. The final zoom equals the maximum, preserving the original reference camera's endpoint constraint. Movement/zoom requested in text must actually exist in supplied keyframes.
- Route following requires an actual Scene route ID and keeps existing route direction and event time fractions. It has one zoom and does not claim dynamic zoom support.
- Optional `territoryColors` maps actual `scene.time_steps[].id` values to RGBA. Channels are 0..1, alpha .08.. .6, at most eight states. Existing Area rendering consumes the palette. It cannot invent factions or states.
- Highlights use actual location IDs, last at least two frames and remain inside the local scene. Maximum sixteen. Existing marker designs and world anchors are reused.
- Optional `initialStateVisibility` is `REVEAL` by default. `PRESERVE_PROVIDED` is allowed only for an existing WAR scene beginning at its event frame zero. It uses the public existing Area reveal/front operation endpoints `[1,1]` so a provided visible starting state remains visible at a scene cut; its supplied geometries, state clock and transitions are unchanged. Runtime separately checks matching boundaries. It does not invent an initial territory or skip an event.
- Shared fields apply unless the matching `sceneOverrides[sceneId]` explicitly supplies them. Unknown scene IDs and fields are rejected. Explicit language conflicting with the resolved camera remains an error.
- Sidecar keyframe/highlight frames are local to each scene. Top-level transition frames are global and exactly equal the original next-scene start frames. The compiler returns transitions separately from each segment.

## Results and safety

The result schema is `WORLD_ENGINE_PRESENTATION_PIPELINE_RESULT_V2`. Status is `PASS`, `NEEDS_INPUT`, `CONFLICT`, `UNSUPPORTED`, or `INVALID`. Issues include field, reason and corrective example. `clarifications` lists missing or conflicting input. Neither `PASS` nor Scene creation is a video-quality verdict.

`renderRequests` contains actual native Scenes, sidecars, source qualification evidence and immutable frame intervals. Invalid scenes remain blocked; independent qualified intervals can be retained for explicit per-scene selection. Full timeline execution requires every scene and boundary to qualify. Declared dependencies still block downstream work, including cycles.

A compiler PASS is followed by actual source-envelope, native camera/Flow/layout, Studio admission, no-duplicate-job and software/hardware execution gates. This compiler does not start a GPU, deploy a workload, change Secrets or authorize paid rendering. It always reports `externalLLMUsed:false`, `paidExecutionAllowed:false`, and `historicalRenderAllowed:false` for this free nonhistorical preview profile.

Current pixel families are the existing WAR and TRANSPORT contracts. A qualified historical partial line/metric example remains `UNSUPPORTED` where no connected pixel consumer exists; missing ownership/evidence remains `NEEDS_INPUT`. Neither is converted to fabricated territory.

## Explicit unsupported commands

Visible city labels, place-name captions or screen text are not rendered by this profile. Recognized requests such as `도시 이름 라벨을 화면에 표시해줘`, `Show city names on the map`, and `Display labels` return `UNSUPPORTED_VISIBLE_LABELS`. Supplied names remain metadata and entity references.

Other recognized unsupported intents include TTS, narration, BGM, explosion effects, live satellite/flight/stock data, 3D models, camera rotation/orbit, dissolve/fade transitions, and dynamic zoom during route-follow. Unknown structured fields are always rejected. SFX, arbitrary facts text and existing internal-only features are not activated by adding prose.

No 80-second rendering, historical G3, paid API/GPU or FINAL promotion is performed by these calls.
