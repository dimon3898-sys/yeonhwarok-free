# Minimum missing DEM coverage source investigation

This investigation follows the existing native-height audit. Existing resolution
is sufficient; existing spatial coverage is incomplete. A new global or higher
resolution DEM is unnecessary merely to improve the sampling density.

AWS's maintained Open Data registry snapshot was downloaded successfully from:

`https://raw.githubusercontent.com/awslabs/open-data-registry/7cbf1a49dfd860c17c1e5af56ade458bd882ed0b/datasets/copernicus-dem.yaml`

The downloaded original document and its HTTP 200 / retrieval time / SHA-256
receipt are saved beside this note. The registry identifies:

- Copernicus DEM **2021 release**, a DSM rather than bare-earth elevation.
- GLO-30 Public, nominal 30-meter data, Cloud Optimized GeoTIFFs.
- Sinergise as the bucket manager; `eu-central-1` as the bucket region.
- Free general-public access under the linked Copernicus license terms.
- Maintainer documentation: `https://copernicus-dem-30m.s3.amazonaws.com/readme.html`.
- License reference: `https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM`.

The maintainer-document request through the inherited managed proxy failed at
CONNECT with **403 Forbidden**. `COPERNICUS_DEM_MAINTAINER_ACCESS.json` records the
actual failure. No direct connection, proxy bypass, alternate bucket hostname,
large-data download, or atlas rebuild was attempted. The next required data host
is **`copernicus-dem-30m.s3.amazonaws.com`**. The legal terms host is
**`dataspace.copernicus.eu`**; the registry-linked metadata catalog uses
**`copernicus-dem-30m-stac.s3.amazonaws.com`**.

The minimal missing grid cell for real-height coverage along the whole preserved
navigation axis is **N31 E032**. Its proposed native object reference is:

`https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N31_00_E032_00_DEM/Copernicus_DSM_COG_10_N31_00_E032_00_DEM.tif`

That URL follows the native tile naming convention; its existence, exact grid,
CRS, revision, sample validity, license applicability, and SHA-256 have **not**
been verified. These fields cannot be borrowed from the four older source COGs.
The additional source must pass its own native metadata and byte audit before
being used. `MISSING_COVERAGE_SOURCE_REFERENCES.json` intentionally stores null
new asset hashes and false availability flags.

Real DEM along the axis and real DEM across the viewport are different
requirements. D1/D2/D3 research viewports require 63/30/15 geographic grid cells;
the existing four COGs leave 59/26/11 additional cells, respectively. These are
derived coverage requirements, **not downloaded or verified tile inventories**.
The registry explicitly says ocean areas have no tiles. Missing ocean objects
must not be represented as certified finite real heights merely by assuming
zero elevation. A whole-viewport real-DEM certificate remains unavailable until
actual source coverage and the existing contract pass.

No new DEM is required solely for native sampling resolution. If complete real
DEM is mandatory, minimum missing spatial coverage must be acquired and audited
after the relevant hosts are available. If it is optional, the existing partial
DEM limitation remains explicit; terrain, coastline/GIS, and Event accuracy must
still pass independently. This note issues no Admission certificate and does
not revise the unknown original retrieval date or missing license field of the
historical, user-provided COG metadata.
