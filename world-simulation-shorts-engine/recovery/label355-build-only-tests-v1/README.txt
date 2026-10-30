Focused free tests for four new label355 build helpers

Base 5b8564e309bb39b35f6417903662cb9cd2b93206 on recovery/label355-build-only-draft-20261030.
Existing CHECKPOINT gates and prior proofs were read; all17 prior PASS are reused.
Only preflight_build_only.py, verify_installed_355.py, backup_build_evidence.py,
and backup_to_recovery.py were changed, plus these new tests and bookkeeping.

102 DISTINCT new test cases PASS:25 preflight,31 installed verifier,19 local
backup and27 remote backup. Four Python files also compile without writing pyc.
LATEST_CASE_OUTCOMES.json derives the final outcome of every case from preserved
chronological logs. No old test suite was run. Initial failures are retained;
only failed/affected cases and new guards were subsequently executed.

All billing, registry and Docker results are synthetic. The355-file verifier
uses tiny generated355-row fixtures and the actual local UID1000; this is not
an installed candidate image validation. Every helper subprocess/HTTP/Git call
is mocked. Tempfile trees contain synthetic metadata only. Remote backup tests
do not run actual fetch/checkout/commit/push; the requested evidence commit is
performed separately through GitHub tools.

Repairs close boolean-zero and size/driver preflight gaps; missing bootstrap
SOURCE_SHA/worker linkage; input/output clobber; arbitrary private-like content
under safe filenames; forged index totals; destination/origin escape; mutable
bytes after checkout; and stale local-only readback after push. Safe summaries
remain closed producer contracts and no secret/raw stderr is exported.

OCI_RESULT.json and BUILD_RESULT.json currently have no reviewed producer
schema, so backup explicitly blocks them. PREFLIGHT.json and INSTALLED_RESULT.json
use their reviewed current producer formats. This is an unresolved contract gate
for those two future producers, not an image/GPU failure fix.

Actual Docker access, current billing/capacity, installed355-file/OCI/UID1000 and
actual helper remote backup are NOT_PROVEN. The draft workflow remains disabled
and untouched. No images, registry writes, Actions, GPUs, paid resources, main
or successful-image changes were requested or executed by these tests.

Run individual NEW failed/changed cases only when their source/assumptions change.
Use -B for Python. Preflight/installed/local test runners support --cases; the
remote runner supports unittest fully qualified case names. Do not rerun old PASS.
