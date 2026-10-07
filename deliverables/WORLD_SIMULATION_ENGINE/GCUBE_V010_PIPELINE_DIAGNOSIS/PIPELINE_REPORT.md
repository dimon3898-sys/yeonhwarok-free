# v010 pipeline diagnosis — publication held

## Evidence and limits

The supplied gcube observation establishes S001 success and S002 exit 1 after a native frame-audit failure. Its partial audit establishes browser `errors=[]`, route R_SUEZ progress 0.11821892, a route outside the Earth and no route discontinuities, and a surface-grounded cargo ship with 0.035km clearance. It does **not** contain `webglError`, `textClipped`, `entityClipped`, `missingTextures`, or `fontReady`.

No current gcube URL, approved workload-log access, full failed checkpoint, or actual Scene JSON was available. No gcube workload was read, started, changed, deleted or charged. No GPU map draw, SwiftShader draw, 75s or 80s render was performed. The saved v009 QA12 plan is a reconstruction from the v009 planner and the supplied settings, not a claim to have recovered the user's exact project.

The reconstruction matches the supplied first S002 route progress exactly, but this does not prove that every other field matches the actual project. The exact real S002 failed invariant remains **NOT_IDENTIFIED**. Releasing `gcube-v010` as a verified root-cause fix is therefore prohibited by the user's evidence and publication conditions.

## Confirmed audit / pipe behavior

`tools/render_production_scene.mjs:63` fails when any of these independent checks fails: browser errors, WebGL error, text clipping, entity clipping, missing textures, route inside Earth, route discontinuities, font not ready. `errors=[]` describes only the browser error collection. It never meant that all native draw invariants passed.

The original worker launches FFmpeg before native audit, then runs renderFrame, JPEG extraction and native audit in that order, checks the audit, and only then writes JPEG bytes to stdin. A first-frame audit failure leaves FFmpeg without frames. An isolated empty image2pipe input reproduces a nonzero encoder exit and no valid video; normal JPEG streams encode successfully with the unchanged input options. The actual reported FFmpeg symptom is consistent with secondary empty-pipe failure, rather than evidence that probesize/analyzeduration is defective. Actual captured stdin bytes/frame count were unavailable.

The additive stable worker preserves that exact post-JPEG-readback native audit order (including GL errors caused by export), then decodes each JPEG using browser createImageBitmap, validates dimensions/signatures/sequence, and starts FFmpeg only after the first valid audited frame. Backpressure and early child exit are observed; child error promises do not escape as an unhandled rejection. Every gate remains fail-closed. Root invariant codes survive the Python worker's bounded tail and appear in the existing failure UI. A private failed_audit checkpoint retains numeric WebGL error, font-ready boolean and per-gate counts without text, URLs, labels or secrets. The existing visual worker source, GPU wrapper, launch/profile selection, codecs and quality settings remain unchanged.

## New JPEG decoder and existing CSP

A browser-backed transport regression caught a new issue in the candidate decoder before publication. A second callback regression injects a readback GL error and verifies that the actual production callback observes it in the native audit before any encoder write. `MobileHandler.end_headers()` retains `connect-src 'self'`. Fetching a `data:` URI is blocked by this policy, even though images permit `data:`. The same valid JPEG under this exact policy failed before the correction and decoded as1080×1920 after the correction. The worker now creates a Blob from the identical base64 JPEG bytes before createImageBitmap. No network fetch, second JPEG encoding, security policy relaxation, WebGL or CPU map rendering is used. `JPEG_CSP_BEFORE_AFTER.json` records the test. This was a candidate-only issue, not an explanation of the already deployed v009 S002 audit failure.

## Collect-all native replay: confirmed additional failures

All 360 frames were replayed using the native camera, route, cargo-ship transform, Earth-polish overlay and conservative licensed-font metrics. No WebGL renderer was constructed. The report distinguishes pose/layout evidence from post-draw pixel evidence.

| Scene | Before (native pose/layout) | After (native pose/layout) |
|---|---|---|
| S001 Rotterdam | PASS | PASS |
| S002 Rotterdam | PASS; real missing GPU audit fields unknown | PASS; real GPU failure still unverified |
| S003 Suez Canal | PASS | PASS |
| S004 Singapore | ENTITY_CLIPPED at local frames 47, 48, 49, 50 | PASS |
| S005 Singapore | PASS | PASS |

