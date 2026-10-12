import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileMinimumContextIntent, compileMinimumContextPlan, evaluateMinimumContextCameraFrame} from '../web/map_infographic_v1/camera_director_v5.mjs';

const polygon = (id, b) => ({id, geometry_type: 'Polygon', coordinates: [[[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]], [b[0], b[1]]]]});
const baseScene = () => ({primary_region_id: 'PRIMARY_SYNTHETIC', primary_geometry: polygon('PRIMARY_SYNTHETIC', [10, 20, 12, 22]),
 event_anchor: [11, 21], approved_final_extent: [9, 19, 13, 23], start_extent: [8, 16, 14, 26],
 primary_label: 'Primary', event_title: 'Event', location_label: 'Location'});
const safeBounds = intent => {
 const b = intent.contextExtent, a = intent.display.safeArea, [w, h] = intent.display.canonicalOutput;
 return [b[0] + a[0] / w * (b[2] - b[0]), b[3] - a[3] / h * (b[3] - b[1]),
  b[0] + a[2] / w * (b[2] - b[0]), b[3] - a[1] / h * (b[3] - b[1])];
};
const contains = (outer, inner) => outer[0] <= inner[0] + 1e-9 && outer[1] <= inner[1] + 1e-9 && outer[2] + 1e-9 >= inner[2] && outer[3] + 1e-9 >= inner[3];
const area = b => (b[2] - b[0]) * (b[3] - b[1]);

test('A: readable Primary and anchor skip Context without forced zoom', () => {
 const scene = baseScene(), before = structuredClone(scene), intent = compileMinimumContextIntent(scene);
 assert.equal(intent.context.required, false);
 assert.deepEqual(intent.contextExtent, scene.start_extent);
 assert.deepEqual(intent.finalExtent, scene.approved_final_extent);
 assert.deepEqual(scene, before);
});

test('B: actual event route outside safe view receives minimum aspect fit', () => {
 const scene = {...baseScene(), event_geometry: {id: 'EVENT_ROUTE', geometry_type: 'LineString', coordinates: [[11, 21], [16, 27]]}};
 const intent = compileMinimumContextIntent(scene), b = intent.contextExtent;
 assert.equal(intent.context.required, true);
 assert(contains(safeBounds(intent), intent.context.requiredGeometryBounds));
 assert(b[2] - b[0] >= 6 && b[3] - b[1] >= 10);
 const latitude = (b[1] + b[3]) / 2;
 assert(Math.abs((b[2] - b[0]) * Math.cos(latitude * Math.PI / 180) / (b[3] - b[1]) - 1080 / 1920) < 1e-12);
 // This fixture is width-limited: any uniformly smaller extent violates safety.
 const c = [(b[0] + b[2]) / 2, latitude], scale = 1 - 1e-6;
 const smaller = [c[0] - (b[2] - b[0]) * scale / 2, c[1] - (b[3] - b[1]) * scale / 2,
  c[0] + (b[2] - b[0]) * scale / 2, c[1] + (b[3] - b[1]) * scale / 2];
 assert.equal(contains(safeBounds({...intent, contextExtent: smaller}), intent.context.requiredGeometryBounds), false);
});

test('B direct relation is an explicit required constraint with retained provenance', () => {
 const direct = {id: 'DIRECT_RELATION', geometry_type: 'LineString', coordinates: [[11, 21], [17, 24]]};
 const intent = compileMinimumContextIntent(baseScene(), {relationGeometry: direct});
 assert.equal(intent.context.required, true);
 assert.equal(intent.context.directRelationSourceCount, 1);
 assert.deepEqual(intent.context.directRelationGeometry, direct);
 assert(contains(safeBounds(intent), [10, 20, 17, 24]));
});

test('B far actual anchor needs context; approved final stays exact even if Primary is no longer visible', () => {
 const scene = {...baseScene(), event_anchor: [30, 35], approved_final_extent: [28, 31, 32, 39]};
 const intent = compileMinimumContextIntent(scene);
 assert.equal(intent.context.required, true);
 assert(contains(safeBounds(intent), [10, 20, 30, 35]));
 assert.deepEqual(intent.anchor, scene.event_anchor);
 assert.deepEqual(intent.startExtent, scene.start_extent);
 assert.deepEqual(intent.finalExtent, scene.approved_final_extent);
 const plan = compileMinimumContextPlan({intent});
 const final = evaluateMinimumContextCameraFrame(plan, plan.checkpoints.FINAL_HOLD);
 assert.deepEqual(final.camera.flatBounds, scene.approved_final_extent);
 assert.equal(final.projectedAnchor.inSafe, true);
 // The author-approved distant final box cannot also show this Primary. The
 // camera keeps that exact input rather than inventing a different final view.
 assert.equal(final.projectedRegion.visible, false);
});

