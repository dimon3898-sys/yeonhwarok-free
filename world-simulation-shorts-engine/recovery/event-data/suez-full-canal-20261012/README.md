# Verified whole-canal data; locked Core proof blocked

Data decision: **SUEZ_EVENT_DATA_READY**.
Proof decision: **PRODUCTION_PROOF_BLOCKED**.

This directory preserves a verified geographic display axis for the entire Suez Canal, its source evidence, the official overall length, and an actual frozen-Core compatibility check. It does not contain an approved Event video or claim Event System Final.

## Geographic identity and assembly

OpenStreetMap waterway relation **7719838 version 17** identifies the Suez Canal (`waterway=canal`, `wikidata=Q899`). Its original named, `boat=yes` main-axis ways **5038117 → 925360882** connect at exactly the same source node **33708264**. The assembled LineString retains all **92 original coordinates / 91 segments**. Only the repeated occurrence of the shared join is omitted. No coordinates, gap connectors, interpolation, tracing, shortest-path route or simplified substitute were generated.

The northern source endpoint **255329793 [32.3263323, 31.2757122]** lies in the mapped Port Said Mediterranean entrance dredged area **197425500**, with native navigation-line/recommended-track evidence. The southern endpoint **33708297 [32.5606978, 29.9303352]** is an exact source node at the Suez outlet mouth. Original line segments and nodes pass through the independently obtained Great Bitter Lake **1410016** and Little Bitter Lake **1691290** water geometries. Extent is **[32.3037758, 29.9303352, 32.5868369, 31.2757122]**, WGS84/EPSG:4326, exported longitude/latitude.

Selected-axis missing nodes, gaps, duplicate segments and branches are **0**; GDAL line validity and simplicity pass. The complete relation legitimately has parallel channels and lateral connections: all nine members and 13 branch junctions remain recorded. Seven alternate/connecting ways are excluded from this single main-axis display, without claiming those waterways do not exist. Selection follows the original named main axis and its documented end-to-end extent; no shortest-path selection was used.

Relation **7682094 remains excluded as a whole-canal geometry candidate**. Its pre-existing southern mouth boundary is supporting outlet evidence only; no boundary coordinates were used to construct the axis. The water polygons similarly validate lake passage and do not generate a centerline.

OSM is a community geographic representation, not an official SCA hydrographic coordinate certificate. This is one full-canal display axis, not all parallel routes or a synthesized offshore vessel itinerary.

## Metric and provenance

The unchanged verified Suez Canal Authority FAQ states **“The length of the canal is 193.30 Km.”** The fixture preserves `193.30` and `km` for the **overall canal**, not a selected shore or partial section. Geometry and metric describe the same overall geographic object. OSM geodesic length is not required to equal the official definition. Publication/update date is not supplied by the captured official passage and is not inferred from retrieval time.

Original full OSM responses, node IDs, ways, timestamps, source URLs and response SHA-256 are retained under `sources/osm`. `GEOMETRY_PROVENANCE.json`, `MAIN_AXIS_MEMBER_SELECTION.json` and `INDEPENDENT_COVERAGE_REVIEW.json` record assembly and scope. Official factual excerpts and their original response hashes are under `sources/sca`; full web-form pages are not runtime inputs.

License: **ODbL 1.0**, **© OpenStreetMap contributors**, https://www.openstreetmap.org/copyright and https://opendatacommons.org/licenses/odbl/1-0/. Preserve attribution and applicable database share-alike/license obligations when distributing this source or derived databases/outputs.

The fixture's north-to-south display direction follows the original way order from Port Said to Suez. It does not assert one-way navigation. The metric anchor is the unchanged northern source node and annotates the complete axis. The 150-frame timeline is an explicit **GENERATOR_RULE**, not recovered historical or reference frame timing.

## Actual locked-Core result

Common Core remains at **00ad07e4a6041ea4cc6369bfce8871762f61f152** and Camera V5 Final at **29b8ee294360812b55ef577b62411de58159003b**. All 24 active source SHA/size checks pass before and after the actual Software WebGL2 run.

The existing API compiles the canonical 30fps/150-frame/5-second production Event Plan, but enabling it at unchanged Camera frame 249 throws **EVENT_LINE_PROTECTED_GRAPHIC_COLLISION**, before drawing any Event. Capacity and Safe Area pass. A concrete original source point, node **255329759 [32.4133477, 30.3140517]**, projects to **[664.1889608053693, 782.0997140375989]**, inside the unchanged Marker protection box **[639.9314201342281, 759.7456236516225, 683.9314201342281, 803.7456236516225]**.

Actual Event OFF frames **0/144/205/249** match the approved V5 PNG and decoded RGBA hashes **BIT_EXACT**. Redrawing OFF after the rejected Event attempt restores the Final Hold **BIT_EXACT**, PNG SHA **fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673**. GL errors are 0. `PRODUCTION_RUNTIME_VALIDATION.json` records the tested fixture and Data Gate hashes. Those exact tested files remain unchanged.

No 150-frame Event capture, MP4 or PNG file was emitted. Event ON pixels outside its region cannot be validated because the guard rejects the input before any Event draw. No Marker movement/hiding, route edits, missing vertices, altered styles, collision bypass, Core changes or Camera/Renderer/Visual changes were used to force a Proof.

## Reproduce the compatibility check

Use the existing pinned V5/Core dependency setup and LFS assets. From the repository root, with Node 24.19.0, Playwright 1.62.1 and Chromium 154.0.8037.57 installed:

```sh
sha256sum -c world-simulation-shorts-engine/recovery/event-data/suez-full-canal-20261012/SHA256SUMS
node world-simulation-shorts-engine/recovery/event-data/suez-full-canal-20261012/tools/validate_production_fixture.mjs --repo . --fixture world-simulation-shorts-engine/recovery/event-data/suez-full-canal-20261012/fixture.json --data-gate-file world-simulation-shorts-engine/recovery/event-data/suez-full-canal-20261012/DATA_GATE.json --report ../suez-production-validation-new.json
```

The thin caller connects existing public APIs and writes a new private diagnostic JSON. It contains no Event, Camera or Renderer implementation. A handled rejection is recorded as `PRODUCTION_PROOF_BLOCKED`; process exit 0 does not establish a successful Event Proof. Required inputs are repository files, not temporary-session files. The output filename must be new.

## Preservation and next decision

These Source/Data/Fixture/evidence files belong only to Development. Public Review allows MP4/PNG and required SHA; no raw sources, internal plans or diagnostics were uploaded as Public Proof.

Full-canal data acquisition is complete. The remaining decision concerns truthful full-canal Event graphics coexisting with the protected existing Marker under the locked Core. This task does not authorize changes to that policy, Marker, Camera or Renderer. No Event Final or subsequent Plugin is started.
