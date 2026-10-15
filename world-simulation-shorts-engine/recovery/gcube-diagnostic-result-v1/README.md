# Existing GPU diagnostic result recovery

This package fixes forwarding of a successful native GPU result into the existing `/diagnostics` response. It also provides a read-only helper for an **already-running old storage-fix container**. No GPU redeployment, GPU initialization, renderer invocation, new endpoint or paid action is part of the recovery command below.

The user reported `DIAGNOSTIC_ONLY` for #5373. The live endpoint URL, full response, actual running image identity and local admission files have not been supplied or accessed from this CPU environment. Therefore the original GPU result has not yet been retrieved here. Local and CI synthetic tests are not gCube hardware proof.

## Why DIAGNOSTIC_ONLY can appear

At `d1f6041`, successful native `admit_gpu` writes `admission_safe.json` and `admission_private.json` before returning its successful result. The old diagnostic worker discarded that result and produced a generic `DIAGNOSTIC_ONLY`, `exitCode: 0` record. This was a confirmed forwarding defect. The outer `gpuRenderingVerified: false` and `renderAllowed: false` are intentional diagnostic-mode locks and remain unchanged.

Failure paths already carry their first stage and error code. Do not replace a failed current record with an older successful admission. A service that later reaches its configured TTL can exit nonzero even after successful diagnostic checks; that exit alone is not a new GPU failure.

## Recover from the currently running old container without redeployment

1. Open the terminal/exec facility for the **existing #5373 container**, if gCube provides one. This repository has not verified access to that facility. Do not restart, replace or deploy a GPU merely to obtain a shell. A stopped or replaced container may already have lost its private local records.
2. Keep its existing entrypoint, environment, UID, storage permissions and startup mode unchanged. The reader can run as the current root user or UID 1000; it does not change identity. Inspected private data must still have UID/GID 1000 and private directory/file modes 0700/0600. A different UID may safely receive a permission-denied result.
3. In that existing container, run the following block. It uses Python's standard library; no install, sudo, token or curl is required. The helper is pinned to an immutable source commit, its SHA-256 is checked **before any helper code executes**, and it is saved only in a freshly created private temporary directory.

```sh
(
set -eu
READER_FILE="$(python3 - <<'PY'
import hashlib
from pathlib import Path
import tempfile
import urllib.request

url = "https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/b5b83c4ed93151ee31c94bff09b7668e1789043a/world-simulation-shorts-engine/recovery/gcube-diagnostic-result-v1/recover_existing.py"
expected = "7a12a58f130a9cdc7c50646a14f5a92cf06030dd0a3f4912f7480988ea8ba039"
try:
    with urllib.request.urlopen(url, timeout=30) as response:
        if response.status != 200:
            raise ValueError()
        body = response.read(128 * 1024 + 1)
    if len(body) > 128 * 1024 or hashlib.sha256(body).hexdigest() != expected:
        raise ValueError()
except Exception:
    raise SystemExit("PINNED_HELPER_DOWNLOAD_OR_SHA_FAILED; helper not executed")
directory = Path(tempfile.mkdtemp(prefix="world-engine-existing-reader-", dir="/tmp"))
target = directory / "recover_existing.py"
with target.open("xb") as stream:
    stream.write(body)
target.chmod(0o600)
print(target)
PY
)"
python3 -B "$READER_FILE"
)
```

The helper makes one bounded request to the fixed `http://127.0.0.1:8000/diagnostics`, with proxies and redirects disabled. It cannot query a custom port or a remote URL. If that service has expired, port 8000 is not the existing configured port, GitHub download is blocked, or terminal access is unavailable, stop this procedure and report that access limitation. Do not restart the workload or change its port to make this command pass.

The reader checks the private export receipt and its recorded root/directory inode identities, matches the exact current safe startup response to its exported safe record, then reads only the corresponding session's `admission_safe.json`. Exactly one native admission must match within the bounded 240-second startup window. There is no newest-file fallback. The helper does **not** read `admission_private.json`, initialize GPU, call a renderer, change ownership/modes or write diagnostic records. The download block creates only the fresh helper file above.

## Interpret the result and act

