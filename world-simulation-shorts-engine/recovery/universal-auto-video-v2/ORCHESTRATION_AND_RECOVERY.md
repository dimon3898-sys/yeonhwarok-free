# Universal coordinator and recovery

`orchestrator.py` runs the same plan/scene/cache/compose path at every supported
duration. It reads exact half-open global ranges, never restarts a scene clock,
and never keeps the complete movie or all decoded frames in memory. The
production dispatcher accepts only the verified `UNIVERSAL_AREA_ASTRA_V2`
renderer capability. Unknown adapters and unbound historical data fail before
GPU admission.

The implementation reuses the original storage adapter's no-follow directory
walk, streamed reads/writes, private POSIX constraints, original detached
manager's PID/boot-ID/start-time identity, original common `CAPTURE.guard`,
original NVIDIA admission, allocation query, memory limits and child cleanup.
The original fixed150-frame/one-shot7-file store cannot represent multi-scene
results, so the new ledger is separate; old managers and claims are untouched.

The fixed production path is:

1. Validate the complete plan and operator approval.
2. Acquire a private per-plan job lock and the unchanged common GPU lease.
3. Verify new and frozen sources, native dependencies, and prepare the original
   ASTRA activation once through `prepare_video.prepare_job_inputs`.
4. Rehash a successful scene cache entry, or obtain fresh native NVIDIA
   admission and invoke only the fixed `long_capture.mjs` CLI.
5. Verify the encoded segment and its frame count; commit an immutable cache
   receipt only after success. Bind the native per-frame evidence and receipts.
6. Copy each completed segment and its SHA manifest to a distinct Dropbox
   recovery export through the existing adapter. Keep private provenance anchors
   outside shared/Public Review folders. Mounted readback is not remote sync.
7. Compose, fully verify and export the final MP4 using existing FFmpeg and
   storage machinery. Rehash final mounted bytes before returning an old
   COMPLETED result. Missing/corrupt final bytes fail closed; no automatic paid
   rerender or deletion is triggered.

`start` detaches a fixed worker with `start_new_session=True`, disconnected
stdin, a private worker log and an actual PID identity. A real CPU PTY-hangup
test verifies the child survives terminal closure. The worker is not an HTTP
service. Nothing automatically starts on container boot. A container restart
or killed supervisor requires an explicit `--resume`; a live/orphan renderer
blocks duplicate dispatch. No claim is reset and failed attempts are retained.

## Approval and invocation

Paid execution has not been authorized or performed by this implementation
task. Before a real execution, an operator must explicitly approve the actual
plan, immutable image, known GPU rate, currency, total cost, wall time, retry
ceiling and expiry. The local JSON record is an operator authorization, not a
cryptographic signature or a gCube billing control. It contains no credentials.

The required fields are:

```json
{
  "schema": "WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1",
  "approved": true,
  "planSHA256": "ACTUAL_CANONICAL_PLAN_SHA256",
  "imageDigest": "sha256:ACTUAL_REGISTERED_IMAGE_DIGEST",
  "validUntil": "OPERATOR_APPROVED_ISO8601_TIME_WITH_TIMEZONE",
  "maxWallSeconds": 3600,
  "maxRetries": 0,
  "maxCostAmount": "OPERATOR_APPROVED_POSITIVE_DECIMAL",
  "currency": "OPERATOR_CONFIRMED_THREE_LETTER_CURRENCY",
  "gpuHourlyRate": "ACTUAL_CONFIRMED_POSITIVE_DECIMAL"
}
```

These placeholders are deliberately not executable authorization. The known
rate multiplied by the wall ceiling must fit inside the approved cost. Retries
are limited to0–2 for the whole job; the default is0. The same original deadline
and used retry count survive an explicit resume. An expired approval, changed
plan or image, unknown rate, unbounded cost, diagnostic mode or non-NVIDIA
admission blocks execution. The dedicated supervisor's wall timer covers input
preparation, admission, capture, composition and export. Native child shutdown
can require the original bounded cleanup grace. Stopping local work does not
stop external gCube billing; an official platform stop/schedule is separate.

Plan and approval files must be0600 under a0700 local POSIX directory owned by
the engine account. Production must run as UID/GID1000 with normal startup mode
and `WORLD_ENGINE_RENDER_MODE=gpu-required`.

After explicit approval, the fixed local entrypoints are:

```bash
/usr/bin/python3 -B /opt/world-engine-universal-v2/orchestrator.py start --plan /PRIVATE/VIDEO_PLAN.json --approval /PRIVATE/OPERATOR_APPROVAL.json
/usr/bin/python3 -B /opt/world-engine-universal-v2/orchestrator.py status --plan /PRIVATE/VIDEO_PLAN.json
/usr/bin/python3 -B /opt/world-engine-universal-v2/orchestrator.py start --plan /PRIVATE/VIDEO_PLAN.json --approval /PRIVATE/OPERATOR_APPROVAL.json --resume
```

The last command is an intentional resume, not a recommendation to retry a
failure blindly. `run` executes synchronously with the same checks. There is
no arbitrary shell command, executable override or production CPU fallback.

## Cache invalidation and durability

Each key includes the entire scene, original source manifests, renderer/image,
camera, timeline, material, encoder, global native binding and neighboring
boundary states. A title-only change can reuse every identical segment.
Independent scene changes invalidate their keys and changed adjoining boundary
contracts invalidate neighbors. The current full-global legacy/native binding
is conservative: any change to that binding invalidates every dependent
segment. Selective reuse is never obtained by dropping geometry or timeline
hashes. More granular verified per-range native dependencies can extend this
later without changing the cache protocol.

Failed renders never create success receipts. Corrupt receipts/artifacts,
symlinks, hardlinks, unsafe owners/modes, path traversal and shared cache roots
are rejected. A new attempt does not overwrite an old one. Disk usage scales
with completed compressed scenes, not full-length PNG sequences; the capture
adapter removes only verified newly generated intermediate frame files after
encoding and preserves bounded checkpoints/evidence.

The private cache is container-local unless a suitable private POSIX volume is
configured. Dropbox recovery exports protect scene bytes from terminal loss
and make them recoverable after a container replacement, but shared Dropbox
JSON is never trusted as a private NVIDIA provenance ledger. Automatic recovery
after private storage loss requires either a retained private POSIX ledger or
independently trusted operator hash/provenance anchors. The current coordinator
does not automatically adopt untrusted recovery files. Keep the workload until
final external-download SHA verification, or configure private persistent
storage before a long render. Mounted write/readback is explicitly distinct
from Dropbox remote synchronization and HTTP download success.

## Evidence scope

The focused tests include real filesystem/hash/lock/PID behavior and a real
terminal hangup. Hardware allocation tests use CPU mocks and mark no NVIDIA
PASS. Synthetic orchestration media is explicitly TEST_ONLY and cannot enter a
production cache. Actual FFmpeg composition and real mounted adapter tests are
documented separately. An80-second NVIDIA render,600-second GPU execution,
VRAM performance,60-minute production target and Dropbox external delivery
remain unverified until the separately authorized real job completes.
