Issue #1 - optional10-second/300-frame Studio source extension
Base:fdc4294fd2bcd528229a0f030b803c353cd3a2c4.

Implemented source contract:6s/180 remains the default; explicit10s/300 at30fps
is the only additional NVIDIA Studio sample duration. No80-second path is added.
No GPU/browser capture, image build, GHCR publication, permission change, bootstrap
work or previous PASS suite is performed. The existing aviation180/180 NVIDIA PASS
and WAR input/map/camera evidence remain historical evidence, not new test results.

NEW10-SECOND BLOCKERS TRACED AND CONNECTED
- Input qualification: FREE composite240-frame cap remains default. Only the
  private NVIDIA Studio normalizer opts into an explicit10s/30fps/300 input.
- Compiler/selection: complete contiguous timeline may be300 with opt-in. Existing
  per-scene240 limit remains, so the provided sample uses150+150 frames.
- Plan/source binding: duration_contract accepts only6/180 or10/300, fps30;
  runtime wire, plan hash, scene coverage and source qualification remain bound.
- Capture permit and adapters: both derived and actual instrumented candidate
  require explicit10/300. Receipts/frame evidence add timing only for10; the
  existing6 schemas and field shapes remain. NVIDIA/Vulkan guard and launch flags
  are unchanged; no software fallback can satisfy native receipt validation.
- Worker/supervisor: expected receipt/media/frame/progress counts and final state
  derive from the validated plan. Default supervisor API remains180; only180/300
  is allowed. Ordered frame indices cover0..299; extra/repeated/out-of-range
  progress does not establish completion.
- Media/export: 300-frame H264,30fps,1080x1920,10s,silent,full-decode validation
  and safe QA summaries use the validated contract. Original media validation,
  source-credit metadata and cleanupVerified export gates remain.
- Diagnostics: explicit10/300 bounds permit failure frame299 and count300.
  Private/error/token restrictions and first-failure/cleanup separation remain.
- Owner UI: server exposes10/300 only for a validated10 plan. The UI requires that
  exact pair matching the structured input, displays10 seconds in consent, and
  blocks missing/mismatched timing. Original HTML and default6 example are unchanged.
- Time/cost: actual approved plan/image/expiry/consent remain mandatory.600-second
  upper execution cap, policy cost ceiling, retries0, original GPU lease/ACTIVE
  claim and unresolved-cleanup behavior are unchanged. Render duration is not a
  request to raise operator wall time or stop the provider workload automatically.

SAMPLE AND EXACT REMAINING LIMITATION
GENERIC_CAMERA_TERRITORY_10S.json is a real WORLD_ENGINE_PRESENTATION_PROMPT_V2
input with two synthetic events, supplied geometry/source notes and label metadata.
It is not a frame blueprint. It preserves synthetic labeling in input/source
credits, and requests event1/zoom-in/result-hold, then zoom-out/travel/event2/hold.
See SAMPLE_README.txt for frame intervals and attribution.

VISIBLE LABEL QUALITY IS BLOCKED: the unchanged runtime sets
visibleNativeLabels:false, passes location/country/title/disclosure reveals0,
and the existing compiler explicitly rejects visible-label requests. Name fields
are displayMetadataOnly. These fields are not claimed to be visible in the video.
No unsupported-intent filter or renderer was changed to manufacture a PASS.
The source-duration extension and its focused CPU tests pass; the full requested
camera/territory/visible-label quality sample cannot be declared PASS under the
current renderer restriction. Source coverage and visual pacing are not GPU proof.

FOCUSED FREE EVIDENCE
-18 new Python controller cases PASS, exit0: contracts, native proof/media/evidence
  checks with fake media results, consent/approval/cost,300 progress/initialstate,
  diagnostics, safe export and unchanged cleanup/lease/deadline restrictions.
-9 explicit Node cases PASS, exit0: actual V2 compiler with injected admission
  boundary (prior source/map qualification reused, not rerun), actual generated
  and instrumented capture validators,300 indices, permits, diagnostics, consent
  display and blocked source/visible-label cases. A new generic6 fixture matches
  the serialized output hash generated from the pinned original compiler.
-1 changed-pin chain case PASS, exit0. It checks only changed rows/new dependencies
  and JSON row identity for inherited pins, without rehashing the inherited source
  closure. It does not repeat the old350/353-file image integrity PASS.
Total:28 distinct new focused cases. No existing PASS suite or old GPU job rerun.

Authoritative Node log is evidence/input-harness-diagnostic.log: it lists all9 case
names and pass9. Initial node--test launcher logs reported a single file-level
result without case attribution and are retained but are not counted as9 cases.
To reproduce the new cases without GPU/build/network:
python3 -I -B world-simulation-shorts-engine/recovery/studio-ten-second-v1/test_ten_second_controller.py
node --input-type=module -e "import('./world-simulation-shorts-engine/recovery/studio-ten-second-v1/test_ten_second_input.mjs')"
python3 -I -B world-simulation-shorts-engine/recovery/studio-ten-second-v1/test_changed_pins.py
These are new tests; do not run any existing suite as part of this work order.

PIN CONNECTION AND REAL-RUN BOUNDARY
Changed generated capture SHA and source rows are pinned. The checkout's historical
350-row manifest omitted the three already existing G2 diagnostics dependencies;
those are included to retain the documented353-file image closure. Only13 changed
existing rows and those3 dependencies are hashed.337 inherited rows are reused.
Bootstrap SOURCE_SHA and startup manifest links are refreshed without executing
bootstrap. Whole inherited source closure verification is NOT rerun or claimed.

Existing successful images, OCI ENTRYPOINT/digest and G2 packaging tools are
unchanged. Their old fixed source pins/profile-only overlay cannot package this
multi-file extension unchanged. A separately authorized10s packaging review/build
must bind these sources and OCI ENTRYPOINT before an approved real10s GPU attempt.
Existing21/22 preparation results do not prove a10s image has been built/published.

STOP
No actual10s image, MP4 or GPU PASS exists from this task. Preserve this commit and
new evidence. Visible-label scope requires a later explicit decision; image/GPU
validation is a separate authorization. Do not silently extend bootstrap, renderer,
budget, timeout, retries or permissions to remove these remaining blocks.
