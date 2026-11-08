# Native NVIDIA / candidate timeline boundary proposal

Status: isolated proposal; not installed or deployment-approved.

The recovered Dot adapter routes every300-frame input through a two-chunk software timeline. The existing NVIDIA controller overrides the native preparation hooks, which that timeline bypasses; it also does not transport candidate authority to its worker. Replacing the baseline adapter directly can therefore break the existing native10-second route or silently omit candidate effects.

These two proposed edits add a server-only mode selection, preserve legacy constructor compatibility, and fail explicitly if an unsupported candidate is configured or returned. The default candidate software lane remains separate. This is a compatibility prerequisite, **not** the missing NVIDIA candidate implementation.

Focused routing tests:13 PASS. They execute the changed method ASTs with compiler/I/O seams stubbed. They do not prove real source admission, browser appearance, GPU execution, or full Studio behavior. No existing PASS suite was rerun.

The baseline repository renderer/runtime must stay on disk. Browser overlays belong in the separately pinned private resource store. Do not apply this directory as an image overlay, activate a recovered registry, or reuse CPU fixtures as production inputs. Destination records and source/browser closure must be regenerated through the official issuer before subsequent validation.

CPU screen validation remains blocked by AF_UNIX EPERM on this host. Do not repeat that browser failure or disable the sandbox. No image was built and no paid GPU was started.
