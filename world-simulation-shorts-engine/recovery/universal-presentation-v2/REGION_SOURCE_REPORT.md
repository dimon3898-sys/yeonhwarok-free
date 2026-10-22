# Region and source extension audit

This is an independent provider under `universal-presentation-v2`. Original G1/G2/FINAL, the five-region pipeline and its assets are not edited. A technical provider result is not a visual or NVIDIA GPU result.

## Confirmed previous limit

`recovery/universal-data-pipeline-v1/capture_generic.mjs:30` requires `SOURCE_REGIONS.includes(sourceRegionId)` and reads `<registered id>/RECOVERY_RUNTIME.json` from the retained five-case archive. Its native style coverage is verified only against that case's raster. This is a source/profile selection restriction, not evidence that the native renderer itself can only draw five countries.

The new provider receives standard EPSG:4326 `[longitude,latitude]` and `[west,south,east,north]`. It uses the same retained 242-country source geometry, unchanged `compileScalePlan`, genuine Camera V5 and original native factory. Source selection is data in `REGION_SOURCE_CATALOG.json`; no country-name conditionals or newly invented terrain are used. Existing five profile aliases remain an internal, exact-source regression contract. The Studio input contract uses explicit coordinates and bounds.

## Actual source availability

| Source | Verified existing bytes | Native resolution | Coverage and treatment |
|---|---:|---|---|
| Five retained Natural Earth 1 native crops | 5 source PNG hashes pinned in catalog | 1/60 degree per pixel, RGB | Each recorded crop bounds; `BAKED_RELIEF_V1` |
| Existing East Asia Natural Earth 1 image | 13,947,958 | 2880 × 3360; 1/60 degree | `[104,7,152,63]`; `BAKED_RELIEF_V1` |
| Existing global Earth Day RGB | 4,565,076 | 8192 × 4096; 0.0439453125 degree | `[-180,-90,180,90]` equirectangular source; `CURRENT` |
| Global Natural Earth 1 TIFF | **134-byte Git LFS pointer only** | Expected original 21600 × 10800 | **Unavailable. Not decoded, downloaded or selected.** |

The global TIFF's expected hash in old receipts does not establish that its full source bytes are present. This audit found the pointer by reading actual bytes. The expected 699,969,932-byte file was not fetched. Retained crop hashes prove those available source PNGs; their recorded original-parent provenance is retained without claiming a new original-TIFF verification.

Global RGB is a color texture, not new elevation, bathymetry, DEM or baked relief. Source registration follows its existing renderer's global UV contract; survey geolocation accuracy has not been established. Outside a retained NE1 crop, the provider may choose this RGB style for the **entire camera envelope**. It does not splice a rectangular NE1 patch into a global texture or claim identical map quality between different sources. The unchanged native renderer's existing `RELIEF_PROXY` remains a proxy, not ASTRA DEM evidence.

## Coverage and alignment contract

`qualifyRegion({region,facts,scene})` checks actual catalog, selected raster, license, retained GIS and source-archive bytes. It returns `REQUEST_COVERAGE_ONLY`; this cannot authorize rendering. Each supplied location's optional country reference is checked against actual source geometry. Border uncertainty uses the catalog's explicit 0.1-degree generalized-GIS tolerance and is reported rather than called surveyed accuracy. Region-country references describe the center; a bbox may cross countries.

When no country is supplied and the center is offshore, an actual source polygon intersecting the view can provide the native factory's structural context. It is explicitly not center membership or historical ownership. Pure-ocean extents without any real country geometry are `UNSUPPORTED` because the protected factory requires land context. No nearest-capital or fake land polygon is inserted.

`resolveRegionPlan({scene,region})` preserves original source geometry and measured native text/glyph bindings. It compiles the existing regional scale plan and a genuine Camera V5 plan. V5 computes its own recognition start extent; forcing the closest final box as its recognition extent was confirmed to fail when the whole primary country could not fit the safe area. The approved final extent remains locked and unchanged. Arbitrary scene titles are metadata; they cannot replace strings bound to the original measured glyph atlas.

`prepareRegionTerrain({regionPlan,bounds,outputRoot})` requires the union of **every actual presentation-camera frame** before Studio creates a job claim. It selects one raster covering that complete trajectory **and the unchanged approved framing used for factory initialization and model analysis**. These two bounds and their union are recorded separately. Source-pixel floor/ceil windows include a two-pixel requested gutter and require at least one actual pixel on all sides. It refuses out-of-support trajectories, dateline splitting, polar flat projection beyond ±85°, and native windows over 4096 pixels in either dimension. It never lowers resolution to make an unsupported request pass.

Pillow crops the verified parent RGB image with no resizing, recoloring, blur, missing-data fill, height synthesis or interpolation. Pixel-edge geographic bounds follow the exact source window; pixel centers remain half a native pixel inside those edges, with north-to-south source rows. A decoded RGB SHA proves the stored PNG's pixels equal that exact source window. The existing native renderer receives those actual crop bounds through its normal terrain asset contract.

## Cache and reuse safety

Generated crops are stored only below a server-owned, UID-owned `0700` directory outside the repository. Files are `0600`, created exclusively. The key includes catalog/version hash, original request gate, actual source hash, complete camera envelope, original initialization/analysis framing, their required coverage union, native window, geographic bounds and no-resampling method. Source/style changes or a changed camera envelope create a different key. Existing G1/G2 caches are never accessed for writing.

`verifyRegionQualification({prepared})` rechecks the catalog, source/archive/GIS/license bytes, source selection, complete-camera receipt, key, cache record, PNG bytes, original pixel window, terrain binding and material classification. Both Studio before claim and the worker before draw reuse it. A missing, incomplete, stale or corrupt cache is refused without overwriting the damaged file or silently claiming readiness. Request-only receipts remain explicitly insufficient.

## Licenses and credits

Natural Earth raster and GIS use retained Public Domain license evidence. The global RGB source has retained Solar System Scope/NASA CC-BY-4.0 evidence in `cinematic-world-map/assets/v3/earth/SOURCE_README.md` and `assets/v3/CREDITS_V3.txt`. Its preserved original URL, actual JPEG hash and license/credit hashes are in the catalog. A generated video using it must retain the supplied attribution in its credits/metadata; it must not be presented as a new unlicensed ASTRA product. No new map data was downloaded or redistributed for this implementation.

## Verification boundary

The focused provider suite checks existing source/credit bytes and dimensions; all five old profile hashes/framing; new Japan and Australia requests; geographic/name conflicts; offshore context and unsupported pure ocean; antimeridian geometry; coordinate/CRS/polar gates; native RGB pixel identity; private cache policy; reuse; full trajectory source selection; stale/corrupt receipt rejection. Actual draw probes and Studio MP4s are separately recorded by the runtime/Studio owner. This provider report alone claims no successful draw or video quality PASS.

## Confirmed E-probe recovery

The first actual probes exposed a provider initialization-coverage defect: a native crop selected only for a panned trajectory could omit the left/top edge of the original approved framing. The unchanged native scale contract then correctly rejected it with `REGION_SOURCE_FULL_VIEWPORT_REQUIRED`. The provider now includes both extents in source selection, native crop identity and receipt verification. It does not weaken the native admission rule or expand source data.

Chile exposed a separate correct rejection: its retained source ends at longitude `-61.86666666666666`, while the requested camera reached `-60.42368421052632`. The exact-profile regression had centered a camera on an event anchor instead of the original framing center. An exact legacy movement test must use the approved framing's midpoint and stay within the original source. A new explicit-coordinate `AUTO` request may instead qualify a single global RGB source and must report that different style. The original overreach rejection and failed records remain preserved.
