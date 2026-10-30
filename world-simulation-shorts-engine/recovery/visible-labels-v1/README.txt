Issue #2 - generic visible presentation labels (source and CPU evidence)
Baseline:f80a6e585c5f8d25db2b66c9f0c0a9c45709b784.

IMPLEMENTED
Optional presentation.labels connects supplied metadata to real Canvas glyph
pixels and a transparent pass in the existing presentation WebGL framebuffer.
The map/camera/territory renderer is reused. There is no country-specific code,
new GPU context, finished-map image blit, automatic text/fact generation or silent
software replacement for the NVIDIA path. Missing labels leave the legacy path
without a new allocation, draw or diagnostics field. The default6-second input
and optional10-second/300-frame duration contract are unchanged.

Input (see GENERIC_LABELS_10S.json):
presentation.labels={enabled:true,items:[
 {id,role,text,locationId,eventId?,startFrame,endFrame,revealFrames?,exitFrames?,priority?}
]}
Roles are COUNTRY, EVENT and NUMERIC. COUNTRY paints a white rectangular plate
with dark bold text; event/value text is bold white with dark outline. A thin
connector follows the projected supplied location. The yellow pin has a dark
center, and is suppressed when the original primary marker already occupies it.
The COUNTRY role also supports authored region names; it has no country lookup
or per-country positioning exception. NUMERIC strings are supplied, not inferred.

The closed contract permits1..16 items, <=24 NFC graphemes and finite font-supported
Hangul syllables/basic Latin/digits/explicit ASCII punctuation. Unsupported glyphs,
controls, arbitrary font/style/URL/screen-position fields fail closed. Anchors must
match an existing supplied location exactly. EVENT/NUMERIC require an existing
highlight ID with the same location and an enclosing frame interval. Reveal,
hold and exit are determined by scene-local integer frames, not wall time.

LAYOUT AND RUNTIME CONNECTION
The existing factory.screen projection is evaluated on every draw. Measured text,
safe viewport margins, role/author priority and stable prior-slot preference
determine placement. Lower priority labels reposition or suppress instead of
covering primary event markers or earlier label/pin boxes. Offscreen anchors are
suppressed with a reason; invalid projection/font contracts block rather than
fabricate screen coordinates. Actual Canvas alpha is clipped to the safe region.

The pass draws after existing markers and before gl.finish(). It uses the same
renderer with autoClear=false, a transparent glyph CanvasTexture, y-down camera,
flipY=false, depth disabled and explicit disposal. The original map feature-pixel
proof still runs BEFORE labels, so labels cannot replace a missing map/event draw.
Original native factory labels remain off (visibleNativeLabels:false); opt-in
visiblePresentationLabels/presentationLabels describe this distinct additive pass.
Original native GPU guards, owner approval, lease, ACTIVE, cleanupVerified,
deadlines, cost limits and retry controls are untouched.

REAL PIXELS / EXACT ASSET
The new CPU tests use preinstalled @napi-rs/canvas and the SAME existing pinned
NotoSansCJKkr-Bold.otf, aliased Gate1Bold like the production factory. No substitute
system font is used. Font SHA256:
da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0
The exact asset's cmap supports every allowed Hangul/basic Latin character and
the actual sample strings. Asset identity/glyph coverage is a new label dependency
check; no previous full source/image/GPU PASS suite is repeated.

Actual pixel counts, anchor pan/zoom checks, priority/collision, primary-marker
protection, timing and compositor-construction evidence are in NEW_PIXEL_VALIDATION.
The first safe-edge case exposed a1-pixel round connector cap outside the viewport.
The Canvas clip fix and a new unsupported-glyph case passed targeted checks; all
other already successful cases were reused. Initial failure logs are preserved.

NEW FOCUSED RESULTS ONLY
-12 contract cases: initial11 PASS, then only changed case04/newcase12 PASS.
-11 CPU pixel/layout cases: initial9 PASS+one failure; only fixed08/new11 PASS.
-4 actual V2-input/compiler/capture-request integration cases PASS.
-2 font-range/changed-source-pin cases PASS.
Total29 distinct new cases PASS. Old6-second GPU, old10-second28 cases and all
other existing PASS suites were SKIP, not rerun or relabeled as new evidence.

Reproduction commands (new tests only, from repository root):
node --input-type=module -e "import('./world-simulation-shorts-engine/recovery/visible-labels-v1/test_label_contract.mjs')"
node world-simulation-shorts-engine/recovery/visible-labels-v1/test_label_pixels.mjs
node --input-type=module -e "import('./world-simulation-shorts-engine/recovery/visible-labels-v1/test_label_input_integration.mjs')"
python3 -I -B world-simulation-shorts-engine/recovery/visible-labels-v1/test_label_pins_and_font.py
The pixel script supports selective cases; do not rerun successful cases during
this work order. These commands document future reproduction, not authorization.

EXAMPLE AND CONTACT SHEET
GENERIC_LABELS_10S.json is a genuine WORLD_ENGINE_PRESENTATION_PROMPT_V2 input,
two150-frame synthetic events, authored names/values and source attribution.
Its geometry/event clocks remain unchanged when the label option is removed.
COMPILED_LABEL_PREVIEW_INPUT.json comes from the actual compiler with an injected
source-admission boundary, reusing prior map qualification rather than repeating it.

LABEL_CPU_CONTACT_SHEET.png and4 full-size PNGs use those compiled label items,
the actual font and supplied geometry as a schematic backdrop. Their projection
is explicitly a CPU region-bbox fixture; this is NOT the qualified terrain runtime,
NVIDIA draw, actual MP4, native-camera parity or a reference64306.mp4 comparison.
The contact sheet is visibly marked CPU-only. Frame210 shows the intended reveal
fade; hold-frame text is fully visible. Reference styling is interpreted only
from Issue2's generic description; no platform UI/assets/unique phrases are copied.

PINS AND STOP CONDITIONS
The original/generated runtime hashes, changed source rows, bootstrap SOURCE_SHA
and startup links are refreshed. The source closure grows353->355 for the two new
modules. Only7 changed rows/new modules are checked;346 inherited source rows are
reused without repeating full-runtime integrity checks. The exact font dependency
is checked separately for this new feature. Cold-start bootstrap is not executed.
Existing image/tag/digest, OCI ENTRYPOINT and image packaging workflows remain
unchanged. No GPU/browser capture, Actions run, image build or GHCR write occurs.

Existing fixed-pin/profile-only packaging does not cover the355-source closure
and cannot be called a new label image PASS. A separately reviewed image packaging
step and GPU approval are required for actual NVIDIA label pixels/MP4/readability.
Actual native pan/zoom/terrain occlusion and reference-style visual acceptance
remain BLOCKED/NOT_RUN. CPU evidence clears the missing-consumer source block only.
Stop after this recovery-branch commit; no automatic next stage.
