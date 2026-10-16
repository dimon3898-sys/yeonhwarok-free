# gCube control plane for universal production V3

`operations.py` implements authenticated reads against the official `https://api.gcube.ai` origin and a separately approved, single-attempt workload stop. Tests use an injected local mock; no real account call, workload mutation, paid GPU launch, SSH session, or billing-termination check was performed. This is not completed end-to-end cloud automation.

The evidence is the saved official gcube-cli **0.4.2** wheel, SHA256 `9aafcafdc84b129ff119b4f735c0d56f09ba6898667fa3d6713a5fb85d06d692`, under `docs/evidence/gcube_official_sources_v001/`, and the earlier `recovery/universal-auto-video-v2/OPERATIONS_AUDIT.md`. Saved extracted `api/client.py`, `api/workload.py`, and `commands/workload.py` byte-match the wheel. No new endpoint was inferred from a hostname or browser UI.

## Authentication and read-only preflight

Use secure environment configuration to bind `GCUBE_API_TOKEN` for **api.gcube.ai only** and set `GCUBE_EMAIL` to the intended personal account. `SecretSelectors` accepts names beginning `GCUBE_`; it never reads arbitrary credential files. `presence()` returns selector names and booleans only. Token values, provider response bodies, container environment variables, and SSH passwords are never written to logs or returned in public summaries.

The adapter sends the official Bearer header, retains TLS verification and the platform proxy, rejects redirects, limits response sizes, fixes the API origin, and performs no automatic retries. Provider HTTP/auth/transport failures produce stable error codes rather than provider text. API clients and injected transports run in a trusted private process; approval objects must never be populated from untrusted Scene JSON or an unauthenticated HTTP request. There is no HTTP server in this module.

Local capability inspection makes no network request:

```bash
python3 world-simulation-shorts-engine/recovery/universal-production-v3/operations.py capabilities
```

After account reads are authorized and secure bindings/network policy are ready, the explicit read-only command is:

```bash
python3 world-simulation-shorts-engine/recovery/universal-production-v3/operations.py preflight --workload-ser YOUR_SER --allow-account-read
```

This command was **not run against an account** in this task. It makes the official authenticated `GET /api/users/{email}` request, verifies the workload's exact SER and owner through `GET /api/workloads/gai/{SER}`, and reads schedules, account points and GPU price fields. A successful requested-user lookup alone does not establish that the bearer token belongs to that account. The bounded local JWT payload check rejects a readable `email` or email-like `sub` inconsistent with the configured account before account calls. A local claim match plus authenticated user lookup is reported separately as `tokenAccountBindingVerified`; `tokenClaimsCryptographicallyVerified` remains **false** because decoding is not signature verification. Tokens, local payloads and claim values are never logged. An opaque proxy placeholder, undecodable token, or token without an account claim can still make read-only requests, reported as `authenticatedRequestSucceeded:true` and `tokenAccountBindingVerified:false`; it cannot authorize a stop. No invented `/users/me` endpoint is used.

Team-owned workloads fail closed because the personal-account owner check cannot establish team authorization. Missing, malformed, nonfinite or unknown billing fields fail; they are not coerced to free/zero prices. Returned price and usage-price fields retain their official currency and a bounded allowlist of GPU identity fields: `gpuName`, `productName`, `gpuExt`, `productCode`, `gpu`, `vram`, `cpu`, `memory`, `disk`, and `ppIndex` when valid. Unsafe text and token echoes are excluded. Rows report incomplete identity explicitly, and **all** report `rateBindingVerified:false` because a matching workload GPU specification has not been established. The adapter does not invent a job-total estimate or attribute an arbitrary rate to an RTX 4080 SUPER.

Do not use `gcube auth status` or `gcube config get token` in captured diagnostics: the pinned CLI prints token prefixes. Normal CLI commands use `GCUBE_ACCESS_TOKEN`, while this adapter deliberately reads the separate protected `GCUBE_API_TOKEN` binding. The adapter does not invoke CLI login, read `~/.gcube/config.yaml`, or change credentials. If the CLI is used separately, `GCUBE_NO_UPDATE_CHECK=1` prevents its updater from making unrelated network/cache changes.

## Approval and executable operations

Python callers can import `GcubeOperations`, `SecretSelectors`, `Approval`, and `OperationsError`. `GcubeOperations.from_environment()` resolves the selectors inside the trusted control-plane process. `preflight(SER)`, `cost_snapshot()`, `verify_stopped(SER)`, `verify_stop_schedule(SER, stop_at=...)`, and `schedule_history(SER)` are authenticated read methods. Schedule history exposes a count, not raw provider log bodies or an inferred execution success.

Every executable stop requires an `Approval` with an explicit approval identifier, exact account and workload SER, allowed operation `stop`, a future expiration, finite positive `max_cost`, `USD` or `KRW`, bounded `max_wall_seconds` (1–86400), and `max_retries` (0–2). These values record a real operator authorization; constructing the object does not create authorization. This development task supplies no approval for a real account mutation.

