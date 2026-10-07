# RTX4080S one-shot diagnostic operating image

Release requested: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v010-diag`.

This image preserves the complete v010 pipeline candidate over the immutable v009 image. S002's real GPU failed invariant is still unknown. No actual gcube workload is started by the build, tests, or publication workflow. Only the owner-approved next RTX4080 SUPER QA12 run can establish map draw success.

Runtime settings remain port **8000**, blank command, ephemeral test storage `/data`, `WORLD_ENGINE_OWNER_CODE` supplied privately, `WORLD_ENGINE_RENDER_MODE=gpu-required`, and `NVIDIA_DRIVER_CAPABILITIES=all`. Keep the validated NVIDIA Vulkan profile and verified GL-EGL alternative. No graphics driver, GPU validation, renderer, shader, quality, or software fallback policy is changed.

## Evidence lifetime

Before GPU rendering, the worker saves all five persisted Scene inputs and the approved plan to the private per-job directory. `scene-input-capture.json` explicitly distinguishes persisted subprocess inputs, actually started browser Scene specs, and scenes not yet started. Browser-final Scene specs replace only the diagnostic copies. Scene input, numeric preparation, per-frame native audit, browser errors, actual renderer/vendor/backend, JPEG validation results, frame attempt and failure rules are flushed synchronously before rejection. Original frame order stays draw → JPEG readback → native audit; the readback GL error is not consumed early.

Audit invariants retain their exact strict predicates. `errors` is a browser error list and is not the full draw acceptance decision. `FAILED_INVARIANT` contains actual failed gates, including numeric preparation and JPEG validation. A failing gate remains a failing gate. The original validation is never skipped and no invalid frame reaches FFmpeg.

The encoder starts only after a valid, audited JPEG. Native encoder exit records are separate from the primary renderer error. Python media subprocesses retain original commands and behavior; their observed exit code, duration and sanitized output tails are added to diagnostic evidence. Neither complete commands, subprocess input, request bodies nor environments are exported.

All JSON records use atomic replacement and fsync. Frame journals use append/fsync; valid earlier journal records survive worker SIGKILL. The surviving gateway can recover a killed worker's ZIP. The ZIP includes sanitized native journals as redundant evidence if aggregation fails, and records corrupt/truncated lines structurally without exposing raw data. A reserved 4 MiB is freed before failure packaging. A completed ZIP is immutable.

`diagnostic_pending` keeps the mobile browser polling while a terminal job's ZIP is being completed. The failed screen retains the authenticated ZIP download; retry is not recommended before examining its evidence. Success exposes both existing MP4 downloads and ZIP. GET, HEAD and byte ranges retain the existing owner, Host, Origin and path policy. ZIPs are private until authenticated download.

Download the ZIP **before** stopping an ephemeral Workload. Disk fsync does not preserve ephemeral data after container deletion. A completely unwritable/full storage device or termination of the entire container can prevent final ZIP assembly; redundant journals and gateway recovery protect worker/aggregation failures while the container remains alive.

## Measurements and redaction

Only observed timings, child CPU seconds/RSS, actual nvidia-smi samples/VRAM peak, encoder process lifetime and final MP4 duration/size are recorded. Missing GPU measurements and unexecuted draw stages remain unavailable/NOT_RUN. Encoder lifetime includes waiting for source frames and is not a standalone GPU speed benchmark.

Only named job artifacts and GPU/runtime projections can be exported. Credential fields, configured sensitive values, the runtime owner-code value, URL strings/queries and internal absolute paths are removed. Arbitrary nearby files, owner access files, sessions, cookies, request headers and environment dumps are not packaged. The owner code is read internally only for redaction and never written into the image or evidence.

## Maintainer verification

The `gcube-one-shot-diag.yml` workflow builds without publishing, audits the real image before mounting readonly test fixtures, runs all core/proxy/diagnostic tests, exercises synthetic JPEG/FFmpeg/concat/audio/QC/retry, validates the owner-authenticated gateway and 61-second persistence, and proves the actual production entrypoint fails closed without physical NVIDIA. Only then does it publish the new immutable tag and verify an anonymous pull plus OCI revision and gateway persistence on those pulled bytes.

The Android test uses a real local HTTPS transport, a 393×851 Chromium mobile viewport and the actual gcube HTTP gateway. Its test-only TLS bridge supplies the verified external gcube authority/header fixture while keeping browser traffic on loopback. It tests Secure owner cookies and a real downloaded ZIP, including the delayed-ZIP polling boundary. It is not a physical Android or public gcube service test, and never draws map frames or admits GPU rendering.

The frozen 28 approved sources and prior MASTER/assets/projects/results remain unchanged. QA12 fixture preparation and collect-all are native geometry/static checks, not proof of actual NVIDIA map output. The only remaining paid test is the same Suez QA12, HIGH, FAST_PLUS after explicit owner approval. If it fails, download the ZIP and stop the Workload; do not repeatedly retry before analyzing the captured invariant.