test('C: unrelated countries and legacy whole context extent cannot expand required context', () => {
 const scene = baseScene(), plain = compileMinimumContextIntent(scene);
 const withContext = compileMinimumContextIntent({...scene, context_geometry: [polygon('DISTANT', [-100, -40, -95, -35]),
  polygon('BROAD_OPTIONAL', [-80, 19, 160, 70])], context_extent: [-120, -50, 170, 80]});
 assert.deepEqual(withContext.contextExtent, plain.contextExtent);
 assert.equal(withContext.context.optionalContextSourceCount, 2);
 assert.equal(withContext.context.optionalContextPortions[0].bounds, null);
 assert.deepEqual(withContext.context.optionalContextPortions[1].bounds, plain.context.requiredGeometryBounds);
 assert.equal(withContext.context.legacyContextExtentUsage, 'NOT_A_REQUIRED_CONSTRAINT');
});

test('C: unrelated countries do not alter an event-constrained fit', () => {
 const scene = {...baseScene(), event_geometry: {geometry_type: 'LineString', coordinates: [[11, 21], [16, 27]]}};
 assert.deepEqual(compileMinimumContextIntent({...scene, context_geometry: polygon('DISTANT', [-100, -40, -95, -35])}).contextExtent,
  compileMinimumContextIntent(scene).contextExtent);
});

test('asymmetric safe area is respected without changing output or approved final', () => {
 const scene = {...baseScene(), safe_area: [80, 150, 1000, 1800], event_geometry: {geometry_type: 'Point', coordinates: [16, 27]}};
 const intent = compileMinimumContextIntent(scene);
 assert(contains(safeBounds(intent), intent.context.requiredGeometryBounds));
 assert.deepEqual(intent.display.safeArea, scene.safe_area);
 assert.deepEqual(intent.finalExtent, scene.approved_final_extent);
});

test('saved Suez data excludes the excessive five-country union and preserves start/final', () => {
 const saved = JSON.parse(readFileSync(new URL('../recovery/v4/V4-state-records/camera-plan.json', import.meta.url), 'utf8')).intent;
 const scene = {primary_region_id: saved.primaryRegionId, primary_geometry: saved.primaryGeometry, event_anchor: saved.anchor,
  event_geometry: saved.eventGeometry, context_geometry: saved.contextGeometry, canonical_output: saved.display.canonicalOutput,
  safe_area: saved.display.safeArea, start_extent: saved.startExtent, approved_final_extent: saved.approvedFinalExtent,
  scale_admission: saved.admission, primary_label: saved.texts.primaryLabel, location_label: saved.texts.locationLabel,
  event_title: saved.texts.eventTitle};
 const intent = compileMinimumContextIntent(scene);
 assert.equal(intent.context.required, false);
 assert.deepEqual(intent.contextExtent, saved.startExtent);
 assert.deepEqual(intent.startExtent, saved.startExtent);
 assert.deepEqual(intent.finalExtent, saved.finalExtent);
 assert.equal(intent.context.optionalContextSourceCount, saved.contextGeometry.length);
 assert(area(saved.contextExtent) / area(intent.contextExtent) > 10);
});

test('V4 public shape compatibility, random access and exact final bound preservation', () => {
 const plan = compileMinimumContextPlan({scene: baseScene(), seed: 3});
 assert.equal(plan.version, 'CAMERA_DIRECTOR_V4');
 assert.equal(plan.directorVersion, 'CAMERA_DIRECTOR_V5');
 assert.equal(plan.implementationStage, 'NATURAL_TURNAROUND');
 assert(!plan.timeline.some(state => state.state === 'CONTEXT_EXPANSION'));
 const final = evaluateMinimumContextCameraFrame(plan, plan.checkpoints.FINAL_HOLD);
 assert.deepEqual(final.camera.flatBounds, baseScene().approved_final_extent);
 assert.deepEqual(evaluateMinimumContextCameraFrame(plan, 7), evaluateMinimumContextCameraFrame(plan, 7));
 assert.equal(final.primaryMaterial, 1);
 assert.equal(plan.compatibility.revealAlgorithm, 'UNCHANGED');
});

