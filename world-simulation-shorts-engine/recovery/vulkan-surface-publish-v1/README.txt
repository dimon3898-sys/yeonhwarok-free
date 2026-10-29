WORLD ENGINE verified Vulkan surface candidate publication - PREPARATION ONLY

No workflow registration/dispatch, Docker/skopeo execution, image build/push,
GPU/render, secret creation or registry permission change is performed here.
Existing 21 preparation PASS cases and all earlier PASS suites are reused.

REUSE AND LEAST PRIVILEGE
The original build-only workflow/actions_candidate.py/package_candidate.py remain
unchanged. The separate publish workflow retains every original build/verification
step verbatim and adds policy/tool gates, registry-ready export and publication.
The job GITHUB_TOKEN still has only contents:read/packages:read. GitHub permissions
are job-level, not per-step; this design does not claim step-level permissions.
Only the final publish step receives two separately provisioned Secret inputs:
WORLD_ENGINE_SURFACE_GHCR_PUBLISHER_USER and WORLD_ENGINE_SURFACE_GHCR_PUBLISHER_TOKEN.
Do not place their values in chat, source, job-level env, image context or logs.

SEPARATE REGISTRY BOUNDARY
Successful package (read-only): ghcr.io/dimon3898-sys/world-simulation-shorts-engine
Successful digest: sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da
Candidate-only package (proposed, NOT provisioned by this task):
ghcr.io/dimon3898-sys/world-engine-vulkan-surface-candidates
Tag: surface-v1-d259e61c96e8-<GitHub-run-ID>-a1; reruns are forbidden.
Existing destination tags are a hard failure, never overwritten or deleted.
GHCR tags are mutable and a missing-tag check is NOT an atomic create guarantee.
Therefore an independently reviewed candidate-exclusive publisher ACL, which cannot
write/delete the successful package and has no delete scope, is a prerequisite.
No same-package broad writer token or prefix-only restriction substitutes for ACLs.

DEFAULT LOCK / EXECUTION BLOCKERS
PUBLISH_POLICY.json is DRAFT_NOT_AUTHORIZED and deliberately blocks BEFORE build.
A separate explicit approval must supply a truthful approved policy, publisher
identity/ACL evidence SHA, exclusive-writer proof and exact approved skopeo version.
The new workflow also requires default-branch registration, separately approved
manual dispatch, exact reviewed HEAD and both build/publication approval strings.
No push/schedule trigger, repository_dispatch workaround or main modification.
Existing cost/public standard ubuntu-24.04/zero-budget confirmation, overlay2,
disk/permission gates remain. vfs and retries remain forbidden. No install step is
added: missing/wrong skopeo or unsupported CLI flags block before any image build.
Current tool, ACL, credential, package provisioning and live cost/disk/permission
readiness are UNVERIFIED, not implied by the new synthetic tests.

DIGEST CONTRACT
After every new-image receipt is PASS, bind image ID, profile, parent, 353 rows,
four overlays, pin-chain and layer-preservation receipts. Never rerun old tests.
Export that verified daemon image once to compressed skopeo dir: transport with
OCI manifest (not another build). Require export space 2x image Size + 2 GiB.
Hash exact manifest/config/layer blobs; config digest must equal tested image ID,
and layer diff IDs must equal the tested image's RootFS. Unsupported conversion,
indexes, foreign URLs, changed bytes or extra files are BLOCKED.
Expected registry digest is SHA256 of these exact manifest bytes. It is NOT the
Docker image ID and NOT a registry digest observed before the new tag exists.
Before transfer require target absence and successful tag/digest baseline match.
Transfer only dir: -> fixed candidate namespace with --preserve-digests and
--retry-times=0. Credential is held in a fresh private authfile only for that step,
excluded from child env, argv secrets, image layers, evidence and build contexts.
After transfer compare digestfile, tag-addressed raw manifest and digest-addressed
raw manifest, expected digest and tested config ID. Recheck original success tag.
Only then may a registry-retention PASS receipt be emitted. No GPU PASS follows.

FAILURE AND EVIDENCE
Exclusive per-stage markers prevent retry. Safe mutation intent is persisted and
flushed to logs before transfer, so a hard timeout is not mistaken for no mutation.
On transfer/readback failure record BLOCKED, attempt1 and remote ambiguity; do not
retry, delete, roll back a tag, rebuild or permit GPU execution. A partially or
fully uploaded remote object may exist without a verified receipt.
Only fixed bounded safe JSON/base64 receipts leave the runner. Authfiles/raw logs/
Docker config/environment are excluded. No artifact/cache upload or Git write step.
Later authorized connector work must back up safe log receipts to the recovery
branch before log expiration. Existing successful image/tag/digest are never targets.

FREE PREP TESTS
Run only test_publish_contract.py and test_publish_control.py for this new contract.
They simulate manifests, transfers and failures and cannot execute subprocesses.
No original 21 tests, Docker, skopeo, network, build, registry or GPU proof is claimed.

References:
https://github.com/containers/skopeo/blob/main/docs/skopeo-copy.1.md
https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
https://docs.github.com/en/billing/concepts/product-billing/github-actions
