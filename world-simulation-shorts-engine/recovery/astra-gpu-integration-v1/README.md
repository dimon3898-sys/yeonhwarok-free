# ASTRA GPU handoff — partial preparation, inactive rendering

Current decision: **ASTRA_GPU_INTEGRATION_PARTIAL_BLOCKED**. This package does not activate ASTRA in the existing65422 rendering path. No new ASTRA image, GPU video or visual PASS is claimed.

Only the missing CPU→WebGL2 resource handoff is implemented here. The original ASTRA providers, raw data, cache and optional Scene preparation are imported unchanged. Existing FINAL, renderer, camera, territory/frontier, national-unit design, GPU admission, encoding, storage and detached manager remain untouched.

## Reuse and actual connection state

| Function | Actual state |
| --- | --- |
| ASTRA CPU source parsing, provenance, request/crop, cache, Scene preparation | Existing complete code, already packaged; reused |
| Physical GPU/WebGL2 and original65422 output/Dropbox playback | Prior completion supplied by the user; not repeated here |
| Native GIS land coverage and projection | Existing renderer API; no new coastline invented |
| Numeric upload bundle and WebGL2 allocation helper | New code, CPU and explicit fake-context tests only |
| Current-frame GIS/projection binding plan | New validation plan only; no depth sampling or coastline-alignment claim |
| ASTRA height/surface/depth visible material | Not implemented/connected; current selector is blocked |
| ASTRA connection to existing relief light, territory/frontier composition | Not connected; protected original composition remains active |
| Physical NVIDIA upload, coast seams, frame time and video quality | Not executed; hardware validation required |

The source-bound [connection audit](evidence/CONNECTION_AUDIT.json) identifies exact files, lines, hashes and saved regional coverage. Audit `PASS` means the known source path was checked; its separate integration decision stays `BLOCKED_PROTECTED_ACTIVE_SELECTOR`.

## New entry points — CPU preparation only

- `upload_bundle.py`: `build_upload_bundle`, `export_upload_bundle`, `prepare_upload_bundle`. Reuses `prepare_scene` and `CpuDataPipeline`; no second parser/cache/Scene implementation.
- `gpu_upload.mjs`: `loadUploadBundle`, `describeUploadBundle`, `createUploadTextures`, `planScreenDepthSampling`. No shader, material, draw loop, camera, public service or GPU admission is added.
- `check_integration.py`: read-only source/selector/protection classification; does not run GPU.
- `verify_bridge.py` and `crosscheck_bundle.mjs`: explicit CPU fixture transport over the existing saved small ROI; not a renderer or real HTTP download test.

Run focused local checks using the already installed system GDAL/NetCDF/NumPy/Pillow Python and Node24.19:

```sh
/usr/bin/python3 -B -m unittest discover -s world-simulation-shorts-engine/recovery/astra-gpu-integration-v1/tests -p 'test_*.py' -v
node --test --test-isolation=none world-simulation-shorts-engine/recovery/astra-gpu-integration-v1/tests/test_gpu_upload.mjs
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/astra-gpu-integration-v1/verify_bridge.py
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/astra-gpu-integration-v1/check_integration.py --repo-root .
```

No old8/104/233-test full suite, source research, supplier retrieval or24-member archive audit is repeated. Existing three source hashes are checked only as required by the reused providers during the new handoff test.

## Why adding an image layer would not activate ASTRA

The unchanged manager fixes `launch.py --render-65422`; the unchanged GPU launcher fixes `hardware_render.mjs`; its runtime creates V4 directly without a pre-pipeline hook. V4 renders native with `dem:false`, then its local terrain material replaces the source color. The original source contract also states `heightSourcePresent:false`. Passing height, attaching `mapData` or adding files to an image cannot select the new material.

This task stops that protected selection change as requested. It does not rewrite module responses, monkeypatch original runtime, replace immutable source files, abuse TEST_ONLY runner seams or paint ASTRA over completed territory/units. The free workflow tests the inactive handoff using the existing immutable image; it has no Docker build, push or GPU deployment phase. A meaningless image containing unused code is not registered as an ASTRA renderer.

## Next safe integration boundary

See [ACTIVATION_CONTRACT.md](ACTIVATION_CONTRACT.md) for the concrete separately versioned runtime/material selection needed to finish. Existing frozen files can remain intact, but that new execution lane, its composition and its job identity need implementation and validation. This is broader than inserting data into an existing supported hook, because that hook does not exist.

Do not redeploy or rerun the already successful65422 job expecting this package to change it. Do not delete its claim or result. Keep its current image/output intact. No paid GPU operation is authorized or performed by these CPU checks.
