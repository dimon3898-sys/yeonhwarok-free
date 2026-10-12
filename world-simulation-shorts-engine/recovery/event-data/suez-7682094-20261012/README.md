# Suez candidate 7682094: actual source validation

Decision: **SUEZ_EVENT_DATA_BLOCKED**. The official metric is verified. This candidate geometry does not describe the same object.

The Common Core remains frozen at `00ad07e4a6041ea4cc6369bfce8871762f61f152`, with Camera V5 Final `29b8ee294360812b55ef577b62411de58159003b`. All 24 active source hashes remain unchanged. This directory stores data and rejected-candidate evidence only; it contains no complete production fixture, Event Plan or rendered Proof.

## Official fact

The Suez Canal Authority FAQ was retrieved successfully. Under “What is the length of the Canal?” it states: “The length of the canal is 193.30 Km.” `VERIFIED_METRIC.json` preserves the display string `193.30`, unit `km`, numeric value 193.3, authority, official URL, captured passage and source body SHA. Publication/update date is not supplied by the captured passage and is not inferred from its retrieval date. This is the overall canal's official length; its value is not required to equal a length computed from OSM coordinates.

Only the relevant official factual quotation, retrieval metadata and body hash are committed. The original fetched page is retained privately; changing web UI/form fields are not runtime inputs.

## Actual OSM candidate

The original full response is `sources/relation-7682094-full.osm`, retrieved from `https://www.openstreetmap.org/api/0.6/relation/7682094/full`. Original bytes, all member ways/node coordinates, tags, versions and timestamps are retained. SHA-256: `901a85fed2d4ac4da9c9d70a9fee01ac4511babd26decf116ebaf4240c72f6ba`.

Relation version 5 has `type=multipolygon`, `natural=water`, `water=canal`. All four members are `outer` boundary ways: 387050169, 387050172, 387050173 and 535420894. There are 1,291 unique nodes. Extent is `[32.5595792, 29.9263939, 32.5884493, 30.1644151]`; coordinates are WGS84/EPSG:4326, longitude/latitude when exported.

The ring's source-node connectivity passes: missing ways/nodes 0, duplicate segments 0, branch nodes 0, endpoint gaps 0, valid/simple polygon. Its validated boundary traversal is way 387050169 FORWARD → 387050172 REVERSE → 387050173 FORWARD → 535420894 REVERSE. These describe a closed shoreline ring, not a vessel navigation direction.

This southern water-surface polygon is not a continuous navigation centerline or the entire canal route. A Suez Canal name tag alone cannot establish complete coverage. Attaching the overall 193.30km metric to this southern perimeter, a shore, or a partial centerline fails **GEOMETRY_METRIC_SEMANTIC_MATCH**. The geometry was not flattened, snapped, simplified, interpolated or converted into an invented route.

## License and preservation

© OpenStreetMap contributors. OSM data is available under the Open Database License (ODbL) 1.0: `https://opendatacommons.org/licenses/odbl/1-0/`. `sources/OSM_LICENSE.json` records the actual copyright-page quotation, attribution/use conditions, URL, retrieval time and SHA. Retain the ODbL/attribution with this source and any permitted derived database/output.

The original XML is stored on the Development data branch, separate from Public Review. Runtime Source, Fixture/Data and source licensing must not be published as Public Proof. No Public Release was changed.

## Gate consequence

No production fixture or 5-second MP4/PNG was created because the whole-route/semantic gate failed. Event OFF pixel rendering was not rerun on an invalid fixture; the preserved Common Core's earlier Event OFF evidence remains unchanged. Data integrity/topology tests and active source SHA checks were performed without Camera, Renderer, Visual or Core modifications.

Required next input is a verified full-canal navigation route/centerline with actual member nodes and provenance for the same overall canal object. A different explicitly defined section would require its own verified section-specific metric. Do not infer a centerline from this water polygon, invent connectors, or substitute the reference geometry/value.

Verify the stored data from the repository root:

```sh
sha256sum -c world-simulation-shorts-engine/recovery/event-data/suez-7682094-20261012/SHA256SUMS
```
