# GCUBE v005 — T4 final proxy recovery

## Scope

Only the gcube gateway, read-only diagnostic projection, tests and publication workflow changed. The approved engine, shaders, assets, mobile UI, authentication implementation, renderer, GPU admission/probe, runtime entrypoint and Chromium arguments remain unchanged. No T4 deployment, video render, GPU workload or paid service was started.

## Reproduced failure and correction

The v004 pending and bound-origin policies rejected `X-Forwarded-Host` differing from `Host`. An ordinary same-Pod Istio hop can retain external HTTPS authority while sending an internal HTTP `Host: localhost:8000`. The internal health branch also rejected such forwarded requests instead of letting the full origin policy handle them. Both paths now use the strict gcube envelope parser; header-free read-only container probes and a bounded same-Pod internal-HTTP health probe retain their limited liveness exception. Neither can reach authentication or project APIs.

The prior policy did not explicitly validate XFF chains. v005 adds bounded IP-chain syntax checks; it does not claim that XFF alone was proven to cause the actual T4 error. No raw production T4 header capture is available, so the exercised envelopes are simulations of the documented topology, not observations of the live workload.

## Security boundary

- Only a single workload label under `service.gcube.ai`, or the existing legacy single-label `gcube.ai` service format, is accepted; apex, reserved names, unrelated hosts and suffix spoofs are rejected.
- Numeric ports are normalized and restricted to 1–65535. Explicit external-port conflicts are rejected.
- Authority rewriting requires an HTTPS envelope and a loopback/exact local Pod TCP peer; unrelated private addresses are not trusted. Forwarded IPs never authenticate, select a trusted peer, or bypass rate limiting.
- XFF and RFC 7239 `Forwarded` chains accept valid comma-separated IPs and quoted IPv6 nodes. Empty, malformed, oversized and contradictory chains fail closed.
- `Host`, `Origin`, forwarded host/proto/port and Envoy external address cannot contain duplicate ambiguous header values. Forwarded host is restricted to the same workload authority or the exact internal listener.
- Successful owner authentication pins the exact HTTPS origin and port. Every state-changing route still requires that origin, and owner/session checks remain intact. No wildcard Host, Origin or CORS is introduced.
- The owner-only proxy endpoint exposes normalized authority, scheme/port, XFF count and Envoy-address presence only. It never returns owner code, cookie, authorization value or individual client IPs.

## Test matrix

Automated contracts cover A/B single and multiple XFF, C dynamic external ports, D internal/public Host rewrites, E forged forwarded host, F unrelated Host, G malformed XFF, H forged/missing Origin, and I/J/K absent/incorrect/correct owner code. Additional cases cover RFC chains, IPv6, repeated chain field lines, duplicate authority headers, untrusted peers, port disagreement, health-route forwarding and eight state-changing API paths.

The publication workflow builds the full amd64 image before registry login. Fresh root and UID1000 containers verify foreground boot, 0.0.0.0:8000, login, health probes and actual explicit CPU-comparison Chromium/WebGL2 drawing. GPU-required/no-device startup remains blocked; no software renderer is admitted as NVIDIA. A separate same-Pod TCP relay exercises the public HTTPS/internal HTTP envelope and 48 malicious mutation requests, then observes the server for at least 61 seconds after READY. No video rendering endpoint is invoked with valid render credentials.

The explicit CPU comparison exists only in automated test containers. The production image still defaults to the existing GPU-required admission flow and does not fall back to CPU.

## GPU diagnostic presentation

The existing stages A–F and observed GPU/driver, renderer, vendor, WebGL/WebGL2, software-renderer and backend information remain the source of truth. EGL/Vulkan backend PASS requires the existing successful actual NVIDIA draw proof. Unselected/unexecuted backends display NOT_RUN rather than a fabricated PASS. T4 success displays `NVIDIA T4 WEBGL VERIFIED · WORLD ENGINE READY` only when the existing admission proof is valid. Missing T4 graphics delivery displays `Tier1 T4에서도 NVIDIA graphics runtime 전달 실패` and the stop-workload billing guidance. GPU admission code is unchanged.

## Existing T4 VM / image replacement

Official documentation was fetched during this task:

- https://raw.githubusercontent.com/Data-Alliance/gai-platform-docs/master/docs/user-guide/gcube-cli/cli-workload.ko.md
- https://raw.githubusercontent.com/Data-Alliance/gai-platform-docs/master/docs/user-guide/workload/stop-workload.ko.md
- https://raw.githubusercontent.com/Data-Alliance/gai-platform-docs/master/docs/user-guide/workload/register-workload.md
- https://raw.githubusercontent.com/Data-Alliance/gai-platform-docs/master/docs/user-guide/workload/deploy-workload.md

The CLI guide permits updating only a stopped workload. The stop guide warns that an environment without Personal Storage is deleted after stopping. These establish stopped-workload configuration updates; they do not establish a hot image swap or retention of the same Tier1 VM. Existing-VM preservation is therefore unverified. Do not promise that stopping, editing the image and redeploying avoids VM provisioning or its costs. No user CLI commands or actual deployment were performed.

## Next actual T4 test

Use only `gcube-v005` once publication and anonymous public pull have passed. Keep port 8000, blank command, GPU-required runtime and the existing storage/proxy settings. Replace any previously exposed owner code with a new private value of at least 16 characters. Inspect actual EGL/Vulkan attempts, WebGL2 and NVIDIA T4 renderer plus stage F draw proof first. Do not start the 12-second QA video until the user approves it after GPU PASS.
