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

Completed in free Actions run43359755603: the existing180frame CPU ledger is
116332024 bytes (SHA8750c66d...), exceeding the generic33554432-byte cap. The old
reader raises JSON_SIZE_INVALID; the restored reader returns the exact parsed
document and leaves the source bytes unchanged. This is direct evidence of the
current input's admission defect, not a measurement of the unavailable GPU file.
The new180frame ledger cap is377487360 bytes; all other JSON retains32MiB.

Only four runtime files were overlaid on digest8f8. Installed UID1000/no-network/
read-only verification confirms the actual worker import, call binding and new
source/startup seals. No renderer, encoder or GPU was invoked. The existing ten
reader security PASS tests and all reference compilation/visual PASS were reused.
An initial test setup failure (receipt and ledger in different artifact folders)
is retained in execution-a1; only that new setup path was corrected for a2.

New image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:reference6s-jsonfix-df10b435ec73-43359755603`

Digest: `sha256:d1bf9b54ba361c46e42c7e231485b63b58ad54a4d3b3431f4fc34983a5c3a0c1`

State: PENDING_GPU_VALIDATION_NO_RETRY_AUTHORIZED. gCube remains stopped with its
previous image selected; NEXT_IMAGE_SETTINGS.json contains the exact three
configuration changes. Applying those values is not permission to deploy or
render. Keep all old failure records and images. The old private MP4/raw exception
cannot currently be recovered, and the new image's actual GPU export is untested.
