import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileTerritoryControlIntent, compileTerritoryControlPlan, assertTerritoryControlPlan,
 evaluateTerritoryControlFrame, sampleControlBoundary, classifyControlPoint}
 from '../web/map_infographic_v1/territory_control_adapter_v1.mjs';

const box = (left, bottom, right, top) => [[left, bottom], [right, bottom], [right, top], [left, top], [left, bottom]];
const input = () => ({semantic_mode: 'REFERENCE_VISUAL_STUDY', source: {source_type: 'SYNTHETIC_TEST',
 source_reference: 'fixture://complementary-control', verification_status: 'SYNTHETIC_TEST'},
 domain: [{id: 'main', geometry: {type: 'Polygon', coordinates: [box(-2, -2, 2, 3), box(.3, .4, .8, 1)]}},
  {id: 'island', geometry: {type: 'MultiPolygon', coordinates: [[box(2.1, -1.4, 2.4, -.9)], [box(-2.7, 1.4, -2.4, 1.7)]]}}],
 factions: {winner: {id: 'SIDE_A'}, loser: {id: 'SIDE_B'}}, longitudinal_knots: [-3, -1, 1, 3],
 base_boundary_latitudes: [-1, -1, -1, -1], boundary_keyframes: [{frame: 0, latitudes: [0, .1, -.1, 0]},
  {frame: 49, latitudes: [.7, .9, .1, .4]}, {frame: 149, latitudes: [2.2, 2, .7, 1.3]}],
 advance_direction: 'POSITIVE_LATITUDE', start_frame: 0, total_frames: 150, fps: 30, interpolation: 'LINEAR'});

test('Every land point has exactly one owner in all 150 frames, and ownership gained never reverses', () => {
 const plan = compileTerritoryControlPlan(input()), previous = new Map();
 let landSamples = 0;
 for (let frame = 0; frame < 150; frame++) {
  const controls = evaluateTerritoryControlFrame(plan, frame);
  for (let xi = -27; xi <= 24; xi += 2) for (let yi = -20; yi <= 30; yi += 2) {
   const point = [xi / 10, yi / 10], result = classifyControlPoint(controls, point), key = point.join(',');
   if (result.inDomain) {
    landSamples++;
    assert.equal(Number(result.winner) + Number(result.loser), 1);
    assert.equal(result.owner, result.winner ? 'SIDE_A' : 'SIDE_B');
    if (previous.get(key)) assert.equal(result.winner, true, 'already-gained land cannot revert');
    previous.set(key, result.winner);
   } else assert.equal(result.owner, null);
  }
 }
 assert(landSamples > 70000);
});

test('Moving interface changes continuously, keeps irregular longitudinal shape, and matches exact keyframes', () => {
 const supplied = input(), plan = compileTerritoryControlPlan(supplied);
 for (const keyframe of supplied.boundary_keyframes)
  assert.deepEqual(evaluateTerritoryControlFrame(plan, keyframe.frame).boundaryLatitudes, keyframe.latitudes);
 let maximumStep = 0;
 for (let frame = 1; frame < 150; frame++) {
  const previous = evaluateTerritoryControlFrame(plan, frame - 1), current = evaluateTerritoryControlFrame(plan, frame);
  for (const longitude of [-2.6, -1.1, -.5, .7, 1.2, 2.2]) {
   const step = sampleControlBoundary(current, longitude) - sampleControlBoundary(previous, longitude);
   assert(step >= -1e-14); maximumStep = Math.max(maximumStep, step);
  }
 }
 assert(maximumStep < .017);
 assert(sampleControlBoundary(plan, -2, {frame: 149}) > sampleControlBoundary(plan, 2, {frame: 149}));
 assert.equal(sampleControlBoundary(plan, 0, {kind: 'base', frame: 70}), -1);
});

test('Existing winner material, newly gained material, losing material, holes and islands remain distinct', () => {
 const controls = evaluateTerritoryControlFrame(compileTerritoryControlPlan(input()), 149);
 assert.equal(classifyControlPoint(controls, [0, -1.4]).region, 'WINNER_EXISTING');
 assert.equal(classifyControlPoint(controls, [0, .2]).region, 'WINNER_GAINED');
 assert.equal(classifyControlPoint(controls, [0, 2.8]).region, 'LOSER');
 assert.equal(classifyControlPoint(controls, [.5, .7]).region, 'OUTSIDE_DOMAIN');
 assert.equal(classifyControlPoint(controls, [2.2, -1.1]).region, 'WINNER_EXISTING');
 assert.equal(classifyControlPoint(controls, [-2.5, 1.5]).region, 'WINNER_GAINED');
 const exactBoundary = sampleControlBoundary(controls, 0);
 assert.equal(classifyControlPoint(controls, [0, exactBoundary]).winner, true, 'single tie owner');
});

