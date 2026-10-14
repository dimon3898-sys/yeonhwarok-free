# Remaining checks on authorized real hardware

None of the following is asserted PASS by CPU tests or SwiftShader.

1. Build the new configuration on a suitable CPU builder, verify its native dependency/source reports, and record its real registry digest after an authorized push. The previous GHCR digest is prior-image provenance, not the new image identity.
2. On gCube, verify the selected allocation really is RTX 4080 SUPER 16 GB (or the allowed alternatives), driver/library injection and loadability, inherited device permissions after UID drop, and provider graphics/utility capabilities. Do not install a host NVIDIA driver in the image.
3. Verify Chromium headless WebGL2, unmasked NVIDIA identity, actual colored draw/readPixels, selected Vulkan/EGL profile, and no software fallback. The package must fail closed if these checks fail.
4. Verify at least 1 GiB available `/dev/shm` (2 GiB configured), sufficient RAM/disk, VRAM/free reserve, and the memory watchdog on a real run. Polling is not a hard driver reservation.
5. Verify the dedicated persistent output mount is writable as the engine UID, supports atomic rename, survives restart/redeployment and has adequate capacity. An unmounted container directory is not durable storage.
6. Run the isolated existing 5-second scene only after authorization. Check actual hardware diagnostics, source hashes, 1080×1920/30 fps/150 silent frames, geometry/timing/API protection, mobile visual quality and comparison with the preserved 65422 proof. GPU differences must not be disguised as BIT_EXACT.
7. If public review is requested later, publish only the original new MP4, PNG and SHA256SUMS. Verify HTTP 200 and downloaded SHA equality. This package health endpoint is not a file server, remote shell or render API.

ASTRA providers, acquisition plans, cache, Scene preparation and neutral export are shipped unchanged and available for CPU execution. New texture packing/upload, masked height/shoreline handling, surface/bathymetry materials, globe/LOD behavior and full camera coverage remain the separate existing ASTRA `GPU_INTEGRATION_TODO.md` scope. Regional samples and missing production coast masks are not padded or silently replaced. This task does not duplicate or solve that visual integration by modifying the approved renderer.
