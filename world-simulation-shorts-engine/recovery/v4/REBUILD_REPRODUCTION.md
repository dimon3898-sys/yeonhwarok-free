# V4 equivalent recovery and reproduction procedure

Status: global `GATE_INCOMPLETE` / `USER_VISUAL_REVIEW_REQUIRED`. Actual Static Final Hold is `BIT_EXACT`; 375 V4 frames rendered and all checked Camera/Reveal contracts passed. Six of seven checkpoint PNGs matched exactly; Context differs in 43 pixels (maximum channel difference 200), and decoded MP4 comparison reported differences in 214 frames despite matching encoder SEI settings. These differences are not a full V4 PASS. Persistence, durable remote retrieval and clean Static reproduction are decided from their actual final receipts and do not remove the pending visual review.

Run these commands from the development checkout root. Preserve the 43 original files and `RECOVERY_MANIFEST.json` unchanged. New scene/scale bindings are `RECOVERED_EQUIVALENT_V4_PLAN_CANDIDATE`, not recovered historical Plan JSON. Do not repeat original searches or rewrite historical expected hashes. A fresh render and actual comparison decide whether the approved candidate reproduces the fixture.

## Permanent paths and active closure

Let `E` mean `world-simulation-shorts-engine` under the repository root. These seven files form the active browser asset/bootstrap mapping:

| Runtime URL | Repository file | Role |
|---|---|---|
| `/camera-v4-assets/context-native.png` | `E/web/camera-v4-assets/context-native.png` | Native wide/context RGB texture |
| `/static/earth-detail/v018/detail_0.png` | `E/web/earth-detail/v018/detail_0.png` | Regional RGB detail texture |
| `/height.f32` | `E/web/dem/glo30/height.f32` | Native Float32 height samples |
| `/v3/assets/v3/earth/earth-day-8k.jpg` | `cinematic-world-map/assets/v3/earth/earth-day-8k.jpg` | Global fallback texture loaded by the factory |
| `/v3/assets/gis/earth-topology.png` | `cinematic-world-map/assets/gis/earth-topology.png` | Topography texture loaded by the factory |
| `/static/fonts/NotoSansCJKkr-Bold.otf` | `E/web/fonts/NotoSansCJKkr-Bold.otf` | Pinned Korean font |
| `/three.js` | `E/web/vendor/three/0.170.0/three.module.js` | Pinned Three.js bootstrap module |

The native NE1 master at `E/library/flat/terrain/NE1_HR_LC_SR_W_DR.tif` and COG4 at `E/library/flat/dem/copernicus-glo30/originals/` are five physical build-only inputs. They are separate from derivatives and are not browser fetches. Historical `continent-native.png` is an independent NE1 crop, not the source of context, and is unused when the admitted context override is active. Its missing old file does not enlarge this active runtime closure.

The adapter serves `/runtime-config.json`, `/inputs/*.json`, `/modules/*` and the listed asset routes on loopback only. Candidate geometry arrays are actual Plan/scene inputs, not extra browser GIS downloads. Their persistence and provenance still belong in the input inventory. Archived `recovery/v4/past-paths/tmp` paths preserve old data origins; no live route may depend on a real `/tmp` session file.

## 1. Freeze inputs and install the pinned dependencies

The selected candidate uses `E/recovery/v4/equivalent-plans/REGIONAL-plan.json`, `CONTINENT-plan.json` and `scene.json`. V4 uses retained `E/recovery/v4/V4-state-records/camera-plan.json` and `input-manifest.json`. Record actual hashes in `runtime/DEPENDENCY_MANIFEST.json` and actual imports/bindings in `runtime/IMPORT_MANIFEST.json`. A changed candidate or shared input requires a new Static prerequisite.

```sh
bash tools/setup_v4_recovery.sh
```

The setup script requires installed Node 24.19.0, Chromium 154.0.8037.57, system Python 3.13.5, GDAL 3.10.3, NumPy 2.2.4 and Pillow 11.1.0. It performs frozen `npm ci --ignore-scripts` in `cinematic-world-map` and verifies Three.js 0.170.0 and Playwright/playwright-core 1.62.1. It does not render, tune candidate data or automatically install a different browser. Retain inherited proxy/CA trust and checksum verification. Generated npm cache/node_modules are setup products; locks and admitted browser artifacts are reproducibility inputs.

