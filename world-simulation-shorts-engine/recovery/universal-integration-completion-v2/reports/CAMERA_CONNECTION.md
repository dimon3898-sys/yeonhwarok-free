# Camera connection — source-bound V5 event tracking

**CPU consumer connection verified. Actual NVIDIA frames, reference comparison and visual quality remain NOT_VERIFIED.** Existing Camera V5, Detail adapter, projection, source plans, native renderer and layout files were not modified.

## Supported request

The independent completion runtime accepts the following camera metadata, derived from the strict completion prompt contract:

```json
{
  "mode": "V5_EVENT_TRACKING",
  "settleFrames": 18,
  "holdFrames": 24
}
```

- `mode`: `V5_EVENT_TRACKING` or `PRESERVE_PARENT`.
- `settleFrames`: integer 6–60; default 18. Consumed by original V5 `profile.settleSeconds = settleFrames / fps`.
- `holdFrames`: integer 0–120; default 24. A minimum post-lock hold reservation within the existing chapter budget; remaining chapter frames also hold the final pose. It does not extend or change the video timeline.
- Explicit `PRESERVE_PARENT` is exactly `{"mode":"PRESERVE_PARENT"}`. Other camera fields in that mode are rejected rather than ignored.
- Existing integration `cameraApproachFrames` remains effective: the bridge merges the original validated five-field profile and passes its value to original V5 `profile.approachBaseSeconds = cameraApproachFrames / fps`. Original source metrics and readability budgets may require more motion frames.

No roll, tilt, new projection, arbitrary user coordinates, invented camera target, fixed zoom multiplier or closer-than-parent floor is exposed. Selecting an unsafe source path fails closed; it never silently reverts to the old rendering profile.

## Actual preserved consumers

1. `production_camera_bridge.mjs` imports `createProductionNativeCamera`, `nativeGraphicReservations` and `nativeBoundarySupport` through `/completion-v2/parent_camera.mjs`. That alias points to preserved source. The bridge explicitly merges the validated V1 five-field profile before constructing either mode.
2. `createCompletionNativeCamera(input, {camera, originalFactory, operations})` delegates `PRESERVE_PARENT` directly to that original production camera factory. Tracking mode instead uses the unchanged **native V5 bridge** and original `compileProductionFocusPlan`; it does not call the old production factory's incompatible adjacent-only focus path.
3. Tracking mode selects qualified source geometry for each chapter and strengthens the original focus compiler's caller-supplied `validateBounds` with **all supplied timeline geometry safety plus original native layout admission**. An earlier small-state focus cannot strand a later larger state. No compiler, source coordinates, dates or ownership are changed. The first source chapter retains the original native Detail lock and first reveal.
4. For later chapters, `compileCompletionCameraTracking` calls **unchanged `compileMinimumContextPlan`**. `evaluateCompletionCameraFrame` calls **unchanged `evaluateMinimumContextCameraFrame`**. Their V5 natural-turn, center/log-span interpolation, deceleration and settle math remain the motion owners.
5. Existing `minimum_context_geometry_refs` select explicit source geometry for the original V5 minimum-context/turn logic. Those geometries are context, not inferred occupied regions. Missing references fail closed. No context is invented from country names, dates or military labels.
6. Before any selected path is used, every motion frame is checked with the original `geometryScreenSafety`, parent minimum extent and original native moving-layout validator. Insufficient chapter time, an invalid projection extent, a discontinuous literal start, source crop or a protected graphic collision blocks the path.
7. Draws use existing native public APIs: `updateCamera`, `setScaleVisual`, `setTerrainLod`, `renderFrame`, the original moving-layout evaluator, original reservations and original boundary-support owner. This redraw occurs before ASTRA/territory/front composition in the preserved runtime. It is not an overlay of a finished image. The bridge publishes exact per-frame native boundary segments into the private completion frame context before the preserved front adapter strips them from public diagnostics; later overlays retain the original masks.

The adapter can require an additional native redraw after the preserved camera draw. Performance has not been measured; no speed claim is made.

## API exports

`camera_extension.mjs` exports:

- `normalizeCompletionCamera(input)`
- `completionChapterGeometries(plan, chapter)`
- `completionRelationGeometries(plan)`
- `compileCompletionCameraTracking({plan, request, parentFocusPlan, safeArea, camera, geometriesForChapter?, validateBounds, approachFrames?})`
- `evaluateCompletionCameraFrame(compiled, frame)`
- `createCompletionNativeCamera(input, {camera, originalFactory, operations})`

The browser bridge exports the same `createProductionNativeCamera` name and native helper exports as the existing camera module. The parent API is preserved.

