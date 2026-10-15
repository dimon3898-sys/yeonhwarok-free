# ASTRA_GPU_UPLOAD_BUNDLE_V1

This is a new resource-transfer contract, not an active renderer or hardware PASS. It consumes typed existing `ProviderResult`/`RasterData` objects, or the unchanged `prepare_scene`→`CpuDataPipeline.prepare` results.

Original scalar Float32 elevation, signed Int16 positive-up elevation and RGBA uint8 color are retained with original dtype/byte SHA and original metadata. Upload encoding is little-endian R32F/RED/FLOAT, R16I/RED_INTEGER/SHORT and RGBA8/RGBA/UNSIGNED_BYTE. Endian conversion changes byte order only, including NaN payloads and signed zero. Invalid source values are retained; separate R8UI valid bytes are0/1. RGB sources, unsupported scalar precision or CRS are explicit errors rather than conversions.

Actual Float64 x/y sample centers and GDAL corner transform are separate hash-bound artifacts. Source row order, Point/Area registration, CRS, actual support bbox, original resolution, vertical datum, source URL/version/SHA, attribution and warnings stay in the manifest. No half-pixel relocation, resampling, edge stretching, synthetic missing data, mask creation or height/depth derivation is performed. GEBCO negative land remains signed land elevation until actual GIS classification says otherwise.

Default aggregate binary budget64MiB; hard limit256MiB; manifest2MiB; maximum16parts per source; CPU planning dimension limit default16,384 and maximum32,768. These are input bounds, not device support. The actual GL MAX_TEXTURE_SIZE is separately checked before allocation. Textures use NEAREST, no mipmaps, no Y flip, no premultiplication, no implicit color transfer and tightly packed alignment1. Float64 axes remain CPU metadata; no arbitrary GPU float64 format is assigned.

An export requires a new explicit absolute directory. Files are exclusive and fsynced, and UPLOAD_BUNDLE.json is published last. Existing outputs are never overwritten; a failed partial directory remains without a success manifest. This local CPU export is not Dropbox remote durability or result receipt.

Browser loading requires an independent expected manifest SHA, bounded same-origin fetch without redirects, per-file size/SHA and total-byte checks. It validates shape, original-byte SHA, transform/centers, support flags, CRS, units and byte order before allocation. The opaque verified handle does not expose mutable arrays. Creation failure deletes resources and restores GL bindings/pixel-store state. A real WebGL2 context is not proof of NVIDIA; this helper neither issues GPU admission nor permits a render.

Unavailable/version/license/auth/invalid statuses remain explicit and allocate no values. Partial support always requires `UNCHANGED_BASELINE_OUTSIDE_SOURCE_OR_INVALID`; the future material must implement this policy before activation. Current flat rectilinear EPSG:4326 sampling is the supported contract. Wrapped requests require existing provider-split non-wrapping parts; projected, rotated and Globe sampling are unsupported here. No country or fixed scene bbox selects data in core logic.

`planScreenDepthSampling` only checks a supplied native coverage buffer's hash, shape, frame, camera and projection identity against expected frame context. It does not rasterize coastline, sample depths, verify real shoreline alignment, issue an admission or draw. Actual geographic sampling and partial-coverage fallback remain material-integration work. It must never infer ocean from negative elevation.

BMNG's original unknown ICC/sRGB/gamma declarations remain unknown; encoded channels are uploaded without implicit conversion. EGM2008 terrain and GEBCO mixed mean-sea-level datum caveats remain distinct. A later material must document any color transfer/lighting before hardware comparison.
