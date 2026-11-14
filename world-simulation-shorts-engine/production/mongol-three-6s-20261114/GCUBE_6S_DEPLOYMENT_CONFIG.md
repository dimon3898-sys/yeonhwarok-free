# gCube #5373 — common image prepared, runtime gate blocked

Status: COMMON_IMAGE_VALIDATED_GPU_ENVIRONMENT_BLOCKED. The common image and all three input transports passed free actual-image admission. Current-node EGL/WebGL2 recovery and stopped-volume ownership remain unproved. READY_FOR_USER_GPU_START is false. No deployment or Studio action was taken.

## Exact common image candidate

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:universal-input-v2-f32d54dc0150-43567343017
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8afa856b2c87378354aae42755b3329eceed7c1db27a27491d367b76c15dc10d
```

Source commit: f32d54dc01507036fd66c4b06813611e48a6214b. GitHub Actions run43567343017. Source manifestSHA256 288498f70bb9ca0de337cfa0459d9e6b2db43d0c2984814014e6fce42be41169; startup manifestSHA256 08b240a9f94b375b9512fa0efd2ba9be75077b722f4c36467e75190163edd16b.

This is one common external-data/window contract version, not a Mongol-specific image. The new historical data package is excluded from the image. Legacy embedded V1 data remains for backward compatibility. The release approval is an image-publication gate, not GPU execution approval or proof that EGL has been repaired.

## Observed configuration and prepared values

Observed2026-11-14 and reconfirmed after publication: 종료 (Stopped), Tier2 RTX5090×1/32GB, CPU12Core, RAM63GB, disk937GB, shared memory3GB, existing dropbox volume `/world-storage`. Settings remain unchanged. The stopped workload still references `history20-6970708eb71a-43551475182`. Its stopped terminal is unavailable. Current driver and actual Pod imageID are not visible.

This differs from historical RTX4080SUPER success; driver580.159.03 must not be assumed on the current5090 node. Preserve existing sandbox, startup, authentication and secret settings. Never put credentials into an input or report.

Prepared non-secret variables (NOT applied):

```text
WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST=sha256:8afa856b2c87378354aae42755b3329eceed7c1db27a27491d367b76c15dc10d
WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST=sha256:8afa856b2c87378354aae42755b3329eceed7c1db27a27491d367b76c15dc10d
WORLD_ENGINE_DATA_ROOT=/world-storage/world-engine-data/v1
WORLD_ENGINE_DATA_CATALOG_SHA256=06cdf5e6509b3775c40afe307e95d77524da3fbb61b095987c9488c6e5d59822
GPU_BACKEND=vulkan
```

External files from this directory's `data/`: `catalog.json` and `8e42f3ec56bf2c8bbf321d47aa1fc23102b78bf971f2b49dea089876b8e664c0.json`. Root, every ancestor and files must be regular/non-symlink as applicable, owned by root or UID1000, with no group/world write; UID1000 must read files and traverse directories. The actual volume is unverified. Do not relax the guard or add arbitrary descriptor paths. The CI proof used a read-only `/reviewed-data` mount with these restrictions, not the stopped gCube volume.

Use existing authenticated Studio upload after all runtime gates and separate approval. Local JSON paths are the three `MONGOL_6S_PART_0*.json` files in this directory. The exact live Studio URL is unavailable while stopped and is not guessed. Outputs use the existing unique private job directory `output/VIDEO.mp4` and exported `WORLD_ENGINE_STUDIO_VIDEO.mp4`; download each under distinct part names. No absolute per-job output path is invented before the real jobID exists.

## Remaining sequence

1. Recover retained same-pod graphicsPreparation/selector evidence; resolve the confirmed initialization cause. No paid reproduction is authorized.
2. Verify external data mounting/ownership and exact immutable image settings, then prepare a bounded GPU request with current hourly rate, maximum time/cost, retries0, and initialization-stop condition.
3. Only after separate authorization: initialization gate first; if it fails, stop and collect diagnostics. Do not advance to full rendering or retry automatically.
4. If approved initialization passes, execute only the separately approved render scope in part01→02→03 order. Verify180frames,1080×1920,30fps,6s and decode/download each. Stop workload and verify 종료.

Current time/cost limits: NOT_AUTHORIZED. Current rate/maximum duration cannot be established from the stopped workload detail; prior4080 budgets do not transfer. No numeric estimate is fabricated.
