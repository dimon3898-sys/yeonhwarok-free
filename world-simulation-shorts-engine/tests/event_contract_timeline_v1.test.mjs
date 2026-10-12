import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileEventIntent, assertEventIntent} from '../web/map_infographic_v1/event_contract_v1.mjs';
import {compileEventPlan, assertEventPlan, evaluateEventFrame, evaluateEventReadiness} from '../web/map_infographic_v1/event_timeline_v1.mjs';
import {evaluateMinimumContextCameraFrame} from '../web/map_infographic_v1/camera_director_v5.mjs';

const syntheticSource = () => ({source_type: 'SYNTHETIC_TEST', source_reference: 'fixture://contract-timeline', verification_status: 'SYNTHETIC_TEST'});
const verifiedSource = () => ({source_type: 'DOCUMENTED_MEASUREMENT', source_reference: 'fixture://verified-sample', verification_status: 'VERIFIED'});
const input = () => ({data_mode: 'SYNTHETIC_TEST', line: {geometry: {type: 'LineString', coordinates: [[-4, 2], [-3, 3], [-1, 3]]},
 source: syntheticSource(), direction: 'FORWARD', style_role: 'EVENT_HIGHLIGHT', anchor: [-3, 3]},
 metric: {display_value: '120.5', unit: 'km', source: syntheticSource(), anchor: [-3, 3]}});
const profile = () => ({ready_frames: 2, line_reveal_frames: 7, line_hold_frames: 3, metric_reveal_frames: 6, information_hold_frames: 9});
const plan = () => compileEventPlan(compileEventIntent(input()), {fps: 30, profile: profile(), seed: 11});
const context = () => ({cameraState: {scale: 'REGIONAL', projection: 'FLAT_GEOGRAPHIC', cameraLocked: true,
 settle: {locked: true}, camera: {flatBounds: [-5, 0, 0, 5]},
 admission: {status: 'LOCAL_NOT_ADMITTED', effectiveScale: 'REGIONAL', localUsed: false}},
 project: p => [(p[0] + 5) * 100, (5 - p[1]) * 100], safeArea: [0, 0, 500, 500], protectedBoxes: [[0, 0, 20, 20]]});

