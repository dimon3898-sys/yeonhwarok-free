import test from 'node:test';
import assert from 'node:assert/strict';
import {chooseRelatedMetricPlacement} from '../web/map_infographic_v1/event_layout_adapter_v1.mjs';

const input = () => ({linePrimitive: {screenCoordinates: [[100, 300], [500, 300]]},
 measurement: {atlasDimensions: [120, 48]}, safeArea: [0, 0, 600, 600], protectedBoxes: [],
 markerOcclusions: [], linePaddingPixels: 6, gap: 10, anchor: [300, 300]});
const overlaps = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
function assertSafe(result) {
 assert.equal(result.lineCollision, false);
 assert.ok(result.relationshipGapPixels >= 8 - 1e-9 && result.relationshipGapPixels <= 14 + 1e-9);
 assert.ok(result.roi[0] >= result.safeArea[0] && result.roi[1] >= result.safeArea[1]);
 assert.ok(result.roi[2] <= result.safeArea[2] && result.roi[3] <= result.safeArea[3]);
 for (const box of result.protectedBoxes) assert.equal(overlaps(result.roi, box), false);
 assert.equal(result.ownership, 'EVENT_ANNOTATION_ONLY');
 assert.equal(result.reservationSpace, 'FULL_MEASURED_ATLAS');
}

test('annotation uses visible line support and measured full atlas with a ten pixel halo gap', () => {
 const result = chooseRelatedMetricPlacement(input()); assertSafe(result);
 assert.ok(Math.abs(result.relationshipGapPixels - 10) < 1e-9);
 assert.deepEqual(result.box.slice(2), [120, 48]);
 assert.equal(result.nearestVisiblePoint[1], 300);
 assert.ok(result.nearestVisiblePoint[0] >= result.roi[0] && result.nearestVisiblePoint[0] <= result.roi[2]);
 assert.equal(result.relationshipSpace, 'FULL_VISIBLE_PROJECTED_GEOMETRY_AFTER_MARKER_OCCLUSION');
});

test('Marker occlusion cuts placement support only while preserving supplied line geometry and full strict Marker bounds', () => {
 const given = {...input(), markerOcclusions: [[240, 260, 360, 340]], protectedBoxes: [
  {kind: 'MARKER', box: [240, 260, 360, 340]},
  {kind: 'TEXT', box: [80, 205, 230, 250], outlineRadius: 2},
 ]};
 const before = structuredClone(given), result = chooseRelatedMetricPlacement(given); assertSafe(result);
 assert.deepEqual(given, before);
 assert.deepEqual(result.visibleSupportSegments.map(segment => segment.path), [
  [[100, 300], [240, 300]], [[360, 300], [500, 300]],
 ]);
 assert.ok(result.nearestVisiblePoint[0] <= 240 || result.nearestVisiblePoint[0] >= 360);
 assert.deepEqual(result.protectedBoxes[0], [240, 260, 360, 340]);
 assert.deepEqual(result.protectedBoxes[1], [76, 201, 234, 254]);
});

test('multiple overlapping Marker occlusions clip the union without restarting original intervals', () => {
 const given = {...input(), markerOcclusions: [[200, 250, 290, 350], [260, 250, 370, 350]],
  protectedBoxes: [[200, 250, 290, 350], [260, 250, 370, 350]]};
 const result = chooseRelatedMetricPlacement(given); assertSafe(result);
 assert.deepEqual(result.visibleSupportSegments.map(segment => segment.path), [
  [[100, 300], [200, 300]], [[370, 300], [500, 300]],
 ]);
 assert.deepEqual(result.visibleSupportSegments.map(segment => segment.interval), [[0, .25], [.675, 1]]);
});

test('curved-line interior remains eligible without excluding its whole line AABB', () => {
 const result = chooseRelatedMetricPlacement({...input(),
  linePrimitive: {screenCoordinates: [[100, 150], [100, 450], [500, 450]]}, anchor: [300, 350],
  measurement: {atlasDimensions: [100, 36]}, protectedBoxes: [[0, 0, 600, 130], [0, 470, 600, 600], [0, 130, 80, 470]]});
 assertSafe(result);
 assert.ok(result.roi[0] > 100 && result.roi[2] < 500 && result.roi[1] > 150 && result.roi[3] < 450,
  'annotation may occupy safe interior of a curved line bounding rectangle');
});

test('alternate line orientations and scales choose a measured near-line relation without coordinate specialization', () => {
 for (const points of [[[300, 80], [300, 520]], [[100, 100], [500, 500]],
  [[500, 100], [100, 500]], [[120, 420], [200, 360], [440, 180]], [[500, 300], [100, 300]]]) {
  const given = {...input(), linePrimitive: {screenCoordinates: points}, measurement: {atlasDimensions: [150, 56]}};
  const before = structuredClone(given), result = chooseRelatedMetricPlacement(given); assertSafe(result);
  assert.deepEqual(given, before); assert.ok(result.eligibleCandidateCount > 0);
 }
});

