# MAP_INFOGRAPHIC_RENDERER_V1 — Scale System V1 static proof

Decision: **SCALE_SYSTEM_DATA_LIMITED**. Final visual review remains with USER.

Focused final validation: PASS 214, FAIL 0, ERROR 0, SKIP 1 (actual RTX prohibited).

Exactly four final1080×1920 lossless PNGs. Software WebGL2/SwiftShader only; no animation, video, container or gCube run.

## Geographic Scale contract

- WORLD: WORLD_GLOBE_ORTHOGRAPHIC; geographic extent [-180, -90, 180, 90]; admission ADMITTED.
- CONTINENT: REGIONAL_EQUIRECTANGULAR; geographic extent [7.457023519999993, -20.47138446407132, 57.49424648, 62.55268346407132]; admission ADMITTED.
- REGIONAL: REGIONAL_EQUIRECTANGULAR; geographic extent [23.25, 16.472168113664114, 38.15, 39.827831886335886]; admission ADMITTED.
- LOCAL: REGIONAL_EQUIRECTANGULAR; geographic extent [31.710562904538683, 29.28763616, 33.053841095461316, 31.34908184]; admission LOCAL_DATA_LIMITED.

## LOD and visual protection

- WORLD: existing8192×4096global RGB,2048×1024RELIEF_PROXY(notDEM),242realcountryPolygons/MultiPolygons withholes; target-centered visible hemisphere.
- CONTINENT: exact native3003×4983existingNaturalEarthRGB window,60texels/degree; noresize ornewdata.
- REGIONAL: approved1440×1680NE1crop andexisting7200²R32FGLO30 footprint; byte-identical approvedPNG SHA fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673.
- LOCAL: sameNE1source+realDEM onlywithinverifiedfootprint,2×exaggeration unchanged. Generalizedcountrycoast andnativeRGB enlargement13.4×15.5px/texel restrictdetail. Marker/locationnormal; country/titleadmittedoff.
- Terrain Material,DEM normal/lighting/outputresponse,colors,font,markerdesign andGISsourcecoordinates unchanged. Boundarysize/infoadmissionadjustedbyScale only.
- REGIONAL/LOCAL flatstandardparallelprojection retained. Verywide/polar/datelineextentneedsfutureprojectionadmission; notclaimedverifiedhere.

## Three implementation iterations

1. ExplicitScalepaths/samefactory: fourPNGs generated;REGIONALidentical. CONTINENTsourcepatch seam identified. LOCALtest incorrectlydemandedSecondarywhichwasoutsideview; fixedvisibilityexpectation withoutfabricatinggeography.
2. CoveringnativeNE1LOD selectedforCONTINENT;seamremoved. ActualGPUribbonalphaQC exposedsubpixelWORLDcores and differencebetweennominalwidthandAAintegral.
3. WORLD/CONTINENTgenericminimum3pxPrimary/2pxSecondary; edgegapfamilyunchanged. QC comparesactualcoverageagainstshaderAA,response preserved. No furtheriteration.

## Actual GPU boundary pixel evidence

Requested geometric corewidth differs from integrated antialiased alpha coverage. No extra final PNG was rendered for width measurement.

| Scale | Nominal Primary/Secondary(px) | Measured AA Primary/Secondary(px) |
|---|---|---|
| WORLD | 3/2 | 1.950/0.698 |
| CONTINENT | 3.25/2 | 2.106/0.716 |
| REGIONAL | 5/2.5 | 3.981/1.616 |
| LOCAL | 4/2 | 2.519/OUT OF VIEW |

## Original PNG hashes

- `01_WORLD.png`: `8b5c432250bce421988c869e9dcc495ad56f2682fbe30b78ee05054aa74b1cdc`
- `02_CONTINENT.png`: `fab41d0917592cfa4d322f7f58204d9458a95da805418e6ce06dd2aead1602c4`
- `03_REGIONAL.png`: `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673`
- `04_LOCAL.png`: `9bdaa897b1954fa44626a42a52c5a0ff0c7842d926e5a38a6c9dfba27104e248`

NEXT: USER PNG REVIEW REQUIRED. No next-stage work authorized or started.
