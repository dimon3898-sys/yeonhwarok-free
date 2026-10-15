# Visual quality upgrade V1 — implementation and evidence

## Scope and evidence limits

This task prepares a separately versioned candidate image from source a7df81f and immutable parent image sha256:8aba498e295b45a9cbfa29eeacd6f7779ff3d2ce4482c92215176be1540ff71a. Original sources, prior images, saved jobs and approved videos are preserved. Supplier research, original CPU/data/cache/upload, NVIDIA admission, detached supervisor, FFmpeg and Dropbox adapters are reused rather than redeveloped.

No existing actual ASTRA GPU MP4 or current capture locator was supplied in this request. A download URL/capture ID was requested while independent work continued. The findings below are source/data/CPU or explicitly marked actual software-render observations. They must not be represented as a visual inspection of an unavailable NVIDIA video. Real GPU deployment and paid rendering are not performed here.

## Confirmed findings and minimal changes

| Item | Confirmed cause or behavior | Candidate action |
| --- | --- | --- |
| A: source support boundary | Old shader fades the rectangular source bbox over one source pixel; internal invalid cells and DEM invalid-neighbor boundaries return baseline immediately | Per-role true support masks, distance to unsupported cells, continuous screen-sized feather; preserve source sampling and separate native coastline coverage |
| B: territory readability | Saved fill alpha .61/.62 retains38–39% of variable ASTRA background | Generic opacity floor .72, preserving source RGB hues and at least28% terrain contribution in this fixture |
| Actual territorial change | Original evaluators show real expansion over all150frames | Preserve geometry, classifier, events and timing; no invented expansion |
| C: frontier | Existing pass already uses the actual same-frame boundary and combined terrain texture, screen pixel widths and measured motion energy | Reuse unchanged; D is an explicit unchanged control, not an invented repair |
| D: camera priority | Original land-clipped front projection drifts relative to the visual focus | Smallest safe scene-only candidate selected from bounded candidates; same camera core, roll/time/data; E separates this variable |

The150-frame fixed-grid, latitude-weighted domain estimate uses4,326 land samples. Winner area changes44.923%→69.205% with monotonic advance; this is an approximate CPU coverage estimate, not surveyed area. The boundary is still moving at output frame149. A fabricated terminal stop/fade/hold would misstate the saved event. A synthetic actual-stop fixture instead verifies the existing frontier energy settles to .08.

Territory opacity is a profile rule, not a country/faction color branch. It preserves original color RGB and has bounded gain/floor/ceiling. Synthetic background blend tests show roughly17% greater faction color separation; actual-render measurements are recorded separately by the A/B probe, and neither is user approval.

## Supported-data boundary treatment

The original verified upload layer remains the source of raw Float32 heights, signed Int16 bathymetry and encoded surface colors. A small bounded WebGL readback derives only actual support booleans: valid finite DEM center plus four valid finite neighbors; valid negative bathymetry; valid nontransparent surface cells. It does not read back or alter source values into a new synthetic terrain dataset.

An exact distance transform includes internal holes and outer source support. A new source-stage material pass blends its contribution toward the original material over a32-output-pixel default, using the current camera scale and actual source transform to convert units. This blends contribution weights; it does not interpolate missing heights/depth or move source coordinates. Original native same-frame GIS coverage independently gates land versus sea, so the coastline itself is not blurred into a support mask. Unsupported pixels and NoData use baseline.

The three data roles retain independent support and fade widths. Source limits, signed depths, original validity, pixel centers/rows, native resolution and provenance remain intact. The samples remain regional/partial; full-world detailed coverage is not claimed. Height affects normal lighting and bounded altitude tone as before; this task does not add mesh displacement.

## Data-driven camera candidate

The pure planner samples the original actual land-clipped front across150frames and evaluates small generic zoom/centering candidates. It chooses the first sufficient candidate rather than maximum zoom. Each candidate must respect the original native envelope, inherited minimum framing scale, continuity bounds, visible front margin and unchanged unit layout protection.

For the saved fixture the selected candidate uses maximum nominal zoom1.04 and centering gain .25, ramped through the existing camera keyframes. CPU projected front-focus RMS improves123.94→101.62px (about18%); mean front width547.45→559.31px; minimum sampled front margin31.44→50.18px; maximum center step5.035→4.993px/frame. All150 unit-layout frames remain safe with critical collisions0. These are framing proxies, not a GPU quality verdict. The initial framing, roll values, event frames, expansion speed, unit design and geography remain unchanged. No global slowdown or invented final event hold is introduced.

