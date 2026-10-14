# CPU acquisition implementation and limits

Phase D is implemented in `astra_cpu/acquisition.py`; **46 focused tests PASS**. This task performs **zero live supplier requests/downloads**. Current cloud policy does not configure the three supplier domains, so the user-authorized request-generation/offline-response path is used. Existing ASTRA research and the completed 24-member audit are reused, not repeated.

| Source | Actual CPU implementation | Evidence and limits |
|---|---|---|
| Copernicus | Bounded index request; strict listed-key text reader → version-bound index records; bbox/date-line intersections; staged COG header probes; verified-layout block Range plans; explicit bounded full-tile fallback | Synthetic index grammar/hemispheres/missing/version tests. A GDAL-generated local COG test extracts real block offsets and decodes planned compressed bytes to exact Float32 source pixels. Original public index and original full COG are not archived; live grammar/access/header parsing is not claimed. |
| GEBCO | Strict DDS/DAS parser; coordinate-only discovery plans; subset indices from supplied actual complete axes; signed Int16 ASCII response parser with dataset/shape/axes binding | Actual supplied DDS/DAS/ASCII parsed; all 230400 values and both local axes match supplied NetCDF. Global coordinate vectors are not supplied; arbitrary global indices are not inferred from only a shape. No global elevation request. |
| NASA | Actual WMTS layer/matrix/scale/bounds/limits parser and bounded tile planner; WMS1.3 EPSG:4326 axis conversion; PNG response parsing with request-derived registration | Actual archived WMTS metadata and WMS PNG fidelity verified. CRS84/4326 axis rules and padded non-XYZ matrices tested. WMTS JPEG tiles/live availability/decoding are unverified; selected WMS PNG remains the implemented surface path. |

Requests carry pinned source ID/version, HTTPS URL, bounded response bytes, optional response hash/ETag/object size, geographic bbox, CRS/resolution and source-metadata hash. `AcquisitionPlan.status='planned'` is never a download-success claim. `expected_sha256` hashes exactly the response artifact: a requested Range is distinct from its whole object. A full-tile SHA is not applied to a metadata probe or partial block.

Copernicus batches default to at most 256 selected tiles and 512 MiB planned response bytes, with explicit tighter limits. Full-tile fallback requires opt-in plus known object size within the response limit. Missing/version-mismatched entries are explicit; no guessed all-world tile URLs are generated. Listed-name footprints are nominal one-degree candidates, not actual Point pixel edges or complete sample support; actual TIFF transform/crop remains authoritative.

GEBCO planning requires real coordinate vectors consistent with metadata. Without them, it generates bounded coordinate-only requests and a metadata-required stage. Source counts alone do not prove coordinate registration/regularity. Current decoder accepts rectilinear degree grids and rejects malformed/packed/unsupported sign/units/CRS rather than inventing depths or coordinates. Negative elevation never supplies an ocean mask.

WMTS uses the advertised CRS, OGC 0.28-mm scale definition, top-left corner, tile dimensions, matrix dimensions and optional limits. Coarse matrices may exceed layer extent; requests are clipped to declared coverage. It never substitutes Web Mercator XYZ formulas. Source nominal resolution is provenance; a larger WMS image or finer request does not prove added source detail. Static August 2004 identity is retained.

Limits apply per response, cells, tiles, ranges and Copernicus aggregate plan. No new datasets, global full-resolution raster, source research, credential values or service-limit bypass is introduced. Network transport/retry/cache results are documented separately; mocks cannot certify supplier SLA, live license terms, global real-data availability or video quality.

## Execution status

- PASS: 46 actual local acquisition tests, including supplied real responses and separately labeled generated/synthetic fixtures (`evidence/D_FINAL_TEST_RESULTS.json`).
- BLOCKED: live supplier HTTP, full public-index completeness, actual remote COG window access and global GEBCO axis acquisition; policy is not configured and no live attempt is reported.
- SKIP: WMTS JPEG decoding/upload and hardware/image-quality evaluation; outside the supplied PNG/CPU scope.
- No GPU/WebGL/rendering or existing-source modification.
