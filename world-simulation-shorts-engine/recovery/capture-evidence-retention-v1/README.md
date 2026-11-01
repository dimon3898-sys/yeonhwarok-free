# Capture evidence retention — 2026-11-01

This change prepares the existing capture path to retain the safe runtime facts missing from the stopped job `studio-7d7a08be1d09817c903f41484bce3f33`. It does **not** establish or fix the GPU root cause, replay the old failure, or authorize a GPU run.

## Handover and preserved evidence

- Read all PART 1–19 of `WORLD_ENGINE_전체_인수인계_20261101.txt` and reconciled them with the operating checkpoint at `296402e71257c7847d0045215ca0cdaf3dd700d2` and research branch at `c2340920a015b0f02b090a4cd2d19ed3e107b149`.
- Reuse the existing 19-file knowledge base on `research/gpu-webgl-knowledgebase-20261101-7d7a08be`; no rewrite or repeated raw-file search.
- The old job's confirmed failure is `UP2_WEBGL2_REQUIRED`, `PAGE_EVALUATE_FIRST_NATIVE_DRAW`, 0/300 frames. Root cause remains unconfirmed. Its safe diagnostic SHA256 is `0f61c08da02b98fba68f08f9964c416a3d0d9adf9553e6113fcfc1e75df8baed`.
- The original `CAPTURE_RECEIPT.json` and `GPU_ALLOCATION.json` were not recovered in the prior investigation. No other job's receipt is substituted.
- Preserve the surface-restore parent image digest `sha256:c9fa126b0bf0d06c109bbe45f9fe14b5cc71de4282a4a57455b3b5f19d3366b5`, its tag/backup, main, existing data, and prior PASS evidence.

## Confirmed information-loss paths and minimal changes

| File | Existing gap | Change |
|---|---|---|
| `controller/nvidia_backend.py` | The capture environment did not enable Playwright browser logging. | Add a capture-only environment helper with fixed `DEBUG=pw:browser`; no inherited wildcard or arbitrary debug destination. |
| `controller/lease_supervisor.py` | Non-JSON child output was discarded; native browser initialization errors and final browser exit were not retained. | Consume bounded existing Playwright output into fixed safe fields; atomically preserve a snapshot and final supervisor evidence. Distinguish browser exit from Node capture exit. |
| `controller/safe_capture_export.py` | Existing safe export omitted receipt dependency/profile facts and GPU allocation metadata. | Add `runtimeEvidence` to the existing SAFE_V3 export, with strict re-filtering and an explicit missing/expected/actual distinction. |

Only the three source rows and their existing runtime manifest → bootstrap pin → startup manifest chain change. Capture source, WebGL context calls, browser rendering options, generated manifest, approval, GPU lease and cleanup gate are preserved. No integrity bypass.

## Data and safety contract

- Preserve recognized public browser binary paths, selected actual argument tokens, version numbers, GPU model/driver/memory and hashed GPU identifier. Unknown arguments, paths and arbitrary text are omitted; hashes and omission counts are retained.
- Native messages yield only allowlisted Vulkan/EGL/GL codes, function names, fixed categories and line hashes. Categories are observations, not proven root causes.
- Driver capabilities use a fixed allowlist. Device selection and Vulkan override retain selection class/presence and hashes; library/display/runtime paths retain presence only. No tokens, Owner codes or whole environment are exported.
- Diagnostic input line cap 16 KiB, cumulative native input cap 256 KiB, at most 32 native events; existing 128 KiB JSON progress contract remains. Export inputs and final JSON retain a 64 KiB bound.
- `imageIdentity.expectedImageDigest` is from the private plan or capture environment, with source and agreement fields. `actualImageDigest` stays null / `NOT_OBSERVED_FROM_APPLICATION_PROCESS`; application environment is not registry or host attestation.
- Export still requires `cleanupVerified:true` and uses the existing isolated, time-bounded helper. Storage failures do not replace the original capture failure or authorize release of an unresolved lease.

## Persistence and retrieval

Existing private sources: `<control_root>/handoff-gpu-jobs/<jobId>/capture/CAPTURE_RECEIPT.json`, sibling `GPU_ALLOCATION.json`, `PLAN.json`, `BROWSER_DIAGNOSTIC.json`, and `LEASE_SUPERVISOR_RESULT.json`.

Existing post-cleanup exporter writes `CAPTURE_DIAGNOSTIC.json` and `SHA256SUMS` under `/world-storage/capture-diagnostic-<jobId>/` with exclusive directory creation, atomic files and fsync. This patch extends the existing safe artifact rather than adding another service or diagnostic runner.

Free mock failure tests exercise the existing isolated exporter subprocess, verify SHA256, remove the synthetic private job, and recover the shared export. This proves local persistence/retrieval behavior only. Real gCube mount delivery, remote Dropbox retention after shutdown, actual browser stderr contents, GPU initialization and workload image attestation remain **NOT_RUN**.

## Focused validation and publication

`FOCUSED_RESULT.json` binds the observed new test results to exactly six overlay files. Individual new test outputs and independent static review are in `evidence/`. Existing PASS suites were not rerun. The export and packaging test tools each initially returned no observable result due to the tool output/context limit; their new checks were called again with file capture. This is recorded separately from old PASS reruns and GPU retries, both zero.

The one-time build workflow uses the fixed successful parent, requires this exact branch/parent/message/run-attempt, reserves a permanent release before building, archives the complete image before push, and checks the new overlay bytes/configuration plus published digest/config identity. Existing image tags are checked unchanged. This is a new-image identity check, not a rerun of the previous full CPU/GPU suites.

## Official logging basis

- Playwright v1.62.1 `packages/utils/processLauncher.ts`: launch, browser stderr and exit logging; `packages/playwright-core/src/server/browserType.ts` and `progress.ts` connect the `browser` namespace after launch. Source: https://github.com/microsoft/playwright/tree/v1.62.1
- Playwright CI troubleshooting documents `DEBUG=pw:browser`: https://playwright.dev/docs/ci#debugging-browser-launches

The fixed logger was selected from the exact existing Playwright version's source. No Chromium GPU flag was guessed or changed.

## Next authorized GPU execution target

After separate user approval, use the prepared image and unchanged existing 10-second input/path once. Determine whether actual Chromium launch and native error evidence are present; compare NVIDIA allocation/graphics conditions, Vulkan/ANGLE/GPU-process codes, first-failure stage and image identity to the preserved success evidence. If capture succeeds, preserve MP4 and SHA256. If it fails, retrieve the extended safe artifact before stopping the workload, then verify Finished/node release. Do not add a one-frame CLI mode, repeat the old standalone runner, retry the render, or claim WebGL2 PASS from these CPU checks.