## Selected path and compositing

```text
new explicit one-shot quality job F
→ fixed quality launch adapter over original ASTRA launch/admission/storage
→ fixed official Node module-resolution adapter over original ASTRA capture/encoder
→ quality runtime + original source/data/browser boot
→ original camera/GIS/coverage
→ original baseline material + quality ASTRA source material
→ original territory shader with optional bounded opacity profile
→ unchanged actual-boundary frontier and terrain lighting
→ original presentation/postprocess
→ original flags and military artwork
→ original150-frame encoder/export verifier + strict F profile receipt
```

Browser import maps select only explicit source-material and territory factory dependencies. Original ASTRA browser boot is reused. The Node resolver remaps only the old capture module's exact literal runtime import to the new fixed module; all other imports delegate normally. It does not rewrite original source text or offer an environment-selected command/runtime. Source signatures bind new runtime/profile/derived Scene and manifest, and production requires fresh original NVIDIA/WebGL2 admission with the same browser/backend.

Profile F completion requires the actual new material/territory diagnostics for all150frames, not merely an adapter label. Any new quality/source verification failure blocks export and records failure for only the current new capture. The original source, GPU guard, budget monitoring and seven-file verifier remain required.

## Independent comparisons

| Variant | Boundary | Territory | Frontier | Camera |
| --- | --- | --- | --- | --- |
| A | Original | Original | Original | Original |
| B | Distance feather | Original | Original | Original |
| C | Original | Contrast profile | Original | Original |
| D | Original | Original | Unchanged audited control | Original |
| E | Original | Original | Original | Candidate |
| F | Distance feather | Contrast profile | Original | Same candidate as E |

Actual SwiftShader draw/readPixels uses the real saved data/geometry and outputs at1080×1920. A/B, A/C and A/D comparisons keep camera, event clock, output and data fixed. A/E is explicitly the camera study. E/F compares integrated material changes under the same candidate camera. Separate small synthetic GL probes test per-role support/NoData discontinuities under controlled backgrounds; they are not actual scene data or hardware video evidence.

Expected evidence includes variant raw hashes, actual diagnostics, source/scene/camera bindings, frame metrics, saved PNG hashes, protected-source checks and explicit test-only/backend flags. Required phases must pass before image publication. New-image checks run the actual selected path again, and another runner pulls the immutable digest and verifies the closure.

## Files and reuse

New files are confined to `recovery/visual-quality-upgrade-v1/` and `.github/workflows/visual-quality-upgrade-v1.yml`.

| Group | Purpose |
| --- | --- |
| distance_support.mjs, support_gpu.mjs, quality_material_core.mjs, quality_material.mjs | Actual support distance and source-stage material factory |
| territory_style_core.mjs, quality_territory.mjs | Generic opacity profile over the unchanged original shader |
| quality_profiles.mjs, quality_runtime.mjs, quality_adapter.mjs, serve_quality.py | Explicit A–F selection, bounded Scene camera, exact loopback/import-map lane |
| prepare_quality.py | Original provider/upload preparation, distinct private quality activation and extension verification |
| capture_quality.mjs, launch_quality.py, job_quality.py | Fixed native entry, original capture/encoder/storage reuse, distinct detached one-shot identity |
| software_probe.mjs, support_ab_probe.mjs, tests/, audit_control_frontier.mjs | Focused CPU and actual software A/B; separate synthetic and real-data evidence |
| ci.py, Dockerfile, workflow, manifests/reports/checksums | Unique additive image, free standard runner, strict inventory, secret scan, independent pull and permanent recovery evidence |

No original FINAL/V4/camera/territory/frontier/data/provider/encoder/storage/old manager source is edited. No old claim is reset, no image is overwritten, no dataset is re-acquired, no camera core is copied. Required temp-only source/asset/recipe files remain0; private bundles are reproducibly derived from the persisted parent assets.

## Remaining hardware and review gates

After separate user authorization: NVIDIA upload/draw; actual supported-region seam/coast/NoData behavior; territory readability and frontier alignment; camera rhythm; flags/units; VRAM/shared-memory/per-frame performance; complete MP4 decode; Dropbox remote synchronization and original-download HTTP200/SHA equality; reference/mobile visual comparison. The task does not claim that code/software PASS meets the reference's visual quality.

Use GCUBE_EXECUTION.md and the immutable image recorded in IMAGE.json after reviewing this candidate. No deployment, paid rendering, fourteen-second extension or FINAL promotion follows automatically.
