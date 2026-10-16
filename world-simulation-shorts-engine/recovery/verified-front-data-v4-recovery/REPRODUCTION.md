# V4 source-grounded partial-front reproduction

Continue this saved branch; do not rebuild the old V3 engine or repeat source
acquisition. `IMAGE.json` records the actual successful image and source commit.
The parent plan, renderer, camera, ASTRA, frontier, markers and existing claims
remain frozen. The first successful two-front image is retained in `checkpoints/`.

## CPU data reproduction

Use `/usr/bin/python3 -B` with GDAL/OSR and NumPy. From the repository root:

```bash
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery/build_front_profile.py --verify-numerical
```

This is read-only. All 26 derived files must reproduce from the committed native
map rasters, actual source-pixel trace parts, independent reference controls,
review admissions and immutable parent plan. Source pixels, retained edges,
dates, gaps, source identity and schedule must be exact. Cross-platform affine
coordinates may differ by at most 1e-10 degree and derived residuals by 1e-3 m;
this comparison tolerance does not certify historical map accuracy. Exact bytes
are compared and reported separately. No network or `/tmp` original is required.

Original document URLs and SHA, lossless raster extraction and rights limits are
recorded in the evidence files. Re-extracting a book is optional audit work, not
a runtime dependency or reason to repeat completed acquisition.

## Image and software evidence

The pinned public free-runner workflow is
`.github/workflows/verified-front-v4-recovery.yml`. Its persisted `runs/<id>-<attempt>/`
reports are the evidence of actual execution, rather than this runbook.

The workflow checks the new profile-to-inventory source closure, performs the
focused tests, numerically reproduces the source outputs, then executes actual
SwiftShader draw/readPixels before any image build. It stages only the explicit
inventory onto the immutable parent digest. It repeats the actual connected
software probe in the built image, scans default Gitleaks rules without an
allowlist, pushes a unique tag only after success, and independently pulls the
immutable digest on a fresh runner. Existing tags and images are preserved.

`FRONT_FILES.json` is the exact manifest serialized by the successful source
commit's build, not a regeneration from a later report commit. `SHA256SUMS`
records permanent files relative to this directory and excludes itself. In this
directory it can be checked with `sha256sum -c SHA256SUMS`.

The persisted PNGs show representative source dates and segment boundaries.
Check their own SHA256SUMS, actual raw-pixel evidence and pre-build versus image
hashes. Those software checks are not NVIDIA proof, an 80-second finished MP4,
or final mobile video quality approval.

Every source snapshot and the final frame also require source-suppressed versus
source-visible A/B. `sourceVisibility.cases` must show visible center-stroke
changes, unchanged protected graphics and safe area, and no changed pixel
outside the actual source stroke/halo corridor. Static native country boundaries
remain beneath the historical source line only in that corridor; the inactive
fallback retains its original boundary mask. A legacy draw-call diagnostic is
not a substitute for these actual pixel checks.

## Hardware boundary

Read `OPERATOR_RUNBOOK.md` for image-local plan binding, a deliberately blocked
approval template, detached start/status, safe storage and external delivery.
Actual paid GPU authorization, account access, pricing and billing-stop policy
are separate prerequisites. Do not reuse the old 65422 claims, fabricate an
approval, delete state, bypass hardware admission or automatically promote FINAL.

Eight approximate partial source snapshots cover 850 of 2,400 frames. The other
1,550 frames remain schematic. Unknown source accuracy, missing early fronts,
unobserved intermediate dates and missing troop positions stay unresolved.
