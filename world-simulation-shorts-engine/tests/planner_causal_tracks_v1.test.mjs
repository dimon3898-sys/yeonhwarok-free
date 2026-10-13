import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {compileScenePlan, validateFactDataset, validateScenePlan} from '../web/map_infographic_v1/planner_scene_v1.mjs';

const root = new URL('../recovery/planner-scene-json-v1/', import.meta.url);
const load = name => JSON.parse(readFileSync(new URL(name, root), 'utf8'));
const copy = value => structuredClone(value);
const legacyHashes = {A: '9126919936cd0583a172dfd6e1ecc67907ef012d172c3f935c69f82e199bd9a0',
 B: 'e3214427b5f2d8209a60426ca6412aff86e404e8d899d2cad55d06d7c6059434',
 C: 'e2d37611db33cfdb2851196394bba3e900fc9e4b1120bde8bc8f51110e0a0c31'};

function causalInput({reverse = false} = {}) {
 const input = copy(load('fixtures/SYNTHETIC_C.json')), facts = input.facts;
 for (const [id, date, source] of [['STATE_4', '2000-06-01', facts.stages[0]], ['STATE_5', '2000-07-01', facts.stages[2]]])
  facts.stages.push({...copy(source), id, date, label: date});
 facts.time_range.end = facts.stages.at(-1).date;
 const endpoints = [[2, 40.1], [2, 39.7]], coordinates = reverse ? [...endpoints].reverse() : endpoints;
 facts.geometries.push({id: 'ACTION_GEOMETRY', source_id: 'SYNTH_SOURCE', geometry: {type: 'LineString', coordinates}});
 facts.routes = [{id: 'ACTION_ROUTE', geometry_ref: 'ACTION_GEOMETRY', direction: reverse ? 'REVERSE' : 'FORWARD',
  object_role: 'SCHEMATIC_ACTOR', object_profile: 'GENERIC', required_for_story: true,
  object_graphic: {width_px: 36, height_px: 24, polygons: [{points: [[-.5, -.5], [.5, 0], [-.5, .5]], color: [.1, .8, .9, 1]}]}}];
 facts.scene_timing = {fps: 30, total_frames: 420, duration_seconds: 14, camera_lock_frame: 0, event_start_frame: 0,
  initial_reveal_frames: 36, state_transition_frames: 87, final_hold_frames: 36, action_frames: 384,
  frame_policy: 'INTEGER_DETERMINISTIC', blank_interstage_frames: 0};
 facts.causal_tracks = [{id: 'ACTION_TRACK', source_id: 'SYNTH_SOURCE', action_kind: 'WITHDRAW',
  from_state_id: 'STATE_1', to_state_id: 'STATE_2', motion_start_frame: 1, contact_frame: 36,
  control_start_frame: 38, control_end_frame: 120, end_frame: 123, contact_kind: 'SCHEMATIC_FRONT_CONTACT',
  semantic_mode: 'SCHEMATIC_STATE_TRANSITION', represents_historical_unit: false, route_id: 'ACTION_ROUTE',
  object_id: 'OBJECT_ACTION_ROUTE', target_front_line_id: 'FRONT_STATE_2_0', contact_anchor: endpoints[1]},
 {id: 'SETTLEMENT_TRACK', source_id: 'SYNTH_SOURCE', action_kind: 'SETTLEMENT',
  from_state_id: 'STATE_4', to_state_id: 'STATE_5', motion_start_frame: 297, contact_frame: 330,
  control_start_frame: 330, control_end_frame: 384, end_frame: 384, contact_kind: 'NONE',
  semantic_mode: 'SCHEMATIC_STATE_TRANSITION', represents_historical_unit: false}];
 return input;
}

test('optional additions preserve exact legacy family output and stored production Scene JSON', () => {
 for (const [name, expected] of Object.entries(legacyHashes)) {
  const scene = compileScenePlan(load('fixtures/SYNTHETIC_' + name + '.json'));
  assert.equal(createHash('sha256').update(JSON.stringify(scene)).digest('hex'), expected);
  assert.equal(Object.hasOwn(scene, 'causal_tracks'), false);
  assert.equal(scene.beats[0].duration_frames, scene.timing.fps);
  assert.equal(scene.beats[1].end_frame, scene.timing.camera_lock_frame);
 }
 const stored = load('fixtures/SCENE_PLAN.json'), facts = load('data/FACT_DATA.json');
 assert.equal(JSON.stringify(compileScenePlan({topic: stored.metadata.topic, facts})), JSON.stringify(stored));
});

