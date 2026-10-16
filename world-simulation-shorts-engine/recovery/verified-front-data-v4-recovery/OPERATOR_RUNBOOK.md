# Archival front V4 — approved operator execution

This runbook prepares one complete 80-second production job. These GPU commands
have **not** been run by this development task. They require a separately
authorized, authenticated operator and an explicitly approved paid execution
policy. CPU/SwiftShader verification does not establish NVIDIA rendering or
video quality. No FINAL promotion is authorized here.

## Scope of the historical data

The unchanged 80-second plan has 2,400 frames at 30 fps and 12 event chapters.
Eight source-reviewed dated U.N. front snapshots are selected in 850 frames;
1,550 frames retain explicitly dated schematic context. These are approximately
registered **partial** source lines, not certified daily occupation polygons,
complete front coverage, or an exact armistice military demarcation line.
Unknown original cartographic accuracy remains unknown. No missing historical
movement, opposing occupation area, or military unit position is invented.

## Select the verified image

Read the final `IMAGE.json` in this namespace from the remote-saved checkout.
It is a post-build record and is not assumed to exist inside its own image.
Do not substitute the parent image or invent a digest. On the trusted checkout:

```bash
python3 -B - <<'PY'
import json
from pathlib import Path
p = Path('world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery/IMAGE.json')
d = json.loads(p.read_text())
assert d['built'] is True and d['pushed'] is True
assert d['independentDigestPullVerified'] is True
print(json.dumps({k: d[k] for k in ('imageReference', 'imageDigest')}, indent=2))
PY
```

Use that exact immutable `imageReference` only after its independent pull and
source inventory evidence pass. The image retains the original entrypoint,
default command, healthcheck, legacy images and all protected parent files.

## gCube configuration — after separate approval

- One RTX 4080 SUPER 16 GB; existing launcher compatibility for 4090/5090 is
  retained. Enable the provider's NVIDIA device and graphics runtime delivery.
- `/dev/shm`: **2 GiB**. Container RAM and the existing renderer's **8 GiB VRAM
  budget** are separate settings. No host NVIDIA kernel driver is installed by
  this image.
- `NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compute`.
- `WORLD_ENGINE_RENDER_MODE=gpu-required`.
- `WORLD_ENGINE_STARTUP_MODE=normal`; diagnostic mode is not a rendering mode.
- `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST`: the exact `imageDigest` read above.
- Keep the inherited entrypoint and command. Do not put the orchestrator command
  into an unverified gCube command-override field or replace normal startup.
- Mount the existing approved Dropbox export storage at `/world-storage`.
  Existing files and mount permissions must not be reset, deleted or recursively
  changed. The reused storage adapter performs actual isolated write/readback
  checks and does not treat shared Dropbox as trusted private POSIX storage.

Use only an already authenticated, approved in-container execution path. This
runbook does not provision SSH, change network admission, deploy a GPU workload,
or provide an unauthenticated render API. A gCube mobile terminal session is not
assumed to grant this Codex environment remote execution access.

The original normal startup checks storage, sources, dependencies and actual
NVIDIA/WebGL2 admission. A failed GPU check must remain a failure. The job also
reuses its own hardware admission, common GPU lease, VRAM controller and timeout.
Do not set a software backend, diagnostic-only mode or a test admission to make
production proceed.

## Create the private image-bound plan

The following commands belong in the approved container as **UID/GID 1000**.
The image-local namespace alias is `/opt/world-engine-front-v4`; private ledger
state is under `/var/lib/world-engine-private/engine/verified-front-v4`.
The alias resolves to the new source namespace; the protected V3 plan and
renderer remain unchanged.

First check the fixed source closure and create a fresh, private input directory.
Keep the printed directory path in the trusted operator job record. Run these
commands in the same shell, without printing environment values or credentials:

