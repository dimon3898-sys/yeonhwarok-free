import test from 'node:test';
import assert from 'node:assert/strict';
import {compileFlowIntent, compileFlowPlan, compileFlowRoute, evaluateFlowFrame,
 sampleFlowRoute} from '../web/map_infographic_v1/flow_core_v2.mjs';
import {evaluateGeographicLineReveal} from '../web/map_infographic_v1/event_line_v1.mjs';
import {compileFlowVisualProfile, assertFlowVisualProfile, applyFlowVisualProfile,
 FLOW_OBJECT_SCALE_CANDIDATES} from '../web/map_infographic_v1/flow_visual_profile_v2.mjs';

function fixture(coordinates = [[-2, 1], [-1, 1], [-.5, 1.5]], direction = 'FORWARD', role = 'authored_transport') {
 const intent = compileFlowIntent({data_mode: 'SYNTHETIC_TEST',
  route_geometry: {type: 'LineString', coordinates},
  route_source: {source_type: 'SYNTHETIC_TEST', source_reference: 'fixture://flow-visual-profile-v2',
   verification_status: 'SYNTHETIC_TEST'}, direction,
  start_anchor: direction === 'FORWARD' ? coordinates[0] : coordinates.at(-1),
  end_anchor: direction === 'FORWARD' ? coordinates.at(-1) : coordinates[0], object_role: role,
  object_graphic: {width_px: 52, height_px: 30, polygons: [{
   points: [[-.5, -.4], [.25, -.4], [.5, 0], [.25, .4], [-.5, .4]], color: [1, 1, 1, 1]}]}});
 const eventContext = {cameraState: {scale: 'REGIONAL', projection: 'FLAT_GEOGRAPHIC', cameraLocked: true,
  settle: {locked: true}, camera: {flatBounds: [-5, -2, 5, 5]},
  admission: {status: 'LOCAL_NOT_ADMITTED', effectiveScale: 'REGIONAL', localUsed: false}},
  project: point => [(point[0] + 5) * 80, (5 - point[1]) * 100],
  safeArea: [0, 0, 1000, 1000], protectedBoxes: []};
 const plan = compileFlowPlan(intent), primitive = compileFlowRoute(intent, {project: eventContext.project});
 return {intent, plan, primitive, eventContext};
}
const render = (value, frame, profile = compileFlowVisualProfile()) => {
 const controls = evaluateFlowFrame(value.plan, frame, value);
 return {original: controls, ...applyFlowVisualProfile({flowPlan: value.plan, controls,
  primitive: value.primitive, profile})};
};

test('Selected object size is fixture/profile data and preserves authored silhouette for arbitrary roles', () => {
 assert.deepEqual(FLOW_OBJECT_SCALE_CANDIDATES, [1, 1.12, 1.20, 1.28]);
 for (const role of ['authored_transport', 'custom_object']) {
  const value = fixture(undefined, 'FORWARD', role), before = JSON.stringify(value.intent);
  for (const objectScale of FLOW_OBJECT_SCALE_CANDIDATES) {
   const profile = compileFlowVisualProfile({profileName: 'GENERIC_MOBILE', roleGroup: 'GENERIC', objectScale});
   const result = render(value, 75, profile);
   assert.deepEqual(result.metadata.beforeSize, [52, 30]);
   assert.deepEqual(result.metadata.afterSize, [52 * objectScale, 30 * objectScale]);
   assert.deepEqual(result.objectGraphic.polygons, value.intent.object_graphic.polygons);
   assert.deepEqual(assertFlowVisualProfile(JSON.parse(JSON.stringify(profile))), profile);
   assert(Object.isFrozen(result.objectGraphic.polygons[0].points[0]));
  }
  assert.equal(JSON.stringify(value.intent), before);
 }
});

test('Short, curved and reverse routes preserve every object motion field while reveal is monotonic', () => {
 const curves = [[-4, 2], [-3.8, 2.05], [-3, 1.9], [-1.6, 1.4], [-.2, 1.1], [1, .8], [3, .6]];
 for (const value of [fixture(), fixture(curves), fixture(curves, 'REVERSE')]) {
  const before = JSON.stringify({plan: value.plan, primitive: value.primitive});
  let previous = -1;
  for (let frame = 0; frame < value.plan.totalFrames; frame++) {
   const result = render(value, frame), original = result.original, controls = result.controls;
   for (const key of ['frame', 'localFrame', 'state', 'stateFrame', 'stateProgress', 'objectFraction',
    'objectPosition', 'heading', 'objectHeading', 'headingVector', 'headingLookAheadPixels',
    'objectVisible', 'complete', 'hold', 'eventControls', 'departurePulse'])
    assert.deepEqual(controls[key], original[key], `${key} changed at frame ${frame}`);
   assert(controls.routeFraction >= previous); previous = controls.routeFraction;
   assert(controls.routeFraction >= controls.objectFraction);
   assert.deepEqual(controls.routeReveal, evaluateGeographicLineReveal(value.primitive, controls.routeFraction));
   assert(controls.directionalFraction >= controls.objectFraction);
   assert(controls.directionalFraction <= controls.routeFraction);
   const expectedDirection = sampleFlowRoute(value.primitive, controls.directionalFraction,
    {lookAheadPixels: original.headingLookAheadPixels});
   assert.deepEqual(controls.directionalPosition, expectedDirection.position);
   assert.equal(controls.directionalHeading, expectedDirection.heading);
   if (controls.hold) assert.equal(controls.routeFraction, 1);
  }
  assert.equal(JSON.stringify({plan: value.plan, primitive: value.primitive}), before);
 }
});