test('supplied zero-lock timing preserves five states, immediate action and exact 420-frame coverage', () => {
 const scene = compileScenePlan(causalInput());
 assert.deepEqual(scene.time_steps.map(row => row.start_frame), [0, 36, 123, 210, 297]);
 assert.deepEqual(scene.beats.map(row => row.type), ['EVENT_ACTION', 'STATE_CHANGE', 'STATE_CHANGE', 'STATE_CHANGE', 'STATE_CHANGE', 'HOLD']);
 assert.equal(scene.beats[0].start_frame, 0);
 assert.equal(scene.beats.at(-1).start_frame, 384);
 assert.equal(scene.beats.at(-1).end_frame, 420);
 assert.equal(scene.timing.action_frames, 384);
 assert.equal(scene.selected_features.includes('MOVING_OBJECT'), true);
 assert.equal(scene.selected_features.includes('IMPACT_ZONE'), false);
 assert.equal(validateScenePlan(scene).valid, true);
});

test('causal facts canonicalize and freeze without mutation; JSON roundtrip remains deterministic', () => {
 const input = causalInput(), before = JSON.stringify(input), facts = validateFactDataset(input.facts);
 assert.equal(JSON.stringify(input), before);
 assert.equal(Object.isFrozen(facts.causal_tracks[0].contact_anchor), true);
 const scene = compileScenePlan(input), second = compileScenePlan(JSON.parse(before));
 assert.equal(JSON.stringify(scene), JSON.stringify(second));
 assert.deepEqual(scene.causal_tracks, facts.causal_tracks);
 assert.equal(Object.hasOwn(scene, 'scene_timing'), false);
 assert.equal(validateScenePlan(JSON.parse(JSON.stringify(scene))).valid, true);
});

test('directed endpoint and supplied front bind for reversed routes and omitted optional front declaration', () => {
 const reversed = compileScenePlan(causalInput({reverse: true}));
 assert.deepEqual(reversed.causal_tracks[0].contact_anchor, [2, 39.7]);
 const input = causalInput(); delete input.facts.causal_tracks[0].target_front_line_id; delete input.facts.causal_tracks[0].contact_anchor;
 assert.equal(validateScenePlan(compileScenePlan(input)).valid, true);
});

test('track references reject missing sources, nonadjacent states, mismatched actors and unsupported front contacts', () => {
 const mutations = [
  [track => {track.source_id = 'ABSENT';}, /CAUSAL_SOURCE_REFERENCE/],
  [track => {track.to_state_id = 'STATE_3';}, /CAUSAL_ADJACENT_STATES/],
  [track => {track.object_id = 'ABSENT';}, /CAUSAL_ROUTE_OBJECT_REFERENCE/],
  [track => {delete track.object_id;}, /CAUSAL_ACTOR_BINDING/],
  [track => {track.contact_anchor = [2, 39.6];}, /CAUSAL_SUPPLIED_FRONT_CONTACT/],
  [track => {track.target_front_line_id = 'FRONT_STATE_3_0';}, /CAUSAL_SUPPLIED_FRONT_CONTACT/],
  [track => {track.represents_historical_unit = true;}, /CAUSAL_SCHEMATIC_SEMANTICS/],
  [track => {track.unknown = true;}, /CAUSAL_TRACK_UNKNOWN_FIELD/]
 ];
 for (const [mutate, expected] of mutations) {
  const input = causalInput(); mutate(input.facts.causal_tracks[0]);
  assert.throws(() => compileScenePlan(input), expected);
 }
 const input = causalInput(); input.facts.routes[0].required_for_story = false;
 assert.throws(() => compileScenePlan(input), /CAUSAL_ROUTE_OBJECT_REFERENCE/);
});

test('contact without declared front still cannot fabricate a point away from supplied target fronts', () => {
 const input = causalInput(), track = input.facts.causal_tracks[0];
 delete track.target_front_line_id; delete track.contact_anchor;
 input.facts.geometries.at(-1).geometry.coordinates[1] = [2, 39.6];
 assert.throws(() => compileScenePlan(input), /CAUSAL_SUPPLIED_FRONT_CONTACT/);
 track.contact_kind = 'ARRIVAL';
 assert.equal(validateScenePlan(compileScenePlan(input)).valid, true);
});

