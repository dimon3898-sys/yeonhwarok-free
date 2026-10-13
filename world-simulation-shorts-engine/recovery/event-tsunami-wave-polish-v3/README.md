# Tsunami Wave Visual Polish V3

This candidate changes only the tsunami-wave visual extension and its fixture data. The entire Area Candidate at `17557113f628a724aafca839a158899e7927210b` remains immutable, including Area Core, Front Line, State Transition, Time Step, native Camera V5, terrain material, region colors, markers and layout.

The implementation keeps FACT_BASED_VISUAL_GRADE. Authored wave fronts and staggered coastline contact are illustrative geographic graphics. They do not assert physical wave speed, height, exact arrival time or inundation extent. Historical event origin and coastline relation come from the retained parent fixture.

Storage order is implementation commit before long proof rendering, then original media and candidate manifest commit. A later HTTP receipt binds the immutable media commit and actual downloaded bodies. Required runtime inputs use permanent repository-relative paths. Original MP4 encoding is retained for public delivery.

Only MP4, eight Checkpoint PNGs and SHA256SUMS belong in `public-review/`. Source, fixture, diagnostics and internal records stay outside that folder. This is a review Candidate; user approval and the full Permanent Gate remain deferred. Stop at USER_VIDEO_REVIEW_REQUIRED.

## Inventory and scan

Run the pinned Python interpreter from the repository root:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-tsunami-wave-polish-v3/build_candidate_manifest.py --stage implementation --write-manifests
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-tsunami-wave-polish-v3/scan_candidate.py --repo . --scanner /workspace/.onboarding/event-v1-tools/gitleaks --output world-simulation-shorts-engine/recovery/event-tsunami-wave-polish-v3/evidence/SECRET_SCAN_IMPLEMENTATION.json
```

After proof creation and visual inspection, use `--stage candidate --write-manifests`, scan the new worktree, commit the original media, and run `--stage candidate --require-persisted`. None of these commands renders or executes the approval-only Permanent Gate.

## Pinned reproduction tools

Use Node 24.19.0; `/usr/bin/python3` 3.13.5; `/usr/bin/chromium` 154.0.8037.57; FFmpeg 7.1.5; Three 0.170.0 and Playwright/Playwright Core 1.62.1. NumPy 2.2.4 is the focused decoded-frame audit dependency used by the pinned Python interpreter, inherited from `recovery/v4/runtime/python-requirements.lock`. Pillow 11.1.0 and GDAL 3.10.3 retain their existing pins. No runtime dependencies were added. The manifest records actual toolchain observations and the unchanged lock SHA.

If the pinned Node dependencies are missing in a clean checkout, use the existing saved setup command:

```sh
npm --prefix cinematic-world-map ci --ignore-scripts --no-audit --no-fund --strict-ssl=true
```

Before the pre-render implementation commit, the focused Wave check is:

```sh
node world-simulation-shorts-engine/recovery/event-tsunami-wave-polish-v3/verify_wave_regression.mjs
```

Then generate implementation manifests, scan and persist the tested source and receipt. For original source reproduction, pin the pre-render source commit from `REPRODUCTION_MANIFEST.json`; its public output directories are absent. Keep the retained prerequisite receipt unchanged and run:

```sh
node world-simulation-shorts-engine/recovery/event-tsunami-wave-polish-v3/render_proof.mjs
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-tsunami-wave-polish-v3/verify_visual_proof.py
```

The audit first reports `TECHNICAL_PASS_VISUAL_REVIEW_REQUIRED` and writes private decoded PNGs under `evidence/decoded-audit/`. Inspect those actual decoded video frames for wave fronts, coast arrival, impact, rhythm and legibility. Only after that inspection, repeat the audit command with `--visual-review-pass` to record technical Candidate PASS. This flag does not claim user approval. Do not overwrite or re-encode retained approved media. A rerun of the prerequisite check changes its dated receipt; save a new pre-render implementation revision before rendering from that changed input set.

After the original Candidate media commit has been pushed, verify delivery with:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-tsunami-wave-polish-v3/verify_public_downloads.py --commit ORIGINAL_MEDIA_COMMIT
```

The verifier performs ten real HTTP GETs, requires HTTP 200 and checks downloaded bodies against both the original local bytes and immutable Git commit bytes. Download copies are temporary verification outputs; they are not required runtime inputs.
