# INVALID_TARGET observation fix

The old `Handler.dispatch()` rejected queries, absolute URLs, fragments and
targets longer than 4096 characters before invoking the proxy observer or
recording a diagnostic. This is a confirmed diagnostic defect, **not proof of
the real gcube INVALID_FORWARDED_HEADERS cause**.

The investigated file's Git blob is
`c040c22fdd67a16aea00bd8ebdf0ba94b686c449`. Anonymous registry verification
downloaded and hashed the small diagnostic COPY layer of `gcube-v006-diag`:

- Revision: `d614b210e29a758e38ce29bed9af3c801c0c8f25`.
- Digest: `sha256:8379661514b22ace09d463fc2e400f80b2af0dd43ddf82cb6061224b2d6506d4`.
- Its actual `server_diag.py` has the same Git blob and byte content as the
  investigated checkout. This establishes image/source correspondence without
  asserting which image any currently running remote Pod uses.

## Admission and privacy

`target.py` classifies the raw target separately from proxy validation and
authentication. BaseHTTPRequestHandler's leading `//` normalization is undone
for classification; controls are checked before urlsplit can discard them.
The stdlib error responder is overridden so invalid request lines/versions
cannot echo query secrets through its default error HTML.

Only length, form, scheme/authority/query/fragment presence, status and constant
rule identifiers leave the target classifier. URLs, paths, query values,
userinfo, request bodies and exception values never enter reports or stdout.
The existing observer masks header authorities and IPs with per-process HMAC
comparison IDs; auth/cookie/token headers remain excluded.

Valid **GET** queries are ignored only on `/`, `/auth/login`, `/diag.json`.
They do not supply passwords, redirects, origin bindings or filenames. HEAD and
mutating requests with queries, and queries on other paths, remain rejected.
No percent decoding, path canonicalization into another route, or URL fetching
is performed. `/diag.json` still requires an owner session.

Absolute targets require allowed HTTP/HTTPS syntax, valid port/authority, no
userinfo/fragment/control/backslash, and exact normalized scheme/authority
equality with the effective origin accepted by the **unchanged** proxy policy.
A different gcube workload is also rejected. The policy's current public mode
requires HTTPS; an HTTP absolute target cannot authorize login or receive a
cookie. When proxy validation fails, absolute authority admission is NOT_RUN.
No actual service URL or actual external TLS topology has been inferred.

Malformed targets still produce HTTP rejection. Both the target's primary rule
and the separately observed `proxy_validation` are retained. stdout recording
is bounded by the existing diagnostic rate limit; the request response still
contains its masked failure report. Raw HTTP-parser failures with unavailable
headers mark proxy validation NOT_RUN. Liveness remains a narrowly fixed,
query-free health probe and is never GPU readiness.

The validator SHA256 stays
`b5e66d4ceee91c25eab4daa8a24339a67c89592ae25ba2dacdc68c6bdb2ede07`.
All 21 AST rule locations remain mapped and tested. No operating engine,
renderer, GPU admission, login implementation, project or asset is changed.

## Same-input HTTP comparison

These are real local HTTP servers using the old file and the corrected file,
with explicitly synthetic proxy fixtures, **not captured gcube requests**.

| Input | Old server | Corrected server | Authentication |
| --- | --- | --- | --- |
| GET `/`, GET `/auth/login` | 200, no record | 200, masked record | No session issued |
| GET `/?probe=1`, `/auth/login?next=/` | 400 INVALID_TARGET, no record | 200, ignored query, masked record | No session issued |
| GET matching HTTPS absolute target | 400 INVALID_TARGET, no record | 200 after strict authority validation | No session issued |
| GET fragment | 400, no record | 400 TARGET_HAS_FRAGMENT, record | Rejected |
| GET 4097-character target | 400, no record | 400 TARGET_TOO_LONG, record | Rejected |
| Query plus synthetic XFProto=http | 400, no record | 403 X_FORWARDED_PROTO_NOT_HTTPS, record | Rejected |
| Wrong owner-code | 401 | 401 | Rejected |
| External Origin | 403 | 403 | Rejected |
| Forged forwarded authority | 400 | 400 | Rejected |

