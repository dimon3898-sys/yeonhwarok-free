# Suez Event data investigation

Status: **SUEZ_EVENT_DATA_BLOCKED**. This directory contains research evidence and native source data, not a VERIFIED production fixture.

Parent Common Core: `development/event-system-v1-20261012`, commit `00ad07e4a6041ea4cc6369bfce8871762f61f152`. Core, V5, Renderer, Terrain, palette, existing boundary/glow, layout, glyph, Scale and LOCAL remain unchanged. Data is stored on `development/suez-event-data-20261012`; Public Proof is unchanged.

## Actual acquired geometry

Natural Earth's original `ne_10m_rivers_lake_centerlines` shapefile, version 5.0.0, is pinned to repository commit `ca96624a56bd078437bca8184e78163e5039ad19` (repository snapshot date 2022-06-02; this is not asserted as the dataset publication date). The scale is **1:10,000,000**, not 10-metre spatial precision. The original PRJ specifies WGS84/EPSG:4326; exported coordinates use longitude/latitude order.

Two named Suez Canal features exist: FID 516 / ne_id 1159113913 is a Lake Centerline LineString with 11 vertices; FID 517 / ne_id 1159113931 is a River MultiLineString with 13-vertex north and 2-vertex south parts. `NATIVE_FEATURES_ONLY.json` exactly matches OGR exports of those original features. The combined native extent is `[32.296630859375, 30.01141998905662, 32.577734375, 31.272723699994117]`.

The north and lake junction coordinates do not match; their diagnostic gap is approximately 82.31m. This diagnostic is not an Event Metric. No connector, snapping, interpolation, resampling, geometry simplification or new coordinates were produced. The original multipart source is **DATA_LIMITED** for a verified continuous full-canal LineString, and completeness against later/current navigation channels is unverified. It cannot be promoted by joining unlike endpoints.

Source component SHA-256/size and available Git blob SHA were verified. The pinned maintainer repository's LICENSE declares the data public domain and permits redistribution/commercial use. Original GIS, PRJ, version, documentation, license and retrieval provenance are retained under `sources/natural-earth/`.

## Metric and access gate

The exact Suez Canal Authority characteristics page was requested, but the environment proxy denied its HTTPS tunnel with HTTP403. No official body, metric value, unit, definition or publication/update date was obtained. No remembered number, reference display value, whole shipping-itinerary distance or computed geometry length was adopted.

The original Overpass canal query and OpenStreetMap copyright page were also denied by the environment policy. A configuration Draft was saved with exactly three new hosts, preserving all existing custom rules and other fields:

- `www.suezcanal.gov.eg`: official metric definition and current characteristics.
- `overpass-api.de`: native connected canal geometry and node/way/relation provenance.
- `www.openstreetmap.org`: ODbL and attribution/use conditions.

Saving the Draft does not apply or publish it. Environment settings require review/save and Publish before retrying these destinations. No proxy/network-policy bypass was attempted.

## Resume after Publish

Recheck the recorded requests. Identify a real whole canal or officially defined segment, retain original coordinates/CRS/source/license/version/date, and verify topology and current applicability. Read the official metric and its definition, endpoint scope, qualifiers and update date; resolve differing official values before selection. Match that metric to the same chosen geographic object. Store explicit reveal direction and its geographic reason in Fixture/Data, without country-specific Engine branches.

Only after geometry, metric, semantic match, license and source gates all PASS may a production fixture be compiled. Check its footprint/annotation against the unchanged admitted REGIONAL camera, safe area and existing protected graphics through the existing Common Core. If the input cannot be read or violates those contracts, report DATA_LIMITED rather than change the Core, Camera, marker or labels.

No production fixture, Event Plan, rendered PNG or MP4 was created. The 150-frame/30fps/1080×1920/5-second Silent Proof is **NOT RUN**. It remains conditional on all data gates passing. No Event Final or next plugin stage is authorized here.

From the repository root, verify the saved investigation payload with:

```sh
sha256sum -c world-simulation-shorts-engine/recovery/event-data/suez-20261012/SHA256SUMS
```
