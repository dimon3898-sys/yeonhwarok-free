# Variant pin correction image applied — 2026-11-06 KST

Approved1image build/publication and gCube image/digest settings update completed. GPU starts0, renders0, retries0.

- Sealed source commit2d1f8a5b0460e4e1eb3fa423e0a0625e271787fb from successful CPU run42145763081 reused. No historical PASS suite rerun.
- Four installed files and356-row startup/source closure verified asUID1000. The actual verifyGeneratedSources() function also completed inside the built image, verifying all3source pairs. This covers the previously omitted hardcoded variant gate.
- Parent129layers preserved with1additive layer. Complete806482561-byte image archive retained before GHCR publication; archive, installed image and registry identities agree.
- gCube#5373 now saves the new image and both matching expected digest fields. Readback confirms stopped and node unassigned, /world-storage,3GB shared memory. Port8080 was restored after image validation auto-fill and checked before Save. Existing credentials and unrelated settings were not changed.

Image: ghcr.io/dimon3898-sys/world-simulation-shorts-engine:variant-pin-fix-v1-42163156402
Digest: sha256:af3ad26a305c160a916ac231122a31824cbee4759338c044bab0d6c9dab1691a
Backup: https://github.com/dimon3898-sys/yeonhwarok-free/releases/tag/variant-pin-fix-image-backup-42163156402

Changed in this stage: image-variant-pin/{build_once.py,installed_probe.py,BASE_PINS.json,PREPARATION.json,APPROVAL.json}, .github/workflows/world-engine-variant-pin-fix-image-once.yml, CHECKPOINT.json, NEXT_GATE.json, prior IMAGE_PLAN authorization status and this execution evidence. No additional runtime source edits; the correction remains one capture_nvidia.mjs hash plus3dependent pin files. Existing QUALITY_LABELS_10S.json is unchanged.

Remaining: actual gCube Studio HTTP preflight, mount/checkpoint external retrieval and continuous300-frame10sMP4 completion have not run. These require a separately approved GPU session. The installed source gate PASS is not a completed-render claim.
