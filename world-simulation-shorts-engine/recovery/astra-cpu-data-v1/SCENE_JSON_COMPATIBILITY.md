# Optional Scene JSON CPU preparation

The existing parser, strict planner schema, renderer API and stored Scene files are unchanged. `astra_cpu.scene.prepare_scene(scene, sources=None)` is an independent wrapper that consumes only top-level optional `mapData` and returns a deep copy of every original renderer field. Augmented input must pass through this wrapper before a legacy strict parser; the old parser is not claimed to accept a new field directly.

The extension supports `enabled`, `bbox` in W/S/E/N, `crs` (currently EPSG:4326), positive `targetGroundResolution`, any explicit role selector `terrain`, `bathymetry`, `surfaceTexture` with exact `{sourceId,version}`, and bounded `cache` policy. The additive schema is `fixtures/map_data.schema.json`. No scene geometry/country/camera is used as an inferred source region. Date-line requests are split explicitly; unsupported CRS returns an error.

Missing or disabled settings do not resolve sources, create a cache, fetch bytes or activate rendering. Present disabled fields are still type/limit checked, and incomplete selectors may remain staged. Enabled settings require bbox and at least one explicit source role; unknown fields, IDs, mismatched versions/roles or invalid limits fail. SourceSpec bindings are detached deep snapshots so later catalog metadata mutation is detected before extraction. Input Scene and defaults remain unmodified.

Configuration preparation does no provider execution. `CpuDataPipeline.prepare(preparation)` is the explicit local CPU execution step; it respects read_write/read_only/bypass and the configured maximum artifact size. Concurrency/retry/timeout settings are prepared for the standalone DownloadManager; this local archive CLI does not make HTTP calls. `gpuActivation=False` is fixed and cannot be requested through Scene JSON.

Actual stored `MAP_ENGINE_UNIT_SCENE_V4` and `PLANNER_SCENE_JSON_V1` are compared by full deep equality and canonical renderer-payload SHA, including camera, timeline, units and layout. Augmented copies strip only mapData. Canonical SHA uses sorted-key compact ASCII-escaped finite JSON; it is not an original file-byte SHA or GPU render receipt.

Final F: **33 PASS** (16 config tests and 17 pipeline/CLI tests); evidence in `F_FINAL_TEST_RESULTS.json`. Fresh-process local exports are deterministic; disabled CLI ignores a missing archive and creates no cache. Read-only cache initialization performs no directory creation. GPU upload, old parser modification and camera/layout integration remain deferred.
