# V4 minimum rebuild and reproduction procedure

Status: GATE_INCOMPLETE. This is an honest blocked procedure, not a verified full-render command.

The development branch is development/v4-minimum-rebuild-20261012. Keep the 43 preserved originals byte-identical. The final bounded protobuf-only search recovered no originals. Do not repeat Git, Release, Artifact, Container or workspace original searches.

## Required order

A. Confirm and rebuild all four missing module contracts. glyph_atlas.mjs has a concrete createMeasuredGlyph(text, style) contract and is rebuilt with the pinned existing Noto Sans CJK KR Bold font. Historical Korean measurement fixtures pass (92 checks; correction 1). boundary_glow.mjs, korean_layout.mjs and region_colors.mjs have only historical hash references; their public interfaces remain UNKNOWN. Do not fill their paths with empty exports or invent APIs. Stage A is FAIL.

B. Only after A passes, validate the complete import graph. The glyph_atlas path now exists and exports createMeasuredGlyph, but full Stage B is NOT_RUN. Do not modify renderer imports or disable Korean text.

C. Only after B passes, recover all four Terrain inputs. height.f32 is deterministically regenerable from the four preserved COG originals with their recorded hashes and atlas offsets: [0,3600], [3600,3600], [0,0], [3600,0]. Source bands are 3600x3600 native Float32, north-up, EPSG:4326, no NoData, scale1/offset0. Stitch the unmodified samples into a 7200x7200 north-up C-order little-endian Float32 grid: 207360000 bytes. No resampling, mask substitution, datum transform or new data. Verify output SHA08a1b86fbe9c47a9495336e0e83d0bfdea014a4e5c7b36beaaa544aa283fd5a8. Existing /usr/bin/python3 has GDAL3.10.3 and NumPy2.2.4. This procedure has not been executed because A fails.

context-native.png and continent-native.png require the missing exact NE1 RGB master b47bdddd1336b07f498c50eba5d70699ec57dd726a7ea0a85d2dca243236c9eb. Recorded native windows are [11222,1605,3054,5065] and [11247,1646,3003,4983], respectively. The NE1 TIFF itself cannot be reconstructed from partial crops or unrelated DSM bands. No replacement dataset, new download or approximate texture is admitted. Their recorded runtime URLs are not proof of a working file-serving mapping. C is NOT_RUN.

D. Renderer startup; E. CameraPlan compile; F. RevealPlan compile; G. Static Final Hold; H. checkpoint frames; I. V4 MP4. All remain NOT_RUN after A failure. Use unchanged V4 source/plans/layout/renderer only after prior prerequisites pass; do not fabricate startup commands or mark untested commands verified. Existing approved media is preservation evidence, not fresh rendering. Final Hold expected SHA is fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673. Only after static success compare 1080x1920,30fps,375frames,12.5seconds decoded video, camera center/extent, reveal frames, marker/label placements, checkpoints and final frame. Report BIT_EXACT, PIXEL_EQUIVALENT, VISUALLY_EQUIVALENT or MISMATCH only when an actual comparison ran. Visually equivalent alone cannot advance without user review. Limit module/Terrain correction attempts to three total; one has been used.

## Persistence and next-Gate check

Source, assets, input/asset/SHA/dependency/import manifests and a verified render procedure must be committed before persistence PASS. The current PERMANENT_GATE_MANIFEST.json keeps every known missing record and unconfirmed closure. It does not claim full runtime closure or clean reproducibility.

Run the actual read-only validator before recording Gate completion or moving to another development Gate:

```sh
python3 -B tools/validate_permanent_gate.py --repo . --manifest world-simulation-shorts-engine/recovery/v4/PERMANENT_GATE_MANIFEST.json
```

Exit1/GATE_INCOMPLETE is expected now. It blocks next-Gate/CameraV5 advancement. It does not prohibit authorized work to resolve this Gate's failures in A-I order. A clean reproduction receipt must come from a separate fixed-commit checkout, verified dependencies and actual new output; copying the approved PNG or declaring PASS in JSON is not reproduction. No clean environment renderer command has been run or established for this incomplete state.

Development contains Source+Assets+Manifest. Public review contains MP4/PNG. Never copy development files into a public Proof branch or treat public media as the source backup.
