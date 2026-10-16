# Production V3 additive image contract

The image starts from immutable V2 digest
`sha256:5f17537fa8e5387de39ed8999e4c8d7ce2fe8a3593a71a5a3c1ae033f22dd014`.
Its source is `311a92137d00ba88220c1caa243c9ff0389e4121`; its exact
`UNIVERSAL_FILES.json` SHA is
`982cf2c0a5f435afe936605c0aeb76cbf40b6990da41d27c0ea0bd5ef22eb756`.
The recorded 168 V2 tests are reused, rather than rerun as new V3 results.

`PARENT_CLOSURE.json` records the 86 inherited extension files. Along with the
original 160-file receipt and its two inventory metadata files, these describe
all 248 parent files. The original source auditor checks their unchanged bytes
and ownership together with the explicit new extension. It rejects unexpected
files instead of hiding the new namespace from the inventory walk.

The Docker build context contains only `Dockerfile` and `production/` with the
explicit runtime, explicit software probe, and generated `PRODUCTION_FILES.json`.
It does not copy or regenerate any parent file, source manifest, cache, claim,
renderer, or dependency. The parent namespace, entrypoint, command, healthcheck,
ports, and environment remain inherited. There is no package-manager install.
The new namespace must be absent before `COPY`; aliases are created only after
their absence is checked.

`source_manifest.verify_sources(package_root=Path('/opt/rtx-package'),
require_staged=True)` is the production integrity entrypoint. The CLI is
`source_manifest.py --verify-extension`. CPU source-only checking is explicitly
marked `testOnly` and requires `--source-only`; it is not hardware admission.
The parent verifier is imported only after its pinned bytes and closure pass.

The new workflow uses only the standard public `ubuntu-24.04` runner, requires
20 GiB of available build space, and preserves existing images and caches.
The branch/path trigger is restricted to this new namespace and its new workflow.
The owner stages and pushes the workflow only after reviewing the connected
runtime checkpoint. The unique tag is
`production-v3-e09be5d-<GitHub run ID>-<attempt>`; existing tags cannot be reused.

Required new gates are focused tests, actual connected Chromium/SwiftShader
draw/readPixels before the build and inside the built image, strict inventory,
unchanged default Secret Scan with zero findings, a unique-tag push, and an
independent runner pull by immutable digest. Source records are bounded and
append-only. A software proof never certifies NVIDIA execution, an 80-second
MP4, historical data beyond the supplied source evidence, external Dropbox
delivery, video quality, cost, or the 60-minute production target.

The production CLI alias is `/opt/world-engine-production-v3`. New private
state is stored in `/var/lib/world-engine-private/engine/universal-production-v3`
with UID/GID 1000 and mode 0700. Existing V2 state is not reset. No paid GPU
deployment or gCube control-plane call belongs to this build workflow.
