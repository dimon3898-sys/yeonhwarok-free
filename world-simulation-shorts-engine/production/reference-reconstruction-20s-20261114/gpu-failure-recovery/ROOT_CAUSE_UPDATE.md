# Root-cause update — EGL recovery integration

**ROOT_CAUSE_UNCONFIRMED / BLOCKED.** The new audit narrows the gap to two boundaries: legacy GPU admission → Studio Controller, and Controller → Worker environment filtering.

Confirmed from the pinned current code and new CPU investigation:

1. `prepare_graphics_runtime()` is present in the published image and called by the separate legacy admission child before its own Chromium probe.
2. Its returned selectors are applied only to that child's copied environment. Studio starts independently first; there is no selector transfer to Controller.
3. `_runtime_environment()` drops `__EGL_VENDOR_LIBRARY_FILENAMES` and `VK_DRIVER_FILES` even when valid generated paths are supplied. It retains `VK_ICD_FILENAMES` but performs no path validation itself.
4. The helper's intended parent ownership/modes permit UID1000 reads. This was observed only in a new CPU fixture, not in the stopped container.

The new user terminal evidence confirms default NVIDIA EGL JSON absence and an unsuccessful manual workaround on a different pod. It does not inspect the helper's `/run/world-engine` output, prove automatic generation, or reproduce formal UID1000/sandboxed Worker conditions. Libraries listed by `ldconfig` are not proof of successful fixed-symbol dlopen. Original `graphicsPreparation` is unavailable.

The loss mechanism is confirmed at code level; it is **not** sufficient to classify the original GPU failure as RECURRENCE_CONFIRMED or NEW_DEFECT_CONFIRMED. Old native successes with the same filter remain relevant: nodes with usable defaults can work without generated selectors. The failed manual test also prevents claiming that adding EGL/Vulkan variables alone resolves the issue.

Production edit gate: **not met**. No production source, generated runtime, manifest, startup pin or image changed. No broad forwarding of arbitrary descriptor paths. No GPU start or Studio render.

Recorded artifacts: `EGL_RUNTIME_PATH_AUDIT.md`, `ENV_PROPAGATION_AUDIT.json`, new bounded `egl-runtime-audit/ENV_PROPAGATION_PROBE.json`, and screenshot provenance in `egl-runtime-audit/USER_TERMINAL_EVIDENCE.json`. Existing PASS suites are preserved. The next step is obtaining existing same-pod automatic-generation/selector evidence if retained; otherwise keep BLOCKED without a paid retry.
