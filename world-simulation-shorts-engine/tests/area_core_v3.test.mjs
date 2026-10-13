import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileAreaIntent, assertAreaIntent, compileAreaPlan, assertAreaPlan, evaluateAreaFrame,
 validateAreaGeometry, compileAreaLinePrimitive} from '../web/map_infographic_v1/area_core_v3.mjs';
import {evaluateGeographicLineReveal} from '../web/map_infographic_v1/event_line_v1.mjs';
import {sampleFlowRoute} from '../web/map_infographic_v1/flow_core_v2.mjs';
import {compileAreaDataProfile, evaluateAreaVisualAdmission} from '../web/map_infographic_v1/area_visual_admission_v3.mjs';

const source = {source_type: 'SYNTHETIC_TEST', source_reference: 'fixture://area-core-v3', verification_status: 'SYNTHETIC_TEST'};
const polygon = (left = -1, bottom = -1, right = 1, top = 1) => ({type: 'Polygon',
 coordinates: [[[left, bottom], [right, bottom], [right, top], [left, top], [left, bottom]]]});
const area = (id, geometry = polygon(), role = 'EVENT_AREA') => ({id, geometry, role, style_role: 'PRIMARY'});
const intent = data => compileAreaIntent({data_mode: 'SYNTHETIC_TEST', source, origin: [0, 0], ...data});
const op = (type, target_id, start_frame, duration_frames, extra = {}) => ({type,
 ...(target_id ? {target_id} : {}), start_frame, duration_frames, ...extra});
const project = point => [540 + point[0] * 120, 960 - point[1] * 120];
const evaluate = (plan, frame) => evaluateAreaFrame(plan, frame, {project});
const evidence = {evidenceKind: 'SYNTHETIC_TEST_ONLY', status: 'VISUAL_PASS', criticalCollisions: 0, severeErrors: []};
const semantic = {sameGeography: true, sameObject: true, relationCorrect: true, geometryMeaningPreserved: true, metricMateriallyTrue: true};
function admit(plan, extra = {}) {
 return evaluateAreaVisualAdmission({areaPlan: plan, project, safeArea: [48, 72, 1032, 1848], protectedGraphics: [],
  currentCameraState: {bounds: [-4.5, -8, 4.5, 8], output: [1080, 1920]}, semanticIntegrity: semantic,
  visualEvidence: evidence, dataProfile: compileAreaDataProfile({areaPlan: plan}), ...extra});
}

test('Synthetic A: reveal/grow/contract/ring/impact/hold are deterministic, bounded and source-preserving', () => {
 const circle = {type: 'Polygon', coordinates: [Array.from({length: 17}, (_, i) =>
  i === 16 ? [1, 0] : [Math.cos(i * Math.PI / 8), Math.sin(i * Math.PI / 8)])]};
 const supplied = {areas: [area('area', circle)], impacts: [area('impact', polygon(.6, -.5, 1.4, .5), 'IMPACT_ZONE')],
  propagations: [{id: 'ring', radius_start_degrees: 0, radius_end_degrees: 2, angular_range_degrees: [0, 360]}]};
 const data = intent(supplied), before = JSON.stringify(data);
 const plan = compileAreaPlan(data, {operations: [op('AREA_REVEAL', 'area', 0, 8), op('AREA_GROW', 'area', 0, 20),
  op('AREA_CONTRACT', 'area', 20, 20), op('PROPAGATION_RING', 'ring', 0, 40), op('IMPACT_ZONE', 'impact', 30, 10),
  op('AREA_HOLD', null, 40, 10)]});
 assert.equal(plan.totalFrames, 50); assert.equal(evaluate(plan, 0).areas[0].alpha, 0);
 assert.equal(evaluate(plan, 19).areas[0].coverage, 1); assert.equal(evaluate(plan, 39).areas[0].coverage, 0);
 let previousRadius = 0;
 for (let frame = 0; frame < plan.totalFrames; frame++) {
  const controls = evaluate(plan, frame), shown = controls.areas[0];
  assert.deepEqual(shown.geometry, circle); assert(shown.alpha >= 0 && shown.alpha <= 1);
  assert(shown.coverage >= 0 && shown.coverage <= 1);
  assert.equal(controls.physicalSimulation, false);
  for (const ring of controls.propagations) {
   assert(ring.radius_degrees >= previousRadius); previousRadius = ring.radius_degrees;
   assert.equal(ring.visualOnly, true); assert.equal(ring.physicalSimulation, false);
   assert.deepEqual(ring.geometry.coordinates[0], ring.geometry.coordinates.at(-1));
   assert.deepEqual(ring.lineReveal, evaluateGeographicLineReveal(ring.linePrimitive, 1));
  }
 }
 assert.equal(evaluate(plan, 39).impacts[0].alpha, 1);
 assert.deepEqual(evaluate(plan, 40).areas, evaluate(plan, 49).areas);
 assert.deepEqual(evaluate(plan, 40).propagations, evaluate(plan, 49).propagations);
 assert.equal(JSON.stringify(data), before);
 assert.equal(admit(plan).decision, 'USE_CURRENT_VIEW'); assert.equal(admit(plan).productionEligible, false);
 const expected = evaluate(plan, 15); for (const frame of [49, 0, 40, 4]) evaluate(plan, frame);
 assert.deepEqual(evaluate(plan, 15), expected); assert.equal(assertAreaPlan(JSON.parse(JSON.stringify(plan))).totalFrames, 50);
});

