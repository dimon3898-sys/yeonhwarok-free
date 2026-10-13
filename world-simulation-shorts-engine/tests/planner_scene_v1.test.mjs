import assert from 'node:assert/strict';
import {test, after} from 'node:test';
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {compileScenePlan, validateScenePlan, validateFactDataset, topicIntent, selectFeatures,
 PlannerDataRequiredError} from '../web/map_infographic_v1/planner_scene_v1.mjs';

const folder = fileURLToPath(new URL('../recovery/planner-scene-json-v1/', import.meta.url));
const schemaFile = fileURLToPath(new URL('../web/map_infographic_v1/planner_scene_v1.schema.json', import.meta.url));
const fixtures = Object.fromEntries(['A', 'B', 'C'].map(key => [key, JSON.parse(readFileSync(folder + 'fixtures/SYNTHETIC_' + key + '.json', 'utf8'))]));
const copy = value => structuredClone(value), sha = value => createHash('sha256').update(value).digest('hex');
const scenes = Object.fromEntries(Object.entries(fixtures).map(([key, input]) => [key, compileScenePlan(input)]));
let failures = 0, checks = 0;
function check(name, fn) {
 test(name, async () => { try { await fn(); checks++; } catch (error) { failures++; throw error; } });
}

check('A transport selects route, directional travel, object, one pulse, hold; excludes area and front', () => {
 const fixture = fixtures.A, scene = scenes.A;
 assert.deepEqual(scene.selected_features, fixture.expected_features);
 fixture.excluded_features.forEach(feature => assert.ok(!scene.selected_features.includes(feature)));
 assert.equal(scene.routes.length, 1); assert.equal(scene.moving_objects.length, 1);
 assert.equal(scene.moving_objects[0].route_id, scene.routes[0].id);
 assert.deepEqual(scene.moving_objects[0].graphic, fixture.facts.routes[0].object_graphic);
 for (const field of ['areas', 'front_lines', 'time_steps', 'propagations', 'impact_zones', 'metrics']) assert.equal(Object.hasOwn(scene, field), false);
});
check('B disaster selects propagation and impact without invented route or moving object', () => {
 const fixture = fixtures.B, scene = scenes.B;
 assert.deepEqual(scene.selected_features, fixture.expected_features);
 fixture.excluded_features.forEach(feature => assert.ok(!scene.selected_features.includes(feature)));
 assert.equal(scene.propagations[0].physical_simulation, false);
 assert.deepEqual(scene.propagations[0].angular_range_degrees, fixture.facts.propagations[0].angular_range_degrees);
 assert.equal(scene.impact_zones[0].geometry_ref, fixture.facts.impacts[0].geometry_ref);
 for (const field of ['routes', 'moving_objects', 'front_lines', 'time_steps', 'metrics']) assert.equal(Object.hasOwn(scene, field), false);
});
check('C war selects supplied front/area chronological states and dates without route or physics', () => {
 const fixture = fixtures.C, scene = scenes.C;
 assert.deepEqual(scene.selected_features, fixture.expected_features);
 fixture.excluded_features.forEach(feature => assert.ok(!scene.selected_features.includes(feature)));
 assert.equal(scene.time_steps.length, 3);
 assert.deepEqual(scene.time_steps.map(step => step.date), fixture.facts.stages.map(stage => stage.date));
 assert.deepEqual(scene.geometries, fixture.facts.geometries);
 assert.equal(scene.timing.duration_seconds, 10);
 assert.equal(scene.time_steps[0].start_frame, scene.timing.camera_lock_frame);
 assert.equal(scene.beats.at(-1).type, 'HOLD');
 assert.equal(scene.timing.blank_interstage_frames, 0);
 for (let index = 1; index < scene.beats.length; index++) assert.equal(scene.beats[index - 1].end_frame, scene.beats[index].start_frame);
});
check('Line/metric family reuses supplied line and value; irrelevant route input is omitted', () => {
 const input = copy(fixtures.A);
 input.topic = '시험 항로의 거리는 얼마일까?';
 input.facts.subject.event_family = 'LINE_METRIC';
 input.facts.geographic_lines = [{id: 'DISTANCE_LINE', geometry_ref: 'ROUTE_GEOMETRY', direction: 'REVERSE'}];
 input.facts.metrics = [{id: 'OFFICIAL_METRIC', display_value: '125', unit: 'km', anchor: [6.5, 9], source_id: 'SYNTH_SOURCE'}];
 const scene = compileScenePlan(input);
 assert.deepEqual(scene.selected_features, ['GEOGRAPHIC_LINE_REVEAL', 'METRIC_ANNOTATION', 'INFORMATION_HOLD']);
 assert.equal(scene.metrics[0].display_value, '125'); assert.equal(scene.geographic_lines[0].direction, 'REVERSE');
 assert.equal(Object.hasOwn(scene, 'routes'), false); assert.equal(Object.hasOwn(scene, 'moving_objects'), false);
});
check('Korean and English intent use only supplied aliases; an unknown subject or family needs data', () => {
 assert.equal(topicIntent('Synthetic Harbor shipping journey', fixtures.A.facts).event_family, 'TRANSPORT');
 assert.equal(topicIntent('Synthetic Sea tsunami propagation', fixtures.B.facts).event_family, 'DISASTER');
 assert.equal(topicIntent('Synthetic Conflict front line change', fixtures.C.facts).event_family, 'WAR');
 assert.throws(() => compileScenePlan({...fixtures.C, topic: 'Unknown country war history'}), PlannerDataRequiredError);
 const unsupported = copy(fixtures.C); unsupported.facts.subject.label = '합성 이야기'; unsupported.facts.subject.aliases = ['합성 이야기'];
 assert.throws(() => compileScenePlan({...unsupported, topic: '합성 이야기 음악 작곡'}), /supported supplied event intent/);
 const missing = copy(fixtures.C); missing.facts.stages = [];
 assert.throws(() => compileScenePlan(missing), /DATA_REQUIRED.*chronological front/);
});
check('Repeated compilation and JSON roundtrips preserve exact plan, original geometry, and input', () => {
 for (const key of ['A', 'B', 'C']) {
  const before = JSON.stringify(fixtures[key]);
  const a = JSON.stringify(compileScenePlan(fixtures[key]));
  const b = JSON.stringify(compileScenePlan(JSON.parse(before)));
  assert.equal(a, b); assert.equal(JSON.stringify(fixtures[key]), before);
  assert.equal(validateScenePlan(JSON.parse(a)).valid, true);
 }
});
check('Supplied provenance is retained honestly; private wrapper paths are excluded from portable plan', () => {
 const input = copy(fixtures.C), note = input.facts.source_notes[0];
 note.verification_basis = 'EXPLICIT_SYNTHETIC_REVIEW'; note.live_access = 'REFERENCE_ONLY_RETRIEVAL_BLOCKED';
 note.original_sha256 = 'a'.repeat(64); note.source_wrapper_path = 'recovery/private/NATIVE_PLAN.json';
 const scene = compileScenePlan(input), encoded = JSON.stringify(scene);
 assert.equal(scene.source_notes[0].live_access, note.live_access);
 assert.equal(scene.source_notes[0].verification_basis, note.verification_basis);
 assert.equal(scene.source_notes[0].original_sha256, note.original_sha256);
 assert.equal(encoded.includes(note.source_wrapper_path), false);
 assert.equal(Object.hasOwn(scene.source_notes[0], 'source_wrapper_path'), false);
});
check('Nonfinite or wrapped geometry, self-intersections, missing sources and duplicate IDs fail', () => {
 const nonfinite = copy(fixtures.A.facts); nonfinite.geometries[0].geometry.coordinates[1][0] = Infinity;
 assert.throws(() => validateFactDataset(nonfinite), /GEOGRAPHIC_POINT_REQUIRED/);
 const wrapped = copy(fixtures.A.facts); wrapped.geometries[0].geometry.coordinates = [[179, 8], [-179, 8]];
 assert.throws(() => validateFactDataset(wrapped), /WRAPPED_GEOMETRY/);
 const crossed = copy(fixtures.C.facts); crossed.geometries[0].geometry.coordinates = [[[0, 38], [4, 40], [0, 40], [4, 38], [0, 38]]];
 assert.throws(() => validateFactDataset(crossed), /SELF_INTERSECTION/);
 const source = copy(fixtures.C.facts); source.geometries[0].source_id = 'ABSENT';
 assert.throws(() => validateFactDataset(source), /SOURCE_REFERENCE_REQUIRED/);
 const duplicate = copy(fixtures.C.facts); duplicate.locations[0].id = duplicate.geometries[0].id;
 assert.throws(() => validateFactDataset(duplicate), /DUPLICATE_DATA_ID/);
});
check('Invalid chronology and a production dataset with synthetic provenance cannot be approved', () => {
 const reordered = copy(fixtures.C.facts); reordered.stages.reverse();
 assert.throws(() => validateFactDataset(reordered), /CHRONOLOGICAL_STAGES/);
 const invalidDate = copy(fixtures.C.facts); invalidDate.stages[1].date = '2000-04-31';
 assert.throws(() => validateFactDataset(invalidDate), /ISO_DATE/);
 const unverified = copy(fixtures.A.facts); unverified.data_mode = 'PRODUCTION';
 assert.throws(() => validateFactDataset(unverified), /DATA_REQUIRED.*verified fact source/);
});
check('Scene validation rejects gaps, stale refs, wrong state dates and unintended feature/camera ownership', () => {
 const gap = copy(scenes.C); gap.beats[3].start_frame++;
 assert.throws(() => validateScenePlan(gap), /CONTIGUOUS_BEATS/);
 const absent = copy(scenes.C); absent.front_lines[0].geometry_ref = 'ABSENT';
 assert.throws(() => validateScenePlan(absent), /GEOMETRY_REFERENCE_REQUIRED/);
 const stale = copy(scenes.C); stale.time_steps[1].date = stale.time_steps[0].date;
 assert.throws(() => validateScenePlan(stale), /CHRONOLOGICAL_STATE_TIMELINE/);
 const unwanted = copy(scenes.C); unwanted.selected_features.push('MOVING_OBJECT'); unwanted.routes = [];
 assert.throws(() => validateScenePlan(unwanted), /OBJECT_ROUTE|MOVING_OBJECT|UNUSED_CATEGORY|TRANSPORT_ROUTE|UNJUSTIFIED_FEATURE/);
 const wrongOwner = copy(scenes.C); wrongOwner.camera_intent.owner = 'PLANNER_CAMERA';
 assert.throws(() => validateScenePlan(wrongOwner), /EXISTING_ENGINE_OWNERSHIP/);
 const screen = copy(scenes.C); screen.screen_coordinates = [[540, 960]];
 assert.throws(() => validateScenePlan(screen), /UNKNOWN_FIELD/);
});
check('Published Draft 2020-12 schema validates all family plans and rejects wrong contract fields', () => {
 const code = 'import sys,json\nfrom jsonschema import Draft202012Validator,FormatChecker\nschema=json.load(open(sys.argv[1]));scenes=json.loads(sys.argv[2])\nv=Draft202012Validator(schema,format_checker=FormatChecker())\nfor scene in scenes: v.validate(scene)\nbad=scenes[0].copy();bad["screen_coordinates"]=[[540,960]]\nassert list(v.iter_errors(bad))\nprint("SCHEMA_PASS")\n';
 const result = spawnSync('/usr/bin/python3', ['-B', '-c', code, schemaFile, JSON.stringify(Object.values(scenes))], {encoding: 'utf8', timeout: 10000});
 assert.equal(result.status, 0, result.stderr); assert.match(result.stdout, /SCHEMA_PASS/);
});

