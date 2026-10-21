# P0: additional official source evidence

The new source-only front is **28 June 1950, evening**, copied from the ticked
“South Korean Front” in Appleman, *South to the Naktong, North to the Yalu*,
Map I, PDF page 49. It is a retrospective source depiction, not a surveyed
bilateral territorial boundary. Its original projection and total positional
uncertainty remain unknown.

`source-review/ADDITIONAL_FRONT_BINDINGS.json` binds the original PDF/raster,
source-pixel trace, approximate registration, supported edge subset, GeoJSON and
inspection evidence. Its classification is `OBSERVED_ROK_FRONT`. It must not be
renamed `OBSERVED_UN_FRONT` to pass the old UN-only adapter: June 1950 source
semantics and later coalition participation are separate facts.

Four fitted and four held-out modern Natural Earth place points were reused as
approximate locality references. The existing 5,000 m model-residual limit was
retained. Maximum fit residual is 775.70 m; maximum held-out residual is
3,661.88 m. These are model checks, **not total historical-map accuracy**.
The relatively small held-out footprint and checks outside the fit hull remain
warnings. Fit/check allocation, original failure and the independently reviewed
Suwon source-symbol correction are preserved. The first Suwon pixel was a
label/blank position, not the actual city circle. It was not moved to reduce
error without source evidence, and no threshold was changed.

The unchanged registration and trace modules were replayed against the actual
original raster and reference source. The canonical report and trace matched
their saved values. The three GeoJSON line parts match exactly the retained
source-coordinate arrays: 19 vertices, 16 retained edges, two unsupported edges
excluded, zero synthetic vertices. No gap, coast closure, polygon, opposing
territory, troop coordinate or transition correspondence was created.

There are two kinds of SHA in these receipts. The `sha256` of an evidence file is
the hash of its actual UTF-8 bytes. `reportSHA256`/`traceSHA256` inside the old
math reports hash the canonical JSON body before the self-hash field is added
(`ensure_ascii=False`, sorted keys, compact separators). The binding records
both explicitly; they are not interchangeable.

The finalizer reused existing official downloads and made no network request.
`reports/P0_SOURCE_ACQUISITION.json` now includes the UN Offensive booklet,
Appleman's full Army history and the Naval Historical Center Inchon history,
alongside the earlier Outbreak booklet and Truman M99. Public review packaging
must not redistribute all PDF photography under a blanket public-domain claim.
The new trace uses only the Army-authored cartographic source.

The official local maps supply further evidence, not completed runtime geometry:

| Source | Confirmed symbol/date | Remaining work |
|---|---|---|
| UN Offensive, PDF 8 | Marine positions, nights 15 and 16 September | Stable historical GCPs and source-specific registration; exclude BHL/landing arrows |
| Appleman Map VII, PDF 546 | U.S. positions 19/21/24/28 September | Verify physical landmark coordinates, fit/held-out checks and partial tracing; gray Seoul is built-up area |
| Appleman Map III, PDF 214 | Eighth Army front, evening 1 August | Separate registration and supported trace; do not use attack arrows as fronts |
| UN Offensive, PDF 16 | Forward positions, evenings 15 and 22 September | Source-specific registration; does not establish all national control |
| UN Offensive, PDF 20 | Local occupied areas, night 14 October; advance axes | No continuous national control boundary supplied |

The inherited source reviews directly inspected these map pages. This finalizer
reviewed the Map I source/trace image and replayed its geometry math; it did not
claim a new complete reading or independent georeferencing of the other maps.
Landmark API access returned proxy 403 in prior research. No repeated request or
policy bypass was attempted; the additional domain configuration is a draft,
not an applied network permission.

All twelve complete two-owner control states and supported continuous morph
correspondences remain unavailable. The new partial line can improve the
explicit June 28 source-review snapshot after the root-owned generic consumer
checks its hashes and draws it. It cannot satisfy the Seoul expansion sample
or authorize an 80-second production render. Actual draw, NVIDIA and visual
approval remain separate gates.
