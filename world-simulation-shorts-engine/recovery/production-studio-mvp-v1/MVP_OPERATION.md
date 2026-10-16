# Production Studio MVP: operator procedure and limits

This is an additive mobile production application. It does not deploy or stop a
GPU, perform historical research, generate TTS/subtitles/BGM, or promote FINAL.
The user deploys and stops the workload manually. Image publication and CPU
tests do not constitute an actual NVIDIA production-video approval.

## Deployment after explicit user approval

Use the unique Studio candidate recorded in `IMAGE.json` only after its build
and independent digest-pull evidence exists. Never substitute the old parent
image for the Studio image. Preserve old images, completed media and job claims.

Retain the previously working RTX 4080 SUPER 16 GB configuration, 2 GiB shared
memory, provider-assigned NVIDIA devices, `NVIDIA_DRIVER_CAPABILITIES=graphics,utility`,
`WORLD_ENGINE_RENDER_MODE=gpu-required`, `WORLD_ENGINE_STARTUP_MODE=normal`, and
Dropbox mounted at `/world-storage`. Leave Command override empty. The new
wrapper runs the unchanged original startup/health child; port 8000 stays the
original health service. Explicitly select container port **8080** for the mobile
application; do not let port auto-detection choose health-only port 8000.

Configure these values in the workload settings, without putting credentials in
chat, Scene JSON, GitHub, an image or a public folder:

- `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN`: the actual HTTPS origin issued for this
  workload's port-8080 service, without a path or trailing slash.
- `WORLD_ENGINE_STUDIO_OWNER_CODE`: a new private owner access code of 16–256
  printable non-space ASCII characters. The application writes it once to a
  local owner-only file and removes it from child environments. It does not
  invent a code, rotate an existing file, or reuse a gCube API token.
- `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST`: only the actual `sha256:` digest from
  `IMAGE.json`, without a repository prefix or `@`. The full immutable image
  reference belongs in the gCube image field, not this environment variable.
- `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON`: an actual operator-approved JSON
  object containing `validUntil`, `maxWallSeconds`, `maxRetries`,
  `maxCostAmount`, `currency` and `gpuHourlyRate`. Rates and budgets have no fake
  defaults. Missing or expired policy blocks Start. Render timeout does not stop
  provider billing; stop the workload manually after verifying the result.

The private state root defaults to
`/var/lib/world-engine-private/engine/production-studio-mvp-v1`. Dropbox is a
shared export mount, not a trusted private claim/authentication directory. A
container replacement can lose ephemeral private state. Retain an approved
private POSIX volume if cross-container claims/cache/authentication must survive;
never point private state at Dropbox to bypass its security requirements.

The actual gCube HTTPS forwarding/Host behavior and a physical phone session
remain deployment checks. No fabricated public Studio URL or verified SSO claim
is provided. After deployment, open the actual port-8080 HTTPS address and log
in with the owner code; terminal commands and intermediate scene review are not
part of normal production use.

## Production input and Start

Paste `examples/STUDIO_PROMPT_V4_80S.json` for the preserved 80-second fixture, or
attach a complete verified native Scene JSON. This is a structured-input parser,
not a free-form research/planning AI. Sources, geography, timelines and events
must already be supplied and verified outside the app. Missing fields are
reported instead of invented.

The V4 archival preset is exactly 80 seconds, 2,400 frames and 12 chapters. Its
eight source fronts are partial and approximate; original projection and full
absolute accuracy remain unknown. It is not a complete precise historical
occupation reconstruction. Other supported lengths (120/180/300/600 seconds)
require a verified complete UNIVERSAL_V3 plan for that duration; the app does
not stretch this archival fixture into invented history.

Run Preflight, inspect the actual admission result and configured limits, give
explicit owner consent, then press Start once. Authentication, CSRF, input/source
integrity, original GPU admission, storage, resource and claim checks remain
mandatory. The original detached manager owns actual rendering and scene caches.
Closing the browser does not start a new job. A restarted container does not
automatically resubmit work. Progress reports observed counts and elapsed time,
not an invented completion estimate.

## Audio and interval revisions

Original licensed SFX are bound to actual supplied timeline event IDs and frame
positions. SFX ON/OFF and gain are supported. The existing renderer first
produces and verifies its original silent result; the additive stage mixes SFX
and copies the existing H.264 video stream into the final audio MP4. An optional
SFX WAV is available. This leaves old silent-only contracts unchanged.

After a completed job, enter a half-open time interval and a supported command,
for example `효과음 음량 50%`, `효과음 끄기`, or a structured SFX revision. The app
previews the impact; explicit Start creates a new version, reuses verified silent
video and GPU scene caches, updates audio and recomposes. Old versions remain.
An SFX cue is selected by onset frame; an existing sound tail begun before the
interval is retained. Changed tails or local neighboring cue admission can
extend past the requested endpoint. The preview reports conservative audio
sample intervals and adjacent scenes rather than promising that these tails
stop at the selected second. Focused PCM tests verify unchanged samples outside
the reported bounds; this is not a claim of identical AAC bytes. Exact
restrictions are in `PROMPT_INPUT_CONTRACT.md`.

**Camera/territory/frontier interval editing is not implemented by this MVP.**
The preserved V4 execution contract admits only its exact derived plan, and
closer framing is not authorized by its current camera admission. Such requests
must return an explicit unsupported response. A newly verified visual Scene JSON
can be submitted as a new production, with normal cache invalidation; this is
not claimed to be a local visual revision. Actual partial GPU revision success
has not been demonstrated.

## Completion, recovery and Dropbox

Completed versions contain `WORLD_ENGINE_STUDIO_VIDEO.mp4`, `SHA256SUMS`, a safe
`QUALITY_SUMMARY.json`, and optionally `SFX.wav`, inside a newly generated export
directory. Plans, raw source data, approvals, private state and diagnostic logs
are never downloads. Mounted readback and SHA checks do not prove external
Dropbox synchronization. Confirm the same files in Dropbox and compare an
actual external download's hash before treating remote delivery as verified.

Owner-authenticated status and downloads are available after reconnecting.
Explicit recovery must preserve original claims, successful scene caches,
original deadline, retry ceiling and cost authorization. It must not reset a
failed claim, run concurrently with an existing renderer, or retry automatically.
No 80-second NVIDIA run, 60-minute performance goal, actual external Dropbox
delivery or final visual approval is certified by free CPU/software tests.