test('contract copies and freezes every supplied geometry, metric and provenance level', () => {
 const given = input(), before = structuredClone(given), intent = compileEventIntent(given);
 assert.deepEqual(given, before);
 given.line.geometry.coordinates[0][0] = 100; given.metric.display_value = '999';
 assert.deepEqual(intent.line.geometry.coordinates[0], [-4, 2]); assert.equal(intent.metric.display_value, '120.5');
 assert(Object.isFrozen(intent.line.geometry.coordinates[0])); assert(Object.isFrozen(intent.metric.source));
 assert.throws(() => { intent.line.geometry.coordinates[0][0] = 0; }, TypeError);
});
test('production default requires both verified sources and preserves the fixed value/unit', () => {
 const given = input(); delete given.data_mode;
 given.line.source = verifiedSource(); given.metric.source = verifiedSource();
 const intent = compileEventIntent(given);
 assert.equal(intent.data_mode, 'PRODUCTION'); assert.equal(intent.metric.display_value, '120.5'); assert.equal(intent.metric.unit, 'km');
 given.metric.source.verification_status = 'UNVERIFIED';
 assert.throws(() => compileEventIntent(given), /METRIC_VERIFIED_PRODUCTION_SOURCE_REQUIRED/);
});
test('missing geometry or metric provenance blocks rather than inferring from its display text', () => {
 const given = input(); delete given.line.source; assert.throws(() => compileEventIntent(given), /LINE_SOURCE_OBJECT_REQUIRED/);
 const metricOnly = {data_mode: 'SYNTHETIC_TEST', metric: input().metric}; delete metricOnly.metric.source;
 assert.throws(() => compileEventIntent(metricOnly), /METRIC_SOURCE_OBJECT_REQUIRED/);
});
test('reference display values and synthetic records cannot masquerade as production evidence', () => {
 for (const type of ['REFERENCE_DISPLAY_VALUE', 'SYNTHETIC_TEST']) {
  const given = input(); given.data_mode = 'PRODUCTION'; given.line.source = verifiedSource();
  given.metric.source = {...verifiedSource(), source_type: type};
  assert.throws(() => compileEventIntent(given), /METRIC_VERIFIED_PRODUCTION_SOURCE_REQUIRED/);
 }
});
test('synthetic data requires explicit provenance and stays tagged not production', () => {
 const given = input(); given.metric.source.verification_status = 'VERIFIED';
 assert.throws(() => compileEventIntent(given), /EXPLICIT_SYNTHETIC_PROVENANCE_REQUIRED/);
 const intent = compileEventIntent(input());
 assert.equal(intent.provenance_class, 'SYNTHETIC_TEST_NOT_PRODUCTION');
 assert.equal(evaluateEventFrame(compileEventPlan(intent, {fps: 30, profile: profile()}), 10, context()).productionEligible, false);
});
test('line source coordinates and duplicate vertices remain unchanged, with explicit direction', () => {
 const given = input(); given.line.geometry.coordinates.splice(1, 0, [-4, 2]); given.line.direction = 'REVERSE';
 const intent = compileEventIntent(given);
 assert.deepEqual(intent.line.geometry.coordinates, given.line.geometry.coordinates); assert.equal(intent.line.direction, 'REVERSE');
 given.line.direction = 'AUTO'; assert.throws(() => compileEventIntent(given), /DIRECTION_REQUIRED/);
});
test('invalid geometry, zero-length, wrapped crossings and invented missing anchors fail', () => {
 for (const coordinates of [[], [[0, 0]], [[0, 0], [0, 0]], [[0, 0], [181, 0]], [[0, 0], [1, NaN]], [[0, 0, 3], [1, 2]], [[170, 0], [-170, 1]]]) {
  const given = input(); given.line.geometry.coordinates = coordinates; assert.throws(() => compileEventIntent(given), /EVENT_/);
 }
 const given = input(); delete given.metric.anchor; assert.throws(() => compileEventIntent(given), /METRIC_ANCHOR/);
});
test('contract rejects absent primitives, unsupported mode and line-breaking/control characters', () => {
 assert.throws(() => compileEventIntent({}), /PRIMITIVE_REQUIRED/);
 assert.throws(() => compileEventIntent({...input(), data_mode: 'GUESS'}), /DATA_MODE/);
 const given = input(); given.metric.unit = 'm\nother'; assert.throws(() => compileEventIntent(given), /METRIC_UNIT/);
});
test('plan has contiguous half-open integer frame beats and explicit end frame', () => {
 const p = plan();
 assert.equal(p.totalFrames, 27); assert.equal(p.durationSeconds, .9);
 assert.deepEqual(p.timeline.map(b => [b.state, b.startFrame, b.endFrame]), [
  ['EVENT_READY', 0, 2], ['LINE_REVEAL', 2, 9], ['LINE_HOLD', 9, 12], ['METRIC_REVEAL', 12, 18], ['INFORMATION_HOLD', 18, 27]]);
 assert(Object.isFrozen(p.timeline[0]));
});
test('line and metric reveal each start exactly at zero and end exactly at one', () => {
 const p = plan(), c = context();
 assert.equal(evaluateEventFrame(p, 2, c).lineFraction, 0); assert.equal(evaluateEventFrame(p, 8, c).lineFraction, 1);
 assert.equal(evaluateEventFrame(p, 12, c).metricFraction, 0); assert.equal(evaluateEventFrame(p, 17, c).metricFraction, 1);
 assert.equal(evaluateEventFrame(p, 5, c).lineFraction, .5);
});
test('both holds preserve complete controls and unchanged metric value/unit', () => {
 const p = plan();
 for (let f = 0; f < p.totalFrames; f++) {
  const state = evaluateEventFrame(p, f, context());
  assert.equal(state.metricValue, '120.5'); assert.equal(state.metricUnit, 'km');
  if (f >= 9) assert.equal(state.lineFraction, 1);
  if (f >= 18) assert.equal(state.metricFraction, 1);
 }
});
test('random frame order is deterministic and does not mutate input camera/layout state', () => {
 const p = plan(), c = context(), before = JSON.stringify(c);
 const expected = evaluateEventFrame(p, 21, c); for (const f of [26, 0, 7, 19, 4]) evaluateEventFrame(p, f, c);
 assert.deepEqual(evaluateEventFrame(p, 21, c), expected); assert.equal(JSON.stringify(c), before);
});
test('omitted primitives omit only their own beats; zero optional line hold stays omitted', () => {
 for (const primitive of ['line', 'metric']) {
  const given = input(); given[primitive] = null;
  const p = compileEventPlan(compileEventIntent(given), {fps: 24, profile: profile()});
  assert(!p.timeline.some(b => b.state.startsWith(primitive.toUpperCase())));
 }
 const p = compileEventPlan(compileEventIntent(input()), {fps: 60, profile: {...profile(), line_hold_frames: 0}});
 assert(!p.timeline.some(b => b.state === 'LINE_HOLD'));
});
test('integer profile, fps, seed and frame validation reject guesses and out-of-range access', () => {
 const intent = compileEventIntent(input());
 assert.throws(() => compileEventPlan(intent, {fps: 30}), /PROFILE_REQUIRED/);
 for (const bad of [0, -1, 2.5, NaN]) assert.throws(() => compileEventPlan(intent, {fps: bad, profile: profile()}), /FPS/);
 for (const bad of [1.5, undefined, -1]) assert.throws(() => compileEventPlan(intent, {fps: 30, profile: {...profile(), ready_frames: bad}}), /INTEGER_REQUIRED/);
 assert.throws(() => compileEventPlan(intent, {fps: 30, profile: {...profile(), line_reveal_frames: 1}}), /INTEGER_REQUIRED/);
 assert.throws(() => compileEventPlan(intent, {fps: 30, profile: profile(), seed: '11'}), /SEED/);
 for (const f of [-1, .5, 27, Infinity]) assert.throws(() => evaluateEventFrame(plan(), f, context()), /EVENT_FRAME/);
});
test('serialized plans are validated by contents, not a claimed version stamp', () => {
 const p = JSON.parse(JSON.stringify(plan())); assert.deepEqual(assertEventPlan(p), plan());
 p.timeline[1].endFrame++; assert.throws(() => assertEventPlan(p), /NON_CANONICAL/);
 const i = JSON.parse(JSON.stringify(compileEventIntent(input()))); i.metric.source.verification_status = 'VERIFIED';
 assert.throws(() => assertEventIntent(i), /PROVENANCE_REQUIRED/);
});
test('safe geometry and geographic anchors are required on every frame, including holds', () => {
 const p = plan(), outside = {...context(), safeArea: [250, 0, 500, 500]};
 for (const f of [0, 8, 26]) assert.throws(() => evaluateEventFrame(p, f, outside), /GEOMETRY_OUTSIDE_SAFE_AREA/);
 const given = input(); given.metric.anchor = [-4.9, 4.9];
 const q = compileEventPlan(compileEventIntent(given), {fps: 30, profile: profile()});
 assert.throws(() => evaluateEventFrame(q, 0, {...context(), safeArea: [50, 50, 500, 500]}), /ANCHOR_OUTSIDE_SAFE_AREA/);
});
test('arrival, actual transform, projection and scale admission fail closed', () => {
 for (const camera of [
  {cameraLocked: false}, {settle: {locked: false}}, {projection: ''},
  {camera: {flatBounds: [0, 0, 0, 5]}}, {scale: 'IMAGINARY'},
  {admission: {status: 'UNKNOWN', effectiveScale: 'REGIONAL', localUsed: false}},
  {admission: {status: 'LOCAL_NOT_ADMITTED', effectiveScale: 'LOCAL', localUsed: false}},
 ]) {
  const c = context(); c.cameraState = {...c.cameraState, ...camera}; assert.throws(() => evaluateEventFrame(plan(), 0, c), /EVENT_/);
 }
 assert.throws(() => evaluateEventFrame(plan(), 0, {...context(), project: undefined}), /EXISTING_PROJECTION_REQUIRED/);
 assert.throws(() => evaluateEventFrame(plan(), 0, {...context(), project: () => [NaN, 0]}), /PROJECTION_POINT_REQUIRED/);
});
test('LOCAL_NOT_ADMITTED never becomes LOCAL event readiness; forged stamp lacks the complete legacy contract', () => {
 const c = context(); c.cameraState.scale = 'LOCAL';
 c.cameraState.admission.effectiveScale = 'LOCAL';
 assert.throws(() => evaluateEventFrame(plan(), 0, c), /EVENT_LOCAL_NOT_ADMITTED/);
 c.cameraState.admission = {status: 'LOCAL_ADMITTED', effectiveScale: 'LOCAL', localUsed: true};
 assert.throws(() => evaluateEventFrame(plan(), 0, {...c, scalePlan: {scale: {name: 'LOCAL'}}}), /LOCAL/);
});
test('LOCAL snapshot effective scale mismatch fails before the preserved complete admission validator', () => {
 const c = context(); c.cameraState.scale = 'LOCAL';
 c.cameraState.admission = {status: 'LOCAL_ADMITTED', effectiveScale: 'REGIONAL', localUsed: true};
 // Even an asserted admission cannot bind this contradictory snapshot. The
 // error proves rejection before any access to the supplied scale-plan object.
 const scalePlan = new Proxy({}, {get() {throw Error('LEGACY_VALIDATOR_SHOULD_NOT_BE_REACHED');}});
 assert.throws(() => evaluateEventFrame(plan(), 0, {...c, scalePlan}), {message: 'EVENT_CAMERA_SCALE_ADMISSION_MISMATCH'});
});
test('projection receives copies and cannot modify supplied geometry; protected boxes remain read-only', () => {
 const intent = compileEventIntent(input()), c = context();
 c.project = point => {const output = [(point[0] + 5) * 100, (5 - point[1]) * 100]; point[0] = 179; return output;};
 const result = evaluateEventReadiness(intent, c); assert.deepEqual(intent.line.geometry.coordinates[0], [-4, 2]);
 assert(Object.isFrozen(result.protectedBoxes[0])); assert.deepEqual(c.protectedBoxes, [[0, 0, 20, 20]]);
});
test('actual preserved V5 final snapshot satisfies the read-only Event arrival interface', () => {
 const cameraPlan = JSON.parse(readFileSync(new URL('../recovery/v5/inputs/camera-plan.json', import.meta.url), 'utf8'));
 const state = evaluateMinimumContextCameraFrame(cameraPlan, cameraPlan.checkpoints.FINAL_HOLD), [w, h] = cameraPlan.intent.display.canonicalOutput;
 const bounds = state.camera.flatBounds, anchor = state.geographicAnchor;
 const given = input(); given.line.geometry.coordinates = [anchor, [anchor[0] + .01, anchor[1] + .01]];
 given.line.anchor = [...anchor]; given.metric.anchor = [...anchor];
 const p = compileEventPlan(compileEventIntent(given), {fps: 30, profile: profile()});
 const c = {cameraState: state, safeArea: cameraPlan.intent.display.safeArea,
  project: point => [(point[0] - bounds[0]) / (bounds[2] - bounds[0]) * w, (bounds[3] - point[1]) / (bounds[3] - bounds[1]) * h]};
 const before = structuredClone(state), result = evaluateEventFrame(p, 0, c);
 assert.equal(result.readiness.status, 'EVENT_READY'); assert.equal(result.readiness.scale, 'REGIONAL'); assert.deepEqual(state, before);
});
