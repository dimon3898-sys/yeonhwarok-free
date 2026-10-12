# Coastline / Water GIS source investigation

Result: **GIS_DETAIL_NOT_VERIFIED**. Detailed native OSM vectors are available for
comparison, and official WorldCover/JRC documentation was acquired. No acquired
source establishes a hash-bound positional error in metres for all GIS records
required by the unchanged `LocalDetailAdmission` contract. No detail admission is
granted here.

## Preserved native OSM evidence

The protected `recovery/event-data/suez-full-canal-20261012` snapshot remains
unchanged. It includes the validated relation 7719838 v17 navigation axis,
92 native coordinates / 91 segments, and the original entrance/lake extracts.
The axis, metric, metric source, and source coordinates were not replaced.

`audit_saved_osm.py` reads those original XML files. It assembles water rings by
identical native node IDs only, preserving every coordinate and declining open,
ambiguous, missing, or invalid rings. It neither closes gaps nor simplifies GIS.
`SAVED_NATIVE_WATER_COMPARISON.geojson` is comparison data; it is not a replacement
for the locked event axis or the native Renderer country GIS.

| Native water relation | Version | Coordinates | Unchanged axis vertices in/on water |
| --- | --- | ---: | ---: |
| Great Bitter Lake 1410016 | 21 | 5,642 | 10 |
| Little Bitter Lake 1691290 | 15 | 1,501 | 13 |
| Southern canal water 7682094 | 5 | 1,292 | 18 |

These three assembled multipolygons pass OGR validity checks. The saved XML also
contains 28 coastline ways with 10,944 native node references. The extraction
proves **zero source-relative simplification error** and zero generated or
interpolated coordinates. It does **not** prove zero positional error. OSM
`source=Bing` or `source=landsat` tags do not identify the image product, acquisition
date, registration accuracy, independent control points, or a metre error bound.
The mouth/lake extracts do not establish complete continuous coastline/water
coverage over every proposed Detail extent.

The OSM license is ODbL 1.0 with attribution “© OpenStreetMap contributors”, as
already verified in the protected source license receipt. Source file hashes,
versions, missing members, assembly counts, and the unchanged axis hash are in
`SAVED_OSM_GIS_AUDIT.json`.

## ESA WorldCover candidate

The official ESA-WorldCover GitHub repository and the provider's AWS registry
record verify:

- WorldCover 2020 v100 and 2021 v200, with native 10 m land-cover raster products.
- 11 classes from Sentinel-1 and Sentinel-2, including permanent water bodies.
- Global coverage and 3 × 3 degree GeoTIFF tiles; the product is a classification
  map, not a replacement for the existing Terrain style or official country GIS.
- CC-BY 4.0; attribution: “© ESA WorldCover project [year] / Contains modified
  Copernicus Sentinel data ([year]) processed by ESA WorldCover consortium”.
- 2021 v200 DOI `10.5281/zenodo.7254221`.

The official README, download script, current AWS registry, and a Microsoft
Planetary Computer example are preserved byte-for-byte with retrieval receipts.
The download script identifies the official public S3 tile and grid paths. The
product user manual and actual raster data are inaccessible under this session's
current destination policy. No Suez tile bytes, CRS metadata from those bytes,
water segmentation, co-registration measurement, or positional accuracy bound
were acquired. **10 m native resolution is not a 10 m positional error bound.**
Vectorizing classification pixels alone cannot supply the missing geographic
accuracy evidence or establish exact canal banks. Pixel quantization and source
registration/classification errors must be measured separately.

## JRC Global Surface Water candidate

Google's official Earth Engine catalog record was retrieved and preserved. It
identifies JRC Global Surface Water v1.4, global Landsat-derived 30 m layers for
1984–2021, including occurrence, seasonality, and maximum detected extent.
Its stated terms are Copernicus free use with proper acknowledgement and
attribution “Source: EC JRC/Google”; its reference paper is
`10.1038/nature20584`.

The official JRC download endpoint is denied by the current destination policy.
The catalog is metadata, not a downloaded Suez water raster. Temporal maximum
water extent also is not an exact contemporary canal-bank or country-boundary
vector. No metre positional error bound is asserted by the acquired catalog.

## Actual destination-policy failures

The saved retrieval receipts record `Tunnel connection failed: 403 Forbidden` for:

- `www.openstreetmap.org`: original OSM API water relation retrieval.
- `wiki.openstreetmap.org`: source accuracy documentation.
- `osmdata.openstreetmap.de`: unsimplified coastline/water polygon distribution.
- `esa-worldcover.org`: official product access page.
- `esa-worldcover.s3.eu-central-1.amazonaws.com`: official v200 Product User Manual
  and, by the same host rule, the identified native tile/grid distribution.
- `global-surface-water.appspot.com`: official JRC data distribution.
- `www.capmas.gov.eg`: government GIS/source investigation entry point.

Proxy settings and TLS verification were preserved. No destination was accessed
by bypassing the proxy. Allowed GitHub provider/registry documents were acquired
as independent, legitimate documentation sources, not as a tunnel to a denied
destination. Host availability would enable further data investigation; it would
not by itself prove quality or grant Admission. Failed guessed GitHub paths are
recorded as HTTP 404 and are not treated as data sources.

## Unchanged Admission constraints

The policy requires at most 1 screen pixel per native Terrain texel, and at most
1 screen pixel of verified GIS geometry error. The geometry error must be the sum
of independently supported positional and simplification metre bounds, bound to
the exact source geometry SHA-256. Relevant primary/country polygons all need
that evidence. Water polygons or a fine raster alone cannot certify those country
polygons. Existing OSM completeness/semantic validation does not establish an
absolute metre accuracy bound.

The current `LOCAL_RENDER_CAPABILITIES.eventRepresentations` additionally contains
only `Point`. The preserved canal is `LineString`. It cannot be recast as a Point
to claim that its whole geometry was admitted. This is a capability limit, separate
from Terrain/GIS source availability. No Camera, Renderer, Event, admission policy,
or threshold is changed by this research.

## Reproduce comparison extraction

Run from any directory with the repository present:

```bash
/usr/bin/python3 world-simulation-shorts-engine/recovery/suez-detail-data-admission-v1/research/gis/audit_saved_osm.py
```

The script uses the existing GDAL/OGR 3.10.3 runtime solely for polygon validity
and point membership. It creates only the two comparison/audit files alongside
the script. Projection, source positions, protected baseline files, and runtime
rendering are unchanged.