The Docker build creates the V4 control directory as UID/GID 1000, mode 0700.
The inherited bootstrap does not recreate this specific namespace if a mounted
or replaced private base hides it. The commands below create missing directories
and use the existing `PrivateTree` checks to validate ownership, permissions,
local filesystem and path isolation. They do not repair or change existing
permissions. Stop on a failed validation; do not apply chmod/chown to work around
an untrusted or incompatible mount.

```bash
set -euo pipefail
test "$(id -u)" = 1000
test "$(id -g)" = 1000
test "$WORLD_ENGINE_STARTUP_MODE" = normal
test "$WORLD_ENGINE_RENDER_MODE" = gpu-required
/usr/bin/python3 -B /opt/world-engine-front-v4/source_manifest_recovery.py --verify-extension
umask 077
mkdir -p -- /var/lib/world-engine-private/engine/verified-front-v4
/usr/bin/python3 -B - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, '/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-auto-video-v2')
from cache import PrivateTree
with PrivateTree(Path('/var/lib/world-engine-private/engine/verified-front-v4')):
    pass
PY
FRONT_OPERATOR_DIR=$(mktemp -d /var/lib/world-engine-private/engine/verified-front-v4/operator-input-XXXXXXXX)
set -o noclobber
/usr/bin/python3 -B /opt/world-engine-front-v4/scene_binding.py \
  --image-digest "$WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST" \
  > "$FRONT_OPERATOR_DIR/VIDEO_PLAN.json"
printf '%s\n' "$FRONT_OPERATOR_DIR"
```

`scene_binding.py` derives the execution plan from the exact bound parent plan,
adds the actual `FRONT_PROFILE.json` and `FRONT_FILES.json` digests to
`sourceManifest.archivalFrontV4`, sets the selected immutable image digest, and
uses the unchanged V3 work-scene allocator. Camera, legacy geometry, event
chapters, frame count and source chronology are not retimed.

The Python hardware adapter calls the fixed local `long_capture.mjs` shim.
That shim adds only the image-local profile/manifest paths and their verified
hashes to `front_capture.mjs`; callers cannot choose another capture program or
replace the four archival-data arguments. The V4 runtime checks those bytes and
the execution-plan source binding again before the unchanged NVIDIA-only opener.

## Private approval — template is deliberately non-executable

The existing coordinator requires exactly these authorization keys:

`schema`, `approved`, `planSHA256`, `imageDigest`, `validUntil`,
`maxWallSeconds`, `maxRetries`, `maxCostAmount`, `currency`, `gpuHourlyRate`.

Create a **blocked template**, not an execution approval. This computes the
canonical plan hash used by the frozen coordinator. It is distinct from the
SHA-256 of the pretty-printed JSON file:

```bash
/usr/bin/python3 -B - "$FRONT_OPERATOR_DIR" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, '/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-auto-video-v2')
from cache import canonical_sha256
directory = Path(sys.argv[1])
raw = (directory / 'VIDEO_PLAN.json').read_bytes()
plan = json.loads(raw)
approval = {
    'schema': 'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1',
    'approved': False,
    'planSHA256': canonical_sha256(plan),
    'imageDigest': plan['renderProfile']['imageDigest'],
    'validUntil': None,
    'maxWallSeconds': 3600,
    'maxRetries': 0,
    'maxCostAmount': None,
    'currency': None,
    'gpuHourlyRate': None,
}
with (directory / 'OPERATOR_APPROVAL.json').open('x') as output:
    output.write(json.dumps(approval, sort_keys=True, indent=2) + '\n')
print(json.dumps({'canonicalPlanSHA256': approval['planSHA256'],
                 'planFileSHA256': hashlib.sha256(raw).hexdigest(),
                 'approved': False}, indent=2))
PY
```

Only the authorized operator may replace the blocked approval after obtaining
the user's explicit GPU authorization. Use the actual allocation's hourly rate
and currency, approved maximum cost and wall time, retry count (0–2), and a
timezone-qualified future expiry. Monetary amounts/rates use the coordinator's
validated positive decimal format. Keep the existing plan and image hash
bindings. The template's 3,600 seconds is a proposed local ceiling, not an
approved budget or a proven 60-minute production time. Leave `approved:false`
and the unknown fields null until approval exists. Do not put tokens, account
passwords or SSH keys in this record.

