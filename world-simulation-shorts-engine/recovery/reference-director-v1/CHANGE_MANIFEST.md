# Change manifest

All changes are additive in `recovery/reference-director-v1/`. Existing tracked files, the protected native renderer/shaders and existing outputs/caches were not changed.

- Camera/model/window contract: `director_camera.mjs`
- Authored events, SVG pins and existing glyph measurement: `director_events.mjs`, `assets/`
- Authenticated read-only Studio gate: `studio_preflight.py`
- Partial input and source bindings: `REFERENCE_DIRECTOR_INPUT.json`, `DATA_BINDING_ADMISSION.json`
- Non-executable 546-frame event track and unmeasured trace: `COMPILED_DIRECTOR_TRACK.json`, `INPUT_TO_PIXEL_TRACE.csv`
- Focused tests, baseline503 rerun, source audit, protection/secret checks and evidence: `tests/`, `tools/`, `reports/`, `evidence/`
- Input analysis/specification data only: `supplied/`; source video/screenshots excluded.

Complete snapshot list/hash is `CHANGE_MANIFEST.json`. Its own files and later packaging/download receipts are enumerated separately by `SHA256SUMS`/the public package receipt. No complete-reference MP4 or comparison PNG was generated because the native capability and data-detail gates are blocked.
