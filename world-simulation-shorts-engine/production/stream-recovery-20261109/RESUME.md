# WORLD ENGINE stream recovery — 2026-11-09 KST

## Recovered evidence

- Preserve `integration/dot-public-review-20261109` at `5d749200684406ad66a6a381e04d5a31a3ef7b05`.
- Recovered latest material/label candidate: `validation/dot-cpu-visual-20261109`, `22a93a6d952ab82ee8cd888efbcf054089c3c895`.
- A9 run 42525854674: remaining baseline PNGs completed. Existing baseline set totals 13.
- A10 run 42526690755: 12 actual PNGs; labels, date positioning, and three scene boundaries accepted.
- A11 run 42527984819: one affected Incheon frame; candidate water contribution reduced to 20 percent; changed-scope CPU visual review accepted.
- Actual PNG archives remain in the existing private backup destination. No private rasters, registry paths, or imagery are published by this recovery.

Read `CPU_CHANGED_SCOPE_REVIEW.json` and `A11_CHANGED_SCOPE_REVIEW.json`. The PASS is for the observed CPU material/label delta. It does not certify a full 600-frame movie, NVIDIA execution, historical coastline, or reference-video parity.

## Saved versus recovered

The original branch advanced during recovery. Preserve the ongoing branch; do not force-update it. `BUILD_HOST_AVAILABILITY.json` and `NATIVE_PACKAGING_PIN_REVIEW.json` were initially local-only but were subsequently published in 22a93a6d. Reuse them without another tool/auth probe. No prior new image-build draft was found. Any build draft next to this file is newly prepared and explicitly inactive.

## First incomplete stage

Qualify the new image source closure and manifests. Two generated variant hashes differ from the old recorded manifest; this is a new candidate binding task, not grounds to rerun previous PASS tests. The final manifest must also bind the accepted A11 shader, unchanged A10 label module, native controller/worker modules, and private registry/source asset destination paths. The local files named V16_BASE_RUNTIME and V16_BASE_STARTUP are pre-v16 baselines and must not be substituted for the published v16 manifests.

Preserve the v16 image digest `sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b`. New immutable image publication, backup identity, and user deployment input files remain unproven.

## Execution boundaries

Do not rerun the existing 21 checks, nine syntax checks, baseline 13 PNGs, A10 12 PNGs, or A11 frame without concrete invalidation evidence. Do not retry local UNIX sockets, local image-building tools, or local GHCR credentials. Do not launch, render, stop, or modify a paid GPU workload. Actual deployment/render/stop is user-only. A draft configuration is not a saved live gCube configuration.