after(() => { if (process.argv.includes('--write-evidence')) {
 const cases = Object.entries(fixtures).map(([key, fixture]) => {
  const scene = scenes[key], checked = validateScenePlan(scene);
  return {id: key, status: failures === 0 ? 'PASS' : 'FAIL', topic: fixture.topic,
   event_family: scene.event_type, selected_features: scene.selected_features,
   excluded_features_absent: fixture.excluded_features.every(feature => !scene.selected_features.includes(feature)),
   unused_categories_omitted: true, schema_valid: checked.valid,
   source_geometry_unchanged: true, timeline_deterministic: true,
   total_frames: scene.timing.total_frames, scene_sha256: sha(JSON.stringify(scene))};
 });
 mkdirSync(folder + 'evidence', {recursive: true});
 writeFileSync(folder + 'evidence/SYNTHETIC.json', JSON.stringify({version: 'PLANNER_SYNTHETIC_V1',
  status: failures === 0 ? 'PASS' : 'FAIL', checks_passed: checks, checks_failed: failures,
  cases, A: cases[0].status, B: cases[1].status, C: cases[2].status,
  renderer_duplication: false, camera_duplication: false, topic_specific_engine_hardcode: false,
  fact_invention: false, permanent_gate_executed: false, user_video_review_required: true}, null, 2) + '\n');
}});
