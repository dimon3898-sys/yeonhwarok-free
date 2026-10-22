# Reference 64306: geographic input admission

Status: **DATA_DETAIL_BLOCKED**. The available data support a partial, coarse context registry. They do not establish the tiny hero place, its precise polygon, the explained boundary, or a sufficiently detailed basemap. No geographic reference render is admitted. Technical fixture tests remain independent.

The audit used base `82854af429d09aebb4b31c2f168e2f0ddc9560c9`. The parent verified the original 307 protected-file hashes before this new namespace was written. Existing registry, vector, font, raster, and cache files were read without alteration. No new GIS assets were downloaded.

## What actually exists

| Target binding | Existing source evidence | Admission |
|---|---|---|
| `primaryCountryGeometryId` | `COUNTRY_ESP`: Natural Earth 1:50m country source, feature 54 / `ADM0_A3=ESP` | Available coarse country geometry; native full MultiPolygon preserved |
| `contextRegionGeometryId` | `COUNTRY_MAR`: same source, feature 103 / `ADM0_A3=MAR` | Available candidate; the target has not supplied an explicit final region selection |
| `contextLocationIds[0]` | Ceuta: Natural Earth place feature 4976 / `ne_id=1159146357`, `[-5.306999,35.888984]` | Regional locality point; display name `세우타` comes from the supplied reference analysis |
| `contextLocationIds[1]` | Melilla: feature 5681 / `ne_id=1159147943`, `[-2.950011,35.300002]` | Regional locality point; display name `멜리야` comes from the supplied analysis |
| `detailLocationId` | No named, verified matching registry record found | `NEEDS_INPUT` |
| `detailGeometryId` | No detailed matching Polygon/MultiPolygon found | `NEEDS_INPUT` |
| `detailBoundaryGeometryId` | No real matching ordered LineString found | `NEEDS_INPUT` |
| `metricValueId` | Source video visibly says `85 m` | Display text can be referenced as **observation only**; independently measured length remains unverified |
| `basemapSourceIds` | Existing global 8K RGB supports overview geography | Native detail insufficient for the observed close-up; no complete final binding |
| `contextBoundaryGroups` | Supplied target has an empty mapping | `NEEDS_INPUT`; no continent/name-based automatic style assignment |

The two populated-place coordinates are source-native regional cartographic points. They are not verified survey positions for the exact pin tips shown by the source video. Apparent coordinate precision is not an accuracy certificate.

Country file SHA-256: `3e458fc036ad0a66411f2c1e6cac49c5d7bfb81cb1123bc513b22511a2b7fdeb`. Place file SHA-256: `fd3fa867a320cbd5c5b6bb5bc550afeec2939fb2cef688e508007282a55ac42f`. Both are preserved Natural Earth public-domain data; `SOURCE_BINDING_AUDIT.json` and `REFERENCE_DIRECTOR_INPUT.json` carry selectors and hashes.

Spain is a 12-part MultiPolygon, including islands. Its full bounds are `[-18.160547,27.646387,4.32207,43.764551]`. Mainland component 4 has bounds `[-9.235645,36.025928,3.306738,43.764551]`. These parts must not silently disappear to satisfy the target country's screen-width constraint. A reference framing scope or explicit component selection is still needed for exact matching. No component was dropped or moved.

## Missing input formats

1. `detailLocationId`: verified identity and EPSG:4326 Point `[longitude,latitude]`, source identifier, original SHA-256, date, and positional uncertainty.
2. `detailGeometryId`: license-cleared detailed GeoJSON Polygon/MultiPolygon, geographic CRS, native precision/scale, positional uncertainty, source and SHA-256. A rectangle, screenshot trace, or invented coast is insufficient.
3. `detailBoundaryGeometryId`: license-cleared ordered LineString with verified endpoints, direction, boundary definition, source/hash, date and uncertainty. The original order defines reveal arclength.
4. Geographic measurement: source and definition supporting a length claim. The literal `85 m` may remain a clearly classified reference observation; it cannot establish the real boundary length.
5. `contextRegionGeometryId` and `contextBoundaryGroups`: explicit region and geometry-to-style selection.
6. `basemapSourceIds`: source covering the entire inverse-projected, rotated camera envelope, with usable local native detail, registration, CRS, pixel-edge bounds, native spacing, dimensions, original hash, NoData, license and attribution. If a source hierarchy is required, registration and seamless style continuity must be proved. Upsampling alone supplies no missing detail.

The hero place is **not identified** in this audit. A familiar small enclave, including Peñón de Vélez de la Gomera, must not be assigned solely from the image or its `85 m` text. Local searches for Ceuta, Melilla, Vélez/Velez and Gomera found only existing place/airport/port context records, not a detailed hero polygon or boundary source.

There are six required geographic/source binding gaps in the machine-readable gate. Independent verification of the `85 m` length is recorded separately as an unverified claim: it is required before asserting a measured geographical fact, but does not prohibit drawing the supplied literal text as a classified reference observation.

## Separated outcomes

- `DIRECTOR_IMPLEMENTATION`: parent/camera/event capability tests; this data report does not award a renderer pass.
- `GEO_AND_SOURCE_READY`: **DATA_DETAIL_BLOCKED**.
- `REFERENCE_VISUAL_MATCH`: **not executed**, because the data gate fails.
- `HISTORICAL_G3`: **BLOCKED**; this geographical explanation does not unlock historical production.

`fixtures/SYNTHETIC_NORTH.json` and `SYNTHETIC_SOUTH.json` are explicitly fictional, original nonrectangular geometries in different hemispheres. They exercise generic contracts, projected anchors, line order and different label lengths. They are never substituted into `REFERENCE_DIRECTOR_INPUT.json`, and cannot establish reference geography, real Studio rendering, or reference visual quality.

No original reference video, extracted screenshot, or user analysis image is republished by these data deliverables. No paid GPU/API, render, deployment, cache reset, or existing asset modification was performed.
