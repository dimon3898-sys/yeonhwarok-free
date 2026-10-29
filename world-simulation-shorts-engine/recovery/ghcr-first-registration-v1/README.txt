WORLD ENGINE GHCR first registration - CONTRACT PREPARATION ONLY

No actual repository/package/Secret creation, settings change, default-branch
registration, Actions execution, build, image copy/push or GPU action is performed.
The existing publisher code, policy and all earlier PASS evidence remain intact.

CONFIRMED CIRCULAR GATE
The normal publisher requires an existing candidate package's exclusive publisher
ACL before build/publication. A nonexistent package has no package settings from
which to establish that ACL. Do not change that gate to accept missing evidence.
The documented GHCR creation route is a first image publication. A separate
empty-package creation endpoint was not found in the official Packages API list.

SUPPORTED FIRST-REGISTRATION BOUNDARY
Proposed dedicated public bootstrap repository under the same namespace owner:
dimon3898-sys/world-engine-ghcr-candidate-bootstrap
Its OWN directly started workflow can use its repository-scoped GITHUB_TOKEN.
It must not run as the existing yeonhwarok-free caller or merely call a reusable
workflow hoping to change token scope. An owner PAT is not a package-only token
and cannot meet the old-package no-write condition. Do not use it.

The successful package must NOT link to, inherit permissions from, or grant
Actions write/admin to the bootstrap repository. Establish this by authoritative
read-only package settings evidence; never use a push/delete denial probe.
A token's packages:write scope is not by itself proof of access to every package.
GitHub also requires the relevant package/repository access grant. Conversely,
GITHUB_TOKEN gets admin on packages it publishes: acknowledge its temporary admin
capability on the NEW candidate package; do not claim it has no deletion capability
there. No old-package write/admin access is permitted.

PHASE A: FIRST REGISTRATION, SEPARATELY APPROVED IN THE FUTURE
Require reviewed bootstrap workflow/head, public standard-runner cost controls,
one explicit manual attempt, no retries and authoritative candidate absence.
An unauthorized or anonymous 404 is NOT authoritative absence.
Copy only the already public immutable parent image:
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da
to the fixed candidate package's unique bootstrap-parent-9378a86d8134-<runID>-a1.
This future copy is image publication and needs explicit approval; it is forbidden
in the present task. It needs no rebuild or new image labels. Preserve exact source
manifest/config/layer bytes and digest; never change the successful image or tag.
The seed is NOT the Vulkan option candidate and cannot satisfy its build/GPU gate.
This avoids transferring a newly built runner-local candidate across repositories.
No bootstrap publication workflow/client is added in this preparation stage.

PHASE B: CREATED BUT QUARANTINED
Read back package identity, exact source/destination digest, private visibility,
linked repository/Actions access and the successful package's unchanged ACL.
GitHub documents first workflow publication auto-linking, but inspect actual
association: preserved image source metadata may affect it. Do not add a source
label to force it, since that changes the image config/digest. Unexpected linkage,
existing namespace, conflict, auth error or ambiguous timeout stops without retry,
delete or automatic publication. Default private visibility stays private; do not
automatically make the package public (that change is irreversible).

PHASE C: NORMAL PUBLISHER HANDOFF, SEPARATELY APPROVED
After successful registration, an authorized package administrator configures ONLY
the candidate package's granular permissions: disable inheritance, grant the
non-owner normal publisher Write without Admin/delete scope, remove bootstrap
Actions write/admin access and any other automated writers. Acknowledge namespace
owner/admin break-glass authority; do not pretend GitHub removes owner admin.
Wait for bootstrap job completion/token expiry and disable further bootstrap runs.
Preserve actual before/after ACL and package receipts. Then evaluate the existing
normal policy as-is; the first-registration contract does not activate or edit it.
The old successful package needs no permission changes at any phase.

CURRENT STATUS / NEXT APPROVALS
FIRST_REGISTRATION_POLICY.json remains DRAFT_NOT_AUTHORIZED/executionEnabled=false.
Live package absence, bootstrap repository, old-package ACL exclusion, job/token
scope, copy tool/cost controls and post-create ACLs have NOT been verified.
The new module only validates supplied evidence in memory, with synthetic tests.
First registration and normal candidate publication are different approvals.
No Secret values belong in chat/source/evidence; configure normal-publisher Secrets
only through an approved store after the candidate ACL exists and is reviewed.

OFFICIAL SOURCES
https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
https://docs.github.com/en/actions/concepts/security/github_token
https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions
https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility
https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations
https://docs.github.com/en/rest/packages/packages