test('V4 Local admission and approved safe closest validation remain active', () => {
 const local = {...baseScene(), desired_detail_level: 'LOCAL', scale_admission: {status: 'LOCAL_ADMITTED', renderLocal: true, admittedExtent: [10, 20, 12, 22]}};
 assert.deepEqual(compileMinimumContextIntent(local).finalExtent, [10, 20, 12, 22]);
 assert.throws(() => compileMinimumContextIntent({...baseScene(), scale_admission: {safeClosest: {bounds: [0, 0, 1, 1]}}}), /SAFE_CLOSEST_MISMATCH/);
});

test('required geometry, anchor and invalid explicit relation fail rather than inventing data', () => {
 assert.throws(() => compileMinimumContextIntent({...baseScene(), primary_geometry: null}), /PRIMARY_GEOMETRY_REQUIRED/);
 assert.throws(() => compileMinimumContextIntent({...baseScene(), event_anchor: [200, 21]}), /ANCHOR_REQUIRED/);
 assert.throws(() => compileMinimumContextIntent(baseScene(), {relationGeometry: {geometry_type: 'LineString', coordinates: []}}), /GEOMETRY_COORDINATES_REQUIRED/);
});

test('explicit remote recognition start fails closed without silently changing saved input', () => {
 const scene = {...baseScene(), start_extent: [-80, 16, -74, 26]}, before = structuredClone(scene);
 assert.throws(() => compileMinimumContextIntent(scene), /PRIMARY_RECOGNITION_INFEASIBLE/);
 assert.deepEqual(scene, before);
});

test('implicit recognition uses actual asymmetric safe rectangle', () => {
 const scene = {...baseScene(), safe_area: [0, 0, 300, 1200]}; delete scene.start_extent;
 const intent = compileMinimumContextIntent(scene);
 assert(contains(safeBounds({...intent, contextExtent: intent.startExtent}), intent.primaryBounds));
 assert.deepEqual(intent.finalExtent, scene.approved_final_extent);
});

test('actual Primary polygon is required, not a visible bbox around empty geometry', () => {
 const scene = {...baseScene(), primary_geometry: {id: 'NOT_A_POLYGON', geometry_type: 'LineString', coordinates: [[10, 20], [12, 22]]}};
 assert.throws(() => compileMinimumContextIntent(scene), /PRIMARY_RECOGNITION_INFEASIBLE/);
});

const farPlan = fps => compileMinimumContextPlan({scene: {...baseScene(), event_anchor: [30, 35],
 approved_final_extent: [28, 31, 32, 39]}, profile: {fps}});
const close = (a, b, tolerance = 1e-9) => assert(Math.abs(a - b) <= tolerance, `${a} != ${b}`);

test('far Context turn has shared actual-seconds C2 derivatives and nonzero pan', () => {
 const plan = farPlan(30), [left, right] = plan.naturalMotion.segments;
 assert(!plan.timeline.some(state => state.state === 'RELATION_HOLD'));
 assert.equal(plan.checkpoints.DIRECTIONAL_TURN, plan.naturalMotion.peakFrame);
 assert.deepEqual(left.endVelocity, right.startVelocity);
 assert.deepEqual(left.endAcceleration, right.startAcceleration);
 assert(Math.hypot(...left.endVelocity.slice(0, 2)) > 0);
 for (let axis = 0; axis < 4; axis++) {
  const a = left.coefficients[axis], b = right.coefficients[axis];
  close(a.reduce((sum, value, i) => sum + (i ? i * value : 0), 0) / left.durationSeconds,
   b[1] / right.durationSeconds, 1e-9);
  close(a.reduce((sum, value, i) => sum + (i > 1 ? i * (i - 1) * value : 0), 0) / left.durationSeconds ** 2,
   2 * b[2] / right.durationSeconds ** 2, 1e-9);
 }
 const peak = plan.naturalMotion.peakFrame, at = evaluateMinimumContextCameraFrame(plan, peak);
 assert.deepEqual(at.camera.flatBounds, plan.intent.contextExtent);
 close(at.velocity.logWidthPerSecond, 0);
 assert(Math.hypot(at.velocity.longitudeDegreesPerSecond, at.velocity.latitudeDegreesPerSecond) > 0);
 assert(evaluateMinimumContextCameraFrame(plan, peak - 1).velocity.logWidthPerSecond > 0);
 assert(evaluateMinimumContextCameraFrame(plan, peak + 1).velocity.logWidthPerSecond < 0);
 close(at.panWeight, 1); close(at.zoomWeight, 0);
 assert(evaluateMinimumContextCameraFrame(plan, peak + Math.floor((plan.naturalMotion.arrivalFrame - peak) / 2)).zoomWeight > 0);
});

