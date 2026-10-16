# Universal video V2: provider operations and performance boundary

Checked 2026-10-16, Asia/Seoul. This is a read-only reuse audit. No workload was registered, started, stopped, updated or deleted; no paid API was called. No previous image, claim, cache, source or result was changed.

The existing official-source audit in `world-simulation-shorts-engine/docs/evidence/gcube_official_sources_v001/` already includes the released Data-Alliance gcube-cli 0.4.2 wheel and exact source. The current task reuses it. Only two already-known documentation URLs were refreshed; both remain HTTP 200 with the same saved SHA. `OPERATIONS_SOURCE_CHECK.json` records that check.

## What is supported by official evidence

| Operation | Official evidence | Verified on this account now |
| --- | --- | --- |
| Workload registration/update/describe/list | Released official CLI and saved workload client | No |
| Deployment/start | `GET /api/workloads/gai/{SER}/state/deploy` | No; this GET has a billing side effect and was not probed |
| Stop | `GET /api/workloads/gai/{SER}/state/finish` | No; not invoked |
| Scheduled START/STOP | Released official client `GET/PUT/DELETE .../{SER}/schedule` | No |
| Remote command execution | Official CLI `gcube workload ssh SER --pod N --container N -- command...`; source uses SSH `exec_command` and returns remote exit code | No |
| Binary result recovery | Official SSH command path preserves binary stdout separately from stderr | No new GPU result exists to recover |
| Log/status/resource inspection | Released official workload/resource commands | No live account access |

The management API is not a remote shell API. SSH provisioning may register a service, inject an in-Pod SSH daemon and update provider source-IP rules. Those are distinct, authorized account operations; no such action was performed. Do not assume browser terminal access means Codex has SSH access.

Official scheduling supports automatic stop, but does not establish a tested task-completion callback or this account's actual schedule entitlement. Schedule PUT replaces the complete schedule list. A future operator must preserve existing entries and verify the requested STOP with GET/history; do not overwrite unknown schedules. A render timeout or process exit alone does not stop GPU billing.

## Current connection and authorization state

The managed environment status reports current observations, no configured secret bindings/runtime variables/outbound identities, and a restricted desired HTTP policy whose enforcement state is `unknown`. The local policy snapshot has no gCube API host and no TCP destination grant; VPN is not configured. The gcube CLI is absent. Only the presence of `GCUBE_ACCESS_TOKEN`, `GCUBE_EMAIL` and `GCUBE_API_URL` was checked; none was set. No credential value or secret file was read.

Consequently, terminal-free operation is architecturally supported by the provider's official CLI/API, but end-to-end account execution, authentication, SSH connectivity, actual GPU availability, price, auto-stop and Dropbox synchronization are **not verified**. This task must not claim a functioning cloud control plane.

## Exact requirements for eventual terminal-free operation

1. User approval must name the workload/account, maximum cost, wall-time and retry count. No paid launch or automatic retry is authorized by this development task.
2. Supply a provider access token through an approved secret binding, plus the correct CLI account configuration/workload SER. Never put credentials in chat, Scene JSON, image, GitHub or public summary.
3. Permit the documented `api.gcube.ai` HTTPS route and the provider-issued SSH host/port, with authorized source-IP admission. Configure the official CLI in the trusted control-plane worker, not a public unauthenticated render endpoint.
4. Perform read-only account describe/pricing/schedule inspection first. Pin the new immutable image digest; preserve the default normal-mode service, NVIDIA graphics/utility and Dropbox `/world-storage`.
5. After authorization, execute the one-shot detached universal job through the verified SSH path. Poll its authenticated status and recover completed scene receipts. Never clear old claims to force a run.
6. Use an approved STOP schedule/watchdog with a measured safety margin, preserve existing schedules, and independently verify a stopped state. Keep artifacts and private recovery state externally durable before stopping. If provider authorization or STOP verification is unavailable, require the user's console stop; do not promise automatic billing termination.
7. Confirm final external Dropbox URL HTTP 200 and downloaded SHA equality. Mount readback is not external delivery. Only MP4, SHA256SUMS and a sanitized completion/quality summary belong in the final public folder.

## Performance baseline and the 60-minute target

The user reports that the original 65422 hardware render produced a playable 5-second MP4. No trustworthy per-stage NVIDIA timing or total-VRAM measurement was available in the audited saved recovery records. The protected V2 report explicitly leaves NVIDIA speed/VRAM validation pending. SwiftShader build/test timings and a successful 5-second file are not RTX 4080 SUPER throughput evidence.

`PERFORMANCE_BASELINE.json` distinguishes actual evidence from an unmeasured target. At 2,400 frames, 3,600 seconds allows at most **1.5 seconds/frame only if all other work takes zero time**. The usable budget is `(3600 - measured non-render overhead) / 2400`. No runtime estimate, percentage speedup, price or 60-minute PASS is asserted.

The new real-source CPU integration recorded 6,276.808141 ms to load and bind its 2,400-frame/12-scene plan, 148 source bindings and three ASTRA roles. `REAL_CPU_RUNTIME_INTEGRATION.json` says no browser or GPU was started and zero frames were captured. This is a CPU preparation observation; it does not establish GPU upload, rendering throughput or total production time.

One RGB24 output frame is 6,220,800 bytes; buffering 2,400 frames would require 14,929,920,000 bytes before overhead. The new path must stream/bound frame buffers, encode each scene, validate its cache and preserve successful scenes. Durations 120/180/300/600 seconds use the same contracts, not separate renderers. Their actual NVIDIA production throughput remains unmeasured. Only measured bottlenecks justify later GPU concurrency/readback/encoder optimizations; no legacy renderer or visual-quality reduction is permitted here.
