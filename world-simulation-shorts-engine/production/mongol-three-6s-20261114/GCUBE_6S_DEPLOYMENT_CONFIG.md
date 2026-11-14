# gCube #5373 — stopped configuration preparation

Status: BLOCKED until a common V2 image passes actual-image admission and the existing GPU environment failure is resolved. Do not deploy, start Studio rendering or retry automatically.

Observed 2026-11-14: 종료 (Stopped), Tier2 RTX5090 ×1 /32GB, CPU12 Core, RAM63GB, disk937GB, shared memory3GB, existing dropbox volume /world-storage. Preserve these settings. This differs from historical RTX4080 SUPER success; its driver580.159.03 must not be assumed on the stopped5090 node. The UI does not expose a current Pod digest or driver.

The stopped workload still references history20-6970708eb71a-43551475182. No configuration change has been made. The old g2 success image and its digest are preserved in SIX_SECOND_GPU_SUCCESS_BASELINE.md; it does not admit the new historical input.

New common image tag/digest: PENDING_BUILD_AND_REMOTE_DIGEST. After release admission, both WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST and WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST must equal its verified digest. Preserve GPU_BACKEND=vulkan, existing sandbox, startup and secret values. Never store owner codes or tokens in this report.

External-data configuration:
- WORLD_ENGINE_DATA_ROOT=/world-storage/world-engine-data/v1
- WORLD_ENGINE_DATA_CATALOG_SHA256=06cdf5e6509b3775c40afe307e95d77524da3fbb61b095987c9488c6e5d59822
- Files: catalog.json and 8e42f3ec56bf2c8bbf321d47aa1fc23102b78bf971f2b49dea089876b8e664c0.json from data/.
- Root, all ancestors and files: regular/non-symlink, owned by root or UID1000, no group/world write. UID1000 must read files and traverse directories. These stopped-node permissions remain unverified. Do not bypass the check.

Submit MONGOL_6S_PART_01.json, 02, 03 through the existing authenticated Studio input only after release/runtime gates and separately authorized GPU scope. Output uses existing unique private job directories and exported WORLD_ENGINE_STUDIO_VIDEO.mp4; download each under distinct part names. Different input hashes and job IDs prevent private output collisions; do not overwrite downloaded files.

Execution order after separate approval: bounded GPU initialization check → part1 → part2 → part3 → download/check180frames each → stop workload → verify 종료. Do not proceed from failed initialization to full rendering, and do not auto-retry. Current GPU cost/time cap is NOT_AUTHORIZED; previous RTX4080 approvals do not transfer. Obtain current rate and present an explicit maximum before asking for GPU approval.
