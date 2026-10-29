WORLD ENGINE Vulkan surface candidate Actions preparation

STATUS: PREPARATION ONLY. No workflow dispatch, Docker pull/build, publication,
browser, GPU or renderer execution is authorized or performed by this prep task.

Immutable parent:
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da
Approved profile source commit: d259e61c96e83a97a8b97e797670786a434a240d
Approved profile SHA256: f55758af58a7c8724bddc097f05586b6d4cfdfa81133fa093636e335bca171c5

FILES
.github/workflows/world-engine-vulkan-surface-candidate.yml: workflow_dispatch only.
actions_candidate.py: cost/identity/driver/capacity gates and one-attempt stages.
package_candidate.py: four-file overlay and installed pin/config verification.
test_package_candidate.py and test_workflow_gates.py: new synthetic prep tests only.

SCOPE
Use the installed G2 tree, never the whole checkout. Overlay only profile_contract,
runtime manifest, installed bootstrap SOURCE_SHA, and startup manifest. Preserve
353 runtime rows (only the profile row changes), other 352 rows, generated variants,
worker, native guard and external bindings. Startup baseImageDigest is historical
and remains unchanged. ENTRYPOINT changes only its runtime/startup hash arguments.
Four explicit file COPY instructions preserve parent directory modes. No RUN,
installation, additional Chromium options or changes to original G2 tools/workflow.

EXECUTION BLOCKERS / REQUIRED SEPARATE APPROVAL
1. GitHub requires a workflow_dispatch workflow on the default branch before
   manual dispatch. This new recovery-branch file is not registered there. Do not
   add push/schedule triggers or modify main to work around this in the prep task.
2. A separately approved default-branch registration and explicit manual dispatch
   are required. The actor needs repository write permission to dispatch.
3. At dispatch, select the recovery branch, supply exact reviewed workflow HEAD
   (not historical d259 source commit), exact BUILD_SURFACE_CANDIDATE_LOCAL_ONLY,
   and fresh zero-cost/budget-control confirmation (default false).
4. Public repository, standard ubuntu-24.04 runner, github-hosted Linux X64,
   run_attempt=1 and matching checked-out SHA are required. Historical cost receipt
   is user-attested evidence, not a live billing API query. Current compute/quota
   and Actions/repository policy availability are not established by this prep.
5. contents:read/packages:read, Docker daemon/build access and anonymous parent
   pull availability must hold. No package write permission or registry login.

CAPACITY AND FAILURE
Reject vfs and unknown drivers before pull. Require overlay2 and actual Docker
data-root free capacity >= 4x compressed layer bytes + 8 GiB. This is a conservative
estimate, not measured expansion. Recheck an 8 GiB reserve after pull and before
the single build. No cache/image pruning, daemon repair, runner swap or automatic
retry. Per-stage exclusive attempt markers and failure receipt block continuation.
The local-vfs BLOCKED checkpoint remains historical; no local build is retried.

NEW VERIFICATION ONLY
Before build reject unapproved Dockerfile instructions, symlinks and extra/tampered
overlay files. After build compare installed four-file hashes, the 353-row manifest
connection and unchanged-row digest, frozen startup identity/worker row, bootstrap
SOURCE_SHA, ENTRYPOINT and other image Config fields. Confirm inherited parent
layer prefix plus four COPY layers and unchanged parent image identity/config.
Do not rerun G0/G1/G2, aviation, WAR scene/map/camera, pending10 or surface-option7.
No browser launch, service startup, owner input or GPU initialization PASS.

EVIDENCE AND IMAGE RETENTION
Only allowlisted bounded safe JSON/base64 chunks and SHA256 are emitted in job
logs, including after failure. No raw stderr, Docker Config.Env, environment dump,
credentials, upload-artifact/cache, Git write or package publish step exists.
Later authorized connector work must copy those safe receipts to the recovery
branch before log expiration; this read-only workflow cannot perform that backup.
Any future candidate image is runner-local and disappears with runner teardown.
An image ID is not a retained/deployable registry image. Separate retention or
publication design/approval is required before a later GPU deployment can use it.

REFERENCES
Existing successful run: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/40767632198
Manual registration: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
Compute/log billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
