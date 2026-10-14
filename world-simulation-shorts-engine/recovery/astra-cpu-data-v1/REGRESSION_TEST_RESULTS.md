# Final CPU regression results

| Group | Result | Actual evidence |
|---|---|---|
| New CPU implementation | PASS, 233/233; FAIL0/SKIP0/BLOCKED0 within the executed suite | `ALL_TEST_RESULTS.json` and log |
| Existing Flat terrain/cache | PASS, 10/10 | `flat_terrain_cache.log` |
| Existing production visual/cache keys | PASS, 5/5 | `production_visual_cache.log` |
| Existing pure frontier/camera/control evaluator | PASS, 4/4 | `frontier_cpu.log`; no browser or GPU |
| Old pinned assets/source/media/Final manifests | PASS, 209/209 SHA/size matches; changed protected paths0 | `PROTECTION_RESULTS.json` |
| Fresh worktree CPU extraction | PASS, 4/4 exact SHA comparisons | `FRESH_WORKTREE_REPRODUCTION.json` |
| Supplier live network/access | BLOCKED, not configured / not executed | `DATA_ACQUISITION_REPORT.md` |
| Physical GPU and rendered video quality | SKIP, outside CPU instruction / not executed | `GPU_INTEGRATION_TODO.md` |
| Whole old engine/Planner suites, 250-frame render, Permanent Gate | SKIP, no affected core changes; not executed | CPU task scope |

The final 233 comprise B/C92 + D46 + E62 + F33. Per-case names/status/details are retained in the JSON, separating actual archived source cases from generated COG, synthetic grids/geographic cases and injected HTTP mocks. Real source fidelity includes full original Float32 TIFF heights, all 230400 signed NetCDF elevations/ASCII values and their axes, and exact PNG channels/PGW/PRJ. Southern/western/date-line, missing tiles, versions, unsupported regions/CRS, half-pixel registration, masks/nodata and cache interruption are covered. Synthetic geometry does not certify global real supplier coverage.

The existing commands each ran once with a60-second subprocess cap. Node24 emitted Unicode summary `ℹ tests4` rather than TAP `# tests4`; the report counter was corrected by reparsing the unchanged successful saved log, without rerunning the tests. Exit0 and four passing actual test records are preserved. Duplicate earlier checkpoint evidence is historical, not additional final test counts.

Protection reuses existing frontier166, Master17, Phase A input/media and approved Flat17 inventories, deduplicates them and adds four Final manifest pins from Phase A Git bytes. It does not extract or repeat the 24-member ASTRA audit. Final/source protection applies to the entire old tracked tree through the baseline diff as well. All task changes remain isolated under `recovery/astra-cpu-data-v1/`.

No technical CPU result is reported as video-quality PASS. No video was generated/reencoded; no approved engine style/timing or FINAL was tuned to pass a test.
