# Generic Detail Data Admission API review

Read-only review of the preserved APIs. This file does not certify any framing,
alter a protected module, or authorize a Camera/Event animation.

## Preserved API constraints

`web/map_infographic_v1/local_detail_admission.mjs` exports the existing strict
policy: at most **1 output pixel per native terrain texel**, at most **1 output
pixel of verified geometry error**, complete coverage, and the Regional
equirectangular projection. These limits must be imported, not copied into a
more permissive policy. `terrainDetailDescriptor` gives native source spacing
priority over derived image dimensions; increasing the raster dimensions never
creates detail.

`LocalDetailAdmission` requires hash-bound, verified positional and
simplification error in metres for every relevant country polygon, plus the
primary polygon even when its outer vertices are outside the viewport. Scale
denominators, coordinate count, raster resolution and OSM provenance do not
provide a positional error bound. Missing error evidence remains insufficient.
Comparing two datasets measures discrepancy; it does not by itself establish
absolute accuracy. A bound needs the independent reference's accuracy and the
measurement/simplification uncertainty, with its confidence and geographic
scope explicitly stated. Empirical sample statistics must not be presented as
a guaranteed bound over unmeasured segments.

`LOCAL_RENDER_CAPABILITIES` is currently frozen to `Point`. The verified V2
Event Line is a separate GPU pass and supports a supplied `LineString` of up to
128 segments. Its source/reveal is immutable and the full line may be occluded
only by typed protected Marker rectangles. The fixed Marker represents a
Point; it is not a replacement representation of the complete canal axis.
Relabeling the axis as Point or claiming that the preserved legacy validator
admitted the LineString would be a bypass.

`SafeClosestExtent` can legitimately return
`DATA_CERTIFIED_REGIONAL_EXTENT` after terrain/GIS/coverage pass even when the
Event is not a legacy LOCAL representation. It therefore offers a reuse path
for a closer **REGIONAL** data-certified view, while the full geographic line
is audited separately against the actual V2 pass. Its result must never be
renamed `LOCAL_ADMITTED`. Its initial assessment also requires verified data
at the approved Regional extent; a small-area accuracy audit cannot silently
be used as a bound for that larger extent.

The unchanged renderer's `updateCamera` uses the supplied locked
`layoutPlan.framing.bounds` (or the Regional plan itself) as minimum spans. A
new, independently certified Regional plan may be used as a new static input.
Omitting the old layoutPlan or replacing it with an uncertified smaller plan
to evade the minimum-span guard is not admission. The renderer source and all
old plans remain unchanged.

The default terrain treatment is `BAKED_RELIEF_V1` and demands genuine
`BAKED HILLSHADE` classification for both primary and context terrain. Raw
remote-sensing RGB cannot acquire that classification by relabeling. A
compatible derivative needs a documented build from real data, honest native
resolution, full source coverage and the unchanged treatment. Switching to
`CURRENT` would change the protected treatment.

## Suggested new contracts

New generic data/profile modules may wrap the existing policies without
editing the protected source modules. No place name, coordinate, Event id or
preferred zoom factor belongs in decision logic.

```json
{
  "version": "DETAIL_DATA_PROFILE_V1",
  "profile_id": "content-derived identifier",
  "baselines": {"renderer_sha256": "...", "policy_module_sha256": "..."},
  "projection": "REGIONAL_EQUIRECTANGULAR",
  "canonical_output": [1080, 1920],
  "sources": [
    {
      "role": "TERRAIN_OR_GIS_OR_DEM",
      "source": "organization and dataset",
      "version": "original version or dated item id",
      "retrieval_date_utc": "ISO8601",
      "license": "verifiable license/reference",
      "original_url": "public source",
      "sha256": "original bytes",
      "crs": "declared CRS",
      "native_resolution": "source resolution, not derivative resolution",
      "extent": "source footprint",
      "build_recipe": "null or reproducible recipe and inputs"
    }
  ],
  "terrain_descriptor": "existing terrainDetailDescriptor-compatible record",
  "geometries": "actual hash-bound renderer polygons",
  "event_geometry": "unchanged supplied geometry and completeness evidence",
  "quality_evidence": "existing validator-compatible verified metre bounds",
  "audit_scope": "exact geography, data hashes, reference and uncertainty",
  "safe_scale_range": "only evaluated/certified extents; null if none",
  "render_representation": {
    "effective_scale": "REGIONAL",
    "local_legacy_status": "actual preserved LocalDetailAdmission result",
    "line_pass_sha256": "actual V2 renderer capability binding"
  }
}
```

`DETAIL_QUALITY_AUDIT_V1` should retain one row per candidate with:

- Candidate bounds, centre, degree spans and derivation inputs.
- Actual source-native terrain density and full coverage, plus pixelation and
  source-water/land alignment evidence when available.
- Minimum ground metres per output pixel across the **entire** viewport,
  rather than only at the Event anchor.
- Each relevant polygon's positional plus simplification bound, source hash,
  error in screen pixels, reference provenance and verified scope.
