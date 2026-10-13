/** Focused visual-polish regression. No full Permanent Gate, data audit or old proof rerender. */
import assert from 'node:assert/strict';
import path from 'node:path';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {openPolishRuntime, root, engine, repo, json, sha} from './polish_runtime.mjs';
import {assertFlowPlan, compileFlowRoute, sampleFlowRoute} from '../../web/map_infographic_v1/flow_core_v2.mjs';
import {assertFlowVisualProfile, applyFlowVisualProfile} from '../../web/map_infographic_v1/flow_visual_profile_v2.mjs';
import {evaluateGeographicLineReveal} from '../../web/map_infographic_v1/event_line_v1.mjs';

const parentFinal = 'f79f3d55d945ef0e53b03ac2ed666f48f28b5881';
const acceptedCandidate = '12715730f0d93cecf450bd51099be9e99fbdb71c';
const out = path.join(root, 'evidence'), resultFile = path.join(out, 'FOCUSED_VALIDATION.json');
await mkdir(out, {recursive: true});
const report = {schema: 1, status: 'STARTED', scope: 'FLOW_MOVEMENT_VISUAL_POLISH_ONLY',
 parentFinal, acceptedCandidate, permanentGateExecuted: false, oldFullSyntheticSuiteRepeated: false,
 dataResearchRepeated: false, startedAtUtc: new Date().toISOString()};
