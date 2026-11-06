# Source variant preflight mismatch — 2026-11-06 KST

The user supplied a preflight screenshot showing HANDOFF_EXACT_VARIANT_SET_REQUIRED. The file itself was not the problem: QUALITY_LABELS_10S.json remains SHA256 281250a9f3c866d4d0a424da0d06a6e9a3cf4e2ab31660b879657e7ab0b3a24e.

Confirmed defect: the frame1 patch updated original presentation_runtime.mjs and GENERATED_SOURCE_MANIFEST.json, but capture_nvidia.mjs still required the previous original runtime hash. Its exact variant check rejected the new, correctly hashed source. The last packaging checks validated installed source bytes and startup closure, but did not execute validateVariantManifest. This omission is ours.

One runtime line is corrected, plus3dependent source/startup pins. No validation guard is removed. Actual files: backend/capture_nvidia.mjs, RUNTIME_SOURCE_MANIFEST.json, studio-cold-start-v2/bootstrap.py and STARTUP_MANIFEST.json. See SOURCE.patch and the new source seal.

Validation: baseline error reproduced locally. Candidate validates all3real source pairs and rejects old-pin and duplicate-variant metadata. On public standard CPU CI42145763081, UID1000 in the pinned existing image with4read-only overlays passed the startup/source closure and actual prepareNvidiaRuntimeRequest plus verifyNvidiaPreparedRuntimeRequest. Both segments and the300-frame plan were prepared and verified in3.265seconds. Network disabled; GPU, browser, encoder and rendered frames all0. Historical frame1/quality/control PASS suites were not rerun. This does not claim full Studio HTTP preflight, real gCube mount or completed MP4 success.

No image was built or published and no gCube setting or GPU state was changed by this correction work. Live GPU state was not inspected; user was advised to stop any running workload while awaiting the fix.

Next: approve1new additive image publication plus existing stopped workload image/digest update. Previous1-image authorization is consumed. Preserve129parent layers, source/runtime checks, same example and existing settings. Run verifyGeneratedSources inside the candidate image before publication. GPU start/render still requires its own separate approval.
