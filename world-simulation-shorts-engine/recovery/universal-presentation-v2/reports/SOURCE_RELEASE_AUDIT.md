# Source release audit

SOURCE_LICENSE_AND_TRAJECTORY_AUDIT_PASS

Read-only audit of the three completed Studio outputs rendered from source commit `002d90516551774aaf5740eb3968fdda07ed5600`. No renderer, cached asset, source file or output video was modified. No rendering, recompilation, download or GPU operation was performed.

All three outputs contain 180 frames, 6.000 seconds, 1080×1920 H.264 at 30fps. Independently checked video hashes match their private original capture receipts. All 540 frame records retain their admitted source hash, material classification and whole-viewport positive gutter. All six decoded crop RGB buffers exactly match their original available source-pixel windows.

| Studio case | Actual complete-movie source/style | License | Frame source checks | Metadata credits |
|---|---|---|---:|---|
| case-1 | GLOBAL_EARTH_DAY_RGB_V1 / CURRENT | CC-BY-4.0 | 180 | PASS |
| case-2 | NE1_SOUTH_AMERICA_CHILE_NATIVE_V1 / BAKED_RELIEF_V1 | Public Domain | 180 | PASS |
| case-3 | NE1_NAMIBIA_DESERT_COAST_NATIVE_V1 / BAKED_RELIEF_V1 | Public Domain | 180 | PASS |

Each movie uses one parent source and style through both scene trajectories; per-scene native crop windows differ while the map source/style remain consistent. The selected parent files, native pixel windows, crop hashes, measured gutters, exact video hashes and actual metadata tags are in the companion JSON.

The CC-BY-4.0 global RGB movie contains Solar System Scope/NASA attribution, the license link, preserved source URL and explicit crop/render/graphics modification disclosure in both MP4 `comment` and `copyright` tags. Public-domain NE1 movies also preserve source attribution and modification disclosure. Catalog source, license and credit-file hashes were checked directly against the local original files.

Global RGB is `CURRENT` color imagery with the existing relief proxy. It is not new DEM, measured bathymetry or baked NE1 relief. The NE1 cases use their verified retained RGB native crops as `BAKED_RELIEF_V1`; no new elevation data is claimed. The global NE1 TIFF remains a 134-byte Git LFS pointer. Its expected original hash and URL are upstream provenance, not proof that its 699,969,932 bytes were available or freshly verified. The capture field named `sourceOriginalSHA256` identifies the actual available parent PNG/JPEG; this audit distinguishes it from unavailable upstream TIFF provenance.

The earlier request-probe `regionEvidence.initialWindow` is not used as the final source window after source reselection. Actual final registration is established by `sourceStyle.cropSourcePixelBox`, `actualCropBounds`, source/crop SHA and every frame material binding. Survey-grade global RGB geolocation remains unverified.

The runtime/capture records explicitly identify SwiftShader and `nvidiaVerified:false`; this audit makes no NVIDIA hardware claim. The capture receipts record full video decode PASS; this audit independently ran ffprobe metadata checks and source/frame-binding checks.

Visual quality remains **USER_REVIEW_REQUIRED**. This is a source/license/trajectory binding audit, not user approval or FINAL promotion.
