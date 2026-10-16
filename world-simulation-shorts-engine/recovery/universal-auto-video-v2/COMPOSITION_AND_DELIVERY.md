# Streaming composition and delivery

This additive layer calls the existing FFmpeg/FFprobe binaries and the preserved
Dropbox storage adapter. It changes no renderer, camera, FINAL or existing job.

## APIs

`compose.verify_segment(path, scene, plan, diagnostics=None)` admits a completed
segment only after its SHA-256, actual H.264/yuv420p silent stream, resolution,
FPS, every presentation timestamp, exact frame count and full CPU decode pass.
It returns `technical: PASS`, `frameCountVerified: true`, decoded RGB24 first and
last hashes, and evidence in a fresh private verification directory. It does
not assert GPU rendering or geographic correctness.

`compose.compose_segments(plan, segments, destination)` accepts an ordered list
of `sceneId`, `startFrame`, `endFrame`, `path`, `sha256` receipts. Resolution is
either `{width,height}` or `[width,height]`; FPS is a positive integer at most
120. Total duration times FPS must be an integer. Every range is half open;
scene IDs, ordered ranges and optional `plan.scenes` must exactly agree.
There are at most 10,000 segments and 86,400 seconds per invocation. The same
implementation handles the requested 80, 120, 180, 300 and 600-second contracts.

The compositor probes and fully decodes each input. It stream-copies only if
all codec/extradata/time-base/color signatures match, start PTS is zero, first
frame is a keyframe and every PTS has the declared cadence. Otherwise it
normalizes each already verified CFR segment through lossless H.264, with
explicit FPS and packet duration, then concatenates. A wrong cadence is a
failure; normalization is not permission to invent, drop or retime frames.

The entire final MP4 is decoded and **every RGB24 frame hash must match the
ordered input decoded sequence**. Any copy/re-encode change, missing frame,
reordering or corruption fails. Legitimate identical hold frames are allowed;
there is no false rule that all frame images must differ. Whole-map near-black
frames (at least 99% below the detector's luma threshold 26) fail this map-only
profile. Color interpretation or re-encoding that changes a decoded pixel is
blocked rather than silently accepted.

Optional segment `boundaryFrames` carries actual encoded RGB24 first/last
hashes. Optional scene `boundaryStart`/`boundaryEnd` dictionaries (or canonical
state SHA fields) must match at the same mathematical scene boundary. Adjacent
time frames normally have different pixels. These checks record their actual
images and verify requested state contracts, **not visual continuity approval**.
Camera, historical meaning and geographic visual quality remain review items.

## Bounded memory, preservation and timing

Python never reads complete media files or stores decoded frame images. SHA
and file copying use 1 MiB chunks; decoded frame hashes stream to private files.
FFmpeg uses bounded codec pipelines and two worker threads, not a full-video
array. Each media operation has an upper time bound. Normalization uses
additional disk space, which the coordinator must reserve before execution.
Private receipt timings separately record source verification, normalization,
muxing, final full validation and final source readback/commit. These are actual
measurements of the invocation, not an 80-second production performance claim.

Output requires a fresh directory. Existing clips and outputs are never
overwritten. Partial movies, stderr and `COMPOSE_FAILED.json` stay quarantined
in that new private directory. No completion receipt is created on failure.
Successful output contains a private `COMPOSE_COMPLETE.json` and exactly:

- `public-review/WORLD_ENGINE_AUTO_VIDEO.mp4`
- `public-review/QUALITY_SUMMARY.json` — fixed safe fields, no paths/URLs/logs
- `public-review/SHA256SUMS`

## Dropbox adapter reuse

`delivery.export_video(plan, composed, export_root, private_base=None)` (alias
`export_completed`) verifies the completed manifest and safe public allowlist,
then uses the unchanged `StorageSession.create/preflight`, private path and
UID/GID checks, source hash validation, exclusive streamed copy, fsync and
mounted readback. The inherited adapter source is pinned to
`4c858e7afe5e912bce63bf03f08c6c98d9430cc91134262710db5bdbd6ca4491`.

Production uses UID/GID 1000, private local POSIX storage and untrusted
`/world-storage` for exports only. The private base defaults to the composition
directory. Each call creates a unique export session and video directory;
existing Dropbox exports and claims are preserved. The original adapter's
**4 GiB per-file limit** is retained. Longer contracts do not imply a verified
600-second file under that bound. Exceeding it requires an explicitly reviewed
adapter extension, never a security bypass.

The adapter returns `MOUNTED_EXPORT_VERIFIED` with
`mountedViewReadbackVerified: true`, `remotePersistenceVerified: false`,
`externalDownloadVerified: false`. A mounted copy is not Dropbox sync proof.

`delivery.verify_external(public_dir, urls, destination, sha256sums_anchor)`
requires an actual private URL map for the same three files and a separately
anchored SHA256SUMS hash. It reuses the existing HTTPS Dropbox URL/redirect
guards, then makes bounded streamed GETs, requires HTTP 200, checks downloaded
byte counts and hashes, and revalidates the public allowlist. It never records
URLs or credentials in receipts. No link/account discovery or public API is
created. A supplied mock opener always returns `SYNTHETIC_ONLY` and
`externalDownloadVerified: false`, even when all mock hashes match.

## Focused validation

`/usr/bin/python3 -B -m unittest discover -s recovery/universal-auto-video-v2/tests -p test_compose_delivery.py -v`
(run from `world-simulation-shorts-engine`, or use its full path from repo root).

Twenty focused tests passed locally as UID/GID 1000. They include actual short
64×96 CPU FFmpeg fixtures, full decoded-order equality, nonzero-PTS lossless
normalization, corrupt MP4 refusal, real black-frame refusal, half-open ranges,
requested versus actual boundary hashes, output preservation, original storage
private/preflight/copy/readback and safe public summary checks. Mock HTTPS tests
cover response errors and SHA mismatch without claiming real Dropbox delivery.
80–600-second tests exercise contracts and segmentation only. They do not
render long videos, use NVIDIA or prove the production 60-minute target.

The real storage export test is explicitly SKIP if not UID/GID 1000; CI should
also run it inside the candidate image with its production identity. A SKIP
must not be reported as a storage PASS.