| Result | Meaning and next action |
| --- | --- |
| `RECOVERED_SAFE_ADMISSION` | A unique existing safe native admission was correlated to the current diagnostic response. Share this allowlisted JSON, including its SHA, timestamps, native verification scope, model, driver, memory and source result. It proves recovery of stored evidence; the helper did not rerun hardware checks, render 65422 or certify current visual quality. |
| `TEST_ONLY` | A Python-only fixture seam was used. This cannot establish physical GPU execution. The production command has no fixture/path flags. |
| `UNVERIFIED` + `CURRENT_RECORD_NOT_RECOVERABLE` | The current response is not the exact old successful diagnostic-only shape. Retrieve the existing `/diagnostics` response and preserve its first failure stage/code; do not substitute another admission. |
| `UNVERIFIED` + `NATIVE_ADMISSION_STALE` | The stored admission is outside the current startup window. Preserve the result and current safe response; do not use it as a current admission. |
| `UNVERIFIED` + `NATIVE_ADMISSION_AMBIGUOUS_OR_MISSING` or `CURRENT_RECORD_AMBIGUOUS` | No unique correlation is available. Do not choose the newest record. Preserve the safe response and this reason for review. |
| `UNVERIFIED` + `RECEIPT_INVALID`, a private-path/file validation code, or `errnoName` | Safe receipt/path access could not be established. Report the allowlisted code/errno. Do not chmod/chown, copy private admissions into shared storage, or bypass the checks. |
| `UNVERIFIED` + `EXISTING_EVIDENCE_UNVERIFIED` | A non-allowlisted access/format/runtime error prevented recovery. Exception text, raw paths and secrets remain withheld. Report the safe JSON and whether terminal, download and loopback access were available. |

Other fixed reason codes explicitly identify bounded-record, timestamp, native metadata or source/shared-memory validation failures. All unverified results have `gpuRenderingVerified: false`, `renderAllowed: false` and `actualHardwareRerun: false`. The command exits 0 only when existing evidence was recovered, and exits 2 when unverified; neither authorizes rendering. In a recovered summary, the outer GPU boolean deliberately remains false: the recorded native scope describes prior admission, while this command performed no new hardware test.

Share only the helper's safe JSON and the existing safe `/diagnostics` response. Do not paste credentials, GPU UUIDs, environment dumps, `admission_private.json`, a whole diagnostics archive or private source files. The existing response can be viewed locally without changing the service:

```sh
python3 - <<'PY'
import importlib.util
import json
import sys
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError()

try:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open("http://127.0.0.1:8000/diagnostics", timeout=3) as response:
        if response.status != 200:
            raise ValueError()
        body = response.read(128 * 1024 + 1)
    if len(body) > 128 * 1024:
        raise ValueError()
    value = json.loads(body)
    if not isinstance(value, dict) or value.get("schema") != "WORLD_ENGINE_STARTUP_DIAGNOSTIC_V1":
        raise ValueError()
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("existing_safe_records", "/opt/world-engine-startup-diagnostics/records.py")
    records = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(records)
    print(json.dumps(records.safe_record(value), sort_keys=True, allow_nan=False))
except Exception:
    raise SystemExit("EXISTING_LOOPBACK_DIAGNOSTICS_UNAVAILABLE; no restart performed")
PY
```

This viewer relies on the identity of the existing trusted diagnostic service. It is not a substitute for the helper's receipt and admission correlation.

## New image behavior

After a separately approved future deployment, the fixed existing `/diagnostics` endpoint carries sanitized native success details under `safeDiagnostics.gpu`, including staged NVIDIA/WebGL diagnostics and draw results. Diagnostic readiness remains 503, rendering remains blocked, and the first existing failure remains authoritative. Normal native GPU admission and the renderer API are preserved.

The helper is already packaged at the following path in the new result image; no network download is needed there:

```sh
python3 -B /opt/world-engine-diagnostic-result/recover_existing.py
```

The recovery helper requires the successful diagnostic-only outer envelope and the same strict receipt/admission correlation in either image. If the new endpoint already carries `safeDiagnostics.gpu`, read that existing safe response directly; recovery is unnecessary. A helper `CURRENT_RECORD_NOT_RECOVERABLE` means the outer envelope did not match and is not evidence of GPU failure by itself. Use the actual image reference and digest recorded in the verified build/pull result, not an assumed tag. No gCube deployment has been executed by this work.

## Remaining boundaries

Actual #5373 image identity, current response, admission-file survival and hardware outcome remain unverified until retrieved from the existing container. GPU device/driver delivery, EGL/Vulkan, physical WebGL2 draw/readPixels, VRAM/shared memory, provider health/restart policy, Dropbox remote durability, external download SHA and 65422 rendering cannot be certified by these CPU tests. A mounted-view match is not an external backup. Do not enable rendering or change GPU settings based only on `DIAGNOSTIC_ONLY` or a recovery helper exit 0.
