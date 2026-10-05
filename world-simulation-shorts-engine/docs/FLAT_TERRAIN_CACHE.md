# Source-backed terrain asset cache

`tools/prepare_flat_terrain.py` prepares geographic textures from an **already
preserved local GIS raster**. It never downloads, modifies the source, renders
video or enables FLAT mode by default. Scenes can reuse the same prepared texture.

The bundled `web/flat_assets/natural_earth_1_east_asia.png` is the native,
lossless 2880×3360 crop of the verified 21600×10800 Natural Earth source, covering
104–152°E and 7–63°N. Source/license details are in `assets/flat/SOURCES.json`.
The full 699,969,932-byte TIFF is retained in the local library and excluded from
ordinary Git. A fresh checkout can use the bundled crop without that full TIFF.
Additional crops require the separately acquired, exact pinned source file.

To prepare another supported region in an environment that already has the
original source:

```bash
.venv/bin/python tools/prepare_flat_terrain.py \
  --source library/flat/terrain/NE1_HR_LC_SR_W_DR.tif \
  --source-record library/flat/terrain/ORIGINAL_SOURCE_RECORD.json \
  --world-file library/flat/terrain/NE1_HR_LC_SR_W_DR.tfw \
  --projection-file library/flat/terrain/NE1_HR_LC_SR_W_DR.prj \
  --license-notice assets/flat/NATURAL_EARTH_PUBLIC_DOMAIN.txt \
  --bounds 104 7 152 63 \
  --max-width 4096 --max-height 4096 \
  --cache-dir web/flat_assets/cache
```

Bounds are `WEST SOUTH EAST NORTH`. Negative longitudes work normally. The tool
requires the original SHA-256, native dimensions, pinned source commit,
author/license, and matching world-file/projection hashes. Only north-up,
unrotated WGS84 geographic rasters are supported. Requests outside the raster,
dateline wrapping and polar crops return explicit errors; the caller should use
the existing Earth fallback or a separately supported projection.

The cache key includes source SHA, requested/actual source-grid bounds,
dimensions, maximum-size settings, source provenance, georeferencing and license
notice hashes, tool version and lossless PNG encoding settings. Identical calls
reuse bytes only after matching metadata and PNG SHA/dimensions. Tampered or
incomplete entries fail without overwriting either file. New entries use
exclusive creation; an interrupted partial entry remains available for diagnosis.

Arbitrary requested bounds round outwards to native source pixel edges. Renderer
UVs must use the returned `geographic_bounds`, rather than assuming the original
request fits exactly. The output only downsamples when required and never
upscales. Cartographic shaded relief is **not a survey DEM**. Crop preparation and
source-hash times are asset measurements, separate from Scene/video render times.

The targeted tests use an explicitly synthetic 8×4 temporary fixture to validate
real pixel cropping, negative-longitude registration, repeat-call reuse without
rewrites, size caps, cache tampering/missing metadata, source/projection mismatch,
invalid geographic requests and pinned provenance. They are not visual-quality
or production renderer benchmarks:

```bash
.venv/bin/python -m unittest discover -s tests -p test_flat_terrain_cache.py -v
```
