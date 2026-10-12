import test from 'node:test';
import assert from 'node:assert/strict';
import {chooseMetricPlacement} from '../web/map_infographic_v1/event_layout_adapter_v1.mjs';

const input = () => ({anchor: [200, 300], measurement: {atlasDimensions: [100, 40]}, safeArea: [0, 0, 600, 600],
 protectedBoxes: [], markerSize: 40, gap: 18});

test('right full-atlas candidate derives from geographic screen anchor and current marker/gap', () => {
 const result = chooseMetricPlacement(input());
 assert.equal(result.placement, 'RIGHT'); assert.deepEqual(result.box, [238, 280, 100, 40]); assert.deepEqual(result.roi, [238, 280, 338, 320]);
 assert.equal(result.reservationSpace, 'FULL_MEASURED_ATLAS'); assert.equal(result.ownership, 'EVENT_ANNOTATION_ONLY');
});
test('only annotation changes candidate when full old marker/panel boxes block its right placement', () => {
 const given = input(); given.protectedBoxes = [[237, 279, 339, 321]];
 const before = structuredClone(given), result = chooseMetricPlacement(given);
 assert.equal(result.placement, 'LEFT'); assert.deepEqual(result.box, [62, 280, 100, 40]); assert.deepEqual(given, before);
});
test('four anchor-derived candidates select above or below without moving historical labels', () => {
 const given = input(); given.protectedBoxes = [[237, 279, 339, 321], [61, 279, 163, 321]];
 const above = chooseMetricPlacement(given); assert.equal(above.placement, 'ABOVE'); assert.deepEqual(above.box, [150, 222, 100, 40]);
 given.protectedBoxes.push([149, 221, 251, 263]);
 const below = chooseMetricPlacement(given); assert.equal(below.placement, 'BELOW'); assert.deepEqual(below.box, [150, 338, 100, 40]);
});
test('safe area rejects full atlas overflow even if the revealed prefix would fit', () => {
 const given = {...input(), safeArea: [100, 100, 260, 550]};
 const result = chooseMetricPlacement(given); assert.equal(result.placement, 'ABOVE');
 assert.equal(result.candidates[0].safe, false); assert.equal(result.candidates[1].safe, false);
 assert.deepEqual(result.atlasDimensions, [100, 40]);
});
test('line ROI is another immutable exclusion; line collision chooses a different annotation candidate', () => {
 const given = {...input(), lineRoi: [230, 270, 350, 330]}, before = structuredClone(given);
 const result = chooseMetricPlacement(given);
 assert.equal(result.placement, 'LEFT'); assert.equal(result.candidates[0].lineCollision, true); assert.deepEqual(given, before);
});
test('all blocked candidates fail instead of guessing a screen coordinate or moving the camera', () => {
 const given = {...input(), protectedBoxes: [[0, 0, 600, 600]]};
 const before = structuredClone(given);
 assert.throws(() => chooseMetricPlacement(given), {message: 'EVENT_METRIC_LAYOUT_BLOCKED'}); assert.deepEqual(given, before);
 assert.throws(() => chooseMetricPlacement({...input(), measurement: {atlasDimensions: [700, 700]}}), /LAYOUT_BLOCKED/);
});
test('old text ink reserves actual outline plus two pixels, while marker/panel use full boxes', () => {
 const given = input(); given.protectedBoxes = [
  {kind: 'TEXT', box: [340, 282, 380, 310], outlineRadius: 1},
  {kind: 'MARKER', box: [180, 280, 220, 320]}, {kind: 'PANEL', box: [100, 100, 150, 130]},
 ];
 const result = chooseMetricPlacement(given);
 assert.deepEqual(result.protectedBoxes[0], [337, 279, 383, 313]);
 assert.deepEqual(result.protectedBoxes[1], [180, 280, 220, 320]); assert.deepEqual(result.protectedBoxes[2], [100, 100, 150, 130]);
 assert.equal(result.placement, 'LEFT');
});
test('all returned placement metadata is frozen and input references are defensively copied', () => {
 const given = input(), result = chooseMetricPlacement(given);
 given.anchor[0] = 99; given.measurement.atlasDimensions[0] = 900; given.safeArea[0] = 50;
 assert.deepEqual(result.anchor, [200, 300]); assert.deepEqual(result.atlasDimensions, [100, 40]); assert.deepEqual(result.safeArea, [0, 0, 600, 600]);
 assert(Object.isFrozen(result.candidates[0].roi)); assert(Object.isFrozen(result.box));
 assert.throws(() => {result.box[0] = 0;}, TypeError);
});
test('full measured atlas produces stable placement independent of reveal progress or prefix width', () => {
 const given = input(), result = chooseMetricPlacement(given);
 for (const visibleFraction of [0, .25, .75, 1]) {
  const next = chooseMetricPlacement({...given, measurement: {...given.measurement, visibleFraction, prefixDimensions: [20, 40]}});
  assert.deepEqual(next.box, result.box); assert.deepEqual(next.roi, result.roi);
 }
});
test('different screen anchors, orientations, marker radii and caller gaps remain data-driven', () => {
 const first = chooseMetricPlacement({...input(), anchor: [50, 100], markerSize: 20, gap: 5});
 assert.deepEqual(first.box, [65, 80, 100, 40]);
 const second = chooseMetricPlacement({...input(), anchor: [500, 100], markerSize: 60, gap: 30});
 assert.equal(second.placement, 'LEFT'); assert.deepEqual(second.box, [340, 80, 100, 40]);
});
test('zero-area or nonfinite bounds, missing dimensions/markers/gaps and out-of-safe anchors fail', () => {
 for (const change of [{anchor: [NaN, 3]}, {anchor: [-1, 3]}, {measurement: {atlasDimensions: [20.5, 40]}},
  {measurement: {atlasDimensions: [0, 40]}}, {markerSize: 0}, {gap: undefined}, {gap: -1},
  {safeArea: [0, 0, 0, 100]}, {protectedBoxes: undefined}, {lineRoi: [0, 0, 20, Infinity]},
  {protectedBoxes: [{kind: 'TEXT', box: [0, 0, 20, 20]}]},
  {protectedBoxes: [{kind: 'UNKNOWN', box: [0, 0, 20, 20]}]}]) {
  assert.throws(() => chooseMetricPlacement({...input(), ...change}), /EVENT_/);
 }
});
