# Studio V1 immutable-image CPU startup reproduction

This independent diagnostic lane runs the published Studio image by immutable
digest. It does not modify the image, production startup code, source manifests,
renderer, GPU admission or any existing data. It does not build or push images.

The workflow requires the public repository and a standard GitHub-hosted Ubuntu
24.04 runner, an overlay Docker driver and at least 20 GiB available before pull.
The local vfs Docker daemon is intentionally not used because its layer-copy
storage demand cannot be established as safe within the local disk budget.

The default-entrypoint cases are actual isolated container starts:

| Synthetic input | Expected first recorded error | Expected container exit |
| --- | --- | --- |
| No Studio environment | `STUDIO_HTTPS_ORIGIN_REQUIRED` | 1 |
| Test-only valid origin, no owner | `STUDIO_OWNER_CONFIGURATION_REQUIRED` | 1 |
| Only unprefixed `PUBLIC_ORIGIN`, `OWNER_CODE`, `IMAGE_DIGEST` | `STUDIO_HTTPS_ORIGIN_REQUIRED` | 1 |

A separate probe imports the installed, unmodified `bootstrap.py` and invokes
only `prepare_configuration` with a test-only origin and owner, without operator
policy. Its expected exit is 0. That result tests optional configuration handling;
it is not successful service startup, GPU admission or permission to render.

No real credentials are used. Containers have no network and no GPU device.
No test value is written to gCube or proposed as production configuration.
Only whitelisted JSON status and error-code fields are published. Original log
byte counts and SHA-256 values are recorded; raw logs and environment are not
published. No existing Docker object is removed or altered.

Run through `studio-startup-recovery-cpu.yml` on the diagnostic development
branch. `results.json` records actual Docker/container exits and is accompanied
by `SHA256SUMS`. A successful synthetic reproduction does not establish which
error occurred in Workload #5373; authenticated official workload logs remain
necessary for that conclusion.
