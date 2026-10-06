# One World Engine address — deployment candidate

**Status: local acceptance passed; external deployment is blocked.** No live
World Engine address has been issued. The user does not operate Ports, Pull,
VS Code, terminals or Codespace lifecycle as the intended daily workflow.

After an eligible deployment is verified, daily use is: open its fixed HTTPS
address → World Engine password → topic → plan approval → generate/download.
The fixed address belongs to a deployed ASGI front, not a private Codespaces
port or a replacement-changing compute tunnel.

## Code and boundaries

- `portal.py`: owner login before compute allocation, exact Origin/Host CSRF
  checks, server-only backend owner session, existing UI/API relay, Range/HEAD
  and attachment streaming. No arbitrary upstream URL or wildcard CORS.
- `control_state.py`: persisted logout revocations and cumulative monthly
  compute reservations; same-month configuration changes are rejected. New
  allocation is blocked when its full lifetime plus300s startup headroom reaches
  the end of the verified UTC month, with a recheck immediately before creation.
- `budget.py`: no default free credit or price. Missing account verification,
  no-card evidence, disabled paid overage, current rates or reserve blocks use.
  This verifies the completeness of operator evidence, not the provider itself.
- `modal_candidate.py`: optional SDK1.6.1, deployed ASGI address and named
  bounded compute Sandbox. Public app-login entry intentionally does not demand
  Modal workspace proxy headers. Browser closing does not terminate a Sandbox.
- `sandbox_boot.py`: unchanged mobile gateway, owner secret to0600 file,
  existing jobs/checkpoint recovery,900s idle shutdown only without runnable or
  unknown jobs,4h maximum lifetime. Initial candidate permits only≤20s QA jobs.
  Provider credentials are never injected into this compute container.
- `../diagnose_access.py`: read-only safe probes to identify response signatures
  when the complete Codespaces URL is available. Never follows authentication
  redirects, logs in, or saves response bodies/cookies.

The approved generator, V3/Flat v004/Rhythm renderers,28 certified source hashes,
existing UI, cache, previous projects, media and Git history remain intact.
This module is not loaded by their normal startup.

## Operator activation — not end-user daily work

Only Codex/operator performs these commands after external authorization and
free account/billing checks. The Android user is not asked to enter commands.

1. Confirm actual Starter eligibility, no card requirement, paid-overage hard
   stop, retained-storage costs and current resource rates. Official examples
   mention free credits, but do not establish these conditions. Save verified
   `Budget` fields in an operator-private file outside the checkout. No usable
   budget template with invented prices is provided.
2. Provide Modal deployment credentials securely as `MODAL_TOKEN_ID` and
   `MODAL_TOKEN_SECRET`, never in chat/Git. Allow provider domains through the
   managed network policy: `modal.com`, `api.modal.com`, `api.modal2.com` and
   exact issued `*.modal.run` / `*.modal.host` endpoints. SDK1.6.1 supports the
   session HTTP proxy; TLS checks must stay enabled. Build endpoints must be
   added only if actually required and officially documented.
3. Create provider Secret `world-engine-owner` with `WORLD_OWNER_PASSWORD`
   (16–512 characters) and `WORLD_PORTAL_SESSION_KEY` (≥32 bytes). The operator
   can create this via the authorized SDK; the account token is not that password.
4. From the engine directory, use an isolated environment with
   `requirements-modal.txt`. Set `WORLD_ONE_URL_BUDGET_FILE` to the verified
   private file, then deploy `deployment/one_url/modal_candidate.py` with
   `modal deploy`. Import without this configuration does not create resources.
5. Record the actual provider-issued URL, verify public Android/login/CSRF,
  ≤20s background rendering with browser closed, ranged/full MP4 download,
   restart durability and no paid usage. Only then consider normal production
   duration limits; do not render75s for this acceptance task.

No service/account/Secret/card was created during this implementation. The
current managed environment has no Modal credential and denies native provider
access. No remote API deployment was attempted around those restrictions.

## Persistence caveat

Runtime, cache and generated audio mount three different provider Volumes at
their existing absolute engine paths. The front's control Volume is separate
and explicitly committed after logout/reservations. One named backend prevents
two render owners; local file locks are not claimed as distributed locks.

The Sandbox SDK enables background volume commits, but offers no public
Sandbox commit/flush API and no verified commit cadence here. Abrupt provider
termination durability, image build, storage admission and actual cloud render
speed remain **unverified**. This is why the adapter remains a candidate. A local
fsync or ordinary server restart does not certify provider volume durability.
Concurrent deploy/cold replicas could also require stronger distributed control
serialization; the candidate uses one front container, one named backend and
requires account-level zero-paid enforcement in addition to its reservations.

## Reproduce local checks

Engine dependencies stay unchanged. Optional relay dependencies are isolated.

```sh
python -m unittest deployment.tests.test_diagnose_access \
  deployment.one_url.test_portal deployment.one_url.test_budget \
  deployment.one_url.test_control_state deployment.one_url.test_sandbox_boot \
  deployment.one_url.test_modal_contract -q
```

The SDK construction test skips without the optional SDK; it was also run with
real SDK1.6.1, including its actual closure serializer after only declared
dependencies receive synthetic handles. Neither that test nor mock HTTPS/ASGI
transport deploys a service.
Full local acceptance and official source records are linked in
`../ONE_URL_MOBILE_REPORT.md`.
