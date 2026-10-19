# Source inputs and replay

The actual historical capture source is the canonical 80-second document with raw SHA-256 `33596c97b433887afb7ced6847d4ef63d099a9b6633546d541890a45c9c6289e`; its legacy Scene object SHA is `1b2301864058d3ec4109259057ba17baa44ea165f60467bcbfd7756757cdf4b9`. The twelve source ranges cover `[0,2400)`. All twelve reference the same verified native payload SHA `f7085aaefa45efe5af51b14f48c692d21c72598c5bfbf89350af6c826cb60090`.

The canonical preparation is an existing implementation, not a new parser. Do not substitute the differently formatted/differently bound historical `VALIDATED_80S_SUBMISSION.json` simply because it also describes eighty seconds. The existing `universal-overnight-v3/prepare_source_preview.py` produces the actual source-bound canonical Plan and Submission used by the previous free capture.

## Durable source closure

All source programs below are tracked Git files. Generated activation bundles, `PLAN.json`, `SUBMISSION.json`, sidecars and local Chromium caches do not contain unique hand-created source data.

| Source | SHA-256 | Role |
|---|---|---|
| `recovery/universal-overnight-v3/PREVIEW_PROFILE.json` | `f1d1b560739e252dc5e348ec5cec8bbdc94607c295a93cdc437f89d4995509f1` | Existing structured input contract and explicit completion settings |
| `recovery/astra-gpu-activation-v1/SCENE_MAP_DATA.json` | `f459f3db4aadf93f9833a1fc5b66a5cd9442598737ce722b23c4b463e314c555` | Existing source selection, coverage and material policy |
| `recovery/astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip` | `bd028be93f1813e0ac16628afcd218e95685cedb730b89a6584d196878ead66a` | Original ASTRA sample archive, 12,582,426 bytes; tracked in Git, not redistributed in the review ZIP |
| `recovery/universal-auto-video-v2/fixtures/NATIVE_PAYLOAD.json` | `f7085aaefa45efe5af51b14f48c692d21c72598c5bfbf89350af6c826cb60090` | Same immutable native input context for all twelve source ranges |

Paths in this table are relative to `world-simulation-shorts-engine/`. Referenced native assets, archival GeoJSONs and preservation manifests remain in their original tracked locations. The adapter does not alter them.

## Existing preparation sequence

These are developer replay commands, not actions the mobile user must perform. They create only new private directories and inert data; they do not open Chromium, render an MP4, create a Studio claim or deploy a GPU.

1. Use the tracked `reference-visual-master-v2/prepare_ref2.py` existing `--prepare-activation --variant F --private-root <new owner-only directory>` command. The private root must already exist with mode 0700 and belong to the execution user. This reuses the existing CPU providers and GPU-upload-bundle preparation. A fresh activation contains its own bundle path, so compute and use its returned `activationSha256`; do not hardcode the earlier path-dependent activation hash.
2. Pass the returned activation file/hash to the tracked preparer:

   ```sh
   python3 -B world-simulation-shorts-engine/recovery/universal-overnight-v3/prepare_source_preview.py \
     --destination <new-private-input-directory> \
     --image-digest sha256:a956c93e4b23bc1f73990d94948c85e4db0c2f18f0bdef301f61ad7882be4886 \
     --activation-file <returned-activation-file> \
     --activation-sha256 <returned-activation-sha256>
   ```

   This digest is the **original input document's inert image binding**, preserved so the historical input bytes remain unchanged. It is not a claim that the image was executed locally, and it does not deploy or pull it.

3. Check `PREPARED.json` has `renderStarted=false`, `full80sRenderAllowed=false`, and `options.expectedPlanSha256=33596c97b433887afb7ced6847d4ef63d099a9b6633546d541890a45c9c6289e`.
4. Use this task's `loadSourceOptions(<new directory>/PREPARED.json)` to validate the actual Plan, Submission and activation before calling `openDirectorRuntime`. It checks the original inputs rather than accepting a filename alone.
5. Add the separate director presentation profile/camera module files through the new `runtime_adapter.mjs` options. These files change only the opt-in presentation edge; their hashes are part of the task's capture provenance. Sampling passes source-global frame indices unchanged.

The original reference preparation internally reads the old visual Scene for its source-data closure. The historical browser consumer explicitly binds the historical legacy Scene and validates `fictional65422SceneUsed=false`; the fictional scalar boundary and military positions are not rendered.

## Actual reconstruction check in this task

The existing source preparer was executed once into a new private inert directory using the already available activation. It returned the exact Plan SHA above, `sceneId=scene-0007`, current preserved source manifest SHA `ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7`, and `renderStarted=false`. This proves the generated Plan/Submission are reproducible from the preserved preparer, without replaying the earlier 5-second movie or using a GPU. No ASTRA samples were re-downloaded or re-parsed for this check.

The existing activation and bundle were already validated against their actual hashes by the source loader. Their regeneration uses the existing tracked preparation chain; this task did not repeat prior ASTRA parsing tests merely to create duplicate evidence. Required unique temp-only source files: **0**. Generated software capture caches are not needed to regenerate source inputs.

## Image provenance boundary

The latest repository-attested image considered here is `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:1bb399679bfaf1f3d6d57df67c139974e8c63862f07142e950b9b6d150281c9f`, built from source commit `f8b17ec3b2e0e8100b7e29980fecd1fdd8517218`. Existing independent-runner pull/source proofs verify fifteen reconciliation files and eighty-two retained parent files. This task additionally rechecks anonymous manifest/config metadata only; see `IMAGE_METADATA_RECHECK_RETRY.json`.

The 16-frame preview runs the source checkout with SwiftShader, not this container. The current gCube-deployed image is **UNVERIFIED** without an actual authenticated workload response. This task does not create a new image, deploy gCube, perform NVIDIA validation, or approve video quality.