`stop(SER, approval=...)` rechecks token/account binding, workload ownership and approval before sending the official **mutating GET** `/api/workloads/gai/{SER}/state/finish`. Opaque credentials whose token/account binding cannot be established fail with `AUTH_ACCOUNT_BINDING_UNVERIFIED`, even when read-only account requests succeed. It sends at most one stop request and makes one bounded independent describe readback. A transport timeout may happen after the platform accepted the stop; the result is unknown and is never automatically retried. Separate read-only verification is required. The stop path bounds every request by its remaining local wall-time budget; ending that local timer is never treated as billing cessation.

The newest raw `operations[0]` record takes priority over a stale workload `state`, following the official CLI. Only latest `type:STOP` plus `status:COMPLETED` counts as a verified provider stop operation. A raw `finish` state without operation history is insufficient for this stronger claim. Even a completed stop operation is not labeled an independent billing guarantee; review authenticated account billing evidence as needed.

## Why starts and schedule writes remain blocked

The official start route is a billing-changing **GET** `/api/workloads/gai/{SER}/state/deploy`. Registration is `POST /api/workloads/gai/register`, and `isDeploy:true` may start deployment immediately. Neither is called by this adapter. `plan_start(...)` returns a local blocked plan; `start(...)` and `deploy(...)` require approval and still reject execution. `register(...)` always rejects execution. The HTTP verb alone never classifies an operation as read-only.

No provider-enforced cumulative monetary hard cap is documented in the pinned sources. Registration's `maxPrice` is computed from current hourly pricing, not a job's cumulative spend limit. A finite approval budget, process timeout, CLI `--timeout`, STOP schedule, balance observation or watchdog does not establish such a hard cap. The official CLI timeout ends monitoring while the workload continues. Actual paid launch therefore remains `STRICT_PROVIDER_COST_CAP_UNSUPPORTED`; the adapter does not promise an unattended budget guarantee.

`plan_stop_schedule(SER, stop_at=..., approval=...)` requires a `schedule` approval, reads the dedicated schedule endpoint, preserves **every existing enabled and disabled entry**, records the timezone and snapshot hash, and appends an enabled one-time STOP with a future minute-precision deadline inside the approved wall time. Plans use the official Asia/Seoul timezone and fail if the timezone of an existing schedule cannot be established. `verify_stop_schedule(...)` requires the exact enabled future STOP and explicit timezone; an arbitrary old or disabled STOP does not pass. A verified saved schedule is not evidence that it executed.

Official schedule PUT is a **full-list replacement** without a documented revision/CAS condition. Read/modify/write cannot eliminate a concurrent edit between GET and PUT. Thus `install_stop_schedule(...)` and `rollback_stop_schedule(...)` reject execution with `SCHEDULE_ATOMIC_UPDATE_UNSUPPORTED`. The plan records a conditional rollback limited to one write: restore the saved original only after a current read matches the exact desired-list hash, then verify readback. This is reviewable planning information, not an executed rollback or a claim that the race has been solved. Never use blanket `unschedule` to roll back one added STOP; it removes all entries. No start path can bypass the blocked schedule/cost checks.

## SSH and the remaining external prerequisites

Official `gcube workload ssh SER --pod N --container N -- command...` can provision SSH, install an in-Pod daemon, register credentials and alter source-IP admission. It is not a harmless connectivity probe. The adapter's `ssh()` fails closed. An eventual existing-workload command path needs explicit authorization, a fixed approved command, a securely selected private key, pinned `known_hosts`, the provider-issued hostname/port with managed TCP grants, and independently verified stop and budget controls. None are configured or verified here. Do not assume browser terminal access grants this worker SSH access.

The current managed environment observations supplied to this task have no secret bindings, runtime variables, outbound identities, TCP grants or VPN. Names-only checks also found `GCUBE_API_TOKEN`, `GCUBE_EMAIL` and `GCUBE_ACCESS_TOKEN` absent. The root setup workflow records required secure bindings and the **api.gcube.ai** HTTPS domain; it does not publish credentials, guess an SSH endpoint, or authorize a paid launch. A physical NVIDIA render, actual account preflight, strict budget enforcement and complete unattended operation remain unverified.

## Local validation

```bash
python3 -m unittest discover -s world-simulation-shorts-engine/recovery/universal-production-v3/tests -p test_operations.py -v
```

The mock suite checks approval scope/expiry/finite controls, unauthorized mutating GET rejection, wrong account/owner rejection, local JWT account mismatch, opaque/oversized credential read-versus-stop behavior, retained GPU price identity, redirect refusal, response sanitization, incomplete/nonfinite billing rejection, disabled-schedule preservation, exact future STOP verification, stale-state/failure handling, single-attempt stop and ambiguous-timeout behavior. Mock JWTs are synthetic unsigned claim containers, not validated credentials. Passing these tests validates local adapter behavior only; it is not evidence of authentication, provider entitlement, hardware access, schedule execution, delivery or billing cessation on a real gCube account.
