import test from 'node:test';
import assert from 'node:assert/strict';
import {compileEventIntent} from '../web/map_infographic_v1/event_contract_v1.mjs';
import {compileEventPlan, evaluateEventFrame} from '../web/map_infographic_v1/event_timeline_v1.mjs';
import {compileGeographicLinePrimitive, assertGeographicLinePrimitive, evaluateGeographicLineReveal} from '../web/map_infographic_v1/event_line_v1.mjs';

const intent = (coordinates = [[0, 0], [1, 0], [1, 9]], direction = 'FORWARD') => compileEventIntent({data_mode: 'SYNTHETIC_TEST',
 line: {geometry: {type: 'LineString', coordinates}, direction, style_role: 'EVENT_HIGHLIGHT',
  source: {source_type: 'SYNTHETIC_TEST', source_reference: 'fixture://projected-arc-length', verification_status: 'SYNTHETIC_TEST'}}});
const projected = (given = intent()) => compileGeographicLinePrimitive(given, {project: point => [...point]});
const pathLength = path => path.slice(1).reduce((total, point, index) => total + Math.hypot(point[0] - path[index][0], point[1] - path[index][1]), 0);
const close = (a, b, tolerance = 1e-10) => assert(Math.abs(a - b) <= tolerance, `${a} != ${b}`);