test('moving Context beat keeps actual Primary core visible and event anchor safe', () => {
 const plan = farPlan(30), turn = plan.timeline.find(state => state.state === 'DIRECTIONAL_TURN');
 for (let frame = turn.startFrame; frame < turn.endFrame; frame++) {
  const state = evaluateMinimumContextCameraFrame(plan, frame);
  assert.equal(state.projectedRegion.geometryVisible, true);
  assert.equal(state.projectedRegion.geometryVisibleInSafe, true);
  assert.equal(state.projectedAnchor.inSafe, true);
  assert(Math.hypot(state.velocity.longitudeDegreesPerSecond, state.velocity.latitudeDegreesPerSecond,
   state.velocity.logWidthPerSecond, state.velocity.logHeightPerSecond) > 0);
 }
 // This is Context/turn feasibility, not a claim that the distant final still
 // contains Primary; that final is explicitly author-approved and preserved.
 assert.equal(evaluateMinimumContextCameraFrame(plan, plan.checkpoints.FINAL_HOLD).projectedRegion.visible, false);
});

test('whole camera trajectory never zooms past context or approved final and ends exactly static', () => {
 const plan = farPlan(30), maximum = plan.intent.contextExtent, minimum = plan.intent.finalExtent;
 for (let frame = plan.naturalMotion.startFrame; frame < plan.totalFrames; frame++) {
  const state = evaluateMinimumContextCameraFrame(plan, frame), b = state.camera.flatBounds;
  for (let axis = 0; axis < 2; axis++) {
   assert(b[axis + 2] - b[axis] <= maximum[axis + 2] - maximum[axis] + 1e-10);
   assert(b[axis + 2] - b[axis] >= minimum[axis + 2] - minimum[axis] - 1e-10);
  }
 }
 for (const frame of [plan.naturalMotion.startFrame, plan.naturalMotion.arrivalFrame, plan.checkpoints.FINAL_HOLD, plan.totalFrames - 1]) {
  const state = evaluateMinimumContextCameraFrame(plan, frame);
  assert(Object.values(state.velocity).every(value => value === 0));
  assert(Object.values(state.acceleration).every(value => value === 0));
  if (frame >= plan.naturalMotion.arrivalFrame) assert.deepEqual(state.camera.flatBounds, minimum);
 }
});

test('actual-seconds spline derivatives and random access are valid at different fps', () => {
 const localJerkBound = (segment, axis, low, high) => {
  const c = segment.coefficients[axis], candidates = [low, high];
  if (c[5] !== 0) {
   const vertex = -c[4] / (5 * c[5]);
   if (vertex > low && vertex < high) candidates.push(vertex);
  }
  return Math.max(...candidates.map(t => Math.abs(6 * c[3] + 24 * c[4] * t + 60 * c[5] * t * t))) / segment.durationSeconds ** 3;
 };
 for (const fps of [24, 60]) {
  const plan = farPlan(fps), frame = plan.naturalMotion.peakFrame;
  const left = evaluateMinimumContextCameraFrame(plan, frame - 1), at = evaluateMinimumContextCameraFrame(plan, frame), right = evaluateMinimumContextCameraFrame(plan, frame + 1);
  const h = 1 / fps, [incoming, outgoing] = plan.naturalMotion.segments;
  for (const axis of [0, 1]) {
   // A one-frame central difference has bounded O(h²) error even when jerk
   // differs across a C2 knot. Use the actual polynomial's local jerk bound.
   const jerk = Math.max(localJerkBound(incoming, axis, 1 - h / incoming.durationSeconds, 1),
    localJerkBound(outgoing, axis, 0, h / outgoing.durationSeconds));
   const expected = axis === 0 ? at.velocity.longitudeDegreesPerSecond : at.velocity.latitudeDegreesPerSecond;
   close((right.center[axis] - left.center[axis]) / (2 * h), expected, jerk * h * h / 6 + 1e-9);
  }
  assert.deepEqual(at, evaluateMinimumContextCameraFrame(plan, frame));
  assert.equal(at.primaryMaterial, 1);
 }
});

