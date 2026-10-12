# Camera Director V5 final baseline

The user reviewed the actual `SUEZ_CAMERA_DIRECTOR_V5.mp4` and approved the
Camera Director V5 candidate. This record supersedes the candidate's pending
review disposition. Historical candidate manifests, reports and instructions
remain unchanged and retain their original status.

The approved runtime, assets, build inputs, plans and review media are pinned to
`941860391aa740772f822f18a972aeeca20a4a7f` on
`development/camera-director-v5-20261012`. The final metadata commit records the
freeze; it does not introduce a different camera or render. The final baseline
is `V5_CAMERA_DIRECTOR_FINAL_BASELINE` / `V5_FINAL`. Its V4 parent is
`V4_RECOVERED_EQUIVALENT_BASELINE`, not a lost temporary historical V4.

## Preserved behavior

Minimum Sufficient Context can either expand or skip expansion. The far-event
fixture requires expansion; near-event and already-sufficient fixtures skip it.
Suez's skipped expansion does not disable this generic feature. Natural
Turnaround, pan/zoom phasing, deceleration, unchanged V4 Reveal and all protected
visual, geographic anchor, REGIONAL endpoint and LOCAL admission behavior stay
unchanged. None of these systems is tuned during this freeze.

## Permanent completion rule

Every development Gate requires all seven conditions:

1. `SOURCE_PERSISTED`
2. `ASSETS_PERSISTED`
3. `HASH_MANIFEST_PASS`
4. `DEPENDENCY_MANIFEST_PASS`
5. `IMPORT_MANIFEST_PASS`
6. `NO_REQUIRED_TEMP_FILES`
7. `CLEAN_ENV_REPRODUCIBLE`

A video or PNG alone cannot complete a Gate. A failed condition means
`GATE_INCOMPLETE` and blocks the next stage. Run the final storage validator
before beginning the next development Gate. A later implementation needs its
own persisted source/assets/manifests and fresh clean reproduction evidence;
this V5 receipt cannot certify changed source. User approval of this Camera
Director does not automatically start Event System, Route, TTS or Planner work.

## Validate the saved final state

From the development repository root with the pinned toolchain and hydrated LFS
assets:

```sh
/usr/bin/python3 -B tools/validate_v5_final.py --repo . --require-persisted
```

The validator never installs, renders, changes Git or adjusts the Camera. It
verifies the approved 112-file payload, original candidate/media manifests,
actual Git body persistence, final evidence, all 250 frame hashes and diagnostic
records, all seven checkpoints, media properties, used/skipped Context tests and
the secret scan. A precommit inspection cannot produce `V5_GATE_COMPLETE`.

`FINAL_HASH_MANIFEST.json` binds all required candidate and final verification
files. `BASELINE_MANIFEST.json` binds that inventory. Neither includes its own
hash or metadata commit, avoiding circular bindings. The immutable source
commit inside the baseline remains the approved candidate commit; the metadata
successor commit identifies the saved freeze externally.

## Clean reproduction

Use an independent remote checkout of the approved commit, with no local Git
alternates, copied payload, shared package cache or external asset mount. A
sparse checkout may contain the complete manifest-declared closure instead of
unrelated projects. Recover the two tracked LFS pointers from this repository's
remote LFS storage and verify their exact SHA and size. This retrieves saved
data; it does not acquire a new dataset. The clean run recorded here used native
`git lfs smudge` on each exact pointer after generic partial-clone discovery was
stopped for unnecessary storage use. Same-checkout hardlinks to freshly fetched
LFS objects only avoided duplicate disk storage; all runtime paths are ordinary
repository files with verified bytes and no outside-cache dependency.

Install the unchanged npm lock with `npm ci --ignore-scripts --no-audit --no-fund`
and a new cache inside this checkout's `.git` directory. Preserve TLS and package
integrity verification. Validate Node 24.19.0, Three 0.170.0, Playwright/Core
1.62.1, Chromium 154.0.8037.57, FFmpeg 7.1.5, system Python 3.13.5, GDAL 3.10.3,
NumPy 2.2.4, Pillow 11.1.0 and zlib 1.3.1. Never upgrade to match an output.

Run the 21 Camera tests and compile inputs into a new private directory. Compare
those three files with the saved inputs. Use the unchanged capture CLI with
`--phase checkpoints` first: its first capture is the static, random-access
Final Hold, evaluated at the locked endpoint without running an animation.
Require zero decoded RGBA difference before `--phase video`. All capture output
directories are newly created outside the checkout and are output destinations,
not required inputs. Then compare the actual 250 rendered PNG/raw RGBA hashes,
Camera/Reveal plans, frame diagnostics, checkpoints and decoded H.264 frames
against the approved candidate. No old MP4 or reference PNG is a render input.

The receipt certifies an independent checkout on the same pinned CPU toolchain,
not provisioning of another cloud machine. Required runtime/build files must
remain retrievable from development Git/LFS; session caches are not preservation.

## Development and public review

Development retains Source, Assets, Build Inputs, Plans, Manifests and internal
verification evidence. Public review contains only MP4, PNG and optional
`SHA256SUMS`. Do not copy Source, internal Plans, diagnostics or credentials into
a public Proof branch or Release. This freeze leaves approved review media,
the V4 baseline, main, Releases and tags unchanged.
