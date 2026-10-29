WORLD ENGINE - minimal Vulkan candidate build/publication connection

Scope: preparation only. No image build, image copy/publication, GPU, rendering,
Secret creation, ACL change, workflow dispatch or default-branch edit is authorized
or performed. Do not rerun existing PASS suites. Do not extend bootstrap.

SELECTED PATH
Keep the existing separate candidate package:
ghcr.io/dimon3898-sys/world-engine-vulkan-surface-candidates
Tag:surface-v1-d259e61c96e8-<runID>-a1.
Use the already prepared original-repository manual publication workflow with its
read-only job GITHUB_TOKEN and a separately provisioned non-owner candidate-only
Write credential only in the final publication step. No new workflow or publisher
is needed. Existing PUBLISH_POLICY.json remains DRAFT_NOT_AUTHORIZED.

The successful package is read-only input:
ghcr.io/dimon3898-sys/world-simulation-shorts-engine
Parent digest:sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da
Profile modification remains d259e61c96e83a97a8b97e797670786a434a240d only.
The topic -> GPT JSON -> WORLD ENGINE rendering structure is untouched.

WHY NOT A UNIQUE TAG IN THE SUCCESSFUL PACKAGE
GHCR write permissions are package-level. A writer publishing a new tag in the
successful package can also change existing tags. A unique prefix, reviewed code
or pre-push absence check is not a tag-restricted credential or atomic create.
Do not describe that route as isolated or safe for the successful tags.
The selected candidate namespace supports a separate ACL boundary, but requires
actual evidence; a package name or policy boolean alone does not prove permissions.

EXISTING CONNECTION ALREADY PRESENT (REUSED, NOT REIMPLEMENTED)
.github/workflows/world-engine-vulkan-surface-publish-candidate.yml already calls:
publication preflight -> original build preflight/pull/stage/build/verify ->
registry-ready prepare -> one publish -> safe evidence collection.
The original actions_candidate.py/package_candidate.py are unchanged. Work paths
remain surface-candidate-work and surface-publish-work. publish.receipts() consumes
PREFLIGHT, BUILD, CONNECTION_VERIFY, IMAGE_SCOPE and STAGE_RECEIPT; actual existing
publish_contract.validate_evidence() binds fixed source/profile, 353 runtime files,
352 unchanged rows, four overlay files, manifest/bootstrap/ENTRYPOINT pin chains,
tested image ID and preserved parent/layers. Prior21 build and22 publication PASS
are reused. This task does not execute their tests or image-level verifiers.

EXACT MINIMAL CHANGE
Only vulkan-surface-publish-v1/publish_candidate.py changes, seven added lines:
1. policy_gate rejects namespace-owner publisher identity (case-insensitive),
   along with malformed GitHub usernames. The owner cannot truthfully satisfy
   the existing no-write/no-delete condition on its successful package.
2. prepare checks the local candidate tag resolves to the tested BUILD image ID
   before exporting it. Previously the ID was inspected but export used the tag.
   Existing export config/diff-ID validation already failed closed on changed
   bytes; it remains necessary for any alias race after this new precheck.
3. publish binds REGISTRY_READY.candidateImageID to the current BUILD receipt ID
   before using publication credentials or permitting the transfer.
No new helper framework, transport, permission grant or fallback route is added.

NEW FREE VERIFICATION ONLY
test_build_publish_connection.py exercises the new connections using actual
receipt loading and unchanged evidence/layout/precondition/readback validators.
Only Docker/skopeo/network effects are mocked and guarded. Small synthetic blobs
are used for the candidate; the previously recorded public parent manifest is
read-only fixture data, not a new registry query or an old PASS rerun.
Cases/log/exit code are recorded in evidence/RESULT.json and the new test log.
All resulting image IDs/digests/publication events in these tests are synthetic.
They do not prove an actual candidate exists or WebGL2 initialization succeeds.

FAILURE AND PRESERVATION
Existing stage markers, retry-times=0, candidate-only destination, fsynced intent,
raw manifest/tag/digest readback, original success-tag checks and sanitized evidence
remain. Wrong local tag/ID or substituted ready ID blocks before publication;
failed/ambiguous transfer still requires manual inspection without retry/delete.
Original build tools, publication contract, workflows, policy, bootstrap artifacts,
renderer, Scene, camera, native guard and successful images are unchanged.

REMAINING CONDITIONS FOR ONE REAL BUILD AND PUBLICATION
1. Candidate package existence and a reviewed real candidate-only normal-publisher
   ACL: non-owner Write without Admin/delete scope or successful-package write/
   delete rights; only approved automated writer, owner-admin authority acknowledged.
   Any missing package/ACL evidence remains BLOCKED. No provisioning is added here.
2. Approved policy with evidence SHA and reviewed skopeo version; separately stored
   final-step publisher credential inputs, never their values in chat/logs/source.
3. Separate approval to register the existing publication workflow on main and run
   the exact reviewed recovery commit once, with both existing build/publication
   confirmation strings and fresh public-standard-runner zero-cost confirmation.
4. Existing live permissions, overlay2/capacity, export-space and tool-feature gates
   must pass before their respective mutation. No local vfs retry or auto install.
5. Preserve new installed-pin/image-scope/digest receipts and readback evidence from
   that one run. Only then can a separate GPU validation request name the actual
   candidate registry digest. GPU execution requires its own approval.

Read-only current state: main has the build-only candidate workflow; the separate
publication workflow is absent there. This task does not install or dispatch it.
Live candidate package/ACL/credential readiness is not established by this work.
Preparation PASS never means image publication PASS or WAR GPU success.

Official permission basis (existing audit reused):
https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility
https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
https://docs.github.com/en/actions/concepts/security/github_token
https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
