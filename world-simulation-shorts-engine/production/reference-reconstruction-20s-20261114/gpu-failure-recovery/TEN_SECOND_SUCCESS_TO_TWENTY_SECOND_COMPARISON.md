# 10-second GPU capture success → 20-second failure: evidence-bound comparison

Status: BLOCKED_ROOT_CAUSE_UNKNOWN. No GPU execution, production modification, image build, or prior PASS rerun.

## Verified 10-second capture counterexample
- Source: production/capture-json-size-fix-v13/evidence/CAPTURE_DIAGNOSTIC.json
- Job studio-06ff7116b2bb6c464a64c1a576f3faf0; 300/300 frames; nativeProofCompleted=true; capture process exitCode=0.
- This is **not** a proven final MP4/receipt success: missingEvidence.capture=true; capture.code=UNCLASSIFIED_EXCEPTION.
- Expected image digest sha256:bb97c55401f25abba360f648b7f240be900ab44cbed2d9926a4ccc5a3be68726; actual image digest not observed.
- Driver 580.126.09; UID/GID 1000; GPU backend vulkan; graphics environment records no Vulkan ICD override; safeActualArgs include --enable-unsafe-swiftshader as well as Vulkan/ANGLE and --disable-software-rasterizer.
- Browser diagnostics say nativeGraphicsInitializationVerified=false. Native frame success is not standalone proof of hardware-backed EGL context or identical node environment.

## Verified 20-second failure
- Job studio-aa674e471413a268fb2f8da56e66535c; 0/600 frames; UP2_WEBGL2_REQUIRED / EGL_NOT_INITIALIZED at WEBGL_CONTEXT.
- Expected published image digest sha256:f44f5c9a6d948fb7a08476465566d7363fc4c1008526a4ab67681537bd700795; failed pod actual digest not attested.
- Different GPU allocation/node from 10-second capture, though same recorded driver version and safe browser args.
- Existing RECURRENCE_COMPARISON.json reports source-level browser launch options and Controller runtime allowlist byte-identical across successful and failed versions. Therefore a newly introduced change in these exact scoped functions is **not evidenced**.

## EGL path audit already PASS as an investigation, not GPU remediation
- Existing graphics helper is called by sibling legacy GPU admission process, not Studio's Controller→Worker→capture ancestry.
- No guaranteed handoff of generated descriptors to Studio; Controller's environment filter drops __EGL_VENDOR_LIBRARY_FILENAMES and VK_DRIVER_FILES.
- No incident record proves descriptors were generated in the failed pod. A later manual /tmp descriptor on a different pod still yielded webgl2=false, but was not formal UID1000 Worker execution.
- Do not patch only the allowlist: this cannot create absent selector values and can widen unvalidated environment paths.

## Minimum next steps (free, no PASS reruns)
1. Reuse the above two existing capture diagnostics and prior comparison; do not rerender 10 seconds.
2. Recover, if already retained, original failed-pod admission_private.json graphicsPreparation and selector evidence. Do not request a paid GPU start for retrieval.
3. If not recoverable, keep incident-causation BLOCKED and isolate a new *prospective* GPU initialization contract repair from retrospective incident claims. Any code edit requires an explicit changed-scope gate and trusted descriptor validation.
4. Before a separately authorized GPU check, require proof that the formal Studio child receives the prepared descriptors and that UID1000 can read them. Test WebGL2 + hardware renderer first, not 600 frames.
5. Preserve the original 20-second design and 10s×2 segmentation; no time compression.

Evidence: RECURRENCE_COMPARISON.json; EGL_RUNTIME_PATH_AUDIT.md; ENV_PROPAGATION_AUDIT.json; CHECKPOINT.json; production/capture-json-size-fix-v13/evidence/CAPTURE_DIAGNOSTIC.json.