test('Synthetic B: irregular A/B/C state crossfades preserve every supplied ring and hole without vertex morphing', () => {
 const first = {type: 'Polygon', coordinates: [[[-2, -1], [2, -1], [1.5, 2], [-1, 1.7], [-2, -1]],
  [[-.5, -.2], [-.5, .6], [.5, .6], [.5, -.2], [-.5, -.2]]]};
 const second = {type: 'MultiPolygon', coordinates: [first.coordinates, polygon(2.5, -.5, 3.4, .5).coordinates]};
 const third = polygon(-1.5, -1, 1.8, 2);
 const states = [first, second, third].map((geometry, index) => ({state_id: ['A', 'B', 'C'][index],
  time_label: 'STAGE ' + (index + 1), areas: [area('territory', geometry)]}));
 const data = intent({states}), plan = compileAreaPlan(data, {operations: [op('STATE_TRANSITION', null, 0, 60,
  {state_ids: ['A', 'B', 'C']}), op('AREA_HOLD', null, 60, 12)]});
 for (let frame = 0; frame < 72; frame++) {
  const controls = evaluate(plan, frame);
  assert(controls.areas.length <= 2);
  for (const shown of controls.areas) assert.deepEqual(shown.geometry,
   data.states.find(state => state.state_id === shown.state_id).areas[0].geometry);
 }
 assert.equal(evaluate(plan, 0).stateId, 'A'); assert.equal(evaluate(plan, 59).stateId, 'C');
 assert.equal(evaluate(plan, 59).timeLabel, 'STAGE 3');
 assert(evaluate(plan, 25).areas.some(shown => shown.state_id === 'B' && shown.geometry.coordinates[0].length === 2));
 assert.deepEqual(evaluate(plan, 60).areas, evaluate(plan, 71).areas);
 assert.deepEqual(assertAreaIntent(JSON.parse(JSON.stringify(data))), data);
});

test('Synthetic C: supplied moving fronts, territorial states and Time Step use the same deterministic core', () => {
 const states = [0, 1, 2].map(index => ({state_id: ['A', 'B', 'C'][index], time_label: 'PHASE ' + (index + 1),
  areas: [area('control', polygon(-2, -1, index + .2, 1), 'CONTROLLED_AREA')],
  fronts: [{id: 'front', geometry: {type: 'LineString', coordinates: [[index + .2, -1], [index + .2, 1]]}}]}));
 const data = intent({states}), plan = compileAreaPlan(data, {operations: [op('TIME_STEP', null, 0, 36, {state_ids: ['A', 'B', 'C']}),
  op('FRONT_LINE', 'front', 0, 8), op('AREA_HOLD', null, 36, 12)]});
 const seen = new Set();
 for (let frame = 0; frame < 48; frame++) {
  const controls = evaluate(plan, frame); seen.add(controls.stateId);
  assert.equal(controls.timeLabelVisible, true);
  const state = data.states.find(value => value.state_id === controls.stateId);
  assert.deepEqual(controls.areas[0].geometry, state.areas[0].geometry);
  assert.deepEqual(controls.fronts[0].geometry, state.fronts[0].geometry);
  assert.deepEqual(controls.fronts[0].lineReveal,
   evaluateGeographicLineReveal(controls.fronts[0].linePrimitive, controls.fronts[0].revealFraction));
 }
 assert.deepEqual([...seen], ['A', 'B', 'C']); assert.equal(evaluate(plan, 47).hold, true);
 assert.deepEqual(evaluate(plan, 36).fronts, evaluate(plan, 47).fronts);
});

