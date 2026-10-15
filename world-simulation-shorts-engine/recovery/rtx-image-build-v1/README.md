# RTX image build and immutable GHCR publication

This additive orchestration reuses `recovery/rtx-gpu-package-v1/` unchanged.
It does not deploy gCube, execute the hardware launcher, render a scene, or
change ASTRA providers, renderer, camera, frontier, or Final baselines.

## Pinned inputs

- Package source: `2f9158ba2df2a9f58362fb0b17118b8dc19f705a`.
- CPU source: `a002d89492734bfa9d17b98145ee6cb9a3b366a2`.
- Frontier source: `45af879d7417abba58e9ebd59d8e6630a785ac28`.
- Source contract SHA-256: `5938d0f33168daae415d9573701cafe290bcdd9850a14f4cb61c966560640180`.
- Exactly 140 original files and 20 package files form the existing context.
- Existing dependency audit and 104-test report are reused. They are not rerun.

## Free builder and storage gate

The new workflow is `.github/workflows/rtx-gpu-image.yml`. It permits only the
named public repository and development branch on the standard GitHub-hosted
`ubuntu-24.04` runner. GitHub documents public standard runners as free:
https://github.com/github/docs/blob/main/content/billing/concepts/product-billing/github-actions.md

No larger runner, paid service, storage artifact upload, remote cache exporter,
or GPU service is configured. Runner availability and capacity are unverified
until its job actually starts. Each job requires at least 20 GiB free on the
Docker disk-backed filesystem. It never prunes images, cache, volumes or tools.
The local Codex vfs builder has about 1.87 GiB free and is not used for a build.

## Execution

Pushes affecting this new workflow or helper sources on the development branch
start one serialized run. Report-only commits do not start another run. An
authorized manual dispatch can also run it on this branch. The image tag is
`rtx4080s-2f9158b-<GitHub run ID>-<attempt>`; a rerun uses a new attempt tag.

1. Sparse checkout the helpers/contracts, retain commit ancestry, then select
   the exact existing manifest paths. No full media checkout or branch merge.
2. Check public/free runner, actual Docker filesystem and unique tag absence.
   An ambiguous registry response or already-existing tag stops execution.
3. Verify source/package bytes and unchanged protected paths; stage one fresh
   context. No authentication files enter that context.
4. Build the existing Dockerfile for `linux/amd64`. No secret build argument.
5. Override its GPU entrypoint. As UID 1000 with `--network=none`, verify source
   hashes, installed CPU dependencies/APIs, Playwright module loading and a tiny
   two-frame 16x16 CPU codec fixture. No Chromium page or GPU rendering is run.
6. Check image credential environment keys and known root credential paths;
   run pinned Gitleaks on actual copied application bytes. Credential values
   and private configuration contents are never printed or reported.
7. Use the repository-generated `GITHUB_TOKEN` with `packages: write` in an
   isolated, newly-created Docker auth directory. Recheck tag absence, push
   once, retain its actual digest, then verify remote manifest/config hashes.
8. On a fresh free runner, pull the immutable digest and compare the config
   digest, package source label and original staged source hashes again.
9. Save sanitized build/pull JSON evidence in this namespace on the development
   branch. Reports retain blocked states; unexecuted operations are not PASS.

Registry scope observations and a missing tag do not prove successful writing.
Only the actual push and verified registry presence establish publication.
There is no tag-reservation API; serialized workflow plus unique run/attempt
tags and an immediate pre-push check protect this workflow's writers.

## Permissions and blockers

The workflow needs repository Actions enabled, the ability to save its report
commit, and `packages: write` access to the existing
`dimon3898-sys/world-simulation-shorts-engine` GHCR package. An existing package
may require its owner to grant this repository Actions write access. Do not
change package visibility, use another account, or place tokens in this repo.

The managed cloud draft adds `api.github.com` without changing the existing
164 allowed hosts or credentials; it requires publication in environment
settings before direct API monitoring is available. Git HTTPS operation and
public GitHub HTML can be used for the currently authorized workflow launch
and evidence retrieval. A draft is not evidence of active API access.

If free runner disk space, authentication, dependencies, checkout protection,
Secret Scan, or push/pull verification fails, stop that phase and retain its
diagnostic result. Fix only an evidenced, safe orchestration issue before one
new attempt. Do not delete prior data or lower checks to make a run pass.

## gCube reference after success

Use only the actual verified reference recorded by the run:
`ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:<actual digest>`.
Reuse the existing package's `GCUBE_SETTINGS.md`, `GCUBE_EXECUTION.md` and
`GPU_HARDWARE_VALIDATION_TODO.md` without changing approved runtime settings.
Host NVIDIA drivers, actual GPU access, Chromium WebGL2 draw/readPixels and
video quality remain unverified until a separately authorized deployment.

## Required permanent files

All new executable helpers, focused tests, workflow and sanitized run evidence
are stored in Git. Build contexts, isolated auth, scanner extraction and
inspection containers are disposable CI artifacts; none is required for
reproduction. Required temp-only source/assets: zero. Isolated newly-created
auth files and the newly-created never-started inspection container are the
only explicit removals; prior caches/images/volumes/project files are retained.
