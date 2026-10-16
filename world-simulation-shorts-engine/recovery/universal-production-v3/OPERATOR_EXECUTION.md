# Production V3 — execution boundary and one-job procedure

This procedure is for an authenticated trusted operator/control-plane worker after
explicit approval. It is not a request for mobile-terminal scene commands. No
paid GPU is deployed or started by this development task.

## Account and provider prerequisites

Review/save/Publish the environment draft and verify its actual application.
Official-history HTTPS sources and api.gcube.ai are required; api.github.com is
also required for direct Actions status queries (currently CONNECT403). Git
repository access works separately and is used to preserve CI evidence.
GCUBE_API_TOKEN must be provided through the approved secret binding, never chat.
GCUBE_EMAIL and GCUBE_WORKLOAD_SER identify the intended account/workload.
Opaque proxy credentials allow authenticated reads but do not prove local token
account binding; stop mutations fail closed when that binding remains unverified.

Read workload snapshots, GPU pricing, schedule reads and point/balance snapshots
through the allowlisted operations.py adapter. Its verify_stopped result derives
only the latest STOP completion from workload state; it does not expose raw
operation records or detailed spending/billing endpoints. Detailed spending and
billing cessation require a separately authorized official read. Price rows are
not yet matched to an actual RTX 4080 SUPER allocation; reported rates remain
unverified until that match.
The official evidence does not document an enforced cumulative spend cap, and
schedule writes lack an atomic revision guard. Thus deploy/start/register and
schedule-write automation stay blocked. Do not treat rendering timeout as a
billing stop. Resolve the provider-enforced budget/termination policy before
claiming unattended paid operation is safe. A separate supervised policy would
need explicit user authorization and would not be automatic-operation success.

SSH execution is not currently connected. It requires approved private-key file
selection, strict known-host verification, existing account-authorized endpoint,
source-IP/TCP access and a bounded fixed-command executor. Never use CLI commands
that print token prefixes or --show-password. Do not automatically provision SSH
or alter access rules during read-only checks.

## Runtime configuration

Use the new immutable image recorded by IMAGE.json once verified, retaining the
parent image and completed claims. RTX 4080 SUPER16GB, /dev/shm2GB, normal startup,
WORLD_ENGINE_RENDER_MODE=gpu-required and
NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compute are required. Set
WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST to that exact image digest. Keep the inherited
ENTRYPOINT/CMD and Dropbox /world-storage. Do not use diagnostic-only mode.

Private control state is UID/GID1000,0700 under
/var/lib/world-engine-private/engine/universal-production-v3. Files are0600.
A persistent POSIX ledger or trusted recovery anchor is required for adoption
across container replacement; Dropbox shared receipts alone are insufficient.
No existing V2 claim or completed export may be deleted/reset.

## Approved single production job

After the image is finalized, use the image-bound FIRST_PRODUCTION_80S_PLAN.json
and canonical SHA recorded in FIRST_PRODUCTION_REQUEST.json, copied byte-for-byte
into the trusted private job directory. The source fixture stays image-unbound
to avoid a circular image digest. A newly generated plan needs a new approval.
OPERATOR_APPROVAL_TEMPLATE.json is deliberately approved:false with unknown rate,
cost and expiry. It cannot authorize execution.

Only after real price, currency, maximum cost, maximum wall time, retry count,
expiry, account permissions and termination policy are explicitly approved may
the trusted worker invoke the fixed in-image entrypoint:

```bash
/usr/bin/python3 -B /opt/world-engine-production-v3/orchestrator.py start --plan /PRIVATE/VIDEO_PLAN.json --approval /PRIVATE/OPERATOR_APPROVAL.json
/usr/bin/python3 -B /opt/world-engine-production-v3/orchestrator.py status --plan /PRIVATE/VIDEO_PLAN.json
```

These commands have NOT been executed against gCube. They reuse the original
hardware-only admission, common GPU lease, private cache and detached worker.
They do not themselves deploy/stop a workload or enforce platform billing caps.
After interruption, verify that the previous process ended and use explicit
start --resume; retain original deadline/retry counts and completed scene hashes.

## Completion and user review

The coordinator captures12 work ranges on one global2400-frame clock, verifies
segments, composes H.264, fully decodes the final80-second1080x1920/30FPSsilent MP4,
then uses the unchanged export adapter. Public Review contains MP4,SHA256SUMS and
a safe QUALITY_SUMMARY only; keep sources/diagnostics/logs private.

Mounted readback is separate from Dropbox external sync. Acquire the real HTTPS
download URL, require HTTP200, compare downloaded SHA and fully decode/play the
MP4. Review ASTRA/coast/territory/front/native markers/camera/mobile readability.
The user reviews only the completed80-second video. Confirm actual workload stop
and account billing records separately; API acceptance does not prove billing
ceased. No FINAL promotion occurs before user video approval.