test('Area Move reuses actual projected arc length and supplied tangent while immutable geometry translates', () => {
 const trajectory = {id: 'trajectory', geometry: {type: 'LineString', coordinates: [[0, 0], [1, .2], [2, .8], [3, 1]]}, direction: 'REVERSE'};
 const data = intent({areas: [area('moving', polygon(-.3, -.2, .3, .2))], trajectories: [trajectory]}),
  plan = compileAreaPlan(data, {operations: [op('AREA_MOVE', 'moving', 0, 40, {trajectory_id: 'trajectory'}), op('AREA_HOLD', null, 40, 10)]});
 const primitive = compileAreaLinePrimitive({...data.trajectories[0], data_mode: data.data_mode}, {project});
 const initial = evaluate(plan, 0).areas[0]; assert.deepEqual(initial.transform.translation, [0, 0]);
 let previous = -1;
 for (let frame = 0; frame < 50; frame++) {
  const item = evaluate(plan, frame).areas[0], expected = sampleFlowRoute(primitive, item.motion.fraction);
  assert(item.motion.fraction >= previous); previous = item.motion.fraction;
  assert.deepEqual(item.motion.projectedPosition, expected.position); assert.equal(item.transform.heading, expected.heading);
  assert.deepEqual(item.sourceGeometry, data.areas[0].geometry);
  assert.deepEqual(item.coverageOrigin, data.areas[0].anchor.map((value, axis) => value + item.transform.translation[axis]));
  assert.equal(item.geometry.coordinates[0].length, item.sourceGeometry.coordinates[0].length);
 }
 assert.deepEqual(evaluate(plan, 39).areas[0].transform.translation, [-3, -1]);
 assert.deepEqual(evaluate(plan, 40).areas, evaluate(plan, 49).areas);
});

test('Directional Wave is an authored angular arc using the same original Line reveal, with no repeated pulse or physical claim', () => {
 const data = intent({propagations: [{id: 'wave', radius_start_degrees: .1, radius_end_degrees: 2,
  angular_range_degrees: [180, 270]}]}), plan = compileAreaPlan(data,
  {operations: [op('PROPAGATION_WAVE', 'wave', 0, 30), op('AREA_HOLD', null, 30, 10)]});
 let previous = -1;
 for (let frame = 0; frame < 40; frame++) {
  const wave = evaluate(plan, frame).propagations[0];
  assert(wave.radius_degrees >= previous); previous = wave.radius_degrees;
  assert.equal(wave.propagationType, 'PROPAGATION_WAVE'); assert.equal(wave.visualOnly, true);
  assert.notDeepEqual(wave.geometry.coordinates[0], wave.geometry.coordinates.at(-1));
  assert(wave.geometry.coordinates.every(point => point[0] <= 1e-10 && point[1] <= 1e-10));
  assert.deepEqual(wave.lineReveal, evaluateGeographicLineReveal(wave.linePrimitive, 1));
 }
 assert.deepEqual(evaluate(plan, 30).propagations, evaluate(plan, 39).propagations);
});

test('Polygon admission checks the full future sweep and uses a typed Area request instead of a Line certificate', () => {
 const data = intent({states: [{state_id: 'A', time_label: 'FIRST', areas: [area('footprint', polygon(-.2, -.2, .2, .2))]},
  {state_id: 'B', time_label: 'SECOND', areas: [area('footprint', polygon(-6, -2, 6, 2))]}]}),
  plan = compileAreaPlan(data, {operations: [op('TIME_STEP', null, 0, 12, {state_ids: ['A', 'B']}), op('AREA_HOLD', null, 12, 6)]});
 const admitted = admit(plan);
 assert.equal(admitted.fullSweepSafe, false); assert.equal(admitted.decision, 'DETAIL_APPROACH_REQUIRED');
 assert.equal(admitted.requestVersion, 'AREA_DETAIL_FRAMING_REQUEST_V3');
 assert.equal(admitted.targetFraming.admissionRequired, true); assert.equal(admitted.productionEligible, false);
 assert.deepEqual(admitted.fullSweepGeographicBounds, [-6, -2, 6, 2]);
 assert.equal(admit(plan, {semanticIntegrity: {...semantic, relationCorrect: false}}).decision, 'AREA_VISUAL_BLOCKED');
 assert.equal(admit(plan, {visualEvidence: {...evidence, criticalCollisions: 1}}).decision, 'AREA_VISUAL_BLOCKED');
 assert(admitted.warnings.some(warning => warning.name === 'GIS_ABSOLUTE_ACCURACY_NOT_SURVEY_CERTIFIED'));
 assert.equal(admitted.surveyAdmissionModified, false);
});