Run the seven-condition diagnostic in `docs/PERMANENT_GATE_POLICY.md` to identify missing persistence or evidence. A local development render may resolve this Gate's reproduction questions after its phase prerequisites pass; it cannot establish permanent persistence before the inputs are committed.

## 2. Verify or rebuild the admitted native terrain

The actual local result is stronger than pixel equivalence: NE1, context PNG and height binary all match the historical complete byte hashes and sizes:

| Asset | Bytes | SHA256 |
|---|---:|---|
| NE1 master | 699969932 | `b47bdddd1336b07f498c50eba5d70699ec57dd726a7ea0a85d2dca243236c9eb` |
| context-native.png | 23909281 | `6bafd19fd3d74d0786a52cd0f0be41863bf00b9acebf94e56edc4e2532468b4d` |
| height.f32 | 207360000 | `08a1b86fbe9c47a9495336e0e83d0bfdea014a4e5c7b36beaaa544aa283fd5a8` |

The tool reads the exact NE1 native RGB window `[11222,1605,3054,5065]`, writes 3054×5065 uint8 RGB without resampling/color operations and verifies decoded native-pixel equality. Current pinned Pillow 11.1.0/zlib 1.3.1, PNG compression level 6 and optimize=false also reproduced the historical PNG bytes. Independent verification compared all 15,468,510 pixels with zero differences.

Height uses the four preserved native 3600×3600 Float32 COG bands. Atlas offsets are `[0,3600]`, `[3600,3600]`, `[0,0]`, `[3600,0]` for N29E032, N29E033, N30E032, N30E033 respectively. Serialize a 7200×7200 north-up C-order `<f4` array; no header, row flip, interpolation, scale/offset, masking, NoData substitution or datum transform. All 51,840,000 samples are finite and independently bit-equal to their original tile positions.

After exact sources are hydrated, rerun with a new evidence file:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/tools/v4_recovery_terrain.py \
  --evidence /absolute/private/new-terrain-build.json
```

Initial acquisition may explicitly use `--ne1-source /path/to/verified-download` or `--download-ne1`. The latter uses only the pinned public URL from `ORIGINAL_SOURCE_RECORD.json` through inherited proxy/CA trust and accepts only the original SHA/size. It admits no replacement dataset. Existing outputs are verified/reused without overwriting; repeated execution preserved all seven source/derivative files' size and mtime. The frozen missing-original manifest remains unchanged.

## 3. Run Static, then compare every decoded pixel

Prepare an existing private parent directory outside the checkout and choose a new output directory. The CLI creates that directory exclusively, starts its own loopback server and browser, and closes its own processes after capture. It has no golden-image rendering input.

```sh
node world-simulation-shorts-engine/recovery/v4/runtime/render.mjs \
  --mode static --output-dir /absolute/private/new-static-run
```

The CLI itself runs `/usr/bin/python3 -B tools/compare_v4_png.py` against the two actual files and writes `static-final-hold.comparison.json`. Its `--golden` defaults to `recovery/v4/approved-proof/07_FINAL_HOLD.png`; this is an external comparison input and is not passed to the renderer. The fixed reference PNG SHA is `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673` and decoded top-down RGBA SHA is `cee0e480f1a0941f13d7bbe675952abe5a3bef53dd0bcc44c001f856982e7376`. The comparator returns exit 0 only for `BIT_EXACT` or `PIXEL_EXACT`, with complete-image decoded RGBA equality. Require 1080×1920, zero changed pixels and zero channel difference. Preserve both PNG hashes and decoded RGBA hashes. A masked comparison, visual resemblance, selected glyph matches or a render exit 0 is insufficient. A mismatch stops here; do not start 375-frame V4 or Camera V5. Maximum visual/reproduction correction iterations: three.

`runtime-diagnostic.json.static_comparison` preserves the comparison path, report, passed state and actual command. A mismatch retains the actual PNG/diagnostic, returns CLI exit 1 and records status ERROR. `runtime-diagnostic.json` records actual invocation, source commit, required-input hashes, times, output PNG/raw RGBA hashes, backend and errors. `RENDERED` reports capture completion, not comparison PASS or clean-environment reproduction. The approved original PNG is comparison evidence, never a fresh generated output.

## 4. Run checkpoints and all 375 V4 frames only after Static PASS

Bind the actual successful Static diagnostic/comparison to unchanged source and shared input hashes. The CLI guard re-decodes its actual output against the fixed verified reference and permits only BIT_EXACT or actual decoded PIXEL_EXACT with the approved decoded hash; a missing, stale or forged receipt blocks V4 startup.

```sh
node world-simulation-shorts-engine/recovery/v4/runtime/render.mjs \
  --mode checkpoints --frames 0,330,374 \
  --static-receipt /absolute/private/new-static-run/runtime-diagnostic.json \
  --output-dir /absolute/private/new-checkpoint-run
