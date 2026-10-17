# Studio authentication and recovery result — 2026-10-18 KST

## Authentication: BLOCKED_AUTH_REQUIRED

Official `gcube-cli 0.4.2` was reused locally and verified in a free public
standard GitHub Actions runner. Local official describe/logs still fail before
the API call: `No token configured. Run: gcube auth login` (CLI exit 1).
Neither a managed credential binding, outbound gCube identity, local CLI
configuration, nor token environment input is available. The repository Secret
metadata API was HTTP 403 and was not used as proof of credential absence.
Actual approved Secret inputs in Actions were also unavailable; collector
result: `APPROVED_SECRET_CREDENTIAL_NOT_PROVIDED`, credential source `NONE`.

Official `GCUBE_ACCESS_TOKEN` and the prior adapter's `GCUBE_API_TOKEN` are
different input names. The official CLI has no legacy alias. Actual legacy
Bearer compatibility remains NOT_TESTED; no value was fabricated or exposed.

An official environment draft update saved the correct optional personal
Secret requirement and retained prior requirements/settings. The result
required publication; actual runtime still has no binding. No available tool
can issue a gCube account token or publish the draft. Supported network access
was granted for this turn, which does not grant account access.

Official logs use WSS `console.gcube.ai:61443` with a query token. An HTTPS-only
managed proxy Secret is not claimed to authenticate that route. The prepared
free Actions route uses approved repository Secrets directly with the official
CLI, strict read-only commands, bounded logging, and redacted evidence.

## Actual workload 5373 cause: UNCONFIRMED

- Current deployment state: not verified.
- First actual startup failure: not retrieved.
- Actual container exit code: not retrieved.
- Environment/storage/UID/health/port failures: not established by live logs.
- Historical stdout/stderr: not retrieved. CLI has no previous-container log
  option and requires a deployed workload with existing pods.

No Studio production defect is established. Therefore no bootstrap, origin,
policy, owner, digest, storage, port, probe, or renderer change was made.
Fix-before/after success is NOT_RUN; it must not be inferred from offline tests.

## Independent completed work

1. Four existing CPU results were recovered with their original SHA256SUMS,
   without repeating container tests. Original image:
   `sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94`.

   | Synthetic condition | Original execution | Container exit | Result |
   |---|---|---:|---|
   | Required origin absent | Actual original ENTRYPOINT | 1 | `STUDIO_HTTPS_ORIGIN_REQUIRED` |
   | First-start owner absent | Actual original ENTRYPOINT | 1 | `STUDIO_OWNER_CONFIGURATION_REQUIRED` |
   | Generic unprefixed aliases | Actual original ENTRYPOINT | 1 | `STUDIO_HTTPS_ORIGIN_REQUIRED` |
   | Optional policy absent | Configuration function only | 0 | Config accepted; no GPU admission claim |

   Original results SHA:
   `a237740f24c524e2a30cdebce39a5c8f3a06dde53977a1e18db5e0c3e6c7746a`.
   These are fixture observations, not workload 5373 configuration evidence.

2. New read-only collector security/parser checks: 14 PASS locally and in free
   Actions. They cover allowed commands, missing credentials, legacy uncertainty,
   private raw capture, redaction, timeouts, explicit terminated states, wrong
   workload rejection, and distinguishing ordinary success codes from errors.
   Mock auth responses are not real authentication or NVIDIA validation.
3. Existing CPU artifact download was performed by official GitHub tooling in
   the approved free runner. Sanitized results were committed, fetched here,
   and checked against SHA256SUMS. Earlier local HTTP 403 was not hidden and
   the old tests were not rerun.

## Persistence and protection

- Branch: `development/studio-auth-recovery-20261018`.
- Implementation: `de08981b6b24a814609ca48c936d3670824fa458`.
- Sanitized receipt commit: `90df1ea`.
- Free run: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39075887886
- Source additions: isolated collector, tests, evidence-recovery helper,
  read-only workflow, instructions, and sanitized reports.
- Existing FINAL/V4/Studio/renderer/camera/frontier/claim/video changes: 0.
- Existing images/tags/digests overwritten: 0.
- New image tag/digest: NONE; no verified production fix requires one.
- GPU execution/deployment or paid calls: 0.
- Required temp-only files: 0.
- High-confidence Secret scan: 0 findings in the new deliverables.

## Exact next action

Securely supply the official token as `GCUBE_ACCESS_TOKEN` in this repository's
GitHub **Settings → Secrets and variables → Actions**. The official CLI directs
token issuance to https://gcube.ai/ko/demand/user/access-token . Do not send
credentials through chat or delete old Secrets. This is the prepared direct
Secret execution route for official WSS logs; it does not require GPU
redeployment or use of the disabled container terminal.

Then rerun the free read-only run above, or tell Codex secure connection is
complete. After real evidence arrives, only the established defect should be
fixed and reproduced, with a replacement image built only if needed. If old
pods/logs have been removed, obtain retained startup logs and the previous
terminated-container exit state from gCube support, without GPU redeployment.

Studio recovery and actual 80-second production are **not yet verified ready**.
