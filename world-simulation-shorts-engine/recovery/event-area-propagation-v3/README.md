# AREA / PROPAGATION V3 Candidate

Technical state: `EVENT_FEATURE_BUNDLE_V3_AREA_CANDIDATE_PASS`. Next: `USER_VIDEO_REVIEW_REQUIRED`. No Final promotion or Permanent Gate has been run for V3.

The parent Flow V2 Final at `fbc3be89d94040271c7f54a051162913ad134bac` and all 2,461 parent tracked paths are unchanged. Seven separate Area modules implement sourced Polygon states, radial coverage, trajectory motion through V1 arc length, visual propagation, impact, front/state/time transitions and hold. Existing Camera V5, measured Glyph/Layout, country material/boundary/glow and Marker remain their owners.

Core checkpoint: `19a5c72`. Fixture/camera and original render source: `f161bd2fc1da4b75933e32465b8c7dc840272978`. The Candidate media commit binds this directory's original public media and manifests; the later download receipt records its full immutable hash.

## Actual proof

`AREA_PROPAGATION_V3_TSUNAMI_CANDIDATE.mp4`: 9 seconds, 270 frames, 1080×1920, 30fps, silent. SHA-256: `2a99321fc150f069c232656740b455fc1f714f68a61bc41b2c45701789146a71`.

The 2011 Tohoku fixture presents the offshore origin, outward propagation and Japanese Pacific coast relationship. Country GIS and Natural Earth terrain are inherited licensed data. Official USGS/NOAA sites returned environment HTTP 403; `data/PUBLIC_EVENT_REFERENCES.json` records published historical references and explicitly records that their documents were not retrieved. No new official-document hash or precision certificate is claimed. Propagation frames/radius and coastal focus are an illustrative infographic, not wave height/speed/arrival-time or inundation measurements. The final graphic says `확산 개념도`.

Full future Area sweep is safe and readable at 44.3923% coverage. Admission returns `USE_CURRENT_VIEW`; survey `LOCAL_NOT_ADMITTED` remains recorded. The proof seeks the unchanged V5 plan to its arrival/fine-approach segment, settles for the existing budget, locks, then executes Area graphics. No new Detail camera or forced LOCAL entry is used.

## Reproduction

Use persisted fixtures without rerunning the source-reference recorder or altering their bytes. The parent pinned toolchain is Node 24.19.0, Playwright 1.62.1, Chromium 154.0.8037.57, Three 0.170.0, Python 3.13.5 and FFmpeg 7.1.5. Browser rendering uses SwiftShader; RTX was not tested. Runtime needs only repository-persisted assets, fixtures and modules. The V5 read-only HTTP server binds localhost, so this managed environment needs execution permission for that local server/browser.

From repository root, in a fresh output checkout with pinned dependencies and Git LFS bodies available:

```sh
node world-simulation-shorts-engine/tests/area_core_v3.test.mjs
node world-simulation-shorts-engine/recovery/event-area-propagation-v3/verify_synthetic.mjs
node world-simulation-shorts-engine/recovery/event-area-propagation-v3/verify_integration.mjs
node world-simulation-shorts-engine/recovery/event-area-propagation-v3/render_proof.mjs
node world-simulation-shorts-engine/recovery/event-area-propagation-v3/verify_protection.mjs
```

`render_proof.mjs` creates new output directories and refuses to overwrite existing Candidate media. For a media-bearing checkout, remove the existing output directories only in the separate reproduction checkout after preserving its approved media for comparison. Do not remove or modify the saved Candidate in the development checkout. Static diagnostics and manifests already persisted here are not runtime substitutes for rendering.

The focused regression checks Source protection, 3 actual native V5 OFF samples, all 270 protected frames, source geometry/determinism, no subject-specific Engine branch, safe area and native GL errors. This is not the deferred approval-only clean Permanent Gate.

## Public review

Only the original MP4, eight original native-frame PNGs and SHA256SUMS belong in `public-review/`. Internal source, diagnostics, references and plans are excluded from that folder. `verify_public_downloads.py` performs HTTP 200 and downloaded-body/Git/original SHA comparisons using immutable media-commit URLs. All required runtime files are permanent; required temp-only files: 0.
