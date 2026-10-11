# LOCAL DETAIL ADMISSION V1

## Suez audit

- Terrain INSUFFICIENT: native NE1 RGB is magnified 13.4001 × 15.5231 output pixels per texel. Output ground spacing at the anchor is 119.62 × 119.02 m/pixel; source RGB spacing is 1602.95 × 1847.63 m/texel.
- DEM INSUFFICIENT for full-screen real elevation coverage: actual GLO-30 intersects 65.1817% of the requested LOCAL screen. Native sampling is sufficient where present. DEM remains optional unless the Scene explicitly requires complete real elevation; no extra DEM download is demanded by default.
- GIS INSUFFICIENT: Natural Earth 1:50,000,000 Egypt boundary has no verified metre positional/simplification bound. Screen error is UNKNOWN/null, not invented from map scale.
- Canal INSUFFICIENT: 1:10,000,000 schematic centerlines are not detailed complete local canal geometry. Current pixel pipeline displays the real waypoint Marker, not a detailed canal shape.

## Result

LOCAL_NOT_ADMITTED. No LOCAL PNG generated. Effective Scale REGIONAL.

Safe bounds: 23.25°E–38.15°E, 16.472168113664114°N–39.827831886335886°N.
APPROVED_REGIONAL_FALLBACK. closestExtentCertified=false; additionalZoomPermitted=false.
Unknown GIS accuracy prevents certifying a closer extent. This is the unchanged previously approved Regional view, not a claim of newly certified LOCAL-quality detail.

## Minimal missing data

- Higher native-detail terrain RGB (approximately 120 m/output-pixel target in this requested view).
- Verified detailed local GIS/coastline, with documented positional plus simplification error in metres.
- Verified complete detailed canal geometry. The explicit line/area event pixel pass is also not implemented in the current static renderer; data alone cannot silently enable it.

## Protection and validation

WORLD/CONTINENT/REGIONAL compiled plans are identical. All shader/material/lighting/boundary/glyph/layout/projection code is unchanged; Renderer edits are admission import and pre-context guard only.
CONTINENT and REGIONAL PNGs are byte-identical. Final SAFE_CLOSEST_VIEW is byte-identical to approved REGIONAL.
The strict WORLD pixel equality test FAIL is preserved: current output differs in nine of 2,073,600 pixels near the globe limb, max RGB difference 5/255; the unchanged approved renderer itself differs from its prior artifact in 13 pixels. No graphic/background pixels differ. This is confirmed pre-existing Software GL repeatability variance; the precise numerical/runtime cause remains UNKNOWN. No WORLD visual tuning was performed to hide it.

Focused final admission tests: 76 PASS /0FAIL /0ERROR. Final safe-only runtime: 41 PASS /0FAIL /0ERROR /1SKIP RTX. Across unique focused test IDs, including protected-scale checks: 158 PASS /1FAIL /0ERROR /1SKIP. The one FAIL is WORLD strict pixel equality, not a LOCAL admission or Renderer exception.

Two implementation iterations. No new data download, legacy regression, Container, video, animation, gCube or RTX execution.

## Output

SAFE_CLOSEST_VIEW.png: 1080×1920 lossless PNG.
SHA-256: fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673.
LOCAL_ADMITTED.png: NOT GENERATED.

USER PNG REVIEW REQUIRED. No next stage started.
