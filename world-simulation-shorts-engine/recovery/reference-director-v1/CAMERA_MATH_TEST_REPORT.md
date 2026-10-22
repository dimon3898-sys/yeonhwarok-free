# Independent camera math verification

Base: `82854af429d09aebb4b31c2f168e2f0ddc9560c9`.

Command run successfully in the free CPU environment:

```sh
node --test --test-isolation=none --test-reporter=tap world-simulation-shorts-engine/recovery/reference-director-v1/tests/director_camera.test.mjs
```

Latest independent review result: **19 tests passed, 0 failed, 0 skipped**. The persisted updated TAP log is `evidence/DIRECTOR_CAMERA_TEST_attempt02.tap`.

The earlier17-test passing run remains intact as `evidence/DIRECTOR_CAMERA_TEST.tap` and its preserved copy `evidence/DIRECTOR_CAMERA_TEST_attempt01.tap`. The review fix was made after checkpoint `3b0e65a387a500ddd3b9a6ddce4e1e746400f415`; the503-test baseline was not repeated for this isolated new-module validation.

The initial default-isolated Node invocation did not provide child-suite diagnostics in this sandbox. Running the same suite with Node's supported `--test-isolation=none` produced the full results. Two initial fixture checks failed because the fixture source-truth contract is a string rather than an object; the tests were corrected to inspect the actual explicit synthetic-source statement. No renderer or fixture data was changed to obtain the passing result.

Verified behavior:

- Honest global546-frame mapping and180/180/186 partitions; invalid gaps, overlaps, frame counts and oversized windows rejected.
- Forward/inverse standard-parallel Q and uniform similarity across angles, scales and anchors; no private native camera mutation.
- Joint two-anchor framing and geographic hero anchoring.
- Unchanged polygon geometry with explicit incompatible-aspect residuals.
- Heading derived from a supplied geographic segment rather than treating a measured screen angle as camera Euler yaw.
- Whole-track bounded C1 interpolation of center/log-scale/unwrapped angle, finite motion across sample constraints, deterministic random access.
- A review window may end wider without a fake endpoint or altered legacy final-closest rule.
- All four rotated viewport corners and every546-frame source bbox/pixel-spacing check; insufficient coverage/resolution remains blocked.
- Missing source evidence and partial global tracks rejected.
- The same mathematical API on two explicitly fictional, nonrectangular, different-hemisphere fixtures with different labels.
- Canonical projection descriptor validation at public projection/inverse/compile boundaries. Missing fields, nonfinite/zero/inconsistent standard-parallel cosine, mismatched center and invalid bounds are rejected with `DIRECTOR_PROJECTION_DESCRIPTOR_INVALID`. Created descriptors and their bounds/center arrays are immutable.
- Wrapped longitude bounds, polygon/anchor/segment collections spanning more than180degrees, and points requiring a wrap relative to the projection origin are rejected with `DIRECTOR_DATELINE_WRAP_UNSUPPORTED`. This bounded profile does **not** silently interpret179to−179as a358-degree long-way shape. Unwrapped local geometry near the dateline remains supported. Actual wrapped geographic rendering requires a separately designed projection contract.

The review reproduced two real input-validation gaps in the new module before fixing them: a descriptor with cosine0 yielded an infinite inverse coordinate; and a179/−179anchor pair produced a long-way pose instead of an explicit unsupported error. A descriptor missing its center threw a generic TypeError. These are new-module mathematical input defects only, unrelated to the protected native renderer barrier. Focused regressions now verify explicit failures without changing source geometry or relaxing assertions.

**Not verified:** source-bound reference camera fit, actual map rotation, native draw/readPixels, real geographic detail/source license/admission, screenshot similarity, mobile browser graphics, NVIDIA graphics, reference MP4 production or video quality. No actual reference camera was invented from missing data. Every compiled mathematical result declares `NOT_CONNECTED_CAPABILITY_EXTENSION_REQUIRED`; source hashes, NoData and licenses require the separate data gate.

The protected renderer capability barrier is documented in `CAPABILITY_GAP_AND_PATCH_MAP.md` and `CAPABILITY_AUDIT.json`. This report is a mathematical test PASS only and does not advance blocked production gates.
