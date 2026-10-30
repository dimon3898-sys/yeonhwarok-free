Unchanged IMAGE_CONFIG_SAFE handoff — source preservation + new connection only

Base 9f0a1d5fd3f3354f1d408ba86c3126f1e6dfdc09 exactly matched the requested safe branch HEAD.
Safe branch: review/label355-runner-temp-static-fix-20261030.
Uploaded ZIP four-entry SHA list and all actual bytes matched. The3837-byte
image_config_safe.py is copied unchanged, SHA256eb271566ca3a9b7d73033b842a7d716e0a857dd47fcdd11d74da5edffb830ed1.
The attachment's INSTRUCTION.txt is preserved as data, not extra authorization.

The existing9 generator tests and11 localmirror contract tests are LOCKED_PASS,
reused from user evidence/ZIP report and never executed. All other oldPASS skipped.
Only3 NEW connections were run: CLI actualfile bytes through fetched9f0a validator,
collector andindex; CLI exclusiveoutput refusesoverwrite; actualserializedwire
raw128KiB+1 cap. Bothcommands exited0, no retries/fixes. Tiny synthetic inspect,
not actualimage data. Receipt stays CAPTURED_NOT_COMPARED, not build/comparePASS.

Fourteen producer/consumerfields agree. No generator, consumer or workflowcode
changes were needed. WrongID/parent/layers/privatefields/type cases remain reused
prior9/11 coverage, not repeated tests. The actualCLI output contains a normalLF.

Safe-branch proof reuses prior56-workflow audit:55currentworkflowblobs unchanged,
onechangedworkflow's event block still targets only the executionbranch. No push
trigger matches thisreviewbranch. No Actions, imagebuild, GHCR, GPU, main or
execution-target write. Old successfulimage/355source/102/23 proofs are reused.

This sourcepreservation task has no remainingblocker. The existing separateD9
executiongate remains BLOCKED: unexplained imageID mismatch must stop publication,
and that publisher control is not implemented/authorized here. Do not expand
scope or start a build; nextstage is a separately authorized control review.

Evidence: ZIP_VERIFICATION.json, ZIP_SHA256SUMS.txt, CONTRACT_AUDIT.json,
NEW_CONNECTION_RESULT.json, TRANSPORT_GUARD_RESULT.json, new-*.log,
SAFE_BRANCH_REUSE_RECEIPT.json, RESULT.json andSHA256_MANIFEST.json.
