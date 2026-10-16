# Production Studio MVP V1 — execution candidate

Decision: **PRODUCTION_STUDIO_MVP_CANDIDATE_READY_WITH_LIMITS**.

The mobile production/SFX execution package is built and registered. This is
not a claim that every requested MVP feature is complete: interval camera,
territory and frontier editing remains unsupported. No new NVIDIA 80-second
video, actual gCube ingress session, external Dropbox download or final visual
approval was performed. Paid GPU execution and FINAL promotion were not run.

## Candidate and persistence

- Branch: `development/production-studio-mvp-v1-20261016`.
- Actual image source: `147e4f4d0da894ecf35151826890ed4501ee3db8`.
- Image tag: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:studio-v1-344dc2d-38883417252-1`.
- Immutable image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94`.
- Platform: `linux/amd64`; actual image size: 1,603,016,749 bytes.
- Studio source-manifest SHA: `1f4129faaeb59027429d4d531da2b7e7b50156ca7c1652e700dd542c935b88de`.
- Actual manifest: `image-manifests/studio-v1-344dc2d-38883417252-1.json`.
- Build and fresh independent pull: [run 38883417252](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38883417252).
- Anonymous manifest GET: HTTP 200; manifest and config digests match. This
  extra local check fetched metadata only, not a full local Docker image.

Implementation was saved incrementally: SFX checkpoint `e09109d`, integrated
checkpoint `810fcb3`, confirmed image-layout corrections `47676a1`/`7ee4322`,
bounded SFX checkpoint `ae5a112`, and final candidate source `147e4f4`.
Concurrent report-only commits were merged while retaining both histories;
no force push, reset, claim deletion or old image overwrite was used.
The earlier source-7ee4322 image remains preserved but is superseded because it
predates the confirmed interval-audio correction. Use the image above.

Required temp-only runtime/source/asset files: **0**. Sources, explicit runtime
inventory, tests, original WAV assets, manifests, recipes and evidence are stored
on the development branch; actual runtime bytes are also in GHCR.

## Implemented path and current limits

| Requirement | Implementation and evidence | Remaining boundary |
|---|---|---|
| Mobile production UI | Authenticated new-video, preflight, consent/start, measured status, completion/download, revision and explicit recovery screens | Actual gCube HTTPS/proxy and physical phone remain untested |
| Input | Structured JSON/fenced JSON or complete verified Scene JSON; authored missing-field hints | No unrestricted natural-language AI or new facts/history research |
| Existing Scene JSON | Preserved V4 80s plan; packaging image identity rebound and scenes rederived by original validators | The V4 archival plan is exact and cannot be silently retuned |
| Start | Owner session + Origin/CSRF + actual operator limits + original admission, claim and GPU manager | Real NVIDIA production has not been started by this task |
| Session independence | Original detached execution/PID identities; idempotent starts; no start on GET/reconnect/restart | Container replacement can lose ephemeral private state |
| Recovery | Explicit authenticated Resume, original approval/deadline/retry limits retained | No claim reset, unlimited retry or automatic billing stop |
| SFX | Six classes, 18 original CC0 WAVs, exact frame/sample binding, gain/ON/OFF, optional WAV and AAC MP4 | No reference-audio extraction, TTS, subtitles or BGM |
| Interval revision | SFX ON/OFF/gain/verified cues; disclosed neighboring audio/tail impact; new version, unchanged GPU video caches | Camera/territory/frontier edits return explicit HTTP 422 |
| Duration | Same native V3 engine accepts verified 80/120/180/300/600s plans | Built-in V4 fixture is 80s only; long GPU success is unverified |
| Delivery | New MP4/SHA/safe summary/optional WAV export with mounted SHA readback; authenticated verified-snapshot download | External Dropbox synchronization/download is not asserted |

The Start path is `server.py` → `StudioController` → `studio_runtime.py` → fixed
original V4/V3 coordinator CLI → original scene renderer/cache/FFmpeg/export →
additive licensed SFX/AAC mux → fresh versioned `StorageSession` export.
No user-supplied executable, shell command, source path or GPU deployment API is
accepted. Current progress displays actual observed counts/phase/elapsed time;
there is no invented ETA.

The default V4 SFX schedule uses the 12 supplied chapter-onset events. Other
sound classes require actual supplied event/cue bindings; absent marker,
occupation-completion or camera events are not invented. Audio uses 48 kHz and
bounded one-second mixing blocks. Video H.264 is copied through the final mux;
decoded video frames/timestamps are checked unchanged.

