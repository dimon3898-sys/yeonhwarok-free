# Baseline regression results — actual execution

**298 PASS,0FAIL,0SKIP.** All tests were run again in this task against the unchanged `b0d0138` source checkout. Previous reports were not treated as fresh executions.

The preserved143 tests ran first, in their original ten-suite order. Then the previous pipeline's109prompt,14JSONSchema,22Studio and10capture tests ran. All14 commands, elapsed times, exit codes, expected counts and complete stdout/stderr are under:

- `reports/regressions/actual-298-01-original143/RESULTS.json`
- `reports/regressions/actual-298-01/RESULTS.json`

The runner is `tools/run_baseline_298.py --attempt actual-298-01`. Its only adaptation to the old runner is relocation of the result destination in memory. All old test files, assertions, expected counts, source files and old report bytes remain unchanged. Historical provenance fields inside the preserved runner retain their original values; the new aggregate report explicitly names `b0d0138` as the task baseline.

The combined observed suite time was approximately36seconds. No renderer performance inference is made from this unit/contract-test duration. Localhost HTTP authentication/CSRF/Origin tests executed through the supported sandbox execution permission. No external paid API, GPU deployment or NVIDIA validation occurred.

The protection checks before and after execution are separate from test counts. The original307 SHA identities and all6,439 baseline tracked-file hashes match. Both preserved checkouts remain clean and unchanged.565 existing cache metadata entries across three roots retain their inode, mtime, size, permissions and kind; no cache content was altered or deleted. See `reports/PROTECTION_INITIAL.json` and `reports/PROTECTION_AFTER_298.json`.

These results show that the **existing** baseline remains valid. New natural-language extraction, dynamic regions, camera motion, feature composition, actual Studio movies and user visual quality still require their own later gates. This report does not mark those unexecuted features PASS.
