# Actual encoded Studio frame audit

Technical status: PASS. Visual status: QUALITY_REVIEW_REQUIRED; no automatic quality approval.

Decoded all180frames at1080×1920/30fps/6seconds. Exit0; sequential PTS verified. Recovery MP4 SHA256 `2aa3c8de7ad867863b7ec7d8f2ad60f6e93255c742cb631732c9d7a57fd41cc9`.

Before/after exact scene-state frames: 180/180. Camera, owner/unknown/contested/shared-front, marker, glyph and frame clock compared; terrain style metadata intentionally excluded.

Source coverage all180viewports: True; decoded native overlap exact: True; actualHTTP/receipt: PASS.

Old support-edge thresholds remain vertical12.133750066757203 and horizontal0.75. Flagged recovered frames: vertical1, horizontal0.

These are known-location diagnostics, not a generic image-quality test. Inspect flagged natural features before classifying a defect. No threshold was relaxed or refit.

Comparison PNG shows actual encoded frames [0, 30, 60, 90, 120, 150, 151, 179]. The script performs no manual semantic review; independent reviewer must record their actual viewed frames separately.

All180decoded PNGs remain in the new private scratch directory. Existing baseline source/video/cache files are not modified. HistoricalG3 remains BLOCKED.

Detailed results and exact commands: `reports/RECOVERY_FRAME_AUDIT.json`; per-frame data: `reports/RECOVERY_FRAME_AUDIT.csv`.


## Final recovery layout evidence

Overall technical status after current-camera layout checks: PASS. Visual status: QUALITY_REVIEW_REQUIRED; user approval remains required.

Current-camera layout checks: PASS, 180/180 frames. The original location label stays selected and is measured with the actual font and projection. The unchanged source runtime does not draw its native LOCATION_LABEL; it draws the marker and the SYNTHETIC caption. These checks prove layout admission and collision safety, not visible location-label pixel quality. No label deletion or collision-check bypass is inferred.

Detailed per-frame evidence: `reports/FINAL_LAYOUT_FRAME_AUDIT.json`. All 180 original comparison measurements and support-edge thresholds were reused unchanged.
