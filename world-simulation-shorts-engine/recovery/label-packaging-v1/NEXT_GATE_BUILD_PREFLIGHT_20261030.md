# WORLD ENGINE — 355-source candidate build preflight (planning only)

Status: PLAN_ONLY / BUILD_BLOCKED. Source baseline: 9693132920bb269b6b6fefa1ed5ecd1e9e7e3237.
No image pull/build/push, Actions dispatch, permission change, GPU use or previous PASS rerun authorized by this document.

## Evidence already preserved
- label-packaging-v1/evidence/RESULT.json: 21 new source/context/entrypoint tests PASS; 333 inherited, 20 changed, 2 new labels, 355 rows.
- label-packaging-v1/evidence/CONTEXT_PLAN.json: 25 overlay files, 26 context files, pinned parent digest sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da.
- label-packaging-v1/evidence/Dockerfile.preview: declared ENTRYPOINT with only two changed manifest SHA arguments.
- Prior G2 Actions run 40767632198 succeeded on 353-source image; this is historical evidence, NOT live capacity/billing proof.

## First incomplete gate: LIVE_BUILD_PREFLIGHT
1. Read CHECKPOINT.json, RESULT.json, CONTEXT_PLAN.json, and prior G2 cost/capacity evidence. SKIP completed PASS.
2. Read-only verify live runner/Actions allowance, storage, permissions, billing and capacity. If not observable, mark UNKNOWN/BLOCKED; do not infer from historical success.
3. Verify build route has explicit one-attempt limit, zero retries, pinned parent digest, isolated candidate tag, no main or successful-image mutation.
4. Require explicit separate approval before any image pull/build or workflow dispatch. GHCR publication is a distinct approval and ACL gate.
5. After approval only: build one candidate; verify actual installed 355 source files/hashes, bootstrap, OCI config/ENTRYPOINT, UID1000 access and rollback. Fail closed and preserve logs.
6. Actual NVIDIA 10-second 300-frame MP4 requires another separate paid GPU approval. CPU source PASS is not visual quality PASS.

## Stop criteria
Stop at first FAIL/BLOCKED. Report verified facts, missing evidence, minimal next action, exact branch/commit and no invented PASS.
