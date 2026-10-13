import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileFlowIntent, assertFlowIntent, compileFlowPlan, assertFlowPlan,
 compileFlowRoute, sampleFlowRoute, evaluateFlowFrame} from '../web/map_infographic_v1/flow_core_v2.mjs';
import {evaluateGeographicLineReveal} from '../web/map_infographic_v1/event_line_v1.mjs';
import {evaluateEventFrame} from '../web/map_infographic_v1/event_timeline_v1.mjs';
import {classifyEventLineProtection} from '../web/map_infographic_v1/event_occlusion_policy_v1.mjs';

const source = () => ({source_type: 'SYNTHETIC_TEST', source_reference: 'fixture://flow-core-v2',
 verification_status: 'SYNTHETIC_TEST'});
const graphic = () => ({width_px: 52, height_px: 24, polygons: [{
 points: [[-.5, -.4], [.3, -.4], [.5, 0], [.3, .4], [-.5, .4]], color: [1, 1, 1, 1]}]});
const input = (coordinates = [[-2, 1], [-1, 1], [-.5, 1.5]], direction = 'FORWARD') => ({
 data_mode: 'SYNTHETIC_TEST', route_geometry: {type: 'LineString', coordinates}, route_source: source(), direction,
 start_anchor: [...(direction === 'FORWARD' ? coordinates[0] : coordinates.at(-1))],
 end_anchor: [...(direction === 'FORWARD' ? coordinates.at(-1) : coordinates[0])],
 object_role: 'generic_transport', object_graphic: graphic()});
const context = () => ({cameraState: {scale: 'REGIONAL', projection: 'FLAT_GEOGRAPHIC', cameraLocked: true,
 settle: {locked: true}, camera: {flatBounds: [-5, -2, 5, 5]},
 admission: {status: 'LOCAL_NOT_ADMITTED', effectiveScale: 'REGIONAL', localUsed: false}},
 project: point => [(point[0] + 5) * 80, (5 - point[1]) * 100], safeArea: [0, 0, 1000, 1000], protectedBoxes: []});
const compile = (given = input(), options = {}) => {
 const intent = compileFlowIntent(given), plan = compileFlowPlan(intent, options), eventContext = context();
 const primitive = compileFlowRoute(intent, {project: eventContext.project});
 return {intent, plan, primitive, eventContext};
};
const frame = (fixture, value) => evaluateFlowFrame(fixture.plan, value, fixture);
const close = (a, b, epsilon = 1e-9) => assert(Math.abs(a - b) <= epsilon, `${a} != ${b}`);
const magnitude = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

