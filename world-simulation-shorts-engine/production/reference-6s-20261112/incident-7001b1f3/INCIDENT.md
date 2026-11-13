# Post-capture JSON reader incident

Job: `studio-7001b1f300b62b05f2e9ea66ec1615df`.
User reports FAILED / FAILED, 1/1 scenes, 180/180 frames, 80.49s,
`JSON_SIZE_INVALID`. This supersedes deployment readiness, not the existing
compiler, geography, source, PNG or continuity PASS evidence.

## Directly recovered evidence

- Dropbox `/WORLD_ENGINE/capture-checkpoint-studio-7001b1f300b62b05f2e9ea66ec1615df/`
  exists and contains only `CAPTURE_CHECKPOINT.json` (880 bytes).
- Dropbox `/WORLD_ENGINE/capture-diagnostic-studio-7001b1f300b62b05f2e9ea66ec1615df/`
  exists and contains `CAPTURE_DIAGNOSTIC.json` (3388 bytes) and `SHA256SUMS`.
  Both listings completed without pagination. Exact recovered bytes are in `evidence/`.
- Checkpoint snapshot hash matches its canonical newline-terminated payload.
  Last recorded operation is frame179 / PROGRESS END, renderedFrames180.
- Safe diagnostic records capture Node process exit0 and verified supervisor cleanup.
  It does not include the raw exception traceback, offending filename/size,
  private CAPTURE_RECEIPT, FRAME_EVIDENCE, stdout, stderr, or MP4.
- On 2026-11-13 the gCube #5373 page showed stopped, deployment time12:15:42 KST,
  no allocated node, disabled container terminal and SSH. No provider action was taken.
  Therefore the current `/world-storage/...` mount and terminated private filesystem
  could not be inspected directly; the matching external Dropbox copies were inspected.
- All five new public export directories contain only storage-preflight JSON files.
  Complete listings are retained. No accessible MP4 was recovered.

## Confirmed code defect and evidentiary limit

The failed image8f8 source manifest pins the old nvidia_worker.py SHA566ada4a... .
Its `_validate_capture` reads `FRAME_EVIDENCE.json` through `PrivateTree.json`, whose
`cache.py` size guard rejects zero bytes or more than33554432 bytes. This read is
in VIDEO_VERIFY after capture exit0 and before MP4 verification/public export.
The same JSON_SIZE_INVALID code can also be raised by other generic cache reads
or writes; the exact GPU throwing file and its byte count are unavailable.
Do not present the archived CPU ledger byte count as the lost GPU file's size.

The already tested v13 worker (SHAd5bf03d4...) admits only FRAME_EVIDENCE with a
bounded frame-scaled cap, receipt SHA256, ownership/mode/no-follow/single-link,
immutable read, duplicate-key and finite-number guards. It was stored as a
production candidate and never merged into the canonical worker. The reference6s
packager copied the canonical old worker over an older immutable base, excluding
that existing repair. Source-closure equality alone did not detect this omission.

The v13 candidate is now copied byte-for-byte into the canonical worker; only the
worker and three required startup/source pins change. Its ten PASS security tests
are reused. A new test reads the existing reference6s180 CPU artifact, without
rendering, to establish the current input's post-capture admission regression.

## MP4 distinction

180 processed frames alone is not an encoded or exported MP4. The unchanged
capture JavaScript normally exits0 only after FFmpeg, internal ffprobe/full decode,
and capture receipts finish. Together with observed exit0 this supports an
inference that a private VIDEO.mp4 was made. It is not a recovered video, file hash,
or proof of successful external delivery. The stopped container cannot currently
provide those bytes. No automatic rerender/retry is authorized or performed.

## Continuation

Run only the archived-ledger admission test, then build an additive four-file image
over digest8f8. Verify the installed new reader and required source/startup pins.
Preserve the immutable old image and failure records. Do not rerun old visual or
compiler checks, start a GPU, or claim the failed job's MP4 has been recovered.
