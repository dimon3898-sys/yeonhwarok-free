# RTX4080S one-shot diagnostic preparation — verified release

Published image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v010-diag`  
Digest: `sha256:a44ecb0ae6aa41cc0f7608084dab8412e6950b3a560f394b5d1a795a3480675d`  
Code revision: `a3f46ae9905b6b02814cddc2c3a5e261357d8258`  
Code branch: `fix/v010-one-shot-diagnostics`  
Official build/public-pull proof: [run 37626881896](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37626881896/job/112810826204).

## Result and limits

All **719 container regressions PASS, 0 FAIL, 0 SKIP**: core 482, proxy/security/GPU logic 206, unchanged v007 diagnosis 31. Root-only UID-drop descriptor verification ran in the final image. The final image's **59 required assets/runtime files** pass before readonly test fixtures are mounted: original 56 retained plus three diagnostic helpers. Packages, Node, Chromium, FFmpeg, isolated optional offline TTS, writable UID1000 paths and the production entrypoint were tested. Anonymous Docker pull, image revision, owner login/Secure cookie, external Origin rejection and 61-second gateway persistence PASS. The actual entrypoint stays alive for 61 seconds and **fails closed without physical NVIDIA**, with `engine_ready=false`; no GPU readiness is fabricated.

The original 679 cases remain included. Forty additive tests cover full actual input capture, every strict frame predicate, errors=[] with injected independent failures, actual process termination, atomic flush faults, fallback ZIP packaging, success/failure/mid-scene/pre-frame paths, redaction, cached audit preservation, mobile download, pending-ZIP polling and real worker state boundaries. Failure injection is explicitly test-only. No test claims the injected WEBGL_ERROR is the real S002 failure.

Synthetic HIGH fixtures exercised 360 real JPEG frames, five scene MP4s, concat, audio, strict QC and checkpoint/retry. Measured synthetic pipeline time **35.385 seconds**. This is a CPU media fixture measurement, not a GPU map benchmark. Subtitle fixture passes; an overlong optional QA narration is rejected by the unchanged speech-time policy. The separately calibrated provider budget test passes. Existing default TTS and subtitles remain OFF.

S001–S005 collect-all tests use the actual newly generated/persisted QA12 plan and native geometry/camera/route/entity checks. They do not reconstruct the missing user's original actual GPU inputs. At real execution, all five actual persisted inputs are captured before the first draw, and each started browser's final Scene spec is captured separately. Source origin/started status is explicit in `scene-input-capture.json`. All native draw/audit predicates and browser errors are retained with actual frame index, scene time, pose, route/entity data and renderer/vendor/backend.

The real S002 failed invariant remains **UNKNOWN**. All actual NVIDIA map frames, final map MP4/QC, public gcube/physical Android delivery remain **NOT_RUN** here. The workload remained stopped; no gcube deployment/settings/start/delete/points operation and no 75/80-second render was performed.

## Failure evidence and owner download

Frame journal and failure rules use synchronous fsync before Node rejection. Failed JPEGs are refused before starting the encoder. Actual renderer errors and subsequent encoder exits stay primary/secondary. Native scene inputs, preparation, frame attempt, full frame audit and exact failure record remain in redundant sanitized journals. Worker SIGTERM/SIGKILL, aggregation-write failure and a truncated last journal line are tested; a surviving gateway packages existing evidence. Four MiB is reserved and released for error packaging. Existing final ZIPs are immutable.

Each success/failure exports `WORLD_ENGINE_GPU_DIAGNOSTIC_<job-id>.zip` through the existing owner-authenticated download policy. GET/HEAD/range, wrong owner, external Origin and path traversal are tested. A **393×851 real Chromium mobile viewport** logs in over **actual loopback HTTPS** through a test-only bridge into the actual gcube HTTP gateway, clicks the failed-screen button and saves a valid ZIP. The delayed-ZIP boundary proves polling continues after failure until the archive appears. This is not physical Android or a real gcube public connection. Success shows the existing MP4 link plus diagnostic ZIP; failure keeps the ZIP link and tells the user to download it before stopping the Workload.

Export is restricted to named job artifacts and safe GPU/runtime fields. Credential keys/configured values/runtime owner-code values are removed. Raw headers, authentication files, cookies, sessions, full environments, subprocess input and complete command lines are excluded. Python diagnostics and redundant native journals are re-redacted when packaging. Measurements are actual elapsed time/child CPU+RSS/device memory samples/encoder lifetime/final MP4 size+duration; unavailable values are not invented. Device-memory peak is the maximum observed nvidia-smi sample, not an isolated or continuous process-VRAM measurement.

A completely unwritable device or deletion of the entire ephemeral container can prevent final assembly; no implementation can retain that data after deletion. Download the ZIP while the stopped/failed renderer's server remains accessible. Do not repeatedly retry before interpreting its exact failed invariant.

## Preservation and next step

All **28 frozen approved sources** match their prior hashes. MASTER V3, premium flat v004, FAST_PLUS, route/entity graphics, GPU admission/profile/verification, Host/Origin/owner auth, original partial cache/checkpoints and original render/audio/QC gates remain intact. Prior candidate fixes are included: terrain packaging, QA S004 clipping, QA S003 PCM onset, JPEG CSP decoding, calibrated optional TTS, storage probe protection, lazy encoder, QA12–15, safe failure details and hidden internal plan prose.

After explicit user approval only: use the new image on the existing **RTX4080 SUPER** settings and run the same **Suez QA12 / HIGH / FAST_PLUS** once. Successful output: MP4 plus ZIP. Failed output: download ZIP and stop Workload, preserving exact real input/audit/failure evidence for analysis. No first production 75/80-second render is authorized.
