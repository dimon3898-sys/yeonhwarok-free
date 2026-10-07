# gcube-v004 Host fix validation

Source revision: `b1f3c50477b4d559fe959831b5e691fe39e45a66`. This is a Host-admission release only. The current official Tier1 T4 screenshot shows `https://<id>.service.gcube.ai:24999`, independently of its container port. The previous validator rejected both the service namespace and an explicit external port.

`HOST_REPRODUCTION.json` records actual calls to the previous and corrected provider validator. `OFFICIAL_HOST_EVIDENCE.json` records freshly retrieved official documentation URLs and image hashes. The numeric service port is validated rather than fixed to the documentation example.

## Executed local checks

- 184 deployment tests executed in 32.268 seconds: 183 passed, one root-only descriptor permission test skipped on the nonroot host, no failures. The root-only test remains required in the existing fresh-image CI.
- The Host/Origin module ran 32 tests successfully, including real local HTTP owner login and exact dynamic-port binding/restart checks.
- 72 malformed or cross-origin/cross-port state-changing HTTP requests were rejected before core dispatch. No generated video was requested.
- Provider authority tests cover official service addresses, valid dynamic ports, legacy addresses, reserved/apex/nested/spoofed domains, invalid ports, duplicate headers, default HTTPS-port normalization and localhost development behavior.
- Existing Origin/forwarded-header checks and owner authentication are unchanged. The four policy/application/handler definitions were compared structurally against the prior source, and the other 57 baseline source files stayed byte-identical.
- All 52 prior scene/checkpoint/final artifact hashes remained unchanged. GPU admission, browser flags, rendering, cache, checkpoint and project code remain unchanged.

## Fresh image and publication

The [actual CI run](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37563128130) builds the complete image, boots five validation containers, tests owner login, explicit CPU comparison WebGL2 draw, GPU-required failure without hardware, foreground lifetime and the GPU/Host contracts before publishing. CPU comparison is a test setting, not an automatic production fallback. No actual NVIDIA result is inferred from this environment.

`PUBLICATION.json` records final workflow success, source revision, digest, anonymous manifest/config/layer access and preserved v001/v002/v003 tag digests after publication completes. These registry checks do not perform a gigabyte-scale local image pull.

## User settings

Change only Container Image to `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v004` and redeploy. Keep container port 8000, command blank, the current GPU/resources, storage and existing environment variables. The externally allocated service port is handled by Host validation; it is not a new container-port setting.
