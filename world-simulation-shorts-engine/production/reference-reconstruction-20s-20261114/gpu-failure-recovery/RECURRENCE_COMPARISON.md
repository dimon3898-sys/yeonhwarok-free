# Exact-job comparison — history20 failure

Classification: **ROOT_CAUSE_UNCONFIRMED**. The WebGL2 initialization symptom has occurred before; the current native root cause is not established.

- Current job: `studio-aa674e471413a268fb2f8da56e66535c`, node `wnb247afd4`, pod `dep5373-76bc6dcb67-kw8p4`. Runtime import completed, then `UP2_WEBGL2_REQUIRED` at `WEBGL_CONTEXT`; 0/600 frames. Native exported facts include `EGL_NOT_INITIALIZED` / `eglInitialize`.
- On 2026-11-02 the provider reported missing EGL vendor configuration on **another node**, `wnc6bc6433`. The preserved provider reply is user-supplied. After provider remediation, the unchanged image created a native NVIDIA WebGL2 context. That proves the earlier repair on that node, not coverage of the present node.
- An existing actual capture, `studio-06ff7116b2bb6c464a64c1a576f3faf0`, completed 300 native frames with driver `580.126.09`, the same recorded browser arguments and graphics-environment facts. Its later artifact-reader issue is separate. The driver version and `NVIDIA_VISIBLE_DEVICES` selection class alone do not prove the current root cause.
- Launcher construction and capture environment allowlist are byte-identical in the compared function scope to commit `f276f19`. No speculative flag or environment changes were made.

| Earlier failure | Current evidence and relationship |
|---|---|
| Incomplete historical/timeline input | This job passed admission and reached runtime import. No such inner error was exported. |
| Worker publication race / stale worker | Existing actual-image admission records the repaired Worker hash and publication fix; the failed job's child ran. |
| Missing modules, generated/source mismatch | Existing image closure is reused. This job completed runtime import. No missing-module or manifest error was exported. |
| Startup manifest pin mismatch | Different stage. Browser launched; existing image startup checks remain valid within their scope. |
| JSON_SIZE_INVALID after capture | Different stage. Earlier incident completed 300 frames; large-reader protection is present in the published image evidence. |
| EGL/WebGL initialization | Same symptom family. Current node descriptor/library state and exact native Vulkan failure are unavailable. |

The published image's verified digest is not independent attestation of the stopped pod's running digest. This job exported an expected image digest only. Original JSON file bytes were not recovered; its recorded canonical prompt hash matches the validated input.

The legacy graphics-descriptor preparation helper and the Studio capture environment filter were inspected. Selector propagation is a possible investigation lead, but there is no evidence that this job supplied a selector or generated descriptor. The unchanged filter also preceded known successful captures. Editing it now would not establish that this GPU failure is fixed.

All detailed paths, hashes, source comparisons and reused image-admission evidence are in `RECURRENCE_COMPARISON.json`. These are new incident comparisons, not reruns of existing PASS suites. GPU starts, renders, old-suite reruns and production-source edits in this recovery: **0**.