let session;
try {
 const [savedPlan, profileData, acceptedReport, real, fixtureProtection] = await Promise.all([
  json(path.join(root, 'fixtures/FLOW_PLAN.json')), json(path.join(root, 'fixtures/VISUAL_PROFILE.json')),
  json(path.join(engine, 'recovery/event-feature-bundle-v2/evidence/proof/REPORT.json')),
  json(path.join(root, 'fixtures/ROUTE_FLOW_REAL.json')), json(path.join(root, 'fixtures/FIXTURE_PROTECTION.json'))]);
 const plan = assertFlowPlan(savedPlan), profile = assertFlowVisualProfile(profileData);
 assert.equal(profile.objectScale, 1.20); assert.equal(plan.totalFrames, 180);
 const oldPlanBytes = await readFile(path.join(engine, 'recovery/event-feature-bundle-v2/fixtures/FLOW_PLAN.json'));
 assert.deepEqual(await readFile(path.join(root, 'fixtures/FLOW_PLAN.json')), oldPlanBytes);
 assert.equal(fixtureProtection.protection.hold_frames, 34);

 // Narrow, locked implementation owners only. Whole-baseline inventories remain the separate persistence check.
 const parentSources = ['camera_director_v5.mjs', 'camera_gpu_pipeline_v5.mjs', 'camera_detail_approach_adapter_v1.mjs',
  'visual_detail_admission_v1.mjs', 'visual_event_gpu_adapter_v1.mjs', 'renderer.mjs', 'scale_projection.mjs',
  'graphic_layout.mjs', 'event_contract_v1.mjs', 'event_timeline_v1.mjs', 'event_line_v1.mjs',
  'event_line_pass_v1.mjs', 'event_occlusion_policy_v1.mjs', 'event_style_v1.mjs'];
 report.protectedSources = [];
 for (const [commit, names] of [[parentFinal, parentSources], [acceptedCandidate, ['flow_core_v2.mjs', 'flow_graphic_pass_v2.mjs']]]) {
  for (const name of names) {
   const relative = 'world-simulation-shorts-engine/web/map_infographic_v1/' + name;
   const current = await readFile(path.join(repo, relative));
   const frozen = execFileSync('git', ['show', `${commit}:${relative}`], {cwd: repo, maxBuffer: 8 * 1024 * 1024});
   assert.deepEqual(current, frozen, 'Protected source changed: ' + name);
   report.protectedSources.push({path: relative, referenceCommit: commit, sha256: sha(current), unchanged: true});
  }
 }
 const presentationSource = await readFile(path.join(engine, 'web/map_infographic_v1/flow_visual_profile_v2.mjs'), 'utf8');
 assert(!/suez|egypt|193\.30/iu.test(presentationSource));
 report.engineGeographySpecificBranch = false;

 const testCommand = ['node', '--test', 'world-simulation-shorts-engine/tests/flow_visual_profile_v2.test.mjs'];
 const testLog = execFileSync(testCommand[0], testCommand.slice(1), {cwd: repo, encoding: 'utf8', maxBuffer: 1024 * 1024});
 await writeFile(path.join(out, 'FOCUSED_PROFILE_TESTS.log'), testLog, {flag: 'wx'});
 assert(/tests 5/u.test(testLog)); assert(/pass 5/u.test(testLog)); assert(/fail 0/u.test(testLog));
 report.profileTests = {command: testCommand, status: 'PASS', tests: 5, failures: 0,
  log: 'evidence/FOCUSED_PROFILE_TESTS.log', sha256: sha(Buffer.from(testLog))};

 const motionFields = ['objectFraction', 'objectPosition', 'heading', 'objectHeading', 'headingVector',
  'headingLookAheadPixels', 'objectVisible', 'movingObjectVisible', 'complete', 'hold', 'frame', 'localFrame',
  'state', 'stateFrame', 'stateProgress'];
 const savedFrames = acceptedReport.frames.filter(item => item.flow.enabled);
 assert.equal(savedFrames.length, 180);
 session = await openPolishRuntime({visualProfile: profile});
 // Run exact source replay in Chromium, matching the original production evaluator's math implementation.
 // Node and Chromium may differ by one ulp in atan2 despite using identical immutable source/inputs.
 report.originalCoreReplay = await session.page.evaluate(async ({plan, savedFrames}) => {
  const {evaluateFlowFrame, compileFlowRoute} = await import('/modules/flow_core_v2.mjs');
  let checked = 0;
  for (const item of savedFrames) {
   const original = item.flow.controls, ready = original.eventControls.readiness;
   const lookup = new Map(plan.intent.route_geometry.coordinates.map((point, index) =>
    [JSON.stringify(point), ready.projectedGeometry[index]]));
   const project = point => [...lookup.get(JSON.stringify(point))];
   const primitive = compileFlowRoute(plan.intent, {project});
   const eventContext = {project, safeArea: ready.safeArea, protectedBoxes: ready.protectedBoxes,
    cameraState: {scale: ready.scale, projection: ready.projection, cameraLocked: true,
     settle: {locked: true}, camera: {flatBounds: item.cameraBounds},
     admission: {status: 'LOCAL_NOT_ADMITTED', effectiveScale: ready.scale, localUsed: false}}};
   const evaluated = evaluateFlowFrame(plan, original.frame, {primitive, eventContext});
   if (JSON.stringify(evaluated) !== JSON.stringify(original)) throw Error('ORIGINAL_BROWSER_CORE_CONTROLS_CHANGED_' + item.frame);
   if (JSON.stringify(primitive) !== JSON.stringify(item.flow.primitive)) throw Error('ORIGINAL_BROWSER_ROUTE_CHANGED_' + item.frame);
   checked++;
  }
  return {status: 'PASS', frames: checked, comparison: 'EXACT_ALL_CONTROL_FIELDS_AND_PROJECTED_PRIMITIVE',
   evaluator: 'UNCHANGED_FLOW_CORE_V2_IN_PINNED_CHROMIUM'};
 }, {plan, savedFrames});
 assert.equal(report.originalCoreReplay.frames, 180);
 let previousRoute = -1, previousObject = -1, previousHeading = null;
 let maxHeadingStep = 0, maxObjectStepPixels = 0, firstComplete = null, firstOldComplete = null;
 const arrivalValues = [], frames = [];
 for (const item of savedFrames) {
  const original = item.flow.controls, ready = original.eventControls.readiness;
  const lookup = new Map(plan.intent.route_geometry.coordinates.map((point, index) =>
   [JSON.stringify(point), ready.projectedGeometry[index]]));
  const project = point => [...lookup.get(JSON.stringify(point))];
  const primitive = compileFlowRoute(plan.intent, {project});
  assert.deepEqual(primitive, item.flow.primitive, 'Projected route changed at ' + item.frame);
  const presented = applyFlowVisualProfile({flowPlan: plan, controls: original, primitive, profile});
  const visual = presented.controls;
  for (const key of motionFields) assert.deepEqual(visual[key], original[key], key + ' changed at ' + item.frame);
  assert.deepEqual(visual.eventControls, original.eventControls);
  assert(visual.routeFraction >= previousRoute); previousRoute = visual.routeFraction;
  assert(visual.objectFraction >= previousObject); previousObject = visual.objectFraction;
  assert(visual.routeFraction >= visual.objectFraction);
  assert(visual.directionalFraction >= visual.objectFraction && visual.directionalFraction <= visual.routeFraction);
  assert.deepEqual(visual.routeReveal, evaluateGeographicLineReveal(primitive, visual.routeFraction));
  const expectedObject = sampleFlowRoute(primitive, visual.objectFraction, {lookAheadPixels: visual.headingLookAheadPixels});
  assert.deepEqual(visual.objectPosition, expectedObject.position);
  if (previousHeading !== null) maxHeadingStep = Math.max(maxHeadingStep,
   Math.abs(Math.atan2(Math.sin(visual.heading - previousHeading), Math.cos(visual.heading - previousHeading))));
  previousHeading = visual.heading;
  if (frames.length) {
   const previous = frames.at(-1).objectPosition;
   maxObjectStepPixels = Math.max(maxObjectStepPixels, Math.hypot(visual.objectPosition[0] - previous[0], visual.objectPosition[1] - previous[1]));
  }
  if (visual.routeFraction === 1 && firstComplete === null) firstComplete = {flowFrame: original.localFrame, globalFrame: item.frame};
  if (original.routeFraction === 1 && firstOldComplete === null) firstOldComplete = {flowFrame: original.localFrame, globalFrame: item.frame};
  if (visual.arrivalPulse.active) arrivalValues.push({flowFrame: original.localFrame, globalFrame: item.frame,
   alpha: visual.arrivalPulse.alpha, radius: visual.arrivalPulse.radius});
  if (visual.hold) {assert.equal(visual.routeFraction, 1); assert.equal(visual.pulse.alpha, 0);}
  frames.push({globalFrame: item.frame, flowFrame: original.localFrame, objectFraction: visual.objectFraction,
   objectPosition: visual.objectPosition, heading: visual.heading, routeFraction: visual.routeFraction,
   directionalFraction: visual.directionalFraction, motionFieldsExact: true, hold: visual.hold});
 }
 assert(maxHeadingStep < .25); assert.equal(frames.filter(item => item.hold).length, 34);
 assert.deepEqual(firstOldComplete, {flowFrame: 32, globalFrame: 92});
 assert.deepEqual(firstComplete, {flowFrame: 97, globalFrame: 157});
 assert.equal(arrivalValues.length, 18);
 assert.deepEqual(arrivalValues.map(item => item.flowFrame), Array.from({length: 18}, (_, index) => 128 + index));
 assert.equal(arrivalValues[0].alpha, 0); assert.equal(arrivalValues.at(-1).alpha, 0);
 const arrivalPeak = arrivalValues.reduce((chosen, item) => item.alpha > chosen.alpha ? item : chosen);
 assert.equal(arrivalPeak.flowFrame, 132); assert.equal(arrivalPeak.globalFrame, 192);
 let maxima = 0, falling = false, lastAlpha = -1;
 for (const pulse of arrivalValues) {
  assert(pulse.alpha >= 0 && pulse.alpha <= 1); assert(pulse.radius <= 64);
  if (!falling && pulse.alpha < lastAlpha) {maxima++; falling = true;}
  if (falling) assert(pulse.alpha <= lastAlpha);
  lastAlpha = pulse.alpha;
 }
 assert.equal(maxima, 1);
 report.controls = {status: 'PASS', frames: 180, originalCoreEvaluationsExact: 180,
  objectMotionFieldsUnchanged: motionFields, routeGeometryUnchanged: true, projectedRouteUnchanged: true,
  routeRevealMonotonic: true, objectFollowsOriginalArcLength: true, directionalTravelerOnVisibleRoute: true,
  maxWrappedHeadingStepRadians: maxHeadingStep, maxObjectStepPixels,
  beforeRouteComplete: firstOldComplete, afterRouteComplete: firstComplete,
  arrivalPulse: {oneShot: true, activeFrames: 18, singleMaximum: true, peak: arrivalPeak},
  holdFrames: 34, beforeObjectSize: [52, 30], afterObjectSize: [62.4, 36], framesData: frames};

 report.native = {status: 'STARTED', backend: session.info.backend, frames: []};
 const safe = session.detailPlan.safeArea;
 for (const frame of [0, 26, 60, 72, 80, 120, 170, 192, 239]) {
  const capture = await session.page.evaluate(frame => window.flowProof.capture(frame, {protect: true, png: false}), frame);
  const diagnostic = capture.diagnostic, gpu = diagnostic.native.gpu, protection = diagnostic.flow.protection;
  assert.equal(diagnostic.glError, 0); assert.equal(gpu.glError, 0);
  assert.equal(protection.protectedChangedPixels, 0); assert.equal(protection.markerChangedPixels, 0);
  assert.equal(protection.outsideRoiChangedPixels, 0);
  assert.deepEqual(diagnostic.camera.flatBounds, acceptedReport.frames[frame].cameraBounds);
  assert.equal(gpu.layoutValidation.valid, true); assert.deepEqual(gpu.layoutValidation.failures, []);
  assert(!gpu.layout.some(item => item.role === 'SCENARIO_DISCLOSURE'));
  assert(!gpu.visibleRoles.includes('SCENARIO_DISCLOSURE'));
  const title = gpu.layout.find(item => item.role === 'EVENT_TITLE');
  const location = gpu.layout.find(item => item.role === 'LOCATION_LABEL');
  assert.equal(title.text, real.subject.title); assert.equal(location.text, fixtureProtection.text_cleanup.remaining.location);
  assert(gpu.visibleRoles.includes('EVENT_TITLE')); assert(gpu.visibleRoles.includes('LOCATION_LABEL'));
  for (const item of gpu.layout.filter(item => gpu.visibleRoles.includes(item.role))) {
   const [x, y, width, height] = item.box;
   assert(x >= safe[0] && y >= safe[1] && x + width <= safe[2] && y + height <= safe[3], 'Visible native graphic outside safe area');
  }
  if (frame < 60) {assert.equal(diagnostic.flow.enabled, false); assert.equal(diagnostic.flow.controls, null);}
  else {
   assert.equal(diagnostic.camera.cameraLocked, true);
   for (const key of motionFields) assert.deepEqual(diagnostic.flow.controls[key], acceptedReport.frames[frame].flow.controls[key]);
   assert.deepEqual(diagnostic.flow.primitive, acceptedReport.frames[frame].flow.primitive);
   assert.equal(diagnostic.flow.graphics.nativeStateRestored, true); assert.equal(diagnostic.flow.style.width, 7);
   for (const roi of diagnostic.flow.graphics.rois) assert(roi[0] >= safe[0] && roi[1] >= safe[1]
    && roi[2] <= safe[2] && roi[3] <= safe[3], 'Flow finite support outside safe area');
   if (diagnostic.flow.graphics.object) assert.deepEqual(diagnostic.flow.graphics.object.graphicDimensions, [62.4, 36]);
  }
  report.native.frames.push({frame, state: diagnostic.state, raw_rgba_sha256: capture.raw_rgba_sha256,
   cameraBounds: diagnostic.camera.flatBounds, cameraLocked: diagnostic.camera.cameraLocked,
   originalObjectMotionExact: frame >= 60, protection, glError: 0, layoutValid: true, visibleSafeAreaFailures: 0,
   visibleRoles: gpu.visibleRoles, removedDisclosureAbsent: true, remainingText: {title: title.text, location: location.text},
   hiddenGeographicLabels: diagnostic.native.hiddenGeographicLabels,
   flowGraphics: diagnostic.flow.graphics, visualProfile: diagnostic.flow.visualProfile});
  console.log(JSON.stringify({phase: 'POLISH_FOCUSED_NATIVE', frame, state: diagnostic.state,
   protectedChangedPixels: 0, markerChangedPixels: 0, visibleSafeAreaFailures: 0}));
 }
 assert.deepEqual(session.errors, []); report.native.status = 'PASS'; report.native.browserErrors = [];
 report.textCleanup = {removed: ['이동 예시'], nativeDisclosureAbsentInAllSampledFrames: true,
  remaining: fixtureProtection.text_cleanup.remaining, existingNativeGlyphStyleUnchanged: true};
 report.criticalCollisions = 0; report.status = 'PASS';
 console.log(JSON.stringify({status: report.status, originalObjectFramesExact: 180, nativeFrames: report.native.frames.length,
  beforeRouteComplete: firstOldComplete, afterRouteComplete: firstComplete,
  arrivalPeak: {flowFrame: arrivalPeak.flowFrame, globalFrame: arrivalPeak.globalFrame}, holdFrames: 34}));
} catch (error) {
 report.status = 'FAIL'; report.error = error.stack ?? error.message; throw error;
} finally {
 report.completedAtUtc = new Date().toISOString();
 await writeFile(resultFile, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
 await session?.close();
}
