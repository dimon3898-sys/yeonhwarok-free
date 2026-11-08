# DSM inventory delta, 2026-11-08

This CPU-only source-index inventory is not source admission or a new visual-quality PASS. The preserved full-camera envelope intersects 117 nominal one-degree cells: 87 are published, 30 absent. Absence remains unclassified, not proven ocean, missing land, or zero elevation. Published tiles still require byte/hash, CRS, NoData, sample-center, seam, coverage and resolution/LOD qualification.

The prior Incheon receipt and rejected EOX2016 candidate are preserved. CHECKPOINT.json, runtime, production sources, deployment image and previous PASS evidence are unchanged. Raster downloads, old-suite reruns, GPU starts, image builds, Studio renders and MP4 encodes: zero. Five new helper checks validate only inventory arithmetic and absent-cell handling.

Source: Copernicus DEM GLO-30 AWS inventory, https://copernicus-dem-30m.s3.amazonaws.com/tileList.txt . Its SHA256 is recorded in the JSON. Provider provenance/terms: https://copernicus-dem-30m.s3.amazonaws.com/readme.html and https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM . This modern DSM does not establish 1950 terrain/coastlines. No raster is redistributed here. Preserve provider attribution in later admitted raster products.

First unfinished stage remains quality-qualified full surface/DSM coverage and suitable LOD before Studio binding. Next DSM step: classify the 30 absent cells using an authoritative land mask, then qualify necessary actual land tiles. Surface imagery remains a separate unresolved gate.