test('integer chronology and target state windows reject premature control, reversals and out-of-bounds tracks', () => {
 const mutations = [
  track => {track.motion_start_frame = .5;}, track => {track.contact_frame = track.motion_start_frame;},
  track => {track.control_start_frame = track.contact_frame - 1;}, track => {track.control_end_frame = track.control_start_frame;},
  track => {track.end_frame = track.control_end_frame - 1;}, track => {track.control_end_frame = 124; track.end_frame = 124;},
  track => {track.control_start_frame = 35; track.contact_frame = 35;}, track => {track.end_frame = 421;}
 ];
 for (const mutate of mutations) {
  const input = causalInput(); mutate(input.facts.causal_tracks[0]);
  assert.throws(() => compileScenePlan(input), /CAUSAL_.*(INTEGER|ORDER|WINDOW)/);
 }
 const scene = copy(compileScenePlan(causalInput())); scene.causal_tracks[0].control_end_frame = 124; scene.causal_tracks[0].end_frame = 124;
 assert.throws(() => validateScenePlan(scene), /CAUSAL_STATE_WINDOW/);
});

test('actorless settlement/control tracks require NONE and actor actions require route/object references', () => {
 const input = causalInput(); input.facts.causal_tracks[1].action_kind = 'CONTROL_ONLY';
 assert.equal(validateScenePlan(compileScenePlan(input)).valid, true);
 for (const mutate of [track => {track.contact_kind = 'ARRIVAL';}, track => {track.action_kind = 'ADVANCE';},
  track => {track.route_id = 'ACTION_ROUTE'; track.object_id = 'OBJECT_ACTION_ROUTE';}]) {
  const bad = causalInput(); mutate(bad.facts.causal_tracks[1]);
  assert.throws(() => compileScenePlan(bad), /CAUSAL_ACTOR_BINDING/);
 }
});

test('explicit timing rejects incomplete or inconsistent duration, output fps and action totals', () => {
 for (const mutate of [timing => {delete timing.action_frames;}, timing => {timing.extra = 1;},
  timing => {timing.duration_seconds++;}, timing => {timing.event_start_frame++;}, timing => {timing.action_frames--;},
  timing => {timing.fps = 24; timing.duration_seconds = timing.total_frames / timing.fps;}, timing => {timing.final_hold_frames++;}]) {
  const input = causalInput(); mutate(input.facts.scene_timing);
  assert.throws(() => compileScenePlan(input), /SCENE_TIMING/);
 }
});

test('published schema accepts old and causal scenes and rejects malformed optional tracks', () => {
 const schema = fileURLToPath(new URL('../web/map_infographic_v1/planner_scene_v1.schema.json', import.meta.url));
 const scenes = ['A', 'B', 'C'].map(name => compileScenePlan(load('fixtures/SYNTHETIC_' + name + '.json')));
 scenes.push(load('fixtures/SCENE_PLAN.json'), compileScenePlan(causalInput()));
 const code = 'import sys,json\nfrom jsonschema import Draft202012Validator,FormatChecker\nv=Draft202012Validator(json.load(open(sys.argv[1])),format_checker=FormatChecker())\nscenes=json.loads(sys.argv[2])\nfor scene in scenes:v.validate(scene)\nfor field,value in [("represents_historical_unit",True),("contact_kind","BATTLE"),("unexpected",1)]:\n bad=json.loads(json.dumps(scenes[-1]));bad["causal_tracks"][0][field]=value;assert list(v.iter_errors(bad))\nbad=json.loads(json.dumps(scenes[-1]));del bad["causal_tracks"][0]["object_id"];assert list(v.iter_errors(bad))\nprint("CAUSAL_SCHEMA_PASS")\n';
 const result = spawnSync('/usr/bin/python3', ['-B', '-c', code, schema, JSON.stringify(scenes)], {encoding: 'utf8', timeout: 10000});
 assert.equal(result.status, 0, result.stderr);
 assert.match(result.stdout, /CAUSAL_SCHEMA_PASS/);
});
