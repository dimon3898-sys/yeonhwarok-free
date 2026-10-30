10-second WORLD ENGINE Studio input sample (Issue #1)

GENERIC_CAMERA_TERRITORY_10S.json is a complete authored
WORLD_ENGINE_PRESENTATION_PROMPT_V2 input, not a frame blueprint or pre-rendered
animation. It contains the existing WORLD_ENGINE_DATA_PROMPT_V1 facts contract,
two actual synthetic WAR-family area scenes, source notes, original supplied
geometry, camera keyframes, marker highlights and one real scene-cut boundary.
The existing Area/marker/camera consumers are reused; no renderer is added.

Duration and timeline
  10 seconds, 30fps, 300 frames, global indices0..299.
  Event A scene:[0,150), Event B scene:[150,300).
  Frame150 is the only cut; segment frame indices are local0..149.

Authored pacing (frame ranges below are inclusive)
  0..29   Supplied starting area appears; zoom-in begins atframe15.
  30..59  Event A marker emphasis and continued zoom-in.
  30..89  Supplied small-to-large synthetic area transition.
  60..149 Closest first view is held; result is fully visible during90..149.
  150     Cut retains Event A's supplied final geometry, front, source and color.
  150..174 Zoom out from the retained state.
  174..210 Travel with a wider view toward the supplied second camera anchor.
  210..254 Event B marker emphasis, supplied large-to-small transition, zoom-in.
  255..299 Final view and Event B result hold for45frames (1.5seconds).
This is data-driven timing, not a visual-quality or GPU-success verdict.

Source and synthetic-data labeling
  The existing FICTIONAL_AFRICA_NL.json example supplies unchanged Namibia context,
  WINDHOEK geographic anchor, illustrative area/front geometry and source notes.
  Its reference is under recovery/universal-presentation-v2/examples/ at evidence
  commit fdc4294fd2bcd528229a0f030b803c353cd3a2c4. Existing Natural Earth map context
  remains public-domain context with its original source qualification gate.
  This new input modifies only timing, camera keyframes, highlights and descriptive
  labels. data.simulationType=FICTIONAL, facts.data_mode=SYNTHETIC_TEST and
  source verification_status=SYNTHETIC_TEST remain explicit in both scenes.
  Every event date, territory shape/state, transition and color is illustrative;
  no historical occupation, military control, survey or current-traffic claim.
  Original source notes/license and per-geometry provenance remain attached.

Studio submission
  Paste/attach this V2 input as the prompt object of the existing NVIDIA Studio
  request schema WORLD_ENGINE_NVIDIA_PRESENTATION_REQUEST_V1, selecting the full
  timeline with sceneId="__timeline__". The NVIDIA private normalizer
  explicitly enables the10-second sample contract; ordinary FREE preview remains
  limited to240frames. Approval, source qualification, private storage, owner
  authorization, cost/deadline, native GPU, lease and cleanup gates still apply.
  A new input does not authorize GPU execution or promote a preview to NVIDIA PASS.

Visible-label prerequisite: BLOCKED by existing consumer, not changed here
  Subject/stage/location labels are supplied as descriptive metadata and entity
  bindings. Existing presentation_prompt.mjs classifies subject/location/marker
  names as displayMetadataOnly; requests to display labels return
  UNSUPPORTED_VISIBLE_LABELS. Existing presentation_runtime.mjs disables native
  base graphics and reports layout.visibleNativeLabels=false. It draws existing
  terrain, areas, flow and marker passes without a connected label-text pass.
  Therefore this sample truthfully supplies label metadata but does not claim
  readable on-screen label rendering. No unsupported-intent filter is relaxed,
  no fake label or software/NVIDIA PASS is produced, and no renderer is rewritten.
  Full visible-label acceptance requires a separately scoped existing-consumer
  connection or an explicit revision of that requirement; it is not silently PASS.

Scope boundary
  This sample does not build/publish an image, dispatch Actions, run a browser/GPU,
  create credentials, extend GHCR bootstrap, repeat existing PASS suites or change
  the successful6-second input. New CPU checks and remaining source/image
  packaging prerequisites are recorded by the parent Issue #1 evidence task.
