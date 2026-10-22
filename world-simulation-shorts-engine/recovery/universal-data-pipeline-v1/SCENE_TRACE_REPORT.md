# Scene to actual pixel audit

Status: **DATA_TO_PIXEL_TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED**. This is a technical source/clock/engine audit, not user video-quality approval.

The audit reads the exact Scene wire used by each real detached Studio worker, recompiles the original supplied prompt independently, re-evaluates existing Camera V5/Area V3/Flow V2 controls for every frame, and compares all persisted frame diagnostics. It independently checks geographic-to-screen coordinates using the native flat viewport formula. It does not render, alter source files, fabricate missing frames, or use a GPU.

| Real Studio subject | Frames checked | Actual feature draws | Input-to-pixel result |
|---|---:|---|---|
| AVIATION_DEMO | 90 | Flow 88; object 82; Area 0 | DATA_TO_PIXEL_TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED |
| FICTIONAL_AREA_DEMO | 90 | Flow 0; object 0; Area 89 | DATA_TO_PIXEL_TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED |
| TRADE_DEMO | 90 | Flow 88; object 82; Area 0 | DATA_TO_PIXEL_TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED |

Every successful case preserves exact source geometry, semantic input trace, original event clock, real admitted locked camera, source-native terrain coverage and actual layout admission. Measured pre/post feature readPixels differences are distinct from nonblack base-map pixels. The paired changed-input proof separately establishes that changing an input route changes actual pixels while leaving the map and camera unchanged.

Scene semantic SHA and exact-wire SHA are recorded separately. The unchanged strict Planner validator requires canonical geometry member ordering; the new Studio wire-string persistence bridge preserves it across Python sorted-key cache storage. No original validation is weakened.

Limitations: registered regional views are locked; arbitrary pan/zoom, physical travel speed, visible arbitrary labels/text, automatic named object artwork, worldwide source coverage, historical ownership reconstruction, and LINE_METRIC/DISASTER pixel profiles are not claimed. Supplied locality/marker labels and object-profile identifiers are explicitly semantic metadata. These three demos are illustrative general/fictional inputs; they are not observed airline, shipping, or historical military movements.

The legacy diagnostic `nativeDraw` is a frame ordinal in the current consumer; this audit uses capture-receipt measured draw counts and complete frame rows instead of interpreting a random-access frame ordinal as a measured count.

NVIDIA hardware validation, final visual quality, external Dropbox delivery, G3, paid rendering and FINAL promotion remain outside this result.


## Manual frame scope

Actual frame45 PNGs from all three completed Studio demos were viewed. Namibia's rectangular gold overlays exactly represent the supplied fictional polygon states, rather than a raster-tile seam. Aviation and trade show their supplied route and moving object over the actual source-native map. The trade line is explicitly an illustrative connection, not an observed navigable shipping path. No obvious raster-source discontinuity was seen in these three PNGs; this limited inspection is not whole-video or final visual approval. Exact PNG hashes and observations are in `reports/DATA_TO_PIXEL_MANUAL_FRAME_SCOPE.json`.
