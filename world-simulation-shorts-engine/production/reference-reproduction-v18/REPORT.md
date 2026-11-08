# Reference reproduction: presentation input correction and free evidence

**Presentation input correction is verified. Full reference quality remains BLOCKED.**

Latest evidence base: v17 audit 5aed991e5cddc3144af08c6bc2ab1254edbaac2c.
The v16 worker image build 42446481907 remained successful; its digest and runtime
closure were reused. Original branches, input JSON, images and earlier PASS were preserved.

## New result

- Two corrected 10-second inputs are in `ready-a4/`. Their corresponding
  `COMPILED_REQUEST_01.json` and `COMPILED_REQUEST_02.json` contain the formal Scene
  JSON and presentation bindings. All factual Scene objects equal the preserved
  original compilation. History, geometry, dates and GENERAL admission are unchanged.
- Existing HERO pins replace small event pins. Labels and contextual places are
  explicitly timed; input label gaps are zero in both clips. The baseline first
  clip had 100 frames without any authored label.
- The geographic tint alpha changes from 0.52 to 0.14, exposing more source relief.
  Camera stops are wider and arrive earlier, allowing more reading time. No new
  historical ownership or military front geometry is invented.
- The first new candidate exposed a three-frame HERO conflict. Ending the preceding
  direction highlight five frames earlier fixes it. A separate boundary comparison
  found label-position jumps; contextual labels now fade before the relevant seams.

## New free validation

| Scope | Result |
|---|---|
| Existing NvidiaPresentationController._normal → compiler → source admission | Both changed inputs PASS; no submit/start |
| Existing layout + pinned font in Chromium | 600 layout frames, zero failures |
| Same persistent labels/camera at two scene seams and one clip seam | 3 PASS in continuous layout evaluation |
| New camera coverage and all-state viewport checks | 600 camera frames PASS; details in CAMERA_COVERAGE.json |
| Existing runtime's sparse CPU diagnostic stills | 13 initial + 7 affected frames PASS |
| Actual new NVIDIA MP4 / final 20-second composition | NOT RUN |

Actions evidence:
https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/42451035648
https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/42451652447

Artifact 13605413527 SHA256 0858bafed9f039cd883fef462510bf84d73cbccb2813d0fe0c20fa316bc447da.
Artifact 13605708512 SHA256 2b4f8d2419e5998d72b922b05a4e617cd30788b00af0f85e981507cf043836c9.
Summaries are retained in this repository. Diagnostic PNGs remain in the linked Actions artifacts.

Sparse stills skip intermediate layout history. Their date positions can therefore
differ from a continuous capture; they demonstrate pixel styling and source output,
not temporal seam continuity. The separate Chromium check follows every layout
frame in order. Actual NVIDIA video motion and continuity still require the user-run
formal output. No sparse still or layout result is promoted to reference-video PASS.

## Remaining blockers and next minimum work

The new diagnostic visibly improves pin emphasis and terrain exposure, but remains
a regional map with generalized coastlines and nearly flat offshore source imagery.
The surface data were not upgraded. At the authored final views the source window
contains about 922×1309 pixels (Naktong), 724×1029 (Incheon), and 597×847 (Seoul),
still below the 1080×1920 output. These numbers are sampled source pixels, not a
claim of newly resolved detail.

The native renderer already accepts real `heightSource` data, but Studio's current
presentation runtime does not pass it and sets `dem:false`. Next: qualify suitable
surface/coastline and height data, then connect that existing capability through
the formal source contract with truthful coverage, metadata and diagnostics.
See DATA_AND_CONNECTION_AUDIT.md for the exact connection and checked source options.

The mobile two-MP4 composer UI also remains unconnected. Existing composition is
retained; it is not used to replace missing generator features. HISTORICAL mode
remains blocked. Do not start a paid render merely because these presentation
checks passed. These inputs are review candidates, not a declaration of reference
quality or GPU readiness.

Runtime source changes 0; image builds 0; deployment changes 0; GPU starts 0;
Studio renders 0; MP4 encodes 0; old PASS suites rerun 0.

## Resumed Work on 2026-11-08

Recovered unpublished completed evidence at eaf477e without running old checks.
The preserved A1 layout failure contains 3 frames (100–102), not the 32 frames
reported in the handoff summary. The separate reported 113 PASS has no located
original suite receipt and is not promoted to a newly verified result.

One Copernicus GLO-30 Incheon tile was acquired and decoded (3600×3600 Float32,
EPSG:4326, no missing or nonfinite samples). This is one modern DSM tile only.
EOX2016 imagery was downloaded and rejected: conspicuous white gap, clouds,
and visible coastal mosaic seams. It also does not cover the initial wide view.
No candidate source was installed, no production runtime was changed, and no
new image, diagnostic render, MP4, or GPU run was made by resumed Work.
See SOURCE_QUALIFICATION.md and evidence/source-qualification for the exact
URLs, hashes, source scope, and minimum remaining implementation boundaries.
