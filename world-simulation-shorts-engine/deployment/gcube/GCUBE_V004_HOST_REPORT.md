# gcube-v004: official service Host admission

The running workload was reachable but returned `INVALID_HOST`. The prior admission regex matched the entire Host header as only one bare `label.gcube.ai`. Current official gcube screenshots show `https://label.service.gcube.ai:24999`, including the Tier1 T4 example below. Both the service namespace and explicit external port were rejected. The external service port is independent of the container port.

## Narrow change

Only `provider_origin()` and its hostname constants change application behavior. It reuses the existing strict authority parser without changing that parser. It admits a single workload label under the fixed `service.gcube.ai` namespace, retaining the previously documented single-label `gcube.ai` form. Optional numeric ports must be 1–65535; HTTPS port 443 is canonicalized and every other port remains part of the exact origin. Apex, reserved, nested, spoofed, external and malformed authorities remain blocked.

Origin/CSRF checks, Host/forwarded-host equality, HTTPS requirements, owner-code authentication and authenticated exact-origin persistence remain unchanged. After owner login, another workload or another port is rejected. GPU admission, Chromium flags, renderer code, CPU-fallback policy, UI, projects, cache and checkpoints are unchanged. No video render is requested.

## Official evidence

- [Tier1 T4 screenshot](https://raw.githubusercontent.com/Data-Alliance/gai-platform-docs/master/docs/user-guide/platform-guide/img/openwebui-comfyui/opencomfy_06.png): `https://3f2de722.service.gcube.ai:24999`, container port 8080.
- [Ollama screenshot](https://raw.githubusercontent.com/Data-Alliance/gai-platform-docs/master/docs/user-guide/platform-guide/img/ollama-api/%EC%82%AC%EC%9A%A9%EC%9E%90_%EA%B0%80%EC%9D%B4%EB%93%9C_chatbox_08.jpg): `https://903053f5.service.gcube.ai:24999`, container port 11434.
- [Deployment screenshot](https://raw.githubusercontent.com/Data-Alliance/gai-platform-docs/master/docs/user-guide/workload/img/deploy-workload/002_deploy-workload.png): `https://e27414c4.service.gcube.ai:24999`, container port 8888.

These are public documentation examples, not the user's workload address. Port 24999 is not hardcoded. The documentation does not establish a mandatory eight-character workload label, so the existing strict DNS-label limits are retained.

## Verification and deployment

Regression tests exercise the official authority shape through real local HTTP requests, owner login, exact-port binding and restart. Cross-origin or cross-port mutation requests must be blocked before entering the core handler. Malformed authorities, duplicate headers, forwarded-header mismatches and localhost behavior are covered. The fresh-image CI also retains all v003 boot and GPU rejection checks; no GPU PASS is inferred from a Host fix.

The release workflow publishes only `gcube-v004` and its source-SHA tag after required checks. Prior v001/v002/v003 tags are not pushed. Publication and anonymous manifest/config/layer access evidence are saved separately in `deliverables/WORLD_SIMULATION_ENGINE/GCUBE_HOST_FIX_v004` after completion.

For gcube, change only the image to `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v004` and redeploy. Keep container port 8000, command blank, the current GPU/resources, storage and existing environment variables. No user terminal or additional configuration is required.