test('Invalid topology, timelines, sources and stale area profiles fail rather than being silently repaired', () => {
 for (const geometry of [{type: 'Polygon', coordinates: [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]},
  {type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
  {type: 'Polygon', coordinates: [...polygon().coordinates, [[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]]},
  {type: 'Polygon', coordinates: [[[179, 0], [-179, 0], [-179, 1], [179, 1], [179, 0]]]}])
  assert.throws(() => validateAreaGeometry(geometry), /AREA_/);
 const data = intent({areas: [area('area')]});
 assert.throws(() => compileAreaIntent({...data, data_mode: 'PRODUCTION'}), /VERIFIED_PRODUCTION_SOURCE/);
 assert.throws(() => compileAreaPlan(data, {operations: [op('AREA_REVEAL', 'area', 0, 10)]}), /FINAL_HOLD/);
 assert.throws(() => compileAreaPlan(data, {operations: [op('AREA_REVEAL', 'missing', 0, 10), op('AREA_HOLD', null, 10, 5)]}), /TARGET_NOT_FOUND/);
 const plan = compileAreaPlan(data, {operations: [op('AREA_REVEAL', 'area', 0, 10), op('AREA_HOLD', null, 10, 5)]});
 assert.throws(() => evaluate(plan, 15), /FRAME_OUT_OF_RANGE/); assert.throws(() => evaluate(plan, .5), /FRAME_INTEGER/);
 const stale = {...compileAreaDataProfile({areaPlan: plan}), geometryBinding: 'stale'};
 assert.throws(() => admit(plan, {dataProfile: stale}), /STALE_DATA_PROFILE/);
 const changed = JSON.parse(JSON.stringify(plan)); changed.operations[0].duration_frames++;
 assert.throws(() => assertAreaPlan(changed), /FINAL_HOLD|TOTAL_FRAMES|NON_CANONICAL/);
});

test('Production admission requires fresh native proof binding and never derives physical numbers', () => {
 const publicSource = {source_type: 'PUBLIC_GEOGRAPHIC_DATA', source_reference: 'fixture://verified-source', verification_status: 'VERIFIED'};
 const data = compileAreaIntent({data_mode: 'PRODUCTION', source: publicSource, origin: [0, 0], areas: [area('area')]}),
  plan = compileAreaPlan(data, {operations: [op('AREA_REVEAL', 'area', 0, 10), op('AREA_HOLD', null, 10, 5)]});
 const render = {verified: true, sha256: 'a'.repeat(64), byteLength: 1, width: 1080, height: 1920,
  bounds: [-4.5, -8, 4.5, 8], geometryBinding: plan.geometryBinding};
 const audit = admit(plan, {visualEvidence: {...evidence, evidenceKind: 'ACTUAL_NATIVE_RENDER', render}});
 assert.equal(audit.productionEligible, true); assert.equal(audit.physicalSimulation, false);
 assert.equal(admit(plan).productionEligible, false);
 assert.equal(admit(plan, {visualEvidence: {...evidence, evidenceKind: 'ACTUAL_NATIVE_RENDER', render: {...render, geometryBinding: 'stale'}}}).decision,
  'AREA_VISUAL_BLOCKED');
 for (const name of ['area_core_v3.mjs', 'area_visual_admission_v3.mjs']) {
  const text = readFileSync(new URL('../web/map_infographic_v1/' + name, import.meta.url), 'utf8');
  assert(!/suez|egypt|tsunami|war\b|193\.30/iu.test(text));
 }
});
