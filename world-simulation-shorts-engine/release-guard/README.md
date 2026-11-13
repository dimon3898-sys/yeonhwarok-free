# Common WORLD ENGINE release gate

This gate applies to formal images for every scene type. It does not compile,
measure, render or encode any video. Required fixes are evidence-backed entries
in REQUIRED_FIXES.json: bounded frame-ledger reader, worker publication barrier,
and matching startup/runtime source pins. Whole source hashes preserve the
already validated security and launch behavior; changed code requires a reviewed
policy revision and changed-scope evidence.

Every package-writing Actions job in this branch, plus the separate OCI publisher,
installs the same runner-local Docker publication interlock before its original
checkout/build commands. The guard survives sparse checkout and later checkouts
in RUNNER_TEMP. A `docker push` invokes actual-image verification before invoking
the real Docker push. Any failure exits nonzero, saves a failure receipt, and
prevents publication. Every hooked job uploads the common receipts with always().
The existing build and render code is preserved. Direct buildx push, manifest push,
and skopeo registry copy are blocked until converted to the common loaded-image
gate; they cannot silently mint deployment-approved images.

`audit_workflows.py` checks every package-writing job and the isolated publisher
credential route, including future jobs. The mandatory publisher-wiring workflow
runs on workflow/gate changes and pull requests. Existing jobs with old images
fail closed if mandatory fixes are absent. This protection is independent of
GEOGRAPHIC, WAR, aviation, labels, geography or the current6s input.

Actual image admission runs as UID1000, read-only, network none, no capabilities,
NVIDIA_VISIBLE_DEVICES=void, and a bounded disposable tmpfs. It verifies the actual
imported worker, NVIDIA caller/reader binding, >32MiB metadata admission, preserved
generic32MiB cap, SHA/mode/single-link safeguards, and the actual entrypoint's
parent/child startup source closure. No GPU or renderer is called.

Admission produces candidate-only evidence. After publication, the registry digest
is pulled and matched to the inspected image before RELEASE_APPROVAL.json is
issued. Deployment admission requires that current policy approval, the same
image reference, both matching digest variables, and a stopped workload. This
does not authorize GPU deployment or rendering. The gCube UI save/readback is a
separate user-authorized configuration action.

Limits: these are repository/workflow controls, not an organization registry ACL
or immutable GitHub branch rules. Main and other branches were not modified;
their old workflow contents do not change retroactively. An administrator can
deliberately bypass/change workflow code or publish outside these paths. Such
images have no valid current release approval and must not be deployment candidates.
Never describe this as an unconditional guarantee against every future error.

The 2026-11-13 JSON incident's private GPU filename/byte count remains unknown.
The known code defect is independently reproduced using archived CPU evidence.
The additional v16 omission is a confirmed source defect, not a proven attribution
of that GPU incident. Existing visual/compiler/security/launch PASS suites are
reused rather than rerun; only the new gate and changed image integration run.