S004 camera FOV was 44 degrees. At frame47, the projected ship center x=2192.782 and radius31.62 placed its entire projected bound beyond internal width2160. A QA-only 50-degree FOV preserves geography, HIGH resolution, route, entity and material behavior. Its entry/exit camera state and adjacent boundary camera endpoints are synchronized, preserving the existing continuity gate. This fix applies to newly generated QA plans; approved historical plans/files are not rewritten.

Same-place S001→S002 and S004→S005 camera/route interpolation stays finite. All routes, quaternions, FOVs, entity poses and native numeric gate pass after correction. Max camera orientation change is 2.485582781 degrees/frame, below the unchanged2.5 threshold; max normalized position step0.1545275 is below the existing QC0.25 threshold. GPU-dependent texture, WebGL error, font rasterization and actual visual quality remain NOT_RUN.

## Real synthetic media chain and additional final-QC failure

The transport fixture creates test-pattern JPEGs at HIGH internal2160×3840, actually decodes all360 JPEGs, and encodes five72-frame1080×1920 H.26430fps BT.709 yuv420p scene MP4s with the actual frame-pipe helper/unchanged encoder settings. They are test patterns, not substitute map footage and not a final product sample.

Five actual scene MP4s pass stream-compatibility checks and concatenate. Real BGM/SFX mixing, PCM48k, AAC final mux, muted export, video/audio decode, frame count, duration, color, exposure, retention and strict sound-sync QC are exercised. Subtitle ON produces five ASS captions and muxes successfully. TTS OFF is preserved; TTS ON produces the explicit existing `NARRATION_EXCEEDS_SCENE` rejection when the unshortened narration cannot fit2.4s, without paid API access or forced playback acceleration.

The first strict final QC failed `RHYTHM_SOUND_FRAME_SYNC_FAILED` at S003/E007, R_CAPE route_start: native route head appears at globalframe166 (5.533333333s); the generic global one-frame delay inserted sound at frame167 (5.566666667s), and the actual PCM attack added about2.0833ms. Difference1.0625frames exceeded the unchanged1frame plus1ms allowance.

The QA shipping audio adapter inserts bound route-start layers one frame earlier, keeping the original generated waves, variants, intensity and all other sound categories. It aligns recorded history with actual insertion timestamps. Correcting audio on the same synthetic video makes the original strict QC pass; its thresholds are untouched. Normal production audio selection is unchanged. Retry retains earlier audio/checkpoint files and writes corrected audio to a new directory.

The full corrected synthetic pipeline took93.331seconds locally; this is a media/preflight measurement, **not a GPU render benchmark**.

## Retry / checkpoint proof

A controlled S002 worker failure was injected after a real synthetic S001 MP4 had completed. On retry, only S002,S003,S004,S005 were submitted. S001 bytes/hash and completed cache were preserved. Failed S002 partial output remained intact; the retry used a new attempt path, then actual concat, audio and QC completed. The fixture explicitly labels injected failure and synthetic content and does not claim to reproduce the unknown actual GPU audit invariant.

## Container storage probe ownership guard

The root container regression `test_replaced_probe_target_is_not_overwritten_or_deleted` failed in the unchanged storage probe. `_identity()` records only device/inode after closing the created file. A newly written foreign replacement can receive the just-freed inode on overlay/ext4; the stale identity check can then miss replacement before atomic replace and cleanup. This is a container filesystem/security issue, not evidence about the original S002 GPU audit.

The probe now pins descriptors for its directory and files until its cleanup finishes. An unlinked original object remains allocated while pinned; its inode cannot be reassigned to the foreign replacement. All pins close in a final cleanup block even on refusal. Existing filesystem ownership/mode, mount policy, locks and atomic replace checks remain. Existing user files are never changed. A regression asserts that the original unlinked inode remains held and that foreign replacement bytes survive the refusal. Local26 storage tests pass; the final root-container regression including this new pin test also passes.

## Deployed asset and exception coverage

`ASSET_MANIFEST_LOCAL.json` records47 referenced files, existence, readability, nonzero size and SHA256: terrain rasters, Earth day/night/cloud textures, topology, country/coastline GIS, fonts, entry HTML, renderer modules containing shaders/procedural models, Node dependencies and audio/frame helpers. Ship, aircraft, routes, LUT and SFX are procedural/embedded or generated from licensed source code; no fictitious external model/audio file is declared mandatory. New runtime audio is written outside readonly image assets.