test('Direction is data-driven and supports an analogous decreasing-latitude advance', () => {
 const supplied = input(); supplied.advance_direction = 'NEGATIVE_LATITUDE';
 supplied.base_boundary_latitudes = [1, 1, 1, 1];
 supplied.boundary_keyframes = supplied.boundary_keyframes.map(key => ({frame: key.frame, latitudes: key.latitudes.map(v => -v)}));
 const plan = compileTerritoryControlPlan(supplied), first = evaluateTerritoryControlFrame(plan, 0), last = evaluateTerritoryControlFrame(plan, 149);
 assert.equal(first.advanceSign, -1);
 assert.equal(classifyControlPoint(first, [0, -.8]).region, 'LOSER');
 assert.equal(classifyControlPoint(last, [0, -.8]).region, 'WINNER_GAINED');
 assert.equal(classifyControlPoint(last, [0, 1.8]).region, 'WINNER_EXISTING');
});

test('Source geometry and input keyframes remain unchanged under out-of-order evaluation and JSON restore', () => {
 const supplied = input(), before = JSON.stringify(supplied), intent = compileTerritoryControlIntent(supplied);
 const plan = compileTerritoryControlPlan(intent), expected = evaluateTerritoryControlFrame(plan, 83);
 for (const frame of [149, 0, 49, 84, 12, 148]) evaluateTerritoryControlFrame(plan, frame);
 assert.deepEqual(evaluateTerritoryControlFrame(plan, 83), expected);
 assert.equal(JSON.stringify(supplied), before);
 assert.equal(JSON.stringify(plan.intent.domain), JSON.stringify(supplied.domain));
 assert.deepEqual(evaluateTerritoryControlFrame(assertTerritoryControlPlan(JSON.parse(JSON.stringify(plan))), 83), expected);
 assert(Object.isFrozen(plan.intent.domain[0].geometry.coordinates[0][0]));
 assert.throws(() => { plan.intent.domain[0].geometry.coordinates[0][0][0] = 100; }, TypeError);
 assert.equal(expected.geometryUnchanged, true);
 assert.equal(expected.physicalSimulation, false);
 assert.equal(expected.routeVisuals, false);
 assert.equal(expected.standaloneFrontLine, false);
});

test('Frame bounds, canonical source binding, profile coverage, capacities and reversal fail safely', () => {
 const plan = compileTerritoryControlPlan(input());
 for (const frame of [-1, .5, 150]) assert.throws(() => evaluateTerritoryControlFrame(plan, frame), /CONTROL_FRAME_/);
 assert.throws(() => classifyControlPoint(plan, [0, 0]), /CLASSIFICATION_FRAME_REQUIRED/);
 const changed = JSON.parse(JSON.stringify(plan)); changed.intent.domain[0].geometry.coordinates[0][0][0] -= .1;
 changed.intent.domain[0].geometry.coordinates[0].at(-1)[0] -= .1;
 assert.throws(() => assertTerritoryControlPlan(changed), /PLAN_NON_CANONICAL/);
 for (const mutate of [
  data => { data.boundary_keyframes[1].latitudes[1] = -.5; },
  data => { data.boundary_keyframes[1].frame = 0; },
  data => { data.boundary_keyframes.at(-1).frame = 150; },
  data => { data.longitudinal_knots[0] = -2; },
  data => { data.longitudinal_knots = Array.from({length: 65}, (_, i) => i / 10); },
  data => { data.factions.loser.id = data.factions.winner.id; }
 ]) { const invalid = input(); mutate(invalid); assert.throws(() => compileTerritoryControlPlan(invalid), /CONTROL_/); }
});

test('Optional smooth interpolation reuses the frozen detail easing while absolute-frame schedule stays deterministic', () => {
 const supplied = input(); supplied.interpolation = 'SMOOTHERSTEP'; supplied.start_frame = 20;
 const plan = compileTerritoryControlPlan(supplied), first = evaluateTerritoryControlFrame(plan, 20), last = evaluateTerritoryControlFrame(plan, 169);
 assert.deepEqual(first.boundaryLatitudes, supplied.boundary_keyframes[0].latitudes);
 assert.deepEqual(last.boundaryLatitudes, supplied.boundary_keyframes.at(-1).latitudes);
 assert.equal(first.timeSeconds, 0); assert.equal(last.timeSeconds, 149 / 30);
 for (let frame = 21; frame <= 169; frame++) {
  const previous = evaluateTerritoryControlFrame(plan, frame - 1), current = evaluateTerritoryControlFrame(plan, frame);
  assert(current.boundaryLatitudes.every((latitude, index) => latitude >= previous.boundaryLatitudes[index] - 1e-14));
 }
 assert.throws(() => evaluateTerritoryControlFrame(plan, 19), /FRAME_OUT_OF_RANGE/);
});

test('Extension source has no subject names, fixture coordinates, inherited route engine or physical implementation', () => {
 const source = readFileSync(new URL('../web/map_infographic_v1/territory_control_adapter_v1.mjs', import.meta.url), 'utf8');
 assert(!/korea|suez|egypt|pyongyang|seoul|1950|193\.30|compileFlow|sampleFlow|frontLine/iu.test(source.replaceAll('standaloneFrontLine', '')));
 assert(!/createShader|createProgram|canvas|WebGL|three\.js/u.test(source));
});
