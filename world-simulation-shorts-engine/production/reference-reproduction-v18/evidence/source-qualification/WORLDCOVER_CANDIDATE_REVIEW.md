# WorldCover 2021 bounded candidate review

Status: PROMISING_LOCAL_SAMPLES_NOT_PRODUCTION_ADMITTED. No renderer, Studio, source catalog or deployment image was changed. GPU starts, image builds, renders and MP4 encodes: zero. Existing PASS suites were not rerun.

## Actual source inspected

Official catalog: https://esa-worldcover.s3.eu-central-1.amazonaws.com/esa_worldcover_grid_composites.fgb . Product documentation: https://esa-worldcover.org/en/data-access . Exact tile URLs are resolved from that catalog, not guessed. Catalog SHA256 and coverage inventory are recorded beside this report.

Four bounded windows from three actual Sentinel-2 annual median RGBNIR COGs were decoded using verified-TLS HTTP range reads. No whole TIFF was downloaded. These are source-data inspections, not generated-engine frames. Incheon, Seoul west, Naktong and Seoul east seam windows contain respectively 512×512, 496×512, 512×512 and 512×512 decoded pixels. The west Seoul request crossed the source edge; actual clipped extent is explicitly recorded. Whole-TIFF SHA256 was not acquired; hashes identify decoded crop arrays and preview PNGs only.

Observed metadata: EPSG:4326; 12000×12000 pixels per nominal 1-degree tile; four uint16 bands R/G/B/NIR; NoData 0; pixel-is-area; 2021 annual median. All four decoded windows have zero masked samples. NoData validity is not a cloud mask or scientific cloud-free certification.

## Visual and numeric observations

The actual source previews were viewed with one fixed display mapping, clip(raw / 3000, 0, 1), no geographic editing or inpainting.

- Incheon: harbor outlines, ships/wharves, buildings and roads are visibly detailed. No conspicuous cloud or blank patch in this small crop. Modern reclamation/industrial harbor is visible; this is not evidence of a 1950 coastline.
- Seoul west/east: visible urban and forest texture, no conspicuous cloud or blank patch in the sampled area. The adjoining 127-degree edge has aligned pixel rows. Across-edge RGB absolute difference means (115.39, 102.43, 102.00 raw units) are comparable to nearby horizontal differences (left 110.87, 99.71, 95.12; right 121.94, 110.97, 106.52). This local descriptive test finds no exceptional edge jump, but is not a full mosaic seam certification.
- Naktong: river, agricultural fields and wooded relief texture are visible, no conspicuous cloud or blank patch in this small crop. Optical appearance does not supply terrain height.

## Attribution and limits

The inspected TIFF metadata explicitly states: CC-BY 4.0, https://creativecommons.org/licenses/by/4.0/ . Required provenance string retained from source metadata: “ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium”. Preview tone mapping is a display modification. This is 2021 imagery, not historical 1950 imagery.

The official catalog provides RGBNIR2021 entries for 90 of 117 nominal envelope cells. The remaining 27 cells are absent/unclassified, not assumed ocean. Only four small windows were read, not all listed rasters or timeline positions. Clouds, NoData, shoreline accuracy, offshore coverage, cross-tile color and seams across the entire camera envelope remain unqualified. No scientific cloud-mask input was present among the four RGBNIR bands.

## Next implementation gate

Do not label this optical RGB as BAKED_RELIEF_V1. Before source admission, resolve complete land/ocean coverage, source masking and zoom resolution with explicit LOD (the current 4096 texture cap cannot preserve 10m detail across the whole envelope). Then qualify targeted source assets and coordinate borders, bind through the formal source contract and existing renderer heightSource/contextTerrain, and test only affected paths. Existing BMNG/Natural Earth and the rejected EOX2016 evidence remain unchanged. GPU and image build remain on hold.
