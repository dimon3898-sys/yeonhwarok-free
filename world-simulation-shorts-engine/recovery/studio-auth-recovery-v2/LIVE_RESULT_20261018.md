# Studio authenticated recovery result — 2026-10-18 KST

**Authentication PASS. Historical CrashLoopBackOff cause UNCONFIRMED.**

The supplied repository Secret `GCUBE_ACCESS_TOKEN` successfully authenticated
official CLI 0.4.2 describe/pods requests for workload 5373. No credential value
was displayed or copied into this environment. No replacement Secret is needed.

## Actual observations

| Evidence | Result |
|---|---|
| Current workload state | `finish` |
| Returned pod status | `Terminating` |
| Official CLI live logs | Refused non-deploy state; CLI exit 1 |
| Official shipped HTTP pod log API | HTTP/API 404 |
| Historical first error / container exit code | Not returned; not inferred |

CLI exit 1 is not a container exit code. The platform did not return retained
stdout/stderr. HTTP 404 alone does not establish why historical logs are
unavailable. No workload state was forced and no GPU was started/redeployed.

## Confirmed current configuration blocker

Authenticated stored configuration has no `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN`.
The unchanged original image's previous CPU evidence proves this missing-input
condition emits `STUDIO_HTTPS_ORIGIN_REQUIRED` and exits 1. This establishes a
current reproducible startup blocker; it does not prove the first historical
GPU error without retained logs.

Other stored checks: approved image path/tag matches; port 8080; empty command;
owner input has valid format; raw universal image digest matches the approved
SHA; startup/render modes are `normal` / `gpu-required`. Actual runtime image
digest after termination was not observed.

Operator policy is absent. It is optional for startup, so it is not treated as
the startup cause. Production Start requires a valid policy later; no budget,
rate, expiry, duration, or retry value is fabricated.

The API did not provide an unambiguous admitted HTTPS service origin. A
non-secret address clarification was requested. Once the actual address is
confirmed, add only `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN` to the stopped
workload's existing settings, preserving all other values. No remote setting
update was performed. The official update method sends a whole body without
automatic merge; an unverified partial PUT is not used.

## Implementation and validation

Changes are limited to the independent diagnostic profile: official HTTP log
retrieval, safe actual state handling (`open`, `deploy`, `finish`), registry-relative
image normalization, and safe public-origin checks. No Studio production code
defect has been established or patched.

Focused offline and free CI tests: **26 PASS**. They are not GPU evidence.
Existing four CPU results were reused with their original SHA verification,
without rerunning container tests. Actual read-only receipts were committed,
fetched here, and verified against SHA256SUMS. The final configuration-only
request performed one describe GET and did not repeat the rejected log calls.

Evidence runs and receipt commits:

- `39075887886`, attempt 2: authenticated CLI, `1031d82`.
- `39078290370`: official HTTP 404 and stored settings, `000e2ea`.
- `39078505528`: configuration-only follow-up, `2c92c1e`.

Branch: `development/studio-auth-recovery-20261018`.
Existing FINAL/V4/Studio runtime/renderer/camera/frontier/claims/videos/images
were not changed or deleted. Existing image tags/digests were preserved.
High-confidence Secret scan: 0 findings. Required temp-only files: 0.

**New image: NONE.** A missing deployment-specific origin is a configuration
repair, and no justified production source change requires rebuilding an image.
Actual GPU startup, Studio operation, and 80-second production are unverified.

## Remaining action

Confirm the actual HTTPS Studio origin, without tokens or passwords. No guessed
origin or test value is substituted. Historical logs and terminated-container
exit state must come from retained platform records if available; a support
request is prepared separately and was not sent automatically. Paid GPU
redeployment remains prohibited in this task.

The execution environment briefly disconnected during final documentation.
It recovered; the work resumed from saved commit `2c92c1e` without rerunning
completed API requests or tests.