test('Route introduction stays live through travel instead of completing in the initial reveal beat', () => {
 const value = fixture([[-4, 2], [-3, 1.9], [-1.6, 1.4], [1, .8], [3, .6]]);
 const first = render(value, 0), departure = render(value, 20), introductionEnd = render(value, 32);
 assert.equal(first.controls.routeFraction, 0);
 assert(departure.controls.routeFraction > 0 && departure.controls.routeFraction < 1);
 assert.equal(introductionEnd.original.routeFraction, 1);
 assert(introductionEnd.controls.routeFraction < .2);
 assert(render(value, 70).controls.routeFraction > introductionEnd.controls.routeFraction);
 assert.equal(render(value, 127).controls.routeFraction, 1);
 assert(render(value, 75).metadata.directionalLeadPixels > render(value, 75).objectGraphic.width_px * .5 + 7);
 const expected = render(value, 75);
 for (const frame of [179, 0, 135, 32]) render(value, frame);
 assert.deepEqual(render(value, 75), expected);
});

test('Arrival emphasis is one continuous pulse with an earlier single maximum and unchanged hold', () => {
 const value = fixture(), profile = compileFlowVisualProfile();
 const values = Array.from({length: value.plan.totalFrames}, (_, frame) => render(value, frame, profile));
 const active = values.filter(result => result.controls.arrivalPulse.active);
 assert.equal(active.length, value.plan.timing.arrival_pulse_frames);
 assert.equal(active[0].controls.frame, value.plan.arrivalFrame);
 assert.equal(active.at(-1).controls.frame, value.plan.holdFrame - 1);
 assert.equal(active[0].controls.arrivalPulse.alpha, 0);
 assert.equal(active.at(-1).controls.arrivalPulse.alpha, 0);
 const peak = active.reduce((chosen, result) => result.controls.arrivalPulse.alpha > chosen.controls.arrivalPulse.alpha
  ? result : chosen);
 assert(peak.controls.frame < value.plan.arrivalFrame + value.plan.timing.arrival_pulse_frames / 2);
 let increasing = true, previous = -1, maxima = 0;
 for (const result of active) {
  const alpha = result.controls.arrivalPulse.alpha;
  assert(alpha >= 0 && alpha <= 1); assert(result.controls.arrivalPulse.radius <= 64);
  if (alpha < previous && increasing) {increasing = false; maxima++;}
  if (!increasing) assert(alpha <= previous);
  previous = alpha;
  assert.deepEqual(result.controls.arrivalPulse.anchor, result.original.arrivalPulse.anchor);
 }
 assert.equal(maxima, 1);
 assert.equal(values.filter(result => result.controls.hold).length, 34);
 for (const result of values.filter(result => result.controls.hold)) {
  assert.equal(result.controls.pulse.alpha, 0);
  assert.deepEqual(result.controls.objectPosition, value.primitive.screenCoordinates.at(-1));
 }
});

test('Bad profiles or mismatched route/frame bindings fail before native drawing', () => {
 for (const options of [{objectScale: .9}, {objectScale: Infinity}, {routeLeadPixels: 0},
  {arrivalPeakProgress: .6}, {roleGroup: 'UNKNOWN'}, {unknown: 1}])
  assert.throws(() => compileFlowVisualProfile(options), /FLOW_VISUAL_/);
 const value = fixture(), controls = evaluateFlowFrame(value.plan, 40, value), profile = compileFlowVisualProfile();
 assert.throws(() => applyFlowVisualProfile({flowPlan: value.plan, controls: {...controls, localFrame: 1},
  primitive: value.primitive, profile}), /CURRENT_FRAME_BINDING/);
 const other = fixture([[-2, 1], [-.8, 1], [-.5, 1.5]]);
 assert.throws(() => applyFlowVisualProfile({flowPlan: value.plan, controls,
  primitive: other.primitive, profile}), /CURRENT_ROUTE_BINDING/);
});
