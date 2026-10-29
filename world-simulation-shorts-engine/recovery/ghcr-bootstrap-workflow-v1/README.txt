WORLD ENGINE - GHCR first-registration workflow PREPARATION ONLY

This directory is a deployable root for the dedicated PUBLIC repository
dimon3898-sys/world-engine-ghcr-candidate-bootstrap (GitHub repository ID1438054766).
It is preserved in yeonhwarok-free's existing recovery branch, NOT installed as an
active workflow there. The target repository is currently empty (branches=[]).
Separate default-branch installation approval remains required. No Actions run,
image copy/publication, Docker, build, GPU, Secret or package setting change is
performed by this preparation task.

REUSED EVIDENCE
Source contract commit:4ed3db0299ae7ad9c73c6dda7a09ac11d85104a2.
The existing14 first-registration tests and every earlier PASS are reused without
execution. tools/registration_contract.py is the unchanged original pure module;
SHA256:16287be23c51d9964992e92cebf6203b8c49d343a7f82a219af34a2a6604bd00.
Only the new workflow/client controls are synthetically tested. No original
publisher, policy, workflow, renderer or source image is changed.

INTENDED ONE-TIME OPERATION (NOT AUTHORIZED OR EXECUTED HERE)
Source, fixed by digest:
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da
Destination, fixed package with a unique run-ID tag:
ghcr.io/dimon3898-sys/world-engine-vulkan-surface-candidates:bootstrap-parent-9378a86d8134-<runID>-a1
This seed is an UNMODIFIED old parent, not the Vulkan surface candidate.
Copying it is first publication and needs separate explicit approval.

FILES TO INSTALL ONLY AFTER SEPARATE APPROVAL
.github/workflows/world-engine-ghcr-first-registration.yml
BOOTSTRAP_POLICY.json
tools/registration_contract.py
tools/bootstrap_registration.py
README.txt
OWNER_ATTESTATION.example.json
Do not copy tests/evidence into .github/workflows or modify the original project's
default branch. Register this manual-only workflow on bootstrap/main only after
reviewing the exact bundle. First publication cannot use the original repository's
token or a reusable workflow called from it. No PAT or manually created Secret is
used. The workflow uses its own repository-scoped GITHUB_TOKEN.

EXECUTION GATES
The shipped policy is DRAFT_NOT_AUTHORIZED, executionEnabled=false,
skopeoVersion=null. DRAFT refuses before network/tool/registry effects.
Future approval must separately authorize installing the workflow, select the
reviewed preinstalled skopeo version (no installation or fallback), and enable the
policy in a reviewed bootstrap commit. This task does none of these actions.
Public GitHub-hosted standard ubuntu-24.04 only; live repository ID/public status,
main ref, reviewed exact commit/policy/workflow hashes, direct namespace-owner
dispatch and triggering actor, runAttempt1, fresh zero-cost and budget-stop
confirmations are mandatory. Fixed concurrency never cancels a running copy.
No retry, rerun, second copy, build, label change, prune, delete or repair is allowed.
An existing candidate package or ambiguous response blocks first registration.

The owner must supply a fresh <=600-second non-secret attestation covering BOTH:
1. Namespace-owner-authorized candidate PACKAGE absence, not merely tag absence.
2. Old successful package has no bootstrap link/inheritance/Actions write/admin.
   The user's supplied Actions-list observation is preserved as intake evidence;
   it alone does not prove all three conditions or current candidate absence.
The attestation binds the exact reviewed commit, policy and workflow SHA256 and
confirms an exclusive namespace window with no concurrent external publisher.
Package screenshots/API evidence remain with the owner; only hashes and allowed
metadata are supplied. Never include credentials, private raw logs or API bodies.
The client checks schemas/bindings/age/owner identity, not screenshot authenticity.
A repository GITHUB_TOKEN/anonymous404 is only a secondary check and NEVER replaces
authoritative owner absence. 200,401,403,429, network failure or malformed metadata
stops. No push/delete denial probe is performed against the successful package.

GitHub permissions are JOB-level, not STEP-level. Only the isolated first-
registration job requests contents:read and packages:write. Checkout is SHA-pinned,
does not persist credentials, and receives the reviewed exact commit. The client
token is provided only to the registration step. Preflight has no token argument.
GitHub grants the creator workflow admin on the NEW candidate package: this includes
candidate deletion capability, acknowledged rather than denied. The client never
uses it to change settings/delete. Old-package write/admin is prohibited.

RUNTIME CONTROL AND SAFE EVIDENCE
Before the single copy, verify installed skopeo/version, free-space gate, raw source
manifest digest and existing success-tag digest, owner evidence and fresh candidate
absence. No Docker daemon or local image is needed. Copy uses preserve-digests and
retry-times=0, fixed endpoints, bounded commands/copy/job timeouts. Private temporary
authfiles carry the token; it is not a command argument, receipt or child environment.
Raw process stderr and raw remote metadata are never emitted. Evidence filenames
are fixed, append-only, confined to a fresh private RUNNER_TEMP subdirectory.
An intent receipt is fsynced and printed before mutation; bounded safe outcomes are
printed to the run log. No artifact/cache upload or repository-write token is used.
After any failed/timeout/ambiguous mutation: outcome unconfirmed, stop, preserve
intent, inspect independently; NO retry/delete. Hard cancellation can leave only
the already-flushed intent, which is not success evidence.

POST-REGISTRATION IS QUARANTINE, NEVER NORMAL PUBLISH READY
The client reads actual candidate package identity/private visibility/linked
repository and both tag-addressed and digest-addressed raw manifests. Exact parent
digest/manifest and the old successful tag must match. Unchanged source metadata
can affect association; unexpected association stops without relabeling or repair.
Package metadata does not prove complete Actions ACLs. An API read failure after
copy is unconfirmed, not evidence that publication did not occur.

Same-job output is provisional pending INDEPENDENT post-job owner review. It does
not call validate_created_seed or claim token expiry/job completion/creator role.
An authorized reviewer must later gather read-only actual package ID, bootstrap
association, private visibility, exact source/destination digest/byte preservation,
candidate creator ADMIN acknowledgment, old-package ACL exclusion AFTER copy,
completed job and expired job token. Use the unchanged contract's
validate_created_seed only once those actual receipts exist. No post-job API
repair/settings automation is included. GitHub's documented token expiry at job
completion is distinct from the receipt that proves this particular job completed.

Future candidate-only normal publisher handoff is a separate approval: disable
bootstrap workflow/access and inheritance, remove other automated writers, grant
non-owner Write without Admin/delete scope or old-package rights; acknowledge owner
admins. Existing normal publication policy stays locked and unchanged.

CURRENT USER ACTION / NEXT APPROVAL
Review the prepared bundle and evidence. Before ANY actual first registration,
separately approve bootstrap default-branch installation and one immutable-parent
copy; provide fresh authoritative absence/full old-ACL evidence, namespace freeze,
reviewed tool version, free-cost/budget confirmation, exact commit/policy hashes
and creator-admin acknowledgment. Do not dispatch while DRAFT or any proof is absent.
No GPU initialization or Vulkan candidate image success is claimed here.

PRIMARY DOCUMENTATION (already audited; reused)
https://docs.github.com/en/actions/concepts/security/github_token
https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions
https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility
https://docs.github.com/en/rest/packages/packages
https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
https://docs.github.com/en/billing/concepts/product-billing/github-actions
https://github.com/containers/skopeo/blob/main/docs/skopeo-copy.1.md
