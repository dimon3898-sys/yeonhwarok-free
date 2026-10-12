import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileEventIntent} from '../web/map_infographic_v1/event_contract_v1.mjs';
import {compileEventPlan} from '../web/map_infographic_v1/event_timeline_v1.mjs';
import {generateDetailExtentCandidates} from '../web/map_infographic_v1/detail_data_profile_v1.mjs';
import {createEventDetailFramingRequest} from '../web/map_infographic_v1/visual_detail_admission_v1.mjs';
import {compileCameraDetailApproach, assertCameraDetailApproachPlan, evaluateCameraDetailApproachFrame,
 assessCameraDetailMotion, detailSmootherstep} from '../web/map_infographic_v1/camera_detail_approach_adapter_v1.mjs';

const source = () => ({source_type: 'SYNTHETIC_TEST', source_reference: 'fixture://camera-detail-extension', verification_status: 'SYNTHETIC_TEST'});
const geometry = () => ({type: 'LineString', coordinates: [[-.2, -1], [0, 0], [.2, 1]]});
const out = [1080, 1920], safe = [80, 120, 1000, 1800], start = [-8, -12, 8, 12], target = [-2, -3, 2, 3];
const event = (g = geometry(), direction = 'FORWARD') => compileEventPlan(compileEventIntent({data_mode: 'SYNTHETIC_TEST',
 line: {geometry: g, direction, style_role: 'EVENT_HIGHLIGHT', source: source(), anchor: [0, 0]},
 metric: {display_value: '120.5', unit: 'km', source: source(), anchor: [0, 0]}}),
 {fps: 30, profile: {ready_frames: 1, line_reveal_frames: 59, line_hold_frames: 15, metric_reveal_frames: 30, information_hold_frames: 45}, seed: 5});
function request(g = geometry(), bounds = target, decision = 'DETAIL_APPROACH_REQUIRED') {
 const binding = JSON.stringify({coordinates: g.coordinates, type: g.type});
 return {version: 'EVENT_DETAIL_FRAMING_REQUEST_V1', decision, targetFraming: {bounds: [...bounds], output: [...out], safeArea: [...safe]},
  eventGeometryBinding: binding, currentCameraState: {flatBounds: [...start]}, eventAnchor: [0, 0],
  certificate: {version: 'VISUAL_DETAIL_ADMISSION_V1', status: 'VISUAL_DETAIL_ADMITTED', candidateId: 'SYNTHETIC_DETAIL',
   bounds: [...bounds], eventGeometryBinding: binding, output: [...out], safeArea: [...safe],
   evidenceKind: 'SYNTHETIC_TEST_ONLY', productionEligible: false, surveyDetailStatus: 'NOT_ADMITTED'}};
}
const input = () => ({currentCamera: {flatBounds: [...start]}, framingRequest: request(), eventPlan: event(),
 eventGeometry: geometry(), output: [...out], safeArea: [...safe], mode: 'SYNTHETIC_TEST'});
const compile = () => compileCameraDetailApproach(input());
function context(p) {
 const b = p.targetBounds;
 return {cameraState: {scale: 'REGIONAL', projection: 'FLAT_GEOGRAPHIC', cameraLocked: true, settle: {locked: true},
  camera: {flatBounds: [...b]}, admission: {status: 'LOCAL_NOT_ADMITTED', effectiveScale: 'REGIONAL', localUsed: false}},
  project: point => [(point[0] - b[0]) / (b[2] - b[0]) * out[0], (b[3] - point[1]) / (b[3] - b[1]) * out[1]],
  safeArea: [...safe], protectedBoxes: []};
}

