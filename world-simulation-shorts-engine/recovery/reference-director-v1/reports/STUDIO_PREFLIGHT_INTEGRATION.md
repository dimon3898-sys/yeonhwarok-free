# Authenticated read-only Studio reference readiness

`studio_preflight.py` adds one opt-in readiness request family over the actual preserved `universal-presentation-v2/studio_adapter.py` controller and authenticated Studio HTTP server. It does not change those files or replace their authentication, Origin, CSRF, session, owner-file, production-submission, or claim handling.

```json
{
  "schema": "WORLD_ENGINE_REFERENCE_DIRECTOR_STUDIO_REQUEST_V1",
  "windowId": "A_CONTEXT",
  "targetSHA256": "090c499edd8791e74a0e0dec9f099af92a8d93739c6e9045b2f55a97369009e9"
}
```

Only `A_CONTEXT`, `B_FOCUS`, and `C_BOUNDARY_METRIC` are accepted; all extra fields are rejected. The target is a server-bound file with an exact hash, not a client-supplied capability or truth assertion. The protected renderer is checked against its actual `82854af` byte hash. Changing either file fails closed.

The separately sealed `REFERENCE_DIRECTOR_INPUT.json` (SHA-256 `4b892aadfb6415088a7a35bba58e9408d50bbd6f140d6e5c74d6f931e68b4dc0`) supplies the actual partial binding state. Spain's country geometry, the two sourced locality points, and the reference-observed `85 m` text are listed as available. Exactly six actual missing bindings are reported from that file's gate. The original unbound authoring target is not falsely treated as proof that those available data are still absent. Changing the partial input also fails closed.

An independent 85 m survey is **not required to display the reference-observed text**. Its geographic measurement truth remains explicitly unverified, separately from text availability; the missing real boundary geometry still blocks the intended line/metric rendering.

Authenticated `POST /api/preflight` returns a valid request with `ready:false` and `renderAllowed:false`, explaining `CAPABILITY_EXTENSION_REQUIRED` and `DATA_DETAIL_BLOCKED`, precise missing bindings, and needed native projection consumers. It reports local ranges 0..180/180/186 alongside the unchanged global source range 29..575 and global core count 546. No timeline reset, fake short global duration, or relaxed 240-frame limit is used.

Reference `POST /api/submissions` rejects with HTTP 409 / `RD_REFERENCE_RENDER_GATES_BLOCKED` before saving a submission, claim, or launching any process. This is truthful readiness integration only. The reference renderer/worker/encoder execution path is **not implemented or approved by this adapter**. Existing non-reference preflight/submission calls delegate to the preserved implementation unchanged. No public unauthenticated route, deployment, new GPU operation, or production UI change is introduced.

## Executed checks

Command: `PYTHONDONTWRITEBYTECODE=1 python -B tests/test_studio_preflight.py`

Twelve focused tests passed. Actual localhost HTTP exercised the preserved server with a newly generated private owner fixture, all three authenticated reference windows, health status, unauthorized access (401), invalid login (401), wrong Origin (403), missing CSRF (403), denied submission (409), unchanged controller files, and zero worker launch calls. Other checks cover extra admission flags, malformed window types, client/server target tampering, renderer tampering, missing owner file, read-only behavior, and delegation of existing request families.

The first restricted-sandbox run passed 11 tests but could not create a socket (`EPERM`). That was an execution permission limitation, not a Studio defect. The official escalation mechanism approved the localhost test; the same unmodified suite then passed all 12 checks in 0.788 seconds. After refining the adapter to use the actual sealed partial bindings, all 12 focused checks passed again. No assertions were weakened or skipped. Structured results and final actual unittest logs are in `STUDIO_PREFLIGHT_TEST.json` and the adjacent stdout/stderr files.

The localhost-only `local_application` factory reuses existing owner/Origin/CSRF setup for development checks. It is not a new public service or a gCube deployment procedure. No live owner credential, cookie, CSRF token, user Secret, or private fixture is included in reports.

No render was run. CPU HTTP checks do not establish NVIDIA capability, visual quality, geographic precision, readiness for production rendering, or reference reproduction.
