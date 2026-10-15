# DIAGNOSTIC_ONLY trace at d1f6041

The user reports DIAGNOSTIC_ONLY from actual gCube #5373. The full live JSON, image identity and local files have not been retrieved in this CPU environment. No current gCube URL/credentials are configured. This observation does not by itself certify physical GPU execution here.

The code condition is exact: original bootstrap, source and dependency checks run, then original gpu_launcher.admit_gpu. On success it writes `admission_safe.json` and `admission_private.json` under the selected local private session's diagnostics directory and returns an Admission. The diagnostic worker discarded that successful tuple and made a generic DIAGNOSTIC_ONLY / exitCode 0 record. Thus DIAGNOSTIC_ONLY is a normal diagnostic-mode label; outer gpuRenderingVerified=false/renderAllowed=false are intentional render locks. The missing successful native check details are a confirmed observability defect, not evidence of a GPU failure.

Failures from _checks already retain their original stage/code and sanitized GPU diagnostics. A second confirmed defect is the later parent privilege-drop exception overwriting an earlier failed worker record; both original startup.main and active storage launch.main had that path.

The minimal change forwards only `Admission.private_report["probe"]["diagnostics"]` after validating the native result envelope through the existing make_record GPU allowlist. The bounded worker pipe, safe_record, local JSON persistence, shared safe export and existing /diagnostics handler already preserve safeDiagnostics.gpu. No new endpoint, record schema, renderer or GPU probe is needed. records.py, service.py, healthcheck.py, storage.py and original native GPU package remain unchanged. Generic DIAGNOSTIC_ONLY, render locks and readiness503 remain. Invalid/missing success evidence is explicit DIAGNOSTIC_RECORD_INVALID; an existing first failure is returned unchanged. A later privilege failure is separately recorded without admitting a service or renderer.

The independent read-only helper can recover an existing result without rerunning GPU checks. It requires the exact current loopback /diagnostics response, an identity-checked private export receipt, the exact exported safe startup JSON, and exactly one matching admission_safe.json within the bounded startup time. It never reads admission_private.json, copies raw records, opens a render route, initializes GPU, writes files or changes permissions. It cannot recover files destroyed by a restart or infer the newest candidate when evidence is missing/ambiguous. Synthetic helper tests always label TEST_ONLY.

Private result pattern at the baseline:
`/var/lib/world-engine-private/engine/session-*/diagnostics/<UTC>-<random>/admission_safe.json`.
Only safe summary is suitable for sharing; do not publish private admission, UUIDs, environment values, credentials or a whole diagnostics archive. Mounted-view file matching is not external backup or remote durability.

A diagnostic worker exitCode0 is not the container's eventual stop code. The existing bounded diagnostic service intentionally returns 2 on TTL/stop after a successful diagnostic-only check; this is not a new GPU failure. Failed readiness and render denial remain in place even with nested native evidence.
