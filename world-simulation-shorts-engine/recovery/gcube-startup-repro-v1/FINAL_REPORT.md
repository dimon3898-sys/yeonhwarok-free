# gCube #5373 — CPU startup reproduction result

2026-10-15 (Asia/Seoul)

**CRASH_CAUSE_UNCONFIRMED**

The immutable image's CPU startup cases were executed on a free public standard
GitHub `ubuntu-24.04` runner. All eight cases matched their expected negative
outcomes. This does not establish the actual cause of Workload #5373, restore
its service, or validate an NVIDIA GPU. Its actual terminated exit code and
previous stdout/stderr have not been obtained.

## Actual results and failure locations

| Case | Actual exit | Observed boundary |
|---|---:|---|
| Default ENTRYPOINT/CMD, no volume | 2 | `GPU_HARDWARE_UNAVAILABLE` |
| No volume, `--check` | 2 | `GPU_HARDWARE_UNAVAILABLE` |
| Writable UID 1000 / 0700 mount | 2 | `GPU_HARDWARE_UNAVAILABLE` |
| Foreign-owned private subdirectory, root startup | 2 | Root changed this new disposable subdirectory from UID/GID 42 to 1000, retained 0700, then GPU absence |
| Correct private storage, `chown` denied mock | 1 | `RTX_BOOTSTRAP_FAILED`, injected EPERM at storage metadata operation |
| Correct private storage, `chmod` denied mock | 1 | `RTX_BOOTSTRAP_FAILED`, injected EPERM at storage metadata operation |
| Actual read-only bind mount | 1 | `RTX_BOOTSTRAP_FAILED: [Errno 30] Read-only file system` |
| Foreign-owned private storage, non-root UID 1000 startup | 1 | `runtime/storage directory must be private and engine-owned` |

The first four cases reached the GPU device query after bootstrap, source
contract and mandatory native dependency checks. Their exit 2 is expected on a
CPU-only runner, not an application defect or successful GPU startup.

The metadata-denial cases demonstrate the exact early failure condition:
`bootstrap._directory()` unconditionally calls root `chown`/`chmod`, even when
storage already has UID 1000 and mode 0700. EPERM aborts before source,
dependency and GPU checks. They intentionally inject only the named operation on
`/world-storage/rtx-gpu-package-v1`; they do not emulate a real Dropbox PVC.

The read-only and foreign-owner tests are genuine Linux bind-mount/account
conditions on a free runner. They do not prove those conditions existed on gCube.
No case timed out, was OOM killed, or rendered a frame. Exit codes, complete
bounded stdout/stderr, byte hashes, failure stages and mount metadata are saved
in `runs/38673379956-1/`. All 137 listed evidence SHA-256 entries were verified
after retrieval from Git.

## Image comparison: verified facts and limits

| Field | Prior audited image `7e32…31e` | Failing-image baseline `82a4…16a37` |
|---|---|---|
| Platform | linux/amd64 | linux/amd64 |
| Initial user | root | root |
| ENTRYPOINT | `tini -g -- python /opt/gate1-static/server.py` | `tini -g -- /usr/bin/python3 /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/bootstrap.py` |
| CMD | null | null |
| Verified config SHA | `242de322e668a763d8b79626f4876221293d37425757682184e475772a976989` | `1e784975dd022458c06f95fcd8804f1c6adc0ed0640db106e6e588f1049adb4a` |
| Later UID / startup gates | Old server bytes not inspected in this task | UID 1000 before source/native dependencies/GPU admission |

The prior manifest and small config JSON were anonymously retrieved and SHA
verified; no old image layers were downloaded. The new identity was checked
from the actual immutable image on Actions. The old entrypoint is a static-proof
server path; the repository's generic `deployment.gcube.start` is not proof of
what that exact old server does. The old image's application commit and binding
to the user's successful RTX 4080 SUPER workload remain unconfirmed.

The new path is runtime directory → storage directory → device groups →
setgid/setuid → XDG directories → staged source contract → mandatory native
dependencies → GPU launcher. Bootstrap preparation failures exit 1. GPU
admission failures exit 2; the health service starts only after admission.

NVIDIA graphics/utility injection, actual shared-memory allocation, device/group
access, driver versions, EGL/Vulkan initialization and Chromium WebGL2 draw on
#5373 remain untested. CPU absence does not establish a graphics-library fault.

## Changes, correction and protection

Production runtime fixes applied: **none**. The real workload cause is unknown,
so no speculative metadata suppression, relaxed permissions, GPU bypass or new
image was introduced. Later diagnostic persistence also uses chmod; changing
bootstrap alone would not certify an arbitrary chmod-incompatible filesystem.

Added only a diagnostic workflow and `gcube-startup-repro-v1/` helpers/evidence.
The mock probe is test-only and calls the unchanged bootstrap; it is not a
production entrypoint. Actual mounted private contents were excluded from the
published synthetic diagnostic record.

An initial diagnostic workflow configuration error was confirmed and corrected:
job-level `runner.temp` is not an allowed expression context. Run 38673236788
had no jobs/container executions. The evidence path was changed to a unique
`/tmp` path based on supported GitHub run-ID contexts. A focused context check
passed; corrected run 38673379956 succeeded in 41 seconds. This correction is
not a fix for #5373.

Against baseline `9034e18`, all changed paths belong to the new diagnostic
namespace or its workflow. FINAL, renderer, camera, frontier, ASTRA, old RTX
package and approved videos have zero changes. Existing 104 tests, build,
source/assets and dependency audits were reused rather than repeated.
Existing containers/images/cache/volumes/files were not deleted. Tests used
new disposable directories only. No GPU deployment, paid runner, registry
write, new image build/push, actual GPU admission or render occurred.

Secret Scan of the new diagnostic source/workflow/evidence uses pinned Gitleaks
8.24.3; the result is recorded separately in `SECRET_SCAN.json`. Runtime cases
receive no GitHub/gCube credentials and have no network access.

## Persistence

- Branch: `development/gcube-startup-repro-20261015`
- Initial diagnostic source: `b94b5cf`
- Corrected diagnostic source: `e25daeb`
- Actual CPU evidence: `1fdb38f354b1c60d5a06eb18c7e280759407f7b9`
- [Successful CPU run](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38673379956)
- Case/command records and raw streams: `runs/38673379956-1/`
- Machine result: `RESULT.json`
- New image tag/digest: **none**; existing image references remain unchanged.

## Required next evidence

Without restarting or redeploying a GPU, obtain retained #5373 records from
gCube's existing logs or provider support: previous container stdout/stderr,
terminated exit code/reason, initial runAs UID/GID, volume mount path and
read-only status, storage ownership/mode and metadata capability, environment
and shared-memory configuration. Never send tokens/passwords/private keys.
Also confirm the exact image/digest of the previously successful workload.

Only then can a matching failure stage be identified and an appropriately
limited runtime correction tested. The current state is **not ready for GPU
redeployment**. Stop here for user review; do not promote FINAL.
