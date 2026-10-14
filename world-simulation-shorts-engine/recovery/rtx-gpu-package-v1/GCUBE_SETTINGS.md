# gCube workload settings

Preparation has not deployed, pushed, started or billed a gCube workload.
The new image is not built and has no new image digest.

Select one provider-allocated RTX4080 SUPER in the 16 GiB VRAM class. The launcher
also admits its explicitly supported RTX4090 and RTX5090 models. Provider
graphics/utility NVIDIA userspace injection and device permissions are required.
Preserve the provider's device selection. No kernel driver or CUDA/NVENC toolkit
installation is part of this package.

Use 8 GiB memory, 2 GiB shared memory and a persistent mount at /world-storage.
Bootstrap makes only /world-storage/rtx-gpu-package-v1 engine-owned. Existing
volume contents are untouched. Port 8000 is the health service. Leave command
override empty. Set:

    NVIDIA_DRIVER_CAPABILITIES=graphics,utility
    WORLD_ENGINE_RENDER_MODE=gpu-required
    RTX_STORAGE_ROOT=/world-storage/rtx-gpu-package-v1

Leave WORLD_ENGINE_GPU_PROFILE unset for existing Vulkan then EGL selection.
An explicit vulkan or egl setting selects that profile. Bootstrap preserves
provider device groups, creates private runtime directories, drops to engine
UID 1000, checks staged source bytes and CPU dependencies, then invokes the new
launcher. Admission checks GPU identity, memory, shared memory and an actual
native draw. Failure cannot become CPU success.

Default startup performs admission and serves health only. It does not render
a proof automatically. The explicit launcher render mode is required.
ASTRA CPU artifacts are packaged for preparation and receive no new GPU
material/texture layout here. Protected renderer, camera, glow and FINAL bytes
remain the original source bytes.

compose.example.yml is a configuration example. Starting it performs GPU
admission; preparation does not start it. Replace its UNBUILT image reference
only after a verified build. Known downloads are approximately 145 MB native base,
80 MB Node builder, 144 MB Chrome, plus Ubuntu runtime packages/npm dependencies.
Staged source is approximately 70 MB. These are input sizes, not measured final
image size or peak RAM/VRAM.