test('Country/Location/Title reservations reject only annotation candidates and retain full text outline padding', () => {
 const given = {...input(), protectedBoxes: [
  {kind: 'TEXT', box: [70, 220, 530, 280], outlineRadius: 3},
  {kind: 'TEXT', box: [0, 0, 600, 100], outlineRadius: 1},
  {kind: 'PANEL', box: [0, 500, 600, 600]},
 ]};
 const before = structuredClone(given), result = chooseRelatedMetricPlacement(given); assertSafe(result);
 assert.equal(result.placement, 'NORMAL_LEFT');
 assert.ok(result.box[1] > 300); assert.ok(result.rejectionCounts.protected > 0);
 assert.deepEqual(result.protectedBoxes[0], [65, 215, 535, 285]); assert.deepEqual(given, before);
});

test('full line and atlas preserve placement through every Metric reveal fraction and direction', () => {
 const given = input(), original = chooseRelatedMetricPlacement(given);
 for (const visibleFraction of [0, .25, .75, 1]) {
  const next = chooseRelatedMetricPlacement({...given, linePrimitive: {...given.linePrimitive, visibleFraction},
   measurement: {...given.measurement, visibleFraction, prefixDimensions: [12, 48]}});
  assert.deepEqual(next.box, original.box); assert.deepEqual(next.roi, original.roi);
 }
 const reverse = chooseRelatedMetricPlacement({...given, linePrimitive: {screenCoordinates: [...given.linePrimitive.screenCoordinates].reverse()}});
 assert.deepEqual(reverse.box, original.box);
});

test('fully occluded geometry, crowded native graphics, and full-atlas overflow fail closed', () => {
 const cases = [
  {...input(), markerOcclusions: [[50, 250, 550, 350]]},
  {...input(), protectedBoxes: [{kind: 'MARKER', box: [0, 0, 600, 600]}]},
  {...input(), protectedBoxes: [{kind: 'TEXT', box: [0, 0, 600, 600], outlineRadius: 2}]},
  {...input(), measurement: {atlasDimensions: [700, 48]}},
 ];
 for (const given of cases) {
  const before = structuredClone(given);
  assert.throws(() => chooseRelatedMetricPlacement(given), {message: 'EVENT_METRIC_LAYOUT_BLOCKED'});
  assert.deepEqual(given, before);
 }
});

test('disjoint caller-provided visible support and unrelated anchor remain data-driven', () => {
 const result = chooseRelatedMetricPlacement({...input(), linePrimitive: undefined,
  visibleGeometry: {segments: [[[60, 100], [250, 100]], [[350, 400], [550, 400]]]},
  anchor: [500, 100], protectedBoxes: [[0, 0, 300, 90]], measurement: {atlasDimensions: [90, 38]}});
 assertSafe(result); assert.equal(result.visibleSupportSegments.length, 2);
 assert.ok(result.relationshipGapPixels < 11);
});

test('placement metadata is deeply frozen and preserves no mutable input references', () => {
 const given = input(), result = chooseRelatedMetricPlacement(given);
 given.linePrimitive.screenCoordinates[0][0] = 0; given.measurement.atlasDimensions[0] = 900;
 given.protectedBoxes.push([0, 0, 600, 600]);
 assert.deepEqual(result.atlasDimensions, [120, 48]);
 assert.deepEqual(result.visibleSupportSegments[0].path, [[100, 300], [500, 300]]);
 assert.ok(Object.isFrozen(result.visibleSupportSegments[0].path[0]));
 assert.throws(() => { result.box[0] = 0; }, TypeError);
});

test('invalid geometry, measurements, clearance, protection, and gap range reject instead of guessing', () => {
 for (const change of [{linePrimitive: null}, {linePrimitive: {screenCoordinates: [[1, 1]]}},
  {linePrimitive: {screenCoordinates: [[1, 1], [1, 1]]}}, {linePrimitive: {screenCoordinates: [[NaN, 1], [2, 2]]}},
  {linePaddingPixels: undefined}, {linePaddingPixels: -1}, {measurement: {atlasDimensions: [20.5, 30]}},
  {markerOcclusions: [[0, 0, 20, Infinity]]}, {protectedBoxes: undefined},
  {protectedBoxes: [{kind: 'TEXT', box: [0, 0, 20, 20]}]}, {minGap: 12}, {maxGap: 4}, {distanceWeight: -1}])
  assert.throws(() => chooseRelatedMetricPlacement({...input(), ...change}), /EVENT_/);
});
