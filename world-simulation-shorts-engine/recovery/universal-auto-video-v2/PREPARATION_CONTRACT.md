# Universal video preparation

`prepare_video.py` completes an offline plan using a reviewed catalog-native
fixture. `HISTORY_CATALOG.json` owns the initial topic-to-fixture association;
core logic contains no country name, historical date or coordinate selection.
The catalog now binds the original runtime fixture by SHA-256. The resulting
`NATIVE_PAYLOAD.json` binds its five original native JSON inputs by exact hash.

Before marking the renderer binding `READY`, preparation reads those actual files
and checks the event anchor, primary country, complete primary geometry, output
resolution, native camera FPS, V5 version, final extent and lock-before-event
ordering. This verifies data/configuration bindings; it does not claim that a GPU
render or visual quality test occurred. The frozen native camera fixture currently
supports 1080×1920 at 30FPS. Other timing settings can be planned, but native
preparation rejects incompatible resolution/FPS rather than changing the camera.

## One topic to a bound plan

For a production job, use an existing private 0700 directory owned by the engine
UID. Output plans are exclusively created as 0600 and never overwrite a previous
plan or payload. The example duration is supplied in the topic, not fixed in the
algorithm.

```sh
/usr/bin/python3 -B /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-auto-video-v2/prepare_video.py \
  '한국전쟁의 전선 변화를 80초 영상으로 만들어줘.' \
  --image-digest 'sha256:<actual newly published image digest>' \
  --output /var/lib/world-engine-private/engine/universal-video-v2/request/PLAN.json
```

`WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` may supply the same operator-controlled
value when the flag is omitted. Only a `sha256:` prefix followed by 64 lowercase
hex digits is accepted. An immutable digest is recorded as operator configuration,
not as container self-attestation. The hardware wrapper must compare it to its
trusted deployment configuration. This step does not grant cost authorization.
The separate private approval must match the final plan hash, image, finite time,
cost, known GPU rate, retry cap and expiry before paid work can begin.

A plan prepared without the digest records `IMAGE_BINDING_REQUIRED`; the checked-in
80-second fixture is deliberately in that state. It has a native `READY` binding,
but is not authorized or paid-runnable. Supply the published digest when creating a
new runtime plan, then create approval for that exact immutable plan. Never mutate
a plan after issuing approval.

## CPU data preparation and recovery

`prepare_job_inputs(plan_dict, private_job_root)` is the coordinator API. It:

1. Revalidates the complete plan and native payload against actual preserved files.
2. Runs the staged additive-source verifier and all inherited frozen manifests.
3. Creates a private `runtime-inputs` child, with a lock independent of old jobs.
4. Invokes original `prepare_ref2.prepare_activation(..., variant='F')` once under
   an exclusive new attempt directory. The inherited fictional five-second scene
   supplies immutable source/data closure only; it is not rendered or substituted
   for the historical event plan.
5. Calls the old `loadReferenceRuntimePlan` CPU-only loader to verify the original
   activation/profile/bundle/source contracts without opening a browser or GPU.
6. Hashes every generated file and exclusively stores a complete receipt bound to
   the full approved plan, source, renderer and overlay manifest.

Resume reuses that receipt only after every generated hash and old activation
validation pass again. A corrupt receipt, altered part, symlink, path escape or
changed plan fails closed. Incomplete attempts are preserved and never registered
as successful inputs. One later explicit recovery attempt may create a new
attempt directory; the maximum is two preparation attempts. No automatic loop,
claim reset, source deletion or old result overwrite is provided.

The returned dictionary contains `activationFile`, `activationSha256`, `cacheHit`
and `gpuExecuted: false`. This is the same prepared data closure reused across
all scenes of a job. Image publication, NVIDIA rendering, billing stop, final MP4
and external Dropbox download remain separate measured checks.