test('real zoom separates early pan completion from later zoom and late event motion slows', () => {
 const scene = {...baseScene(), event_anchor: [30, 35], approved_final_extent: [28, 31, 33, 39]};
 const plan = compileMinimumContextPlan({scene}), midpoint = name => {
  const s = plan.timeline.find(state => state.state === name);
  return evaluateMinimumContextCameraFrame(plan, s.startFrame + Math.floor(s.durationFrames / 2));
 };
 const early = midpoint('EVENT_APPROACH'), late = midpoint('EVENT_FRAMING'), deceleration = midpoint('DECELERATE');
 assert.equal(plan.naturalMotion.realZoomNeeded, true);
 assert.equal(plan.naturalMotion.panArrivalFrame, plan.timeline.find(s => s.state === 'DECELERATE').startFrame);
 assert(early.panWeight > late.panWeight);
 assert(late.zoomWeight > early.zoomWeight);
 assert(early.panWeight > early.zoomWeight);
 close(late.panWeight, 0); close(late.zoomWeight, 1);
 assert(late.screenVelocity.event.pixelsPerSecond < deceleration.screenVelocity.event.pixelsPerSecond);
 const split = evaluateMinimumContextCameraFrame(plan, plan.naturalMotion.panArrivalFrame);
 assert.deepEqual(split.center, [(scene.approved_final_extent[0] + scene.approved_final_extent[2]) / 2,
  (scene.approved_final_extent[1] + scene.approved_final_extent[3]) / 2]);
 close(split.panProgress, 1); assert(split.zoomProgress < 1);
 assert(Math.abs(split.velocity.logWidthPerSecond) > 0);
 for (let i = 1; i < plan.naturalMotion.segments.length; i++) {
  const left = plan.naturalMotion.segments[i - 1], right = plan.naturalMotion.segments[i];
  assert.deepEqual(left.to, right.from);
  assert.deepEqual(left.endVelocity, right.startVelocity);
  assert.deepEqual(left.endAcceleration, right.startAcceleration);
  for (let axis = 0; axis < 4; axis++) {
   close(left.coefficients[axis].reduce((sum, value, power) => sum + (power ? power * value : 0), 0) / left.durationSeconds,
    right.coefficients[axis][1] / right.durationSeconds, 1e-9);
   close(left.coefficients[axis].reduce((sum, value, power) => sum + (power > 1 ? power * (power - 1) * value : 0), 0) / left.durationSeconds ** 2,
    2 * right.coefficients[axis][2] / right.durationSeconds ** 2, 1e-9);
  }
 }
});

test('motion entry is the literal approved start, with zero velocity and acceleration', () => {
 const saved = JSON.parse(readFileSync(new URL('../recovery/v4/V4-state-records/camera-plan.json', import.meta.url), 'utf8')).intent;
 const plan = compileMinimumContextPlan({scene: {primary_region_id: saved.primaryRegionId, primary_geometry: saved.primaryGeometry,
  event_anchor: saved.anchor, start_extent: saved.startExtent, approved_final_extent: saved.approvedFinalExtent,
  context_geometry: saved.contextGeometry, safe_area: saved.display.safeArea}});
 const entry = evaluateMinimumContextCameraFrame(plan, plan.naturalMotion.startFrame);
 assert.deepEqual(entry.camera.flatBounds, saved.startExtent);
 assert(Object.values(entry.velocity).every(value => value === 0));
 assert(Object.values(entry.acceleration).every(value => value === 0));
 assert.equal(plan.naturalMotion.realZoomNeeded, false);
 assert.equal(plan.naturalMotion.panArrivalFrame, plan.naturalMotion.arrivalFrame);
 assert.equal(plan.naturalMotion.segments.length, 1);
});

test('coincident centers expose pure zoom reversal without inventing directional pan', () => {
 const scene = {primary_region_id: 'SYMMETRIC_PRIMARY', primary_geometry: polygon('SYMMETRIC_PRIMARY', [-1, -1, 1, 1]),
  event_anchor: [0, 0], start_extent: [-2, -4, 2, 4], approved_final_extent: [-1, -2, 1, 2],
  event_geometry: {geometry_type: 'LineString', coordinates: [[-8, 0], [8, 0]]}};
 const plan = compileMinimumContextPlan({scene}), peak = evaluateMinimumContextCameraFrame(plan, plan.naturalMotion.peakFrame);
 assert.equal(plan.naturalMotion.turnMode, 'PURE_ZOOM_REVERSAL');
 close(peak.velocity.longitudeDegreesPerSecond, 0); close(peak.velocity.latitudeDegreesPerSecond, 0);
 close(peak.velocity.logWidthPerSecond, 0);
 assert(peak.acceleration.logWidthPerSecondSquared < 0);
 assert(evaluateMinimumContextCameraFrame(plan, plan.naturalMotion.peakFrame - 1).velocity.logWidthPerSecond > 0);
 assert(evaluateMinimumContextCameraFrame(plan, plan.naturalMotion.peakFrame + 1).velocity.logWidthPerSecond < 0);
 assert(!plan.timeline.some(state => state.state === 'RELATION_HOLD'));
 for (let frame = 0; frame < plan.totalFrames; frame++) assert.deepEqual(evaluateMinimumContextCameraFrame(plan, frame).center, [0, 0]);
});