test('nonuniform segment lengths reveal by distance, not by vertex index', () => {
 const p = projected(); assert.deepEqual(p.segmentLengthsPixels, [1, 9]); assert.equal(p.totalLengthPixels, 10);
 assert.deepEqual(evaluateGeographicLineReveal(p, .5).path, [[0, 0], [1, 0], [1, 4]]);
});
test('exact zero is empty and exact one contains every directed supplied projected vertex', () => {
 const p = projected(); const zero = evaluateGeographicLineReveal(p, 0), one = evaluateGeographicLineReveal(p, 1);
 assert.deepEqual(zero.path, []); assert.equal(zero.roi, null); assert.equal(zero.visibleLengthPixels, 0);
 assert.deepEqual(one.path, p.screenCoordinates); assert.equal(one.visibleLengthPixels, p.totalLengthPixels); assert.equal(one.complete, true);
});
test('explicit reverse changes start and drawing direction without mutating original geometry', () => {
 const i = intent(undefined, 'REVERSE'), before = structuredClone(i), p = projected(i);
 assert.deepEqual(p.screenCoordinates, [[1, 9], [1, 0], [0, 0]]);
 assert.deepEqual(evaluateGeographicLineReveal(p, .5).path, [[1, 9], [1, 4]]);
 assert.deepEqual(i, before);
});
test('current supplied projection determines visual speed without computing a geographic metric', () => {
 const i = intent([[1, 1], [4, 1], [4, 2]]), p = compileGeographicLinePrimitive(i, {project: point => [point[0] * 2, point[1] * 10]});
 assert.deepEqual(p.segmentLengthsPixels, [6, 10]); assert.equal(p.measurementSpace, 'CURRENT_PROJECTED_SCREEN_PIXELS');
 assert.deepEqual(evaluateGeographicLineReveal(p, .5).path, [[2, 10], [8, 10], [8, 12]]);
});
test('densifying a collinear input does not change arc-length endpoint position', () => {
 const a = projected(intent([[0, 0], [1, 0], [1, 9]]));
 const b = projected(intent([[0, 0], [.2, 0], [.7, 0], [1, 0], [1, 2], [1, 6], [1, 9]]));
 for (const fraction of [.05, .1, .125, .25, .6, .8, .975]) {
  const pa = evaluateGeographicLineReveal(a, fraction), pb = evaluateGeographicLineReveal(b, fraction);
  close(pa.path.at(-1)[0], pb.path.at(-1)[0]); close(pa.path.at(-1)[1], pb.path.at(-1)[1]);
  close(pathLength(pa.path), pathLength(pb.path));
 }
});
test('duplicates remain unchanged at complete reveal and cannot cause division by zero', () => {
 const i = intent([[0, 0], [0, 0], [1, 0], [1, 0], [1, 9], [1, 9]]), p = projected(i);
 assert.deepEqual(p.segmentLengthsPixels, [0, 1, 0, 9, 0]);
 assert.deepEqual(evaluateGeographicLineReveal(p, 1).path, i.line.geometry.coordinates);
 for (const fraction of [.01, .1, .2, .9]) close(pathLength(evaluateGeographicLineReveal(p, fraction).path), fraction * 10);
});
test('no supplied segment is skipped; exact corner cuts terminate at the original vertex', () => {
 const p = projected(intent([[0, 0], [3, 0], [3, 4], [9, 4]]));
 assert.deepEqual(evaluateGeographicLineReveal(p, 3 / 13).path, [[0, 0], [3, 0]]);
 assert.deepEqual(evaluateGeographicLineReveal(p, 7 / 13).path, [[0, 0], [3, 0], [3, 4]]);
 assert.deepEqual(evaluateGeographicLineReveal(p, 9 / 13).path, [[0, 0], [3, 0], [3, 4], [5, 4]]);
});
test('monotone reveal has continuous tip position and the specified visible length', () => {
 const p = projected(intent([[0, 0], [3, 0], [3, 4], [9, 4]]));
 let previous = null;
 for (let step = 1; step <= 1000; step++) {
  const fraction = step / 1000, output = evaluateGeographicLineReveal(p, fraction);
  close(pathLength(output.path), fraction * 13);
  if (previous) assert(Math.hypot(output.path.at(-1)[0] - previous[0], output.path.at(-1)[1] - previous[1]) <= 13 / 1000 + 1e-10);
  previous = output.path.at(-1);
 }
});
test('endpoint interpolation stays on its supplied segment in different orientations', () => {
 for (const coordinates of [[[1, 7], [1, -3]], [[-5, 1], [5, 1]], [[-3, -4], [3, 4]]]) {
  const p = projected(intent(coordinates));
  for (const fraction of [.1, .3, .8]) {
   const output = evaluateGeographicLineReveal(p, fraction), [a, b] = coordinates;
   close(output.path.at(-1)[0], a[0] + (b[0] - a[0]) * fraction);
   close(output.path.at(-1)[1], a[1] + (b[1] - a[1]) * fraction);
  }
 }
});
test('ROI follows only current path plus explicit kernel padding, and output is frozen', () => {
 const p = projected(), output = evaluateGeographicLineReveal(p, .5, {paddingPixels: 2});
 assert.deepEqual(output.roi, [-2, -2, 3, 6]); assert(Object.isFrozen(output.path[0])); assert(Object.isFrozen(output.roi));
 assert.throws(() => { output.path.push([0, 0]); }, TypeError);
});
test('random-access reveal and complete hold are stable with no mutable frame cache', () => {
 const p = projected(), before = structuredClone(p), hold = evaluateGeographicLineReveal(p, 1);
 for (const fraction of [.8, .1, 1, .6, 0]) evaluateGeographicLineReveal(p, fraction);
 assert.deepEqual(evaluateGeographicLineReveal(p, 1), hold); assert.deepEqual(p, before);
});
test('projection receives copied coordinates and nonfinite, collapsed or overflowing results fail', () => {
 const i = intent(), before = structuredClone(i);
 const p = compileGeographicLinePrimitive(i, {project: point => { const result = [...point]; point[0] = 99; return result; }});
 assert.deepEqual(i, before); assert.equal(p.totalLengthPixels, 10);
 for (const project of [() => [0, 0], () => [NaN, 1], () => [0], point => [point[0] ? 1e308 : -1e308, 0]])
  assert.throws(() => compileGeographicLinePrimitive(i, {project}), /EVENT_LINE_/);
 assert.throws(() => compileGeographicLinePrimitive(i), /EXISTING_PROJECTION_REQUIRED/);
});
test('serialized primitive contents, fraction and padding are validated', () => {
 const p = projected(), saved = JSON.parse(JSON.stringify(p)); assert.deepEqual(assertGeographicLinePrimitive(saved), p);
 saved.totalLengthPixels = 999; assert.throws(() => evaluateGeographicLineReveal(saved, .5), /NON_CANONICAL/);
 for (const fraction of [-.01, 1.01, NaN, Infinity]) assert.throws(() => evaluateGeographicLineReveal(p, fraction), /FRACTION_RANGE/);
 for (const paddingPixels of [-1, NaN, Infinity]) assert.throws(() => evaluateGeographicLineReveal(p, .5, {paddingPixels}), /PADDING_REQUIRED/);
});
test('pure Timeline controls connect directly to reveal without fixture frame constants', () => {
 const i = intent(), p = compileEventPlan(i, {fps: 24, profile: {ready_frames: 2, line_reveal_frames: 11,
  line_hold_frames: 3, metric_reveal_frames: 2, information_hold_frames: 4}}), line = projected(i);
 const c = {cameraState: {scale: 'REGIONAL', projection: 'FLAT_GEOGRAPHIC', cameraLocked: true, settle: {locked: true},
  camera: {flatBounds: [-1, -1, 2, 10]}, admission: {status: 'LOCAL_NOT_ADMITTED', effectiveScale: 'REGIONAL', localUsed: false}},
  project: point => [...point], safeArea: [-1, -1, 2, 10]};
 for (let frame = 0; frame < p.totalFrames; frame++) {
  const control = evaluateEventFrame(p, frame, c), output = evaluateGeographicLineReveal(line, control.lineFraction);
  close(output.visibleLengthPixels, control.lineFraction * 10);
  if (control.state === 'LINE_HOLD' || control.state === 'INFORMATION_HOLD') assert.deepEqual(output.path, line.screenCoordinates);
 }
});
