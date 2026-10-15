# gCube settings after separate GPU deployment authorization

This task does not redeploy #5373 or start paid work. Use only the new unique tag/digest from the final report; preserve the previous image reference for rollback.

1. Keep Dropbox mounted at `/world-storage`. UID 1000 must be able to create a new export namespace there. Existing `rtx-gpu-package-v1` contents and metadata need not be repaired or removed. The image never changes their permissions/ownership.
2. Preserve the image default root entry so the original bootstrap can drop to UID 1000 and the diagnostic parent can clear supplementary groups. Do not add a runAsUser override or inherited supplementary groups for this diagnostic-service check. The service itself still runs as UID/GID 1000 with no supplementary groups. A forced nonroot process cannot clear inherited groups and the existing guard correctly refuses the service. If the platform mandates such a conflicting identity, preserve the refusal and inspect the exported safe logs; resolve the platform identity policy before expecting diagnostic keepalive.

Leave command override empty. The new image supplies its isolated storage entrypoint. Do not select the one-shot `--check-storage` as the container's long-running command.
3. Keep diagnostic port 8000 and set:

```text
WORLD_ENGINE_STARTUP_MODE=diagnostic
WORLD_ENGINE_DIAGNOSTIC_PORT=8000
WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS=900
NVIDIA_DRIVER_CAPABILITIES=graphics,utility
WORLD_ENGINE_RENDER_MODE=gpu-required
```

4. If platform probes are configurable, liveness uses `/healthz` with startup grace at least 300 seconds. `/readyz` remains 503 in diagnostic mode. Confirm the actual provider policy rather than treating diagnostic liveness as GPU readiness. An Always policy can restart after the 900-second TTL.
5. Inspect stdout/stderr and `/diagnostics`: storage preflight facts must show private local capability verification and separate shared-export readback; then SOURCE_INTEGRITY and DEPENDENCY completion. Export root and legacy candidate numeric UID/GID/mode are measured read-only. If shared write fails, do not bypass it; supply a verified writable approved mount/path through the provider configuration before retrying.
6. A CPU environment should stop at GPU_HARDWARE_UNAVAILABLE after storage/source/dependencies pass. On the real RTX allocation inspect the **next actual code**, NVIDIA device/driver, EGL/Vulkan, Chromium physical WebGL2 draw/readPixels and VRAM/shared memory. Keep at least the original recommended 2 GiB /dev/shm and verify actual capacity; do not substitute SwiftShader or a mock admission.
7. New sanitized logs appear under `/world-storage/world-engine-export-*/`. A successful actual native capture exports to a new `capture-*/public-review/` containing only MP4/PNG/SHA256SUMS. EXPORT_COMPLETE.json is beside that public directory, outside the public review allowlist. No raw private diagnostics or source is copied there.
8. Download the exported files through the provider's authorized storage path, verify each downloaded SHA-256 against the source/receipt, and confirm the remote upload completed. Mounted-view readback alone is not durable backup or external retrieval. Do not stop the workload before this external verification. Private local frames/admission/logs require a separately verified private retrieval channel if needed; they are not automatically copied to the shared destination.

After reviewing a real diagnostic execution, normal native health/render may be tested only as a separately authorized operation. The unchanged explicit --render-65422 path performs native GPU admission and retains original capture protection, then requires verified public export. This package makes no automatic renderer/API/FINAL change.
