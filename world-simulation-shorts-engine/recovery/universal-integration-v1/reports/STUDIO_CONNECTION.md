# Independent Studio integration entry

This change adds an opt-in source candidate. It does not modify the existing
Studio entry, FINALs, renderers, camera, data, existing jobs, or current GPU
image. No GPU job, container, rendering, or deployment was started.

## Actual API connection

The new `studio_entry.py.Application` subclasses the preserved HTTPS proxy
application. It injects only a new controller factory. Existing owner login,
session cookies, CSRF checks, fixed HTTPS Origin checks, proxy normalization,
request limits and GPU admission remain inherited.

The inherited authenticated routes now reach this independent controller:

| Route | Actual behavior in this candidate |
| --- | --- |
| `POST /api/preflight` | Parse V1 unchanged or V2 using `contract_v2.py`; enforce the integrated production and 5-second quality prerequisites before any native GPU preflight. |
| `POST /api/submissions` | Save the exact frozen `videoPlan` and sibling `integration` metadata in one hash-bound submission. Saving never renders. |
| `POST /api/start` | Preserve owner consent, budget, idempotency and claims; dispatch V2 only to the explicit integration bridge. Block if prerequisites are absent. |
| `POST /api/jobs/{id}/resume` | Recheck the integration quality gate and preserve the original authorization/deadline before a bridge recovery can run. |
| `POST /api/jobs/{id}/revisions` | V2 returns `STUDIO_UNIFIED_REVISION_NOT_CONNECTED`; frozen SFX-only revision must not silently drop the new metadata. |
| `GET /api/integration/profile` | Owner-authenticated, Origin-checked profile metadata; always reports `renderAllowed: false` and no hardware verification. |

There is no authentication-free setup or production API. The previous HTTPS
setup and login flow remains in place. The shipped mobile UI is read from its
preserved source; only its browser-local job/start/resume storage keys receive
the new `world-studio-unified-v1-` namespace. This prevents an old browser job
identifier from being mistaken for a new integration job. No UI or video asset
was copied into a replacement renderer.

## Input and dispatch

Use the versioned `WORLD_ENGINE_STUDIO_PROMPT_V2` example in
`../PROMPT_V2_COOKBOOK.md`. The inner prompt can configure the five validated
`visualProfile` values. The original V4 plan remains unchanged; new metadata is
stored as the sibling:

```json
{
  "integration": {
    "schema": "WORLD_ENGINE_UNIVERSAL_INTEGRATION_V1",
    "profile": "VISUAL_UNIFIED_V1",
    "visualProfile": {
      "territoryOpacity": 0.62,
      "frontCoreWidthPixels": 4.8,
      "frontGlowRadiusPixels": 10,
      "frontGlowGain": 0.42,
      "cameraApproachFrames": 48
    }
  }
}
```

Changing that metadata changes the submission hash. Per-instance `ContextVar`
dispatch passes the complete immutable submission to the new bridge. Missing
bridge methods fail with `STUDIO_UNIFIED_RUNTIME_NOT_CONNECTED`; they cannot
fall back to the old renderer. This test does not prove an integration runtime
is already included in a deployed image.

V1 normalization remains exactly delegated to the original parser. However,
this **new** execution profile blocks V1 long-video production with
`INTEGRATION_PROFILE_REQUIRED_BEFORE_80S`. Otherwise, selecting the old preset
could bypass the user's mandatory integrated 5-second quality approval. The
original independent Studio entry remains unchanged.

## Private state and approval

The controller adds the private namespace
`<existing production control root>/universal-integration-v1`. Existing claims,
completed results and job history remain untouched. A missing owned parent
directory is safely created using the existing `PrivateTree`; existing modes
are never repaired or loosened. The existing parent operator policy is read
without modification when no new-namespace policy is present.

The production gate reads only its server-chosen private receipt path
`<new control root>/quality_receipts/approval.json`. Neither the receipt path,
quality verdict, GPU proof nor source-image proof is accepted from a prompt.
The unchanged private budget validator is called again by the quality gate.
An accepted prerequisite receipt still does not replace explicit start consent,
physical NVIDIA checks, GPU lease, native admission, or the original time/cost
limits. It does not control provider billing or deploy/stop a workload.

The existing global GPU lease remains a dependency of the actual integration
runtime. This controller does not introduce a second GPU-lock implementation.
No global parent module functions are monkeypatched.

## CPU verification

`tests/test_studio_entry.py`: **9 tests PASS**. These tests use actual inherited
HTTP handlers, owner authentication, CSRF/Origin checks, private storage and the
actual new quality gate. Render backends and source/image/receipt evidence in
the tests are explicitly synthetic fixtures. No fixture is a real permission
to render.

Verified:

- V1 input normalization equality and explicit long-video production block.
- V2 metadata preservation and distinct immutable submission IDs.
- Missing 5-second quality receipt blocks before native GPU preflight.
- An auto-cleaned private receipt fixture exercises the real positive quality
  gate and then reaches only an explicitly fake bridge, which rejects hardware.
- Blocked starts leave no start claim and invoke no rendering backend.
- Existing private state is preserved and an existing policy can be read.
- A missing integration bridge never falls back to V1.
- Actual localhost HTTP V2 preflight/submission uses inherited authentication
  and CSRF protection; wrong Host and Origin are rejected.
- The reused mobile script uses a separate local job namespace.

The initial sandbox denied binding a localhost socket; the supported execution
permission mechanism allowed the same free CPU tests to run. No external
service, paid work, GPU, WebGL draw or MP4 was used.

## Remaining boundaries

The new entry requires a complete source manifest and a new package before it
can be exposed as an operational service. `studio_entry.verify_extension()`
fails closed if `RUNTIME_SOURCE_MANIFEST.json` is missing or inconsistent, and
the existing inherited source checks still run. The current deployed image is
not modified by adding these files to GitHub.

The new controller intentionally cannot authorize 80 seconds until the new
source/image/Scene bindings, required historical data, actual 5-second NVIDIA
comparison and explicit user quality approval exist. Historical unit positions
or bilateral ownership cannot be invented to satisfy these conditions.

Actual gCube HTTPS behavior, physical GPU admission, rendering, detached bridge
job recovery, output quality and new-image inclusion remain separate validation
items. Existing previous evidence is reused; CPU fixtures are not reported as
those items passing.
