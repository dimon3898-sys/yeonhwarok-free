# Raw catalog point source audit — v022

All 291 inherited catalog points were compared directly with the actual raw source. PASS: 33 Natural Earth city Points, 242 Natural Earth country label Points and 16 OurAirports airport coordinates; coordinate mismatch count is 0. The three raw files also match their catalog-declared SHA256 hashes. Runtime, registry and profile were not changed.

## What each hash means

For a registry Point whose `provenance.selector.kind` is `location_catalog`, `source_feature_sha256` hashes the preserved catalog entry. It does **not** claim to hash the original upstream GeoJSON feature or CSV row. `source_file_sha256` hashes the original raw source file. The accompanying JSON supplies both the canonical catalog-entry hash and the separate original raw-feature/row hash, original selector, extraction rule and exact coordinate comparison for every point.

Country Polygon/MultiPolygon and native Suez canal registry records directly preserve the native feature geometry and raw feature hash. Country label points remain separate Point records; no label point, port waypoint or city point is promoted to a boundary, area or canal line.

## Coordinate and source limits

- City Points use the GeoJSON Point geometry coordinates. Some separate longitude/latitude properties differ; those properties are not substituted.
- Country label Points use source `LABEL_X`/`LABEL_Y`. They are representative map labels, not geographic centroids or political boundaries. Country Polygon/MultiPolygon holes and native parts remain intact.
- Airport CSV coordinates are latitude,longitude; the registry stores longitude,latitude in EPSG:4326, without invented values or coordinate rounding.
- Natural Earth `10m` and `50m` mean cartographic scales 1:10 million and 1:50 million, not 10 or 50 metre accuracy. The native Suez data consists of two source features, three disjoint parts and 26 unchanged vertices. An approximately 82.237 m native gap remains disconnected. The separate inherited Suez representative waypoint lies approximately 2.377 km from this generalized centerline. No connector, precise blockage boundary or survey-grade accuracy is claimed.
- Natural Earth is public domain; OurAirports/DataHub uses ODC PDDL1.0. Separate inherited searoute shipping points use Apache2.0 and retain attribution. Runtime-readable licenses and GIS source manifest are bundled under `data/infographic/v022` and its identical `web` mirror.

This is source/coordinate verification. It does not prove that an airport is currently operating or that a real canal closure/reopening occurred. CLOSED/OPEN in the new QA remain explicitly watermarked hypothetical states. GPU output, projected pixel quality and human video acceptance remain NOT_RUN in this audit.
