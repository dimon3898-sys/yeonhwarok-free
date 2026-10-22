# Authenticated Studio presentation profile

This additive profile uses the preserved Studio authentication server and job
manager. It is a **source-checkout, free software-review profile**, not a claim
that the existing deployed GPU image or its visible production form changed.
The existing production prompt textarea does not yet construct this new V2
envelope. The verified UI path is mobile Chromium login followed by same-origin,
authenticated Studio API requests from the preserved test client.

## Exact request

```json
{
  "schema": "WORLD_ENGINE_PRESENTATION_STUDIO_REQUEST_V2",
  "prompt": {
    "schema": "WORLD_ENGINE_PRESENTATION_PROMPT_V2",
    "prompt": "Use my supplied locations, route and camera instructions.",
    "data": "<the complete, validated WORLD_ENGINE_DATA_PROMPT_V1 object>",
    "region": "<the geographic region object>",
    "presentation": "<the supported presentation object>"
  },
  "sceneId": "__timeline__"
}
```

The strings in angle brackets above describe objects, not executable fixture
values. Complete executable requests are the supplied `examples/*_NL.json`
envelopes wrapped by `run_studio_demos.py`. `__timeline__` selects every Scene
explicitly and requires an uninterrupted timeline, no blocked Scene and an exact
CUT at each Scene boundary. A named Scene is an explicit partial selection;
its original global frame interval is retained as `sourceFrameRange`.

## Preserved security and execution path

1. `local_application()` creates only a loopback, local-test Studio server.
2. The preserved mobile client authenticates at `/api/login` and receives the
   existing session/CSRF protection. Origin, CSRF and authentication checks stay
   in the unchanged server.
3. `/api/preflight` validates natural-language intent against attached data,
   compiles existing Planner Scenes, validates the full camera trajectory and
   crops one actual licensed source per complete camera envelope.
4. Source catalog, actual source bytes, native crop bytes, stable qualification
   wire/hash and source code bindings are checked before readiness and before
   a start claim. A missing or corrupt prior crop is refused, not overwritten.
5. `/api/submissions` persists the normalized request privately. Runtime wire
   order and semantic hashes are kept separately so Planner geometry ordering
   survives sorted JSON persistence.
6. `/api/start` with the saved `submissionId` still requires explicit owner consent and a
   bounded idempotency key. The original claim/active-job implementation starts
   one detached worker. Closing HTTP/browser connections does not kill it.
7. The worker rechecks source code and package seals. Capture re-prepares actual
   source/camera data in a new output directory and compares its qualification
   with the preclaim seal before browser draw. Rendering is serial, software-only,
   30fps, 1080×1920, 2–240 frames, at most 900 seconds and zero automatic retries.
8. An actual Scene switch occurs at each approved CUT; global and local frame
   indices remain explicit. One FFmpeg stream encodes the output. Full decoding,
   exact frame count and source/capture hashes are independently checked.

Historical production, paid GPU/API/deployment, automatic restart rendering and
resuming old production claims remain forbidden in this profile. Historical
compiler results remain inspectable; they provide no historical-render authority.

## Gated three-demo command

Only a root-reviewed `reports/GATES.json` with PHASE A–E PASS and matching SHA
authorizes the free short demos. The runner rejects a pending/failed gate.

```sh
PYTHONDONTWRITEBYTECODE=1 WORLD_ENGINE_NODE_DEPS=/workspace/universal-data-pipeline-v1-private-20261022/node-deps \
python -B world-simulation-shorts-engine/recovery/universal-presentation-v2/run_studio_demos.py \
  --private-root /workspace/up2-studio-actual-UNIQUE-ATTEMPT \
  --attempt UNIQUE-ATTEMPT \
  --gate-file world-simulation-shorts-engine/recovery/universal-presentation-v2/reports/GATES.json \
  --expected-gate-sha256 VERIFIED_GATE_SHA256 \
  --request world-simulation-shorts-engine/recovery/universal-presentation-v2/examples/AVIATION_EUROPE_NL.json \
  --name UP2_AVIATION_EUROPE \
  --request world-simulation-shorts-engine/recovery/universal-presentation-v2/examples/TRADE_SOUTH_AMERICA_NL.json \
  --name UP2_TRADE_SOUTH_AMERICA \
  --request world-simulation-shorts-engine/recovery/universal-presentation-v2/examples/FICTIONAL_AFRICA_NL.json \
  --name UP2_FICTIONAL_AFRICA
```

This is an operator test command, not a requirement for the mobile user to run a
terminal. It reuses the actual mobile login client, authenticated preflight,
submission/start, duplicate-touch and browser-disconnect/reconnect checks. Each
job has fresh private state and exclusive output names. No old claim or cache is
deleted. Failure logs stay in the private attempt root; safe execution summaries
and MP4/PNG/receipt copies go under this new namespace only.

Software technical success does not approve visual quality or verify NVIDIA.
The reports and capture receipts record these boundaries explicitly.