node world-simulation-shorts-engine/recovery/v4/runtime/render.mjs \
  --mode frames \
  --static-receipt /absolute/private/new-static-run/runtime-diagnostic.json \
  --output-dir /absolute/private/new-375-frame-run
```

Frames mode defaults to every integer frame 0–374. Preserve each PNG/diagnostic and the aggregate runtime diagnostic. Verify saved checkpoint contracts, camera/reveal/layout results and full frame count; passing three frames is not a claim about all 375. Encoding 30-fps, 12.5-second MP4 is a later phase using an inventoried encoder/procedure after required checks and authorization. This document does not invent an unverified encoder invocation.

## 5. Persist and reproduce from a clean checkout

Preserve Source+Assets+Manifest+input data+locks+setup/build/render/comparison procedures in the development branch, separate from public MP4/PNG Proof. Keep original files immutable and new equivalent bindings explicitly identified. A local exact terrain build and an uncommitted successful render do not satisfy permanent persistence.

LFS attributes now target only `E/library/flat/terrain/NE1_HR_LC_SR_W_DR.tif` and `E/web/dem/glo30/height.f32`. Commit exact pointers and reviewed attributes in the development branch, verify local hydrated bodies, verify a separate clean checkout can retrieve all required bodies from the approved durable remote, and preserve current-commit LFS/fetch evidence. Cloud-local objects or a copied cache alone leave availability incomplete. Do not upload/publish from this procedure without the applicable authorization.

Use the committed approved invocation in a separate clean checkout of the same HEAD and preserve its new output, command log and full input/manifest bindings in a private `fresh_clean_environment_reproduction` receipt. `runtime-diagnostic.json` alone is not this receipt. Run `tools/v4_recovery_gate.py` with explicit receipt/clean-checkout and, when needed, LFS receipt/checkout arguments. Missing temp closure, actual receipt, durable retrieval evidence or any of seven PASS conditions leaves `GATE_INCOMPLETE` and blocks the next development Gate/Camera V5. Even if all seven technical/persistence conditions PASS, the global V4 Gate remains incomplete while `USER_VISUAL_REVIEW_REQUIRED` is unresolved; clean Static success is not complete V4/MP4 acceptance.

## Recorded end-stage result and stop condition

- Static Final Hold: actual `BIT_EXACT`.
- V4 rendering: 375 frames produced; all checked Camera/Reveal contracts PASS.
- Checkpoint comparison: 6/7 PNGs exact; Context 43 changed pixels, maximum channel difference 200.
- MP4 comparison: 214 decoded frames differ; encoder SEI/settings match. This is `USER_VISUAL_REVIEW_REQUIRED`, not decoded-video equivalence or full V4 PASS.
- Additional REG242 geometry candidate: 56 changed Context pixels, rejected. The bounded search is stopped; preserve the rejection evidence and do not expand bounds search automatically.
- Permanent result: review the actual development commit, LFS remote/clean-checkout and clean Static receipts separately. Local correctness and eventual seven-condition PASS cannot waive the remaining visual decision.

Preserve the actual media and comparisons for user visual review. Global `GATE_INCOMPLETE` remains until acceptance or a newly authorized successful correction. Do not start Camera V5 automatically.