- The complete immutable Event axis: coordinate count/hash, projected length,
  full bounds, axis coverage, halo containment and crop flag.
- V2 Marker anchor/design/size checks; fresh native glyph measurements;
  protected graphics and safe-area containment; Line footprint collision
  results; full measured Metric atlas placement and relation gap.
- Existing DEM contract, density, geographic coverage and whether DEM is a
  requirement. Optional partial coverage is a limitation, not full coverage.
- Actual `LocalDetailAdmission` and `SafeClosestExtent` results, plus the
  separate V2 LineString representation audit.
- `ADMITTED`, `NOT_ADMITTED` or `DATA_LIMITED`, with every reason and number.

`SAFE_DETAIL_EXTENT_V1` is present only when all required checks pass. Its
certificate binds the exact bounds, terrain/GIS/height/source hashes, policy,
safe area, measured protected layout, Event geometry and Metric specification.
It records that it is a new data-certified **REGIONAL** input where applicable.
Otherwise it is null. No certificate may contain an untested fixed extent.

## Candidate derivation and selection

Compute geographic bounds from every original Event vertex. In the existing
equirectangular projection, screen x/y are linear in longitude/latitude, so
full-vertex containment also contains every original segment. Add only the
unchanged finite Line halo and the Marker/text reservations. A linear safe-area
fit is a proposal; it is not a data-admission result.

Use the supplied current aspect and actual safe area to derive candidate spans
from requested readable geometry coverage. Candidate centres are derived from
the geographic bounds and remaining safe-area space, accounting for the fixed
Marker at its geographic anchor. Protected screen text reservations must come
from fresh measurements/projection for each candidate, never V2 screen
coordinates reused after zoom. Reuse `chooseRelatedMetricPlacement` with the
full projected line and marker occlusion rectangles; its full measured atlas
is the reservation, and all native labels remain strict protected exclusions.

Sort proposed candidates from least enlargement toward closer views. Select
the **first** admitted candidate satisfying the explicit generic readability
request: minimum sufficient detail. A still smaller frame that passes quality
is not preferred automatically. The readability request is separate from the
unchanged data quality thresholds; do not weaken quality to achieve visual
coverage. Every failure is retained rather than silently cropped or padded
with fabricated terrain.

## Essential tests before persistence/render

1. Already-readable full geometry keeps the current view.
2. Small geometry produces larger projected coverage with bounds derived from
   inputs; unknown positional accuracy yields `DATA_LIMITED`, never admission.
3. Long narrow geometry preserves both ends, every vertex and the finite halo;
   a length increase achieved by crop is rejected.
4. Translating the same synthetic data gives the correspondingly translated
   extent; no country/coordinate identifier affects the result.
5. Upscaling only a derivative does not improve native terrain density.
6. Terrain density exactly at the preserved limit passes; just above it fails.
7. GIS error exactly at the preserved limit passes; just above it fails. The
   worst viewport latitude, not anchor-only metres/pixel, determines the test.
8. Missing hash, stale evidence, incomplete footprint, unverified metre error,
   unsupported local representation and invalid height metadata fail closed.
9. A certified REGIONAL fallback remains REGIONAL and keeps legacy LOCAL
   denial. A forged Point stand-in cannot certify a complete LineString.
10. Metric collision/safe-area failure invalidates the candidate; native
    protected graphics, Marker anchor/size/design and Metric value/source are
    unchanged and no line coordinates are generated.
11. Native renderer receives the honestly certified static plan and enforces
    its closest spans; no camera update below that endpoint is accepted.
12. Profile/audit changes to source, extent, geometry, policy or measured layout
    invalidate the certificate binding. Protected baseline bytes remain exact.

## Existing height source qualification

The existing 7200×7200 GLO-30 Float32 source has 1/3600 degree spacing and
footprint `[31.999861111111112, 29.000138888888888, 33.99986111111111,
31.000138888888888]`. This does **not** cover the complete northern Event axis
or necessarily an entire closer candidate viewport. If height is optional in
the unchanged renderer, report sufficient density inside the footprint plus
the existing fallback limitation. If a new compatible terrain build requires
full-area real DEM, northern coverage is missing and must not be called
`DEM_EXISTING_SUFFICIENT` for that build.

## Reviewed preserved inputs

- `web/map_infographic_v1/local_detail_admission.mjs`
- `web/map_infographic_v1/scale_contract.mjs`
- `web/map_infographic_v1/renderer.mjs`
- `web/map_infographic_v1/graphic_layout.mjs`
- `web/map_infographic_v1/event_line_v1.mjs`
- `web/map_infographic_v1/event_line_pass_v1.mjs`
- `web/map_infographic_v1/event_layout_adapter_v1.mjs`
- `recovery/event-v1-v3-detail-approach/verify_baseline_admission.mjs`
- `recovery/v4/V4-state-records/input-manifest.json`
- `recovery/v4/past-paths/tmp/world-local-detail-admission/iteration-02/local-admission.json`
