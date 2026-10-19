"""Reproducible, evidence-preserving review of the pinned 151 audit records.

This is a decision report generator, not a renderer.  Static inclusion, candidate
routing, CPU tests and actual output are deliberately different evidence axes.
No source/audit catalog is edited and no feature is promoted to APPLIED here.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
CATALOG = REPOSITORY / "world-simulation-shorts-engine/docs/audits/knowledge-handoff-v2-20261019/CAPABILITY_CATALOG.json"
CATALOG_SHA256 = "85f14ba4f52931b0f6248c173104529bc5b837e83655007b5140a2e2fba86861"
VALID_STATUSES = frozenset({"APPLIED", "SUPPORTING", "NOT_APPLICABLE", "BLOCKED", "UNVERIFIED"})
VALID_RELEVANCE = frozenset({"REQUIRED", "SUPPORTING", "UNRELATED"})

# One reviewed row per original identity.  These are not auto-generated guesses
# from classification or feature names.  Actions describe real remaining work,
# never permission to invent historical states, actors or GPU output evidence.
_REVIEW_TEXT = r"""
AREA.AUTOMATIC_CONTRAST|SUPPORTING|SUPPORTING|The existing native-sample contrast selector remains a supporting primitive; the production white/gold style is a separate explicitly selected style.|Keep the primitive and expose only bounded presentation options; do not claim its old standalone pass is selected.
AREA.CONTRACT|REQUIRED|BLOCKED|The master requests geographically faithful contraction, but supplied snapshots do not establish a continuously contracting occupied polygon; radial clipping is not a historical front.|Supply reviewed owner polygons and dated transition semantics; never turn radial clipping into evidence of historical occupation.
AREA.FRONT_LINE|REQUIRED|UNVERIFIED|The supplied archival lines have a source-bound Area front route; new selection can be CPU traced, but no candidate frame/output is executed.|Verify candidate front calls and exact source geometry in a separately approved five-second draw before any eighty-second render.
AREA.GROW|REQUIRED|BLOCKED|Radial coverage inside one polygon exists, but no verified continuous occupied-area growth data are supplied for every requested historical interval.|Provide reviewed dated owner polygons or explicitly approved illustrative transition semantics; do not infer occupied land from an open front.
AREA.HOLD|REQUIRED|SUPPORTING|The existing Area final hold is reusable without new history; it is a timeline primitive rather than proof of rendered visual quality.|Reuse supplied state timing and validate the final hold on the global frame clock.
AREA.IMPACT_ZONE|UNRELATED|NOT_APPLICABLE|This fixture supplies no verified disaster impact polygon or sourced impact-zone event; adding one would manufacture an event.|Leave the impact primitive available for a future source-backed event, with no impact graphics in this historical fixture.
AREA.LONG_FORM_SOURCE_CLOCK|REQUIRED|SUPPORTING|The existing monotone source-frame mapping retimes supplied states on the long global clock without adding vertices.|Preserve the existing deterministic source clock and disclose crossfade versus observed motion.
AREA.MOVE|REQUIRED|BLOCKED|A polygon translation primitive exists, but translating an occupied region along an invented trajectory would misstate this historical sequence.|Require a sourced moving-area path and matching semantics before selecting MOVE for this fixture.
AREA.NATIVE_PROTECTION|REQUIRED|UNVERIFIED|The existing bridge protects native graphics and layout; the additive presentation needs actual-frame protection verification.|Run actual candidate Safe Area and protected-pixel checks only after the five-second GPU approval.
AREA.POLYGON_VALIDATION|REQUIRED|SUPPORTING|Existing topology validation is a prerequisite for supplied owner polygons and does not repair or invent history.|Reuse the validator unchanged; reject self-intersections, unsupported wrapping and invalid holes.
AREA.PRODUCTION_WHITE_GOLD|REQUIRED|UNVERIFIED|Existing Area production style draws supplied front/owner geometry; candidate contrast and source-terrain composition remain unrendered.|Keep geometry/timing fixed and compare the candidate white core/gold halo against actual output.
AREA.PROPAGATION_RING|UNRELATED|NOT_APPLICABLE|A circular disaster propagation event is absent from this war timeline and was not requested as a war fact.|Do not inject rings to meet the integration count; preserve the separate primitive.
AREA.PROPAGATION_WAVE|UNRELATED|NOT_APPLICABLE|No sourced tsunami/wave event belongs to this historical fixture.|Keep wave support separate; never use it as a substitute for occupied-area changes.
AREA.REVEAL|REQUIRED|UNVERIFIED|Supplied polygon opacity reveal is reusable, but candidate output has not been drawn.|Verify selected area reveal against source-bound polygons without interpreting opacity as measured occupation movement.
AREA.STATE_TRANSITION|REQUIRED|UNVERIFIED|The existing transition crossfades known states and supplies no continuous historical boundary morph.|Retain source snapshots and their limits; require actual frames before claiming the requested visible expansion is achieved.
AREA.TIME_STEP|REQUIRED|SUPPORTING|Dated state selection supports the global narrative clock; a state date does not validate all coordinates on that date.|Bind time steps to source snapshot dates independently of chapter event dates.
ASTRA.BATHYMETRY_COLOR|REQUIRED|UNVERIFIED|The current material uses signed depth only under native ocean coverage; no new candidate NVIDIA output is available.|Preserve sign and coverage gating and inspect coastline/depth output in the approved preview.
ASTRA.GPU_UPLOAD_CONTRACT|REQUIRED|SUPPORTING|The existing SHA-bound neutral bundle preserves Float32/Int16/RGBA data and validity masks; upload implementation is reused.|Keep actual GPU upload/admission verification separate from CPU bundle validation.
ASTRA.NODATA_FALLBACK|REQUIRED|SUPPORTING|Per-role invalid/outside support falls back to the unchanged base material, preventing fake zero heights or fabricated coverage.|Reuse source masks and explicit fallback; record partial sample coverage in the timeline report.
ASTRA.SUPPORT_DISTANCE_BLEND|REQUIRED|UNVERIFIED|Existing support-distance blending is reused; visible seam quality for the candidate is not observed.|Inspect the actual source-support boundary at fixed scene/camera conditions after preview approval.
ASTRA.SURFACE_TEXTURE|REQUIRED|UNVERIFIED|Actual surface RGB composition exists only within valid source support; the partial sample must not be reported as global coverage.|Keep source resolution/support metadata and verify output texture selection in the approved preview.
ASTRA.TERRAIN_NORMAL_LIGHTING|REQUIRED|UNVERIFIED|Elevation-neighbor normal lighting exists and is reused, but no candidate frame verifies its final composed appearance.|Keep original heights/NoData and review terrain relief after territory/front composition.
ASTRA_CPU.BATHYMETRY_PARSER|REQUIRED|SUPPORTING|The signed NetCDF parser is a preserved data prerequisite; old parse evidence is reused instead of repeating the full data audit.|Preserve positive-up elevations, real axes and validity metadata; do not replace negative depths with zero.
ASTRA_CPU.BOUNDED_DOWNLOAD_RECOVERY|SUPPORTING|SUPPORTING|The bounded downloader is a reusable library with network grants and failure-safe cache semantics; it is not automatically active in current Studio.|Keep network acquisition opt-in and explicit; do not claim any new remote data download.
ASTRA_CPU.COPERNICUS_REQUESTS|SUPPORTING|SUPPORTING|Existing regional tile/range request planning supports changing regions but does not discover arbitrary COG layouts or prove server downloads.|Supply the source index/IFD metadata and authorized network grant when a different dataset is actually needed.
ASTRA_CPU.EXPLICIT_OCEAN_DEPTH|REQUIRED|SUPPORTING|CPU depth derivation requires an aligned explicit ocean mask, while active GPU ocean gating reuses native GIS coverage.|Keep these two contracts distinct; never classify all negative land heights as ocean.
ASTRA_CPU.GEBCO_SUBSET_REQUESTS|SUPPORTING|SUPPORTING|Existing bounded subset planning preserves source latitude direction; the current fixture uses pinned archive samples.|Require real pinned axes/metadata for a future regional request; no download-success claim is made.
ASTRA_CPU.MAPDATA_CONFIG|SUPPORTING|SUPPORTING|Neutral optional mapData configuration is reusable, but adding a JSON field alone cannot activate a GPU material or worldwide download.|Select explicit source profiles through the additive contract and keep unsupported configurations fail-closed.
ASTRA_CPU.PROVIDER_INTERFACE|REQUIRED|SUPPORTING|The three provider roles already expose source/version/license/status metadata; a universal interface is preserved without a country branch.|Use sourceId/version/bbox contracts and report unavailable/auth/license/version states explicitly.
ASTRA_CPU.RAW_TRANSFORM_CACHE|REQUIRED|SUPPORTING|Existing version/hash/CRS/bbox-addressed CPU cache remains distinct from scene MP4 cache and external durability.|Reuse checked cache identities; do not silently use corrupt or mismatched source data.
ASTRA_CPU.SURFACE_PARSER|REQUIRED|SUPPORTING|The existing PNG/worldfile/projection parser preserves color and pixel-center alignment and is not reimplemented.|Keep source/sidecar hashes and reject unsupported grids rather than guessing registration.
ASTRA_CPU.TERRAIN_PARSER|REQUIRED|SUPPORTING|The existing Float32 geographic GeoTIFF parser preserves PixelIsPoint, height values, NoData and vertical-datum declarations.|Reuse the pinned source parser and preserve unsupported-grid errors.
ASTRA_CPU.WMS_WMTS_REQUESTS|SUPPORTING|SUPPORTING|Metadata-bound NASA WMS/WMTS request generation exists, including axis conversion, but current Studio is not a live worldwide acquisition service.|Preserve internal west/south/east/north order and require actual service metadata for new requests.
AUDIO.LEGACY_BGM|UNRELATED|NOT_APPLICABLE|The legacy BGM engine exists, but this master forbids adding BGM without an actual requirement; SFX is the requested audio path.|Keep legacy BGM untouched and exclude it from the new Studio profile.
AUDIO.LEGACY_SUBTITLES|UNRELATED|NOT_APPLICABLE|The legacy subtitle implementation exists, but text-free event readability is requested and no subtitle production is authorized here.|Do not enable ASS/subtitle composition in this candidate.
AUDIO.LEGACY_TTS|UNRELATED|NOT_APPLICABLE|Legacy TTS/external narration exists but is outside this silent-text-free/SFX integration requirement.|Keep the original TTS code untouched; do not advertise or invoke it through the new prompt.
BACKUP.DROPBOX_OFFLINE_OAUTH|SUPPORTING|UNVERIFIED|Offline token renewal is implemented in a later optional backup layer, not proven selected in the current immutable image or candidate runtime.|Preserve existing Secrets and OAuth; verify secure container Secret delivery before enabling this optional layer.
BACKUP.ENCRYPTED_CHECKPOINT|SUPPORTING|UNVERIFIED|Encrypted checkpoints exist in a separate durability extension; this audit does not read private backup data or prove candidate durability.|Reuse the optional extension only with authenticated external roundtrip evidence; do not rewrite keys or backup paths.
BACKUP.FAIL_CLOSED_BARRIER|SUPPORTING|SUPPORTING|The existing optional durability barrier is a safety primitive, not permission to claim backups are active when the selected image is no-backup.|Retain fail-closed behavior if durability is selected and distinguish mount readback from external backup proof.
BACKUP.FRESH_ROOT_RESTORE|SUPPORTING|UNVERIFIED|A restore implementation exists, but no fresh-root restore for this new candidate is executed and a restore never grants paid restart approval.|Preserve checkpoint binding and require explicit safe restore verification before claiming it protects the candidate.
BACKUP.MOBILE_PKCE_CONNECT|SUPPORTING|SUPPORTING|Existing mobile PKCE/offline consent and sealed Secret registration are preserved; integration review does not repeat user authentication.|Do not request tokens again or infer gCube Secret delivery from GitHub Secret registration alone.
BACKUP.PRODUCTION_INPUT_ADAPTER|SUPPORTING|UNVERIFIED|The later backup production adapter is separate from the old operating image; its existence is not current runtime selection evidence.|Keep optional backup profile/image admission explicit and do not silently alter the active storage policy.
CAMERA.CONSERVATIVE_CHAPTER_FOCUS|REQUIRED|SUPPORTING|The existing safe chapter pan/widen focus remains a protected baseline; it does not itself implement the requested cinematic zoom/roll.|Preserve parent lock and Safe Area while testing the independent presentation camera profile.
CAMERA.GUIDED_LAYOUT_SCALE|REQUIRED|SUPPORTING|Existing measured scale tokens and native camera/layout factories are prerequisites for safe presentation changes.|Reuse tokens and layout checks unchanged; do not infer detail permission from display scale.
CAMERA.MINIMUM_CONTEXT|REQUIRED|SUPPORTING|Minimum-context framing is preserved as the camera's geographic safety owner.|Pass real supplied event geometry and reject infeasible/polar framing rather than clipping it.
CAMERA.NATURAL_TURNAROUND|REQUIRED|UNVERIFIED|The C2-continuous V5 motion evaluator is reusable, while candidate pacing/settle still needs actual frame verification.|Keep V5 unchanged and verify independent camera adaptation without discontinuity or event-before-lock.
COMBAT.LEGACY_BADGE_OVERLAY|UNRELATED|NOT_APPLICABLE|The old soldier artwork factory is superseded by the existing original national-tablet design; enabling both would duplicate icons.|Preserve the legacy artwork source and reuse only its already-shared layout primitives where required.
COMBAT.PHYSICS_SIMULATION|UNRELATED|NOT_APPLICABLE|Scientific tactical/weapon/vehicle physics is not implemented and is explicitly outside a fact-based infographic generator.|Do not infer battle physics from icon animation or add it to the prompt contract.
DETAIL.DATA_PROFILE_AUDIT|SUPPORTING|SUPPORTING|Existing data/source-quality inspection is an optional supporting validator, not evidence of a rendered detail view.|Reuse its exact source requirements if selecting closer framing; preserve strict survey results separately.
DETAIL.POST_ARRIVAL_APPROACH|REQUIRED|BLOCKED|The standalone post-lock adapter requires bound visual admission and whole-geometry safety; the new production camera bridge does not select that full adapter or provide its certificate.|Add a separately admitted adapter connection without altering V5, then verify native lock/settle in the approved preview.
DETAIL.SURVEY_LOCAL_ADMISSION|SUPPORTING|SUPPORTING|Strict survey admission remains unchanged and must not be rewritten to pretend visual-grade data is surveyed.|Preserve its original result and use the separate visual-grade contract where allowed.
DETAIL.VISUAL_GRADE_ADMISSION|REQUIRED|UNVERIFIED|Visual-grade admission needs real static/native-render evidence; CPU metadata alone cannot certify the new framing's quality.|Keep warning versus blocking semantics and obtain actual preview evidence before promoting detail admission.
EVENT.AUTOMATIC_LINE_CONTRAST|SUPPORTING|SUPPORTING|The original accent selector is a supporting contrast primitive; white/gold production front styling is separately bound.|Avoid recoloring protected events implicitly; use bounded validated presentation choices only.
EVENT.GEOGRAPHIC_LINE_ARCLENGTH|REQUIRED|SUPPORTING|Existing Event arc-length evaluation is shared by front/route primitives, so no duplicate line engine is needed.|Preserve geometry and deterministic arc-length progression.
EVENT.INTEGER_TIMELINE|REQUIRED|SUPPORTING|The existing line/hold/metric/information timeline is available for source-backed beats; selecting it must not invent a metric story.|Use verified event/timing inputs through the shared planner and omit unrequested metric annotations.
EVENT.MARKER_OCCLUSION|REQUIRED|UNVERIFIED|Marker-above-line and protected-text policy exists; actual candidate front/tablet collisions have not been rendered.|Keep existing occlusion rules and verify actual frames after the preview approval.
EVENT.METRIC_GLYPH_PRIMITIVE|SUPPORTING|SUPPORTING|The existing glyph primitive supports measured layout/date metadata; it is not a request to show the independent Suez metric.|Preserve the primitive while the candidate's text-free profile omits date/metric text overlays.
EVENT.METRIC_LAYOUT|SUPPORTING|SUPPORTING|Collision-safe metric layout remains available internally; the current fixture requires no new measured metric annotation.|Keep its protections and do not add a 193.30 km/Suez metric to an unrelated historical scene.
FLOW.DIRECTIONAL_FLOW|REQUIRED|BLOCKED|Directional movement is requested but no verified historical actor route/position chronology is supplied; schematic paths cannot become facts.|Provide sourced actor routes and causal timing; keep optional route graphics hidden as required by the master.
FLOW.ENDPOINT_PULSE|REQUIRED|BLOCKED|A factual arrival pulse needs a verified actor endpoint/time, which this fixture lacks.|Supply a source-backed endpoint and arrival frame rather than placing a pulse at an invented location.
FLOW.HEADING|REQUIRED|BLOCKED|Continuous heading exists but depends on an admitted historical route; no such route is supplied.|Validate a sourced route before reusing tangent/unwrap heading.
FLOW.MOVING_OBJECT|REQUIRED|BLOCKED|The common moving-object engine exists, but historical national unit positions/routes are missing.|Require country/role/date/location/route provenance; never copy modern counterfactual anchors into history.
FLOW.ROUTE_HOLD|REQUIRED|BLOCKED|Route/object final hold cannot represent a verified arrival before its missing route/endpoint data are supplied.|Preserve the primitive and activate it only after the historical movement inputs pass admission.
FLOW.ROUTE_REVEAL|REQUIRED|BLOCKED|Arc-length route reveal exists but the master forbids unnecessary visible paths and no factual historical route is bound.|Reuse motion evaluation only with source-backed data; keep displayed paths disabled unless separately justified.
FLOW.VISUAL_POLISH_PROFILE|REQUIRED|BLOCKED|Role-based size and arrival polish are reusable only after a legitimate historical object/route is admitted.|Preserve the approved profile without importing the Suez ship fixture or inventing historical anchors.
FRONTIER.MOVING_SCALAR_LIGHT|REQUIRED|BLOCKED|The advanced five-second light follows a one-winner monotone scalar boundary; partial historical open fronts do not define that ownership field.|Use a geometry-bound front presentation layer for supplied states and obtain full owner polygons before any scalar occupation claim.
FRONTIER.OUTER_DOMAIN_GOLD|SUPPORTING|UNVERIFIED|The advanced outer-domain glow needs registered native domain coverage; it is not interchangeable with an actual opposing-front glow.|Keep outer coastline/domain lighting distinct and verify candidate mask registration before selection.
FRONTIER.PRODUCTION_FRONT_STYLE|REQUIRED|UNVERIFIED|The existing exact supplied-front white/gold style is the same primitive as AREA.PRODUCTION_WHITE_GOLD; actual candidate output is not observed.|Reuse one canonical style pass and test visibility/synchronization in the approved preview.
FRONTIER.TERRAIN_DESTINATION_LIGHT|REQUIRED|BLOCKED|The scalar compositor receives the ASTRA-combined terrain texture, but the long Area factory does not; forwarding five style controls does not add that missing texture input.|Design a compatible independent material/front composition connection and verify real draw output without final-screen image overlays.
IMAGE.CURRENT_SOURCE_CLOSURE|REQUIRED|SUPPORTING|The immutable operating image inclusion evidence is preserved, separately from selection and the not-yet-built additive candidate.|Bind a new immutable digest/source manifest only after an authorized build; never silently fall back to the old path.
LAYOUT.UNIVERSAL_MEASURED|REQUIRED|SUPPORTING|Measured native glyph/graphic/layout protections remain reusable; UI exposure is not implied by internal availability.|Reuse actual projected reservations and measured bounds; do not move protected graphics to hide collisions.
MAP.BAKED_RELIEF|REQUIRED|SUPPORTING|Registered SHA-verified baseline relief remains the legitimate fallback outside real ASTRA support.|Preserve it rather than fabricating DEM values from RGB.
MAP.GIS_LAND_COVERAGE|REQUIRED|SUPPORTING|Native GIS coverage is the land/ocean and coastal safety owner in the existing GPU path.|Reuse same-frame coverage for ASTRA ocean gating and terrain composition.
MAP.NATIVE_WEBGL_FACTORY|REQUIRED|UNVERIFIED|The protected native factory is reused by the additive path; no new actual WebGL draw is executed in this CPU stage.|Validate imports/contracts now and reserve actual draw/readPixels for separately approved hardware execution.
MAP.PROJECTION|REQUIRED|SUPPORTING|The existing geographic projection is reused for map geometry and anchors; no country-specific projection is added.|Reject unsupported wrapped/polar geometry and use supplied region/source profiles.
MAP.REFERENCE_PRESENTATION_ROLL|REQUIRED|BLOCKED|Coherent five-second map roll exists, but the current new camera bridge forwards only conservative approach duration and does not select roll, closer zoom or a new path.|Add an independent admitted roll/overscan profile with actual layout continuity evidence; never mutate the approved camera core.
MAP.SOURCE_GRADE|REQUIRED|UNVERIFIED|The current long route already calls the supported source grade, so it is reused rather than reimplemented.|Verify grade/territory contrast at fixed Scene/camera conditions in the approved preview.
MAP.SOURCE_OCEAN_TONE|REQUIRED|UNVERIFIED|Source-derived ocean tones exist without fabricated ripple physics; actual candidate appearance is not measured.|Retain source support/coast proximity and inspect mobile contrast after the approved preview.
MAP.TERRAIN_LOD|REQUIRED|SUPPORTING|Existing framing-dependent baseline LOD remains separate from real ASTRA support/resolution.|Keep source-resolution limits explicit; do not claim additional detail from camera zoom alone.
MAP.WARM_TERRAIN_TREATMENT|REQUIRED|UNVERIFIED|Existing bounded gold/warm relief treatment is reused but final candidate gold/front separation is not observed.|Inspect the real composed terrain and frontier together without changing protected lighting sources.
PLANNER.ADVANCED_F_NOT_SELECTED|REQUIRED|SUPPORTING|This record is the audited compatibility diagnosis: old eighty-second Area routing did not select the advanced scalar F path.|Preserve the distinction and connect compatible presentation through a separate adapter instead of copying unrelated scalar history.
PLANNER.BOUNDED_TOPIC_PARSER|SUPPORTING|SUPPORTING|The offline bounded parser exists but is not a general research or arbitrary-topic planning AI.|Use the explicit versioned structured contract and reject unsupported free-text commands.
PLANNER.CACHE_IDENTITIES|REQUIRED|SUPPORTING|Existing scene/source/renderer/boundary cache identities prevent stale scene reuse and are preserved.|Include new presentation profile/signature in candidate identity without deleting old claims or results.
PLANNER.CATALOG_TOPIC_SELECTION|SUPPORTING|SUPPORTING|The supplied topic catalog is a supporting source selector with only genuinely bound entries, not a universal history database.|Require source-backed catalog additions for new topics and reject ambiguous/unsupported ones.
PLANNER.CAUSAL_TRACKS|REQUIRED|BLOCKED|Existing schematic causal tracks explicitly reject representing historical units; the fixture supplies no factual unit-contact tracks.|Provide reviewed route/contact/control timing before binding historical causal motion.
PLANNER.DATED_CHAPTERS|REQUIRED|SUPPORTING|Twelve source-bound narrative chapters already exist; narrative dates are separate from geometry snapshot dates.|Preserve the chronology and expose source uncertainty in coverage instead of inventing dated front coordinates.
PLANNER.FAMILY_DISASTER|UNRELATED|NOT_APPLICABLE|The current fixture is not a sourced disaster/tsunami event; a planner family must not be selected merely to use all modules.|Retain the family for a separately supplied disaster dataset.
PLANNER.FAMILY_LINE_METRIC|UNRELATED|NOT_APPLICABLE|No independent geographic-length/metric story is requested for this war fixture.|Keep shared line/glyph primitives supporting; do not inject the standalone Suez line/metric sequence.
PLANNER.FAMILY_TRANSPORT|REQUIRED|BLOCKED|Transport family mapping exists but requires verified route/object-role facts absent from the historical fixture.|Supply source-backed movements before enabling a transport subevent, with visible route graphics disabled when unnecessary.
PLANNER.FAMILY_WAR|REQUIRED|SUPPORTING|The existing generic WAR mapping is the correct family for supplied fronts/states and does not require a country-specific engine.|Preserve source-driven feature selection and explicitly report missing ownership/actors.
PLANNER.GENERAL_AI_RESEARCH|UNRELATED|NOT_APPLICABLE|A general historical research AI is not implemented and is outside this integration; verified supplied facts are the allowed input.|Do not present the strict JSON contract as free-form research or fabricate missing facts.
PLANNER.LEGACY_FACT_DATASET|REQUIRED|SUPPORTING|The existing fact validator remains a source/provenance/timing prerequisite across event families.|Reuse it and add strict wrapper validation rather than accepting arbitrary unknown prompt fields.
PLANNER.LEGACY_SCENE_COMPILE|REQUIRED|SUPPORTING|The existing Scene compiler is reused for source-backed visual beats, not duplicated as a historical renderer.|Keep source IDs/geometry/timing intact and bind its output through the long Scene contract.
PLANNER.LEGACY_SCENE_VALIDATE|REQUIRED|SUPPORTING|Existing chronological, lock, contiguous-beat and source-reference checks remain mandatory.|Retain validation errors and do not relax frozen V1 behavior to accept V2 fields.
PLANNER.LONG_DURATION_ALLOCATOR|REQUIRED|SUPPORTING|The existing allocator supports exact global frames without length-specific renderers.|Verify eighty seconds equals 2400 frames and retain longer-duration structural support without claiming long GPU success.
PLANNER.LONG_SCENE_SCHEMA|REQUIRED|SUPPORTING|The existing long Scene wrapper, half-open intervals and boundary signatures remain the temporal contract.|Use an additive versioned presentation wrapper while preserving parent Scene identity.
PLANNER.NATIVE_PAYLOAD_BINDING|REQUIRED|SUPPORTING|Exact native inputs and event-after-lock binding remain necessary even when the event data changes.|Reuse SHA-bound native bundles; changing bbox alone is not proof of arbitrary-region render readiness.
PLANNER.NIGHT_RUN_SCHEMATIC_COMPOSITION|UNRELATED|NOT_APPLICABLE|The standalone fourteen-second causal demonstration is synthetic/schematic and not a source of factual historical actor positions.|Preserve the fixture for tests only; do not import its routes/arrows into the war production.
PLANNER.SCENE_SPLIT|REQUIRED|SUPPORTING|Existing work-scene splitting preserves a shared event/camera clock and bounded memory.|Reuse split/cache/compose contracts without resetting state at cuts.
PLANNER.SOURCE_GEOMETRY_CLOCK|REQUIRED|SUPPORTING|Source geometry clocks deterministically select the known snapshots; transition alpha does not create observed intermediate fronts.|Preserve snapshot identity and uncertainty at every global frame.
PLANNER.SOURCE_MANIFEST|REQUIRED|SUPPORTING|Source manifests bind files and provenance; a verified event date does not certify all boundary coordinates.|Keep actual hashes and semantic limits through planner, runtime and candidate manifest.
PLANNER.STUDIO_DIRECT_SCENE|REQUIRED|SUPPORTING|This is the same direct-input route as STUDIO.DIRECT_SCENE_INPUT and must retain frozen validation.|Use the new explicit profile adapter without relaxing the old direct Scene validator.
PLANNER.TOPIC_INTENT|SUPPORTING|SUPPORTING|Supplied aliases/event families can select a topic intent, but no general reasoning model is implied.|Keep selection data-driven and return unsupported-topic errors rather than guessing.
PLANNER.V3_EXACT_METADATA_ADMISSION|REQUIRED|SUPPORTING|Exact source-generated production metadata admission protects the parent historical plan.|Reuse it unchanged before adding a separate presentation envelope.
PLANNER.V3_VISUAL_PROFILE|REQUIRED|UNVERIFIED|The existing production palette/front settings are source-bound; new bounded presentation settings need actual output confirmation.|Connect only explicitly consumed controls and compare fixed-Scene output after preview approval.
PLANNER.V4_FROZEN_80S|REQUIRED|SUPPORTING|The immutable eighty-second V4 plan remains the source parent; its historical gaps are not removed by a new prompt.|Preserve exact parent validation and block full rendering until source/quality gates pass.
PLANNER.V4_PARTIAL_ARCHIVAL_PROFILE|REQUIRED|BLOCKED|Eight approximate partial fronts cover only 850 of 2400 scheduled frames and do not establish complete bilateral occupation or actor locations.|Supply reviewed missing dated owner polygons/front coverage and historical actor data; retain partial-source disclosures.
PLANNER.VERIFIED_FACT_BINDING|REQUIRED|SUPPORTING|Existing catalog/provenance/source file SHA and identity binding is a prerequisite rather than generated historical truth.|Reuse bound facts; do not upgrade schematic or approximate geometry to surveyed precision.
SCALE.GEOGRAPHIC_ADMISSION|REQUIRED|SUPPORTING|Existing projection/coverage/scale admission remains the safety gate for regional rendering.|Preserve polar/dateline/unsupported-source errors and distinguish display scale from actual data detail.
STUDIO.ACTUAL_80S_INPUT_OUTPUT|REQUIRED|UNVERIFIED|The actual 66430/eighty-second user input, private job record and MP4 are unavailable to this integration task.|Do not claim an actual prior-output comparison; use preserved source evidence and request the artifact only when a real quality comparison is required.
STUDIO.ADVANCED_VISUAL_PROMPT|REQUIRED|SUPPORTING|The old V1 arbitrary-field/free-NL capability remains absent; a separate strict V2 structured extension is the permitted integration route.|Document exact V2 fields and reject unknown/free-text commands; do not claim V1 or arbitrary natural-language support changed.
STUDIO.AUTH_DOWNLOAD|REQUIRED|SUPPORTING|Existing authenticated allowlisted result download and SHA validation are retained.|Do not expose raw logs, credentials, private state or arbitrary file paths through the new entrypoint.
STUDIO.DETACHED_WORKER|REQUIRED|SUPPORTING|Existing detached supervisor/job identity and duplicate prevention are retained rather than replaced.|Preserve claims and job history; never restart paid work merely because a browser disconnects.
STUDIO.DIRECT_SCENE_INPUT|REQUIRED|SUPPORTING|Direct validated Scene submission remains available without reinterpretation; it is shared with PLANNER.STUDIO_DIRECT_SCENE.|Keep parent validation and choose the new explicit profile without silent old-path fallback.
STUDIO.DURATION_SELECTION|REQUIRED|SUPPORTING|The existing duration contract remains eighty through six hundred seconds, while frozen historical V4 is exactly eighty.|Do not create a separate renderer per length or claim unexecuted long GPU output.
STUDIO.EXPLICIT_RECOVERY|REQUIRED|SUPPORTING|Explicit recovery preserves original plan/audio/approval limits and reuses verified complete cache only.|Retain duplicate/deadline/cost checks and never erase claims to force a rerun.
STUDIO.EXPLICIT_START|REQUIRED|SUPPORTING|Production still needs authenticated explicit consent, preflight, approval and idempotent job start.|The new quality gate must stop eighty-second launch before five-second user approval; no paid start occurs in this task.
STUDIO.FFMPEG_COMPOSE|REQUIRED|SUPPORTING|Existing streaming scene composition, exact frame/PTS verification and full decode are reused.|Preserve order/format checks and avoid whole-video frame buffers.
STUDIO.FREE_NL_GENERATION|UNRELATED|NOT_APPLICABLE|Free natural-language historical generation is not implemented or authorized as a replacement for verified Scene data.|Reject unsupported prose and provide exact structured JSON examples instead.
STUDIO.GPU_NATIVE_ADMISSION|REQUIRED|SUPPORTING|Existing physical NVIDIA model/VRAM/WebGL admission remains mandatory; CPU tests cannot satisfy it.|Keep hardware admission and fail on SwiftShader for production; no GPU deployment is performed here.
STUDIO.HTTPS_SETUP|REQUIRED|SUPPORTING|Existing authenticated HTTPS bootstrap/registration remains unchanged.|Reuse the established secure Origin rather than trusting arbitrary Host or adding an unauthenticated setup API.
STUDIO.INTERVAL_SFX_REVISION|SUPPORTING|SUPPORTING|Existing SFX-only interval revision remains available and is the canonical alias for STUDIO.SFX_INTERVAL_REVISION.|Do not reinterpret a visual camera/territory edit as a valid audio-only revision.
STUDIO.JOB_LOOKUP|SUPPORTING|SUPPORTING|Existing authenticated job lookup reports missing IDs rather than inventing a job or auto-starting one.|Preserve old job records and require explicit creation for a genuinely new profile.
STUDIO.MOBILE_UI|REQUIRED|UNVERIFIED|The parent mobile UI exists; new profile/contract wiring must be separately verified and no live gCube session is exercised here.|Verify the explicit new route/profile and show blocked/missing-data feedback without implying production output success.
STUDIO.OPERATOR_POLICY|REQUIRED|SUPPORTING|Existing real rate/max-cost/time/retry/expiry policy remains separate from quality approval and source admission.|Preserve all policy gates; quality approval does not grant paid GPU deployment or unlimited retries.
STUDIO.ORIGIN_CSRF|REQUIRED|SUPPORTING|The existing fixed HTTPS Origin and per-session CSRF checks remain mandatory on new routes.|Reuse current authenticated dispatch and never create a public render-start API.
STUDIO.OWNER_AUTH|REQUIRED|SUPPORTING|Existing owner authentication, secure sessions and login limits remain the security owner.|Do not reset credentials or expose tokens in prompt/report/download files.
STUDIO.PER_SCENE_EXPORT|REQUIRED|SUPPORTING|Existing checked per-scene export preserves completed outputs in the mounted result store without implying external Dropbox sync.|Retain readback/SHA checks and keep external-sync status separate.
STUDIO.PREFLIGHT|REQUIRED|SUPPORTING|Existing plan/source/disk/GPU/SFX/approval preflight remains in addition to new integration gates.|Never bypass the old preflight because the new CPU contract tests pass.
STUDIO.PRIVATE_STATE|REQUIRED|SUPPORTING|Existing private POSIX state separation is preserved; shared output mounts are not trusted private caches.|Do not point private state at a shared mount or weaken symlink/ownership/mode checks.
STUDIO.SCENE_CACHE|REQUIRED|SUPPORTING|Existing successful-artifact hash validation is retained; the new profile/signature must produce separate cache identity.|Do not delete earlier successful outputs or reuse cache across mismatched presentation/source state.
STUDIO.SFX_AUTHORED_CUES|REQUIRED|SUPPORTING|Structured source-event SFX cues exist; current V1 UI overrides inner cues, so V2 must carry explicit normalized audio without silent loss.|Keep cue event/frame references exact and test the new envelope rather than advertising hidden V1 UI support.
STUDIO.SFX_CONTROLS|REQUIRED|SUPPORTING|The existing shared SFX normalizer supports bounded gain/types and real event/frame binding.|Reuse it for all aliases; document default versus explicit empty cue behavior and avoid per-change inferred sounds without facts.
STUDIO.SFX_INTERVAL_REVISION|SUPPORTING|SUPPORTING|This is an alias of STUDIO.INTERVAL_SFX_REVISION, not a second engine or additional visual-edit capability.|Preserve one implementation and its completed-parent/interval requirements.
STUDIO.SFX_MUX|REQUIRED|UNVERIFIED|Existing mux can preserve video pixels and add AAC, but no new candidate MP4/audio output is produced here.|Verify exact effective audio/video duration and clipping on the later approved output.
STUDIO.SFX_RENDER|REQUIRED|SUPPORTING|Existing original CC0 effects and frame-to-sample scheduling are reusable without extracting reference audio.|Preserve cooldown/overlap/clipping/sample-count checks and do not add TTS/BGM.
STUDIO.SFX_TOGGLE_GAIN|REQUIRED|SUPPORTING|This input-control record aliases the shared SFX normalizer; the V2 envelope must not silently erase explicit cues.|Document explicit outer/inner precedence and test gain/ON/OFF through the actual new entrypoint.
STUDIO.SOURCE_IMAGE_BINDING|REQUIRED|SUPPORTING|Exact source and immutable-image binding remains mandatory; old image inclusion is not new candidate inclusion.|Bind candidate package manifest/digest when genuinely built and reject missing/mismatched candidate runtime selection.
STUDIO.STARTUP_DIAGNOSTICS|SUPPORTING|SUPPORTING|Existing sanitized startup diagnostics remain unchanged and diagnostic mode never grants rendering.|Retain first-failure stage/code and distinguish live diagnostic service from GPU readiness.
STUDIO.STRUCTURED_PRESET|REQUIRED|SUPPORTING|The existing V1 frozen preset is preserved while the new explicit V2 profile must be separately selected.|Reject silent fallback to the old V4 route and preserve unknown-field errors.
STUDIO.TITLE_METADATA|SUPPORTING|SUPPORTING|Title remains metadata only and must not introduce on-screen text in the candidate.|Keep title storage separate from map labels, subtitles and glyph drawing.
STUDIO.VISUAL_INTERVAL_REVISION|UNRELATED|NOT_APPLICABLE|Arbitrary visual interval editing remains unimplemented and is not required to connect a new whole-video production profile.|Return the unsupported visual-revision error rather than silently changing or re-rendering protected intervals.
TERRITORY.ARCHIVAL_FRONT_ONLY|REQUIRED|BLOCKED|Partial open fronts are verified only approximately and do not define complete opposing occupied territories or continuous movement.|Retain front-only presentation where supported and block full historical occupation claims until reviewed owner polygons exist.
TERRITORY.COMPLEMENTARY_SCALAR_CONTROL|REQUIRED|BLOCKED|The five-second complementary monotone scalar classifier cannot safely represent arbitrary partial historical fronts/ownership without additional reviewed data.|Do not copy fictional scalar keyframes; require compatible source-backed control geometry or use exact supplied polygons only.
TERRITORY.GAIN_STYLE|REQUIRED|UNVERIFIED|Existing advanced gain styling is a presentation primitive; applying its look to qualified polygons must preserve their actual geographic mask.|Connect only compatible bounded style parameters and verify fixed-geometry contrast in the approved preview.
TERRITORY.SUPPLIED_AREA_COLOR|REQUIRED|BLOCKED|Qualified schematic held cores exist, but complete bilateral dated occupation polygons for all eighty seconds are missing.|Keep supplied owner colors where qualified and report the missing owner/time coverage rather than filling an inferred complement.
UNITS.HISTORICAL_PARTICIPATION_GATE|REQUIRED|SUPPORTING|The existing role/date/flag validator is essential but cannot create factual unit positions or routes.|Reuse it for supplied actors and reject unsupported roles, including falsely placed Soviet ground forces.
UNITS.NATIONAL_TABLETS|REQUIRED|BLOCKED|Original national artwork exists, but verified historical country/role/date/location anchor data are absent from this fixture.|Provide sourced actor anchors and roles; never reuse the modern counterfactual national-tablet placement as history.
UNITS.NATIVE_MARKERS|SUPPORTING|SUPPORTING|Native protected map markers remain preserved and are not evidence of historical military units.|Keep native markers distinct from national-tablet actor data and preserve their layout.
UNITS.SAFE_STATIC_SCALE|REQUIRED|BLOCKED|Bounded national-unit scale selection needs actual admitted per-frame anchors/roles; those historical inputs are missing.|First provide validated historical actor data, then reuse the static scale/safety selector without changing artwork.
WAVE.IRREGULAR_OPEN_FRONTS|UNRELATED|NOT_APPLICABLE|The approved nonphysical tsunami front sequence has no sourced event in this Korean War fixture.|Preserve the separate wave implementation and do not inject decorative waves into the war production.
"""


def _reviews() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for line in _REVIEW_TEXT.strip().splitlines():
        feature_id, relevance, status, reason, action = line.split("|", 4)
        if feature_id in result:
            raise ValueError(f"DUPLICATE_REVIEW_ID:{feature_id}")
        if relevance not in VALID_RELEVANCE or status not in VALID_STATUSES:
            raise ValueError(f"INVALID_REVIEW_ENUM:{feature_id}")
        result[feature_id] = {"relevance": relevance, "status": status,
                              "reason": reason, "nextAction": action}
    return result


def load_catalog(path: Path = CATALOG) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != CATALOG_SHA256:
        raise ValueError("AUDIT_CATALOG_SHA_MISMATCH")
    catalog = json.loads(raw)
    if catalog.get("schema") != "WORLD_ENGINE_CAPABILITY_CATALOG_V2":
        raise ValueError("AUDIT_CATALOG_SCHEMA_MISMATCH")
    return catalog, digest


def build_decisions(catalog: dict[str, Any], catalog_sha: str) -> dict[str, Any]:
    """Return review records preserving the original feature objects verbatim."""
    if catalog_sha != CATALOG_SHA256:
        raise ValueError("AUDIT_CATALOG_SHA_MISMATCH")
    features = catalog.get("features", [])
    ids = [f.get("id") for f in features]
    if len(ids) != 151 or len(set(ids)) != 151:
        raise ValueError("AUDIT_151_DISTINCT_IDS_REQUIRED")
    reviews = _reviews()
    if set(ids) != set(reviews):
        raise ValueError("REVIEW_ID_SET_MISMATCH")
    unwired = [f["id"] for f in features if f.get("classification") == "NOT_WIRED"]
    if len(unwired) != 53:
        raise ValueError("AUDIT_53_UNWIRED_REQUIRED")
    aliases: dict[str, str] = {}
    groups: dict[str, list[str]] = {}
    for group in catalog.get("overlapGroups", []):
        canonical = group["canonical"]
        group_ids = [canonical, *group["records"]]
        for feature_id in group_ids:
            aliases[feature_id] = canonical
            groups[feature_id] = group_ids
    rows = []
    for original in features:
        feature = copy.deepcopy(original)
        review = copy.deepcopy(reviews[feature["id"]])
        source_evidence = [e["evidenceId"] for e in feature["evidence"]]
        review.update({
            "decisionScope": "KOREAN_WAR_80S_UNIVERSAL_INTEGRATION_CANDIDATE_CPU_STAGE",
            "canonicalId": aliases.get(feature["id"], feature["id"]),
            "aliasGroup": groups.get(feature["id"], [feature["id"]]),
            "reviewedOriginalInput": copy.deepcopy(feature["input"]),
            "reviewedDataDependencies": copy.deepcopy(feature["dependencies"]),
            "reviewedSourceConstraints": copy.deepcopy(feature["constraints"]),
            "parentImageMembership": feature["axes"]["BUILT_IN_IMAGE"],
            "parentImageMembershipScope": "PINNED_OLD_OPERATING_IMAGE_ONLY",
            "candidateExtensionInParentImage": False,
            "candidateImage": {"state": "NOT_BUILT", "digest": None},
            "candidateOutputVerified": False,
            "executionTrace": {
                "traceKind": "STATIC_SOURCE_AND_CONTRACT_REVIEW_NOT_A_RENDER_EXECUTION",
                "historicalSourceEvidenceIds": source_evidence,
                "historicalEntrypoint": feature["input"].get("entrypoint"),
                "candidatePromptParserPlannerEvidence": "See STUDIO_CONNECTION.md and TEST_RESULTS.json; no renderer execution is implied.",
                "candidateRendererConnectionEvidence": "See PRESENTATION_CONNECTION.md and runtime_binding.mjs; source connection is not a draw result.",
                "candidateDataCoverageEvidence": "See TIMELINE_80S_COVERAGE.json; missing historical coverage remains blocked.",
                "actualCandidateRendererCalled": "NOT_EXECUTED",
                "actualCandidateOutput": "NOT_PRODUCED",
                "actual80sArtifactCompared": False,
            },
        })
        feature["integrationReview"] = review
        rows.append(feature)
    summary = dict(Counter(row["integrationReview"]["status"] for row in rows))
    return {
        "schema": "WORLD_ENGINE_INTEGRATION_FEATURE_DECISIONS_V1",
        "baselineCatalogPath": "world-simulation-shorts-engine/docs/audits/knowledge-handoff-v2-20261019/CAPABILITY_CATALOG.json",
        "baselineCatalogSHA256": catalog_sha,
        "baselineSourceCommit": catalog["sourceCommit"],
        "baselineOperatingImage": copy.deepcopy(catalog["operatingImage"]),
        "candidateImage": {"state": "NOT_BUILT", "digest": None},
        "featureCount": 151, "unwiredCount": 53,
        "statusDefinitions": {
            "APPLIED": "Actual target prompt/parser/planner/renderer/output call chain verified. No such candidate output is generated by this task.",
            "SUPPORTING": "Preserved internal validation, source contract, safety or reusable implementation. Does not assert candidate renderer execution.",
            "NOT_APPLICABLE": "Not part of this source-backed fixture; explicit reason/action supplied, implementation remains preserved.",
            "BLOCKED": "Needed for this fixture but required historical data, compatible connection or implementation is missing.",
            "UNVERIFIED": "Relevant source/connection exists, but actual target-frame/output or integration evidence is insufficient.",
        },
        "reviewPolicy": {
            "all151IdentityPreserved": True,
            "all53UnwiredReviewed": True,
            "blindAPIExposureAllowed": False,
            "reasonAgainstBlind53Exposure": "The list contains aliases, unrelated disaster/audio families, schematic-only actors and primitives needing verified geometry. Exposing all APIs would neither establish historical truth nor connect renderer output.",
            "appliedRequiresActualTargetOutput": True,
            "newRenderingExecuted": False,
            "newGPUExecution": False,
            "oldImageMembershipIsNotCandidateInclusion": True,
            "unknownFieldsMayBeIgnored": False,
            "missingHistoryMayBeInvented": False,
        },
        "overlapGroups": copy.deepcopy(catalog.get("overlapGroups", [])),
        "summary": summary,
        "requiredBlockers": [row["id"] for row in rows if row["integrationReview"]["relevance"] == "REQUIRED" and row["integrationReview"]["status"] in {"BLOCKED", "UNVERIFIED"}],
        "full80sRenderAllowed": False,
        "features": rows,
    }


def unwired_report(decisions: dict[str, Any]) -> dict[str, Any]:
    rows = [copy.deepcopy(f) for f in decisions["features"] if f["classification"] == "NOT_WIRED"]
    if len(rows) != 53:
        raise ValueError("UNWIRED_REVIEW_COUNT_MISMATCH")
    return {"schema": "WORLD_ENGINE_UNWIRED_INTEGRATION_REVIEW_V1",
            "baselineCatalogSHA256": decisions["baselineCatalogSHA256"],
            "baselineOperatingImage": copy.deepcopy(decisions["baselineOperatingImage"]),
            "count": len(rows), "allReviewed": True,
            "summary": dict(Counter(f["integrationReview"]["status"] for f in rows)),
            "reasonAgainstBlindAPIExposure": decisions["reviewPolicy"]["reasonAgainstBlind53Exposure"],
            "features": rows}


def decisions_csv(features: list[dict[str, Any]]) -> str:
    fields = ["id", "domain", "name", "originalClassification", "lifecycle", "relevance", "status", "reason", "nextAction", "canonicalId", "aliasGroup", "parentImageDigest", "parentImageMembership", "candidateImageState", "candidateOutputVerified", "executionTraceKind", "inputEntrypoint", "inputFields", "dataDependencies", "sourceEvidence", "sourceAxes"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for f in features:
        r = f["integrationReview"]
        writer.writerow({"id": f["id"], "domain": f["domain"], "name": f["name"],
            "originalClassification": f["classification"], "lifecycle": f["lifecycle"],
            **{k: r[k] for k in ("relevance", "status", "reason", "nextAction", "canonicalId", "parentImageMembership", "candidateOutputVerified")},
            "aliasGroup": ";".join(r["aliasGroup"]),
            "parentImageDigest": "sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da",
            "candidateImageState": r["candidateImage"]["state"],
            "executionTraceKind": r["executionTrace"]["traceKind"],
            "inputEntrypoint": f["input"].get("entrypoint", ""),
            "inputFields": json.dumps(f["input"].get("fields"), ensure_ascii=False, separators=(",", ":")),
            "dataDependencies": json.dumps(f["dependencies"], ensure_ascii=False, separators=(",", ":")),
            "sourceEvidence": ";".join(f"{e['path']}:{e['startLine']}:{e['symbol']}" for e in f["evidence"]),
            "sourceAxes": json.dumps(f["axes"], ensure_ascii=False, separators=(",", ":"))})
    return output.getvalue()


def write_reports(output: Path = HERE / "reports", catalog_path: Path = CATALOG) -> dict[str, Any]:
    catalog, sha = load_catalog(catalog_path)
    decisions = build_decisions(catalog, sha)
    unwired = unwired_report(decisions)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in (("FEATURE_DECISIONS_151.json", decisions), ("UNWIRED_REVIEW_53.json", unwired)):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "FEATURE_DECISIONS_151.csv").write_text(decisions_csv(decisions["features"]), encoding="utf-8")
    (output / "UNWIRED_REVIEW_53.csv").write_text(decisions_csv(unwired["features"]), encoding="utf-8")
    return decisions


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output", type=Path, default=HERE / "reports")
    args = parser.parse_args()
    result = write_reports(args.output, args.catalog)
    print(json.dumps({"features": result["featureCount"], "unwiredReviewed": result["unwiredCount"], "summary": result["summary"], "full80sRenderAllowed": False}, ensure_ascii=False))
