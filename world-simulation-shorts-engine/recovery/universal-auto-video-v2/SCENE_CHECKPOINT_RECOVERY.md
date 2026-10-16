# Scene checkpoint recovery and final result revalidation

`delivery.export_scene_checkpoint(plan, scene, segment, shared_root,
private_base=job.path)` runs only after actual segment verification/cache
completion. It reuses the preserved StorageSession private path, identity,
preflight, bounded 4 GiB source/copy and mounted-readback checks. Every call
creates a unique export session; no old result or claim is deleted.

The separate **NONPUBLIC recovery** directory contains only `segment.mp4` and
`SHA256SUMS`. It is not a public review folder. It contains no source data,
diagnostic logs or shared JSON claiming hardware provenance. Mounted readback
is recorded; Dropbox synchronization/external download remains unverified.

A private `SCENE_CHECKPOINT_ANCHOR.json` binds the canonical plan and scene,
global half-open frame range, actual MP4/manifest hashes, generated export
location and test/native provenance. The trusted job record retains its path
and hash. Native checkpoint admission requires the existing hardware and full
decode verification flags; CPU synthetic tests remain explicitly test-only.

`delivery.verify_scene_checkpoint(checkpoint, shared_root)` checks the retained
private anchor and its ownership/mode/hash first, then no-follow rehashes both
shared files. Shared data never authenticates itself. Corruption fails closed;
the caller may preserve the bad checkpoint and create a fresh one from a still
verified local scene cache, without GPU re-rendering.

**Container replacement limitation:** automatic cross-container trust requires
the original private POSIX control/cache/anchor volume to persist. Dropbox is
an untrusted export mount and is not promoted to a private ledger. If both the
private ledger and private anchors are lost, an operator must supply a
separately trusted hash/provenance anchor through an explicitly reviewed
restore process. This implementation does not invent NVIDIA provenance from
shared MP4/SHA files or promise automatic trusted restore after such a loss.
Raw scene files are still preserved for that recovery.

`delivery.verify_mounted_export(result, shared_root)` revalidates a completed
job before reusing success: generated directory shape, no symlinks, exact three
public files, every byte count/SHA, anchored SHA256SUMS and safe QA fields. It is
read-only; it does not render, rewrite, repair or mark a missing result as
complete. The coordinator can preserve the completed state and report an
integrity error, then explicitly recompose/export from valid scene caches.

Six focused local tests passed with real CPU FFmpeg fixtures and the existing
UID/GID 1000 storage adapter: final mounted rehash, missing/mutated media,
symlink/traversal refusal, scene checkpoint roundtrip, shared corruption/lost
private anchor and forged plan/hash/hardware fields. These are mounted-view
tests, not actual Dropbox external synchronization or NVIDIA verification.
