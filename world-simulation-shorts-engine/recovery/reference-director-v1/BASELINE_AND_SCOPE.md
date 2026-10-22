# Baseline and scope — Reference64306 director V1

The exact starting commit is `82854af429d09aebb4b31c2f168e2f0ddc9560c9` on `development/reference-director-v1-20261022`. No existing source has been altered. All additions are confined to `world-simulation-shorts-engine/recovery/reference-director-v1/`.

## Actual preservation gate

- Original protected manifest SHA-256: `cc09c9dca0262b800387df1d27e6ac91d0fd18d2c5c582862cc600baf843ce3e`.
- **307/307 original files matched actual bytes and size** (306 repository files and one existing canonical generated Plan). No canonical file was reconstructed.
- **6,746 pinned Git files** matched actual SHA-256, size, and their exact starting Git blob. The complete list is in `reports/PROTECTION_BASELINE.json`.
- Existing private/cache roots: **4**, **1,059 metadata entries** captured with size, inode, mtime, mode, owner and kind; symlinks are not followed.
- Existing three worktrees are clean and preserved at their recorded HEADs. No old worktree, cache or report is a test-output destination.
- `reports/PROTECTED_307.csv` contains the exact original protected list and actual hashes. `reports/PROTECTION_INITIAL.json` records the initial PASS.

| Existing worktree | Recorded HEAD |
|---|---|
| `/workspace/yeonhwarok-free` | `7f882ce970feb051700bf76e828dd81fe374f1d2` |
| `/workspace/world-engine-universal-data-pipeline` | `b0d013832ee38571f9d3dfe685ce63f7083ba90f` |
| `/workspace/world-engine-universal-presentation` | `82854af429d09aebb4b31c2f168e2f0ddc9560c9` |

## Baseline tests

The previous **503** is a historical report count, not reused proof. `tools/run_baseline_503.py` actually re-executes the preserved suites. **Current actual result: 503 PASS, 0 FAIL, 0 SKIP.** Successful suites are not repeated when a sandbox-only localhost failure is retried.

Test assertions and preserved source files remain unchanged. Python's test TemporaryDirectory `/workspace` destination is relocated into a unique new private root; Node's two newly created output-root literals are relocated by an explicit load hook. The original command and executed wrapper command are both recorded. Original reports and old private caches are never output destinations. Fixture cleanup affects only files freshly created by that test run.

Actual test logs are under `reports/baseline-503/`. New private data is under `/workspace/reference-director-v1-private-20261022/baseline-503/`. Attempt 01 retains a genuine sandbox `PermissionError: [Errno 1] Operation not permitted` at the Studio22 localhost socket. This is distinct from a product failure. The officially escalated attempt resumes that suite and the remaining suites, preserving the 266 successful checks from this same execution.

The 503 suite inventory is: original G2 143; prior prompt/schema/Studio/capture 155; natural language 70; presentation schema 15; region 44; presentation plan 23; preparation 17; Studio presentation 36. Final results are in `reports/baseline-503/attempt-02-localhost-authorized/RESULTS.json`; it pins attempt 01 and its 266 successful checks by SHA, then records the remaining 237 successful checks. The exact 503 named test outcomes are listed in `reports/BASELINE_503_TEST_INVENTORY.csv`; suite counts and both commands are in `reports/BASELINE_503_SUITE_RESULTS.csv`. Successful prefixes are from this execution, not historical reports.

## Reproduction commands

```sh
PYTHONDONTWRITEBYTECODE=1 python -B world-simulation-shorts-engine/recovery/reference-director-v1/tools/protection.py --acquire
PYTHONDONTWRITEBYTECODE=1 python -B world-simulation-shorts-engine/recovery/reference-director-v1/tools/run_baseline_503.py --attempt attempt-01
PYTHONDONTWRITEBYTECODE=1 python -B world-simulation-shorts-engine/recovery/reference-director-v1/tools/run_baseline_503.py --attempt attempt-02-localhost-authorized --resume-from attempt-01
PYTHONDONTWRITEBYTECODE=1 python -B world-simulation-shorts-engine/recovery/reference-director-v1/tools/protection.py --output PROTECTION_FINAL.json
```

Acquisition is exclusive and must not be rerun over an existing baseline. Test attempt IDs and final preservation report names must be new. Official sandbox escalation is needed only for free local HTTP security tests, not for paid resources.

## Limits

These are CPU contract/regression checks. They prove neither new director pixels nor reference visual quality, physical Android behavior, NVIDIA execution, historical G3 readiness or FINAL approval. No paid GPU/API, deployment, 80-second render, old-image modification or FINAL promotion is performed by these tools. Existing UI and deployment are outside the change scope.
