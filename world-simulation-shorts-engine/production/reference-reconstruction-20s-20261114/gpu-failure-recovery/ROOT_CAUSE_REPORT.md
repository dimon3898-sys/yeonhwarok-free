# GPU failure root-cause investigation

Status: **BLOCKED_ROOT_CAUSE_UNKNOWN**. Classification: **ROOT_CAUSE_UNCONFIRMED**. Failure stage is confirmed; the underlying current-node graphics cause is not. No renderer fix or successful GPU result is claimed.

## 1. Actual error

Exact-job export: `page.evaluate: Error: UP2_WEBGL2_REQUIRED`.
Outer Studio code: `GCUBE_CAPTURE_RUNTIME_FAILED`. Safe native facts: `EGL_NOT_INITIALIZED`, `eglInitialize`, ANGLE/Vulkan/GPU-process failures. Raw stderr/stdout, numeric Vulkan result and extension names were not retained. They cannot be reconstructed from SHA256 hashes.

## 2. Failure stage

Runtime import completed. `WEBGL_CONTEXT` failed during `PAGE_EVALUATE_FIRST_NATIVE_DRAW`, frame 0 of 600, native proof incomplete. Chromium launched; Node capture exited 1. Browser exit 0 is cleanup, not successful graphics initialization. FFmpeg follows native drawing/capture in this route and was not reached. Successful checkpoint export demonstrates that its evidence directory was writable; it does not validate the final MP4 destination.

## 3. Source location

The formal presentation source is `world-simulation-shorts-engine/recovery/universal-presentation-v2/presentation_runtime.mjs`. The throw site is its `createPresentationRuntime` WebGL2 acquisition. The NVIDIA route uses its generated Vulkan variant under `recovery/codex-to-gcube-handoff-v1/backend/`; the original build/manifest closure remains authoritative. The native-driver/provider cause is below this JavaScript guard and has not been localized to a source file.

## 4. Function and classification

`createPresentationRuntime` calls `canvas.getContext('webgl2', ...)` and asserts `UP2_WEBGL2_REQUIRED` when no context is returned. `capture_nvidia.mjs::classifyCaptureFailure` maps the prefixed Playwright message to the generic code. `CLASSIFIER_MAPPING_CHECK.json` records execution of that exact existing pure function on the recovered message. Both outer code and stage match the archived failure. The inner message and operation are already preserved in the private safe diagnostic export. Changing this outer label would not repair graphics initialization.

## 5. Relationship to previous errors

The symptom matches the earlier WebGL incident. Provider-supplied history reported missing EGL vendor configuration on node `wnc6bc6433`; unchanged code subsequently passed native context creation there. This failed allocation was node `wnb247afd4`. Its EGL files, Vulkan ICD selection and loaded libraries were not recorded. Consequently same-root recurrence and a new defect are both unconfirmed.

Existing native capture evidence also completed 300 frames on driver `580.126.09` with identical recorded safe browser args and graphics environment. Driver version, `NVIDIA_VISIBLE_DEVICES=void`, or the retained Vulkan surface flag alone are insufficient explanations. Full library/descriptor/argument identity is not claimed.

## 6. Why a production fix is not yet justified

No missing application module, new input-contract failure, source-manifest mismatch or changed launcher function is identified. Existing actual-image admission contains the prior Worker publication, startup-pin and bounded large-reader fixes. Its published digest is preserved. Current-node loader configuration and raw native diagnostics are the missing discriminator.

The legacy graphics helper prepares descriptor selectors, and the Studio capture allowlist omits two selector names; this is a conditional code lead, not a proved cause of this execution. The allowlist is unchanged since prior success, and current selector values were not captured. No workaround is applied without establishing relevance.

## 7. Minimal change scope

Only incident evidence, comparisons, this report, the provider inquiry draft, and recovery/checkpoint state are changed. No production Python/JavaScript, generated adapters, manifests, image, gCube settings, history data, geometry, design or MP4 is altered. Existing finite-vocabulary diagnostic tooling under `recovery/webgl-init-diagnostic-v1` already captures more detailed loader evidence if separately authorized later; no replacement tool is developed or run.

## 8. Existing PASS impact

The prior READY designation is superseded by the actual 0-frame failure. Design, 106 shapes, input rejection cases, Controller/Worker transport, source/image closure and deployment-setting readback remain historical valid evidence within their original non-render scope. They never established live NVIDIA rendering. No prior PASS suite is rerun. Actual graphics rendering, output delivery and video quality remain unverified.

## 9. Free checks performed

Recovered original exact-job Dropbox bytes; verified original checksum; joined checkpoint and diagnostic by job ID; compared preserved prior provider repair and actual captures; compared current launcher/environment function text against commit `f276f19`; executed only the exact-incident error classifier; reviewed formal startup/capture/environment paths. No browser/context attempt, frame render or image build was performed for validation. `FREE_INCIDENT_VALIDATION.json` records the limited evidence checks separately from the blocked runtime status.

## 10. Outstanding evidence and GPU-only validation

First obtain existing provider records/configuration for node `wnb247afd4` and pod `dep5373-76bc6dcb67-kw8p4`, at 2026-11-14 12:53:24–12:55:56 KST, particularly EGL vendor descriptors, NVIDIA libraries, Vulkan ICD, mount/permission errors and stored imageID. `SUPPORT_REQUEST.txt` is a prepared, unsent request; it explicitly excludes workload restart or paid reproduction.

If provider evidence confirms a missing host configuration, remediation belongs to that configuration; do not assume a new image is needed. If it confirms an application defect, document that cause and modify only the proved path, then run the affected free checks. If existing records cannot establish the cause, remain blocked; do not silently authorize a paid diagnostic.

Any subsequent actual context creation, native draw, 600-frame capture, FFmpeg/MP4 receipt, download and visual review requires a separate user-approved GPU execution. The current gCube state was observed stopped and has not been changed. Recovery GPU starts: 0.
