# Official authentication and safe Studio recovery

## Credentials and protocols

Official `gcube-cli 0.4.2` reads `GCUBE_ACCESS_TOKEN`, then the local official
CLI configuration. It does not recognize `GCUBE_API_TOKEN` as an alias.
The existing V3 `universal-production-v3/operations.py` separately uses
`GCUBE_API_TOKEN` as its default Bearer-token selector. These are different
application input names. A legacy value is not proven compatible until the
official CLI completes an authenticated read-only request.

Official reference: preserved, SHA-verified `gcube_cli-0.4.2-py3-none-any.whl`,
`gcube_cli/cli.py:84`, `gcube_cli/api/client.py`, `gcube_cli/api/logs.py`.
The preserved wheel's official README directs headless users to:
https://gcube.ai/ko/demand/user/access-token

The CLI's browser login is PKCE with a loopback callback on the machine running
the CLI. Opening a remote Codex login URL on a phone does not connect the
phone's localhost callback to Codex. Do not start that flow here or invent a
token. The documentation does not establish a read-only token scope or expiry;
do not claim either without verification.

REST describe/pods calls use HTTPS Bearer authentication to `api.gcube.ai`.
Official logs use WSS to `console.gcube.ai:61443` with the token in a query
parameter. An HTTPS-only proxy Secret binding does not establish authenticated
WSS support. Never extract a proxy Secret or print a signed/token-bearing URL.
Do not print raw `gcube auth status`: this CLI version displays a token prefix.

## Current managed environment

Current runtime observations report no secret bindings and no outbound
identities. Neither official nor legacy token is present; the local official
CLI configuration is absent. Official describe/logs return local exit 1 with
`No token configured. Run: gcube auth login`. This is not a container exit.

The environment draft now includes optional personal `GCUBE_ACCESS_TOKEN`
delivery to HTTPS `api.gcube.ai`, preserved legacy requirements, and retained
startup instructions. Existing 11 custom destinations were preserved; added
destinations are `gcube.ai`, `console.gcube.ai`, and `data-alliance.github.io`.
Draft revision 13 was saved with `requires_publish: true`; it is not applied or
published. No value was supplied and no old Secret/requirement was removed.
The missing old `GCUBE_API_TOKEN`, `GCUBE_EMAIL`, and `GCUBE_WORKLOAD_SER`
requirements remain unchanged. Filling them with fabricated values is forbidden.

The environment tools can save requirements for secure user entry, but cannot
mint a gCube access token, log in as the user, or publish the environment.
An official network-access request was granted for this turn; it does not
grant gCube account authorization. Anonymous live documentation requests still
encountered a proxy error; official source evidence was reused instead.

## Approved free execution route

The separate `studio-auth-readonly.yml` workflow uses a free standard public
GitHub runner and the exact official CLI. It can use existing repository
Secrets without revealing their values. Metadata listing of repository
Secrets was HTTP 403 here, so their availability was not inferred from that
API failure. The workflow checks its actual Secret inputs safely.

The collector permits only these fixed commands for existing workload 5373:

```text
gcube --version
gcube -o json workload describe 5373
gcube -o json workload pods 5373
gcube workload logs 5373
```

No workload start, stop, update, delete, render, GPU deployment, image build,
or paid API is present. Logs are bounded, raw output remains private to the
ephemeral runner, and only strict sanitized fields are persisted. No public
rendering or diagnostic HTTP API is created. GPU/Studio status is never
reported successful because this read-only workflow itself completed.

If an official repository Secret is available, use it. A legacy Secret is
tried only when the official one is unavailable, and compatibility is recorded
only after a real successful read. If both are unavailable to the job, the
report remains `BLOCKED_AUTH_REQUIRED` and no gCube request is attempted.

## Exact user action if still blocked

1. Sign in to the official gCube access-token page above and obtain the proper
   token. Do not send it through chat.
2. In the repository's **Settings → Secrets and variables → Actions**, securely
   supply repository Secret `GCUBE_ACCESS_TOKEN`. Do not delete or rename any
   existing Secret. This raw-secret runner route supports the official WSS
   client without extracting a managed HTTPS proxy Secret.
3. Resume or manually run the isolated read-only workflow on branch
   `development/studio-auth-recovery-20261018`. If GitHub does not display a
   dispatch action for a workflow outside the default branch, Codex can push
   a report-free trigger change on that existing branch after the Secret is
   connected. No gCube deployment or terminal is needed for this step.
4. If workload/pod records have already been removed, official CLI 0.4.2 has no
   `--previous` option and requires a deployed workload with pods. Request
   retained startup stdout/stderr and previous terminated-container exit state
   from gCube support. Never redeploy a paid GPU to retrieve old logs.

Only actual error/exit evidence can justify a minimal Studio fix and subsequent
focused CPU reproduction or replacement image. Until then, existing images,
FINAL, renderer, camera, frontier, and job claims remain unchanged.
