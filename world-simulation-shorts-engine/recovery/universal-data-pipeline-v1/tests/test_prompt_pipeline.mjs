/** Contract fixtures here are technical mocks, never historical evidence or rendered historical scenes. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import os from 'node:os';
import {analyzePrompt, canonicalJSON, parsePrompt, validateLegacyScene} from '../prompt_pipeline.mjs';
const here = path.dirname(fileURLToPath(import.meta.url));
const read = name => JSON.parse(fs.readFileSync(path.resolve(here, '../examples', name + '.json'), 'utf8'));
const hash = value => createHash('sha256').update(canonicalJSON(value)).digest('hex');
const base = () => read('AVIATION_GERMANY');
const check = (modify, status, code, value = base()) => {
  modify(value); const result = analyzePrompt(value);
  assert.equal(result.status, status, JSON.stringify(result.issues));
  if (code) assert(result.issues.some(row => row.code === code), JSON.stringify(result.issues));
  assert.equal(result.renderRequests.length, 0);
  return result;
};
for (const fixture of ['AVIATION_GERMANY', 'FICTIONAL_NAMIBIA', 'TRADE_CHILE']) {
  test(fixture + ': supplied prompt compiles through preserved Planner and exact engine binding', () => {
    const value = read(fixture), result = analyzePrompt(value), request = result.renderRequests[0];
    assert.equal(result.status, 'PASS', JSON.stringify(result.issues)); assert.equal(request.scene.metadata.schema, 'PLANNER_SCENE_JSON_V1');
    assert.equal(request.scene.timing.total_frames, 90); assert.equal(request.endFrame - request.startFrame, 90);
    assert.equal(request.scene.metadata.output.fps, 30); assert(request.enginePlan.plans.length > 0);
    assert.equal(request.scene.metadata.user_video_review_required, true); assert.equal(result.timelinePreserved, true);
    assert.deepEqual(request.scene.geometries.map(x => x.geometry), value.scenes[0].facts.geometries.map(x => x.geometry));
    assert(request.inputTrace.some(x => x.inputPath.includes('camera')));
    assert.equal(validateLegacyScene(request.scene).reinterpretation, false);
  });
}
test('structured single fenced prompt is accepted without AI reinterpretation', () => assert.equal(analyzePrompt('Production input\n```json\n' + JSON.stringify(base()) + '\n```').status, 'PASS'));
test('same input produces byte-deterministic result', () => assert.equal(canonicalJSON(analyzePrompt(base())), canonicalJSON(analyzePrompt(base()))));
test('canonical hash is independent of object key insertion order', () => {
  const a = base(), b = Object.fromEntries(Object.entries(a).reverse());
  assert.equal(analyzePrompt(a).inputSHA256, analyzePrompt(b).inputSHA256);
});
test('data modifications change both input digest and source geometry trace', () => {
  const a = base(), b = base(); b.scenes[0].facts.geometries.find(x => x.geometry.type === 'LineString').geometry.coordinates[1][0] += .02;
  const x = analyzePrompt(a), y = analyzePrompt(b); assert.equal(y.status, 'PASS'); assert.notEqual(x.inputSHA256, y.inputSHA256);
  assert.notEqual(x.renderRequests[0].sceneSHA256, y.renderRequests[0].sceneSHA256);
});
for (const [name, value, code] of [
  ['unstructured natural language', 'Make a Roman Empire video', 'FREE_NATURAL_LANGUAGE_NOT_SUPPORTED'],
  ['invalid JSON', '{"schema":}', 'Unexpected'],
  ['two fenced documents', '```json\n{}\n```\n```json\n{}\n```', 'SINGLE_JSON_FENCE_REQUIRED'],
  ['root array', '[]', 'INPUT_OBJECT_REQUIRED'],
  ['duplicate plain key', '{"schema":"x","schema":"y"}', 'DUPLICATE_JSON_KEY:schema'],
  ['escaped duplicate key', '{"schema":"x","sch\\u0065ma":"y"}', 'DUPLICATE_JSON_KEY:schema'],
  ['nested duplicate key', '{"a":{"x":1,"x":2}}', 'DUPLICATE_JSON_KEY:x'],
  ['infinite JSON number', '{"a":1e999}', 'NONFINITE_JSON_NUMBER'],
  ['prototype key', '{"__proto__":{}}', 'RESERVED_JSON_KEY'],
]) test('reject ' + name, () => {
  const result = analyzePrompt(value); assert.notEqual(result.status, 'PASS'); assert.equal(result.renderRequests.length, 0);
  if (code !== 'Unexpected') assert(result.issues.some(x => x.code.includes(code)), JSON.stringify(result.issues));
});
for (const [name, make] of [
  ['NaN', () => ({a: NaN})], ['Infinity', () => ({a: Infinity})], ['undefined', () => ({a: undefined})],
  ['BigInt', () => ({a: 1n})], ['Date object', () => ({a: new Date()})], ['Map object', () => ({a: new Map()})],
  ['cyclic object', () => { const x = {}; x.x = x; return x; }],
  ['sparse array', () => ({x: new Array(3)})], ['accessor', () => Object.defineProperty({}, 'x', {enumerable: true, get: () => 'not JSON'})],
]) test('plain JSON object guard ' + name, () => { const result = analyzePrompt(make()); assert.equal(result.status, 'INVALID'); assert.equal(result.renderRequests.length, 0); });

const bad = [
  ['unknown top field', x => {x.inventHistory = true;}, 'UNSUPPORTED', 'UNSUPPORTED_FIELD'],
  ['wrong schema', x => {x.schema = 'guess';}, 'INVALID', 'PROMPT_SCHEMA_REQUIRED'],
  ['missing title', x => {delete x.topic;}, 'NEEDS_INPUT', 'TOPIC_REQUIRED'],
  ['unknown mode', x => {x.simulationType = 'AUTOMATIC';}, 'INVALID', 'SIMULATION_TYPE_REQUIRED'],
  ['fps60 unsupported consumer', x => {x.fps = 60; x.durationSeconds = 1.5;}, 'UNSUPPORTED', 'PREVIEW_FPS'],
  ['fractional fps', x => {x.fps = 30.1;}, 'INVALID', 'FPS_RANGE'],
  ['landscape resolution', x => {x.resolution = {width: 1920, height: 1080};}, 'UNSUPPORTED', 'PREVIEW_RESOLUTION'],
  ['extra resolution parameter', x => {x.resolution.quality = 'ultra';}, 'UNSUPPORTED', 'UNSUPPORTED_FIELD'],
  ['render settings string', x => {x.renderSettings = 'invalid';}, 'INVALID', 'OBJECT_REQUIRED'],
  ['render settings null', x => {x.scenes[0].renderSettings = null;}, 'INVALID', 'OBJECT_REQUIRED'],
  ['duration/frame mismatch', x => {x.durationSeconds = 4;}, 'CONFLICT', 'TOTAL_FRAME_MISMATCH'],
  ['timeline gap', x => {x.scenes[0].startFrame = 1;}, 'CONFLICT', 'CONTIGUOUS_HALF_OPEN_TIMELINE'],
  ['reversed scene range', x => {x.scenes[0].startFrame = 90; x.scenes[0].endFrame = 0;}, 'CONFLICT', 'CONTIGUOUS_HALF_OPEN_TIMELINE'],
  ['source path injection', x => {x.scenes[0].renderSettings.sourceRegionId = '/etc/passwd';}, 'UNSUPPORTED', 'SOURCE_REGION_NOT_AVAILABLE'],
  ['unsupported camera path', x => {x.scenes[0].renderSettings.cameraPath = [];}, 'UNSUPPORTED', 'UNSUPPORTED_FIELD'],
  ['LOCAL scale', x => {x.scenes[0].facts.scale.preferred = 'LOCAL';}, 'UNSUPPORTED', 'REGIONAL_SCALE_ONLY'],
  ['unsupported physical speed', x => {x.scenes[0].facts.routes[0].speedKmh = 500;}, 'UNSUPPORTED', 'UNSUPPORTED_FIELD'],
  ['unconnected visible title', x => {x.scenes[0].facts.text = [{id: 'VISIBLE_TITLE', content: 'Must not vanish', role: 'TITLE'}];}, 'UNSUPPORTED', 'FEATURE_HAS_NO_PIXEL_CONSUMER'],
  ['military data not required for route', x => {x.scenes[0].facts.stages = [{id: 'bad', date: '2026-10-22', label: 'unused', area_refs: [], front_refs: []}];}, 'UNSUPPORTED', 'FEATURE_HAS_NO_PIXEL_CONSUMER'],
  ['ignored nested native context key', x => {x.scenes[0].facts.camera.native_context = {secret_override: true};}, 'CONFLICT', 'UNSUPPORTED_FIELD'],
  ['unknown geometry field', x => {x.scenes[0].facts.geometries[0].precision = 999;}, 'UNSUPPORTED', 'UNSUPPORTED_FIELD'],
  ['source unknown verified flag', x => {x.scenes[0].facts.source_notes[0].autoVerify = true;}, 'UNSUPPORTED', 'UNSUPPORTED_FIELD'],
  ['null facts', x => {x.scenes[0].facts = null;}, 'NEEDS_INPUT', 'FACTS_REQUIRED'],
  ['missing route', x => {x.scenes[0].facts.routes = [];}, 'NEEDS_INPUT', 'ROUTE_DATA_REQUIRED'],
  ['invalid source SHA', x => {x.scenes[0].facts.source_notes[0].sha256 = 'wrong';}, 'NEEDS_INPUT', 'PLANNER_SOURCE_SHA256_REQUIRED'],
  ['unmatched topic intent', x => {x.topic = 'Unknown subject';}, 'NEEDS_INPUT', 'DATA_REQUIRED'],
  ['duplicate data id', x => {x.scenes[0].facts.geometries.push(structuredClone(x.scenes[0].facts.geometries[0]));}, 'CONFLICT', 'DUPLICATE_ID'],
  ['wrong coordinates longitude', x => {x.scenes[0].facts.locations[0].anchor[0] = 181;}, 'INVALID', 'COORDINATE_RANGE'],
  ['wrong coordinates latitude', x => {x.scenes[0].facts.locations[0].anchor[1] = -91;}, 'INVALID', 'COORDINATE_RANGE'],
  ['wrong coordinate array arity', x => {x.scenes[0].facts.locations[0].anchor.push(1);}, 'INVALID', 'COORDINATE_RANGE'],
  ['reversed source time', x => {x.scenes[0].facts.time_range = {start: '2026-10-23', end: '2026-10-22'};}, 'CONFLICT', 'REVERSED_TIME_RANGE'],
  ['invalid Gregorian date', x => {x.scenes[0].facts.time_range.start = '2026-02-30';}, 'INVALID', 'ISO_DATE_REQUIRED'],
  ['approximate date not made precise', x => {x.scenes[0].facts.time_range.start = '2026';}, 'INVALID', 'ISO_DATE_REQUIRED'],
  ['BCE date unsupported', x => {x.scenes[0].facts.time_range.start = '27 BCE';}, 'UNSUPPORTED', 'ISO_DATE_REQUIRED'],
  ['antimeridian route', x => {x.scenes[0].facts.geometries.find(y => y.geometry.type === 'LineString').geometry.coordinates = [[179, 0], [-179, 0]];}, 'UNSUPPORTED', 'ANTIMERIDIAN_SEGMENT'],
  ['wrong route reference', x => {x.scenes[0].facts.routes[0].geometry_ref = 'missing';}, 'NEEDS_INPUT', 'PLANNER_ROUTE_GEOMETRY_REFERENCE_REQUIRED'],
  ['wrong route direction', x => {x.scenes[0].facts.routes[0].direction = 'BACKWARDS';}, 'NEEDS_INPUT', 'PLANNER_ROUTE_DIRECTION_REQUIRED'],
  ['oversized object graphic', x => {x.scenes[0].facts.routes[0].object_graphic.width_px = 81;}, 'INVALID', 'FLOW_GRAPHIC_GPU_LIMIT'],
  ['too many GPU graphic polygons', x => {x.scenes[0].facts.routes[0].object_graphic.polygons = Array(9).fill(x.scenes[0].facts.routes[0].object_graphic.polygons[0]);}, 'INVALID', 'FLOW_GRAPHIC_GPU_LIMIT'],
  ['too many GPU graphic vertices', x => {x.scenes[0].facts.routes[0].object_graphic.polygons[0].points = Array(13).fill([0, 0]);}, 'INVALID', 'FLOW_GRAPHIC_VERTEX_LIMIT'],
  ['invisible object alpha', x => {x.scenes[0].facts.routes[0].object_graphic.polygons[0].color[3] = 0;}, 'NEEDS_INPUT', 'FLOW_OBJECT_RGBA_COLOR_REQUIRED'],
  ['missing dependency', x => {x.scenes[0].dependsOn = ['absent'];}, 'INVALID', 'DEPENDENCY_REFERENCE'],
  ['self dependency', x => {x.scenes[0].dependsOn = [x.scenes[0].sceneId];}, 'INVALID', 'DEPENDENCY_REFERENCE'],
  ['explicit wrong internal timing', x => {x.scenes[0].facts.scene_timing = {fps: 30};}, 'NEEDS_INPUT', 'PLANNER_COMPLETE_SCENE_TIMING_REQUIRED'],
];
for (const [name, modify, status, code] of bad) test('validation: ' + name, () => check(modify, status, code));
for (const key of ['source_notes', 'geometries', 'locations', 'routes', 'stages', 'markers', 'text', 'metrics'])
  test('malformed null record is structured INVALID: ' + key, () => check(x => {x.scenes[0].facts[key] = [null];}, 'INVALID', 'OBJECT_REQUIRED'));
test('malformed source records cannot throw while historical evidence is inspected', () => check(x => {
  x.simulationType = 'HISTORICAL'; x.scenes[0].facts.data_mode = 'PRODUCTION'; x.scenes[0].facts.source_notes = [null];
  x.scenes[0].historicalEvidence = [{recordId: 'r', sourceId: 's', claimId: 'c'}];
}, 'INVALID', 'OBJECT_REQUIRED'));
test('malformed null evidence is structured INVALID', () => check(x => {x.simulationType = 'HISTORICAL'; x.scenes[0].facts.data_mode = 'PRODUCTION'; x.scenes[0].historicalEvidence = [null];}, 'INVALID', 'OBJECT_REQUIRED'));
test('malformed non-array evidence is structured INVALID', () => check(x => {x.simulationType = 'HISTORICAL'; x.scenes[0].facts.data_mode = 'PRODUCTION'; x.scenes[0].historicalEvidence = 'invalid';}, 'INVALID', 'EVIDENCE_ARRAY_REQUIRED'));
test('conflicting native context is not silently shadowed', () => check(x => {x.scenes[0].facts.camera.native_context = {country_ids: ['DIFFERENT']};}, 'CONFLICT', 'AMBIGUOUS_NATIVE_CONTEXT'));
test('minimum Flow GPU width is checked before pixel consumer', () => check(x => {x.scenes[0].facts.routes[0].object_graphic.width_px = 23;}, 'INVALID', 'FLOW_GRAPHIC_GPU_LIMIT'));

test('fiction has no history source requirement', () => assert.equal(analyzePrompt(read('FICTIONAL_NAMIBIA')).status, 'PASS'));
test('fiction cannot self declare observed PRODUCTION mode', () => check(x => {x.simulationType = 'FICTIONAL'; x.scenes[0].facts.data_mode = 'PRODUCTION';}, 'INVALID', 'FICTION_MODE_BINDING'));
test('history cannot self declare synthetic mode', () => check(x => {x.simulationType = 'HISTORICAL';}, 'INVALID', 'HISTORY_MODE_BINDING'));
test('GENERAL illustrative networks do not need military front data', () => {const x = base(); delete x.scenes[0].facts.stages; assert.equal(analyzePrompt(x).status, 'PASS');});
test('GENERAL observed claims require evidence instead of trusting VERIFIED', () => check(x => {x.scenes[0].facts.data_mode = 'PRODUCTION'; x.scenes[0].facts.source_notes[0].source_type = 'OFFICIAL_DATA'; x.scenes[0].facts.source_notes[0].verification_status = 'VERIFIED';}, 'NEEDS_INPUT', 'REVIEWED_EVIDENCE_REQUIRED'));
test('Korean missing control is not promoted from partial front to full area', () => {const x = analyzePrompt(read('KOREAN_WAR_MISSING_CONTROL')); assert.notEqual(x.status, 'PASS'); assert.equal(x.renderRequests.length, 0); assert(x.issues.some(y => y.code === 'TERRITORY_AND_FRONT_STATES_REQUIRED' || y.code === 'REVIEWED_EVIDENCE_REQUIRED'));});
test('Rome missing extent stays blocked without fabricated dates or geometry', () => {const source = read('ROMAN_EMPIRE_MISSING_EXTENT'), x = analyzePrompt(source); assert.equal(x.status, 'NEEDS_INPUT'); assert.equal(source.scenes[0].facts.geometries.length, 0); assert.equal(x.renderRequests.length, 0);});
test('existing supplied stages are sorted by verified date, preserving stage trace source index', () => {
  const value = read('FICTIONAL_NAMIBIA'); value.scenes[0].facts.stages.reverse(); const result = analyzePrompt(value);
  assert.equal(result.status, 'PASS'); const scene = result.renderRequests[0].scene;
  assert(scene.time_steps[0].date < scene.time_steps[1].date); assert(result.renderRequests[0].inputTrace.some(x => x.inputPath.endsWith('.facts.stages[1]')));
});
function twoScenes() {
  const value = base(); value.durationSeconds = 6; const second = structuredClone(value.scenes[0]);
  second.sceneId = 'independent_2'; second.startFrame = 90; second.endFrame = 180; value.scenes.push(second); return value;
}
test('qualified independent scene preserved while another needs input', () => {
  const value = twoScenes(); value.scenes[0].facts.routes = []; const result = analyzePrompt(value);
  assert.equal(result.status, 'NEEDS_INPUT'); assert.deepEqual(result.blockedSceneIds, [value.scenes[0].sceneId]);
  assert.deepEqual(result.renderableSceneIds, ['independent_2']); assert.equal(result.renderRequests[0].startFrame, 90);
  assert.equal(result.partialRenderRequiresExplicitSceneSelection, true); assert.equal(result.totalFrames, 180);
});
test('declared dependency propagates block without renumbering', () => {
  const value = twoScenes(); value.scenes[0].facts.routes = []; value.scenes[1].dependsOn = [value.scenes[0].sceneId];
  const result = analyzePrompt(value); assert.deepEqual(result.renderableSceneIds, []); assert(result.issues.some(x => x.code === 'DEPENDENCY_BLOCKED'));
});
test('cyclic dependency rejected', () => {
  const value = twoScenes(); value.scenes[0].dependsOn = ['independent_2']; value.scenes[1].dependsOn = [value.scenes[0].sceneId];
  const result = analyzePrompt(value); assert.equal(result.status, 'CONFLICT'); assert(result.issues.some(x => x.code === 'CYCLIC_SCENE_DEPENDENCY')); assert.equal(result.renderRequests.length, 0);
});
test('global timeline overlap never partly admitted', () => {const value = twoScenes(); value.scenes[1].startFrame = 89; const result = analyzePrompt(value); assert.equal(result.status, 'CONFLICT'); assert.equal(result.renderRequests.length, 0);});
test('unknown scene policy not ignored', () => check(x => {x.scenes[0].bypassChecks = true;}, 'UNSUPPORTED', 'UNSUPPORTED_FIELD'));
test('evidence registry cannot be smuggled through prompt', () => check(x => {x.evidenceRegistry = {records: []};}, 'UNSUPPORTED', 'UNSUPPORTED_FIELD'));
test('existing LINE_METRIC planner family not falsely advertised as pixel connected', () => check(x => {x.scenes[0].facts.subject.event_family = 'LINE_METRIC';}, 'UNSUPPORTED', 'FAMILY_NOT_CONNECTED'));

function mockHistory() {
  // In-memory logic-only mock, explicitly not a real historical source or video fixture.
  const value = read('FICTIONAL_NAMIBIA'); value.simulationType = 'HISTORICAL'; const facts = value.scenes[0].facts;
  facts.data_mode = 'PRODUCTION'; const source = facts.source_notes[0]; source.source_type = 'CONTRACT_MOCK_NOT_HISTORICAL_EVIDENCE';
  source.verification_status = 'VERIFIED'; source.source_reference = 'test://in-memory-evidence-gate'; source.original_sha256 = 'a'.repeat(64);
  const record = {id: 'mock-record', sourceId: source.id, claimId: 'mock-claim', reviewStatus: 'VERIFIED', sourceReference: source.source_reference,
    sourceSHA256: source.original_sha256, canonicalFactsSHA256: hash(facts), scope: 'FULL_TERRITORY', applicableDates: facts.time_range,
    geometrySHA256ById: Object.fromEntries(facts.geometries.map(x => [x.id, hash(x.geometry)]))};
  value.scenes[0].historicalEvidence = [{recordId: record.id, sourceId: record.sourceId, claimId: record.claimId, geometryIds: facts.geometries.map(x => x.id), stageIds: facts.stages.map(x => x.id)}];
  return {value, record};
}
test('evidence matching positive control is logic-only mock, not historical verification', () => {
  const {value, record} = mockHistory(), result = analyzePrompt(value, {evidenceRegistry: {records: [record]}});
  assert.equal(result.status, 'PASS', JSON.stringify(result.issues)); assert.equal(result.renderRequests[0].sourceManifest[0].originalBytesVerified, false);
});
for (const [name, modify, status, code] of [
  ['unregistered self VERIFIED', (value, record) => {record.id = 'other';}, 'NEEDS_INPUT', 'EVIDENCE_NOT_ADMITTED'],
  ['SHA mismatch', (value, record) => {record.sourceSHA256 = 'b'.repeat(64);}, 'CONFLICT', 'EVIDENCE_SOURCE_MISMATCH'],
  ['new geometry under old source', (value, record) => {value.scenes[0].facts.geometries[0].geometry.coordinates[0][1][0] += .001;}, 'NEEDS_INPUT', 'EVIDENCE_DATASET_NOT_REVIEWED'],
  ['source identity mismatch', (value, record) => {record.sourceReference += '/different';}, 'CONFLICT', 'EVIDENCE_SOURCE_MISMATCH'],
  ['missing exact facts binding', (value, record) => {delete record.canonicalFactsSHA256;}, 'NEEDS_INPUT', 'EVIDENCE_DATASET_NOT_REVIEWED'],
  ['partial line cannot certify area', (value, record) => {record.scope = 'PARTIAL_FRONT';}, 'NEEDS_INPUT', 'EVIDENCE_SCOPE_INSUFFICIENT'],
  ['event date outside map validity', (value, record) => {record.applicableDates = {start: '2020-01-01', end: '2020-01-02'};}, 'CONFLICT', 'EVIDENCE_DATE_MISMATCH'],
  ['geometry hash mismatch', (value, record) => {record.geometrySHA256ById[Object.keys(record.geometrySHA256ById)[0]] = 'c'.repeat(64);}, 'CONFLICT', 'EVIDENCE_GEOMETRY_MISMATCH'],
]) test('historical gate: ' + name, () => {
  const {value, record} = mockHistory(); modify(value, record); const result = analyzePrompt(value, {evidenceRegistry: [record]});
  assert.equal(result.status, status, JSON.stringify(result.issues)); assert(result.issues.some(x => x.code === code), JSON.stringify(result.issues)); assert.equal(result.renderRequests.length, 0);
});
test('every blocked issue contains a field path, reason, code and correction example', () => {
  const result = analyzePrompt(read('ROMAN_EMPIRE_MISSING_EXTENT'));
  for (const row of result.issues) { assert(row.field.startsWith('$')); assert(row.reason.length); assert(row.code.length); assert(row.example && typeof row.example === 'object'); }
});
test('CLI writes a new private output without stdout source disclosure', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'udp-cli-output-')), output = path.join(directory, 'analysis.json');
  const child = spawnSync(process.execPath, [path.resolve(here, '../prompt_pipeline.mjs'), '--input', path.resolve(here, '../examples/AVIATION_GERMANY.json'), '--output', output], {encoding: 'utf8'});
  assert.equal(child.status, 0, child.stderr); assert.equal(child.stdout, '');
  assert.equal(JSON.parse(fs.readFileSync(output, 'utf8')).status, 'PASS'); assert.equal(fs.statSync(output).mode & 0o777, 0o600);
});
test('CLI refuses to overwrite an existing Scene or artifact', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'udp-cli-preserve-')), output = path.join(directory, 'existing.json');
  const original = '{"preserve":"existing-source-or-result"}\n'; fs.writeFileSync(output, original, {mode: 0o600});
  const child = spawnSync(process.execPath, [path.resolve(here, '../prompt_pipeline.mjs'), '--input', path.resolve(here, '../examples/AVIATION_GERMANY.json'), '--output', output], {encoding: 'utf8'});
  assert.equal(child.status, 2); assert.equal(fs.readFileSync(output, 'utf8'), original);
  // Nested child stderr is not observable in this managed execution environment;
  // exit status and exact original bytes are the required non-overwrite assertions.
});
