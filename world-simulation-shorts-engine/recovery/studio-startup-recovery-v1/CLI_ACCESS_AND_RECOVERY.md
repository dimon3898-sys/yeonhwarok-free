# Studio V1 workload 5373: authenticated log retrieval

## Observed result

The official gcube CLI 0.4.2 was installed in an isolated environment from the
previously preserved official wheel. Its SHA-256 matches the preserved official
PyPI metadata: `9aafcafdc84b129ff119b4f735c0d56f09ba6898667fa3d6713a5fb85d06d692`.

`gcube auth status` and `gcube config status` report no login. No
`GCUBE_ACCESS_TOKEN`, local `~/.gcube/config.yaml`, or managed gCube credential
binding was available. No actual Studio workload 5373 crash log was found in
the available checkout's docs/deliverables, the preserved Studio reports, or
matching workspace log filenames. A wider lazy historical-blob search timed
out and is not represented as an exhaustive repository search. No credential
values were displayed or committed.

Executed read-only commands:

| Command | CLI exit | Result |
|---|---:|---|
| `gcube --version` | 0 | gcube 0.4.2 |
| `gcube auth status` | 0 | Not logged in |
| `gcube config status` | 0 | Effective auth: not logged in |
| `gcube -o json workload describe 5373` | 1 | No token configured. Run: gcube auth login |
| `gcube workload logs 5373` | 1 | No token configured. Run: gcube auth login |
| `gcube -o json workload pods 5373` | 1 | No token configured. Run: gcube auth login |

These failures happen locally before the API request. **CLI exit 1 is not the
container exit code.** Current deployment state, first container error, and
actual container exit code remain unverified. No code defect or gCube crash
cause is established by these results.

## Exact safe continuation

1. In an authorized local interactive CLI environment, use the official
   `gcube auth login` browser flow. For this headless managed environment, supply
   the officially supported `GCUBE_ACCESS_TOKEN` through its approved Secret
   mechanism. Do not paste credentials into chat, Git, command arguments, or
   reports. `GCUBE_API_TOKEN`, `GCUBE_EMAIL`, and `GCUBE_WORKLOAD_SER` do not
   replace the official CLI access-token input.
2. Re-run the read-only `describe`, `pods`, and `logs` commands above. Capture
   raw responses privately: workload configuration may contain sensitive
   environment values. Do not publish raw `auth status` output after login:
   this CLI version prints a token prefix and an email address.
3. Extract only safe evidence: workload/image identity, pod/container status,
   first startup error code/time, and any terminated-container exit code. If
   the exit code is not present, leave it unverified.
4. Official CLI 0.4.2 streams logs only when workload state is `deploy` and pods
   are present. It supports `--pod` and `--container` selection, but has no
   `--previous` option. If the existing workload is stopped or the pod was
   removed, request retained logs and the previous terminated-container state
   from the gCube console/support. Do not start or redeploy a paid GPU merely
   to retrieve old logs.
5. Change Studio code only if actual evidence establishes a code defect.
   Required authentication/origin/GPU checks must remain in force.

Official references reused, without repeating the platform audit:

- https://pypi.org/project/gcube-cli/0.4.2/
- https://github.com/data-alliance/gcube-cli
- https://data-alliance.github.io/gai-platform-docs/
- https://gcube.ai/ko/demand/user/access-token
- Existing repository evidence:
  `world-simulation-shorts-engine/docs/evidence/gcube_official_sources_v001/`
  (`cli_pypi.md`, official wheel, and extracted `commands/workload.py`).

## Source findings, distinct from the actual workload

The approved image uses `tini -g -- /usr/bin/python3 -B
/opt/world-engine-production-studio/bootstrap.py` and `CMD []`. An empty gCube
Command is consistent with that image configuration.

| Input | Source-defined behavior |
|---|---|
| `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN` | Required HTTPS origin; missing input emits `STUDIO_HTTPS_ORIGIN_REQUIRED`, bootstrap exit 1 |
| `WORLD_ENGINE_STUDIO_OWNER_CODE` | Required for the first start unless a valid existing private owner file is present; missing input emits `STUDIO_OWNER_CONFIGURATION_REQUIRED`, bootstrap exit 1 |
| `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON` | Optional at startup; absence blocks production Start later. Invalid supplied JSON/policy may fail startup |
| `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` | Controller requires raw `sha256:<64 lowercase hex>`, not a tag/full image URL; invalid value emits `STUDIO_IMAGE_DIGEST_REQUIRED`, server exit 2 |
| Legacy startup mode | Preserved by bootstrap; operations documentation requires `normal` and render mode `gpu-required` |

These are conditional source facts, not evidence that the actual workload had
any particular environment value. Missing policy alone must not be reported
as the actual CrashLoopBackOff cause. No production source fix or replacement
image is justified without a confirmed defect.
