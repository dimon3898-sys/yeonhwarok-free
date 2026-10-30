# Label355 D9 execution 41121425853

Status: BLOCKED — image ID mismatch cause remains unverified.

One authorized offline candidate build succeeded. New actual 355-file SHA256/size, bootstrap, worker, OCI and UID1000 verification passed. Safe config capture and backup passed. D9 then stopped publication; publication attempts 0, retries 0, GPU runs 0, old PASS reruns 0.

New image: sha256:987c9143a33428e494d988f83456eef7939481a81021cea1affa3f9bc6ae9584
Previous successful image: sha256:a175c1b01fda0513625a171e74987951d8c11ad083d8583fc297f4fcff2271cc

The safe image receipt contains 100 rootfs DiffIDs and hashes of selected config fields. Its status is CAPTURED_NOT_COMPARED. historyCount is zero because Docker inspect supplied no History. This does not recover full historical config or establish the mismatch cause.

The exact eight runner receipts retain their original statuses and bytes. SAFE_INDEX status PREPARED_NOT_REMOTE_BACKED_UP describes the runner stage; later artifact/log retrieval and Git preservation are documented separately. BUILD_RESULT is identity-only; the actual installed PASS is in INSTALLED_RESULT. IMAGE_ID_COMPARISON status COMPARED does not override the subsequent D9 failure.

Only the approved workflow was changed operationally; the publisher already matched the approved version. Source af934796, pinned parent, existing images/tags, and main were preserved. The runtime candidate was not exported or published. No 10-second GPU video was executed.

Read only: compare retained old/new image configuration or layer evidence if available. Old successful-image full config/rootfs evidence is absent from the existing preserved receipts; do not assert a mismatch cause. Current authorized one rebuild is consumed. Do not rerun, bypass D9, publish, develop another build method, or execute GPU. Any further build/publication needs new explicit authorization after the blocker is resolved.

Run: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/41121425853
Activation: https://github.com/dimon3898-sys/yeonhwarok-free/commit/6e30a9d38a96e8548ceefc20e13ec919560fcbb5
