# Frame1 fix image publication and stopped gCube configuration

Approved scope completed on 2026-11-06 KST. Build1, publication1, settings save1, retry0, GPU start0, render0.

- Existing CPU regression run42031019500 reused; no historical PASS rerun.
- Sealed runtime source754b09262140b0ad5a48238843e0f98aaa8c4735 packaged in image run42102096738.
- Nine installed source pins, UID1000 startup manifest and356-row runtime contract PASS. Existing128 parent layers preserved; one new additive layer.
- Full806448907-byte backup retained before publication; archive, image and remote registry identities agree.
- gCube#5373 saved with new image and both matching digest fields. Saved detail confirms stopped and node unassigned, /world-storage,3GB shared memory. Port8080 was restored after image validation auto-fill and checked before saving.
- No changes to Scene, labels/maps, credentials, parent image tag, successful MP4 or main.

Image: ghcr.io/dimon3898-sys/world-simulation-shorts-engine:frame1-fix-v1-42102096738
Digest: sha256:dd79cad7aafcd2caefb1468c95f9fc28f8834c960135c6a038e208d04d221091

Actual changes this stage: new image-frame1/build_once.py, BASE_PINS.json, PREPARATION.json, APPROVAL.json, new .github/workflows/world-engine-frame1-fix-image-once.yml, CHECKPOINT.json, NEXT_GATE.json, and evidence in this execution directory. Runtime source was already validated in the previous stage; no runtime edit in this publication stage.

Remaining gate: separate paid GPU approval, actual mounted-storage plus active checkpoint external readback, then one unchanged QUALITY_LABELS_10S.json job. Continuous300-frame completion, full decode, external MP4 retrieval and reference-quality approval remain unproven. No automatic retry.
