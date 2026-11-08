# Native runtime integration candidate — not installed

This is a narrow NVIDIA variant of the recovered official presentation runtime, derived from its exact SHA256. The existing engine's factory, candidate lifecycle, camera, source/height policy, labels and async frame preparation remain intact. NVIDIA/Vulkan identity and the existing three-draw stability receipt replace the software-only gate. No browser, encoder, job runner or new video generator is introduced.

Two patches add awaited optional frame preparation before the native stability draw and each ordinary draw. A preparation failure stops before the next draw/readback. Native jobs without that hook keep their call order.

Validation: five new source/ordering tests and two JavaScript syntax checks. Sequencing tests use synthetic context and pixel fixtures; they are not GPU or browser evidence. The existing13 boundary tests and all prior CPU/source PASS were preserved without rerun.

Do not install these files as replacements for the successful image. Remaining implementation: sealed controller/worker transport, per-segment candidate server sessions, exact new resource/source closure pins, diagnostics integration for the candidate runtime, and deployment-destination qualification. Then perform the changed-scope screen check on an allowed ordinary-sandbox CPU host. AF_UNIX EPERM must not be bypassed. The frozen original variant-manifest checks must remain intact on the default path; a qualified candidate closure needs a separate explicit selection.

No image build, registry activation, GPU execution or deployment readiness is claimed.
