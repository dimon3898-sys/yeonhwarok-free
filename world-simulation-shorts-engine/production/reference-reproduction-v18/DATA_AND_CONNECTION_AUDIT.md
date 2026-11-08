# Remaining reference-reproduction connections

Read against the deployed v16 source closure, not an imagined replacement engine.

| Requirement | Existing implementation | Actual current Studio connection | Next bounded work |
|---|---|---|---|
| HERO pin, blue label halo and grapheme reveal | `presentation_label_layer.mjs` and `reference-director-v1/director_events.mjs` | Connected when explicitly authored; current candidate uses them | Verify new diagnostic pixels and later actual MP4 |
| Terrain under the geographic tint | Existing native map renderer plus AREA overlay | Connected, but baseline tint opacity 0.52 obscured relief; candidate 0.14 | Inspect current-source contrast before any shader change |
| Real elevation shading | `web/map_infographic_v1/renderer.mjs`, `createMapInfographicRenderer(...heightSource...)`, R32F texture and `renderFrame` DEM controls | `presentation_runtime.mjs` creates the factory without `heightSource`; `presentationNativeMapOptions` sets `dem:false` | Admit a real regional height source, carry it through source bindings/server assets, pass it to existing factory and existing render controls; preserve default behavior and truthful receipts |
| Close-up coastline/surface detail | Existing source coverage/detail admission | 500m BMNG and 1:10-million generalized coastline; reducing overlay does not create detail | Source acquisition, georeferencing, licensing/attribution, hash qualification and scale-appropriate admission precede connection |
| Independent factual area colors | Current presentation colors are keyed by timeline state | All areas in the same state receive the same color | Do not fabricate two factions by recoloring all land; qualify factual independent regions first |
| Ocean surface texture | Native source RGB in the current material | No authored water-detail input was found; present source is visually flat offshore | Distinguish actual surface imagery from any optional decorative material; do not claim unsupported water detail is enabled |
| Font size, arbitrary screen placement, camera tilt | No corresponding fields in `validateLabelSpec` / `validatePresentation` | Unknown fields are rejected | No fake metadata fields; determine specific missing control after existing features are assessed |

## Source options checked on 2026-11-08

- Copernicus DEM GLO-30 is an existing renderer-supported **DSM**, not RGB imagery
  or a reconstruction of 1950 terrain. The official distribution describes 30m
  public COG tiles, with some coverage exceptions. A Korean tile and its coverage
  have **not** been downloaded or admitted in this revision.
  https://registry.opendata.aws/copernicus-dem/
  https://copernicus-dem-30m.s3.amazonaws.com/readme.html
  https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
- EOX's published pricing distinguishes 2016 imagery under CC BY 4.0 from
  2018–2025 imagery requiring noncommercial conditions or a commercial license.
  No paid EOX service was ordered, and newer mosaics were not silently treated as
  free commercial assets. This remains a possible imagery source review, not an
  installed dataset.
  https://cloudless.eox.at/pricing

DSM alone cannot fix source RGB sharpness, exact shorelines, ocean imagery or
historical changes. These are separate inputs. Never label a modified material
as reference-level terrain before its source and actual output are verified.

## Free diagnostic boundary

Local Chromium is absent (Playwright launch returned executable missing). The
existing public-repository CPU workflow uses the pinned already-built image for
13 sparse diagnostic stills through the unchanged renderer. It has no GPU device,
no network in the container, no Studio submit/start, no image build and no MP4
encode. The old MP4 and all previous PASS suites remain untouched.
