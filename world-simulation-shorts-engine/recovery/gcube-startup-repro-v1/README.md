# gCube #5373 — immutable startup CPU reproduction

Baseline: `9034e18062ebcb8fd1f1fcc6dcee8898764650c7`.
This diagnostic branch preserves the RTX package, renderer, camera, frontier,
ASTRA source, approved media and FINAL. It does not build/push an image or deploy
a gCube workload. Only a free public standard `ubuntu-24.04` runner is admitted.

The existing immutable `82a4d908…16a37` image is pulled once, with at least 20 GiB
of Docker storage required. Its config SHA, linux/amd64 platform, ENTRYPOINT,
CMD and user are checked. Cases use no GPU, no network, no restart policy,
4 GiB memory, 2 CPUs, 2 GiB shm and a bounded 180-second wait.

Eight cases record actual stdout/stderr bytes, SHA-256, container exit code,
OOM/timeout status, failure stage and mount ownership/mode before/after:

1. Original default ENTRYPOINT/CMD, no mount.
2. Original ENTRYPOINT with `--check`, no mount.
3. Writable private mount owned by UID 1000.
4. Writable dedicated subdirectory initially owned by another UID, root startup.
5. Correct storage ownership/mode with storage `chown` EPERM injected.
6. Correct storage ownership/mode with storage `chmod` EPERM injected.
7. Actual read-only bind mount.
8. Foreign-owned private storage with UID 1000 startup.

Cases 5/6 are explicit test wrappers calling the unchanged original bootstrap.
They are not an actual Dropbox mount, gCube PVC test, production wrapper or GPU
admission bypass. Ordinary cases retain the image's original entrypoint.
Private mounted contents are outside the evidence directory and are not
published. Existing files/images/containers/cache/volumes are not deleted.

Expected GPU absence (`exit 2`, `GPU_HARDWARE_UNAVAILABLE`) is a successful
negative test, not successful container service/GPU rendering. A storage
refusal (`exit 1`) must be distinguished from dependency/source failures.
An unexpected result fails the matrix and is preserved for investigation.

`OLD_CONFIG_METADATA.json` contains verified small registry metadata for the
previous `7e32…` image; no old layers were downloaded. Its actual entrypoint is
`python /opt/gate1-static/server.py`, not the repository's generic gCube start
module. The old server bytes and historical workload/image binding are not
proven, so source-family comparisons must not be presented as an old-image
runtime test.

The actual #5373 terminated exit code, stdout/stderr, PVC semantics and NVIDIA
graphics initialization are unavailable. CPU reproduction cannot identify the
actual gCube cause without matching evidence. A matrix PASS must not be reported
as #5373 recovery. No runtime fix or new image is authorized by a mock alone.

The workflow persists only bounded diagnostic records and checksums under
`runs/<run-id>-<attempt>/`, on the diagnostic branch, using a commit with
`[skip ci]`. Original package tests/build evidence are reused; the 104-test suite
is not repeated.
