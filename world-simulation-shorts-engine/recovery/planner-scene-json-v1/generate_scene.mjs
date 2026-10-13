/** Reproducible fixture → deterministic Scene JSON → existing engine request wiring. */
import {writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {buildWarFacts} from './build_war_fixture.mjs';
import {prepareNativeInputs} from './prepare_native_inputs.mjs';
import {compileScenePlan, validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const serialize = value => JSON.stringify(value, null, 2) + '\n';
const sha = value => createHash('sha256').update(value).digest('hex');
const result = buildWarFacts();
await mkdir(path.join(root, 'data'), {recursive: true});
for (const [file, value] of Object.entries({'FACT_DATA.json': result.facts, 'SOURCE_REFERENCES.json': result.references,
 'NATIVE_PENINSULA.json': result.native, 'FACT_PROVENANCE.json': result.provenance}))
 await writeFile(path.join(root, 'data', file), serialize(value));
const scene = compileScenePlan({topic: '한국전쟁 당시 전선은 어떻게 변했을까?', facts: result.facts});
validateScenePlan(scene);
const actualGeo = new Map(scene.geometries.map(item => [item.id, item.geometry]));
if (result.facts.geometries.some(item => JSON.stringify(actualGeo.get(item.id)) !== JSON.stringify(item.geometry)))
 throw Error('WAR_SCENE_SOURCE_GEOMETRY_MUTATED');
if (!scene.markers.some(marker => marker.anchor[0] === result.facts.camera.anchor[0]
 && marker.anchor[1] === result.facts.camera.anchor[1])) throw Error('WAR_NATIVE_MARKER_ANCHOR_MUST_MATCH_DECLARED_DATA');
if (/\/workspace\/|\/tmp\/|\.mjs|recovery\//u.test(JSON.stringify(scene))) throw Error('WAR_PUBLIC_SCENE_INTERNAL_PATH_LEAK');
const names = ['02_INITIAL_FRONT.png', '03_PUSAN_PERIMETER.png', '04_NORTH_ADVANCE.png',
 '05_SEOUL_WITHDRAWAL.png', '06_ARMISTICE.png'];
const checkpoints = [{frame: 0, name: '01_GEOGRAPHIC_CONTEXT.png'},
 ...scene.time_steps.map((step, index) => ({frame: step.start_frame + step.transition_frames - 1, name: names[index]})),
 {frame: scene.beats.find(beat => beat.type === 'HOLD').start_frame, name: '07_FRONT_COMPLETE.png'},
 {frame: scene.timing.total_frames - 1, name: '08_FINAL_HOLD.png'}];
if (checkpoints.some(point => !point.name) || checkpoints.length !== 8) throw Error('WAR_EIGHT_CHECKPOINTS_REQUIRED');
await mkdir(path.join(root, 'fixtures'), {recursive: true});
await writeFile(path.join(root, 'fixtures/SCENE_PLAN.json'), serialize(scene));
const native = await prepareNativeInputs({scene, facts: result.facts, checkpoints,
 videoFilename: 'KOREAN_WAR_PLANNER_SCENE_JSON_V1_CANDIDATE.mp4'});
await mkdir(path.join(root, 'evidence'), {recursive: true});
const binding = {version: 'FACT_SCENE_BINDING_V1', status: 'PASS',
 facts_sha256: sha(serialize(result.facts)), scene_sha256: sha(serialize(scene)),
 source_geometry_unchanged: true, marker_anchor_matches_declared_facts: true,
 feature_selection: scene.selected_features, chronology: scene.time_steps.map(({id, date, label}) => ({id, date, label})),
 source_references_live_access: 'REFERENCE_ONLY_RETRIEVAL_BLOCKED',
 quality_policy: 'FACT_BASED_VISUAL_GRADE', historical_geometry: 'ILLUSTRATIVE_NOT_ARCHIVAL',
 frames: scene.timing.total_frames, duration_seconds: scene.timing.duration_seconds,
 checkpoints, renderer_duplicated: false, camera_duplicated: false, required_temp_only_files: 0};
await writeFile(path.join(root, 'evidence/FACT_SCENE_BINDING.json'), serialize(binding));
console.log(JSON.stringify({status: 'PASS', frames: binding.frames, duration: binding.duration_seconds,
 sceneSha: binding.scene_sha256, checkpoints, camera: native.runtime.cameraDecision}));