test('default approach adds sixty frames to the exact unchanged 150-frame Event plan', () => {
 const p = compile();
 assert.equal(p.totalFrames, 210); assert.equal(p.durationSeconds, 7); assert.equal(p.detailLockFrame, 60);
 assert.deepEqual(p.timeline.map(b => [b.state, b.startFrame, b.endFrame]), [
  ['EVENT_ARRIVAL', 0, 5], ['DETAIL_DECISION', 5, 6], ['DETAIL_APPROACH', 6, 48], ['DETAIL_SETTLE', 48, 60],
  ['DETAIL_LOCK', 60, 61], ['LINE_REVEAL', 61, 120], ['LINE_HOLD', 120, 135],
  ['METRIC_REVEAL', 135, 165], ['INFORMATION_HOLD', 165, 210]]);
 assert.deepEqual(p.eventPlan, event());
});
test('first and final approach samples exactly equal source and admitted bounds', () => {
 const p = compile();
 assert.deepEqual(evaluateCameraDetailApproachFrame(p, 6).flatBounds, start);
 assert.deepEqual(evaluateCameraDetailApproachFrame(p, 47).flatBounds, target);
 for (let frame = 48; frame < p.totalFrames; frame++) assert.deepEqual(evaluateCameraDetailApproachFrame(p, frame).flatBounds, target);
});
test('quintic motion decelerates with analytic zero velocity and acceleration at both endpoints', () => {
 assert.equal(detailSmootherstep(0), 0); assert.equal(detailSmootherstep(1), 1);
 const h = 1e-4;
 assert(detailSmootherstep(h) / h < 1e-6); assert((1 - detailSmootherstep(1 - h)) / h < 1e-6);
 for (const t of [-1, 1.1, NaN]) assert.throws(() => detailSmootherstep(t), /NORMALIZED_TIME/);
 const p = compile(), frames = Array.from({length: 42}, (_, i) => evaluateCameraDetailApproachFrame(p, i + 6));
 const delta = frames.slice(1).map((f, i) => Math.abs(Math.log(f.extent[0] / frames[i].extent[0])));
 assert(delta[0] < delta[10]); assert(delta.at(-1) < delta[30]);
 assert(delta.at(-1) < .001);
});
test('aspect and monotonic shrinking remain stable with no sampled hard cut', () => {
 const p = compile(), evidence = assessCameraDetailMotion(p);
 assert.equal(evidence.status, 'PASS'); assert.equal(evidence.continuousInterpolant, true);
 assert(evidence.maximumNormalizedCornerStep < .04); assert(evidence.maximumLogSpanStep < .07);
 assert.equal(evidence.exactStart, true); assert.equal(evidence.exactTarget, true);
 let previous = Infinity;
 for (let f = 0; f < p.totalFrames; f++) {
  const state = evaluateCameraDetailApproachFrame(p, f);
  assert(Math.abs(state.extent[0] / state.extent[1] - 2 / 3) < 1e-12);
  assert(state.extent[0] <= previous + 1e-12); previous = state.extent[0];
 }
});
test('every motion sample retains unchanged geometry, complete halo and anchor within Safe Area', () => {
 const p = compile(), evidence = assessCameraDetailMotion(p);
 assert.equal(evidence.framesChecked, 210); assert.equal(evidence.wholeGeometryAndHaloSafeEveryFrame, true);
 assert.equal(evidence.geometryRegenerated, false); assert.deepEqual(p.eventGeometry, geometry());
 for (let f = 0; f < 210; f++) {
  const s = evaluateCameraDetailApproachFrame(p, f).safety;
  assert(s.wholeGeometryVisible); assert(s.anchorVisible);
  assert(s.projectedHaloBounds[0] >= safe[0]); assert(s.projectedHaloBounds[2] <= safe[2]);
 }
});
test('no Line or Metric controls are evaluated before DETAIL LOCK even when given unusable context', () => {
 const p = compile();
 for (let frame = 0; frame < p.detailLockFrame; frame++) {
  const state = evaluateCameraDetailApproachFrame(p, frame, {eventContext: {invalid: true}});
  assert.equal(state.eventEnabled, false); assert.equal(state.eventFrame, null); assert.equal(state.controls, null);
  assert.equal(state.lineAllowed, false); assert.equal(state.metricAllowed, false); assert.equal(state.cameraLocked, false);
 }
 assert.equal(assessCameraDetailMotion(p).noEventBeforeLock, true);
});
test('DETAIL LOCK delegates old Event readiness and arc-length control timing without modifying its meaning', () => {
 const p = compile(), c = context(p);
 const lock = evaluateCameraDetailApproachFrame(p, 60, {eventContext: c});
 assert.equal(lock.state, 'DETAIL_LOCK'); assert.equal(lock.controls.state, 'EVENT_READY'); assert.equal(lock.controls.lineActive, false);
 assert.equal(lock.surveyAdmission, 'NOT_ADMITTED'); assert.equal(c.cameraState.admission.status, 'LOCAL_NOT_ADMITTED');
 const line = evaluateCameraDetailApproachFrame(p, 61, {eventContext: c});
 assert.equal(line.controls.lineFraction, 0); assert.equal(line.controls.metricFraction, 0);
 assert.equal(evaluateCameraDetailApproachFrame(p, 119, {eventContext: c}).controls.lineFraction, 1);
 assert.equal(evaluateCameraDetailApproachFrame(p, 135, {eventContext: c}).controls.metricFraction, 0);
 const hold = evaluateCameraDetailApproachFrame(p, 209, {eventContext: c});
 assert.equal(hold.controls.metricFraction, 1); assert.equal(hold.controls.metricValue, '120.5'); assert.equal(hold.controls.metricUnit, 'km');
});
test('caller must provide fresh target projection bindings and preserve existing readiness checks', () => {
 const p = compile(), c = context(p); c.cameraState.camera.flatBounds = start;
 assert.throws(() => evaluateCameraDetailApproachFrame(p, 61, {eventContext: c}), /LOCKED_EVENT_CONTEXT_BINDING/);
 const moving = context(p); moving.cameraState.cameraLocked = false;
 assert.throws(() => evaluateCameraDetailApproachFrame(p, 61, {eventContext: moving}), /GEOGRAPHIC_ARRIVAL/);
 const forbiddenLocal = context(p); forbiddenLocal.cameraState.scale = 'LOCAL'; forbiddenLocal.cameraState.admission.effectiveScale = 'LOCAL';
 assert.throws(() => evaluateCameraDetailApproachFrame(p, 61, {eventContext: forbiddenLocal}), /LOCAL_NOT_ADMITTED/);
});
test('USE_CURRENT_VIEW omits movement and redundant settle rather than replaying another Camera sequence', () => {
 const given = input(); given.framingRequest = request(geometry(), start, 'USE_CURRENT_VIEW');
 const p = compileCameraDetailApproach(given);
 assert.equal(p.detailLockFrame, 6); assert.equal(p.totalFrames, 156); assert.equal(p.timing.approachFrames, 0); assert.equal(p.timing.settleFrames, 0);
 assert(!p.timeline.some(b => ['DETAIL_APPROACH', 'DETAIL_SETTLE'].includes(b.state)));
 for (let f = 0; f < p.totalFrames; f++) assert.deepEqual(evaluateCameraDetailApproachFrame(p, f).flatBounds, start);
 given.framingRequest.targetFraming.bounds = target; given.framingRequest.certificate.bounds = target;
 assert.throws(() => compileCameraDetailApproach(given), /CURRENT_VIEW_MUST_NOT_MOVE/);
});
test('off-center long narrow geographic objects stay fully visible and source vertices are never added', () => {
 const g = {type: 'LineString', coordinates: [[.05, -1.7], [.11, -.1], [.09, 1.6]]}, given = input();
 given.eventGeometry = g; given.eventPlan = event(g); given.framingRequest = request(g);
 const p = compileCameraDetailApproach(given);
 assert.equal(assessCameraDetailMotion(p).wholeGeometryAndHaloSafeEveryFrame, true);
 assert.equal(p.eventGeometry.coordinates.length, 3); assert.deepEqual(p.eventGeometry.coordinates, g.coordinates);
});
test('geometry crop and halo-only crop are blocked despite a claimed admission certificate', () => {
 const given = input(); given.framingRequest = request(geometry(), [-.1, -.15, .1, .15]);
 assert.throws(() => compileCameraDetailApproach(given), /MOTION_GEOMETRY_OR_HALO_CROP/);
 const g = {type: 'LineString', coordinates: [[-1.7, 0], [1.7, 0]]}, other = input();
 other.eventGeometry = g; other.eventPlan = event(g); other.framingRequest = request(g); other.linePaddingPixels = 90;
 assert.throws(() => compileCameraDetailApproach(other), /MOTION_GEOMETRY_OR_HALO_CROP/);
});
test('input copying, deep freezing and shuffled frame evaluation preserve Camera, geometry and Metric', () => {
 const given = input(), before = JSON.stringify(given), p = compileCameraDetailApproach(given);
 assert.equal(JSON.stringify(given), before); given.currentCamera.flatBounds[0] = 99;
 given.eventGeometry.coordinates[0][0] = 50; given.framingRequest.certificate.bounds[0] = 50;
 assert.deepEqual(p.startBounds, start); assert.deepEqual(p.eventGeometry, geometry());
 assert(Object.isFrozen(p.eventGeometry.coordinates[0])); assert(Object.isFrozen(p.request.certificate));
 const expected = evaluateCameraDetailApproachFrame(p, 100, {eventContext: context(p)});
 for (const f of [209, 0, 135, 6, 47]) evaluateCameraDetailApproachFrame(p, f);
 assert.deepEqual(evaluateCameraDetailApproachFrame(p, 100, {eventContext: context(p)}), expected);
});
test('serialized adapter plans are canonical and reject forged lock or Camera bounds', () => {
 const p = JSON.parse(JSON.stringify(compile())); assert.deepEqual(assertCameraDetailApproachPlan(p), compile());
 p.detailLockFrame--; assert.throws(() => assertCameraDetailApproachPlan(p), /NON_CANONICAL/);
 const q = JSON.parse(JSON.stringify(compile())); q.targetBounds[0] += .1;
 assert.throws(() => assertCameraDetailApproachPlan(q), /NON_CANONICAL/);
});
test('invalid frame, duration, safe area and changed projection aspect fail explicitly', () => {
 const p = compile();
 for (const f of [-1, 1.2, Infinity, 210]) assert.throws(() => evaluateCameraDetailApproachFrame(p, f), /DETAIL_FRAME/);
 const given = input(); given.timing = {approachFrames: 1}; assert.throws(() => compileCameraDetailApproach(given), /APPROACH_FRAMES/);
 given.timing = {}; given.safeArea = [-1, 0, 1080, 1920]; assert.throws(() => compileCameraDetailApproach(given), /SAFE_AREA_HALO/);
 const aspect = input(); aspect.framingRequest = request(geometry(), [-3, -3, 3, 3]);
 assert.throws(() => compileCameraDetailApproach(aspect), /ASPECT_MUST_REMAIN_UNCHANGED/);
});
test('unbound requests, altered coordinates and false production claims cannot grant Camera authority', () => {
 for (const mutate of [r => { r.certificate.eventGeometryBinding = '{}'; }, r => { r.certificate.bounds[0] += .1; },
  r => { r.certificate.output[0] = 720; }, r => { r.certificate.safeArea[0]++; }, r => { r.certificate.status = 'NOT_ADMITTED'; },
  r => { r.currentCameraState.flatBounds[0]++; }]) {
  const given = input(); mutate(given.framingRequest);
  assert.throws(() => compileCameraDetailApproach(given), /BINDING_REQUIRED/);
 }
 const given = input(); given.eventGeometry.coordinates[0][0] += .01;
 assert.throws(() => compileCameraDetailApproach(given), /UNCHANGED_EVENT_GEOMETRY/);
 const production = input(); production.mode = 'PRODUCTION';
 assert.throws(() => compileCameraDetailApproach(production), /PRODUCTION_VISUAL_EVIDENCE/);
});
test('reverse Event direction is retained without regenerating or reversing native geometry', () => {
 const given = input(); given.eventPlan = event(geometry(), 'REVERSE'); const p = compileCameraDetailApproach(given);
 assert.equal(p.eventPlan.intent.line.direction, 'REVERSE'); assert.deepEqual(p.eventGeometry, geometry());
 assert.equal(evaluateCameraDetailApproachFrame(p, 119, {eventContext: context(p)}).controls.lineFraction, 1);
});
test('extension source has no country, fixture or numeric Metric specialization', () => {
 const body = readFileSync(new URL('../web/map_infographic_v1/camera_detail_approach_adapter_v1.mjs', import.meta.url), 'utf8');
 assert(!/suez|egypt|193\.30|32\.3/i.test(body));
 assert.equal(assessCameraDetailMotion(compile()).v5SourceModificationRequired, false);
});
test('Visual Admission producer and Camera adapter share canonical geometry and current bounds contracts', () => {
 const given = input(), g = given.eventGeometry;
 const candidates = generateDetailExtentCandidates({eventGeometry: g, eventAnchor: [0, 0], currentBounds: start,
  output: out, safeArea: safe, desiredScreenCoverageRange: [.2, .35, .5]}), evidenceByCandidate = {};
 for (const candidate of candidates) {
  const b = candidate.projectedGeometryBounds, mid = (b[1] + b[3]) / 2;
  evidenceByCandidate[candidate.id] = {evidenceKind: 'SYNTHETIC_TEST_ONLY',
   render: {verified: true, sha256: 'a'.repeat(64), byteLength: 1234, width: 1080, height: 1920,
    candidateBounds: candidate.bounds, geometryBinding: candidate.geometryBinding},
   visual: {terrain: 'VISUAL_PASS', coastline: 'VISUAL_WARNING', canal: 'VISUAL_PASS', marker: 'VISUAL_PASS',
    labels: 'VISUAL_PASS', safeArea: 'VISUAL_PASS', metric: 'VISUAL_PASS', lineReadable: true, metricRelated: true},
   semantic: {sameGeography: true, sameObject: true, relationCorrect: true, geometryMeaningPreserved: true, metricMateriallyTrue: true},
   protection: {cameraV5: true, eventV2: true, rendererVisual: true, geometry: true, marker: true},
   layout: {verified: true, candidateBounds: candidate.bounds, geometryBinding: candidate.geometryBinding,
    metricBounds: [b[2] + 20, mid + 30, b[2] + 220, mid + 90],
    protectedGraphics: [{kind: 'TEXT', bounds: [100, 140, 300, 180]}, {kind: 'MARKER', bounds: [520, 940, 560, 980]}]},
   quality: {gisAbsoluteAccuracyCertified: false, coastAlignmentMeasured: false}};
 }
 given.framingRequest = createEventDetailFramingRequest({eventGeometry: g, eventAnchor: [0, 0], safeArea: safe,
  currentCameraState: {bounds: start, output: out}, evidenceByCandidate, surveyDetailStatus: 'LOCAL_NOT_ADMITTED'});
 const p = compileCameraDetailApproach(given);
 assert.equal(p.request.decision, 'DETAIL_APPROACH_REQUIRED'); assert.equal(p.request.certificate.productionEligible, false);
 assert.equal(p.eventGeometryBinding, p.request.certificate.eventGeometryBinding);
 assert.equal(assessCameraDetailMotion(p).wholeGeometryAndHaloSafeEveryFrame, true);
 assert.equal(evaluateCameraDetailApproachFrame(p, 60).surveyAdmission, 'LOCAL_NOT_ADMITTED');
});
