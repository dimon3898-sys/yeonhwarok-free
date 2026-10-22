# Universal source pipeline V2 — actual software review

Actual authenticated Studio demo: 6 seconds /180 freshly drawn frames /1080×1920 /
30fps /H.264 /silent /SwiftShader. Historical Incheon G2_FULL_AREA remains BLOCKED;
historical G3 was not run. The demo has visible regional-material seams and is
NEEDS_REWORK for visual quality. No NVIDIA or user quality approval is claimed.

Read `IMPLEMENTATION_REPORT.md`, `DATA_CONTRACT.md` and `reports/GATE_STATUS.json`.
Public video/PNG hashes are in `public-review/SHA256SUMS`; the neutral source
archive and review ZIP are also covered by root `SHA256SUMS`. Fixed-commit mobile
URLs and actual HTTP/download hash evidence are in `reports/DOWNLOAD_VERIFICATION.json`.

Baseline `e6ff697348a8e63c9308d7b4546682cbc6620c96`. Independent branch and
namespace; existing G1, FINAL, engines, images, Scenes and claims are unchanged.

The new `WORLD_ENGINE_UNIVERSAL_SOURCE_SCENE_V2` family passes an explicit Scene
through the actual authenticated Studio HTTP normalizer, server-pinned source
index, existing G2 control-state provider, existing Camera V5, native Renderer,
Area V3 fill/front passes, existing Marker/Glyph, readPixels and FFmpeg.

`fixtures/DEMO_SOURCE_SCENE.json` is a nonhistorical technical example in another
region/theme. It uses authored observation-grid zones, not claimed occupation or
real pollution. Its grid domain is explicitly inside unchanged modern GIS; it is
not a historical control area or source coastline. Each frame is a persisted
sample, with owner/unknown/contested/sharedFront from one field ID and clock.
No renderer computes the authored split. No partial front is closed against a
coastline and no historical opposing ownership is inferred.

`fixtures/INCHEON_SOURCE_SCENE_BLOCKED.json` connects the actual dated PDF vector
positions. These retain PDF page coordinates and cubic commands. Geographic
transform, bilateral owner masks, LOCAL camera admission and source-qualified
historical pixel presentation remain blocked. It cannot start a render.

The native demo reuses actual Camera V5 integer states forward/hold/reverse;
historical event time is not reversed. It uses the unchanged native global
source fallback, without pretending the regional raster/ASTRA covers the world.
The G1-specific V4 shader clamps outside its raster; it is deliberately not used
outside that support. Existing regional/local detail guards stay active.

Strict contract: unknown fields, modified source dates/geometry IDs, unregistered
source bundles and unsupported transforms fail. The versioned Scene fields are
shown in the two JSON examples. Source registrations and their hashes are server
configuration, never client approval flags. Audio cue slots and custom visual
annotations are not connected in this lane; nonempty values explicitly block.
The actual demo renders an existing Glyph-based SYNTHETIC DEMO caption.

To restore the neutral inputs, use `tools/source_fixture_store.py`; it verifies
the published archive and all entries and never overwrites different existing
bytes. `tools/run_studio_demo.py` runs one explicit free source demo through the
preserved loopback Studio authentication flow. It does not deploy a service or
start NVIDIA. Historical G3, full 80 seconds and user visual approval are separate
gates. No GPU budget or authorization is forged for the software lane.