Interval corrections now select variants by cue identity and use local authored
cue admission. Removing a 25-second cue no longer changes an unchanged 36-second
cue. Actual 80-second PCM tests show identical samples outside conservatively
reported audio support. Tails or local neighboring cue effects are previewed,
including adjacent scenes. This is PCM evidence, not a claim of identical AAC
bytes. All video scene keys remain reusable. Actual visual partial GPU rendering
is not claimed.

## Free validation

Final image CI passed **176 Python tests**:

| Focused suite | Tests |
|---|---:|
| CI safety / registry / evidence reuse | 21 |
| Bootstrap and private configuration | 18 |
| Actual loopback HTTP/auth/download API | 21 |
| SFX, PCM, real FFmpeg and 600s streaming | 23 |
| Input, native V4 binding and interval impact | 36 |
| Controller, consent, claims and recovery | 22 |
| Exact source manifest | 11 |
| Runtime and real CPU composition/export | 24 |

Actual Chromium portrait emulation passed **12 checks**, including paste/upload,
owner authentication, double activation, browser reconnect, completion,
unsupported visual requests and adjacent audio-impact display. Its injected
CPU test controller/media fixture is not a real GPU production or physical
phone test. Versioned local and CI screenshots/reports are retained.

The real CPU media integration used a synthetic 2-second, 60-frame, 64×96 H.264
fixture through the original silent composer/export, actual SFX/AAC mux,
versioned storage export, SHA readback and corruption rejection. A real
600-second WAV verifies bounded memory and the audio sample grid, not a
600-second NVIDIA movie.

Actual inherited SwiftShader shader compile/draw/readPixels ran in
`38881729276-1`: 12 temporal samples and 14 saved PNG hashes. The final audio/UI
image independently reverified the same immutable 373-file parent and pinned
report/source/PNG hashes. Its record explicitly says `executedInThisRun:false`;
no duplicate long map draw or new NVIDIA claim is made. Legacy 104/168/full
suites and prior historical/data audits were reused rather than repeated.

Confirmed integration defects were fixed: normalized GPU-health model names,
bounded mutable export reads, private verified download snapshots, actual phase
display, safe contract hints, two CI layout/entrypoint assumptions, and the
demonstrated stateful SFX revision cascade. Old failure reports remain saved.

## Protection and security

- Preexisting protected file modifications: **0** against baseline
  `344dc2da48e15230725d687a4343456cbbae89a8`.
- Old immutable V4 image and exact **373-file** closure: preserved and verified.
- New independently verified Studio payload: **51 files**, outside the old tree.
- Original synthesizer and all 18 original WAV bytes: unchanged.
- Actual new image/source/workflow Secret Scan: **0 findings**, pinned gitleaks
  defaults with no ignore suppression. Final local report scan is recorded too.
- Owner authentication and operator policy are private0600 files; owner/policy
  values are removed from child environments. No credentials are baked into the
  image. Public downloads exclude source, diagnostics, approvals and plans.

The V4 source still contains partial approximate fronts with unknown original
projection/full absolute accuracy; only 850 frames use those archival fronts
and 1,550 remain preserved schematic context. No new coordinates, units,
occupation polygons or historical claims were generated.

## User's next action

Follow `MVP_OPERATION.md`. Manually deploy the new tag above with the existing
RTX 4080 SUPER/2 GiB shared memory/Dropbox GPU-required settings, no Command
override, and explicit container port **8080**. Keep original health port 8000.
Provide the actual issued HTTPS origin and private owner code. The application
URL is that real port-8080 HTTPS service address; no live URL was created here.

Set `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` to exactly:

```text
sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94
```

Before Start, configure the real operator policy's expiry, hourly rate, currency,
maximum cost, duration and retry ceiling. Missing/expired limits fail closed.
Open the mobile app, paste `examples/STUDIO_PROMPT_V4_80S.json`, keep 80s/V4,
choose SFX and press Preflight/explicit Start. No GPU terminal command or
intermediate 5-second review is required. Inspect only the completed production
in Dropbox and stop the workload manually after verifying remote delivery.

Remaining actual-run checks: NVIDIA upload/draw, complete 80s/2,400-frame output,
camera/frontier/marker continuity, sound listening and mobile playback, real
gCube routing, external Dropbox HTTP/download SHA and actual performance/cost.
The 60-minute production target is **unmeasured**. A render timeout does not stop
provider billing. No GPU/API rate, cost or completion time is fabricated.

No next plugin, automatic GPU operation or FINAL promotion is started.
