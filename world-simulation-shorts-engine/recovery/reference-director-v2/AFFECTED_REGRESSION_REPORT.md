# Change-impact regression report

Latest authorized renderer SHA at run: `9f60a7e4a6299b23b6c9070be4b830a3bbad25f5e1b321e5eff383ce35fb4995` (candidate05).

Actual unchanged existing test sources were verified against the immutable5cc9b98 snapshot before execution. No assertion, expected value, source fixture or existing output was changed.

| Existing suite | Tests | Result | Reason |
| --- | ---: | --- | --- |
| `world-simulation-shorts-engine/tests/camera_director_v5.test.mjs` | 21 | PASS | Preserved minimum context, canonical portrait aspect, closest-stop and admission ownership |
| `world-simulation-shorts-engine/tests/reference_camera_adapter_v1.test.mjs` | 7 | PASS | Preserved deterministic bounds track, fixed admitted endpoint and locked-state truth |
| `world-simulation-shorts-engine/tests/visual_detail_admission_v1.test.mjs` | 17 | PASS | Preserved independent source-detail/readability admission, not an opt-in bypass |
| `world-simulation-shorts-engine/recovery/universal-presentation-v2/tests/test_presentation_plan.mjs` | 23 | PASS | Existing presentation selection, projection round-trip, source viewport and moving-admission contract |

**68 PASS /0 FAIL /0 SKIP** on candidate05. These are selected directly adjacent existing contract tests. They are not claimed to be the exact subset of the prior503 inventory, nor a new run of all503. Commands, original source hashes, stdout/stderr and actual exit codes are in `reports/affected-regressions/after-renderer-02/`.

The first68-test run, on candidate04 SHA
`c5aaf6b902d5f5374d93230e8979919dee398e47c41cf65a12e3bf2a35b55f9d`,
is preserved separately in `after-renderer-01/`. Its CPU contracts passed even
though the actual default-globe pixel gate subsequently failed. Candidate05
changed the native shader selection, so a new run of the same68 unchanged tests
was justified. Neither CPU result resolves native pixel variance or grants a
production/video gate PASS.

The preserved prior503 PASS evidence remains a historical result from5cc9b98. It has not been relabeled as a post-modification full rerun. Actual native default/globe and opt-in draw/readPixels are a separate mandatory gate owned by the pixel audit; these CPU contracts do not establish image or video quality.

## Intentional old seal distinction

The prior `reference-director-v1/studio_preflight.py` pins the old renderer SHA. It must reject a changed renderer, even an explicitly authorized one. The old test, seal and original307 manifest were not modified to grant the new path access. This is not a default renderer failure or justification to weaken the old check. A new opt-in execution path must separately bind the authorized new renderer identity.

## Output isolation

All new test logs live in this namespace and temporary outputs use the matching
`/workspace/reference-director-v2-private-20261022/affected-regressions/`
attempt directory. The old worktrees/cache roots are not written. No browser or
GPU render, API deployment, paid service or80-second output was started by this
runner.
