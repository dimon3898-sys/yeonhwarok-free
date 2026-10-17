# Studio V1 startup investigation result

## Actual workload evidence

**BLOCKED_AUTH_REQUIRED — actual workload 5373 cause unconfirmed.**

Official gcube CLI 0.4.2 was installed and executed. Authentication status is
not logged in. Read-only workload describe, pods, and the exact requested
`gcube workload logs 5373` each exit 1 with:

`No token configured. Run: gcube auth login`

No API request was made by those failed commands. This is a confirmed local
authentication blocker, not the container's first failure or exit code.
No actual Studio crash log was found in the inspected stored material.
Deployment state and real container exit code remain unverified.

## Independent free CPU verification

- Harness commit: `1440def79e547d345211f63496efa308cda4061e`.
- Free public standard Ubuntu GitHub Actions run:
  https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39074308838
- GitHub API reports workflow success; the actual immutable-image startup
  probe step and sanitized-result upload step both succeeded.
- The harness checks missing prefixed origin, missing first-start owner,
  incorrect generic variable aliases, and a separate configuration-only
  optional-policy probe. These are synthetic inputs, not real workload values.
- The artifact and job-log download endpoints returned HTTP 403 in this
  environment. Raw case records and artifact SHA have therefore **not** been
  independently downloaded/verified here. GitHub workflow metadata is stored
  in `CPU_RUN_RESULT.json`; this limitation is explicit.
- GPU devices, rendering, image builds/pushes, and gCube redeployment were not
  requested. CPU probe success is not NVIDIA or actual-workload success.

## Fix decision and preservation

No production code defect has been established. Therefore no production
source was modified and no replacement image was built. Required origin,
owner, source, storage, and GPU security checks remain intact. Existing
FINAL, renderer, camera, source data, image tags/digests, and the original
working checkout were preserved.

All new test code, sanitized evidence, and recovery instructions are isolated
on `development/studio-startup-recovery-20261018`. Required temp-only files: 0.
High-confidence secret-pattern scan of new deliverable text: 0 findings.
No authentication values or signed download URLs are included in these files.

## Exact next action

Supply official `GCUBE_ACCESS_TOKEN` through the managed environment's approved
Secret facility, or authenticate the official CLI locally with
`gcube auth login`. Do not send the token through chat. Then run the read-only
describe/pods/logs commands in `CLI_ACCESS_AND_RECOVERY.md` against the existing
workload. Do not redeploy a GPU to fetch logs. If the workload/pod no longer
exists, obtain retained startup logs and the previous terminated-container
exit code from the gCube console/support.

The first actual error and terminated-container state must establish the
cause before any production fix or replacement image is justified.
