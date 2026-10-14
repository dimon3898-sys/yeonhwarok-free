# ASTRA CPU data layer V1

This isolated extension prepares real geographic data for later GPU integration. It never starts WORLD ENGINE rendering. See the required completion report and contracts.

Use installed `/usr/bin/python3` with Python3.13.5, NumPy2.2.4, Pillow11.1.0, GDAL3.10.3 and libnetcdf4.9.3 (`DEPENDENCIES.json`). No pip installation is needed. Existing regression tools also use installed Node24.19.0. Run from this directory:

```bash
/usr/bin/python3 -B run_tests.py --phase ALL --output evidence/ALL_TEST_RESULTS.json
/usr/bin/python3 -B run_regressions.py
/usr/bin/python3 -B check_protection.py
```

To reproduce the saved tiny real-data fixture into a new output directory:

```bash
/usr/bin/python3 -B prepare_data.py   --scene fixtures/LOCAL_DATA_SCENE.json   --archive ../astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip   --cache-dir /workspace/astra-cpu-optional-cache   --output /workspace/astra-cpu-neutral-output   --accept-recorded-license-evidence
```

The license flag is an explicit assertion of the preserved Phase A notices/review, not a license waiver. Without it, selected providers return license_unverified and no raster is emitted. A missing/disabled mapData scene does not inspect the archive or create a cache. Source archive and byte-exact source/sidecar hashes are permanently tracked in Phase A; neutral examples are tracked here. The mutable cache is optional; no preexisting `/tmp` file is required.

Compare produced NPZ/preparation-manifest SHA with `fixtures/neutral-output/`. The CLI preserves identical output files and refuses differing ones; use a separate output directory when request/source configuration changes. Output and cache directories may not alias input files or each other. Live network is off by default; no supplier download is claimed.

For geographic source requests: use the data request planners from `astra_cpu.acquisition`, source-bound `DownloadRequest`, opt-in bounded `DownloadManager` and the shared raw cache. Supply verified source metadata/axes/layout rather than guessing registration or generating full-world requests. CPU values/masks/axes remain neutral; actual GPU allocation/material/API integration is listed separately in `GPU_INTEGRATION_TODO.md`.

Status: CPU_ONLY_READY_FOR_GPU_INTEGRATION. User review is required before resuming the hardware phase. No visual-quality PASS, new proof, 14-second expansion or FINAL promotion is included.
