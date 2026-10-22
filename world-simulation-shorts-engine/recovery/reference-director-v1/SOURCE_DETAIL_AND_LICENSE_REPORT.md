# Source detail, coverage and licenses

**Data/source gate: DATA_DETAIL_BLOCKED.** This is a local audit of actual existing bytes, not a claim that a detailed reference basemap was acquired. All seven catalog raster files match their preserved SHA-256, byte size, decoded dimensions and license-file hash. See `reports/SOURCE_BINDING_AUDIT.json` for machine-readable evidence.

## Existing raster sources

| Source | Native dimensions | Geographic bounds `[W,S,E,N]` | Native spacing | Relevant limit |
|---|---:|---|---:|---|
| Europe/Germany NE1 crop | 1936×2776 | `[-6.1333,27.8667,26.1333,74.1333]` | 1/60° | Excludes western mainland Spain and the country's island extent; cannot cover the complete overview |
| Namibia NE1 crop | 1936×2776 | `[-1.1333,-45.1333,31.1333,1.1333]` | 1/60° | Does not cover the reference region |
| Chile NE1 crop | 3136×2716 | `[-114.1333,-59.1333,-61.8667,-13.8667]` | 1/60° | Does not cover the reference region |
| Korean peninsula NE1 crop | 1936×2776 | `[109.8667,12.8667,142.1333,59.1333]` | 1/60° | Does not cover the reference region |
| Nepal NE1 crop | 1816×2776 | `[69.8667,5.8667,100.1333,52.1333]` | 1/60° | Does not cover the reference region |
| East Asia NE1 crop | 2880×3360 | `[104,7,152,63]` | 1/60° | Does not cover the reference region |
| Global Earth day RGB | 8192×4096 | `[-180,-90,180,90]` | 0.0439453125° | Covers overview, but cannot reveal the observed tiny coastal detail |

The actual global RGB SHA-256 is `88ab060b6e7d241cfc590c69f528fab2b3247b738d40124cb590999a6fe44abc`. It is color imagery, not measured elevation, bathymetry, or a survey coastline. Survey-grade source registration is not established by the existing equirectangular UV contract.

The apparent global NE1 TIFF is **only a 134-byte Git LFS pointer**. Its expected raster is 699,969,932 bytes, 21600×10800, SHA-256 `b47bdddd1336b07f498c50eba5d70699ec57dd726a7ea0a85d2dca243236c9eb`. Neither a pointer nor metadata is a loaded raster. No missing raster was fetched in this task.

Other preserved global images are lower resolution: `earth-blue-marble.jpg` is 4096×2048, and `earth-topology.png` is 2048×1024. The latter is a graphical bump source, not a source of measured local land heights. They do not fill the missing coastal detail.

## Native detail budget

For scale illustration at latitude 36°, an equirectangular global RGB pixel spans approximately **3958 m east–west ×4892 m north–south**. One NE1 pixel spans approximately **1501×1855 m**. These are sampling estimates, not claims of source accuracy.

Conditional example only: **if** a real boundary were 85 m long, it would occupy approximately **0.0215 global-RGB pixels**, or **0.0566 NE1 pixels** east–west. The reference's final bright line is estimated at 311 original-video pixels, approximately 409 pixels after output scaling. Matching that hypothetical scale at one native raster sample per output pixel would require approximately 0.208 m/sample. The image does not independently verify the 85 m geography; this example only demonstrates the source-detail gap. A global crop enlarged thousands of times cannot be described as high-resolution local data.

The exact required ground resolution and complete rotated camera envelope cannot be solved until genuine detail geometry, boundary and anchor are supplied. The current result therefore records insufficiency, rather than inventing precise camera/ground dimensions.

## Existing ASTRA data are not new reference coverage

The preserved ASTRA CPU preparation manifest records three Korean regional sources:

- Copernicus crop: `[128.2498611,37.2501389,128.7498611,37.7501389]`.
- GEBCO source subset: `[128,37,130,39]`.
- BMNG source texture: `[124,33,132,43]`.

Those samples do not cover the reference's Spain/North Africa context. Existing separate Copernicus TIFFs are Suez tiles at N29–N30/E032–E033. Global product availability is different from local downloaded bytes. No original-height or seabed sample was invented or replaced with zero.

## License and font reuse

- Natural Earth vectors and regional NE1 crops: Public Domain; existing license file `cinematic-world-map/assets/gis/natural-earth-license.html`, SHA-256 `2631b5b39b6d1acc56de75235109b5af2dbb4b0ac5a127b6f06185977247fd4b`. Public-domain permission does not certify geographic precision.
- Global Earth day: Solar System Scope/NASA derivative under **CC BY 4.0**, as recorded in existing `earth/SOURCE_README.md` and `CREDITS_V3.txt`. Retain creator, https://www.solarsystemscope.com/textures/ and https://creativecommons.org/licenses/by/4.0/ with any eventual reviewed video. Source README SHA-256: `f6bb96c8452e6c45601a80d781b6964c30b93cb06f6ab32051b322763d0ebedb`; credits SHA-256: `2e9971a07bec997f82cb95efdda91e28f0b40ad5870743cc543c96bfa63986a2`.
- Existing bold Korean font: `world-simulation-shorts-engine/web/fonts/NotoSansCJKkr-Bold.otf`, SHA-256 `da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0`. Actual cmap contains every glyph in `세우타멜리야85 m`. License copy `LICENSE_Noto_CJK.txt`, SHA-256 `849f4ea9c214fa4ac3593b770c699f387534b11ce671264c1b10d85bdcb5997b`, contains the SIL Open Font License. Availability of glyphs is not proof that the protected existing label pass can draw them with the required rotation/placement.
- Original source-video project, original font and source map license are not supplied. The uploaded video can be analyzed in the workspace; no right to republish the original or extracted images is newly presumed.

No new map asset, source image or original reference media was distributed by this audit. Generic synthetic fixture data are newly authored and marked CC0-1.0 for tests; they are not real geographic replacements.