`EXCEPTION_PATHS.json` lists63 explicit raise paths across rendering, worker, audio, assembly and QC. `QC_POLICY.json` extracts33 explicit failure/warning codes from the unchanged QC. `PRESERVED_APPROVED_SOURCES.json` verifies all28 source hashes from the existing approval certificate remain intact; no promotion hash was weakened or replaced.

The candidate Dockerfile inherits the immutable public v009 digest `sha256:5f8250473de90076bfb7d2a357881523a1e4555ff3a5b970bb8e598fd4acfb9a`, overlays the additive transport/preflight/QA fixes and an isolated, byte-pinned calibrated offline speech provider, and does not publish a tag. Image boot/dependency/assets/UID1000 write-path/media checks run in GitHub Actions without a GPU. Historical regression scene JSON, devcontainer config, the old label fixture and the existing licensed upload MP4 are mounted readonly **for tests only**; asset checks are run before these mounts, on the actual image filesystem.

## Optional TTS portability

The unchanged 20s production narration regression reserves 10% of each scene for timing. The calibrated Ubuntu Noble eSpeak NG1.51+dfsg-12build1 produces the tested Korean line in2.909125s, below the unchanged2.928s reserve. The Debian Bookworm package in the original container differs. We do not lengthen scenes, change narration, increase speaking speed or relax the regression.

The candidate extracts the exact already-calibrated CLI, speech library and Korean data from official Ubuntu packages into a private speech-only directory. All package bytes and four calibrated file bytes are SHA256-pinned and were downloaded/extracted/verified locally. The child-process library path affects speech only, not Chromium, CUDA or the server. The original GPL copyright notices and exact corresponding source archives are retained in the image. `CALIBRATED_TTS_PROVENANCE.json` records sources and byte checks. The final container measured the same2.909125s waveform and passed the complete optional-speech regressions. TTS remains optional and OFF for QA and production default.

## Verification status

Final local and candidate-container test counts, boot/persistence results and public workflow URLs are recorded in VALIDATION_RESULTS.json and CONTAINER_VALIDATION_RESULTS.json. A health200 response in a no-GPU container is a liveness result only. GPU-required entrypoint must report engine_ready=false and GPU_HARDWARE_UNAVAILABLE; no GPU readiness or CPU renderer fallback is inferred from health.

## Release decision and next evidence

Changes are preserved on `fix/v010-pipeline-preflight`; existing main and all gcube image tags are preserved. **gcube-v010 is not published.** The missing actual S002 invariant prevents the requested before-failure/after-pass proof and the publication condition from being met.

The next necessary input is the **existing** full failed `Frame audit failed` audit or failed worker checkpoint, restricted to `webglError`, `textClipped`, `entityClipped`, `missingTextures`, `fontReady` and frame index. No owner-code, cookie, authorization, request URL or secret should be included. Do not start a GPU to collect a new failure. Only after the real invariant is identified and repaired should an immutable operating image and a single paid12s QA run be considered.

Local final regression:442 core PASS (491.197s),205 gcube PASS/1 root-only SKIP (39.732s),31 diagnostic PASS;678 PASS/0 FAIL/1 SKIP from679 executed tests. Focused new contracts including safe audit snapshot, actual CSP JPEG decoding and native post-readback GL-error capture:13 PASS (20.400s). Storage pin tests:26 PASS (1.590s). Standalone local gateway auth/secure-cookie/forged-Origin rejection/61s persistence PASS; this does not admit GPU rendering.

Final candidate container:442 core +206 proxy/security/GPU-logic +31 diagnostic =679 PASS/0 FAIL/0 SKIP. Installed package checks,56 readonly asset checks before test mounts,360 HIGH synthetic JPEG/FFmpeg frames,concat/audio/strict QC,retry,Secure owner login and61s gateway persistence all PASS. Actual production entrypoint stays live for61s with GPU_HARDWARE_UNAVAILABLE and engine_ready=false on the no-GPU runner. GPU map draws remain NOT_RUN. Synthetic media chain took55.371seconds, not a GPU benchmark.

Verified code commit: `24138bfcbcabdcd727b6a039b5b41a5894a75f8a`. [Public complete container validation](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37617138747/job/112778103778). The validation image was built and run locally on the GitHub runner only; no gcube-v010 tag was published.
