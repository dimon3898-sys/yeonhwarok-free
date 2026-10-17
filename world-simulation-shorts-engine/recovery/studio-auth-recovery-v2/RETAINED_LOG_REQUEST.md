# Prepared support request — not sent

Workload **5373 / world-engine-test**, image tag
`studio-v1-344dc2d-38883417252-1`, previously reported CrashLoopBackOff with
disabled container terminal.

Authenticated observations on **2026-10-18 around 08:10–08:18 KST**:
current state `finish`, pod `Terminating`; official CLI live logs rejected the
non-deploy state; shipped official HTTP pod-log method returned HTTP/API 404.
The pod/workload response contained no explicit terminated-container exit code.

Please provide retained startup stdout/stderr, first failure timestamp,
previous `lastState.terminated` exit code/reason, and related startup/readiness/
liveness probe events if retained. Please clarify the HTTP 404 retention or
endpoint limitation. Do not restart or redeploy a GPU to retrieve records.

Remove Secret values, private keys, sensitive environment values, and
token-bearing URLs before returning excerpts. No credentials are included.