The coordinator rejects an expired or mismatched approval and a time ceiling
whose rate-based cost exceeds its approved maximum. This local guard cannot
prove or stop provider billing. Actual pricing, account permission, workload
stop and billing cessation must be separately verified. No provider-enforced
cumulative spend cap or automatic gCube billing stop is certified here.

## One detached job — future approved execution only

After all approval prerequisites are satisfied, the trusted worker invokes:

```bash
/usr/bin/python3 -B /opt/world-engine-front-v4/orchestrator.py start \
  --plan "$FRONT_OPERATOR_DIR/VIDEO_PLAN.json" \
  --approval "$FRONT_OPERATOR_DIR/OPERATOR_APPROVAL.json"
/usr/bin/python3 -B /opt/world-engine-front-v4/orchestrator.py status \
  --plan "$FRONT_OPERATOR_DIR/VIDEO_PLAN.json"
```

`start` launches the fixed in-image worker with a separate session and closed
terminal descriptors. Closing the browser/terminal therefore does not supervise
or terminate the worker. Job ID, actual process identities, progress, first
failure, scene receipts and completed hashes stay in the private ledger. The
existing common GPU lease excludes other renderer jobs, including legacy
65422/ASTRA/V2 jobs. An identical live job is observed rather than duplicated.
No existing claim, receipt or result should be deleted or reset.

For interruption, inspect `status` and the private worker log first. If the
original process is still alive, do not start another job. After its termination
is verified, an explicitly authorized resume uses the same command plus
`--resume` on `start`. Existing completed scenes are rehashed and reused; the
original deadline, retry accounting and plan binding remain in force. An
expired job is not revived by deleting its state or changing its timestamps.

Terminal disconnection differs from container termination. For adoption across
container replacement, the private POSIX ledger needs approved persistent
storage or a separately verified trusted recovery anchor. Dropbox export
receipts alone do not establish private job ownership or make automatic
cross-container recovery safe. No automatic workload restart/resubmission is
provided by this runbook.

## Completion, Dropbox and external verification

The reused serial scene renderer writes bounded per-scene captures, verifies
H.264 segments, composes and fully decodes the final 80-second, 1080×1920,
30-fps silent MP4. Do not invoke `--render-65422`; it is the older five-second
fixture, not this production job.

Read the coordinator's completed status `result.exportDirectory` and verified
`files` hashes. The export directory is a newly created path beneath
`/world-storage`; do not guess or reuse an older export. The unchanged public
allowlist is:

- `WORLD_ENGINE_AUTO_VIDEO.mp4`
- `SHA256SUMS`
- `QUALITY_SUMMARY.json`

Keep source maps, internal plans, approval records, raw data, logs, diagnostics,
private receipts and PNG validation evidence out of the public folder. Mounted
readback establishes only `mountedViewReadbackVerified:true`. It does not prove
Dropbox external sync or mobile delivery.

After Dropbox sync, obtain the actual authorized HTTPS download links. Require
HTTP 200, download every public file, and compare the downloaded SHA-256 values
against the private completion receipt and `SHA256SUMS`. Fully decode and play
the MP4; verify 80 seconds, 2,400 frames, 1080×1920, 30 fps, H.264 and no audio.
Review archival-date qualifiers, partial-front meaning, ASTRA/coast appearance,
native markers, camera continuity and mobile readability in the finished
80-second video. Do not ask the user to approve intermediate five-second samples.

Stop the paid workload only through the separately approved official provider
procedure. Verify actual stopped state and account billing records; a renderer
timeout, completed MP4, accepted stop request or closed terminal is insufficient
proof that charges ended. Actual NVIDIA success, external delivery and video
quality remain unverified until their real evidence is collected. The final
video remains `USER_VIDEO_REVIEW_REQUIRED`; no FINAL promotion follows here.
