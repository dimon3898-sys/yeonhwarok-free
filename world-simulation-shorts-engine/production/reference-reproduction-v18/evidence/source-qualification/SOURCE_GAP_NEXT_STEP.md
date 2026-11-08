# Source coverage narrowed using preserved evidence

This is new CPU geometry/sampling analysis, not another run of the existing 600-frame PASS suite.

The existing A4 Actions artifact 13605708512 was retrieved and its SHA256 matched the prior receipt exactly (2b4f8d2419e5998d72b922b05a4e617cd30788b00af0f85e981507cf043836c9). The CHROMIUM_LAYOUT_600.json member contains all actual saved viewport bounds. Their union is exactly the original 123.27404215372272–131.72595784627728 E, 32.2–44.2 N rectangle: the initial viewport already covers it. Reducing source coverage by treating it as an inflated envelope would be incorrect.

The original pinned Natural Earth 1:10m global country source was verified against its already recorded SHA256 239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255. This includes China, South Korea, North Korea, Russia and Japan within the viewport. The production scene's Korea-only context would not suffice. No polygon validity repair was needed.

All 27 optical and 30 DSM absent cells have no mapped land intersection in that generalized dataset. This classification is NO_MAPPED_LAND_AT_NE10M_SCALE, not proven ocean or zero elevation: 1:10m means 1:10-million cartographic scale, not 10-metre resolution. Small unrepresented islands and modern/historical coast differences remain limits.

## Smaller acquisition target

The 117 visible cells include 82 mapped-land cells and 35 with no mapped land. Every mapped-land cell has both an optical catalog entry and a published GLO30 entry. Publication is not raster qualification.

The minimum saved viewport height is 3.529411764705884 degrees. For 1080×1920 output, rounded-up per-degree grids need 47 land tiles at 256², 18 at 512² and 17 at 1024². With a two-pixel gutter this is approximately 78 MB decoded RGB, or 309 MB at 2× sampling, before compression. These are acquisition planning bounds, not encoded/network byte estimates or a visual-quality approval. There is no reason to download every original 12000² optical TIFF.

## Next concrete work

1. Use bounded COG overview/window acquisition for the 82 mapped-land cells, checking CRS, actual masks and source metadata. Do not infer valid imagery from catalog presence.
2. Resolve water/shoreline source policy explicitly: retain valid existing ocean context where technically compatible, preserve land/water masks, and never silently replace absent DSM land with zero.
3. Inspect complete per-scene source coverage, clouds, tile seams and sampling. Optical source treatment must be distinct from BAKED_RELIEF_V1.
4. Only then bind qualified optical/height/LOD assets through Studio's formal source path and perform focused changed-path tests. Runtime/build remains unchanged until admission.

Nine new focused evidence checks passed. Original checkpoints and PASS evidence are preserved. GPU starts, renderer runs, image builds, MP4 encodes and old-suite reruns: zero. No extra user input or payment is needed for these remaining public-data checks; this is an unfinished technical admission task, not a claim that access is blocked.

## Reproduce this evidence analysis

Place the original pinned Natural Earth GeoJSON beside the scripts using the URL and SHA256 in SOURCE_GAP_GEOMETRY_AUDIT.json. PRESERVED_FRAME_BOUNDS.json contains bounds copied from the verified existing artifact, with its source member hash. With Python and Shapely installed, run classify_coverage_gaps.py, plan_source_lod.py, then test_source_gap_evidence.py. Do not rerun camera/layout/rendering suites to recreate these bounds.

Natural Earth data are public domain: https://www.naturalearthdata.com/about/terms-of-use/ . Modern context does not establish historical borders or coastline accuracy.
