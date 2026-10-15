# gCube diagnostic startup settings — deployment not performed

Use only after separate user authorization for a GPU allocation. This package
does not deploy, restart or stop Workload #5373 or any paid workload.

Use the new unique tag and immutable digest recorded in the completed image
report. The older tags/digests remain unchanged. gCube's documented registry UI
format is `ghcr.io/owner/repository:tag`; actual digest UI support is unconfirmed.

For the first diagnostic execution, leave the command override empty and set:

```text
WORLD_ENGINE_STARTUP_MODE=diagnostic
WORLD_ENGINE_DIAGNOSTIC_PORT=8000
WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS=900
NVIDIA_DRIVER_CAPABILITIES=graphics,utility
WORLD_ENGINE_RENDER_MODE=gpu-required
```

The new mode is explicit. Default startup remains `normal`. Diagnostic mode
never runs `--render-65422`, never dispatches the existing render function, and
never reports GPU readiness. Do not combine it with a render command.

Keep the original image's staged source tree and its default output path:
`/world-storage/rtx-gpu-package-v1`. The diagnostic layer does not change
approved source files, storage ownership rules, GPU admission or render styles.
It records a storage refusal instead of pretending that the mounted filesystem
is usable. It does not repair ownership/mode or replace Dropbox with a different
storage provider. Keep the original GPU and mount settings when investigating
their actual failure, rather than silently changing the experiment.

## What to inspect

- Container stdout/stderr: fixed startup stage, error code, termination reason,
  UTC timestamp and allowlisted diagnostic facts.
- `GET /healthz`: HTTP 200 only means the diagnostic service is alive. Inspect
  `startupMode`, `status`, `stage`, `errorCode`, `gpuRenderingVerified:false` and
  `renderAllowed:false`. It is not a GPU success or rendering admission.
- `GET /readyz`: HTTP 503 in diagnostic mode, including after a successful
  diagnostic-only hardware check. Rendering remains disabled.
- `GET /diagnostics`: the same sanitized diagnostic record; no credentials,
  original exception text, private source tree or file-serving API.
- Render/job/command routes do not exist. Non-GET methods are rejected.

If safe storage is available, private JSON records are written beneath
`/world-storage/rtx-gpu-package-v1/startup-diagnostics/`. Otherwise an exclusively
created 0700 directory under `/tmp/world-engine-startup-diagnostics-*` is tried.
The fallback is **not persistent** and must not be treated as a backup. Both
failing still leaves structured stdout/stderr and, if safe privilege transition
succeeds, the read-only diagnostic response.

## Healthcheck and restart limits

The new Docker HEALTHCHECK is mode aware. In normal mode it requires the
unchanged native GPU verification response. In diagnostic mode it validates the
explicit diagnostic liveness response while retaining failed readiness and
disabled rendering. It does not unconditionally return exit 0.

The isolated startup worker is bounded to 240 seconds. Allow at least 300 seconds
of startup grace before a platform liveness timeout. The diagnostic server runs
for at most the configured TTL (1–900 seconds) and then preserves a nonzero
failure exit; an operator should collect the record and stop through approved
procedures before the TTL expires. A platform `Always` restart policy can restart
the process after TTL expiry or an external kill. This image does not modify
that platform policy or promise indefinite keepalive.

If gCube permits separate probes, diagnostic **liveness** must target `/healthz`,
not `/readyz`. Readiness must not be repurposed as a successful GPU flag. If the
provider hardcodes a conflicting probe/path or cannot allow the startup grace,
stop and resolve the platform setting before expecting this mode to stay alive.
Do not weaken GPU checks or make readiness return 200 to satisfy the provider.

Actual #5373 pod specification, health/restart policy, driver/device injection,
NVIDIA memory, EGL/Vulkan and Chromium WebGL2 remain unverified. CPU container
tests validate the image contract, not those gCube platform settings. The old
workload's real exit code and previous logs are still needed to identify its
historical root cause.

## Normal execution after diagnostic review

`WORLD_ENGINE_STARTUP_MODE=normal` retains the existing fail-closed behavior:
bootstrap/source/dependency failure exits 1; GPU admission failure exits 2;
normal GPU health or rendering is available only after native admission.
Actual hardware rendering remains a separately authorized operation.
