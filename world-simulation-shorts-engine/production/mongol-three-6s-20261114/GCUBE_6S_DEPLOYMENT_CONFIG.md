# gCube #5373 — settings saved, runtime gate blocked

Status: DEPLOYMENT_SETTINGS_SAVED_GPU_RUNTIME_BLOCKED. The existing free actual-image admission evidence is reused. The image and four required environment values were saved and reopened on the stopped workload under the latest user authorization. Current-node EGL/WebGL2 and actual volume permissions remain unproved. READY_FOR_GPU_RENDER is false. No GPU deployment or Studio render was started.

## Exact common image candidate

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:universal-input-v2-f32d54dc0150-43567343017
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8afa856b2c87378354aae42755b3329eceed7c1db27a27491d367b76c15dc10d
```

Source commit: f32d54dc01507036fd66c4b06813611e48a6214b. GitHub Actions run43567343017. Source manifestSHA256 288498f70bb9ca0de337cfa0459d9e6b2db43d0c2984814014e6fce42be41169; startup manifestSHA256 08b240a9f94b375b9512fa0efd2ba9be75077b722f4c36467e75190163edd16b.

This is one common external-data/window contract version, not a Mongol-specific image. The new historical data package is excluded from the image. Legacy embedded V1 data remains for backward compatibility. The release approval is an image-publication gate, not GPU execution approval or proof that EGL has been repaired.

## Observed configuration and prepared values

Observed2026-11-14 and reconfirmed after publication: 종료 (Stopped), Tier2 RTX5090×1/32GB, CPU12Core, RAM63GB, disk937GB, shared memory3GB, existing dropbox volume `/world-storage`. The settings were saved and reopened: the stopped workload now references `universal-input-v2-f32d54dc0150-43567343017`. See GCUBE_DEPLOYMENT_SETTINGS_APPLIED.json and DEPLOYMENT_SETTINGS_DIFF.json. All resources, command, port8080 and existing non-digest environment values were preserved. Its stopped terminal is unavailable. Current driver and actual Pod imageID are not visible.

This differs from historical RTX4080SUPER success; driver580.159.03 must not be assumed on the current5090 node. Preserve existing sandbox, startup, authentication and secret settings. Never put credentials into an input or report.

Saved and reopened non-secret variables (two digest values changed; data root and catalog hash added; GPU_BACKEND retained):

```text
WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST=sha256:8afa856b2c87378354aae42755b3329eceed7c1db27a27491d367b76c15dc10d
WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST=sha256:8afa856b2c87378354aae42755b3329eceed7c1db27a27491d367b76c15dc10d
WORLD_ENGINE_DATA_ROOT=/world-storage/world-engine-data/v1
WORLD_ENGINE_DATA_CATALOG_SHA256=06cdf5e6509b3775c40afe307e95d77524da3fbb61b095987c9488c6e5d59822
GPU_BACKEND=vulkan
```

External files from this directory's `data/`: `catalog.json` and `8e42f3ec56bf2c8bbf321d47aa1fc23102b78bf971f2b49dea089876b8e664c0.json`. Root, every ancestor and files must be regular/non-symlink as applicable, owned by root or UID1000, with no group/world write; UID1000 must read files and traverse directories. The provider files were uploaded and their transfer identity verified, but actual mounted ownership/modes and UID1000 read access remain unverified. Do not relax the guard or add arbitrary descriptor paths. The CI proof used a read-only `/reviewed-data` mount with these restrictions, not the stopped gCube volume.

Use existing authenticated Studio upload after all runtime gates and separate approval. Local JSON paths are the three `MONGOL_6S_PART_0*.json` files in this directory. The exact live Studio URL is unavailable while stopped and is not guessed. Outputs use the existing unique private job directory `output/VIDEO.mp4` and exported `WORLD_ENGINE_STUDIO_VIDEO.mp4`; download each under distinct part names. No absolute per-job output path is invented before the real jobID exists.

## Provider placement and address limitation

The existing storage maps Dropbox `/WORLD_ENGINE` to container `/world-storage`. Data is uploaded under `/WORLD_ENGINE/world-engine-data/v1/`; the three inputs are uploaded under `/WORLD_ENGINE/mongol-three-6s-20261114/`. These are unchanged source files. See DEPLOYMENT_DATA_TRANSFER.json for file identities and container paths. Studio still uses its existing authenticated upload flow; no new renderer or auto-run command was installed.

gCube could not verify the immutable @sha256 address in its settings form. The exact specified tag was accepted and saved with both expected digest variables. An actual Pod imageID must be checked during a separately authorized execution; the environment variables do not prove it.

The stored historical operator policy is preserved and is not authorization to run. The GPU selector showed an estimated910–1300 KRW/hour excluding VAT for the retained RTX5090 resource; no time or budget is approved for this task.

## Remaining sequence

1. Recover retained same-pod graphicsPreparation/selector evidence; resolve the confirmed initialization cause. No paid reproduction is authorized.
2. Verify external data mounting/ownership and exact immutable image settings, then prepare a bounded GPU request with current hourly rate, maximum time/cost, retries0, and initialization-stop condition.
3. Only after separate authorization: initialization gate first; if it fails, stop and collect diagnostics. Do not advance to full rendering or retry automatically.
4. If approved initialization passes, execute only the separately approved render scope in part01→02→03 order. Verify180frames,1080×1920,30fps,6s and decode/download each. Stop workload and verify 종료.

Current time/cost limits: NOT_AUTHORIZED. The current selector estimate is recorded above; it is not a maximum approved charge. Prior budgets do not transfer automatically. No paid action or automatic retry is authorized.
