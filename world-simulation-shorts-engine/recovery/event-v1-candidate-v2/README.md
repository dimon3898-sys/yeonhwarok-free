# Event System V1 Candidate V2

State: `USER_VIDEO_REVIEW_REQUIRED`. This is a Development Candidate, never an Event Final.

The saved V1 Candidate `1d5182f7effde2e776f9c9ac21b00f6d681a423a` and its media/evidence remain immutable. V2 changes only Event line styling and the Event Metric's own measured reservation. Camera V5, native Renderer/visuals, geographic data, Marker, existing labels/title, line geometry/progress/occlusion, and Metric value/provenance remain protected.

The Event line receives a bounded one-step width increment. A generic accent palette is ranked against actual unchanged Primary framebuffer samples derived from projected geometry, native coverage, native glow, and protected reservations. Display sRGB is decoded once for luminance/OKLab analysis. Glow remains compact and uses the selected Event accent. The Metric inherits native font APIs, increases its own requested size modestly, and selects a full measured atlas beside visible line support, excluding Marker masks and every protected graphic.

Save implementation and procedures to the Development branch before any GPU measurement. Measure actual raster core width and composited Primary contrast using `measure_visuals.mjs`; resolve any failed measurement and save the final source before the complete validation run. Then run `validate_candidate.mjs` phases in order: `off`, `on`, followed by Synthetic A/B and Collision tests, `grammar`, `video`, and `checkpoints`. Persist evidence between long phases. Each output directory must be new; saved evidence is never overwritten.

Use `/usr/bin/python3 -B validate_manifests.py --write-manifests` after all required media/proofs exist, commit the Candidate assets, then run `--require-persisted`. `scan_candidate.py` provides the saved-source secret scan. Node, Chromium, fonts, and runtime assets remain pinned by the protected V5 manifests.

Public review contains only the V2 MP4, Checkpoint PNGs, and `SHA256SUMS`. Verify a full HTTP 200 download and equal SHA-256 for each committed public asset. Source, Manifest, diagnostics, and this plan remain outside the public-review directory. User video approval is required before any Final promotion.
