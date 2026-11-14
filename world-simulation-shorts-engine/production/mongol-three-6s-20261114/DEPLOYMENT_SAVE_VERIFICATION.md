# gCube #5373 settings saved; runtime remains blocked

The stopped workload was edited through its existing `수정` workflow, saved, reopened, and compared against the intended values. The separate `배포` control was not invoked. The workload remained `종료`; the displayed last deployment and stop event remained 2026-11-14 13:34:54 and 13:40:35. Same-detail cost and balance displays were unchanged. This is an observation of no new execution, not an independent billing audit.

## Saved changes

- Image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:universal-input-v2-f32d54dc0150-43567343017`.
- Both image-digest environment variables: `sha256:8afa856b2c87378354aae42755b3329eceed7c1db27a27491d367b76c15dc10d`.
- Data root: `/world-storage/world-engine-data/v1`.
- Catalog SHA256: `06cdf5e6509b3775c40afe307e95d77524da3fbb61b095987c9488c6e5d59822`.

The gCube image-address check could not verify the `@sha256` form and accepted the exact supplied tag. The original published tag/digest evidence is reused. These environment values do not attest the eventual Pod imageID.

Image-address verification automatically changed the draft port from 8080 to 8000. This was caught by the before/after comparison, restored to 8080 before save, and confirmed at readback. No unintended port change was persisted.

## Preserved and checked after reopening

RTX5090 Tier2 ×1/32GB, CPU12, RAM63GB, disk937GB, replica1, shared memory3GB; port8080, empty command, concurrency4; Istio enabled, L7 consistent hash disabled, no minimum CUDA constraint. Existing environment values13/13, including authentication and operator policy, remained equal. Total variables17. No EGL/Vulkan selector was added; GPU_BACKEND=vulkan was retained. Secret values are omitted from reports.

The pre-existing external storage alias `world-engine-test` maps Dropbox `/WORLD_ENGINE` to `/world-storage`, PV/PVC Bound. The connection was retained. The existing historical package/catalog and three existing JSONs were uploaded into new folders without regeneration or overwriting old files. All five transfer sizes and Dropbox content hashes match the source bytes; see DEPLOYMENT_DATA_TRANSFER.json. The three source SHA256 values still match DEPLOY_PREFLIGHT.json.

## Limits and next gate

No engine test, old PASS, image build, container pull/start, Studio render or GPU trial was run. File availability in Dropbox is proved; actual mounted UID1000 ownership/readability, parent directory modes, real Pod digest and EGL/WebGL2 are not proved. Existing security guards remain in force. Existing 6-second success and 20-second failure records remain unchanged.

Status: `DEPLOYMENT_SETTINGS_SAVED_GPU_RUNTIME_BLOCKED`. `READY_FOR_GPU_RENDER=false`.
The next execution action requires a separate, bounded authorization for initialization-first six-second GPU testing. The existing EGL blocker is retained; initialization failure must prevent full rendering and trigger stop/evidence collection. No automatic retries. The stored historical operator policy is not new user approval.
