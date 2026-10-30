Single runner.temp context defect — static preparation only

Source targetHEAD: 7efe029da0c372e97f376e9f332d01aad723d0fc.
Failed workflow: bf00c12a171ccdc8d3dd68b0f736b0f0157431d9.
Failedrun41024915935 was rejected before jobs atline26,column22.
Currenttargetworkflow is byte-identical to that failed version.

Safe preservation branch: review/label355-runner-temp-static-fix-20261030.
Execution target: recovery/label355-build-only-draft-20261030 (NOT UPDATED).
All56workflow event blocks were read at the sourcecommit.53push triggers use
literalbranch allowlists excluding this safebranch; no create/other automatic
trigger exists. No execution targetpush, merge, dispatch or rerun is performed.

Patchonly: remove the invalid job-envDOCKER_CONFIG runner.temp reference.
At the first authentication run, export the exact RUNNER_TEMP path, keepmkdir
andchmod0700, then append onlyDOCKER_CONFIG=<path> toGITHUB_ENV. This makes later
DockerCLI/publisher steps use the same auth directory. The token stays in the
original authstepenv and stdinlogin; it is never written toGITHUB_ENV. There is
no dedicated cleanupstep in the currentworkflow/publisher, and none is added.
Allother workflow fields, flags, steps, conditions and publishercode unchanged.

NEW staticverificationPASS: actionlint1.7.12 YAML/Actionscontext checks, PyYAML
parsing, bash-n for modifiedrun text, exact parsed/source diff and path-flow audit.
Optionalexternal shellcheck/pyflakes are disabled; no run text is executed.
Toolarchive verified against officialGitHubrelease SHA256 before use.
AlloldPASS are reused, including actual355image/installedverification. No old
suite, actualbuild, registrypublication, Docker/GPU or Actions execution.

Separate executiongateBLOCKED: fixedgithub.event.before is07ba1ad253bd1b1d055aa33f6f9386e1f9cb03f4,
while currenttargetHEAD is7efe029da0c372e97f376e9f332d01aad723d0fc.
The nextdirectpushbefore value would mismatch. The condition is intentionally
unchanged. Stop here; a separate executiongate must assess it before target
integration/newexecution. StaticPASS is notGHCRpublicationPASS.
