# gcube-v003 GPU/WebGL validation

This record covers only the gcube container/GPU/browser deployment adapter. Implementation commit: `26ecb1d12f9f96c0ce59be503f56209f46c2bbbd`; image source revision after the test-fixture correction: `deaaa03022e4318dd684bd476b3b3773b8bb539b`. Existing renderers, approved graphics, mobile generation UI, owner authentication, projects, videos, cache and checkpoints are preserved. No video render was requested.

## Local checks actually performed

- 173 deployment tests: 172 passed, one root-only permission test skipped on the nonroot host, zero failures. Elapsed: 28.291 seconds.
- The skipped descriptor-read test then passed inside the root test container after a real drop to engine UID 1000. NVIDIA driver entrypoints in that permission test were mocks; it is not GPU hardware evidence.
- The current deployment adapter ran in an existing cached dependency container. This was not a newly built v003 image. The cached image's older runtime-link layout was aligned only in that test container; persistent scene/project files were not changed.
- Actual Chromium WebGL2 shader draw/readback produced `[255, 0, 0, 255]` using the observed SwiftShader renderer in explicit CPU comparison mode.
- NVIDIA admission rejected that actual software-renderer result at stage E. CPU comparison status reported `gpu_rendering_verified: false`; no NVIDIA READY result was claimed.
- Anonymous GPU diagnostics returned HTTP 401. Existing owner login and authenticated JSON/HTML diagnostics worked. The foreground server was sampled for 64.161 seconds without a render request.
- The cached-container record's `boot_seconds` field is the delay from starting the QA client until observing health, not a cold container-start benchmark.
- The 28 protected source files and 52 prior scene/checkpoint/final files had unchanged hashes.
- The temporary validation container was stopped and removed after checks; its mounted data and cached image were retained. The pre-existing mobile release validation container was left intact.

## Fresh image and publication

The first [run 37547541039](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37547541039) built and booted the fresh image but blocked publication when two test storage fixtures omitted UID/GID on the root-only `fchown` path. The issue was reproduced; only the fixture metadata was corrected. Production `fchown` and GPU admission were not relaxed. All 112 selected root contract tests then passed locally in 14.844 seconds.

The corrected-source [run 37548320087](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37548320087) passed the complete fresh-image build, five-container startup/login/diagnostic/foreground smoke checks and 112 built-image GPU contract tests before registry publication. The smoke checks used explicit CPU comparison mode for two positive browser tests, with GPU-required mode staying blocked on the GPU-less runner. Local cached-container results above do not stand in for this fresh-image result.

The final publication and anonymous manifest/config/layer access checks are recorded separately in `PUBLICATION.json`. Previous v001/v002 manifest digests must match the before-publication record.

## Actual NVIDIA limitation

Neither this Codex environment nor the GitHub runner has an RTX 3070. A successful NVIDIA WebGL2 draw, GPU utilization, gcube performance or point consumption is not claimed. That final check requires the existing gcube workload to run v003. Hardware validation remains mandatory; failure starts no video render and shows the actual failed stage, renderer, backend and reason with a stop-workload notice.
