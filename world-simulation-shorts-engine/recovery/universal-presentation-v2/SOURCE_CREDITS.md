# Map source credits and limits

This review uses preserved source files, with no new map downloads.

| Source | Credit / license | Actual scope |
|---|---|---|
| Natural Earth I regional native-pixel images | Natural Earth, public domain. <https://www.naturalearthdata.com/about/terms-of-use/> | Existing licensed regional crops; their actual geographic extents and original pixel spacing constrain camera coverage. |
| Global Earth Day RGB | Solar System Scope, NASA. <https://www.solarsystemscope.com/textures/> — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Preserved 8192×4096 equirectangular RGB image. Native pixel cropping and rendering are modifications. This is a color image, not DEM or measured bathymetry. |
| Modern country outlines and locality points | Natural Earth, public domain | Country/location alignment and declared technical examples; not evidence of observed airline services, shipping operations, historical armies or control boundaries. |

`REGION_SOURCE_CATALOG.json` records actual local paths, source and license file
SHA-256 values, source references, resolution and coverage. The per-capture
receipts identify the source actually selected for each complete camera path.
Map style selection is consistent over that whole path; an unsupported regional
crop is not patched over part of another map.

The retained global Natural Earth TIFF is a 134-byte Git LFS pointer, not an
available 699,969,932-byte raster. Its expected parent hash is provenance
metadata only. No unavailable raster is reported as loaded or verified.

The global RGB registration follows the retained renderer's equirectangular UV
contract. Survey-grade geolocation accuracy has not been established. This
profile rejects unsupported projection/coverage requests instead of generating
missing elevation, depth, coastline or historical facts.

Fictional rectangles and the illustrative route directions in the examples are
explicitly supplied test data. They are not map tiles or historical claims.