## CPU verification

From repository root:

```text
node world-simulation-shorts-engine/recovery/universal-integration-completion-v2/tests/test_camera_extension.mjs
```

**11 PASS, 0 FAIL, 0 SKIP.** The tests execute actual preserved V5 math and original geometry-screen safety. They verify:

- strict settings and rejection of unknown, null, fractional or out-of-range values;
- unchanged source coordinates and independent copy semantics;
- pan and zoom from a wider admitted synthetic source pose back toward the original minimum extent;
- real V5 context expansion, `DIRECTIONAL_TURN`, zoom reversal and settle selected by explicit source context geometry;
- equivalent operation on synthetic southern/western and opposite-hemisphere inputs;
- real consumers for `settleFrames`, `holdFrames` and retained `cameraApproachFrames`;
- unsafe layout, crop, closer floor, discontinuity and short chapter rejection;
- exact original production-factory invocation for preserve mode, native V5 source reuse for tracking mode, and native scale/LOD/layout/reservation/redraw calls through labeled CPU spies;
- actual preserved 80-second inputs, all five native JSON SHA references, 12 chapters and all 2,400 CPU camera states, including source-safe bounds, minimum extent and continuous chapter endpoints.

Synthetic coordinates and context are test fixtures only. They are not historical positions and are not inserted into the Korean War plan. Native draw and layout spies are not WebGL draws, actual font-layout proof or evidence of pixel quality. Actual native layout admission remains mandatory in the browser path; no spy is selectable there.

## Actual preserved 80-second CPU trace

The exact preserved `REGIONAL-plan.json` (`cdb4d2a9f2f05ace10934d7f873702fe96ad6ea24fdabb81ebe1780221623bd5`), native V5 camera plan and `VIDEO_PLAN_80S.json` were used. The old focus compiler with an explicit layout-allowed CPU spy reaches `PRODUCTION_FOCUS_NO_SAFE_CURRENT_VIEW_chapter-08`: an earlier accepted local focus leaves a later larger source outside that view. This is a confirmed mathematical reproduction with that caller policy, **not a claim about an actual historical GPU failure**. The new caller predicate rejects the earlier unsafe-for-future pans while still calling the unchanged compiler.

The completion camera traversed all **2,400 CPU frames** with 4,261 native-layout spy calls and 2,193 public-native redraw spy calls. Every supplied timeline geometry remains inside the canonical safe area after event arrival; no camera frame is closer than the original floor. Chapter end/start poses match within floating-point tolerance. The Scene JSON remains unchanged.

| Chapter | Selected camera | Active V5 frames through lock | Fixed hold frames | Actual V5 context turn selected |
|---|---|---:|---:|---|
| 01 | Preserve native arrival / first Detail lock | — | — | No new camera motion |
| 02 | V5 event tracking | 72 | 128 | No |
| 03 | V5 event tracking | 100 | 100 | Yes |
| 04 | V5 event tracking | 101 | 99 | Yes |
| 05 | V5 event tracking | 101 | 99 | Yes |
| 06 | V5 event tracking | 101 | 99 | Yes |
| 07 | V5 event tracking | 101 | 99 | Yes |
| 08 | V5 event tracking | 98 | 102 | Yes |
| 09 | V5 event tracking | 95 | 105 | Yes |
| 10 | V5 event tracking | 98 | 102 | Yes |
| 11 | V5 event tracking | 100 | 100 | Yes |
| 12 | V5 event tracking | 101 | 99 | Yes |

All tracking entries reserve 18 original V5 settle frames and at least 24 hold frames. Two existing explicit minimum-context geometry references are consumed. Frequent context turns are **not a visual-quality endorsement**: repetition, pace and mobile readability require the approved GPU preview. The first 0–5 seconds lie within preserved chapter 01; a later source-bound five-second comparison window is needed to evaluate the newly selected tracking behavior.

## Honest limitations

- A partial archival front remains partial; camera movement does not make it a verified bilateral occupation boundary.
- V5 may skip a context turn when the supplied geography already fits. No decorative zoom or forced turn is added to manufacture visible movement.
- V5's existing admission can reject a wider final extent that would change the literal starting pose. Such a plan blocks with `COMPLETION_CAMERA_V5_START_WOULD_JUMP` instead of jumping.
- Camera-only evaluation uses the original V5 phases through `LOCK`. Event titles and information graphics remain their existing owners; the adapter does not replay V5 title graphics or add text.
- 5-second paid GPU comparison and explicit user quality approval remain required before any 80-second render. No GPU or video rendering was performed during this CPU task.
