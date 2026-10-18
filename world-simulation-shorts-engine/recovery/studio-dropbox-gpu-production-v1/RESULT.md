# GPU production preparation: CPU candidate verified, owner approval pending

## Final immutable candidate

- Branch: `development/dropbox-gpu-production-20261018`.
- Parent saved source: `00cae13c4ce009ac3e56a8db1cf52f08de60a3cd`.
- Implementation checkpoint A: `04a56b91ccf9fdd5a5043dc0ec2f18cd602edab2`.
- Final image source: `a849ee8696f9f9a5c71f6f7ea82ac10423619549`.
- Build evidence: `abec427`; independent pull/recovery evidence: `f7b83b5`.
- Tag: `studio-dropbox-gpu-prod-v1-00cae13-39115824691-1`.
- Image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:c3bdd5107f28ceaaef9c3db2061d8dbe60f4abf17b6d541acc2d18a6462f2692`.
- Actual free CI: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39115824691

## Connected behavior

The existing offline Dropbox engine, encryption, per-scene checkpoints, cache,
FFmpeg verification, detached process manager, GPU admission and Studio are
reused. The verified key normalizer now runs in the production entry and each
fixed child stage; strict UID1000/0600 Secret reading and the original key reader
remain in force. Secret source files and decoded key bytes are unchanged.

No changes to existing FINAL, Candidate sources, Camera, Area, Flow, Event,
Planner, renderer, shaders, ASTRA, SFX or GPU policy. Only the new namespace and
its workflow differ from the parent commit. Docker inherited layer prefix,
original source manifests and dependency inventories match. No old image,
claim, cached scene, result or backup was deleted/overwritten.

## Actual free validation

| Check | Result |
| --- | --- |
| Focused CPU tests | PASS: 54, failures 0, errors 0, skips 0 |
| Actual frozen 240-minute/cost/expiry/retry validators | PASS |
| Original one-hour approval remains unchanged | PASS |
| Parent source/layers/dependencies | PASS |
| Secret Scan | PASS: 0 findings, unchanged pinned default rules |
| Unique tag build and GHCR publication | PASS |
| Independent runner digest/tag/config/payload pull | PASS |
| Actual Dropbox read-only fresh-root recovery | PASS |
| Second distinct CPU container rechecks retained cache/claim | PASS |
| Raw Secret input bytes preserved; new temporary copies removed | PASS |
| Remote backup writes/deletes during this recovery check | 0 |
| GPU deployment, NVIDIA execution, paid render | NOT EXECUTED |
| Actual gCube restart/probe behavior and 80-second production recovery | NOT EXECUTED |

The approved proofId remains
`08398705cd4ffb90a7f68a26ee6f65a121c5efa62ad4f854c1aa50ea371b55a7`.
No new upload/re-authentication/proof creation was performed. The prior upload
proof was authenticated and reused with the same key/prefix.

In final run `39115824691`, container `7015a981a446...` restored the existing
synthetic checkpoint from Dropbox; new container `ab358a928a7d...` verified the
same retained files. Both exited 0. Two completed synthetic scenes and one
incomplete scene were preserved; cache/claim tree SHA stayed
`ec4dc7934c52ee8b6e02edcb8a882303e84a4ba74a75283213f985c6b0e4066a`.
There were 16 then 12 authenticated downloads, zero remote writes, no execution
authority restoration and no automatic render. Full media decoding and cache
validation use the original functions. Production still rejects synthetic
checkpoints; this does not promote the probe to actual 80-second GPU evidence.

## Confirmed issues corrected along the way

1. First image check ran 33 tests successfully, but policy fixture setup lacked
   the inherited Studio import path. The isolated import reproduced
   `ModuleNotFoundError: studio_contracts`. Calling the unchanged runtime's
   normal initialization fixed the test harness; the engine was not altered.
2. The first live restart proof reported `EMPTY_ARTIFACT` because its inventory
   used a media-only hasher on normal empty lock/verification log metadata.
   The probe now fingerprints only exact known metadata with strict path,
   ownership, mode, link and before/after identity checks. Unknown empty files
   and empty media stay rejected. A probe-only scoped private umask preserves
   strict permissions and is restored on success/failure. The intermediate
   job was cancelled before an avoidable extra live proof. Failed/cancelled
   records and previous images remain intact.

## 240 minutes and new 80-second job

Existing validators accept `maxWallSeconds=14400`; use `maxRetries=0` for a new
job after owner approval. No deadline/claim from an old job was extended. The
actual deadline is the earlier of job creation plus wall limit and approval expiry.
This is the whole production-job wall limit, including preparation/composition,
not a separate additional four-hour GPU-draw allowance.
The new approval must include real hourly rate, currency, approved maximum cost
and sufficient future timezone-aware expiry. The controller requires budget to
cover four times the hourly rate. No price/expiry/approval was fabricated.

80 seconds / 30fps / 2400 frames / 12 scenes / 1080x1920 / H.264 and existing
SFX/visual profiles remain the inherited path. No long video or new 5-second
sample was rendered. Completion time and NVIDIA performance remain unmeasured.

The official stored catalogue at 2026-10-18 12:47:11 KST listed RTX4080SUPER
252-360 KRW/hour; four-hour arithmetic is 1008-1440 KRW. This is historical
catalogue evidence, not a current selected-node quote, complete bill or owner
cost approval. App timeouts do not stop gCube billing. Manual workload stop
remains the owner's action after result preservation.

## Exact owner actions and remaining boundaries

`GCUBE_SETUP.md` contains the verified image/tag/digest and exact environment
names/values. Service 8080, Command empty, shared memory 2GB and public-result
mount `/world-storage` are retained. Private Studio state is not moved there.
Reuse the same owner code and four existing Dropbox Secrets. GitHub Secrets
are not automatically injected into gCube and cannot be retrieved via a Secret
read API. No login/token reissue/key rotation is required.

Official gCube docs/CLI describe generic container environment values but do
not establish a dedicated restricted/masked Secret reference/file-injection
contract. The exact safe mechanism for this account must be confirmed before
transferring credentials; no ordinary YAML/describe body containing Secrets was
published or automatically sent. Confirm restricted Secret input or private
0600 file mount with gCube, then connect the existing values. Owner must also
approve the current selected-node quote, maximum cost/time and expiry before
any paid deployment. No gCube resources were deployed/stopped/changed here.

Production cold recovery already accepts explicit authenticated checkpoint ID,
original plan SHA, same original production image digest and fresh private root.
Fresh owner/Origin/policy setup and explicit start are required; authority/PIDs
are not restored and old claims are not reset. Current synthetic CPU proof IDs
must not be used as real production checkpoint IDs. Actual platform restart
grace and GPU behavior remain hardware checks after separate approval.

Required temp-only source files: 0. All implementation, configuration guidance,
run evidence and SHA manifests are remotely preserved. No FINAL promotion.

Decision: `GPU_PRODUCTION_CANDIDATE_CPU_VERIFIED_HARDWARE_PENDING`.
Next: `USER_APPROVAL_REQUIRED` with Secret delivery and actual cost settings
confirmed before deployment.