test('Flow intent preserves every authored vertex, anchor, source and role without mutating input', () => {
 const given = input(), before = structuredClone(given), intent = compileFlowIntent(given);
 assert.deepEqual(given, before); assert.deepEqual(intent.route_geometry, before.route_geometry);
 assert.deepEqual(intent.start_anchor, before.start_anchor); assert.deepEqual(intent.end_anchor, before.end_anchor);
 given.route_geometry.coordinates[0][0] = 40; given.object_graphic.polygons[0].points[0][0] = 0;
 assert.deepEqual(intent.route_geometry, before.route_geometry); assert.deepEqual(intent.object_graphic, before.object_graphic);
 assert(Object.isFrozen(intent.object_graphic.polygons[0].points[0]));
 assert.throws(() => {intent.start_anchor[0] = 0;}, TypeError);
});
test('Production provenance remains the verified V1 contract, never inferred from object role', () => {
 const given = input(); given.data_mode = 'PRODUCTION';
 assert.throws(() => compileFlowIntent(given), /VERIFIED_PRODUCTION_SOURCE_REQUIRED/);
 given.route_source = {source_type: 'PUBLIC_GEOGRAPHIC_DATA', source_reference: 'fixture://verified', verification_status: 'VERIFIED'};
 const fixture = compile(given); assert.equal(frame(fixture, 30).productionEligible, true);
 for (const role of ['aircraft', 'ship', 'custom_fixture_object']) {
  const intent = compileFlowIntent({...given, object_role: role});
  assert.equal(intent.object_role, role); assert.deepEqual(intent.object_graphic, graphic());
 }
});
test('Directed anchors must match input route endpoints exactly; a new anchor cannot invent a route', () => {
 const given = input(); given.start_anchor = [-1.9999, 1];
 assert.throws(() => compileFlowIntent(given), /ANCHORS_MUST_MATCH_DIRECTED_ROUTE_ENDPOINTS/);
 const reverse = input(undefined, 'REVERSE'); reverse.start_anchor = [...reverse.route_geometry.coordinates[0]];
 assert.throws(() => compileFlowIntent(reverse), /ANCHORS_MUST_MATCH_DIRECTED_ROUTE_ENDPOINTS/);
});
test('Fixture graphics require visible polygons, finite dimensions and bounded authored vertices', () => {
 for (const change of [g => {g.width_px = 0;}, g => {g.height_px = Infinity;}, g => {g.polygons = [];},
  g => {g.polygons[0].points = [[0, 0], [.1, .1], [.2, .2]];},
  g => {g.polygons[0].points[0][0] = .51;}, g => {g.polygons[0].color = [1, 1, 1, 0];}]) {
  const given = input(); change(given.object_graphic); assert.throws(() => compileFlowIntent(given), /FLOW_OBJECT_/);
 }
});
test('Default flow is 180 contiguous frames with reveal/direction overlapping deterministic travel', () => {
 const {plan} = compile(); assert.equal(plan.totalFrames, 180); assert.equal(plan.durationSeconds, 6);
 assert.deepEqual(plan.timeline.map(beat => [beat.state, beat.startFrame, beat.endFrame]), [
  ['FLOW_READY', 0, 1], ['ROUTE_REVEAL', 1, 12], ['DIRECTIONAL_FLOW', 12, 20],
  ['MOVING_OBJECT', 20, 128], ['ENDPOINT_PULSE', 128, 146], ['ROUTE_HOLD', 146, 180]]);
 assert.equal(plan.routeEventPlan.totalFrames, 180); assert.equal(plan.routeEventPlan.intent.metric, null);
 assert.equal(plan.ownership.camera, 'READ_ONLY'); assert.equal(plan.ownership.physics, 'NONE');
});
test('Synthetic A: short route fully reveals, travels, pulses once and holds the completed endpoint', () => {
 const fixture = compile(); let departureRuns = 0, arrivalRuns = 0, departurePrevious = false, arrivalPrevious = false;
 let previousFraction = -1;
 for (let index = 0; index < fixture.plan.totalFrames; index++) {
  const result = frame(fixture, index);
  assert(result.objectFraction >= previousFraction); assert(result.objectFraction <= result.routeFraction + 1e-12);
  previousFraction = result.objectFraction;
  if (result.departurePulse.active && !departurePrevious) departureRuns++;
  if (result.arrivalPulse.active && !arrivalPrevious) arrivalRuns++;
  departurePrevious = result.departurePulse.active; arrivalPrevious = result.arrivalPulse.active;
  if (result.hold) {assert.equal(result.objectFraction, 1); assert.equal(result.routeFraction, 1);
   assert.equal(result.pulse.alpha, 0); assert.equal(result.directionalActive, false);}
 }
 assert.equal(departureRuns, 1); assert.equal(arrivalRuns, 1);
 assert.equal(frame(fixture, 19).objectVisible, false); assert.equal(frame(fixture, 20).objectVisible, true);
 assert.deepEqual(frame(fixture, 127).objectPosition, fixture.primitive.screenCoordinates.at(-1));
 assert.deepEqual(frame(fixture, 179).objectPosition, fixture.primitive.screenCoordinates.at(-1));
});
test('Route controls are the original V1 evaluator at every frame, with no second reveal engine', () => {
 const fixture = compile();
 for (let index = 0; index < fixture.plan.totalFrames; index++) {
  const result = frame(fixture, index), original = evaluateEventFrame(fixture.plan.routeEventPlan, index, fixture.eventContext);
  assert.equal(result.routeFraction, original.lineFraction);
  assert.deepEqual(result.routeReveal, evaluateGeographicLineReveal(fixture.primitive, original.lineFraction));
 }
});
test('Synthetic B: nonuniform curved route motion uses true screen arc length and smooth endpoint speeds', () => {
 const fixture = compile(input([[-4, 2], [-3.8, 2.05], [-3, 1.9], [-1.6, 1.4], [-.2, 1.1], [1, .8], [3, .6]]));
 const travel = [];
 for (let index = 20; index <= 127; index++) {
  const result = frame(fixture, index), sample = sampleFlowRoute(fixture.primitive, result.objectFraction);
  assert.deepEqual(result.objectPosition, sample.position); close(sample.distancePixels,
   result.objectFraction * fixture.primitive.totalLengthPixels);
  const exact = result.objectFraction === 0 ? fixture.primitive.screenCoordinates[0]
   : evaluateGeographicLineReveal(fixture.primitive, result.objectFraction).path.at(-1);
  assert.deepEqual(result.objectPosition, exact); travel.push(result);
 }
 const distances = travel.slice(1).map((value, index) => magnitude(value.objectPosition, travel[index].objectPosition));
 assert(distances[0] < distances[30] * .01); assert(distances.at(-1) < distances[70] * .01);
 const velocity = travel.slice(1).map((value, index) => value.objectFraction - travel[index].objectFraction);
 const maxAccelerationChange = Math.max(...velocity.slice(1).map((value, index) => Math.abs(value - velocity[index])));
 assert(maxAccelerationChange < .0006); assert(Math.max(...distances) < fixture.primitive.totalLengthPixels * .018);
 const headingChange = travel.slice(1).map((value, index) => Math.abs(value.heading - travel[index].heading));
 assert(Math.max(...headingChange) < .16);
});
test('Finite secant heading crosses atan2 wrap continuously and works without earlier frame state', () => {
 const given = input([[4, 0], [2, 1], [0, 0], [-2, -1], [-4, 0]]);
 const intent = compileFlowIntent(given), primitive = compileFlowRoute(intent, {project: point => [point[0] * 50, point[1] * 50]});
 const samples = Array.from({length: 501}, (_, index) => sampleFlowRoute(primitive, index / 500));
 assert(Math.max(...samples.slice(1).map((sample, index) => Math.abs(sample.heading - samples[index].heading))) < .06);
 assert(samples.some(sample => sample.heading > Math.PI));
 for (const index of [450, 1, 250, 499, 0, 50]) assert.deepEqual(sampleFlowRoute(primitive, index / 500), samples[index]);
});
test('Actual Synthetic B detail framing keeps heading smooth using authored object size while arc positions stay exact', () => {
 const supplied = JSON.parse(readFileSync(new URL('../recovery/event-feature-bundle-v2/fixtures/synthetic-b.json', import.meta.url)));
 const bounds = [-28.1951219512, -16.4713414634, 21.1951219512, 20.5713414634];
 const [width, height] = supplied.context.output;
 const project = point => [(point[0] - bounds[0]) / (bounds[2] - bounds[0]) * width,
  (bounds[3] - point[1]) / (bounds[3] - bounds[1]) * height];
 const intent = compileFlowIntent(supplied.intent), plan = compileFlowPlan(intent, supplied.timeline);
 const eventContext = {...supplied.context, project,
  cameraState: {...supplied.context.cameraState, camera: {flatBounds: bounds}}};
 const primitive = compileFlowRoute(intent, {project});
 const fixture = {plan, primitive, eventContext}, travel = [];
 for (let index = plan.timing.object_start_frame; index < plan.arrivalFrame; index++) {
  const value = frame(fixture, index), expected = value.objectFraction === 0 ? primitive.screenCoordinates[0]
   : evaluateGeographicLineReveal(primitive, value.objectFraction).path.at(-1);
  assert.deepEqual(value.objectPosition, expected);
  assert.equal(value.headingLookAheadPixels, Math.max(intent.object_graphic.width_px, intent.object_graphic.height_px) * .5);
  travel.push(value);
 }
 const wrappedChange = travel.slice(1).map((value, index) =>
  Math.abs(Math.atan2(Math.sin(value.heading - travel[index].heading), Math.cos(value.heading - travel[index].heading))));
 assert(Math.max(...wrappedChange) <= .25, `Largest actual heading step ${Math.max(...wrappedChange)} exceeds .25rad`);
 assert.deepEqual(primitive.intent.line.geometry, supplied.intent.route_geometry);
 assert.equal(travel[0].objectFraction, 0); assert.equal(travel.at(-1).objectFraction, 1);
});
test('REVERSE is applied once and preserves original coordinates while all motion starts at directed anchor', () => {
 const fixture = compile(input(undefined, 'REVERSE'));
 assert.deepEqual(fixture.primitive.screenCoordinates,
  [...fixture.intent.route_geometry.coordinates].reverse().map(fixture.eventContext.project));
 assert.deepEqual(frame(fixture, 20).objectPosition, fixture.eventContext.project(fixture.intent.start_anchor));
 assert.deepEqual(frame(fixture, 127).objectPosition, fixture.eventContext.project(fixture.intent.end_anchor));
 assert.deepEqual(frame(fixture, 32).routeReveal.path, fixture.primitive.screenCoordinates);
});
test('Zero-length duplicate segments remain authored and cannot introduce NaN samples or headings', () => {
 const fixture = compile(input([[-2, 1], [-2, 1], [-1, 1], [-1, 1], [-.5, 1.5], [-.5, 1.5]]));
 assert.deepEqual(fixture.primitive.segmentLengthsPixels.filter(value => value === 0), [0, 0, 0]);
 for (const value of [0, .001, .1, .5, .99, 1]) {
  const sample = sampleFlowRoute(fixture.primitive, value);
  assert(sample.position.every(Number.isFinite)); assert(Number.isFinite(sample.heading));
 }
 assert.equal(frame(fixture, 179).routeReveal.path.length, 6);
});
test('Directional traveler stays on the visible route, and pulse alpha is a bounded one-shot envelope', () => {
 const fixture = compile();
 for (let index = 0; index < fixture.plan.totalFrames; index++) {
  const result = frame(fixture, index);
  assert(result.directionalFraction <= result.routeFraction); assert(result.directionalFraction >= result.objectFraction - 1e-12);
  for (const pulse of [result.departurePulse, result.arrivalPulse]) {
   assert(pulse.amplitude >= 0 && pulse.amplitude <= 1); assert.equal(pulse.alpha, pulse.amplitude);
   if (!pulse.active || pulse.progress === 0 || pulse.progress === 1) assert.equal(pulse.alpha, 0);
  }
 }
 assert.equal(frame(fixture, 11).directionalActive, false); assert.equal(frame(fixture, 12).directionalActive, true);
 assert.equal(frame(fixture, 128).directionalActive, false);
});
test('Synthetic C: native Marker occlusion remains the sole line exception and nearby text is strict', () => {
 const fixture = compile();
 const protectedGraphics = [{kind: 'MARKER', box: [230, 380, 250, 420]},
  {kind: 'TEXT', box: [300, 450, 370, 490]}, {kind: 'PANEL', box: [10, 10, 150, 80]}];
 const before = structuredClone(protectedGraphics), protection = classifyEventLineProtection({protectedGraphics});
 assert.deepEqual(protection.markerOcclusions, [[230, 380, 250, 420]]);
 assert.deepEqual(protection.strictBoxes, [[300, 450, 370, 490], [10, 10, 150, 80]]);
 for (let index = 0; index < fixture.plan.totalFrames; index++) {
  const result = frame(fixture, index); assert(result.objectFraction <= result.routeFraction + 1e-12);
 }
 assert.deepEqual(protectedGraphics, before);
 const textCrossing = classifyEventLineProtection({protectedGraphics: [{kind: 'TEXT', box: [230, 380, 250, 420]}]});
 assert.deepEqual(textCrossing.markerOcclusions, []); assert.deepEqual(textCrossing.strictBoxes, [[230, 380, 250, 420]]);
});
test('Camera lock, scale admission and route Safe Area are checked even during final holds', () => {
 const fixture = compile();
 for (const value of [0, 20, 179]) {
  const unlocked = {...fixture.eventContext, cameraState: {...fixture.eventContext.cameraState, cameraLocked: false}};
  assert.throws(() => evaluateFlowFrame(fixture.plan, value, {...fixture, eventContext: unlocked}), /GEOGRAPHIC_ARRIVAL_REQUIRED/);
  assert.throws(() => evaluateFlowFrame(fixture.plan, value,
   {...fixture, eventContext: {...fixture.eventContext, safeArea: [300, 0, 1000, 1000]}}), /GEOMETRY_OUTSIDE_SAFE_AREA/);
 }
 const local = structuredClone(fixture.eventContext.cameraState); local.scale = 'LOCAL'; local.admission.effectiveScale = 'LOCAL';
 assert.throws(() => evaluateFlowFrame(fixture.plan, 40, {...fixture,
  eventContext: {...fixture.eventContext, cameraState: local}}), /LOCAL_NOT_ADMITTED/);
});
test('Source intent and the current projection bind every supplied primitive before object evaluation', () => {
 const fixture = compile();
 const unrelated = compileFlowRoute(compileFlowIntent(input([[-3, 1], [-1, 1], [-.5, 1.5]])), {project: fixture.eventContext.project});
 assert.throws(() => evaluateFlowFrame(fixture.plan, 30, {...fixture, primitive: unrelated}), /CURRENT_INTENT_AND_PROJECTION/);
 const differentProjection = compileFlowRoute(fixture.intent, {project: point => [point[0] * 50, point[1] * 50]});
 assert.throws(() => evaluateFlowFrame(fixture.plan, 30, {...fixture, primitive: differentProjection}), /CURRENT_INTENT_AND_PROJECTION/);
});
test('Saved intents/plans are canonical; random-access and offset frame evaluation have no mutable state', () => {
 const fixture = compile(input(), {start_frame: 60}), before = JSON.stringify(fixture.plan);
 assert.deepEqual(assertFlowIntent(JSON.parse(JSON.stringify(fixture.intent))), fixture.intent);
 assert.deepEqual(assertFlowPlan(JSON.parse(JSON.stringify(fixture.plan))), fixture.plan);
 const expected = frame(fixture, 150); for (const value of [239, 60, 80, 170, 100]) frame(fixture, value);
 assert.deepEqual(frame(fixture, 150), expected); assert.equal(JSON.stringify(fixture.plan), before);
 assert.equal(frame(fixture, 60).localFrame, 0); assert.equal(frame(fixture, 239).hold, true);
 const saved = JSON.parse(before); saved.timeline[1].endFrame++;
 assert.throws(() => assertFlowPlan(saved), /NON_CANONICAL/);
 for (const value of [-1, 59, 240, 60.5, NaN]) assert.throws(() => frame(fixture, value), /FLOW_FRAME/);
});
test('Invalid schedules fail before rendering instead of permitting an object to overtake the route', () => {
 const intent = compileFlowIntent(input());
 for (const options of [{fps: 0}, {start_frame: -1}, {travel_frames: 1}, {arrival_pulse_frames: 1},
  {reveal_frames: 120, object_start_frame: 12, travel_frames: 25}, {direction_start_frame: 25},
  {departure_pulse_frames: 120}, {unknown: 10}]) assert.throws(() => compileFlowPlan(intent, options), /FLOW_/);
 for (const value of [-.01, 1.01, NaN]) assert.throws(() => sampleFlowRoute(compile().primitive, value), /FRACTION_RANGE/);
 assert.throws(() => sampleFlowRoute(compile().primitive, .5, {lookAheadPixels: 0}), /LOOKAHEAD/);
});
