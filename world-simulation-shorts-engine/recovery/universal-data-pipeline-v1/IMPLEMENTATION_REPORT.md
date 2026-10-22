# Universal data pipeline — implementation and limits

Baseline: `e39969cbc76a071d34a38440d9551425e6d5e545`. Work branch: `development/universal-data-pipeline-v1-20261022`.

## Actual changes

The opt-in `WORLD_ENGINE_DATA_PROMPT_V1` adapter accepts one structured JSON prompt, or one fenced JSON prompt. It validates the supplied topic, simulation class, dates, geographic facts, source identities, scene intervals and supported presentation settings. It calls the existing generic Planner and existing engine-plan compiler. It does not call an external AI or invent missing facts.

The validator returns `PASS`, `NEEDS_INPUT`, `CONFLICT`, `UNSUPPORTED` or `INVALID`, with field paths and correction examples. An independent qualified scene retains its original frame interval when a neighbouring scene is blocked. Declared dependency failures propagate; gaps, overlaps and cycles do not silently disappear. A historical source's hash and date alone never qualify a full occupation polygon. Server-reviewed dataset, source, geometry, time and claim-scope bindings are separate checks.

The new source Studio adapter reuses the existing authenticated HTTP server and original detached job manager. A real browser submits a selected scene through login, preflight, submission and explicit start. Authentication, effective Origin, CSRF, private claims, idempotency and active-job checks remain in effect. The new profile permits only explicitly enabled, bounded free software review. It has no paid-provider authority and keeps G3 historical production blocked.

The new runtime composes the unchanged native map factory, Camera V5, G2 measured layout recovery, Area V3 and Flow V2. It uses the map factory's projection for supplied features. A server-owned regional style/GIS seed supplies the basemap; it does not substitute its old territory or route for the user's scene. Native source coverage and source-file hashes are checked. Actual before/after feature readback distinguishes a drawn event from an unchanged basemap.

An actual Studio attempt exposed a serialization defect before its first frame: private canonical JSON storage sorted the geometry object keys, while the existing strict Scene validator expects the Planner's canonical member order. The extension now preserves the original compiled Scene wire string and independently verifies its wire SHA and semantic SHA after persistence. The existing validator and geometry values are unchanged. The original failed job and its evidence remain preserved. See `STUDIO_SERIALIZATION_RECOVERY.md`.

## Reused functions and preserved assets

- Existing `validateFactDataset`, `compileScenePlan`, `validateScenePlan` and `compileExistingEnginePlan`.
- Existing Area, Flow, Camera, map projection/material, native marker and measured-layout code.
- Existing authenticated Studio server, private state tree, job claims, detached launch and descendant cleanup.
- Existing FFmpeg encoding and full-decode tools.
- Existing source-qualified regional NE1 textures, GIS, font and Three assets; no new map source was redistributed without a license.
- Existing historical files, source ledgers and appropriately limited prior reviews. Missing or unqualified history remains missing or unqualified.

All original 6,268 tracked files, including FINAL, G1/G2, videos, shaders, camera, historical scenes and assets, are covered by the additive preservation snapshot. The original 307-file hash contract is checked separately. Old private caches absent from this fresh execution environment are not claimed to have retained their prior machine's inode/mtime.

## Explicit remaining limits

This is a bounded review implementation, not unrestricted worldwide production readiness:

- Structured data prompts only; free natural-language fact extraction and research are unsupported.
- Connected new pixel families are `WAR` and `TRANSPORT`. Existing `LINE_METRIC` and `DISASTER` Planner code is preserved, but this new pixel consumer rejects those families explicitly.
- Five registered regional source profiles, regional locked V5 camera, 1080×1920, 30fps and 16–240 frames per scene. Arbitrary global coverage, new data sources, arbitrary camera motion, close zoom and physical speed are not silently approximated.
- Supplied labels and object-profile names are metadata where documented. Requested visible text, arbitrary style controls and other undrawn features are rejected.
- Aviation and trade fixtures connect modern city coordinates illustratively. They do not assert real airports, ports, services, navigable paths, traffic volumes or trade measurements.
- Korean War exact full-control and Roman Empire extent examples remain `NEEDS_INPUT`. Existing partial historical front lines do not establish bilateral ownership. The qualified partial-line fixture additionally reports the unconnected `LINE_METRIC` consumer as `UNSUPPORTED`.
- No gCube workload, paid GPU, paid API, deployment, 80-second film or FINAL promotion is authorized by these tests. This source path's inclusion in a running GPU image has not been established in this task.
- Dropbox was not invoked. Public GitHub artifact download verification is a separate delivery test and is not a Dropbox synchronization claim.

Actual execution, frame audit, protection and download evidence are recorded in the final gate and accompanying reports. A code or software-WebGL result cannot establish NVIDIA performance or user-approved video quality.
