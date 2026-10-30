OCI / BUILD evidence schema connection — contract validation only

Base: fa3dbb203839f7a8e0933607d5738221f4856d5a
Branch: recovery/label355-build-only-draft-20261030

Read CHECKPOINT and existing102-case evidence first. All priorPASS were skipped.
Only backup_build_evidence.py changes: two closed-schema elif branches matching
produce_image_results.py. Producer, otherhelpers, workflow and sourcepins stay
unchanged. The existing PREFLIGHT/INSTALLED branches, shared parser, size/path
limits and snapshot collector are preserved byte-for-byte.

OCI has exactly8fields; BUILD exactly7. Reject missing/extra/private fields,
wrong schema/name/scope/parent, malformed SHA256 image IDs, integer/boolean
substitution and noninteger355. OCI's three match flags must be true booleans;
GPU must be false. BUILD accepts only IDENTITY_ONLY. PASS promotion is rejected.
The validated dict and payload bytes are returned unchanged.

New verification: actual producer.main was executed using synthetic inspect
metadata and the existing declared entrypoint. No actual image was inspected.
The initial3 producer/collection cases failed withUNREVIEWED_EVIDENCE_SCHEMA;
those3 were repaired and rerun, and20newnegative cases ran for the first time.
Final23cases PASS, exit0. Initial/error and final logs are preserved.
No existing102-case or older suite was executed.

The safe index remains PREPARED_NOT_REMOTE_BACKED_UP. The producer's OCI PASS
means only its OCI configuration comparison; BUILD IDENTITY_ONLY and the schema
PASS here are not proof of an image build, installed355sources, UID1000 access,
real remote backup, rendering orGPU behavior.

First incomplete stage: LIVE_BUILD_PREFLIGHT_COST_CAPACITY_DOCKER_ACCESS.
Current freecost/capacity and authorized localDockerAPIaccess remain unproven.
Actual candidatebuild and installed355/OCI/UID1000 checks, realbackup execution,
publication andGPU gates remain separate. Do not enable the draft workflow.

Evidence: evidence/RESULT.json, PRODUCER_CONTRACT_RECEIPT.json,
FOCUSED_TEST_RESULT.json, schema-initial.log, schema-focused.log,
SOURCE_CHANGE.patch andSHA256_MANIFEST.json.
