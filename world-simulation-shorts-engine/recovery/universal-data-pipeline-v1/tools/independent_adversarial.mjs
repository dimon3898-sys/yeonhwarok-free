/** Independent, bounded input probes. No renderer, job, GPU or deployment. */
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {analyzePrompt, canonicalJSON} from '../prompt_pipeline.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sha = raw => createHash('sha256').update(raw).digest('hex');
const read = name => JSON.parse(readFileSync(path.join(root, 'examples', name)));
const base = read('AVIATION_GERMANY.json');
const cases = [];
function probe(id, mutate = () => {}, expected = 'INVALID', seed = base, predicate = null) {
  const input = structuredClone(seed);
  mutate(input);
  const row = {id, expected};
  try {
    const result = analyzePrompt(input);
    row.status = result.status;
    row.renderableSceneIds = result.renderableSceneIds;
    row.blockedSceneIds = result.blockedSceneIds;
    row.issues = result.issues.map(({status, code, field}) => ({status, code, field}));
    row.pass = predicate ? predicate(result) : result.status === expected;
  } catch (error) {
    row.pass = false;
    row.uncaught = error.message;
  }
  cases.push(row);
}

for (const file of ['AVIATION_GERMANY.json', 'TRADE_CHILE.json', 'FICTIONAL_NAMIBIA.json'])
  probe('BASELINE_' + file, () => {}, 'PASS', read(file));
probe('UNKNOWN_RESOLUTION_FIELD', x => { x.resolution.fakeAntiAlias = true; }, 'UNSUPPORTED');
probe('SHADOWED_NATIVE_CONTEXT_UNKNOWN', x => { x.scenes[0].facts.camera.native_context = {secret_override: true}; }, 'UNSUPPORTED_OR_CONFLICT_WITH_EXPLICIT_FIELD_ERROR', base,
  result => ['UNSUPPORTED', 'CONFLICT'].includes(result.status) && result.renderRequests.length === 0 &&
    result.issues.some(x => x.code === 'UNSUPPORTED_FIELD' && x.field.endsWith('.secret_override')));
probe('UNDRAWN_TEXT_REJECTED', x => { x.scenes[0].facts.text = [{id: 'review_label', content: 'Must not be silently ignored', role: 'TITLE'}]; }, 'UNSUPPORTED');
probe('UNSUPPORTED_60FPS', x => { x.fps = 60; x.durationSeconds = 1.5; }, 'UNSUPPORTED');
probe('UNSUPPORTED_LOCAL_SCALE', x => { x.scenes[0].facts.scale = {preferred: 'LOCAL'}; }, 'UNSUPPORTED');
probe('NONOBJECT_RENDER_SETTINGS', x => { x.renderSettings = 'unsupported-string'; });
probe('CLIENT_EVIDENCE_REGISTRY_REJECTED', x => { x.evidenceRegistry = [{reviewStatus: 'VERIFIED'}]; }, 'UNSUPPORTED');
for (const field of ['geometries', 'locations', 'markers', 'routes', 'source_notes', 'stages'])
  probe('MALFORMED_NULL_RECORD_' + field, x => { x.scenes[0].facts[field] = [null]; });
probe('MALFORMED_HISTORY_BINDING', x => {
  x.simulationType = 'HISTORICAL'; x.scenes[0].facts.data_mode = 'PRODUCTION';
  x.scenes[0].historicalEvidence = [null];
});
probe('HISTORICAL_CLIENT_VERIFIED_CANNOT_APPROVE', () => {}, 'NOT_PASS', read('negative/SELF_ASSERTED_HISTORICAL_VERIFICATION.json'),
  result => result.status !== 'PASS' && result.renderRequests.length === 0);
probe('UNRELATED_QUALIFIED_SCENE_RETAINED', x => {
  x.durationSeconds = 6;
  const second = structuredClone(x.scenes[0]);
  second.sceneId = 'missing-route'; second.startFrame = 90; second.endFrame = 180;
  second.facts.routes = [];
  x.scenes.push(second);
}, 'PARTIAL_NEEDS_INPUT', base, result => result.status === 'NEEDS_INPUT' &&
  result.renderableSceneIds.length === 1 && result.renderableSceneIds[0] === base.scenes[0].sceneId &&
  result.blockedSceneIds.includes('missing-route') && result.partialRenderRequiresExplicitSceneSelection === true &&
  result.renderRequests[0].startFrame === 0 && result.renderRequests[0].endFrame === 90);
probe('DECLARED_BLOCKED_DEPENDENCY_PROPAGATES', x => {
  x.durationSeconds = 6;
  const second = structuredClone(x.scenes[0]);
  second.sceneId = 'missing-route'; second.startFrame = 90; second.endFrame = 180; second.facts.routes = [];
  x.scenes[0].dependsOn = ['missing-route']; x.scenes.push(second);
}, 'NO_RENDERABLE_DEPENDENT', base, result => result.status === 'NEEDS_INPUT' && result.renderRequests.length === 0 && result.blockedSceneIds.length === 2);

const report = {schema: 'WORLD_ENGINE_UDP_INDEPENDENT_ADVERSARIAL_PROBES_V1',
  status: cases.every(x => x.pass) ? 'PASS' : 'FAIL',
  tests: cases.length, failures: cases.filter(x => !x.pass).length,
  compilerSHA256: sha(readFileSync(path.join(root, 'prompt_pipeline.mjs'))),
  originalSourceModified: false, renderExecuted: false, gpuExecuted: false, paidWorkExecuted: false,
  cases};
writeFileSync(path.join(root, 'reports/INDEPENDENT_ADVERSARIAL_PROBES.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({status: report.status, tests: report.tests, failures: report.failures,
  failed: cases.filter(x => !x.pass)}));
if (report.status !== 'PASS') process.exitCode = 1;