Additional tests cover sensitive queries, mismatching absolute authorities and
ports, HTTP absolute login rejection, parser exceptions, raw controls, fragments,
overlarge raw request lines, combined target/header failure, software/GPU
admission regressions, cookie security, and disabled renderer routes.

The fresh container smoke test checks bind 0.0.0.0:8000, owner login, query and
absolute-form handling, rejection rules, safe stdout, untrusted bridge peers,
and at least 61 seconds in the foreground. A same-container loopback relay is a
controlled test of trusted proxy handling; it is not the actual gcube topology.

## Existing gcube and T4 evidence boundary

The ZIP provides copied guard reproduction and reviewed source, not remote
headers, container logs, Pod identification, or a full exact service URL.
Configured cloud bindings supply no gcube identity/secret/VPN/SSH session.
No remote workload was inspected, started, stopped, updated or deleted.
No current service URL was guessed or requested. Stored evidence contained no
actual T4 loader/blocked/diagnosis log or retained `gcube-runtime.json`.

Official CLI source supports `workload logs` with Pod/container selection and
SSH for running workloads. These require authorized access and a running
workload; no credentials were requested in chat. Account/workload describe
data containing environment values must not be published wholesale.

Operating `start.py:run_engine()` calls `select_graphics_profile()` before
starting the production gateway, and writes the success record below
`storage.runtime_root`. A login error does not establish that GPU preflight
was never run. No prior T4 image/Pod/time/GPU verdict can be established from
the available evidence. The diagnostic image deliberately never starts GPU
checks; NOT_RUN is not a T4 failure.

The next evidence step is existing Container Log/stdout and any retained
runtime record from the identified operating Pod. If an already-running
diagnostic workload and exact authorized HTTPS URL are available, a single
query-free GET of `/` and `/auth/login` may expose the old proxy diagnostic.
Do not start a stopped GPU or create a new VM for this attempt.

Only if existing evidence is insufficient should an explicitly approved
diagnostic deployment be considered. The corrected **diagnostic-only** image
uses new immutable tag `gcube-v007-diag`; neither v006-diag nor v001–v005 is
overwritten. Image publication does not deploy it to gcube. It fixes target
observation, not the still-unidentified real proxy rejection.

Before any future public login replace the previously exposed owner-code via
approved secret/environment input, not chat. GPU success requires an actual
NVIDIA WebGL2 draw/readPixels on EGL **or** Vulkan; unused backends are NOT_RUN.
No CPU fallback, software renderer acceptance, or video render is introduced.

## Completed verification

- main source commit: `532bd68af7e9fa590a57f6a0743697511607584f`.
- Published diagnostic-only image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v007-diag`.
- OCI digest: `sha256:5123aff4b87f2ffaeec2e29ca12f3605948658c00a5dc0d953ad1597d1f6ece6`.
- Local diagnostic tests: 31 passed, no skips. Existing regressions: 230 passed, 1 skipped (231 run).
- Fresh-image diagnostic/security/regression suites and real container HTTP smoke: PASS; nonroot engine identity, 0.0.0.0:8000, owner login, strict rejection, sensitive-query stdout masking, 61-second foreground life.
- CI run: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37584164762
- Anonymous full pull in CI: PASS. Independent registry manifests/config/layer access: PASS; downloaded final COPY layer source matches checkout. v001–v005 and v006-diag digests preserved.
- Protected engine/renderer/GPU files: all 134 unchanged. No real gcube request, GPU run, workload operation or video render was performed.
- Actual gcube proxy rule, remote Pod/image assignment, external TLS topology and prior T4 GPU record remain UNKNOWN/NOT_AVAILABLE. Existing logs are the next evidence source; do not start or redeploy a stopped T4 just for this analysis.
