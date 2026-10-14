# Terrain and ocean V4 recipe

The engine remains the existing native renderer. Only new V4 material modules
and profiles are used by this study; every earlier source and Candidate is kept.

The raster input is the original registered Public Domain Natural Earth I East
Asia crop. Its SHA-256 is
`49127186cb2076131e49e3787454c31474e48ef206c27c6c637749173aca143a`.
It has baked shaded relief and cartographic water colour, not true height or
measured bathymetry. No image sharpening, invented geographic detail, RGB-to-height
reconstruction, upscale or downloaded substitute is performed by these modules.

1. Import `DEFAULT_REFERENCE_TERRAIN_PROFILE_V4` into the new scene fixture.
2. Create `createReferenceTerrainMaterialPassV4` with the existing verified source
   descriptor and same 1080 × 1920 native canvas.
3. Draw using unchanged camera bounds and actual native GIS coverage. The colour
   treatment retains more real source chroma and reduces local tonal exaggeration.
   Warm colour is limited to actual locally bright, varying land features.
4. Ocean colour uses original registered source tone/chroma and weighted actual
   GIS coastline proximity. Analytical ripple, glint and time phase are removed;
   it generates no fake wave texture or geography. Low source density remains a
   limitation, so natural high-detail ocean/reference parity is not claimed.
5. Consume the module's actual RGB8 framebuffer snapshot for classified territory
   lighting. The snapshot is regenerated from genuine map inputs for each frame;
   no reference-movie or concept-image pixels are used by the renderer.
6. Reuse the unchanged ownership field, native projection and presentation motion.
7. Run the two focused Node tests and root's real native/GPU static probe, then
   save and verify the remote checkpoint before a complete proof render.

The native renderer already accepts admitted R32F elevation and emits real light,
normal and coverage diagnostics. A future licensed Korea DEM could use this same
path; absent height is a data limitation, not evidence that a second map engine is
needed. The existing Suez DEM covers another geography and is never substituted.

The present gold response is artistic treatment of actual baked illumination.
It does not claim physical elevation relighting. Technical tests and an encoder's
30fps timeline do not prove real-time 30fps rendering or visual quality acceptance.
