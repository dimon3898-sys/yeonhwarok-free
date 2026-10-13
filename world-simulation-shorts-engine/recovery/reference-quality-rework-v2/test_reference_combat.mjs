import test from 'node:test';
import assert from 'node:assert/strict';
import {validateReferenceCombatUnits, evaluateReferenceCombatLayout}
 from '../../web/map_infographic_v1/reference_combat_overlay_v2.mjs';

const profile = {role: {flag_shapes: [{type: 'rect', x: -.5, y: -.5, width: 1, height: 1, fill: '#abcdef'}]}};
const make = (id, x) => ({id, profile_id: 'role',
 anchor_frames: Array.from({length: 150}, (_, frame) => [x + frame / 149, 30 + frame / 149]),
 size_frames: Array.from({length: 150}, () => 112), rotation_frames: Array.from({length: 150}, () => 11)});
const project = ([longitude, latitude]) => [longitude * 10, 1900 - latitude * 20];
const safeArea = [48, 72, 1032, 1848];

test('render coordinates bind supplied geographic frame anchors through camera-owned projection', () => {
 const units = [make('generic_01', 30), make('generic_02', 50)];
 const before = JSON.stringify(units);
 assert.deepEqual(validateReferenceCombatUnits(units, profile), {units: 2, frames: 150, motionEngine: 'NONE_SUPPLIED_FRAME_ANCHORS'});
 for (const frame of [149, 0, 74, 15, 149]) {
  const actual = evaluateReferenceCombatLayout(units, frame, {project, safeArea});
  assert.deepEqual(actual.units[0].position, project(units[0].anchor_frames[frame]));
  assert.equal(actual.criticalCollisions.length, 0);
  assert.equal(actual.safeAreaViolations.length, 0);
  assert.equal(actual.noRoutesArrowsOrText, true);
  assert.equal(actual.speculativeImpactCues, 0);
 }
 assert.equal(JSON.stringify(units), before);
});

test('protected graphic collision and safe area are reported without moving existing graphics', () => {
 const units = [make('generic_01', 30)];
 const protectedGraphics = [{id: 'existing_label', bounds: [290, 1290, 310, 1310]}];
 const before = JSON.stringify(protectedGraphics);
 const actual = evaluateReferenceCombatLayout(units, 0, {project, safeArea, protectedGraphics});
 assert.deepEqual(actual.criticalCollisions, [{unit: 'generic_01', protected: 'existing_label'}]);
 assert.equal(JSON.stringify(protectedGraphics), before);
 const outside = evaluateReferenceCombatLayout(units, 0, {project: () => [50, 100], safeArea});
 assert.deepEqual(outside.safeAreaViolations, ['generic_01']);
});

test('malformed frame bindings fail instead of creating fallback random symbols', () => {
 assert.throws(() => validateReferenceCombatUnits([{...make('generic', 30), anchor_frames: [[181, 30], [30, 30]]}], profile),
  /GEOGRAPHIC_FRAME_ANCHORS_REQUIRED/);
 assert.throws(() => validateReferenceCombatUnits([{...make('generic', 30), size_frames: [112]}], profile),
  /MEASURED_SCREEN_SIZES_REQUIRED/);
 assert.throws(() => evaluateReferenceCombatLayout([make('generic', 30)], 150, {project, safeArea}), /FRAME_OUT_OF_RANGE/);
});

test('empty octagonal texture corners do not create false unit collisions', () => {
 const units = [make('generic_01', 30), make('generic_02', 42)];
 units[1].anchor_frames = Array.from({length: 150}, () => [42, 42]);
 for (const unit of units) unit.size_frames.fill(130);
 const actual = evaluateReferenceCombatLayout(units, 0, {
  project: point => point.map(value => value*10), safeArea: [0, 0, 1080, 1920]});
 const [a, b] = actual.units.map(unit => unit.bounds);
 assert.ok(a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1]);
 assert.deepEqual(actual.unitOverlaps, []);
});
